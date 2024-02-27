
import os
import psutil
import signal
import sys
import threading
import time
from fastapi import APIRouter
from fastapi import Depends
from fastapi import Request
from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.security import OAuth2PasswordBearer
from typing import Annotated

from app import logging
from app.config import Config
from app.constants import RESTART_REQUIRED_LOCK_PATH
from app.models.Channel import Channel
from app.models.Program import Program
from app.models.TwitterAccount import TwitterAccount
from app.models.User import User
from app.routers.UsersRouter import GetCurrentAdminUser
from app.routers.UsersRouter import GetCurrentUser


# ルーター
router = APIRouter(
    tags = ['Maintenance'],
    prefix = '/api/maintenance',
)


async def GetCurrentAdminUserOrLocal(
    request: Request,
    token: Annotated[str | None, Depends(OAuth2PasswordBearer(tokenUrl='users/token', auto_error=False))],
) -> User | None:
    """
    現在管理者ユーザーでログインしているか、http://127.0.0.77:7010 からのアクセスであるかを確認する
    KonomiTV の Windows サービスからサーバーをシャットダウンするために必要
    """

    # HTTP リクエストの Host ヘッダーが 127.0.0.77:7010 である場合、Windows サービスプロセスからのアクセスと見なす
    ## 通常アクセス時の Host ヘッダーは 192-168-1-11.local.konomi.tv:7000 のような形式になる
    valid_host = f'127.0.0.77:{Config().server.port + 10}'
    if request.headers.get('host', '').strip() == valid_host:
        return None

    # それ以外である場合、管理者ユーザーでログインしているかを確認する
    if token is None:
        logging.error('[MaintenanceRouter][GetCurrentAdminUserOrLocal] Not authenticated')
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = 'Not authenticated',
            headers = {'WWW-Authenticate': 'Bearer'},
        )
    return await GetCurrentAdminUser(await GetCurrentUser(token))


@router.post(
    '/update-database',
    summary = 'データベース更新 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def UpdateDatabaseAPI(
    current_user: Annotated[User, Depends(GetCurrentAdminUser)],
):
    """
    データベースに保存されている、チャンネル情報・番組情報・Twitter アカウント情報などの外部 API に依存するデータをすべて更新する。<br>
    即座に外部 API からのデータ更新を反映させたい場合に利用する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    await Channel.update()
    await Channel.updateJikkyoStatus()
    await Program.update(multiprocess=True)
    await TwitterAccount.updateAccountsInformation()


@router.post(
    '/restart',
    summary = 'サーバー再起動 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
def ServerRestartAPI(
    current_user: Annotated[User | None, Depends(GetCurrentAdminUserOrLocal)],
):
    """
    KonomiTV サーバーを再起動する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    def Restart():

        # シグナルの送信対象の PID
        ## --reload フラグが付与されている場合のみ、Reloader の起動元である親プロセスの PID を利用する
        target_process: psutil.Process = psutil.Process(os.getpid())
        if '--reload' in sys.argv:
            target_process = target_process.parent()

        # 現在の Uvicorn サーバーを終了する
        if sys.platform == 'win32':
            target_process.send_signal(signal.CTRL_C_EVENT)
        else:
            target_process.send_signal(signal.SIGINT)

        # Waiting for connections to close. となって終了できない場合があるので、少し待ってからもう一度シグナルを送る
        time.sleep(0.5)
        if sys.platform == 'win32':
            target_process.send_signal(signal.CTRL_C_EVENT)
        else:
            target_process.send_signal(signal.SIGINT)

        # Uvicorn 終了後に再起動が必要であることを示すロックファイルを作成する
        # Uvicorn 終了後、KonomiTV.py でロックファイルの存在が確認され、もし存在していればサーバー再起動が行われる
        RESTART_REQUIRED_LOCK_PATH.touch(exist_ok=True)

    # バックグラウンドでサーバー再起動を開始
    threading.Thread(target=Restart).start()


@router.post(
    '/shutdown',
    summary = 'サーバー終了 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
def ServerShutdownAPI(
    current_user: Annotated[User | None, Depends(GetCurrentAdminUserOrLocal)],
):
    """
    KonomiTV サーバーを終了する。<br>
    なお、PM2 環境 / Docker 環境ではサーバー終了後に自動的にプロセスが再起動されるため、事実上 /api/maintenance/restart と等価。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    def Shutdown():

        # シグナルの送信対象の PID
        ## --reload フラグが付与されている場合のみ、Reloader の起動元である親プロセスの PID を利用する
        target_process: psutil.Process = psutil.Process(os.getpid())
        if '--reload' in sys.argv:
            target_process = target_process.parent()

        # 現在の Uvicorn サーバーを終了する
        if sys.platform == 'win32':
            target_process.send_signal(signal.CTRL_C_EVENT)
        else:
            target_process.send_signal(signal.SIGINT)

        # Waiting for connections to close. となって終了できない場合があるので、少し待ってからもう一度シグナルを送る
        time.sleep(0.5)
        if sys.platform == 'win32':
            target_process.send_signal(signal.CTRL_C_EVENT)
        else:
            target_process.send_signal(signal.SIGINT)

    # バックグラウンドでサーバー終了を開始
    threading.Thread(target=Shutdown).start()
