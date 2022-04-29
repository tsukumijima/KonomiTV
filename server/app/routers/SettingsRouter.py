
import asyncio
import tweepy
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from fastapi import status
from typing import Optional

from app import schemas
from app.models import TwitterAccount
from app.models import User
from app.utils import Interlaced

# ルーター
router = APIRouter(
    tags=['Settings'],
    prefix='/api/settings',
)


@router.get(
    '/twitter/auth',
    summary = 'Twitter 認証 URL 発行 API',
    response_model = schemas.TwitterAuthURL,
    response_description = 'ユーザーにアプリ連携してもらうための認証 URL。',
)
async def TwitterAuthURLAPI(
    request: Request,
    current_user: User = Depends(User.getCurrentUser),
):
    """
    Twitter アカウントと連携するための認証 URL を取得する。<br>
    認証 URL をブラウザで開くとアプリ連携の許可を求められ、ユーザーが許可すると TwitterAuthCallbackAPI に戻ってくる。

    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。<br>
    """

    # コールバック URL を設定
    ## Twitter API では事前にコールバック先の URL をデベロッパーダッシュボードから設定しておく必要がある
    ## 一方 KonomiTV サーバーの URL は当然ながら環境によってバラバラなため、コールバック URL を https://app.konomi.tv/api/redirect/twitter に集約する
    ## この API はリクエストをそっくりそのまま ?server= で指定された KonomiTV サーバーの TwitterAuthCallbackAPI にリダイレクトする
    ## こうすることで、コールバック URL が1つに定まらなくても、コールバック結果 (oauth_verifier) を KonomiTV サーバーに返せるようになる
    ## ref: https://github.com/tsukumijima/KonomiTV-API
    callback_url = f'https://app.konomi.tv/api/redirect/twitter?server={request.url.scheme}://{request.url.netloc}/'

    # OAuth1UserHandler を初期化し、認証 URL を取得
    ## signin_with_twitter を True に設定すると、oauth/authenticate の認証 URL が生成される
    ## oauth/authorize と異なり、すでにアプリ連携している場合は再承認することなくコールバック URL にリダイレクトされる
    ## ref: https://developer.twitter.com/ja/docs/authentication/api-reference/authenticate
    try:
        oauth_handler = tweepy.OAuth1UserHandler(Interlaced(1), Interlaced(2), callback=callback_url)
        authorization_url = await asyncio.to_thread(oauth_handler.get_authorization_url, signin_with_twitter=True)  # 同期関数なのでスレッド上で実行
    except tweepy.TweepyException:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Failed to get Twitter authorization URL',
        )

    # 仮で TwitterAccount のレコードを作成
    ## 戻ってきたときに oauth_token がどのユーザーに紐づいているのかを判断するため
    ## TwitterAuthCallbackAPI は仕組み上認証をかけられないので、勝手に任意のアカウントを紐付けられないためにはこうせざるを得ない
    twitter_account = TwitterAccount()
    twitter_account.user = current_user
    twitter_account.name = 'Temporary'
    twitter_account.screen_name = 'Temporary'
    twitter_account.icon_url = 'Temporary'
    twitter_account.access_token = oauth_handler.request_token['oauth_token']  # 暫定的に oauth_token を格納 (認証 URL の ?oauth_token= と同じ値)
    twitter_account.access_token_secret = oauth_handler.request_token['oauth_token_secret']  # 暫定的に oauth_token_secret を格納
    await twitter_account.save()

    return {'authorization_url': authorization_url}


@router.get(
    '/twitter/callback',
    summary = 'Twitter 認証コールバック API',
    response_model = schemas.TwitterAuthCallbackSuccess,
    response_description = 'ユーザーアカウントに Twitter アカウントのアクセストークン・アクセストークンが登録できたことを示す。',
)
async def TwitterAuthCallbackAPI(
    oauth_token: Optional[str] = Query(None, description='コールバック URL から渡された oauth_token。OAuth 認証が成功したときのみセットされる。'),
    oauth_verifier: Optional[str] = Query(None, description='コールバック URL から渡された oauth_verifier。OAuth 認証が成功したときのみセットされる。'),
    denied: Optional[str] = Query(None, description='このパラメーターがセットされているとき、OAuth 認証がユーザーによって拒否されたことを示す。'),
):
    """
    Twitter の認証のコールバックを受け取り、ユーザーアカウントに Twitter アカウントのアクセストークン・アクセストークンを登録する。

    """

    # "denied" パラメーターがセットされている
    # OAuth 認証がユーザーによって拒否されたことを示しているので、401 エラーにする
    if denied is not None:

        # 認証が失敗したので、TwitterAuthURLAPI で作成されたレコードを削除
        ## "denied" パラメーターの値は oauth_token と同一
        twitter_account = await TwitterAccount.filter(access_token=denied).get_or_none()
        if twitter_account:
            await twitter_account.delete()

        # 401 エラーを送出
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = 'Authorization was denied by user',
        )

    # なぜか oauth_token も oauth_verifier もない
    if oauth_token is None or oauth_verifier is None:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'oauth_token or oauth_verifier does not exist',
        )

    # oauth_token に紐づく Twitter アカウントを取得
    twitter_account = await TwitterAccount.filter(access_token=oauth_token).get_or_none()
    if not twitter_account:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'TwitterAccount associated with oauth_token does not exist',
        )

    # OAuth1UserHandler を初期化
    ## ref: https://docs.tweepy.org/en/latest/authentication.html#legged-oauth
    oauth_handler = tweepy.OAuth1UserHandler(Interlaced(1), Interlaced(2), callback='')
    oauth_handler.request_token = {
        'oauth_token': twitter_account.access_token,
        'oauth_token_secret': twitter_account.access_token_secret,
    }

    # アクセストークン・アクセストークンシークレットを取得し、仮の oauth_token, oauth_token_secret と置き換える
    ## 同期関数なのでスレッド上で実行
    try:
        twitter_account.access_token, twitter_account.access_token_secret = await asyncio.to_thread(oauth_handler.get_access_token, oauth_verifier)
    except tweepy.TweepyException:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Failed to get Twitter access token',
        )

    # アクセストークン・アクセストークンシークレットを保存
    await twitter_account.save()

    # 完了を確認できるように、適当に何か返しておく
    ## 204 No Content だと画面遷移が発生しない
    return {'detail': 'Success'}
