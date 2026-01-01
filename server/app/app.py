
import asyncio
import atexit
import mimetypes
from pathlib import Path
from typing import Any

import tortoise.contrib.fastapi
import tortoise.log
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import logging, schemas
from app.config import Config, LoadConfig
from app.constants import (
    CLIENT_DIR,
    DATABASE_CONFIG,
    QUALITY,
    VERSION,
)
from app.metadata.RecordedScanTask import RecordedScanTask
from app.models.Channel import Channel
from app.models.Program import Program
from app.routers import (
    CapturesRouter,
    ChannelsRouter,
    DataBroadcastingRouter,
    DiscordRouter,
    LiveStreamsRouter,
    MaintenanceRouter,
    NiconicoRouter,
    ProgramsRouter,
    ReservationConditionsRouter,
    ReservationsRouter,
    SeriesRouter,
    SettingsRouter,
    TwitterRouter,
    UsersRouter,
    VersionRouter,
    VideosRouter,
    VideoStreamsRouter,
)
from app.streams.LiveStream import LiveStream
from app.utils.edcb.EDCBTuner import EDCBTuner
from app.utils.FastAPITaskUtil import repeat_every


# もし Config() の実行時に AssertionError が発生した場合は、LoadConfig() を実行してサーバー設定データをロードする
## 自動リロードモードでは app.py がサーバープロセスのエントリーポイントになるため、
## サーバープロセス上にサーバー設定データがロードされていない状態になる
try:
    CONFIG = Config()
except AssertionError:
    # バリデーションは既にサーバー起動時に行われているためスキップする
    CONFIG = LoadConfig(bypass_validation=True)

import discord_main
from discord_main import StartDiscordBot, StopDiscordBot


# FastAPI を初期化
app = FastAPI(
    title = 'KonomiTV',
    description = 'KonomiTV: Kept Organized, Notably Optimized, Modern Interface TV media server',
    version = VERSION,
    openapi_url = '/api/openapi.json',
    docs_url = '/api/docs',
    redoc_url = '/api/redoc',
)

# ルーターの追加
app.include_router(ChannelsRouter.router)
app.include_router(ProgramsRouter.router)
app.include_router(VideosRouter.router)
app.include_router(SeriesRouter.router)
app.include_router(LiveStreamsRouter.router)
app.include_router(VideoStreamsRouter.router)
app.include_router(ReservationsRouter.router)
app.include_router(ReservationConditionsRouter.router)
app.include_router(CapturesRouter.router)
app.include_router(DataBroadcastingRouter.router)
app.include_router(DiscordRouter.router)
app.include_router(NiconicoRouter.router)
app.include_router(TwitterRouter.router)
app.include_router(UsersRouter.router)
app.include_router(SettingsRouter.router)
app.include_router(MaintenanceRouter.router)
app.include_router(VersionRouter.router)

# CORS の設定
## 開発環境では全てのオリジンからのリクエストを許可
## 本番環境では app.konomi.tv 以外のオリジンからのリクエストを拒否
CORS_ORIGINS = ['*'] if CONFIG.general.debug is True else ['https://app.konomi.tv']
app.add_middleware(
    CORSMiddleware,
    allow_origins = CORS_ORIGINS,
    # すべての HTTP メソッドと HTTP ヘッダーを許可
    allow_methods = ['*'],
    allow_headers = ['*'],
    allow_credentials = True,
)

# 拡張子と MIME タイプの対照表を上書きする
## StaticFiles の内部動作は mimetypes.guess_type() の挙動に応じて変化する
## 一部 Windows 環境では mimetypes.guess_type() が正しく機能しないため、明示的に指定しておく
for suffix, mime_type in [
    ('.css', 'text/css'),
    ('.html', 'text/html'),
    ('.ico', 'image/x-icon'),
    ('.js', 'application/javascript'),
    ('.json', 'application/json'),
    ('.map', 'application/json'),
    ]:
    guess = mimetypes.guess_type(f'foo{suffix}')[0]
    if guess != mime_type:
        mimetypes.add_type(mime_type, suffix)

# 静的ファイルの配信
app.mount('/assets', StaticFiles(directory=CLIENT_DIR / 'assets', html=True))

# ルート以下のルーティング (同期ファイル I/O を伴うため同期関数として実装している)
# ファイルが存在すればそのまま配信し、ファイルが存在しなければ index.html を返す
@app.get('/{file:path}', include_in_schema=False)
def Root(file: str):

    # ディレクトリトラバーサル対策のためのチェック
    ## ref: https://stackoverflow.com/a/45190125/17124142
    try:
        CLIENT_DIR.joinpath(Path(file)).resolve().relative_to(CLIENT_DIR.resolve())
    except ValueError:
        # URL に指定されたファイルパスが CLIENT_DIR の外側のフォルダを指している場合は、
        # ファイルが存在するかに関わらず一律で index.html を返す
        return FileResponse(CLIENT_DIR / 'index.html', media_type='text/html')

    # ファイルが存在する場合のみそのまま配信
    filepath = CLIENT_DIR / file
    if filepath.is_file():
        # 拡張子から MIME タイプを判定
        if filepath.suffix in ['.css', '.html', '.ico', '.js', '.json', '.map']:
            mime = mimetypes.guess_type(f'foo{filepath.suffix}')[0] or 'text/plain'
        else:
            mime = 'text/plain'
        return FileResponse(filepath, media_type=mime)

    # デフォルトドキュメント (index.html)
    # URL の末尾にスラッシュがついている場合のみ
    elif (filepath / 'index.html').is_file() and (file == '' or file[-1] == '/'):
        return FileResponse(filepath / 'index.html', media_type='text/html')

    # 存在しない静的ファイルが指定された場合
    else:
        if file.startswith('api/'):
            # パスに api/ が前方一致で含まれているなら、404 Not Found を返す
            return JSONResponse({'detail': 'Not Found'}, status_code = status.HTTP_404_NOT_FOUND)
        else:
            # パスに api/ が前方一致で含まれていなければ、index.html を返す
            return FileResponse(CLIENT_DIR / 'index.html', media_type='text/html')

# Internal Server Error のハンドリング
@app.exception_handler(Exception)
async def ExceptionHandler(request: Request, exc: Exception):
    return JSONResponse(
        {'detail': f'Oops! {type(exc).__name__} did something. There goes a rainbow...'},
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
        # FastAPI の謎仕様で CORSMiddleware は exception_handler に対しては効かないので、ここで自前で CORS ヘッダーを付与する
        headers = {'Access-Control-Allow-Origin': CORS_ORIGINS[0] if len(CORS_ORIGINS) > 0 else ''},
    )

# Tortoise ORM の初期化
## Tortoise ORM が利用するロガーを Uvicorn のロガーに差し替える
## ref: https://github.com/tortoise/tortoise-orm/issues/529
tortoise.log.logger = logging.logger
tortoise.log.db_client_logger = logging.logger
## Tortoise ORM を FastAPI に登録する
## ref: https://tortoise-orm.readthedocs.io/en/latest/contrib/fastapi.html
tortoise.contrib.fastapi.register_tortoise(
    app = app,
    config = DATABASE_CONFIG,
    generate_schemas = True,
    add_exception_handlers = True,
)

# 予約通知チェック用のグローバル変数
previously_recording: set[int] = set()
# 前回の予約情報を保持（録画終了時の通知に必要）
previous_reservations: dict[int, 'schemas.Reservation'] = {}


async def check_and_notify_reservations():
    """予約の開始時刻と終了時刻をチェックし、通知が必要な場合はDiscordに通知を送信する"""
    try:
        # 予約通知をサポートするバックエンド / レコーダー構成かを確認
        from app.config import Config
        config = Config()

        # Discord 連携が有効かつ、予約通知が有効かどうかを確認
        if not config.discord.enabled or not config.discord.notify_recording:
            return

        # ReservationsAPI を呼び出して予約情報を取得
        from app.routers.ReservationsRouter import GetCtrlCmdUtil, ReservationsAPI
        edcb = GetCtrlCmdUtil()
        reservations_data = await ReservationsAPI(edcb=edcb)


        # 現在時刻を取得 (JST)
        import datetime
        JST = datetime.timezone(datetime.timedelta(hours=9))
        current_time = datetime.datetime.now(JST)

        # 通知済みの予約IDをdiscord_main.pyから取得
        discord_notified_start = discord_main.notified_reservations_start
        discord_notified_end = discord_main.notified_reservations_end

        # 現在録画中の予約IDを保持するセット（終了検知用）
        global previously_recording, previous_reservations
        currently_recording = set()
        current_reservations = {}

        for reservation in reservations_data.reservations:
            # 予約が有効でない場合はスキップ
            if not reservation.record_settings.is_enabled:
                continue

            # 録画予約番組の番組開始時刻と終了時刻をJSTに変換
            start_time_jst = reservation.program.start_time.astimezone(JST)
            end_time_jst = reservation.program.end_time.astimezone(JST)

            # 現在録画中の予約を記録し、予約情報も保存
            if reservation.is_recording_in_progress:
                currently_recording.add(reservation.id)
            current_reservations[reservation.id] = reservation

            # 予約開始時刻の通知
            if (reservation.is_recording_in_progress and
                reservation.id not in previously_recording and
                reservation.id not in discord_notified_start):

                if await discord_main.SendReservationNotification(reservation, "start"):
                    # 通知済みIDに追加
                    discord_notified_start.add(reservation.id)
                    logging.info(f'[ReservationNotification] Sent start notification for reservation ID {reservation.id} - {reservation.program.title}')

            # 予約終了時刻の通知
            if (reservation.id in previously_recording and
                not reservation.is_recording_in_progress and
                reservation.id not in discord_notified_end):

                if await discord_main.SendReservationNotification(reservation, "end"):
                    # 通知済みIDに追加
                    discord_notified_end.add(reservation.id)
                    logging.info(f'[ReservationNotification] Sent end notification for reservation ID {reservation.id} - {reservation.program.title}')

        # 録画終了を検知して通知を送信
        if previously_recording != currently_recording:
            # 終了した録画を特定
            ended_recordings = previously_recording - currently_recording
            if ended_recordings:
                # 終了した録画について、前回保存していた予約情報を使って通知を送信
                for ended_reservation_id in ended_recordings:
                    if (ended_reservation_id not in discord_notified_end and
                        ended_reservation_id in previous_reservations):
                        previous_reservation = previous_reservations[ended_reservation_id]

                        if await discord_main.SendReservationNotification(previous_reservation, "end"):
                            # 通知済みIDに追加
                            discord_notified_end.add(ended_reservation_id)
                            logging.info(f'[ReservationNotification] Sent end notification for reservation ID {ended_reservation_id} - {previous_reservation.program.title}')

        # 前回の録画状態と予約情報を更新
        previously_recording = currently_recording.copy()
        previous_reservations = current_reservations.copy()

        # 過去の通知済みIDと予約情報をクリアする（番組終了時刻から1時間後）
        # 現在の予約と前回保存した予約の両方をチェック
        all_reservations = list(reservations_data.reservations) + list(previous_reservations.values())
        cleaned_reservation_ids = set()

        for reservation in all_reservations:
            if not reservation.record_settings.is_enabled:
                continue

            # 重複チェック（同じ予約IDが複数回処理されないように）
            if reservation.id in cleaned_reservation_ids:
                continue
            cleaned_reservation_ids.add(reservation.id)

            start_time_jst = reservation.program.start_time.astimezone(JST)
            end_time_jst = reservation.program.end_time.astimezone(JST)

            # 開始時刻から1時間以上経過し、通知済みの場合、通知済みセットから削除
            if start_time_jst + datetime.timedelta(hours=1) < current_time and reservation.id in discord_notified_start:
                discord_notified_start.discard(reservation.id)
            # 終了時刻から1時間以上経過し、通知済みの場合、通知済みセットと予約情報から削除
            if end_time_jst + datetime.timedelta(hours=1) < current_time:
                if reservation.id in discord_notified_end:
                    discord_notified_end.discard(reservation.id)
                # 古い予約情報も削除してメモリリークを防ぐ
                if reservation.id in previous_reservations:
                    del previous_reservations[reservation.id]

    except Exception as e:
        logging.error(f'[ReservationNotification] Error checking reservations: {e}')

# サーバーの起動時に実行する
recorded_scan_task: RecordedScanTask | None = None
discord_bot_task: asyncio.Task[Any] | None = None
reservation_checker_task: asyncio.Task[Any] | None = None

@app.on_event('startup')
async def Startup():
    global recorded_scan_task, discord_bot_task, reservation_checker_task

    # チャンネル情報を更新
    await Channel.update()

    # ニコニコ実況関連のステータスを更新
    await Channel.updateJikkyoStatus()

    # 番組情報を更新
    await Program.update()

    # 全てのチャンネル&品質のライブストリームを初期化する
    for channel in await Channel.filter(is_watchable=True).order_by('channel_number'):
        for quality in QUALITY:
            LiveStream(channel.display_channel_id, quality)

    # 録画フォルダ監視・メタデータ更新/同期タスクを開始
    ## 録画ファイルの量次第では録画ファイルの更新確認に時間がかかるため、非同期で実行する
    # ref: https://docs.astral.sh/ruff/rules/asyncio-dangling-task/
    recorded_scan_task = RecordedScanTask()
    await recorded_scan_task.start()

    # Discord Bot をバックグラウンドタスクとして起動する
    if CONFIG.discord.enabled and CONFIG.discord.token:
        logging.info('Discord Bot starting...')
        discord_bot_task = asyncio.create_task(StartDiscordBot())

    # 予約通知チェックをバックグラウンドタスクとして起動する
    if CONFIG.discord.enabled and CONFIG.discord.notify_recording:
        logging.info('Reservation Notification Checker starting...')
        reservation_checker_task = asyncio.create_task(repeat_every(seconds=30, wait_first=30, logger=logging.logger)(check_and_notify_reservations)())

# サーバー設定で指定された時間 (デフォルト: 15分) ごとに1回、チャンネル情報と番組情報を更新する
# チャンネル情報は頻繁に変わるわけではないけど、手動で再起動しなくても自動で変更が適用されてほしい
# 番組情報の更新処理はかなり重くストリーム配信などの他の処理に影響してしまうため、マルチプロセスで実行する
@app.on_event('startup')
@repeat_every(
    seconds = CONFIG.general.program_update_interval * 60,
    wait_first = CONFIG.general.program_update_interval * 60,
    logger = logging.logger,
)
async def UpdateChannelAndProgram():
    await Channel.update()
    await Channel.updateJikkyoStatus()
    await Program.update(multiprocess=True)

# 30秒に1回、ニコニコ実況関連のステータスを更新する
@app.on_event('startup')
@repeat_every(seconds=0.5 * 60, wait_first=0.5 * 60, logger=logging.logger)
async def UpdateChannelJikkyoStatus():
    await Channel.updateJikkyoStatus()

# サーバーの終了時に実行する
cleanup = False
@app.on_event('shutdown')
async def Shutdown():

    # 2度呼ばれないように
    global cleanup
    if cleanup is True:
        return
    cleanup = True

    # 全てのライブストリームを終了する
    for live_stream in LiveStream.getAllLiveStreams():
        live_stream.setStatus('Offline', 'ライブストリームは Offline です。', True)

    # 全てのチューナーインスタンスを終了する (EDCB バックエンドのみ)
    if CONFIG.general.backend == 'EDCB':
        await EDCBTuner.closeAll()

    # 録画フォルダ監視タスクを停止
    global recorded_scan_task
    if recorded_scan_task is not None:
        await recorded_scan_task.stop()
        recorded_scan_task = None

    # Discord Bot を停止する
    ## Discord 連携が有効な場合のみ停止処理を行う
    if CONFIG.discord.enabled and CONFIG.discord.token:
        logging.info('Discord Bot stopping...')
        await StopDiscordBot()

# shutdown イベントが発火しない場合も想定し、アプリケーションの終了時に Shutdown() が確実に呼ばれるように
# atexit は同期関数しか実行できないので、asyncio.run() でくるむ
atexit.register(asyncio.run, Shutdown())
