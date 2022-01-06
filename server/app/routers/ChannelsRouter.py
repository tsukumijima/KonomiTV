
import asyncio
import json
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
from tortoise import Tortoise
from typing import Optional

from app import schemas
from app.constants import CONFIG, LOGO_DIR
from app.models import Channels
from app.models import LiveStream
from app.utils import RunAsync
from app.utils.EDCB import EDCBUtil, CtrlCmdUtil
from app.utils import Jikkyo


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
    channels:Channels
    tasks.append(Channels.all().order_by('channel_number').order_by('remocon_id'))

    # データベースの生のコネクションを取得
    # 地デジ・BS・CS を合わせると 18000 件近くになる番組情報を SQLite かつ ORM で絞り込んで素早く取得するのは無理があるらしい
    # そこで、この部分だけは ORM の機能を使わず、直接クエリを叩いて取得する
    conn = Tortoise.get_connection('default')

    # 現在の番組情報を取得する
    ## 一度に取得した方がパフォーマンスが向上するため敢えてそうしている
    ## 24時間分しか取得しないのもパフォーマンスの関係で、24時間を超える番組は確認できる限り存在しないため実害はないと判断
    programs_present:dict
    tasks.append(conn.execute_query_dict(
        'SELECT * FROM "programs" WHERE "start_time"<=(?) AND "end_time">=(?) AND "end_time"<(?) ORDER BY "start_time" DESC',
        [
            now,  # 番組開始時刻が現在時刻以下
            now,  # 番組終了時刻が現在時刻以上
            now + timedelta(hours=24)  # 番組終了時刻が現在時刻から先24時間以内
        ]
    ))

    # 次の番組情報を取得する
    programs_following:dict
    tasks.append(conn.execute_query_dict(
        'SELECT * FROM "programs" WHERE "start_time">=(?) AND "end_time"<(?) ORDER BY "start_time" ASC',
        [
            now,  # 番組開始時刻が現在時刻以上
            now + timedelta(hours=24) # 番組終了時刻が現在時刻から先24時間以内
        ]
    ))

    # 並行して実行
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

        # 番組情報のリストからチャンネル ID が合致するものを探し、最初に見つけた値を返す
        def FilterProgram(programs, channel_id) -> Optional[dict]:
            for program in programs:
                if program['channel_id'] == channel_id:
                    return program
            return None  # 全部回したけど見つからなかった

        # 現在と次の番組情報をチャンネル ID で絞り込む
        # filter() はイテレータを返すので、list に変換する
        channel.program_present = FilterProgram(programs_present, channel.channel_id)
        channel.program_following = FilterProgram(programs_following, channel.channel_id)

        # JSON データで格納されているカラムをデコードする
        if channel.program_present is not None:
            channel.program_present['detail'] = json.loads(channel.program_present['detail'])
            channel.program_present['genre'] = json.loads(channel.program_present['genre'])
        if channel.program_following is not None:
            channel.program_following['detail'] = json.loads(channel.program_following['detail'])
            channel.program_following['genre'] = json.loads(channel.program_following['genre'])

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

    # NHK総合
    # ロゴが全国共通なので、チャンネル名の前方一致で決め打ち
    if channel.channel_type == 'GR' and channel.channel_name.startswith('NHK総合'):
        return FileResponse(LOGO_DIR / 'NID32736-SID1024.png', headers=header)

    # NHKEテレ
    # ロゴが全国共通なので、チャンネル名の前方一致で決め打ち
    if channel.channel_type == 'GR' and channel.channel_name.startswith('NHKEテレ'):
        return FileResponse(LOGO_DIR / 'NID32737-SID1032.png', headers=header)

    # 地デジでかつサブチャンネルのみ、メインチャンネルにロゴがあればそれを利用する
    if channel.channel_type == 'GR' and channel.is_subchannel is True:

        # メインチャンネルの情報を取得
        # ネットワーク ID が同じチャンネルのうち、一番サービス ID が若いチャンネルを探す
        main_channel = await Channels.filter(network_id=channel.network_id).order_by('service_id').first()

        # メインチャンネルが存在し、ロゴも存在する
        if main_channel is not None and pathlib.Path.exists(LOGO_DIR / f'{main_channel.id}.png'):
            return FileResponse(LOGO_DIR / f'{main_channel.id}.png', headers=header)

    # BS でかつサブチャンネルのみ、メインチャンネルにロゴがあればそれを利用する
    if channel.channel_type == 'BS' and channel.is_subchannel is True:

        # メインチャンネルのサービス ID を算出
        # NHKBS1 と NHKBSプレミアム だけ特別に、それ以外は一の位が1のサービス ID を算出
        if channel.service_id == 102:
            main_service_id = 101
        elif channel.service_id == 104:
            main_service_id = 103
        else:
            main_service_id = int(channel.channel_number[0:2] + '1')

        # メインチャンネルの情報を取得
        main_channel = await Channels.filter(network_id=channel.network_id, service_id=main_service_id).first()

        # メインチャンネルが存在し、ロゴも存在する
        if main_channel is not None and pathlib.Path.exists(LOGO_DIR / f'{main_channel.id}.png'):
            return FileResponse(LOGO_DIR / f'{main_channel.id}.png', headers=header)

    # ***** Mirakurun からロゴを取得 *****

    if CONFIG['general']['backend'] == 'Mirakurun':

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

    # ***** EDCB からロゴを取得 *****

    if CONFIG['general']['backend'] == 'EDCB':

        # CtrlCmdUtil を初期化
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
                # なるべく画質が良いロゴタイプのものを取得
                for logo_type in [5, 2, 4, 1, 3, 0]:
                    logo_name = EDCBUtil.getLogoFileNameFromDirectoryIndex(logo_dir_index, channel.network_id, logo_id, logo_type)
                    if logo_name is not None:
                        files = await edcb.sendFileCopy2(['LogoData\\' + logo_name]) or []
                        if len(files) == 1:
                            logo = files[0]['data']
                            logo_media_type = 'image/bmp' if logo_name.upper().endswith('.BMP') else 'image/png'
                        break

        # 取得したロゴデータを返す
        if logo is not None and len(logo) > 0:
            return Response(content=logo, media_type=logo_media_type, headers=header)

    # ***** デフォルトのロゴ画像を利用 *****

    # 同梱のロゴファイルも Mirakurun や EDCB からのロゴもない場合のみ
    return FileResponse(LOGO_DIR / 'default.png', headers=header)


@router.get(
    '/{channel_id}/jikkyo',
    summary = 'ニコニコ実況セッション情報 API',
    response_description = '',
)
async def ChannelJikkyoSessionAPI(
    channel_id:str = Path(..., description='チャンネル ID 。ex:gr011'),
):
    """
    チャンネルに紐づくニコニコ実況のセッション情報を取得する。
    """

    # チャンネル情報を取得
    channel = await Channels.filter(channel_id=channel_id).get_or_none()

    # 指定されたチャンネル ID が存在しない
    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Specified channel_id was not found',
        )

    # ニコニコ実況クライアントを初期化する
    jikkyo = Jikkyo(channel.network_id, channel.service_id)

    # ニコ生の視聴セッション情報を取得する
    # 今のところ値をそのまま返す
    return await jikkyo.fetchNicoLiveSession()
