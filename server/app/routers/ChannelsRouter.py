
import asyncio
import time
from datetime import timedelta
from fastapi import APIRouter
from tortoise import timezone

from app import schemas
from app.models import Channels
from app.models import Programs
from app.utils import Logging


# ルーター
router = APIRouter(
    tags=['Channels'],
    prefix='/api/channels',
)


@router.get(
    '',
    summary = 'チャンネル情報一覧 API',
    response_description = 'チャンネル情報。',
    response_model = schemas.Channels,
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
    ## 13時間分しか取得しないのはパフォーマンスの関係 当然 13 時間を超える番組は表示できなくなるが、
    ## そもそも 13 時間を超える番組はデータ放送やショップチャンネル垂れ流しの CATV くらいなので実害はないと判断
    ## 24時間分取得するときよりも 100ms ほど短縮される
    tasks.append(Programs.all().filter(
        start_time__lte = now,  # 番組開始時刻が現在時刻と等しいかそれより前
        end_time__gt = now,  # 番組終了時刻が現在時刻よりも後
        end_time__lt = now + timedelta(hours=13),  # 番組終了時刻が(現在時刻 + 13時間)より前
    ).order_by('-start_time').values())

    # 次の番組情報を取得する
    tasks.append(Programs.all().filter(
        start_time__gt = now,  # 番組開始時刻が現在時刻よりも後
        end_time__lt = now + timedelta(hours=13),  # 番組終了時刻が(現在時刻 + 13時間)より前
    ).order_by('start_time').values())

    # 並列実行
    channels, programs_current, programs_next = await asyncio.gather(*tasks)

    Logging.debug(f'Query Time: {time.time() - now_t}')

    # レスポンスの雛形
    result = {
        'GR': list(),
        'BS': list(),
        'CS': list(),
        'SKY': list(),
    }

    now_t = time.time()

    # チャンネルごとに実行
    for channel in channels:

        # チャンネル ID で絞り込む
        program_current = list(filter(lambda temp: temp['channel_id'] == channel['channel_id'], programs_current))
        program_next = list(filter(lambda temp: temp['channel_id'] == channel['channel_id'], programs_next))

        # 要素が 0 個以上であれば
        channel['program_current'] = program_current[0] if len(program_current) > 0 else None
        channel['program_next'] = program_next[0] if len(program_next) > 0 else None

        # チャンネルタイプで分類
        result[channel['channel_type']].append(channel)

    Logging.debug(f'Filter Time: {time.time() - now_t}')

    # チャンネルタイプごとに返却
    return result
