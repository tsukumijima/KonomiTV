
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import httpx
import time
import traceback
from datetime import datetime
from tortoise import fields
from tortoise import Tortoise
from tortoise import transactions
from tortoise.fields import Field as TortoiseField
from tortoise.models import Model as TortoiseModel
from tortoise.exceptions import ConfigurationError
from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q
from typing import Any, cast, Literal, TYPE_CHECKING
from zoneinfo import ZoneInfo

from app import logging
from app.config import Config
from app.constants import DATABASE_CONFIG, HTTPX_CLIENT
from app.utils import GetMirakurunAPIEndpointURL
from app.utils.edcb.CtrlCmdUtil import CtrlCmdUtil
from app.utils.edcb.EDCBUtil import EDCBUtil
from app.utils.Jikkyo import Jikkyo
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
    type = cast(TortoiseField[Literal['GR', 'BS', 'CS', 'CATV', 'SKY', 'STARDIGIO']], fields.CharField(255))
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
        except Exception:
            traceback.print_exc()

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
                logging.error(f'Failed to get channels from Mirakurun / mirakc. (Network Error)')
                raise ex
            except httpx.TimeoutException as ex:
                logging.error(f'Failed to get channels from Mirakurun / mirakc. (Connection Timeout)')
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
                channel.id = f'NID{service["networkId"]}-SID{service["serviceId"]:03d}'
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
                    continue

                # チャンネルタイプが STARDIGIO でサービス ID が 400 ～ 499 以外のチャンネルを除外
                # だいたい謎の試験チャンネルとかで見るに耐えない
                if channel.type == 'STARDIGIO' and not 400 <= channel.service_id <= 499:
                    continue

                # 「試験チャンネル」という名前（前方一致）のチャンネルを除外
                # CATV や SKY に存在するが、だいたいどれもやってないし表示されてるだけ邪魔
                if channel.name.startswith('試験チャンネル'):
                    continue

                # type が 0x02 のサービスのみ、ラジオチャンネルとして設定する
                # 今のところ、ラジオに該当するチャンネルは放送大学ラジオとスターデジオのみ
                channel.is_radiochannel = True if (service['type'] == 0x02) else False

                # 同じネットワーク内にあるサービスのカウントを追加
                if channel.network_id not in same_network_id_counts:  # まだキーが存在しないとき
                    same_network_id_counts[channel.network_id] = 0
                same_network_id_counts[channel.network_id] += 1  # カウントを足す

                # リモコン番号を算出
                # 地デジでは既にリモコン番号が決まっているので、そのまま利用する
                if channel.type != 'GR':
                    channel.remocon_id = channel.calculateRemoconID()

                # チャンネル番号を算出
                channel.channel_number = await channel.calculateChannelNumber(same_network_id_counts, same_remocon_id_counts)

                # 表示用チャンネルID = チャンネルタイプ(小文字)+チャンネル番号
                channel.display_channel_id = channel.type.lower() + channel.channel_number

                # サブチャンネルかどうかを算出
                channel.is_subchannel = channel.calculateIsSubchannel()

                # レコードを保存する
                try:
                    await channel.save()
                # 既に登録されているチャンネルならスキップ
                except IntegrityError:
                    pass

            # 不要なチャンネル情報を削除する
            for duplicate_channel in duplicate_channels.values():
                await duplicate_channel.delete()


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
                if service['epg_cap_flag'] == False and service['service_type'] != 0x02:
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
                    continue

                # チャンネルタイプが STARDIGIO でサービス ID が 400 ～ 499 以外のチャンネルを除外
                # だいたい謎の試験チャンネルとかで見るに耐えない
                if channel.type == 'STARDIGIO' and not 400 <= channel.service_id <= 499:
                    continue

                # 「試験チャンネル」という名前（前方一致）のチャンネルを除外
                # CATV や SKY に存在するが、だいたいどれもやってないし表示されてるだけ邪魔
                if channel.name.startswith('試験チャンネル'):
                    continue

                # type が 0x02 のサービスのみ、ラジオチャンネルとして設定する
                # 今のところ、ラジオに該当するチャンネルは放送大学ラジオとスターデジオのみ
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
                    channel.remocon_id = channel.calculateRemoconID()

                # チャンネル番号を算出
                channel.channel_number = await channel.calculateChannelNumber(same_network_id_counts, same_remocon_id_counts)

                # 表示用チャンネルID = チャンネルタイプ(小文字)+チャンネル番号
                channel.display_channel_id = channel.type.lower() + channel.channel_number

                # サブチャンネルかどうかを算出
                channel.is_subchannel = channel.calculateIsSubchannel()

                # レコードを保存する
                try:
                    await channel.save()
                # 既に登録されているチャンネルならスキップ
                except IntegrityError:
                    logging.warning(f'Channel: {channel.name} ({channel.id}) is already registered.')
                    pass

            # 不要なチャンネル情報を削除する
            for duplicate_channel in duplicate_channels.values():
                await duplicate_channel.delete()


    def calculateRemoconID(self) -> int:
        """ このチャンネルのリモコン番号を算出する (地デジ以外) """

        assert self.type is not None, 'type not set.'
        assert self.type != 'GR', 'GR type channel is not supported.'
        assert self.service_id is not None, 'service_id not set.'

        # 基本的にはサービス ID をリモコン番号とする
        remocon_id = self.service_id

        # BS: 一部のチャンネルに決め打ちでチャンネル番号を割り当てる
        if self.type == 'BS':
            if 101 <= self.service_id <= 102:
                remocon_id = 1
            elif 103 <= self.service_id <= 104:
                remocon_id = 3
            elif 141 <= self.service_id <= 149:
                remocon_id = 4
            elif 151 <= self.service_id <= 159:
                remocon_id = 5
            elif 161 <= self.service_id <= 169:
                remocon_id = 6
            elif 171 <= self.service_id <= 179:
                remocon_id = 7
            elif 181 <= self.service_id <= 189:
                remocon_id = 8
            elif 191 <= self.service_id <= 193:
                remocon_id = 9
            elif 200 <= self.service_id <= 202:
                remocon_id = 10
            elif self.service_id == 211:
                remocon_id = 11
            elif self.service_id == 222:
                remocon_id = 12

        # SKY: サービス ID を 1024 で割った余りをリモコン番号 (=チャンネル番号) とする
        ## SPHD (network_id=10) のチャンネル番号は service_id - 32768 、
        ## SPSD (SKYサービス系: network_id=3) のチャンネル番号は service_id - 16384 で求められる
        ## 両者とも 1024 の倍数なので、1024 で割った余りからチャンネル番号が算出できる
        elif self.type == 'SKY':
            remocon_id = self.service_id % 1024

        return remocon_id


    async def calculateChannelNumber(self,
        same_network_id_counts: dict[int, int] | None = None,
        same_remocon_id_counts: dict[int, int] | None = None,
    ) -> str:
        """ このチャンネルのチャンネル番号を算出する """

        assert self.id is not None, 'id not set.'
        assert self.type is not None, 'type not set.'
        assert self.network_id is not None, 'network_id not set.'
        assert self.service_id is not None, 'service_id not set.'
        assert self.remocon_id is not None, 'remocon_id not set.'

        # 基本的にはサービス ID をチャンネル番号とする
        channel_number = str(self.service_id).zfill(3)

        # 地デジ: リモコン番号からチャンネル番号を算出する (枝番処理も行う)
        if self.type == 'GR' and same_remocon_id_counts is not None and same_network_id_counts is not None:

            # 同じリモコン番号のサービスのカウントを定義
            if self.remocon_id not in same_remocon_id_counts:  # まだキーが存在しないとき
                # 011(-0), 011-1, 011-2 のように枝番をつけるため、ネットワーク ID とは異なり -1 を基点とする
                same_remocon_id_counts[self.remocon_id] = -1

            # 同じネットワーク内にある最初のサービスのときだけ、同じリモコン番号のサービスのカウントを追加
            # これをやらないと、サブチャンネルまで枝番処理の対象になってしまう
            if same_network_id_counts[self.network_id] == 1:
                same_remocon_id_counts[self.remocon_id] += 1

            # 上2桁はリモコン番号から、下1桁は同じネットワーク内にあるサービスのカウント
            channel_number = str(self.remocon_id).zfill(2) + str(same_network_id_counts[self.network_id])

            # 同じリモコン番号のサービスが複数ある場合、枝番をつける
            if same_remocon_id_counts[self.remocon_id] > 0:
                channel_number += '-' + str(same_remocon_id_counts[self.remocon_id])

        # 地デジ (録画番組向け): リモコン番号からチャンネル番号を算出する (枝番処理も行うが、DB アクセスが発生する)
        elif self.type == 'GR':

            # 同じネットワーク内にあるサービスのカウントを取得
            ## 地デジのサービス ID は、ARIB TR-B14 第五分冊 第七編 9.1 によると
            ## (地域種別:6bit)(県複フラグ:1bit)(サービス種別:2bit)(地域事業者識別:4bit)(サービス番号:3bit) の 16bit で構成されている
            ## 0x0007 はビット単位に直すと 0b0000000110000111 になるので、AND 演算でビットマスク（1以外のビットを強制的に0に設定）すると、
            ## サービス番号 (0~7) のみを取得できる (1~8 に直すために +1 する)
            same_network_id_count = (self.service_id & 0x0007) + 1

            # 上2桁はリモコン番号から、下1桁は同じネットワーク内にあるサービスのカウント
            channel_number = str(self.remocon_id).zfill(2) + str(same_network_id_count)

            # Tortoise ORM のコネクションが取得できない時は Tortoise ORM を初期化する
            ## 基本 MetadataAnalyzer を単独で実行したときくらいしか起きないはず…
            cleanup_required = False
            try:
                Tortoise.get_connection('default')
            except ConfigurationError:
                await Tortoise.init(config=DATABASE_CONFIG)
                cleanup_required = True

            # 同じチャンネル番号のサービスのカウントを DB から取得
            ## チャンネル ID は NID-SID の組 (CATV を除き日本全国で一意) なので、
            ## チャンネル ID が異なる場合は同じリモコン番号/チャンネル番号でも別チャンネルになる
            ## ex: tvk1 (gr031) / NHK総合1・福岡 (gr031)
            same_channel_number_count = await Channel.filter(
                ~Q(id = self.id),  # チャンネル ID が自身のチャンネル ID と異なる (=異なるチャンネルだがチャンネル番号が同じ)
                channel_number = channel_number,  # チャンネル番号が同じ
                type = 'GR',  # 地デジのみ
            ).count()

            # Tortoise ORM を独自に初期化した場合は、開いた Tortoise ORM のコネクションを明示的に閉じる
            # コネクションを閉じないと Ctrl+C を押下しても終了できない
            if cleanup_required is True:
                await Tortoise.close_connections()

            # 異なる NID-SID で同じチャンネル番号のサービスが複数ある場合、枝番をつける
            ## same_channel_number_count は自身を含まないため、1 以上の場合は枝番をつける
            if same_channel_number_count >= 1:
                channel_number += '-' + str(same_channel_number_count)

        # SKY: サービス ID を 1024 で割った余りをチャンネル番号とする
        ## SPHD (network_id=10) のチャンネル番号は service_id - 32768 、
        ## SPSD (SKYサービス系: network_id=3) のチャンネル番号は service_id - 16384 で求められる
        ## 両者とも 1024 の倍数なので、1024 で割った余りからチャンネル番号が
        ## 両者とも 1024 の倍数なので、1024 で割った余りからチャンネル番号が算出できる
        elif self.type == 'SKY':
            channel_number = str(self.service_id % 1024).zfill(3)

        return channel_number


    def calculateIsSubchannel(self) -> bool:
        """ このチャンネルがサブチャンネルかどうかを算出する """

        assert self.type is not None, 'type not set.'
        assert self.service_id is not None, 'service_id not set.'

        # 地デジ: サービス ID に 0x0187 を AND 演算（ビットマスク）した時に 0 でない場合
        ## 地デジのサービス ID は、ARIB TR-B14 第五分冊 第七編 9.1 によると
        ## (地域種別:6bit)(県複フラグ:1bit)(サービス種別:2bit)(地域事業者識別:4bit)(サービス番号:3bit) の 16bit で構成されている
        ## 0x0187 はビット単位に直すと 0b0000000110000111 になるので、AND 演算でビットマスク（1以外のビットを強制的に0に設定）すると、
        ## サービス種別とサービス番号のみを取得できる  ビットマスクした値のサービス種別が 0（テレビ型）でサービス番号が 0（プライマリサービス）であれば
        ## メインチャンネルと判定できるし、そうでなければサブチャンネルだと言える
        if self.type == 'GR':
            is_subchannel = (self.service_id & 0x0187) != 0

        # BS: EDCB / Mirakurun から得られる情報からはサブチャンネルかを判定できないため、決め打ちで設定
        elif self.type == 'BS':
            # サービス ID が以下のリストに含まれるかどうか
            if ((self.service_id in [102, 104]) or
                (142 <= self.service_id <= 149) or
                (152 <= self.service_id <= 159) or
                (162 <= self.service_id <= 169) or
                (172 <= self.service_id <= 179) or
                (182 <= self.service_id <= 189) or
                (self.service_id in [232, 233])):
                is_subchannel = True
            else:
                is_subchannel = False

        # それ以外: サブチャンネルという概念自体がないため一律で False に設定
        else:
            is_subchannel = False

        return is_subchannel


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
        await Jikkyo.updateStatuses()

        # 全てのチャンネル情報を取得
        channels = await Channel.filter(is_watchable=True)

        # チャンネル情報ごとに
        for channel in channels:

            # 実況チャンネルのステータスを取得
            jikkyo = Jikkyo(channel.network_id, channel.service_id)
            status = await jikkyo.getStatus()

            # ステータスが None（実況チャンネル自体が存在しないか、コミュニティの場合で実況枠が存在しない）でなく、
            # force が -1 (何らかのエラー) でなければステータスを更新
            if status != None and status['force'] != -1:
                channel.jikkyo_force = status['force']
                await channel.save()
