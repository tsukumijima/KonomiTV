
import asyncio
import logging
import os
import sys
import tortoise.contrib.fastapi
from fastapi import FastAPI
from fastapi import Request
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi_utils.tasks import repeat_every
from pydantic import ValidationError

from app.constants import CONFIG, CLIENT_DIR, DATABASE_CONFIG, QUALITY, VERSION
from app.models import Channels
from app.models import LiveStream
from app.models import Programs
from app.routers import ChannelsRouter
from app.routers import LiveStreamsRouter
from app.schemas import Config
from app.utils import Logging
from app.utils import RunAwait


# このアプリケーションのイベントループ
loop = asyncio.get_event_loop()

# 環境設定のバリデーション
try:
    Config(**CONFIG)
except ValidationError as error:
    Logging.error(
        '設定内容が不正なため、Konomi を起動できません。\n          '
        '以下のエラーメッセージを参考に、config.yaml の記述が正しいかどうか確認してください。'
    )
    Logging.error(error)
    sys.exit(1)

# FastAPI を初期化
app = FastAPI(
    title='Konomi',
    description='Konomi: Kind and Optimized Next brOadcast watching systeM Infrastructure',
    version=VERSION,
    openapi_url='/api/openapi.json',
    docs_url='/api/docs',
    redoc_url='/api/redoc',
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
app.include_router(ChannelsRouter.router)
app.include_router(LiveStreamsRouter.router)

# 静的ファイルの配信
app.mount('/assets', StaticFiles(directory=CLIENT_DIR / 'assets', html=True))

# ルート以下のルーティング
# ファイルが存在すればそのまま配信し、ファイルが存在しなければ index.html を返す
@app.get('/{file:path}', include_in_schema=False)
async def Root(file:str):

    # ファイルが存在する
    filepath = CLIENT_DIR / f'{file}'
    if os.path.isfile(filepath):
        fileext = os.path.splitext(file)[1]
        # MIMEタイプ
        if fileext == '.css':
            mime = 'text/css'
        elif fileext == '.html':
            mime = 'text/html'
        elif fileext == '.ico':
            mime = 'image/x-icon'
        elif fileext == '.js':
            mime = 'application/javascript'
        elif fileext == '.json':
            mime = 'application/json'
        else:
            mime = 'text/plain'
        return FileResponse(filepath, media_type=mime)

    # デフォルトドキュメント (index.html)
    # URL の末尾にスラッシュがついている場合のみ
    elif os.path.isfile(filepath / 'index.html') and (file == '' or file[-1] == '/'):
        return FileResponse(filepath / 'index.html', media_type='text/html')

    # 存在しない静的ファイルが指定された場合
    else:
        if file.startswith('api/'):
            # パスに api/ が前方一致で含まれているなら、404 Not Found を返す
            return JSONResponse({'detail': 'Not Found'}, status_code=status.HTTP_404_NOT_FOUND)
        else:
            # パスに api/ が前方一致で含まれていなければ、index.html を返す
            return FileResponse(CLIENT_DIR / 'index.html', media_type='text/html')

# Internal Server Error のハンドリング
@app.exception_handler(Exception)
async def ExceptionHandler(request:Request, exc: Exception):
    return JSONResponse(
        {'detail': f'Oops! {type(exc).__name__} did something. There goes a rainbow...'},
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )

# Tortoise ORM の初期化
## ロガーを Uvicorn に統合する
## ref: https://github.com/tortoise/tortoise-orm/issues/529
tortoise.contrib.fastapi.logging = logging.getLogger('uvicorn')
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
    await Channels.update()

    # 番組情報を更新
    await Programs.update()

    # 全てのチャンネル&品質のライブストリームを初期化する
    for channel in await Channels.all().order_by('channel_number').values():
        for quality in QUALITY:
            LiveStream(channel['channel_id'], quality)

# 15分に1回、番組情報を定期的に更新する
# 番組情報の更新処理は重く他の処理に影響してしまうため、同期関数にして外部スレッドで実行する
@app.on_event('startup')
@repeat_every(seconds=15 * 60, wait_first=True, logger=Logging.logger)
def UpdateProgram():
    RunAwait(Programs.update())
