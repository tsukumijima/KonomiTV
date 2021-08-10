
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

    # チャンネル情報を取得
    channels = await Channels.all().order_by('channel_number').values()

    # レスポンスの雛形
    result = {
        'GR': list(),
        'BS': list(),
        'CS': list(),
        'SKY': list(),
    }

    # チャンネルごとに実行
    tasks = list()
    for channel in channels:

        # 非同期並列実行するタスク
        async def task(channel):

            now = time.time()

            # 現在の番組情報を取得する
            ## 番組開始時刻が現在時刻と等しいかそれより前で、番組終了時刻が現在時刻よりも後
            program_current = await Programs.filter(channel_id=channel['channel_id']).order_by('-start_time') \
                                            .filter(start_time__lte = now, end_time__gt = now).first().values()
            channel['program_current'] = program_current[0] if len(program_current) > 0 else None

            # 次の番組情報を取得する
            ## 番組開始時刻が現在時刻よりも後
            program_next = await Programs.filter(channel_id=channel['channel_id']).order_by('start_time') \
                                        .filter(start_time__gt = now).first().values()
            channel['program_next'] = program_next[0] if len(program_next) > 0 else None

            # チャンネルタイプで分類
            result[channel['channel_type']].append(channel)

            Logging.info('time:' + str(time.time() - now))

        # タスク（コルーチン）を順次追加していく
        tasks.append(task(channel))

    # 一気に並列実行
    await asyncio.gather(*tasks)

    # チャンネルタイプごとに返却
    return result
