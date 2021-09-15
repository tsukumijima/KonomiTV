
import requests
from tortoise import fields
from tortoise import models
from tortoise import timezone
from tortoise.exceptions import IntegrityError
from typing import Optional

from app.constants import CONFIG
from app.utils import Jikkyo
from app.utils import RunAsync
from app.utils import TSInformation
from app.utils import ZenkakuToHankaku
from app.utils.EDCB import EDCBUtil, CtrlCmdUtil


class Channels(models.Model):

    # テーブル設計は Notion を参照のこと
    id:str = fields.TextField(pk=True)
    service_id:int = fields.IntField()
    network_id:int = fields.IntField()
    transport_stream_id:Optional[int] = fields.IntField(null=True)
    remocon_id:Optional[int] = fields.IntField(null=True)
    channel_id:str = fields.TextField()
    channel_number:str = fields.TextField()
    channel_name:str = fields.TextField()
    channel_type:str = fields.TextField()
    channel_force:Optional[int] = fields.IntField(null=True)
    channel_comment:Optional[int] = fields.IntField(null=True)
    is_subchannel:bool = fields.BooleanField()


    @classmethod
    async def update(cls) -> None:
        """チャンネル情報を更新する"""

        # Mirakurun バックエンド
        if CONFIG['general']['backend'] == 'Mirakurun':
            await cls.updateFromMirakurun()

        # EDCB バックエンド
        elif CONFIG['general']['backend'] == 'EDCB':
            await cls.updateFromEDCB()


    @classmethod
    async def updateFromMirakurun(cls) -> None:
        """Mirakurun バックエンドからチャンネル情報を取得し、更新する"""

        # 既にデータベースにチャンネル情報が存在する場合は一旦全て削除する
        await Channels.all().delete()

        # Mirakurun の API からチャンネル情報を取得する
        mirakurun_services_api_url = f'{CONFIG["general"]["mirakurun_url"]}/api/services'
        services = (await RunAsync(requests.get, mirakurun_services_api_url)).json()

        # 同じネットワーク ID のサービスのカウント
        same_network_id_counts = dict()

        # 同じリモコン番号のサービスのカウント
        same_remocon_id_counts = dict()

        # サービスごとに実行
        for service in services:

            # type が 1 以外のサービス（＝ワンセグやデータ放送 (type:192) など）を弾く
            if service['type'] != 1:
                continue

            # 新しいチャンネルのレコードを作成
            channel = Channels()

            # 取得してきた値を設定
            channel.id = f'NID{service["networkId"]}-SID{service["serviceId"]:03d}'
            channel.service_id = service['serviceId']
            channel.network_id = service['networkId']
            channel.remocon_id = service['remoteControlKeyId'] if ('remoteControlKeyId' in service) else None
            channel.channel_name = ZenkakuToHankaku(service['name']).replace('：', ':')
            channel.channel_type = service['channel']['type']
            channel.channel_force = None
            channel.channel_comment = None

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

            # BS・CS・SKY: サービス ID をそのままチャンネル番号・リモコン番号とする
            else:
                channel.remocon_id = channel.service_id  # ソートする際の便宜上設定しておく
                channel.channel_number = str(channel.service_id).zfill(3)

            # チャンネルID = チャンネルタイプ(小文字)+チャンネル番号
            channel.channel_id = channel.channel_type.lower() + channel.channel_number

            # ***** サブチャンネルかどうかを算出 *****

            # 地デジ: チャンネル番号の下一桁が 1 以外かどうか
            if channel.channel_type == 'GR':
                channel.is_subchannel = bool(channel.channel_number[2:] != '1')

            # BS: Mirakurun から得られる情報からはサブチャンネルかを判定できないため、決め打ちで設定
            elif channel.channel_type == 'BS':
                # サービス ID が以下のリストに含まれるかどうか
                if channel.service_id in [102, 104, 142, 143, 152, 153, 162, 163, 172, 173, 182, 183]:
                    channel.is_subchannel = True
                else:
                    channel.is_subchannel = False

            # CS・SKY: サブチャンネルという概念自体がないため一律で False に設定
            else:
                channel.is_subchannel = False

            # レコードを保存する
            await channel.save()


    @classmethod
    async def updateFromEDCB(cls) -> None:
        """EDCB バックエンドからチャンネル情報を取得し、更新する"""

        # リモコン番号が取得できない場合に備えてバックアップ
        backup_remocon_ids = {channel.id: channel.remocon_id for channel in await Channels.all()}

        # 既にデータベースにチャンネル情報が存在する場合は一旦全て削除する
        await Channels.all().delete()

        # CtrlCmdUtil を初期化
        edcb = CtrlCmdUtil()
        edcb.setNWSetting(CONFIG['general']['edcb_host'], CONFIG['general']['edcb_port'])

        # EDCB の ChSet5.txt からチャンネル情報を取得する
        services = await edcb.sendFileCopy('ChSet5.txt')
        if services is not None:
            services = EDCBUtil.parseChSet5(EDCBUtil.convertBytesToString(services))
            # 枝番処理がミスらないようソートしておく
            services.sort(key = lambda temp: temp['onid'] * 100000 + temp['sid'])
        else:
            services = []

        # EDCB から EPG 由来のチャンネル情報を取得する
        # sendEnumService() の情報源は番組表で、期限切れなどで番組情報が1つもないサービスについては取得できない
        # あればラッキー程度の情報と考えてほしい
        epg_services = await edcb.sendEnumService() or []

        # 同じネットワーク ID のサービスのカウント
        same_network_id_counts = dict()

        # 同じリモコン番号のサービスのカウント
        same_remocon_id_counts = dict()

        for service in services:

            # type が 1 以外のサービス（＝ワンセグやデータ放送 (type:192) など）を弾く
            if service['service_type'] != 1:
                continue

            # 新しいチャンネルのレコードを作成
            channel = Channels()

            # 取得してきた値を設定
            channel.id = f'NID{service["onid"]}-SID{service["sid"]:03d}'
            channel.service_id = service['sid']
            channel.network_id = service['onid']
            channel.transport_stream_id = service['tsid']
            channel.remocon_id = None
            channel.channel_name = ZenkakuToHankaku(service['service_name']).replace('：', ':')
            channel.channel_type = TSInformation.getNetworkType(channel.network_id)
            channel.channel_force = None
            channel.channel_comment = None

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

            # BS・CS・SKY: サービス ID をそのままチャンネル番号・リモコン番号とする
            else:
                channel.remocon_id = channel.service_id  # ソートする際の便宜上設定しておく
                channel.channel_number = str(channel.service_id).zfill(3)

            # チャンネルID = チャンネルタイプ(小文字)+チャンネル番号
            channel.channel_id = channel.channel_type.lower() + channel.channel_number

            # ***** サブチャンネルかどうかを算出 *****

            # 地デジ: サービス ID に 0x0187 を AND 演算した時に 0 でない場合
            # どういう原理かよくわからないんだけど、メインチャンネルでは 0 、サブチャンネルでは 1 以上を返してくれる
            # EDCB バックエンドでは必ずしもチャンネル番号がうまく算出できているとは限らないため、このようにしてみる
            if channel.channel_type == 'GR':
                channel.is_subchannel = (channel.service_id & 0x0187) != 0

            # BS: EDCB から得られる情報からはサブチャンネルかを判定できないため、決め打ちで設定
            elif channel.channel_type == 'BS':
                # サービス ID が以下のリストに含まれるかどうか
                if channel.service_id in [102, 104, 142, 143, 152, 153, 162, 163, 172, 173, 182, 183]:
                    channel.is_subchannel = True
                else:
                    channel.is_subchannel = False

            # CS・SKY: サブチャンネルという概念自体がないため一律で False に設定
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
        """チャンネル情報のうち、ニコニコ実況関連のステータスを更新する"""

        # 全ての実況チャンネルのステータスを更新
        await Jikkyo.updateStatus()

        # 全てのチャンネル情報を取得
        channels = await Channels.all()

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
        """現在と次の番組情報を取得する

        Returns:
            tuple: 現在と次の番組情報が入ったタプル
        """

        # モジュール扱いになるのを避けるためここでインポート
        from app.models import Programs

        # 現在時刻
        now = timezone.now()

        # 現在の番組情報を取得する
        program_present = await Programs.filter(
            channel_id = self.channel_id,  # 同じチャンネルID
            start_time__lte = now,  # 番組開始時刻が現在時刻以下
            end_time__gte = now,  # 番組終了時刻が現在時刻以上
        ).order_by('-start_time').first()

        # 次の番組情報を取得する
        program_following = await Programs.filter(
            channel_id = self.channel_id,  # 同じチャンネルID
            start_time__gte = now,  # 番組開始時刻が現在時刻以上
        ).order_by('start_time').first()

        # 現在の番組情報、次の番組情報のタプルを返す
        return (program_present, program_following)
