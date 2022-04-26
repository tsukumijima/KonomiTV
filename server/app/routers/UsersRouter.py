
import json
from datetime import datetime
from datetime import timedelta
from fastapi import APIRouter
from fastapi import Body
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Path
from fastapi import status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from passlib.context import CryptContext
from tortoise import timezone
from typing import List

from app import schemas
from app.constants import JWT_SECRET_KEY
from app.models import User


# ルーター
router = APIRouter(
    tags=['Users'],
    prefix='/api/users',
)


@router.post(
    '',
    summary = 'アカウント作成 API',
    response_description = '作成したユーザーアカウントの情報。',
    response_model = schemas.User,
    status_code = status.HTTP_201_CREATED,
)
async def UserCreateAPI(
    user_create_request: schemas.UserCreateRequest = Body(..., description='作成するユーザーの名前とパスワード。'),
):
    """
    新しいユーザーアカウントを作成する。

    指定されたユーザー名のアカウントがすでに存在する場合は 422 エラーが返される。<br>
    また、最初に作成されたアカウントのみ、特別に管理者権限 (is_admin: True) が付与される。
    """

    # Passlib のコンテキストを作成
    passlib_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

    # 同じユーザー名のアカウントがあったら 422 を返す
    # ユーザー名がそのままログイン ID になるので、同じユーザー名のアカウントがあると重複する
    if await User.filter(name=user_create_request.username).get_or_none() is not None:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified username is duplicated',
        )

    # 新しいユーザーアカウントのモデルを作成
    user = User()
    user.name = user_create_request.username  # ユーザー名
    user.password = passlib_context.hash(user_create_request.password)  # ハッシュ化されたパスワード
    user.client_settings = {}  # クライアント側の設定（ひとまず空の辞書を設定）

    # 他のユーザーアカウントがまだ作成されていないなら、特別に管理者権限を付与
    if await User.all().count() == 0:
        user.is_admin = True
    else:
        user.is_admin = False

    # レコードを保存する
    await user.save()

    return user


@router.post(
    '/token',
    summary = 'アクセストークン発行 API (OAuth2 準拠)',
    response_description = 'JWT エンコードされたアクセストークン。',
    response_model = schemas.UserAccessToken,
)
async def UserAccessTokenAPI(
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
    指定されたユーザー名とパスワードを検証し、そのユーザーの JWT エンコードされたアクセストークンを発行する。<br>
    この API は OAuth2 のトークンエンドポイントの仕様に準拠している（はず）。

    発行された JWT トークンを Authorization: Bearer で送ることで、認証が必要なエンドポイントにアクセスできる。<br>
    この API はアクセストークンを発行するだけで、ログインそのものは行わない。
    """

    # Passlib のコンテキストを作成
    passlib_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

    # ユーザーを取得
    user = await User.filter(name=form_data.username).get_or_none()

    # 指定されたユーザーが存在しない
    if not user:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = 'Incorrect username',
            headers = {'WWW-Authenticate': 'Bearer'},
        )

    # 指定されたパスワードのハッシュが DB にあるものと一致しない
    if not passlib_context.verify(form_data.password, user.password):
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = 'Incorrect password',
            headers = {'WWW-Authenticate': 'Bearer'},
        )

    # JWT エンコードするペイロード
    jwt_payload = {
        # トークンの発行者
        'iss': 'KonomiTV Server',
        # ユーザーの識別子
        ## 今のところユーザー ID のみ含める
        ## ユーザー名は他のアカウントと被らなければ変更できるため使えない
        'sub': json.dumps({'user_id': user.id}),
        # JWT の発行時間
        'iat': datetime.now(timezone.get_default_timezone()),
        # JWT の有効期限 (JWT の発行から 30 日間)
        'exp': datetime.now(timezone.get_default_timezone()) + timedelta(days=30),
    }

    # JWT エンコードを行い、アクセストークンを生成
    access_token = jwt.encode(jwt_payload, JWT_SECRET_KEY, algorithm='HS256')

    # JWT トークンを OAuth2 準拠の JSON で返す
    return {
        'access_token': access_token,
        'token_type': 'bearer',
    }
