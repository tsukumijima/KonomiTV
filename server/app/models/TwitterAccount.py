
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
    TWITTER_ACCOUNT_COOKIE_ENCRYPTION_PREFIX,
    TWITTER_ACCOUNT_COOKIE_FERNET,
)


if TYPE_CHECKING:
    from app.models.User import User


class TwitterAccount(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'twitter_accounts'

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


    def encryptAccessTokenSecret(self, plain_text: str) -> str:
        """
        Netscape 形式の Cookie データを暗号化する

        Returns:
            str: 暗号化済みのテキスト
        """

        # 空文字は暗号化不要なのでそのまま返し、無駄な処理を避ける
        if plain_text == '':
            return ''

        # Fernet で暗号化し、接頭辞を付けて暗号化済みであることを明示する
        encrypted_text = TWITTER_ACCOUNT_COOKIE_FERNET.encrypt(plain_text.encode('utf-8')).decode('utf-8')
        return f'{TWITTER_ACCOUNT_COOKIE_ENCRYPTION_PREFIX}{encrypted_text}'


    def decryptAccessTokenSecret(self) -> str:
        """
        データベースに保存されている Cookie データを復号する

        Returns:
            str: 復号済みのテキスト
        """

        # 暗号化された Cookie の接頭辞がない場合はそのまま返す
        encrypted_text = self.access_token_secret or ''
        if encrypted_text == '':
            return ''
        # 接頭辞が無い (= 従来形式) 場合は平文として扱う
        if encrypted_text.startswith(TWITTER_ACCOUNT_COOKIE_ENCRYPTION_PREFIX) is False:
            return encrypted_text

        # 暗号化された Cookie の接頭辞を除去して復号する
        token = encrypted_text[len(TWITTER_ACCOUNT_COOKIE_ENCRYPTION_PREFIX):].encode('utf-8')
        try:
            decrypted_text = TWITTER_ACCOUNT_COOKIE_FERNET.decrypt(token).decode('utf-8')
        except InvalidToken as ex:
            logging.error('[TwitterAccount][decryptAccessTokenSecret] Failed to decrypt cookie:', exc_info=ex)
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail = 'Failed to decrypt Twitter cookies. Please re-link your Twitter account.',
            ) from ex

        return decrypted_text


