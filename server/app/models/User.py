
# 引数の戻り値などに自クラスを指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import json
from datetime import datetime
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from jose import JWTError
from tortoise import fields
from tortoise import models
from typing import Optional

from app.constants import JWT_SECRET_KEY
from app.models import TwitterAccount


class User(models.Model):

    # データベース上のテーブル名
    class Meta:
        table:str = 'users'

    # テーブル設計は Notion を参照のこと
    id: int = fields.IntField(pk=True)
    name: str = fields.TextField()
    password: str = fields.TextField()
    is_admin: bool = fields.BooleanField()
    client_settings: dict = fields.JSONField()
    niconico_user_id: Optional[int] = fields.IntField(null=True)
    niconico_user_name: Optional[str] = fields.TextField(null=True)
    niconico_access_token: Optional[str] = fields.TextField(null=True)
    niconico_refresh_token: Optional[str] = fields.TextField(null=True)
    ## クラスが読み込まれる前なので、TwitterAccount(モジュール).TwitterAccount(クラス) のようにしないと参照できない
    twitter_accounts: fields.ReverseRelation['TwitterAccount.TwitterAccount']
    created_at: datetime = fields.DatetimeField(auto_now_add=True)
    updated_at: datetime = fields.DatetimeField(auto_now=True)


    @classmethod
    async def getCurrentUser(cls, token: str = Depends(OAuth2PasswordBearer(tokenUrl='users/token'))) -> User:
        """
        現在ログイン中のユーザーを取得する。FastAPI の Depends() で使うことが前提。
        Bearer トークンが指定されていない場合・JWT トークンが不正な場合・ユーザーアカウントが存在しない場合は例外がスローされる。

        Args:
            token (str, optional): OAuth2PasswordBearer() によって取得された JWT トークン。

        Raises:
            HTTPException: JWT の検証に失敗したときの例外。

        Returns:
            User: ユーザー情報。
        """

        try:
            # JWT トークンをデコード
            jwt_payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])

            # ユーザー ID が JWT に含まれていない (JWT トークンが不正)
            if jwt_payload.get('sub') is None:
                raise HTTPException(
                    status_code = status.HTTP_401_UNAUTHORIZED,
                    detail = 'Access token data is invalid',
                    headers = {'WWW-Authenticate': 'Bearer'},
                )

            # ペイロード内のユーザー ID（ユーザー名ではなく、ユーザーごとに一意な数値）を取得
            user_id: str = json.loads(jwt_payload.get('sub'))['user_id']

        # JWT トークンが不正
        except JWTError:
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED,
                detail = 'Access token is invalid',
                headers = {'WWW-Authenticate': 'Bearer'},
            )

        # JWT トークンに刻まれたユーザー ID に紐づくユーザー情報を取得
        user = await User.filter(id=user_id).get_or_none()

        # そのユーザー ID のユーザーが存在しない
        if not user:
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED,
                detail = 'User associated with access token does not exist',
                headers = {'WWW-Authenticate': 'Bearer'},
            )

        # 外部テーブルのデータを取得してから返す
        # 明示的に fetch_related() しないと取得されない仕様になっているらしい
        await user.fetch_related('twitter_accounts')
        return user


    @classmethod
    async def getCurrentAdminUser(cls, token: str = Depends(OAuth2PasswordBearer(tokenUrl='users/token'))):
        """
        現在ログイン中の管理者ユーザーを取得する。FastAPI の Depends() で使うことが前提。
        getCurrentUser() 同様、Bearer トークンが指定されていない場合・JWT トークンが不正な場合・ユーザーアカウントが存在しない場合は例外がスローされる。
        加えて、ログイン中のユーザーが管理者でない場合も例外がスローされる。

        Raises:
            HTTPException: JWT の検証に失敗したときの例外。

        Returns:
            User: ユーザー情報。
        """

        # getCurrentUser() を実行して、ユーザーを取得
        # 取得できなければ例外がスローされる
        user = await cls.getCurrentUser(token)

        # 取得したユーザーが管理者ではない
        if user.is_admin is False:
            raise HTTPException(
                status_code = status.HTTP_403_FORBIDDEN,
                detail = 'Don\'t have permission to access this resource',
                headers = {'WWW-Authenticate': 'Bearer'},
            )

        # 外部テーブルのデータを取得してから返す
        # 明示的に fetch_related() しないと取得されない仕様になっているらしい
        await user.fetch_related('twitter_accounts')
        return user
