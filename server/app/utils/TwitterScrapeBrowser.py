import asyncio
import atexit
import base64
import json
import random
import re
import time
from datetime import datetime
from typing import Any, ClassVar, cast

import anyio
import psutil
from fastapi import UploadFile
from pydantic import BaseModel
from typing_extensions import TypedDict
from zendriver import Browser, Tab, cdp

from app import logging, schemas
from app.constants import (
    JST,
    STATIC_DIR,
    TWITTER_DEBUG_SCREENSHOTS_DIR,
    TWITTER_DEBUG_SCREENSHOTS_RETENTION_DAYS,
)
from app.models.TwitterAccount import TwitterAccount


class BrowserBinaryNotFoundError(RuntimeError):
    """
    Chrome / Brave の実行ファイルが検出できず、Zendriver がブラウザを起動できない場合に送出される例外
    """

class BrowserConnectionFailedError(RuntimeError):
    """
    Chrome / Brave はおそらく起動できたが、ブラウザインスタンスへの接続に失敗した場合に送出される例外
    """

class BrowserSetupTimeoutError(RuntimeError):
    """
    ヘッドレスブラウザは起動できたが、x.com のセットアップ処理がタイムアウトした場合に送出される例外
    Cookie セッションの有効期限切れやアカウントのロック・一時制限により、通常の x.com ページではなく
    captcha 画面やログイン画面が表示された結果、main.js のブレークポイントが hit せずにタイムアウトするケースが該当する
    """

class TwitterBrowserGraphQLAPIResult(BaseModel):
    """ヘッドレスブラウザ経由の GraphQL API レスポンスの生データ。"""

    parsed_response: Any | None = None
    status_code: int | None = None
    response_text: str | None = None
    headers: dict[str, Any] | None = None
    request_error: str | None = None

class PostTweetViaComposeUIResult(BaseModel):
    """ツイート送信モーダルの自動操作によるツイート送信の結果。"""

    is_success: bool
    error_message: str | None = None
    compose_submitted_at: float | None = None
    graphql_api_result: TwitterBrowserGraphQLAPIResult | None = None


class TwitterScrapeBrowser:
    """
    Twitter のヘッドレスブラウザ操作を隠蔽するクラス
    ヘッドレスブラウザのセットアップ処理や、ブラウザインスタンス自身の低レベル操作を隠蔽する
    """

    # Python プロセス終了時に取り残しなくブラウザを回収するため、起動したブラウザ親プロセスを保持する
    _active_browser_processes: ClassVar[dict[int, psutil.Process]] = {}
    # Chrome の User-Agent 簡略化後も文字列に残る OS 表記
    ## 細かい OS バージョンは UA-CH 側に移され、User-Agent には丸められた表記だけが残る
    _UA_OS_INFO_BY_PLATFORM: ClassVar[dict[str, str]] = {
        'macOS': 'Macintosh; Intel Mac OS X 10_15_7',
        'Windows': 'Windows NT 10.0; Win64; x64',
        'Linux': 'X11; Linux x86_64',
    }
    # navigator.platform が空だった場合に使う OS ごとの代表値
    _NAVIGATOR_PLATFORM_BY_PLATFORM: ClassVar[dict[str, str]] = {
        'macOS': 'MacIntel',
        'Windows': 'Win32',
        'Linux': 'Linux x86_64',
    }

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
        # 起動中ブラウザの親プロセス
        ## Browser.stop() が失敗した場合でもプロセスツリーを直接 terminate / kill できるように保持する
        self._browser_process: psutil.Process | None = None

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

    async def _detectCurrentUserAgent(self, page: Tab) -> str | None:
        """
        現在のヘッドレスブラウザが JavaScript 上で公開している User-Agent を取得する

        Args:
            page (Tab): 情報取得に使うタブ

        Returns:
            str | None: 現在の User-Agent
        """

        # ZenDriver は headless=True で起動した際に User-Agent 文字列から "HeadlessChrome" の "Headless" を除去するため、
        # Browser.getVersion() ではなく、ページ上で実際に見える navigator.userAgent を読む
        result, exception = await page.send(cdp.runtime.evaluate(
            expression='navigator.userAgent',
            return_by_value=True,
        ))
        # User-Agent が取れない場合は OS 表現を差し替えられないため、補正せずに続行する
        if exception is not None:
            logging.warning(f'{self.log_prefix} Failed to detect current User-Agent. exception: {exception}')
            return None
        if not isinstance(result.value, str) or result.value == '':
            logging.warning(f'{self.log_prefix} Current User-Agent result is invalid. value: {result.value}')
            return None
        return result.value

    def _buildSpoofedUserAgent(self, server_user_agent: str, cookie_platform: str) -> str | None:
        """
        ヘッドレスブラウザの User-Agent 文字列から、OS 部分だけを Cookie 採取元ブラウザの OS 表現へ差し替える

        Args:
            server_user_agent (str): ヘッドレスブラウザの現在の User-Agent 文字列
            cookie_platform (str): Cookie 採取元ブラウザの platform

        Returns:
            str | None: 差し替え後の User-Agent 文字列
        """

        spoofed_os_info = self._UA_OS_INFO_BY_PLATFORM.get(cookie_platform)
        if spoofed_os_info is None:
            return None

        # Chrome のバージョンは現在の環境に合わせ、OS 表現だけを Cookie 採取元に合わせる
        spoofed_user_agent = re.sub(
            r'^(Mozilla/5\.0 \()[^)]+(\))',
            rf'\g<1>{spoofed_os_info}\g<2>',
            server_user_agent,
            count=1,
        )
        # 想定外の UA 形式では置換できないため、壊れた文字列を作らず補正をやめる
        ## 同じ OS の場合は置換前後が同じ文字列になるため、正規表現に一致したかだけを見る
        if re.match(r'^(Mozilla/5\.0 \()[^)]+(\))', server_user_agent) is None:
            return None
        return spoofed_user_agent

    def _buildAcceptLanguage(self, accept_languages: Any) -> str | None:
        """
        保存済み Accept-Language 言語タグ配列を CDP に渡す文字列へ変換する

        Args:
            accept_languages (Any): HTTP Accept-Language から q 値を除去した言語タグ配列

        Returns:
            str | None: CDP に渡す Accept-Language
        """

        # CDP には q 値を除いた言語タグだけを渡し、実際の重み付けは Chrome に任せる
        ## `en;q=0.9` みたいな q 値付き文字列をそのまま渡すと、Chrome 側で重みが二重に付く
        if not isinstance(accept_languages, list):
            return None

        # 空文字や非文字列は保存値として不自然なので、CDP に渡す前に除外する
        normalized_languages = [
            language.strip()
            for language in accept_languages
            if isinstance(language, str) and language.strip() != ''
        ]
        # 有効な言語がない場合は空のヘッダーを作らず、Chrome の既定値に任せる
        if len(normalized_languages) == 0:
            return None

        return ','.join(normalized_languages)

    async def _detectOverriddenNavigatorInfo(self, page: Tab) -> dict[str, Any] | None:
        """
        UA / UA-CH override 適用後に navigator から見える値を取得する

        Args:
            page (Tab): 情報取得に使うタブ

        Returns:
            dict[str, Any] | None: override 後の navigator 情報
        """

        # navigator / Intl から見える値をログに残し、User-Agent 補正後の状態を確認する
        result, exception = await page.send(cdp.runtime.evaluate(
            expression='''
            (async () => {
                const userAgentData = navigator.userAgentData;
                let highEntropyValues = null;
                if (typeof userAgentData?.getHighEntropyValues === 'function') {
                    highEntropyValues = await userAgentData.getHighEntropyValues([
                        'architecture',
                        'bitness',
                        'brands',
                        'fullVersionList',
                        'mobile',
                        'model',
                        'platform',
                        'platformVersion',
                        'uaFullVersion',
                        'wow64',
                    ]);
                } else if (userAgentData) {
                    highEntropyValues = {
                        brands: userAgentData.brands ?? [],
                        mobile: userAgentData.mobile ?? false,
                        platform: userAgentData.platform ?? '',
                    };
                }
                return {
                    userAgent: navigator.userAgent,
                    platform: navigator.platform,
                    language: navigator.language,
                    languages: navigator.languages,
                    locale: Intl.DateTimeFormat().resolvedOptions().locale,
                    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                    userAgentData: highEntropyValues,
                };
            })()
            ''',
            await_promise=True,
            return_by_value=True,
        ))
        # ログ用の取得に失敗しても補正処理は完了しているため、セットアップは続ける
        if exception is not None:
            logging.warning(f'{self.log_prefix} Failed to verify overridden navigator info. exception: {exception}')
            return None
        if not isinstance(result.value, dict):
            logging.warning(f'{self.log_prefix} Overridden navigator info result is invalid. value: {result.value}')
            return None
        return result.value

    def _logNetworkResponseDiagnostics(
        self,
        reason: str,
        status_code: int | None,
        headers: dict[str, Any] | None,
        response_text: str | None,
    ) -> None:
        """
        CDP Network で取得したレスポンスの診断情報をログに出力する

        Args:
            reason (str): 診断ログを出力する理由
            status_code (int | None): HTTP ステータスコード
            headers (dict[str, Any] | None): HTTP レスポンスヘッダー
            response_text (str | None): HTTP レスポンス本文
        """

        # JSON パース失敗時は本文だけでは原因を追いづらいため、ステータスコードと HTTP レスポンスヘッダーも出力する
        logging.error(f'{self.log_prefix} {reason}. status_code: {status_code}')
        logging.error(f'{self.log_prefix} Response headers: {json.dumps(headers or {}, ensure_ascii=False)}')

        # レスポンス本文は巨大化しやすいため、原因確認に必要な先頭部分だけを残す
        if response_text is None:
            logging.error(f'{self.log_prefix} Response text: <None>')
            return
        response_text_limit = 4000
        if len(response_text) > response_text_limit:
            logging.error(
                f'{self.log_prefix} Response text: '
                f'{response_text[:response_text_limit]}... (truncated, total_length: {len(response_text)})',
            )
        else:
            logging.error(f'{self.log_prefix} Response text: {response_text}')

    async def _applyBrowserEnvironmentOverride(self, page: Tab) -> None:
        """
        Cookie 採取元ブラウザの OS / 言語情報に基づいて UA / UA-CH を補正する

        Args:
            page (Tab): override を適用するタブ
        """

        # 既存アカウントや採取失敗時は保存値がないため、ヘッドレスブラウザの環境でそのまま起動する
        raw_cookie_browser_info: Any = self.twitter_account.cookie_browser_info
        if not isinstance(raw_cookie_browser_info, dict):
            logging.info(f'{self.log_prefix} No cookie browser info available, skipping UA override.')
            return

        cookie_browser_info = cast(schemas.BrowserEnvironmentInfo, raw_cookie_browser_info)
        typed_http_headers = cookie_browser_info['http_headers']
        typed_user_agent_data = cookie_browser_info['user_agent_data']

        # UA 文字列を安全に作れる OS だけを補正対象にする
        cookie_platform = typed_user_agent_data['platform']
        if cookie_platform not in self._UA_OS_INFO_BY_PLATFORM:
            logging.info(f'{self.log_prefix} Cookie browser platform is unsupported, skipping UA override. platform: {cookie_platform}')
            return

        try:
            # Chrome バージョンは実行中のブラウザに合わせるため、現在の User-Agent 文字列を基準にする
            server_user_agent = await self._detectCurrentUserAgent(page)
            if server_user_agent is None:
                return

            # User-Agent は OS 部分だけを差し替え、ブラウザ名と Chrome バージョンは維持する
            spoofed_user_agent = self._buildSpoofedUserAgent(server_user_agent, cookie_platform)
            if spoofed_user_agent is None:
                logging.warning(f'{self.log_prefix} Failed to build spoofed User-Agent, skipping UA override.')
                return

            # UA-CH には Cookie 採取元の OS 情報を入れ、ブランド情報と詳細版は Chrome 側に任せる
            ## headless=True で欠けやすい OS 系の値だけを補い、実行中の Chrome と違うバージョンは名乗らない
            cookie_mobile = typed_user_agent_data['mobile']
            is_cookie_mobile = cookie_mobile
            cookie_platform_version = typed_user_agent_data['platform_version']
            cookie_architecture = typed_user_agent_data['architecture']
            cookie_model = typed_user_agent_data['model']
            cookie_bitness = typed_user_agent_data['bitness']
            cookie_wow64 = typed_user_agent_data['wow64']
            user_agent_metadata = cdp.emulation.UserAgentMetadata(
                platform=cookie_platform,
                platform_version=cookie_platform_version,
                architecture=cookie_architecture,
                model=cookie_model,
                mobile=is_cookie_mobile,
                bitness=cookie_bitness,
                wow64=cookie_wow64,
            )

            # 言語情報は Cookie 認証時の HTTP ヘッダーから作った配列を使う
            accept_language = self._buildAcceptLanguage(typed_http_headers['accept_languages'])
            # navigator.platform は UA-CH と別枠なので、空の場合だけ OS ごとの代表値を使う
            cookie_navigator_platform = cookie_browser_info['navigator_platform']
            navigator_platform = (
                cookie_navigator_platform
                if cookie_navigator_platform != ''
                else self._NAVIGATOR_PLATFORM_BY_PLATFORM[cookie_platform]
            )
            # ロケールとタイムゾーンは JavaScript から見えるため、Cookie 採取元に合わせる
            locale = cookie_browser_info['locale']
            timezone = cookie_browser_info['timezone']

            # CDP に登録する値と、リクエスト上で見える想定の値をログに残す
            user_agent_metadata_json = user_agent_metadata.to_json()
            expected_headers: dict[str, str] = {
                'user-agent': spoofed_user_agent,
                'sec-ch-ua-platform': f'"{user_agent_metadata_json["platform"]}"',
                'sec-ch-ua-platform-version': f'"{user_agent_metadata_json["platformVersion"]}"',
                'sec-ch-ua-arch': f'"{user_agent_metadata_json["architecture"]}"',
                'sec-ch-ua-mobile': '?1' if user_agent_metadata_json['mobile'] is True else '?0',
                'sec-ch-ua-model': f'"{user_agent_metadata_json["model"]}"',
            }
            # Accept-Language が空の場合は CDP に渡さないため、ログにも出さない
            if accept_language is not None:
                expected_headers['accept-language'] = accept_language
            # bitness がない場合は、空の UA-CH ヘッダーを作らない
            if 'bitness' in user_agent_metadata_json:
                expected_headers['sec-ch-ua-bitness'] = f'"{user_agent_metadata_json["bitness"]}"'

            # CDP に渡す値をそのままログ化し、検証時に同じ値を見られるようにする
            cdp_payload = {
                'userAgent': spoofed_user_agent,
                'acceptLanguage': accept_language,
                'platform': navigator_platform,
                'userAgentMetadata': user_agent_metadata_json,
                'locale': locale,
                'timezone': timezone,
            }
            # x.com への初回アクセス前に補正し、最初の GraphQL リクエストから反映させる
            logging.info(
                f'{self.log_prefix} Applying UA override. '
                f'cookie_platform: {cookie_platform}, navigator_platform: {navigator_platform}',
            )
            logging.info(
                f'{self.log_prefix} UA override CDP payload: '
                f'{json.dumps(cdp_payload, ensure_ascii=False)}',
            )
            logging.info(
                f'{self.log_prefix} Expected UA request headers after override: '
                f'{json.dumps(expected_headers, ensure_ascii=False)}',
            )
            await page.send(cdp.emulation.set_user_agent_override(
                user_agent=spoofed_user_agent,
                accept_language=accept_language,
                platform=navigator_platform,
                user_agent_metadata=user_agent_metadata,
            ))
            # Intl 系の API は User-Agent とは別の CDP コマンドで反映する
            ## 空文字は既定値へ戻す指定になるため、値がある場合だけ上書きする
            if locale != '':
                await page.send(cdp.emulation.set_locale_override(locale=locale))
            if timezone != '':
                await page.send(cdp.emulation.set_timezone_override(timezone_id=timezone))

            # about:blank では UA-CH を確認しづらいため、navigator の検証ログは x.com への遷移後に出す
            logging.info(f'{self.log_prefix} UA override applied successfully.')
        except Exception as ex:
            # 補正に失敗しても Twitter 機能は止めず、ヘッドレスブラウザの環境で続行する
            logging.warning(f'{self.log_prefix} Failed to apply UA override, continuing with server Chrome defaults:', exc_info=ex)

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

            # Zendriver はブラウザ親プロセスの PID を public API として公開していないため、
            # 終了保証のためにここだけ内部属性を参照する
            browser_process_id = self._browser._process_pid  # pyright: ignore[reportPrivateUsage]
            # _process_pid が未設定でも Popen は保持されている場合があるため、その場合は pid を直接参照する
            if browser_process_id is None and self._browser._process is not None:  # pyright: ignore[reportPrivateUsage]
                browser_process_id = self._browser._process.pid  # pyright: ignore[reportPrivateUsage]
            self._browser_process = None

            # 後続の shutdown() / atexit から同じブラウザ親プロセスを安全に回収できるよう、psutil.Process を保持する
            if browser_process_id is not None:
                try:
                    self._browser_process = psutil.Process(browser_process_id)
                    self._active_browser_processes[browser_process_id] = self._browser_process
                except psutil.NoSuchProcess:
                    self._browser_process = None
                except psutil.Error as ex:
                    logging.warning(f'{self.log_prefix} Failed to capture browser process metadata:', exc_info=ex)
                    self._browser_process = None

            logging.info(f'{self.log_prefix} Browser started.')

            # Browser.create() 成功後に例外が起きた場合でも、以降の処理で起動済みプロセスを取りこぼさないようにする
            try:
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

                # Cookie 採取時に保存したブラウザ情報を、x.com へ移動する前に Chrome へ渡す
                ## 最初の x.com リクエストから User-Agent / UA-CH / 言語設定を揃えるため、about:blank の時点で設定する
                await self._applyBrowserEnvironmentOverride(self._page)

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
                except TimeoutError:
                    logging.error(f'{self.log_prefix} Timeout: Breakpoint was not hit or setup did not complete within 15 seconds.')
                    self.is_setup_complete = False
                    raise BrowserSetupTimeoutError(
                        'ヘッドレスブラウザのセットアップがタイムアウトしました。'
                        'Cookie セッションの有効期限が切れたか、アカウントがロック・一時制限されている可能性があります。'
                        'ブラウザで Twitter (x.com) にアクセスして状態を確認してください。'
                    )
                except Exception as ex:
                    logging.error(f'{self.log_prefix} Error during setup:', exc_info=ex)
                    self.is_setup_complete = False
                    raise ex

                # x.com のページ内 JavaScript から見える navigator / Intl の値をログに残す
                ## about:blank では基本的に UA-CH が取れないため、実ページへ遷移した後に確認しなければならない
                overridden_navigator_info = await self._detectOverriddenNavigatorInfo(self._page)
                if overridden_navigator_info is not None:
                    logging.info(
                        f'{self.log_prefix} Navigator info after UA override on x.com: '
                        f'{json.dumps(overridden_navigator_info, ensure_ascii=False)}',
                    )

                # ===========================================
                # タイムラインタブを「フォロー中」に切り替える
                # ===========================================
                # デフォルトでは「おすすめ」タブが選択されているが、KonomiTV では HomeLatestTimeline API
                # (フォロー中の最新ツイート) を使用するため、ページの状態を合わせる必要がある
                ## タブを切り替えることで以下のメリットがある:
                ## - Web App が自然に HomeLatestTimeline API を呼び、正しい scribe イベントが発火する
                ## - 以降の invokeGraphQLAPI による HomeLatestTimeline 呼び出しがタブ状態と矛盾しない
                ## - ツイート送信時も「最新 TL を見ながらツイート」という自然なフローになる
                ## enableRanking=false の強制は zendriver_setup.js 側の XHR フックで行うため、
                ## ドロップダウン UI の操作は不要 (Control Panel for Twitter と同じ手法)
                logging.info(f'{self.log_prefix} Switching to "Following" timeline tab...')
                try:
                    _, tab_switch_exception = await self._page.send(cdp.runtime.evaluate(
                        expression='''
                        new Promise((resolve, reject) => {
                            const timeout = setTimeout(() => reject(new Error('Timeout: Following tab not found')), 10000);
                            const check = () => {
                                // タイムラインタブリストの2番目のタブ (「フォロー中」) を探す
                                const tabList = document.querySelector('nav div[role="tablist"]');
                                if (!tabList) {
                                    requestAnimationFrame(check);
                                    return;
                                }
                                const followingTab = tabList.querySelector('div:nth-child(2) > [role="tab"]');
                                if (!followingTab) {
                                    requestAnimationFrame(check);
                                    return;
                                }
                                // 既に「フォロー中」タブが選択されている場合はそのまま完了
                                if (followingTab.getAttribute('aria-selected') === 'true') {
                                    clearTimeout(timeout);
                                    resolve('already_selected');
                                    return;
                                }
                                // 「フォロー中」タブをクリックして切り替える
                                followingTab.click();
                                clearTimeout(timeout);
                                resolve('switched');
                            };
                            check();
                        })
                        ''',
                        await_promise=True,
                        return_by_value=True,
                    ))
                    if tab_switch_exception is not None:
                        logging.warning(f'{self.log_prefix} Failed to switch to Following tab: {tab_switch_exception}')
                    else:
                        logging.info(f'{self.log_prefix} Following tab is active.')
                        # タブ切り替え後、Web App が HomeLatestTimeline を自動的に呼ぶのを少し待つ
                        await asyncio.sleep(2.0)
                except Exception as ex:
                    # タブ切り替えの失敗はセットアップ全体を失敗させるほどのものではない
                    logging.warning(f'{self.log_prefix} Error switching timeline tab:', exc_info=ex)

            except BaseException:
                # セットアップ途中で失敗した場合、作成済みのブラウザプロセスをここで確実に回収する
                ## ここで回収しないと KonomiTV サービス再起動時に古いヘッドレスブラウザが残りうる
                self.is_setup_complete = False
                try:
                    # まずは Zendriver の正規停止を試し、接続が生きているケースでは穏当に終了させる
                    if self._browser is not None:
                        await asyncio.wait_for(self._browser.stop(), timeout=5.0)
                except Exception as ex:
                    logging.error(f'{self.log_prefix} Error while cleaning up browser after setup failure:', exc_info=ex)

                # Browser.stop() が失敗・タイムアウトしても、親プロセスが分かっていれば OS レベルで回収する
                if self._browser_process is not None:
                    await asyncio.to_thread(
                        self._terminateBrowserProcessTree,
                        self._browser_process,
                        self.log_prefix,
                    )
                    self._active_browser_processes.pop(self._browser_process.pid, None)

                self._browser = None
                self._page = None
                self._browser_process = None
                raise

    def isBrowserProcessAlive(self) -> bool:
        """
        ブラウザプロセスがまだ生存しているかどうかを確認する
        ブラウザが外部から kill された場合やクラッシュした場合に False を返す
        psutil でプロセス情報を取得できなかった場合 (_browser_process が None) は、
        プロセスの死活が不明なため安全側に倒して True を返す (健全なブラウザを誤って再起動しないため)

        Returns:
            bool: ブラウザプロセスが生存している (または死活不明) 場合は True、確実に死んでいる場合は False
        """

        # _browser_process が None の場合は psutil でプロセス情報を取得できなかったケース
        # プロセスの死活が判定できないため、安全側に倒して True を返す
        if self._browser_process is None:
            return True
        try:
            return self._browser_process.is_running()
        except psutil.Error:
            return True

    async def captureDebugScreenshot(self, reason: str) -> str | None:
        """
        デバッグ用にヘッドレスブラウザの現在の画面をスクリーンショットとして保存する
        ツイート送信モーダルでのエラー発生時など、ブラウザの状態を確認するために使用する
        スクリーンショットの撮影自体が失敗してもエラーを伝搬させず、None を返す

        Args:
            reason (str): スクリーンショットを保存する理由 (ファイル名に使用される)

        Returns:
            str | None: 保存したスクリーンショットのファイルパス、または撮影に失敗した場合は None
        """

        if self._page is None:
            logging.warning(f'{self.log_prefix} Cannot capture screenshot: page is not initialized.')
            return None

        try:
            # スクリーンショットの保存先ディレクトリを作成
            TWITTER_DEBUG_SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

            # CDP Page.captureScreenshot でスクリーンショットを取得
            ## capture_screenshot() は Base64 エンコードされた画像データを str として直接返す
            ## runtime.evaluate() とは異なりタプルではないため、アンパッキングせずそのまま受け取る
            screenshot_data = await self._page.send(cdp.page.capture_screenshot(format_='png'))
            screenshot_bytes = base64.b64decode(screenshot_data)

            # ファイル名を生成して保存
            ## reason に含まれるファイル名に使えない文字を置換する
            ## Windows では <>:"/\|?* と制御文字がファイル名に使用できないため、正規表現で一括置換する
            safe_reason = re.sub(r'[<>:"/\\|?*\x00-\x1f\s]+', '_', reason).strip('_')[:80]
            timestamp = datetime.now(JST).strftime('%Y%m%d_%H%M%S')
            filename = f'{self.twitter_account.screen_name}_{timestamp}_{safe_reason}.png'
            filepath = TWITTER_DEBUG_SCREENSHOTS_DIR / filename
            filepath.write_bytes(screenshot_bytes)

            logging.info(f'{self.log_prefix} Debug screenshot saved: {filepath}')

            # 保持期限を超えた古いスクリーンショットを自動削除する
            ## スクリーンショットにはユーザーの下書きテキストやタイムラインが写り込む可能性があるため、
            ## 診断に十分な期間だけ保持し、それ以降は自動的に削除する
            cutoff_time = time.time() - (TWITTER_DEBUG_SCREENSHOTS_RETENTION_DAYS * 86400)
            for old_file in TWITTER_DEBUG_SCREENSHOTS_DIR.glob('*.png'):
                try:
                    if old_file.stat().st_mtime < cutoff_time:
                        old_file.unlink()
                except OSError:
                    pass

            return str(filepath)
        except Exception as ex:
            logging.warning(f'{self.log_prefix} Failed to capture debug screenshot:', exc_info=ex)
            return None

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
        throttle_remaining_seconds: float,
        in_reply_to_status_id: str | None = None,
    ) -> PostTweetViaComposeUIResult:
        """
        Twitter Web App のツイート送信モーダルを DOM 操作で自動化し、ツイートを送信する
        通常投稿では "n" キーのショートカット、リプライ投稿では履歴状態と query を使ってツイート送信モーダルを開く
        ツイート送信モーダルを開いたまま自然な待機を入れた後、テキスト入力・画像添付・Ctrl+Enter 送信を行う
        読み取り系 API と異なり、Web App の正規 UI 経路を通すため user_flow.json の scribe イベントが自然に発火する
        画像アップロードの完了と CreateTweet のレスポンスは CDP Network ドメインで監視する

        Args:
            tweet_text (str): ツイートの本文
            images (list[UploadFile]): 添付する画像（無いときは空リスト）
            throttle_remaining_seconds (float): ツイート送信モーダルを開いた後に吸収したいスロットル残り時間
            in_reply_to_status_id (str | None): リプライ先のツイート ID (None の場合は単独ツイート)

        Returns:
            PostTweetViaComposeUIResult: ツイート送信結果
        """

        class TwitterNetworkResponseInfo(TypedDict):
            """CDP Network イベントから取得したレスポンスの診断情報。"""

            status_code: int
            headers: dict[str, Any]

        # ヘッドレスブラウザが起動していない場合はエラー
        if self._browser is None or self._page is None:
            raise RuntimeError('Browser or page is not initialized.')

        page = self._page
        compose_flow_started_at = time.time()

        # CDP Network 監視の状態管理
        ## CreateTweet のレスポンスと画像アップロードの完了を CDP Network ドメインで監視する
        ## XHR フックと異なり、ページの JavaScript グローバル状態を一切汚染しない
        create_tweet_future: asyncio.Future[TwitterBrowserGraphQLAPIResult] = asyncio.Future()
        # CreateTweet の request_id と HTTP レスポンス情報を保持する辞書
        ## ボディ取得時点では responseReceived イベントの詳細へ戻れないため、
        ## JSON パース失敗時にステータスコードとヘッダーをログへ残せるよう先に退避しておく
        create_tweet_responses: dict[str, TwitterNetworkResponseInfo] = {}
        expected_upload_count = len(images)
        upload_finalize_count = 0
        # 画像アップロード完了を通知するイベント (画像がない場合は None)
        upload_complete_event: asyncio.Event | None = asyncio.Event() if expected_upload_count > 0 else None
        # 画像アップロード失敗を通知するイベント (FINALIZE が 4xx/5xx を返した場合にセットされる)
        upload_failed_event: asyncio.Event | None = asyncio.Event() if expected_upload_count > 0 else None
        # upload.x.com へのリクエスト総数を追跡するカウンター (デバッグ用)
        ## アップロードタイムアウト時に「リクエスト自体が出ていないのか、出ているが応答がないのか」を切り分ける
        upload_request_count = 0
        # ネットワーク監視が有効かどうかのフラグ
        ## CDP Network を disable した後もイベントハンドラは登録されたままなので、
        ## このフラグでイベントを無視するかどうかを制御する
        is_network_monitoring_active = False

        async def OnResponseReceived(event: cdp.network.ResponseReceived) -> None:
            """
            CDP Network.responseReceived イベントハンドラ
            CreateTweet の request_id と画像アップロード FINALIZE の完了を追跡する
            """

            nonlocal upload_finalize_count, upload_request_count
            if is_network_monitoring_active is not True:
                return

            # CORS preflight (OPTIONS) リクエストは無視する
            # upload.x.com はクロスオリジンのため FINALIZE に対して preflight が発生し、
            # preflight の 200 レスポンスを誤って FINALIZE 完了としてカウントしてしまう問題を防ぐ
            if event.type_ is not None and event.type_ == cdp.network.ResourceType.PREFLIGHT:
                return
            url = event.response.url

            # upload.x.com へのリクエスト総数を追跡 (デバッグ用)
            if 'upload.x.com' in url:
                upload_request_count += 1

            # CreateTweet のリクエストを追跡
            if 'CreateTweet' in url:
                create_tweet_responses[str(event.request_id)] = {
                    'status_code': event.response.status,
                    'headers': dict(event.response.headers),
                }

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
            if request_id_str not in create_tweet_responses:
                return
            if create_tweet_future.done():
                return

            # レスポンスボディを取得して Future に設定する
            ## get_response_body() が失敗した場合も診断ログで本文なしと明示できるよう、先に None で初期化する
            response_text: str | None = None
            try:
                response_info = create_tweet_responses[request_id_str]
                response_text, _ = await page.send(cdp.network.get_response_body(event.request_id))
                parsed_response = json.loads(response_text)
                create_tweet_future.set_result(TwitterBrowserGraphQLAPIResult(
                    status_code=response_info['status_code'],
                    parsed_response=parsed_response,
                    response_text=response_text,
                    headers=response_info['headers'],
                    request_error=None,
                ))
            except Exception as ex:
                logging.error(f'{self.log_prefix} Failed to read or parse CreateTweet response:', exc_info=ex)
                response_info = create_tweet_responses.get(request_id_str)
                self._logNetworkResponseDiagnostics(
                    reason='Failed to read or parse CreateTweet response',
                    status_code=response_info['status_code'] if response_info is not None else None,
                    headers=response_info['headers'] if response_info is not None else None,
                    response_text=response_text,
                )
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
            if request_id_str not in create_tweet_responses:
                return
            if create_tweet_future.done():
                return

            logging.error(f'{self.log_prefix} CreateTweet request failed: {event.error_text}')
            create_tweet_future.set_exception(
                RuntimeError(f'CreateTweet request failed: {event.error_text}')
            )

        # ツイート送信モーダルを閉じるためのヘルパー関数
        # エラー発生時のクリーンアップに使用する
        async def CloseComposeModal() -> None:
            """
            ツイート送信モーダルが開いている場合、Escape キーで閉じる
            テキストや画像が入力されている場合は「変更を破棄」ダイアログが表示されるため、
            破棄ボタンのクリックも試行する
            """

            try:
                # Escape キーを送信して ツイート送信モーダルを閉じる
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
                logging.warning(f'{self.log_prefix} Failed to close tweet posting modal:', exc_info=ex)

        compose_submitted_at: float | None = None

        # エラー時の共通レスポンスを生成するヘルパー
        # エラー発生時にデバッグ用スクリーンショットも自動保存する
        # ツイート送信モーダルを閉じる前にスクリーンショットを撮ることで、エラー時の UI 状態を正確に記録する
        async def MakeErrorResult(error_message: str) -> PostTweetViaComposeUIResult:
            # エラー発生時のブラウザ画面を保存して、根本原因の特定に役立てる
            # スクリーンショットはモーダルを閉じる前に撮影する (閉じた後ではエラー状態が見えない)
            await self.captureDebugScreenshot(f'compose_error_{error_message[:50]}')
            # スクリーンショット撮影後に ツイート送信モーダルを閉じてクリーンアップする
            await CloseComposeModal()
            return PostTweetViaComposeUIResult(
                is_success=False,
                error_message=error_message,
                graphql_api_result=None,
                compose_submitted_at=compose_submitted_at,
            )

        # CDP Network 監視を有効化するヘルパー関数
        ## 画像アップロードの FINALIZE 監視と CreateTweet レスポンスの取得に使用する
        ## ツイート送信モーダルを開く → テキスト paste の間は Network 監視不要なので、
        ## 必要になる直前まで遅延させることで、Twitter Web App のバックグラウンド通信
        ## (TL 更新、badge_count、user_flow.json 等) による CDP イベントハンドラの呼び出しを抑制し、
        ## asyncio イベントループの輻輳を防ぐ
        async def EnableNetworkMonitoring() -> None:
            nonlocal is_network_monitoring_active
            if is_network_monitoring_active is True:
                return
            logging.info(f'{self.log_prefix} Enabling CDP Network monitoring...')
            await page.send(cdp.network.enable())
            is_network_monitoring_active = True
            page.add_handler(cdp.network.ResponseReceived, OnResponseReceived)
            page.add_handler(cdp.network.LoadingFinished, OnLoadingFinished)
            page.add_handler(cdp.network.LoadingFailed, OnLoadingFailed)

        async def OpenComposeModal() -> PostTweetViaComposeUIResult | None:
            """
            ツイート送信モーダルを開き、送信前の待機に入れる状態まで遷移させる。

            Returns:
                PostTweetViaComposeUIResult | None: 失敗時はエラー結果、成功時は None
            """

            # ===========================================
            # Step 1: ツイート送信モーダルを開く
            # (この時点では CDP Network 監視はまだ有効化しない)
            # ===========================================
            if in_reply_to_status_id is None:
                # "n" キーは Twitter Web App のキーボードショートカットで、ツイート送信モーダルを開く
                # SideNav ボタンのクリックと異なり、ビューポートサイズに依存しない
                # モーダルが開くと URL が /compose/post に SPA 遷移する
                #
                # CDP Input.dispatchKeyEvent で "n" ショートカットを発火させるには以下の条件が必要:
                # 1. ページがアクティブ (bring_to_front) であること
                # 2. document.body にフォーカスが当たっていること (テキスト入力欄にフォーカスがあると "n" が入力される)
                # 3. keyDown イベントに text='n' を含めること
                #    text パラメータなしだと keydown DOM イベントのみが生成され、keypress イベントが発生しない
                #    Twitter のキーボードショートカットハンドラが keypress に依存している場合、ショートカットが発火しない
                logging.info(f'{self.log_prefix} Opening tweet posting modal via "n" keyboard shortcut...')
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
            else:
                # リプライ投稿では Twitter Web App の compose ルートが読む履歴状態と query の両方にリプライ先 ID を渡す
                # query も併用することで、親ツイートが未取得のページ状態でも Web App 側の取得処理へ入れる
                if re.fullmatch(r'\d+', in_reply_to_status_id) is None:
                    logging.error(f'{self.log_prefix} Invalid in_reply_to_status_id for reply modal: {in_reply_to_status_id}')
                    return await MakeErrorResult('リプライ先のツイート ID が不正です。')
                validated_reply_to_status_id = in_reply_to_status_id
                logging.info(f'{self.log_prefix} Opening reply modal via SPA navigation. in_reply_to_status_id: {validated_reply_to_status_id}')
                reply_state = {
                    'state': {
                        'inReplyToStatusId': validated_reply_to_status_id,
                    },
                    'key': ''.join(random.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(6)),
                }
                await page.send(cdp.page.bring_to_front())
                await page.send(cdp.runtime.evaluate(
                    expression=f'''
                    (() => {{
                        const wrappedState = {json.dumps(reply_state)};
                        const composeUrl = `/compose/post?in_reply_to=${{encodeURIComponent({json.dumps(validated_reply_to_status_id)})}}`;
                        window.history.pushState(wrappedState, '', composeUrl);
                        window.dispatchEvent(new PopStateEvent('popstate', {{ state: wrappedState }}));
                    }})()
                    ''',
                    return_by_value=True,
                ))

            # ===========================================
            # Step 2: ツイート送信モーダルが開くのを待機する
            # ===========================================
            # /home のタイムライン上部にもインラインの tweetTextarea_0 が存在するため、
            # 単に tweetTextarea_0 の存在をチェックするだけではモーダルが開いたことを正しく判定できない
            # ツイート送信モーダルが開くと URL が /compose/post に SPA 遷移し、
            # モーダル内の tweetTextarea_0 は [role="dialog"] の子孫に配置される
            # そのため「URL が /compose/post に遷移 && [role="dialog"] 内に tweetTextarea_0 が存在」を条件にする
            logging.info(f'{self.log_prefix} Waiting for tweet posting modal to open...')
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
                logging.error(f'{self.log_prefix} Tweet posting modal not found: {compose_modal_exception}')
                return await MakeErrorResult('ツイート送信モーダルが開きませんでした。')

            logging.debug(f'{self.log_prefix} Compose modal opened.')
            return None

        async def SubmitTweet() -> PostTweetViaComposeUIResult:
            """
            開いている ツイート送信モーダルに対して内容を入力し、送信レスポンスまで待機する。

            Returns:
                PostTweetViaComposeUIResult: ツイート送信結果
            """

            # 外側の compose_submitted_at を更新するために nonlocal 宣言が必要
            ## SubmitTweet() は内部関数なので、nonlocal なしだと新しいローカル変数が作られてしまい、
            ## MakeErrorResult() が参照する compose_submitted_at が None のままになる
            nonlocal compose_submitted_at

            # ===========================================
            # Step 3: ClipboardEvent paste でテキストを入力する
            # ===========================================
            # Draft.js エディタに対しては ClipboardEvent paste が最も安定して動作する
            # document.execCommand('insertText') は React の DOM 管理と衝突して error_log.json にエラーが送信されてしまう
            # ClipboardEvent paste なら Draft.js の _onPaste ハンドラが正規経路でテキストを処理するため、
            # エラーが発生せず、interaction detector の totalPasteCount も自然にインクリメントされる
            if tweet_text:
                logging.info(f'{self.log_prefix} Pasting tweet text ({len(tweet_text)} chars)...')
                paste_result, paste_exception = await page.send(cdp.runtime.evaluate(
                    expression=f'''
                    (() => {{
                        // ツイート送信モーダル内の tweetTextarea_0 を対象にする (タイムラインのインライン投稿欄ではなくモーダルのもの)
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
                    return await MakeErrorResult('テキストの入力に失敗しました。')

                logging.debug(f'{self.log_prefix} Tweet text pasted.')

            # ===========================================
            # Step 4: 画像をアップロードする (画像がある場合)
            # ===========================================
            if len(images) > 0:
                # テキスト入力後から画像を添付するまでの自然な遅延 (sleep) と、
                # 画像の Base64 エンコード + ブラウザへのプリロードを並列実行する
                ## sleep 中はイベントループがアイドルになるため、その間に画像データをブラウザ側の
                ## グローバル変数に転送しておくことで、後の fileInput 設定を軽量化する
                ## (Base64 データを JS 式に埋め込んで runtime.evaluate するコストを sleep の裏側に隠す)
                async def PreloadImagesToBrowser() -> None:
                    """
                    画像を Base64 エンコードし、ブラウザのグローバル変数にプリロードする。
                    """

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
                    # ブラウザ側のグローバル変数に Base64 データを格納する
                    ## このタイミングでは CDP WebSocket 経由で数百 KB 〜数 MB のデータが転送される
                    await page.send(cdp.runtime.evaluate(
                        expression=f'window.__preloadedImages = {json.dumps(images_json_array, ensure_ascii=False)}',
                        return_by_value=True,
                    ))

                # 画像のアップロードを待機（最低でも 0.2 ~ 0.4 秒は待つ）
                logging.debug(f'{self.log_prefix} Pre-loading {len(images)} image(s) to browser during sleep...')
                await asyncio.gather(
                    asyncio.sleep(random.uniform(0.2, 0.4)),
                    PreloadImagesToBrowser(),
                )

                # CDP Network 監視を有効化する (画像アップロードの FINALIZE を監視するために必要)
                ## ツイート送信モーダルを開く → テキスト paste の間は Network 監視が不要なので、ここまで遅延させている
                await EnableNetworkMonitoring()

                # プリロード済みデータからファイルを生成して fileInput に設定する
                ## 重い Base64 データの転送は sleep 中に完了しているため、ここでは File オブジェクト生成 + change 発火のみ
                logging.info(f'{self.log_prefix} Uploading {len(images)} image(s) via fileInput...')
                upload_result, upload_exception = await page.send(cdp.runtime.evaluate(
                    expression='''
                    (() => {
                        const images = window.__preloadedImages;
                        delete window.__preloadedImages;
                        if (!images) return 'preloaded images not found';
                        const fileInput = document.querySelector('[role="dialog"] [data-testid="fileInput"]');
                        if (!fileInput) return 'fileInput not found';
                        const dt = new DataTransfer();
                        for (const img of images) {
                            const binaryString = atob(img.base64);
                            const bytes = new Uint8Array(binaryString.length);
                            for (let i = 0; i < binaryString.length; i++) {
                                bytes[i] = binaryString.charCodeAt(i);
                            }
                            const file = new File([bytes], img.fileName, { type: img.mimeType });
                            dt.items.add(file);
                        }
                        fileInput.files = dt.files;
                        fileInput.dispatchEvent(new Event('change', { bubbles: true }));
                        return true;
                    })()
                    ''',
                    return_by_value=True,
                ))

                if upload_exception is not None or (upload_result and upload_result.value is not True):
                    error_detail = upload_result.value if upload_result else str(upload_exception)
                    logging.error(f'{self.log_prefix} Failed to set images on fileInput: {error_detail}')
                    return await MakeErrorResult(f'画像の設定に失敗しました。({error_detail})')

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
                        # リクエスト自体が出ていないのか、出ているが応答がないのかを切り分けるためにネットワーク状態をログ出力する
                        logging.error(
                            f'{self.log_prefix} Timeout waiting for image upload FINALIZE. '
                            f'upload requests observed: {upload_request_count}, '
                            f'FINALIZE succeeded: {upload_finalize_count}/{expected_upload_count}',
                        )
                        return await MakeErrorResult('画像アップロードがタイムアウトしました。')
                    if upload_failed_event.is_set():
                        logging.error(f'{self.log_prefix} Image upload FINALIZE returned an error.')
                        return await MakeErrorResult('画像のアップロードに失敗しました。')
                except Exception as ex:
                    logging.error(f'{self.log_prefix} Error waiting for image uploads:', exc_info=ex)
                    return await MakeErrorResult(f'画像アップロードの待機中にエラーが発生しました。({ex})')

                logging.info(f'{self.log_prefix} All image uploads completed.')

            # ===========================================
            # Step 5: tweetButton が有効になるまで待機する
            # ===========================================
            # 画像アップロード完了後も tweetButton が有効になるまで少し時間がかかる場合がある
            # タイムラインのインライン投稿欄ではなく、ツイート送信モーダル内の tweetButton を対象にする
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
                return await MakeErrorResult('ツイートボタンが有効になりませんでした。テキストや画像の入力に問題がある可能性があります。')

            logging.debug(f'{self.log_prefix} tweetButton is enabled.')

            # ===========================================
            # Step 6: Ctrl+Enter でツイートを送信する
            # ===========================================
            # 画像がなかった場合、ここで初めて CDP Network 監視を有効化する
            ## (CreateTweet レスポンスを監視するために必要)
            await EnableNetworkMonitoring()

            # Ctrl+Enter 送信前に、ツイートテキストエリアにフォーカスが戻っていることを確認する
            ## 画像添付後は fileInput 側へフォーカスが移る場合があるため、明示的にツイートテキストエリアを再 focus する
            logging.info(f'{self.log_prefix} Ensuring tweet textarea is focused...')
            focus_result, focus_exception = await page.send(cdp.runtime.evaluate(
                expression='''
                (() => {
                    const textarea = document.querySelector('[role="dialog"] [data-testid="tweetTextarea_0"]');
                    if (!textarea) {
                        return false;
                    }
                    if (document.activeElement !== textarea) {
                        textarea.focus();
                    }
                    return document.activeElement === textarea;
                })()
                ''',
                return_by_value=True,
            ))

            if focus_exception is not None or (focus_result and focus_result.value is not True):
                logging.error(f'{self.log_prefix} Failed to focus tweet textarea: {focus_exception}')
                return await MakeErrorResult('ツイートテキストエリアへのフォーカスに失敗しました。')

            logging.info(f'{self.log_prefix} Submitting tweet via Ctrl+Enter...')
            await page.send(cdp.input_.dispatch_key_event(
                type_='keyDown',
                modifiers=2,
                key='Control',
                code='ControlLeft',
                windows_virtual_key_code=17,
                native_virtual_key_code=17,
            ))
            await page.send(cdp.input_.dispatch_key_event(
                type_='keyDown',
                modifiers=2,
                key='Enter',
                code='Enter',
                text='\r',
                unmodified_text='\r',
                windows_virtual_key_code=13,
                native_virtual_key_code=13,
            ))
            await page.send(cdp.input_.dispatch_key_event(
                type_='keyUp',
                modifiers=2,
                key='Enter',
                code='Enter',
                windows_virtual_key_code=13,
                native_virtual_key_code=13,
            ))
            await page.send(cdp.input_.dispatch_key_event(
                type_='keyUp',
                key='Control',
                code='ControlLeft',
                windows_virtual_key_code=17,
                native_virtual_key_code=17,
            ))

            # Ctrl+Enter で送信した時刻を記録し、最小送信間隔の基準に使う
            compose_submitted_at = time.time()

            # ===========================================
            # Step 7: CDP Network 監視で CreateTweet のレスポンスを待機する
            # ===========================================
            logging.info(f'{self.log_prefix} Waiting for CreateTweet response via CDP Network...')
            try:
                response_data = await asyncio.wait_for(create_tweet_future, timeout=30.0)
            except TimeoutError:
                logging.error(f'{self.log_prefix} Timeout waiting for CreateTweet response.')
                return await MakeErrorResult('CreateTweet のレスポンスがタイムアウトしました。')
            except Exception as ex:
                logging.error(f'{self.log_prefix} Error waiting for CreateTweet response:', exc_info=ex)
                return await MakeErrorResult(f'CreateTweet のレスポンスを取得できませんでした。({ex})')

            status_code = response_data.status_code
            logging.info(f'{self.log_prefix} CreateTweet response received. (HTTP {status_code})')

            return PostTweetViaComposeUIResult(
                is_success=True,
                error_message=None,
                graphql_api_result=response_data,
                compose_submitted_at=compose_submitted_at,
            )

        try:
            # ツイート送信モーダルを開く
            open_compose_result = await OpenComposeModal()
            if open_compose_result is not None:
                return open_compose_result

            # ツイート送信モーダルを開いた後に、まだ必要なスロットル待機だけを残して自然な「考え中」時間として吸収する
            ## OpenComposeModal() の実行時間を差し引き、モーダルが開いた直後に即 paste しないよう最低限の待機も確保する
            elapsed_seconds = time.time() - compose_flow_started_at
            compose_throttle_remaining_seconds = max(0.0, throttle_remaining_seconds - elapsed_seconds)
            minimum_thinking_seconds = round(random.uniform(1.0, 2.0), 3)
            compose_thinking_wait_seconds = max(compose_throttle_remaining_seconds, minimum_thinking_seconds)
            logging.info(
                f'{self.log_prefix} Waiting before tweet submission. '
                f'throttle remaining: {compose_throttle_remaining_seconds:.3f}s, '
                f'thinking wait: {compose_thinking_wait_seconds:.3f}s',
            )
            await asyncio.sleep(compose_thinking_wait_seconds)

            # ツイートを送信し、結果を返す
            return await SubmitTweet()

        except Exception as ex:
            logging.error(f'{self.log_prefix} Unexpected error during tweet posting via modal:', exc_info=ex)
            return await MakeErrorResult(f'ツイート送信中に予期しないエラーが発生しました。({ex})')

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
            if self._browser is None and self._browser_process is None:
                logging.warning(f'{self.log_prefix} Browser is not initialized, skipping shutdown.')
                return

            # 停止対象をローカル変数へ退避しておくことで、後段のクリーンアップで参照を明確にする
            browser = self._browser
            browser_process = self._browser_process

            # セットアップ完了フラグをリセット（シャットダウン開始時点でセットアップ状態を無効化）
            ## これにより、シャットダウン中に setup が呼ばれた場合でも、シャットダウン完了後に再度セットアップが必要になる
            self.is_setup_complete = False

            # ヘッドレスブラウザを停止
            # まずは Zendriver の正規停止を試し、通常の終了処理で片付くケースを優先する
            if browser is not None:
                logging.info(f'{self.log_prefix} Waiting for browser to terminate...')
                try:
                    await asyncio.wait_for(browser.stop(), timeout=5.0)
                    logging.info(f'{self.log_prefix} Browser terminated.')
                except Exception as ex:
                    logging.error(f'{self.log_prefix} Error while terminating browser:', exc_info=ex)

            # Browser.stop() の成否にかかわらず、親プロセスが残っていれば最後に OS レベルで残骸を掃除する
            if browser_process is not None:
                await asyncio.to_thread(
                    self._terminateBrowserProcessTree,
                    browser_process,
                    self.log_prefix,
                )
                self._active_browser_processes.pop(browser_process.pid, None)

            # 参照を明示的に破棄し、以後は新しい setup() でのみ再利用される状態に戻す
            self._browser = None
            self._page = None
            self._browser_process = None

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

    @classmethod
    def _terminateBrowserProcessTree(cls, browser_process: psutil.Process, log_prefix: str) -> None:
        """
        指定されたブラウザプロセスツリーを同期的に terminate / kill する。

        Args:
            browser_process (psutil.Process): 終了したいブラウザ親プロセス
            log_prefix (str): ログ出力用のプレフィックス
        """

        try:
            # PID 再利用対策は psutil.Process 側が持っているため、保持済みの Process をそのまま起点にする
            if browser_process.is_running() is not True:
                return
            root_process = browser_process
            # Chrome 系ブラウザは親プロセスの配下に複数の子プロセスをぶら下げるため、必ずプロセスツリーごと回収する
            target_processes = root_process.children(recursive=True)
            target_processes.append(root_process)
        except psutil.NoSuchProcess:
            return
        except psutil.Error as ex:
            logging.warning(f'{log_prefix} Failed to enumerate browser process tree. pid: {browser_process.pid}', exc_info=ex)
            return

        logging.warning(
            f'{log_prefix} Force terminating browser process tree. '
            f'pid: {browser_process.pid}, descendants: {len(target_processes) - 1}',
        )

        # 子から順に terminate することで、親だけ先に落として子プロセスが孤児化する可能性を下げる
        for target_process in reversed(target_processes):
            try:
                target_process.terminate()
            except psutil.NoSuchProcess:
                continue
            except psutil.Error as ex:
                logging.warning(f'{log_prefix} Failed to terminate browser process. pid: {target_process.pid}', exc_info=ex)

        # まずは穏当な terminate を試し、通常の終了シーケンスに乗れるプロセスはそのまま終了させる
        _, alive_processes = psutil.wait_procs(target_processes, timeout=5.0)
        if len(alive_processes) == 0:
            return

        logging.warning(f'{log_prefix} Browser process tree did not exit after terminate(). Killing survivors...')
        # terminate で落ちなかったプロセスだけ kill に切り替え、残骸を確実に掃除する
        for alive_process in alive_processes:
            try:
                alive_process.kill()
            except psutil.NoSuchProcess:
                continue
            except psutil.Error as ex:
                logging.warning(f'{log_prefix} Failed to kill browser process. pid: {alive_process.pid}', exc_info=ex)

        _, still_alive_processes = psutil.wait_procs(alive_processes, timeout=2.0)
        if len(still_alive_processes) > 0:
            still_alive_pids = [process.pid for process in still_alive_processes]
            logging.error(f'{log_prefix} Browser process tree is still alive after kill(). pids: {still_alive_pids}')

    @classmethod
    def cleanupBrowserProcessesAtExit(cls) -> None:
        """
        Python プロセス終了時に、未回収のヘッドレスブラウザをすべて強制終了する。
        """

        # atexit 中に辞書を書き換えながら走査しないよう、現在の回収対象を先にスナップショット化する
        active_processes = list(cls._active_browser_processes.values())
        cls._active_browser_processes.clear()

        for browser_process in active_processes:
            cls._terminateBrowserProcessTree(
                browser_process=browser_process,
                log_prefix='[TwitterScrapeBrowser][ProcessExit]',
            )


# 通常の shutdown 経路に入れなかった場合でも、Python プロセス終了時に最後の保険として必ず回収する
atexit.register(TwitterScrapeBrowser.cleanupBrowserProcessesAtExit)
