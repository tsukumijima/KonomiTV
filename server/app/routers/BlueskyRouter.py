
from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)

from app import logging, schemas
from app.models.BlueskyAccount import BlueskyAccount
from app.models.User import User
from app.routers.UsersRouter import GetCurrentUser
from app.utils.BlueskyAPI import BlueskyAPI


# ルーター
router = APIRouter(
    tags = ['Bluesky'],
    prefix = '/api/bluesky',
)


async def GetCurrentBlueskyAccount(
    handle: Annotated[str, Path(description='Bluesky アカウントの handle。')],
    current_user: Annotated[User, Depends(GetCurrentUser)],
) -> BlueskyAccount:
    """ 現在ログイン中のユーザーに紐づく Bluesky アカウントを取得する """

    # handle は変更可能だが、API パスでは UI 上の識別子として使う
    # 実際の更新・削除操作ではログイン中ユーザーに紐づくレコードだけに絞り込み、他ユーザーの認証情報へ触れないようにする
    normalized_handle = BlueskyAPI.normalizeBlueskyHandle(handle)
    bluesky_account = await BlueskyAccount.filter(user_id=current_user.id, handle=normalized_handle).get_or_none()
    if bluesky_account is None:
        logging.error(f'[BlueskyRouter][GetCurrentBlueskyAccount] BlueskyAccount associated with handle does not exist. [handle: {normalized_handle}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'BlueskyAccount associated with handle does not exist',
        )

    return bluesky_account


@router.post(
    '/auth',
    summary = 'Bluesky 認証 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def BlueskyAuthAPI(
    auth_request: Annotated[schemas.BlueskyAuthRequest, Body(description='Bluesky 認証リクエスト')],
    current_user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    指定された handle と App Password で Bluesky 連携を行い、ログイン中のユーザーアカウントと Bluesky アカウントを紐づける。
    """

    # 認証処理では App Password を使って atproto SDK のセッションを作成し、保存用の ORM インスタンスへ変換する
    try:
        bluesky_account = await BlueskyAPI.authenticate(auth_request.handle, auth_request.app_password)
    except Exception as ex:
        logging.error('[BlueskyRouter][BlueskyAuthAPI] Failed to login to Bluesky:', exc_info=ex)
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Failed to login to Bluesky',
        ) from ex

    # authenticate() はユーザーに紐づかない未保存インスタンスを返すため、ここでログイン中ユーザーへ接続する
    bluesky_account.user = current_user

    # 同じ DID のアカウントが既にある場合は、セッションとプロフィール情報を更新する
    existing_account = await BlueskyAccount.filter(user_id=current_user.id, did=bluesky_account.did).get_or_none()
    if existing_account is not None:
        existing_account.handle = bluesky_account.handle
        existing_account.name = bluesky_account.name
        existing_account.icon_url = bluesky_account.icon_url
        existing_account.session_string = bluesky_account.session_string
        await existing_account.save()
        logging.info(f'[BlueskyRouter][BlueskyAuthAPI] Updated existing Bluesky account. [id: {existing_account.id}, handle: {existing_account.handle}]')
        return

    await bluesky_account.save()
    logging.info(f'[BlueskyRouter][BlueskyAuthAPI] Created new Bluesky account. [id: {bluesky_account.id}, handle: {bluesky_account.handle}]')


@router.delete(
    '/accounts/{handle}',
    summary = 'Bluesky アカウント連携解除 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def BlueskyAccountDeleteAPI(
    bluesky_account: Annotated[BlueskyAccount, Depends(GetCurrentBlueskyAccount)],
):
    """
    指定された Bluesky アカウントの連携を解除する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    # BlueskyAccount に紐づく AccountLink は外部キーの cascade で削除される
    await bluesky_account.delete()


@router.post(
    '/accounts/{handle}/posts',
    summary = 'Bluesky 投稿送信 API',
    response_description = 'Bluesky 投稿の送信結果。',
    response_model = schemas.PostTweetResult | schemas.TwitterAPIResult,
)
async def BlueskyPostAPI(
    bluesky_account: Annotated[BlueskyAccount, Depends(GetCurrentBlueskyAccount)],
    post: Annotated[str, Form(description='Bluesky 投稿の本文。')] = '',
    images: Annotated[list[UploadFile], File(description='Bluesky 投稿に添付する画像 (4枚まで) 。')] = [],
):
    """
    Bluesky に投稿を送信する。投稿本文 or 画像のみ送信することもできる。<br>
    投稿には handle で指定した Bluesky アカウントが利用される。
    """

    # 本文と画像の検証・画像圧縮・セッション復元は BlueskyAPI 側に集約する
    return await BlueskyAPI(bluesky_account).createPost(post, images)


@router.put(
    '/accounts/{handle}/posts/repost',
    summary = 'Bluesky リポスト実行 API',
    response_description = 'Bluesky リポストの実行結果。',
    response_model = schemas.TwitterAPIResult,
)
async def BlueskyRepostAPI(
    action_request: Annotated[schemas.BlueskyPostActionRequest, Body(description='Bluesky 投稿操作リクエスト')],
    bluesky_account: Annotated[BlueskyAccount, Depends(GetCurrentBlueskyAccount)],
):
    """
    指定された Bluesky 投稿をリポストする。<br>
    リポストには handle で指定した Bluesky アカウントが利用される。
    """

    # atproto のリポスト作成には URI だけでなく CID も必要なため、クライアントの古い表示データをここで弾く
    if action_request.bluesky_cid is None:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'bluesky_cid is required',
        )
    return await BlueskyAPI(bluesky_account).createRepost(action_request.bluesky_uri, action_request.bluesky_cid)


@router.delete(
    '/accounts/{handle}/posts/repost',
    summary = 'Bluesky リポスト取り消し API',
    response_description = 'Bluesky リポストの取り消し結果。',
    response_model = schemas.TwitterAPIResult,
)
async def BlueskyRepostCancelAPI(
    action_request: Annotated[schemas.BlueskyPostActionRequest, Body(description='Bluesky 投稿操作リクエスト')],
    bluesky_account: Annotated[BlueskyAccount, Depends(GetCurrentBlueskyAccount)],
):
    """
    指定された Bluesky 投稿のリポストを取り消す。<br>
    リポストの取り消しには handle で指定した Bluesky アカウントが利用される。
    """

    return await BlueskyAPI(bluesky_account).deleteRepost(action_request.bluesky_uri)


@router.put(
    '/accounts/{handle}/posts/like',
    summary = 'Bluesky like 実行 API',
    response_description = 'Bluesky like の実行結果。',
    response_model = schemas.TwitterAPIResult,
)
async def BlueskyLikeAPI(
    action_request: Annotated[schemas.BlueskyPostActionRequest, Body(description='Bluesky 投稿操作リクエスト')],
    bluesky_account: Annotated[BlueskyAccount, Depends(GetCurrentBlueskyAccount)],
):
    """
    指定された Bluesky 投稿を like する。<br>
    like には handle で指定した Bluesky アカウントが利用される。
    """

    # like 作成も StrongRef (URI + CID) が必要なので、CID の欠落は API 呼び出し前に 422 として返す
    if action_request.bluesky_cid is None:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'bluesky_cid is required',
        )
    return await BlueskyAPI(bluesky_account).favoritePost(action_request.bluesky_uri, action_request.bluesky_cid)


@router.delete(
    '/accounts/{handle}/posts/like',
    summary = 'Bluesky like 取り消し API',
    response_description = 'Bluesky like の取り消し結果。',
    response_model = schemas.TwitterAPIResult,
)
async def BlueskyLikeCancelAPI(
    action_request: Annotated[schemas.BlueskyPostActionRequest, Body(description='Bluesky 投稿操作リクエスト')],
    bluesky_account: Annotated[BlueskyAccount, Depends(GetCurrentBlueskyAccount)],
):
    """
    指定された Bluesky 投稿の like を取り消す。<br>
    like の取り消しには handle で指定した Bluesky アカウントが利用される。
    """

    return await BlueskyAPI(bluesky_account).unfavoritePost(action_request.bluesky_uri)


@router.get(
    '/accounts/{handle}/timeline',
    summary = 'Bluesky ホームタイムライン取得 API',
    response_description = 'Bluesky タイムラインの投稿リスト。',
    response_model = schemas.TimelineTweetsResult | schemas.TwitterAPIResult,
)
async def BlueskyTimelineAPI(
    bluesky_account: Annotated[BlueskyAccount, Depends(GetCurrentBlueskyAccount)],
    cursor_id: Annotated[str | None, Query(description='前回のレスポンスから取得した、次のページを取得するための cursor 。')] = None,
):
    """
    Bluesky のホームタイムラインを取得する。<br>
    ホームタイムラインの取得には handle で指定した Bluesky アカウントが利用される。
    """

    return await BlueskyAPI(bluesky_account).homeLatestTimeline(cursor_id=cursor_id)


@router.get(
    '/accounts/{handle}/search',
    summary = 'Bluesky 投稿検索 API',
    response_description = 'Bluesky 検索結果の投稿リスト。',
    response_model = schemas.TimelineTweetsResult | schemas.TwitterAPIResult,
)
async def BlueskySearchAPI(
    bluesky_account: Annotated[BlueskyAccount, Depends(GetCurrentBlueskyAccount)],
    query: Annotated[str, Query(description='検索クエリ。')],
    cursor_id: Annotated[str | None, Query(description='前回のレスポンスから取得した、次のページを取得するための cursor 。')] = None,
):
    """
    指定されたクエリで Bluesky 投稿を検索する。
    """

    return await BlueskyAPI(bluesky_account).searchTimeline(query=query, cursor_id=cursor_id)
