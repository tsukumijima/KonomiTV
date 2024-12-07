
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import asyncio
import json
import time
import tweepy
from requests.cookies import RequestsCookieJar
from tortoise import fields
from tortoise.models import Model as TortoiseModel
from tweepy_authlib import CookieSessionUserHandler
from typing import TYPE_CHECKING

from app import logging

if TYPE_CHECKING:
    from app.models.User import User


class TwitterAccount(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'twitter_accounts'

    # テーブル設計は Notion を参照のこと
    id = fields.IntField(pk=True)
    user: fields.ForeignKeyRelation[User] = \
        fields.ForeignKeyField('models.User', related_name='twitter_accounts', on_delete=fields.CASCADE)
    user_id: int
    name = fields.TextField()
    screen_name = fields.TextField()
    icon_url = fields.TextField()
    access_token = fields.TextField()
    access_token_secret = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)


    @classmethod
    async def updateAccountsInformation(cls):
        """ 登録されているすべての Twitter アカウントの情報を更新する """

        timestamp = time.time()
        logging.info('Twitter accounts updating...')

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
            except tweepy.TweepyException as ex:
                logging.error(f'Failed to get user information for Twitter account @{twitter_account.screen_name}')
                logging.error(ex)
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

        logging.info(f'Twitter accounts update complete. ({round(time.time() - timestamp, 3)} sec)')

        # せっかくなので Twitter GraphQL API のエンドポイント情報もここで更新する
        from app.utils.TwitterGraphQLAPI import TwitterGraphQLAPI
        await TwitterGraphQLAPI.updateEndpointInfos()


    def getTweepyAuthHandler(self) -> CookieSessionUserHandler:
        """
        tweepy の認証ハンドラーを取得する

        Returns:
            CookieSessionUserHandler: tweepy の認証ハンドラー (Cookie セッション)
        """

        # Cookie ログイン or パスワードログイン の場合
        ## Cookie ログインの場合は access_token フィールドが "DIRECT_COOKIE_SESSION" の固定値になっている
        ## パスワードログインの場合は access_token フィールドが "COOKIE_SESSION" の固定値になっている
        if self.access_token in ['DIRECT_COOKIE_SESSION', 'COOKIE_SESSION']:

            # access_token_secret から Cookie を取得
            cookies_dict: dict[str, str] = json.loads(self.access_token_secret)

            # RequestCookieJar オブジェクトに変換
            cookies = RequestsCookieJar()
            for key, value in cookies_dict.items():
                cookies.set(key, value)

            # 読み込んだ RequestCookieJar オブジェクトを CookieSessionUserHandler に渡す
            ## Cookie を指定する際はコンストラクタ内部で API リクエストは行われないため、ログイン時のように await する必要性はない
            auth_handler = CookieSessionUserHandler(cookies=cookies)

        # OAuth 認証 (廃止) の場合
        else:
            assert False, 'OAuth session is no longer available.'

        return auth_handler


    def getTweepyAPI(self) -> tweepy.API:
        """
        tweepy の API インスタンスを取得する

        Returns:
            tweepy.API: tweepy の API インスタンス
        """

        # auth_handler で初期化した tweepy.API インスタンスを返す
        return tweepy.API(auth=self.getTweepyAuthHandler())
