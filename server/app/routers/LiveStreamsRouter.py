
import asyncio
import copy
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.requests import Request
from fastapi.responses import Response, StreamingResponse
from sse_starlette.sse import EventSourceResponse
from starlette.types import Receive

from app import logging, schemas
from app.constants import QUALITY, QUALITY_TYPES
from app.models.Channel import Channel
from app.streams.LiveStream import LiveStream, LiveStreamStatus


# ルーター
router = APIRouter(
    tags = ['Streams'],
    prefix = '/api/streams/live',
)


async def ValidateChannelID(display_channel_id: Annotated[str, Path(description='チャンネル ID 。ex: gr011')]) -> str:
    """ チャンネル ID のバリデーション """

    # チャンネル ID が存在するか確認
    if await Channel.filter(display_channel_id=display_channel_id).get_or_none() is None:
        logging.error(f'[LiveStreamsRouter][ValidateChannelID] Specified display_channel_id was not found. [display_channel_id: {display_channel_id}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified display_channel_id was not found',
        )

    return display_channel_id


async def ValidateQuality(quality: Annotated[str, Path(description='映像の品質。ex: 1080p')]) -> QUALITY_TYPES:
    """ 映像の品質のバリデーション """

    # 指定された品質が存在するか確認
    if quality not in QUALITY:
        logging.error(f'[LiveStreamsRouter][ValidateQuality] Specified quality was not found. [quality: {quality}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified quality was not found',
        )

    return quality


@router.get(
    '',
    summary = 'ライブストリーム一覧 API',
    response_description = 'ステータスごとに分類された、すべてのライブストリームの状態。',
    response_model = schemas.LiveStreamStatuses,
)
async def LiveStreamsAPI():
    """
    すべてのライブストリームの状態を Offline・Standby・ONAir・Idling・Restart の各ステータスごとに取得する。
    """

    # 返却するデータ
    # 逆順になっているのは、デバッグ時に全体の大半を占める Offline なストリームが邪魔なため
    result: dict[str, dict[str, LiveStreamStatus]] = {
        'Restart': {},
        'Idling' : {},
        'ONAir'  : {},
        'Standby': {},
        'Offline': {},
    }

    # すべてのストリームごとに
    for live_stream in LiveStream.getAllLiveStreams():
        live_stream_status = live_stream.getStatus()
        result[live_stream_status.status][live_stream.live_stream_id] = live_stream_status

    # すべてのライブストリームの状態を返す
    return result


@router.get(
    '/{display_channel_id}/{quality}',
    summary = 'ライブストリーム API',
    response_description = 'ライブストリームの状態。',
    response_model = schemas.LiveStreamStatus,
)
async def LiveStreamAPI(
    display_channel_id: Annotated[str, Depends(ValidateChannelID)],
    quality: Annotated[QUALITY_TYPES, Depends(ValidateQuality)],
):
    """
    ライブストリームの状態を取得する。<br>
    ライブストリーム イベント API にて配信されるイベントと同一のデータだが、一回限りの取得である点が異なる。
    """

    # ライブストリームを取得
    # ステータスを取得したいだけなので、接続はしない
    live_stream = LiveStream(display_channel_id, quality)

    # 取得してきた値をそのまま返す
    return live_stream.getStatus()


@router.get(
    '/{display_channel_id}/{quality}/events',
    summary = 'ライブストリーム イベント API',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'ライブストリームのイベントが随時配信されるイベントストリーム。',
            'content': {'text/event-stream': {}},
        }
    }
)
async def LiveStreamEventAPI(
    display_channel_id: Annotated[str, Depends(ValidateChannelID)],
    quality: Annotated[QUALITY_TYPES, Depends(ValidateQuality)],
):
    """
    ライブストリームのイベントを Server-Sent Events で随時配信する。

    イベントには、
    - 初回接続時に現在のステータスを示す **initial_update**
    - ステータスの更新を示す **status_update**
    - ステータス詳細の更新を示す **detail_update**
    - クライアント数の更新を示す **clients_update**
    の4種類がある。

    どのイベントでも配信される JSON 構造は同じ。<br>
    ステータスが Offline になった、あるいは既にそうなっている時は、status_update イベントが配信された後に接続を終了する。
    """

    # ライブストリームを取得
    # ステータスを取得したいだけなので、接続はしない
    live_stream = LiveStream(display_channel_id, quality)

    # ステータスの変更を監視し、変更があればステータスをイベントストリームとして出力する
    async def generator():
        """イベントストリームを出力するジェネレーター"""

        # 初期値
        previous_status = live_stream.getStatus()

        # 取得できたクライアント数はあくまで同じチャンネル+同じ画質で視聴中のクライアントをカウントしたものなので、
        # 同じチャンネル+すべての画質で視聴中のクライアント数を別途取得して上書きする
        previous_status.client_count = LiveStream.getViewerCount(display_channel_id)

        # 初回接続時に必ず現在のステータスを返す
        yield {
            'event': 'initial_update',  # initial_update イベントを設定
            'data': previous_status.model_dump_json(),
        }

        while True:

            # 現在のライブストリームのステータスを取得
            status = live_stream.getStatus()

            # 取得できたクライアント数はあくまで同じチャンネル+同じ画質で視聴中のクライアントをカウントしたものなので、
            # 同じチャンネル+すべての画質で視聴中のクライアント数を別途取得して上書きする
            status.client_count = LiveStream.getViewerCount(display_channel_id)

            # 以前の結果と異なっている場合のみレスポンスを返す
            if previous_status != status:

                # ステータスが以前と異なる
                if previous_status.status != status.status:
                    yield {
                        'event': 'status_update',  # status_update イベントを設定
                        'data': status.model_dump_json(),
                    }
                # 詳細が以前と異なる
                elif previous_status.detail != status.detail:
                    yield {
                        'event': 'detail_update',  # detail_update イベントを設定
                        'data': status.model_dump_json(),
                    }
                # クライアント数が以前と異なる
                elif previous_status.client_count != status.client_count:
                    yield {
                        'event': 'clients_update',  # clients_update イベントを設定
                        'data': status.model_dump_json(),
                    }

                # 取得結果を保存
                previous_status = copy.copy(status)

            # 一応スリープを入れておく
            await asyncio.sleep(0.05)

    # EventSourceResponse でイベントストリームを配信する
    return EventSourceResponse(generator())


# ***** ライブ PSI/SI アーカイブデータストリーミング API *****


@router.get(
    '/{display_channel_id}/{quality}/psi-archived-data',
    summary = 'ライブ PSI/SI アーカイブデータストリーミング API',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'ライブ PSI/SI アーカイブデータストリーム。',
            'content': {'application/octet-stream': {}},
        }
    }
)
async def LivePSIArchivedDataAPI(
    request: Request,
    display_channel_id: Annotated[str, Depends(ValidateChannelID)],
    quality: Annotated[QUALITY_TYPES, Depends(ValidateQuality)],
):
    """
    ライブ PSI/SI アーカイブデータストリームを配信する。

    何らかの理由でライブストリームが終了しない限り、継続的にレスポンスが出力される（ストリーミング）。
    """

    # ライブストリームを取得
    # PSI/SI アーカイブデータを取得したいだけなので、接続はしない
    live_stream = LiveStream(display_channel_id, quality)

    # LivePSIDataArchiver がまだ初期化されていない場合は、起動するまで最大10秒待つ
    ## LivePSIDataArchiver は LiveEncodingTask が起動次第自動的に初期化されるので、ここでは待つだけ
    for _ in range(20):
        if live_stream.psi_data_archiver is not None:
            break
        await asyncio.sleep(0.5)

    # 10秒待っても起動しなかった場合はエラー
    if live_stream.psi_data_archiver is None:
        logging.error('[LiveStreamsRouter][LivePSIArchivedDataAPI] PSI/SI Data Archiver is not running.')
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'PSI/SI Data Archiver is not running',
        )

    # StreamingResponse で読み取ったストリームデータをストリーミングする
    # LivePSIDataArchiver.getPSIArchivedData() は AsyncGenerator なので、そのまま渡せる
    response = StreamingResponse(live_stream.psi_data_archiver.getPSIArchivedData(request), media_type='application/octet-stream')

    # HTTP リクエストがキャンセルされたときに psisiarc を終了できるよう、StreamingResponse のインスタンスにモンキーパッチを当てる
    # モンキーパッチしている理由は LiveMPEGTSStreamAPI と同じ
    # ref: https://github.com/encode/starlette/pull/839
    async def listen_for_disconnect_monkeypatch(receive: Receive) -> None:
        try:
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    # HTTP リクエストの切断を検知できるようにしばらく待つ
                    await asyncio.sleep(5)
                    break
        except asyncio.CancelledError:
            pass
    response.listen_for_disconnect = listen_for_disconnect_monkeypatch

    return response


# ***** MPEG-TS ストリーミング API *****


@router.get(
    '/{display_channel_id}/{quality}/mpegts',
    summary = 'ライブ MPEG-TS ストリーム API',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'ライブ MPEG-TS ストリーム。',
            'content': {'video/mp2t': {}},
        }
    }
)
async def LiveMPEGTSStreamAPI(
    request: Request,
    display_channel_id: Annotated[str, Depends(ValidateChannelID)],
    quality: Annotated[QUALITY_TYPES, Depends(ValidateQuality)],
):
    """
    ライブ MPEG-TS ストリームを配信する。

    同じチャンネル ID 、同じ画質のライブストリームが Offline 状態のときは、新たにエンコードタスクを立ち上げて、
    ONAir 状態になるのを待機してからストリームデータを配信する。<br>
    同じチャンネル ID 、同じ画質のライブストリームが ONAir や Idling 状態のときは、新たにエンコードタスクを立ち上げることなく、他のクライアントとストリームデータを共有して配信する。

    何らかの理由でライブストリームが終了しない限り、継続的にレスポンスが出力される（ストリーミング）。
    """

    # ライブストリームに接続し、ライブストリームクライアントを取得する
    ## 接続時に Offline だった場合は自動的にエンコードタスクが起動される
    live_stream = LiveStream(display_channel_id, quality)
    live_stream_client = await live_stream.connect('mpegts')

    # ライブストリームを出力するジェネレーター
    async def generator():
        while True:

            # リクエストがキャンセル（切断）されている場合
            ## エンコードに失敗とかしない限り基本エンドレスで配信されるので、
            ## チャンネル変えたりやタブの再読み込みで必然的にリクエストがキャンセルされる
            if await request.is_disconnected():

                # ライブストリームへの接続を切断し、ループを終了する
                logging.debug_simple('[LiveStreamsRouter][LiveMPEGTSStreamAPI] Request is disconnected.')
                live_stream.disconnect(live_stream_client)
                break

            if live_stream.getStatus().status != 'Offline':

                # クライアントが持つ Queue から読み取ったストリームデータ
                stream_data: bytes | None = await live_stream_client.readStreamData()

                # 読み取ったストリームデータを yield で随時出力する
                if stream_data is not None:
                    yield stream_data

                # stream_data に None が入った場合はエンコードタスクが終了し、接続が切断されたものとみなす
                else:

                    # ライブストリームへの接続を切断し、ループを終了する
                    logging.debug_simple('[LiveStreamsRouter][LiveMPEGTSStreamAPI] Encode task is finished.')
                    live_stream.disconnect(live_stream_client)  # 必要ないとは思うけど念のため
                    break

            # ライブストリームが Offline になった場合もエンコードタスクが終了し、接続が切断されたものとみなす
            else:

                # ライブストリームへの接続を切断し、ループを終了する
                logging.debug_simple('[LiveStreamsRouter][LiveMPEGTSStreamAPI] LiveStream is currently Offline.')
                live_stream.disconnect(live_stream_client)  # 必要ないとは思うけど念のため
                break

    # StreamingResponse で読み取ったストリームデータをストリーミングする
    response = StreamingResponse(generator(), media_type='video/mp2t')

    # HTTP リクエストがキャンセルされたときに自前でライブストリームの接続を切断できるよう、StreamingResponse のインスタンスにモンキーパッチを当てる
    ## StreamingResponse はリクエストがキャンセルされるとレスポンスを生成するジェネレーターの実行自体を勝手に強制終了してしまう
    ## そうするとリクエストがキャンセルされたか判定できず、クライアントがタイムアウトするまで接続切断がライブストリームに反映されない
    ## これを避けるため StreamingResponse.listen_for_disconnect() を書き換えて、自前でライブストリームの接続を切断できるようにする
    # ref: https://github.com/encode/starlette/pull/839
    async def listen_for_disconnect_monkeypatch(receive: Receive) -> None:
        try:
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    # 上のループでライブストリームへの接続を切断できるようにしばらく待つ
                    await asyncio.sleep(5)
                    break
        except asyncio.CancelledError:
            pass
    response.listen_for_disconnect = listen_for_disconnect_monkeypatch

    return response
