
from fastapi import APIRouter

from app.models import Channels
from app.schemas import ChannelsAPIResponse


# ルーター
router = APIRouter(
    tags=['Channels'],
    prefix='/api/channels',
)


@router.get(
    '',
    summary = 'チャンネル情報 API',
    response_description = 'チャンネル情報。',
    response_model = ChannelsAPIResponse,  # Response の構造を明示
)
async def ChannelsAPI():
    """
    地デジ (GR)・BS・CS・SKY それぞれのチャンネル情報を一括で取得する。
    """

    # 各チャンネルタイプごとにチャンネル番号順で並び替えて表示
    return {
        'GR': await Channels.filter(channel_type='GR').order_by('channel_number').values(),
        'BS': await Channels.filter(channel_type='BS').order_by('channel_number').values(),
        'CS': await Channels.filter(channel_type='CS').order_by('channel_number').values(),
        'SKY': await Channels.filter(channel_type='SKY').order_by('channel_number').values(),
    }
