
import asyncio
import atexit
import logging
import tortoise.contrib.fastapi
from fastapi import FastAPI
from fastapi import Request
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi_utils.tasks import repeat_every

from app.constants import CONFIG, CLIENT_DIR, DATABASE_CONFIG, QUALITY, VERSION
from app.models import Channel
from app.models import LiveStream
from app.models import Program
from app.models import TwitterAccount
from app.routers import CapturesRouter
from app.routers import ChannelsRouter
from app.routers import LiveStreamsRouter
from app.routers import NiconicoRouter
from app.routers import SettingsRouter
from app.routers import TwitterRouter
from app.routers import UsersRouter
from app.routers import VersionRouter
from app.utils import Interlaced
from app.utils import Logging
from app.utils.EDCB import EDCBTuner


# このアプリケーションのイベントループ
loop = asyncio.get_event_loop()

# FastAPI を初期化
app = FastAPI(
    title = 'KonomiTV',
    description = 'KonomiTV: Kept Organized, Notably Optimized, Modern Interface TV media server',
    openapi_url = '/api/openapi.json',
    docs_url = '/api/docs',
    redoc_url = '/api/redoc',
    version = VERSION,
)

# CORS の設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        '*' if CONFIG['general']['debug'] is True else '',  # デバッグ時のみ CORS ヘッダーを有効化
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーターの追加
app.include_router(CapturesRouter.router)
app.include_router(ChannelsRouter.router)
app.include_router(LiveStreamsRouter.router)
app.include_router(SettingsRouter.router)
app.include_router(NiconicoRouter.router)
app.include_router(TwitterRouter.router)
app.include_router(UsersRouter.router)
app.include_router(VersionRouter.router)

# 静的ファイルの配信
app.mount('/assets', StaticFiles(directory=CLIENT_DIR / 'assets', html=True))

# ルート以下のルーティング
# ファイルが存在すればそのまま配信し、ファイルが存在しなければ index.html を返す
@app.get('/{file:path}', include_in_schema=False)
async def Root(file: str):

    # ファイルが存在する場合のみそのまま配信
    filepath = CLIENT_DIR / f'{file}'
    if filepath.is_file():
        # 拡張子から MIME タイプを判定
        if filepath.suffix == '.css':
            mime = 'text/css'
        elif filepath.suffix == '.html':
            mime = 'text/html'
        elif filepath.suffix == '.ico':
            mime = 'image/x-icon'
        elif filepath.suffix == '.js':
            mime = 'application/javascript'
        elif filepath.suffix == '.json':
            mime = 'application/json'
        elif filepath.suffix == '.map':
            mime = 'application/json'
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
    )

# Tortoise ORM の初期化
## ロガーを Uvicorn に統合する
## ref: https://github.com/tortoise/tortoise-orm/issues/529
tortoise.contrib.fastapi.logging = logging.getLogger('uvicorn')  # type: ignore
## Tortoise ORM を登録する
## ref: https://tortoise-orm.readthedocs.io/en/latest/contrib/fastapi.html
tortoise.contrib.fastapi.register_tortoise(
    app=app,
    config=DATABASE_CONFIG,
    generate_schemas=True,
    add_exception_handlers=True,
)

# サーバーの起動時に実行する
@app.on_event('startup')
async def Startup():

    # チャンネル情報を更新
    await Channel.update()

    # ニコニコ実況関連のステータスを更新
    await Channel.updateJikkyoStatus()

    # 番組情報を更新
    await Program.update()

    # 登録されている Twitter アカウントの情報を更新
    await TwitterAccount.updateAccountInformation()

    # 全てのチャンネル&品質のライブストリームを初期化する
    for channel in await Channel.all().order_by('channel_number').values():
        for quality in QUALITY:
            LiveStream(channel['channel_id'], quality)

# 環境設定で指定された時間 (デフォルト: 15分) ごとに1回、チャンネル情報と番組情報を更新する
# チャンネル情報は頻繁に変わるわけではないけど、手動で再起動しなくても自動で変更が適用されてほしい
# 番組情報の更新処理はかなり重くストリーム配信などの他の処理に影響してしまうため、マルチプロセスで実行する
@app.on_event('startup')
@repeat_every(seconds=CONFIG['general']['program_update_interval'] * 60, wait_first=True, logger=Logging.logger)
async def UpdateChannelAndProgram():
    await Channel.update()
    await Channel.updateJikkyoStatus()
    await Program.update(multiprocess=True)

# 30秒に1回、ニコニコ実況関連のステータスを更新する
@app.on_event('startup')
@repeat_every(seconds=0.5 * 60, wait_first=True, logger=Logging.logger)
async def UpdateChannelJikkyoStatus():
    await Channel.updateJikkyoStatus()

# 1時間に1回、登録されている Twitter アカウントの情報を更新する
@app.on_event('startup')
@repeat_every(seconds=60 * 60, wait_first=True, logger=Logging.logger)
async def UpdateTwitterAccountInformation():
    await TwitterAccount.updateAccountInformation()

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
    for livestream in LiveStream.getAllLiveStreams():
        livestream.setStatus('Offline', 'ライブストリームは Offline です。', True)

    # 全てのチューナーインスタンスを終了する (EDCB バックエンドのみ)
    if CONFIG['general']['backend'] == 'EDCB':
        await EDCBTuner.closeAll()

# shutdown イベントが発火しない場合も想定し、アプリケーションの終了時に Shutdown() が確実に呼ばれるように
# atexit は同期関数しか実行できないので、asyncio.run() でくるむ
atexit.register(asyncio.run, Shutdown())

# Twitter の CK/CS
consumer_key: str = CONFIG['twitter']['consumer_key'] if CONFIG['twitter']['consumer_key'] is not None else Interlaced(1)
consumer_secret: str = CONFIG['twitter']['consumer_secret'] if CONFIG['twitter']['consumer_secret'] is not None else Interlaced(2)
