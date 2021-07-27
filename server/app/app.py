
import os
import traceback
from fastapi import FastAPI
from fastapi import Request
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.constants import CLIENT_DIR
from app.routers import streams
from app.utils import Logging


# FastAPI を初期化
app = FastAPI(
    title='Konomi',
    description='Konomi: Kind and Optimized Next brOadcast watching systeM Infrastructure',
    version='0.1.0',
)

# ルーターの設定
app.include_router(streams.router)

# 静的ファイルの設定
app.mount('/assets', StaticFiles(directory=CLIENT_DIR / 'assets', html=True))

# ルート以下の静的ファイルの配信の設定
@app.get('/{file:path}', include_in_schema=False)
def root(file:str):
    # ファイルパス
    filepath = CLIENT_DIR / f'{file}'
    if os.path.isfile(filepath):  # ファイルが存在する
        fileext = file.split('.')[1]
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
    else:  # 存在しない静的ファイルが指定された場合
        Logging.info(file)
        # パスに api/ が前方一致で含まれているなら、Not Found を返す
        if file.startswith('api/'):
            return JSONResponse({'detail': 'Not Found'}, status_code=status.HTTP_404_NOT_FOUND)
        # パスに api/ が前方一致で含まれていなければ、index.html を返す
        else:
            return HTMLResponse(open(CLIENT_DIR / 'index.html', encoding='utf-8').read())

# index.html の設定
@app.get('/', include_in_schema=False)
def index():
    return HTMLResponse(open(CLIENT_DIR / 'index.html', encoding='utf-8').read())

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
    Logging.error(traceback.format_exc())
    if type(exc).__name__ == 'HTTPException':  # HTTPException を除外
        return JSONResponse(
            {'detail': f'Oops! {type(exc).__name__} did something. There goes a rainbow...'},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
