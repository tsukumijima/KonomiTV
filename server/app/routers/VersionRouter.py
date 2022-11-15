
import asyncio
import os
import requests
from fastapi import APIRouter
from pathlib import Path

from app import schemas
from app.constants import API_REQUEST_HEADERS, CONFIG, VERSION

# ルーター
router = APIRouter(
    tags = ['Version'],
    prefix = '/api/version',
)


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

    # GitHub API で KonomiTV の最新のタグ (=最新バージョン) を取得
    latest_version = ''
    try:
        response = await asyncio.to_thread(requests.get,
            url = 'https://api.github.com/repos/tsukumijima/KonomiTV/tags',
            headers = API_REQUEST_HEADERS,
            timeout = 3,
        )
        if response.status_code == 200:
            latest_version = response.json()[0]['name'].replace('v', '')  # 先頭の v を取り除く
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        pass

    # サーバーが稼働している環境を取得
    environment = 'Windows' if os.name else 'Linux'
    if environment == 'Linux' and Path.exists(Path('/.dockerenv')) is True:
        # Linux かつ Docker 環境
        environment = 'Linux-Docker'

    return {
        'version': VERSION,
        'latest_version': latest_version,
        'environment': environment,
        'backend': CONFIG['general']['backend'],
        'encoder': CONFIG['general']['encoder'],
    }
