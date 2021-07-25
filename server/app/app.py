
import os
import traceback
from fastapi import FastAPI
from fastapi import Request
from fastapi import HTTPException
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.constants import CLIENT_DIR
from app.routers import streams
from app.utils import Logging


# FastAPI を初期化
app = FastAPI(
    title='Konomi',
    description='Konomi: Kind and Optimized Next brOadcast watching systeM Infrastructure',
    version='0.1.0',
)

# 静的ファイルの設定
app.mount('/assets', StaticFiles(directory=CLIENT_DIR / 'assets', html=True))

## ルート以下の静的ファイルの配信の設定
@app.get('/{filename}.{fileext}', include_in_schema=False)
def root(filename:str, fileext:str):
    # ファイルパス
    filepath = CLIENT_DIR / f'{filename}.{fileext}'
    if os.path.isfile(filepath):  # ファイルが存在する
        # MIMEタイプ
        if fileext == 'ico':
            mime = 'image/x-icon'
        elif fileext == 'js':
            mime = 'application/javascript'
        elif fileext == 'json':
            mime = 'application/json'
        else:
            mime = 'text/plain'
        return FileResponse(CLIENT_DIR / filepath, media_type=mime)
    else:  # 存在しない静的ファイルが指定された場合、index.html を返す
        return HTMLResponse(open(CLIENT_DIR / 'index.html', encoding='utf-8').read())

## index.html の設定
@app.get('/', include_in_schema=False)
def index():
    return HTMLResponse(open(CLIENT_DIR / 'index.html', encoding='utf-8').read())

# ルーターの設定
app.include_router(streams.router)

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

# 404 Not found 時の設定
# @app.exception_handler(StarletteHTTPException)
# def notfound_handler(request:Request, exc: Exception):
#     # 404 で、かつパスに /api/ が含まれていない
#     Logging.error(exc.status_code)
#     if exc.status_code == 404 and '/api/' not in str(request.url):
#         return HTMLResponse(open(CLIENT_DIR / 'index.html', encoding='utf-8').read())
#     # 404 で、かつパスに /api/ が含まれている
#     else:
#         return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={'detail': 'Not Found'})

# 500 Internal server error の設定
@app.exception_handler(Exception)
def exception_handler(request:Request, exc: Exception):
    Logging.error(traceback.format_exc())
    if type(exc).__name__ == 'HTTPException':  # HTTPException を除外
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'detail': f'Oops! {type(exc).__name__} did something. There goes a rainbow...'}
        )
