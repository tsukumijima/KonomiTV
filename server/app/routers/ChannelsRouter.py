
import asyncio
import pathlib
import requests
from datetime import timedelta
from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Path
from fastapi import status
from fastapi.responses import FileResponse
from fastapi.responses import Response
from tortoise import timezone

from app import schemas
from app.constants import CONFIG, LOGO_DIR
from app.models import Channels
from app.models import LiveStream
from app.models import Programs
from app.utils import RunAsync
from app.utils.EDCB import EDCBUtil, CtrlCmdUtil


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
    地デジ (GR)・BS・CS・SKY それぞれ全てのチャンネルの情報を取得する。
    """

    # 現在時刻
    now = timezone.now()

    # タスク
    tasks = list()

    # チャンネル情報を取得
    tasks.append(Channels.all().order_by('channel_number'))

    # 現在の番組情報を取得する
    ## 一度に取得した方がパフォーマンスが向上するため敢えてそうしている
    ## 13時間分しか取得しないのもパフォーマンスの関係 当然 13 時間を超える番組は表示できなくなるが、
    ## そもそも 13 時間を超える番組はデータ放送やショップチャンネル垂れ流しの CATV くらいなので実害はないと判断
    ## 24時間分取得するときよりも 100ms ほど短縮される
    tasks.append(Programs.all().filter(
        start_time__lte = now,  # 番組開始時刻が現在時刻以下
        end_time__gte = now,  # 番組終了時刻が現在時刻以上
        end_time__lt = now + timedelta(hours=13),  # 番組終了時刻が(現在時刻 + 13時間)より前
    ).order_by('-start_time'))

    # 次の番組情報を取得する
    tasks.append(Programs.all().filter(
        start_time__gte = now,  # 番組開始時刻が現在時刻以上
        end_time__lt = now + timedelta(hours=13),  # 番組終了時刻が(現在時刻 + 13時間)より前
    ).order_by('start_time'))

    # 並行実行
    channels, programs_present, programs_following = await asyncio.gather(*tasks)

    # レスポンスの雛形
    result = {
        'GR': list(),
        'BS': list(),
        'CS': list(),
        'SKY': list(),
    }

    # チャンネルごとに実行
    for channel in channels:

        # チャンネル ID で絞り込む
        program_present = list(filter(lambda temp: temp.channel_id == channel.channel_id, programs_present))
        program_following = list(filter(lambda temp: temp.channel_id == channel.channel_id, programs_following))

        # 要素が 0 個以上であれば
        channel.program_present = program_present[0] if len(program_present) > 0 else None
        channel.program_following = program_following[0] if len(program_following) > 0 else None

        # サブチャンネルでかつ現在の番組情報が両方存在しないなら、表示フラグを False に設定
        # 現在放送されているサブチャンネルのみをチャンネルリストに表示するような挙動とする
        # 一般的にサブチャンネルは常に放送されているわけではないため、放送されていない時にチャンネルリストに表示する必要はない
        if channel.is_subchannel is True and channel.program_present is None:
            channel.is_display = False

        # 現在の視聴者数を取得
        channel.viewers = LiveStream.getViewers(channel.channel_id)

        # チャンネルタイプで分類
        result[channel.channel_type].append(channel)

    # チャンネルタイプごとに返却
    return result


@router.get(
    '/{channel_id}',
    summary = 'チャンネル情報 API',
    response_description = 'チャンネル情報。',
    response_model = schemas.Channel,
)
async def ChannelAPI(
    channel_id:str = Path(..., description='チャンネル ID 。ex:gr011'),
):
    """
    チャンネルの情報を取得する。
    """

    # チャンネル情報を取得
    channel = await Channels.filter(channel_id=channel_id).get_or_none()

    # 指定されたチャンネル ID が存在しない
    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Specified channel_id was not found',
        )

    # 現在と次の番組情報を取得
    channel.program_present, channel.program_following = await channel.getCurrentAndNextProgram()

    # サブチャンネルでかつ現在の番組情報が両方存在しないなら、表示フラグを False に設定
    # 現在放送されているサブチャンネルのみをチャンネルリストに表示するような挙動とする
    # 一般的にサブチャンネルは常に放送されているわけではないため、放送されていない時にチャンネルリストに表示する必要はない
    if channel.is_subchannel is True and channel.program_present is None:
        channel.is_display = False

    # 現在の視聴者数を取得
    channel.viewers = LiveStream.getViewers(channel.channel_id)

    # チャンネル情報を返却
    return channel


@router.get(
    '/{channel_id}/logo',
    summary = 'チャンネルロゴ API',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'チャンネルロゴ。',
            'content': {'image/png': {}}
        }
    }
)
async def ChannelLogoAPI(
    channel_id:str = Path(..., description='チャンネル ID 。ex:gr011'),
):
    """
    チャンネルのロゴを取得する。
    """

    # チャンネル情報を取得
    channel = await Channels.filter(channel_id=channel_id).get_or_none()

    # 指定されたチャンネル ID が存在しない
    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Specified channel_id was not found',
        )

    # ブラウザにキャッシュしてもらえるようにヘッダーを設定
	# ref: https://qiita.com/yuuuking/items/4f11ccfc822f4c198ab0
    header = {
        'Cache-Control': 'public, max-age=2592000',  # 30日間
    }

    # ***** 同梱のロゴを利用（存在する場合）*****

    # 放送波から取得できるロゴはどっちみち画質が悪いし、取得できていないケースもありうる
    # そのため、同梱されているロゴがあればそれを返すようにする
    # ロゴは NID32736-SID1024.png のようなファイル名の PNG ファイル (256x256) を想定
    if pathlib.Path.exists(LOGO_DIR / f'{channel.id}.png'):
        return FileResponse(LOGO_DIR / f'{channel.id}.png', headers=header)

    if CONFIG['general']['backend'] == 'EDCB':
        edcb = CtrlCmdUtil()
        edcb.setNWSetting(CONFIG['general']['edcb_host'], CONFIG['general']['edcb_port'])

        # EDCB の LogoData フォルダからロゴを取得
        logo = None
        files = await edcb.sendFileCopy2(['LogoData.ini', 'LogoData\\*.*']) or []
        if len(files) == 2:
            logo_data_ini = EDCBUtil.convertBytesToString(files[0]['data'])
            logo_dir_index = EDCBUtil.convertBytesToString(files[1]['data'])
            logo_id = EDCBUtil.getLogoIDFromLogoDataIni(logo_data_ini, channel.network_id, channel.service_id)
            if logo_id >= 0:
                # なるべく良いロゴタイプのものを取得
                for logo_type in [5, 2, 4, 1, 3, 0]:
                    logo_name = EDCBUtil.getLogoFileNameFromDirectoryIndex(logo_dir_index, channel.network_id, logo_id, logo_type)
                    if logo_name is not None:
                        files = await edcb.sendFileCopy2(['LogoData\\' + logo_name]) or []
                        if len(files) == 1:
                            logo = files[0]['data']
                            logo_media_type = 'image/bmp' if logo_name.upper().endswith('.BMP') else 'image/png'
                        break

        if logo is not None and len(logo) > 0:
            return Response(content = logo, media_type = logo_media_type, headers = header)

        return FileResponse(LOGO_DIR / 'default.png', headers = header)

    # ***** Mirakurun からロゴを取得 *****

    # Mirakurun 形式のサービス ID
    # NID と SID を 5 桁でゼロ埋めした上で int に変換する
    mirakurun_service_id = int(str(channel.network_id).zfill(5) + str(channel.service_id).zfill(5))

    # Mirakurun の API からロゴを取得する
    # 同梱のロゴが存在しない場合のみ
    mirakurun_logo_api_url = f'{CONFIG["general"]["mirakurun_url"]}/api/services/{mirakurun_service_id}/logo'
    mirakurun_logo_api_response:requests.Response = await RunAsync(requests.get, mirakurun_logo_api_url)

    # ステータスコードが 200 であれば
    # ステータスコードが 503 の場合はロゴデータが存在しない
    if mirakurun_logo_api_response.status_code == 200:

        # 取得したロゴデータを返す
        mirakurun_logo = mirakurun_logo_api_response.content
        return Response(content=mirakurun_logo, media_type='image/png', headers=header)

    # ***** デフォルトのロゴ画像を利用 *****

    # 同梱のロゴファイルも Mirakurun のロゴもない場合のみ
    return FileResponse(LOGO_DIR / 'default.png', headers=header)
