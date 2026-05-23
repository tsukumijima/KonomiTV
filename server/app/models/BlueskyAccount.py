
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

from typing import TYPE_CHECKING

from cryptography.fernet import InvalidToken
from fastapi import HTTPException, status
from tortoise import fields
from tortoise.models import Model as TortoiseModel

from app import logging
from app.constants import (
    BLUESKY_ACCOUNT_SESSION_ENCRYPTION_PREFIX,
    BLUESKY_ACCOUNT_SESSION_FERNET,
)


if TYPE_CHECKING:
    from app.models.AccountLink import AccountLink
    from app.models.User import User


class BlueskyAccount(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'bluesky_accounts'
        unique_together = (('user', 'did'),)

    id = fields.IntField(pk=True)
    # KonomiTV のユーザーアカウントと Bluesky アカウントを紐づける
    # ユーザー削除時は認証情報を同時に削除すべきなので cascade を指定
    user: fields.ForeignKeyRelation[User] = \
        fields.ForeignKeyField('models.User', related_name='bluesky_accounts', on_delete=fields.CASCADE)
    user_id: int
    # DID は handle が変更された場合でも同じアカウントを識別するための Bluesky 側の永続 ID
    did = fields.TextField()
    handle = fields.TextField()
    name = fields.TextField()
    icon_url = fields.TextField()
    # atproto SDK の session_string は暗号化して保存し、App Password 自体は保存しない
    session_string = fields.TextField()
    # Twitter アカウントとの紐付け情報
    # 未紐付けの場合は空の ReverseRelation として扱われる
    account_link: fields.ReverseRelation[AccountLink]
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)


    def encryptSessionString(self, plain_text: str) -> str:
        """
        atproto SDK のセッション文字列を暗号化する

        Args:
            plain_text (str): 暗号化前のセッション文字列

        Returns:
            str: 暗号化済みのセッション文字列
        """

        # 空文字は暗号化不要なのでそのまま返し、無駄な処理を避ける
        if plain_text == '':
            return ''

        # Fernet で暗号化し、接頭辞を付けて暗号化済みであることを明示する
        encrypted_text = BLUESKY_ACCOUNT_SESSION_FERNET.encrypt(plain_text.encode('utf-8')).decode('utf-8')
        return f'{BLUESKY_ACCOUNT_SESSION_ENCRYPTION_PREFIX}{encrypted_text}'


    def decryptSessionString(self) -> str:
        """
        データベースに保存されている atproto SDK のセッション文字列を復号する

        Returns:
            str: 復号済みのセッション文字列
        """

        # 暗号化されたセッション文字列の接頭辞がない場合はそのまま返す
        encrypted_text = self.session_string or ''
        if encrypted_text == '':
            return ''
        # 接頭辞が無い場合は平文として扱う
        if encrypted_text.startswith(BLUESKY_ACCOUNT_SESSION_ENCRYPTION_PREFIX) is False:
            return encrypted_text

        # 暗号化されたセッション文字列の接頭辞を除去して復号する
        token = encrypted_text[len(BLUESKY_ACCOUNT_SESSION_ENCRYPTION_PREFIX):].encode('utf-8')
        try:
            decrypted_text = BLUESKY_ACCOUNT_SESSION_FERNET.decrypt(token).decode('utf-8')
        except InvalidToken as ex:
            logging.error('[BlueskyAccount][decryptSessionString] Failed to decrypt session string:', exc_info=ex)
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail = 'Failed to decrypt Bluesky session. Please re-link your Bluesky account.',
            ) from ex

        return decrypted_text
