"""録画ファイルのスキャン処理に関連する API の E2E テスト。"""


import asyncio
import os
import shutil
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx2 as httpx

from app.constants import JST, THUMBNAILS_DIR
from app.metadata.RecordedScanTask import RecordedScanTask
from app.models.RecordedVideo import RecordedVideo
from tests.conftest import FIXTURES_DIR


async def WaitUntil(condition: Callable[[], Awaitable[Any]], timeout: float = 30.0) -> Any:
    """
    条件の関数が真の値を返すまで繰り返し呼び、その値を返す

    Args:
        condition (Callable[[], Awaitable[Any]]): 待つ条件 (真の値を返したら待ち終える)
        timeout (float): 待つ秒数の上限

    Returns:
        Any: 条件の関数が返した真の値
    """

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        result = await condition()
        if result:
            return result
        assert loop.time() < deadline, f'Condition was not met within {timeout} seconds.'
        await asyncio.sleep(0.2)


def PlaceRecording(file_name: str, recorded_folder: Path) -> Path:
    """
    テスト用の録画ファイルを、録画が終わった状態で録画フォルダへ置く
    コピーの途中を録画中として検知されないよう、録画フォルダの外で写してから名前の変更で一度に置く
    更新日時は、録画が終わってから時間が経った録画と同じく放送日に戻す

    Args:
        file_name (str): tests/fixtures/recorded/ 以下のファイル名
        recorded_folder (Path): 録画フォルダのパス

    Returns:
        Path: 録画フォルダに置いたファイルのパス
    """

    staging_path = recorded_folder.parent / file_name
    shutil.copyfile(FIXTURES_DIR / 'recorded' / file_name, staging_path)
    recorded_at = datetime(2019, 8, 9, 20, 45, tzinfo=JST).timestamp()
    os.utime(staging_path, (recorded_at, recorded_at))
    recorded_path = recorded_folder / file_name
    staging_path.rename(recorded_path)
    return recorded_path


# =====================================================================================
# API 単体 E2E テスト
# ルーターの API 定義順に並べる
# 各 API について 正常系 → 異常系 の順番でテストを並べる
# =====================================================================================

# -------------------------------------------------------------------------------------
# POST /api/maintenance/batch-scan/run (BatchScanAPI) - 正常系
# -------------------------------------------------------------------------------------

async def test_manual_batch_scan__can_run_again_after_startup_scan(client: httpx.AsyncClient) -> None:
    """
    起動時の一括スキャンの実行中に手動の一括スキャンを実行すると 429 を返し、
    起動時の一括スキャンが終わった後は、手動の一括スキャンを再び実行できる
    """

    # 起動時と同じく、録画フォルダの一括スキャンを API を通さずに始める
    startup_scan = asyncio.create_task(RecordedScanTask().runBatchScan())
    await asyncio.sleep(0)
    response = await client.post('/api/maintenance/batch-scan/run')
    assert response.status_code == 429, response.text

    # 起動時の一括スキャンが終わった後は、手動の一括スキャンを実行できる
    await startup_scan
    response = await client.post('/api/maintenance/batch-scan/run')
    assert response.status_code == 204, response.text
    response = await client.post('/api/maintenance/batch-scan/run')
    assert response.status_code == 204, response.text


# =====================================================================================
# 複合 E2E テスト
# 複数の API が絡むフローのテスト
# =====================================================================================

# -------------------------------------------------------------------------------------
# 録画ファイルのスキャン・登録・解析・サムネイル生成・削除フロー
# (POST /api/maintenance/batch-scan/run → GET /api/videos → GET /api/videos/{id} → DELETE /api/videos/{id}) - 正常系
# -------------------------------------------------------------------------------------


async def test_manual_batch_scan__recording_is_registered_analyzed_and_hidden_when_missing(client: httpx.AsyncClient, recorded_folder: Path) -> None:
    """
    録画フォルダに置いた録画が監視で見つかって録画番組として登録され、サムネイルが作られ、
    録画ファイルを消すと録画番組は一覧から隠れ、レコードは Missing として残る
    """

    # 起動時の一括スキャンが終わってから録画を置き、録画フォルダの監視で見つかる経路を通す
    async def IsStartupScanFinished() -> bool:
        response = await client.get('/api/maintenance/batch-scan/status')
        assert response.status_code == 200, response.text
        return response.json()['is_running'] is False
    await WaitUntil(IsStartupScanFinished)
    recorded_path = PlaceRecording('terrestrial-tsreplace-h264.ts', recorded_folder)

    # 監視で見つかり、番組情報を解析して登録されるまで待つ
    async def GetRecordedPrograms() -> list[dict[str, Any]]:
        response = await client.get('/api/videos')
        assert response.status_code == 200, response.text
        return response.json()['recorded_programs']
    recorded_programs = await WaitUntil(GetRecordedPrograms)
    assert len(recorded_programs) == 1
    recorded_program = recorded_programs[0]
    assert recorded_program['title'] == '受信料と公共放送についてご理解いただくために[字]'
    assert recorded_program['channel']['name'] == 'NHK総合1・東京'
    assert recorded_program['recorded_video']['file_path'] == str(recorded_path)
    assert recorded_program['recorded_video']['video_codec'] == 'H.264'

    # バックグラウンドの解析で、代表サムネイルとシークバー用のタイル画像が作られるまで待つ
    async def GetThumbnailInfo() -> dict[str, Any] | None:
        response = await client.get(f'/api/videos/{recorded_program["id"]}')
        assert response.status_code == 200, response.text
        return response.json()['recorded_video']['thumbnail_info']
    thumbnail_info = await WaitUntil(GetThumbnailInfo)
    assert thumbnail_info['representative']['format'] == 'WebP'
    file_hash = recorded_program['recorded_video']['file_hash']
    assert (THUMBNAILS_DIR / f'{file_hash}.webp').exists()
    assert (THUMBNAILS_DIR / f'{file_hash}_tile.webp').exists()
    response = await client.get(f'/api/videos/{recorded_program["id"]}/thumbnail')
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'image/webp'

    # 録画ファイルを消すと、録画番組は一覧からも個別の取得からも隠れる
    recorded_path.unlink()
    async def IsHidden() -> bool:
        return len(await GetRecordedPrograms()) == 0
    await WaitUntil(IsHidden)
    response = await client.get(f'/api/videos/{recorded_program["id"]}')
    assert response.status_code == 422

    # 録画ファイルが一時的に見えなくなっただけの場合に備えて、レコードはすぐには削除されず、見つからなくなった日時とともに残る
    recorded_video = await RecordedVideo.get(id=recorded_program['recorded_video']['id'])
    assert recorded_video.status == 'Missing'
    assert recorded_video.missing_since is not None
