
import asyncio
import time
from fastapi import APIRouter
from tortoise import timezone

from app.models import Channels
from app.models import Programs
from app.schemas import ChannelsAPIResponse
from app.utils import Logging


# ルーター
router = APIRouter(
    tags=['Channels'],
    prefix='/api/channels',
)


@router.get(
    '',
    summary = 'チャンネル情報 API',
    response_description = 'チャンネル情報。',
)
async def ChannelsAPI():
    """
    地デジ (GR)・BS・CS・SKY それぞれのチャンネル情報を一括で取得する。
    """

    # 現在時刻
    now = timezone.now()

    now_t = time.time()

    # タスク
    tasks = list()

    # チャンネル情報を取得
    tasks.append(Channels.all().order_by('channel_number').values())

    # 現在の番組情報を取得する
    ## 番組開始時刻が現在時刻と等しいかそれより前で、番組終了時刻が現在時刻よりも後
    tasks.append(Programs.all().order_by('-start_time').filter(start_time__lte = now, end_time__gt = now).values())

    # 次の番組情報を取得する
    ## 番組開始時刻が現在時刻よりも後
    tasks.append(Programs.all().order_by('start_time').filter(start_time__gt = now).values())

    # 並列実行
    channels, programs_current, programs_next = await asyncio.gather(*tasks)

    Logging.info(f'***** Query Time: {time.time() - now_t} *****')

    # レスポンスの雛形
    result = {
        'GR': list(),
        'BS': list(),
        'CS': list(),
        'SKY': list(),
    }

    now_t = time.time()

    # チャンネルごとに実行
    tasks = list()
    for channel in channels:

        # チャンネル ID で絞り込む
        program_current = list(filter(lambda temp: temp['channel_id'] == channel['channel_id'], programs_current))
        program_next = list(filter(lambda temp: temp['channel_id'] == channel['channel_id'], programs_next))

        # 要素が 0 個以上であれば
        channel['program_current'] = program_current[0] if len(program_current) > 0 else None
        channel['program_next'] = program_next[0] if len(program_next) > 0 else None

        # チャンネルタイプで分類
        result[channel['channel_type']].append(channel)

    Logging.info(f'***** Filter Time: {time.time() - now_t} *****')

    # チャンネルタイプごとに返却
    return result
