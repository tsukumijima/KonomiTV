
import datetime
from tortoise import fields
from tortoise import models


class User(models.Model):

    # データベース上のテーブル名
    class Meta:
        table:str = 'users'

    # テーブル設計は Notion を参照のこと
    id:int = fields.IntField(pk=True)
    name:str = fields.TextField()
    password:str = fields.TextField()
    is_admin:bool = fields.BooleanField()
    client_settings:dict = fields.JSONField()
    niconico_user_id:int = fields.IntField(null=True)
    niconico_user_name:str = fields.TextField(null=True)
    niconico_access_token:str = fields.TextField(null=True)
    niconico_refresh_token:str = fields.TextField(null=True)
    created_at:datetime.datetime = fields.DatetimeField(auto_now_add=True)
    updated_at:datetime.datetime = fields.DatetimeField(auto_now=True)
