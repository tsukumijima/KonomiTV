
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Path
from fastapi import Query
from fastapi import status
from fastapi.responses import Response

from app.constants import QUALITY, QUALITY_TYPES
from app.models.RecordedProgram import RecordedProgram
from app.streams.VideoStream import VideoStream
from app.utils import Logging


# ルーター
router = APIRouter(
    tags = ['Streams'],
    prefix = '/api/streams/video',
)


async def ValidateVideoID(video_id: int = Path(..., description='録画番組の ID 。')) -> RecordedProgram:
    """ 録画番組 ID のバリデーション """
    recorded_program = await RecordedProgram.filter(id=video_id).get_or_none() \
        .select_related('recorded_video') \
        .select_related('channel')
    if recorded_program is None:
        Logging.error(f'[VideoStreamsRouter][ValidateVideoID] Specified video_id was not found [video_id: {video_id}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified video_id was not found',
        )
    return recorded_program


async def ValidateQuality(quality: str = Path(..., description='映像の品質。ex:1080p')) -> QUALITY_TYPES:
    """ 映像の品質のバリデーション """
    if quality not in QUALITY:
        Logging.error(f'[VideoStreamsRouter][ValidateQuality] Specified quality was not found [quality: {quality}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified quality was not found',
        )
    return quality


@router.get(
    '/{video_id}/{quality}/playlist',
    summary = '録画番組 HLS M3U8 プレイリスト API',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': '録画番組の HLS M3U8 プレイリスト。',
            'content': {'application/vnd.apple.mpegurl': {}},
        }
    }
)
async def VideoHLSPlaylistAPI(
    recorded_program: RecordedProgram = Depends(ValidateVideoID),
    quality: QUALITY_TYPES = Depends(ValidateQuality),
):
    """
    指定された画質に対応する、録画番組のストリーミング用 HLS M3U8 プレイリストを返す。<br>
    この M3U8 プレイリストは仮想的なもので、すべてのセグメントデータがエンコード済みとは限らない。セグメントはリクエストされ次第随時生成される。
    """

    video_stream = VideoStream(recorded_program, quality)
    virtual_playlist = await video_stream.getVirtualPlaylist()
    return Response(content=virtual_playlist, media_type='application/vnd.apple.mpegurl')


@router.get(
    '/{video_id}/{quality}/segment',
    summary = '録画番組 HLS セグメント API',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'HLS セグメントとして分割された MPEG-TS データ。',
            'content': {'video/mp2t': {}},
        }
    }
)
async def VideoHLSSegmentAPI(
    recorded_program: RecordedProgram = Depends(ValidateVideoID),
    quality: QUALITY_TYPES = Depends(ValidateQuality),
    sequence: int = Query(..., description='HLS セグメントの 0 スタートのシーケンス番号。'),
):
    """
    指定された画質に対応する、録画番組のストリーミング用 HLS セグメントを返す。<br>
    呼び出された時点でエンコードされていない場合は既存のエンコードタスクが終了され、<br>
    segment_index の HLS セグメントが含まれる範囲から新たにエンコードタスクが開始される。
    """

    # TODO: 適切な Cache-Control ヘッダーを返す

    video_stream = VideoStream(recorded_program, quality)
    encoded_segment_ts = await video_stream.getSegment(sequence)
    if encoded_segment_ts is None:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified sequence segment was not found',
        )
    return Response(content=encoded_segment_ts, media_type='video/mp2t')


@router.put(
    '/{video_id}/{quality}/keep-alive',
    summary = '録画番組 HLS Keep-Alive API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def VideoHLSKeepAliveAPI(
    recorded_program: RecordedProgram = Depends(ValidateVideoID),
    quality: QUALITY_TYPES = Depends(ValidateQuality),
):
    """
    録画番組のストリーミング用 HLS セグメントの生成を継続するための API 。<br>
    ストリーミングセッションを維持するために、この API は録画番組の視聴を続けている間、定期的に呼び出さなければならない。<br>
    この API が定期的に呼び出されなくなった場合、一定時間後にストリーミング用 HLS セグメントの生成が停止され、メモリ上のデータが破棄される。
    """

    video_stream = VideoStream(recorded_program, quality)
    video_stream.keepAlive()
