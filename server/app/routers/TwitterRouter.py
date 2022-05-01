
import asyncio
import tweepy
from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import Form
from fastapi import HTTPException
from fastapi import Path
from fastapi import Query
from fastapi import Request
from fastapi import status
from fastapi import UploadFile
from typing import Coroutine, List, Optional

from app import schemas
from app.models import TwitterAccount
from app.models import User
from app.utils import Interlaced


# ルーター
router = APIRouter(
    tags=['Twitter'],
    prefix='/api/twitter',
)


# Twitter API のエラーメッセージの定義
## 実際に返ってくる可能性があるものだけ
## ref: https://developer.twitter.com/ja/docs/basics/response-codes
error_messages = {
    32:  'アカウントの認証に失敗しました。',
    63:  'アカウントが凍結またはロックされています。',
    64:  'アカウントが凍結またはロックされています。',
    88:  'API エンドポイントのレート制限を超えました。',
    89:  'アクセストークンの有効期限が切れています。',
    99:  'OAuth クレデンシャルの認証に失敗しました。',
    131: 'Twitter でサーバーエラーが発生しています。',
    135: 'アカウントの認証に失敗しました。',
    139: 'すでにいいねされています。',
    144: 'ツイートが削除されています。',
    179: 'フォローしていない非公開アカウントのツイートは表示できません。',
    185: 'ツイート数の上限に達しました。',
    186: 'ツイートが長過ぎます。',
    187: 'ツイートが重複しています。',
    226: 'ツイートが自動化されたスパムと判定されました。',
    261: 'Twitter API アプリケーションが凍結されています。',
    326: 'アカウントが一時的にロックされています。',
    327: 'すでにリツイートされています。',
    416: 'Twitter API アプリケーションが無効化されています。',
}


@router.get(
    '/auth',
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
    '/callback',
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
    Twitter の認証のコールバックを受け取り、ログイン中のユーザーアカウントに Twitter アカウントを連携する。
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
    oauth_handler = tweepy.OAuth1UserHandler(Interlaced(1), Interlaced(2))
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
            detail = 'Failed to get access token',
        )

    # tweepy を初期化
    api = tweepy.API(tweepy.OAuth1UserHandler(
        Interlaced(1), Interlaced(2), twitter_account.access_token, twitter_account.access_token_secret,
    ))

    # アカウント情報を更新
    try:
        verify_credentials = await asyncio.to_thread(api.verify_credentials)
    except tweepy.TweepyException:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Failed to get account information',
        )
    # アカウント名
    twitter_account.name = verify_credentials.name
    # スクリーンネーム
    twitter_account.screen_name = verify_credentials.screen_name
    # アイコン URL
    ## (ランダムな文字列)_normal.jpg だと画像サイズが小さいので、(ランダムな文字列).jpg に置換
    twitter_account.icon_url = verify_credentials.profile_image_url_https.replace('_normal', '')

    # 同じスクリーンネームを持つアカウントが重複している場合、古い方のレコードのデータを更新する
    # すでに作成されている新しいレコード（まだ save() していないので仮の情報しか入っていない）は削除される
    twitter_account_existing = await TwitterAccount.filter(user_id=twitter_account.user_id, screen_name=twitter_account.screen_name).get_or_none()
    if twitter_account_existing is not None:
        twitter_account_existing.name = twitter_account.name  # アカウント名
        twitter_account_existing.icon_url = twitter_account.icon_url  # アイコン URL
        twitter_account_existing.access_token = twitter_account.access_token  # アクセストークン
        twitter_account_existing.access_token_secret = twitter_account.access_token_secret  # アクセストークンシークレット
        await twitter_account_existing.save()
        await twitter_account.delete()

        return {'detail': 'Success'}

    # アクセストークンとアカウント情報を保存
    await twitter_account.save()

    # 完了を確認できるように、適当に何か返しておく
    ## 204 No Content だと画面遷移が発生しない
    return {'detail': 'Success'}


@router.post(
    '/accounts/{screen_name}/tweets',
    summary = 'ツイート送信 API',
    response_description = 'ツイートの送信結果。',
    response_model = schemas.TweetResult,
)
async def TwitterTweetAPI(
    screen_name: str = Path(..., description='ツイートする Twitter アカウントのスクリーンネーム。'),
    tweet: str = Form(..., description='ツイートの本文（基本的には140文字まで）。'),
    images: Optional[List[UploadFile]] = File(None, description='ツイートに添付する画像（4枚まで）。'),
    current_user: User = Depends(User.getCurrentUser),
):
    """
    Twitter にツイートを送信する。<br>
    ツイートには screen_name で指定したスクリーンネームに紐づく Twitter アカウントが利用される。

    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    # 指定されたスクリーンネームに紐づく Twitter アカウントを取得
    # 自分が所有していない Twitter アカウントでツイートできないよう、ログイン中のユーザーに限って絞り込む
    twitter_account = await TwitterAccount.filter(user_id=current_user.id, screen_name=screen_name).get_or_none()

    # 指定された Twitter アカウントがユーザーアカウントに紐付けられていない or 登録されていない
    ## 実際に Twitter にそのスクリーンネームのアカウントが登録されているかとは無関係
    if not twitter_account:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'TwitterAccount associated with screen_name does not exist',
        )

    # 画像が4枚を超えている
    if images is None:
        images = []
    if len(images) > 4:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Can tweet up to 4 images',
        )

    # tweepy を初期化
    api = tweepy.API(tweepy.OAuth1UserHandler(
        Interlaced(1), Interlaced(2), twitter_account.access_token, twitter_account.access_token_secret,
    ))

    # アップロードした画像の media_id のリスト
    media_ids: List[str] = []

    try:

        # 画像をアップロードするタスク
        image_upload_task: List[Coroutine] = []
        for image in images:
            image_upload_task.append(asyncio.to_thread(api.media_upload, filename=image.filename, file=image.file))

        # 画像を Twitter にアップロード
        ## asyncio.gather() で同時にアップロードし、ツイートをより早く送信できるように
        ## ref: https://developer.twitter.com/ja/docs/media/upload-media/api-reference/post-media-upload-init
        for image_upload_result in await asyncio.gather(*image_upload_task):
            media_ids.append(image_upload_result.media_id)

        # ツイートを送信
        result = await asyncio.to_thread(api.update_status, tweet, media_ids=media_ids)

    # 送信失敗
    except tweepy.HTTPException as ex:

        # API のエラーコードがない
        if len(ex.api_codes) == 0:
            return {
                'is_success': False,
                'detail': f'Message: {ex.api_errors[0]} (HTTP Error {ex.response.status_code})',
            }

        # エラーメッセージ
        # 定義されていないエラーコードの時は Twitter API から返ってきたエラーをそのまま返す
        return {
            'is_success': False,
            'detail': error_messages.get(1, f'Code: {ex.api_codes[0]}, Message: {ex.api_messages[0]}'),
        }

    return {
        'is_success': True,
        'tweet_url': f'https://twitter.com/{result.user.screen_name}/status/{result.id}',
        'detail': 'ツイートを送信しました。',
    }
