"""録画番組のストリーミング配信に関連する API の E2E テスト。"""


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

from app.constants import JST
from app.streams.VideoStream import VideoStream
from tests.conftest import FIXTURES_DIR, RECORDED_FOLDER


# ストリーミングのテストで使う録画ファイル
## 60 秒以上あり、録画フォルダのスキャンで録画番組として登録される TS ファイルを使う
STREAMING_FIXTURE_FILE_NAME = 'terrestrial-tsreplace-h264.ts'

# ストリーミングのテストで使う録画ファイルの更新日時
## 録画の移動の照合 (サイズが同じで更新日時が前後2秒の範囲にあるレコードが候補になる) に巻き込まれないよう、録画スキャンのテストで使われていない日時を指定する
STREAMING_FIXTURE_RECORDED_AT = datetime(2019, 8, 20, 20, 45, tzinfo=JST)

# セグメントのエンコードを待つリクエストのタイムアウト (秒)
## エンコードにかかる時間は CPU の状態によって変わるため、既定のタイムアウトでは足りない
SEGMENT_REQUEST_TIMEOUT = 120.0


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


async def EnsureStreamingRecording(client: httpx.AsyncClient, recorded_folder: Path) -> dict[str, Any]:
    """
    ストリーミングのテストで使う録画ファイルを録画フォルダに置き、録画番組として登録されるまで待つ
    同じ録画フォルダを使うテストから繰り返し呼ばれても、置くファイルと登録される録画番組は1つだけになる

    Args:
        client (httpx.AsyncClient): テスト用のサーバーにつないだクライアント
        recorded_folder (Path): 録画フォルダのパス

    Returns:
        dict[str, Any]: 登録された録画番組
    """

    # 起動時の一括スキャンが終わってから録画を置き、録画フォルダの監視で見つかる経路を通す
    await WaitForStartupScan(client)

    # このファイルで最初に呼ばれたときだけ録画を置き、以降のテストは登録済みの録画番組を使い回す
    recorded_path = recorded_folder / 'streaming' / STREAMING_FIXTURE_FILE_NAME
    if await anyio.Path(recorded_path).exists() is False:
        # 録画ファイルのコピーでイベントループを塞がないよう、別スレッドで置く
        await asyncio.to_thread(
            PlaceRecording,
            STREAMING_FIXTURE_FILE_NAME,
            recorded_folder / 'streaming',
            STREAMING_FIXTURE_RECORDED_AT,
        )

    # 監視で見つかり、番組情報を解析して登録されるまで待つ
    return await WaitUntil(lambda: GetRecordedProgramByPath(client, recorded_path))


# =====================================================================================
# API 単体 E2E テスト
# ルーターの API 定義順に並べる
# 各 API について 正常系 → 異常系 の順番でテストを並べる
# =====================================================================================


# -------------------------------------------------------------------------------------
# GET /api/streams/video/{video_id}/{quality}/playlist (VideoHLSPlaylistAPI) - 正常系
# -------------------------------------------------------------------------------------


async def test_playlist__creates_session_and_returns_virtual_playlist(client: httpx.AsyncClient, recorded_folder: Path) -> None:
    """
    プレイリスト API を呼ぶと録画視聴セッションが作られ、セグメントを列挙した仮想プレイリストが返る
    """

    recorded_program = await EnsureStreamingRecording(client, recorded_folder)
    session_id = 'e2e-playlist'

    response = await client.get(
        f'/api/streams/video/{recorded_program["id"]}/1080p/playlist',
        params = {'session_id': session_id},
    )
    assert response.status_code == 200, response.text
    assert response.headers['Content-Type'] == 'application/vnd.apple.mpegurl'
    assert response.headers['Cache-Control'] == 'max-age=0'

    # 仮想プレイリストには、セッション ID 付きのセグメントがすべて列挙される
    playlist = response.text
    assert playlist.startswith('#EXTM3U')
    assert '#EXT-X-PLAYLIST-TYPE:VOD' in playlist
    assert f'segment?session_id={session_id}' in playlist
    assert playlist.count('#EXTINF:') >= 10
    assert playlist.endswith('#EXT-X-ENDLIST\n')


async def test_playlist__master_type_returns_master_playlist(client: httpx.AsyncClient, recorded_folder: Path) -> None:
    """
    type=master を指定すると、主音声と副音声の選択肢を持つマスタープレイリストが返る
    """

    recorded_program = await EnsureStreamingRecording(client, recorded_folder)
    session_id = 'e2e-playlist-master'

    response = await client.get(
        f'/api/streams/video/{recorded_program["id"]}/1080p/playlist',
        params = {'session_id': session_id, 'type': 'master'},
    )
    assert response.status_code == 200, response.text
    assert response.headers['Content-Type'] == 'application/vnd.apple.mpegurl'

    # 主音声と副音声の2つの音声トラックと、メディアプレイリストへの参照が列挙される
    playlist = response.text
    assert playlist.count('#EXT-X-MEDIA:TYPE=AUDIO') == 2
    assert '#EXT-X-STREAM-INF' in playlist
    assert f'playlist?session_id={session_id}&type=primary-audio' in playlist


# -------------------------------------------------------------------------------------
# GET /api/streams/video/{video_id}/{quality}/playlist (VideoHLSPlaylistAPI) - 異常系
# -------------------------------------------------------------------------------------


async def test_playlist__unknown_video_id_is_rejected(client: httpx.AsyncClient) -> None:
    """
    存在しない録画番組の ID を指定すると 422 が返る
    """

    response = await client.get(
        '/api/streams/video/999999/1080p/playlist',
        params = {'session_id': 'e2e-playlist-invalid-video'},
    )
    assert response.status_code == 422
    assert response.json()['detail'] == 'Specified video_id was not found'


async def test_playlist__unknown_quality_is_rejected(client: httpx.AsyncClient, recorded_folder: Path) -> None:
    """
    存在しない品質を指定すると 422 が返る
    """

    recorded_program = await EnsureStreamingRecording(client, recorded_folder)
    response = await client.get(
        f'/api/streams/video/{recorded_program["id"]}/999p/playlist',
        params = {'session_id': 'e2e-playlist-invalid-quality'},
    )
    assert response.status_code == 422
    assert response.json()['detail'] == 'Specified quality was not found'


async def test_playlist__original_quality_is_rejected(client: httpx.AsyncClient, recorded_folder: Path) -> None:
    """
    録画番組の HLS プレイリストでは、ライブ配信専用の original 品質を指定できない (422 が返る)
    """

    recorded_program = await EnsureStreamingRecording(client, recorded_folder)
    response = await client.get(
        f'/api/streams/video/{recorded_program["id"]}/original/playlist',
        params = {'session_id': 'e2e-playlist-original-quality'},
    )
    assert response.status_code == 422
    assert response.json()['detail'] == 'Original quality is not available for HLS playlist'


# -------------------------------------------------------------------------------------
# GET /api/streams/video/{video_id}/{quality}/segment (VideoHLSSegmentAPI) - 正常系
# -------------------------------------------------------------------------------------


async def test_segment__returns_encoded_segment_data(client: httpx.AsyncClient, recorded_folder: Path) -> None:
    """
    プレイリストでセッションを作った後、セグメント API は要求されたセグメントをエンコードして MPEG-TS で返す
    同じセグメントをもう一度要求すると、エンコード済みの同じデータが返る
    """

    recorded_program = await EnsureStreamingRecording(client, recorded_folder)
    session_id = 'e2e-segment'
    base_url = f'/api/streams/video/{recorded_program["id"]}/1080p'

    response = await client.get(f'{base_url}/playlist', params = {'session_id': session_id})
    assert response.status_code == 200, response.text

    response = await client.get(
        f'{base_url}/segment',
        params = {'session_id': session_id, 'sequence': 0, 'cache_key': 'e2e-segment'},
        timeout = SEGMENT_REQUEST_TIMEOUT,
    )
    assert response.status_code == 200, response.text
    assert response.headers['Content-Type'] == 'video/mp2t'
    assert response.headers['Cache-Control'] == 'max-age=10800'
    assert len(response.content) > 0
    # MPEG-TS のデータは、188 バイトのパケットの同期バイト (0x47) から始まる
    assert response.content[0] == 0x47
    first_segment_data = response.content

    response = await client.get(
        f'{base_url}/segment',
        params = {'session_id': session_id, 'sequence': 0, 'cache_key': 'e2e-segment-again'},
        timeout = SEGMENT_REQUEST_TIMEOUT,
    )
    assert response.status_code == 200, response.text
    assert response.content == first_segment_data


# -------------------------------------------------------------------------------------
# GET /api/streams/video/{video_id}/{quality}/segment (VideoHLSSegmentAPI) - 異常系
# -------------------------------------------------------------------------------------


async def test_segment__unknown_sequence_is_rejected(client: httpx.AsyncClient, recorded_folder: Path) -> None:
    """
    存在しないシーケンス番号のセグメントを要求すると 422 が返る
    """

    recorded_program = await EnsureStreamingRecording(client, recorded_folder)
    session_id = 'e2e-segment-invalid-sequence'

    response = await client.get(
        f'/api/streams/video/{recorded_program["id"]}/1080p/segment',
        params = {'session_id': session_id, 'sequence': 9999, 'cache_key': 'e2e-segment-invalid-sequence'},
    )
    assert response.status_code == 422
    assert response.json()['detail'] == 'Specified sequence segment was not found'


# -------------------------------------------------------------------------------------
# PUT /api/streams/video/{video_id}/{quality}/keep-alive (VideoHLSKeepAliveAPI) - 正常系
# -------------------------------------------------------------------------------------


async def test_keep_alive__returns_no_content(client: httpx.AsyncClient, recorded_folder: Path) -> None:
    """
    セッションがある場合も、プレイリストを経由せずに Keep-Alive からセッションが作られる場合も、204 が返る
    """

    recorded_program = await EnsureStreamingRecording(client, recorded_folder)
    base_url = f'/api/streams/video/{recorded_program["id"]}/1080p'

    # プレイリストでセッションを作ってから Keep-Alive を送る
    response = await client.get(f'{base_url}/playlist', params = {'session_id': 'e2e-keep-alive'})
    assert response.status_code == 200, response.text
    response = await client.put(f'{base_url}/keep-alive', params = {'session_id': 'e2e-keep-alive'})
    assert response.status_code == 204
    assert response.content == b''

    # プレイリストを経由せずに Keep-Alive だけを送っても、セッションが作られて 204 が返る
    response = await client.put(f'{base_url}/keep-alive', params = {'session_id': 'e2e-keep-alive-only'})
    assert response.status_code == 204


async def test_keep_alive__recreates_session_after_timeout(
    client: httpx.AsyncClient,
    recorded_folder: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    最後のリクエストから SESSION_TIMEOUT を超えて放置されセッションが破棄された後も、Keep-Alive を送るとセッションが作り直されて 204 が返る
    破棄まで待つ時間を抑えるため、このテストで作られるセッションだけ SESSION_TIMEOUT を短い値に差し替える
    """

    recorded_program = await EnsureStreamingRecording(client, recorded_folder)

    # セッションの生存期限を短くして、破棄を待つ時間を抑える
    monkeypatch.setattr(VideoStream, 'SESSION_TIMEOUT', 2.0)
    session_id = 'e2e-keep-alive-timeout'
    base_url = f'/api/streams/video/{recorded_program["id"]}/1080p'

    response = await client.get(f'{base_url}/playlist', params = {'session_id': session_id})
    assert response.status_code == 200, response.text

    # 最後のリクエストから SESSION_TIMEOUT を超えて放置し、セッションが破棄されるのを待つ
    await asyncio.sleep(VideoStream.SESSION_TIMEOUT + 2)

    # 破棄された後でも、同じ session_id で Keep-Alive を送るとセッションが作り直されて 204 が返る
    response = await client.put(f'{base_url}/keep-alive', params = {'session_id': session_id})
    assert response.status_code == 204


# =====================================================================================
# 複合 E2E テスト
# 複数の API が絡むフローのテスト
# =====================================================================================


# -------------------------------------------------------------------------------------
# 同じ session ID を別の条件で使い回すのを拒否するフロー
# (GET .../playlist → GET .../playlist) - 異常系
# -------------------------------------------------------------------------------------


async def test_session_reuse__quality_mismatch_is_rejected(client: httpx.AsyncClient, recorded_folder: Path) -> None:
    """
    同じ session_id で異なる画質を要求すると、別のストリームにセッションが混ざらないよう 422 で拒否される
    """

    recorded_program = await EnsureStreamingRecording(client, recorded_folder)
    session_id = 'e2e-session-mismatch-quality'
    base_url = f'/api/streams/video/{recorded_program["id"]}'

    response = await client.get(f'{base_url}/1080p/playlist', params = {'session_id': session_id})
    assert response.status_code == 200, response.text

    response = await client.get(f'{base_url}/720p/playlist', params = {'session_id': session_id})
    assert response.status_code == 422
    assert response.json()['detail'] == 'Session exists but program_id or quality mismatch'


async def test_session_reuse__encoding_options_mismatch_is_rejected(client: httpx.AsyncClient, recorded_folder: Path) -> None:
    """
    同じ session_id で同じ画質でも異なるエンコードオプション (-24fps など) を要求すると、422 で拒否される
    """

    recorded_program = await EnsureStreamingRecording(client, recorded_folder)
    session_id = 'e2e-session-mismatch-options'
    base_url = f'/api/streams/video/{recorded_program["id"]}'

    response = await client.get(f'{base_url}/1080p/playlist', params = {'session_id': session_id})
    assert response.status_code == 200, response.text

    response = await client.get(f'{base_url}/1080p-24fps/playlist', params = {'session_id': session_id})
    assert response.status_code == 422
    assert response.json()['detail'] == 'Session exists but encoding options mismatch'


# -------------------------------------------------------------------------------------
# セッションが破棄された後も、同じ session_id の要求からセッションが作り直されて再生が続くフロー
# (GET .../playlist → GET .../segment → SESSION_TIMEOUT 経過 → GET .../segment → PUT .../keep-alive) - 正常系
# -------------------------------------------------------------------------------------


async def test_session_lifecycle__playback_continues_after_session_is_discarded(
    client: httpx.AsyncClient,
    recorded_folder: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    最後のリクエストから SESSION_TIMEOUT を超えて放置されてセッションが破棄されても、
    プレイヤーがプレイリストを取り直さずに同じ session_id で次のセグメントを要求すると、セッションが作り直されて再生が続く
    破棄まで待つ時間を抑えるため、このテストで作られるセッションだけ SESSION_TIMEOUT を短い値に差し替える
    """

    recorded_program = await EnsureStreamingRecording(client, recorded_folder)
    session_id = 'e2e-session-lifecycle'
    base_url = f'/api/streams/video/{recorded_program["id"]}/1080p'

    # プレイリストでセッションを作り、最初のセグメントを取得して再生を始める
    response = await client.get(f'{base_url}/playlist', params = {'session_id': session_id})
    assert response.status_code == 200, response.text
    response = await client.get(
        f'{base_url}/segment',
        params = {'session_id': session_id, 'sequence': 0, 'cache_key': 'e2e-session-lifecycle'},
        timeout = SEGMENT_REQUEST_TIMEOUT,
    )
    assert response.status_code == 200, response.text
    assert len(response.content) > 0
    assert response.content[0] == 0x47

    # 破棄を待つ時間を抑えるため、タイムアウトを一時的に短くした状態で Keep-Alive を送り、タイマーを更新してから破棄されるのを待つ
    ## 次のセグメントのエンコード中に破棄されないよう、セグメントを要求する前にタイムアウトを元の値に戻す
    with monkeypatch.context() as timeout_patch:
        timeout_patch.setattr(VideoStream, 'SESSION_TIMEOUT', 2.0)
        response = await client.put(f'{base_url}/keep-alive', params = {'session_id': session_id})
        assert response.status_code == 204
        await asyncio.sleep(VideoStream.SESSION_TIMEOUT + 2)

    # プレイリストを取り直さずに次のセグメントを要求しても、セッションが作り直されて再生が続く
    response = await client.get(
        f'{base_url}/segment',
        params = {'session_id': session_id, 'sequence': 1, 'cache_key': 'e2e-session-lifecycle'},
        timeout = SEGMENT_REQUEST_TIMEOUT,
    )
    assert response.status_code == 200, response.text
    assert len(response.content) > 0
    assert response.content[0] == 0x47

    # 作り直されたセッションはそのまま生きていて、Keep-Alive も通る
    response = await client.put(f'{base_url}/keep-alive', params = {'session_id': session_id})
    assert response.status_code == 204
