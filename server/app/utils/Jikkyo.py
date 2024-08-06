
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import httpx
import json
import re
import traceback
import websockets
from datetime import datetime
from typing import Any, ClassVar, Literal, NotRequired, TypedDict
from zoneinfo import ZoneInfo

from app import logging
from app import schemas
from app.constants import API_REQUEST_HEADERS, HTTPX_CLIENT, JIKKYO_CHANNELS_PATH
from app.models.User import User


class JikkyoChannelStatus(TypedDict):
    force: int
    viewers: int
    comments: int


class Jikkyo:
    """ ニコニコ実況関連のクライアント実装 """

    # 実況チャンネル ID とサービス ID (SID)・ネットワーク ID (NID) の対照表
    ## NicoJK の jkch.sh.txt (https://github.com/xtne6f/NicoJK/blob/master/jkch.sh.txt) をベースに、情報更新の上で JSON に変換したもの
    with open(JIKKYO_CHANNELS_PATH, mode='r', encoding='utf-8') as file:
        JIKKYO_CHANNELS: ClassVar[list[dict[str, Any]]] = json.load(file)

    # 実況チャンネル ID とニコニコ生放送上の番組 ID の対照表
    ## 現在アクティブ (実況可能) なニコニコ実況チャンネルがここに記載されている
    ## id が None のチャンネルは NX-Jikkyo にのみ存在する実況チャンネル
    JIKKYO_NICOLIVE_PROGRAM_ID_TABLE: ClassVar[dict[str, str | None]] = {
        'jk1': 'lv345479988',
        'jk2': 'lv345479989',
        'jk4': 'lv345479991',
        'jk5': 'lv345479993',
        'jk6': 'lv345479994',
        'jk7': 'lv345479995',
        'jk8': 'lv345479996',
        'jk9': 'lv345479997',
        'jk10': None,
        'jk11': None,
        'jk12': None,
        'jk101': 'lv345479990',
        'jk103': None,
        'jk141': None,
        'jk151': None,
        'jk161': None,
        'jk171': None,
        'jk181': None,
        'jk191': None,
        'jk192': None,
        'jk193': None,
        'jk211': 'lv345479998',
        'jk222': None,
        'jk236': None,
        'jk252': None,
        'jk260': None,
        'jk263': None,
        'jk265': None,
        'jk333': None,
    }

    # ニコニコの色指定を 16 進数カラーコードに置換するテーブル
    COLOR_TABLE: dict[str, str] = {
        'white': '#FFEAEA',
        'red': '#F02840',
        'pink': '#FD7E80',
        'orange': '#FDA708',
        'yellow': '#FFE133',
        'green': '#64DD17',
        'cyan': '#00D4F5',
        'blue': '#4763FF',
        'purple': '#D500F9',
        'black': '#1E1310',
        'white2': '#CCCC99',
        'niconicowhite': '#CCCC99',
        'red2': '#CC0033',
        'truered': '#CC0033',
        'pink2': '#FF33CC',
        'orange2': '#FF6600',
        'passionorange': '#FF6600',
        'yellow2': '#999900',
        'madyellow': '#999900',
        'green2': '#00CC66',
        'elementalgreen': '#00CC66',
        'cyan2': '#00CCCC',
        'blue2': '#3399FF',
        'marineblue': '#3399FF',
        'purple2': '#6633CC',
        'nobleviolet': '#6633CC',
        'black2': '#666666',
    }

    # 実況チャンネルのステータスをキャッシュするための辞書
    __jikkyo_channels_statuses: ClassVar[dict[str, JikkyoChannelStatus]] = {}


    def __init__(self, network_id: int, service_id: int) -> None:
        """
        ニコニコ実況クライアントを初期化する

        Args:
            network_id (int): チャンネルのネットワーク ID
            service_id (int): チャンネルのサービス ID
        """

        self.network_id: int = network_id
        self.service_id: int = service_id

        # ネットワーク ID + サービス ID に対応する実況チャンネル ID (ex: jk101) を取得
        self.jikkyo_id: str | None = self.__getJikkyoChannelID()

        # 実況チャンネル ID に対応するニコニコ生放送上の ID を取得する
        # ニコニコ生放送上の ID が存在しない実況チャンネルは NX-Jikkyo にのみ存在する
        if (self.jikkyo_id in Jikkyo.JIKKYO_NICOLIVE_PROGRAM_ID_TABLE) and \
           (Jikkyo.JIKKYO_NICOLIVE_PROGRAM_ID_TABLE[self.jikkyo_id] is not None):
            self.nicolive_program_id: str | None = Jikkyo.JIKKYO_NICOLIVE_PROGRAM_ID_TABLE[self.jikkyo_id]
        else:
            self.nicolive_program_id: str | None = None


    def __getJikkyoChannelID(self) -> str | None:
        """
        ネットワーク ID + サービス ID に対応する実況チャンネル ID (ex: jk101) を取得する
        対応する実況チャンネル ID が存在しない場合は None を返す

        Returns:
            str | None: 実況チャンネル ID (対応するニコニコ実況チャンネルが存在しない場合は None を返す)
        """

        # ネットワーク ID + サービス ID に対応する実況チャンネル ID を特定する
        for jikkyo_channel in Jikkyo.JIKKYO_CHANNELS:

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

            # 上記の条件に一致し、かつ実況チャンネル ID が存在する場合のみ
            # -1 は対応するニコニコ実況チャンネルが存在しないことを示す
            if match() and jikkyo_channel['jikkyo_id'] != -1:
                jikkyo_id = 'jk' + str(jikkyo_channel['jikkyo_id'])

                # さらに対照表に存在するかをチェックする
                # jikkyo_channels.json には現在は存在しない実況チャンネルの ID (ex: jk256) が含まれているため
                if jikkyo_id in Jikkyo.JIKKYO_NICOLIVE_PROGRAM_ID_TABLE:
                    return jikkyo_id

        # 実況チャンネル ID が取得できていなければ None を返す
        return None


    async def getStatus(self) -> JikkyoChannelStatus | None:
        """
        実況チャンネルの現在のステータスを取得する (ステータス更新は updateStatus() で行う)
        戻り値は force: 実況勢い / viewers: 累計視聴者数 / comments: 累計コメント数 の各カウントの辞書だが、force 以外は現在未使用

        Returns:
            JikkyoChannelStatus | None: 実況チャンネルのステータス
        """

        # 起動してから一度も実況チャンネルのステータスが取得されていなければここで更新する
        if self.__jikkyo_channels_statuses == {}:
            await self.updateStatuses()

        # ネットワーク ID + サービス ID に対応するニコニコ実況チャンネルがない場合は None を返す
        ## 実況チャンネルが昔から存在しない CS や、2020年12月のニコニコ実況リニューアルで廃止された BS スカパーのチャンネルなどが該当
        if self.jikkyo_id is None:
            return None

        # このインスタンスに紐づく実況チャンネルのステータスを返す
        return self.__jikkyo_channels_statuses[self.jikkyo_id]


    @classmethod
    async def updateStatuses(cls) -> None:
        """
        全ての実況チャンネルのステータスを更新する
        更新したステータスは getStatus() で取得できる
        """

        # NX-Jikkyo のチャンネル情報 API から実況チャンネルのステータスを取得する
        ## サーバー混雑時は若干時間がかかることがあるのでタイムアウトを 5 秒に伸ばしている
        try:
            async with HTTPX_CLIENT() as client:
                response = await client.get('https://nx-jikkyo.tsukumijima.net/api/v1/channels', timeout=5.0)
                response.raise_for_status()
                channels_data = response.json()
        except (httpx.NetworkError, httpx.TimeoutException, httpx.HTTPStatusError):
            # エラー発生時はステータス更新を中断
            return

        # 現在時刻に対応するスレッドから実況チャンネルのステータスを取得する
        current_time = datetime.now(ZoneInfo('Asia/Tokyo'))
        for channel in channels_data:
            jikkyo_id = channel['id']
            if jikkyo_id in cls.JIKKYO_NICOLIVE_PROGRAM_ID_TABLE:
                for thread in channel['threads']:
                    if datetime.fromisoformat(thread['start_at']) <= current_time <= datetime.fromisoformat(thread['end_at']):
                        cls.__jikkyo_channels_statuses[jikkyo_id] = {
                            'force': thread['jikkyo_force'],
                            'viewers': thread['viewers'],
                            'comments': thread['comments'],
                        }
                        break


    def getJikkyoWebSocketInfo(self) -> schemas.JikkyoWebSocketInfo:
        """
        ニコニコ実況からコメントを受信するための WebSocket API の情報を取得する
        2024/08/05 以降の新ニコニコ生放送でコメントサーバーが刷新された影響で、従来 KonomiTV で実装していた
        「ブラウザから直接ニコ生の WebSocket API に接続しコメントを受信する」手法が使えなくなったため、
        当面の間、常に NX-Jikkyo の旧ニコニコ生放送互換 WebSocket API の URL を返す
        """

        # ネットワーク ID + サービス ID に対応するニコニコ実況チャンネルがない場合
        ## 実況チャンネルが昔から存在しない CS や、2020年12月のニコニコ実況リニューアルで廃止された BS スカパーのチャンネルなどが該当
        if self.jikkyo_id is None:
            return schemas.JikkyoWebSocketInfo(
                websocket_url = None,
                is_nxjikkyo_exclusive = False,
            )

        # NX-Jikkyo の旧ニコニコ生放送「視聴セッション維持用 WebSocket API」互換の WebSocket API の URL を生成して返す
        return schemas.JikkyoWebSocketInfo(
            websocket_url = f'wss://nx-jikkyo.tsukumijima.net/api/v1/channels/{self.jikkyo_id}/ws/watch',
            # 現在は NX-Jikkyo のみ存在するニコニコ実況チャンネルかどうかを表すフラグ
            ## 実況チャンネル ID に対応するニコニコ生放送 ID が存在しない場合、NX-Jikkyo 固有のニコニコ実況チャンネルと判定する (jk141 など)
            is_nxjikkyo_exclusive = self.nicolive_program_id is None,
        )


    async def sendComment(self, current_user: User, comment: schemas.JikkyoSendCommentRequest) -> schemas.JikkyoSendCommentResult:
        """
        ニコニコ実況 (ニコニコ生放送) の現在放送中の実況枠にコメントを送信する
        NX-Jikkyo 固有のニコニコ実況チャンネルには送信できないため、常に失敗する

        Args:
            current_user (User): ログイン中のユーザーのモデルオブジェクト
            comment (schemas.JikkyoSendCommentRequest): コメント送信リクエスト

        Returns:
            schemas.JikkyoSendCommentResult: コメント送信結果
        """

        # 対応するニコニコ生放送番組 ID が存在しないチャンネル
        if self.nicolive_program_id is None:
            return schemas.JikkyoSendCommentResult(
                is_success = False,
                detail = 'ニコニコ実況に存在しない実況チャンネルにはコメントを送信できません。',
            )

        # ニコニコアカウントと連携されていないユーザーアカウント
        ## フロントエンド側で事前にニコニコアカウント連携済みかバリデーションされてから送信しているため、通常は発生しないはず
        if not all([
            current_user.niconico_user_id,
            current_user.niconico_user_name,
            current_user.niconico_access_token,
            current_user.niconico_refresh_token,
        ]):
            return schemas.JikkyoSendCommentResult(
                is_success = False,
                detail = 'コメントするには、ニコニコアカウントと連携してください。',
            )

        try:
            # 視聴セッションの WebSocket URL を取得する
            ## レスポンスで取得できる WebSocket に接続すると、ログイン中のユーザーに紐づくニコニコアカウントでコメントできる
            wsendpoint_api_url = (
                'https://api.live2.nicovideo.jp/api/v1/wsendpoint?'
                f'nicoliveProgramId={self.nicolive_program_id}&userId={current_user.niconico_user_id}'
            )

            async def getSession():  # 使い回せるように関数化
                async with HTTPX_CLIENT() as client:
                    return await client.get(
                        url = wsendpoint_api_url,
                        headers = {**API_REQUEST_HEADERS, 'Authorization': f'Bearer {current_user.niconico_access_token}'},
                    )
            wsendpoint_api_response = await getSession()

            # ステータスコードが 401 (Unauthorized)
            ## アクセストークンの有効期限が切れているため、リフレッシュトークンでアクセストークンを更新してからやり直す
            if wsendpoint_api_response.status_code == 401:
                try:
                    await current_user.refreshNiconicoAccessToken()
                except Exception as ex:
                    return schemas.JikkyoSendCommentResult(is_success=False, detail=ex.args[0])
                wsendpoint_api_response = await getSession()

            # ステータスコードが 200 以外
            if wsendpoint_api_response.status_code != 200:
                error_code = ''
                try:
                    error_code = f' ({wsendpoint_api_response.json()["meta"]["errorCode"]})'
                except Exception:
                    pass
                return schemas.JikkyoSendCommentResult(is_success=False, detail=(
                    '現在、ニコニコ生放送でエラーが発生しています。'
                    f'(HTTP Error {wsendpoint_api_response.status_code}{error_code})'
                ))

            # 視聴セッションの WebSocket URL を取得
            websocket_url = wsendpoint_api_response.json()['data']['url']

        # 接続エラー（サーバー再起動やタイムアウトなど）
        except (httpx.NetworkError, httpx.TimeoutException):
            return schemas.JikkyoSendCommentResult(
                is_success = False,
                detail = 'ニコニコ生放送に接続できませんでした。ニコニコで障害が発生している可能性があります。',
            )

        # ニコニコ生放送の視聴セッション WebSocket に接続する
        ## 2024/08/05 以降のニコニコ生放送ではコメントサーバーが刷新されたが、コメント送信は従来同様に WebSocket から行う
        try:
            async with websockets.connect(websocket_url) as websocket:

                # 接続が確立したら、視聴開始リクエストを送る
                await websocket.send(json.dumps({
                    'type': 'startWatching',
                    'data': {
                        'reconnect': False,
                    },
                }))

                # その後、コメント送信リクエストを送る
                await websocket.send(json.dumps({
                    'type': 'postComment',
                    'data': {
                        # コメント本文
                        'text': comment.text,
                        # コメントの色
                        'color': comment.color,
                        # コメント位置
                        'position': comment.position,
                        # コメントサイズ
                        'size': comment.size,
                        # 番組開始時間からの累計秒 (10ミリ秒単位)
                        'vpos': comment.vpos,
                        # 匿名コメント (184) にするかどうか
                        'isAnonymous': True,
                    }
                }))

                # メッセージを受信
                while True:
                    raw_message = await websocket.recv()
                    message: dict[str, Any] = json.loads(raw_message)

                    # postCommentResult が送られてきた → コメント送信に成功している
                    if message['type'] == 'postCommentResult':
                        logging.info('Comment sent successfully.')

                        # 明示的に WebSocket 接続を閉じてから返す
                        await websocket.close()
                        return schemas.JikkyoSendCommentResult(is_success=True, detail='コメントを送信しました。')

                    # コメント送信直後に error が送られてきた → コメント送信に失敗している
                    if message['type'] == 'error':
                        error_code: str = message['data']['code']
                        error_message: str = f'コメントの送信に失敗しました。({error_code})'
                        if error_code == 'COMMENT_POST_NOT_ALLOWED':
                            error_message = 'コメントが許可されていません。'
                        elif error_code == 'INVALID_MESSAGE':
                            error_message = 'コメント内容が無効です。'
                        logging.error(f'Comment sending failed. (Code: {error_code})')

                        # 明示的に WebSocket 接続を閉じてから返す
                        await websocket.close()
                        return schemas.JikkyoSendCommentResult(
                            is_success = False,
                            detail = error_message,
                        )

        except websockets.WebSocketException:
            logging.error('An error occurred while connecting to the NicoLive WebSocket API.')
            logging.error(traceback.format_exc())
            return schemas.JikkyoSendCommentResult(
                is_success = False,
                detail = 'ニコニコ生放送の WebSocket API に接続できませんでした。ニコニコで障害が発生している可能性があります。',
            )
        except Exception:
            logging.error('An error occurred while communicating with the NicoLive WebSocket API.')
            logging.error(traceback.format_exc())
            return schemas.JikkyoSendCommentResult(
                is_success = False,
                detail = 'ニコニコ生放送の WebSocket API との通信時に不明なエラーが発生しました。',
            )


    async def fetchJikkyoComments(self, recording_start_time: datetime, recording_end_time: datetime) -> schemas.JikkyoComments:
        """
        ニコニコ実況 過去ログ API から過去ログコメントを取得し、DPlayer が受け付けるコメント形式に変換して返す
        何らかの理由で取得できなかった場合は is_success が False になる

        Args:
            recording_start_time (datetime): 録画開始時刻
            recording_end_time (datetime): 録画終了時刻

        Returns:
            schemas.JikkyoComments: 過去ログコメントのリスト
        """

        # ニコニコ実況 過去ログ API から過去ログコメントを取得する
        ## 30秒応答がなかったらタイムアウト (レスポンスが結構重めなので場合によっては時間がかかることがある)
        try:
            start_time = int(recording_start_time.timestamp())
            end_time = int(recording_end_time.timestamp())
            kakolog_api_url = f'https://jikkyo.tsukumijima.net/api/kakolog/{self.jikkyo_id}?starttime={start_time}&endtime={end_time}&format=json'
            async with HTTPX_CLIENT() as client:
                kakolog_api_response = await client.get(kakolog_api_url, timeout=30)
        except (httpx.NetworkError, httpx.TimeoutException):  # 接続エラー（サーバー再起動やタイムアウトなど）
            return schemas.JikkyoComments(
                is_success = False,
                comments = [],
                detail = '過去ログ API に接続できませんでした。過去ログ API で障害が発生している可能性があります。',
            )

        # ステータスコードが 200 以外
        if kakolog_api_response.status_code != 200:
            if kakolog_api_response.status_code == 500:
                return schemas.JikkyoComments(
                    is_success = False,
                    comments = [],
                    detail = '過去ログ API でサーバーエラーが発生しました。過去ログ API に不具合がある可能性があります。(HTTP Error 500)',
                )
            elif kakolog_api_response.status_code == 503:
                return schemas.JikkyoComments(
                    is_success = False,
                    comments = [],
                    detail = '現在、過去ログ API は一時的に利用できなくなっています。(HTTP Error 503)',
                )
            else:
                return schemas.JikkyoComments(
                    is_success = False,
                    comments = [],
                    detail = f'現在、過去ログ API でエラーが発生しています。(HTTP Error {kakolog_api_response.status_code})',
                )

        # JSON をデコード
        # エラーが入っていた場合はそのエラーを返す
        kakolog_api_response_json = kakolog_api_response.json()
        if 'error' in kakolog_api_response_json:
            return schemas.JikkyoComments(
                is_success = False,
                comments = [],
                detail = kakolog_api_response_json["error"],
            )

        class Chat(TypedDict):
            thread: str
            no: str
            vpos: str
            date: str
            date_usec: NotRequired[str]
            user_id: NotRequired[str]
            mail: NotRequired[str]
            premium: NotRequired[str]
            anonymity: NotRequired[str]
            deleted: NotRequired[str]
            content: NotRequired[str]

        class Packet(TypedDict):
            chat: Chat

        # 過去ログコメントを取得
        # 過去ログコメントが1つもない場合はエラーを返す
        raw_jikkyo_comments: list[Packet] = kakolog_api_response_json['packet']
        if len(raw_jikkyo_comments) == 0:
            return schemas.JikkyoComments(
                is_success = False,
                comments = [],
                detail = 'この録画番組の過去ログコメントは存在しないか、現在取得中です。',
            )

        # 取得した過去ログコメントを随時整形
        jikkyo_comments: list[schemas.JikkyoComment] = []
        for raw_jikkyo_comment in raw_jikkyo_comments:

            # コメントデータが不正な場合はスキップ
            comment = raw_jikkyo_comment['chat'].get('content')
            if type(comment) is not str or comment == '':
                continue

            # 削除されているコメントを除外
            if raw_jikkyo_comment['chat'].get('deleted') == '1':
                continue

            # 運営コメントは今のところ全て弾く
            if re.match(r'\/[a-z]+ ', comment):
                continue

            # コメントコマンドをパース
            color, position, size = self.parseCommentCommand(raw_jikkyo_comment['chat'].get('mail'))

            # コメント時間 (秒単位) を算出
            chat_date = float(raw_jikkyo_comment["chat"]["date"])
            chat_date_usec = int(raw_jikkyo_comment["chat"].get("date_usec", 0))
            comment_time = float(f'{int(chat_date - start_time)}.{chat_date_usec}')

            # コメントデータを整形して追加
            jikkyo_comments.append(schemas.JikkyoComment(
                time = comment_time,
                type = position,
                size = size,
                color = color,
                author = raw_jikkyo_comment['chat'].get('user_id', ''),
                text = comment,
            ))

        return schemas.JikkyoComments(
            is_success = True,
            comments = jikkyo_comments,
            detail = '過去ログコメントを取得しました。',
        )


    @staticmethod
    def getCommentColor(color: str) -> str | None:
        """
        ニコニコの色指定を 16 進数カラーコードに置換する
        フロントエンド側の CommentUtils.getCommentColor() を移植したもの

        Args:
            color (str): ニコニコの色指定

        Returns:
            str | None: 16 進数カラーコード
        """
        return Jikkyo.COLOR_TABLE.get(color)


    @staticmethod
    def getCommentPosition(position: str) -> Literal['top', 'right', 'bottom'] | None:
        """
        ニコニコの位置指定を DPlayer の位置指定に置換する
        フロントエンド側の CommentUtils.getCommentPosition() を移植したもの

        Args:
            position (str): ニコニコの位置指定

        Returns:
            str | None: DPlayer の位置指定
        """

        positions: dict[str, Literal['top', 'right', 'bottom']] = {'ue': 'top', 'naka': 'right', 'shita': 'bottom'}
        return positions.get(position)


    @staticmethod
    def getCommentSize(size: str) -> Literal['big', 'medium', 'small'] | None:
        """
        ニコニコのサイズ指定を DPlayer のサイズ指定に置換する
        フロントエンド側の CommentUtils.getCommentSize() を移植したもの

        Args:
            size (str): ニコニコのサイズ指定

        Returns:
            str | None: DPlayer のサイズ指定
        """

        sizes: dict[str, Literal['big', 'medium', 'small']] = {'big': 'big', 'medium': 'medium', 'small': 'small'}
        return sizes.get(size)


    @staticmethod
    def parseCommentCommand(comment_mail: str | None) -> tuple[str, Literal['top', 'right', 'bottom'], Literal['big', 'medium', 'small']]:
        """
        ニコニコのコメントコマンドを解析し、色・位置・サイズを取得する
        フロントエンド側の CommentUtils.parseCommentCommand() を移植したもの

        Args:
            comment_mail (str | None): ニコニコのコメントコマンド

        Returns:
            tuple[str, str, str]: コメントの色、位置、サイズ
        """

        color = '#FFEAEA'  # 初期色
        position = 'right'  # 初期位置
        size = 'medium'  # 初期サイズ

        if comment_mail is not None:
            commands = comment_mail.replace('184', '').split(' ')
            for command in commands:
                parsed_color = Jikkyo.getCommentColor(command)
                parsed_position = Jikkyo.getCommentPosition(command)
                parsed_size = Jikkyo.getCommentSize(command)
                if parsed_color is not None:
                    color = parsed_color
                if parsed_position is not None:
                    position = parsed_position
                if parsed_size is not None:
                    size = parsed_size

        return color, position, size
