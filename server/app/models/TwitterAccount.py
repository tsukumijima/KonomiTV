
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import asyncio
import json
import tweepy
from requests.cookies import RequestsCookieJar
from tortoise import fields
from tortoise import models
from tweepy_authlib import CookieSessionUserHandler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.User import User


class TwitterAccount(models.Model):

    # データベース上のテーブル名
    class Meta:  # type: ignore
        table: str = 'twitter_accounts'

    # テーブル設計は Notion を参照のこと
    id: int = fields.IntField(pk=True)  # type: ignore
    user: fields.ForeignKeyRelation[User] = \
        fields.ForeignKeyField('models.User', related_name='twitter_accounts', on_delete=fields.CASCADE)
    user_id: int
    name: str = fields.TextField()  # type: ignore
    screen_name: str = fields.TextField()  # type: ignore
    icon_url: str = fields.TextField()  # type: ignore
    access_token: str = fields.TextField()  # type: ignore
    access_token_secret: str = fields.TextField()  # type: ignore
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    @property
    def is_oauth_session(self) -> bool:
        return self.access_token != 'COOKIE_SESSION'


    @classmethod
    async def updateAccountInformation(cls):
        """ Twitter のアカウント情報を更新する """

        # 登録されているすべての Twitter アカウントの情報を更新する
        for twitter_account in await TwitterAccount.all():

            # アイコン URL が Temporary になってる仮のアカウント情報が何らかの理由で残っていたら、ここで削除する
            if twitter_account.icon_url == 'Temporary':
                await twitter_account.delete()
                continue

            # tweepy の API インスタンスを取得
            api = twitter_account.getTweepyAPI()

            # アカウント情報を更新
            try:
                verify_credentials = await asyncio.to_thread(api.verify_credentials)
            except tweepy.TweepyException:
                continue
            # アカウント名
            twitter_account.name = verify_credentials.name
            # スクリーンネーム
            twitter_account.screen_name = verify_credentials.screen_name
            # アイコン URL
            ## (ランダムな文字列)_normal.jpg だと画像サイズが小さいので、(ランダムな文字列).jpg に置換
            twitter_account.icon_url = verify_credentials.profile_image_url_https.replace('_normal', '')

            # 更新したアカウント情報を保存
            await twitter_account.save()


    def getTweepyAuthHandler(self) -> tweepy.OAuth1UserHandler | CookieSessionUserHandler:
        """
        tweepy の認証ハンドラーを取得する

        Returns:
            tweepy.OAuth1UserHandler | CookieSessionUserHandler: tweepy の認証ハンドラー
        """

        # パスワード認証 (Cookie セッション) の場合
        ## Cookie セッションでは access_token フィールドが "COOKIE_SESSION" の固定値になっている
        if self.access_token == 'COOKIE_SESSION':

            # access_token_secret から Cookie を取得
            cookies_dict: dict[str, str] = json.loads(self.access_token_secret)

            # RequestCookieJar オブジェクトに変換
            cookies = RequestsCookieJar()
            for key, value in cookies_dict.items():
                cookies.set(key, value)

            # 読み込んだ RequestCookieJar オブジェクトを CookieSessionUserHandler に渡す
            ## Cookie を指定する際はコンストラクタ内部で API リクエストは行われないため、ログイン時のように await する必要性はない
            auth_handler = CookieSessionUserHandler(cookies=cookies)

        # 通常の OAuth 認証の場合
        else:
            from app.app import consumer_key, consumer_secret
            auth_handler = tweepy.OAuth1UserHandler(
                consumer_key, consumer_secret, self.access_token, self.access_token_secret,
            )

        return auth_handler


    def getTweepyAPI(self) -> tweepy.API:
        """
        tweepy の API インスタンスを取得する

        Returns:
            tweepy.API: tweepy の API インスタンス
        """

        # auth_handler で初期化した tweepy.API インスタンスを返す
        return tweepy.API(auth=self.getTweepyAuthHandler())
