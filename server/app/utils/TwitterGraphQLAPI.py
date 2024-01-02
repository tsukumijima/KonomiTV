
import httpx
import json
from typing import Any, Literal

from app import logging
from app import schemas
from app.models.TwitterAccount import TwitterAccount


class TwitterGraphQLAPI:
    """
    Twitter Web App で利用されている GraphQL API の薄いラッパー
    外部ライブラリを使うよりすべて自前で書いたほうが柔軟に対応でき凍結リスクを回避できると考え実装した
    以下に実装されているリクエストペイロードなどはすべて実装時点の Twitter Web App が実際に送信するリクエストを可能な限り模倣したもの
    メソッド名は GraphQL API でのエンドポイント名に対応している
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


    def __init__(self, twitter_account: TwitterAccount) -> None:
        """
        Twitter GraphQL API クライアントを初期化する

        Args:
            twitter_account: Twitter アカウントのモデル
        """

        self.twitter_account = twitter_account

        # Chrome への偽装用 HTTP リクエストヘッダーと Cookie を取得
        cookie_session_user_handler = self.twitter_account.getTweepyAuthHandler()
        headers_dict = cookie_session_user_handler.get_graphql_api_headers()
        cookies_dict = cookie_session_user_handler.get_cookies_as_dict()

        # httpx の非同期 HTTP クライアントのインスタンスを作成
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
        Twitter Web App の GraphQL API を叩く
        実際には GraphQL と言いつつペイロードで JSON を渡しているので謎
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

        # Twitter GraphQL API にリクエストを飛ばす
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
                        url = f'https://twitter.com/i/api/graphql/{query_id}/{endpoint}',
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
                        url = f'https://twitter.com/i/api/graphql/{query_id}/{endpoint}',
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


    async def createTweet(self, tweet: str, media_ids: list[str] = []) -> schemas.TweetResult:
        """
        ツイートを送信する

        Args:
            tweet (str): ツイート内容
            media_ids (list[str], optional): 添付するメディアの ID のリスト (デフォルトは空リスト)

        Returns:
            schemas.TweetResult: ツイートの送信結果
        """

        # 画像の media_id をリストに格納 (画像がない場合は空のリストになる)
        media_entities: list[dict[str, Any]] = []
        for media_id in media_ids:
            media_entities.append({
                'media_id': media_id,
                'tagged_users': []
            })

        # Twitter GraphQL API にリクエスト
        response = await self.invokeGraphQLAPI(
            method = 'POST',
            query_id = 'bDE2rBtZb3uyrczSZ_pI9g',
            endpoint = 'CreateTweet',
            variables = {
                'tweet_text': tweet,
                'dark_request': False,
                'media': {
                    'media_entities': media_entities,
                    'possibly_sensitive': False,
                },
                'semantic_annotation_ids': [],
            },
            # 以下の謎のフラグも数週間単位で頻繁に変更されうるが、Twitter Web App と完全に一致していないからといって
            # 必ずしも動かなくなるわけではなく、queryId 同様にある程度は古い値でも動くようになっているらしい
            features = {
                'c9s_tweet_anatomy_moderator_badge_enabled': True,
                'tweetypie_unmention_optimization_enabled': True,
                'responsive_web_edit_tweet_api_enabled': True,
                'graphql_is_translatable_rweb_tweet_is_translatable_enabled': True,
                'view_counts_everywhere_api_enabled': True,
                'longform_notetweets_consumption_enabled': True,
                'responsive_web_twitter_article_tweet_consumption_enabled': False,
                'tweet_awards_web_tipping_enabled': False,
                'longform_notetweets_rich_text_read_enabled': True,
                'longform_notetweets_inline_media_enabled': True,
                'rweb_video_timestamps_enabled': True,
                'responsive_web_graphql_exclude_directive_enabled': True,
                'verified_phone_label_enabled': False,
                'freedom_of_speech_not_reach_fetch_enabled': True,
                'standardized_nudges_misinfo': True,
                'tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled': True,
                'responsive_web_media_download_video_enabled': False,
                'responsive_web_graphql_skip_user_profile_image_extensions_enabled': False,
                'responsive_web_graphql_timeline_navigation_enabled': True,
                'responsive_web_enhance_cards_enabled': False,
            },
            error_message_prefix = 'ツイートの送信に失敗しました。',
        )

        # 戻り値が str の場合、ツイートの送信に失敗している (エラーメッセージが返ってくる)
        if isinstance(response, str):
            return schemas.TweetResult(
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

        return schemas.TweetResult(
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
