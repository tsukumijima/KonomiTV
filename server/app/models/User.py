
import json
from tortoise import fields
from tortoise import models
from typing import Any

from app.models import TwitterAccount


class User(models.Model):

    # データベース上のテーブル名
    class Meta:  # type: ignore
        table: str = 'users'

    # テーブル設計は Notion を参照のこと
    id: int = fields.IntField(pk=True)  # type: ignore
    name: str = fields.TextField()  # type: ignore
    password: str = fields.TextField()  # type: ignore
    is_admin: bool = fields.BooleanField()  # type: ignore
    client_settings: dict[str, Any] = fields.JSONField(default={}, encoder=lambda x: json.dumps(x, ensure_ascii=False))  # type: ignore
    niconico_user_id: int | None = fields.IntField(null=True)  # type: ignore
    niconico_user_name: str | None = fields.TextField(null=True)  # type: ignore
    niconico_user_premium: bool | None = fields.BooleanField(null=True)  # type: ignore
    niconico_access_token: str | None = fields.TextField(null=True)  # type: ignore
    niconico_refresh_token: str | None = fields.TextField(null=True)  # type: ignore
    twitter_accounts: fields.ReverseRelation[TwitterAccount]
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
