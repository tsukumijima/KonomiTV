"""ライブ配信の入力待機とクライアント回収の E2E テスト。"""

import asyncio
import importlib
from collections.abc import AsyncGenerator
from types import SimpleNamespace

import httpx2 as httpx
import pytest
import pytest_asyncio

from app.streams.LiveEncodingTask import LiveEncodingTask
from app.streams.LiveStream import LiveStream, LiveStreamClient


@pytest_asyncio.fixture
async def live_stream(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[tuple[LiveStream, SimpleNamespace]]:
    """
    起動済みアプリケーションのライブ配信と、その配信だけが参照する時計を用意する

    Args:
        client (httpx.AsyncClient): 起動済みアプリケーションへの HTTP クライアント
        monkeypatch (pytest.MonkeyPatch): pytest の monkeypatch

    Returns:
        AsyncGenerator[tuple[LiveStream, SimpleNamespace]]: ライブ配信と時計
    """

    # テスト用 Mirakurun のチャンネルを使い、配信の時計だけを進められるようにする
    clock = SimpleNamespace(now=1000.0)
    module = importlib.import_module('app.streams.LiveStream')
    monkeypatch.setattr(module, 'time', SimpleNamespace(time=lambda: clock.now))
    stream = LiveStream('gr011', '1080p')
    assert stream.getStatus().status == 'Offline'
    assert stream.getStatus().client_count == 0
    yield stream, clock

    # 各テストで接続したクライアントと配信状態を解放する
    stream.disconnectAll()
    stream.setStatus('Offline', 'Test finished.')
    await asyncio.sleep(0)
    response = await client.get('/api/streams/live/gr011/1080p')
    assert response.json()['status'] == 'Offline'
    assert response.json()['client_count'] == 0


async def StartReading(stream_client: LiveStreamClient) -> asyncio.Task[bytes | None]:
    """
    クライアントが入力待機へ進んだ後で、読み取りタスクを返す

    Args:
        stream_client (LiveStreamClient): 接続済みのクライアント

    Returns:
        asyncio.Task[bytes | None]: 入力待機中の読み取りタスク
    """

    reading = asyncio.Event()

    # 通知の後は実際の読み取りが Queue で待機するまで同じタスク内で実行する
    async def Read() -> bytes | None:
        reading.set()
        return await stream_client.readStreamData()

    task = asyncio.create_task(Read())
    await reading.wait()
    return task


@pytest.mark.parametrize('input_delay', [0.1, 11.0, 60.0])
async def test_mpegts_api_delivers_data_after_input_wait(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    live_stream: tuple[LiveStream, SimpleNamespace],
    input_delay: float,
) -> None:
    """
    初回入力を待機中の HTTP クライアントへ、待機時間に関わらず最初のデータを配信する

    Args:
        client (httpx.AsyncClient): 起動済みアプリケーションへの HTTP クライアント
        monkeypatch (pytest.MonkeyPatch): pytest の monkeypatch
        live_stream (tuple[LiveStream, SimpleNamespace]): ライブ配信と時計
        input_delay (float): 最初の入力までに進める秒数
    """

    stream, clock = live_stream
    reading = asyncio.Event()
    readers: list[LiveStreamClient] = []
    original_read = LiveStreamClient.readStreamData
    payload = b'first stream data'

    # HTTP API が実際の Queue 読み取りを開始したタイミングを記録する
    async def ReadStreamData(stream_client: LiveStreamClient) -> bytes | None:
        readers.append(stream_client)
        reading.set()
        return await original_read(stream_client)
    monkeypatch.setattr(LiveStreamClient, 'readStreamData', ReadStreamData)

    # 外部エンコーダーの入力到着だけを置き換え、配信 API と Queue は実装をそのまま通す
    async def Run(encoding_task: LiveEncodingTask) -> None:
        await asyncio.wait_for(reading.wait(), timeout=3)
        clock.now += input_delay
        encoding_task.live_stream.setStatus('ONAir', 'Test stream is on air.')
        encoding_task.live_stream.writeStreamData(payload)
        for stream_client in readers:
            stream_client.writeStreamData(None)
    monkeypatch.setattr(LiveEncodingTask, 'run', Run)

    response = await asyncio.wait_for(client.get('/api/streams/live/gr011/1080p/mpegts'), timeout=3)
    assert response.status_code == 200
    assert response.content == payload
    assert stream.getStatus().client_count == 0


async def test_stopped_consumer_is_collected(
    client: httpx.AsyncClient,
    live_stream: tuple[LiveStream, SimpleNamespace],
) -> None:
    """
    読み取りを開始していないクライアントは従来どおりタイムアウトで回収する

    Args:
        client (httpx.AsyncClient): 起動済みアプリケーションへの HTTP クライアント
        live_stream (tuple[LiveStream, SimpleNamespace]): ライブ配信と時計
    """

    stream, clock = live_stream
    stream.setStatus('ONAir', 'Test stream is on air.')
    await stream.connect('mpegts')
    response = await client.get('/api/streams/live/gr011/1080p')
    assert response.json()['client_count'] == 1
    clock.now += 11
    stream.writeStreamData(b'new stream data')

    response = await client.get('/api/streams/live/gr011/1080p')
    assert response.status_code == 200
    assert response.json()['client_count'] == 0


async def test_completed_read_refreshes_consumer_timeout(
    live_stream: tuple[LiveStream, SimpleNamespace],
) -> None:
    """
    長い入力待機の直後は、読み取り完了から10秒間クライアントを維持する

    Args:
        live_stream (tuple[LiveStream, SimpleNamespace]): ライブ配信と時計
    """

    stream, clock = live_stream
    stream.setStatus('ONAir', 'Test stream is on air.')
    stream_client = await stream.connect('mpegts')
    read = await StartReading(stream_client)
    clock.now += 11
    stream.writeStreamData(b'first stream data')
    # 元実装でも待機を終了できるよう終端を入れ、応答の内容で回帰を判定する
    stream_client.writeStreamData(None)
    assert await asyncio.wait_for(read, timeout=3) == b'first stream data'

    clock.now += 2
    stream.writeStreamData(b'second stream data')
    assert stream.getStatus().client_count == 1
    clock.now += 9
    stream.writeStreamData(b'third stream data')
    assert stream.getStatus().client_count == 0


async def test_cancelled_read_can_be_collected(
    live_stream: tuple[LiveStream, SimpleNamespace],
) -> None:
    """
    読み取りをキャンセルしたクライアントは、消費が止まればタイムアウトで回収する

    Args:
        live_stream (tuple[LiveStream, SimpleNamespace]): ライブ配信と時計
    """

    stream, clock = live_stream
    stream.setStatus('ONAir', 'Test stream is on air.')
    stream_client = await stream.connect('mpegts')
    read = await StartReading(stream_client)
    read.cancel()
    with pytest.raises(asyncio.CancelledError):
        await read
    clock.now += 11
    stream.writeStreamData(b'new stream data')
    assert stream.getStatus().client_count == 0
