
import ariblib.constants
import datetime
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
    network_id:int = fields.IntField()
    service_id:int = fields.IntField()
    event_id:int = fields.IntField()
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

        # Mirakurun の API から番組情報を取得する
        mirakurun_programs_api_url = f'{CONFIG["general"]["mirakurun_url"]}/api/programs'
        programs = (await RunAsync(requests.get, mirakurun_programs_api_url)).json()

        # このトランザクションは単にパフォーマンス向上のため
        async with transactions.in_transaction():

            # この変数から更新or更新不要な番組情報を削除していき、残った古い番組情報を最後にまとめて削除する
            duplicate_programs = {temp.id:temp for temp in await Programs.all()}

            # チャンネル情報を取得
            # NID32736-SID1024 形式の ID をキーにした辞書にまとめる
            channels = {temp.id:temp for temp in await Channels.all()}

            # 番組情報ごとに
            for program_info in programs:

                # この番組が放送されるチャンネルの情報を取得
                channel = channels.get(f'NID{program_info["networkId"]}-SID{program_info["serviceId"]:03d}', None)

                # 登録されていないチャンネルの番組を弾く（ワンセグやデータ放送など）
                if channel is None:
                    continue

                # メインの番組情報でないなら弾く
                if IsMainProgram(program_info) is False:
                    continue

                # 番組タイトルがない（＝サブチャンネルでメインチャンネルの内容をそのまま放送している）を弾く
                if 'name' not in program_info:
                    continue

                # 重複する番組情報が登録されているかの判定に使うため、ここで先に番組情報を取得する

                # 番組タイトル・番組概要
                title = ZenkakuToHankaku(program_info['name'])
                description = ZenkakuToHankaku(program_info['description'])

                # 番組詳細
                detail = dict()  # デフォルト値
                if 'extended' in program_info:

                    # 番組詳細の見出しと本文の辞書ごとに
                    for head, text in program_info['extended'].items():

                        # 見出しと本文
                        head_han = ZenkakuToHankaku(head).replace('◇', '')  # ◇ を取り除く
                        text_han = ZenkakuToHankaku(text)
                        detail[head_han] = text_han

                        # 番組概要が空の場合、番組詳細の最初の本文を概要として使う
                        # 空でまったく情報がないよりかは良いはず
                        if description.strip() == '':
                            description = text_han

                # 番組開始時刻・番組終了時刻
                start_time = MillisecondToDatetime(program_info['startAt'])
                end_time = MillisecondToDatetime(program_info['startAt'] + program_info['duration'])

                # 番組終了時刻が現在時刻より1時間以上前な番組を弾く
                if datetime.datetime.now(timezone.get_default_timezone()) - end_time > timedelta(hours = 1):
                    continue

                # ***** ここからは 追加・更新・更新不要 のいずれか *****

                # DB は読み取りよりも書き込みの方が負荷と時間がかかるため、不要な書き込みは極力避ける

                # 番組 ID
                program_id = f'NID{program_info["networkId"]}-SID{program_info["serviceId"]:03d}-EID{program_info["eventId"]}'

                # 重複する番組 ID の番組情報があれば取得する
                duplicate_program = duplicate_programs.get(program_id)

                # 重複する番組情報があり、かつタイトル・番組概要・番組詳細・番組開始時刻・番組終了時刻が全て同じ
                if (duplicate_program is not None and
                    duplicate_program.title == title and
                    duplicate_program.description == description and
                    len(duplicate_program.detail) == len(detail) and
                    duplicate_program.start_time == start_time and
                    duplicate_program.end_time == end_time):

                    # 更新不要なのでスキップ
                    del duplicate_programs[program_id]
                    continue

                # 重複する番組情報が存在しない（追加）
                if duplicate_program is None:
                    program = Programs()

                # 重複する番組情報が存在する（更新）
                else:
                    del duplicate_programs[program_id]  # 参照を削除
                    program = duplicate_program

                # 取得してきた値を設定
                program.id = program_id
                program.network_id = channel.network_id
                program.service_id = channel.service_id
                program.event_id = program_info['eventId']
                program.channel_id = channel.channel_id
                program.title = title
                program.description = description
                program.detail = detail
                program.start_time = start_time
                program.end_time = end_time
                program.duration = (end_time - start_time).total_seconds()
                program.is_free = program_info['isFree']

                # 映像情報
                program.video_type = ariblib.constants.COMPONENT_TYPE[program_info['video']['streamContent']][program_info['video']['componentType']]
                program.video_codec = program_info['video']['type']
                program.video_resolution = program_info['video']['resolution']

                # 音声情報
                program.primary_audio_type = ''  # デフォルト値
                program.primary_audio_language = ''  # デフォルト値
                program.primary_audio_sampling_rate = ''  # デフォルト値

                ## Mirakurun 3.9 以降向け
                ## ref: https://github.com/Chinachu/Mirakurun/blob/master/api.d.ts#L88-L105
                if 'audios' in program_info:

                    ## 主音声
                    program.primary_audio_type = ariblib.constants.COMPONENT_TYPE[0x02][program_info['audios'][0]['componentType']]
                    program.primary_audio_language = TSInformation.getISO639LanguageCodeName(program_info['audios'][0]['langs'][0])
                    program.primary_audio_sampling_rate = str(int(program_info['audios'][0]['samplingRate'] / 1000)) + 'kHz'  # kHz に変換
                    ## デュアルモノのみ
                    if program.primary_audio_type == '1/0+1/0モード(デュアルモノ)':
                        if len(program_info['audios'][0]['langs']) == 2:  # 他言語の定義が存在すれば
                            program.primary_audio_language += '+' + TSInformation.getISO639LanguageCodeName(program_info['audios'][0]['langs'][1])
                        else:
                            program.primary_audio_language = program.primary_audio_language + '+副音声'  # 副音声で固定

                    ## 副音声（存在する場合）
                    if len(program_info['audios']) == 2:
                        program.secondary_audio_type = ariblib.constants.COMPONENT_TYPE[0x02][program_info['audios'][1]['componentType']]
                        program.secondary_audio_language = TSInformation.getISO639LanguageCodeName(program_info['audios'][1]['langs'][0])
                        program.secondary_audio_sampling_rate = str(int(program_info['audios'][1]['samplingRate'] / 1000)) + 'kHz'  # kHz に変換
                        ## デュアルモノのみ
                        if program.secondary_audio_type == '1/0+1/0モード(デュアルモノ)':
                            if len(program_info['audios'][1]['langs']) == 2:  # 他言語の定義が存在すれば
                                program.secondary_audio_language += '+' + TSInformation.getISO639LanguageCodeName(program_info['audios'][1]['langs'][1])
                            else:
                                program.secondary_audio_language = program.secondary_audio_language + '+副音声'  # 副音声で固定

                ## Mirakurun 3.8 以下向け（フォールバック）
                else:

                    ## 主音声
                    ## 副音声の情報は常に存在しないため省略
                    program.primary_audio_type = ariblib.constants.COMPONENT_TYPE[0x02][program_info['audio']['componentType']]
                    program.primary_audio_sampling_rate = str(int(program_info['audio']['samplingRate'] / 1000)) + 'kHz'  # kHz に変換
                    ## Mirakurun 3.8 以下では言語コードが取得できないため、日本語で固定する
                    program.primary_audio_language = '日本語'
                    ## デュアルモノのみ
                    if program.primary_audio_type == '1/0+1/0モード(デュアルモノ)':
                        program.primary_audio_language = '日本語+英語'  # 日本語+英語で固定

                # ジャンル
                ## 数字だけでは開発中の視認性が低いのでテキストに変換する
                program.genre = list()  # デフォルト値
                if 'genres' in program_info:
                    for genre in program_info['genres']:  # ジャンルごとに

                        # major … 大分類
                        # middle … 中分類
                        genre_dict = {
                            'major': ariblib.constants.CONTENT_TYPE[genre['lv1']][0].replace('／', '・'),
                            'middle': ariblib.constants.CONTENT_TYPE[genre['lv1']][1][genre['lv2']].replace('／', '・'),
                        }

                        # BS/地上デジタル放送用番組付属情報がジャンルに含まれている場合、user_nibble から値を取得して書き換える
                        # たとえば「中止の可能性あり」や「延長の可能性あり」といった情報が取れる
                        if genre_dict['major'] == '拡張':
                            if genre_dict['middle'] == 'BS/地上デジタル放送用番組付属情報':
                                user_nibble = (genre['un1'] * 0x10) + genre['un2']
                                genre_dict['middle'] = ariblib.constants.USER_TYPE.get(user_nibble, '')
                            # 「拡張」はあるがBS/地上デジタル放送用番組付属情報でない場合はなんの値なのかわからないのでパス
                            else:
                                continue

                        # ジャンルを追加
                        program.genre.append(genre_dict)

                # 番組情報をデータベースに保存する
                if duplicate_program is None:
                    Logging.debug(f'Add Program: {program.id}')
                else:
                    Logging.debug(f'Update Program: {program.id}')

                await program.save()

            # この時点で残存している番組情報は放送が終わって EPG から削除された番組なので、まとめて削除する
            # ここで削除しないと終了した番組の情報が幽霊のように残り続ける事になり、結果 DB が肥大化して遅くなってしまう
            for duplicate_program in duplicate_programs.values():
                Logging.debug(f'Delete Program: {duplicate_program.id}')
                await duplicate_program.delete()


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

            # この変数から更新or更新不要な番組情報を削除していき、残った古い番組情報を最後にまとめて削除する
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

                    # 重複する番組情報が登録されているかの判定に使うため、ここで先に番組情報を取得する

                    # 番組タイトル・番組概要
                    title = ''  # デフォルト値
                    description = ''  # デフォルト値
                    if 'short_info' in program_info:
                        title = ZenkakuToHankaku(program_info['short_info']['event_name'])
                        description = ZenkakuToHankaku(program_info['short_info']['text_char'])

                    # 番組詳細
                    detail = dict()  # デフォルト値
                    if 'ext_info' in program_info:

                        # 番組詳細テキストから取得した、見出しと本文の辞書ごとに
                        for head, text in EDCBUtil.parseProgramExtendedText(program_info['ext_info']['text_char']).items():

                            # 見出しと本文
                            head_han = ZenkakuToHankaku(head).replace('◇', '')  # ◇ を取り除く
                            if head_han == '':  # 見出しが空の場合、固定で「番組内容」としておく
                                head_han = '番組内容'
                            text_han = ZenkakuToHankaku(text)
                            detail[head_han] = text_han

                            # 番組概要が空の場合、番組詳細の最初の本文を概要として使う
                            # 空でまったく情報がないよりかは良いはず
                            if description.strip() == '':
                                description = text_han

                    # 番組開始時刻
                    start_time:datetime.datetime = program_info['start_time']

                    # 番組終了時刻
                    ## 終了時間未定の場合、とりあえず5分とする
                    end_time:datetime.datetime = start_time + timedelta(seconds = program_info.get('duration_sec', 300))

                    # 番組終了時刻が現在時刻より1時間以上前な番組を弾く
                    if datetime.datetime.now(CtrlCmdUtil.TZ) - end_time > timedelta(hours = 1):
                        continue

                    # ***** ここからは 追加・更新・更新不要 のいずれか *****

                    # DB は読み取りよりも書き込みの方が負荷と時間がかかるため、不要な書き込みは極力避ける

                    # 番組 ID
                    program_id = f'NID{nid}-SID{sid:03d}-EID{program_info["eid"]}'

                    # 重複する番組 ID の番組情報があれば取得する
                    duplicate_program = duplicate_programs.get(program_id)

                    # 重複する番組情報があり、かつタイトル・番組概要・番組詳細・番組開始時刻・番組終了時刻が全て同じ
                    if (duplicate_program is not None and
                        duplicate_program.title == title and
                        duplicate_program.description == description and
                        len(duplicate_program.detail) == len(detail) and
                        duplicate_program.start_time == start_time and
                        duplicate_program.end_time == end_time):

                        # 更新不要なのでスキップ
                        del duplicate_programs[program_id]
                        continue

                    # 重複する番組情報が存在しない（追加）
                    if duplicate_program is None:
                        program = Programs()

                    # 重複する番組情報が存在する（更新）
                    else:
                        del duplicate_programs[program_id]  # 参照を削除
                        program = duplicate_program

                    # 取得してきた値を設定
                    program.id = program_id
                    program.network_id = channel.network_id
                    program.service_id = channel.service_id
                    program.event_id = program_info['eid']
                    program.channel_id = channel.channel_id
                    program.title = title
                    program.description = description
                    program.detail = detail
                    program.start_time = start_time
                    program.end_time = end_time
                    program.duration = (end_time - start_time).total_seconds()
                    program.is_free = program_info['free_ca_flag'] == 0  # free_ca_flag が 0 であれば無料放送

                    # 映像情報
                    ## テキストにするために ariblib.constants や TSInformation の値を使う
                    program.video_type = ''  # デフォルト値
                    program.video_codec = ''  # デフォルト値
                    program.video_resolution = ''  # デフォルト値
                    component_info = program_info.get('component_info')
                    if component_info is not None:
                        ## 映像の種類
                        component_types = ariblib.constants.COMPONENT_TYPE.get(component_info['stream_content'])
                        if component_types is not None:
                            program.video_type = component_types.get(component_info['component_type'], '')
                        ## 映像のコーデック
                        program.video_codec = TSInformation.STREAM_CONTENT.get(component_info['stream_content'], '')
                        ## 映像の解像度
                        program.video_resolution = TSInformation.COMPONENT_TYPE.get(component_info['component_type'], '')

                    # 音声情報
                    program.primary_audio_type = ''  # デフォルト値
                    program.primary_audio_language = ''  # デフォルト値
                    program.primary_audio_sampling_rate = ''  # デフォルト値
                    audio_info = program_info.get('audio_info')
                    if audio_info is not None and len(audio_info['component_list']) > 0:

                        ## 主音声
                        audio_component_info = audio_info['component_list'][0]
                        program.primary_audio_type = ariblib.constants.COMPONENT_TYPE[0x02].get(audio_component_info['component_type'], '')
                        program.primary_audio_sampling_rate = ariblib.constants.SAMPLING_RATE.get(audio_component_info['sampling_rate'], '')
                        ## 2021/09 現在の EDCB では言語コードが取得できないため、日本語か英語で固定する
                        ## EpgDataCap3 のパーサー止まりで EDCB 側では取得していないらしい
                        program.primary_audio_language = '日本語'
                        ## デュアルモノのみ
                        if program.primary_audio_type == '1/0+1/0モード(デュアルモノ)':
                            if audio_component_info['es_multi_lingual_flag'] != 0:  # デュアルモノ時の多言語フラグ
                                program.primary_audio_language += '+英語'  #
                            else:
                                program.primary_audio_language += '+副音声'

                        # 副音声（存在する場合）
                        if len(audio_info['component_list']) > 1:
                            audio_component_info = audio_info['component_list'][1]
                            program.secondary_audio_type = ariblib.constants.COMPONENT_TYPE[0x02].get(audio_component_info['component_type'], '')
                            program.secondary_audio_sampling_rate = ariblib.constants.SAMPLING_RATE.get(audio_component_info['sampling_rate'], '')
                            ## 2021/09 現在の EDCB では言語コードが取得できないため、副音声で固定する
                            ## 英語かもしれないし解説かもしれない
                            program.secondary_audio_language = '副音声'
                            ## デュアルモノのみ
                            if program.secondary_audio_type == '1/0+1/0モード(デュアルモノ)':
                                if audio_component_info['es_multi_lingual_flag'] != 0:  # デュアルモノ時の多言語フラグ
                                    program.secondary_audio_language += '+英語'  #
                                else:
                                    program.secondary_audio_language += '+副音声'

                    # ジャンル
                    ## 数字だけでは開発中の視認性が低いのでテキストに変換する
                    program.genre = list()  # デフォルト値
                    content_info = program_info.get('content_info')
                    if content_info is not None:
                        for content_data in content_info['nibble_list']:  # ジャンルごとに

                            # 大まかなジャンルを取得
                            genre_tuple = ariblib.constants.CONTENT_TYPE.get(content_data['content_nibble'] >> 8)
                            if genre_tuple is not None:

                                # major … 大分類
                                # middle … 中分類
                                genre_dict = {
                                    'major': genre_tuple[0].replace('／', '・'),
                                    'middle': genre_tuple[1].get(content_data['content_nibble'] & 0xf, '').replace('／', '・'),
                                }

                                # BS/地上デジタル放送用番組付属情報がジャンルに含まれている場合、user_nibble から値を取得して書き換える
                                # たとえば「中止の可能性あり」や「延長の可能性あり」といった情報が取れる
                                if genre_dict['major'] == '拡張':
                                    if genre_dict['middle'] == 'BS/地上デジタル放送用番組付属情報':
                                        user_nibble = (content_data['user_nibble'] >> 8 << 4) | (content_data['user_nibble'] & 0xf)
                                        genre_dict['middle'] = ariblib.constants.USER_TYPE.get(user_nibble, '')
                                    # 「拡張」はあるがBS/地上デジタル放送用番組付属情報でない場合はなんの値なのかわからないのでパス
                                    else:
                                        continue

                                # ジャンルを追加
                                program.genre.append(genre_dict)

                    # 番組情報をデータベースに保存する
                    if duplicate_program is None:
                        Logging.debug(f'Add Program: {program.id}')
                    else:
                        Logging.debug(f'Update Program: {program.id}')

                    await program.save()

            # この時点で残存している番組情報は放送が終わって EPG から削除された番組なので、まとめて削除する
            # ここで削除しないと終了した番組の情報が幽霊のように残り続ける事になり、結果 DB が肥大化して遅くなってしまう
            for duplicate_program in duplicate_programs.values():
                Logging.debug(f'Delete Program: {duplicate_program.id}')
                await duplicate_program.delete()
