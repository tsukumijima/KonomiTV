
from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import status
from typing import Literal

from app import schemas
from app.models.RecordedProgram import RecordedProgram
from app.utils import Logging


# ルーター
router = APIRouter(
    tags = ['Videos'],
    prefix = '/api/videos',
)


@router.get(
    '',
    summary = '録画番組一覧 API',
    response_description = '録画番組のリスト。',
    response_model = schemas.RecordedPrograms,
)
async def VideosAPI(
    order: Literal['desc', 'asc'] = 'desc',
    page: int = 1,
):
    """
    すべての録画番組を一度に 100 件ずつ取得する。<br>
    order には "desc" か "asc" を指定する。<br>
    page (ページ番号) には 1 以上の整数を指定する。
    """

    PAGE_SIZE = 100
    recorded_programs = await RecordedProgram.all() \
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
    response_description = '録画番組。',
    response_model = schemas.RecordedProgram,
)
async def VideoAPI(video_id: int):
    """
    指定された録画番組を取得する。
    """

    recorded_program = await RecordedProgram.get_or_none(id=video_id)
    if recorded_program is None:
        Logging.error(f'[VideosRouter][VideoAPI] Specified video_id was not found [video_id: {video_id}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified video_id was not found',
        )

    return recorded_program
