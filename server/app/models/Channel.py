
import asyncio
import requests
import time
from tortoise import fields
from tortoise import models
from tortoise import timezone
from tortoise.exceptions import IntegrityError
from typing import Literal, Optional

from app.constants import CONFIG
from app.utils import Jikkyo
from app.utils import Logging
from app.utils import TSInformation
from app.utils.EDCB import CtrlCmdUtil
from app.utils.EDCB import EDCBUtil


class Channel(models.Model):

    # データベース上のテーブル名
    class Meta:
        table: str = 'channels'

    # テーブル設計は Notion を参照のこと
    id: str = fields.TextField(pk=True)
    network_id: int = fields.IntField()
    service_id: int = fields.IntField()
    transport_stream_id: Optional[int] = fields.IntField(null=True)
    remocon_id: Optional[int] = fields.IntField(null=True)
    channel_id: str = fields.TextField()
    channel_number: str = fields.TextField()
    channel_name: str = fields.TextField()
    channel_type: Literal['GR', 'BS', 'CS', 'CATV', 'SKY', 'STARDIGIO'] = fields.TextField()
    channel_force: Optional[int] = fields.IntField(null=True)
    channel_comment: Optional[int] = fields.IntField(null=True)
    is_subchannel: bool = fields.BooleanField()
    is_radiochannel: bool = fields.BooleanField()


    @classmethod
    async def update(cls) -> None:
        """ チャンネル情報を更新する """

        timestamp = time.time()

        # Mirakurun バックエンド
        if CONFIG['general']['backend'] == 'Mirakurun':
            await cls.updateFromMirakurun()

        # EDCB バックエンド
        elif CONFIG['general']['backend'] == 'EDCB':
            await cls.updateFromEDCB()

        Logging.info(f'Channels update complete. ({round(time.time() - timestamp, 3)} sec)')


    @classmethod
    async def updateFromMirakurun(cls) -> None:
        """ Mirakurun バックエンドからチャンネル情報を取得し、更新する """

        # 既にデータベースにチャンネル情報が存在する場合は一旦全て削除する
        await Channel.all().delete()

        # Mirakurun の API からチャンネル情報を取得する
        try:
            mirakurun_services_api_url = f'{CONFIG["general"]["mirakurun_url"]}/api/services'
            mirakurun_services_api_response = await asyncio.to_thread(requests.get, mirakurun_services_api_url, timeout=3)
            if mirakurun_services_api_response.status_code != 200:  # Mirakurun からエラーが返ってきた
                Logging.error(f'Failed to get channels from Mirakurun. (HTTP Error {mirakurun_services_api_response.status_code})')
                return
            services = mirakurun_services_api_response.json()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            Logging.error(f'Failed to get channels from Mirakurun. (Connection Timeout)')
            return

        # 同じネットワーク ID のサービスのカウント
        same_network_id_counts = {}

        # 同じリモコン番号のサービスのカウント
        same_remocon_id_counts = {}

        # サービスごとに実行
        for service in services:

            # type が 0x01 (デジタルTVサービス) / 0x02 (デジタル音声サービス) / 0xa1 (161: 臨時映像サービス) /
            # 0xa2 (162: 臨時音声サービス) / 0xad (173: 超高精細度4K専用TVサービス) 以外のサービスを弾く
            ## ワンセグ・データ放送 (type:0xC0) やエンジニアリングサービス (type:0xA4) など
            ## 詳細は ARIB STD-B10 第2部 6.2.13 に記載されている
            ## https://web.archive.org/web/20140427183421if_/http://www.arib.or.jp/english/html/overview/doc/2-STD-B10v5_3.pdf#page=153
            if service['type'] not in [0x01, 0x02, 0xa1, 0xa2, 0xad]:
                continue

            # 不明なネットワーク ID のチャンネルを弾く
            if TSInformation.getNetworkType(service['networkId']) == 'OTHER':
                continue

            # 新しいチャンネルのレコードを作成
            channel = Channel()

            # 取得してきた値を設定
            channel.id = f'NID{service["networkId"]}-SID{service["serviceId"]:03d}'
            channel.service_id = service['serviceId']
            channel.network_id = service['networkId']
            channel.remocon_id = service['remoteControlKeyId'] if ('remoteControlKeyId' in service) else None
            channel.channel_name = TSInformation.formatString(service['name'])
            channel.channel_type = TSInformation.getNetworkType(channel.network_id)
            channel.channel_force = None
            channel.channel_comment = None

            # チャンネルタイプが STARDIGIO でサービス ID が 400 ～ 499 以外のチャンネルを除外
            # だいたい謎の試験チャンネルとかで見るに耐えない
            if channel.channel_type == 'STARDIGIO' and not 400 <= channel.service_id <= 499:
                continue

            # 「試験チャンネル」という名前（前方一致）のチャンネルを除外
            # CATV や SKY に存在するが、だいたいどれもやってないし表示されてるだけ邪魔
            if channel.channel_name.startswith('試験チャンネル'):
                continue

            # type が 0x02 のサービスのみ、ラジオチャンネルとして設定する
            # 今のところ、ラジオに該当するチャンネルは放送大学ラジオとスターデジオのみ
            channel.is_radiochannel = True if (service['type'] == 0x02) else False

            # 同じネットワーク ID のチャンネルのカウントを追加
            if channel.network_id not in same_network_id_counts:  # まだキーが存在しないとき
                same_network_id_counts[channel.network_id] = 0
            same_network_id_counts[channel.network_id] += 1  # カウントを足す

            # ***** チャンネル番号・チャンネル ID を算出 *****

            # 地デジ: リモコン番号からチャンネル番号を算出する
            if channel.channel_type == 'GR':

                # リモコン番号が不明のときはとりあえず 0 とする
                if channel.remocon_id is None:
                    channel.remocon_id = 0

                # 同じリモコン番号のサービスのカウントを定義
                if channel.remocon_id not in same_remocon_id_counts:  # まだキーが存在しないとき
                    # 011(-0), 011-1, 011-2 のように枝番をつけるため、ネットワーク ID とは異なり -1 を基点とする
                    same_remocon_id_counts[channel.remocon_id] = -1

                # 同じネットワーク内にある最初のサービスのときだけ、同じリモコン番号のサービスのカウントを追加
                # これをやらないと、サブチャンネルまで枝番処理の対象になってしまう
                if same_network_id_counts[channel.network_id] == 1:
                    same_remocon_id_counts[channel.remocon_id] += 1

                # 上2桁はリモコン番号から、下1桁は同じネットワーク内にあるサービスのカウント
                channel.channel_number = str(channel.remocon_id).zfill(2) + str(same_network_id_counts[channel.network_id])

                # 同じリモコン番号のサービスが複数ある場合、枝番をつける
                if same_remocon_id_counts[channel.remocon_id] > 0:
                    channel.channel_number += '-' + str(same_remocon_id_counts[channel.remocon_id])

            # BS・CS・CATV・STARDIGIO: サービス ID をそのままチャンネル番号・リモコン番号とする
            elif (channel.channel_type == 'BS' or
                  channel.channel_type == 'CS' or
                  channel.channel_type == 'CATV' or
                  channel.channel_type == 'STARDIGIO'):
                channel.remocon_id = channel.service_id  # ソートする際の便宜上設定しておく
                channel.channel_number = str(channel.service_id).zfill(3)

                # BS のみ、一部のチャンネルに決め打ちでチャンネル番号を割り当てる
                if channel.channel_type == 'BS':
                    if 101 <= channel.service_id <= 102:
                        channel.remocon_id = 1
                    elif 103 <= channel.service_id <= 104:
                        channel.remocon_id = 3
                    elif 141 <= channel.service_id <= 149:
                        channel.remocon_id = 4
                    elif 151 <= channel.service_id <= 159:
                        channel.remocon_id = 5
                    elif 161 <= channel.service_id <= 169:
                        channel.remocon_id = 6
                    elif 171 <= channel.service_id <= 179:
                        channel.remocon_id = 7
                    elif 181 <= channel.service_id <= 189:
                        channel.remocon_id = 8
                    elif 191 <= channel.service_id <= 193:
                        channel.remocon_id = 9
                    elif 200 <= channel.service_id <= 202:
                        channel.remocon_id = 10
                    elif channel.service_id == 211:
                        channel.remocon_id = 11
                    elif channel.service_id == 222:
                        channel.remocon_id = 12

            # SKY: サービス ID を 1024 で割った余りをチャンネル番号・リモコン番号とする
            ## SPHD (network_id=10) のチャンネル番号は service_id - 32768 、
            ## SPSD (SKYサービス系: network_id=3) のチャンネル番号は service_id - 16384 で求められる
            ## 両者とも 1024 の倍数なので、1024 で割った余りからチャンネル番号が算出できる
            elif channel.channel_type == 'SKY':
                channel.remocon_id = channel.service_id % 1024  # ソートする際の便宜上設定しておく
                channel.channel_number = str(channel.service_id % 1024).zfill(3)

            # チャンネルID = チャンネルタイプ(小文字)+チャンネル番号
            channel.channel_id = channel.channel_type.lower() + channel.channel_number

            # ***** サブチャンネルかどうかを算出 *****

            # 地デジ: サービス ID に 0x0187 を AND 演算（ビットマスク）した時に 0 でない場合
            ## 地デジのサービス ID は、ARIB TR-B14 第五分冊 第七編 9.1 によると
            ## (地域種別:6bit)(県複フラグ:1bit)(サービス種別:2bit)(地域事業者識別:4bit)(サービス番号:3bit) の 16bit で構成されている
            ## 0x0187 はビット単位に直すと 0b0000000110000111 になるので、AND 演算でビットマスク（1以外のビットを強制的に0に設定）すると、
            ## サービス種別とサービス番号だけが取得できる  ビットマスクした値のサービス種別が 0（テレビ型）でサービス番号が 0（プライマリサービス）であれば
            ## メインチャンネルと判定できるし、そうでなければサブチャンネルだと言える
            if channel.channel_type == 'GR':
                channel.is_subchannel = (channel.service_id & 0x0187) != 0

            # BS: Mirakurun から得られる情報からはサブチャンネルかを判定できないため、決め打ちで設定
            elif channel.channel_type == 'BS':
                # サービス ID が以下のリストに含まれるかどうか
                if ((channel.service_id in [102, 104]) or
                    (142 <= channel.service_id <= 149) or
                    (152 <= channel.service_id <= 159) or
                    (162 <= channel.service_id <= 169) or
                    (172 <= channel.service_id <= 179) or
                    (182 <= channel.service_id <= 189)):
                    channel.is_subchannel = True
                else:
                    channel.is_subchannel = False

            # それ以外: サブチャンネルという概念自体がないため一律で False に設定
            else:
                channel.is_subchannel = False

            # レコードを保存する
            await channel.save()


    @classmethod
    async def updateFromEDCB(cls) -> None:
        """ EDCB バックエンドからチャンネル情報を取得し、更新する """

        # リモコン番号が取得できない場合に備えてバックアップ
        backup_remocon_ids = {channel.id: channel.remocon_id for channel in await Channel.all()}

        # 既にデータベースにチャンネル情報が存在する場合は一旦全て削除する
        await Channel.all().delete()

        # CtrlCmdUtil を初期化
        edcb = CtrlCmdUtil()
        edcb.setConnectTimeOutSec(3)  # 3秒後にタイムアウト

        # EDCB の ChSet5.txt からチャンネル情報を取得する
        services = await edcb.sendFileCopy('ChSet5.txt')
        if services is not None:
            services = EDCBUtil.parseChSet5(EDCBUtil.convertBytesToString(services))
            # 枝番処理がミスらないようソートしておく
            services.sort(key = lambda temp: temp['onid'] * 100000 + temp['sid'])
        else:
            Logging.error(f'Failed to get channels from EDCB.')
            return

        # EDCB から EPG 由来のチャンネル情報を取得する
        # sendEnumService() の情報源は番組表で、期限切れなどで番組情報が1つもないサービスについては取得できない
        # あればラッキー程度の情報と考えてほしい
        epg_services = await edcb.sendEnumService() or []

        # 同じネットワーク ID のサービスのカウント
        same_network_id_counts = {}

        # 同じリモコン番号のサービスのカウント
        same_remocon_id_counts = {}

        for service in services:

            # type が 0x01 (デジタルTVサービス) / 0x02 (デジタル音声サービス) / 0xa1 (161: 臨時映像サービス) /
            # 0xa2 (162: 臨時音声サービス) / 0xad (173: 超高精細度4K専用TVサービス) 以外のサービスを弾く
            ## ワンセグ・データ放送 (type:0xC0) やエンジニアリングサービス (type:0xA4) など
            ## 詳細は ARIB STD-B10 第2部 6.2.13 に記載されている
            ## https://web.archive.org/web/20140427183421if_/http://www.arib.or.jp/english/html/overview/doc/2-STD-B10v5_3.pdf#page=153
            if service['service_type'] not in [0x01, 0x02, 0xa1, 0xa2, 0xad]:
                continue

            # 不明なネットワーク ID のチャンネルを弾く
            if TSInformation.getNetworkType(service['onid']) == 'OTHER':
                continue

            # 新しいチャンネルのレコードを作成
            channel = Channel()

            # 取得してきた値を設定
            channel.id = f'NID{service["onid"]}-SID{service["sid"]:03d}'
            channel.service_id = service['sid']
            channel.network_id = service['onid']
            channel.transport_stream_id = service['tsid']
            channel.remocon_id = None
            channel.channel_name = TSInformation.formatString(service['service_name'])
            channel.channel_type = TSInformation.getNetworkType(channel.network_id)
            channel.channel_force = None
            channel.channel_comment = None

            # チャンネルタイプが STARDIGIO でサービス ID が 400 ～ 499 以外のチャンネルを除外
            # だいたい謎の試験チャンネルとかで見るに耐えない
            if channel.channel_type == 'STARDIGIO' and not 400 <= channel.service_id <= 499:
                continue

            # 「試験チャンネル」という名前（前方一致）のチャンネルを除外
            # CATV や SKY に存在するが、だいたいどれもやってないし表示されてるだけ邪魔
            if channel.channel_name.startswith('試験チャンネル'):
                continue

            # type が 0x02 のサービスのみ、ラジオチャンネルとして設定する
            # 今のところ、ラジオに該当するチャンネルは放送大学ラジオとスターデジオのみ
            channel.is_radiochannel = True if (service['service_type'] == 0x02) else False

            # 同じネットワーク内にあるサービスのカウントを追加
            if channel.network_id not in same_network_id_counts:  # まだキーが存在しないとき
                same_network_id_counts[channel.network_id] = 0
            same_network_id_counts[channel.network_id] += 1  # カウントを足す

            # ***** チャンネル番号・チャンネル ID を算出 *****

            # 地デジ: リモコン番号からチャンネル番号を算出する
            if channel.channel_type == 'GR':

                # EPG 由来のチャンネル情報を取得
                # 現在のチャンネルのリモコン番号が含まれる
                epg_service = next(filter(lambda temp: temp['onid'] == channel.network_id and temp['sid'] == channel.service_id, epg_services), None)

                if epg_service is not None:
                    # EPG 由来のチャンネル情報が取得できていればリモコン番号を取得
                    channel.remocon_id = epg_service['remote_control_key_id']
                else:
                    # 取得できなかったので、あれば以前のバックアップからリモコン番号を取得
                    # それでもリモコン番号が不明のときはとりあえず 0 とする
                    channel.remocon_id = backup_remocon_ids.get(channel.id, 0)

                # 同じリモコン番号のサービスのカウントを定義
                if channel.remocon_id not in same_remocon_id_counts:  # まだキーが存在しないとき
                    # 011(-0), 011-1, 011-2 のように枝番をつけるため、ネットワーク ID とは異なり -1 を基点とする
                    same_remocon_id_counts[channel.remocon_id] = -1

                # 同じネットワーク内にある最初のサービスのときだけ、同じリモコン番号のサービスのカウントを追加
                # これをやらないと、サブチャンネルまで枝番処理の対象になってしまう
                if same_network_id_counts[channel.network_id] == 1:
                    same_remocon_id_counts[channel.remocon_id] += 1

                # 上2桁はリモコン番号から、下1桁は同じネットワーク内にあるサービスのカウント
                channel.channel_number = str(channel.remocon_id).zfill(2) + str(same_network_id_counts[channel.network_id])

                # 同じリモコン番号のサービスが複数ある場合、枝番をつける
                if same_remocon_id_counts[channel.remocon_id] > 0:
                    channel.channel_number += '-' + str(same_remocon_id_counts[channel.remocon_id])

            # BS・CS・CATV・STARDIGIO: サービス ID をそのままチャンネル番号・リモコン番号とする
            elif (channel.channel_type == 'BS' or
                  channel.channel_type == 'CS' or
                  channel.channel_type == 'CATV' or
                  channel.channel_type == 'STARDIGIO'):
                channel.remocon_id = channel.service_id  # ソートする際の便宜上設定しておく
                channel.channel_number = str(channel.service_id).zfill(3)

                # BS のみ、一部のチャンネルに決め打ちでチャンネル番号を割り当てる
                if channel.channel_type == 'BS':
                    if 101 <= channel.service_id <= 102:
                        channel.remocon_id = 1
                    elif 103 <= channel.service_id <= 104:
                        channel.remocon_id = 3
                    elif 141 <= channel.service_id <= 149:
                        channel.remocon_id = 4
                    elif 151 <= channel.service_id <= 159:
                        channel.remocon_id = 5
                    elif 161 <= channel.service_id <= 169:
                        channel.remocon_id = 6
                    elif 171 <= channel.service_id <= 179:
                        channel.remocon_id = 7
                    elif 181 <= channel.service_id <= 189:
                        channel.remocon_id = 8
                    elif 191 <= channel.service_id <= 193:
                        channel.remocon_id = 9
                    elif 200 <= channel.service_id <= 202:
                        channel.remocon_id = 10
                    elif channel.service_id == 211:
                        channel.remocon_id = 11
                    elif channel.service_id == 222:
                        channel.remocon_id = 12

            # SKY: サービス ID を 1024 で割った余りをチャンネル番号・リモコン番号とする
            ## SPHD (network_id=10) のチャンネル番号は service_id - 32768 、
            ## SPSD (SKYサービス系: network_id=3) のチャンネル番号は service_id - 16384 で求められる
            ## 両者とも 1024 の倍数なので、1024 で割った余りからチャンネル番号が算出できる
            elif channel.channel_type == 'SKY':
                channel.remocon_id = channel.service_id % 1024  # ソートする際の便宜上設定しておく
                channel.channel_number = str(channel.service_id % 1024).zfill(3)

            # チャンネルID = チャンネルタイプ(小文字)+チャンネル番号
            channel.channel_id = channel.channel_type.lower() + channel.channel_number

            # ***** サブチャンネルかどうかを算出 *****

            # 地デジ: サービス ID に 0x0187 を AND 演算（ビットマスク）した時に 0 でない場合
            ## 地デジのサービス ID は、ARIB TR-B14 第五分冊 第七編 9.1 によると
            ## (地域種別:6bit)(県複フラグ:1bit)(サービス種別:2bit)(地域事業者識別:4bit)(サービス番号:3bit) の 16bit で構成されている
            ## 0x0187 はビット単位に直すと 0b0000000110000111 になるので、AND 演算でビットマスク（1以外のビットを強制的に0に設定）すると、
            ## サービス種別とサービス番号だけが取得できる  ビットマスクした値のサービス種別が 0（テレビ型）でサービス番号が 0（プライマリサービス）であれば
            ## メインチャンネルと判定できるし、そうでなければサブチャンネルだと言える
            if channel.channel_type == 'GR':
                channel.is_subchannel = (channel.service_id & 0x0187) != 0

            # BS: EDCB から得られる情報からはサブチャンネルかを判定できないため、決め打ちで設定
            elif channel.channel_type == 'BS':
                # サービス ID が以下のリストに含まれるかどうか
                if ((channel.service_id in [102, 104]) or
                    (142 <= channel.service_id <= 149) or
                    (152 <= channel.service_id <= 159) or
                    (162 <= channel.service_id <= 169) or
                    (172 <= channel.service_id <= 179) or
                    (182 <= channel.service_id <= 189)):
                    channel.is_subchannel = True
                else:
                    channel.is_subchannel = False

            # それ以外: サブチャンネルという概念自体がないため一律で False に設定
            else:
                channel.is_subchannel = False

            # レコードを保存する
            try:
                await channel.save()
            # 既に登録されているチャンネルならスキップ
            except IntegrityError:
                pass


    @classmethod
    async def updateJikkyoStatus(cls) -> None:
        """ チャンネル情報のうち、ニコニコ実況関連のステータスを更新する """

        # 全ての実況チャンネルのステータスを更新
        await Jikkyo.updateStatus()

        # 全てのチャンネル情報を取得
        channels = await Channel.all()

        # チャンネル情報ごとに
        for channel in channels:

            # 実況チャンネルのステータスを取得
            jikkyo = Jikkyo(channel.network_id, channel.service_id)
            status = await jikkyo.getStatus()

            # ステータスが None（実況チャンネル自体が存在しないか、コミュニティの場合で実況枠が存在しない）でなく、force が -1 でなければ
            if status != None and status['force'] != -1:

                # ステータスを更新
                channel.channel_force = status['force']
                channel.channel_comment = status['comments']
                await channel.save()


    async def getCurrentAndNextProgram(self) -> tuple:
        """
        現在と次の番組情報を取得する

        Returns:
            tuple: 現在と次の番組情報が入ったタプル
        """

        # モジュール扱いになるのを避けるためここでインポート
        from app.models import Program

        # 現在時刻
        now = timezone.now()

        # 現在の番組情報を取得する
        program_present = await Program.filter(
            channel_id = self.channel_id,  # 同じチャンネルID
            start_time__lte = now,  # 番組開始時刻が現在時刻以下
            end_time__gte = now,  # 番組終了時刻が現在時刻以上
        ).order_by('-start_time').first()

        # 次の番組情報を取得する
        program_following = await Program.filter(
            channel_id = self.channel_id,  # 同じチャンネルID
            start_time__gte = now,  # 番組開始時刻が現在時刻以上
        ).order_by('start_time').first()

        # 現在の番組情報、次の番組情報のタプルを返す
        return (program_present, program_following)
