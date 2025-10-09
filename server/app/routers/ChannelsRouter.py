
import asyncio
import hashlib
import json
from datetime import datetime, timedelta
from typing import Annotated, Any
from zoneinfo import ZoneInfo

import anyio
import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.security.utils import get_authorization_scheme_param
from tortoise import connections

from app import logging, schemas
from app.config import Config
from app.constants import HTTPX_CLIENT, LOGO_DIR, VERSION
from app.models.Channel import Channel
from app.routers.UsersRouter import GetCurrentUser
from app.streams.LiveStream import LiveStream
from app.utils import GetMirakurunAPIEndpointURL
from app.utils.edcb.CtrlCmdUtil import CtrlCmdUtil
from app.utils.edcb.EDCBUtil import EDCBUtil
from app.utils.JikkyoClient import JikkyoClient


# ルーター
router = APIRouter(
    tags = ['Channels'],
    prefix = '/api/channels',
)


async def GetChannel(channel_id: Annotated[str, Path(description='チャンネル ID (id or display_channel_id) 。ex: NID32736-SID1024, gr011')]) -> Channel:
    """ チャンネル ID (id or display_channel_id) からチャンネル情報を取得する """

    # チャンネル ID が存在するか確認
    ## display_channel_id ではなく通常の id が指定されている場合は、そのまま id からチャンネル情報を取得する
    if 'NID' in channel_id and 'SID' in channel_id:
        channel = await Channel.filter(id=channel_id).get_or_none()
    else:
        channel = await Channel.filter(display_channel_id=channel_id).get_or_none()
    if channel is None:
        logging.error(f'[ChannelsRouter][GetChannel] Specified display_channel_id was not found. [display_channel_id: {channel_id}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified display_channel_id was not found',
        )

    return channel


@router.get(
    '',
    summary = 'チャンネル情報一覧 API',
    response_description = 'チャンネル情報。',
    response_model = schemas.LiveChannels,
)
async def ChannelsAPI():
    """
    地デジ (GR)・BS・CS・CATV・SKY (SPHD)・BS4K それぞれ全てのチャンネルの情報を取得する。
    """

    # 現在時刻
    now = datetime.now(ZoneInfo('Asia/Tokyo'))

    # タスク
    tasks = []

    # チャンネル情報を取得
    channels: list[Channel]
    tasks.append(Channel.filter(is_watchable=True).order_by('channel_number').order_by('remocon_id'))

    # データベースの生のコネクションを取得
    # 地デジ・BS・CS を合わせると 18000 件近くになる番組情報を SQLite かつ ORM で絞り込んで素早く取得するのは無理があるらしい
    # そこで、この部分だけは ORM の機能を使わず、直接クエリを叩いて取得する
    connection = connections.get('default')

    # 現在と次の番組情報を取得する
    ## 一度に取得した方がパフォーマンスが向上するため敢えてそうしている
    ## SQL 文の時間比較は、左にいくほど時刻が小さく、右にいくほど時刻が大きくなるように統一している
    ## 番組時間は EPG の仕様上必ず24時間以下に収まるので、パフォーマンスを考慮して24時間以内に放送開始予定の番組のみに絞り込む
    pf_programs: list[dict[str, Any]]
    tasks.append(connection.execute_query_dict(
        """
        SELECT *
        FROM (
            SELECT
                -- チャンネル ID (ex: NID32736-SID1024) ごとに番組開始時刻が小さい順でランクを付け、program_order フィールドにセット
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
        'BS4K': [],
    }

    # チャンネルごとに実行
    for channel in channels:

        # チャンネル情報の辞書を作成
        ## クラスそのままだとレスポンスを返す際にシリアライズ処理が入る関係でパフォーマンスが悪い
        channel_dict: dict[str, Any] = {
            'id': channel.id,
            'display_channel_id': channel.display_channel_id,
            'network_id': channel.network_id,
            'service_id': channel.service_id,
            'transport_stream_id': channel.transport_stream_id,
            'remocon_id': channel.remocon_id,
            'channel_number': channel.channel_number,
            'type': channel.type,
            'name': channel.name,
            'jikkyo_force': channel.jikkyo_force,
            'is_subchannel': channel.is_subchannel,
            'is_radiochannel': channel.is_radiochannel,
            'is_watchable': True,
            'is_display': True,
            'viewer_count': 0,
            'program_present': None,
            'program_following': None,
        }

        # チャンネルに紐づく現在と次の番組情報を取得
        pf_program: list[dict[str, Any]] = list(filter(lambda pf_program:
            pf_program['network_id'] == channel_dict['network_id'] and
            pf_program['service_id'] == channel_dict['service_id'],
        pf_programs))

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
            ## あとなぜか DateTime 型の文字列値が正しい ISO8601 フォーマットになっていないので、ここで整形する
            ## 真偽値も SQLite では 0/1 で管理されているため、bool 型に変換する
            if channel_dict['program_present'] is not None:
                channel_dict['program_present']['detail'] = json.loads(channel_dict['program_present']['detail'])
                channel_dict['program_present']['start_time'] = channel_dict['program_present']['start_time'].replace(' ', 'T')
                channel_dict['program_present']['end_time'] = channel_dict['program_present']['end_time'].replace(' ', 'T')
                channel_dict['program_present']['is_free'] = bool(channel_dict['program_present']['is_free'])
                channel_dict['program_present']['genres'] = json.loads(channel_dict['program_present']['genres'])
                channel_dict['program_present'].pop('is_present')
                channel_dict['program_present'].pop('program_order')
            if channel_dict['program_following'] is not None:
                channel_dict['program_following']['detail'] = json.loads(channel_dict['program_following']['detail'])
                channel_dict['program_following']['start_time'] = channel_dict['program_following']['start_time'].replace(' ', 'T')
                channel_dict['program_following']['end_time'] = channel_dict['program_following']['end_time'].replace(' ', 'T')
                channel_dict['program_following']['is_free'] = bool(channel_dict['program_following']['is_free'])
                channel_dict['program_following']['genres'] = json.loads(channel_dict['program_following']['genres'])
                channel_dict['program_following'].pop('is_present')
                channel_dict['program_following'].pop('program_order')

        # サブチャンネル & 現在の番組情報が存在しないなら、表示フラグを False に設定
        ## 現在放送中のサブチャンネルのみをチャンネルリストに表示するような挙動とする
        ## 一般的にサブチャンネルは常に放送されているわけではないため、放送されていない時にチャンネルリストに表示する必要はない
        if channel_dict['is_subchannel'] is True and channel_dict['program_present'] is None:
            channel_dict['is_display'] = False

        # 現在の視聴者数を取得
        channel_dict['viewer_count'] = LiveStream.getViewerCount(channel_dict['display_channel_id'])

        # せっかくチャンネルごとにループで回しているので、ここでチャンネルタイプごとの分類もやっておく
        ## 後から filter() で絞り込むのだと効率が悪い
        result[channel_dict['type']].append(channel_dict)

    # JSONResponse を直接返すことで、通常自動的に行われる重いバリデーションや整形処理を回避できる
    ## チャンネル情報は情報量が多くすべてのチャンネルに対してバリデーションを行うと重くなるため、検証をスキップしてパフォーマンスを向上させる
    return JSONResponse(result)


@router.get(
    '/{channel_id}',
    summary = 'チャンネル情報 API',
    response_description = 'チャンネル情報。',
    response_model = schemas.LiveChannel,
)
async def ChannelAPI(
    channel: Annotated[Channel, Depends(GetChannel)],
):
    """
    指定されたチャンネルの情報を取得する。
    """

    # 現在と次の番組情報を取得
    channel.program_present, channel.program_following = await channel.getCurrentAndNextProgram()

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
    request: Request,
    channel_id: Annotated[str, Path(description='チャンネル ID (id or display_channel_id) 。ex: NID32736-SID1024, gr011')],
):
    """
    指定されたチャンネルに紐づくロゴを取得する。
    """

    async def GetLogoFilePath(channel: Channel) -> anyio.Path | None:
        """ 同梱されているロゴの中からチャンネルに対応するロゴファイルのパスを取得する """

        # 放送波から取得できるロゴはどっちみち画質が悪いし、取得できていないケースもありうる
        # そのため、同梱されているロゴがあればそれを返すようにする
        ## ロゴは NID32736-SID1024.png のようなファイル名の PNG ファイル (256x256) を想定
        logo_dir = anyio.Path(str(LOGO_DIR))
        if await (logo_dir /f'{channel.id}.png').exists():
            return logo_dir / f'{channel.id}.png'

        # ***** ロゴが全国共通なので、チャンネル名の前方一致で決め打ち *****

        # NHK総合
        if channel.type == 'GR' and channel.name.startswith('NHK総合'):
            return logo_dir / 'NID32736-SID1024.png'

        # NHKEテレ
        if channel.type == 'GR' and channel.name.startswith('NHKEテレ'):
            return logo_dir / 'NID32737-SID1032.png'

        # 複数の地域で放送しているケーブルテレビの場合、コミュニティチャンネル (自主放送) の NID と SID は地域ごとに異なる
        # さらにコミュニティチャンネルの NID-SID は CATV 間で稀に重複していることがあるため、チャンネル名から決め打ちで判定する
        ## ref: https://youzaka.hatenablog.com/entry/2013/06/30/154243

        # J:COMテレビ
        if channel.type == 'GR' and channel.name.startswith('J:COMテレビ'):
            return logo_dir / 'community-channels/J：COMテレビ.png'

        # J:COMチャンネル
        if channel.type == 'GR' and channel.name.startswith('J:COMチャンネル'):
            return logo_dir / 'community-channels/J：COMチャンネル.png'

        # イッツコムch10
        if channel.type == 'GR' and channel.name.startswith('イッツコムch10'):
            return logo_dir / 'community-channels/イッツコムch10.png'

        # イッツコムch11
        if channel.type == 'GR' and channel.name.startswith('イッツコムch11'):
            return logo_dir / 'community-channels/イッツコムch11.png'

        # スカパー！ナビ1
        if channel.type == 'GR' and channel.name.startswith('スカパー！ナビ1'):
            return logo_dir / 'community-channels/スカパー！ナビ1.png'

        # スカパー！ナビ2
        if channel.type == 'GR' and channel.name.startswith('スカパー！ナビ2'):
            return logo_dir / 'community-channels/スカパー！ナビ2.png'

        # eo光チャンネル
        if channel.type == 'GR' and channel.name.startswith('eo光チャンネル'):
            return logo_dir / 'community-channels/eo光チャンネル.png'

        # ZTV
        if channel.type == 'GR' and channel.name.startswith('ZTV'):
            return logo_dir / 'community-channels/ZTV.png'

        # BaycomCH
        if channel.type == 'GR' and channel.name.startswith('BaycomCH'):
            return logo_dir / 'community-channels/BaycomCH.png'

        # ベイコム12CH
        if channel.type == 'GR' and channel.name.startswith('ベイコム12CH'):
            return logo_dir / 'community-channels/ベイコム12CH.png'

        # スターデジオ
        ## 本来は局ロゴは存在しないが、見栄えが悪いので 100 チャンネルすべてで同じ局ロゴを表示する
        if channel.type == 'SKY' and 400 <= channel.service_id <= 499:
            return logo_dir / 'NID1-SID400.png'

        # ***** サブチャンネルのロゴを取得 *****

        # 地デジでかつサブチャンネルのみ、メインチャンネルにロゴがあればそれを利用する
        if channel.type == 'GR' and channel.is_subchannel is True:

            # メインチャンネルの情報を取得
            # ネットワーク ID が同じチャンネルのうち、一番サービス ID が若いチャンネルを探す
            main_channel = await Channel.filter(network_id=channel.network_id).order_by('service_id').first()

            # メインチャンネルが存在し、ロゴも存在する
            if main_channel is not None and await (logo_dir / f'{main_channel.id}.png').exists():
                return logo_dir / f'{main_channel.id}.png'

        # BS でかつサブチャンネルのみ、メインチャンネルにロゴがあればそれを利用する
        if channel.type == 'BS' and channel.is_subchannel is True:

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
            if main_channel is not None and await (logo_dir / f'{main_channel.id}.png').exists():
                return logo_dir / f'{main_channel.id}.png'

        return None

    async def GetFallbackLogoData(channel: Channel) -> tuple[bytes, str] | None:
        """ フォールバックとして EDCB または Mirakurun からロゴデータと MIME タイプを取得する """

        # EDCB バックエンドの場合
        if Config().general.backend == 'EDCB':

            # CtrlCmdUtil を初期化
            edcb = CtrlCmdUtil()
            edcb.setConnectTimeOutSec(5)  # 5秒後にタイムアウト

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
                return (logo, logo_media_type)

        # Mirakurun バックエンドの場合
        elif Config().general.backend == 'Mirakurun':

            # Mirakurun 形式のサービス ID
            # NID と SID を 5 桁でゼロ埋めした上で int に変換する
            mirakurun_service_id = int(str(channel.network_id).zfill(5) + str(channel.service_id).zfill(5))

            # 同梱のロゴが存在しない場合のみ、Mirakurun の API からロゴを取得する
            ## mirakc においては、ユーザーが mirakc にロゴを手動設定している場合のみ局ロゴを取得できる
            try:
                mirakurun_logo_api_url = GetMirakurunAPIEndpointURL(f'/api/services/{mirakurun_service_id}/logo')
                async with HTTPX_CLIENT() as client:
                    mirakurun_logo_api_response = await client.get(mirakurun_logo_api_url, timeout=5)

                # ステータスコードが 200 であれば
                # ステータスコードが 503 の場合はロゴデータが存在しない
                if mirakurun_logo_api_response.status_code == 200:

                    # 取得したロゴデータを返す
                    mirakurun_logo = mirakurun_logo_api_response.content
                    return (mirakurun_logo, 'image/png')

            # API に接続できなかった際は特にエラーは吐かず、デフォルトのロゴ画像を利用する
            except (httpx.NetworkError, httpx.TimeoutException):
                pass

        return None

    def GetETag(logo_data: bytes) -> str:
        """ ロゴデータのバイナリから ETag を生成する """
        return hashlib.sha256(logo_data).hexdigest()

    # HTTP レスポンスヘッダーの Cache-Control の設定
    ## 1ヶ月キャッシュする
    CACHE_CONTROL = 'public, no-transform, immutable, max-age=2592000'

    # ***** チャンネル情報を取得 *****

    # チャンネル ID からチャンネル情報を取得する
    # "NID0-SID0" "gr000" はフロントエンド側のチャンネル情報のデフォルト値になっているため、特別にデフォルトのロゴ画像を返す
    # Depends だと GetChannel() が実行された時点で 422 エラーになるので、意図的に手動で GetChannel() を実行している
    if channel_id == 'NID0-SID0' or channel_id == 'gr000':
        return FileResponse(LOGO_DIR / 'default.png', headers={
            'Cache-Control': CACHE_CONTROL,
            'ETag': GetETag(b'default'),
        })
    channel = await GetChannel(channel_id)

    # ***** 同梱のロゴを利用（存在する場合）*****

    # 同梱されているロゴがあれば取得する (ない場合は None が返る)
    logo_path = await GetLogoFilePath(channel)
    if logo_path is not None:

        # リクエストに If-None-Match ヘッダが存在し、ETag が一致する場合は 304 を返す
        ## ETag はロゴファイルのパスとバージョン情報のハッシュから生成する
        etag = GetETag(f'{logo_path}{VERSION}'.encode())
        if request.headers.get('If-None-Match') == etag:
            return Response(status_code=304)

        # ロゴデータを返す
        return FileResponse(logo_path, headers={
            'Cache-Control': CACHE_CONTROL,
            'ETag': etag,
        })

    # ***** EDCB または Mirakurun からロゴを取得 *****

    # EDCB または Mirakurun からロゴデータを取得する (ない場合は None が返る)
    result = await GetFallbackLogoData(channel)
    if result is not None:
        logo_data, logo_media_type = result

        # リクエストに If-None-Match ヘッダが存在し、ETag が一致する場合は 304 を返す
        ## ETag はロゴデータのハッシュから生成する
        etag = GetETag(logo_data)
        if request.headers.get('If-None-Match') == etag:
            return Response(status_code=304)

        # ロゴデータを返す
        return Response(content=logo_data, media_type=logo_media_type, headers={
            'Cache-Control': CACHE_CONTROL,
            'ETag': etag,
        })

    # ***** デフォルトのロゴ画像を利用 *****

    # 同梱のロゴファイルも Mirakurun や EDCB からのロゴもない場合は、デフォルトのロゴ画像を返す
    return FileResponse(LOGO_DIR / 'default.png', headers={
        'Cache-Control': CACHE_CONTROL,
        'ETag': GetETag(b'default'),
    })


@router.get(
    '/{channel_id}/jikkyo',
    summary = 'ニコニコ実況 WebSocket URL API',
    response_description = 'ニコニコ実況コメント送受信用 WebSocket API の情報。',
    response_model = schemas.JikkyoWebSocketInfo,
)
async def ChannelJikkyoWebSocketInfoAPI(
    request: Request,
    channel: Annotated[Channel, Depends(GetChannel)],
):
    """
    指定されたチャンネルに対応する、ニコニコ実況コメント送受信用 WebSocket API の情報を取得する。
    """

    # もし Authorization ヘッダーがあるなら、ログイン中のユーザーアカウントを取得する
    current_user = None
    if request.headers.get('Authorization') is not None:

        # JWT アクセストークンを取得
        _, user_access_token = get_authorization_scheme_param(request.headers.get('Authorization'))

        # アクセストークンに紐づくユーザーアカウントを取得
        ## もともとバリデーション用なので HTTPException が送出されるが、ここではエラーにする必要はないのでパス
        try:
            current_user = await GetCurrentUser(token=user_access_token)
        except HTTPException:
            pass

    # ニコニココメント送受信用 WebSocket API の情報を取得する
    jikkyo_client = JikkyoClient(channel.network_id, channel.service_id)
    return await jikkyo_client.fetchWebSocketInfo(current_user)
