
import asyncio
import json
from collections.abc import Coroutine
from typing import Annotated, Any, Literal, cast

import tweepy
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    Request,
    UploadFile,
    status,
)
from tweepy_authlib import CookieSessionUserHandler

from app import logging, schemas
from app.models.TwitterAccount import TwitterAccount
from app.models.User import User
from app.routers.UsersRouter import GetCurrentUser
from app.utils.TwitterGraphQLAPI import TwitterGraphQLAPI


# ルーター
router = APIRouter(
    tags = ['Twitter'],
    prefix = '/api/twitter',
)


async def GetCurrentTwitterAccount(
    screen_name: Annotated[str, Path(description='Twitter アカウントのスクリーンネーム。')],
    current_user: Annotated[User, Depends(GetCurrentUser)],
) -> TwitterAccount:
    """ 現在ログイン中のユーザーに紐づく Twitter アカウントを取得する """

    # 指定されたスクリーンネームに紐づく Twitter アカウントを取得
    # 自分が所有していない Twitter アカウントでツイートできないよう、ログイン中のユーザーに限って絞り込む
    ## 通常あり得ないが、万が一同一スクリーンネームのアカウントが作成されてしまった場合に削除できるよう
    ## あえて get_or_none() ではなく all() で取得している
    twitter_account = await TwitterAccount.filter(user_id=current_user.id, screen_name=screen_name).all()

    # 指定された Twitter アカウントがユーザーアカウントに紐付けられていない or 登録されていない
    ## 実際に Twitter にそのスクリーンネームのアカウントが登録されているかとは無関係
    if len(twitter_account) == 0:
        logging.error(f'[TwitterRouter][GetCurrentTwitterAccount] TwitterAccount associated with screen_name does not exist. [screen_name: {screen_name}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'TwitterAccount associated with screen_name does not exist',
        )

    return twitter_account[0]


@router.post(
    '/auth',
    summary = 'Twitter 認証 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def TwitterPasswordAuthAPI(
    auth_request: Annotated[schemas.TwitterPasswordAuthRequest | schemas.TwitterCookieAuthRequest, Body(description='Twitter 認証リクエスト')],
    current_user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    tweepy-authlib によるパスワードログイン or 指定された Cookie 情報で Twitter 連携を行い、ログイン中のユーザーアカウントと Twitter アカウントを紐づける。
    """

    # スクリーンネームとパスワードでログインを実行し、Cookie を取得
    if isinstance(auth_request, schemas.TwitterPasswordAuthRequest):

        # 万が一スクリーンネームに @ が含まれていた場合は事前に削除する
        auth_request.screen_name = auth_request.screen_name.replace('@', '')

        try:
            # ログインには数秒かかるため、非同期で実行
            auth_handler = await asyncio.to_thread(CookieSessionUserHandler,
                screen_name=auth_request.screen_name,
                password=auth_request.password,
            )
        except tweepy.HTTPException as ex:
            # パスワードが間違っている、Twitter サーバー側の規制が強化された、Twitter が鯖落ちしているなどの理由で認証に失敗した
            if len(ex.api_codes) > 0 and len(ex.api_messages) > 0:
                error_message = f'Code: {ex.api_codes[0]} / Message: {ex.api_messages[0]}'
            else:
                error_message = f'Unknown Error (HTTP Error {ex.response.status_code})'
            logging.error(f'[TwitterRouter][TwitterPasswordAuthAPI] Failed to authenticate with password. ({error_message}) [screen_name: {auth_request.screen_name}]')
            raise HTTPException(
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail = f'Failed to authenticate with password ({error_message})',
            )
        except tweepy.TweepyException as ex:
            # 認証フローの途中で予期せぬエラーが発生し、ログインに失敗した
            error_message = f'Message: {ex}'
            logging.error(f'[TwitterRouter][TwitterPasswordAuthAPI] Unexpected error occurred while authenticate with password. ({error_message}) [screen_name: {auth_request.screen_name}]')
            raise HTTPException(
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail = f'Unexpected error occurred while authenticate with password ({error_message})',
            )

        # 現在のログインセッションの Cookie を取得
        cookies: dict[str, str] = auth_handler.get_cookies_as_dict()

    # cookies.txt (Netscape 形式) をパースして Cookie を取得
    else:

        try:
            # cookies.txt の内容を行ごとに分割
            cookies_lines = auth_request.cookies_txt.strip().split('\n')
            cookies: dict[str, str] = {}
            for line in cookies_lines:
                # コメント行やヘッダー行をスキップ
                if line.startswith('#') or line.startswith('# ') or not line.strip():
                    continue
                # タブで分割し、必要な情報を取得
                parts = line.split('\t')
                if len(parts) >= 7:
                    domain, _, _, _, _, name, value = parts[:7]
                    # ドメインが .twitter.com または .x.com の場合のみ処理
                    if domain in ['.twitter.com', 'twitter.com', '.x.com', 'x.com']:
                        cookies[name] = value
            if not cookies:
                logging.error('[TwitterRouter][TwitterPasswordAuthAPI] No valid cookies found in the provided cookies.txt.')
                raise HTTPException(
                    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail = 'No valid cookies found in the provided cookies.txt',
                )
        except Exception as ex:
            error_message = f'Failed to parse cookies.txt: {ex!s}'
            logging.error(f'[TwitterRouter][TwitterPasswordAuthAPI] {error_message}')
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail = error_message,
            )

    # TwitterAccount のレコードを作成
    ## アクセストークンは今までの OAuth 認証 (廃止) との互換性を保つため "DIRECT_COOKIE_SESSION" または "COOKIE_SESSION" の固定値、
    ## アクセストークンシークレットとして Cookie を JSON 化した文字列を入れる
    ## ここでは ORM クラスのみを作成し、Twitter アカウント情報を取得した後に DB に保存する
    twitter_account = TwitterAccount(
        user = current_user,
        name = 'Temporary',
        screen_name = 'Temporary',
        icon_url = 'Temporary',
        # Cookie ログインの場合は "DIRECT_COOKIE_SESSION" で、パスワードログインの場合は "COOKIE_SESSION" で固定
        access_token = 'DIRECT_COOKIE_SESSION' if isinstance(auth_request, schemas.TwitterCookieAuthRequest) else 'COOKIE_SESSION',
        access_token_secret = json.dumps(cookies, ensure_ascii=False),
    )

    # tweepy の API インスタンスを取得
    tweepy_api = twitter_account.getTweepyAPI()

    # 自分の Twitter アカウント情報を取得
    try:
        verify_credentials = await asyncio.to_thread(tweepy_api.verify_credentials)
    except tweepy.TweepyException as ex:
        logging.error(f'[TwitterRouter][TwitterPasswordAuthAPI] Failed to get user information for Twitter account @{twitter_account.screen_name}:', exc_info=ex)
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'Failed to get user information',
        )

    # アカウント名を設定
    twitter_account.name = verify_credentials.name
    # スクリーンネームを設定
    twitter_account.screen_name = verify_credentials.screen_name
    # アイコン URL を設定
    ## (ランダムな文字列)_normal.jpg だと画像サイズが小さいので、(ランダムな文字列).jpg に置換
    twitter_account.icon_url = verify_credentials.profile_image_url_https.replace('_normal', '')

    # 同じユーザー ID とスクリーンネームを持つアカウント情報の重複チェック
    existing_accounts = await TwitterAccount.filter(
        user_id = cast(Any, twitter_account).user_id,
        screen_name = twitter_account.screen_name,
    )

    # 既存のアカウントが見つかった場合、最も古いアカウント情報を更新
    if existing_accounts:
        oldest_account = min(existing_accounts, key=lambda x: x.id)

        # 最も古いアカウント情報を更新
        oldest_account.name = twitter_account.name  # アカウント名
        oldest_account.icon_url = twitter_account.icon_url  # アイコン URL
        oldest_account.access_token = twitter_account.access_token  # アクセストークン
        oldest_account.access_token_secret = twitter_account.access_token_secret  # アクセストークンシークレット
        await oldest_account.save()

        # 他の重複アカウントを削除
        for account in existing_accounts:
            if account.id != oldest_account.id:
                await account.delete()

        logging.info(f'[TwitterRouter][TwitterPasswordAuthAPI] Updated existing account and removed {len(existing_accounts) - 1} duplicate(s). [screen_name: {twitter_account.screen_name}]')

    # 既存のアカウントが見つからなかった場合、新しいアカウント情報を DB に保存
    else:
        await twitter_account.save()
        logging.info(f'[TwitterRouter][TwitterPasswordAuthAPI] Created new account. [screen_name: {twitter_account.screen_name}]')

    # 処理完了
    if isinstance(auth_request, schemas.TwitterCookieAuthRequest):
        logging.info(f'[TwitterRouter][TwitterPasswordAuthAPI] Logged in with cookie. [screen_name: {twitter_account.screen_name}]')
    else:
        logging.info(f'[TwitterRouter][TwitterPasswordAuthAPI] Logged in with password. [screen_name: {twitter_account.screen_name}]')


@router.delete(
    '/accounts/{screen_name}',
    summary = 'Twitter アカウント連携解除 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def TwitterAccountDeleteAPI(
    twitter_account: Annotated[TwitterAccount, Depends(GetCurrentTwitterAccount)],
):
    """
    指定された Twitter アカウントの連携を解除する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    assert twitter_account.access_token in ['COOKIE_SESSION', 'DIRECT_COOKIE_SESSION'], 'OAuth session is no longer available.'

    # パスワードログイン (COOKIE_SESSION) の場合は明示的にログアウト処理を行う
    ## 単に Cookie を削除するだけだと Twitter 側にログインセッションが残り続けてしまう
    ## Cookie ログイン (DIRECT_COOKIE_SESSION) の場合はここでログアウトするとブラウザ側もログアウトされてしまうので、行わない
    if twitter_account.access_token == 'COOKIE_SESSION':
        cookie_session_user_handler = twitter_account.getTweepyAuthHandler()
        try:
            await asyncio.to_thread(cookie_session_user_handler.logout)
            logging.info(f'[TwitterRouter][TwitterAccountDeleteAPI] Logged out with password. [screen_name: {twitter_account.screen_name}]')
        except tweepy.HTTPException as ex:
            # サーバーエラーが発生した
            if len(ex.api_codes) > 0 and len(ex.api_messages) > 0:
                # Code: 32 が返された場合、現在のログインセッションが強制的に無効化 (強制ログアウト) されている
                ## この場合同時にアカウントごとロックされ (解除には Arkose チャレンジのクリアが必要) 、
                ## また当該アカウントの Twitter Web App でのログインセッションが全て無効化されるケースが大半
                ## エラーは送出せず、当該 Twitter アカウントに紐づくレコードを削除して連携解除とする
                if ex.api_codes[0] == 32:
                    await twitter_account.delete()
                    return
                error_message = f'Code: {ex.api_codes[0]} / Message: {ex.api_messages[0]}'
            else:
                error_message = f'Unknown Error (HTTP Error {ex.response.status_code})'
            logging.error(f'[TwitterRouter][TwitterAccountDeleteAPI] Failed to logout. ({error_message}) [screen_name: {twitter_account.screen_name}]')
            raise HTTPException(
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail = f'Failed to logout ({error_message})',
            )
        except tweepy.TweepyException as ex:
            # 予期せぬエラーが発生した
            error_message = f'Message: {ex}'
            logging.error(f'[TwitterRouter][TwitterAccountDeleteAPI] Unexpected error occurred while logout. ({error_message}) [screen_name: {twitter_account.screen_name}]')
            raise HTTPException(
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail = f'Unexpected error occurred while logging out ({error_message})',
            )

    # 指定された Twitter アカウントのレコードを削除
    ## Cookie 情報などが保持されたレコードを削除することで連携解除とする
    await twitter_account.delete()


@router.get(
    '/accounts/{screen_name}/challenge-data',
    summary = 'Twitter Web App Challenge 情報取得 API',
    response_description = 'Twitter Web App の Challenge 情報。',
    response_model = schemas.TwitterChallengeData | schemas.TwitterAPIResult,
)
async def TwitterChallengeAPI(
    twitter_account: Annotated[TwitterAccount, Depends(GetCurrentTwitterAccount)],
):
    """
    Twitter Web App の API リクエスト内の X-Client-Transaction-ID ヘッダーを算出するために必要な Challenge 情報を取得する。<br>
    この API のレスポンスを元にブラウザ上のフロントエンドで算出した X-Client-Transaction-ID を API リクエスト時に含めてもらう想定。

    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    return await TwitterGraphQLAPI(twitter_account).fetchChallengeData()


@router.post(
    '/accounts/{screen_name}/tweets',
    summary = 'ツイート送信 API',
    response_description = 'ツイートの送信結果。',
    response_model = schemas.PostTweetResult | schemas.TwitterAPIResult,
)
async def TwitterTweetAPI(
    request: Request,
    twitter_account: Annotated[TwitterAccount, Depends(GetCurrentTwitterAccount)],
    tweet: Annotated[str, Form(description='ツイートの本文 (基本的には140文字までだが、プレミアムの加入状態や英数字の量に依存する) 。')] = '',
    images: Annotated[list[UploadFile], File(description='ツイートに添付する画像 (4枚まで) 。')] = [],
):
    """
    Twitter にツイートを送信する。ツイート本文 or 画像のみ送信することもできる。<br>
    ツイートには screen_name で指定したスクリーンネームに紐づく Twitter アカウントが利用される。

    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    # 画像が4枚を超えている
    if len(images) > 4:
        logging.error(f'[TwitterRouter][TwitterTweetAPI] Can tweet up to 4 images. [image length: {len(images)}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Can tweet up to 4 images',
        )

    # アップロードした画像の media_id のリスト
    media_ids: list[str] = []

    try:

        tweepy_api = twitter_account.getTweepyAPI()

        # 画像をアップロードするタスク
        image_upload_task: list[Coroutine[Any, Any, Any | None]] = []
        for image in images:
            image_upload_task.append(asyncio.to_thread(tweepy_api.media_upload,
                filename = image.filename,
                file = image.file,
                # Twitter Web App の挙動に合わせて常にチャンク送信方式でアップロードする
                chunk = True,
                # Twitter Web App の挙動に合わせる
                media_category = 'tweet_image',
            ))

        # 画像を Twitter にアップロード
        ## asyncio.gather() で同時にアップロードし、ツイートをより早く送信できるように
        ## ref: https://developer.twitter.com/ja/docs/media/upload-media/api-reference/post-media-upload-init
        for image_upload_result in await asyncio.gather(*image_upload_task):
            if image_upload_result is not None:
                media_ids.append(str(image_upload_result.media_id))

    # 画像のアップロードに失敗した
    except tweepy.HTTPException as ex:
        if len(ex.api_codes) > 0 and len(ex.api_messages) > 0:
            # 定義されていないエラーコードの時は Twitter API から返ってきたエラーメッセージをそのまま返す
            error_message = 'ツイート画像のアップロードに失敗しました。' + \
                TwitterGraphQLAPI.ERROR_MESSAGES.get(ex.api_codes[0], f'Code: {ex.api_codes[0]} / Message: {ex.api_messages[0]}')
        else:
            error_message = f'ツイート画像のアップロード中に Twitter API から HTTP {ex.response.status_code} エラーが返されました。'
            if len(ex.api_errors) > 0:
                error_message += f'Message: {ex.api_errors[0]}'  # エラーメッセージがあれば追加
        return {
            'is_success': False,
            'detail': error_message,
        }

    # GraphQL API を使ってツイートを送信し、結果をそのまま返す
    return await TwitterGraphQLAPI(twitter_account).createTweet(tweet, media_ids, request.headers.get('x-client-transaction-id'))


@router.put(
    '/accounts/{screen_name}/tweets/{tweet_id}/retweet',
    summary = 'リツイート実行 API',
    response_description = 'リツイートの実行結果。',
    response_model = schemas.TwitterAPIResult,
)
async def TwitterRetweetAPI(
    request: Request,
    twitter_account: Annotated[TwitterAccount, Depends(GetCurrentTwitterAccount)],
    tweet_id: Annotated[str, Path(description='リツイートするツイートの ID。')],
):
    """
    指定されたツイートをリツイートする。<br>
    リツイートには screen_name で指定したスクリーンネームに紐づく Twitter アカウントが利用される。

    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    return await TwitterGraphQLAPI(twitter_account).createRetweet(tweet_id, request.headers.get('x-client-transaction-id'))


@router.delete(
    '/accounts/{screen_name}/tweets/{tweet_id}/retweet',
    summary = 'リツイート取り消し API',
    response_description = 'リツイートの取り消し結果。',
    response_model = schemas.TwitterAPIResult,
)
async def TwitterRetweetCancelAPI(
    request: Request,
    twitter_account: Annotated[TwitterAccount, Depends(GetCurrentTwitterAccount)],
    tweet_id: Annotated[str, Path(description='リツイートを取り消すツイートの ID。')],
):
    """
    指定されたツイートのリツイートを取り消す。<br>
    リツイートの取り消しには screen_name で指定したスクリーンネームに紐づく Twitter アカウントが利用される。

    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    return await TwitterGraphQLAPI(twitter_account).deleteRetweet(tweet_id, request.headers.get('x-client-transaction-id'))


@router.put(
    '/accounts/{screen_name}/tweets/{tweet_id}/favorite',
    summary = 'いいね実行 API',
    response_description = 'いいねの実行結果。',
    response_model = schemas.TwitterAPIResult,
)
async def TwitterFavoriteAPI(
    request: Request,
    twitter_account: Annotated[TwitterAccount, Depends(GetCurrentTwitterAccount)],
    tweet_id: Annotated[str, Path(description='いいねするツイートの ID。')],
):
    """
    指定されたツイートをいいねする。<br>
    いいねには screen_name で指定したスクリーンネームに紐づく Twitter アカウントが利用される。

    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    return await TwitterGraphQLAPI(twitter_account).favoriteTweet(tweet_id, request.headers.get('x-client-transaction-id'))


@router.delete(
    '/accounts/{screen_name}/tweets/{tweet_id}/favorite',
    summary = 'いいね取り消し API',
    response_description = 'いいねの取り消し結果。',
    response_model = schemas.TwitterAPIResult,
)
async def TwitterFavoriteCancelAPI(
    request: Request,
    twitter_account: Annotated[TwitterAccount, Depends(GetCurrentTwitterAccount)],
    tweet_id: Annotated[str, Path(description='いいねを取り消すツイートの ID。')],
):
    """
    指定されたツイートのいいねを取り消す。<br>
    いいねの取り消しには screen_name で指定したスクリーンネームに紐づく Twitter アカウントが利用される。

    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    return await TwitterGraphQLAPI(twitter_account).unfavoriteTweet(tweet_id, request.headers.get('x-client-transaction-id'))


@router.get(
    '/accounts/{screen_name}/timeline',
    summary = 'ホームタイムライン取得 API',
    response_description = 'タイムラインのツイートのリスト。',
    response_model = schemas.TimelineTweetsResult | schemas.TwitterAPIResult,
)
async def TwitterTimelineAPI(
    request: Request,
    twitter_account: Annotated[TwitterAccount, Depends(GetCurrentTwitterAccount)],
    cursor_id: Annotated[str | None, Query(description='前回のレスポンスから取得した、次のページを取得するためのカーソル ID 。')] = None,
):
    """
    ホームタイムラインを取得する。<br>
    ホームタイムラインの取得には screen_name で指定したスクリーンネームに紐づく Twitter アカウントが利用される。

    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    return await TwitterGraphQLAPI(twitter_account).homeLatestTimeline(
        cursor_id = cursor_id,
        count = 20,
        x_client_transaction_id = request.headers.get('x-client-transaction-id'),
    )


@router.get(
    '/accounts/{screen_name}/search',
    summary = 'ツイート検索 API',
    response_description = '検索結果のツイートのリスト。',
    response_model = schemas.TimelineTweetsResult | schemas.TwitterAPIResult,
)
async def TwitterSearchAPI(
    request: Request,
    twitter_account: Annotated[TwitterAccount, Depends(GetCurrentTwitterAccount)],
    query: Annotated[str, Query(description='検索クエリ。')],
    search_type: Annotated[Literal['Top', 'Latest'], Query(description='検索タイプ。Top は話題のツイート、Latest は最新のツイート。')] = 'Latest',
    cursor_id: Annotated[str | None, Query(description='前回のレスポンスから取得した、次のページを取得するためのカーソル ID 。')] = None,
):
    """
    指定されたクエリでツイートを検索する。

    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    return await TwitterGraphQLAPI(twitter_account).searchTimeline(
        search_type = search_type,
        query = query,
        cursor_id = cursor_id,
        count = 20,
        x_client_transaction_id = request.headers.get('x-client-transaction-id'),
    )
