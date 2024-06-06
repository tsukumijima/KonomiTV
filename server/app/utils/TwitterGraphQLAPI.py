
import asyncio
import httpx
import json
import re
import time
from datetime import datetime
from typing import Any, ClassVar, Literal, TypedDict
from zoneinfo import ZoneInfo

from app import logging
from app import schemas
from app.models.TwitterAccount import TwitterAccount


class TweetLockInfo(TypedDict):
    lock: asyncio.Lock
    last_tweet_time: float


class TwitterGraphQLAPI:
    """
    Twitter Web App で利用されている GraphQL API の薄いラッパー
    外部ライブラリを使うよりすべて自前で書いたほうが柔軟に対応でき凍結リスクを回避できると考え実装した
    以下に実装されているリクエストペイロードなどはすべて実装時点の Twitter Web App が実際に送信するリクエストを可能な限り模倣したもの
    メソッド名は概ね GraphQL API でのエンドポイント名に対応している
    """

    # Twitter API のエラーコードとエラーメッセージの対応表
    ## 実際に返ってくる可能性があるものだけ
    ## ref: https://developer.twitter.com/ja/docs/basics/response-codes
    ERROR_MESSAGES = {
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

    # ツイートの最小送信間隔 (秒)
    MINIMUM_TWEET_INTERVAL = 20  # 必ずアカウントごとに 20 秒以上間隔を空けてツイートする

    # アカウントごとにロックと最後のツイート時刻を管理する辞書 (ツイート送信時の排他制御用)
    __tweet_locks: ClassVar[dict[str, TweetLockInfo]] = {}


    def __init__(self, twitter_account: TwitterAccount) -> None:
        """
        Twitter GraphQL API クライアントを初期化する

        Args:
            twitter_account: Twitter アカウントのモデル
        """

        self.twitter_account = twitter_account

        # Chrome への偽装用 HTTP リクエストヘッダーと Cookie を取得
        ## User-Agent ヘッダーも Chrome に偽装されている
        cookie_session_user_handler = self.twitter_account.getTweepyAuthHandler()
        headers_dict = cookie_session_user_handler.get_graphql_api_headers()
        cookies_dict = cookie_session_user_handler.get_cookies_as_dict()

        # httpx の非同期 HTTP クライアントのインスタンスを作成
        ## 可能な限り Chrome からのリクエストに偽装するため、app.constants.HTTPX_CLIENT は使わずに独自のインスタンスを作成する
        self.httpx_client = httpx.AsyncClient(
            ## リクエストヘッダーと Cookie を設定
            headers = headers_dict,
            cookies = cookies_dict,
            ## リダイレクトを追跡する
            follow_redirects = True,
            ## 可能な限り Chrome からのリクエストに偽装するため、HTTP/1.1 ではなく明示的に HTTP/2 で接続する
            http2 = True,
        )


    async def invokeGraphQLAPI(self,
        method: Literal['GET', 'POST'],
        query_id: str,
        endpoint: str,
        variables: dict[str, Any],
        features: dict[str, bool] | None = None,
        error_message_prefix: str = 'Twitter API の操作に失敗しました。',
    ) -> dict[str, Any] | str:
        """
        Twitter Web App の GraphQL API に HTTP リクエストを送信する
        実際には GraphQL と言いつつペイロードで JSON を渡しているので謎… (本当に GraphQL なのか？)
        クエリ ID はおそらく API のバージョン (?) を示しているらしい謎の値で、数週間単位で変更されうる (定期的に追従が必要)

        Args:
            query_id (str): GraphQL API のクエリ ID
            endpoint (str): GraphQL API のエンドポイント (例: CreateTweet)
            variables (dict[str, Any]): GraphQL API のクエリに渡すペイロードのうち variables 以下の部分 (基本 API に送信するパラメータのはず)
            features (dict[str, bool] | None): GraphQL API のクエリに渡すペイロードのうち features 以下の部分 (頻繁に変わる謎のフラグが入る)
            error_message_prefix (str, optional): エラー発生時に付与する prefix (例: 'ツイートの送信に失敗しました。')

        Returns:
            dict[str, Any] | str: GraphQL API のレスポンス (失敗時は日本語のエラーメッセージを返す)
        """

        # Twitter GraphQL API に HTTP リクエストを送信する
        try:
            async with self.httpx_client:
                if method == 'POST':
                    # POST の場合はペイロードを組み立てて JSON にして渡す
                    ## features が存在しない API のときは features を省略する
                    if features is not None:
                        payload = {
                            'variables': variables,
                            'features': features,
                            'queryId': query_id,  # クエリ ID も JSON に含める必要がある
                        }
                    else:
                        payload = {
                            'variables': variables,
                            'queryId': query_id,  # クエリ ID も JSON に含める必要がある
                        }
                    response = await self.httpx_client.post(
                        url = f'https://x.com/i/api/graphql/{query_id}/{endpoint}',
                        json = payload,
                    )
                elif method == 'GET':
                    # GET の場合は queryId はパスに、variables と features はクエリパラメータに JSON エンコードした上で渡す
                    ## features が存在しない API のときは features を省略する
                    if features is not None:
                        params = {
                            'variables': json.dumps(variables, ensure_ascii=False),
                            'features': json.dumps(features, ensure_ascii=False),
                        }
                    else:
                        params = {
                            'variables': json.dumps(variables, ensure_ascii=False),
                        }
                    response = await self.httpx_client.get(
                        url = f'https://x.com/i/api/graphql/{query_id}/{endpoint}',
                        params = params,
                    )

        # 接続エラー（サーバーメンテナンスやタイムアウトなど）
        except (httpx.NetworkError, httpx.TimeoutException):
            logging.error('[TwitterAPI] Failed to connect to Twitter GraphQL API')
            # return 'Failed to connect to Twitter GraphQL API'
            return error_message_prefix + 'Twitter API に接続できませんでした。'

        # この時点でリクエスト自体は成功しているはずなので、httpx のセッションが持つ Cookie を DB に反映する
        ## 基本 API リクエストでは Cookie は更新されないはずだが、不審がられないように念のためブラウザ同様リクエストごとに永続化する
        session_cookies_dict = dict(self.httpx_client.cookies)
        self.twitter_account.access_token_secret = json.dumps(session_cookies_dict, ensure_ascii=False)
        await self.twitter_account.save()

        # HTTP ステータスコードが 200 系以外の場合
        if not (200 <= response.status_code < 300):
            logging.error(f'[TwitterAPI] Failed to invoke GraphQL API (HTTP {response.status_code})')
            return error_message_prefix + f'Twitter API から HTTP {response.status_code} エラーが返されました。'

        # JSON でないレスポンスが返ってきた場合
        ## charset=utf-8 が付いている場合もあるので完全一致ではなく部分一致で判定
        if 'application/json' not in response.headers['Content-Type']:
            logging.error('[TwitterAPI] Response is not JSON')
            return error_message_prefix + 'Twitter API から不正なレスポンスが返されました。'

        # レスポンスを JSON としてパース
        try:
            response_json = response.json()
        except Exception:
            logging.error('[TwitterAPI] Failed to parse response as JSON')
            return error_message_prefix + 'Twitter API のレスポンスを JSON としてパースできませんでした。'

        # API レスポンスにエラーが含まれている場合
        ## API レスポンスは Twitter の仕様変更で変わりうるので、ここで判定されなかったと言ってエラーでないとは限らない
        if 'errors' in response_json:

            # Twitter API のエラーコードとエラーメッセージを取得
            ## このエラーコードは API v1.1 の頃と変わっていない
            response_error_code = response_json['errors'][0]['code']
            response_error_message = response_json["errors"][0]["message"]

            # 想定外のエラーコードが返ってきた場合のエラーメッセージ
            alternative_error_message = f'Code: {response_error_code} / Message: {response_error_message}'
            logging.error(f'[TwitterAPI] Failed to invoke GraphQL API ({alternative_error_message})')

            # エラーコードに対応するエラーメッセージを返し、対応するものがない場合は alternative_error_message を返す
            return error_message_prefix + self.ERROR_MESSAGES.get(response_error_code, alternative_error_message)

        # API レスポンスにエラーが含まれていないが、'data' キーが存在しない場合
        ## 実装時点の GraphQL API は必ず成功時は 'data' キーの下にレスポンスが格納されるはず
        ## もし 'data' キーが存在しない場合は、API 仕様が変更されている可能性がある
        elif 'data' not in response_json:
            logging.error('[TwitterAPI] Response does not have "data" key')
            return error_message_prefix + 'Twitter API のレスポンスに "data" キーが存在しません。開発者に修正を依頼してください。'

        # ここまで来たら (中身のデータ構造はともかく) API レスポンスの取得には成功しているはず
        return response_json['data']


    async def createTweet(self, tweet: str, media_ids: list[str] = []) -> schemas.PostTweetResult | schemas.TwitterAPIResult:
        """
        ツイートを送信する

        Args:
            tweet (str): ツイート内容
            media_ids (list[str], optional): 添付するメディアの ID のリスト (デフォルトは空リスト)

        Returns:
            schemas.PostTweetResult | schemas.TwitterAPIResult: ツイートの送信結果
        """

        # まだ排他制御用のロックが存在しない場合は初期化
        screen_name = self.twitter_account.screen_name
        if screen_name not in self.__tweet_locks:
            self.__tweet_locks[screen_name] = TweetLockInfo(lock=asyncio.Lock(), last_tweet_time=0.0)

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

            # variables を組み立てる
            variables = {
                'tweet_text': tweet,
                'dark_request': False,
                'media': {
                    'media_entities': media_entities,
                    'possibly_sensitive': False,
                },
                'semantic_annotation_ids': [],
            }

            # Twitter GraphQL API にリクエスト
            ## features 以下の謎のフラグも数週間単位で頻繁に変更されうるが、Twitter Web App と完全に一致していないからといって
            ## 必ずしも動かなくなるわけではなく、queryId 同様にある程度は古い値でも動くようになっているらしい
            response = await self.invokeGraphQLAPI(
                method = 'POST',
                query_id = 'oB-5XsHNAbjvARJEc8CZFw',
                endpoint = 'CreateTweet',
                variables = variables,
                features = {
                    'communities_web_enable_tweet_community_results_fetch': True,
                    'c9s_tweet_anatomy_moderator_badge_enabled': True,
                    'tweetypie_unmention_optimization_enabled': True,
                    'responsive_web_edit_tweet_api_enabled': True,
                    'graphql_is_translatable_rweb_tweet_is_translatable_enabled': True,
                    'view_counts_everywhere_api_enabled': True,
                    'longform_notetweets_consumption_enabled': True,
                    'responsive_web_twitter_article_tweet_consumption_enabled': True,
                    'tweet_awards_web_tipping_enabled': False,
                    'creator_subscriptions_quote_tweet_preview_enabled': False,
                    'longform_notetweets_rich_text_read_enabled': True,
                    'longform_notetweets_inline_media_enabled': True,
                    'articles_preview_enabled': True,
                    'rweb_video_timestamps_enabled': True,
                    'rweb_tipjar_consumption_enabled': True,
                    'responsive_web_graphql_exclude_directive_enabled': True,
                    'verified_phone_label_enabled': False,
                    'freedom_of_speech_not_reach_fetch_enabled': True,
                    'standardized_nudges_misinfo': True,
                    'tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled': True,
                    'responsive_web_graphql_skip_user_profile_image_extensions_enabled': False,
                    'responsive_web_graphql_timeline_navigation_enabled': True,
                    'responsive_web_enhance_cards_enabled': False,
                },
                error_message_prefix = 'ツイートの送信に失敗しました。',
            )

            # 最後のツイート時刻を更新
            self.__tweet_locks[screen_name]['last_tweet_time'] = time.time()

            # 戻り値が str の場合、ツイートの送信に失敗している (エラーメッセージが返ってくる)
            if isinstance(response, str):
                return schemas.TwitterAPIResult(
                    is_success = False,
                    detail = response,  # エラーメッセージをそのまま返す
                )

            # おそらくツイートに成功しているはずなので、可能であれば送信したツイートの ID を取得
            tweet_id: str
            try:
                tweet_id = str(response['create_tweet']['tweet_results']['result']['rest_id'])
            except Exception:
                # API レスポンスが変わっているなどでツイート ID を取得できなかった
                tweet_id = '__error__'

            return schemas.PostTweetResult(
                is_success = True,
                detail = 'ツイートを送信しました。',
                tweet_url = f'https://twitter.com/i/status/{tweet_id}',
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
            method = 'POST',
            query_id = 'ojPdsZsimiJrUGLR1sjUtA',
            endpoint = 'CreateRetweet',
            variables = {
                'tweet_id': tweet_id,
                'dark_request': False,
            },
            error_message_prefix = 'リツイートに失敗しました。',
        )

        # 戻り値が str の場合、リツイートに失敗している (エラーメッセージが返ってくる)
        if isinstance(response, str):
            return schemas.TwitterAPIResult(
                is_success = False,
                detail = response,  # エラーメッセージをそのまま返す
            )

        return schemas.TwitterAPIResult(
            is_success = True,
            detail = 'リツイートしました。',
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
            method = 'POST',
            query_id = 'iQtK4dl5hBmXewYZuEOKVw',
            endpoint = 'DeleteRetweet',
            variables = {
                'source_tweet_id': tweet_id,
                'dark_request': False,
            },
            error_message_prefix = 'リツイートの取り消しに失敗しました。',
        )

        # 戻り値が str の場合、リツイートの取り消しに失敗している (エラーメッセージが返ってくる)
        if isinstance(response, str):
            return schemas.TwitterAPIResult(
                is_success = False,
                detail = response,  # エラーメッセージをそのまま返す
            )

        return schemas.TwitterAPIResult(
            is_success = True,
            detail = 'リツイートを取り消ししました。',
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
            method = 'POST',
            query_id = 'lI07N6Otwv1PhnEgXILM7A',
            endpoint = 'FavoriteTweet',
            variables = {
                'tweet_id': tweet_id,
            },
            error_message_prefix = 'いいねに失敗しました。',
        )

        # 戻り値が str の場合、いいねに失敗している (エラーメッセージが返ってくる)
        if isinstance(response, str):
            return schemas.TwitterAPIResult(
                is_success = False,
                detail = response,  # エラーメッセージをそのまま返す
            )

        return schemas.TwitterAPIResult(
            is_success = True,
            detail = 'いいねしました。',
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
            method = 'POST',
            query_id = 'ZYKSe-w7KEslx3JhSIk5LA',
            endpoint = 'UnfavoriteTweet',
            variables = {
                'tweet_id': tweet_id,
            },
            error_message_prefix = 'いいねの取り消しに失敗しました。',
        )

        # 戻り値が str の場合、いいねの取り消しに失敗している (エラーメッセージが返ってくる)
        if isinstance(response, str):
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

        # '__typename' が 'TimelineTimelineCursor' で、'cursorType' が指定されたタイプと一致し、'value' キーを持つオブジェクトを再帰的に探索する
        ## 既に探索したオブジェクトは再度探索しないようにすることで、無限ループを防ぐ
        def find_cursor_id(object: Any, searched_objects: list[Any] = []) -> str | None:
            if object in searched_objects:
                return None
            searched_objects.append(object)
            if isinstance(object, dict):
                if ('__typename' in object and 'cursorType' in object and 'value' in object) and \
                   (object['__typename'] == 'TimelineTimelineCursor' and object['cursorType'] == cursor_type):
                    return object['value']
                for key in object:
                    item = find_cursor_id(object[key], searched_objects)
                    if item is not None:
                        return item
            elif isinstance(object, list):
                for item in object:
                    cursor_id = find_cursor_id(item, searched_objects)
                    if cursor_id is not None:
                        return cursor_id
            return None

        return find_cursor_id(response)


    def __getTweetsFromTimelineAPIResponse(self, response: dict[str, Any]) -> list[schemas.Tweet]:
        """
        GraphQL API のうちツイートタイムライン系の API レスポンスから、ツイートリストを取得する

        Args:
            response (dict[str, Any]): ツイートタイムライン系の API レスポンス

        Returns:
            list[schemas.Tweet]: ツイートリスト
        """

        # ここに API レスポンスから抽出したツイート情報を格納し、そこからさらに必要な情報を抽出して schemas.Tweet に格納する
        raw_tweet_objects: list[dict[str, Any]] = []

        # '__typename' が 'TimelineTweet' で、'tweetDisplayType' が 'Tweet' で、
        # 'promotedMetadata' キーを持たず、'tweet_results' オブジェクトを持つオブジェクトを再帰的に探索し、
        # tweet_results.result の '__typename' が 'Tweet' or 'TweetWithVisibilityResults ならそのオブジェクトを raw_tweet_objects に格納する
        ## 既に探索したオブジェクトは再度探索しないようにすることで、無限ループを防ぐ
        def find_tweet_objects(object: Any, searched_objects: list[Any] = []) -> None:
            if object in searched_objects:
                return
            searched_objects.append(object)
            if isinstance(object, dict):
                if ('__typename' in object and 'tweetDisplayType' in object and 'tweet_results' in object and 'promotedMetadata' not in object) and \
                   (object['__typename'] == 'TimelineTweet' and object['tweetDisplayType'] == 'Tweet') and \
                   ('result' in object['tweet_results'] and '__typename' in object['tweet_results']['result']) and \
                   (object['tweet_results']['result']['__typename'] in ['Tweet', 'TweetWithVisibilityResults']):
                    raw_tweet_objects.append(object['tweet_results']['result'])
                for key in object:
                    find_tweet_objects(object[key], searched_objects)
            elif isinstance(object, list):
                for item in object:
                    find_tweet_objects(item, searched_objects)

        # API レスポンスからツイート情報を抽出
        find_tweet_objects(response)

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
                    expanded_text = expanded_text.replace(url_entity['url'], url_entity['expanded_url'])

            # 残った t.co の URL を削除
            if len(image_urls) > 0 or movie_url:
                expanded_text = re.sub(r'\s*https://t\.co/\w+$', '', expanded_text)

            return schemas.Tweet(
                id = raw_tweet_object['legacy']['id_str'],
                created_at = datetime.strptime(raw_tweet_object['legacy']['created_at'], '%a %b %d %H:%M:%S %z %Y').astimezone(ZoneInfo('Asia/Tokyo')),
                user = schemas.TweetUser(
                    id = raw_tweet_object['core']['user_results']['result']['rest_id'],
                    name = raw_tweet_object['core']['user_results']['result']['legacy']['name'],
                    screen_name = raw_tweet_object['core']['user_results']['result']['legacy']['screen_name'],
                    # (ランダムな文字列)_normal.jpg だと画像サイズが小さいので、(ランダムな文字列).jpg に置換
                    icon_url = raw_tweet_object['core']['user_results']['result']['legacy']['profile_image_url_https'].replace('_normal', ''),
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

        # API レスポンスから取得したツイート情報を schemas.Tweet に変換して返す
        return list(map(format_tweet, raw_tweet_objects))


    async def homeLatestTimeline(self,
        cursor_id: str | None = None,
        count: int = 20,
    ) -> schemas.TimelineTweetsResult | schemas.TwitterAPIResult:
        """
        タイムラインの最新ツイートを取得する
        一応 API 上は取得するツイート数を指定できることになっているが、検索と異なり実際に返ってくるツイート数は保証されてないっぽい (100 件返ってくることもある)

        Args:
            cursor_id (str | None, optional): 次のページを取得するためのカーソル ID (デフォルトは None)
            count (int, optional): 取得するツイート数 (デフォルトは 20)

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
            method = 'POST',
            query_id = '9EwYy8pLBOSFlEoSP2STiQ',
            endpoint = 'HomeLatestTimeline',
            variables = variables,
            features = {
                'rweb_tipjar_consumption_enabled': True,
                'responsive_web_graphql_exclude_directive_enabled': True,
                'verified_phone_label_enabled': False,
                'creator_subscriptions_tweet_preview_api_enabled': True,
                'responsive_web_graphql_timeline_navigation_enabled': True,
                'responsive_web_graphql_skip_user_profile_image_extensions_enabled': False,
                'communities_web_enable_tweet_community_results_fetch': True,
                'c9s_tweet_anatomy_moderator_badge_enabled': True,
                'articles_preview_enabled': True,
                'tweetypie_unmention_optimization_enabled': True,
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
            error_message_prefix = 'タイムラインの取得に失敗しました。',
        )

        # 戻り値が str の場合、タイムラインの取得に失敗している (エラーメッセージが返ってくる)
        if isinstance(response, str):
            return schemas.TwitterAPIResult(
                is_success = False,
                detail = response,  # エラーメッセージをそのまま返す
            )

        # まずはカーソル ID を取得
        ## カーソル ID が取得できなかった場合は仕様変更があったとみなし、エラーを返す
        next_cursor_id = self.__getCursorIDFromTimelineAPIResponse(response, 'Top')  # 現在よりも新しいツイートを取得するためのカーソル ID
        previous_cursor_id = self.__getCursorIDFromTimelineAPIResponse(response, 'Bottom')  # 現在よりも過去のツイートを取得するためのカーソル ID
        if next_cursor_id is None or previous_cursor_id is None:
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
    ) -> schemas.TimelineTweetsResult | schemas.TwitterAPIResult:
        """
        ツイートを検索する

        Args:
            search_type (Literal['Top', 'Latest']): 検索タイプ (Top: トップツイート, Latest: 最新ツイート)
            query (str): 検索クエリ
            cursor_id (str | None, optional): 次のページを取得するためのカーソル ID (デフォルトは None)
            count (int, optional): 取得するツイート数 (デフォルトは 20)

        Returns:
            schemas.TimelineTweets | schemas.TwitterAPIResult: 検索結果
        """

        # variables の挿入順序を Twitter Web App に厳密に合わせるためにこのような実装としている
        variables: dict[str, Any] = {}
        variables['rawQuery'] = query.strip() + ' exclude:replies lang:ja'
        variables['count'] = count
        if cursor_id is not None:
            variables['cursor'] = cursor_id
        variables['querySource'] = ''  # Twitter Web App 自体が空文字を送っているので合わせる
        variables['product'] = search_type  # 検索タイプに Top か Latest を指定する

        # Twitter GraphQL API にリクエスト
        response = await self.invokeGraphQLAPI(
            method = 'GET',
            query_id = 'TQmyZ_haUqANuyBcFBLkUw',
            endpoint = 'SearchTimeline',
            variables = variables,
            features = {
                'rweb_tipjar_consumption_enabled': True,
                'responsive_web_graphql_exclude_directive_enabled': True,
                'verified_phone_label_enabled': False,
                'creator_subscriptions_tweet_preview_api_enabled': True,
                'responsive_web_graphql_timeline_navigation_enabled': True,
                'responsive_web_graphql_skip_user_profile_image_extensions_enabled': False,
                'communities_web_enable_tweet_community_results_fetch': True,
                'c9s_tweet_anatomy_moderator_badge_enabled': True,
                'articles_preview_enabled': True,
                'tweetypie_unmention_optimization_enabled': True,
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
            error_message_prefix = 'ツイートの検索に失敗しました。',
        )

        # 戻り値が str の場合、ツイートの検索に失敗している (エラーメッセージが返ってくる)
        if isinstance(response, str):
            return schemas.TwitterAPIResult(
                is_success = False,
                detail = response,  # エラーメッセージをそのまま返す
            )

        # まずはカーソル ID を取得
        ## カーソル ID が取得できなかった場合は仕様変更があったとみなし、エラーを返す
        next_cursor_id = self.__getCursorIDFromTimelineAPIResponse(response, 'Top')  # 現在よりも新しいツイートを取得するためのカーソル ID
        previous_cursor_id = self.__getCursorIDFromTimelineAPIResponse(response, 'Bottom')  # 現在よりも過去のツイートを取得するためのカーソル ID
        if next_cursor_id is None or previous_cursor_id is None:
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
