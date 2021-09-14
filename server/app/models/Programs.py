
import ariblib.constants
import datetime
import re
import requests
import time
from datetime import timedelta
from tortoise import fields
from tortoise import models
from tortoise import timezone
from tortoise import transactions
from typing import Optional

from app.constants import CONFIG
from app.models import Channels
from app.utils import Logging
from app.utils import RunAsync
from app.utils import TSInformation
from app.utils import ZenkakuToHankaku
from app.utils.EDCB import EDCBUtil, CtrlCmdUtil


class Programs(models.Model):

    # テーブル設計は Notion を参照のこと
    id:str = fields.TextField(pk=True)
    channel_id:str = fields.TextField()
    title:str = fields.TextField()
    description:str = fields.TextField()
    detail:dict = fields.JSONField()
    start_time:datetime.datetime = fields.DatetimeField()
    end_time:datetime.datetime = fields.DatetimeField()
    duration:float = fields.FloatField()
    is_free:bool = fields.BooleanField()
    genre:list = fields.JSONField()
    video_type:str = fields.TextField()
    video_codec:str = fields.TextField()
    video_resolution:str = fields.TextField()
    primary_audio_type:str = fields.TextField()
    primary_audio_language:str = fields.TextField()
    primary_audio_sampling_rate:str = fields.TextField()
    secondary_audio_type:Optional[str] = fields.TextField(null=True)
    secondary_audio_language:Optional[str] = fields.TextField(null=True)
    secondary_audio_sampling_rate:Optional[str] = fields.TextField(null=True)


    @classmethod
    async def update(cls) -> None:
        """番組情報を更新する"""

        # 現在時刻のタイムスタンプ
        timestamp = time.time()

        Logging.info('Program updating...')

        # Mirakurun バックエンド
        if CONFIG['general']['backend'] == 'Mirakurun':
            await cls.updateFromMirakurun()

        # EDCB バックエンド
        elif CONFIG['general']['backend'] == 'EDCB':
            await cls.updateFromEDCB()

        Logging.info(f'Program update complete. ({round(time.time() - timestamp, 3)} sec)')


    @classmethod
    async def updateFromMirakurun(cls) -> None:
        """Mirakurun バックエンドから番組情報を取得し、更新する"""

        def IsMainProgram(program: dict) -> bool:
            """
            relatedItems からメインの番組情報か判定する
            EIT[p/f] 対応により増えた番組情報から必要なものだけを取得する
            ref: https://github.com/l3tnun/EPGStation/blob/master/src/model/epgUpdater/EPGUpdateManageModel.ts#L103-L136

            Args:
                program (dict): 番組情報の辞書
            Returns:
                bool: メインの番組情報かどうか
            """

            if 'relatedItems' not in program:
                return True

            for item in program['relatedItems']:

                # Mirakurun 3.8 以下では type が存在しない && relatedItems が機能していないので true を返す
                if 'type' not in item:
                    return True

                # 移動したイベントか？
                if item['type'] == 'movement':
                    return True

                # リレーの場合は無視
                if item['type'] == 'relay':
                    continue

                # type が shared でメインの放送か？
                if item['eventId'] == program['eventId'] and item['serviceId'] == program['serviceId']:
                    return True

            return False

        def MillisecondToDatetime(millisecond: int) -> datetime.datetime:
            """
            ミリ秒から Datetime を取得する

            Args:
                millisecond (int): ミリ秒

            Returns:
                datetime.datetime: Datetime（タイムゾーン付き）
            """

            return datetime.datetime.fromtimestamp(
                millisecond / 1000,  # ミリ秒なので秒に変換
                tz = timezone.get_default_timezone(),  # タイムゾーンを UTC+9（日本時間）に指定する
            )

        def ISO639CodeToJapanese(iso639_code: str) -> str:
            """
            ISO639 形式の言語コードを日本語に変換する

            Args:
                iso639_code (str): ISO639 形式の言語コード

            Returns:
                str: 日本語に訳した言語を示す文字列
            """

            if iso639_code == 'jpn':
                return '日本語'
            elif iso639_code == 'eng':
                return '英語'
            elif iso639_code == 'deu':
                return 'ドイツ語'
            elif iso639_code == 'fra':
                return 'フランス語'
            elif iso639_code == 'ita':
                return 'イタリア語'
            elif iso639_code == 'rus':
                return 'ロシア語'
            elif iso639_code == 'zho':
                return '中国語'
            elif iso639_code == 'kor':
                return '韓国語'
            elif iso639_code == 'spa':
                return 'スペイン語'
            else:
                return 'その他の言語'

        # Mirakurun の API から番組情報を取得する
        mirakurun_programs_api_url = f'{CONFIG["general"]["mirakurun_url"]}/api/programs'
        programs = (await RunAsync(requests.get, mirakurun_programs_api_url)).json()

        # 登録されている全ての番組を取得し、番組 ID (ex:NID32736-SID1024-EID11200) をキーに持つ辞書に変換する
        # EID (イベントID) だけでは一意にならないため、敢えて NID と SID も追加した ID としている
        db_programs = await Programs.all()
        duplicate_programs = {temp.id:temp for temp in db_programs}

        # このトランザクションは単にパフォーマンス向上のため
        async with transactions.in_transaction():

            # 番組情報ごとに
            for program_info in programs:

                # 既にある番組情報の更新かどうかのフラグ
                is_update = False

                # 番組タイトルがない（＝サブチャンネルでメインチャンネルの内容をそのまま放送している）を弾く
                if 'name' not in program_info:
                    continue

                # メインの番組情報でないなら弾く
                if IsMainProgram(program_info) is False:
                    continue

                # 既に同じ番組 ID の番組が DB に登録されているなら（情報の更新がない場合のみ）スキップ
                # DB は読み取るよりも書き込みの方が負荷と時間がかかるため、不要な書き込みは極力避ける
                duplicate_program_id = f'NID{program_info["networkId"]}-SID{program_info["serviceId"]:03d}-EID{program_info["eventId"]}'
                if duplicate_program_id in duplicate_programs:

                    # 重複している番組のモデルを取得
                    duplicate_program = duplicate_programs[duplicate_program_id]

                    # 番組終了時刻が現在時刻から1時間以上前ならレコードを削除
                    if timezone.now() - duplicate_program.end_time > timedelta(hours=1):
                        Logging.debug(f'Delete Program: {duplicate_program.id}')
                        await duplicate_program.delete()

                    # 番組タイトル・番組概要・番組詳細・番組開始時刻・番組終了時刻がすべて同じならスキップ
                    if (duplicate_program.title == ZenkakuToHankaku(program_info['name'])) and \
                    (duplicate_program.description == ZenkakuToHankaku(program_info['description'])) and \
                    (len(duplicate_program.detail) == len(program_info.get('extended', {}))) and \
                    (duplicate_program.start_time == MillisecondToDatetime(program_info['startAt'])) and \
                    (duplicate_program.end_time == MillisecondToDatetime(program_info['startAt'] + program_info['duration'])):

                        # 次のループへ
                        continue

                    # すでに存在する番組情報を更新する
                    else:
                        is_update = True

                # 番組終了時刻が現在時刻より1時間以上前な番組を弾く
                # 既に終わった番組を登録してもしょうがないし、番組を DB に入れれば入れるほど重くなるので不要なものは減らしたい
                if time.time() - ((program_info['startAt'] + program_info['duration']) / 1000) > (60 * 60):
                    continue

                # 番組に紐づくチャンネルを取得
                channel = await Channels.filter(network_id=program_info['networkId'], service_id=program_info['serviceId']).first()
                if channel is None:  # 登録されていないチャンネルの番組を弾く（ワンセグやデータ放送など）
                    continue

                if is_update is False:
                    # 新しい番組のレコードを作成
                    program = Programs()
                else:
                    # 既に存在する番組のレコードを設定
                    program = duplicate_program

                # 取得してきた値を設定
                program.id = f'{channel.id}-EID{str(program_info["eventId"])}'  # チャンネルの ID に EID (イベントID) を追加する
                program.channel_id = channel.channel_id
                program.title = ZenkakuToHankaku(program_info['name'])
                program.description = ZenkakuToHankaku(program_info['description'])
                program.start_time = MillisecondToDatetime(program_info['startAt'])
                program.end_time = MillisecondToDatetime(program_info['startAt'] + program_info['duration'])
                program.duration = float(program_info['duration'] / 1000)  # ミリ秒なので秒に変換
                program.is_free = program_info['isFree']
                program.video_type = ariblib.constants.COMPONENT_TYPE[program_info['video']['streamContent']][program_info['video']['componentType']]
                program.video_codec = program_info['video']['type']
                program.video_resolution = program_info['video']['resolution']

                # 音声情報
                ## Mirakurun 3.9 以降向け
                ## ref: https://github.com/Chinachu/Mirakurun/blob/master/api.d.ts#L88-L105
                if 'audios' in program_info:
                    ## 主音声
                    program.primary_audio_type = ariblib.constants.COMPONENT_TYPE[0x02][program_info['audios'][0]['componentType']]
                    program.primary_audio_language = ISO639CodeToJapanese(program_info['audios'][0]['langs'][0])
                    program.primary_audio_sampling_rate = str(int(program_info['audios'][0]['samplingRate'] / 1000)) + 'kHz'  # kHz に変換
                    ## デュアルモノのみ
                    if program.primary_audio_type == '1/0+1/0モード(デュアルモノ)':
                        if len(program_info['audios'][0]['langs']) == 2:  # 他言語の定義が存在すれば
                            program.primary_audio_language = \
                                program.primary_audio_language + '+' + ISO639CodeToJapanese(program_info['audios'][0]['langs'][1])
                        else:
                            program.primary_audio_language = program.primary_audio_language + '+英語'  # 英語で固定
                    ## 副音声（存在する場合）
                    if len(program_info['audios']) == 2:
                        program.secondary_audio_type = ariblib.constants.COMPONENT_TYPE[0x02][program_info['audios'][1]['componentType']]
                        program.secondary_audio_language = ISO639CodeToJapanese(program_info['audios'][1]['langs'][0])
                        program.secondary_audio_sampling_rate = str(int(program_info['audios'][1]['samplingRate'] / 1000)) + 'kHz'  # kHz に変換
                ## Mirakurun 3.8 以下向け（フォールバック）
                else:
                    ## 主音声
                    program.primary_audio_type = ariblib.constants.COMPONENT_TYPE[0x02][program_info['audio']['componentType']]
                    program.primary_audio_language = '日本語'  # 日本語で固定
                    program.primary_audio_sampling_rate = str(int(program_info['audio']['samplingRate'] / 1000)) + 'kHz'  # kHz に変換
                    ## デュアルモノのみ
                    if program.primary_audio_type == '1/0+1/0モード(デュアルモノ)':
                        program.primary_audio_language = '日本語+英語'  # 日本語+英語で固定
                    ## 副音声の情報は常に存在しないため省略

                # 番組詳細
                if 'extended' not in program_info:
                    ## extended がない場合
                    program.detail = dict()  # 空の辞書を入れる
                else:
                    ## 全角→半角へ変換するため、敢えて一度ばらしてから再構築する
                    program.detail = dict()  # 辞書を定義
                    for head, text in program_info['extended'].items():

                        # 見出しと本文
                        head_han = ZenkakuToHankaku(head).replace('◇', '')  # ◇ を取り除く
                        text_han = ZenkakuToHankaku(text)
                        program.detail[head_han] = text_han

                        # 番組概要が空の場合、番組詳細の最初の本文を概要として使う
                        # 空でまったく情報がないよりかは良いはず
                        if program.description == '':
                            program.description == text_han

                # ジャンル
                if 'genres' not in program_info:
                    ## genres がない場合
                    program.genre = list()  # 空のリストを入れる
                else:
                    ## 数字だけでは開発中の視認性が低いのでテキストに変換する
                    program.genre = list() # リストを定義
                    for genre in program_info['genres']:

                        # major … 大分類
                        # middle … 中分類
                        genre_dict = {
                            'major': ariblib.constants.CONTENT_TYPE[genre['lv1']][0],
                            'middle': ariblib.constants.CONTENT_TYPE[genre['lv1']][1][genre['lv2']],
                        }

                        # ／ を・に置換
                        genre_dict['major'] = genre_dict['major'].replace('／', '・')
                        genre_dict['middle'] = genre_dict['middle'].replace('／', '・')

                        # BS/地上デジタル放送用番組付属情報がジャンルに含まれている場合、user_nibble から値を取得して書き換える
                        # たとえば「中止の可能性あり」や「延長の可能性あり」といった情報が取れる
                        if genre_dict['major'] == '拡張':
                            if genre_dict['middle'] == 'BS/地上デジタル放送用番組付属情報':
                                user_nibble = (genre['un1'] * 0x10) + genre['un2']
                                genre_dict['middle'] = ariblib.constants.USER_TYPE[user_nibble]
                            # 「拡張」はあるがBS/地上デジタル放送用番組付属情報でない場合はなんの値なのかわからないのでパス
                            else:
                                continue

                        program.genre.append(genre_dict)

                if is_update is False:
                    Logging.debug(f'Add Program: {program.id}')
                else:
                    Logging.debug(f'Update Program: {program.id}')

                # レコードを保存する
                await program.save()

            # Mirakurun の番組 ID (ex:327360102411200) をキーに持つ辞書に変換する
            mirakurun_programs = {temp['id']:temp for temp in programs}

            # DB に登録されているが Mirakurun の API レスポンスに存在しない番組を洗い出し、削除する
            # Mirakurun の API レスポンスに存在しないという事は何らかの理由で削除された番組なので、残しておくと幽霊化する
            for db_program in db_programs:

                # NID・SID・EID を抽出
                network_id, service_id, event_id = re.match(r'^NID([0-9]+)-SID([0-9]+)-EID([0-9]+)$', db_program.id).groups()

                # Mirakurun 形式の番組 ID を算出
                mirakurun_program_id = int(str(network_id).zfill(5) + str(service_id).zfill(5) + str(event_id).zfill(5))

                # Mirakurun の API レスポンスに存在しないなら番組を削除する
                if mirakurun_program_id not in mirakurun_programs:
                    Logging.debug(f'Delete Program (ghost): {db_program.id}')
                    await db_program.delete()


    @classmethod
    async def updateFromEDCB(cls) -> None:
        """EDCB バックエンドから番組情報を取得し、更新する"""

        # CtrlCmdUtil を初期化
        edcb = CtrlCmdUtil()
        edcb.setNWSetting(CONFIG['general']['edcb_host'], CONFIG['general']['edcb_port'])

        # 開始時間未定をのぞく全番組を取得する (リスト引数の前2要素は全番組、残り2要素は全期間を意味)
        program_services = await edcb.sendEnumPgInfoEx([0xffffffffffff, 0xffffffffffff, 1, 0x7fffffffffffffff]) or []

        # このトランザクションは単にパフォーマンス向上のため
        async with transactions.in_transaction():

            # この変数から更新不要な番組情報を削除していき、残った番組情報を最後にまとめて削除する
            duplicate_programs = {temp.id:temp for temp in await Programs.all()}

            # チャンネルごとに
            for program_service in program_services:

                # NID・SID・TSID を取得
                nid = program_service['service_info']['onid']
                sid = program_service['service_info']['sid']
                tsid = program_service['service_info']['tsid']

                # チャンネル情報を取得
                channel = await Channels.filter(network_id = nid, service_id = sid).first()
                if channel is None:  # 登録されていないチャンネルの番組を弾く（ワンセグやデータ放送など）
                    continue

                # 番組情報ごとに
                for program_info in program_service['event_list']:

                    # メインの番組でないなら弾く
                    group_info = program_info.get('event_group_info')
                    if (group_info is not None and len(group_info['event_data_list']) == 1 and
                       (group_info['event_data_list'][0]['onid'] != nid or
                        group_info['event_data_list'][0]['tsid'] != tsid or
                        group_info['event_data_list'][0]['sid'] != sid or
                        group_info['event_data_list'][0]['eid'] != program_info['eid'])):
                        continue

                    # 番組タイトル・番組概要
                    title = ''  # デフォルト値
                    description = ''  # デフォルト値
                    if 'short_info' in program_info:
                        title = ZenkakuToHankaku(program_info['short_info']['event_name'])
                        description = ZenkakuToHankaku(program_info['short_info']['text_char'])

                    # 番組詳細
                    detail = dict()  # デフォルト値
                    if 'ext_info' in program_info:
                        for head, text in EDCBUtil.parseProgramExtendedText(program_info['ext_info']['text_char']).items():

                            # 見出しと本文
                            head_han = ZenkakuToHankaku(head).replace('◇', '')  # ◇ を取り除く
                            if head_han == '':  # 見出しが空の場合、固定で「番組内容」としておく
                                head_han = '番組内容'
                            text_han = ZenkakuToHankaku(text)
                            detail[head_han] = text_han

                            # 番組概要が空の場合、番組詳細の最初の本文を概要として使う
                            # 空でまったく情報がないよりかは良いはず
                            if description == '':
                                description = text

                    # 番組開始時刻
                    start_time = program_info['start_time']

                    # 番組終了時刻
                    ## 終了時間未定の場合、とりあえず5分とする
                    end_time = start_time + timedelta(seconds = program_info.get('duration_sec', 300))

                    # 番組終了時刻が現在時刻より1時間以上前な番組を弾く
                    if datetime.datetime.now(CtrlCmdUtil.TZ) - end_time > timedelta(hours = 1):
                        continue

                    # ここからは追加か更新か更新不要のいずれか

                    program_id = f'NID{nid}-SID{sid:03d}-EID{program_info["eid"]}'
                    duplicate_program = duplicate_programs.get(program_id)
                    if (duplicate_program is not None and
                        duplicate_program.title == title and
                        duplicate_program.description == description and
                        len(duplicate_program.detail) == len(detail) and
                        duplicate_program.start_time == start_time and
                        duplicate_program.end_time == end_time):
                        # 更新不要
                        del duplicate_programs[program_id]
                        continue

                    if duplicate_program is None:
                        program = Programs()
                    else:
                        del duplicate_programs[program_id]
                        program = duplicate_program

                    program.id = program_id
                    program.channel_id = channel.channel_id
                    program.title = title
                    program.description = description
                    program.detail = detail
                    program.start_time = start_time
                    program.end_time = end_time
                    program.duration = (end_time - start_time).total_seconds()
                    program.is_free = program_info['free_ca_flag'] == 0

                    program.video_type = ''
                    program.video_codec = ''
                    program.video_resolution = ''
                    component_info = program_info.get('component_info')
                    if component_info is not None:
                        component_types = ariblib.constants.COMPONENT_TYPE.get(component_info['stream_content'])
                        if component_types is not None:
                            program.video_type = component_types.get(component_info['component_type'], '')
                        program.video_codec = TSInformation.STREAM_CONTENT.get(component_info['stream_content'], '')
                        program.video_resolution = TSInformation.COMPONENT_TYPE.get(component_info['component_type'], '')

                    program.primary_audio_type = ''
                    program.primary_audio_language = ''
                    program.primary_audio_sampling_rate = ''
                    audio_info = program_info.get('audio_info')
                    if audio_info is not None:
                        if len(audio_info['component_list']) > 0:
                            audio_component_info = audio_info['component_list'][0]
                            program.primary_audio_type = ariblib.constants.COMPONENT_TYPE[0x02].get(audio_component_info['component_type'], '')
                            program.primary_audio_sampling_rate = ariblib.constants.SAMPLING_RATE.get(audio_component_info['sampling_rate'], '')
                            # 言語コードは分からないので日本語か英語で固定
                            if audio_component_info['component_type'] == 0x02:
                                program.primary_audio_language = '日本語+' + ('英語' if audio_component_info['es_multi_lingual_flag'] != 0 else '副音声')
                            else:
                                program.primary_audio_language = '日本語'

                            if len(audio_info['component_list']) > 1:
                                audio_component_info = audio_info['component_list'][1]
                                program.secondary_audio_type = ariblib.constants.COMPONENT_TYPE[0x02].get(audio_component_info['component_type'], '')
                                program.secondary_audio_sampling_rate = ariblib.constants.SAMPLING_RATE.get(audio_component_info['sampling_rate'], '')
                                if audio_component_info['component_type'] == 0x02:
                                    program.secondary_audio_language = '日本語+' + ('英語' if audio_component_info['es_multi_lingual_flag'] != 0 else '副音声')
                                else:
                                    # 英語かもしれないし解説かもしれない
                                    program.secondary_audio_language = '副音声'

                    program.genre = []
                    content_info = program_info.get('content_info')
                    if content_info is not None:
                        for content_data in content_info['nibble_list']:
                            genre_dict = {'major': '', 'middle': ''}
                            genre_tuple = ariblib.constants.CONTENT_TYPE.get(content_data['content_nibble'] >> 8)
                            if genre_tuple is not None:
                                genre_dict['major'] = genre_tuple[0].replace('／', '・')
                                if content_data['content_nibble'] == 0x0e00:
                                    user_nibble = (content_data['user_nibble'] >> 8 << 4) | (content_data['user_nibble'] & 0xf)
                                    genre_dict['middle'] = ariblib.constants.USER_TYPE.get(user_nibble, '')
                                elif content_data['content_nibble'] >> 8 == 0x0e:
                                    continue
                                else:
                                    genre_dict['middle'] = genre_tuple[1].get(content_data['content_nibble'] & 0xf, '').replace('／', '・')
                            program.genre.append(genre_dict)

                    if duplicate_program is None:
                        Logging.debug(f'Add Program: {program.id}')
                    else:
                        Logging.debug(f'Update Program: {program.id}')

                    await program.save()

            # 重複している番組をまとめて削除
            for duplicate_program in duplicate_programs.values():
                Logging.debug(f'Delete Program: {duplicate_program.id}')
                await duplicate_program.delete()
