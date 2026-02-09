
import asyncio
import random
from collections.abc import Coroutine
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

import httpx
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
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app import logging, schemas
from app.constants import API_REQUEST_HEADERS
from app.models.TwitterAccount import TwitterAccount
from app.models.User import User
from app.routers.UsersRouter import GetCurrentUser
from app.utils.TwitterGraphQLAPI import TwitterGraphQLAPI
from app.utils.TwitterScrapeBrowser import TwitterScrapeBrowser


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

    # 古い形式のレコード (access_token が "NETSCAPE_COOKIE_FILE" でない) は利用できない
    # これが検出された場合、その場で当該レコードを削除する
    ## 重複レコードの可能性もなくもないため、リスト全体をイテレートしてチェックする
    is_removed = False
    valid_accounts: list[TwitterAccount] = []
    for record in twitter_account:
        if record.access_token != 'NETSCAPE_COOKIE_FILE':
            logging.error(f'[TwitterRouter][GetCurrentTwitterAccount] Old cookie format or OAuth session is no longer available. [screen_name: {record.screen_name}, id: {record.id}]')
            await record.delete()
            is_removed = True
        else:
            valid_accounts.append(record)

    # 古い形式のレコードが削除された場合、エラーを返す
    if is_removed is True:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Old cookie format or OAuth session is no longer available',
        )

    # 有効なアカウントが存在しない場合
    if len(valid_accounts) == 0:
        logging.error(f'[TwitterRouter][GetCurrentTwitterAccount] No valid TwitterAccount found after cleanup. [screen_name: {screen_name}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'TwitterAccount associated with screen_name does not exist',
        )

    return valid_accounts[0]


@router.post(
    '/auth',
    summary = 'Twitter 認証 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def TwitterCookieAuthAPI(
    auth_request: Annotated[schemas.TwitterCookieAuthRequest, Body(description='Twitter 認証リクエスト')],
    current_user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    指定された Cookie 情報 (Netscape 形式) で Twitter 連携を行い、ログイン中のユーザーアカウントと Twitter アカウントを紐づける。
    """

    # cookies.txt (Netscape 形式) をパースして Cookie が取得できるかを試す
    # パースしたデータ自体は使われないが、正しいフォーマットかを検証するために必須
    try:
        cookie_params = TwitterScrapeBrowser.parseNetscapeCookieFile(auth_request.cookies_txt)
        # Twitter 関連の Cookie が存在するかを確認
        ## CookieParam の domain に 'x.com' が含まれているかチェック
        twitter_cookies = [
            param for param in cookie_params
            if param.domain is not None and 'x.com' in param.domain
        ]
    except Exception as ex:
        error_message = f'Failed to parse cookies.txt: {ex!s}'
        logging.error(f'[TwitterRouter][TwitterCookieAuthAPI] {error_message}')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = error_message,
        ) from ex
    if len(twitter_cookies) == 0:
        logging.error('[TwitterRouter][TwitterCookieAuthAPI] No valid cookies found in the provided cookies.txt.')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'No valid cookies found in the provided cookies.txt',
        )

    # TwitterAccount のレコードを作成
    ## アクセストークンは "NETSCAPE_COOKIE_FILE" の固定値、
    ## アクセストークンシークレットとして Netscape 形式の Cookie ファイルの内容をそのまま保存する
    ## ここでは ORM インスタンスのみを作成し、実際にログイン中の Twitter アカウント情報を取得できた段階で DB に保存する
    twitter_account = TwitterAccount(
        user = current_user,
        name = 'Temporary',
        screen_name = 'Temporary',
        icon_url = 'Temporary',
        # Netscape Cookie ファイル形式の場合は "NETSCAPE_COOKIE_FILE" で固定
        access_token = 'NETSCAPE_COOKIE_FILE',
        # Netscape 形式の Cookie ファイルの内容をそのまま保存
        access_token_secret = auth_request.cookies_txt,
    )

    # 一時的に作成した TwitterAccount ORM インスタンスの ID (通常 None) を控えておき、後段でシングルトンを付け替える
    temporary_account_id = twitter_account.id

    # 上記で作成した TwitterAccount ORM インスタンスを使い、現在ログイン中の Twitter アカウント情報を取得
    try:
        viewer_result = await TwitterGraphQLAPI(twitter_account).fetchLoggedViewer()
    except Exception as ex:
        logging.error('[TwitterRouter][TwitterCookieAuthAPI] Failed to get user information:', exc_info=ex)
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'Failed to get user information',
        ) from ex

    # ユーザー情報の取得に失敗した場合
    if isinstance(viewer_result, schemas.TwitterAPIResult) and viewer_result.is_success is False:
        logging.error(f'[TwitterRouter][TwitterCookieAuthAPI] Failed to get user information: {viewer_result.detail}')
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = viewer_result.detail,  # エラーメッセージをそのまま返す
        )

    # viewer_result が TweetUser の場合のみ処理を続行
    if not isinstance(viewer_result, schemas.TweetUser):
        logging.error('[TwitterRouter][TwitterCookieAuthAPI] Failed to get user information: Invalid response type')
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'Failed to get user information',
        )

    # アカウント名を設定
    twitter_account.name = viewer_result.name
    # スクリーンネームを設定
    twitter_account.screen_name = viewer_result.screen_name
    # アイコン URL を設定
    twitter_account.icon_url = viewer_result.icon_url
    # Cookie を暗号化して保持
    twitter_account.access_token_secret = twitter_account.encryptAccessTokenSecret(auth_request.cookies_txt)

    # 同じユーザー ID とスクリーンネームを持つアカウント情報の重複チェック
    existing_accounts = await TwitterAccount.filter(
        user_id = twitter_account.user_id,
        screen_name = twitter_account.screen_name,
    )

    # 永続化後に使う TwitterAccount を示す変数
    persisted_account: TwitterAccount | None = None

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
                logging.info(f'[TwitterRouter][TwitterCookieAuthAPI] Deleted duplicate account. [id: {account.id}, screen_name: {account.screen_name}]')

        logging.info(f'[TwitterRouter][TwitterCookieAuthAPI] Updated existing account. [id: {twitter_account.id}, screen_name: {twitter_account.screen_name}]')

        # 永続化後に使う TwitterAccount を設定
        persisted_account = oldest_account

    # 既存のアカウントが見つからなかった場合、新しいアカウント情報を DB に保存
    # ここで twitter_account.id が新規に auto-increment で自動採番される
    else:
        await twitter_account.save()
        logging.info(f'[TwitterRouter][TwitterCookieAuthAPI] Created new account. [id: {twitter_account.id}, screen_name: {twitter_account.screen_name}]')

        # 永続化後に使う TwitterAccount を設定
        persisted_account = twitter_account

    # Temporary で立ち上げた GraphQL API インスタンスを永続化後の ID に紐づけ直す
    if persisted_account is not None:
        await TwitterGraphQLAPI.rebindInstance(temporary_account_id, persisted_account)
        twitter_account = persisted_account

    # 古い形式のレコード (access_token が "NETSCAPE_COOKIE_FILE" でない) を自動削除
    ## これにより、古い OAuth 認証や旧 Cookie 形式のレコードが処理に用いられないようにする
    deleted_count = await TwitterAccount.filter(
        user_id = current_user.id,
    ).exclude(access_token = 'NETSCAPE_COOKIE_FILE').delete()
    if deleted_count > 0:
        logging.info(f'[TwitterRouter][TwitterCookieAuthAPI] Deleted {deleted_count} old format account(s).')

    # 処理完了
    logging.info(f'[TwitterRouter][TwitterCookieAuthAPI] Logged in with cookie. [id: {twitter_account.id}, screen_name: {twitter_account.screen_name}]')


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

    # Twitter アカウントレコードの ID を取得（削除前に取得する必要がある）
    # この値は Twitter 側のアカウント ID とは異なるので注意
    twitter_account_id = twitter_account.id

    # 指定された Twitter アカウントのレコードを削除
    ## Cookie 情報などが保持されたレコードを削除することで連携解除とする
    await twitter_account.delete()

    # シングルトンインスタンスを削除してリソースリークを防ぐ
    await TwitterGraphQLAPI.removeInstance(twitter_account_id)


@router.post(
    '/accounts/{screen_name}/keep-alive',
    summary = 'Twitter ヘッドレスブラウザ Keep-Alive API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def TwitterKeepAliveAPI(
    twitter_account: Annotated[TwitterAccount, Depends(GetCurrentTwitterAccount)],
):
    """
    この API がユーザーが視聴画面の Twitter パネルで操作を継続している間アクセスされ続けることで、起動中のヘッドレスブラウザの自動シャットダウンを抑制する。<br>
    JWT エンコードされたアクセストークンが Authorization: Bearer に設定されていないとアクセスできない。
    """

    await TwitterGraphQLAPI(twitter_account).keepAlive()


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
        # 画像をアップロードするタスク
        # TODO: 本来はここもヘッドレスブラウザ経由で送信すべきだが、おそらく画像の受け渡しが面倒なのと、
        # upload.x.com のみ他の API と異なり v1.1 時代からほぼそのままで Bot 対策も比較的緩そうなので当面これで行く…
        logging.info(f'[TwitterRouter][TwitterTweetAPI] Uploading {len(images)} images...')
        tweepy_api = twitter_account.getTweepyAPI()
        image_upload_task: list[Coroutine[Any, Any, Any | None]] = []
        for image in images:
            image_upload_task.append(asyncio.to_thread(tweepy_api.media_upload,
                filename = image.filename,
                file = image.file,
                # Twitter Web App の挙動に合わせて常にチャンク送信方式でアップロードする
                chunked = True,
                # Twitter Web App の挙動に合わせる
                media_category = 'tweet_image',
            ))

        # 画像を Twitter にアップロード
        ## asyncio.gather() で同時にアップロードし、ツイートをより早く送信できるように
        ## ref: https://developer.twitter.com/ja/docs/media/upload-media/api-reference/post-media-upload-init
        for image_upload_result in await asyncio.gather(*image_upload_task):
            if image_upload_result is not None:
                logging.info(f'[TwitterRouter][TwitterTweetAPI] Uploaded image. [media_id: {image_upload_result.media_id}]')
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
        return schemas.TwitterAPIResult(
            is_success = False,
            detail = error_message,
        )

    # スパム判定対策のため、ランダムに2〜5秒待機
    await asyncio.sleep(random.uniform(2, 5))

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

    return await TwitterGraphQLAPI(twitter_account).homeLatestTimeline(
        cursor_id = cursor_id,
    )


@router.get(
    '/accounts/{screen_name}/search',
    summary = 'ツイート検索 API',
    response_description = '検索結果のツイートのリスト。',
    response_model = schemas.TimelineTweetsResult | schemas.TwitterAPIResult,
)
async def TwitterSearchAPI(
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
    )


@router.get(
    '/video-proxy',
    summary = 'Twitter 動画プロキシ API',
    response_class = StreamingResponse,
)
async def TwitterVideoProxyAPI(
    request: Request,
    url: Annotated[str, Query(description='プロキシ対象の Twitter 動画 URL 。')],
):
    """
    Twitter の動画を KonomiTV サーバー経由でプロキシ配信する。<br>
    Twitter 側の仕様変更により、許可されたオリジン以外からの動画 URL への直接アクセスが<br>
    403 Forbidden で拒否されるようになったため、サーバー側でリクエストを中継することでこの制限を回避する。<br>
    Range リクエストに対応しており、動画のシーク操作が可能。<br>
    セキュリティ上の理由から、`video.twimg.com` および `pbs.twimg.com` ドメインの HTTPS URL のみプロキシを許可する。
    """

    # Twitter 動画のプロキシで許可するドメインのリスト
    ALLOWED_VIDEO_PROXY_DOMAINS = ['video.twimg.com', 'pbs.twimg.com']

    # URL のバリデーション: スキームが https であること
    parsed_url = urlparse(url)
    if parsed_url.scheme != 'https':
        logging.error(f'[TwitterRouter][TwitterVideoProxyAPI] URL scheme must be https: {parsed_url.scheme}')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'URL scheme must be https.',
        )

    # URL のバリデーション: Twitter の動画ドメインのみ許可
    if parsed_url.hostname not in ALLOWED_VIDEO_PROXY_DOMAINS:
        logging.error(f'[TwitterRouter][TwitterVideoProxyAPI] URL domain is not allowed: {parsed_url.hostname}')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = f'URL domain is not allowed. Only {", ".join(ALLOWED_VIDEO_PROXY_DOMAINS)} are allowed.',
        )

    # リクエストヘッダの構築
    ## Range ヘッダを転送することで、動画のシーク操作に対応する
    proxy_headers: dict[str, str] = {
        'User-Agent': API_REQUEST_HEADERS['User-Agent'],
    }
    allowed_request_headers = ['range', 'accept', 'accept-encoding', 'if-range', 'if-none-match', 'if-modified-since']
    for key, value in request.headers.items():
        if key.lower() in allowed_request_headers:
            proxy_headers[key] = value

    # httpx クライアントを作成し、ストリーミングモードでリクエストを送信
    ## メモリ効率のためにレスポンスボディを一括で読み込まず、チャンク単位でストリーミング転送する
    client = httpx.AsyncClient(follow_redirects=True, timeout=30.0)
    try:
        upstream_request = client.build_request('GET', url, headers=proxy_headers)
        upstream_response = await client.send(upstream_request, stream=True)
    except Exception as ex:
        await client.aclose()
        logging.error('[TwitterRouter][TwitterVideoProxyAPI] Failed to request upstream:', exc_info=ex)
        raise HTTPException(
            status_code = status.HTTP_502_BAD_GATEWAY,
            detail = f'Failed to request upstream: {ex}',
        )

    # 上流サーバーからエラーレスポンスが返された場合はクリーンアップしてエラーを返す
    if upstream_response.status_code >= 400:
        error_body = await upstream_response.aread()
        await upstream_response.aclose()
        await client.aclose()
        error_text = error_body[:200].decode('utf-8', errors='replace')
        logging.error(f'[TwitterRouter][TwitterVideoProxyAPI] Upstream returned HTTP {upstream_response.status_code}: {error_text}')
        raise HTTPException(
            status_code = upstream_response.status_code,
            detail = f'Upstream returned HTTP {upstream_response.status_code}.',
        )

    # レスポンスヘッダの構築
    ## 動画のストリーミング再生に必要なヘッダを転送する
    allowed_response_headers = [
        'content-type',
        'content-length',
        'content-range',
        'accept-ranges',
        'cache-control',
        'etag',
        'last-modified',
    ]
    response_headers = {key: value for key, value in upstream_response.headers.items() if key.lower() in allowed_response_headers}

    # ストリーミングレスポンスの完了後にクリーンアップを行う BackgroundTask
    async def cleanup() -> None:
        await upstream_response.aclose()
        await client.aclose()

    return StreamingResponse(
        upstream_response.aiter_bytes(chunk_size=65536),
        status_code = upstream_response.status_code,
        headers = response_headers,
        background = BackgroundTask(cleanup),
    )
