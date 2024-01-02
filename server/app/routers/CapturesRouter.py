
import asyncio
import errno
import puremagic
import shutil
from fastapi import APIRouter
from fastapi import File
from fastapi import HTTPException
from fastapi import status
from fastapi import UploadFile
from pathlib import Path
from typing import cast

from app import logging
from app.config import Config


# ルーター
router = APIRouter(
    tags = ['Captures'],
    prefix = '/api/captures',
)


@router.post(
    '',
    summary = 'キャプチャ画像アップロード API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def CaptureUploadAPI(
    image: UploadFile = File(description='アップロードするキャプチャ画像 (JPEG or PNG)。'),
):
    """
    クライアント側でキャプチャした画像をサーバーにアップロードする。<br>
    アップロードされた画像は、サーバー設定で指定されたフォルダに保存される。
    """

    # 画像が JPEG または PNG かをチェック
    ## 万が一悪意ある攻撃者から危険なファイルを送り込まれないように
    mimetype: str = puremagic.magic_stream(image.file)[0].mime_type
    if mimetype != 'image/jpeg' and mimetype != 'image/png':
        logging.error('[CapturesRouter][CaptureUploadAPI] Invalid image file was uploaded.')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Please upload JPEG or PNG image',
        )

    # シークを元に戻す（重要）
    ## puremagic を使った時点でファイルはシークされているため、戻さないと 0 バイトになる
    image.file.seek(0)

    # ディレクトリトラバーサル対策のためのチェック
    ## ref: https://stackoverflow.com/a/45190125/17124142
    filename = Path(cast(str, image.filename))
    upload_folder = Path(Config().capture.upload_folder)
    try:
        upload_folder.joinpath(filename).resolve().relative_to(upload_folder.resolve())
    except ValueError:
        logging.error('[CapturesRouter][CaptureUploadAPI] Invalid filename was specified.')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified filename is invalid',
        )

    # 保存するファイルパス
    filepath = upload_folder / filename

    # 既にファイルが存在していた場合は上書きしないようにリネーム
    ## ref: https://note.nkmk.me/python-pathlib-name-suffix-parent/
    count = 1
    while filepath.exists():
        filepath = upload_folder / f'{filename.stem}-{count}{filename.suffix}'
        count += 1

    # キャプチャを保存
    try:
        with await asyncio.to_thread(open, filepath, mode='wb') as buffer:
            await asyncio.to_thread(shutil.copyfileobj, image.file, buffer)
    except PermissionError:
        logging.error('[CapturesRouter][CaptureUploadAPI] Permission denied to save the file.')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Permission denied to save the file',
        )
    except OSError as ex:
        is_disk_full_error = False
        if hasattr(ex, 'winerror'):
            is_disk_full_error = ex.winerror == 112  # type: ignore
        if hasattr(ex, 'errno'):
            is_disk_full_error = ex.errno == errno.ENOSPC
        if is_disk_full_error is True:
            logging.error('[CapturesRouter][CaptureUploadAPI] No space left on the device.')
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail = 'No space left on the device',
            )
        else:
            logging.error(f'[CapturesRouter][CaptureUploadAPI] Unexpected OSError: {ex}')
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail = 'Unexpected error occurred while saving the file',
            )
