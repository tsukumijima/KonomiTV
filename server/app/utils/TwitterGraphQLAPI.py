from __future__ import annotations

import asyncio
import json
import random
import re
import time
from datetime import datetime
from typing import Any, ClassVar, Literal

from app import logging, schemas
from app.constants import JST
from app.models.TwitterAccount import TwitterAccount
from app.utils.TwitterScrapeBrowser import (
    BrowserBinaryNotFoundError,
    BrowserConnectionFailedError,
    TwitterScrapeBrowser,
)


class TwitterGraphQLAPI:
    """
    Twitter Web App で利用されている GraphQL API のラッパー
    外部ライブラリを使うよりすべて自前で書いたほうが柔軟に対応でき、凍結リスクを回避できると考えて実装した
    以下に実装されているリクエストペイロードなどは、すべて実装時点の Twitter Web App が実際に送信するリクエストを可能な限り模倣したもの
    メソッド名は概ね GraphQL API でのエンドポイント名に対応している
    実際の API リクエストは TwitterScrapeBrowser 経由でヘッドレスブラウザから実行される
    """

    # Twitter API のエラーコードとエラーメッセージの対応表
    ## 実際に返ってくる可能性があるものだけ
    ## ref: https://developer.twitter.com/ja/docs/basics/response-codes
    ERROR_MESSAGES: ClassVar[dict[int, str]] = {
        32: 'Twitter アカウントの認証に失敗しました。もう一度連携し直してください。',
        63: 'Twitter アカウントが凍結またはロックされています。',
        64: 'Twitter アカウントが凍結またはロックされています。',
        88: 'Twitter API エンドポイントのレート制限を超えました。',
        89: 'Twitter アクセストークンの有効期限が切れています。',
        99: 'Twitter OAuth クレデンシャルの認証に失敗しました。',
        131: 'Twitter でサーバーエラーが発生しています。',
        135: 'Twitter アカウントの認証に失敗しました。もう一度連携し直してください。',
        139: 'すでにいいねされています。',
        144: 'ツイートが非公開かすでに削除されています。',
        179: 'フォローしていない非公開アカウントのツイートは表示できません。',
        185: 'ツイート数の上限に達しました。',
        186: 'ツイートが長過ぎます。',
        187: 'ツイートが重複しています。',
        226: 'ツイートが自動化されたスパムと判定されました。',
        261: 'Twitter API アプリケーションが凍結されています。',
        326: 'Twitter アカウントが一時的にロックされています。',
        327: 'すでにリツイートされています。',
        328: 'このツイートではリツイートは許可されていません。',
        416: 'Twitter API アプリケーションが無効化されています。',
    }

    # ツイートの最小送信間隔 (秒)
    MINIMUM_TWEET_INTERVAL = 20  # 必ずアカウントごとに 20 秒以上間隔を空けてツイートする

    # ヘッドレスブラウザの自動シャットダウンまでの無操作時間 (秒)
    BROWSER_IDLE_TIMEOUT = 60

    # Twitter アカウント ID ごとのシングルトンインスタンスを管理する辞書
    __instances: ClassVar[dict[int | None, TwitterGraphQLAPI]] = {}

    # 必ず Twitter アカウント ID ごとに1つのインスタンスになるように (Singleton)
    def __new__(cls, twitter_account: TwitterAccount) -> TwitterGraphQLAPI:
        """
        シングルトンパターンの実装
        同じ Twitter アカウント ID のインスタンスが既に存在する場合は、そのインスタンスを返す
        既存インスタンスが見つかった場合、コンストラクタに渡された twitter_account の情報で既存インスタンスを更新する

        Args:
            twitter_account (TwitterAccount): Twitter アカウントのモデル

        Returns:
            TwitterGraphQLAPI: Twitter GraphQL API クライアントのインスタンス
        """

        # まだ同じ Twitter アカウント ID のインスタンスがないときだけ、インスタンスを生成する
        ## __new__ は同期メソッドで await がないため、実行中は他のコルーチンに切り替わらない
        ## そのため、__instances へのアクセスはアトミックであり、ロックは不要
        if twitter_account.id not in cls.__instances:

            # 新しいインスタンスを作成する
            instance = super().__new__(cls)

            # Twitter アカウントのモデル
            instance.twitter_account = twitter_account

            # Zendriver で自動操作されるヘッドレスブラウザのインスタンス
            instance._browser = TwitterScrapeBrowser(twitter_account)

            # 一定期間後にヘッドレスブラウザをシャットダウンするタスク
            instance._shutdown_task = None
            # self._shutdown_task へのアクセスを保護するためのロック
            instance._shutdown_task_lock = asyncio.Lock()
            # GraphQL API の前回呼び出し時刻 (UNIX 時間)
            instance._last_graphql_api_call_time = 0.0

            # ツイート送信時の排他制御用のロック
            instance._tweet_lock = asyncio.Lock()
            # 前回ツイートを送信した時刻 (UNIX 時間)
            instance._last_tweet_time = 0.0

            # 生成したインスタンスを登録する
            cls.__instances[twitter_account.id] = instance
        else:
            # 既存インスタンスが見つかった場合、twitter_account の情報を更新する
            ## DB から取得した新鮮な twitter_account の情報で既存インスタンスを更新することで、認証情報の変更などが反映される
            existing_instance = cls.__instances[twitter_account.id]
            existing_instance.twitter_account = twitter_account

            # browser インスタンスが持っている twitter_account も更新する
            ## 次回 setup() が呼ばれた際に新しい Cookie が使われるようになる
            existing_instance._browser.twitter_account = twitter_account

        # 登録されているインスタンスを返す
        return cls.__instances[twitter_account.id]

    def __init__(self, twitter_account: TwitterAccount) -> None:
        """
        Twitter GraphQL API クライアントのインスタンスを取得する

        Args:
            twitter_account (TwitterAccount): Twitter アカウントのモデル
        """

        # インスタンス変数の型ヒントを定義
        # Singleton のためインスタンスの生成は __new__() で行うが、__init__() も定義しておかないと補完がうまく効かない
        self.twitter_account: TwitterAccount
        self._browser: TwitterScrapeBrowser
        self._shutdown_task: asyncio.Task[None] | None
        self._shutdown_task_lock: asyncio.Lock
        self._last_graphql_api_call_time: float
        self._tweet_lock: asyncio.Lock
        self._last_tweet_time: float

    @property
    def log_prefix(self) -> str:
        """
        ログのプレフィックス
        """
        return f'[TwitterGraphQLAPI][@{self.twitter_account.screen_name}]'

    @classmethod
    async def removeInstance(cls, twitter_account_id: int) -> None:
        """
        指定された Twitter アカウント ID のシングルトンインスタンスを削除する

        Args:
            twitter_account_id (int): 削除する Twitter アカウントの ID
        """

        # __instances へのアクセスは await がないためアトミックであり、ロックは不要
        ## __new__ は同期メソッドで await がないため、実行中は他のコルーチンに切り替わらない
        ## removeInstance の __instances へのアクセス部分（チェック・取得・削除）も await がないため、その部分はアトミック
        if twitter_account_id in cls.__instances:
            instance = cls.__instances[twitter_account_id]
            # シャットダウンタスクをキャンセル
            ## 複数の同時リクエスト完了時の競合状態を防ぐため、ロックで保護する
            async with instance._shutdown_task_lock:
                if instance._shutdown_task is not None:
                    if not instance._shutdown_task.done():
                        instance._shutdown_task.cancel()
                    instance._shutdown_task = None
            # ヘッドレスブラウザをシャットダウン
            ## browser.shutdown() が例外を投げた場合でもレジストリエントリは確実に削除する必要があるため、try/except で囲む
            if instance._browser is not None and instance._browser.is_setup_complete is True:
                try:
                    await instance._browser.shutdown()
                except Exception as ex:
                    logging.error(f'Failed to shutdown browser for Twitter account {twitter_account_id}:', exc_info=ex)
            # レジストリエントリを削除
            del cls.__instances[twitter_account_id]

    @classmethod
    async def rebindInstance(cls, previous_account_id: int | None, twitter_account: TwitterAccount) -> None:
        """
        Temporary アカウントで初期化したシングルトンを実際の Twitter アカウント ID に付け替える。

        Args:
            previous_account_id (int | None): Temporary 状態の Twitter アカウント ID。
            twitter_account (TwitterAccount): 永続化済みの Twitter アカウントモデル。
        """

        # 永続化済みの Twitter アカウント ID が取得できない場合は異常
        if twitter_account.id is None:
            logging.error('[TwitterGraphQLAPI][rebindInstance] twitter_account.id is None. Skip rebinding.')
            return

        # ID の変化が無い場合は情報だけ更新する
        if previous_account_id == twitter_account.id:
            instance = cls.__instances.get(twitter_account.id)
            if instance is not None:
                instance.twitter_account = twitter_account
                instance._browser.twitter_account = twitter_account
            return

        # Temporary なインスタンスが存在しない場合は何もしない
        if previous_account_id not in cls.__instances:
            return

        instance = cls.__instances.pop(previous_account_id)

        # 既に同じ ID に紐づくインスタンスが存在していた場合はリソースリークを防ぐため破棄する
        await cls.removeInstance(twitter_account.id)

        # インスタンスに最新の Twitter アカウント情報を適用し、新しい ID で登録する
        instance.twitter_account = twitter_account
        instance._browser.twitter_account = twitter_account
        cls.__instances[twitter_account.id] = instance

    async def __scheduleShutdownTask(self) -> None:
        """
        一定時間後にヘッドレスブラウザを自動停止させるタスクを再スケジュールする
        """

        # まだヘッドレスブラウザが立ち上がっていない場合は何もしない
        if self._browser.is_setup_complete is not True:
            return

        async def OnShutdown() -> None:
            # タイムアウト時間に到達するまで待つ
            await asyncio.sleep(self.BROWSER_IDLE_TIMEOUT)
            # GraphQL API の前回呼び出し時刻を確認し、タイムアウト時間が経過している場合のみ、
            # しばらく API 呼び出しが行われていないため、リソース節約のためにヘッドレスブラウザをシャットダウンする
            current_time = time.time()
            if current_time - self._last_graphql_api_call_time >= self.BROWSER_IDLE_TIMEOUT:
                logging.info(f'{self.log_prefix} Shutting down browser after {self.BROWSER_IDLE_TIMEOUT} seconds of inactivity.')
                await self._browser.shutdown()

        # 一定時間後にヘッドレスブラウザをシャットダウンするタスクを一旦キャンセルして再スケジュールする
        ## この処理は API リクエストの成功・失敗に関わらず API リクエスト完了後に常に実行すべき
        ## 複数の同時リクエスト完了時の競合状態を防ぐため、ロックで保護する
        async with self._shutdown_task_lock:
            if self._shutdown_task is not None:
                if not self._shutdown_task.done():
                    self._shutdown_task.cancel()
                self._shutdown_task = None
            self._shutdown_task = asyncio.create_task(OnShutdown())

    async def invokeGraphQLAPI(
        self,
        endpoint_name: str,
        variables: dict[str, Any],
        additional_flags: dict[str, Any] | None = None,
        error_message_prefix: str = 'Twitter API の操作に失敗しました。',
    ) -> dict[str, Any] | str:
        """
        Twitter Web App の GraphQL API に HTTP リクエストを送信する
        実際には GraphQL と言いつつペイロードで JSON を渡しているので謎… (本当に GraphQL なのか？)
        実際の API リクエストは TwitterScrapeBrowser 経由でヘッドレスブラウザから実行される

        Args:
            endpoint_name (str): GraphQL API のエンドポイント名 (例: 'CreateTweet')
            variables (dict[str, Any]): GraphQL API へのリクエストパラメータ (ペイロードのうち "variables" の部分)
            additional_flags (dict[str, Any] | None): 追加のフラグ（オプション）
            error_message_prefix (str, optional): エラー発生時に付与する prefix (例: 'ツイートの送信に失敗しました。')

        Returns:
            dict[str, Any] | str: GraphQL API のレスポンス (失敗時は日本語のエラーメッセージを返す)
        """

        # ヘッドレスブラウザがまだ起動していない場合、セットアップ処理を実行
        if self._browser.is_setup_complete is not True:
            try:
                await self._browser.setup()
            except (BrowserBinaryNotFoundError, BrowserConnectionFailedError) as ex:
                # Chrome / Brave 未導入時やブラウザ起動失敗時は、日本語のエラーメッセージをそのまま返す
                return str(ex)

        # TwitterScrapeBrowser 経由で GraphQL API に HTTP リクエストを送信
        browser = self._browser
        try:
            logging.info(f'{self.log_prefix} Requesting {endpoint_name} GraphQL API ...')
            logging.debug(f'{self.log_prefix} Request variables: {variables}')
            if additional_flags is not None:
                logging.debug(f'{self.log_prefix} Additional flags: {additional_flags}')
            raw_response = await browser.invokeGraphQLAPI(
                endpoint_name=endpoint_name,
                variables=variables,
                additional_flags=additional_flags,
            )
        except Exception as ex:
            logging.error(f'{self.log_prefix} Failed to connect to Twitter GraphQL API:', exc_info=ex)
            return error_message_prefix + 'Twitter API に接続できませんでした。'
        finally:
            # GraphQL API リクエスト完了後、更新された可能性があるヘッドレスブラウザの Cookie を DB 側に反映
            ## こうすることでヘッドレスブラウザと DB 間で Cookie の変更が同期されるはず
            ## この処理は API リクエストの成功・失敗に関わらず API リクエスト完了後に常に実行すべき
            cookies_txt_content = await browser.saveTwitterCookiesToNetscapeFormat()
            # Cookie を暗号化してから DB に反映する
            self.twitter_account.access_token_secret = self.twitter_account.encryptAccessTokenSecret(cookies_txt_content)
            await self.twitter_account.save()  # これで変更が DB に反映される

            # GraphQL API の前回呼び出し時刻を更新
            self._last_graphql_api_call_time = time.time()

            # 一定時間後にヘッドレスブラウザをシャットダウンするタスクを再スケジュールする
            await self.__scheduleShutdownTask()

        # 生のレスポンスデータを取得
        parsed_response = raw_response['parsedResponse']
        status_code = raw_response['statusCode']
        response_text = raw_response['responseText']
        headers = raw_response['headers']
        request_error = raw_response['requestError']

        # リクエストエラーが発生した場合（接続エラー）
        if request_error:
            logging.error(f'{self.log_prefix} Request error: {request_error}')
            return error_message_prefix + 'Twitter API に接続できませんでした。'

        # JSON でないレスポンスが返ってきた場合
        ## charset=utf-8 が付いている場合もあるので完全一致ではなく部分一致で判定
        if headers and isinstance(headers, dict):
            content_type = headers.get('content-type', '')
            if content_type and 'application/json' not in content_type:
                logging.error(f'{self.log_prefix} Response is not JSON. (Content-Type: {content_type})')
                return (
                    error_message_prefix
                    + f'Twitter API から JSON 以外のレスポンスが返されました。(Content-Type: {content_type})'
                )

        # レスポンスを JSON としてパース
        response_json: dict[str, Any] | None = None
        if parsed_response is not None:
            # JavaScript 側で既にパース済み
            response_json = parsed_response
        elif response_text:
            # JavaScript 側でパースに失敗した場合、Python 側で再試行
            try:
                response_json = json.loads(response_text)
            except Exception as ex:
                # 何もレスポンスが返ってきていないが、HTTP ステータスコードが 200 系以外で返ってきている場合
                if status_code is not None and not (200 <= status_code < 300):
                    logging.error(f'{self.log_prefix} Failed to invoke GraphQL API. (HTTP Error {status_code})')
                    logging.error(f'{self.log_prefix} Response: {response_text}')
                    return error_message_prefix + f'Twitter API から HTTP {status_code} エラーが返されました。'

                # HTTP ステータスコードは 200 系だが、何もレスポンスが返ってきていない場合
                logging.error(f'{self.log_prefix} Failed to parse response as JSON:', exc_info=ex)
                return error_message_prefix + 'Twitter API のレスポンスを JSON としてパースできませんでした。'

        if response_json is None:
            logging.error(f'{self.log_prefix} Failed to parse response as JSON.')
            return error_message_prefix + 'Twitter API のレスポンスを JSON としてパースできませんでした。'

        # API レスポンスにエラーが含まれていて、かつ data キーが存在しない場合
        ## API レスポンスは Twitter の仕様変更で変わりうるので、ここで判定されなかったと言ってエラーでないとは限らない
        ## なぜか正常にレスポンスが含まれているのにエラーも返ってくる場合があるので、その場合は（致命的な）エラーではないと判断する
        if 'errors' in response_json and 'data' not in response_json:
            # Twitter API のエラーコードとエラーメッセージを取得
            ## このエラーコードは API v1.1 の頃と変わっていない
            response_error_code = response_json['errors'][0]['code']
            response_error_message = response_json['errors'][0]['message']

            # 想定外のエラーコードが返ってきた場合のエラーメッセージ
            alternative_error_message = f'Code: {response_error_code} / Message: {response_error_message}'
            logging.error(f'{self.log_prefix} Failed to invoke GraphQL API ({alternative_error_message})')

            # エラーコードに対応するエラーメッセージを返し、対応するものがない場合は alternative_error_message を返す
            return error_message_prefix + self.ERROR_MESSAGES.get(response_error_code, alternative_error_message)

        # API レスポンスにエラーが含まれていないが、'data' キーが存在しない場合
        ## 実装時点の GraphQL API は必ず成功時は 'data' キーの下にレスポンスが格納されるはず
        ## もし 'data' キーが存在しない場合は、API 仕様が変更されている可能性がある
        if 'data' not in response_json:
            logging.error(f'{self.log_prefix} Response does not have "data" key.')
            return (
                error_message_prefix
                + 'Twitter API のレスポンスに "data" キーが存在しません。開発者に修正を依頼してください。'
            )

        # ここまで来たら (中身のデータ構造はともかく) GraphQL API レスポンスの取得には成功しているはず
        logging.info(f'{self.log_prefix} {endpoint_name} GraphQL API request completed.')
        return response_json['data']

    async def keepAlive(self) -> None:
        """
        ヘッドレスブラウザの自動シャットダウンを抑制する
        視聴画面の Twitter パネルでユーザーの操作が継続している間はこのメソッドが定期的に呼び出される
        """

        # ヘッドレスブラウザが起動していないときは念のため何もしない
        if self._browser.is_setup_complete is not True:
            return

        # 直近アクセス時刻を更新し、再度シャットダウンタイマーをセットする
        self._last_graphql_api_call_time = time.time()
        await self.__scheduleShutdownTask()

    async def fetchLoggedViewer(
        self,
    ) -> schemas.TweetUser | schemas.TwitterAPIResult:
        """
        現在ログイン中の Twitter アカウントの情報を取得する

        Returns:
            schemas.TweetUser | schemas.TwitterAPIResult: Twitter アカウントの情報 (失敗時はエラーメッセージ)
        """

        # Twitter GraphQL API にリクエスト
        response = await self.invokeGraphQLAPI(
            endpoint_name='Viewer',
            variables={
                'withCommunitiesMemberships': True,
            },
            additional_flags={
                'fieldToggles': {
                    'isDelegate': False,
                    'withAuxiliaryUserLabels': True,
                },
            },
            error_message_prefix='ユーザー情報の取得に失敗しました。',
        )

        # 戻り値が str の場合、ユーザー情報の取得に失敗している (エラーメッセージが返ってくる)
        if isinstance(response, str):
            logging.error(f'{self.log_prefix} Failed to fetch logged viewer: {response}')
            return schemas.TwitterAPIResult(
                is_success=False,
                detail=response,  # エラーメッセージをそのまま返す
            )

        # レスポンスからユーザー情報を取得
        ## レスポンス構造: data.viewer.user_results.result
        try:
            viewer = response.get('viewer', {})
            user_results = viewer.get('user_results', {})
            result = user_results.get('result', {})

            # 必要な情報が存在しない場合はエラーを返す
            if not result:
                logging.error(f'{self.log_prefix} Failed to fetch logged viewer: user_results.result not found')
                return schemas.TwitterAPIResult(
                    is_success=False,
                    detail='ユーザー情報の取得に失敗しました。レスポンスにユーザー情報が含まれていません。開発者に修正を依頼してください。',
                )

            # ユーザー ID を取得
            user_id = result.get('rest_id')
            if not user_id:
                logging.error(f'{self.log_prefix} Failed to fetch logged viewer: rest_id not found')
                return schemas.TwitterAPIResult(
                    is_success=False,
                    detail='ユーザー情報の取得に失敗しました。ユーザー ID を取得できませんでした。開発者に修正を依頼してください。',
                )

            # ユーザー名とスクリーンネームを取得
            core = result.get('core', {})
            name = core.get('name', '')
            screen_name = core.get('screen_name', '')
            if not name or not screen_name:
                logging.error(f'{self.log_prefix} Failed to fetch logged viewer: name or screen_name not found')
                return schemas.TwitterAPIResult(
                    is_success=False,
                    detail='ユーザー情報の取得に失敗しました。ユーザー名またはスクリーンネームを取得できませんでした。開発者に修正を依頼してください。',
                )

            # アイコン URL を取得
            avatar = result.get('avatar', {})
            icon_url = avatar.get('image_url', '')
            if not icon_url:
                logging.error(f'{self.log_prefix} Failed to fetch logged viewer: image_url not found')
                return schemas.TwitterAPIResult(
                    is_success=False,
                    detail='ユーザー情報の取得に失敗しました。アイコン URL を取得できませんでした。開発者に修正を依頼してください。',
                )

            # (ランダムな文字列)_normal.jpg だと画像サイズが小さいので、(ランダムな文字列).jpg に置換
            icon_url = icon_url.replace('_normal', '')

            return schemas.TweetUser(
                id=str(user_id),
                name=name,
                screen_name=screen_name,
                icon_url=icon_url,
            )

        except Exception as ex:
            # 予期しないエラーが発生した場合
            logging.error(f'{self.log_prefix} Failed to fetch logged viewer:', exc_info=ex)
            logging.error(f'{self.log_prefix} Response: {response}')
            return schemas.TwitterAPIResult(
                is_success=False,
                detail='ユーザー情報の取得に失敗しました。予期しないエラーが発生しました。開発者に修正を依頼してください。',
            )

    async def createTweet(
        self,
        tweet: str,
        media_ids: list[str] = [],
    ) -> schemas.PostTweetResult | schemas.TwitterAPIResult:
        """
        ツイートを送信する

        Args:
            tweet (str): ツイート内容
            media_ids (list[str], optional): 添付するメディアの ID のリスト (デフォルトは空リスト)

        Returns:
            schemas.PostTweetResult | schemas.TwitterAPIResult: ツイートの送信結果
        """

        # ツイートの最小送信間隔を守るためにロックを取得
        async with self._tweet_lock:
            # 最後のツイート時刻から最小送信間隔を経過していない場合は待機
            current_time = time.time()
            wait_time = max(0, self.MINIMUM_TWEET_INTERVAL - (current_time - self._last_tweet_time))
            if wait_time > 0:
                await asyncio.sleep(wait_time)

            # 画像の media_id をリストに格納 (画像がない場合は空のリストになる)
            media_entities: list[dict[str, Any]] = []
            for media_id in media_ids:
                media_entities.append({'media_id': media_id, 'tagged_users': []})

            # ツイート ID を取得できない場合 (スパム判定されたケースが多い) に備え、最大2回までリトライする
            ## リトライ時は 3〜5 秒のランダムな間隔で待機してから再送信する (経験的にこの範囲で待つと成功しやすい)
            MAX_RETRY_COUNT = 2
            RETRY_WAIT_SECONDS_MIN = 3.0
            RETRY_WAIT_SECONDS_MAX = 5.0
            for retry_count in range(MAX_RETRY_COUNT + 1):

                # Twitter GraphQL API にリクエスト
                response = await self.invokeGraphQLAPI(
                    endpoint_name='CreateTweet',
                    variables={
                        'tweet_text': tweet,
                        'dark_request': False,
                        'media': {
                            'media_entities': media_entities,
                            'possibly_sensitive': False,
                        },
                        'semantic_annotation_ids': [],
                        'disallowed_reply_options': None,
                    },
                    error_message_prefix='ツイートの送信に失敗しました。',
                )

                # 最後のツイート時刻を更新
                self._last_tweet_time = time.time()

                # 戻り値が str の場合、ツイートの送信に失敗している (エラーメッセージが返ってくる)
                # この場合は明示的な API エラーなのでリトライせずにそのまま返す
                if isinstance(response, str):
                    logging.error(f'{self.log_prefix} Failed to create tweet: {response}')
                    return schemas.TwitterAPIResult(
                        is_success=False,
                        detail=response,  # エラーメッセージをそのまま返す
                    )

                # おそらくツイートに成功しているはずなので、可能であれば送信したツイートの ID を取得
                tweet_id: str
                try:
                    tweet_id = str(response['create_tweet']['tweet_results']['result']['rest_id'])
                except Exception as ex:
                    # API レスポンスが変わっているか、スパム判定でツイート ID を取得できなかった
                    logging.error(f'{self.log_prefix} Failed to get tweet ID (attempt {retry_count + 1}/{MAX_RETRY_COUNT + 1}):', exc_info=ex)
                    logging.error(f'{self.log_prefix} Response: {response}')
                    # まだリトライ回数が残っている場合は待機してから再送信する
                    if retry_count < MAX_RETRY_COUNT:
                        retry_wait_seconds = random.uniform(RETRY_WAIT_SECONDS_MIN, RETRY_WAIT_SECONDS_MAX)
                        logging.info(f'{self.log_prefix} Retrying tweet after {retry_wait_seconds:.1f} seconds...')
                        await asyncio.sleep(retry_wait_seconds)
                        continue
                    # リトライ回数を使い切った場合はエラーを返す
                    return schemas.PostTweetResult(
                        is_success=False,
                        detail='ツイートを送信しましたが、ツイート ID を取得できませんでした。開発者に修正を依頼してください。',
                        tweet_url='https://x.com/i/status/__error__',
                    )

                return schemas.PostTweetResult(
                    is_success=True,
                    detail='ツイートを送信しました。',
                    tweet_url=f'https://x.com/i/status/{tweet_id}',
                )

            # ここに到達することはないが、型チェッカーのために念のため返す
            return schemas.PostTweetResult(
                is_success=False,
                detail='ツイートを送信しましたが、ツイート ID を取得できませんでした。開発者に修正を依頼してください。',
                tweet_url='https://x.com/i/status/__error__',
            )

    async def createRetweet(self, tweet_id: str) -> schemas.TwitterAPIResult:
        """
        ツイートをリツイートする

        Args:
            tweet_id (str): リツイートするツイートの ID

        Returns:
            schemas.TwitterAPIResult: リツイートの結果
        """

        # Twitter GraphQL API にリクエスト
        response = await self.invokeGraphQLAPI(
            endpoint_name='CreateRetweet',
            variables={
                'tweet_id': tweet_id,
                'dark_request': False,
            },
            error_message_prefix='リツイートに失敗しました。',
        )

        # 戻り値が str の場合、リツイートに失敗している (エラーメッセージが返ってくる)
        if isinstance(response, str):
            logging.error(f'{self.log_prefix} Failed to create retweet: {response}')
            return schemas.TwitterAPIResult(
                is_success=False,
                detail=response,  # エラーメッセージをそのまま返す
            )

        return schemas.TwitterAPIResult(
            is_success=True,
            detail='リツイートしました。',
        )

    async def deleteRetweet(self, tweet_id: str) -> schemas.TwitterAPIResult:
        """
        ツイートのリツイートを取り消す

        Args:
            tweet_id (str): リツイートを取り消すツイートの ID

        Returns:
            schemas.TwitterAPIResult: リツイートの取り消し結果
        """

        # Twitter GraphQL API にリクエスト
        response = await self.invokeGraphQLAPI(
            endpoint_name='DeleteRetweet',
            variables={
                'source_tweet_id': tweet_id,
                'dark_request': False,
            },
            error_message_prefix='リツイートの取り消しに失敗しました。',
        )

        # 戻り値が str の場合、リツイートの取り消しに失敗している (エラーメッセージが返ってくる)
        if isinstance(response, str):
            logging.error(f'{self.log_prefix} Failed to delete retweet: {response}')
            return schemas.TwitterAPIResult(
                is_success=False,
                detail=response,  # エラーメッセージをそのまま返す
            )

        return schemas.TwitterAPIResult(
            is_success=True,
            detail='リツイートを取り消ししました。',
        )

    async def favoriteTweet(self, tweet_id: str) -> schemas.TwitterAPIResult:
        """
        ツイートをいいねする

        Args:
            tweet_id (str): いいねするツイートの ID

        Returns:
            schemas.TwitterAPIResult: いいねの結果
        """

        # Twitter GraphQL API にリクエスト
        response = await self.invokeGraphQLAPI(
            endpoint_name='FavoriteTweet',
            variables={
                'tweet_id': tweet_id,
            },
            error_message_prefix='いいねに失敗しました。',
        )

        # 戻り値が str の場合、いいねに失敗している (エラーメッセージが返ってくる)
        if isinstance(response, str):
            logging.error(f'{self.log_prefix} Failed to favorite tweet: {response}')
            return schemas.TwitterAPIResult(
                is_success=False,
                detail=response,  # エラーメッセージをそのまま返す
            )

        return schemas.TwitterAPIResult(
            is_success=True,
            detail='いいねしました。',
        )

    async def unfavoriteTweet(self, tweet_id: str) -> schemas.TwitterAPIResult:
        """
        ツイートのいいねを取り消す

        Args:
            tweet_id (str): いいねを取り消すツイートの ID

        Returns:
            schemas.TwitterAPIResult: いいねの取り消し結果
        """

        # Twitter GraphQL API にリクエスト
        response = await self.invokeGraphQLAPI(
            endpoint_name='UnfavoriteTweet',
            variables={
                'tweet_id': tweet_id,
            },
            error_message_prefix='いいねの取り消しに失敗しました。',
        )

        # 戻り値が str の場合、いいねの取り消しに失敗している (エラーメッセージが返ってくる)
        if isinstance(response, str):
            logging.error(f'{self.log_prefix} Failed to unfavorite tweet: {response}')
            return schemas.TwitterAPIResult(
                is_success=False,
                detail=response,  # エラーメッセージをそのまま返す
            )

        return schemas.TwitterAPIResult(
            is_success=True,
            detail='いいねを取り消しました。',
        )

    def __getCursorIDFromTimelineAPIResponse(
        self, response: dict[str, Any], cursor_type: Literal['Top', 'Bottom']
    ) -> str | None:
        """
        GraphQL API のうちツイートタイムライン系の API レスポンスから、指定されたタイプに一致するカーソル ID を取得する
        次の API リクエスト時にカーソル ID を指定すると、そのカーソル ID から次のページを取得できる

        Args:
            response (dict[str, Any]): ツイートタイムライン系の API レスポンス
            cursor_type (Literal['Top', 'Bottom']): カーソル ID タイプ (Top: 現在より最新のツイート, Bottom: 現在より過去のツイート)

        Returns:
            str | None: カーソル ID (仕様変更などで取得できなかった場合は None)
        """

        # HomeLatestTimeline からのレスポンス
        if 'home' in response:
            instructions = response.get('home', {}).get('home_timeline_urt', {}).get('instructions', [])
        # SearchTimeline からのレスポンス
        elif 'search_by_raw_query' in response:
            instructions = (
                response.get('search_by_raw_query', {})
                .get('search_timeline', {})
                .get('timeline', {})
                .get('instructions', [])
            )
        # それ以外のレスポンス (通常あり得ないため、ここに到達した場合はレスポンス構造が変わった可能性が高い)
        else:
            instructions = []
            logging.warning(f'{self.log_prefix} Unknown timeline response format: {response}')

        for instruction in instructions:
            if instruction.get('type') == 'TimelineAddEntries':
                entries = instruction.get('entries', [])
                for entry in entries:
                    content = entry.get('content', {})
                    if (
                        content.get('entryType') == 'TimelineTimelineCursor'
                        and content.get('cursorType') == cursor_type
                    ):
                        return content.get('value')
                    # Bottom 指定時、たまに通常 cursorType が Bottom になるところ Gap になっている場合がある
                    # その場合は Bottom の Cursor として解釈する
                    elif (
                        content.get('entryType') == 'TimelineTimelineCursor'
                        and content.get('cursorType') == 'Gap'
                        and cursor_type == 'Bottom'
                    ):
                        return content.get('value')
            elif instruction.get('type') == 'TimelineReplaceEntry':
                entry = instruction.get('entry', {})
                content = entry.get('content', {})
                if content.get('entryType') == 'TimelineTimelineCursor' and content.get('cursorType') == cursor_type:
                    return content.get('value')
                # Bottom 指定時、たまに通常 cursorType が Bottom になるところ Gap になっている場合がある
                # その場合は Bottom の Cursor として解釈する
                elif (
                    content.get('entryType') == 'TimelineTimelineCursor'
                    and content.get('cursorType') == 'Gap'
                    and cursor_type == 'Bottom'
                ):
                    return content.get('value')

        return None

    def __getTweetsFromTimelineAPIResponse(self, response: dict[str, Any]) -> list[schemas.Tweet]:
        """
        GraphQL API のうちツイートタイムライン系の API レスポンスから、ツイートリストを取得する

        Args:
            response (dict[str, Any]): ツイートタイムライン系の API レスポンス

        Returns:
            list[schemas.Tweet]: ツイートリスト
        """

        def format_tweet(raw_tweet_object: dict[str, Any]) -> schemas.Tweet:
            """API レスポンスから取得したツイート情報を schemas.Tweet に変換する"""

            # もし '__typename' が 'TweetWithVisibilityResults' なら、ツイート情報がさらにネストされているのでそれを取得
            if raw_tweet_object['__typename'] == 'TweetWithVisibilityResults':
                raw_tweet_object = raw_tweet_object['tweet']

            # リツイートがある場合は、リツイート元のツイートの情報を取得
            retweeted_tweet = None
            if 'retweeted_status_result' in raw_tweet_object['legacy']:
                retweeted_tweet = format_tweet(raw_tweet_object['legacy']['retweeted_status_result']['result'])

            # 引用リツイートがある場合は、引用リツイート元のツイートの情報を取得
            ## なぜかリツイートと異なり legacy 以下ではなく直下に入っている
            quoted_tweet = None
            if 'quoted_status_result' in raw_tweet_object:
                if 'result' not in raw_tweet_object['quoted_status_result']:
                    # ごく稀に quoted_status_result.result が空のツイート情報が返ってくるので、その場合は警告を出した上で無視する
                    logging.warning(f'{self.log_prefix} Quoted tweet not found: {raw_tweet_object.get("rest_id", "unknown")}')
                else:
                    quoted_tweet = format_tweet(raw_tweet_object['quoted_status_result']['result'])

            # 画像の URL を取得
            image_urls = []
            movie_url = None
            if 'extended_entities' in raw_tweet_object['legacy']:
                for media in raw_tweet_object['legacy']['extended_entities']['media']:
                    if media['type'] == 'photo':
                        image_urls.append(media['media_url_https'])
                    elif media['type'] in ['video', 'animated_gif']:
                        # content_type が video/mp4 かつ bitrate が最も高いものを取得
                        mp4_variants: list[dict[str, Any]] = list(
                            filter(
                                lambda variant: variant['content_type'] == 'video/mp4', media['video_info']['variants']
                            )
                        )
                        if len(mp4_variants) > 0:
                            highest_bitrate_variant: dict[str, Any] = max(
                                mp4_variants,
                                key=lambda variant: int(variant['bitrate']) if 'bitrate' in variant else 0,  # type: ignore
                            )
                            movie_url = (
                                str(highest_bitrate_variant['url']) if 'url' in highest_bitrate_variant else None
                            )

            # t.co の URL を展開した URL に置換
            expanded_text = raw_tweet_object['legacy']['full_text']
            if 'entities' in raw_tweet_object['legacy'] and 'urls' in raw_tweet_object['legacy']['entities']:
                for url_entity in raw_tweet_object['legacy']['entities']['urls']:
                    if 'expanded_url' in url_entity:  # 展開後の URL が存在する場合のみ (稀に存在しない場合がある)
                        expanded_text = expanded_text.replace(url_entity['url'], url_entity['expanded_url'])

            # 残った t.co の URL を削除
            if len(image_urls) > 0 or movie_url:
                expanded_text = re.sub(r'\s*https://t\.co/\w+$', '', expanded_text)

            return schemas.Tweet(
                id=raw_tweet_object['legacy']['id_str'],
                created_at=datetime.strptime(
                    raw_tweet_object['legacy']['created_at'], '%a %b %d %H:%M:%S %z %Y'
                ).astimezone(JST),
                user=schemas.TweetUser(
                    id=raw_tweet_object['core']['user_results']['result']['rest_id'],
                    name=raw_tweet_object['core']['user_results']['result']['core']['name'],
                    screen_name=raw_tweet_object['core']['user_results']['result']['core']['screen_name'],
                    # (ランダムな文字列)_normal.jpg だと画像サイズが小さいので、(ランダムな文字列).jpg に置換
                    icon_url=raw_tweet_object['core']['user_results']['result']['avatar']['image_url'].replace(
                        '_normal', ''
                    ),
                ),
                text=expanded_text,
                lang=raw_tweet_object['legacy']['lang'],
                via=re.sub(r'<.+?>', '', raw_tweet_object['source']),
                image_urls=image_urls if len(image_urls) > 0 else None,
                movie_url=movie_url,
                retweet_count=raw_tweet_object['legacy']['retweet_count'],
                favorite_count=raw_tweet_object['legacy']['favorite_count'],
                retweeted=raw_tweet_object['legacy']['retweeted'],
                favorited=raw_tweet_object['legacy']['favorited'],
                retweeted_tweet=retweeted_tweet,
                quoted_tweet=quoted_tweet,
            )

        # HomeLatestTimeline からのレスポンス
        if 'home' in response:
            instructions = response.get('home', {}).get('home_timeline_urt', {}).get('instructions', [])
        # SearchTimeline からのレスポンス
        elif 'search_by_raw_query' in response:
            instructions = (
                response.get('search_by_raw_query', {})
                .get('search_timeline', {})
                .get('timeline', {})
                .get('instructions', [])
            )
        # それ以外のレスポンス (通常あり得ないため、ここに到達した場合はレスポンス構造が変わった可能性が高い)
        else:
            instructions = []
            logging.warning(f'{self.log_prefix} Unknown timeline response format: {response}')

        tweets: list[schemas.Tweet] = []
        for instruction in instructions:
            if instruction.get('type') == 'TimelineAddEntries':
                entries = instruction.get('entries', [])
                for entry in entries:
                    # entryId が promoted- から始まるツイートは広告ツイートなので除外
                    if entry.get('entryId', '').startswith('promoted-'):
                        continue
                    content = entry.get('content', {})
                    if (
                        content.get('entryType') == 'TimelineTimelineItem'
                        and content.get('itemContent', {}).get('itemType') == 'TimelineTweet'
                    ):
                        tweet_results = content.get('itemContent', {}).get('tweet_results', {}).get('result')
                        if tweet_results and tweet_results.get('__typename') in ['Tweet', 'TweetWithVisibilityResults']:
                            tweets.append(format_tweet(tweet_results))

        return tweets

    async def homeLatestTimeline(
        self,
        cursor_id: str | None = None,
    ) -> schemas.TimelineTweetsResult | schemas.TwitterAPIResult:
        """
        タイムラインの最新ツイートを取得する
        一応 API 上は取得するツイート数を指定できることになっているが、検索と異なり実際に返ってくるツイート数は保証されてないっぽい (100 件返ってくることもある)

        Args:
            cursor_id (str | None, optional): 次のページを取得するためのカーソル ID (デフォルトは None)

        Returns:
            schemas.TimelineTweets | schemas.TwitterAPIResult: 検索結果
        """

        # variables の挿入順序を Twitter Web App に厳密に合わせるためにこのような実装としている
        variables: dict[str, Any] = {}
        if cursor_id is None:
            ## カーソル ID が指定されていないときは20件取得する (Twitter Web App の挙動に合わせる)
            variables['count'] = 20
        else:
            ## カーソル ID が指定されているときは40件取得する (Twitter Web App の挙動に合わせる)
            variables['count'] = 40
        if cursor_id is not None:
            variables['cursor'] = cursor_id
        variables['includePromotedContent'] = True
        variables['latestControlAvailable'] = True
        if cursor_id is None:
            ## カーソル ID が指定されていないときは、ページの初回ロード時のリクエストに偽装する
            variables['requestContext'] = 'launch'
            ## Twitter Web App のリクエストでは seenTweetIds も指定されることが多いが、
            ## ここでは「PWA のローカルキャッシュが全く残っていないが認証情報はある」際の初回ページロードに偽装する
            ## seenTweetIds はどうも PWA 側の何らかのツイートキャッシュが1つ以上ある時に指定されるものらしい
            ## seenTweetIds が1つ以上指定されているとき、本来は invokeGraphQLAPI() の additional_flags に
            ## {"forcePost": True} を指定する必要があるが、今回は seenTweetIds を指定しないので不要
        else:
            ## カーソル ID が指定されているときは、「フォロー中」ボタンをクリックして手動更新をかけた場合に偽装する
            ## この場合 seenTweetIds は指定されない
            variables['requestContext'] = 'ptr'

        # Twitter GraphQL API にリクエスト
        response = await self.invokeGraphQLAPI(
            endpoint_name='HomeLatestTimeline',
            variables=variables,
            error_message_prefix='タイムラインの取得に失敗しました。',
        )

        # 戻り値が str の場合、タイムラインの取得に失敗している (エラーメッセージが返ってくる)
        if isinstance(response, str):
            logging.error(f'{self.log_prefix} Failed to fetch timeline: {response}')
            return schemas.TwitterAPIResult(
                is_success=False,
                detail=response,  # エラーメッセージをそのまま返す
            )

        # まずはカーソル ID を取得
        ## カーソル ID が取得できなかった場合は仕様変更があったとみなし、エラーを返す
        next_cursor_id = self.__getCursorIDFromTimelineAPIResponse(
            response, 'Top'
        )  # 現在よりも新しいツイートを取得するためのカーソル ID
        previous_cursor_id = self.__getCursorIDFromTimelineAPIResponse(
            response, 'Bottom'
        )  # 現在よりも過去のツイートを取得するためのカーソル ID
        if next_cursor_id is None or previous_cursor_id is None:
            logging.error(f'{self.log_prefix} Failed to fetch timeline: Cursor ID not found')
            return schemas.TwitterAPIResult(
                is_success=False,
                detail='タイムラインの取得に失敗しました。カーソル ID を取得できませんでした。開発者に修正を依頼してください。',
            )

        # ツイートリストを取得
        ## 取得できなかった場合、あるいは単純に一致する結果がない場合は空のリストになる
        tweets = self.__getTweetsFromTimelineAPIResponse(response)

        return schemas.TimelineTweetsResult(
            is_success=True,
            detail='タイムラインを取得しました。',
            next_cursor_id=next_cursor_id,
            previous_cursor_id=previous_cursor_id,
            tweets=tweets,
        )

    async def searchTimeline(
        self,
        search_type: Literal['Top', 'Latest'],
        query: str,
        cursor_id: str | None = None,
    ) -> schemas.TimelineTweetsResult | schemas.TwitterAPIResult:
        """
        ツイートを検索する

        Args:
            search_type (Literal['Top', 'Latest']): 検索タイプ (Top: トップツイート, Latest: 最新ツイート)
            query (str): 検索クエリ
            cursor_id (str | None, optional): 次のページを取得するためのカーソル ID (デフォルトは None)

        Returns:
            schemas.TimelineTweets | schemas.TwitterAPIResult: 検索結果
        """

        # variables の挿入順序を Twitter Web App に厳密に合わせるためにこのような実装としている
        variables: dict[str, Any] = {}
        variables['rawQuery'] = query.strip() + ' exclude:replies lang:ja'
        if cursor_id is None:
            ## カーソル ID が指定されていないときは20件取得する (Twitter Web App の挙動に合わせる)
            variables['count'] = 20
        else:
            ## カーソル ID が指定されているときは40件取得する (Twitter Web App の挙動に合わせる)
            ## 厳密にはより新しいツイートを取得するためのカーソル ID が指定されているときは40件、
            ## より古い過去のツイートを取得するためのカーソル ID が指定されているときは20件取得される仕様のようだが、
            ## 両者を判別する方法がないので一律40件取得する
            variables['count'] = 40
        if cursor_id is not None:
            variables['cursor'] = cursor_id
        ## Twitter Web App で検索すると typed_query になることが多いのでそれに合わせる
        variables['querySource'] = 'typed_query'
        ## 検索タイプに Top か Latest を指定する
        variables['product'] = search_type
        ## Twitter Web App の挙動に合わせて設定
        variables['withGrokTranslatedBio'] = False

        # Twitter GraphQL API にリクエスト
        response = await self.invokeGraphQLAPI(
            endpoint_name='SearchTimeline',
            variables=variables,
            error_message_prefix='ツイートの検索に失敗しました。',
        )

        # 戻り値が str の場合、ツイートの検索に失敗している (エラーメッセージが返ってくる)
        if isinstance(response, str):
            logging.error(f'{self.log_prefix} Failed to search tweets: {response}')
            return schemas.TwitterAPIResult(
                is_success=False,
                detail=response,  # エラーメッセージをそのまま返す
            )

        # まずはカーソル ID を取得
        ## カーソル ID が取得できなかった場合は仕様変更があったとみなし、エラーを返す
        next_cursor_id = self.__getCursorIDFromTimelineAPIResponse(
            response, 'Top'
        )  # 現在よりも新しいツイートを取得するためのカーソル ID
        previous_cursor_id = self.__getCursorIDFromTimelineAPIResponse(
            response, 'Bottom'
        )  # 現在よりも過去のツイートを取得するためのカーソル ID
        if next_cursor_id is None or previous_cursor_id is None:
            logging.error(f'{self.log_prefix} Failed to search tweets: Cursor ID not found')
            return schemas.TwitterAPIResult(
                is_success=False,
                detail='ツイートの検索に失敗しました。カーソル ID を取得できませんでした。開発者に修正を依頼してください。',
            )

        # ツイートリストを取得
        ## 取得できなかった場合、あるいは単純に一致する結果がない場合は空のリストになる
        tweets = self.__getTweetsFromTimelineAPIResponse(response)

        return schemas.TimelineTweetsResult(
            is_success=True,
            detail='ツイートを検索しました。',
            next_cursor_id=next_cursor_id,
            previous_cursor_id=previous_cursor_id,
            tweets=tweets,
        )
