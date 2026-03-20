import asyncio
import base64
import json
import random
import time
from typing import Any

import anyio
from fastapi import UploadFile
from pydantic import BaseModel
from zendriver import Browser, Tab, cdp

from app import logging
from app.constants import STATIC_DIR
from app.models.TwitterAccount import TwitterAccount


class BrowserBinaryNotFoundError(RuntimeError):
    """
    Chrome / Brave の実行ファイルが検出できず、Zendriver がブラウザを起動できない場合に送出される例外
    """

class BrowserConnectionFailedError(RuntimeError):
    """
    Chrome / Brave はおそらく起動できたが、ブラウザインスタンスへの接続に失敗した場合に送出される例外
    """

class TwitterBrowserGraphQLAPIResult(BaseModel):
    """ヘッドレスブラウザ経由の GraphQL API レスポンスの生データ。"""

    parsed_response: Any | None = None
    status_code: int | None = None
    response_text: str | None = None
    headers: dict[str, Any] | None = None
    request_error: str | None = None

class PostTweetViaComposeUIResult(BaseModel):
    """compose UI 自動操作によるツイート送信の結果。"""

    is_success: bool
    error_message: str | None = None
    compose_submitted_at: float | None = None
    graphql_api_result: TwitterBrowserGraphQLAPIResult | None = None


class TwitterScrapeBrowser:
    """
    Twitter のヘッドレスブラウザ操作を隠蔽するクラス
    ヘッドレスブラウザのセットアップ処理や、ブラウザインスタンス自身の低レベル操作を隠蔽する
    """

    def __init__(self, twitter_account: TwitterAccount) -> None:
        """
        TwitterScrapeBrowser を初期化する

        Args:
            twitter_account (TwitterAccount): Twitter アカウントのモデル
        """

        self.twitter_account = twitter_account

        # Zendriver のブラウザインスタンス
        self._browser: Browser | None = None
        # 現在アクティブなタブ（ページ）インスタンス
        self._page: Tab | None = None

        # セットアップ処理が完了したかどうかのフラグ
        self.is_setup_complete = False
        # セットアップ・シャットダウン処理の排他制御用ロック
        ## setup と shutdown が同時に実行されないようにするため、同じロックを使用する
        self._setup_lock = asyncio.Lock()

    @property
    def log_prefix(self) -> str:
        """
        ログのプレフィックス
        """
        return f'[TwitterScrapeBrowser][@{self.twitter_account.screen_name}]'

    async def setup(self) -> None:
        """
        ヘッドレスブラウザを起動し、Cookie の供給などのセットアップ処理を行う
        既にセットアップ済みの場合は何も行われない
        """

        # セットアップ処理が複数進行していないことを確認
        async with self._setup_lock:
            # 既にセットアップ済みの場合は何もしない
            if self.is_setup_complete is True:
                return

            # セットアップ処理の完了を把握するための Future を作成
            setup_complete_future: asyncio.Future[bool] = asyncio.Future()

            # Zendriver でヘッドレスブラウザを起動
            logging.info(f'{self.log_prefix} Starting browser...')
            try:
                self._browser = await Browser.create(
                    # ユーザーデータディレクトリはあえて設定せず、立ち上げたプロセスが終了したらプロファイルも消えるようにする
                    # Cookie に関しては別途 DB と同期・永続化されていて、毎回セットアップ時に復元されるため問題はない
                    user_data_dir=None,
                    # 今の所ウインドウを表示せずとも問題なく動作しているので、ヘッドレスモードで起動する
                    headless=True,
                    # ブラウザは現在の環境にインストールされているものを自動選択させる
                    browser='auto',
                    # Chrome 系ブラウザの起動最適化フラグをチューニングし、なるべくメモリ使用量を下げる
                    # Zendriver デフォルトで指定されているフラグに加え、さらに以下のフラグを追加する
                    browser_args=[
                        # ウインドウをゲストモードで起動する
                        '--bwsi',
                        # 互換性の問題だとかが起きそうな予感がするので GPU レンダリングを無効化
                        '--disable-gpu',
                        '--use-gl=swiftshader',
                        # レンダラープロセスを1つに制限することで、メモリ使用量を抑える
                        # 今の所タブは1つしか開かないので、1つで十分
                        '--renderer-process-limit=1',
                        # 一時フォルダに作成されるプロファイルに保存するディスクキャッシュ領域を可能な限り小さくする
                        '--disk-cache-size=1048576',
                        '--media-cache-size=1048576',
                        # Chrome に実装されている各機能のうち、ヘッドレス用途では不要なものを無効化する
                        '--disable-client-side-phishing-detection',
                        '--disable-component-extensions-with-background-pages',
                        '--disable-domain-reliability',
                        '--disable-default-apps',
                        '--disable-extensions',
                        '--disable-notifications',
                        '--disable-print-preview',
                        '--disable-speech-api',
                        '--disable-sync',
                        '--disable-translate',
                    ]
                )
            except FileNotFoundError as ex:
                logging.error(f'{self.log_prefix} Chrome or Brave is not installed on this machine:', exc_info=ex)
                raise BrowserBinaryNotFoundError('ヘッドレスブラウザの起動に必要な Chrome または Brave が KonomiTV サーバーにインストールされていません。') from ex
            except Exception as ex:
                if 'Failed to connect to browser' in str(ex):
                    logging.error(f'{self.log_prefix} Browser connection failed. Please check if Chrome or Brave is installed:', exc_info=ex)
                    raise BrowserConnectionFailedError('ヘッドレスブラウザとの接続に失敗しました。Chrome または Brave が KonomiTV サーバーにインストールされているかどうかを確認してください。') from ex
                else:
                    logging.error(f'{self.log_prefix} Error starting browser:', exc_info=ex)
                    raise ex
            logging.info(f'{self.log_prefix} Browser started.')

            # まず空のタブを開く
            self._page = await self._browser.get('about:blank')
            logging.debug(f'{self.log_prefix} Blank page opened.')

            # 物理ウィンドウサイズも設定する (非ヘッドレスモードでのデバッグ時に正しいサイズで表示されるように)
            try:
                # get_window_for_target() は (WindowID, Bounds) のタプルを返す
                window_id, _ = await self._page.send(cdp.browser.get_window_for_target())
                await self._page.send(cdp.browser.set_window_bounds(
                    window_id=window_id,
                    bounds=cdp.browser.Bounds(width=1920, height=1080),
                ))
            except Exception as ex:
                # ヘッドレスモードではウィンドウサイズ操作が失敗する場合があるが、
                # set_device_metrics_override で CSS ビューポートは確保されているので無視して問題ない
                logging.debug(f'{self.log_prefix} Failed to set window bounds (expected in headless mode):', exc_info=ex)

            # DB から復号した cookies.txt の内容をパースし、ヘッドレスブラウザの Cookie に設定
            cookies_txt_content = self.twitter_account.decryptAccessTokenSecret()
            if cookies_txt_content:
                cookie_params = self.parseNetscapeCookieFile(cookies_txt_content)
                logging.debug(f'{self.log_prefix} Found {len(cookie_params)} cookies in cookies.txt.')
                # 読み込んだ CookieParam のリストを CookieJar に一括で設定
                try:
                    await self._browser.cookies.set_all(cookie_params)
                    logging.info(f'{self.log_prefix} Successfully set {len(cookie_params)} cookies.')
                except Exception as ex:
                    logging.error(f'{self.log_prefix} Error setting cookies:', exc_info=ex)
            else:
                logging.warning(f'{self.log_prefix} cookies.txt content is empty, skipping Cookie loading.')

            # Debugger を有効化
            await self._page.send(cdp.debugger.enable())

            # zendriver_setup.js の内容を読み込む
            setup_js_path = anyio.Path(STATIC_DIR / 'zendriver_setup.js')
            setup_js_code = await setup_js_path.read_text(encoding='utf-8')

            # Debugger.paused イベントをリッスン
            async def on_paused(event: cdp.debugger.Paused) -> None:
                logging.debug(f'{self.log_prefix} Pause event fired.')
                assert self._page is not None
                page = self._page
                try:
                    # ブレークポイント停止中に zendriver_setup.js のコードをブラウザタブ側に設置する
                    ## await_promise は指定しない（デフォルトは False）ので、スクリプトは設置されるが待機しない
                    ## その後、ブレークポイントから実行を再開すると、設置されたスクリプトが実行される
                    _, exception = await page.send(
                        cdp.runtime.evaluate(
                            expression=setup_js_code,
                            return_by_value=True,
                        )
                    )
                    logging.debug(f'{self.log_prefix} zendriver_setup.js executed.')
                    if exception is not None:
                        # 実行中になんらかの例外が発生した場合
                        setup_complete_future.set_exception(
                            Exception(f'Failed to execute zendriver_setup.js: {exception}')
                        )
                except Exception as ex:
                    setup_complete_future.set_exception(ex)
                finally:
                    # ブレークポイントから実行を再開
                    await page.send(cdp.debugger.resume())
                    try:
                        # 再開後に少し待つ (でないと window.__invokeGraphQLAPISetupPromise 自体がまだセットされていない可能性がある)
                        await asyncio.sleep(1)
                        logging.info(f'{self.log_prefix} Waiting for zendriver_setup.js to be resolved...')
                        # 再開後、window.__invokeGraphQLAPISetupPromise の Promise が解決されるまで待つ
                        result, exception = await page.send(
                            cdp.runtime.evaluate(
                                expression='window.__invokeGraphQLAPISetupPromise',
                                await_promise=True,
                                return_by_value=True,
                            )
                        )
                        logging.debug(f'{self.log_prefix} zendriver_setup.js evaluated.')
                        if exception is not None:
                            setup_complete_future.set_exception(
                                Exception(f'Failed to wait for setup promise: {exception}')
                            )
                        else:
                            # result.value が厳密に True であることを確認（undefined の可能性を排除）
                            if result.value is True:
                                logging.debug(f'{self.log_prefix} zendriver_setup.js resolved.')
                                setup_complete_future.set_result(True)
                            else:
                                setup_complete_future.set_exception(
                                    Exception(f'Setup promise did not return true. Got: {result.value}')
                                )
                    except Exception as ex:
                        setup_complete_future.set_exception(ex)

            self._page.add_handler(cdp.debugger.Paused, on_paused)

            # x.com の main.js の1行目にブレークポイントを設定
            ## ブレークポイントが発火すると on_paused ハンドラーが呼ばれ、zendriver_setup.js が実行される
            ## 正規表現はパスが main.<hash>.js 形式のファイルのみにマッチするように厳密化している
            breakpoint_id, _ = await self._page.send(
                cdp.debugger.set_breakpoint_by_url(
                    line_number=0,  # 0-based なので 1行目は 0
                    url_regex=r'^.*?main\.[a-fA-F0-9]+\.js$',  # main.<hash>.js を厳密にマッチさせる正規表現
                )
            )
            logging.debug(f'{self.log_prefix} Breakpoint set. id: {breakpoint_id}')

            # x.com に移動
            ## x.com/home だと万が一 Cookie セッションが revoke されている場合にログインモーダルが表示されて
            ## セットアップが解決できないっぽいので、ログイン前の画面がそのまま出てくる x.com/ 直下である必要がある
            self._page = await self._browser.get('https://x.com/')
            await self._page.activate()

            # zendriver_setup.js に記述したセットアップ処理が完了するまで待つ
            try:
                await asyncio.wait_for(setup_complete_future, timeout=15.0)
                logging.info(f'{self.log_prefix} Setup completed.')
                # セットアップ完了後、もうブレークポイントを打つ必要はないのでデバッガを無効化
                try:
                    await self._page.send(cdp.debugger.disable())
                except Exception as ex:
                    logging.error(f'{self.log_prefix} Error disabling debugger:', exc_info=ex)
                self.is_setup_complete = True
            except TimeoutError as ex:
                logging.error(f'{self.log_prefix} Timeout: Breakpoint was not hit or setup did not complete within 15 seconds.')
                self.is_setup_complete = False
                raise ex
            except Exception as ex:
                logging.error(f'{self.log_prefix} Error during setup:', exc_info=ex)
                self.is_setup_complete = False
                raise ex

    async def invokeGraphQLAPI(
        self,
        endpoint_name: str,
        variables: dict[str, Any],
        additional_flags: dict[str, Any] | None = None,
    ) -> TwitterBrowserGraphQLAPIResult:
        """
        ヘッドレスブラウザ越しに、Twitter Web App が持つ内部 GraphQL API クライアントに対して HTTP リクエストの実行を要求する
        エラー処理は行わず、生のレスポンスデータを返す（エラー処理は TwitterGraphQLAPI 側で行う）

        Args:
            endpoint_name (str): GraphQL API のエンドポイント名 (例: 'CreateTweet')
            variables (dict[str, Any]): GraphQL API へのリクエストパラメータ (ペイロードのうち "variables" の部分)
            additional_flags (dict[str, Any] | None): 追加のフラグ（オプション）

        Returns:
            TwitterBrowserGraphQLAPIResult: 生のレスポンスデータ
        """

        # 通常、ヘッドレスブラウザが起動していない時にこのメソッドが呼ばれることはない（呼ばれた場合は何かがバグっている）
        if self._browser is None or self._page is None:
            raise RuntimeError('Browser or page is not initialized.')

        # JavaScript コードを構築（JSON を文字列化して渡す）
        # エラー処理は JavaScript 側で完結し、シリアライズ可能なデータを返す
        additional_flags_json = (
            json.dumps(additional_flags, ensure_ascii=False) if additional_flags is not None else 'null'
        )
        js_code = f"""
        (async () => {{
            const requestPayload = {json.dumps(variables, ensure_ascii=False)};
            const additionalFlags = {additional_flags_json};
            const result = await window.__invokeGraphQLAPI('{endpoint_name}', requestPayload, additionalFlags);
            console.log('window.__invokeGraphQLAPI() result:', result);
            return result;
        }})()
        """

        # Twitter GraphQL API に HTTP リクエストを送信する
        result, exception = await self._page.send(
            cdp.runtime.evaluate(
                expression=js_code,
                await_promise=True,
                return_by_value=True,
            )
        )

        # 例外が発生した場合はそのまま例外を投げる
        if exception is not None:
            raise RuntimeError(f'Failed to execute JavaScript: {exception}')

        # 結果が None の場合は例外を投げる
        if result.value is None:
            raise RuntimeError('Response is None.')

        # JavaScript 側から返された結果を取得
        result_value = result.value
        if not isinstance(result_value, dict):
            raise RuntimeError(f'Response is not a dict. Got: {type(result_value)}')

        return TwitterBrowserGraphQLAPIResult(
            parsed_response=result_value.get('parsedResponse'),
            status_code=result_value.get('statusCode'),
            response_text=result_value.get('responseText'),
            headers=result_value.get('headers'),
            request_error=result_value.get('requestError'),
        )

    async def postTweetViaComposeUI(
        self,
        tweet_text: str,
        images: list[UploadFile],
    ) -> PostTweetViaComposeUIResult:
        """
        Twitter Web App の compose UI を DOM 操作で自動化し、ツイートを送信する
        "n" キーのショートカットで compose モーダルを開き、テキスト入力・画像添付・送信ボタンクリックを行う
        読み取り系 API と異なり、Web App の正規 UI 経路を通すため user_flow.json の scribe イベントが自然に発火する
        画像アップロードの完了と CreateTweet のレスポンスは CDP Network ドメインで監視する

        Args:
            tweet_text (str): ツイートの本文
            images (list[UploadFile]): 添付する画像（無いときは空リスト）

        Returns:
            PostTweetViaComposeUIResult: ツイート送信結果
        """

        # ヘッドレスブラウザが起動していない場合はエラー
        if self._browser is None or self._page is None:
            raise RuntimeError('Browser or page is not initialized.')

        page = self._page

        # CDP Network 監視の状態管理
        ## CreateTweet のレスポンスと画像アップロードの完了を CDP Network ドメインで監視する
        ## XHR フックと異なり、ページの JavaScript グローバル状態を一切汚染しない
        create_tweet_future: asyncio.Future[TwitterBrowserGraphQLAPIResult] = asyncio.Future()
        # CreateTweet の request_id と HTTP ステータスコードを保持する辞書
        create_tweet_requests: dict[str, int] = {}
        expected_upload_count = len(images)
        upload_finalize_count = 0
        # 画像アップロード完了を通知するイベント (画像がない場合は None)
        upload_complete_event: asyncio.Event | None = asyncio.Event() if expected_upload_count > 0 else None
        # 画像アップロード失敗を通知するイベント (FINALIZE が 4xx/5xx を返した場合にセットされる)
        upload_failed_event: asyncio.Event | None = asyncio.Event() if expected_upload_count > 0 else None
        # ネットワーク監視が有効かどうかのフラグ
        ## CDP Network を disable した後もイベントハンドラは登録されたままなので、
        ## このフラグでイベントを無視するかどうかを制御する
        is_network_monitoring_active = False

        async def OnResponseReceived(event: cdp.network.ResponseReceived) -> None:
            """
            CDP Network.responseReceived イベントハンドラ
            CreateTweet の request_id と画像アップロード FINALIZE の完了を追跡する
            """

            nonlocal upload_finalize_count
            if is_network_monitoring_active is not True:
                return

            # CORS preflight (OPTIONS) リクエストは無視する
            # upload.x.com はクロスオリジンのため FINALIZE に対して preflight が発生し、
            # preflight の 200 レスポンスを誤って FINALIZE 完了としてカウントしてしまう問題を防ぐ
            if event.type_ is not None and event.type_ == cdp.network.ResourceType.PREFLIGHT:
                return
            url = event.response.url

            # CreateTweet のリクエストを追跡
            if 'CreateTweet' in url:
                create_tweet_requests[str(event.request_id)] = event.response.status

            # 画像アップロード FINALIZE の完了を追跡
            # HTTP ステータスが 2xx 以外の場合はアップロード失敗として扱い、カウントしない
            if upload_complete_event is not None and 'upload.x.com' in url and 'FINALIZE' in url:
                if 200 <= event.response.status < 300:
                    upload_finalize_count += 1
                    logging.debug(f'{self.log_prefix} Upload FINALIZE succeeded ({upload_finalize_count}/{expected_upload_count})')
                    if upload_finalize_count >= expected_upload_count and not upload_complete_event.is_set():
                        upload_complete_event.set()
                else:
                    logging.error(f'{self.log_prefix} Upload FINALIZE failed with HTTP {event.response.status}')
                    # FINALIZE 失敗を即座に通知し、60 秒のタイムアウトを待たずにエラーを返す
                    if upload_failed_event is not None and not upload_failed_event.is_set():
                        upload_failed_event.set()

        async def OnLoadingFinished(event: cdp.network.LoadingFinished) -> None:
            """
            CDP Network.loadingFinished イベントハンドラ
            CreateTweet のレスポンスボディを取得して Future に設定する
            """

            if is_network_monitoring_active is not True:
                return
            request_id_str = str(event.request_id)

            # CreateTweet のリクエスト以外は無視
            if request_id_str not in create_tweet_requests:
                return
            if create_tweet_future.done():
                return

            # レスポンスボディを取得して Future に設定する
            try:
                body, _ = await page.send(cdp.network.get_response_body(event.request_id))
                parsed_response = json.loads(body)
                create_tweet_future.set_result(TwitterBrowserGraphQLAPIResult(
                    status_code=create_tweet_requests[request_id_str],
                    parsed_response=parsed_response,
                    response_text=body,
                    headers=None,
                    request_error=None,
                ))
            except Exception as ex:
                if not create_tweet_future.done():
                    create_tweet_future.set_exception(ex)

        async def OnLoadingFailed(event: cdp.network.LoadingFailed) -> None:
            """
            CDP Network.loadingFailed イベントハンドラ
            CreateTweet のリクエストが通信断やブラウザ側中断で失敗した場合に即座に Future を解決する
            これがないと通信失敗時に 30 秒のタイムアウト待ちが発生してしまう
            """

            if is_network_monitoring_active is not True:
                return
            request_id_str = str(event.request_id)
            if request_id_str not in create_tweet_requests:
                return
            if create_tweet_future.done():
                return

            logging.error(f'{self.log_prefix} CreateTweet request failed: {event.error_text}')
            create_tweet_future.set_exception(
                RuntimeError(f'CreateTweet request failed: {event.error_text}')
            )

        # compose モーダルを閉じるためのヘルパー関数
        # エラー発生時のクリーンアップに使用する
        async def CloseComposeModal() -> None:
            """
            compose モーダルが開いている場合、Escape キーで閉じる
            テキストや画像が入力されている場合は「変更を破棄」ダイアログが表示されるため、
            破棄ボタンのクリックも試行する
            """

            try:
                # Escape キーを送信して compose モーダルを閉じる
                await page.send(cdp.input_.dispatch_key_event(
                    type_='keyDown',
                    key='Escape',
                    code='Escape',
                    windows_virtual_key_code=27,
                ))
                await asyncio.sleep(0.5)
                # 「変更を破棄」ダイアログが表示された場合、破棄ボタンをクリックする
                discard_result, _ = await page.send(cdp.runtime.evaluate(
                    expression='''
                    (() => {
                        const discardBtn = document.querySelector('[data-testid="confirmationSheetConfirm"]');
                        if (discardBtn) {
                            discardBtn.click();
                            return true;
                        }
                        return false;
                    })()
                    ''',
                    return_by_value=True,
                ))
                if discard_result and discard_result.value is True:
                    await asyncio.sleep(0.5)
            except Exception as ex:
                logging.warning(f'{self.log_prefix} Failed to close compose modal:', exc_info=ex)

        compose_submitted_at: float | None = None

        # エラー時の共通レスポンスを生成するヘルパー
        def MakeErrorResult(error_message: str) -> PostTweetViaComposeUIResult:
            return PostTweetViaComposeUIResult(
                is_success=False,
                error_message=error_message,
                graphql_api_result=None,
                compose_submitted_at=compose_submitted_at,
            )

        try:
            # ===========================================
            # Step 1: CDP Network 監視を有効化する
            # ===========================================
            logging.info(f'{self.log_prefix} Enabling CDP Network monitoring...')
            await page.send(cdp.network.enable())
            is_network_monitoring_active = True
            page.add_handler(cdp.network.ResponseReceived, OnResponseReceived)
            page.add_handler(cdp.network.LoadingFinished, OnLoadingFinished)
            page.add_handler(cdp.network.LoadingFailed, OnLoadingFailed)

            # ===========================================
            # Step 2: "n" キーのショートカットで compose モーダルを開く
            # ===========================================
            # "n" キーは Twitter Web App のキーボードショートカットで、compose ダイアログを開く
            # SideNav ボタンのクリックと異なり、ビューポートサイズに依存しない
            # モーダルが開くと URL が /compose/post に SPA 遷移する
            #
            # CDP Input.dispatchKeyEvent で "n" ショートカットを発火させるには以下の条件が必要:
            # 1. ページがアクティブ (bring_to_front) であること
            # 2. document.body にフォーカスが当たっていること (テキスト入力欄にフォーカスがあると "n" が入力される)
            # 3. keyDown イベントに text='n' を含めること
            #    text パラメータなしだと keydown DOM イベントのみが生成され、keypress イベントが発生しない
            #    Twitter のキーボードショートカットハンドラが keypress に依存している場合、ショートカットが発火しない
            logging.info(f'{self.log_prefix} Opening compose modal via "n" keyboard shortcut...')
            # ページをアクティブにし、フォーカスを document.body に設定する
            await page.send(cdp.page.bring_to_front())
            await page.send(cdp.runtime.evaluate(
                expression='document.body.focus()',
                return_by_value=True,
            ))
            await asyncio.sleep(0.1)
            # keyDown (text='n' を含めて keypress も生成させる) → keyUp の順に送信
            await page.send(cdp.input_.dispatch_key_event(
                type_='keyDown',
                key='n',
                code='KeyN',
                text='n',
                windows_virtual_key_code=78,
                native_virtual_key_code=78,
            ))
            await page.send(cdp.input_.dispatch_key_event(
                type_='keyUp',
                key='n',
                code='KeyN',
                windows_virtual_key_code=78,
                native_virtual_key_code=78,
            ))

            # ===========================================
            # Step 3: compose モーダルが開くのを待機する
            # ===========================================
            # /home のタイムライン上部にもインラインの tweetTextarea_0 が存在するため、
            # 単に tweetTextarea_0 の存在をチェックするだけではモーダルが開いたことを正しく判定できない
            # compose モーダルが開くと URL が /compose/post に SPA 遷移し、
            # モーダル内の tweetTextarea_0 は [role="dialog"] の子孫に配置される
            # そのため「URL が /compose/post に遷移 && [role="dialog"] 内に tweetTextarea_0 が存在」を条件にする
            logging.info(f'{self.log_prefix} Waiting for compose modal to open...')
            _, compose_modal_exception = await page.send(cdp.runtime.evaluate(
                expression='''
                new Promise((resolve, reject) => {
                    const timeout = setTimeout(() => reject(new Error('Timeout: compose modal not opened')), 10000);
                    const check = () => {
                        const isComposeUrl = location.pathname === '/compose/post';
                        const textarea = document.querySelector('[role="dialog"] [data-testid="tweetTextarea_0"]');
                        if (isComposeUrl && textarea) {
                            clearTimeout(timeout);
                            resolve(true);
                        } else {
                            requestAnimationFrame(check);
                        }
                    };
                    check();
                })
                ''',
                await_promise=True,
                return_by_value=True,
            ))

            if compose_modal_exception is not None:
                logging.error(f'{self.log_prefix} Compose modal not found: {compose_modal_exception}')
                await CloseComposeModal()
                return MakeErrorResult('compose モーダルが開きませんでした。')

            logging.debug(f'{self.log_prefix} Compose modal opened.')

            # ===========================================
            # Step 4: ClipboardEvent paste でテキストを入力する
            # ===========================================
            # Draft.js エディタに対しては ClipboardEvent paste が最も安定して動作する
            # document.execCommand('insertText') は React の DOM 管理と衝突して error_log.json にエラーが送信されてしまう
            # ClipboardEvent paste なら Draft.js の _onPaste ハンドラが正規経路でテキストを処理するため、
            # エラーが発生せず、interaction detector の totalPasteCount も自然にインクリメントされる
            if tweet_text:
                # compose モーダルが開いてから人間がテキストを入力し始めるまでの自然な遅延を模倣
                await asyncio.sleep(random.uniform(0.3, 0.7))
                logging.info(f'{self.log_prefix} Pasting tweet text ({len(tweet_text)} chars)...')
                paste_result, paste_exception = await page.send(cdp.runtime.evaluate(
                    expression=f'''
                    (() => {{
                        // モーダル内の tweetTextarea_0 を対象にする (インラインの compose ではなくモーダルのもの)
                        const textarea = document.querySelector('[role="dialog"] [data-testid="tweetTextarea_0"]');
                        if (!textarea) return false;
                        textarea.focus();
                        const dt = new DataTransfer();
                        dt.setData('text/plain', {json.dumps(tweet_text, ensure_ascii=False)});
                        const pasteEvent = new ClipboardEvent('paste', {{
                            bubbles: true,
                            cancelable: true,
                            clipboardData: dt,
                        }});
                        textarea.dispatchEvent(pasteEvent);
                        return true;
                    }})()
                    ''',
                    return_by_value=True,
                ))

                if paste_exception is not None or (paste_result and paste_result.value is not True):
                    logging.error(f'{self.log_prefix} Failed to paste tweet text: {paste_exception}')
                    await CloseComposeModal()
                    return MakeErrorResult('テキストの入力に失敗しました。')

                logging.debug(f'{self.log_prefix} Tweet text pasted.')

            # ===========================================
            # Step 5: 画像をアップロードする (画像がある場合)
            # ===========================================
            if len(images) > 0:
                # テキスト入力後から画像を添付するまでの自然な遅延を模倣
                await asyncio.sleep(random.uniform(0.7, 1.5))
                logging.info(f'{self.log_prefix} Uploading {len(images)} image(s) via fileInput...')

                # 全画像を Base64 エンコードして JSON 配列として JavaScript に渡す
                images_json_array: list[dict[str, str]] = []
                for image in images:
                    image_bytes = await image.read()
                    mime_type = image.content_type or 'image/jpeg'
                    filename = image.filename or 'capture.jpg'
                    image_base64 = base64.b64encode(image_bytes).decode('ascii')
                    images_json_array.append({
                        'base64': image_base64,
                        'mimeType': mime_type,
                        'fileName': filename,
                    })

                # DataTransfer API で File オブジェクトを生成し fileInput に設定する
                ## Twitter Web App の fileInput は multiple 属性を持つので一括追加できる
                upload_js = f'''
                (() => {{
                    const images = {json.dumps(images_json_array, ensure_ascii=False)};
                    const fileInput = document.querySelector('[role="dialog"] [data-testid="fileInput"]');
                    if (!fileInput) return 'fileInput not found';
                    const dt = new DataTransfer();
                    for (const img of images) {{
                        const binaryString = atob(img.base64);
                        const bytes = new Uint8Array(binaryString.length);
                        for (let i = 0; i < binaryString.length; i++) {{
                            bytes[i] = binaryString.charCodeAt(i);
                        }}
                        const file = new File([bytes], img.fileName, {{ type: img.mimeType }});
                        dt.items.add(file);
                    }}
                    fileInput.files = dt.files;
                    fileInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return true;
                }})()
                '''
                upload_result, upload_exception = await page.send(cdp.runtime.evaluate(
                    expression=upload_js,
                    return_by_value=True,
                ))

                if upload_exception is not None or (upload_result and upload_result.value is not True):
                    error_detail = upload_result.value if upload_result else str(upload_exception)
                    logging.error(f'{self.log_prefix} Failed to set images on fileInput: {error_detail}')
                    await CloseComposeModal()
                    return MakeErrorResult(f'画像の設定に失敗しました。({error_detail})')

                logging.debug(f'{self.log_prefix} Images set on fileInput.')

                # CDP Network 監視で全画像の FINALIZE レスポンスが返るまで待機する
                ## テキスト入力済みの場合、アップロード開始前にボタンが有効な瞬間が存在するため、
                ## tweetButton の有効/無効状態だけでは画像アップロード完了を正確に判定できない
                ## FINALIZE が失敗した場合 (4xx/5xx) は即座にエラーを返す
                logging.info(f'{self.log_prefix} Waiting for all image uploads to complete...')
                assert upload_complete_event is not None
                assert upload_failed_event is not None
                try:
                    # アップロード完了またはアップロード失敗のどちらかが発火するまで待機
                    upload_success_task = asyncio.create_task(upload_complete_event.wait())
                    upload_failure_task = asyncio.create_task(upload_failed_event.wait())
                    done, pending = await asyncio.wait(
                        [upload_success_task, upload_failure_task],
                        timeout=60.0,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    # 完了しなかったタスクをキャンセルして回収する
                    for pending_task in pending:
                        pending_task.cancel()
                        try:
                            await pending_task
                        except asyncio.CancelledError:
                            pass
                    if len(done) == 0:
                        # タイムアウト
                        logging.error(f'{self.log_prefix} Timeout waiting for image upload FINALIZE.')
                        await CloseComposeModal()
                        return MakeErrorResult('画像アップロードがタイムアウトしました。')
                    if upload_failed_event.is_set():
                        logging.error(f'{self.log_prefix} Image upload FINALIZE returned an error.')
                        await CloseComposeModal()
                        return MakeErrorResult('画像のアップロードに失敗しました。')
                except Exception as ex:
                    logging.error(f'{self.log_prefix} Error waiting for image uploads:', exc_info=ex)
                    await CloseComposeModal()
                    return MakeErrorResult(f'画像アップロードの待機中にエラーが発生しました。({ex})')

                logging.info(f'{self.log_prefix} All image uploads completed.')

            # ===========================================
            # Step 6: tweetButton が有効になるまで待機する
            # ===========================================
            # 画像アップロード完了後も tweetButton が有効になるまで少し時間がかかる場合がある
            # タイムラインのインライン compose UI ではなく、モーダル内の tweetButton を対象にする
            logging.info(f'{self.log_prefix} Waiting for tweetButton to become enabled...')
            _, button_ready_exception = await page.send(cdp.runtime.evaluate(
                expression='''
                new Promise((resolve, reject) => {
                    const timeout = setTimeout(() => reject(new Error('Timeout: tweetButton not enabled')), 30000);
                    const check = () => {
                        const btn = document.querySelector('[role="dialog"] [data-testid="tweetButton"]');
                        if (btn && btn.getAttribute('aria-disabled') !== 'true') {
                            clearTimeout(timeout);
                            resolve(true);
                        } else {
                            setTimeout(check, 300);
                        }
                    };
                    check();
                })
                ''',
                await_promise=True,
                return_by_value=True,
            ))

            if button_ready_exception is not None:
                logging.error(f'{self.log_prefix} tweetButton did not become enabled: {button_ready_exception}')
                await CloseComposeModal()
                return MakeErrorResult('ツイートボタンが有効になりませんでした。テキストや画像の入力に問題がある可能性があります。')

            logging.debug(f'{self.log_prefix} tweetButton is enabled.')

            # ===========================================
            # Step 7: tweetButton をクリックする
            # ===========================================
            # 画像アップロード完了後/テキスト入力後から送信ボタンを押すまでの自然な遅延を模倣
            await asyncio.sleep(random.uniform(0.1, 0.2))
            logging.info(f'{self.log_prefix} Clicking tweetButton...')
            click_result, click_exception = await page.send(cdp.runtime.evaluate(
                expression='''
                (() => {
                    const tweetBtn = document.querySelector('[role="dialog"] [data-testid="tweetButton"]');
                    if (tweetBtn) {
                        tweetBtn.click();
                        return true;
                    }
                    return false;
                })()
                ''',
                return_by_value=True,
            ))

            if click_exception is not None or (click_result and click_result.value is not True):
                logging.error(f'{self.log_prefix} Failed to click tweetButton: {click_exception}')
                await CloseComposeModal()
                return MakeErrorResult('ツイートボタンのクリックに失敗しました。')

            # ツイートボタンをクリックした時刻を記録し、最小送信間隔の基準に使う
            compose_submitted_at = time.time()

            # ===========================================
            # Step 8: CDP Network 監視で CreateTweet のレスポンスを待機する
            # ===========================================
            logging.info(f'{self.log_prefix} Waiting for CreateTweet response via CDP Network...')
            try:
                response_data = await asyncio.wait_for(create_tweet_future, timeout=30.0)
            except TimeoutError:
                logging.error(f'{self.log_prefix} Timeout waiting for CreateTweet response.')
                await CloseComposeModal()
                return MakeErrorResult('CreateTweet のレスポンスがタイムアウトしました。')
            except Exception as ex:
                logging.error(f'{self.log_prefix} Error waiting for CreateTweet response:', exc_info=ex)
                await CloseComposeModal()
                return MakeErrorResult(f'CreateTweet のレスポンスを取得できませんでした。({ex})')

            status_code = response_data.status_code
            logging.info(f'{self.log_prefix} CreateTweet response received. (HTTP {status_code})')

            return PostTweetViaComposeUIResult(
                is_success=True,
                error_message=None,
                graphql_api_result=response_data,
                compose_submitted_at=compose_submitted_at,
            )

        except Exception as ex:
            logging.error(f'{self.log_prefix} Unexpected error during compose UI posting:', exc_info=ex)
            # エラー発生時はモーダルを閉じてクリーンアップする
            await CloseComposeModal()
            return MakeErrorResult(f'ツイート送信中に予期しないエラーが発生しました。({ex})')

        finally:
            # CDP Network 監視を無効化し、登録したイベントハンドラを解除する
            ## ハンドラを解除しないと、同じ browser/tab を使い回す際に stale なクロージャが蓄積し、
            ## 以後の全ネットワークイベントで不要なコールバックが走ってしまう
            is_network_monitoring_active = False
            try:
                await page.send(cdp.network.disable())
            except Exception as ex:
                logging.warning(f'{self.log_prefix} Failed to disable CDP Network monitoring:', exc_info=ex)
            # 登録したイベントハンドラを個別に解除する
            try:
                page.remove_handlers(cdp.network.ResponseReceived, OnResponseReceived)
                page.remove_handlers(cdp.network.LoadingFinished, OnLoadingFinished)
                page.remove_handlers(cdp.network.LoadingFailed, OnLoadingFailed)
            except Exception as ex:
                logging.warning(f'{self.log_prefix} Failed to remove CDP Network handlers:', exc_info=ex)

    async def shutdown(self) -> None:
        """
        使われなくなったヘッドレスブラウザを安全にシャットダウンする
        シャットダウン中は setup() や shutdown() が同時に呼ばれないように、self.setup_lock を使用して排他制御する
        """

        # セットアップ・シャットダウン処理の排他制御
        ## シャットダウン中に setup が呼ばれると状態が競合するため、同じロックを使用する
        async with self._setup_lock:
            if self._browser is None:
                logging.warning(f'{self.log_prefix} Browser is not initialized, skipping shutdown.')
                return

            # セットアップ完了フラグをリセット（シャットダウン開始時点でセットアップ状態を無効化）
            ## これにより、シャットダウン中に setup が呼ばれた場合でも、シャットダウン完了後に再度セットアップが必要になる
            self.is_setup_complete = False

            # ヘッドレスブラウザを停止
            logging.info(f'{self.log_prefix} Waiting for browser to terminate...')
            try:
                await self._browser.stop()
                logging.info(f'{self.log_prefix} Browser terminated.')
            except Exception as ex:
                logging.error(f'{self.log_prefix} Error while terminating browser:', exc_info=ex)

            self._browser = None
            self._page = None

    async def saveTwitterCookiesToNetscapeFormat(self) -> str:
        """
        起動中のヘッドレスブラウザから x.com 関連の Cookie を取得し、Netscape フォーマットの文字列に変換して返す

        Returns:
            str: Netscape フォーマットの Cookie ファイルの内容
        """

        # 通常、ヘッドレスブラウザが起動していない時にこのメソッドが呼ばれることはない（呼ばれた場合は何かがバグっている）
        if self._browser is None:
            raise RuntimeError('Browser is not initialized.')

        # 全ての Cookie を取得
        all_cookies = await self._browser.cookies.get_all(requests_cookie_format=False)
        # requests_cookie_format=False なので cdp.network.Cookie のリストが返される
        # x.com に関連する Cookie をフィルタリング
        twitter_cookies: list[cdp.network.Cookie] = [
            c for c in all_cookies if isinstance(c, cdp.network.Cookie) and ('x.com' in c.domain)
        ]

        # Netscape フォーマットで文字列を構築
        lines: list[str] = []
        # Netscape フォーマットのヘッダーを追加
        lines.append('# Netscape HTTP Cookie File')
        lines.append('# https://curl.haxx.se/rfc/cookie_spec.html')
        lines.append('# This is a generated file! Do not edit.')
        lines.append('')

        if not twitter_cookies:
            logging.warning(f'{self.log_prefix} No Twitter-related cookies found, returning empty Netscape format.')
            return '\n'.join(lines)

        # 各 Cookie を Netscape フォーマットで追加
        for cookie in twitter_cookies:
            # domain がドットで始まる場合は flag を TRUE、そうでなければ FALSE
            flag = 'TRUE' if cookie.domain.startswith('.') else 'FALSE'
            # secure フラグを TRUE/FALSE に変換
            secure_str = 'TRUE' if cookie.secure else 'FALSE'
            # expires が None の場合は 0（セッション cookie）を設定
            expires_value = int(cookie.expires) if cookie.expires is not None else 0
            # Netscape フォーマット: domain, flag, path, secure, expiration, name, value
            netscape_line = (
                f'{cookie.domain}\t{flag}\t{cookie.path}\t{secure_str}\t{expires_value}\t{cookie.name}\t{cookie.value}'
            )
            lines.append(netscape_line)

        return '\n'.join(lines)

    @staticmethod
    def parseNetscapeCookieFile(cookies_content: str) -> list[cdp.network.CookieParam]:
        """
        Netscape フォーマットの Cookie 文字列をパースして CookieParam に変換する

        Args:
            cookies_content (str): Cookie ファイルの内容

        Returns:
            list[cdp.network.CookieParam]: CookieParam のリスト
        """

        cookie_params: list[cdp.network.CookieParam] = []
        for line in cookies_content.splitlines():
            line = line.strip()
            # コメント行や空行をスキップ
            if not line or line.startswith('#'):
                continue
            # Netscape フォーマット: domain, flag, path, secure, expiration, name, value
            parts = line.split('\t')
            if len(parts) < 7:
                continue
            domain = parts[0]
            # flag (parts[1]) は使用しない
            path = parts[2]
            secure = parts[3] == 'TRUE'
            expires_str = parts[4]
            expires = int(expires_str) if expires_str and expires_str != '0' else None
            name = parts[5]
            value = parts[6]

            # expires が None の場合は設定しない（セッション Cookie として扱われる）
            expires_param = None
            if expires is not None:
                # TimeSinceEpoch は秒単位の Unix timestamp
                expires_param = cdp.network.TimeSinceEpoch(expires)
            # domain から URL を構築（ドットで始まる場合は除去）
            domain_for_url = domain.lstrip('.')
            # secure フラグに応じてプロトコルを選択
            protocol = 'https' if secure else 'http'
            url = f'{protocol}://{domain_for_url}'
            cookie_params.append(
                cdp.network.CookieParam(
                    name=name,
                    value=value,
                    url=url,
                    domain=domain,
                    path=path,
                    secure=secure,
                    expires=expires_param,
                )
            )
        return cookie_params
