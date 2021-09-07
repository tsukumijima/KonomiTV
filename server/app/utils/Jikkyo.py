
import json
import requests
import xml.etree.ElementTree as ET
from typing import Optional

from app.constants import BASE_DIR


class Jikkyo:

    # 実況 ID とサービス ID (SID)・ネットワーク ID (NID) の対照表
    with open(BASE_DIR / 'data/jikkyo_channels.json', encoding='utf-8') as file:
        jikkyo_channels = json.load(file)

    # 実況 ID とチャンネル/コミュニティ ID の対照表
    jikkyo_nicolive_table = {
        'jk1': {'type': 'channel', 'id': 'ch2646436', 'name': 'NHK総合'},
        'jk2': {'type': 'channel', 'id': 'ch2646437', 'name': 'NHK Eテレ'},
        'jk4': {'type': 'channel', 'id': 'ch2646438', 'name': '日本テレビ'},
        'jk5': {'type': 'channel', 'id': 'ch2646439', 'name': 'テレビ朝日'},
        'jk6': {'type': 'channel', 'id': 'ch2646440', 'name': 'TBSテレビ'},
        'jk7': {'type': 'channel', 'id': 'ch2646441', 'name': 'テレビ東京'},
        'jk8': {'type': 'channel', 'id': 'ch2646442', 'name': 'フジテレビ'},
        'jk9': {'type': 'channel', 'id': 'ch2646485', 'name': 'TOKYO MX'},
        'jk10': {'type': 'community', 'id': 'co5253063', 'name': 'テレ玉'},
        'jk11': {'type': 'community', 'id': 'co5215296', 'name': 'tvk'},
        'jk12': {'type': 'community', 'id': 'co5359761', 'name': 'チバテレビ'},
        'jk101': {'type': 'channel', 'id': 'ch2647992', 'name': 'NHK BS1'},
        'jk103': {'type': 'community', 'id': 'co5175227', 'name': 'NHK BSプレミアム'},
        'jk141': {'type': 'community', 'id': 'co5175341', 'name': 'BS日テレ'},
        'jk151': {'type': 'community', 'id': 'co5175345', 'name': 'BS朝日'},
        'jk161': {'type': 'community', 'id': 'co5176119', 'name': 'BS-TBS'},
        'jk171': {'type': 'community', 'id': 'co5176122', 'name': 'BSテレ東'},
        'jk181': {'type': 'community', 'id': 'co5176125', 'name': 'BSフジ'},
        'jk191': {'type': 'community', 'id': 'co5251972', 'name': 'WOWOW PRIME'},
        'jk192': {'type': 'community', 'id': 'co5251976', 'name': 'WOWOW LIVE'},
        'jk193': {'type': 'community', 'id': 'co5251983', 'name': 'WOWOW CINEMA'},
        'jk211': {'type': 'channel',   'id': 'ch2646846', 'name': 'BS11'},
        'jk222': {'type': 'community', 'id': 'co5193029', 'name': 'BS12'},
        'jk236': {'type': 'community', 'id': 'co5296297', 'name': 'BSアニマックス'},
        'jk333': {'type': 'community', 'id': 'co5245469', 'name': 'AT-X'},
    }

    # 実況チャンネルのステータスが入る辞書
    # getchannels API のリクエスト結果をキャッシュする
    jikkyo_channels_status = dict()


    def __init__(self, network_id:int, service_id:int):
        """
        ニコニコ実況を初期化する

        Args:
            network_id (int): ネットワーク ID
            service_id (int): サービス ID
        """

        # NID と SID を設定
        self.network_id = network_id
        self.service_id = service_id

        # 実況 ID を取得する
        for jikkyo_channel in self.jikkyo_channels:

            # マッチ条件が複雑すぎるので、絞り込みのための関数を定義する
            def match() -> bool:

                # jikkyo_channels.json に定義されている NID と SID
                jikkyo_network_id = jikkyo_channel['network_id']
                jikkyo_service_id = int(jikkyo_channel['service_id'], 0)  # 16進数の文字列を数値に変換

                # NID と SID が一致する
                # BS・CS・SKY の場合はこれだけで OK
                if self.network_id == jikkyo_network_id and self.service_id == jikkyo_service_id:
                    return True

                # NID が地上波の ID 範囲 (0x7880 ～ 0x7fef) で、かつ jikkyo_channels.json 記載の NID が 15（地上波）であれば
                # jikkyo_channels.json 記載の地上波の NID はなぜか 15 で固定なので、地上波で絞り込めたら後はサービス ID のみで特定する
                if 0x7880 <= self.network_id <= 0x7fef and jikkyo_network_id == 15:

                    # サービス ID が一致する
                    if self.service_id == jikkyo_service_id:
                        return True

                    # サブチャンネル用で、jikkyo_channels.json にはサブチャンネルは定義されていないため必要
                    # 地上波の場合はサービス ID は別チャンネルと隣合わせにならないようになっているはず
                    # 地上波のサブチャンネルはおそらく最大3つなのでこれでカバーしきれるはず

                    # 1つ前のサービス ID なら一致する
                    # たとえば SID が 1025 (NHK総合2・東京) の場合、1つ前の 1024 (NHK総合1・東京) であれば定義があるので一致する
                    if self.service_id - 1 == jikkyo_service_id:
                        return True

                    # 2つ前のサービス ID なら一致する
                    # たとえば SID が 1034 (NHKEテレ3東京) の場合、2つ前の 1032 (NHKEテレ1東京) であれば定義があるので一致する
                    if self.service_id - 2 == jikkyo_service_id:
                        return True

                # ここまでの条件に一致しなかったら False を返す
                return False

            # 上記の条件に一致する場合のみ
            if match():

                # 実況 ID が -1 なら jk0 に
                if jikkyo_channel['jikkyo_id'] == -1:
                    self.jikkyo_id = 'jk0'
                else:
                    self.jikkyo_id = 'jk' + str(jikkyo_channel['jikkyo_id'])
                break

        # この時点で実況 ID が存在しないなら、jk0 を設定する
        if hasattr(self, 'jikkyo_id') is False:
            self.jikkyo_id = 'jk0'

        # ニコ生上のチャンネル/コミュニティ ID を取得する
        if self.jikkyo_id != 'jk0':
            if self.jikkyo_id in self.jikkyo_nicolive_table:
                # 対照表に存在する実況 ID
                self.jikkyo_nicolive_id = self.jikkyo_nicolive_table[self.jikkyo_id]['id']
            else:
                # ニコ生への移行時に廃止されたなどの理由で対照表に存在しない実況 ID
                self.jikkyo_nicolive_id = None
        else:
            self.jikkyo_nicolive_id = None


    async def getStatus(self) -> Optional[dict]:
        """
        実況チャンネルのステータスを取得する

        Returns:
            Optional[dict]: 実況チャンネルのステータス
        """

        # まだ実況チャンネルのステータスが更新されていなければ更新する
        if (self.jikkyo_channels_status == dict()):
            await self.updateStatus()

        # 実況 ID が jk0 であれば None を返す
        if self.jikkyo_id == 'jk0':
            return None

        # 実況チャンネルのステータスが存在しない場合は None を返す
        # 主にニコ生への移行時に実況が廃止されたチャンネル向け
        if self.jikkyo_id not in self.jikkyo_channels_status:
            return None

        # このインスタンスに紐づく実況チャンネルのステータスを返す
        return self.jikkyo_channels_status[self.jikkyo_id]


    @classmethod
    async def updateStatus(cls) -> None:
        """
        全ての実況チャンネルのステータスを更新する
        更新したステータスは getStatus() で取得できる
        """

        # 循環インポートを防ぐ
        from app.utils import RunAsync

        # getchannels API から実況チャンネルのステータスを取得する
        getchannels_api_url = 'https://jikkyo.tsukumijima.net/namami/api/v2/getchannels'
        getchannels_api_result:requests.Response = await RunAsync(requests.get, getchannels_api_url)

        # XML をパース
        channels = ET.fromstring(getchannels_api_result.text)

        # 実況チャンネルごとに
        for channel in channels:

            # 実況 ID を取得
            jikkyo_id = channel.find('video').text

            # 対照表に存在する実況 ID のみ
            if jikkyo_id in cls.jikkyo_nicolive_table:

                # ステータスを更新する
                # XML だと色々めんどくさいので、辞書にまとめ直す
                cls.jikkyo_channels_status[jikkyo_id] = {
                    'force': int(channel.find('./thread/force').text),
                    'viewers': int(channel.find('./thread/viewers').text),
                    'comments': int(channel.find('./thread/comments').text),
                }

                # viewers と comments が -1 の場合、force も -1 に設定する
                if (cls.jikkyo_channels_status[jikkyo_id]['viewers'] == -1 and
                    cls.jikkyo_channels_status[jikkyo_id]['comments'] == -1):
                    cls.jikkyo_channels_status[jikkyo_id]['force'] = -1
