
import asyncio
import json
import tweepy
import tweepy.models
import tweepy.parsers
from fastapi import APIRouter
from fastapi import Body
from fastapi import Depends
from fastapi import File
from fastapi import Form
from fastapi import HTTPException
from fastapi import Path
from fastapi import Query
from fastapi import status
from fastapi import UploadFile
from tweepy_authlib import CookieSessionUserHandler
from typing import Annotated, Any, cast, Coroutine

from app import logging
from app import schemas
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
    twitter_account = await TwitterAccount.filter(user_id=current_user.id, screen_name=screen_name).get_or_none()

    # 指定された Twitter アカウントがユーザーアカウントに紐付けられていない or 登録されていない
    ## 実際に Twitter にそのスクリーンネームのアカウントが登録されているかとは無関係
    if not twitter_account:
        logging.error(f'[TwitterRouter][GetCurrentTwitterAccount] TwitterAccount associated with screen_name does not exist [screen_name: {screen_name}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'TwitterAccount associated with screen_name does not exist',
        )

    return twitter_account


@router.post(
    '/password-auth',
    summary = 'Twitter パスワード認証 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def TwitterPasswordAuthAPI(
    password_auth_request: Annotated[schemas.TwitterPasswordAuthRequest, Body(description='Twitter パスワード認証リクエスト')],
    current_user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    tweepy-authlib を利用してパスワード認証で Twitter 連携を行い、ログイン中のユーザーアカウントと Twitter アカウントを紐づける。
    """

    # 万が一スクリーンネームに @ が含まれていた場合は事前に削除する
    password_auth_request.screen_name = password_auth_request.screen_name.replace('@', '')

    # スクリーンネームとパスワードを指定して認証
    try:
        # ログインには数秒かかるため、非同期で実行
        auth_handler = await asyncio.to_thread(CookieSessionUserHandler,
            screen_name=password_auth_request.screen_name,
            password=password_auth_request.password,
        )
    except tweepy.HTTPException as ex:
        # パスワードが間違っているなどの理由で認証に失敗した
        if len(ex.api_codes) > 0 and len(ex.api_messages) > 0:
            error_message = f'Code: {ex.api_codes[0]} / Message: {ex.api_messages[0]}'
        else:
            error_message = f'Unknown Error (HTTP Error {ex.response.status_code})'
        logging.error(f'[TwitterRouter][TwitterPasswordAuthAPI] Failed to authenticate with password ({error_message}) [screen_name: {password_auth_request.screen_name}]')
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = f'Failed to authenticate with password ({error_message})',
        )
    except tweepy.TweepyException as ex:
        # 認証フローの途中で予期せぬエラーが発生し、ログインに失敗した
        error_message = f'Message: {ex}'
        logging.error(f'[TwitterRouter][TwitterPasswordAuthAPI] Unexpected error occurred while authenticate with password ({error_message}) [screen_name: {password_auth_request.screen_name}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = f'Unexpected error occurred while authenticate with password ({error_message})',
        )

    # 現在のログインセッションの Cookie を取得
    cookies: dict[str, str] = auth_handler.get_cookies().get_dict()

    # TwitterAccount のレコードを作成
    ## アクセストークンは今までの OAuth 認証 (廃止) との互換性を保つため "COOKIE_SESSION" の固定値、
    ## アクセストークンシークレットとして Cookie を JSON 化した文字列を入れる
    ## ここではまだ保存しない
    twitter_account = TwitterAccount(
        user = current_user,
        name = 'Temporary',
        screen_name = 'Temporary',
        icon_url = 'Temporary',
        access_token = 'COOKIE_SESSION',
        access_token_secret = json.dumps(cookies, ensure_ascii=False),
    )

    # tweepy の API インスタンスを取得
    tweepy_api = twitter_account.getTweepyAPI()

    # アカウント情報を更新
    try:
        verify_credentials = await asyncio.to_thread(tweepy_api.verify_credentials)
    except tweepy.TweepyException:
        logging.error('[TwitterRouter][TwitterPasswordAuthAPI] Failed to get user information')
        return HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Failed to get user information',
        )

    # アカウント名
    twitter_account.name = verify_credentials.name
    # スクリーンネーム
    twitter_account.screen_name = verify_credentials.screen_name
    # アイコン URL
    ## (ランダムな文字列)_normal.jpg だと画像サイズが小さいので、(ランダムな文字列).jpg に置換
    twitter_account.icon_url = verify_credentials.profile_image_url_https.replace('_normal', '')

    # ログインセッションとアカウント情報を保存
    await twitter_account.save()

    # 同じスクリーンネームを持つアカウントが重複している場合、古い方のレコードのデータを更新する
    # すでに作成されている新しいレコード（まだ save() していないので仮の情報しか入っていない）は削除される
    twitter_account_existing = await TwitterAccount.filter(
        user_id = cast(Any, twitter_account).user_id,
        screen_name = twitter_account.screen_name,
    )
    if len(twitter_account_existing) > 1:
        twitter_account_existing[0].name = twitter_account.name  # アカウント名
        twitter_account_existing[0].icon_url = twitter_account.icon_url  # アイコン URL
        twitter_account_existing[0].access_token = twitter_account.access_token  # アクセストークン
        twitter_account_existing[0].access_token_secret = twitter_account.access_token_secret  # アクセストークンシークレット
        await twitter_account_existing[0].save()
        await twitter_account.delete()


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

    # 明示的にログアウト処理を行う
    ## 単に Cookie を削除するだけだと Twitter 側にログインセッションが残り続けてしまう
    assert twitter_account.access_token == 'COOKIE_SESSION', 'OAuth session is no longer available.'
    auth_handler = twitter_account.getTweepyAuthHandler()
    try:
        await asyncio.to_thread(auth_handler.logout)
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
        logging.error(f'[TwitterRouter][TwitterAccountDeleteAPI] Failed to logout ({error_message}) [screen_name: {twitter_account.screen_name}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = f'Failed to logout ({error_message})',
        )
    except tweepy.TweepyException as ex:
        # 予期せぬエラーが発生した
        error_message = f'Message: {ex}'
        logging.error(f'[TwitterRouter][TwitterAccountDeleteAPI] Unexpected error occurred while logout ({error_message}) [screen_name: {twitter_account.screen_name}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = f'Unexpected error occurred while logging out ({error_message})',
        )

    # 指定された Twitter アカウントのレコードを削除
    ## アクセストークンなどが保持されたレコードを削除することで連携解除とする
    await twitter_account.delete()


@router.post(
    '/accounts/{screen_name}/tweets',
    summary = 'ツイート送信 API',
    response_description = 'ツイートの送信結果。',
    response_model = schemas.PostTweetResult | schemas.TwitterAPIResult,
)
async def TwitterTweetAPI(
    twitter_account: Annotated[TwitterAccount, Depends(GetCurrentTwitterAccount)],
    tweet: Annotated[str, Form(description='ツイートの本文 (基本的には140文字までだが、プレミアムの加入状態や英数字の量に依存する) 。')] = '',
    images: Annotated[list[UploadFile], File(description='ツイートに添付する画像 (4枚まで) 。')] = [],
):
    """
    Twitter にツイートを送信する。ツイート本文 or 画像のみ送信することもできる。<br>
    ツイートには screen_name で指定したスクリーンネームに紐づく Twitter アカウントが利用される。

    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    tweepy_api = twitter_account.getTweepyAPI()

    # 画像が4枚を超えている
    if len(images) > 4:
        logging.error(f'[TwitterRouter][TwitterTweetAPI] Can tweet up to 4 images [image length: {len(images)}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Can tweet up to 4 images',
        )

    # アップロードした画像の media_id のリスト
    media_ids: list[str] = []

    try:

        # 画像をアップロードするタスク
        image_upload_task: list[Coroutine[Any, Any, Any | None]] = []
        for image in images:
            image_upload_task.append(asyncio.to_thread(tweepy_api.media_upload, filename=image.filename, file=image.file))

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
    return await TwitterGraphQLAPI(twitter_account).createTweet(tweet, media_ids)


@router.put(
    '/accounts/{screen_name}/tweets/{tweet_id}/retweet',
    summary = 'リツイート実行 API',
    response_description = 'リツイートの実行結果。',
    response_model = schemas.TwitterAPIResult,
)
async def TwitterRetweetAPI(
    twitter_account: Annotated[TwitterAccount, Depends(GetCurrentTwitterAccount)],
    tweet_id: Annotated[str, Path(description='リツイートするツイートの ID。')],
):
    """
    指定されたツイートをリツイートする。<br>
    リツイートには screen_name で指定したスクリーンネームに紐づく Twitter アカウントが利用される。

    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    return await TwitterGraphQLAPI(twitter_account).createRetweet(tweet_id)


@router.delete(
    '/accounts/{screen_name}/tweets/{tweet_id}/retweet',
    summary = 'リツイート取り消し API',
    response_description = 'リツイートの取り消し結果。',
    response_model = schemas.TwitterAPIResult,
)
async def TwitterRetweetCancelAPI(
    twitter_account: Annotated[TwitterAccount, Depends(GetCurrentTwitterAccount)],
    tweet_id: Annotated[str, Path(description='リツイートを取り消すツイートの ID。')],
):
    """
    指定されたツイートのリツイートを取り消す。<br>
    リツイートの取り消しには screen_name で指定したスクリーンネームに紐づく Twitter アカウントが利用される。

    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    return await TwitterGraphQLAPI(twitter_account).deleteRetweet(tweet_id)


@router.put(
    '/accounts/{screen_name}/tweets/{tweet_id}/favorite',
    summary = 'いいね実行 API',
    response_description = 'いいねの実行結果。',
    response_model = schemas.TwitterAPIResult,
)
async def TwitterFavoriteAPI(
    twitter_account: Annotated[TwitterAccount, Depends(GetCurrentTwitterAccount)],
    tweet_id: Annotated[str, Path(description='いいねするツイートの ID。')],
):
    """
    指定されたツイートをいいねする。<br>
    いいねには screen_name で指定したスクリーンネームに紐づく Twitter アカウントが利用される。

    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    return await TwitterGraphQLAPI(twitter_account).favoriteTweet(tweet_id)


@router.delete(
    '/accounts/{screen_name}/tweets/{tweet_id}/favorite',
    summary = 'いいね取り消し API',
    response_description = 'いいねの取り消し結果。',
    response_model = schemas.TwitterAPIResult,
)
async def TwitterFavoriteCancelAPI(
    twitter_account: Annotated[TwitterAccount, Depends(GetCurrentTwitterAccount)],
    tweet_id: Annotated[str, Path(description='いいねを取り消すツイートの ID。')],
):
    """
    指定されたツイートのいいねを取り消す。<br>
    いいねの取り消しには screen_name で指定したスクリーンネームに紐づく Twitter アカウントが利用される。

    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    return await TwitterGraphQLAPI(twitter_account).unfavoriteTweet(tweet_id)


@router.get(
    '/accounts/{screen_name}/timeline',
    summary = 'ホームタイムライン取得 API',
    response_description = 'タイムラインのツイートのリスト。',
    response_model = schemas.TimelineTweetsResult | schemas.TwitterAPIResult,
)
async def TwitterTimelineAPI(
    twitter_account: Annotated[TwitterAccount, Depends(GetCurrentTwitterAccount)],
    cursor_id: Annotated[str | None, Query(description='前回のレスポンスから取得した、次のページを取得するためのカーソル ID 。')] = None,
):
    """
    ホームタイムラインを取得する。<br>
    ホームタイムラインの取得には screen_name で指定したスクリーンネームに紐づく Twitter アカウントが利用される。

    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    return await TwitterGraphQLAPI(twitter_account).homeLatestTimeline(cursor_id, count=20)


@router.get(
    '/accounts/{screen_name}/search',
    summary = 'ツイート検索 API',
    response_description = '検索結果のツイートのリスト。',
    response_model = schemas.TimelineTweetsResult | schemas.TwitterAPIResult,
)
async def TwitterSearchAPI(
    twitter_account: Annotated[TwitterAccount, Depends(GetCurrentTwitterAccount)],
    query: Annotated[str, Query(description='検索クエリ。')],
    cursor_id: Annotated[str | None, Query(description='前回のレスポンスから取得した、次のページを取得するためのカーソル ID 。')] = None,
):
    """
    指定されたクエリでツイートを検索する。

    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    return await TwitterGraphQLAPI(twitter_account).searchTimeline('Latest', query, cursor_id, count=20)
