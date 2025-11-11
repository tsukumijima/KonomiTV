
import asyncio
import atexit
import mimetypes
from pathlib import Path

import tortoise.contrib.fastapi
import tortoise.log
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import logging
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

# サーバーの起動時に実行する
recorded_scan_task: RecordedScanTask | None = None
@app.on_event('startup')
async def Startup():
    global recorded_scan_task

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

# shutdown イベントが発火しない場合も想定し、アプリケーションの終了時に Shutdown() が確実に呼ばれるように
# atexit は同期関数しか実行できないので、asyncio.run() でくるむ
atexit.register(asyncio.run, Shutdown())
