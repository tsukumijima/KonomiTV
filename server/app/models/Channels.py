
import requests
from tortoise import fields
from tortoise import models
from tortoise import timezone
from tortoise.exceptions import IntegrityError
from typing import Optional

from app.constants import CONFIG
from app.utils import Jikkyo
from app.utils import RunAsync
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

        if CONFIG['general']['backend'] == 'EDCB':
            edcb = CtrlCmdUtil()
            edcb.setNWSetting(CONFIG['general']['edcb_host'], CONFIG['general']['edcb_port'])

            # リモコン番号が取得できない場合に備える
            db_remocon_ids = {channel.id: channel.remocon_id for channel in await Channels.all()}
            await Channels.all().delete()

            # sendEnumService() の情報源は番組表。期限切れなどで番組情報が1つもないサービスについては取得できないので注意
            # あればラッキー程度の情報と考えてほしい
            epg_services = await edcb.sendEnumService() or []
            services = await edcb.sendFileCopy('ChSet5.txt')
            if services is None:
                services = []
            else:
                services = EDCBUtil.parseChSet5(EDCBUtil.convertBytesToString(services))
                # 枝番処理がミスらないようソートしておく
                services.sort(key = lambda a: (a['onid'] << 16) | a['sid'])

            last_network_id = -1
            same_network_id_count = 0
            last_network_remocon_id = 0
            remocon_id_counts = {}

            for service in services:
                if service['service_type'] != 1:
                    continue
                nid = service['onid']
                sid = service['sid']
                channel = Channels()
                channel.id = f'NID{nid}-SID{sid:03d}'
                channel.service_id = sid
                channel.network_id = nid
                channel.transport_stream_id = service['tsid']
                channel.remocon_id = None
                channel.channel_name = ZenkakuToHankaku(service['service_name']).replace('：', ':')
                # TODO: TSInformation あたりの情報を使いたい
                channel.channel_type = 'BS' if nid == 4 else 'CS' if nid == 6 or nid == 7 else 'SKY' if nid == 1 or nid == 3 or nid == 10 else 'GR'
                channel.channel_force = None
                channel.channel_comment = None

                if channel.channel_type == 'GR':
                    epg_service = next(filter(lambda a: a['onid'] == nid and a['sid'] == sid, epg_services), None)
                    if epg_service is not None:
                        channel.remocon_id = epg_service['remote_control_key_id']
                    else:
                        channel.remocon_id = db_remocon_ids.get(channel.id)

                    if last_network_id != nid:
                        last_network_id = nid
                        same_network_id_count = 1
                        # リモコン番号が不明のときはとりあえず 0 とする
                        last_network_remocon_id = 0 if channel.remocon_id is None else channel.remocon_id
                        remocon_id_counts.setdefault(last_network_remocon_id, 0)
                        remocon_id_counts[last_network_remocon_id] += 1
                    else:
                        same_network_id_count += 1
                    channel.channel_number = str(last_network_remocon_id).zfill(2) + str(same_network_id_count)
                    # 枝番処理
                    if remocon_id_counts[last_network_remocon_id] > 1:
                        channel.channel_number += '-' + str(remocon_id_counts[last_network_remocon_id])
                else:
                    channel.channel_number = str(sid).zfill(3)

                channel.channel_id = channel.channel_type.lower() + channel.channel_number

                if 0x7880 <= nid <= 0x7fef:
                    channel.is_subchannel = (sid & 0x0187) != 0
                elif nid == 4:
                    channel.is_subchannel = sid in [102, 104, 142, 143, 152, 153, 162, 163, 172, 173, 182, 183]
                else:
                    channel.is_subchannel = False

                try:
                    await channel.save()
                except IntegrityError:
                    # 既に登録されているチャンネルならスキップ
                    pass
            return

        # 既にデータベースにチャンネル情報が存在する場合は一旦全て削除する
        await Channels.all().delete()

        # Mirakurun の API からチャンネル情報を取得する
        mirakurun_services_api_url = f'{CONFIG["general"]["mirakurun_url"]}/api/services'
        services = (await RunAsync(requests.get, mirakurun_services_api_url)).json()

        # 同じネットワーク ID のサービスのカウント
        same_network_id_count = dict()

        # サービスごとに実行
        for service in services:

            # type が 1 以外のサービス（＝ワンセグやデータ放送 (type:192) など）を弾く
            if service['type'] != 1:
                continue

            # 新しいチャンネルのレコードを作成
            channel = Channels()

            # 取得してきた値を設定
            channel.id = f'NID{str(service["networkId"])}-SID{str(service["serviceId"]).zfill(3)}'
            channel.service_id = service['serviceId']
            channel.network_id = service['networkId']
            channel.remocon_id = service['remoteControlKeyId'] if ('remoteControlKeyId' in service) else None
            channel.channel_name = ZenkakuToHankaku(service['name']).replace('：', ':')
            channel.channel_type = service['channel']['type']
            channel.channel_force = None
            channel.channel_comment = None

            # カウントを追加
            if channel.network_id not in same_network_id_count:  # まだキーが存在しない
                same_network_id_count[channel.network_id] = 0
            same_network_id_count[channel.network_id] += 1  # カウントを足す

            # ***** チャンネル番号・チャンネル ID を算出 *****

            if channel.channel_type == 'GR':

                # 地デジ: 上2桁はリモコン番号から、下1桁は同じネットワーク内にあるサービスのカウント
                channel.channel_number = str(channel.remocon_id).zfill(2) + str(same_network_id_count[channel.network_id])

                # 既に同じチャンネル番号のチャンネルが存在する場合は枝番をつける
                while await Channels.filter(channel_number=channel.channel_number).get_or_none() is not None:

                        # 既に枝番があればさらに枝番をつける
                    if '-' in (await Channels.filter(channel_number=channel.channel_number).get()).channel_number:
                        duplicate_channel_count = int(channel.channel_number[-1]) + 1  # チャンネル番号の最後の1文字 + 1

                    # 通常
                    else:
                        duplicate_channel_count = 1

                    # チャンネル番号を再定義
                    channel.channel_number = (
                        str(channel.remocon_id).zfill(2) +  # リモコン番号
                        str(same_network_id_count[channel.network_id]) +  # 同じネットワーク内にあるサービスのカウント
                        '-' + str(duplicate_channel_count)  # 枝番
                    )

            else:
                # BS・CS・SKY: SID をそのままチャンネル番号とする
                channel.channel_number = str(channel.service_id).zfill(3)

            # チャンネルID = チャンネルタイプ(小文字)+チャンネル番号
            channel.channel_id = channel.channel_type.lower() + channel.channel_number

            # ***** サブチャンネルかどうかを算出 *****

            # 地デジ: チャンネル番号の下一桁が 1 以外かどうか
            if channel.channel_type == 'GR':
                channel.is_subchannel = bool(channel.channel_number[2:] != '1')

            # BS: Mirakurun から得られる情報からはサブチャンネルかを判定できないため、決め打ちで設定
            elif channel.channel_type == 'BS':
                if (
                    # NHK BS1
                    channel.service_id == 102 or
                    # NHK BSプレミアム
                    channel.service_id == 104 or
                    # BS日テレ
                    channel.service_id == 142 or
                    channel.service_id == 143 or
                    # BS朝日
                    channel.service_id == 152 or
                    channel.service_id == 153 or
                    # BS-TBS
                    channel.service_id == 162 or
                    channel.service_id == 163 or
                    # BSテレ東
                    channel.service_id == 172 or
                    channel.service_id == 173 or
                    # BSフジ
                    channel.service_id == 182 or
                    channel.service_id == 183
                ):
                    channel.is_subchannel = True
                else:
                    channel.is_subchannel = False

            # CS・SKY: サブチャンネルという概念自体がないため一律で False に設定
            else:
                channel.is_subchannel = False

            # レコードを保存する
            await channel.save()


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
