
import asyncio
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
from fastapi.security import OAuth2PasswordBearer
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from jose import JWTError
from passlib.context import CryptContext
from PIL import Image
from typing import Annotated, BinaryIO
from zoneinfo import ZoneInfo

from app import logging
from app import schemas
from app.constants import ACCOUNT_ICON_DIR, ACCOUNT_ICON_DEFAULT_DIR, JWT_SECRET_KEY
from app.models.TwitterAccount import TwitterAccount
from app.models.User import User


# ルーター
router = APIRouter(
    tags = ['Users'],
    prefix = '/api/users',
)


async def GetCurrentUser(token: Annotated[str, Depends(OAuth2PasswordBearer(tokenUrl='users/token'))]) -> User:
    """ 現在ログイン中のユーザーを取得する """

    try:
        # JWT トークンをデコード
        jwt_payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])

        # ユーザー ID が JWT に含まれていない (JWT トークンが不正)
        if jwt_payload.get('sub') is None:
            logging.error('[UsersRouter][GetCurrentUser] Access token data is invalid')
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED,
                detail = 'Access token data is invalid',
                headers = {'WWW-Authenticate': 'Bearer'},
            )

        # ペイロード内のユーザー ID（ユーザー名ではなく、ユーザーごとに一意な数値）を取得
        user_id: str = json.loads(jwt_payload.get('sub', {}))['user_id']

    # JWT トークンが不正
    except JWTError:
        logging.error('[UsersRouter][GetCurrentUser] Access token is invalid')
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = 'Access token is invalid',
            headers = {'WWW-Authenticate': 'Bearer'},
        )

    # JWT トークンに刻まれたユーザー ID に紐づくユーザー情報を取得
    current_user = await User.filter(id=user_id).prefetch_related('twitter_accounts').get_or_none()

    # そのユーザー ID のユーザーが存在しない
    if not current_user:
        logging.error(f'[UsersRouter][GetCurrentUser] User associated with access token does not exist [user_id: {user_id}]')
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
        logging.error(f'[UsersRouter][GetCurrentAdminUser] Don\'t have permission to access this resource [user_id: {current_user.id}]')
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
        logging.error(f'[UsersRouter][GetSpecifiedUser] Specified user was not found [username: {username}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified user was not found',
        )

    return user


async def TrimSquareAndResizeAndSave(file: BinaryIO, save_path: pathlib.Path, resize_width_and_height: int = 400) -> None:
    """
    正方形の 400×400 の PNG にトリミング&リサイズして保存する
    ref: https://note.nkmk.me/python-pillow-basic/
    ref: https://note.nkmk.me/python-pillow-image-resize/
    ref: https://note.nkmk.me/python-pillow-image-crop-trimming/

    Args:
        file (io.BytesIO): 入力元のファイルオブジェクト
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
    user_create_request: Annotated[schemas.UserCreateRequest, Body(description='作成するユーザーの名前とパスワード。')],
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
        logging.error(f'[UsersRouter][UserCreateAPI] Specified username is duplicated [username: {user_create_request.username}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified username is duplicated',
        )

    # ユーザー名が token or me だったら 422 を返す
    ## /api/users/me と /api/users/token があるので、もしその名前で登録できてしまうと重複して面倒なことになる
    ## そんな名前で登録する人はいないとは思うけど、念のため…。
    if user_create_request.username.lower() == 'me' or user_create_request.username.lower() == 'token':
        logging.error(f'[UsersRouter][UserCreateAPI] Specified username is not accepted due to system limitations [username: {user_create_request.username}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified username is not accepted due to system limitations',
        )

    # 新しいユーザーアカウントのモデルを作成・保存
    user = await User.create(
        name = user_create_request.username,  # ユーザー名
        password = passlib_context.hash(user_create_request.password),  # ハッシュ化されたパスワード
        is_admin = False if await User.all().count() > 0 else True,  # 他のユーザーアカウントがまだ作成されていないなら、特別に管理者権限を付与
        client_settings = {},  # クライアント側の設定（ひとまず空の辞書を設定）
    )

    # 外部テーブルのデータを取得してから返す
    await user.fetch_related('twitter_accounts')
    return user


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

    # Passlib のコンテキストを作成
    passlib_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

    # ユーザーを取得
    user = await User.filter(name=form_data.username).get_or_none()

    # 指定されたユーザーが存在しない
    if not user:
        logging.error(f'[UsersRouter][UserAccessTokenAPI] Incorrect username [username: {form_data.username}]')
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = 'Incorrect username',
            headers = {'WWW-Authenticate': 'Bearer'},
        )

    # 指定されたパスワードのハッシュが DB にあるものと一致しない
    if not passlib_context.verify(form_data.password, user.password):
        logging.error(f'[UsersRouter][UserAccessTokenAPI] Incorrect password [username: {form_data.username}]')
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
        'iat': datetime.now(ZoneInfo('Asia/Tokyo')),
        # JWT の有効期限 (JWT の発行から 180 日間)
        'exp': datetime.now(ZoneInfo('Asia/Tokyo')) + timedelta(days=180),
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
async def UserMeAPI(
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
async def UserUpdateMeAPI(
    user_update_request: Annotated[schemas.UserUpdateRequest, Body(description='更新するユーザーアカウントの情報。')],
    current_user: Annotated[User, Depends(GetCurrentUser)],
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
            logging.error(f'[UsersRouter][UserUpdateMeAPI] Specified username is duplicated [username: {user_update_request.username}]')
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail = 'Specified username is duplicated',
            )

        # ユーザー名が token or me だったら 422 を返す
        ## /api/users/me と /api/users/token があるので、もしその名前で登録できてしまうと重複して面倒なことになる
        ## そんな名前で登録する人はいないとは思うけど、念のため…。
        if user_update_request.username.lower() == 'me' or user_update_request.username.lower() == 'token':
            logging.error(f'[UsersRouter][UserUpdateMeAPI] Specified username is not accepted due to system limitations [username: {user_update_request.username}]')
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail = 'Specified username is not accepted due to system limitations',
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
            'content': {'image/jpeg': {}, 'image/png': {}},
        }
    }
)
async def UserIconMeAPI(
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
    save_path = ACCOUNT_ICON_DIR / f'{current_user.id:02}.png'
    if pathlib.Path.exists(save_path):
        return FileResponse(save_path, headers=header)

    # デフォルトのアイコン画像を返す
    return FileResponse(ACCOUNT_ICON_DEFAULT_DIR / 'default.png', headers=header)


@router.put(
    '/me/icon',
    summary = 'アカウントアイコン画像更新 API (ログイン中のユーザー)',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def UserUpdateIconMeAPI(
    image: Annotated[UploadFile, File(description='アカウントのアイコン画像 (JPEG or PNG)。')],
    current_user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    現在ログイン中のユーザーアカウントのアイコン画像を更新する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    # MIME タイプが image/jpeg or image/png 以外
    if image.content_type != 'image/jpeg' and image.content_type != 'image/png':
        logging.error(f'[UsersRouter][UserUpdateIconMeAPI] Please upload JPEG or PNG image [content_type: {image.content_type}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Please upload JPEG or PNG image',
        )

    # 正方形の 400×400 の PNG にリサイズして保存
    # 保存するファイルパス: (ユーザー ID を0埋めしたもの).png
    await TrimSquareAndResizeAndSave(image.file, ACCOUNT_ICON_DIR / f'{current_user.id:02}.png', resize_width_and_height=400)


@router.delete(
    '/me',
    summary = 'アカウント削除 API (ログイン中のユーザー)',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def UserDeleteMeAPI(
    current_user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    現在ログイン中のユーザーアカウントを削除する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    # アイコン画像が保存されていれば削除する
    save_path = ACCOUNT_ICON_DIR / f'{current_user.id:02}.png'
    if pathlib.Path.exists(save_path):
        save_path.unlink()

    # 現在ログイン中のユーザーアカウント（自分自身）を削除
    # アカウントを削除すると、それ以降は（当然ながら）ログインを要求する API へアクセスできなくなる
    await current_user.delete()

    # ユーザーを削除した結果、管理者アカウントがいなくなってしまった場合
    ## ID が一番若いアカウントに管理者権限を付与する（そうしないと誰も管理者権限を行使できないし付与できない）
    if await User.filter(is_admin=True).get_or_none() is None:
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
async def UserAPI(
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
async def UserUpdateAPI(
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

    # レコードを保存する
    await user.save()


@router.get(
    '/{username}/icon',
    summary = 'アカウントアイコン画像 API',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'ユーザーアカウントのアイコン画像。',
            'content': {'image/jpeg': {}, 'image/png': {}},
        }
    }
)
async def UserIconAPI(
    user: Annotated[User, Depends(GetSpecifiedUser)],
):
    """
    指定されたユーザーアカウントのユーザーアカウントのアイコン画像を取得する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    # ブラウザにキャッシュさせないようにヘッダーを設定
    # ref: https://developer.mozilla.org/ja/docs/Web/HTTP/Headers/Cache-Control
    header = {
        'Cache-Control': 'no-store',
    }

    # アイコン画像が保存されていればそれを返す
    save_path = ACCOUNT_ICON_DIR / f'{user.id:02}.png'
    if pathlib.Path.exists(save_path):
        return FileResponse(save_path, headers=header)

    # デフォルトのアイコン画像を返す
    return FileResponse(ACCOUNT_ICON_DEFAULT_DIR / 'default.png', headers=header)


@router.put(
    '/{username}/icon',
    summary = 'アカウントアイコン画像更新 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def UserUpdateIconAPI(
    image: Annotated[UploadFile, File(description='アカウントのアイコン画像 (JPEG or PNG)。')],
    user: Annotated[User, Depends(GetSpecifiedUser)],
):
    """
    指定されたユーザーアカウントのアイコン画像を更新する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    # MIME タイプが image/jpeg or image/png 以外
    if image.content_type != 'image/jpeg' and image.content_type != 'image/png':
        logging.error(f'[UsersRouter][UserUpdateIconAPI] Please upload JPEG or PNG image [content_type: {image.content_type}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Please upload JPEG or PNG image',
        )

    # 正方形の 400×400 の PNG にリサイズして保存
    # 保存するファイルパス: (ユーザー ID を0埋めしたもの).png
    await TrimSquareAndResizeAndSave(image.file, ACCOUNT_ICON_DIR / f'{user.id:02}.png', resize_width_and_height=400)


@router.delete(
    '/{username}',
    summary = 'アカウント削除 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def UserDeleteAPI(
    user: Annotated[User, Depends(GetSpecifiedUser)],
):
    """
    指定されたユーザーアカウントを削除する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    # アイコン画像が保存されていれば削除する
    save_path = ACCOUNT_ICON_DIR / f'{user.id:02}.png'
    if pathlib.Path.exists(save_path):
        save_path.unlink()

    # 指定されたユーザーを削除
    await user.delete()

    # ユーザーを削除した結果、管理者アカウントがいなくなってしまった場合
    ## ID が一番若いアカウントに管理者権限を付与する（そうしないと誰も管理者権限を行使できないし付与できない）
    if await User.filter(is_admin=True).get_or_none() is None:
        id_young_user = await User.all().order_by('id').first()
        if id_young_user is not None:
            id_young_user.is_admin = True
            await id_young_user.save()
