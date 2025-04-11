
import time
from typing import Any

import httpx
from fastapi import APIRouter

from app import schemas
from app.config import Config
from app.constants import HTTPX_CLIENT, VERSION
from app.utils import GetPlatformEnvironment


# ルーター
router = APIRouter(
    tags = ['Version'],
    prefix = '/api/version',
)


# GitHub API から取得した KonomiTV の最新バージョン (と最終更新日時)
latest_version: str | None = None
latest_version_updated_at: float = 0


@router.get(
    '',
    summary = 'バージョン情報取得 API',
    response_description = 'KonomiTV サーバーのバージョンなどの情報。',
    response_model = schemas.VersionInformation,
)
async def VersionInformationAPI():
    """
    KonomiTV サーバーのバージョン情報と、バックエンドの種類、稼働環境などを取得する。
    """

    global latest_version, latest_version_updated_at

    # GitHub API で KonomiTV の最新のタグ (=最新バージョン) を取得
    ## GitHub API は無認証だと60回/1時間までしかリクエストできないので、リクエスト結果を10分ほどキャッシュする
    if latest_version is None or (time.time() - latest_version_updated_at) > 60 * 10:
        try:
            async with HTTPX_CLIENT() as client:
                response = await client.get('https://api.github.com/repos/tsukumijima/KonomiTV/tags')
            if response.status_code == 200:
                latest_version = response.json()[0]['name'].replace('v', '')  # 先頭の v を取り除く
                latest_version_updated_at = time.time()
        except (httpx.NetworkError, httpx.TimeoutException):
            pass

    # サーバーが稼働している環境を取得
    environment = GetPlatformEnvironment()

    result: dict[str, Any] = {
        'version': VERSION,
        'latest_version': latest_version,
        'environment': environment,
        'backend': Config().general.backend,
        'encoder': Config().general.encoder,
    }
    return result
