
import requests
from tortoise import fields
from tortoise import models
from tortoise import timezone
from typing import Optional

from app.constants import CONFIG
from app.utils import ZenkakuToHankaku


class Channels(models.Model):

    # テーブル設計は Notion を参照のこと
    id:str = fields.TextField(pk=True)
    service_id:int = fields.IntField()
    network_id:int = fields.IntField()
    remocon_id:Optional[int] = fields.IntField(null=True)
    channel_id:str = fields.TextField()
    channel_number:str = fields.TextField()
    channel_name:str = fields.TextField()
    channel_type:str = fields.TextField()
    channel_force:Optional[int] = fields.IntField(null=True)
    channel_comment:Optional[int] = fields.IntField(null=True)
    is_subchannel:bool = fields.BooleanField()


    @classmethod
    async def update(cls):
        """チャンネル情報を更新する"""

        # 既にデータベースにチャンネル情報が存在する場合は一旦全て削除する
        await Channels.all().delete()

        # Mirakurun の API からチャンネル情報を取得する
        mirakurun_services_api_url = f'{CONFIG["general"]["mirakurun_url"]}/api/services'
        services = requests.get(mirakurun_services_api_url).json()

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
            channel.channel_name = ZenkakuToHankaku(service['name'])
            channel.channel_type = service['channel']['type']
            channel.channel_force = 0
            channel.channel_comment = 0

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
