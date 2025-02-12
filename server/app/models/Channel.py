
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import httpx
import time
from datetime import datetime
from tortoise import fields
from tortoise import transactions
from tortoise.exceptions import OperationalError
from tortoise.fields import Field as TortoiseField
from tortoise.models import Model as TortoiseModel
from tortoise.exceptions import IntegrityError
from typing import Any, cast, Literal, TYPE_CHECKING
from zoneinfo import ZoneInfo

from app import logging
from app.config import Config
from app.constants import HTTPX_CLIENT
from app.utils import GetMirakurunAPIEndpointURL
from app.utils.edcb.CtrlCmdUtil import CtrlCmdUtil
from app.utils.edcb.EDCBUtil import EDCBUtil
from app.utils.JikkyoClient import JikkyoClient
from app.utils.TSInformation import TSInformation

if TYPE_CHECKING:
    from app.models.Program import Program


class Channel(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'channels'

    # テーブル設計は Notion を参照のこと
    id = fields.CharField(255, pk=True)
    display_channel_id = fields.CharField(255, unique=True)
    network_id = fields.IntField()
    service_id = fields.IntField()
    transport_stream_id = cast(TortoiseField[int | None], fields.IntField(null=True))
    remocon_id = fields.IntField()
    channel_number = fields.CharField(255)
    type = cast(TortoiseField[Literal['GR', 'BS', 'CS', 'CATV', 'SKY', 'BS4K']], fields.CharField(255))
    name = fields.TextField()
    jikkyo_force = cast(TortoiseField[int | None], fields.IntField(null=True))
    is_subchannel = fields.BooleanField()
    is_radiochannel = fields.BooleanField()
    is_watchable = fields.BooleanField()
    # 本当は型を追加したいが、元々動的に追加される追加カラムなので、型を追加すると諸々エラーが出る
    ## 実際の値は Channel モデルの利用側で Channel.getCurrentAndNextProgram() を呼び出して取得する
    ## モデルの取得は非同期のため、@property は使えない
    program_present: Any
    program_following: Any

    @property
    def is_display(self) -> bool:
        # is_watchable が False のチャンネルは録画番組に紐付けられているだけで視聴不可なので常に False を返す
        if self.is_watchable is False:
            return False
        # サブチャンネルでかつ現在の番組情報が両方存在しないなら、表示フラグを False に設定
        # 現在放送されているサブチャンネルのみをチャンネルリストに表示するような挙動とする
        # 一般的にサブチャンネルは常に放送されているわけではないため、放送されていない時にチャンネルリストに表示する必要はない
        if self.is_subchannel is True and self.program_present is None:
            return False
        return True

    @property
    def viewer_count(self) -> int:
        # is_watchable が False のチャンネルは録画番組に紐付けられているだけで視聴不可なので常に 0 を返す
        if self.is_watchable is False:
            return 0
        # 現在の視聴者数を取得
        ## 循環参照を避けるために遅延インポート
        from app.streams.LiveStream import LiveStream
        return LiveStream.getViewerCount(self.display_channel_id)


    @classmethod
    async def update(cls) -> None:
        """ チャンネル情報を更新する """

        timestamp = time.time()
        logging.info('Channels updating...')

        try:
            # Mirakurun バックエンド
            if Config().general.backend == 'Mirakurun':
                await cls.updateFromMirakurun()

            # EDCB バックエンド
            elif Config().general.backend == 'EDCB':
                await cls.updateFromEDCB()
        except Exception as ex:
            logging.error('Failed to update channels:', exc_info=ex)

        logging.info(f'Channels update complete. ({round(time.time() - timestamp, 3)} sec)')


    @classmethod
    async def updateFromMirakurun(cls) -> None:
        """ Mirakurun バックエンドからチャンネル情報を取得し、更新する """

        # このトランザクションはパフォーマンス向上と、チャンネル情報を一時的に削除してから再生成するまでの間に API リクエストが来た場合に
        # "Specified display_channel_id was not found" エラーでフロントエンドを誤動作させるのを防ぐためのもの
        async with transactions.in_transaction():

            # この変数から更新対象のチャンネル情報を削除していき、残った古いチャンネル情報を最後にまとめて削除する
            duplicate_channels = {temp.id:temp for temp in await Channel.filter(is_watchable=True)}

            # Mirakurun / mirakc の API からチャンネル情報を取得する
            try:
                mirakurun_services_api_url = GetMirakurunAPIEndpointURL('/api/services')
                async with HTTPX_CLIENT() as client:
                    mirakurun_services_api_response = await client.get(mirakurun_services_api_url, timeout=5)
                if mirakurun_services_api_response.status_code != 200:  # Mirakurun / mirakc からエラーが返ってきた
                    logging.error(f'Failed to get channels from Mirakurun / mirakc. (HTTP Error {mirakurun_services_api_response.status_code})')
                    raise Exception(f'Failed to get channels from Mirakurun / mirakc. (HTTP Error {mirakurun_services_api_response.status_code})')
                services = mirakurun_services_api_response.json()
            except httpx.NetworkError as ex:
                logging.error('Failed to get channels from Mirakurun / mirakc. (Network Error)')
                raise ex
            except httpx.TimeoutException as ex:
                logging.error('Failed to get channels from Mirakurun / mirakc. (Connection Timeout)')
                raise ex

            # 同じネットワーク ID のサービスのカウント
            same_network_id_counts: dict[int, int] = {}

            # 同じリモコン番号のサービスのカウント
            same_remocon_id_counts: dict[int, int] = {}

            for service in services:

                # type が 0x01 (デジタルTVサービス) / 0x02 (デジタル音声サービス) / 0xa1 (161: 臨時映像サービス) /
                # 0xa2 (162: 臨時音声サービス) / 0xad (173: 超高精細度4K専用TVサービス) 以外のサービスを弾く
                ## ワンセグ・データ放送 (type:0xC0) やエンジニアリングサービス (type:0xA4) など
                ## 詳細は ARIB STD-B10 第2部 6.2.13 に記載されている
                ## https://web.archive.org/web/20140427183421if_/http://www.arib.or.jp/english/html/overview/doc/2-STD-B10v5_3.pdf#page=153
                if service['type'] not in [0x01, 0x02, 0xa1, 0xa2, 0xad]:
                    continue

                # 不明なネットワーク ID のチャンネルを弾く
                channel_type = TSInformation.getNetworkType(service['networkId'])
                if channel_type == 'OTHER':
                    continue

                # チャンネル ID
                channel_id = f'NID{service["networkId"]}-SID{service["serviceId"]:03d}'

                # 既にレコードがある場合は更新、ない場合は新規作成
                duplicate_channel = duplicate_channels.pop(channel_id, None)
                if duplicate_channel is None:
                    # 既に登録されているが、現在は is_watchable = False (録画番組のメタデータのみでライブで視聴不可) なチャンネル情報がある可能性もある
                    # その場合は is_watchable = True (ライブで視聴可能) なチャンネル情報として更新する
                    # 録画番組更新とのタイミングの関係でごく稀に発生しうる問題への対応
                    unwatchable_channel = await Channel.filter(id=channel_id, is_watchable=False).first()
                    if unwatchable_channel is not None:
                        channel = unwatchable_channel
                        channel.is_watchable = True
                        logging.warning(f'Channel: {channel.name} ({channel.id}) is already registered but is_watchable = False.')
                    else:
                        channel = Channel()
                else:
                    channel = duplicate_channel

                # 取得してきた値を設定
                channel.id = channel_id
                channel.service_id = int(service['serviceId'])
                channel.network_id = int(service['networkId'])
                channel.remocon_id = int(service['remoteControlKeyId']) if ('remoteControlKeyId' in service) else 0
                channel.type = channel_type
                channel.name = TSInformation.formatString(service['name'])
                channel.jikkyo_force = None
                channel.is_watchable = True

                # すでに放送が終了した「NHK BSプレミアム」「FOXスポーツ&エンターテインメント」「BSスカパー」「Dlife」を除外
                ## 放送終了後にチャンネルスキャンしていないなどの理由でバックエンド側にチャンネル情報が残っている場合がある
                ## 特に「NHK BSプレミアム」(Ch: 103) は互換性の兼ね合いで停波後も SDT にサービス情報が残っているため、明示的に除外する必要がある
                if channel.type == 'BS' and channel.service_id in [103, 238, 241, 258]:
                    # このチャンネル情報は上記処理で duplicate_channels から削除されているが、
                    # 上記条件に一致するチャンネル情報は DB から削除したいので、再度 duplicate_channels に追加し、最後にまとめて削除する
                    duplicate_channels[channel.id] = channel
                    continue

                # 「試験チャンネル」という名前（前方一致）のチャンネルを除外
                # CATV や SKY に存在するが、だいたいどれもやってないし表示されてるだけ邪魔
                if channel.name.startswith('試験チャンネル'):
                    # このチャンネル情報は上記処理で duplicate_channels から削除されているが、
                    # 上記条件に一致するチャンネル情報は DB から削除したいので、再度 duplicate_channels に追加し、最後にまとめて削除する
                    duplicate_channels[channel.id] = channel
                    continue

                # type が 0x02 のサービスのみ、ラジオチャンネルとして設定する
                # 今のところ、ラジオに該当するチャンネルは放送大学ラジオのみ
                channel.is_radiochannel = True if (service['type'] == 0x02) else False

                # 同じネットワーク内にあるサービスのカウントを追加
                if channel.network_id not in same_network_id_counts:  # まだキーが存在しないとき
                    same_network_id_counts[channel.network_id] = 0
                same_network_id_counts[channel.network_id] += 1  # カウントを足す

                # リモコン番号を算出
                ## 地デジでは既にリモコン番号が決まっているので、そのまま利用する
                if channel.type != 'GR':
                    channel.remocon_id = TSInformation.calculateRemoconID(channel.type, channel.service_id)

                # チャンネル番号を算出
                channel.channel_number = await TSInformation.calculateChannelNumber(
                    channel.type,
                    channel.network_id,
                    channel.service_id,
                    channel.remocon_id,
                    same_network_id_counts,
                    same_remocon_id_counts,
                )

                # 表示用チャンネルID = チャンネルタイプ(小文字)+チャンネル番号
                channel.display_channel_id = channel.type.lower() + channel.channel_number

                # サブチャンネルかどうかを算出
                channel.is_subchannel = TSInformation.calculateIsSubchannel(channel.type, channel.service_id)

                # レコードを保存する
                try:
                    await channel.save()
                # 既に登録されているチャンネルならスキップ
                except IntegrityError:
                    pass

            # 不要なチャンネル情報を削除する
            for duplicate_channel in duplicate_channels.values():
                try:
                    await duplicate_channel.delete()
                # tortoise.exceptions.OperationalError: Can't delete unpersisted record を無視
                except OperationalError as ex:
                    if 'Can\'t delete unpersisted record' not in str(ex):
                        raise ex


    @classmethod
    async def updateFromEDCB(cls) -> None:
        """ EDCB バックエンドからチャンネル情報を取得し、更新する """

        # このトランザクションはパフォーマンス向上と、チャンネル情報を一時的に削除してから再生成するまでの間に API リクエストが来た場合に
        # "Specified display_channel_id was not found" エラーでフロントエンドを誤動作させるのを防ぐためのもの
        async with transactions.in_transaction():

            # この変数から更新対象のチャンネル情報を削除していき、残った古いチャンネル情報を最後にまとめて削除する
            duplicate_channels = {temp.id:temp for temp in await Channel.filter(is_watchable=True)}

            # リモコン番号が取得できない場合に備えてバックアップ
            backup_remocon_ids: dict[str, int] = {channel.id: channel.remocon_id for channel in await Channel.filter(is_watchable=True)}

            # CtrlCmdUtil を初期化
            edcb = CtrlCmdUtil()
            edcb.setConnectTimeOutSec(5)  # 5秒後にタイムアウト

            # EDCB の ChSet5.txt からチャンネル情報を取得する
            chset5_txt = await edcb.sendFileCopy('ChSet5.txt')
            if chset5_txt is not None:
                services = EDCBUtil.parseChSet5(EDCBUtil.convertBytesToString(chset5_txt))
                # 枝番処理がミスらないようソートしておく
                services.sort(key = lambda temp: temp['onid'] * 100000 + temp['sid'])
            else:
                logging.error('Failed to get channels from EDCB.')
                raise Exception('Failed to get channels from EDCB.')

            # EDCB から EPG 由来のチャンネル情報を取得する
            ## sendEnumService() の情報源は番組表で、期限切れなどで番組情報が1つもないサービスについては取得できない
            ## あればラッキー程度の情報と考えてほしい
            epg_services = await edcb.sendEnumService() or []

            # 同じネットワーク ID のサービスのカウント
            same_network_id_counts: dict[int, int] = {}

            # 同じリモコン番号のサービスのカウント
            same_remocon_id_counts: dict[int, int] = {}

            for service in services:

                # type が 0x01 (デジタルTVサービス) / 0x02 (デジタル音声サービス) / 0xa1 (161: 臨時映像サービス) /
                # 0xa2 (162: 臨時音声サービス) / 0xad (173: 超高精細度4K専用TVサービス) 以外のサービスを弾く
                ## ワンセグ・データ放送 (type:0xC0) やエンジニアリングサービス (type:0xA4) など
                ## 詳細は ARIB STD-B10 第2部 6.2.13 に記載されている
                ## https://web.archive.org/web/20140427183421if_/http://www.arib.or.jp/english/html/overview/doc/2-STD-B10v5_3.pdf#page=153
                if service['service_type'] not in [0x01, 0x02, 0xa1, 0xa2, 0xad]:
                    continue

                # 不明なネットワーク ID のチャンネルを弾く
                channel_type = TSInformation.getNetworkType(service['onid'])
                if channel_type == 'OTHER':
                    continue

                # EPG 取得対象でないチャンネルを弾く
                ## EDCB のデフォルトの EPG 取得対象チャンネルはデジタルTVサービスのみ
                ## EDCB で EPG 取得対象でないチャンネルは番組情報が取得できないし、当然予約録画もできず登録しておく意味がない
                ## (BS では極々稀に野球中継の延長時などに臨時サービスが運用されうるが、年に数度あるかないか程度なので当面考慮しない)
                ## この処理により、EDCB 上で有効とされているチャンネル数と KonomiTV 上のチャンネル数が概ね一致するようになる
                ## (上記処理で除外しているワンセグなどのチャンネルが EPG 取得対象になっている場合は一致しないが、基本ないと思うので考慮しない)
                ## これにより、番組検索時のサービス絞り込みリストに EPG 取得対象でないチャンネルが紛れ込むのを回避できる
                ## デジタル音声サービス (service_type: 0x02 / 現在は Ch:531 放送大学ラジオのみ) のみ、デフォルトでは EPG 取得対象に含まれないため通す
                if service['epg_cap_flag'] is False and service['service_type'] != 0x02:
                    continue

                # チャンネル ID
                channel_id = f'NID{service["onid"]}-SID{service["sid"]:03d}'

                # 既にレコードがある場合は更新、ない場合は新規作成
                duplicate_channel = duplicate_channels.pop(channel_id, None)
                if duplicate_channel is None:
                    # 既に登録されているが、現在は is_watchable = False (録画番組のメタデータのみでライブで視聴不可) なチャンネル情報がある可能性もある
                    # その場合は is_watchable = True (ライブで視聴可能) なチャンネル情報として更新する
                    # 録画番組更新とのタイミングの関係でごく稀に発生しうる問題への対応
                    unwatchable_channel = await Channel.filter(id=channel_id, is_watchable=False).first()
                    if unwatchable_channel is not None:
                        channel = unwatchable_channel
                        channel.is_watchable = True
                        logging.warning(f'Channel: {channel.name} ({channel.id}) is already registered but is_watchable = False.')
                    else:
                        channel = Channel()
                else:
                    channel = duplicate_channel

                # 取得してきた値を設定
                channel.id = channel_id
                channel.service_id = int(service['sid'])
                channel.network_id = int(service['onid'])
                channel.transport_stream_id = int(service['tsid'])
                channel.remocon_id = int(service['remocon_id'])  # EDCB-240213 未満の EDCB では ChSet5.txt からリモコン番号を取得できず、常に 0 になる
                channel.type = channel_type
                channel.name = TSInformation.formatString(service['service_name'])
                channel.jikkyo_force = None
                channel.is_watchable = True

                # すでに放送が終了した「NHK BSプレミアム」「FOXスポーツ&エンターテインメント」「BSスカパー」「Dlife」を除外
                ## 放送終了後にチャンネルスキャンしていないなどの理由でバックエンド側にチャンネル情報が残っている場合がある
                ## 特に「NHK BSプレミアム」(Ch: 103) は互換性の兼ね合いで停波後も SDT にサービス情報が残っているため、明示的に除外する必要がある
                if channel.type == 'BS' and channel.service_id in [103, 238, 241, 258]:
                    # このチャンネル情報は上記処理で duplicate_channels から削除されているが、
                    # 上記条件に一致するチャンネル情報は DB から削除したいので、再度 duplicate_channels に追加し、最後にまとめて削除する
                    duplicate_channels[channel.id] = channel
                    continue

                # 「試験チャンネル」という名前（前方一致）のチャンネルを除外
                # CATV や SKY に存在するが、だいたいどれもやってないし表示されてるだけ邪魔
                if channel.name.startswith('試験チャンネル'):
                    # このチャンネル情報は上記処理で duplicate_channels から削除されているが、
                    # 上記条件に一致するチャンネル情報は DB から削除したいので、再度 duplicate_channels に追加し、最後にまとめて削除する
                    duplicate_channels[channel.id] = channel
                    continue

                # type が 0x02 のサービスのみ、ラジオチャンネルとして設定する
                # 今のところ、ラジオに該当するチャンネルは放送大学ラジオのみ
                channel.is_radiochannel = True if (service['service_type'] == 0x02) else False

                # 同じネットワーク内にあるサービスのカウントを追加
                if channel.network_id not in same_network_id_counts:  # まだキーが存在しないとき
                    same_network_id_counts[channel.network_id] = 0
                same_network_id_counts[channel.network_id] += 1  # カウントを足す

                # リモコン番号・チャンネル番号を算出
                ## 地デジ: EDCB からリモコン番号を取得
                if channel.type == 'GR':

                    # EPG 由来のチャンネル情報から現在のチャンネルのリモコン番号を取得
                    ## EDCB-240213 以降であれば ChSet5.txt にリモコン番号が含まれているが、それ以前のバージョンでは
                    ## EPG 由来のチャンネル情報以外からはリモコン番号を取得できないことによる対応
                    epg_service = next(filter(lambda temp: temp['onid'] == channel.network_id and temp['sid'] == channel.service_id, epg_services), None)

                    if epg_service is not None:
                        # EPG 由来のチャンネル情報が取得できていればリモコン番号を取得
                        channel.remocon_id = int(epg_service['remote_control_key_id'])
                    else:
                        # 取得できなかったので、あれば以前のバックアップからリモコン番号を取得
                        if channel.remocon_id <= 0 and channel.id in backup_remocon_ids:
                            channel.remocon_id = backup_remocon_ids.get(channel.id, 0)

                        # それでもリモコン番号が不明の時は、同じネットワーク ID を持つ別サービスのリモコン番号を取得する
                        ## 地上波の臨時サービスはリモコン番号が取得できないことが多い問題への対応
                        if channel.remocon_id <= 0:
                            for temp in epg_services:
                                if temp['onid'] == channel.network_id and temp['sid'] != channel.service_id:
                                    channel.remocon_id = int(temp['remote_control_key_id'])
                                    break

                ## それ以外: サービス ID からリモコン番号を算出
                else:
                    channel.remocon_id = TSInformation.calculateRemoconID(channel.type, channel.service_id)

                # チャンネル番号を算出
                channel.channel_number = await TSInformation.calculateChannelNumber(
                    channel.type,
                    channel.network_id,
                    channel.service_id,
                    channel.remocon_id,
                    same_network_id_counts,
                    same_remocon_id_counts,
                )

                # 表示用チャンネルID = チャンネルタイプ(小文字)+チャンネル番号
                channel.display_channel_id = channel.type.lower() + channel.channel_number

                # サブチャンネルかどうかを算出
                channel.is_subchannel = TSInformation.calculateIsSubchannel(channel.type, channel.service_id)

                # レコードを保存する
                try:
                    await channel.save()
                # 既に登録されているチャンネルならスキップ
                except IntegrityError:
                    logging.warning(f'Channel: {channel.name} ({channel.id}) is already registered.')
                    pass

            # 不要なチャンネル情報を削除する
            for duplicate_channel in duplicate_channels.values():
                try:
                    await duplicate_channel.delete()
                # tortoise.exceptions.OperationalError: Can't delete unpersisted record を無視
                except OperationalError as ex:
                    if 'Can\'t delete unpersisted record' not in str(ex):
                        raise ex


    async def getCurrentAndNextProgram(self) -> tuple[Program | None, Program | None]:
        """
        現在と次の番組情報を取得する

        Returns:
            tuple[Program | None, Program | None]: 現在と次の番組情報が入ったタプル
        """

        # 循環参照を避けるために遅延インポート
        from app.models.Program import Program

        # 現在時刻
        now = datetime.now(ZoneInfo('Asia/Tokyo'))

        # 現在の番組情報を取得する
        program_present = await Program.filter(
            channel_id = self.id,  # 同じ channel_id (ex: NID32736-SID1024)
            start_time__lte = now,  # 番組開始時刻が現在時刻以下
            end_time__gte = now,  # 番組終了時刻が現在時刻以上
        ).order_by('-start_time').first()

        # 次の番組情報を取得する
        program_following = await Program.filter(
            channel_id = self.id,  # 同じ channel_id (ex: NID32736-SID1024)
            start_time__gte = now,  # 番組開始時刻が現在時刻以上
        ).order_by('start_time').first()

        # 現在の番組情報、次の番組情報のタプルを返す
        return (program_present, program_following)


    @classmethod
    async def updateJikkyoStatus(cls) -> None:
        """ チャンネル情報のうち、ニコニコ実況関連のステータスを更新する """

        # 全ての実況チャンネルのステータスを更新
        await JikkyoClient.updateStatuses()

        # 全てのチャンネル情報を取得
        channels = await Channel.filter(is_watchable=True)

        # チャンネル情報ごとに
        for channel in channels:

            # 実況チャンネルのステータスを取得
            jikkyo_client = JikkyoClient(channel.network_id, channel.service_id)
            status = await jikkyo_client.getStatus()

            # ステータスが None（実況チャンネル自体が存在しないか、コミュニティの場合で実況枠が存在しない）でなく、
            # force が -1 (何らかのエラー) でなければステータスを更新
            if status is not None and status['force'] != -1:
                channel.jikkyo_force = status['force']
                await channel.save()
