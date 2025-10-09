
import asyncio
import json
import re
import time
from datetime import datetime
from typing import Any, ClassVar, Literal, cast
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests
from typing_extensions import TypedDict

from app import logging, schemas
from app.constants import HTTPX_CLIENT
from app.models.TwitterAccount import TwitterAccount


class _TweetLockInfo(TypedDict):
    lock: asyncio.Lock
    last_tweet_time: float


class TwitterGraphQLAPI:
    """
    Twitter Web App で利用されている GraphQL API の薄いラッパー
    外部ライブラリを使うよりすべて自前で書いたほうが柔軟に対応でき凍結リスクを回避できると考え実装した
    以下に実装されているリクエストペイロードなどはすべて実装時点の Twitter Web App が実際に送信するリクエストを可能な限り模倣したもの
    メソッド名は概ね GraphQL API でのエンドポイント名に対応している
    """

    # GraphQL API のエンドポイント定義
    ## クエリ ID はおそらく API のバージョン (?) を示しているらしい謎の値で、数週間単位で変更されうる (定期的に追従が必要)
    ## 一方 CreateRetweet など機能の変化が少なく機能フラグも少ない API のクエリ ID はほとんど変更されることがない
    ## リクエストペイロードのうち "features" 内に入っている機能フラグ (？) も数週間単位で頻繁に変更されうるが、Twitter Web App と
    ## 完全に一致していないからといって必ずしも動かなくなるわけではなく、クエリ ID 同様にある程度は古い値でも動くようになっているらしい
    ## 以下のコードはエンドポイントごとに poetry run python -m misc.TwitterAPIQueryGenerator を実行して半自動生成できる
    ENDPOINT_INFOS: ClassVar[dict[str, schemas.TwitterGraphQLAPIEndpointInfo]] = {
        'CreateTweet': schemas.TwitterGraphQLAPIEndpointInfo(
            method = 'POST',
            query_id = 'qc4OW1w4zjtXm-oxpdzgDg',
            endpoint = 'CreateTweet',
            features = {
                'premium_content_api_read_enabled': False,
                'communities_web_enable_tweet_community_results_fetch': True,
                'c9s_tweet_anatomy_moderator_badge_enabled': True,
                'responsive_web_grok_analyze_button_fetch_trends_enabled': True,
                'responsive_web_edit_tweet_api_enabled': True,
                'graphql_is_translatable_rweb_tweet_is_translatable_enabled': True,
                'view_counts_everywhere_api_enabled': True,
                'longform_notetweets_consumption_enabled': True,
                'responsive_web_twitter_article_tweet_consumption_enabled': True,
                'tweet_awards_web_tipping_enabled': False,
                'creator_subscriptions_quote_tweet_preview_enabled': False,
                'longform_notetweets_rich_text_read_enabled': True,
                'longform_notetweets_inline_media_enabled': True,
                'profile_label_improvements_pcf_label_in_post_enabled': False,
                'rweb_tipjar_consumption_enabled': True,
                'responsive_web_graphql_exclude_directive_enabled': True,
                'verified_phone_label_enabled': False,
                'articles_preview_enabled': True,
                'rweb_video_timestamps_enabled': True,
                'responsive_web_graphql_skip_user_profile_image_extensions_enabled': False,
                'freedom_of_speech_not_reach_fetch_enabled': True,
                'standardized_nudges_misinfo': True,
                'tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled': True,
                'responsive_web_graphql_timeline_navigation_enabled': True,
                'responsive_web_enhance_cards_enabled': False,
            },
        ),
        'CreateRetweet': schemas.TwitterGraphQLAPIEndpointInfo(
            method = 'POST',
            query_id = 'ojPdsZsimiJrUGLR1sjUtA',
            endpoint = 'CreateRetweet',
            features = None,
        ),
        'DeleteRetweet': schemas.TwitterGraphQLAPIEndpointInfo(
            method = 'POST',
            query_id = 'iQtK4dl5hBmXewYZuEOKVw',
            endpoint = 'DeleteRetweet',
            features = None,
        ),
        'FavoriteTweet': schemas.TwitterGraphQLAPIEndpointInfo(
            method = 'POST',
            query_id = 'lI07N6Otwv1PhnEgXILM7A',
            endpoint = 'FavoriteTweet',
            features = None,
        ),
        'UnfavoriteTweet': schemas.TwitterGraphQLAPIEndpointInfo(
            method = 'POST',
            query_id = 'ZYKSe-w7KEslx3JhSIk5LA',
            endpoint = 'UnfavoriteTweet',
            features = None,
        ),
        'HomeLatestTimeline': schemas.TwitterGraphQLAPIEndpointInfo(
            method = 'POST',
            query_id = 'UfVanvi6BR1qWBYfN-VXIw',
            endpoint = 'HomeLatestTimeline',
            features = {
                'profile_label_improvements_pcf_label_in_post_enabled': False,
                'rweb_tipjar_consumption_enabled': True,
                'responsive_web_graphql_exclude_directive_enabled': True,
                'verified_phone_label_enabled': False,
                'creator_subscriptions_tweet_preview_api_enabled': True,
                'responsive_web_graphql_timeline_navigation_enabled': True,
                'responsive_web_graphql_skip_user_profile_image_extensions_enabled': False,
                'premium_content_api_read_enabled': False,
                'communities_web_enable_tweet_community_results_fetch': True,
                'c9s_tweet_anatomy_moderator_badge_enabled': True,
                'responsive_web_grok_analyze_button_fetch_trends_enabled': True,
                'articles_preview_enabled': True,
                'responsive_web_edit_tweet_api_enabled': True,
                'graphql_is_translatable_rweb_tweet_is_translatable_enabled': True,
                'view_counts_everywhere_api_enabled': True,
                'longform_notetweets_consumption_enabled': True,
                'responsive_web_twitter_article_tweet_consumption_enabled': True,
                'tweet_awards_web_tipping_enabled': False,
                'creator_subscriptions_quote_tweet_preview_enabled': False,
                'freedom_of_speech_not_reach_fetch_enabled': True,
                'standardized_nudges_misinfo': True,
                'tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled': True,
                'rweb_video_timestamps_enabled': True,
                'longform_notetweets_rich_text_read_enabled': True,
                'longform_notetweets_inline_media_enabled': True,
                'responsive_web_enhance_cards_enabled': False,
            },
        ),
        'SearchTimeline': schemas.TwitterGraphQLAPIEndpointInfo(
            method = 'GET',
            query_id = 'fnkladLRj_7bB0PwaOtymA',
            endpoint = 'SearchTimeline',
            features = {
                'profile_label_improvements_pcf_label_in_post_enabled': False,
                'rweb_tipjar_consumption_enabled': True,
                'responsive_web_graphql_exclude_directive_enabled': True,
                'verified_phone_label_enabled': False,
                'creator_subscriptions_tweet_preview_api_enabled': True,
                'responsive_web_graphql_timeline_navigation_enabled': True,
                'responsive_web_graphql_skip_user_profile_image_extensions_enabled': False,
                'premium_content_api_read_enabled': False,
                'communities_web_enable_tweet_community_results_fetch': True,
                'c9s_tweet_anatomy_moderator_badge_enabled': True,
                'responsive_web_grok_analyze_button_fetch_trends_enabled': True,
                'articles_preview_enabled': True,
                'responsive_web_edit_tweet_api_enabled': True,
                'graphql_is_translatable_rweb_tweet_is_translatable_enabled': True,
                'view_counts_everywhere_api_enabled': True,
                'longform_notetweets_consumption_enabled': True,
                'responsive_web_twitter_article_tweet_consumption_enabled': True,
                'tweet_awards_web_tipping_enabled': False,
                'creator_subscriptions_quote_tweet_preview_enabled': False,
                'freedom_of_speech_not_reach_fetch_enabled': True,
                'standardized_nudges_misinfo': True,
                'tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled': True,
                'rweb_video_timestamps_enabled': True,
                'longform_notetweets_rich_text_read_enabled': True,
                'longform_notetweets_inline_media_enabled': True,
                'responsive_web_enhance_cards_enabled': False,
            },
        ),
    }

    # Twitter API のエラーコードとエラーメッセージの対応表
    ## 実際に返ってくる可能性があるものだけ
    ## ref: https://developer.twitter.com/ja/docs/basics/response-codes
    ERROR_MESSAGES: ClassVar[dict[int, str]] = {
        32:  'Twitter アカウントの認証に失敗しました。もう一度連携し直してください。',
        63:  'Twitter アカウントが凍結またはロックされています。',
        64:  'Twitter アカウントが凍結またはロックされています。',
        88:  'Twitter API エンドポイントのレート制限を超えました。',
        89:  'Twitter アクセストークンの有効期限が切れています。',
        99:  'Twitter OAuth クレデンシャルの認証に失敗しました。',
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

    # Challenge 情報のキャッシュの有効期限 (秒)
    CHALLENGE_INFO_CACHE_EXPIRATION_TIME = 60 * 60  # 1 時間

    # アカウントごとに Challenge 情報を 60 分間キャッシュするための辞書
    ## Twitter Web App は PWA のため、2回目以降のロードでは Service Worker から HTML や JS が返されている
    ## そのため、毎回取得するのではなく一定期間同一の Challenge 情報を返した方がより公式のロジックに近くなると考えられる
    __challenge_info_cache: ClassVar[dict[str, tuple[float, schemas.TwitterChallengeData]]] = {}

    # ツイートの最小送信間隔 (秒)
    MINIMUM_TWEET_INTERVAL = 20  # 必ずアカウントごとに 20 秒以上間隔を空けてツイートする

    # アカウントごとにロックと最後のツイート時刻を管理する辞書 (ツイート送信時の排他制御用)
    __tweet_locks: ClassVar[dict[str, _TweetLockInfo]] = {}


    def __init__(self, twitter_account: TwitterAccount) -> None:
        """
        Twitter GraphQL API クライアントを初期化する

        Args:
            twitter_account: Twitter アカウントのモデル
        """

        self.twitter_account = twitter_account

        # Chrome への偽装用 HTTP リクエストヘッダーを取得
        ## User-Agent ヘッダーも Chrome に偽装されている
        self.cookie_session_user_handler = self.twitter_account.getTweepyAuthHandler()
        self.graphql_headers_dict = cast(dict[str, str], self.cookie_session_user_handler.get_graphql_api_headers())  # GraphQL API 用ヘッダー
        self.html_headers_dict = self.cookie_session_user_handler.get_html_headers()  # HTML 用ヘッダー
        self.js_headers_dict = self.cookie_session_user_handler.get_js_headers(cross_origin=True)  # JavaScript 用ヘッダー

        # 指定されたアカウントへの認証情報が含まれる Cookie を取得し、curl_cffi.requests.Cookies に変換
        ## ここで生成した Cookie を HTTP クライアントに渡す
        cookies_dict = self.cookie_session_user_handler.get_cookies_as_dict()
        cookies = curl_requests.Cookies()
        for name, value in cookies_dict.items():
            # ドメインを ".x.com" 、パスを "/" に設定しておくことが重要 (でないと Cookie 更新時にちゃんと上書きできない)
            ## ただし "lang" キーだけは ".x.com" でなく "x.com" にする必要がある
            if name == 'lang':
                cookies.set(name, value, domain='x.com', path='/')
            else:
                cookies.set(name, value, domain='.x.com', path='/')

        # curl-cffi の非同期 HTTP クライアントのインスタンスを作成
        ## 可能な限り Chrome からのリクエストに偽装するため、app.constants.HTTPX_CLIENT は使わずに独自のインスタンスを作成する
        self.curl_session = curl_requests.AsyncSession(
            ## Cookie を設定
            ## Cookie はこの HTTP クライアントで行う全リクエストで共有されてほしいので、ここで設定している
            ## 一方リクエストヘッダーはリクエスト先のリソース種類によって異なるためここでは設定せず、リクエスト毎に個別に設定する
            ## (HTTP クライアントレベルで設定されたヘッダーは上書きや削除が難しそうなため)
            cookies = cookies,
            ## リダイレクトを追跡する
            allow_redirects = True,
            ## curl-cffi に実装されている中で一番新しい Chrome バージョンに偽装する
            impersonate = 'chrome',
            ## 可能な限り Chrome からのリクエストに偽装するため、明示的に HTTP/2 で接続する
            http_version = 'v2',
        )


    @classmethod
    async def updateEndpointInfos(cls) -> None:
        """
        頻繁に更新される Twitter GraphQL API のエンドポイント定義を最新のものに更新する
        更新できなくても直ちに問題が出るわけではないため、取得失敗時は何もしない (エラーはログに出力するだけ)
        ref: https://github.com/fa0311/TwitterInternalAPIDocument
        """

        start_time = time.time()
        logging.info('Twitter GraphQL API endpoint infos updating...')

        try:
            # GraphQL API のエンドポイント情報を取得
            async with HTTPX_CLIENT() as client:
                response = await client.get('https://raw.githubusercontent.com/fa0311/TwitterInternalAPIDocument/develop/docs/json/GraphQL.json')
                response.raise_for_status()
                endpoint_infos = response.json()

            for endpoint in endpoint_infos:
                exports = endpoint['exports']
                operation_name = exports['operationName']

                # 前から ENDPOINT_INFOS に定義されているエンドポイント情報のみ更新
                if operation_name in cls.ENDPOINT_INFOS:

                    # method は HomeLatestTimeline を除き、operationType が mutation かで判定する
                    ## HomeLatestTimeline は operationType は query だが、実際の挙動を観察するに POST で送信されることの方が多いため
                    if operation_name != 'HomeLatestTimeline':
                        if exports['operationType'] == 'mutation':
                            method = 'POST'
                        else:
                            method = 'GET'
                    else:
                        method = cls.ENDPOINT_INFOS[operation_name].method

                    # features に設定する用の最新の Feature Switches 情報を取得
                    ## longform_notetweets_consumption_enabled: true みたいなやつ
                    metadata = exports['metadata']
                    feature_switches = metadata['featureSwitches']
                    feature_switch = metadata['featureSwitch']
                    features = {}
                    for switch in feature_switches:
                        if switch in feature_switch:
                            features[switch] = feature_switch[switch]['value'] == 'true'
                        else:
                            # ごく稀に featureSwitch にデフォルト値が書かれていない場合があるので、
                            # その場合は true をデフォルト値とする
                            features[switch] = True
                    if not features:
                        features = None

                    # TwitterGraphQLAPIEndpointInfo 型に合わせて更新
                    old_endpoint_info = cls.ENDPOINT_INFOS[operation_name]
                    cls.ENDPOINT_INFOS[operation_name] = schemas.TwitterGraphQLAPIEndpointInfo(
                        method = method,
                        query_id = exports['queryId'],
                        endpoint = operation_name,
                        features = features,  # features が存在しないエンドポイントでは None が入る
                    )

                    # 変更差分があるときのみ出力
                    if old_endpoint_info.query_id != cls.ENDPOINT_INFOS[operation_name].query_id or \
                       old_endpoint_info.method != cls.ENDPOINT_INFOS[operation_name].method or \
                       old_endpoint_info.features != cls.ENDPOINT_INFOS[operation_name].features:
                        logging.debug_simple(f'[TwitterGraphQLAPI] {cls.ENDPOINT_INFOS[operation_name].endpoint}: '
                                             f'[{cls.ENDPOINT_INFOS[operation_name].method}] {cls.ENDPOINT_INFOS[operation_name].path}')

            logging.info(f'Twitter GraphQL API endpoint infos update complete. ({round(time.time() - start_time, 3)} sec)')
        except Exception as ex:
            logging.error('Failed to update Twitter GraphQL API endpoint infos:', exc_info=ex)


    async def persistCookies(self) -> None:
        """
        HTTP クライアントの Cookie をデータベースに永続化する
        """

        # 既存の access_token_secret から Cookie を取得
        existing_cookies: dict[str, str] = json.loads(self.twitter_account.access_token_secret)

        # HTTP クライアントが現在持つ Cookie で既存の Cookie を更新
        for name, value in self.curl_session.cookies.items():
            existing_cookies[name] = value

        # 更新された Cookie を再び JSON にして保存
        self.twitter_account.access_token_secret = json.dumps(existing_cookies, ensure_ascii = False)
        await self.twitter_account.save()


    async def fetchChallengeData(self) -> schemas.TwitterChallengeData | schemas.TwitterAPIResult:
        """
        Twitter Web App の API リクエスト内の X-Client-Transaction-ID ヘッダーを算出するために必要な Challenge 情報を取得する
        X-Client-Transaction-ID はスクレイピング回避のためのヘッダーで、難読化された JavaScript に含まれる算出関数に検証コード
        (twitter-site-verification) とアニメーション SVG (svg[id^="loading-x"] の outerHTML) を投入することで算出される

        詳細な動作原理はよく理解できていないが、ともかくアニメーション SVG のレンダリングや JavaScript の実行にブラウザエンジンが必要になるため、
        Python 製のサーバーだけでは X-Client-Transaction-ID を算出できない
        そのため、サーバー側では X-Client-Transaction-ID の算出に必要な Challenge 情報を返し、そのデータを元にブラウザ上のフロントエンドで算出した
        X-Client-Transaction-ID をサーバーへの API リクエストに含めてもらい、受け取った値を GraphQL API リクエスト時に送信する設計としている

        ref: https://github.com/dimdenGD/OldTweetDeck/blob/main/src/challenge.js#L150-L169
        ref: https://antibot.blog/twitter-header-part-3/

        Returns:
            schemas.TwitterChallengeData | schemas.TwitterAPIResult: Challenge 情報またはエラーメッセージ
        """

        # まだ有効であればキャッシュから Challenge 情報を取得
        ## 頻繁にこの操作が行われると不審と判断される可能性があるため、一定期間フロントエンドに対し同一の Challenge 情報を使わせる
        if self.twitter_account.screen_name in self.__challenge_info_cache:
            cached_time, cached_challenge_data = self.__challenge_info_cache[self.twitter_account.screen_name]
            if time.time() - cached_time < self.CHALLENGE_INFO_CACHE_EXPIRATION_TIME:
                return cached_challenge_data

        # Twitter Web App (SPA) の HTML を取得
        ## HTML リクエスト用のヘッダーに差し替えるのが重要
        twitter_web_app_html = await self.curl_session.get('https://x.com/home', headers=self.html_headers_dict)
        if twitter_web_app_html.status_code != 200:
            logging.error(f'[TwitterGraphQLAPI] Failed to fetch Twitter Web App HTML: {twitter_web_app_html.status_code}')
            return schemas.TwitterAPIResult(
                is_success = False,
                detail = f'Challenge 情報の取得に失敗しました。Twitter Web App の HTML を取得できませんでした。(HTTP Error {twitter_web_app_html.status_code})',
            )
        twitter_web_app_html_text = twitter_web_app_html.text

        # BeautifulSoup を使って HTML をパース
        soup = BeautifulSoup(twitter_web_app_html_text, 'html.parser')

        # HTML の meta タグに含まれる検証コードを取得
        meta_tag = soup.select_one('meta[name="twitter-site-verification"]')
        if meta_tag is None:
            logging.error('[TwitterGraphQLAPI] Failed to fetch verification code from Twitter Web App HTML.')
            return schemas.TwitterAPIResult(
                is_success = False,
                detail = 'Challenge 情報の取得に失敗しました。Twitter Web App の HTML から検証コードを取得できませんでした。',
            )
        verification_code = cast(str, meta_tag['content'])

        # HTML からチャレンジコードを取得
        challenge_code_match = re.search(r'"ondemand.s":"(\w+)"', twitter_web_app_html_text)
        if not challenge_code_match:
            logging.error('[TwitterGraphQLAPI] Failed to fetch challenge code from Twitter Web App HTML.')
            return schemas.TwitterAPIResult(
                is_success = False,
                detail = 'Challenge 情報の取得に失敗しました。Twitter Web App の HTML からチャレンジコードを取得できませんでした。',
            )
        challenge_code = challenge_code_match.group(1)

        # HTML から vendor コードを取得
        vendor_code_match = re.search(r'vendor\.(\w+)\.js["\']', twitter_web_app_html_text)
        if not vendor_code_match:
            logging.error('[TwitterGraphQLAPI] Failed to fetch vendor code from Twitter Web App HTML.')
            return schemas.TwitterAPIResult(
                is_success = False,
                detail = 'Challenge 情報の取得に失敗しました。Twitter Web App の HTML から vendor コードを取得できませんでした。',
            )
        vendor_code = vendor_code_match.group(1)

        # HTML からアニメーション SVG の outerHTML を取得
        challenge_animation_svg_codes = [str(svg) for svg in soup.select('svg[id^="loading-x"]')]

        # Challenge 情報を取得
        ## JavaScript リクエスト用のヘッダーに差し替えるのが重要
        challenge_js_code_response = await self.curl_session.get(
            url = f'https://abs.twimg.com/responsive-web/client-web/ondemand.s.{challenge_code}a.js',
            headers = self.js_headers_dict,
        )
        if challenge_js_code_response.status_code != 200:
            logging.error('[TwitterGraphQLAPI] Failed to fetch challenge code from Twitter Web App HTML.')
            return schemas.TwitterAPIResult(
                is_success = False,
                detail = (
                    f'Challenge 情報の取得に失敗しました。Twitter Web App のチャレンジコードからチャレンジコードを取得できませんでした。'
                    f'(HTTP Error {challenge_js_code_response.status_code})'
                ),
            )
        challenge_js_code = challenge_js_code_response.text

        # Challenge 解決時に必要になる vendor コードを取得
        vendor_js_code_response = await self.curl_session.get(
            url = f'https://abs.twimg.com/responsive-web/client-web/vendor.{vendor_code}.js',
            headers = self.js_headers_dict,
        )
        if vendor_js_code_response.status_code != 200:
            logging.error('[TwitterGraphQLAPI] Failed to fetch vendor script from Twitter Web App HTML.')
            return schemas.TwitterAPIResult(
                is_success = False,
                detail = (
                    'Challenge 情報の取得に失敗しました。Twitter Web App の HTML から vendor コードを取得できませんでした。'
                    f'(HTTP Error {vendor_js_code_response.status_code})'
                ),
            )
        vendor_js_code = vendor_js_code_response.text

        # この時点でリクエスト自体は成功しているはずなので、curl-cffi のセッションが持つ Cookie を DB に反映する
        ## HTML リクエスト時に Cookie が更新される可能性があるため、ここで変更された可能性がある Cookie を永続化する
        await self.persistCookies()

        challenge_data = schemas.TwitterChallengeData(
            is_success = True,
            detail = 'Twitter Web App の Challenge 情報を取得しました。',
            endpoint_infos = self.ENDPOINT_INFOS,
            verification_code = verification_code,
            challenge_js_code = challenge_js_code,
            vendor_js_code = vendor_js_code,
            challenge_animation_svg_codes = challenge_animation_svg_codes,
        )

        # Challenge 情報をキャッシュに保存
        ## 短期間に何回もアクセスされた場合でも、同一の Challenge 情報が返される (そうした方がより精度高く偽装できるはず)
        self.__challenge_info_cache[self.twitter_account.screen_name] = (time.time(), challenge_data)

        return challenge_data


    async def invokeGraphQLAPI(self,
        endpoint_info: schemas.TwitterGraphQLAPIEndpointInfo,
        variables: dict[str, Any],
        x_client_transaction_id: str | None = None,
        error_message_prefix: str = 'Twitter API の操作に失敗しました。',
    ) -> dict[str, Any] | str:
        """
        Twitter Web App の GraphQL API に HTTP リクエストを送信する
        実際には GraphQL と言いつつペイロードで JSON を渡しているので謎… (本当に GraphQL なのか？)

        Args:
            endpoint_info (schemas.TwitterGraphQLAPIEndpointInfo): GraphQL API の各エンドポイントごとに固有の静的な情報
            variables (dict[str, Any]): GraphQL API へのリクエストパラメータ (ペイロードのうち "variables" の部分)
            x_client_transaction_id (str | None, optional): ブラウザ側で算出して API リクエストヘッダーに添付された X-Client-Transaction-ID ヘッダーの値
            error_message_prefix (str, optional): エラー発生時に付与する prefix (例: 'ツイートの送信に失敗しました。')

        Returns:
            dict[str, Any] | str: GraphQL API のレスポンス (失敗時は日本語のエラーメッセージを返す)
        """

        # リクエストヘッダーを組み立てる
        ## X-Client-Transaction-ID は指定されている場合のみ付与する
        headers = self.graphql_headers_dict.copy()
        if x_client_transaction_id is not None:
            headers['x-client-transaction-id'] = x_client_transaction_id
            logging.debug_simple(f'[TwitterGraphQLAPI][{endpoint_info.endpoint}] X-Client-Transaction-ID: {x_client_transaction_id}')

        # CreateTweet / CreateRetweet エンドポイントのみ、Bearer トークンを旧 TweetDeck / 現 X Pro 用のものに差し替える
        ## 旧 TweetDeck 用 Bearer トークン自体は現在も X Pro 用として使われているからか (ただし URL は https://pro.x.com/i/graphql/ 配下) 、
        ## 2024/08/08 現在では Twitter Web App 用 Bearer トークンでリクエストした際と異なり、スパム判定によるツイート失敗がほとんどないメリットがある
        ## なぜこの Bearer トークンが使えるのかはよく分からないが、実際 OldTweetDeck でも同様の実装で数ヶ月運用されている
        ## 今後対策される可能性もなくもないが実装時点ではうまく機能しているので、推定ユーザー数万人を有する OldTweetDeck の実装に合わせる
        ## 2025/05/13 現在は FavoriteTweet / SearchTimeline も同様の対応が必要
        ## UnfavoriteTweet はこの対応をしなくても動作するが、対になる操作のためリストに入れている
        ## ref: https://github.com/dimdenGD/OldTweetDeck/blob/v4.0.3/src/interception.js#L1208-L1219
        ## ref: https://github.com/dimdenGD/OldTweetDeck/blob/v4.0.3/src/interception.js#L1273-L1292
        ## ref: https://github.com/dimdenGD/OldTweetDeck/commit/7afe6fce041943f32838825660815588c0f501ed
        if endpoint_info.endpoint in [
            'CreateTweet',
            'CreateRetweet',
            'FavoriteTweet',
            'UnfavoriteTweet',
            'SearchTimeline',
        ]:
            headers['authorization'] = self.cookie_session_user_handler.TWEETDECK_BEARER_TOKEN

        # Twitter GraphQL API に HTTP リクエストを送信する
        try:
            if endpoint_info.method == 'POST':
                # POST の場合はペイロードを組み立てて JSON にして渡す
                ## features が存在しない API のときは features を省略する
                if endpoint_info.features is not None:
                    payload = {
                        'variables': variables,
                        'features': endpoint_info.features,
                        'queryId': endpoint_info.query_id,  # クエリ ID も JSON に含める必要がある
                    }
                else:
                    payload = {
                        'variables': variables,
                        'queryId': endpoint_info.query_id,  # クエリ ID も JSON に含める必要がある
                    }
                # GraphQL API リクエスト用のヘッダーに差し替えるのが重要
                response = await self.curl_session.post(
                    url = 'https://x.com' + endpoint_info.path,
                    json = payload,
                    headers = headers,
                )
            elif endpoint_info.method == 'GET':
                # GET の場合は queryId はパスに、variables と features はクエリパラメータに JSON エンコードした上で渡す
                ## features が存在しない API のときは features を省略する
                if endpoint_info.features is not None:
                    params = {
                        'variables': json.dumps(variables, ensure_ascii=False),
                        'features': json.dumps(endpoint_info.features, ensure_ascii=False),
                    }
                else:
                    params = {
                        'variables': json.dumps(variables, ensure_ascii=False),
                    }
                # GraphQL API リクエスト用のヘッダーに差し替えるのが重要
                response = await self.curl_session.get(
                    url = 'https://x.com' + endpoint_info.path,
                    params = params,
                    headers = headers,
                )
            else:
                raise ValueError(f'Invalid method: {endpoint_info.method}')

        # 接続エラー（サーバーメンテナンスやタイムアウトなど）
        except (TimeoutError, curl_requests.RequestsError):
            logging.error('[TwitterGraphQLAPI] Failed to connect to Twitter GraphQL API.')
            # return 'Failed to connect to Twitter GraphQL API'
            return error_message_prefix + 'Twitter API に接続できませんでした。'

        # この時点でリクエスト自体は成功しているはずなので、curl-cffi のセッションが持つ Cookie を DB に反映する
        ## 基本 API リクエストでは Cookie は更新されないはずだが、不審がられないように念のためブラウザ同様リクエストごとに永続化する
        await self.persistCookies()

        # HTTP ステータスコードが 200 系以外の場合
        if not (200 <= response.status_code < 300):
            logging.error(f'[TwitterGraphQLAPI] Failed to invoke GraphQL API. (HTTP Error {response.status_code})')
            logging.error(f'[TwitterGraphQLAPI] Response: {response.text}')
            return error_message_prefix + f'Twitter API から HTTP {response.status_code} エラーが返されました。'

        # JSON でないレスポンスが返ってきた場合
        ## charset=utf-8 が付いている場合もあるので完全一致ではなく部分一致で判定
        if 'application/json' not in response.headers['Content-Type']:
            logging.error('[TwitterGraphQLAPI] Response is not JSON.')
            return error_message_prefix + 'Twitter API から不正なレスポンスが返されました。'

        # レスポンスを JSON としてパース
        try:
            response_json = response.json()
        except Exception as ex:
            logging.error('[TwitterGraphQLAPI] Failed to parse response as JSON:', exc_info=ex)
            return error_message_prefix + 'Twitter API のレスポンスを JSON としてパースできませんでした。'

        # API レスポンスにエラーが含まれていて、かつ data キーが存在しない場合
        ## API レスポンスは Twitter の仕様変更で変わりうるので、ここで判定されなかったと言ってエラーでないとは限らない
        ## なぜか正常にレスポンスが含まれているのにエラーも返ってくる場合があるので、その場合は（致命的な）エラーではないと判断する
        if 'errors' in response_json and 'data' not in response_json:

            # Twitter API のエラーコードとエラーメッセージを取得
            ## このエラーコードは API v1.1 の頃と変わっていない
            response_error_code = response_json['errors'][0]['code']
            response_error_message = response_json["errors"][0]["message"]

            # 想定外のエラーコードが返ってきた場合のエラーメッセージ
            alternative_error_message = f'Code: {response_error_code} / Message: {response_error_message}'
            logging.error(f'[TwitterGraphQLAPI] Failed to invoke GraphQL API ({alternative_error_message})')

            # エラーコードに対応するエラーメッセージを返し、対応するものがない場合は alternative_error_message を返す
            return error_message_prefix + self.ERROR_MESSAGES.get(response_error_code, alternative_error_message)

        # API レスポンスにエラーが含まれていないが、'data' キーが存在しない場合
        ## 実装時点の GraphQL API は必ず成功時は 'data' キーの下にレスポンスが格納されるはず
        ## もし 'data' キーが存在しない場合は、API 仕様が変更されている可能性がある
        elif 'data' not in response_json:
            logging.error('[TwitterGraphQLAPI] Response does not have "data" key.')
            return error_message_prefix + 'Twitter API のレスポンスに "data" キーが存在しません。開発者に修正を依頼してください。'

        # ここまで来たら (中身のデータ構造はともかく) API レスポンスの取得には成功しているはず
        return response_json['data']


    async def createTweet(self,
        tweet: str,
        media_ids: list[str] = [],
        x_client_transaction_id: str | None = None,
    ) -> schemas.PostTweetResult | schemas.TwitterAPIResult:
        """
        ツイートを送信する

        Args:
            tweet (str): ツイート内容
            media_ids (list[str], optional): 添付するメディアの ID のリスト (デフォルトは空リスト)
            x_client_transaction_id (str, optional): ブラウザ側で算出して API リクエストヘッダーに添付された X-Client-Transaction-ID ヘッダーの値

        Returns:
            schemas.PostTweetResult | schemas.TwitterAPIResult: ツイートの送信結果
        """

        # まだ排他制御用のロックが存在しない場合は初期化
        screen_name = self.twitter_account.screen_name
        if screen_name not in self.__tweet_locks:
            self.__tweet_locks[screen_name] = _TweetLockInfo(lock=asyncio.Lock(), last_tweet_time=0.0)

        # ツイートの最小送信間隔を守るためにロックを取得
        async with self.__tweet_locks[screen_name]['lock']:

            # 最後のツイート時刻から最小送信間隔を経過していない場合は待機
            current_time = time.time()
            last_tweet_time = self.__tweet_locks[screen_name]['last_tweet_time']
            wait_time = max(0, self.MINIMUM_TWEET_INTERVAL - (current_time - last_tweet_time))
            if wait_time > 0:
                await asyncio.sleep(wait_time)

            # 画像の media_id をリストに格納 (画像がない場合は空のリストになる)
            media_entities: list[dict[str, Any]] = []
            for media_id in media_ids:
                media_entities.append({
                    'media_id': media_id,
                    'tagged_users': []
                })

            # Twitter GraphQL API にリクエスト
            response = await self.invokeGraphQLAPI(
                endpoint_info = self.ENDPOINT_INFOS['CreateTweet'],
                variables = {
                    'tweet_text': tweet,
                    'dark_request': False,
                    'media': {
                        'media_entities': media_entities,
                        'possibly_sensitive': False,
                    },
                    'semantic_annotation_ids': [],
                    'disallowed_reply_options': None,
                },
                x_client_transaction_id = x_client_transaction_id,
                error_message_prefix = 'ツイートの送信に失敗しました。',
            )

            # 最後のツイート時刻を更新
            self.__tweet_locks[screen_name]['last_tweet_time'] = time.time()

            # 戻り値が str の場合、ツイートの送信に失敗している (エラーメッセージが返ってくる)
            if isinstance(response, str):
                logging.error(f'[TwitterGraphQLAPI] Failed to create tweet: {response}')
                return schemas.TwitterAPIResult(
                    is_success = False,
                    detail = response,  # エラーメッセージをそのまま返す
                )

            # おそらくツイートに成功しているはずなので、可能であれば送信したツイートの ID を取得
            tweet_id: str
            try:
                tweet_id = str(response['create_tweet']['tweet_results']['result']['rest_id'])
            except Exception as ex:
                # API レスポンスが変わっているなどでツイート ID を取得できなかった
                logging.error('[TwitterGraphQLAPI] Failed to get tweet ID:', exc_info=ex)
                logging.error(f'[TwitterGraphQLAPI] Response: {response}')
                return schemas.PostTweetResult(
                    is_success = False,
                    detail = 'ツイートを送信しましたが、ツイート ID を取得できませんでした。開発者に修正を依頼してください。',
                    tweet_url = 'https://twitter.com/i/status/__error__',
                )

            return schemas.PostTweetResult(
                is_success = True,
                detail = 'ツイートを送信しました。',
                tweet_url = f'https://twitter.com/i/status/{tweet_id}',
            )


    async def createRetweet(self, tweet_id: str, x_client_transaction_id: str | None = None) -> schemas.TwitterAPIResult:
        """
        ツイートをリツイートする

        Args:
            tweet_id (str): リツイートするツイートの ID
            x_client_transaction_id (str, optional): ブラウザ側で算出して API リクエストヘッダーに添付された X-Client-Transaction-ID ヘッダーの値

        Returns:
            schemas.TwitterAPIResult: リツイートの結果
        """

        # Twitter GraphQL API にリクエスト
        response = await self.invokeGraphQLAPI(
            endpoint_info = self.ENDPOINT_INFOS['CreateRetweet'],
            variables = {
                'tweet_id': tweet_id,
                'dark_request': False,
            },
            x_client_transaction_id = x_client_transaction_id,
            error_message_prefix = 'リツイートに失敗しました。',
        )

        # 戻り値が str の場合、リツイートに失敗している (エラーメッセージが返ってくる)
        if isinstance(response, str):
            logging.error(f'[TwitterGraphQLAPI] Failed to create retweet: {response}')
            return schemas.TwitterAPIResult(
                is_success = False,
                detail = response,  # エラーメッセージをそのまま返す
            )

        return schemas.TwitterAPIResult(
            is_success = True,
            detail = 'リツイートしました。',
        )


    async def deleteRetweet(self, tweet_id: str, x_client_transaction_id: str | None = None) -> schemas.TwitterAPIResult:
        """
        ツイートのリツイートを取り消す

        Args:
            tweet_id (str): リツイートを取り消すツイートの ID
            x_client_transaction_id (str, optional): ブラウザ側で算出して API リクエストヘッダーに添付された X-Client-Transaction-ID ヘッダーの値

        Returns:
            schemas.TwitterAPIResult: リツイートの取り消し結果
        """

        # Twitter GraphQL API にリクエスト
        response = await self.invokeGraphQLAPI(
            endpoint_info = self.ENDPOINT_INFOS['DeleteRetweet'],
            variables = {
                'source_tweet_id': tweet_id,
                'dark_request': False,
            },
            x_client_transaction_id = x_client_transaction_id,
            error_message_prefix = 'リツイートの取り消しに失敗しました。',
        )

        # 戻り値が str の場合、リツイートの取り消しに失敗している (エラーメッセージが返ってくる)
        if isinstance(response, str):
            logging.error(f'[TwitterGraphQLAPI] Failed to delete retweet: {response}')
            return schemas.TwitterAPIResult(
                is_success = False,
                detail = response,  # エラーメッセージをそのまま返す
            )

        return schemas.TwitterAPIResult(
            is_success = True,
            detail = 'リツイートを取り消ししました。',
        )


    async def favoriteTweet(self, tweet_id: str, x_client_transaction_id: str | None = None) -> schemas.TwitterAPIResult:
        """
        ツイートをいいねする

        Args:
            tweet_id (str): いいねするツイートの ID
            x_client_transaction_id (str, optional): ブラウザ側で算出して API リクエストヘッダーに添付された X-Client-Transaction-ID ヘッダーの値

        Returns:
            schemas.TwitterAPIResult: いいねの結果
        """

        # Twitter GraphQL API にリクエスト
        response = await self.invokeGraphQLAPI(
            endpoint_info = self.ENDPOINT_INFOS['FavoriteTweet'],
            variables = {
                'tweet_id': tweet_id,
            },
            x_client_transaction_id = x_client_transaction_id,
            error_message_prefix = 'いいねに失敗しました。',
        )

        # 戻り値が str の場合、いいねに失敗している (エラーメッセージが返ってくる)
        if isinstance(response, str):
            logging.error(f'[TwitterGraphQLAPI] Failed to favorite tweet: {response}')
            return schemas.TwitterAPIResult(
                is_success = False,
                detail = response,  # エラーメッセージをそのまま返す
            )

        return schemas.TwitterAPIResult(
            is_success = True,
            detail = 'いいねしました。',
        )


    async def unfavoriteTweet(self, tweet_id: str, x_client_transaction_id: str | None = None) -> schemas.TwitterAPIResult:
        """
        ツイートのいいねを取り消す

        Args:
            tweet_id (str): いいねを取り消すツイートの ID
            x_client_transaction_id (str, optional): ブラウザ側で算出して API リクエストヘッダーに添付された X-Client-Transaction-ID ヘッダーの値

        Returns:
            schemas.TwitterAPIResult: いいねの取り消し結果
        """

        # Twitter GraphQL API にリクエスト
        response = await self.invokeGraphQLAPI(
            endpoint_info = self.ENDPOINT_INFOS['UnfavoriteTweet'],
            variables = {
                'tweet_id': tweet_id,
            },
            x_client_transaction_id = x_client_transaction_id,
            error_message_prefix = 'いいねの取り消しに失敗しました。',
        )

        # 戻り値が str の場合、いいねの取り消しに失敗している (エラーメッセージが返ってくる)
        if isinstance(response, str):
            logging.error(f'[TwitterGraphQLAPI] Failed to unfavorite tweet: {response}')
            return schemas.TwitterAPIResult(
                is_success = False,
                detail = response,  # エラーメッセージをそのまま返す
            )

        return schemas.TwitterAPIResult(
            is_success = True,
            detail = 'いいねを取り消しました。',
        )


    def __getCursorIDFromTimelineAPIResponse(self, response: dict[str, Any], cursor_type: Literal['Top', 'Bottom']) -> str | None:
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
            instructions = response.get('search_by_raw_query', {}).get('search_timeline', {}).get('timeline', {}).get('instructions', [])
        # それ以外のレスポンス (通常あり得ないため、ここに到達した場合はレスポンス構造が変わった可能性が高い)
        else:
            instructions = []
            logging.warning(f'[TwitterGraphQLAPI] Unknown timeline response format: {response}')

        for instruction in instructions:
            if instruction.get('type') == 'TimelineAddEntries':
                entries = instruction.get('entries', [])
                for entry in entries:
                    content = entry.get('content', {})
                    if (content.get('entryType') == 'TimelineTimelineCursor' and \
                        content.get('cursorType') == cursor_type):
                        return content.get('value')
                    # Bottom 指定時、たまに通常 cursorType が Bottom になるところ Gap になっている場合がある
                    # その場合は Bottom の Cursor として解釈する
                    elif (content.get('entryType') == 'TimelineTimelineCursor' and \
                        content.get('cursorType') == 'Gap' and cursor_type == 'Bottom'):
                        return content.get('value')
            elif instruction.get('type') == 'TimelineReplaceEntry':
                entry = instruction.get('entry', {})
                content = entry.get('content', {})
                if (content.get('entryType') == 'TimelineTimelineCursor' and \
                    content.get('cursorType') == cursor_type):
                    return content.get('value')
                # Bottom 指定時、たまに通常 cursorType が Bottom になるところ Gap になっている場合がある
                # その場合は Bottom の Cursor として解釈する
                elif (content.get('entryType') == 'TimelineTimelineCursor' and \
                    content.get('cursorType') == 'Gap' and cursor_type == 'Bottom'):
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
            """ API レスポンスから取得したツイート情報を schemas.Tweet に変換する """

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
                    logging.warning(f'[TwitterGraphQLAPI] Quoted tweet not found: {raw_tweet_object.get("rest_id", "unknown")}')
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
                        mp4_variants: list[dict[str, Any]] = list(filter(lambda variant: variant['content_type'] == 'video/mp4', media['video_info']['variants']))
                        if len(mp4_variants) > 0:
                            highest_bitrate_variant: dict[str, Any] = max(
                                mp4_variants,
                                key = lambda variant: int(variant['bitrate']) if 'bitrate' in variant else 0,  # type: ignore
                            )
                            movie_url = str(highest_bitrate_variant['url']) if 'url' in highest_bitrate_variant else None

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
                id = raw_tweet_object['legacy']['id_str'],
                created_at = datetime.strptime(raw_tweet_object['legacy']['created_at'], '%a %b %d %H:%M:%S %z %Y').astimezone(ZoneInfo('Asia/Tokyo')),
                user = schemas.TweetUser(
                    id = raw_tweet_object['core']['user_results']['result']['rest_id'],
                    name = raw_tweet_object['core']['user_results']['result']['core']['name'],
                    screen_name = raw_tweet_object['core']['user_results']['result']['core']['screen_name'],
                    # (ランダムな文字列)_normal.jpg だと画像サイズが小さいので、(ランダムな文字列).jpg に置換
                    icon_url = raw_tweet_object['core']['user_results']['result']['avatar']['image_url'].replace('_normal', ''),
                ),
                text = expanded_text,
                lang = raw_tweet_object['legacy']['lang'],
                via = re.sub(r'<.+?>', '', raw_tweet_object['source']),
                image_urls = image_urls if len(image_urls) > 0 else None,
                movie_url = movie_url,
                retweet_count = raw_tweet_object['legacy']['retweet_count'],
                favorite_count = raw_tweet_object['legacy']['favorite_count'],
                retweeted = raw_tweet_object['legacy']['retweeted'],
                favorited = raw_tweet_object['legacy']['favorited'],
                retweeted_tweet = retweeted_tweet,
                quoted_tweet = quoted_tweet,
            )

        # HomeLatestTimeline からのレスポンス
        if 'home' in response:
            instructions = response.get('home', {}).get('home_timeline_urt', {}).get('instructions', [])
        # SearchTimeline からのレスポンス
        elif 'search_by_raw_query' in response:
            instructions = response.get('search_by_raw_query', {}).get('search_timeline', {}).get('timeline', {}).get('instructions', [])
        # それ以外のレスポンス (通常あり得ないため、ここに到達した場合はレスポンス構造が変わった可能性が高い)
        else:
            instructions = []
            logging.warning(f'[TwitterGraphQLAPI] Unknown timeline response format: {response}')

        tweets: list[schemas.Tweet] = []
        for instruction in instructions:
            if instruction.get('type') == 'TimelineAddEntries':
                entries = instruction.get('entries', [])
                for entry in entries:
                    # entryId が promoted- から始まるツイートは広告ツイートなので除外
                    if entry.get('entryId', '').startswith('promoted-'):
                        continue
                    content = entry.get('content', {})
                    if content.get('entryType') == 'TimelineTimelineItem' and \
                    content.get('itemContent', {}).get('itemType') == 'TimelineTweet':
                        tweet_results = content.get('itemContent', {}).get('tweet_results', {}).get('result')
                        if tweet_results and tweet_results.get('__typename') in ['Tweet', 'TweetWithVisibilityResults']:
                            tweets.append(format_tweet(tweet_results))

        return tweets


    async def homeLatestTimeline(self,
        cursor_id: str | None = None,
        count: int = 20,
        x_client_transaction_id: str | None = None,
    ) -> schemas.TimelineTweetsResult | schemas.TwitterAPIResult:
        """
        タイムラインの最新ツイートを取得する
        一応 API 上は取得するツイート数を指定できることになっているが、検索と異なり実際に返ってくるツイート数は保証されてないっぽい (100 件返ってくることもある)

        Args:
            cursor_id (str | None, optional): 次のページを取得するためのカーソル ID (デフォルトは None)
            count (int, optional): 取得するツイート数 (デフォルトは 20)
            x_client_transaction_id (str, optional): ブラウザ側で算出して API リクエストヘッダーに添付された X-Client-Transaction-ID ヘッダーの値

        Returns:
            schemas.TimelineTweets | schemas.TwitterAPIResult: 検索結果
        """

        # variables の挿入順序を Twitter Web App に厳密に合わせるためにこのような実装としている
        variables: dict[str, Any] = {}
        variables['count'] = count
        if cursor_id is not None:
            variables['cursor'] = cursor_id
        variables['includePromotedContent'] = True
        variables['latestControlAvailable'] = True
        if cursor_id is None:
            variables['requestContext'] = 'launch'
        variables['seenTweetIds'] = []  # おそらく実際に表示されたツイートの ID を入れるキーだが、取得できないので空リストを入れておく

        # Twitter GraphQL API にリクエスト
        response = await self.invokeGraphQLAPI(
            endpoint_info = self.ENDPOINT_INFOS['HomeLatestTimeline'],
            variables = variables,
            x_client_transaction_id = x_client_transaction_id,
            error_message_prefix = 'タイムラインの取得に失敗しました。',
        )

        # 戻り値が str の場合、タイムラインの取得に失敗している (エラーメッセージが返ってくる)
        if isinstance(response, str):
            logging.error(f'[TwitterGraphQLAPI] Failed to fetch timeline: {response}')
            return schemas.TwitterAPIResult(
                is_success = False,
                detail = response,  # エラーメッセージをそのまま返す
            )

        # まずはカーソル ID を取得
        ## カーソル ID が取得できなかった場合は仕様変更があったとみなし、エラーを返す
        next_cursor_id = self.__getCursorIDFromTimelineAPIResponse(response, 'Top')  # 現在よりも新しいツイートを取得するためのカーソル ID
        previous_cursor_id = self.__getCursorIDFromTimelineAPIResponse(response, 'Bottom')  # 現在よりも過去のツイートを取得するためのカーソル ID
        if next_cursor_id is None or previous_cursor_id is None:
            logging.error('[TwitterGraphQLAPI] Failed to fetch timeline: Cursor ID not found')
            return schemas.TwitterAPIResult(
                is_success = False,
                detail = 'タイムラインの取得に失敗しました。カーソル ID を取得できませんでした。開発者に修正を依頼してください。',
            )

        # ツイートリストを取得
        ## 取得できなかった場合、あるいは単純に一致する結果がない場合は空のリストになる
        tweets = self.__getTweetsFromTimelineAPIResponse(response)

        return schemas.TimelineTweetsResult(
            is_success = True,
            detail = 'タイムラインを取得しました。',
            next_cursor_id = next_cursor_id,
            previous_cursor_id = previous_cursor_id,
            tweets = tweets,
        )


    async def searchTimeline(self,
        search_type: Literal['Top', 'Latest'],
        query: str,
        cursor_id: str | None = None,
        count: int = 20,
        x_client_transaction_id: str | None = None,
    ) -> schemas.TimelineTweetsResult | schemas.TwitterAPIResult:
        """
        ツイートを検索する

        Args:
            search_type (Literal['Top', 'Latest']): 検索タイプ (Top: トップツイート, Latest: 最新ツイート)
            query (str): 検索クエリ
            cursor_id (str | None, optional): 次のページを取得するためのカーソル ID (デフォルトは None)
            count (int, optional): 取得するツイート数 (デフォルトは 20)
            x_client_transaction_id (str, optional): ブラウザ側で算出して API リクエストヘッダーに添付された X-Client-Transaction-ID ヘッダーの値

        Returns:
            schemas.TimelineTweets | schemas.TwitterAPIResult: 検索結果
        """

        # variables の挿入順序を Twitter Web App に厳密に合わせるためにこのような実装としている
        variables: dict[str, Any] = {}
        variables['rawQuery'] = query.strip() + ' exclude:replies lang:ja'
        variables['count'] = count
        if cursor_id is not None:
            variables['cursor'] = cursor_id
        variables['querySource'] = 'typed_query'  # Twitter Web App で検索すると typed_query になることが多いのでそれに合わせる
        variables['product'] = search_type  # 検索タイプに Top か Latest を指定する
        variables['withGrokTranslatedBio'] = False  # Twitter Web App の挙動に合わせて設定

        # Twitter GraphQL API にリクエスト
        response = await self.invokeGraphQLAPI(
            endpoint_info = self.ENDPOINT_INFOS['SearchTimeline'],
            variables = variables,
            x_client_transaction_id = x_client_transaction_id,
            error_message_prefix = 'ツイートの検索に失敗しました。',
        )

        # 戻り値が str の場合、ツイートの検索に失敗している (エラーメッセージが返ってくる)
        if isinstance(response, str):
            logging.error(f'[TwitterGraphQLAPI] Failed to search tweets: {response}')
            return schemas.TwitterAPIResult(
                is_success = False,
                detail = response,  # エラーメッセージをそのまま返す
            )

        # まずはカーソル ID を取得
        ## カーソル ID が取得できなかった場合は仕様変更があったとみなし、エラーを返す
        next_cursor_id = self.__getCursorIDFromTimelineAPIResponse(response, 'Top')  # 現在よりも新しいツイートを取得するためのカーソル ID
        previous_cursor_id = self.__getCursorIDFromTimelineAPIResponse(response, 'Bottom')  # 現在よりも過去のツイートを取得するためのカーソル ID
        if next_cursor_id is None or previous_cursor_id is None:
            logging.error('[TwitterGraphQLAPI] Failed to search tweets: Cursor ID not found')
            return schemas.TwitterAPIResult(
                is_success = False,
                detail = 'ツイートの検索に失敗しました。カーソル ID を取得できませんでした。開発者に修正を依頼してください。',
            )

        # ツイートリストを取得
        ## 取得できなかった場合、あるいは単純に一致する結果がない場合は空のリストになる
        tweets = self.__getTweetsFromTimelineAPIResponse(response)

        return schemas.TimelineTweetsResult(
            is_success = True,
            detail = 'ツイートを検索しました。',
            next_cursor_id = next_cursor_id,
            previous_cursor_id = previous_cursor_id,
            tweets = tweets,
        )
