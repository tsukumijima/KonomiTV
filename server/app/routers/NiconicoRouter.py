
import asyncio
import base64
import json
import requests
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from fastapi import status
from fastapi.security.utils import get_authorization_scheme_param
from jose import jwt
from typing import Optional

from app import schemas
from app.constants import API_REQUEST_HEADERS, NICONICO_OAUTH_CLIENT_ID
from app.models import User
from app.utils import Interlaced
from app.utils import OAuthCallbackResponse


# ルーター
router = APIRouter(
    tags=['Niconico'],
    prefix='/api/niconico',
)


@router.get(
    '/auth',
    summary = 'ニコニコ OAuth 認証 URL 発行 API',
    response_model = schemas.ThirdpartyAuthURL,
    response_description = 'ユーザーにアプリ連携してもらうための認証 URL。',
)
async def NiconicoAuthURLAPI(
    request: Request,
    current_user: User = Depends(User.getCurrentUser),
):
    """
    ニコニコアカウントと連携するための認証 URL を取得する。<br>
    認証 URL をブラウザで開くとアプリ連携の許可を求められ、ユーザーが許可すると /api/niconico/callback に戻ってくる。

    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。<br>
    """

    # コールバック URL を設定
    ## ニコニコ API の OAuth 連携では、事前にコールバック先の URL を運営側に設定しておく必要がある
    ## 一方 KonomiTV サーバーの URL はまちまちなので、コールバック先の URL を一旦 https://app.konomi.tv/api/redirect/niconico に集約する
    ## この API は、リクエストを認証 URL の "state" パラメーター内で指定された KonomiTV サーバーの NiconicoAuthCallbackAPI にリダイレクトする
    ## 最後に KonomiTV サーバーがリダイレクトを受け取ることで、コールバック対象の URL が定まらなくても OAuth 連携ができるようになる
    ## ref: https://github.com/tsukumijima/KonomiTV-API
    callback_url = 'https://app.konomi.tv/api/redirect/niconico'

    # リクエストの Authorization ヘッダーで渡されたログイン中ユーザーの JWT アクセストークンを取得
    # このトークンをコールバック先の NiconicoAuthCallbackAPI に渡し、ログイン中のユーザーアカウントとニコニコアカウントを紐づける
    _, user_access_token = get_authorization_scheme_param(request.headers.get('Authorization'))

    # コールバック後の NiconicoAuthCallbackAPI に渡す state の値
    state = {
        # リダイレクト先の KonomiTV サーバー
        'server': f'{request.url.scheme}://{request.url.netloc}/',
        # ログイン中ユーザーの JWT アクセストークン
        'user_access_token': user_access_token,
    }

    # state は URL パラメータとして送らないといけないので、JSON エンコードしたあと Base64 でエンコードする
    state_base64 = base64.b64encode(json.dumps(state, ensure_ascii=False).encode('utf-8')).decode('utf-8')

    # 末尾の = はニコニコ側でリダイレクトされる際に変に URL エンコードされる事があるので、削除する
    state_base64 = state_base64.replace('=', '')

    # 利用するスコープを指定
    scope = '%20'.join([
        'offline_access',
        'openid',
        'profile',
        'user.authorities.relives.watch.get',
        'user.authorities.relives.watch.interact',
        'user.premium',
    ])

    # 認証 URL を作成
    authorization_url = (
        f'https://oauth.nicovideo.jp/oauth2/authorize?response_type=code&'
        f'scope={scope}&client_id={NICONICO_OAUTH_CLIENT_ID}&redirect_uri={callback_url}&state={state_base64}'
    )

    return {'authorization_url': authorization_url}


@router.get(
    '/callback',
    summary = 'ニコニコ OAuth コールバック API',
    response_class = OAuthCallbackResponse,
    response_description = 'ユーザーアカウントにニコニコアカウントのアクセストークン・リフレッシュトークンが登録できたことを示す。',
)
async def NiconicoAuthCallbackAPI(
    user_access_token: str = Query(None, description='コールバック元から渡された、ユーザーの JWT アクセストークン。'),
    code: Optional[str] = Query(None, description='コールバック元から渡された認証コード。OAuth 認証が成功したときのみセットされる。'),
    error: Optional[str] = Query(None, description='このパラメーターがセットされているとき、OAuth 認証がユーザーによって拒否されたことを示す。'),
):
    """
    ニコニコの OAuth 認証のコールバックを受け取り、ログイン中のユーザーアカウントとニコニコアカウントを紐づける。
    """

    # "error" パラメーターがセットされている
    # OAuth 認証がユーザーによって拒否されたことを示しているので、401 エラーにする
    if error is not None:

        # 401 エラーを送出
        ## コールバック元から渡されたエラーメッセージをそのまま表示する
        return OAuthCallbackResponse(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = f'Authorization was denied ({error})',
        )

    # なぜか code がない
    if code is None:
        return OAuthCallbackResponse(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'authorization code does not exist',
        )

    # JWT アクセストークンに基づくユーザーアカウントを取得
    # この時点でユーザーアカウントが取得できなければ 401 エラーが送出される
    try:
        current_user = await User.getCurrentUser(token=user_access_token)
    except HTTPException as ex:
        return OAuthCallbackResponse(status_code = ex.status_code, detail = ex.message)

    try:

        # 認証コードを使い、ニコニコ OAuth のアクセストークンとリフレッシュトークンを取得
        token_api_url = 'https://oauth.nicovideo.jp/oauth2/token'
        token_api_response = await asyncio.to_thread(
            requests.post,
            url = token_api_url,
            data = {
                'grant_type': 'authorization_code',
                'client_id': NICONICO_OAUTH_CLIENT_ID,
                'client_secret': Interlaced(3),
                'code': code,
                'redirect_uri': 'https://app.konomi.tv/api/redirect/niconico',
            },
            headers = {**API_REQUEST_HEADERS, 'Content-Type': 'application/x-www-form-urlencoded'},
            timeout = 3,  # 3秒応答がなかったらタイムアウト
        )

        # ステータスコードが 200 以外
        if token_api_response.status_code != 200:
            return OAuthCallbackResponse(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail = f'Failed to get access token (HTTP Error {token_api_response.status_code})',
            )

        token_api_response_json = token_api_response.json()

    # 接続エラー（サーバーメンテナンスやタイムアウトなど）
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return OAuthCallbackResponse(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Failed to get access token',
        )

    # 取得したアクセストークンとリフレッシュトークンをユーザーアカウントに設定
    ## アクセストークンは1時間で有効期限が切れるので、適宜リフレッシュトークンで再取得する
    current_user.niconico_access_token = str(token_api_response_json['access_token'])
    current_user.niconico_refresh_token = str(token_api_response_json['refresh_token'])

    # ニコニコアカウントのユーザー ID を取得
    # ユーザー ID は id_token の JWT の中に含まれている
    id_token_jwt = jwt.get_unverified_claims(token_api_response_json['id_token'])
    current_user.niconico_user_id = int(id_token_jwt.get('sub'))

    try:

        # ニコニコアカウントのユーザー情報を取得
        ## 3秒応答がなかったらタイムアウト
        user_api_url = f'https://nvapi.nicovideo.jp/v1/users/{current_user.niconico_user_id}'
        user_api_headers = {**API_REQUEST_HEADERS, 'X-Frontend-Id': '6'}  # X-Frontend-Id がないと INVALID_PARAMETER になる
        user_api_response = await asyncio.to_thread(requests.get, user_api_url, headers=user_api_headers, timeout=3)

        # ステータスコードが 200 以外
        if user_api_response.status_code != 200:
            return OAuthCallbackResponse(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail = f'Failed to get user information (HTTP Error {user_api_response.status_code})',
            )

        # ユーザー名
        current_user.niconico_user_name = str(user_api_response.json()['data']['user']['nickname'])
        # プレミアム会員かどうか
        current_user.niconico_user_premium = bool(user_api_response.json()['data']['user']['isPremium'])

    # 接続エラー（サーバー再起動やタイムアウトなど）
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return OAuthCallbackResponse(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Failed to get user information',
        )

    # 変更をデータベースに保存
    await current_user.save()

    # OAuth 連携が正常に完了したことを伝える
    return OAuthCallbackResponse(
        status_code = status.HTTP_200_OK,
        detail = 'Success',
    )


@router.delete(
    '/logout',
    summary = 'ニコニコアカウント連携解除 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def NiconicoAccountLogoutAPI(
    current_user: User = Depends(User.getCurrentUser),
):
    """
    現在ログイン中のユーザーアカウントに紐づくニコニコアカウントとの連携を解除する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    # ニコニコ関連のフィールドをすべて None (null) にすることで連携解除とする
    current_user.niconico_user_id = None
    current_user.niconico_user_name = None
    current_user.niconico_user_premium = None
    current_user.niconico_access_token = None
    current_user.niconico_refresh_token = None
    await current_user.save()