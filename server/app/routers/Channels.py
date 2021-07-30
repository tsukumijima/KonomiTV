
from fastapi import APIRouter

from app.models import Channels


# ルーター
router = APIRouter(
    tags=['Channels'],
    prefix='/api/channels',
)


@router.get('', summary='チャンネル情報 API')
async def ChannelsAPI():

    # チャンネル情報を更新
    # 暫定、本来は起動時に実行する
    await Channels.update()

    # 各チャンネルタイプごとにチャンネル番号順で並び替えて表示
    return {
        'GR': await Channels.filter(channel_type='GR').order_by('channel_number').values(),
        'BS': await Channels.filter(channel_type='BS').order_by('channel_number').values(),
        'CS': await Channels.filter(channel_type='CS').order_by('channel_number').values(),
        'SKY': await Channels.filter(channel_type='SKY').order_by('channel_number').values(),
    }
