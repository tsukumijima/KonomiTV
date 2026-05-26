
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields
from tortoise.models import Model as TortoiseModel


if TYPE_CHECKING:
    from app.models.BlueskyAccount import BlueskyAccount
    from app.models.TwitterAccount import TwitterAccount
    from app.models.User import User


class AccountLink(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'account_links'

    id = fields.IntField(pk=True)
    # 紐付けを所有する KonomiTV ユーザー
    # ユーザー削除時は送信先設定としての紐付けも不要になるため cascade で削除する
    user: fields.ForeignKeyRelation[User] = \
        fields.ForeignKeyField('models.User', related_name='account_links', on_delete=fields.CASCADE)
    user_id: int
    # 紐付け対象の Twitter アカウント
    # 一つの Twitter アカウントが複数の Bluesky アカウントへ紐づかないよう OneToOne にする
    twitter_account: fields.OneToOneRelation[TwitterAccount] = \
        fields.OneToOneField('models.TwitterAccount', related_name='account_link', on_delete=fields.CASCADE)
    twitter_account_id: int
    # 紐付け対象の Bluesky アカウント
    # 一つの Bluesky アカウントが複数の Twitter アカウントへ紐づかないよう OneToOne にする
    bluesky_account: fields.OneToOneRelation[BlueskyAccount] = \
        fields.OneToOneField('models.BlueskyAccount', related_name='account_link', on_delete=fields.CASCADE)
    bluesky_account_id: int
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
