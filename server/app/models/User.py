
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import json
from tortoise import fields
from tortoise.fields import Field as TortoiseField
from tortoise.models import Model as TortoiseModel
from typing import Any, cast, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.TwitterAccount import TwitterAccount


class User(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'users'

    # テーブル設計は Notion を参照のこと
    id = fields.IntField(pk=True)
    name = fields.TextField()
    password = fields.TextField()
    is_admin = fields.BooleanField()
    client_settings = cast(TortoiseField[dict[str, Any]], fields.JSONField(default={}, encoder=lambda x: json.dumps(x, ensure_ascii=False)))  # type: ignore
    niconico_user_id = cast(TortoiseField[int | None], fields.IntField(null=True))
    niconico_user_name = cast(TortoiseField[str | None], fields.TextField(null=True))
    niconico_user_premium = cast(TortoiseField[bool | None], fields.BooleanField(null=True))
    niconico_access_token = cast(TortoiseField[str | None], fields.TextField(null=True))
    niconico_refresh_token = cast(TortoiseField[str | None], fields.TextField(null=True))
    twitter_accounts: fields.ReverseRelation[TwitterAccount]
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
