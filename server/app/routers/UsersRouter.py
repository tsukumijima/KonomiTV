
import asyncio
import pathlib
import uuid
from datetime import datetime, timedelta
from typing import Annotated, BinaryIO
from zoneinfo import ZoneInfo

import anyio
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Path,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from PIL import Image

from app import logging, schemas
from app.constants import (
    ACCOUNT_ICON_DEFAULT_DIR,
    ACCOUNT_ICON_DIR,
    JWT_SECRET_KEY,
    PASSWORD_CONTEXT,
)
from app.models.TwitterAccount import TwitterAccount
from app.models.User import User


# ルーター
router = APIRouter(
    tags = ['Users'],
    prefix = '/api/users',
)


def GenerateAccessToken(user_id: int) -> str:
    """
    ユーザー ID を受け取り、そのユーザー ID を含む JWT アクセストークンを生成する

    Args:
        user_id (int): ユーザー ID

    Returns:
        str: JWT アクセストークン (有効期限は 180 日間)
    """

    # JWT エンコードするペイロード
    jwt_payload = {
        # トークンの発行者
        'iss': 'KonomiTV Server',
        # トークンの種類
        'typ': 'AccessToken',
        # ユーザーの識別子 (ユーザー ID を文字列化したもの)
        'sub': f'{user_id}',
        # JWT の発行時間
        'iat': datetime.now(ZoneInfo('Asia/Tokyo')),
        # JWT の有効期限 (JWT の発行から 180 日間)
        'exp': datetime.now(ZoneInfo('Asia/Tokyo')) + timedelta(days=180),
        # JWT ごとの一意な ID (UUID v4)
        'jti': str(uuid.uuid4()),
    }

    # JWT エンコードを行い、JWT アクセストークンを生成
    return jwt.encode(
        claims = jwt_payload,
        key = JWT_SECRET_KEY,
        algorithm = 'HS256',
    )


async def GetCurrentUser(token: Annotated[str, Depends(OAuth2PasswordBearer(tokenUrl='users/token'))]) -> User:
    """ 現在ログイン中のユーザーを取得する """

    try:
        # JWT トークンをデコード
        jwt_payload = jwt.decode(
            token = token,
            key = JWT_SECRET_KEY,
            algorithms = ['HS256'],
            issuer = 'KonomiTV Server',
        )

        # typ が AccessToken でない (JWT トークンが不正)
        if jwt_payload.get('typ') != 'AccessToken':
            logging.warning('[GetCurrentUser] Access token type is invalid.')
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED,
                detail = 'Access token type is invalid',
                headers = {'WWW-Authenticate': 'Bearer'},
            )

        # Subject が JWT ペイロードに含まれていない (JWT トークンが不正)
        if jwt_payload.get('sub') is None:
            logging.warning('[GetCurrentUser] Access token data is invalid.')
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED,
                detail = 'Access token data is invalid',
                headers = {'WWW-Authenticate': 'Bearer'},
            )

    # JWT トークンが不正
    except JWTError as ex:
        logging.warning('[GetCurrentUser] Access token is invalid:', exc_info=ex)
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = 'Access token is invalid',
            headers = {'WWW-Authenticate': 'Bearer'},
        )

    # JWT ペイロードの Subject をユーザー ID として取得
    user_id: int = int(jwt_payload['sub'])

    # JWT トークンに刻まれたユーザー ID に紐づくユーザー情報を取得
    current_user = await User.filter(id=user_id).prefetch_related('twitter_accounts').get_or_none()

    # そのユーザー ID のユーザーが存在しない
    if not current_user:
        logging.warning(f'[GetCurrentUser] User associated with access token does not exist. [user_id: {user_id}]')
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = 'User associated with access token does not exist',
            headers = {'WWW-Authenticate': 'Bearer'},
        )

    return current_user


async def GetCurrentAdminUser(current_user: Annotated[User, Depends(GetCurrentUser)]) -> User:
    """ 現在ログイン中の管理者ユーザーを取得する """

    # 取得したユーザーが管理者ではない
    if current_user.is_admin is False:
        logging.warning(f'[GetCurrentAdminUser] Don\'t have permission to access this resource. [user_id: {current_user.id}]')
        raise HTTPException(
            status_code = status.HTTP_403_FORBIDDEN,
            detail = 'Don\'t have permission to access this resource',
            headers = {'WWW-Authenticate': 'Bearer'},
        )

    return current_user


async def GetSpecifiedUser(
    username: Annotated[str, Path(description='アカウントのユーザー名。')],
    current_user: Annotated[User, Depends(GetCurrentAdminUser)],  # 管理者ユーザーのみアクセス可能
) -> User:
    """ 指定されたユーザー名のユーザーを取得する """

    # 指定されたユーザー名のユーザーを取得
    user = await User.filter(name=username).prefetch_related('twitter_accounts').get_or_none()

    # 指定されたユーザー名のユーザーが存在しない
    if not user:
        logging.error(f'[GetSpecifiedUser] Specified user was not found. [username: {username}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified user was not found',
        )

    return user


def ResizeAndSaveIcon(file: BinaryIO, save_path: pathlib.Path) -> None:
    """
    アイコンを 512×512 の正方形 PNG にリサイズして保存する
    この関数は同期的なので、非同期関数から呼ぶ場合は asyncio.to_thread() を使うこと
    ref: https://note.nkmk.me/python-pillow-basic/
    ref: https://note.nkmk.me/python-pillow-image-resize/
    ref: https://note.nkmk.me/python-pillow-image-crop-trimming/

    Args:
        file (io.BytesIO): 入力元のファイルオブジェクト
        save_path (pathlib.Path): トリミング&リサイズしたファイルの保存先のパス
    """

    # リサイズする画像の幅と高さ
    RESIZE_WIDTH_AND_HEIGHT = 512

    # 画像を開く
    pillow_image = Image.open(file)

    # 縦横どちらか長さが短い方に合わせて正方形にクロップ
    pillow_image_crop = pillow_image.crop((
        (pillow_image.size[0] - min(pillow_image.size)) // 2,
        (pillow_image.size[1] - min(pillow_image.size)) // 2,
        (pillow_image.size[0] + min(pillow_image.size)) // 2,
        (pillow_image.size[1] + min(pillow_image.size)) // 2,
    ))

    # リサイズして保存
    pillow_image_resize = pillow_image_crop.resize((RESIZE_WIDTH_AND_HEIGHT, RESIZE_WIDTH_AND_HEIGHT))
    pillow_image_resize.save(save_path, 'PNG')


@router.post(
    '',
    summary = 'アカウント作成 API',
    response_description = '作成したユーザーアカウントの情報。',
    response_model = schemas.User,
    status_code = status.HTTP_201_CREATED,
)
async def UserCreateAPI(
    user_create_request: Annotated[schemas.UserCreateRequest, Body(description='作成するユーザーの名前とパスワード。')],
):
    """
    新しいユーザーアカウントを作成する。

    指定されたユーザー名のアカウントがすでに存在する場合は 422 エラーが返される。<br>
    また、最初に作成されたアカウントのみ、特別に管理者権限 (is_admin: true) が付与される。
    """

    # 同じユーザー名のアカウントがあったら 422 を返す
    ## ユーザー名がそのままログイン ID になるので、同じユーザー名のアカウントがあると重複する
    if await User.filter(name=user_create_request.username).get_or_none() is not None:
        logging.warning(f'[UsersRouter][UserCreateAPI] Specified username is duplicated. [username: {user_create_request.username}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified username is duplicated',
        )

    # 利用不可なユーザー名だったら 422 を返す
    ## /api/users/me と /api/users/token があるので、もしその名前で登録できてしまうと重複して面倒なことになる
    ## そんな名前で登録する人はいないとは思うけど、念のため…
    PERMITTED_USERNAMES = ['me', 'token']
    if user_create_request.username.lower() in PERMITTED_USERNAMES:
        logging.warning(f'[UsersRouter][UserCreateAPI] Specified username is not permitted. [username: {user_create_request.username}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified username is not permitted',
        )

    # 新しいユーザーアカウントのモデルを作成・保存
    current_user = await User.create(
        name = user_create_request.username,  # ユーザー名
        password = PASSWORD_CONTEXT.hash(user_create_request.password),  # ハッシュ化されたパスワード
        is_admin = False if await User.all().count() > 0 else True,  # 他のユーザーアカウントがまだ作成されていないなら、特別に管理者権限を付与
        client_settings = {},  # クライアント側の設定（ひとまず空の辞書を設定）
    )

    # 外部テーブルのデータを取得してから返す
    await current_user.fetch_related('twitter_accounts')
    return current_user


@router.post(
    '/token',
    summary = 'アクセストークン発行 API (OAuth2 準拠)',
    response_description = 'JWT エンコードされたアクセストークン。',
    response_model = schemas.UserAccessToken,
)
async def UserAccessTokenAPI(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    """
    指定されたユーザー名とパスワードを検証し、そのユーザーの JWT エンコードされたアクセストークンを発行する。<br>
    この API は OAuth2 のトークンエンドポイントの仕様に準拠している（はず）。

    発行された JWT トークンを Authorization: Bearer で送ることで、認証が必要なエンドポイントにアクセスできる。<br>
    この API はアクセストークンを発行するだけで、ログインそのものは行わない。
    """

    # ユーザーを取得
    current_user = await User.filter(name=form_data.username).get_or_none()

    # 指定されたユーザーが存在しない
    if not current_user:
        logging.warning(f'[UsersRouter][UserAccessTokenAPI] Incorrect username. [username: {form_data.username}]')
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = 'Incorrect username',
            headers = {'WWW-Authenticate': 'Bearer'},
        )

    # 指定されたパスワードのハッシュが DB にあるものと一致しない
    if not PASSWORD_CONTEXT.verify(form_data.password, current_user.password):
        logging.warning(f'[UsersRouter][UserAccessTokenAPI] Incorrect password. [username: {form_data.username}]')
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = 'Incorrect password',
            headers = {'WWW-Authenticate': 'Bearer'},
        )

    # JWT アクセストークンを生成して返す
    return schemas.UserAccessToken(
        access_token = GenerateAccessToken(current_user.id),
        token_type = 'bearer',
    )


@router.get(
    '',
    summary = 'アカウント一覧 API',
    response_description = 'すべてのユーザーアカウントの情報。',
    response_model = schemas.Users,
)
async def UsersAPI(
    current_user: Annotated[User, Depends(GetCurrentAdminUser)],
):
    """
    すべてのユーザーアカウントのリストを取得する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    return await User.all().prefetch_related('twitter_accounts')


# ***** ログイン中ユーザーアカウント情報 API *****


@router.get(
    '/me',
    summary = 'アカウント情報 API (ログイン中のユーザー)',
    response_description = 'ログイン中のユーザーアカウントの情報。',
    response_model = schemas.User,
)
async def UserAPI(
    current_user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    現在ログイン中のユーザーアカウントの情報を取得する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    # 一番よく使う API なので、リクエスト時に twitter_accounts テーブルに仮のアカウントデータが残っていたらすべて消しておく
    ## Twitter 連携では途中で連携をキャンセルした場合に仮のアカウントデータが残置されてしまうので、それを取り除く
    if await TwitterAccount.filter(icon_url='Temporary').count() > 0:
        await TwitterAccount.filter(icon_url='Temporary').delete()
        current_user = await User.filter(id=current_user.id).prefetch_related('twitter_accounts').get()  # current_user のデータを更新

    return current_user


@router.put(
    '/me',
    summary = 'アカウント情報更新 API (ログイン中のユーザー)',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def UserUpdateAPI(
    user_update_request: Annotated[schemas.UserUpdateRequest, Body(description='更新するユーザーアカウントの情報。')],
    current_user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    現在ログイン中のユーザーアカウントの情報を更新する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    # ユーザー名を更新（存在する場合）
    if user_update_request.username is not None:

        # 重複しないように、同じユーザー名のアカウントがあったら 422 を返す
        ## 新しいユーザー名が現在のユーザー名と同じなら問題ないので除外
        if user_update_request.username != current_user.name and await User.filter(name=user_update_request.username).get_or_none():
            logging.warning(f'[UsersRouter][UserUpdateAPI] Specified username is duplicated. [username: {user_update_request.username}]')
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail = 'Specified username is duplicated',
            )

        # 利用不可なユーザー名だったら 422 を返す
        ## /api/users/me と /api/users/token があるので、もしその名前で登録できてしまうと重複して面倒なことになる
        ## そんな名前で登録する人はいないとは思うけど、念のため…
        PERMITTED_USERNAMES = ['me', 'token']
        if user_update_request.username.lower() in PERMITTED_USERNAMES:
            logging.warning(f'[UsersRouter][UserUpdateAPI] Specified username is not permitted. [username: {user_update_request.username}]')
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail = 'Specified username is not permitted',
            )

        # 新しいユーザー名を設定
        current_user.name = user_update_request.username

    # パスワードを更新（存在する場合）
    if user_update_request.password is not None:
        current_user.password = PASSWORD_CONTEXT.hash(user_update_request.password)  # ハッシュ化されたパスワード

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
async def UserIconAPI(
    current_user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    現在ログイン中のユーザーアカウントのアイコン画像を取得する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    # ブラウザにキャッシュさせないようにヘッダーを設定
    # ref: https://developer.mozilla.org/ja/docs/Web/HTTP/Headers/Cache-Control
    header = {
        'Cache-Control': 'no-store',
    }

    # アイコン画像が保存されていればそれを返す
    icon_save_path = anyio.Path(str(ACCOUNT_ICON_DIR)) / f'{current_user.id:02}.png'
    if await icon_save_path.exists():
        return FileResponse(icon_save_path, headers=header)

    # デフォルトのアイコン画像を返す
    return FileResponse(ACCOUNT_ICON_DEFAULT_DIR / 'default.png', headers=header)


@router.put(
    '/me/icon',
    summary = 'アカウントアイコン画像更新 API (ログイン中のユーザー)',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def UserUpdateIconAPI(
    image: Annotated[UploadFile, File(description='アカウントのアイコン画像 (JPEG or PNG)。')],
    current_user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    現在ログイン中のユーザーアカウントのアイコン画像を更新する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    # MIME タイプが image/jpeg or image/png 以外
    if image.content_type != 'image/jpeg' and image.content_type != 'image/png':
        logging.warning(f'[UsersRouter][UserUpdateIconAPI] Please upload JPEG or PNG image. [content_type: {image.content_type}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Please upload JPEG or PNG image',
        )

    # 正方形の PNG にリサイズして保存
    # 保存先ファイルパス: (ユーザー ID を0埋めしたもの).png
    await asyncio.to_thread(ResizeAndSaveIcon, image.file, ACCOUNT_ICON_DIR / f'{current_user.id:02}.png')


@router.delete(
    '/me',
    summary = 'アカウント削除 API (ログイン中のユーザー)',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def UserDeleteAPI(
    current_user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    現在ログイン中のユーザーアカウントを削除する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    # アイコン画像が保存されていれば削除する
    icon_save_path = anyio.Path(str(ACCOUNT_ICON_DIR)) / f'{current_user.id:02}.png'
    if await icon_save_path.exists():
        await icon_save_path.unlink()

    # 現在ログイン中のユーザーアカウント（自分自身）を削除
    # アカウントを削除すると、それ以降は（当然ながら）ログインを要求する API へアクセスできなくなる
    await current_user.delete()

    # ユーザーを削除した結果、管理者アカウントがいなくなってしまった場合
    ## ID が一番若いアカウントに管理者権限を付与する（そうしないと誰も管理者権限を行使できないし付与できない）
    if await User.filter(is_admin=True).count() == 0:
        id_young_user = await User.all().order_by('id').first()
        if id_young_user is not None:
            id_young_user.is_admin = True
            await id_young_user.save()


# ***** 指定ユーザーアカウント情報 API (管理者用) *****


@router.get(
    '/{username}',
    summary = 'アカウント情報 API',
    response_description = 'ユーザーアカウントの情報。',
    response_model = schemas.User,
)
async def SpecifiedUserAPI(
    user: Annotated[User, Depends(GetSpecifiedUser)],
):
    """
    指定されたユーザーアカウントの情報を取得する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    return user


@router.put(
    '/{username}',
    summary = 'アカウント情報更新 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def SpecifiedUserUpdateAPI(
    user_update_request: Annotated[schemas.UserUpdateRequestForAdmin, Body(description='更新するユーザーアカウントの情報。')],
    user: Annotated[User, Depends(GetSpecifiedUser)],
):
    """
    指定されたユーザーアカウントの情報を更新する。/api/users/me と異なり、管理者権限の付与/剥奪のみ可能。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    # 管理者権限を付与/剥奪
    if user_update_request.is_admin is not None:
        user.is_admin = user_update_request.is_admin

    # 管理者権限を剥奪する場合、この処理によってシステム内に管理者が一人もいなくならないかを確認
    if user_update_request.is_admin is False:
        remaining_admins = await User.filter(is_admin=True).exclude(id=user.id).count()
        if remaining_admins == 0:
            logging.warning('[UsersRouter][SpecifiedUserUpdateAPI] Cannot revoke admin permission because there are no more admins.')
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail = 'Cannot revoke admin permission because there are no more admins',
            )

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
async def SpecifiedUserIconAPI(
    user: Annotated[User, Depends(GetSpecifiedUser)],
):
    """
    指定されたユーザーアカウントのアイコン画像を取得する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    # ブラウザにキャッシュさせないようにヘッダーを設定
    # ref: https://developer.mozilla.org/ja/docs/Web/HTTP/Headers/Cache-Control
    header = {
        'Cache-Control': 'no-store',
    }

    # アイコン画像が保存されていればそれを返す
    icon_save_path = anyio.Path(str(ACCOUNT_ICON_DIR)) / f'{user.id:02}.png'
    if await icon_save_path.exists():
        return FileResponse(icon_save_path, headers=header)

    # デフォルトのアイコン画像を返す
    return FileResponse(ACCOUNT_ICON_DEFAULT_DIR / 'default.png', headers=header)


@router.delete(
    '/{username}',
    summary = 'アカウント削除 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def SpecifiedUserDeleteAPI(
    user: Annotated[User, Depends(GetSpecifiedUser)],
):
    """
    指定されたユーザーアカウントを削除する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    # アイコン画像が保存されていれば削除する
    icon_save_path = anyio.Path(str(ACCOUNT_ICON_DIR)) / f'{user.id:02}.png'
    if await icon_save_path.exists():
        await icon_save_path.unlink()

    # 指定されたユーザーを削除
    await user.delete()

    # ユーザーを削除した結果、管理者アカウントがいなくなってしまった場合
    ## ID が一番若いアカウントに管理者権限を付与する（そうしないと誰も管理者権限を行使できないし付与できない）
    if await User.filter(is_admin=True).count() == 0:
        id_young_user = await User.all().order_by('id').first()
        if id_young_user is not None:
            id_young_user.is_admin = True
            await id_young_user.save()
