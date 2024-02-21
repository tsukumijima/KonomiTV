
from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Path
from fastapi import Query
from fastapi import status
from typing import Annotated, Literal

from app import logging
from app import schemas
from app.models.RecordedProgram import RecordedProgram
from app.utils.Jikkyo import Jikkyo


# ルーター
router = APIRouter(
    tags = ['Videos'],
    prefix = '/api/videos',
)


@router.get(
    '',
    summary = '録画番組一覧 API',
    response_description = '録画番組の情報のリスト。',
    response_model = schemas.RecordedPrograms,
)
async def VideosAPI(
    order: Annotated[Literal['desc', 'asc'], Query(description='ソート順序 (desc or asc) 。')] = 'desc',
    page: Annotated[int, Query(description='ページ番号。')] = 1,
):
    """
    すべての録画番組を一度に 100 件ずつ取得する。<br>
    order には "desc" か "asc" を指定する。<br>
    page (ページ番号) には 1 以上の整数を指定する。
    """

    PAGE_SIZE = 100
    recorded_programs = await RecordedProgram.all() \
        .select_related('recorded_video') \
        .select_related('channel') \
        .order_by('-start_time' if order == 'desc' else 'start_time') \
        .offset((page - 1) * PAGE_SIZE) \
        .limit(PAGE_SIZE) \

    return {
        'total': await RecordedProgram.all().count(),
        'recorded_programs': recorded_programs,
    }


@router.get(
    '/{video_id}',
    summary = '録画番組 API',
    response_description = '録画番組の情報。',
    response_model = schemas.RecordedProgram,
)
async def VideoAPI(
    video_id: Annotated[int, Path(description='録画番組の ID 。')],
):
    """
    指定された録画番組を取得する。
    """

    recorded_program = await RecordedProgram.get_or_none(id=video_id) \
        .select_related('recorded_video') \
        .select_related('channel')
    if recorded_program is None:
        logging.error(f'[VideosRouter][VideoAPI] Specified video_id was not found [video_id: {video_id}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified video_id was not found',
        )

    return recorded_program


@router.get(
    '/{video_id}/jikkyo',
    summary = '録画番組過去ログコメント API',
    response_description = '録画番組の放送中に投稿されたニコニコ実況の過去ログコメント。',
    response_model = schemas.JikkyoComments,
)
async def VideoJikkyoCommentsAPI(
    video_id: Annotated[int, Path(description='録画番組の ID 。')],
):
    """
    指定された録画番組の放送中に投稿されたニコニコ実況の過去ログコメントを取得する。
    ニコニコ実況 過去ログ API をラップし、DPlayer が受け付けるコメント形式に変換して返す。
    """

    recorded_program = await RecordedProgram.get_or_none(id=video_id) \
        .select_related('recorded_video') \
        .select_related('channel')
    if recorded_program is None:
        logging.error(f'[VideosRouter][VideoAPI] Specified video_id was not found [video_id: {video_id}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified video_id was not found',
        )

    # チャンネル情報と録画開始時刻/録画終了時刻の情報がある場合のみ
    if ((recorded_program.channel is not None) and
        (recorded_program.recorded_video.recording_start_time is not None) and
        (recorded_program.recorded_video.recording_end_time is not None)):

        # ニコニコ実況 過去ログ API から一致する過去ログコメントを取得して返す
        jikkyo = Jikkyo(recorded_program.channel.network_id, recorded_program.channel.service_id)
        return await jikkyo.fetchJikkyoComments(
            recorded_program.recorded_video.recording_start_time,
            recorded_program.recorded_video.recording_end_time,
        )

    # それ以外の場合はエラーを返す
    return schemas.JikkyoComments(
        is_success = False,
        comments = [],
        detail = 'チャンネル情報または録画開始時刻/録画終了時刻の情報がない録画番組です。',
    )
