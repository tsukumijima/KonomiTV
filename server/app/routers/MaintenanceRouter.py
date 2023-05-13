
from fastapi import APIRouter
from fastapi import status

from app.models import Channel
from app.models import Program
from app.models import TwitterAccount


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
async def UpdateDatabaseAPI():
    """
    データベースに保存されている、チャンネル情報・番組情報・Twitter アカウント情報などの外部 API に依存するデータをすべて更新する。<br>
    即座に外部 API でのデータ更新を反映させたい場合に利用する。
    """

    await Channel.update()
    await Channel.updateJikkyoStatus()
    await Program.update(multiprocess=True)
    await TwitterAccount.updateAccountInformation()
