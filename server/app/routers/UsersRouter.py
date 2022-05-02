
import asyncio
import io
import pathlib
import json
from datetime import datetime
from datetime import timedelta
from fastapi import APIRouter
from fastapi import Body
from fastapi import Depends
from fastapi import File
from fastapi import HTTPException
from fastapi import Path
from fastapi import Response
from fastapi import status
from fastapi import UploadFile
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from passlib.context import CryptContext
from PIL import Image
from tortoise import timezone

from app import schemas
from app.constants import ACCOUNT_ICON_DIR, ACCOUNT_ICON_DEFAULT_DIR, JWT_SECRET_KEY
from app.models import User


# ルーター
router = APIRouter(
    tags=['Users'],
    prefix='/api/users',
)


# 正方形の 400×400 の PNG にトリミング&リサイズして保存する関数
async def TrimSquareAndResize(file: io.BytesIO, save_path: pathlib.Path, resize_width_and_height: int = 400):
    """
    正方形の 400×400 の PNG にトリミング&リサイズして保存する関数
    ref: https://note.nkmk.me/python-pillow-basic/
    ref: https://note.nkmk.me/python-pillow-image-resize/
    ref: https://note.nkmk.me/python-pillow-image-crop-trimming/

    Args:
        file (io.BytesIO): 入力元のファイルオブジェクト。
        save_path (pathlib.Path): トリミング&リサイズしたファイルの保存先のパス
        resize_width_and_height (int, optional): リサイズする幅と高さ. Defaults to 400.
    """

    ## 画像を開く
    pillow_image = await asyncio.to_thread(Image.open, file)

    ## 縦横どちらか長さが短い方に合わせて正方形にクロップ
    pillow_image_crop = await asyncio.to_thread(pillow_image.crop, (
        (pillow_image.size[0] - min(pillow_image.size)) // 2,
        (pillow_image.size[1] - min(pillow_image.size)) // 2,
        (pillow_image.size[0] + min(pillow_image.size)) // 2,
        (pillow_image.size[1] + min(pillow_image.size)) // 2,
    ))

    ## 400×400 にリサイズして保存
    pillow_image_resize = await asyncio.to_thread(pillow_image_crop.resize, (resize_width_and_height, resize_width_and_height))
    await asyncio.to_thread(pillow_image_resize.save, save_path)


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
    また、最初に作成されたアカウントのみ、特別に管理者権限 (is_admin: true) が付与される。
    """

    # Passlib のコンテキストを作成
    passlib_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

    # 同じユーザー名のアカウントがあったら 422 を返す
    ## ユーザー名がそのままログイン ID になるので、同じユーザー名のアカウントがあると重複する
    if await User.filter(name=user_create_request.username).get_or_none() is not None:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified username is duplicated',
        )

    # ユーザー名が token or me だったら 422 を返す
    ## /api/users/me と /api/users/token があるので、もしその名前で登録できてしまうと重複して面倒なことになる
    ## そんな名前で登録する人はいないとは思うけど、念のため…。
    if user_create_request.username.lower() == 'me' or user_create_request.username.lower() == 'token':
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified username is not accepted due to system limitations',
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

    # 外部テーブルのデータを取得してから返す
    # Twitter アカウントが登録されているかに関わらず、こうしないとユーザーデータを返せない
    await user.fetch_related('twitter_accounts')

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


@router.get(
    '',
    summary = 'アカウント一覧 API',
    response_description = 'すべてのユーザーアカウントの情報。',
    response_model = schemas.Users,
)
async def UsersAPI(
    current_user: User = Depends(User.getCurrentAdminUser),
):
    """
    すべてのユーザーアカウントのリストを取得する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    # 外部テーブルのデータを取得してから返す
    # 明示的に fetch_related() しないと取得されない仕様になっているらしい
    users = await User.all()
    for user in users:
        await user.fetch_related('twitter_accounts')
    return users


@router.get(
    '/me',
    summary = 'アカウント情報 API (ログイン中のユーザー)',
    response_description = 'ログイン中のユーザーアカウントの情報。',
    response_model = schemas.User,
)
async def UserMeAPI(
    current_user: User = Depends(User.getCurrentUser),
):
    """
    現在ログイン中のユーザーアカウントの情報を取得する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """
    return current_user


@router.put(
    '/me',
    summary = 'アカウント情報更新 API (ログイン中のユーザー)',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def UserUpdateMeAPI(
    user_update_request: schemas.UserUpdateRequest = Body(..., description='更新するユーザーアカウントの情報。'),
    current_user: User = Depends(User.getCurrentUser),
):
    """
    現在ログイン中のユーザーアカウントの情報を更新する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    # Passlib のコンテキストを作成
    passlib_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

    # ユーザー名を更新（存在する場合）
    if user_update_request.username is not None:

        # 同じユーザー名のアカウントがあったら 422 を返す
        # ユーザー名がそのままログイン ID になるので、同じユーザー名のアカウントがあると重複する
        if ((await User.filter(name=user_update_request.username).get_or_none() is not None) and
            (user_update_request.username != current_user.name)):  # ログイン中のユーザーと同じなら問題ないので除外
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail = 'Specified username is duplicated',
            )

        # 新しいユーザー名を設定
        current_user.name = user_update_request.username

    # パスワードを更新（存在する場合）
    if user_update_request.password is not None:
        current_user.password = passlib_context.hash(user_update_request.password)  # ハッシュ化されたパスワード

    # レコードを保存する
    await current_user.save()


@router.get(
    '/me/icon',
    summary = 'アカウントアイコン画像 API (ログイン中のユーザー)',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'ユーザーアカウントのアイコン画像。',
            'content': {'image/png': {}},
        }
    }
)
async def UserIconMeAPI(
    current_user: User = Depends(User.getCurrentUser),
):
    """
    現在ログイン中のユーザーアカウントのアイコン画像を取得する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    # アイコン画像が保存されていればそれを返す
    save_path = ACCOUNT_ICON_DIR / f'{current_user.id:02}.png'
    if await asyncio.to_thread(pathlib.Path.exists, save_path):
        return FileResponse(save_path)

    # デフォルトのアイコン画像を返す
    return FileResponse(ACCOUNT_ICON_DEFAULT_DIR / 'default.png')


@router.put(
    '/me/icon',
    summary = 'アカウントアイコン画像更新 API (ログイン中のユーザー)',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def UserUpdateIconMeAPI(
    image: UploadFile = File(None, description='アカウントのアイコン画像 (JPEG or PNG)。'),
    current_user: User = Depends(User.getCurrentUser),
):
    """
    現在ログイン中のユーザーアカウントのアイコン画像を更新する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    # MIME タイプが image/jpeg or image/png 以外
    if image.content_type != 'image/jpeg' and image.content_type != 'image/png':
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Please upload JPEG or PNG image',
        )

    # 正方形の 400×400 の PNG にリサイズして保存
    # 保存するファイルパス: (ユーザー ID を0埋めしたもの).png
    await TrimSquareAndResize(image.file, ACCOUNT_ICON_DIR / f'{current_user.id:02}.png', resize_width_and_height=400)


@router.delete(
    '/me',
    summary = 'アカウント削除 API (ログイン中のユーザー)',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def UserDeleteMeAPI(
    current_user: User = Depends(User.getCurrentUser),
):
    """
    現在ログイン中のユーザーアカウントを削除する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    # アイコン画像が保存されていれば削除する
    save_path = ACCOUNT_ICON_DIR / f'{current_user.id:02}.png'
    if await asyncio.to_thread(pathlib.Path.exists, save_path):
        await asyncio.to_thread(save_path.unlink)

    # 現在ログイン中のユーザーアカウント（自分自身）を削除
    # アカウントを削除すると、それ以降は（当然ながら）ログインを要求する API へアクセスできなくなる
    await current_user.delete()

    # ユーザーを削除した結果、管理者アカウントがいなくなってしまった場合
    ## ID が一番若いアカウントに管理者権限を付与する（そうしないと誰も管理者権限を行使できないし付与できない）
    if await User.filter(is_admin=True).get_or_none() is None:
        id_young_user = await User.all().order_by('id').first()
        id_young_user.is_admin = True
        await id_young_user.save()


@router.get(
    '/{username}',
    summary = 'アカウント情報 API',
    response_description = 'ユーザーアカウントの情報。',
    response_model = schemas.User,
)
async def UserAPI(
    username: str = Path(..., description='アカウントのユーザー名。'),
    current_user: User = Depends(User.getCurrentAdminUser),
):
    """
    指定されたユーザーアカウントの情報を取得する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    # 指定されたユーザー名のユーザーを取得
    user = await User.filter(name=username).get_or_none()

    # 指定されたユーザー名のユーザーが存在しない
    if not user:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified user was not found',
        )

    # 外部テーブルのデータを取得してから返す
    # Twitter アカウントが登録されているかに関わらず、こうしないとユーザーデータを返せない
    await user.fetch_related('twitter_accounts')

    return user


@router.put(
    '/{username}',
    summary = 'アカウント情報更新 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def UserUpdateAPI(
    username: str = Path(..., description='アカウントのユーザー名。'),
    user_update_request: schemas.UserUpdateRequestForAdmin = Body(..., description='更新するユーザーアカウントの情報。'),
    current_user: User = Depends(User.getCurrentAdminUser),
):
    """
    指定されたユーザーアカウントの情報を更新する。管理者権限を付与/剥奪できるのが /api/users/me との最大の違い。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    # 指定されたユーザー名のユーザーを取得
    user = await User.filter(name=username).get_or_none()

    # 指定されたユーザー名のユーザーが存在しない
    if not user:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified user was not found',
        )

    # Passlib のコンテキストを作成
    passlib_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

    # ユーザー名を更新
    if user_update_request.username is not None:

        # 同じユーザー名のアカウントがあったら 422 を返す
        # ユーザー名がそのままログイン ID になるので、同じユーザー名のアカウントがあると重複する
        if ((await User.filter(name=user_update_request.username).get_or_none() is not None) and
            (user_update_request.username != user.name)):  # ログイン中のユーザーと同じなら問題ないので除外
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail = 'Specified username is duplicated',
            )

        # 新しいユーザー名を設定
        user.name = user_update_request.username

    # パスワードを更新
    if user_update_request.password is not None:
        user.password = passlib_context.hash(user_update_request.password)  # ハッシュ化されたパスワード

    # 管理者権限を付与/剥奪
    if user_update_request.is_admin is not None:
        user.is_admin = user_update_request.is_admin

    # レコードを保存する
    await user.save()


@router.get(
    '/{username}/icon',
    summary = 'アカウントアイコン画像 API',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'ユーザーアカウントのアイコン画像。',
            'content': {'image/png': {}},
        }
    }
)
async def UserIconMeAPI(
    username: str = Path(..., description='アカウントのユーザー名。'),
    current_user: User = Depends(User.getCurrentUser),
):
    """
    指定されたユーザーアカウントのユーザーアカウントのアイコン画像を取得する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    # 指定されたユーザー名のユーザーを取得
    user = await User.filter(name=username).get_or_none()

    # 指定されたユーザー名のユーザーが存在しない
    if not user:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified user was not found',
        )

    # アイコン画像が保存されていればそれを返す
    save_path = ACCOUNT_ICON_DIR / f'{user.id:02}.png'
    if await asyncio.to_thread(pathlib.Path.exists, save_path):
        return FileResponse(save_path)

    # デフォルトのアイコン画像を返す
    return FileResponse(ACCOUNT_ICON_DEFAULT_DIR / 'default.png')


@router.put(
    '/{username}/icon',
    summary = 'アカウントアイコン画像更新 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def UserUpdateIconAPI(
    username: str = Path(..., description='アカウントのユーザー名。'),
    image: UploadFile = File(None, description='アカウントのアイコン画像 (JPEG or PNG)。'),
    current_user: User = Depends(User.getCurrentUser),
):
    """
    指定されたユーザーアカウントのアイコン画像を更新する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    # 指定されたユーザー名のユーザーを取得
    user = await User.filter(name=username).get_or_none()

    # 指定されたユーザー名のユーザーが存在しない
    if not user:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified user was not found',
        )

    # MIME タイプが image/jpeg or image/png 以外
    if image.content_type != 'image/jpeg' and image.content_type != 'image/png':
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Please upload JPEG or PNG image',
        )

    # 正方形の 400×400 の PNG にリサイズして保存
    # 保存するファイルパス: (ユーザー ID を0埋めしたもの).png
    await TrimSquareAndResize(image.file, ACCOUNT_ICON_DIR / f'{user.id:02}.png', resize_width_and_height=400)


@router.delete(
    '/{username}',
    summary = 'アカウント削除 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def UserDeleteAPI(
    username: str = Path(..., description='アカウントのユーザー名。'),
    current_user: User = Depends(User.getCurrentAdminUser),
):
    """
    指定されたユーザーアカウントを削除する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    # 指定されたユーザー名のユーザーを取得
    user = await User.filter(name=username).get_or_none()

    # 指定されたユーザー名のユーザーが存在しない
    if not user:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified user was not found',
        )

    # アイコン画像が保存されていれば削除する
    save_path = ACCOUNT_ICON_DIR / f'{user.id:02}.png'
    if await asyncio.to_thread(pathlib.Path.exists, save_path):
        await asyncio.to_thread(save_path.unlink)

    # 指定されたユーザーを削除
    await user.delete()

    # ユーザーを削除した結果、管理者アカウントがいなくなってしまった場合
    ## ID が一番若いアカウントに管理者権限を付与する（そうしないと誰も管理者権限を行使できないし付与できない）
    if await User.filter(is_admin=True).get_or_none() is None:
        id_young_user = await User.all().order_by('id').first()
        id_young_user.is_admin = True
        await id_young_user.save()
