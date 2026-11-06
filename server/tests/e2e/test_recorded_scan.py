"""録画ファイルのスキャン処理に関連する API の E2E テスト。"""


import asyncio
import os
import shutil
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import anyio
import httpx2 as httpx
import pytest

from app.constants import JST, THUMBNAILS_DIR
from app.metadata.RecordedScanTask import RecordedScanTask
from app.models.RecordedVideo import RecordedVideo
from tests.conftest import FIXTURES_DIR, RECORDED_FOLDER


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


def PlaceRecording(
    file_name: str,
    recorded_folder: Path,
    recorded_at: datetime = datetime(2019, 8, 9, 20, 45, tzinfo=JST),
) -> Path:
    """
    テスト用の録画ファイルを、録画が終わった状態で録画フォルダへ置く
    コピーの途中を録画中として検知されないよう、録画フォルダの外で写してから名前の変更で一度に置く
    更新日時は、録画が終わってから時間が経った録画と同じく放送日に戻す
    同じ録画ファイルを複数のテストで使うときは、テストごとに更新日時を変えて、そのテストで置いたファイルのレコードとだけ照合されるようにする

    Args:
        file_name (str): tests/fixtures/recorded/ 以下のファイル名
        recorded_folder (Path): 置き先のフォルダのパス (録画フォルダかその中のフォルダ。なければ作る)
        recorded_at (datetime): 置いたファイルの更新日時

    Returns:
        Path: 録画フォルダに置いたファイルのパス
    """

    staging_path = RECORDED_FOLDER.parent / file_name
    shutil.copyfile(FIXTURES_DIR / 'recorded' / file_name, staging_path)
    os.utime(staging_path, (recorded_at.timestamp(), recorded_at.timestamp()))
    recorded_folder.mkdir(parents=True, exist_ok=True)
    recorded_path = recorded_folder / file_name
    staging_path.rename(recorded_path)
    return recorded_path


async def WaitForStartupScan(client: httpx.AsyncClient) -> None:
    """
    サーバーの起動時に始まった録画フォルダの一括スキャンが終わるまで待つ

    Args:
        client (httpx.AsyncClient): テスト用のサーバーにつないだクライアント
    """

    async def IsStartupScanFinished() -> bool:
        response = await client.get('/api/maintenance/batch-scan/status')
        assert response.status_code == 200, response.text
        return response.json()['is_running'] is False
    await WaitUntil(IsStartupScanFinished)


async def GetRecordedProgramByPath(client: httpx.AsyncClient, file_path: Path) -> dict[str, Any] | None:
    """
    録画番組の一覧から、録画ファイルのパスが一致する録画番組を探す

    Args:
        client (httpx.AsyncClient): テスト用のサーバーにつないだクライアント
        file_path (Path): 録画ファイルのパス

    Returns:
        dict[str, Any] | None: 録画番組 (一覧にないときは None)
    """

    response = await client.get('/api/videos')
    assert response.status_code == 200, response.text
    for recorded_program in response.json()['recorded_programs']:
        if recorded_program['recorded_video']['file_path'] == str(file_path):
            return recorded_program
    return None


async def IsRecordedProgramGone(client: httpx.AsyncClient, file_path: Path) -> bool:
    """
    録画ファイルのパスが一致する録画番組が、録画番組の一覧から消えたかを返す

    Args:
        client (httpx.AsyncClient): テスト用のサーバーにつないだクライアント
        file_path (Path): 録画ファイルのパス

    Returns:
        bool: 一覧から消えていれば True
    """

    return await GetRecordedProgramByPath(client, file_path) is None


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

    # サーバーの起動時に始まった一括スキャンが終わってから、起動時と同じく、録画フォルダの一括スキャンを API を通さずに始める
    await WaitForStartupScan(client)
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
    await WaitForStartupScan(client)
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


# -------------------------------------------------------------------------------------
# 録画ファイルやフォルダの名前を変えると、同じ録画番組のまま新しいパスに付け替わるフロー
# (録画フォルダの監視 → GET /api/videos → GET /api/videos/{id}) - 正常系
# -------------------------------------------------------------------------------------


async def test_recorded_file_renamed__keeps_same_record(client: httpx.AsyncClient, recorded_folder: Path) -> None:
    """
    録画フォルダの中で録画ファイルの名前を変えると、同じ ID の録画番組のまま新しいパスに付け替わり、作ったサムネイル情報も残る
    """

    await WaitForStartupScan(client)
    recorded_path = PlaceRecording('terrestrial-tsreplace-h264.ts', recorded_folder / 'rename', datetime(2019, 8, 10, 20, 45, tzinfo=JST))
    recorded_program = await WaitUntil(lambda: GetRecordedProgramByPath(client, recorded_path))

    # バックグラウンドの解析が終わってから、名前を変える
    async def GetThumbnailInfo() -> dict[str, Any] | None:
        response = await client.get(f'/api/videos/{recorded_program["id"]}')
        assert response.status_code == 200, response.text
        return response.json()['recorded_video']['thumbnail_info']
    thumbnail_info = await WaitUntil(GetThumbnailInfo)
    renamed_path = recorded_path.with_name('renamed.ts')
    recorded_path.rename(renamed_path)

    # 同じ ID のまま新しいパスに付け替わり、サムネイル情報も同じものが残る
    renamed_program = await WaitUntil(lambda: GetRecordedProgramByPath(client, renamed_path))
    assert renamed_program['id'] == recorded_program['id']
    assert await GetThumbnailInfo() == thumbnail_info

    renamed_path.unlink()
    await WaitUntil(lambda: IsRecordedProgramGone(client, renamed_path))


async def test_recorded_folder_renamed__keeps_same_record(client: httpx.AsyncClient, recorded_folder: Path) -> None:
    """
    録画フォルダの中で録画ファイルの入ったフォルダごと名前を変えると (配下のファイルの通知が届かない)、
    同じ ID の録画番組のまま新しいパスに付け替わる
    """

    await WaitForStartupScan(client)
    folder = recorded_folder / 'folder-rename'
    recorded_path = PlaceRecording('terrestrial-tsreplace-h264.ts', folder, datetime(2019, 8, 14, 20, 45, tzinfo=JST))
    recorded_program = await WaitUntil(lambda: GetRecordedProgramByPath(client, recorded_path))

    # フォルダごと名前を変えると、同じ ID のまま新しいパスに付け替わる
    renamed_folder = recorded_folder / 'folder-renamed'
    folder.rename(renamed_folder)
    renamed_path = renamed_folder / recorded_path.name
    renamed_program = await WaitUntil(lambda: GetRecordedProgramByPath(client, renamed_path))
    assert renamed_program['id'] == recorded_program['id']

    renamed_path.unlink()
    await WaitUntil(lambda: IsRecordedProgramGone(client, renamed_path))


# -------------------------------------------------------------------------------------
# 同じ中身の録画ファイルを別の場所へ写すと、元のファイルが消えるまで付け替えを保留し、消えたら同じ録画番組のまま付け替わるフロー
# (録画フォルダの監視 → POST /api/maintenance/batch-scan/run → GET /api/videos → DELETE /api/videos/{id}) - 正常系
# -------------------------------------------------------------------------------------


async def test_recorded_file_copied__waits_for_original_to_be_removed(client: httpx.AsyncClient, recorded_folder: Path) -> None:
    """
    同じ中身の録画ファイルを録画フォルダの別の場所へ置いても、元のファイルが見えるあいだは新しい録画番組を作らずに保留し、
    サーバーを再起動して保留の記録が消えても一括スキャンで保留に戻り、元のファイルを消すと同じ ID のまま付け替わる
    """

    await WaitForStartupScan(client)
    recorded_at = datetime(2019, 8, 11, 20, 45, tzinfo=JST)
    original_path = PlaceRecording('terrestrial-tsreplace-h264.ts', recorded_folder / 'copy-original', recorded_at)
    original_program = await WaitUntil(lambda: GetRecordedProgramByPath(client, original_path))

    # 別のフォルダへ同じ中身のファイルを置くと、付け替えを保留して、一覧には元の録画番組だけが出る
    copied_path = PlaceRecording('terrestrial-tsreplace-h264.ts', recorded_folder / 'copy-destination', recorded_at)
    async def IsPending() -> bool:
        return copied_path in RecordedScanTask().pending_moves
    await WaitUntil(IsPending)
    assert await GetRecordedProgramByPath(client, copied_path) is None
    assert (await GetRecordedProgramByPath(client, original_path) or {}).get('id') == original_program['id']

    # サーバーを再起動して保留の記録が消えても、一括スキャンで保留に戻る
    RecordedScanTask().pending_moves.clear()
    response = await client.post('/api/maintenance/batch-scan/run')
    assert response.status_code == 204, response.text
    await WaitUntil(IsPending)
    assert await GetRecordedProgramByPath(client, copied_path) is None

    # 元のファイルを消すと、同じ ID のまま新しいパスへ付け替わる
    original_path.unlink()
    moved_program = await WaitUntil(lambda: GetRecordedProgramByPath(client, copied_path))
    assert moved_program['id'] == original_program['id']
    assert copied_path not in RecordedScanTask().pending_moves

    copied_path.unlink()
    await WaitUntil(lambda: IsRecordedProgramGone(client, copied_path))


async def test_recorded_file_copied__original_removed_without_notification(
    client: httpx.AsyncClient,
    recorded_folder: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    付け替えを保留している間に、元のファイルの削除イベントが届かずに消えても (通知があふれたときなど)、
    保留の見回りで元のファイルがなくなったことに気づき、同じ ID のまま付け替わる
    """

    # 見回りの間隔を短くする
    monkeypatch.setattr(RecordedScanTask, 'PENDING_MOVE_CHECK_INTERVAL_SECONDS', 1)

    # 監視していないフォルダを録画フォルダに加えて一括スキャンし、そのフォルダの録画を登録する
    ## このフォルダのファイルを消しても削除イベントは届かない
    await WaitForStartupScan(client)
    recorded_at = datetime(2019, 8, 12, 20, 45, tzinfo=JST)
    unwatched_folder = RECORDED_FOLDER.parent / 'unwatched'
    monkeypatch.setattr(RecordedScanTask(), 'recorded_folders', [anyio.Path(recorded_folder), anyio.Path(unwatched_folder)])
    original_path = PlaceRecording('terrestrial-tsreplace-h264.ts', unwatched_folder, recorded_at)
    response = await client.post('/api/maintenance/batch-scan/run')
    assert response.status_code == 204, response.text
    original_program = await WaitUntil(lambda: GetRecordedProgramByPath(client, original_path))

    # 監視している録画フォルダへ同じ中身のファイルを置くと、付け替えを保留する
    copied_path = PlaceRecording('terrestrial-tsreplace-h264.ts', recorded_folder / 'unwatched-destination', recorded_at)
    async def IsPending() -> bool:
        return copied_path in RecordedScanTask().pending_moves
    await WaitUntil(IsPending)

    # 元のファイルを消すと、削除イベントは届かないが、見回りで同じ ID のまま付け替わる
    original_path.unlink()
    moved_program = await WaitUntil(lambda: GetRecordedProgramByPath(client, copied_path))
    assert moved_program['id'] == original_program['id']

    unwatched_folder.rmdir()
    copied_path.unlink()
    await WaitUntil(lambda: IsRecordedProgramGone(client, copied_path))


async def test_recorded_file_copied__copy_paused_halfway(
    client: httpx.AsyncClient,
    recorded_folder: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    別の場所へのコピーが途中で止まり、途中までの中身が録画済みとして登録されても、
    コピーを再開して書き終えると付け替えを保留し、元のファイルを消すと同じ ID のまま付け替わる
    """

    # 書き込みが止まってから録画の完了とみなすまでの時間を短くする
    monkeypatch.setattr(RecordedScanTask, 'RECORDING_COMPLETE_SECONDS', 2)

    await WaitForStartupScan(client)
    recorded_at = datetime(2019, 8, 18, 20, 45, tzinfo=JST)
    original_path = PlaceRecording('terrestrial-tsreplace-h264.ts', recorded_folder / 'pause-original', recorded_at)
    original_program = await WaitUntil(lambda: GetRecordedProgramByPath(client, original_path))

    # 録画フォルダの中へ直接、中身の8割まで書いて止めると、途中までの中身が別の録画番組として登録される
    content = (FIXTURES_DIR / 'recorded' / 'terrestrial-tsreplace-h264.ts').read_bytes()
    copied_folder = recorded_folder / 'pause-destination'
    copied_folder.mkdir()
    await asyncio.sleep(0.5)
    copied_path = copied_folder / 'terrestrial-tsreplace-h264.ts'
    copied_path.write_bytes(content[:len(content) * 8 // 10])
    partial_program = await WaitUntil(lambda: GetRecordedProgramByPath(client, copied_path))
    assert partial_program['id'] != original_program['id']

    # コピーを再開して書き終え、更新日時を元に戻すと、途中の録画番組は消えて付け替えを保留する
    with copied_path.open('ab') as file:
        file.write(content[len(content) * 8 // 10:])
    os.utime(copied_path, (recorded_at.timestamp(), recorded_at.timestamp()))
    async def IsPending() -> bool:
        return copied_path in RecordedScanTask().pending_moves
    await WaitUntil(IsPending)
    assert await GetRecordedProgramByPath(client, copied_path) is None

    # 元のファイルを消すと、同じ ID のまま付け替わる
    original_path.unlink()
    moved_program = await WaitUntil(lambda: GetRecordedProgramByPath(client, copied_path))
    assert moved_program['id'] == original_program['id']

    copied_path.unlink()
    await WaitUntil(lambda: IsRecordedProgramGone(client, copied_path))


async def test_recorded_file_copied__original_deleted_by_api(
    client: httpx.AsyncClient,
    recorded_folder: Path,
    admin_headers: dict[str, str],
) -> None:
    """
    付け替えを保留している間に、元の録画番組を削除 API で消すと、消した ID は戻さず、残っているファイルを新しい録画番組として登録する
    """

    await WaitForStartupScan(client)
    recorded_at = datetime(2019, 8, 13, 20, 45, tzinfo=JST)
    original_path = PlaceRecording('terrestrial-tsreplace-h264.ts', recorded_folder / 'delete-original', recorded_at)
    original_program = await WaitUntil(lambda: GetRecordedProgramByPath(client, original_path))
    copied_path = PlaceRecording('terrestrial-tsreplace-h264.ts', recorded_folder / 'delete-destination', recorded_at)
    async def IsPending() -> bool:
        return copied_path in RecordedScanTask().pending_moves
    await WaitUntil(IsPending)

    # 元の録画番組を削除 API で消す (録画ファイルも消える)
    response = await client.delete(f'/api/videos/{original_program["id"]}', headers=admin_headers)
    assert response.status_code == 204, response.text
    assert original_path.exists() is False

    # 残っているファイルが、別の ID の新しい録画番組として登録される
    registered_program = await WaitUntil(lambda: GetRecordedProgramByPath(client, copied_path))
    assert registered_program['id'] != original_program['id']

    copied_path.unlink()
    await WaitUntil(lambda: IsRecordedProgramGone(client, copied_path))


# -------------------------------------------------------------------------------------
# 録画ファイルを別のファイルシステムや別のドライブへ移しても、同じ録画番組のまま付け替わるフロー
# (録画フォルダの監視 → GET /api/videos) - 正常系
# -------------------------------------------------------------------------------------


async def test_recorded_file_moved_to_coarser_filesystem__keeps_same_record(client: httpx.AsyncClient, recorded_folder: Path) -> None:
    """
    移動先のファイルシステムの精度に丸められて更新日時が少しずれても (exFAT・NTFS・SMB へ移したときなど)、
    同じ中身であれば同じ ID の録画番組のまま付け替わり、更新日時は移動先の値になる
    """

    await WaitForStartupScan(client)
    recorded_at = datetime(2019, 8, 15, 20, 45, tzinfo=JST)
    original_path = PlaceRecording('terrestrial-tsreplace-h264.ts', recorded_folder / 'coarse-original', recorded_at)
    original_program = await WaitUntil(lambda: GetRecordedProgramByPath(client, original_path))

    # 更新日時を1秒ずらして同じ中身のファイルを置き、元のファイルを消す
    moved_at = datetime(2019, 8, 15, 20, 45, 1, tzinfo=JST)
    moved_path = PlaceRecording('terrestrial-tsreplace-h264.ts', recorded_folder / 'coarse-destination', moved_at)
    async def IsPending() -> bool:
        return moved_path in RecordedScanTask().pending_moves
    await WaitUntil(IsPending)
    original_path.unlink()

    # 同じ ID のまま付け替わり、更新日時は移動先の値になる
    moved_program = await WaitUntil(lambda: GetRecordedProgramByPath(client, moved_path))
    assert moved_program['id'] == original_program['id']
    recorded_video = await RecordedVideo.get(id=moved_program['recorded_video']['id'])
    assert recorded_video.file_modified_at == moved_at

    moved_path.unlink()
    await WaitUntil(lambda: IsRecordedProgramGone(client, moved_path))


async def test_recorded_folder_setting_changed__relinks_from_old_drive(
    client: httpx.AsyncClient,
    recorded_folder: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    録画フォルダの設定を新しいドライブへ書き換え、古いドライブをつないだまま残しても、
    新しいドライブへ写した同じ中身の録画ファイルへ、同じ ID の録画番組のまま付け替わる
    """

    await WaitForStartupScan(client)
    recorded_at = datetime(2019, 8, 16, 20, 45, tzinfo=JST)
    old_drive = recorded_folder / 'old-drive'
    new_drive = recorded_folder / 'new-drive'
    original_path = PlaceRecording('terrestrial-tsreplace-h264.ts', old_drive, recorded_at)
    original_program = await WaitUntil(lambda: GetRecordedProgramByPath(client, original_path))

    # 録画フォルダの設定を新しいドライブだけにしたのと同じく、録画フォルダの一覧を差し替えてから、同じ中身のファイルを写す
    new_drive.mkdir()
    monkeypatch.setattr(RecordedScanTask(), 'recorded_folders', [anyio.Path(new_drive)])
    copied_path = PlaceRecording('terrestrial-tsreplace-h264.ts', new_drive, recorded_at)

    # 古いドライブのファイルが見えていても、録画フォルダの外にあるので、同じ ID のまま新しいドライブへ付け替わる
    moved_program = await WaitUntil(lambda: GetRecordedProgramByPath(client, copied_path))
    assert moved_program['id'] == original_program['id']
    assert original_path.exists() is True

    original_path.unlink()
    copied_path.unlink()
    await WaitUntil(lambda: IsRecordedProgramGone(client, copied_path))


# -------------------------------------------------------------------------------------
# 録画ファイルの入ったフォルダごと録画フォルダの外へ移すと、中の録画番組が一覧から隠れるフロー
# (録画フォルダの監視 → GET /api/videos) - 正常系
# -------------------------------------------------------------------------------------


async def test_recorded_folder_moved_outside__hides_records(client: httpx.AsyncClient, recorded_folder: Path) -> None:
    """
    録画ファイルの入ったフォルダごと録画フォルダの外へ移すと (ゴミ箱へ移したときなど、配下のファイルの通知が届かない)、
    中の録画番組が一覧から隠れる
    """

    await WaitForStartupScan(client)
    folder = recorded_folder / 'trash'
    recorded_path = PlaceRecording('terrestrial-tsreplace-h264.ts', folder, datetime(2019, 8, 17, 20, 45, tzinfo=JST))
    await WaitUntil(lambda: GetRecordedProgramByPath(client, recorded_path))

    # フォルダごと録画フォルダの外へ移すと、中の録画番組が一覧から隠れる
    moved_out_folder = RECORDED_FOLDER.parent / 'trash'
    folder.rename(moved_out_folder)
    await WaitUntil(lambda: IsRecordedProgramGone(client, recorded_path))

    (moved_out_folder / recorded_path.name).unlink()
    moved_out_folder.rmdir()
