
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
    summary = 'シリーズ情報一覧 API',
    response_description = 'シリーズ情報のリスト。',
    response_model = schemas.SeriesList,
)
async def SeriesListAPI():
    """
    すべてのシリーズ情報を取得する。
    """

    return await Series.all() \
        .prefetch_related('broadcast_periods') \
        .prefetch_related('broadcast_periods__recorded_programs') \
        .order_by('-updated_at')


@router.get(
    '/{series_id}',
    summary = 'シリーズ情報 API',
    response_description = 'シリーズ情報。',
    response_model = schemas.SeriesList,
)
async def SeriesAPI(series_id: int):
    """
    指定されたシリーズ情報を取得する。
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
