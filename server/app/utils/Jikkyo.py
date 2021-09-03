
import json

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


    def __init__(self, service_id:str, network_id:str):
        """
        ニコニコ実況を初期化する

        Args:
            service_id (str): サービス ID
            network_id (str): ネットワーク ID
        """

        # SID と NID を設定
        self.service_id = service_id
        self.network_id = network_id

        # 実況 ID を取得する
        for jikkyo_channel in self.jikkyo_channels:

            # SID と NID が一致したときのみ
            if self.service_id == jikkyo_channel['service_id'] and self.network_id == int(jikkyo_channel['network_id'], 0):
                self.jikkyo_id = jikkyo_channel['jikkyo_id']
                break

        # この時点で実況 ID が存在しないなら、-1 を設定する
        if hasattr(self, 'jikkyo_id') is False:
            self.jikkyo_id = -1

        # ニコ生上のチャンネル/コミュニティ ID を取得する
        if self.jikkyo_id > 0:
            if f'jk{self.jikkyo_id}' in self.jikkyo_nicolive_table:
                # 対照表に存在する実況 ID
                self.jikkyo_nicolive_id = self.jikkyo_nicolive_table['id']
            else:
                # ニコ生への移行時に廃止されたなどの理由で対照表に存在しない実況 ID
                self.jikkyo_nicolive_id = None
        else:
            self.jikkyo_nicolive_id = None
