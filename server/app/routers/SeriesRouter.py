
from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import status

from app import schemas
from app.models import Series
from app.utils import Logging


# ルーター
router = APIRouter(
    tags = ['Series'],
    prefix = '/api/series',
)


@router.get(
    '',
    summary = 'シリーズ番組一覧 API',
    response_description = 'シリーズ番組のリスト。',
    response_model = schemas.SeriesList,
)
async def SeriesListAPI():
    """
    すべてのシリーズ番組を取得する。
    """

    series_list = await Series.all() \
        .prefetch_related('broadcast_periods') \
        .prefetch_related('broadcast_periods__recorded_programs') \
        .order_by('-updated_at')

    return {
        'total': await Series.all().count(),
        'series_list': series_list,
    }


@router.get(
    '/{series_id}',
    summary = 'シリーズ番組 API',
    response_description = 'シリーズ番組。',
    response_model = schemas.Series,
)
async def SeriesAPI(series_id: int):
    """
    指定されたシリーズ番組を取得する。
    """

    series = await Series.get_or_none(id=series_id) \
        .prefetch_related('broadcast_periods') \
        .prefetch_related('broadcast_periods__recorded_programs')
    if series is None:
        Logging.error(f'[SeriesRouter][SeriesAPI] Specified series_id was not found [series_id: {series_id}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified series_id was not found',
        )

    return series
