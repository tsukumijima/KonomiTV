
from fastapi import APIRouter
from fastapi import BackgroundTasks
from fastapi import Depends
from fastapi import status

from app.models import Channel
from app.models import Program
from app.models import TwitterAccount
from app.models import User
from app.routers.UsersRouter import GetCurrentAdminUser
from app.utils import ServerManager


# ルーター
router = APIRouter(
    tags = ['Maintenance'],
    prefix = '/api/maintenance',
)


@router.post(
    '/update-database',
    summary = 'データベース更新 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def UpdateDatabaseAPI(
    current_user: User = Depends(GetCurrentAdminUser),
):
    """
    データベースに保存されている、チャンネル情報・番組情報・Twitter アカウント情報などの外部 API に依存するデータをすべて更新する。<br>
    即座に外部 API でのデータ更新を反映させたい場合に利用する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    await Channel.update()
    await Channel.updateJikkyoStatus()
    await Program.update(multiprocess=True)
    await TwitterAccount.updateAccountInformation()


@router.post(
    '/restart',
    summary = 'サーバー再起動 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def ServerRestartAPI(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(GetCurrentAdminUser),
):
    """
    KonomiTV サーバーを再起動する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    # バックグラウンドでサーバーの再起動を行う
    background_tasks.add_task(ServerManager.restart)
