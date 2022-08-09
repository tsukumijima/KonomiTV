
import asyncio
from multiprocessing.sharedctypes import Value
import puremagic
import shutil
from fastapi import APIRouter
from fastapi import File
from fastapi import HTTPException
from fastapi import status
from fastapi import UploadFile
from pathlib import Path

from app.constants import CONFIG, DOCKER_FS_PREFIX


# ルーター
router = APIRouter(
    tags=['Captures'],
    prefix='/api/captures',
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
    アップロードされた画像は、環境設定で指定されたフォルダに保存される。
    """

    # 画像が JPEG または PNG かをチェック
    ## 万が一悪意ある攻撃者から危険なファイルを送り込まれないように
    mimetype: str = puremagic.magic_stream(image.file)[0].mime_type
    if mimetype != 'image/jpeg' and mimetype != 'image/png':
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Please upload JPEG or PNG image',
        )

    # シークを元に戻す（重要）
    ## puremagic を使った時点でファイルはシークされているため、戻さないと 0 バイトになる
    image.file.seek(0)

    # Docker 環境向けの Prefix を付ける (非 Docker 環境ではそのまま)
    upload_folder = DOCKER_FS_PREFIX / Path(CONFIG['capture']['upload_folder'])

    # ディレクトリトラバーサル対策のためのチェック
    ## ref: https://stackoverflow.com/a/45190125/17124142
    try:
        upload_folder.joinpath(Path(image.filename)).resolve().relative_to(upload_folder.resolve())
    except ValueError:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified filename is invalid.',
        )

    # 保存するファイルパス
    filepath = upload_folder / image.filename

    # 既にファイルが存在していた場合は上書きしないようにリネーム
    ## ref: https://note.nkmk.me/python-pathlib-name-suffix-parent/
    count = 1
    while filepath.exists():
        filepath = upload_folder / f'{Path(image.filename).stem}-{count}{Path(image.filename).suffix}'
        count += 1

    # キャプチャを保存
    with open(filepath, 'wb') as buffer:
        await asyncio.to_thread(shutil.copyfileobj, image.file, buffer)
