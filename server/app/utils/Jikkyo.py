
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import asyncio
import html
import json
import re
import requests
import xml.etree.ElementTree as ET
from typing import Dict, Optional, Union

from app.constants import API_REQUEST_HEADERS, JIKKYO_CHANNELS_PATH, NICONICO_OAUTH_CLIENT_ID
from app.models import User


class Jikkyo:

    # 実況 ID とサービス ID (SID)・ネットワーク ID (NID) の対照表
    with open(JIKKYO_CHANNELS_PATH, encoding='utf-8') as file:
        jikkyo_channels: Dict[str, Dict[str, Union[int, str]]] = json.load(file)

    # 実況チャンネルのステータスが入る辞書
    # getchannels API のリクエスト結果をキャッシュする
    jikkyo_channels_status: Dict[str, Dict[str, int]] = {}

    # 実況 ID と実況チャンネル/コミュニティ ID の対照表
    jikkyo_nicolive_id_table: Dict[str, Dict[str, str]] = {
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
        'jk252': {'type': 'community', 'id': 'co5683458', 'name': 'WOWOW PLUS'},
        'jk260': {'type': 'community', 'id': 'co5682554', 'name': 'BS松竹東急'},
        'jk263': {'type': 'community', 'id': 'co5682551', 'name': 'BSJapanext'},
        'jk265': {'type': 'community', 'id': 'co5682548', 'name': 'BSよしもと'},
        'jk333': {'type': 'community', 'id': 'co5245469', 'name': 'AT-X'},
    }


    def __init__(self, network_id: int, service_id: int):
        """
        ニコニコ実況クライアントを初期化する

        Args:
            network_id (int): ネットワーク ID
            service_id (int): サービス ID
        """

        # NID と SID を設定
        self.network_id: int = network_id
        self.service_id: int = service_id

        # 実況 ID
        self.jikkyo_id: str

        # ニコ生上の実況チャンネル/コミュニティ ID
        self.jikkyo_nicolive_id: str

        # 実況 ID を取得する
        for jikkyo_channel in self.jikkyo_channels:

            # マッチ条件が複雑すぎるので、絞り込みのための関数を定義する
            def match() -> bool:

                # jikkyo_channels.json に定義されている NID と SID
                jikkyo_network_id = jikkyo_channel['network_id']
                jikkyo_service_id = int(jikkyo_channel['service_id'], 0)  # 16進数の文字列を数値に変換

                # NID と SID が一致する
                # BS・CS の場合はこれだけで OK
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
                # CATV・SKY・STARDIGIO は実況チャンネル/コミュニティ自体が存在しない
                return False

            # 上記の条件に一致する場合のみ
            if match():

                # 実況 ID が -1 なら jk0 に
                if jikkyo_channel['jikkyo_id'] == -1:
                    self.jikkyo_id = 'jk0'
                else:
                    self.jikkyo_id = 'jk' + str(jikkyo_channel['jikkyo_id'])
                break

        # この時点で実況 ID を設定できていないなら (jikkyo_channels.json に未定義のチャンネル) jk0 を設定する
        if hasattr(self, 'jikkyo_id') is False:
            self.jikkyo_id = 'jk0'

        # ニコ生上の実況チャンネル/コミュニティ ID を取得する
        if self.jikkyo_id != 'jk0':
            if self.jikkyo_id in self.jikkyo_nicolive_id_table:
                # 対照表に存在する実況 ID
                self.jikkyo_nicolive_id = self.jikkyo_nicolive_id_table[self.jikkyo_id]['id']
            else:
                # ニコ生への移行時に廃止されたなどの理由で対照表に存在しない実況 ID
                self.jikkyo_nicolive_id = None
        else:
            self.jikkyo_nicolive_id = None


    async def refreshNiconicoAccessToken(self, current_user: User) -> None:
        """
        指定されたユーザーに紐づくニコニコアカウントのアクセストークンを、リフレッシュトークンで更新する

        Args:
            user (User): ログイン中のユーザーのモデルオブジェクト
        """

        try:

            # リフレッシュトークンを使い、ニコニコ OAuth のアクセストークンとリフレッシュトークンを更新
            from app.utils import Interlaced
            token_api_url = 'https://oauth.nicovideo.jp/oauth2/token'
            token_api_response = await asyncio.to_thread(
                requests.post,
                url = token_api_url,
                data = {
                    'grant_type': 'refresh_token',
                    'client_id': NICONICO_OAUTH_CLIENT_ID,
                    'client_secret': Interlaced(3),
                    'refresh_token': current_user.niconico_refresh_token,
                },
                headers = {**API_REQUEST_HEADERS, 'Content-Type': 'application/x-www-form-urlencoded'},
                timeout = 3,  # 3秒応答がなかったらタイムアウト
            )

            # ステータスコードが 200 以外
            if token_api_response.status_code != 200:
                error_code = ''
                try:
                    error_code = f' ({token_api_response.json()["error"]})'
                except requests.JSONDecodeError:
                    pass
                raise Exception(f'アクセストークンの更新に失敗しました。(HTTP Error {token_api_response.status_code}{error_code})')

            token_api_response_json = token_api_response.json()

        # 接続エラー（サーバーメンテナンスやタイムアウトなど）
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            raise Exception('アクセストークンの更新に失敗しました。')

        # 取得したアクセストークンとリフレッシュトークンをユーザーアカウントに設定
        ## 仕様上リフレッシュトークンに有効期限はないが、一応このタイミングでリフレッシュトークンも更新することが推奨されている
        current_user.niconico_access_token = str(token_api_response_json['access_token'])
        current_user.niconico_refresh_token = str(token_api_response_json['refresh_token'])

        try:

            # ついでなので、このタイミングでユーザー情報を取得し直す
            ## 頻繁に変わるものでもないとは思うけど、一応再ログインせずとも同期されるようにしておきたい
            ## 3秒応答がなかったらタイムアウト
            user_api_url = f'https://nvapi.nicovideo.jp/v1/users/{current_user.niconico_user_id}'
            user_api_headers = {**API_REQUEST_HEADERS, 'X-Frontend-Id': '6'}  # X-Frontend-Id がないと INVALID_PARAMETER になる
            user_api_response = await asyncio.to_thread(requests.get, user_api_url, headers=user_api_headers, timeout=3)

            if user_api_response.status_code == 200:
                # ユーザー名
                current_user.niconico_user_name = str(user_api_response.json()['data']['user']['nickname'])
                # プレミアム会員かどうか
                current_user.niconico_user_premium = bool(user_api_response.json()['data']['user']['isPremium'])

        # 接続エラー（サーバー再起動やタイムアウトなど）
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            pass  # 取れなくてもセッション取得に支障はないのでパス

        # 変更をデータベースに保存
        await current_user.save()


    async def fetchJikkyoSession(self, current_user: Optional[User] = None) -> dict:
        """
        ニコニコ実況（ニコ生）の視聴セッション情報を取得する

        Args:
            current_user (Optional[User]): ログイン中のユーザーのモデルオブジェクト or None

        Returns:
            dict: 視聴セッション情報 or エラーメッセージが含まれる辞書
        """

        # 廃止されたなどの理由でニコ生上の実況チャンネル/コミュニティ ID が取得できていない
        if self.jikkyo_nicolive_id is None:
            return {'is_success': False, 'detail': 'このチャンネルのニコニコ実況はありません。'}

        # ニコ生の視聴ページの HTML を取得する
        ## 結構重いんだけど、ログインなしで視聴セッションを取るには視聴ページのスクレイピングしかない（はず）
        ## 3秒応答がなかったらタイムアウト
        watch_page_url = f'https://live.nicovideo.jp/watch/{self.jikkyo_nicolive_id}'
        try:
            watch_page_response = await asyncio.to_thread(requests.get, watch_page_url, headers=API_REQUEST_HEADERS, timeout=3)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            return {'is_success': False, 'detail': 'ニコニコ実況に接続できませんでした。'}
        watch_page_code = watch_page_response.status_code

        # ステータスコードを判定
        if watch_page_code != 200:
            # 404: Not Found
            if watch_page_code != 404:
                return {'is_success': False, 'detail': '現在放送中のニコニコ実況がありません。(HTTP Error 404)'}
            # 500: Internal Server Error
            elif watch_page_code != 500:
                return {'is_success': False, 'detail': '現在、ニコニコ実況で障害が発生しています。(HTTP Error 500)'}
            # 503: Service Unavailable
            elif watch_page_code != 500:
                return {'is_success': False, 'detail': '現在、ニコニコ実況はメンテナンス中です。(HTTP Error 503)'}
            # それ以外のステータスコード
            else:
                return {'is_success': False, 'detail': f'現在、ニコニコ実況でエラーが発生しています。(HTTP Error {watch_page_code})'}

        # HTML から embedded-data を取得
        embedded_data_raw:dict = re.search(r'<script id="embedded-data" data-props="(.*?)"><\/script>', watch_page_response.text)

        # embedded-data の取得に失敗
        if embedded_data_raw is None:
            return {'is_success': False, 'detail': 'ニコニコ実況の番組情報の取得に失敗しました。'}

        # HTML エスケープを解除してから JSON デコード
        embedded_data = json.loads(html.unescape(embedded_data_raw[1]))

        # 現在放送中 (ON_AIR) でない
        if embedded_data['program']['status'] != 'ON_AIR':
            return {'is_success': False, 'detail': '現在放送中のニコニコ実況がありません。'}

        # 視聴セッションの WebSocket URL
        session = embedded_data['site']['relive']['webSocketUrl']
        if session == '':
            return {'is_success': False, 'detail': '視聴セッションを取得できませんでした。'}

        # ログイン中でかつニコニコアカウントと連携している場合のみ、OAuth API (wsendpoint) から視聴セッションを取得する
        ## wsendpoint から視聴セッションを取得すると、アクセストークンに紐づくユーザーとしてコメントできる
        ## wsendpoint ではニコニコチャンネルやニコニコミュニティの ID を直接指定できず、事前に放送中の番組 ID を取得しておく必要がある
        ## 現在放送中の番組があるかの判定 & 番組 ID の取得がめんどくさいのと、wsendpoint の API レスポンスが早いため、
        ## wsendpoint から視聴セッションを取得する際も番組 ID を取得する目的で視聴ページにアクセスしている
        if current_user is not None and all([
            current_user.niconico_user_id,
            current_user.niconico_user_name,
            current_user.niconico_access_token,
            current_user.niconico_refresh_token,
        ]):
            try:

                # 視聴セッションの WebSocket URL を取得する
                ## レスポンスで取得できる WebSocket に接続すると、ログイン中のユーザーに紐づくニコニコアカウントでコメントできる
                session_api_url = (
                    'https://api.live2.nicovideo.jp/api/v1/wsendpoint?'
                    f'nicoliveProgramId={embedded_data["program"]["nicoliveProgramId"]}&userId={current_user.niconico_user_id}'
                )

                async def getSession():  # 使い回せるように関数化
                    return await asyncio.to_thread(
                        requests.get,
                        session_api_url,
                        headers = {**API_REQUEST_HEADERS, 'Authorization': f'Bearer {current_user.niconico_access_token}'},
                        timeout = 3,  # 3秒応答がなかったらタイムアウト
                    )
                session_api_response = await getSession()

                # ステータスコードが 401 (Unauthorized)
                ## アクセストークンの有効期限が切れているため、リフレッシュトークンでアクセストークンを更新してからやり直す
                if session_api_response.status_code == 401:
                    try:
                        await self.refreshNiconicoAccessToken(current_user)
                    except Exception as ex:
                        return {'is_success': False, 'detail': ex.args[0]}
                    session_api_response = await getSession()

                # ステータスコードが 200 以外
                if session_api_response.status_code != 200:
                    error_code = ''
                    try:
                        error_code = f' ({session_api_response.json()["meta"]["errorCode"]})'
                    except requests.JSONDecodeError:
                        pass
                    return {
                        'is_success': False,
                        'detail': (
                            '現在、ニコニコ実況でエラーが発生しています。'
                            f'(HTTP Error {session_api_response.status_code}{error_code})'
                        ),
                    }

                # 視聴セッションの WebSocket URL を OAuth API から取得したものに置き換える
                session = session_api_response.json()['data']['url']

            # 接続エラー（サーバー再起動やタイムアウトなど）
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                return {'is_success': False, 'detail': 'ニコニコ実況に接続できませんでした。'}

        # 視聴セッションの WebSocket URL を返す
        return {'is_success': True, 'audience_token': session, 'detail': '視聴セッションを取得しました。'}


    async def getStatus(self) -> Optional[dict]:
        """
        実況チャンネルのステータスを取得する

        Returns:
            Optional[dict]: 実況チャンネルのステータス
        """

        # まだ実況チャンネルのステータスが更新されていなければ更新する
        if self.jikkyo_channels_status == {}:
            await self.updateStatus()

        # 実況 ID が jk0（実況チャンネル/コミュニティが存在しない）であれば None を返す
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

        # getchannels API から実況チャンネルのステータスを取得する
        ## 3秒応答がなかったらタイムアウト
        try:
            getchannels_api_url = 'https://jikkyo.tsukumijima.net/namami/api/v2/getchannels'
            getchannels_api_response = await asyncio.to_thread(requests.get, getchannels_api_url, headers=API_REQUEST_HEADERS, timeout=3)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):  # 接続エラー（サーバー再起動やタイムアウトなど）
            return # ステータス更新を中断

        # ステータスコードが 200 以外
        if getchannels_api_response.status_code != 200:
            return  # ステータス更新を中断

        # XML をパース
        channels = ET.fromstring(getchannels_api_response.text)

        # 実況チャンネルごとに
        for channel in channels:

            # 実況 ID を取得
            jikkyo_id = channel.find('video').text

            # 対照表に存在する実況 ID のみ
            if jikkyo_id in cls.jikkyo_nicolive_id_table:

                # ステータス (force: 実況勢い, viewers: 累計視聴者数, comments: 累計コメント数) を更新
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
