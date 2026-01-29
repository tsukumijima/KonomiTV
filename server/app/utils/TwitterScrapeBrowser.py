import asyncio
import json
from typing import Any

import anyio
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
            setup_complete_future = asyncio.get_running_loop().create_future()

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
    ) -> dict[str, Any]:
        """
        ヘッドレスブラウザ越しに、Twitter Web App が持つ内部 GraphQL API クライアントに対して HTTP リクエストの実行を要求する
        エラー処理は行わず、生のレスポンスデータを返す（エラー処理は TwitterGraphQLAPI 側で行う）

        Args:
            endpoint_name (str): GraphQL API のエンドポイント名 (例: 'CreateTweet')
            variables (dict[str, Any]): GraphQL API へのリクエストパラメータ (ペイロードのうち "variables" の部分)
            additional_flags (dict[str, Any] | None): 追加のフラグ（オプション）

        Returns:
            dict[str, Any]: 生のレスポンスデータ（parsedResponse, statusCode, responseText, headers, requestError を含む）
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

        # API レスポンスを取得
        parsed_response = result_value.get('parsedResponse')
        status_code = result_value.get('statusCode')
        response_text = result_value.get('responseText')
        headers = result_value.get('headers')
        request_error = result_value.get('requestError')

        # 生のレスポンスデータを返す（エラー処理は TwitterGraphQLAPI 側で行う）
        return {
            'parsedResponse': parsed_response,
            'statusCode': status_code,
            'responseText': response_text,
            'headers': headers,
            'requestError': request_error,
        }

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
