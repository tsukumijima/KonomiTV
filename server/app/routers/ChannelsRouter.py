
import asyncio
import json
import pathlib
import requests
from datetime import timedelta
from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Path
from fastapi import Request
from fastapi import status
from fastapi.responses import FileResponse
from fastapi.responses import Response
from fastapi.security.utils import get_authorization_scheme_param
from tortoise import connections
from tortoise import timezone
from typing import Dict, List

from app import schemas
from app.constants import API_REQUEST_HEADERS, CONFIG, LOGO_DIR
from app.models import Channel
from app.models import LiveStream
from app.models import User
from app.utils.EDCB import CtrlCmdUtil
from app.utils.EDCB import EDCBUtil
from app.utils import Jikkyo


# ルーター
router = APIRouter(
    tags = ['Channels'],
    prefix = '/api/channels',
)


@router.get(
    '',
    summary = 'チャンネル情報一覧 API',
    response_description = 'チャンネル情報。',
)
async def ChannelsAPI():
    """
    地デジ (GR)・BS・CS・CATV・SKY (SPHD)・STARDIGIO それぞれ全てのチャンネルの情報を取得する。<br>
    パフォーマンス向上のために response_model はあえて設定していないが（設定すると 100~300ms ほど遅くなる）、Channel レスポンスを返す。
    """

    # 現在時刻
    now = timezone.now()

    # タスク
    tasks = []

    # チャンネル情報を取得
    channels: List[Channel]
    tasks.append(Channel.all().order_by('channel_number').order_by('remocon_id'))

    # データベースの生のコネクションを取得
    # 地デジ・BS・CS を合わせると 18000 件近くになる番組情報を SQLite かつ ORM で絞り込んで素早く取得するのは無理があるらしい
    # そこで、この部分だけは ORM の機能を使わず、直接クエリを叩いて取得する
    connection = connections.get('default')

    # 現在と次の番組情報を取得する
    ## 一度に取得した方がパフォーマンスが向上するため敢えてそうしている
    ## SQL 文の時間比較は、左にいくほど時刻が小さく、右にいくほど時刻が大きくなるように統一している
    ## 番組時間は EPG の仕様上必ず24時間以下に収まるので、パフォーマンスを考慮して24時間以内に放送開始予定の番組のみに絞り込む
    pf_programs: List[Dict]
    tasks.append(connection.execute_query_dict(
        """
        SELECT *
        FROM (
            SELECT
                -- チャンネル ID ごとに番組開始時刻が小さい順でランクを付け、program_order フィールドにセット
                DENSE_RANK() OVER (PARTITION BY channel_id ORDER BY start_time ASC) program_order,
                -- 番組開始時刻が現在時刻よりも前（=放送中）なら true 、そうでないなら false を is_present フィールドにセット
                CASE WHEN "start_time" <= (?) THEN true ELSE false END AS is_present,
                *
            FROM
                "programs"
            WHERE
                -- 現在放送中の番組 (start_time <= now <= end_time)
                ("start_time" <= (?) AND (?) <= "end_time")
                OR
                -- 24時間以内に放送開始予定の番組 (now <= start_time <= (now + 24h))
                ((?) <= "start_time" AND "start_time" <= (?))
        ) WHERE
            -- program_order が 1,2 の番組情報だけを取得
            program_order <= 2
        """,
        [
            now,
            now, now,  # 現在放送中の番組
            now, now + timedelta(hours=24),  # 24時間以内に放送開始予定の番組
        ],
    ))

    # 並行して実行
    channels, pf_programs = await asyncio.gather(*tasks)

    # レスポンスの雛形
    result = {
        'GR': [],
        'BS': [],
        'CS': [],
        'CATV': [],
        'SKY': [],
        'STARDIGIO': [],
    }

    # チャンネルごとに実行
    for channel in channels:

        # チャンネル情報の辞書を作成
        ## クラスそのままだとレスポンスを返す際にシリアライズ処理が入る関係でパフォーマンスが悪い
        channel_dict = {
            'id': channel.id,
            'network_id': channel.network_id,
            'service_id': channel.service_id,
            'transport_stream_id': channel.transport_stream_id,
            'remocon_id': channel.remocon_id,
            'channel_id': channel.channel_id,
            'channel_number': channel.channel_number,
            'channel_name': channel.channel_name,
            'channel_type': channel.channel_type,
            'channel_force': channel.channel_force,
            'channel_comment': channel.channel_comment,
            'is_subchannel': channel.is_subchannel,
            'is_radiochannel': channel.is_radiochannel,
            'is_display': True,
            'viewers': 0,
            'program_present': None,
            'program_following': None,
        }

        # チャンネルに紐づく現在と次の番組情報を取得
        pf_program: List[Dict] = list(filter(lambda pf_program: pf_program['channel_id'] == channel_dict['channel_id'], pf_programs))

        # 番組情報が1つ以上取得できていれば
        if len(pf_program) >= 1:

            # 番組情報が1つしか取得できておらず、現在放送中の番組情報のみの場合
            ## 基本的にはまず起こり得ないと思うけど…（そのチャンネルが放送終了とかでもないかぎり）
            if len(pf_program) == 1 and bool(pf_program[0]['is_present']) is True:

                # program_present には取れた現在放送中の番組情報をそのままセットし、program_following には何もセットしない
                channel_dict['program_present'] = pf_program[0]

            # 番組情報が1つしか取得できておらず、次以降の番組情報のみの場合
            ## たまにしか運用されないサブチャンネルで発生しやすい
            elif len(pf_program) == 1 and bool(pf_program[0]['is_present']) is False:

                # program_present には何もセットせず、program_following には取れた次の番組情報をそのままセットする
                channel_dict['program_following'] = pf_program[0]

            # 番組情報が2つ取得できているが、いずれも現在放送中の番組情報の場合
            ## 万が一 DB に放送時刻が重複する番組が登録されていた場合に発生する
            elif len(pf_program) == 2 and bool(pf_program[0]['is_present']) is True and bool(pf_program[1]['is_present']) is True:

                # program_present にはとりあえず最初の番組情報をセットし、program_following には何もセットしない
                channel_dict['program_present'] = pf_program[0]

            # 番組情報が2つ取得できているが、いずれも次以降の番組情報の場合
            ## 放送休止中やサブチャンネルなどで発生する
            elif len(pf_program) == 2 and bool(pf_program[0]['is_present']) is False and bool(pf_program[1]['is_present']) is False:

                # program_present には何もセットせず、program_following には program_order が 1 になっている方 (=より現在時刻に近い) をセットする
                if bool(pf_program[0]['program_order']) == 1:
                    channel_dict['program_following'] = pf_program[0]
                elif bool(pf_program[1]['program_order']) == 1:
                    channel_dict['program_following'] = pf_program[1]

            # それ以外 (番組情報が2つ取得できていて、どちらかが現在放送中でどちらかが次の番組情報の場合)
            else:

                # 現在放送中の番組情報を program_present にセット
                if bool(pf_program[0]['is_present']) is True:
                    channel_dict['program_present'] = pf_program[0]
                elif bool(pf_program[1]['is_present']) is True:
                    channel_dict['program_present'] = pf_program[1]

                # 次の番組情報を program_following にセット
                if bool(pf_program[0]['is_present']) is False:
                    channel_dict['program_following'] = pf_program[0]
                elif bool(pf_program[1]['is_present']) is False:
                    channel_dict['program_following'] = pf_program[1]

            # JSON データで格納されているカラムをデコードする
            ## ついでに SQL 文で設定した is_present / program_order フィールドを削除
            ## 現在の番組か次の番組かを判定するために使っているフィールドだが、もう判定は終わったので必要ない
            if channel_dict['program_present'] is not None:
                channel_dict['program_present']['detail'] = json.loads(channel_dict['program_present']['detail'])
                channel_dict['program_present']['genre'] = json.loads(channel_dict['program_present']['genre'])
                channel_dict['program_present'].pop('is_present')
                channel_dict['program_present'].pop('program_order')
            if channel_dict['program_following'] is not None:
                channel_dict['program_following']['detail'] = json.loads(channel_dict['program_following']['detail'])
                channel_dict['program_following']['genre'] = json.loads(channel_dict['program_following']['genre'])
                channel_dict['program_following'].pop('is_present')
                channel_dict['program_following'].pop('program_order')

        # サブチャンネル & 現在の番組情報が存在しないなら、表示フラグを False に設定
        ## 現在放送中のサブチャンネルのみをチャンネルリストに表示するような挙動とする
        ## 一般的にサブチャンネルは常に放送されているわけではないため、放送されていない時にチャンネルリストに表示する必要はない
        if channel_dict['is_subchannel'] is True and channel_dict['program_present'] is None:
            channel_dict['is_display'] = False

        # 現在の視聴者数を取得
        channel_dict['viewers'] = LiveStream.getViewers(channel_dict['channel_id'])

        # せっかくチャンネルごとにループで回しているので、ここでチャンネルタイプごとの分類もやっておく
        ## 後から filter() で絞り込むのだと効率が悪い
        result[channel_dict['channel_type']].append(channel_dict)

    return result


@router.get(
    '/{channel_id}',
    summary = 'チャンネル情報 API',
    response_description = 'チャンネル情報。',
    response_model = schemas.Channel,
)
async def ChannelAPI(
    channel_id: str = Path(..., description='チャンネル ID 。ex:gr011'),
):
    """
    チャンネルの情報を取得する。
    """

    # チャンネル情報を取得
    channel = await Channel.filter(channel_id=channel_id).get_or_none()

    # 指定されたチャンネル ID が存在しない
    if channel is None:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified channel_id was not found',
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
            'content': {'image/png': {}},
        }
    }
)
async def ChannelLogoAPI(
    channel_id: str = Path(..., description='チャンネル ID 。ex:gr011'),
):
    """
    チャンネルのロゴを取得する。
    """

    # チャンネル情報を取得
    channel = await Channel.filter(channel_id=channel_id).get_or_none()

    # 指定されたチャンネル ID が存在しない
    if channel is None:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified channel_id was not found',
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
    if await asyncio.to_thread(pathlib.Path.exists, LOGO_DIR / f'{channel.id}.png'):
        return FileResponse(LOGO_DIR / f'{channel.id}.png', headers=header)

    # ***** ロゴが全国共通なので、チャンネル名の前方一致で決め打ち *****

    # NHK総合
    if channel.channel_type == 'GR' and channel.channel_name.startswith('NHK総合'):
        return FileResponse(LOGO_DIR / 'NID32736-SID1024.png', headers=header)

    # NHKEテレ
    if channel.channel_type == 'GR' and channel.channel_name.startswith('NHKEテレ'):
        return FileResponse(LOGO_DIR / 'NID32737-SID1032.png', headers=header)

    # 複数の地域で放送しているケーブルテレビの場合、コミュニティチャンネルの NID と SID は地域ごとに異なる
    # ref: https://youzaka.hatenablog.com/entry/2013/06/30/154243

    # J:COMテレビ
    if channel.channel_type == 'GR' and channel.channel_name.startswith('J:COMテレビ'):
        return FileResponse(LOGO_DIR / 'NID32397-SID23656.png', headers=header)

    # J:COMチャンネル
    if channel.channel_type == 'GR' and channel.channel_name.startswith('J:COMチャンネル'):
        return FileResponse(LOGO_DIR / 'NID32399-SID23672.png', headers=header)

    # eo光チャンネル
    if channel.channel_type == 'GR' and channel.channel_name.startswith('eo光チャンネル'):
        return FileResponse(LOGO_DIR / 'NID32127-SID41080.png', headers=header)

    # ZTV
    if channel.channel_type == 'GR' and channel.channel_name.startswith('ZTV'):
        return FileResponse(LOGO_DIR / 'NID32047-SID46200.png', headers=header)

    # スターデジオ
    # 本来は局ロゴは存在しないが、見栄えが悪いので 100 チャンネルすべてで同じ局ロゴを表示する
    if channel.channel_type == 'STARDIGIO':
        return FileResponse(LOGO_DIR / 'NID1-SID400.png', headers=header)

    # ***** サブチャンネルのロゴを取得 *****

    # 地デジでかつサブチャンネルのみ、メインチャンネルにロゴがあればそれを利用する
    if channel.channel_type == 'GR' and channel.is_subchannel is True:

        # メインチャンネルの情報を取得
        # ネットワーク ID が同じチャンネルのうち、一番サービス ID が若いチャンネルを探す
        main_channel = await Channel.filter(network_id=channel.network_id).order_by('service_id').first()

        # メインチャンネルが存在し、ロゴも存在する
        if main_channel is not None and await asyncio.to_thread(pathlib.Path.exists, LOGO_DIR / f'{main_channel.id}.png'):
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
        main_channel = await Channel.filter(network_id=channel.network_id, service_id=main_service_id).first()

        # メインチャンネルが存在し、ロゴも存在する
        if main_channel is not None and await asyncio.to_thread(pathlib.Path.exists, LOGO_DIR / f'{main_channel.id}.png'):
            return FileResponse(LOGO_DIR / f'{main_channel.id}.png', headers=header)

    # ***** Mirakurun からロゴを取得 *****

    if CONFIG['general']['backend'] == 'Mirakurun':

        # Mirakurun 形式のサービス ID
        # NID と SID を 5 桁でゼロ埋めした上で int に変換する
        mirakurun_service_id = int(str(channel.network_id).zfill(5) + str(channel.service_id).zfill(5))

        # Mirakurun の API からロゴを取得する
        # 同梱のロゴが存在しない場合のみ
        try:
            mirakurun_logo_api_url = f'{CONFIG["general"]["mirakurun_url"]}/api/services/{mirakurun_service_id}/logo'
            mirakurun_logo_api_response = await asyncio.to_thread(requests.get,
                url = mirakurun_logo_api_url,
                headers = API_REQUEST_HEADERS,
                timeout = 3,
            )

            # ステータスコードが 200 であれば
            # ステータスコードが 503 の場合はロゴデータが存在しない
            if mirakurun_logo_api_response.status_code == 200:

                # 取得したロゴデータを返す
                mirakurun_logo = mirakurun_logo_api_response.content
                return Response(content=mirakurun_logo, media_type='image/png', headers=header)

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            pass  # 特にエラーは吐かず、デフォルトのロゴ画像を利用させる

    # ***** EDCB からロゴを取得 *****

    if CONFIG['general']['backend'] == 'EDCB':

        # CtrlCmdUtil を初期化
        edcb = CtrlCmdUtil()
        edcb.setConnectTimeOutSec(3)  # 3秒後にタイムアウト

        # EDCB の LogoData フォルダからロゴを取得
        logo = None
        logo_media_type = 'image/png'
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
    response_description = 'ニコニコ実況のセッション情報。',
    response_model = schemas.JikkyoSession,
)
async def ChannelJikkyoSessionAPI(
    request: Request,
    channel_id: str = Path(..., description='チャンネル ID 。ex:gr011'),
):
    """
    チャンネルに紐づくニコニコ実況のセッション情報を取得する。
    """

    # チャンネル情報を取得
    channel = await Channel.filter(channel_id=channel_id).get_or_none()

    # 指定されたチャンネル ID が存在しない
    if channel is None:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified channel_id was not found',
        )

    current_user = None

    # もし Authorization ヘッダーがあるなら、ログイン中のユーザーアカウントを取得する
    if request.headers.get('Authorization') is not None:

        # JWT アクセストークンを取得
        _, user_access_token = get_authorization_scheme_param(request.headers.get('Authorization'))

        # アクセストークンに紐づくユーザーアカウントを取得
        ## もともとバリデーション用なので HTTPException が送出されるが、ここではエラーにする必要はないのでパス
        try:
            current_user = await User.getCurrentUser(token=user_access_token)
        except HTTPException:
            pass

    # ニコニコ実況クライアントを初期化する
    jikkyo = Jikkyo(channel.network_id, channel.service_id)

    # ニコニコ実況（ニコ生）のセッション情報を取得する
    # 取得してきた値をそのまま返す
    return await jikkyo.fetchJikkyoSession(current_user)
