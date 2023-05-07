
import json
from tortoise import fields
from tortoise import models
from typing import Any

from app.models import TwitterAccount


class User(models.Model):

    # データベース上のテーブル名
    class Meta:
        table: str = 'users'

    # テーブル設計は Notion を参照のこと
    id: int = fields.IntField(pk=True)
    name: str = fields.TextField()
    password: str = fields.TextField()
    is_admin: bool = fields.BooleanField()  # type: ignore
    client_settings: dict[str, Any] = fields.JSONField(encoder=lambda x: json.dumps(x, ensure_ascii=False))
    niconico_user_id: int | None = fields.IntField(null=True)
    niconico_user_name: str | None = fields.TextField(null=True)
    niconico_user_premium: bool | None = fields.BooleanField(null=True)  # type: ignore
    niconico_access_token: str | None = fields.TextField(null=True)
    niconico_refresh_token: str | None = fields.TextField(null=True)
    twitter_accounts: fields.ReverseRelation[TwitterAccount]
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
