
import json
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal, cast

import ariblib.constants
from fastapi import APIRouter, Body, Depends, Query
from pydantic import TypeAdapter
from tortoise import connections

from app import logging, schemas
from app.config import Config
from app.constants import JST
from app.routers.ReservationConditionsRouter import EncodeEDCBSearchKeyInfo
from app.routers.ReservationsRouter import GetCtrlCmdUtil
from app.utils import NormalizeToJSTDatetime, ParseDatetimeStringToJST
from app.utils.edcb import EventInfo, ReserveDataRequired, SearchKeyInfo
from app.utils.edcb.CtrlCmdUtil import CtrlCmdUtil
from app.utils.edcb.EDCBUtil import EDCBUtil
from app.utils.TSInformation import TSInformation


# ルーター
router = APIRouter(
    tags = ['Programs'],
    prefix = '/api/programs',
)


def DecodeEDCBEventInfo(event_info: EventInfo) -> schemas.Program:
    """
    EDCB の EventInfo オブジェクトを schemas.Program オブジェクトに変換する
    Program.updateFromEDCB() での変換処理を移植したもの

    Args:
        event_info (EventInfo): EDCB の EventInfo オブジェクト

    Returns:
        schemas.Program: schemas.Program オブジェクト
    """

    # 番組タイトル・番組概要
    title: str = ''
    description: str = ''
    if 'short_info' in event_info:
        title = TSInformation.formatString(event_info['short_info']['event_name']).strip()
        description = TSInformation.formatString(event_info['short_info']['text_char']).strip()

    # 番組詳細
    detail: dict[str, str] = {}
    if 'ext_info' in event_info:

        # 番組詳細テキストから取得した、見出しと本文の辞書ごとに
        for head, text in EDCBUtil.parseProgramExtendedText(event_info['ext_info']['text_char']).items():

            # 見出しと本文
            ## 見出しのみ ariblib 側で意図的に重複防止のためのタブ文字付加が行われる場合があるため、
            ## strip() では明示的に半角スペースと改行のみを指定している
            head_hankaku = TSInformation.formatString(head).replace('◇', '').strip(' \r\n')  # ◇ を取り除く
            ## ないとは思うが、万が一この状態で見出しが衝突しうる場合は、見出しの後ろにタブ文字を付加する
            while head_hankaku in detail.keys():
                head_hankaku += '\t'
            ## 見出しが空の場合、固定で「番組内容」としておく
            if head_hankaku == '':
                head_hankaku = '番組内容'
            text_hankaku = TSInformation.formatString(text).strip()
            detail[head_hankaku] = text_hankaku

            # 番組概要が空の場合、番組詳細の最初の本文を概要として使う
            # 空でまったく情報がないよりかは良いはず
            if description.strip() == '':
                description = text_hankaku

    # 番組開始時刻
    ## 万が一取得できなかった場合は 1970/1/1 9:00 とする
    start_time = NormalizeToJSTDatetime(event_info.get('start_time', datetime(1970, 1, 1, 9, tzinfo=JST)))

    # 番組終了時刻
    ## 終了時間未定の場合、とりあえず5分とする
    end_time = start_time + timedelta(seconds=event_info.get('duration_sec', 300))

    # schemas.Program オブジェクトを作成
    program = schemas.Program(
        id = f'NID{event_info["onid"]}-SID{event_info["sid"]:03d}-EID{event_info["eid"]}',
        channel_id = f'NID{event_info["onid"]}-SID{event_info["sid"]:03d}',
        network_id = event_info['onid'],
        service_id = event_info['sid'],
        event_id = event_info['eid'],
        title = title,
        description = description,
        detail = detail,
        start_time = start_time,
        end_time = end_time,
        duration = (end_time - start_time).total_seconds(),
        is_free = bool(event_info['free_ca_flag'] == 0),
        genres = [],
        video_type = None,
        video_codec = None,
        video_resolution = None,
        primary_audio_type = '',
        primary_audio_language = '',
        primary_audio_sampling_rate = '',
        secondary_audio_type = None,
        secondary_audio_language = None,
        secondary_audio_sampling_rate = None,
    )

    # ジャンル
    ## 数字だけでは開発中の視認性が低いのでテキストに変換する
    program.genres = []  # デフォルト値
    content_info = event_info.get('content_info')
    if content_info is not None:
        for content_data in content_info['nibble_list']:  # ジャンルごとに

            # 大まかなジャンルを取得
            genre_tuple = ariblib.constants.CONTENT_TYPE.get(content_data['content_nibble'] >> 8)
            if genre_tuple is not None:

                # major … 大分類
                # middle … 中分類
                genre_dict: schemas.Genre = {
                    'major': genre_tuple[0].replace('／', '・'),
                    'middle': genre_tuple[1].get(content_data['content_nibble'] & 0xf, '未定義').replace('／', '・'),
                }

                # BS/地上デジタル放送用番組付属情報がジャンルに含まれている場合、user_nibble から値を取得して書き換える
                # たとえば「中止の可能性あり」や「延長の可能性あり」といった情報が取れる
                if genre_dict['major'] == '拡張':
                    if genre_dict['middle'] == 'BS/地上デジタル放送用番組付属情報':
                        user_nibble = (content_data['user_nibble'] >> 8 << 4) | (content_data['user_nibble'] & 0xf)
                        genre_dict['middle'] = ariblib.constants.USER_TYPE.get(user_nibble, '未定義')
                    # 「拡張」はあるがBS/地上デジタル放送用番組付属情報でない場合はなんの値なのかわからないのでパス
                    else:
                        continue

                # ジャンルを追加
                program.genres.append(genre_dict)

    # 映像情報
    ## テキストにするために ariblib.constants や TSInformation の値を使う
    program.video_type = None
    program.video_codec = None
    program.video_resolution = None
    component_info = event_info.get('component_info')
    if component_info is not None:
        ## 映像の種類
        component_types = ariblib.constants.COMPONENT_TYPE.get(component_info['stream_content'])
        if component_types is not None:
            program.video_type = component_types.get(component_info['component_type'])
        ## 映像のコーデック
        program.video_codec = TSInformation.STREAM_CONTENT.get(component_info['stream_content'])
        ## 映像の解像度
        program.video_resolution = TSInformation.COMPONENT_TYPE.get(component_info['component_type'])

    # 音声情報
    program.primary_audio_type = ''
    program.primary_audio_language = ''
    program.primary_audio_sampling_rate = ''
    program.secondary_audio_type = None
    program.secondary_audio_language = None
    program.secondary_audio_sampling_rate = None
    audio_info = event_info.get('audio_info')
    if audio_info is not None and len(audio_info['component_list']) > 0:

        ## 主音声
        audio_component_info = audio_info['component_list'][0]
        program.primary_audio_type = ariblib.constants.COMPONENT_TYPE[0x02].get(audio_component_info['component_type'], '')
        program.primary_audio_sampling_rate = ariblib.constants.SAMPLING_RATE.get(audio_component_info['sampling_rate'], '')
        ## 2021/09 現在の EDCB では言語コードが取得できないため、日本語か英語で固定する
        ## EpgDataCap3 のパーサー止まりで EDCB 側では取得していないらしい
        program.primary_audio_language = '日本語'
        ## デュアルモノのみ
        if program.primary_audio_type == '1/0+1/0モード(デュアルモノ)':
            if audio_component_info['es_multi_lingual_flag'] != 0:  # デュアルモノ時の多言語フラグ
                program.primary_audio_language += '+英語'
            else:
                program.primary_audio_language += '+副音声'

        # 副音声（存在する場合）
        if len(audio_info['component_list']) > 1:
            audio_component_info = audio_info['component_list'][1]
            program.secondary_audio_type = ariblib.constants.COMPONENT_TYPE[0x02].get(audio_component_info['component_type'], '')
            program.secondary_audio_sampling_rate = ariblib.constants.SAMPLING_RATE.get(audio_component_info['sampling_rate'], '')
            ## 2021/09 現在の EDCB では言語コードが取得できないため、副音声で固定する
            ## 英語かもしれないし解説かもしれない
            program.secondary_audio_language = '副音声'
            ## デュアルモノのみ
            if program.secondary_audio_type == '1/0+1/0モード(デュアルモノ)':
                if audio_component_info['es_multi_lingual_flag'] != 0:  # デュアルモノ時の多言語フラグ
                    program.secondary_audio_language += '+英語'
                else:
                    program.secondary_audio_language += '+副音声'

    return program


@router.post(
    '/search',
    summary = '番組検索 API',
    response_description = '検索結果の番組情報のリスト。',
    response_model = schemas.Programs,
)
async def ProgramSearchAPI(
    program_search_condition: Annotated[schemas.ProgramSearchCondition, Body(description='番組検索条件。')],
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
):
    """
    番組情報を検索する。
    """

    # schemas.ProgramSearchCondition オブジェクトを SearchKeyInfo オブジェクトに変換
    search_key_info = await EncodeEDCBSearchKeyInfo(program_search_condition, edcb)

    # EDCB の EPG ストアに保存されているすべての番組情報を検索
    ## 過去番組は検索対象外
    event_info_list: list[EventInfo] | None = await edcb.sendSearchPg([cast(SearchKeyInfo, search_key_info)])
    if event_info_list is None:
        # None が返ってきた場合は空のリストを返す
        return schemas.Programs(total=0, programs=[])

    # EDCB の EventInfo オブジェクトを schemas.Program オブジェクトに変換
    programs = [DecodeEDCBEventInfo(event_info) for event_info in event_info_list]

    return schemas.Programs(total=len(programs), programs=programs)


@router.get(
    '/timetable',
    summary = '番組表 API',
    response_description = '番組表データ。チャンネルごとの番組リストと日付範囲を含む。',
    response_model = schemas.TimeTable,
)
async def TimeTableAPI(
    start_time: Annotated[datetime | None, Query(description='取得開始日時 (ISO8601 形式)。省略時は現在時刻。')] = None,
    end_time: Annotated[datetime | None, Query(description='取得終了日時 (ISO8601 形式)。省略時は DB に存在する最終日時。')] = None,
    channel_type: Annotated[Literal['GR', 'BS', 'CS', 'CATV', 'SKY', 'BS4K'] | None, Query(description='チャンネル種別。省略時は全種別。')] = None,
    pinned_channel_ids: Annotated[str | None, Query(description='チャンネル ID のカンマ区切りリスト (ピン留めチャンネル用)。指定時は channel_type より優先される。')] = None,
):
    """
    番組表データを取得する。<br>
    チャンネルごとの番組リストと、番組データの有効日付範囲を含む。<br>
    EDCB バックエンド時は各番組の予約情報も含む。
    """

    # 現在時刻
    now = datetime.now(JST)

    # 開始時刻のデフォルト値: 現在時刻
    if start_time is None:
        start_time = now

    # タイムゾーンが指定されていない場合は JST として扱う
    start_time = NormalizeToJSTDatetime(start_time)

    # データベースの生のコネクションを取得
    connection = connections.get('default')

    # 番組データの日付範囲を取得 (日付セレクター用)
    date_range_result = await connection.execute_query_dict(
        'SELECT MIN(start_time) AS earliest, MAX(end_time) AS latest FROM programs'
    )
    earliest_str = date_range_result[0]['earliest'] if date_range_result else None
    latest_str = date_range_result[0]['latest'] if date_range_result else None

    # 日付文字列を datetime に変換 (SQLite は文字列で保存されている)
    if earliest_str:
        earliest = ParseDatetimeStringToJST(earliest_str)
    else:
        earliest = now

    if latest_str:
        latest = ParseDatetimeStringToJST(latest_str)
    else:
        latest = now + timedelta(days=7)

    # 終了時刻のデフォルト値: DB に存在する最終日時
    if end_time is None:
        end_time = latest

    # タイムゾーンが指定されていない場合は JST として扱う
    end_time = NormalizeToJSTDatetime(end_time)

    # チャンネル ID リストをパース
    target_channel_ids: list[str] | None = None
    if pinned_channel_ids is not None and pinned_channel_ids.strip() != '':
        target_channel_ids = [cid.strip() for cid in pinned_channel_ids.split(',') if cid.strip()]

    # チャンネル情報を raw SQL で取得 (Tortoise ORM のオーバーヘッドを回避)
    if target_channel_ids is not None:
        # 指定されたチャンネル ID のチャンネルのみ取得
        placeholders = ','.join(['?' for _ in target_channel_ids])
        channels_query = f"""
            SELECT
                id, display_channel_id, network_id, service_id, transport_stream_id,
                remocon_id, channel_number, type, name, jikkyo_force,
                is_subchannel, is_radiochannel, is_watchable
            FROM channels
            WHERE id IN ({placeholders}) AND is_watchable = 1
        """
        channels_result = await connection.execute_query_dict(channels_query, target_channel_ids)
        # 指定された順序でソート
        channel_id_order = {cid: idx for idx, cid in enumerate(target_channel_ids)}
        channels_result.sort(key=lambda c: channel_id_order.get(c['id'], float('inf')))  # type: ignore[arg-type]
    elif channel_type is not None:
        # 指定されたチャンネル種別のチャンネルのみ取得
        channels_query = """
            SELECT
                id, display_channel_id, network_id, service_id, transport_stream_id,
                remocon_id, channel_number, type, name, jikkyo_force,
                is_subchannel, is_radiochannel, is_watchable
            FROM channels
            WHERE type = ? AND is_watchable = 1
            ORDER BY channel_number, remocon_id
        """
        channels_result = await connection.execute_query_dict(channels_query, [channel_type])
    else:
        # 全チャンネル取得
        channels_query = """
            SELECT
                id, display_channel_id, network_id, service_id, transport_stream_id,
                remocon_id, channel_number, type, name, jikkyo_force,
                is_subchannel, is_radiochannel, is_watchable
            FROM channels
            WHERE is_watchable = 1
            ORDER BY channel_number, remocon_id
        """
        channels_result = await connection.execute_query_dict(channels_query)

    # チャンネルがない場合は空のレスポンスを返す
    if not channels_result:
        return schemas.TimeTable(
            channels=[],
            date_range=schemas.TimeTableDateRange(earliest=earliest, latest=latest),
        )

    # チャンネル行データの真偽値を変換 (SQLite では 0/1)
    for channel_row in channels_result:
        channel_row['is_subchannel'] = bool(channel_row['is_subchannel'])
        channel_row['is_radiochannel'] = bool(channel_row['is_radiochannel'])
        channel_row['is_watchable'] = bool(channel_row['is_watchable'])

    # 各 TS (network_id, transport_stream_id) ごとに、サブチャンネルの8時間ルール判定を行う
    # まず TS ごとにグループ化
    ts_channels: dict[tuple[int, int | None], list[dict[str, Any]]] = {}
    for channel_row in channels_result:
        ts_key = (channel_row['network_id'], channel_row['transport_stream_id'])
        if ts_key not in ts_channels:
            ts_channels[ts_key] = []
        ts_channels[ts_key].append(channel_row)

    # サブチャンネル放送時間の集計を1つのクエリで取得
    # 全チャンネルの network_id と transport_stream_id の組み合わせに対して一括取得
    # これにより TS ごとに個別クエリを実行する N+1 問題を回避
    subchannel_durations_query = """
        SELECT
            c.network_id,
            c.transport_stream_id,
            p.service_id,
            DATE(p.start_time, '-4 hours') AS broadcast_date,
            SUM(p.duration) AS total_duration
        FROM programs p
        INNER JOIN channels c ON p.channel_id = c.id
        WHERE c.is_subchannel = 1
        GROUP BY c.network_id, c.transport_stream_id, p.service_id, broadcast_date
    """
    subchannel_durations_result = await connection.execute_query_dict(subchannel_durations_query)

    # サブチャンネル放送時間を TS キー -> サービス ID -> 日付 -> 放送時間 の形式に整理
    subchannel_durations_by_ts: dict[tuple[int, int | None], dict[int, dict[str, float]]] = {}
    for row in subchannel_durations_result:
        ts_key = (row['network_id'], row['transport_stream_id'])
        service_id = row['service_id']
        broadcast_date = row['broadcast_date']
        total_duration = row['total_duration'] or 0

        if ts_key not in subchannel_durations_by_ts:
            subchannel_durations_by_ts[ts_key] = {}
        if service_id not in subchannel_durations_by_ts[ts_key]:
            subchannel_durations_by_ts[ts_key][service_id] = {}
        subchannel_durations_by_ts[ts_key][service_id][broadcast_date] = total_duration

    # 8時間ルールに基づいて独立サブチャンネルを判定
    # 閾値: 8時間 = 28800秒
    INDEPENDENT_SUBCHANNEL_THRESHOLD = 8 * 3600
    independent_subchannels_by_ts: dict[tuple[int, int | None], set[int]] = {}
    for ts_key, durations_by_service in subchannel_durations_by_ts.items():
        independent_subchannels: set[int] = set()
        for service_id, daily_durations in durations_by_service.items():
            # いずれかの日で閾値以上の放送時間があれば独立チャンネルとして判定
            for duration in daily_durations.values():
                if duration >= INDEPENDENT_SUBCHANNEL_THRESHOLD:
                    independent_subchannels.add(service_id)
                    break
        independent_subchannels_by_ts[ts_key] = independent_subchannels

    # 番組情報を取得するためのチャンネル ID リストを構築
    channel_ids_for_query = [c['id'] for c in channels_result]

    # 番組情報を取得
    programs_placeholders = ','.join(['?' for _ in channel_ids_for_query])
    programs_query = f"""
        SELECT *
        FROM programs
        WHERE
            channel_id IN ({programs_placeholders})
            AND (
                -- 指定期間内に開始する番組
                (start_time >= ? AND start_time < ?)
                OR
                -- 指定期間内に終了する番組 (開始は期間前でも可)
                (end_time > ? AND end_time <= ?)
                OR
                -- 期間をまたぐ番組 (開始は期間前、終了は期間後)
                (start_time < ? AND end_time > ?)
            )
        ORDER BY channel_id, start_time
    """

    programs_params: list[Any] = [
        *channel_ids_for_query,
        start_time, end_time,  # 期間内に開始
        start_time, end_time,  # 期間内に終了
        start_time, end_time,  # 期間をまたぐ
    ]

    programs_result = await connection.execute_query_dict(programs_query, programs_params)

    # EDCB バックエンドの場合は予約情報を取得
    reservations_by_program_id: dict[str, dict[str, Any]] = {}
    reservations_by_channel_time: dict[str, list[dict[str, Any]]] = {}
    if Config().general.backend == 'EDCB':
        try:
            edcb = CtrlCmdUtil()
            reserve_data_list: list[ReserveDataRequired] | None = await edcb.sendEnumReserve()
            if reserve_data_list is not None:
                # (ONID, TSID, SID) からチャンネル ID への逆引き辞書
                ## 予約の EID が DB 上の番組情報と不一致でも、同一チャンネルかつ同一時間帯なら予約情報を表示できるようにする
                channel_id_by_service_triplet: dict[tuple[int, int, int], str] = {}
                for channel_row in channels_result:
                    if channel_row['transport_stream_id'] is None:
                        continue
                    channel_id_by_service_triplet[(
                        channel_row['network_id'],
                        channel_row['transport_stream_id'],
                        channel_row['service_id'],
                    )] = channel_row['id']

                # 録画中判定を行う時間範囲 (現在時刻の2時間前〜2時間後)
                # 番組延長や繰り上げを考慮して余裕を持たせる
                recording_check_start = now - timedelta(hours=2)
                recording_check_end = now + timedelta(hours=2)

                for reserve_data in reserve_data_list:
                    reserve_start_time = NormalizeToJSTDatetime(reserve_data['start_time'])
                    reserve_end_time = reserve_start_time + timedelta(seconds=reserve_data['duration_second'])

                    # 番組 ID を構築
                    program_id = f'NID{reserve_data["onid"]}-SID{reserve_data["sid"]:03d}-EID{reserve_data["eid"]}'

                    # 予約状態を判定
                    status: Literal['Reserved', 'Recording', 'Disabled']
                    rec_mode = reserve_data.get('rec_setting', {}).get('rec_mode', 1)
                    if rec_mode >= 5:  # 5以上は無効
                        status = 'Disabled'
                    else:
                        # 現在時刻付近の番組のみ録画中かどうかを判定 (N+1 問題の回避)
                        # 明らかに録画中でない番組に対して EDCB にクエリを発行しても無駄なので、
                        # 録画中判定の時間範囲内 (現在時刻の前後2時間) にある番組のみチェックする
                        if reserve_start_time <= recording_check_end and reserve_end_time >= recording_check_start:
                            is_recording = type(await edcb.sendGetRecFilePath(reserve_data['reserve_id'])) is str
                            status = 'Recording' if is_recording else 'Reserved'
                        else:
                            status = 'Reserved'

                    # 録画可能状態
                    recording_availability: Literal['Full', 'Partial', 'Unavailable'] = 'Full'
                    if reserve_data['overlap_mode'] == 1:
                        recording_availability = 'Partial'
                    elif reserve_data['overlap_mode'] == 2:
                        recording_availability = 'Unavailable'

                    reservations_by_program_id[program_id] = {
                        'id': reserve_data['reserve_id'],
                        'status': status,
                        'recording_availability': recording_availability,
                    }
                    channel_id = channel_id_by_service_triplet.get((
                        reserve_data['onid'],
                        reserve_data['tsid'],
                        reserve_data['sid'],
                    ))
                    if channel_id is not None:
                        if channel_id not in reservations_by_channel_time:
                            reservations_by_channel_time[channel_id] = []
                        reservations_by_channel_time[channel_id].append({
                            'start_time': reserve_start_time,
                            'end_time': reserve_end_time,
                            'reservation': reservations_by_program_id[program_id],
                        })
        except Exception as ex:
            # 予約情報の取得に失敗しても番組表自体は返す
            logging.warning('[ProgramsRouter][TimeTableAPI] Failed to get reservations:', exc_info=ex)

    # チャンネルごとに番組をグループ化
    programs_by_channel: dict[str, list[dict[str, Any]]] = {c['id']: [] for c in channels_result}
    for program_row in programs_result:
        channel_id = program_row['channel_id']
        if channel_id in programs_by_channel:
            # JSON フィールドをデコード
            program_row['detail'] = json.loads(program_row['detail']) if program_row['detail'] else {}
            program_row['genres'] = json.loads(program_row['genres']) if program_row['genres'] else []

            # SQLite から取得した番組開始・終了時刻を JST aware datetime に正規化する
            ## DB には基本的に UTC+9 を保存しているが、将来のデータ混在に備えてタイムゾーンなしでも JST を補う
            program_start_time = ParseDatetimeStringToJST(program_row['start_time'])
            program_end_time = ParseDatetimeStringToJST(program_row['end_time'])
            program_row['start_time'] = program_start_time.isoformat()
            program_row['end_time'] = program_end_time.isoformat()

            # 真偽値を変換 (SQLite では 0/1)
            program_row['is_free'] = bool(program_row['is_free'])

            # 予約情報を追加
            program_id = program_row['id']
            if program_id in reservations_by_program_id:
                program_row['reservation'] = reservations_by_program_id[program_id]
            else:
                # 予約の EID が一致しない場合でも、同一チャンネルかつ同一時間帯で重なる予約があれば暫定的に紐付ける
                ## スポーツ中継の延長などで EIT[p/f] と EIT[schedule] が一時的にずれるケースを救済する
                fallback_reservation = None
                fallback_reservations = reservations_by_channel_time.get(channel_id, [])
                if fallback_reservations:
                    best_overlap_seconds = 0
                    best_overlap_index = -1
                    for index, fallback in enumerate(fallback_reservations):
                        overlap_start_time = max(program_start_time, fallback['start_time'])
                        overlap_end_time = min(program_end_time, fallback['end_time'])
                        overlap_seconds = (overlap_end_time - overlap_start_time).total_seconds()
                        if overlap_seconds > best_overlap_seconds:
                            best_overlap_seconds = overlap_seconds
                            best_overlap_index = index

                    if best_overlap_index >= 0:
                        # pop() で採用済み要素をリストから除外し、以降の番組に同一予約が二重割当されることを防ぐ
                        fallback_reservation = fallback_reservations.pop(best_overlap_index)['reservation']

                program_row['reservation'] = fallback_reservation

            programs_by_channel[channel_id].append(program_row)

    # レスポンスを構築
    result_channels: list[dict[str, Any]] = []

    for channel_row in channels_result:
        ts_key = (channel_row['network_id'], channel_row['transport_stream_id'])
        independent_subchannels = independent_subchannels_by_ts.get(ts_key, set())

        # このチャンネルがサブチャンネルかつ独立サブチャンネルでない場合はスキップ
        # (メインチャンネルの subchannels に含める)
        if channel_row['is_subchannel'] and channel_row['service_id'] not in independent_subchannels:
            continue

        # 番組リスト
        programs_list = programs_by_channel.get(channel_row['id'], [])

        # サブチャンネルのリストを収集 (8時間未満のサブチャンネルのみ)
        subchannels: list[dict[str, Any]] | None = None
        if not channel_row['is_subchannel']:
            # メインチャンネルの場合、同一 TS 内のサブチャンネル番組を収集
            ts_channel_list = ts_channels.get(ts_key, [])
            for sub_channel_row in ts_channel_list:
                # サブチャンネルかつ独立サブチャンネルでない場合のみ
                if sub_channel_row['is_subchannel'] and sub_channel_row['service_id'] not in independent_subchannels:
                    # サブチャンネルの SID がメインチャンネルの SID より小さい場合はスキップ
                    # サブチャンネルは必ずメインチャンネルより大きい SID を持つため、
                    # SID が小さい場合はこのメインチャンネルのサブチャンネルではない
                    # (例: 放送大学ラジオ 531 のサブチャンネルとして放送大学テレビ SD 232 が紐づかないようにする)
                    if sub_channel_row['service_id'] < channel_row['service_id']:
                        continue
                    sub_programs = programs_by_channel.get(sub_channel_row['id'], [])
                    if sub_programs:
                        if subchannels is None:
                            subchannels = []
                        # チャンネル情報と番組リストを含める
                        subchannels.append({
                            'channel': sub_channel_row,
                            'programs': sub_programs,
                        })

        result_channels.append({
            'channel': channel_row,
            'programs': programs_list,
            'subchannels': subchannels,
        })

    # Pydantic v2 は Rust バックエンドにより高速化されているため、モデルを直接返す
    # result_channels のみを TypeAdapter で一括バリデートし、date_range は直接構築する
    channels_adapter = TypeAdapter(list[schemas.TimeTableChannel])
    validated_channels = channels_adapter.validate_python(result_channels)
    return schemas.TimeTable(
        channels=validated_channels,
        date_range=schemas.TimeTableDateRange(earliest=earliest, latest=latest),
    )
