
import asyncio
import tweepy
from datetime import datetime
from tortoise import fields
from tortoise import models

from app.models import User
from app.utils import Interlaced


class TwitterAccount(models.Model):

    # データベース上のテーブル名
    class Meta:
        table:str = 'twitter_accounts'

    # テーブル設計は Notion を参照のこと
    id: int = fields.IntField(pk=True)
    ## クラスが読み込まれる前なので、User(モジュール).User(クラス) のようにしないと参照できない
    user: fields.ForeignKeyRelation['User.User'] = fields.ForeignKeyField('models.User', related_name='twitter_accounts')
    name: str = fields.TextField()
    screen_name: str = fields.TextField()
    icon_url: str = fields.TextField()
    access_token: str = fields.TextField()
    access_token_secret: str = fields.TextField()
    created_at: datetime = fields.DatetimeField(auto_now_add=True)
    updated_at: datetime = fields.DatetimeField(auto_now=True)


    @classmethod
    async def updateAccountInformation(cls):
        """ Twitter のアカウント情報を更新する """

        # 登録されているすべての Twitter アカウントの情報を更新する
        for twitter_account in await TwitterAccount.all():

            # tweepy を初期化
            api = tweepy.API(tweepy.OAuth1UserHandler(
                Interlaced(1), Interlaced(2), twitter_account.access_token, twitter_account.access_token_secret,
            ))

            # アカウント情報を更新
            try:
                verify_credentials = await asyncio.to_thread(api.verify_credentials)
            except tweepy.TweepyException:
                continue
            twitter_account.name = verify_credentials.name
            twitter_account.screen_name = verify_credentials.screen_name
            twitter_account.icon_url = verify_credentials.profile_image_url_https

            # 更新したアカウント情報を保存
            await twitter_account.save()
