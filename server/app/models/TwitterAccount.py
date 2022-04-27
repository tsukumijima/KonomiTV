
from datetime import datetime
from tortoise import fields
from tortoise import models

from app.models import User


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
