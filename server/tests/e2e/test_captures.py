"""キャプチャ関連 API の E2E テスト。"""

import hashlib
from pathlib import Path

import httpx2 as httpx

from tests.conftest import FIXTURES_DIR


# =====================================================================================
# API 単体 E2E テスト
# ルーターの API 定義順に並べる
# 各 API について 正常系 → 異常系 の順番でテストを並べる
# =====================================================================================

# -------------------------------------------------------------------------------------
# POST /api/captures (CaptureUploadAPI) - 異常系
# -------------------------------------------------------------------------------------

async def test_upload_capture__rejects_non_image_file(client: httpx.AsyncClient, capture_folder: Path) -> None:
    """
    画像として読めないファイルはキャプチャとして受け付けず、保存先フォルダにも残さない
    """

    response = await client.post('/api/captures', files={'image': ('Capture_20260101-000000.jpg', b'not an image', 'image/jpeg')})
    assert response.status_code == 422, response.text
    assert list(capture_folder.iterdir()) == []


# =====================================================================================
# 複合 E2E テスト
# 複数の API が絡むフローのテスト
# =====================================================================================

# -------------------------------------------------------------------------------------
# キャプチャアップロード・反映・削除フロー (POST /api/captures → GET /api/captures → DELETE /api/captures) - 正常系
# -------------------------------------------------------------------------------------


async def test_upload_list_and_delete_capture(client: httpx.AsyncClient, admin_headers: dict[str, str], capture_folder: Path) -> None:
    """
    アップロードしたキャプチャが保存先フォルダに保存されて一覧と詳細に現れ、
    同じ内容のアップロードは同じキャプチャを返し、管理者が削除するとファイルごと消える
    """

    file_name = 'Capture_20260826-044039.jpg'
    data = (FIXTURES_DIR / 'captures' / file_name).read_bytes()
    file_hash = hashlib.sha256(data).hexdigest()

    # キャプチャをアップロードする
    response = await client.post('/api/captures', files={'image': (file_name, data, 'image/jpeg')})
    assert response.status_code == 201, response.text
    capture = response.json()
    assert capture['file_hash'] == file_hash
    assert capture['metadata_status'] == 'Parsed'
    assert capture['captured_at'] == '2026-08-26T04:40:39+09:00'
    assert capture['playback_position'] == 639.734

    # 同じ内容をもう一度アップロードすると、保存し直さずに同じキャプチャを返す
    response = await client.post('/api/captures', files={'image': (file_name, data, 'image/jpeg')})
    assert response.status_code == 201, response.text
    assert response.json()['id'] == capture['id']

    # 一覧に現れ、撮影した放送回の番組情報も一緒に返る
    response = await client.get('/api/captures')
    assert response.status_code == 200, response.text
    captures = response.json()
    assert [item['id'] for item in captures['captures']] == [capture['id']]
    assert [program['title'] for program in captures['programs']] == ['Oha！4 ▽中野ブロードウェイ時計店で窃盗 被害総額2億円相当']

    # 詳細には保存先フォルダに置かれたファイルが1つだけある
    response = await client.get(f'/api/captures/{capture["id"]}')
    assert response.status_code == 200, response.text
    files = response.json()['files']
    assert len(files) == 1
    saved_path = Path(files[0]['file_path'])
    assert saved_path.parent == capture_folder
    assert saved_path.read_bytes() == data

    # 画像の API はアップロードした内容をそのまま返す
    response = await client.get(f'/api/captures/{capture["id"]}/image', params={'hash': file_hash})
    assert response.status_code == 200
    assert response.content == data

    # ログインしていなければ削除できない
    response = await client.request('DELETE', '/api/captures', json={'capture_ids': [capture['id']]})
    assert response.status_code == 401, response.text
    assert saved_path.exists()

    # 管理者は実体のファイルごと削除できる
    response = await client.request('DELETE', '/api/captures', json={'capture_ids': [capture['id']]}, headers=admin_headers)
    assert response.status_code == 200, response.text
    assert response.json() == {'deleted_capture_ids': [capture['id']], 'failed_capture_ids': []}
    assert saved_path.exists() is False
    response = await client.get(f'/api/captures/{capture["id"]}')
    assert response.status_code == 404


# -------------------------------------------------------------------------------------
# 放送時間未定の放送回の補完フロー (POST /api/captures → GET /api/captures/{capture_id} → DELETE /api/captures) - 正常系
# -------------------------------------------------------------------------------------

async def test_upload_capture_of_program_with_undecided_duration_then_fill_in(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    """
    放送時間未定の番組で撮ったキャプチャは、終了時刻と番組長が不明な放送回として登録され、
    同じ放送回を長さが決まってから撮ったキャプチャが来ると、放送回の終了時刻と長さが埋まる
    """

    # 放送時間未定のときに撮ったキャプチャをアップロードすると、終了時刻と長さが null の放送回になる
    file_name = 'Capture_20251013-141201.jpg'
    response = await client.post('/api/captures', files={'image': (file_name, (FIXTURES_DIR / 'captures' / file_name).read_bytes(), 'image/jpeg')})
    assert response.status_code == 201, response.text
    undecided_capture = response.json()
    assert undecided_capture['metadata_status'] == 'Parsed'
    response = await client.get(f'/api/captures/{undecided_capture["id"]}')
    assert response.status_code == 200, response.text
    program = response.json()['program']
    assert program['start_time'] == '2025-10-13T13:55:00+09:00'
    assert program['end_time'] is None
    assert program['duration'] is None

    # 同じ放送回を、長さが決まってから撮ったキャプチャをアップロードすると、放送回の終了時刻と長さが埋まる
    file_name = 'Capture_20251013-150401.jpg'
    response = await client.post('/api/captures', files={'image': (file_name, (FIXTURES_DIR / 'captures' / file_name).read_bytes(), 'image/jpeg')})
    assert response.status_code == 201, response.text
    decided_capture = response.json()
    response = await client.get(f'/api/captures/{undecided_capture["id"]}')
    assert response.status_code == 200, response.text
    filled_program = response.json()['program']
    assert filled_program['id'] == program['id']
    assert filled_program['end_time'] == '2025-10-13T15:15:00+09:00'
    assert filled_program['duration'] == 4800

    # ほかのテストの一覧に混ざらないよう、アップロードしたキャプチャを削除する
    response = await client.request('DELETE', '/api/captures', json={'capture_ids': [undecided_capture['id'], decided_capture['id']]}, headers=admin_headers)
    assert response.status_code == 200, response.text
