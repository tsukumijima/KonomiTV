
import ariblib.constants
import asyncio
import concurrent.futures
import datetime
import requests
import time
import traceback
import urllib
from datetime import timedelta
from tortoise import connections
from tortoise import exceptions
from tortoise import fields
from tortoise import models
from tortoise import timezone
from tortoise import Tortoise
from tortoise import transactions
from typing import List, Optional

from app.constants import CONFIG, DATABASE_CONFIG
from app.models import Channel
from app.utils import Logging
from app.utils import TSInformation
from app.utils.EDCB import CtrlCmdUtil
from app.utils.EDCB import EDCBUtil


class Program(models.Model):

    # データベース上のテーブル名
    class Meta:
        table: str = 'programs'

    # テーブル設計は Notion を参照のこと
    id: str = fields.TextField(pk=True)
    network_id: int = fields.IntField()
    service_id: int = fields.IntField()
    event_id: int = fields.IntField()
    channel_id: str = fields.TextField()
    title: str = fields.TextField()
    description: str = fields.TextField()
    detail: dict = fields.JSONField()
    start_time: datetime.datetime = fields.DatetimeField()
    end_time: datetime.datetime = fields.DatetimeField()
    duration: float = fields.FloatField()
    is_free: bool = fields.BooleanField()
    genre: list = fields.JSONField()
    video_type: str = fields.TextField()
    video_codec: str = fields.TextField()
    video_resolution: str = fields.TextField()
    primary_audio_type: str = fields.TextField()
    primary_audio_language: str = fields.TextField()
    primary_audio_sampling_rate: str = fields.TextField()
    secondary_audio_type: Optional[str] = fields.TextField(null=True)
    secondary_audio_language: Optional[str] = fields.TextField(null=True)
    secondary_audio_sampling_rate: Optional[str] = fields.TextField(null=True)


    @classmethod
    async def update(cls, multiprocess: bool=False) -> None:
        """
        番組情報を更新する

        Args:
            multiprocess (bool, optional): マルチプロセスで実行するかどうか
        """

        timestamp = time.time()
        Logging.info('Programs updating...')

        # 番組情報をマルチプロセスで更新する
        if multiprocess is True:

            # 動作中のイベントループを取得
            loop = asyncio.get_running_loop()

            # マルチプロセス実行用の Executor を初期化
            ## with 文で括ることで、with 文を抜けたときに Executor がクリーンアップされるようにする
            ## さもなければプロセスが残り続けてゾンビプロセス化し、メモリリークを引き起こしてしまう
            try:
                with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:

                    # Mirakurun バックエンド
                    if CONFIG['general']['backend'] == 'Mirakurun':
                        await loop.run_in_executor(executor, cls.updateFromMirakurunSync)

                    # EDCB バックエンド
                    elif CONFIG['general']['backend'] == 'EDCB':
                        await loop.run_in_executor(executor, cls.updateFromEDCBSync)

            # データベースが他のプロセスにロックされていた場合
            # 5秒待ってからリトライ
            except exceptions.OperationalError:
                await asyncio.sleep(5)
                await cls.update(multiprocess=multiprocess)
                return

        # 番組情報をシングルプロセスで更新する
        else:

            # Mirakurun バックエンド
            if CONFIG['general']['backend'] == 'Mirakurun':
                await cls.updateFromMirakurun()

            # EDCB バックエンド
            elif CONFIG['general']['backend'] == 'EDCB':
                await cls.updateFromEDCB()

        Logging.info(f'Programs update complete. ({round(time.time() - timestamp, 3)} sec)')


    @classmethod
    async def updateFromMirakurun(cls) -> None:
        """ Mirakurun バックエンドから番組情報を取得し、更新する """

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

                # Mirakurun 3.8 以下では type が存在しない & relatedItems が機能していないので true を返す
                if 'type' not in item:
                    return True

                # 移動したイベントか？
                if item['type'] == 'movement':
                    return True

                # type が shared でメインサービスか？
                if item['type'] == 'shared':
                    # サービス ID とイベント ID が一致すればメインサービスだし、そうでないならメインサービスとイベントを共有している
                    if item['serviceId'] == program['serviceId'] and item['eventId'] == program['eventId']:
                        return True
                    else:
                        return False

                # イベントリレーされてきた番組か？
                if item['type'] == 'relay':
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

        # マルチプロセス時は既存のコネクションが使えないため、Tortoise ORMを初期化し直す
        # ref: https://tortoise-orm.readthedocs.io/en/latest/setup.html
        is_running_multiprocess = False
        try:
            connections.get('default')
        except exceptions.ConfigurationError:
            await Tortoise.init(config=DATABASE_CONFIG)
            is_running_multiprocess = True
        try:

            # Mirakurun の URL の末尾のスラッシュを削除
            ## 多重のスラッシュは Mirakurun だと 404 になってしまう
            ## マルチプロセス時は起動後に動的に調整される Mirakurun の URL が元に戻ってしまうため、再度実行する
            if is_running_multiprocess:
                CONFIG['general']['mirakurun_url'] = CONFIG['general']['mirakurun_url'].rstrip('/')

            # Mirakurun の API から番組情報を取得する
            try:
                mirakurun_programs_api_url = f'{CONFIG["general"]["mirakurun_url"]}/api/programs'
                mirakurun_programs_api_response = await asyncio.to_thread(requests.get, mirakurun_programs_api_url, timeout=3)
                if mirakurun_programs_api_response.status_code != 200:  # Mirakurun からエラーが返ってきた
                    Logging.error(f'Failed to get programs from Mirakurun. (HTTP Error {mirakurun_programs_api_response.status_code})')
                    return
                programs:List[dict] = mirakurun_programs_api_response.json()
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                Logging.error(f'Failed to get programs from Mirakurun. (Connection Timeout)')
                return

            # このトランザクションは単にパフォーマンス向上のため
            async with transactions.in_transaction():

                # この変数から更新or更新不要な番組情報を削除していき、残った古い番組情報を最後にまとめて削除する
                duplicate_programs = {temp.id:temp for temp in await Program.all()}

                # チャンネル情報を取得
                # NID32736-SID1024 形式の ID をキーにした辞書にまとめる
                channels = {temp.id:temp for temp in await Channel.all()}

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
                    title = ''  # デフォルト値
                    description = ''  # デフォルト値
                    if 'name' in program_info:
                        title = TSInformation.formatString(program_info['name'])
                    if 'description' in program_info:
                        description = TSInformation.formatString(program_info['description'])

                    # 番組詳細
                    detail = {}  # デフォルト値
                    if 'extended' in program_info:

                        # 番組詳細の見出しと本文の辞書ごとに
                        for head, text in program_info['extended'].items():

                            # 見出しと本文
                            head_han = TSInformation.formatString(head).replace('◇', '')  # ◇ を取り除く
                            text_han = TSInformation.formatString(text)
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
                        program = Program()

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
                    program.is_free = program_info['isFree']

                    # 番組終了時刻・番組時間
                    # 終了時間未定 (Mirakurun から duration == 1 で示される) の場合、まだ番組情報を取得していないならとりあえず5分とする
                    # すでに番組情報を取得している（番組情報更新）なら以前取得した値をそのまま使う
                    ## Mirakurun の /api/programs API のレスポンスには EIT[schedule] 由来の情報と EIT[p/f] 由来の情報が混ざっている
                    ## さらに EIT[p/f] には番組が延長されたなどの理由で稀に番組時間が「終了時間未定」になることがある
                    ## 基本的には EIT[p/f] 由来の「終了時間未定」が降ってくる前に EIT[schedule] 由来の番組時間を取得しているはず
                    ## 「終了時間未定」だと番組表の整合性が壊れるので、実態と一致しないとしても EIT[schedule] 由来の番組時間を優先したい
                    if program_info['duration'] == 1:
                        if program.duration is None:  # 番組情報をまだ取得していない
                            program.end_time = start_time + timedelta(minutes = 5)
                        else:  # すでに番組情報を取得しているので以前取得した値をそのまま使う
                            pass
                    else:
                        program.end_time = end_time
                    program.duration = (program.end_time - program.start_time).total_seconds()

                    # 映像情報
                    program.video_type = ''  # デフォルト値
                    program.video_codec = ''  # デフォルト値
                    program.video_resolution = ''  # デフォルト値
                    if 'video' in program_info:
                        program.video_type = ariblib.constants.COMPONENT_TYPE \
                            [program_info['video']['streamContent']][program_info['video']['componentType']]
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
                    program.genre = []  # デフォルト値
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
                        Logging.debug_simple(f'Add Program: {program.id}')
                    else:
                        Logging.debug_simple(f'Update Program: {program.id}')

                    ## マルチプロセス実行時は、まれに保存する際にメインプロセスにデータベースがロックされている事がある
                    ## 3秒待ってから再試行し、それでも失敗した場合はスキップ
                    try:
                        await program.save()
                    except exceptions.OperationalError:
                        try:
                            await asyncio.sleep(3)
                            await program.save()
                        except exceptions.OperationalError:
                            pass

                # この時点で残存している番組情報は放送が終わって EPG から削除された番組なので、まとめて削除する
                # ここで削除しないと終了した番組の情報が幽霊のように残り続ける事になり、結果 DB が肥大化して遅くなってしまう
                for duplicate_program in duplicate_programs.values():
                    Logging.debug_simple(f'Delete Program: {duplicate_program.id}')
                    try:
                        await duplicate_program.delete()
                    except exceptions.OperationalError:
                        try:
                            await asyncio.sleep(3)
                            await duplicate_program.delete()
                        except exceptions.OperationalError:
                            pass


        # マルチプロセス実行時は、明示的に例外を拾わないとなぜかメインプロセスも含め全体がフリーズしてしまう
        except Exception:
            Logging.error(traceback.format_exc())

        # マルチプロセス実行時は、開いた Tortoise ORM のコネクションを明示的に閉じる
        # コネクションを閉じないと Ctrl+C を押下しても終了できない
        finally:
            if is_running_multiprocess:
                await connections.close_all()


    @classmethod
    async def updateFromEDCB(cls) -> None:
        """ EDCB バックエンドから番組情報を取得し、更新する """

        # マルチプロセス時は既存のコネクションが使えないため、Tortoise ORMを初期化し直す
        # ref: https://tortoise-orm.readthedocs.io/en/latest/setup.html
        is_running_multiprocess = False
        try:
            connections.get('default')
        except exceptions.ConfigurationError:
            await Tortoise.init(config=DATABASE_CONFIG)
            is_running_multiprocess = True
        try:

            # マルチプロセス時は起動後に動的に追加される EDCB のホスト名とポートが存在しないため、パースし直す
            if is_running_multiprocess:
                edcb_url_parse = urllib.parse.urlparse(CONFIG['general']['edcb_url'])
                CONFIG['general']['edcb_host'] = edcb_url_parse.hostname
                CONFIG['general']['edcb_port'] = edcb_url_parse.port

            # CtrlCmdUtil を初期化
            edcb = CtrlCmdUtil()
            edcb.setConnectTimeOutSec(3)  # 3秒後にタイムアウト

            # 開始時間未定をのぞく全番組を取得する (リスト引数の前2要素は全番組、残り2要素は全期間を意味)
            program_services = await edcb.sendEnumPgInfoEx([0xffffffffffff, 0xffffffffffff, 1, 0x7fffffffffffffff])
            if program_services is None:
                Logging.error(f'Failed to get programs from EDCB.')
                return

            # このトランザクションは単にパフォーマンス向上のため
            async with transactions.in_transaction():

                # この変数から更新or更新不要な番組情報を削除していき、残った古い番組情報を最後にまとめて削除する
                duplicate_programs = {temp.id:temp for temp in await Program.all()}

                # チャンネルごとに
                for program_service in program_services:

                    # NID・SID・TSID を取得
                    nid = program_service['service_info']['onid']
                    sid = program_service['service_info']['sid']
                    tsid = program_service['service_info']['tsid']

                    # チャンネル情報を取得
                    channel = await Channel.filter(network_id = nid, service_id = sid).first()
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
                            title = TSInformation.formatString(program_info['short_info']['event_name'])
                            description = TSInformation.formatString(program_info['short_info']['text_char'])

                        # 番組詳細
                        detail = {}  # デフォルト値
                        if 'ext_info' in program_info:

                            # 番組詳細テキストから取得した、見出しと本文の辞書ごとに
                            for head, text in EDCBUtil.parseProgramExtendedText(program_info['ext_info']['text_char']).items():

                                # 見出しと本文
                                head_han = TSInformation.formatString(head).replace('◇', '')  # ◇ を取り除く
                                if head_han == '':  # 見出しが空の場合、固定で「番組内容」としておく
                                    head_han = '番組内容'
                                text_han = TSInformation.formatString(text)
                                detail[head_han] = text_han

                                # 番組概要が空の場合、番組詳細の最初の本文を概要として使う
                                # 空でまったく情報がないよりかは良いはず
                                if description.strip() == '':
                                    description = text_han

                        # 番組開始時刻
                        start_time: datetime.datetime = program_info['start_time']

                        # 番組終了時刻
                        ## 終了時間未定の場合、とりあえず5分とする
                        end_time: datetime.datetime = start_time + timedelta(seconds = program_info.get('duration_sec', 300))

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
                            program = Program()

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
                        program.duration = (program.end_time - program.start_time).total_seconds()
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
                        program.genre = []  # デフォルト値
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
                            Logging.debug_simple(f'Add Program: {program.id}')
                        else:
                            Logging.debug_simple(f'Update Program: {program.id}')

                        ## マルチプロセス実行時は、まれに保存する際にメインプロセスにデータベースがロックされている事がある
                        ## 3秒待ってから再試行し、それでも失敗した場合はスキップ
                        try:
                            await program.save()
                        except exceptions.OperationalError:
                            try:
                                await asyncio.sleep(3)
                                await program.save()
                            except exceptions.OperationalError:
                                pass

                # この時点で残存している番組情報は放送が終わって EPG から削除された番組なので、まとめて削除する
                # ここで削除しないと終了した番組の情報が幽霊のように残り続ける事になり、結果 DB が肥大化して遅くなってしまう
                for duplicate_program in duplicate_programs.values():
                    Logging.debug_simple(f'Delete Program: {duplicate_program.id}')
                    try:
                        await duplicate_program.delete()
                    except exceptions.OperationalError:
                        try:
                            await asyncio.sleep(3)
                            await duplicate_program.delete()
                        except exceptions.OperationalError:
                            pass

        # マルチプロセス実行時は、明示的に例外を拾わないとなぜかメインプロセスも含め全体がフリーズしてしまう
        except Exception:
            Logging.error(traceback.format_exc())

        # マルチプロセス実行時は、開いた Tortoise ORM のコネクションを明示的に閉じる
        # コネクションを閉じないと Ctrl+C を押下しても終了できない
        finally:
            if is_running_multiprocess:
                await connections.close_all()


    @classmethod
    def updateFromMirakurunSync(cls) -> None:
        """ Programs.updateFromMirakurun() の同期版 """
        # asyncio.run() で非同期メソッドの実行が終わるまで待つ
        asyncio.run(cls.updateFromMirakurun())


    @classmethod
    def updateFromEDCBSync(cls) -> None:
        """ Programs.updateFromEDCB() の同期版 """
        # asyncio.run() で非同期メソッドの実行が終わるまで待つ
        asyncio.run(cls.updateFromEDCB())
