
import asyncio
import logging
import os
import tortoise.contrib.fastapi
from fastapi import FastAPI
from fastapi import Request
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.constants import CLIENT_DIR
from app.constants import DATABASE_CONFIG
from app.constants import VERSION
from app.routers import Channels
from app.routers import Streams
from app.utils import Logging



# FastAPI を初期化
app = FastAPI(
    title='Konomi',
    description='Konomi: Kind and Optimized Next brOadcast watching systeM Infrastructure',
    version=VERSION,
    openapi_url='/api/openapi.json',
    docs_url='/api/docs',
    redoc_url='/api/redoc',
)


async def init():

    # ルーターの追加
    app.include_router(Channels.router)
    app.include_router(Streams.router)

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

    # 静的ファイルの設定
    app.mount('/assets', StaticFiles(directory=CLIENT_DIR / 'assets', html=True))

    # ルート以下の静的ファイルの配信の設定
    @app.get('/{file:path}', include_in_schema=False)
    def root(file:str):
        # ファイルパス
        filepath = CLIENT_DIR / f'{file}'
        # ファイルが存在する
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
        elif os.path.isfile(filepath / 'index.html'):
            return FileResponse(filepath / 'index.html', media_type='text/html')
        # 存在しない静的ファイルが指定された場合
        else:
            # パスに api/ が前方一致で含まれているなら、404 Not Found を返す
            if file.startswith('api/'):
                return JSONResponse({'detail': 'Not Found'}, status_code=status.HTTP_404_NOT_FOUND)
            # パスに api/ が前方一致で含まれていなければ、index.html を返す
            else:
                return FileResponse(CLIENT_DIR / 'index.html', media_type='text/html')

    # index.html の設定
    @app.get('/', include_in_schema=False)
    def index():
        return FileResponse(CLIENT_DIR / 'index.html', media_type='text/html')

    # CORS の設定
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            'http://localhost:7000',
            'http://localhost:7001',
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 500 Internal server error の設定
    @app.exception_handler(Exception)
    def exception_handler(request:Request, exc: Exception):
        return JSONResponse(
            {'detail': f'Oops! {type(exc).__name__} did something. There goes a rainbow...'},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# await を使うために async 関数を非同期実行
loop = asyncio.get_event_loop()
loop.create_task(init())
