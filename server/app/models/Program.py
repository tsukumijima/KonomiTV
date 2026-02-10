
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import asyncio
import concurrent.futures
import gc
import json
import time
from datetime import datetime, timedelta
from typing import Any, cast

import ariblib.constants
import httpx
from tortoise import Tortoise, connections, exceptions, fields, transactions
from tortoise.fields import Field as TortoiseField
from tortoise.models import Model as TortoiseModel

from app import logging
from app.config import Config, LoadConfig
from app.constants import DATABASE_CONFIG, HTTPX_CLIENT, JST
from app.models.Channel import Channel
from app.schemas import Genre
from app.utils import GetMirakurunAPIEndpointURL
from app.utils.edcb.CtrlCmdUtil import CtrlCmdUtil
from app.utils.edcb.EDCBUtil import EDCBUtil
from app.utils.TSInformation import TSInformation


class Program(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'programs'

    id = fields.CharField(255, pk=True)
    channel: fields.ForeignKeyRelation[Channel] = \
        fields.ForeignKeyField('models.Channel', related_name='programs', index=True, on_delete=fields.CASCADE)
    channel_id: str
    network_id = fields.IntField()
    service_id = fields.IntField()
    event_id = fields.IntField()
    title = fields.TextField()
    description = fields.TextField()
    detail = cast(TortoiseField[dict[str, str]], fields.JSONField(default={}, encoder=lambda x: json.dumps(x, ensure_ascii=False)))  # type: ignore
    start_time = fields.DatetimeField(index=True)
    end_time = fields.DatetimeField(index=True)
    duration = fields.FloatField()
    is_free = fields.BooleanField()
    genres = cast(TortoiseField[list[Genre]], fields.JSONField(default=[], encoder=lambda x: json.dumps(x, ensure_ascii=False)))  # type: ignore
    video_type = cast(TortoiseField[str | None], fields.TextField(null=True))
    video_codec = cast(TortoiseField[str | None], fields.TextField(null=True))
    video_resolution = cast(TortoiseField[str | None], fields.TextField(null=True))
    primary_audio_type = fields.TextField()
    primary_audio_language = fields.TextField()
    primary_audio_sampling_rate = fields.TextField()
    secondary_audio_type = cast(TortoiseField[str | None], fields.TextField(null=True))
    secondary_audio_language = cast(TortoiseField[str | None], fields.TextField(null=True))
    secondary_audio_sampling_rate = cast(TortoiseField[str | None], fields.TextField(null=True))


    @classmethod
    async def update(cls, multiprocess: bool = False) -> None:
        """
        番組情報を更新する

        Args:
            multiprocess (bool, optional): マルチプロセスで実行するかどうか
        """

        timestamp = time.time()
        logging.info('Programs updating...')

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
                    if Config().general.backend == 'Mirakurun':
                        await loop.run_in_executor(executor, cls.updateFromMirakurunForMultiProcess)

                    # EDCB バックエンド
                    elif Config().general.backend == 'EDCB':
                        await loop.run_in_executor(executor, cls.updateFromEDCBForMultiProcess)

            # データベースが他のプロセスにロックされていた場合
            # 5秒待ってからリトライ
            except exceptions.OperationalError:
                await asyncio.sleep(5)
                await cls.update(multiprocess=multiprocess)
                return

        # 番組情報をシングルプロセスで更新する
        else:
            try:
                # Mirakurun バックエンド
                if Config().general.backend == 'Mirakurun':
                    await cls.updateFromMirakurun()

                # EDCB バックエンド
                elif Config().general.backend == 'EDCB':
                    await cls.updateFromEDCB()
            except Exception as ex:
                logging.error('Failed to update programs:', exc_info=ex)

        logging.info(f'Programs update complete. ({round(time.time() - timestamp, 3)} sec)')


    @classmethod
    async def updateFromMirakurun(cls, is_running_multiprocess: bool = False) -> None:
        """
        Mirakurun バックエンドから番組情報を取得し、更新する

        Args:
            is_running_multiprocess (bool, optional): マルチプロセスで実行されているかどうか
        """

        def IsMainProgram(program: dict[str, Any]) -> bool:
            """
            relatedItems からメインの番組情報か判定する
            EIT[p/f] 対応により増えた番組情報から必要なものだけを取得する
            ref: https://github.com/l3tnun/EPGStation/blob/master/src/model/epgUpdater/EPGUpdateManageModel.ts#L103-L136

            Args:
                program (dict[str, Any]): 番組情報の辞書
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

        def MillisecondToDatetime(millisecond: int) -> datetime:
            """
            ミリ秒から Datetime を取得する

            Args:
                millisecond (int): ミリ秒

            Returns:
                datetime: Datetime（タイムゾーン付き）
            """

            # タイムゾーンを UTC+9（日本時間）に指定する
            return datetime.fromtimestamp(millisecond / 1000, tz=JST)

        # マルチプロセス時は既存のコネクションが使えないため、Tortoise ORM を初期化し直す
        # ref: https://tortoise-orm.readthedocs.io/en/latest/setup.html
        if is_running_multiprocess is True:

            # Tortoise ORM を再初期化する前に、既存のコネクションを破棄
            ## これをやっておかないとなぜか正常に初期化できず、DB 操作でフリーズする…
            ## Windows だとこれをやらなくても問題ないが、Linux だと必要 (Tortoise ORM あるいは aiosqlite のマルチプロセス時のバグ？)
            connections.discard('default')

            # Tortoise ORM を再初期化
            await Tortoise.init(config=DATABASE_CONFIG)

        try:

            # このトランザクションはパフォーマンス向上と、取得失敗時のロールバックのためのもの
            async with transactions.in_transaction():

                # Mirakurun / mirakc の API から番組情報を取得する
                try:
                    mirakurun_programs_api_url = GetMirakurunAPIEndpointURL('/api/programs')
                    async with HTTPX_CLIENT() as client:
                        # 10秒後にタイムアウト (SPHD や CATV も映る環境だと時間がかかるので、少し伸ばす)
                        mirakurun_programs_api_response = await client.get(mirakurun_programs_api_url, timeout=10)
                    if mirakurun_programs_api_response.status_code != 200:  # Mirakurun / mirakc からエラーが返ってきた
                        logging.error(f'Failed to get programs from Mirakurun / mirakc. (HTTP Error {mirakurun_programs_api_response.status_code})')
                        raise Exception(f'Failed to get programs from Mirakurun / mirakc. (HTTP Error {mirakurun_programs_api_response.status_code})')
                    programs: list[dict[str, Any]] = mirakurun_programs_api_response.json()
                except httpx.NetworkError as ex:
                    logging.error('Failed to get programs from Mirakurun / mirakc. (Network Error)')
                    raise ex
                except httpx.TimeoutException as ex:
                    logging.error('Failed to get programs from Mirakurun / mirakc. (Connection Timeout)')
                    raise ex

                # この変数から更新or更新不要な番組情報を削除していき、残った古い番組情報を最後にまとめて削除する
                duplicate_programs = {temp.id:temp for temp in await Program.all()}

                # チャンネル情報を取得
                # NID32736-SID1024 形式の ID をキーにした辞書にまとめる
                channels = {temp.id:temp for temp in await Channel.filter(is_watchable=True)}

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
                    title: str = ''  # デフォルト値
                    description: str = ''  # デフォルト値
                    if 'name' in program_info:
                        title = TSInformation.formatString(program_info['name']).strip()
                    if 'description' in program_info:
                        description = TSInformation.formatString(program_info['description']).strip()

                    # 番組詳細
                    detail: dict[str, str] = {}  # デフォルト値
                    if 'extended' in program_info:

                        # 番組詳細の見出しと本文の辞書ごとに
                        for head, text in program_info['extended'].items():

                            # 見出しと本文
                            head_hankaku = TSInformation.formatString(head).replace('◇', '').strip()  # ◇ を取り除く
                            if head_hankaku == '':  # 見出しが空の場合、固定で「番組内容」としておく
                                head_hankaku = '番組内容'
                            text_hankaku = TSInformation.formatString(text).strip()
                            detail[head_hankaku] = text_hankaku

                            # 番組概要が空の場合、番組詳細の最初の本文を概要として使う
                            # 空でまったく情報がないよりかは良いはず
                            if description.strip() == '':
                                description = text_hankaku

                    # 番組開始時刻・番組終了時刻
                    start_time = MillisecondToDatetime(program_info['startAt'])
                    end_time = MillisecondToDatetime(program_info['startAt'] + program_info['duration'])

                    # 番組終了時刻が現在時刻より12時間以上前な番組を弾く
                    if datetime.now(JST) - end_time > timedelta(hours=12):
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
                    program.channel_id = channel.id
                    program.network_id = int(channel.network_id)
                    program.service_id = int(channel.service_id)
                    program.event_id = int(program_info['eventId'])
                    program.title = title
                    program.description = description
                    program.detail = detail
                    program.start_time = start_time
                    program.is_free = bool(program_info['isFree'])

                    # 番組終了時刻・番組時間
                    # 終了時間未定 (Mirakurun から duration == 1 で示される) の場合、まだ番組情報を取得していないならとりあえず5分とする
                    # すでに番組情報を取得している（番組情報更新）なら以前取得した値をそのまま使う
                    ## Mirakurun の /api/programs API のレスポンスには EIT[schedule] 由来の情報と EIT[p/f] 由来の情報が混ざっている
                    ## さらに EIT[p/f] には番組が延長されたなどの理由で稀に番組時間が「終了時間未定」になることがある
                    ## 基本的には EIT[p/f] 由来の「終了時間未定」が降ってくる前に EIT[schedule] 由来の番組時間を取得しているはず
                    ## 「終了時間未定」だと番組表の整合性が壊れるので、実態と一致しないとしても EIT[schedule] 由来の番組時間を優先したい
                    if program_info['duration'] == 1:
                        if program.duration is None:  # 番組情報をまだ取得していない
                            program.end_time = start_time + timedelta(minutes=5)
                        else:  # すでに番組情報を取得しているので以前取得した値をそのまま使う
                            pass
                    else:
                        program.end_time = end_time
                    program.duration = (program.end_time - program.start_time).total_seconds()

                    # ジャンル
                    ## 数字だけでは開発中の視認性が低いのでテキストに変換する
                    program.genres = []  # デフォルト値
                    if 'genres' in program_info:
                        for genre in program_info['genres']:  # ジャンルごとに

                            # 大まかなジャンルを取得
                            genre_tuple = ariblib.constants.CONTENT_TYPE.get(genre['lv1'])
                            if genre_tuple is not None:

                                # major … 大分類
                                # middle … 中分類
                                genre_dict: Genre = {
                                    'major': genre_tuple[0].replace('／', '・'),
                                    'middle': genre_tuple[1].get(genre['lv2'], '未定義').replace('／', '・'),
                                }

                                # BS/地上デジタル放送用番組付属情報がジャンルに含まれている場合、user_nibble から値を取得して書き換える
                                # たとえば「中止の可能性あり」や「延長の可能性あり」といった情報が取れる
                                if genre_dict['major'] == '拡張':
                                    if genre_dict['middle'] == 'BS/地上デジタル放送用番組付属情報':
                                        user_nibble = (genre['un1'] * 0x10) + genre['un2']
                                        genre_dict['middle'] = ariblib.constants.USER_TYPE.get(user_nibble, '未定義')
                                    # 「拡張」はあるがBS/地上デジタル放送用番組付属情報でない場合はなんの値なのかわからないのでパス
                                    else:
                                        continue

                                # ジャンルを追加
                                program.genres.append(genre_dict)

                    # 映像情報
                    program.video_type = None
                    program.video_codec = None
                    program.video_resolution = None
                    if 'video' in program_info:
                        if program_info['video']['streamContent'] is not None:
                            program.video_type = ariblib.constants.COMPONENT_TYPE \
                                [program_info['video']['streamContent']].get(program_info['video']['componentType'], 'Unknown')
                        else:
                            program.video_type = 'Unknown'
                        program.video_codec = program_info['video']['type']
                        program.video_resolution = program_info['video']['resolution']

                    # 音声情報
                    program.primary_audio_type = ''
                    program.primary_audio_language = ''
                    program.primary_audio_sampling_rate = ''
                    program.secondary_audio_type = None
                    program.secondary_audio_language = None
                    program.secondary_audio_sampling_rate = None
                    ## Mirakurun 3.9 以降向け
                    ## ref: https://github.com/Chinachu/Mirakurun/blob/master/api.d.ts#L88-L105
                    if 'audios' in program_info:

                        ## 主音声
                        program.primary_audio_type = ariblib.constants.COMPONENT_TYPE[0x02].get(program_info['audios'][0]['componentType'], 'Unknown')
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
                            program.secondary_audio_type = ariblib.constants.COMPONENT_TYPE[0x02].get(program_info['audios'][1]['componentType'], 'Unknown')
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
                        program.primary_audio_type = ariblib.constants.COMPONENT_TYPE[0x02].get(program_info['audio']['componentType'], 'Unknown')
                        program.primary_audio_sampling_rate = str(int(program_info['audio']['samplingRate'] / 1000)) + 'kHz'  # kHz に変換
                        ## Mirakurun 3.8 以下では言語コードが取得できないため、日本語で固定する
                        program.primary_audio_language = '日本語'
                        ## デュアルモノのみ
                        if program.primary_audio_type == '1/0+1/0モード(デュアルモノ)':
                            program.primary_audio_language = '日本語+英語'  # 日本語+英語で固定

                    # 番組情報をデータベースに保存する
                    if duplicate_program is None:
                        logging.debug(f'Add Program: {program.id}')
                    else:
                        logging.debug(f'Update Program: {program.id}')

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
                    logging.debug(f'Delete Program: {duplicate_program.id}')
                    try:
                        await duplicate_program.delete()
                    except exceptions.OperationalError:
                        try:
                            await asyncio.sleep(3)
                            await duplicate_program.delete()
                        except exceptions.OperationalError:
                            pass


        # マルチプロセス実行時は、明示的に例外を拾わないとなぜかメインプロセスも含め全体がフリーズしてしまう
        except Exception as ex:
            logging.error('Failed to update programs from Mirakurun:', exc_info=ex)

        # マルチプロセス実行時は、開いた Tortoise ORM のコネクションを明示的に閉じる
        # コネクションを閉じないと Ctrl+C を押下しても終了できない
        finally:
            if is_running_multiprocess:
                await Tortoise.close_connections()


    @classmethod
    async def updateFromEDCB(cls, is_running_multiprocess: bool = False) -> None:
        """
        EDCB バックエンドから番組情報を取得し、更新する

        Args:
            is_running_multiprocess (bool, optional): マルチプロセスで実行されているかどうか
        """

        # マルチプロセス時は既存のコネクションが使えないため、Tortoise ORM を初期化し直す
        # ref: https://tortoise-orm.readthedocs.io/en/latest/setup.html
        if is_running_multiprocess is True:

            # Tortoise ORM を再初期化する前に、既存のコネクションを破棄
            ## これをやっておかないとなぜか正常に初期化できず、DB 操作でフリーズする…
            ## Windows だとこれをやらなくても問題ないが、Linux だと必要 (Tortoise ORM あるいは aiosqlite のマルチプロセス時のバグ？)
            connections.discard('default')

            # Tortoise ORM を再初期化
            await Tortoise.init(config=DATABASE_CONFIG)

        try:

            # このトランザクションはパフォーマンス向上と、取得失敗時のロールバックのためのもの
            async with transactions.in_transaction():

                # CtrlCmdUtil を初期化
                edcb = CtrlCmdUtil()
                edcb.setConnectTimeOutSec(10)  # 10秒後にタイムアウト (SPHD や CATV も映る環境だと時間がかかるので、少し伸ばす)

                # 開始時間未定をのぞく全番組を取得する (リスト引数の前2要素は全番組、残り2要素は全期間を意味)
                service_event_info_list = await edcb.sendEnumPgInfoEx([0xffffffffffff, 0xffffffffffff, 1, 0x7fffffffffffffff])
                if service_event_info_list is None:
                    logging.error('Failed to get programs from EDCB.')
                    raise Exception('Failed to get programs from EDCB.')

                # この変数から更新or更新不要な番組情報を削除していき、残った古い番組情報を最後にまとめて削除する
                duplicate_programs = {temp.id:temp for temp in await Program.all()}

                # チャンネルごとに
                for service_event_info in service_event_info_list:

                    # NID・SID・TSID を取得
                    nid = int(service_event_info['service_info']['onid'])
                    sid = int(service_event_info['service_info']['sid'])
                    tsid = int(service_event_info['service_info']['tsid'])

                    # チャンネル情報を取得
                    ## TSID まで指定することで、NID-SID が同じだが TSID が異なる番組情報が複数降ってきた場合
                    ## (BS トランスポンダ再編時など) に同一チャンネルの重複追加を回避できる
                    ## EDCB バックエンド利用時、Channel レコードには必ず TSID が設定されている (Mirakurun バックエンド利用時は常に null)
                    channel = await Channel.filter(network_id=nid, service_id=sid, transport_stream_id=tsid).first()
                    if channel is None:  # 登録されていないチャンネルの番組を弾く（ワンセグやデータ放送など）
                        continue

                    # 番組情報ごとに
                    for event_info in service_event_info['event_list']:

                        # メインの番組でないなら弾く
                        group_info = event_info.get('event_group_info')
                        if (group_info is not None and len(group_info['event_data_list']) == 1 and
                        (group_info['event_data_list'][0]['onid'] != nid or
                            group_info['event_data_list'][0]['tsid'] != tsid or
                            group_info['event_data_list'][0]['sid'] != sid or
                            group_info['event_data_list'][0]['eid'] != event_info['eid'])):
                            continue

                        # 重複する番組情報が登録されているかの判定に使うため、ここで先に番組情報を取得する

                        # 番組タイトル・番組概要
                        title: str = ''  # デフォルト値
                        description: str = ''  # デフォルト値
                        if 'short_info' in event_info:
                            title = TSInformation.formatString(event_info['short_info']['event_name']).strip()
                            description = TSInformation.formatString(event_info['short_info']['text_char']).strip()

                        # 番組詳細
                        detail: dict[str, str] = {}  # デフォルト値
                        if 'ext_info' in event_info:

                            # 番組詳細テキストから取得した、見出しと本文の辞書ごとに
                            for head, text in EDCBUtil.parseProgramExtendedText(event_info['ext_info']['text_char']).items():

                                # 見出しと本文
                                ## 見出しのみ ariblib 側で意図的に重複防止のためのタブ文字付加が行われる場合があるため、
                                ## strip() では明示的に半角スペースと改行のみを指定している
                                head_hankaku = TSInformation.formatString(head).replace('◇', '').strip(' \r\n')  # ◇ を取り除く
                                ## ないとは思うが、万が一この状態で見出しが衝突しうる場合は、見出しの後ろにタブ文字を付加する
                                while head_hankaku in detail.keys():
                                    head_hankaku += '\t'
                                ## 見出しが空の場合、固定で「番組内容」としておく
                                if head_hankaku == '':
                                    head_hankaku = '番組内容'
                                text_hankaku = TSInformation.formatString(text).strip()
                                detail[head_hankaku] = text_hankaku

                                # 番組概要が空の場合、番組詳細の最初の本文を概要として使う
                                # 空でまったく情報がないよりかは良いはず
                                if description.strip() == '':
                                    description = text_hankaku

                        # 番組開始時刻
                        ## 万が一取得できなかった場合は 1970/1/1 9:00 とする
                        start_time = event_info.get('start_time', datetime(1970, 1, 1, 9, tzinfo=JST))

                        # 番組終了時刻
                        ## 終了時間未定の場合、とりあえず5分とする
                        end_time = start_time + timedelta(seconds=event_info.get('duration_sec', 300))

                        # 番組終了時刻が現在時刻より12時間以上前な番組を弾く
                        if datetime.now(CtrlCmdUtil.TZ) - end_time > timedelta(hours=12):
                            continue

                        # ***** ここからは 追加・更新・更新不要 のいずれか *****

                        # DB は読み取りよりも書き込みの方が負荷と時間がかかるため、不要な書き込みは極力避ける

                        # 番組 ID
                        program_id = f'NID{nid}-SID{sid:03d}-EID{event_info["eid"]}'

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
                        program.channel_id = channel.id
                        program.network_id = channel.network_id
                        program.service_id = channel.service_id
                        program.event_id = int(event_info['eid'])
                        program.title = title
                        program.description = description
                        program.detail = detail
                        program.start_time = start_time
                        program.end_time = end_time
                        program.duration = (program.end_time - program.start_time).total_seconds()
                        program.is_free = bool(event_info['free_ca_flag'] == 0)  # free_ca_flag が 0 であれば無料放送

                        # ジャンル
                        ## 数字だけでは開発中の視認性が低いのでテキストに変換する
                        program.genres = []  # デフォルト値
                        content_info = event_info.get('content_info')
                        if content_info is not None:
                            for content_data in content_info['nibble_list']:  # ジャンルごとに

                                # 大まかなジャンルを取得
                                genre_tuple = ariblib.constants.CONTENT_TYPE.get(content_data['content_nibble'] >> 8)
                                if genre_tuple is not None:

                                    # major … 大分類
                                    # middle … 中分類
                                    genre_dict: Genre = {
                                        'major': genre_tuple[0].replace('／', '・'),
                                        'middle': genre_tuple[1].get(content_data['content_nibble'] & 0xf, '未定義').replace('／', '・'),
                                    }

                                    # BS/地上デジタル放送用番組付属情報がジャンルに含まれている場合、user_nibble から値を取得して書き換える
                                    # たとえば「中止の可能性あり」や「延長の可能性あり」といった情報が取れる
                                    if genre_dict['major'] == '拡張':
                                        if genre_dict['middle'] == 'BS/地上デジタル放送用番組付属情報':
                                            user_nibble = (content_data['user_nibble'] >> 8 << 4) | (content_data['user_nibble'] & 0xf)
                                            genre_dict['middle'] = ariblib.constants.USER_TYPE.get(user_nibble, '未定義')
                                        # 「拡張」はあるがBS/地上デジタル放送用番組付属情報でない場合はなんの値なのかわからないのでパス
                                        else:
                                            continue

                                    # ジャンルを追加
                                    program.genres.append(genre_dict)

                        # 映像情報
                        ## テキストにするために ariblib.constants や TSInformation の値を使う
                        program.video_type = None
                        program.video_codec = None
                        program.video_resolution = None
                        component_info = event_info.get('component_info')
                        if component_info is not None:
                            ## 映像の種類
                            component_types = ariblib.constants.COMPONENT_TYPE.get(component_info['stream_content'])
                            if component_types is not None:
                                program.video_type = component_types.get(component_info['component_type'])
                            ## 映像のコーデック
                            program.video_codec = TSInformation.STREAM_CONTENT.get(component_info['stream_content'])
                            ## 映像の解像度
                            program.video_resolution = TSInformation.COMPONENT_TYPE.get(component_info['component_type'])

                        # 音声情報
                        program.primary_audio_type = ''
                        program.primary_audio_language = ''
                        program.primary_audio_sampling_rate = ''
                        program.secondary_audio_type = None
                        program.secondary_audio_language = None
                        program.secondary_audio_sampling_rate = None
                        audio_info = event_info.get('audio_info')
                        if audio_info is not None and len(audio_info['component_list']) > 0:

                            ## 主音声
                            audio_component_info = audio_info['component_list'][0]
                            program.primary_audio_type = ariblib.constants.COMPONENT_TYPE[0x02].get(audio_component_info['component_type'], 'Unknown')
                            program.primary_audio_sampling_rate = ariblib.constants.SAMPLING_RATE.get(audio_component_info['sampling_rate'], 'Unknown')
                            ## 2021/09 現在の EDCB では言語コードが取得できないため、日本語か英語で固定する
                            ## EpgDataCap3 のパーサー止まりで EDCB 側では取得していないらしい
                            program.primary_audio_language = '日本語'
                            ## デュアルモノのみ
                            if program.primary_audio_type == '1/0+1/0モード(デュアルモノ)':
                                if audio_component_info['es_multi_lingual_flag'] != 0:  # デュアルモノ時の多言語フラグ
                                    program.primary_audio_language += '+英語'
                                else:
                                    program.primary_audio_language += '+副音声'

                            # 副音声（存在する場合）
                            if len(audio_info['component_list']) > 1:
                                audio_component_info = audio_info['component_list'][1]
                                program.secondary_audio_type = ariblib.constants.COMPONENT_TYPE[0x02].get(audio_component_info['component_type'], 'Unknown')
                                program.secondary_audio_sampling_rate = ariblib.constants.SAMPLING_RATE.get(audio_component_info['sampling_rate'], 'Unknown')
                                ## 2021/09 現在の EDCB では言語コードが取得できないため、副音声で固定する
                                ## 英語かもしれないし解説かもしれない
                                program.secondary_audio_language = '副音声'
                                ## デュアルモノのみ
                                if program.secondary_audio_type == '1/0+1/0モード(デュアルモノ)':
                                    if audio_component_info['es_multi_lingual_flag'] != 0:  # デュアルモノ時の多言語フラグ
                                        program.secondary_audio_language += '+英語'
                                    else:
                                        program.secondary_audio_language += '+副音声'

                        # 番組情報をデータベースに保存する
                        if duplicate_program is None:
                            logging.debug(f'Add Program: {program.id}')
                        else:
                            logging.debug(f'Update Program: {program.id}')

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
                    logging.debug(f'Delete Program: {duplicate_program.id}')
                    try:
                        await duplicate_program.delete()
                    except exceptions.OperationalError:
                        try:
                            await asyncio.sleep(3)
                            await duplicate_program.delete()
                        except exceptions.OperationalError:
                            pass

        # マルチプロセス実行時は、明示的に例外を拾わないとなぜかメインプロセスも含め全体がフリーズしてしまう
        except Exception as ex:
            logging.error('Failed to update programs from EDCB:', exc_info=ex)

        # マルチプロセス実行時は、開いた Tortoise ORM のコネクションを明示的に閉じる
        # コネクションを閉じないと Ctrl+C を押下しても終了できない
        finally:
            if is_running_multiprocess:
                await connections.close_all()

        # 強制的にガベージコレクションを実行する
        gc.collect()


    @classmethod
    def updateFromMirakurunForMultiProcess(cls) -> None:
        """
        Program.updateFromMirakurun() の同期版 (ProcessPoolExecutor でのマルチプロセス実行用)
        """

        # もし Config() の実行時に AssertionError が発生した場合は、LoadConfig() を実行してサーバー設定データをロードする
        ## 通常ならマルチプロセス実行時もサーバー設定データがロードされているはずだが、
        ## 自動リロードモード時のみなぜかグローバル変数がマルチプロセスに引き継がれないため、明示的にロードさせる必要がある
        try:
            Config()
        except AssertionError:
            # バリデーションは既にサーバー起動時に行われているためスキップする
            LoadConfig(bypass_validation=True)

        # asyncio.run() で非同期メソッドの実行が終わるまで待つ
        asyncio.run(cls.updateFromMirakurun(is_running_multiprocess=True))


    @classmethod
    def updateFromEDCBForMultiProcess(cls) -> None:
        """
        Program.updateFromEDCB() の同期版 (ProcessPoolExecutor でのマルチプロセス実行用)
        """

        # もし Config() の実行時に AssertionError が発生した場合は、LoadConfig() を実行してサーバー設定データをロードする
        ## 通常ならマルチプロセス実行時もサーバー設定データがロードされているはずだが、
        ## 自動リロードモード時のみなぜかグローバル変数がマルチプロセスに引き継がれないため、明示的にロードさせる必要がある
        try:
            Config()
        except AssertionError:
            # バリデーションは既にサーバー起動時に行われているためスキップする
            LoadConfig(bypass_validation=True)

        # asyncio.run() で非同期メソッドの実行が終わるまで待つ
        asyncio.run(cls.updateFromEDCB(is_running_multiprocess=True))


    def isOffTheAirProgram(self) -> bool:
        """
        この番組が停波中の番組かを返す
        この番組自身の番組名から判定しているだけで、実際に停波中かを保証するものではない

        Returns:
            bool: 停波中の番組かどうか
        """

        if (('番組情報がありません' == self.title) or
            ('放送休止' in self.title) or
            ('放送終了' in self.title) or
            ('休止' in self.title) or
            ('停波' in self.title)):
            return True

        return False
