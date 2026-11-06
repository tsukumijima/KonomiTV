"""キャプチャの保存先フォルダのスキャン処理に関連する E2E テスト。"""

import asyncio
import shutil
import sys
import tracemalloc
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

import httpx2 as httpx
import pytest

from app.constants import JST
from app.metadata.CaptureScanTask import CaptureScanTask, NormalizeCapturePath
from app.models.Capture import Capture, CaptureFile
from tests.conftest import FIXTURES_DIR, TEMP_DIR


async def WaitUntil(condition: Callable[[], bool], timeout: float = 30.0) -> None:
    """
    条件の関数が True を返すまで、timeout 秒を上限に待つ
    """

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while condition() is False:
        assert loop.time() < deadline, f'Condition was not met within {timeout} seconds.'
        await asyncio.sleep(0.2)


# =====================================================================================
# 複合 E2E テスト
# 複数の API や保存先のファイル操作が絡むフローのテスト
# =====================================================================================

# -------------------------------------------------------------------------------------
# 保存先の一括スキャンで、移動した画像の場所を付け替え、消えた画像を Missing にするフロー
# (保存先の画像の移動・削除 → CaptureScanTask.runBatchScan()) - 正常系
# -------------------------------------------------------------------------------------


async def test_batch_scan__relinks_moved_file_and_marks_removed_file_missing(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    """
    一括スキャンで、保存先の中で別のフォルダへ移した画像は同じ場所の行のまま新しいパスに付け替わり、
    消えた画像の行は Missing になり、同じ場所に戻すと同じ行のまま利用できる状態に戻る
    """

    # 監視している保存先とは別のフォルダに画像を置き、監視の通知を通さずに一括スキャンだけで登録する
    ## 起動時の一括スキャンや、ほかのテストの削除で始まった一括スキャンが終わるのを待ってから始める
    root = TEMP_DIR / 'batch-scan'
    root.mkdir()
    moved_name = 'Capture_20221003-224010.jpg'
    removed_name = 'Capture_20221219-001337.jpg'
    for file_name in (moved_name, removed_name):
        shutil.copyfile(FIXTURES_DIR / 'captures' / file_name, root / file_name)
    scanner = CaptureScanTask()
    await WaitUntil(lambda: scanner.scan_lock.locked() is False)
    assert await scanner.runBatchScan([str(root)]) is True
    moved_file = await CaptureFile.get(file_path=NormalizeCapturePath(root / moved_name))
    removed_file = await CaptureFile.get(file_path=NormalizeCapturePath(root / removed_name))
    assert moved_file.status == 'Available'
    assert removed_file.status == 'Available'

    # 1枚を子フォルダへ移し、もう1枚を消してから一括スキャンする
    (root / 'moved').mkdir()
    (root / moved_name).rename(root / 'moved' / moved_name)
    removed_data = (root / removed_name).read_bytes()
    (root / removed_name).unlink()
    assert await scanner.runBatchScan([str(root)]) is True

    # 移した画像は、同じ行のまま新しいパスに付け替わる
    relinked_file = await CaptureFile.get(id=moved_file.id)
    assert relinked_file.file_path == NormalizeCapturePath(root / 'moved' / moved_name)
    assert relinked_file.status == 'Available'
    assert relinked_file.capture_id == moved_file.capture_id

    # 消えた画像の行は、すぐには削除されずに Missing になる
    missing_file = await CaptureFile.get(id=removed_file.id)
    assert missing_file.status == 'Missing'
    assert missing_file.missing_since is not None

    # 同じ場所に戻すと、同じ行のまま利用できる状態に戻る
    (root / removed_name).write_bytes(removed_data)
    assert await scanner.runBatchScan([str(root)]) is True
    restored_file = await CaptureFile.get(id=removed_file.id)
    assert restored_file.status == 'Available'
    assert restored_file.missing_since is None

    # ほかのテストの一覧に混ざらないよう、登録したキャプチャを削除する
    response = await client.request('DELETE', '/api/captures', json={'capture_ids': [moved_file.capture_id, removed_file.capture_id]}, headers=admin_headers)
    assert response.status_code == 200, response.text


# -------------------------------------------------------------------------------------
# KonomiTV 自身がキャプチャを削除したときと、外で画像が消されたときの監視のフロー
# (DELETE /api/captures → 保存先の監視 → CaptureScanTask.runBatchScan()) - 正常系
# -------------------------------------------------------------------------------------


async def test_delete_capture__does_not_start_batch_scan(
    client: httpx.AsyncClient,
    admin_headers: dict[str, str],
    capture_folder: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    API で削除したキャプチャの削除の通知では保存先の一括スキャンを始めず、
    KonomiTV の外で消された画像の削除の通知では、消えたファイルを確定するために一括スキャンを始める
    """

    # 監視から始まる一括スキャンの回数を数える
    scan_count = 0
    original_run_batch_scan = CaptureScanTask.runBatchScan
    async def CountingRunBatchScan(self: CaptureScanTask, folders: list[str] | None = None) -> bool:
        nonlocal scan_count
        scan_count += 1
        return await original_run_batch_scan(self, folders)
    monkeypatch.setattr(CaptureScanTask, 'runBatchScan', CountingRunBatchScan)
    await WaitUntil(lambda: CaptureScanTask().scan_lock.locked() is False)

    # アップロードしたキャプチャを API で削除しても、一括スキャンは始まらない
    ## 監視の通知は、変更が落ち着くまで (watchfiles の既定で 1.6 秒) まとめてから届くため、それより長く待つ
    file_name = 'Capture_20260826-044039.jpg'
    data = (FIXTURES_DIR / 'captures' / file_name).read_bytes()
    response = await client.post('/api/captures', files={'image': (file_name, data, 'image/jpeg')})
    assert response.status_code == 201, response.text
    capture = response.json()
    response = await client.request('DELETE', '/api/captures', json={'capture_ids': [capture['id']]}, headers=admin_headers)
    assert response.status_code == 200, response.text
    await asyncio.sleep(5)
    assert scan_count == 0

    # KonomiTV の外で画像を消すと、消えたファイルを確定するために一括スキャンが始まる
    response = await client.post('/api/captures', files={'image': (file_name, data, 'image/jpeg')})
    assert response.status_code == 201, response.text
    capture = response.json()
    response = await client.get(f'/api/captures/{capture["id"]}')
    assert response.status_code == 200, response.text
    Path(response.json()['files'][0]['file_path']).unlink()
    await WaitUntil(lambda: scan_count >= 1)
    await WaitUntil(lambda: CaptureScanTask().scan_lock.locked() is False)
    assert list(capture_folder.iterdir()) == []


# -------------------------------------------------------------------------------------
# ドライブのルートのように、ごみ箱や読めないフォルダを含む保存先を一括スキャンするフロー
# (ごみ箱・権限のないフォルダを含む保存先 → CaptureScanTask.runBatchScan()) - 正常系
# -------------------------------------------------------------------------------------


async def test_batch_scan__skips_trash_and_unreadable_folders(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    """
    保存先の中のごみ箱のフォルダは走査の対象から外し、権限がなくて読めないフォルダがあっても走査を最後まで終えたものとして扱い、
    消えた画像を Missing にできる
    """

    # 保存先の直下に画像を1枚置き、ごみ箱のフォルダと、権限のないフォルダにも画像を置く
    root = TEMP_DIR / 'drive-root'
    root.mkdir()
    file_name = 'Capture_20221003-224010.jpg'
    trashed_name = 'Capture_20221219-001337.jpg'
    shutil.copyfile(FIXTURES_DIR / 'captures' / file_name, root / file_name)
    (root / '#recycle').mkdir()
    shutil.copyfile(FIXTURES_DIR / 'captures' / trashed_name, root / '#recycle' / trashed_name)
    ## Windows の chmod() は読み取り専用の属性しか変更できず、読めないフォルダを作れないので、権限のないフォルダは Linux でだけ置く
    if sys.platform != 'win32':
        (root / 'lost+found').mkdir()
        shutil.copyfile(FIXTURES_DIR / 'captures' / trashed_name, root / 'lost+found' / trashed_name)
        (root / 'lost+found').chmod(0o000)
    try:
        scanner = CaptureScanTask()
        await WaitUntil(lambda: scanner.scan_lock.locked() is False)

        # ごみ箱と権限のないフォルダの中の画像は登録されず、走査は最後まで終えたものとして扱われる
        assert await scanner.runBatchScan([str(root)]) is True
        registered_file = await CaptureFile.get(file_path=NormalizeCapturePath(root / file_name))
        assert registered_file.status == 'Available'
        assert await CaptureFile.filter(file_name=trashed_name).exists() is False

        # 保存先の画像をごみ箱へ移すと、移動として付け替えずに Missing になる
        (root / file_name).rename(root / '#recycle' / file_name)
        assert await scanner.runBatchScan([str(root)]) is True
        missing_file = await CaptureFile.get(id=registered_file.id)
        assert missing_file.file_path == registered_file.file_path
        assert missing_file.status == 'Missing'

    # ほかのテストの一覧に混ざらないよう、登録したキャプチャを削除し、権限を戻して一時フォルダを消せるようにする
    finally:
        if sys.platform != 'win32':
            (root / 'lost+found').chmod(0o755)
    response = await client.request('DELETE', '/api/captures', json={'capture_ids': [registered_file.capture_id]}, headers=admin_headers)
    assert response.status_code == 200, response.text


# -------------------------------------------------------------------------------------
# アップロードの保存先のように、1つのフォルダに大量の画像が並ぶ保存先を一括スキャンするフロー
# (画像が1つのフォルダに並ぶ保存先 → CaptureScanTask.runBatchScan()) - 正常系
# -------------------------------------------------------------------------------------


async def test_batch_scan__lists_flat_folder_with_small_memory(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    1つのフォルダに大量の画像が並ぶ保存先も、画像1枚あたり 250 バイト未満のメモリで一覧を保持し、
    名前の新しい塊から順に、塊の中は名前の昇順に処理する
    """

    # KonomiTV からアップロードしたときと同じ形の名前で、5万枚の画像を1つのフォルダに置く
    ## 一覧の保持に使うメモリと処理の順だけを確かめるため、画像の中身は空にする
    root = TEMP_DIR / 'flat-folder'
    root.mkdir()
    file_count = 50000
    captured_at = datetime(2022, 1, 1, tzinfo=JST)
    for _ in range(file_count):
        (root / captured_at.strftime('Capture_%Y%m%d-%H%M%S.jpg')).touch()
        captured_at += timedelta(seconds=157)

    # 処理する順は、名前の昇順に並べた画像を末尾の塊から順に、塊の中は名前の昇順にする
    sorted_paths = sorted(NormalizeCapturePath(path) for path in root.iterdir())
    expected_paths: list[str] = []
    for chunk_end in range(file_count, 0, -CaptureScanTask.SCAN_CHUNK_SIZE):
        expected_paths.extend(sorted_paths[max(0, chunk_end - CaptureScanTask.SCAN_CHUNK_SIZE):chunk_end])

    # 登録と移動の照合は、処理したパスが期待した順かを照合するだけにする
    ## 処理したパスを保持すると、一覧の保持とは別にメモリを確保してしまうため、件数と順の食い違いだけを記録する
    scanner = CaptureScanTask()
    processed_count = 0
    out_of_order_paths: list[str] = []
    async def MoveFile(*args: object) -> bool:
        return False
    async def ProcessFile(path: str) -> bool:
        nonlocal processed_count
        if path != expected_paths[processed_count] and len(out_of_order_paths) < 5:
            out_of_order_paths.append(path)
        processed_count += 1
        return True
    monkeypatch.setattr(scanner, 'moveFile', MoveFile)
    monkeypatch.setattr(scanner, 'processFile', ProcessFile)
    await WaitUntil(lambda: scanner.scan_lock.locked() is False)

    # 一括スキャンの間に確保したメモリの最大値が、画像1枚あたり 250 バイト未満に収まる
    tracemalloc.start()
    try:
        assert await scanner.runBatchScan([str(root)]) is True
        _, peak_memory = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak_memory < file_count * 250, f'Peak memory: {peak_memory} bytes'

    # すべての画像を期待した順に処理する
    assert processed_count == file_count
    assert out_of_order_paths == []


# -------------------------------------------------------------------------------------
# 設定から外した保存先にあった画像が消えたあとに、すべての保存先を一括スキャンするフロー
# (設定にないフォルダの画像の削除 → CaptureScanTask.runBatchScan()) - 正常系
# -------------------------------------------------------------------------------------


async def test_batch_scan__confirms_removed_files_outside_capture_folders(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    """
    設定されたどの保存先にも属さない場所 (設定から外した保存先にあった場所) は、すべての保存先の一括スキャンで、
    ファイルが消えていれば Missing になり、1週間たっても戻らなければキャプチャごと削除され、ファイルがまだあればそのまま残る
    """

    # 設定された保存先には、普段どおりに画像が見えている状態にする
    ## 保存先に画像が1枚も見えないときは、マウントが外れている可能性があるため、すべての保存先で期限による削除が見送られる
    file_name = 'Capture_20260826-044039.jpg'
    response = await client.post('/api/captures', files={'image': (file_name, (FIXTURES_DIR / 'captures' / file_name).read_bytes(), 'image/jpeg')})
    assert response.status_code == 201, response.text
    uploaded_capture = response.json()

    # 設定から外した保存先を再現するため、設定にないフォルダだけを一括スキャンして画像を登録する
    root = TEMP_DIR / 'removed-folder'
    root.mkdir()
    kept_name = 'Capture_20221003-224010.jpg'
    removed_name = 'Capture_20221219-001337.jpg'
    for file_name in (kept_name, removed_name):
        shutil.copyfile(FIXTURES_DIR / 'captures' / file_name, root / file_name)
    scanner = CaptureScanTask()
    await WaitUntil(lambda: scanner.scan_lock.locked() is False)
    assert await scanner.runBatchScan([str(root)]) is True
    kept_file = await CaptureFile.get(file_path=NormalizeCapturePath(root / kept_name))
    removed_file = await CaptureFile.get(file_path=NormalizeCapturePath(root / removed_name))

    # 1枚を消してから、設定されたすべての保存先を一括スキャンすると、消えた画像の行は Missing になり、ファイルがまだある画像の行はそのまま残る
    (root / removed_name).unlink()
    assert await scanner.runBatchScan() is True
    missing_file = await CaptureFile.get(id=removed_file.id)
    assert missing_file.status == 'Missing'
    assert missing_file.missing_since is not None
    assert (await CaptureFile.get(id=kept_file.id)).status == 'Available'

    # 1週間たつ前にファイルが同じ場所に戻れば (マウントが遅れたフォルダや、ごみ箱から戻した画像)、次の一括スキャンで利用できる状態に戻る
    shutil.copyfile(FIXTURES_DIR / 'captures' / removed_name, root / removed_name)
    shutil.copystat(FIXTURES_DIR / 'captures' / removed_name, root / removed_name)
    assert await scanner.runBatchScan() is True
    restored_file = await CaptureFile.get(id=removed_file.id)
    assert restored_file.status == 'Available'
    assert restored_file.missing_since is None

    # もう一度消してから一括スキャンすると、また Missing になる
    (root / removed_name).unlink()
    assert await scanner.runBatchScan() is True
    assert (await CaptureFile.get(id=removed_file.id)).status == 'Missing'

    # 見つからなくなってから1週間たったことにして一括スキャンすると、場所が残っていないキャプチャごと削除される
    await CaptureFile.filter(id=removed_file.id).update(missing_since=datetime.now(JST) - timedelta(days=8))
    assert await scanner.runBatchScan() is True
    assert await CaptureFile.filter(id=removed_file.id).exists() is False
    assert await Capture.filter(id=removed_file.capture_id).exists() is False
    assert (await CaptureFile.get(id=kept_file.id)).status == 'Available'

    # ほかのテストの一覧に混ざらないよう、残ったキャプチャを削除する
    response = await client.request(
        'DELETE',
        '/api/captures',
        json = {'capture_ids': [uploaded_capture['id'], kept_file.capture_id]},
        headers = admin_headers,
    )
    assert response.status_code == 200, response.text
    await WaitUntil(lambda: scanner.scan_lock.locked() is False)


# -------------------------------------------------------------------------------------
# 監視している保存先の中で画像を別のフォルダへ移すフロー
# (POST /api/captures → 保存先の画像の移動 → 保存先の監視) - 正常系
# -------------------------------------------------------------------------------------


async def test_watch__relinks_file_moved_within_capture_folder(client: httpx.AsyncClient, admin_headers: dict[str, str], capture_folder: Path) -> None:
    """
    監視している保存先の中で別のフォルダへ移した画像は、一括スキャンを待たずに同じ場所の行のまま新しいパスに付け替わる
    """

    # 移動先の子フォルダを先に作り、監視がその中の変化も通知するようになるまで待つ
    ## 作った直後に移すと、子フォルダの追加の通知から一括スキャンが始まり、監視の移動の照合を通らない
    (capture_folder / 'moved').mkdir()
    await asyncio.sleep(3)
    await WaitUntil(lambda: CaptureScanTask().scan_lock.locked() is False)

    # アップロードしたキャプチャの画像を、保存先の中の子フォルダへ移す
    file_name = 'Capture_20260826-044039.jpg'
    response = await client.post('/api/captures', files={'image': (file_name, (FIXTURES_DIR / 'captures' / file_name).read_bytes(), 'image/jpeg')})
    assert response.status_code == 201, response.text
    capture = response.json()
    uploaded_file = await CaptureFile.get(capture_id=capture['id'])
    moved_path = NormalizeCapturePath(capture_folder / 'moved' / file_name)
    Path(uploaded_file.file_path).rename(moved_path)

    # 監視の通知で、同じ行が新しいパスに付け替わり、場所の行は1つのまま増えない
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 30
    while (await CaptureFile.get(id=uploaded_file.id)).file_path != moved_path:
        assert loop.time() < deadline, 'Moved capture was not relinked within 30 seconds.'
        await asyncio.sleep(0.2)
    files = await CaptureFile.filter(capture_id=capture['id'])
    assert [(file.id, file.status) for file in files] == [(uploaded_file.id, 'Available')]

    # ほかのテストの一覧に混ざらないよう、アップロードしたキャプチャを削除する
    response = await client.request('DELETE', '/api/captures', json={'capture_ids': [capture['id']]}, headers=admin_headers)
    assert response.status_code == 200, response.text
    await WaitUntil(lambda: CaptureScanTask().scan_lock.locked() is False)
    (capture_folder / 'moved').rmdir()


# -------------------------------------------------------------------------------------
# Windows で大文字と小文字だけが異なるパスの場所が2つあるキャプチャを削除するフロー
# (大文字と小文字を区別しないパスの照合 → DELETE /api/captures) - 正常系
# -------------------------------------------------------------------------------------


async def test_delete_capture__with_paths_differing_only_in_case(
    client: httpx.AsyncClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Windows のように大文字と小文字を区別しないパスの照合で、同じキーになる場所が2つあるキャプチャも、
    同じロックを2回待たずに削除できる
    """

    # Windows と同じく、パスを小文字にしたものを同じファイルかどうかの判定に使う
    def LowerCasePathKey(path: str) -> str:
        return path.lower()
    monkeypatch.setattr('app.metadata.CaptureScanTask.CapturePathKey', LowerCasePathKey)

    # アップロードしたキャプチャに、名前の大文字と小文字だけを変えたパスの場所をもう1つ登録する
    file_name = 'Capture_20260826-044039.jpg'
    response = await client.post('/api/captures', files={'image': (file_name, (FIXTURES_DIR / 'captures' / file_name).read_bytes(), 'image/jpeg')})
    assert response.status_code == 201, response.text
    capture = response.json()
    uploaded_file = await CaptureFile.get(capture_id=capture['id'])
    renamed_path = str(Path(uploaded_file.file_path).with_name(file_name.lower()))
    await CaptureFile.create(
        capture_id = uploaded_file.capture_id,
        file_path = renamed_path,
        file_name = Path(renamed_path).name,
        file_size = uploaded_file.file_size,
        file_created_at = uploaded_file.file_created_at,
        file_modified_at = uploaded_file.file_modified_at,
        status = 'Available',
    )

    # 削除の API が応答し、キャプチャと2つの場所の行がどちらも削除される
    response = await asyncio.wait_for(
        client.request('DELETE', '/api/captures', json={'capture_ids': [capture['id']]}, headers=admin_headers),
        timeout = 10,
    )
    assert response.status_code == 200, response.text
    assert response.json() == {'deleted_capture_ids': [capture['id']], 'failed_capture_ids': []}
    assert await CaptureFile.filter(capture_id=capture['id']).exists() is False
    await WaitUntil(lambda: CaptureScanTask().scan_lock.locked() is False)
