"""ライブ視聴の配信 (LiveStream / LiveEncodingTask) の E2E テスト。"""

import asyncio
from collections.abc import AsyncGenerator

import httpx2 as httpx
import pytest_asyncio

from app.models.Channel import Channel
from app.streams.LiveStream import LiveStream, LiveStreamClient
from tests.conftest import FAKE_MIRAKURUN, FIXTURES_DIR


# 偽の Mirakurun からライブ視聴の放送波として送信する TS
## 偽の Mirakurun のサービスにある NHK総合1・東京 (NID 32736・SID 1024) の録画を使う
STREAM_TS_PATH = FIXTURES_DIR / 'recorded' / 'terrestrial-tsreplace-h264.ts'

# ストリームデータを読み取らなくなったクライアントを削除するまでの秒数
## LiveStream.writeStreamData() のタイムアウト秒数と同じ値
CLIENT_TIMEOUT = 10


@pytest_asyncio.fixture(loop_scope='session')
async def live_stream(client: httpx.AsyncClient) -> AsyncGenerator[LiveStream]:
    """
    偽の Mirakurun から放送波を受信する NHK総合1・東京のライブストリームを返し、テストの終了後にエンコードタスクを終了させる
    チャンネル情報はサーバーの起動時に偽の Mirakurun から取得されるため、client フィクスチャでサーバーを起動しておく

    Args:
        client (httpx.AsyncClient): アプリケーションへの HTTP クライアント

    Returns:
        AsyncGenerator[LiveStream]: 画質が 240p のライブストリーム
    """

    channel = await Channel.get(network_id=32736, service_id=1024)
    FAKE_MIRAKURUN.stream_ts_path = STREAM_TS_PATH
    live_stream = LiveStream(channel.display_channel_id, '240p')
    try:
        yield live_stream
    finally:
        # サーバーの終了時と同じくライブストリームを Offline にして、エンコードタスクとエンコーダーを終了させる
        live_stream.setStatus('Offline', 'ライブストリームは Offline です。', True)

        # エンコードタスクが偽の Mirakurun との接続を閉じ、放送波の受信を終えるまで待つ
        for _ in range(100):
            if FAKE_MIRAKURUN.open_stream_count == 0:
                break
            await asyncio.sleep(0.1)
        assert FAKE_MIRAKURUN.open_stream_count == 0
        FAKE_MIRAKURUN.stream_ts_path = None
        FAKE_MIRAKURUN.stream_start_delay = 0.0


async def test_live_stream__keeps_client_waiting_for_slow_tuner(live_stream: LiveStream) -> None:
    """
    チューナーの起動に 10 秒以上かかり、最初のストリームデータが届くまで待機している間も、視聴を始めたクライアントを削除しない
    待機を始めた時刻を最終読み取り時刻として扱うと、最初のストリームデータを書き込んだ時点でタイムアウトと判断されて削除され、
    クライアントは最初の接続で映像を受け取れなくなる
    """

    # チューナーの起動に時間がかかる環境を再現し、タイムアウトの秒数を超えてから放送波の送信を始める
    FAKE_MIRAKURUN.stream_start_delay = CLIENT_TIMEOUT + 1

    live_stream_client = await live_stream.connect('mpegts')
    try:
        stream_data = await asyncio.wait_for(live_stream_client.readStreamData(), timeout=CLIENT_TIMEOUT + 20)

        # エンコーダーが出力した TS を受け取り、クライアントが接続されたままになっている
        assert stream_data is not None
        assert stream_data[:1] == b'\x47'
        assert live_stream.getStatus().client_count == 1
    finally:
        live_stream.disconnect(live_stream_client)


async def test_live_stream__disconnects_client_that_stops_reading(live_stream: LiveStream) -> None:
    """
    ネットワークの切断などで送信先がストリームデータを受け取らなくなったクライアントは、10 秒後に削除して接続の切断を通知する
    同じライブストリームを視聴しているほかのクライアントには、引き続きストリームデータを書き込む
    """

    # 先に接続したクライアントの読み取りを止め、後に接続したクライアントは読み取りを続ける
    stalled_client = await live_stream.connect('mpegts')
    viewing_client = await live_stream.connect('mpegts')
    viewing_client_received_bytes = 0

    async def KeepReading() -> None:
        nonlocal viewing_client_received_bytes
        while True:
            stream_data = await viewing_client.readStreamData()
            if stream_data is None:
                return
            viewing_client_received_bytes += len(stream_data)

    viewing_task = asyncio.create_task(KeepReading())
    try:
        # 最初のストリームデータを受け取った後は、タイムアウトの秒数を超えるまで読み取らない
        stream_data = await asyncio.wait_for(stalled_client.readStreamData(), timeout=30)
        assert stream_data is not None
        await asyncio.sleep(CLIENT_TIMEOUT + 2)

        # 読み取りを止めたクライアントだけが削除されている
        assert live_stream.getStatus().client_count == 1

        # 削除されたクライアントは、溜まっていたストリームデータを読み終えると、接続の切断 (None) を受け取る
        async def ReadUntilDisconnected() -> None:
            while (await stalled_client.readStreamData()) is not None:
                pass
        await asyncio.wait_for(ReadUntilDisconnected(), timeout=5)

        # 読み取りを続けているクライアントは、引き続きストリームデータを受け取っている
        received_bytes = viewing_client_received_bytes
        await asyncio.sleep(1)
        assert viewing_task.done() is False
        assert viewing_client_received_bytes > received_bytes
    finally:
        viewing_task.cancel()
        live_stream.disconnect(stalled_client)
        live_stream.disconnect(viewing_client)


async def test_live_stream__notifies_all_clients_when_stream_goes_offline(live_stream: LiveStream) -> None:
    """
    ライブストリームが Offline になってエンコードタスクが終了したときは、視聴しているすべてのクライアントに接続の切断を通知する
    """

    # 2台のクライアントが、どちらもストリームデータを受け取れる状態にする
    live_stream_clients = [
        await live_stream.connect('mpegts'),
        await live_stream.connect('mpegts'),
    ]

    async def ReadUntilDisconnected(live_stream_client: LiveStreamClient) -> None:
        while (await live_stream_client.readStreamData()) is not None:
            pass

    try:
        for live_stream_client in live_stream_clients:
            stream_data = await asyncio.wait_for(live_stream_client.readStreamData(), timeout=30)
            assert stream_data is not None

        # サーバーの終了時と同じくライブストリームを Offline にすると、エンコードタスクが終了してすべてのクライアントを切断する
        live_stream.setStatus('Offline', 'ライブストリームは Offline です。', True)

        # どちらのクライアントも、溜まっていたストリームデータを読み終えると、接続の切断 (None) を受け取る
        for live_stream_client in live_stream_clients:
            await asyncio.wait_for(ReadUntilDisconnected(live_stream_client), timeout=10)
        assert live_stream.getStatus().client_count == 0
    finally:
        for live_stream_client in live_stream_clients:
            live_stream.disconnect(live_stream_client)
