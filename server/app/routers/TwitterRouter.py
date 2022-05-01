
import asyncio
import tweepy
from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import Form
from fastapi import HTTPException
from fastapi import Path
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


@router.post(
    '/{screen_name}/tweet',
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

    # 指定された Twitter アカウントがユーザーアカウントに紐付けられていない
    ## 実際に Twitter にそのアカウントが登録されているかとは無関係
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
