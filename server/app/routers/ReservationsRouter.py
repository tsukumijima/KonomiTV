
import asyncio
import configparser
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from tortoise import transactions

from app import logging, schemas
from app.config import Config
from app.constants import JST
from app.models.Channel import Channel
from app.models.Program import Program
from app.utils import NormalizeToJSTDatetime
from app.utils.edcb import (
    EventInfo,
    RecFileSetInfoRequired,
    RecSettingData,
    RecSettingDataRequired,
    ReserveData,
    ReserveDataRequired,
    ServiceEventInfo,
)
from app.utils.edcb.CtrlCmdUtil import CtrlCmdUtil
from app.utils.edcb.EDCBUtil import EDCBUtil
from app.utils.TSInformation import TSInformation


# ルーター
router = APIRouter(
    tags = ['Reservations'],
    prefix = '/api/recording/reservations',
)


# Bitrate.ini のキャッシュ (TTL: 15分)
_bitrate_ini_cache: dict[str, int] | None = None
_bitrate_ini_cache_timestamp: float | None = None


async def DecodeEDCBReserveData(
    reserve_data: ReserveDataRequired,
    channels: list[Channel] | None = None,
    programs: dict[tuple[int, int, int], Program] | None = None,
    is_recording_in_progress: bool = False,
) -> schemas.Reservation:
    """
    EDCB の ReserveData オブジェクトを schemas.Reservation オブジェクトに変換する

    Args:
        reserve_data (ReserveDataRequired): EDCB の ReserveData オブジェクト
        channels (list[Channel] | None): あらかじめ全てのチャンネル情報を取得しておく場合はそのリスト、そうでない場合は None
        programs (dict[tuple[int, int, int], Program] | None): あらかじめ取得しておいた番組情報の辞書 (network_id, service_id, event_id) -> Program
        is_recording_in_progress (bool): 録画中かどうか

    Returns:
        schemas.Reservation: schemas.Reservation オブジェクト
    """

    async def GetBitrateFromEDCB(network_id: int, transport_stream_id: int, service_id: int) -> int:
        """
        EDCB から Bitrate.ini を取得して、指定されたチャンネルのビットレートを取得する
        ref: https://github.com/tkntrec/EDCB/blob/my-build/EpgTimer/EpgTimer/DefineClass/SearchItem.cs#L265-L290

        Args:
            network_id (int): ネットワーク ID (ONID)
            transport_stream_id (int): トランスポートストリーム ID (TSID)
            service_id (int): サービス ID (SID)

        Returns:
            int: ビットレート (kbps)
        """

        global _bitrate_ini_cache, _bitrate_ini_cache_timestamp

        # 常時マルチチャンネル放送のため、例外的に決め打ちの値を使うチャンネルリスト
        # キー: (NID, SID), 値: ビットレート (kbps)
        hardcoded_bitrates = {
            (32391, 23608): 12000,  # TOKYO MX1(091ch) (12Mbps)
            (32391, 23609): 12000,  # TOKYO MX1(092ch) (12Mbps)
            (32391, 23610): 4800,   # TOKYO MX2(093ch) (4.8Mbps)
            (32381, 24680): 10000,  # イッツコムch10(101ch) (10Mbps)
            (32381, 24681): 10000,  # イッツコムch10(102ch) (10Mbps)
            (32383, 24696): 10000,  # イッツコムch10(111ch) (10Mbps)
            (32383, 24697): 10000,  # イッツコムch10(112ch) (10Mbps)
        }

        # 決めうちの値が設定されているかチェック
        channel_key = (network_id, service_id)
        if channel_key in hardcoded_bitrates:
            return hardcoded_bitrates[channel_key]

        # キャッシュが存在し、かつ15分以内の場合はそれを使用
        current_time = time.time()
        if (_bitrate_ini_cache is not None and
            _bitrate_ini_cache_timestamp is not None and
            current_time - _bitrate_ini_cache_timestamp < 900):  # 900秒 = 15分
            # 段階的に検索: 全指定 -> SID=0xFFFF -> TSID=0xFFFF -> ONID=0xFFFF
            for i in range(4):
                onid = 0xFFFF if i > 2 else network_id
                tsid = 0xFFFF if i > 1 else transport_stream_id
                sid = 0xFFFF if i > 0 else service_id

                # EpgTimer の Create64Key ロジックを移植: (onid << 32 | tsid << 16 | sid)
                key = f"{(onid << 32 | tsid << 16 | sid):012X}"

                if key in _bitrate_ini_cache and _bitrate_ini_cache[key] > 0:
                    return _bitrate_ini_cache[key]

            # デフォルト値を返す
            return 19456

        try:
            # EDCB から Bitrate.ini を取得
            files = await CtrlCmdUtil().sendFileCopy2(['Bitrate.ini'])
            if files is None or len(files) == 0:
                logging.warning('[ReservationsRouter][GetBitrateFromEDCB] Failed to get Bitrate.ini from EDCB.')
                return 19456

            # ファイルデータをテキストとして解析
            bitrate_ini_data = files[0]['data']
            if not bitrate_ini_data:
                logging.warning('[ReservationsRouter][GetBitrateFromEDCB] Bitrate.ini is empty.')
                return 19456

            # バイナリデータを文字列に変換 (UTF-16 BOM つきまたは UTF-8)
            try:
                # UTF-16 BOM つきの場合
                if bitrate_ini_data.startswith(b'\xff\xfe'):
                    ini_text = bitrate_ini_data.decode('utf-16')
                else:
                    # UTF-8 として試行
                    ini_text = bitrate_ini_data.decode('utf-8')
            except UnicodeDecodeError:
                # システムデフォルトエンコーディングで試行
                ini_text = bitrate_ini_data.decode('shift_jis', errors='ignore')

            # ConfigParser で解析
            config = configparser.ConfigParser()
            config.read_string(ini_text)

            # BITRATE セクションからビットレート情報を取得してキャッシュに保存
            _bitrate_ini_cache = {}
            _bitrate_ini_cache_timestamp = current_time
            if 'BITRATE' in config:
                for key, value in config['BITRATE'].items():
                    try:
                        _bitrate_ini_cache[key.upper()] = int(value)
                    except ValueError:
                        continue

            # 段階的に検索: 全指定 -> SID=0xFFFF -> TSID=0xFFFF -> ONID=0xFFFF
            for i in range(4):
                onid = 0xFFFF if i > 2 else network_id
                tsid = 0xFFFF if i > 1 else transport_stream_id
                sid = 0xFFFF if i > 0 else service_id

                # EpgTimer の Create64Key ロジックを移植: (onid << 32 | tsid << 16 | sid)
                key = f"{(onid << 32 | tsid << 16 | sid):012X}"

                if key in _bitrate_ini_cache and _bitrate_ini_cache[key] > 0:
                    return _bitrate_ini_cache[key]

            # 見つからない場合はデフォルト値を返す
            return 19456

        except Exception as ex:
            logging.error('[ReservationsRouter][GetBitrateFromEDCB] Failed to parse Bitrate.ini:', exc_info=ex)
            return 19456


    def CalculateEstimatedFileSize(duration_seconds: float, bitrate_kbps: int, recording_mode: str) -> int:
        """
        録画予定時間とビットレートから想定ファイルサイズを計算する

        Args:
            duration_seconds (float): 録画予定時間 (秒)
            bitrate_kbps (int): ビットレート (kbps)
            recording_mode (str): 録画モード (視聴モードの場合は想定サイズ 0 を返す)

        Returns:
            int: 想定ファイルサイズ (バイト)
        """

        # 視聴モードの場合は想定サイズ 0 を返す (録画されないため)
        if recording_mode == 'View':
            return 0

        # EpgTimer のロジック: bitrate / 8 * 1000 * duration (秒)
        # ビットレート (kbps) を バイト/秒 に変換: kbps / 8 * 1000 = bytes/sec
        estimated_size_bytes = max(int(bitrate_kbps / 8 * 1000 * duration_seconds), 0)

        return estimated_size_bytes

    # 録画予約 ID
    reserve_id: int = reserve_data['reserve_id']

    # 録画対象チャンネルのネットワーク ID
    network_id: int = reserve_data['onid']

    # 録画対象チャンネルのサービス ID
    service_id: int = reserve_data['sid']

    # 録画対象チャンネルのトランスポートストリーム ID
    transport_stream_id: int = reserve_data['tsid']

    # 録画対象チャンネルのサービス名
    ## 基本全角なので半角に変換する必要がある
    service_name: str = TSInformation.formatString(reserve_data['station_name'])

    # ここでネットワーク ID・サービス ID・トランスポートストリーム ID が一致するチャンネルをデータベースから取得する
    channel: Channel | None
    if channels is not None:
        # あらかじめ全てのチャンネル情報を取得しておく場合はそのリストを使う
        channel = next(
            (channel for channel in channels if (
                channel.network_id == network_id and
                channel.service_id == service_id and
                channel.transport_stream_id == transport_stream_id
            )
        ), None)
    else:
        # そうでない場合はデータベースから取得する
        channel = await Channel.filter(network_id=network_id, service_id=service_id, transport_stream_id=transport_stream_id).get_or_none()
    ## 取得できなかった場合のみ、上記の限定的な情報を使って間に合わせのチャンネル情報を作成する
    ## 通常ここでチャンネル情報が取得できないのはワンセグやデータ放送など KonomiTV ではサポートしていないサービスを予約している場合だけのはず
    if channel is None:
        channel = Channel(
            id = f'NID{network_id}-SID{service_id}',
            display_channel_id = 'gr001',  # 取得できないため一旦 'gr001' を設定
            network_id = network_id,
            service_id = service_id,
            transport_stream_id = transport_stream_id,
            remocon_id = 0,  # 取得できないため一旦 0 を設定
            channel_number = '001',  # 取得できないため一旦 '001' を設定
            type = TSInformation.getNetworkType(network_id),
            name = service_name,
            jikkyo_force = False,
            is_subchannel = False,
            is_radiochannel = False,
            is_watchable = False,
        )
        # GR 以外のみサービス ID からリモコン ID を算出できるので、それを実行
        if channel.type != 'GR':
            channel.remocon_id = TSInformation.calculateRemoconID(channel.type, channel.service_id)
        # チャンネル番号を算出
        channel.channel_number = await TSInformation.calculateChannelNumber(
            channel.type,
            channel.network_id,
            channel.service_id,
            channel.remocon_id,
        )
        # 改めて表示用チャンネル ID を算出
        channel.display_channel_id = channel.type.lower() + channel.channel_number
        # このチャンネルがサブチャンネルかを算出
        channel.is_subchannel = TSInformation.calculateIsSubchannel(channel.type, channel.service_id)

    # 録画予約番組のイベント ID
    event_id: int = reserve_data['eid']

    # 録画予約番組のタイトル
    ## 基本全角なので半角に変換する必要がある
    title: str = TSInformation.formatString(reserve_data['title'])

    # 録画予約番組の番組開始時刻
    start_time: datetime = reserve_data['start_time']

    # 録画予約番組の番組終了時刻
    end_time: datetime = start_time + timedelta(seconds=reserve_data['duration_second'])

    # 録画予約番組の番組長 (秒)
    duration: float = float(reserve_data['duration_second'])

    # ここでネットワーク ID・サービス ID・イベント ID が一致する番組をデータベースから取得する
    program: Program | None = None
    if programs is not None:
        # あらかじめ取得しておいた番組情報の辞書を使用
        program = programs.get((channel.network_id, channel.service_id, event_id))
    else:
        # そうでない場合はデータベースから個別に取得する
        program = await Program.filter(network_id=channel.network_id, service_id=channel.service_id, event_id=event_id).get_or_none()
    ## 取得できなかった場合のみ、上記の限定的な情報を使って間に合わせの番組情報を作成する
    ## 通常ここで番組情報が取得できないのは同じ番組を放送しているサブチャンネルやまだ KonomiTV に反映されていない番組情報など、特殊なケースだけのはず
    if program is None:
        program = Program(
            id = f'NID{channel.network_id}-SID{channel.service_id}-EID{event_id}',
            channel_id = channel.id,
            network_id = channel.network_id,
            service_id = channel.service_id,
            event_id = event_id,
            title = title,
            description = '',
            detail = {},
            start_time = start_time,
            end_time = end_time,
            duration = duration,
            is_free = True,
            genres = [],
            video_type = '映像1080i(1125i)、アスペクト比16:9 パンベクトルなし',
            video_codec = 'mpeg2',
            video_resolution = '1080i',
            primary_audio_type = '1/0モード(シングルモノ)',
            primary_audio_language = '日本語',
            primary_audio_sampling_rate = '48kHz',
            secondary_audio_type = None,
            secondary_audio_language = None,
            secondary_audio_sampling_rate = None,
        )
    ## 番組情報をデータベースから取得できた場合でも、番組タイトル・番組開始時刻・番組終了時刻・番組長は
    ## EDCB から返される情報の方が正確な可能性があるため (特に追従時など)、それらの情報を上書きする
    else:
        program.title = title
        program.start_time = start_time
        program.end_time = end_time
        program.duration = duration

    # 実際に録画可能かどうか: 全編録画可能 / チューナー不足のため部分的にのみ録画可能 (一部録画できない) / チューナー不足のため全編録画不可能
    # ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-240212/Common/CommonDef.h#L32-L34
    # ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-240212/Common/StructDef.h#L62
    recording_availability: Literal['Full', 'Partial', 'Unavailable'] = 'Full'
    if reserve_data['overlap_mode'] == 1:
        recording_availability = 'Partial'
    elif reserve_data['overlap_mode'] == 2:
        recording_availability = 'Unavailable'

    # コメント: EPG 予約で自動追加された予約なら "EPG自動予約" と入る
    comment: str = reserve_data['comment']

    # 録画予定のファイル名
    ## EDCB からのレスポンスでは配列になっているが、大半の場合は 1 つしかないため単一の値としている
    scheduled_recording_file_name: str = ''
    if len(reserve_data['rec_file_name_list']) > 0:
        scheduled_recording_file_name = reserve_data['rec_file_name_list'][0]

    # 録画設定
    record_settings = DecodeEDCBRecSettingData(reserve_data['rec_setting'])

    # 想定録画ファイルサイズを計算
    estimated_recording_file_size: int = 0
    try:
        # EDCB から Bitrate.ini を取得してビットレートを計算
        bitrate_kbps = await GetBitrateFromEDCB(network_id, transport_stream_id, service_id)
        # 想定ファイルサイズを計算
        estimated_recording_file_size = CalculateEstimatedFileSize(duration, bitrate_kbps, record_settings.recording_mode)
    except Exception as ex:
        logging.warning(f'[ReservationsRouter][DecodeEDCBReserveData] Failed to calculate estimated file size. [reserve_id: {reserve_id}]', exc_info=ex)
        estimated_recording_file_size = 0

    # Tortoise ORM モデルは本来 Pydantic モデルと型が非互換だが、FastAPI がよしなに変換してくれるので雑に Any にキャストしている
    ## 逆に自前で変換する方法がわからない…
    return schemas.Reservation(
        id = reserve_id,
        channel = cast(Any, channel),
        program = cast(Any, program),
        is_recording_in_progress = is_recording_in_progress,
        recording_availability = recording_availability,
        comment = comment,
        scheduled_recording_file_name = scheduled_recording_file_name,
        estimated_recording_file_size = estimated_recording_file_size,
        record_settings = record_settings,
    )


def DecodeEDCBRecSettingData(rec_settings_data: RecSettingDataRequired) -> schemas.RecordSettings:
    """
    EDCB の RecSettingData オブジェクトを schemas.RecordSettings オブジェクトに変換する

    Args:
        rec_settings_data (RecSettingDataRequired): EDCB の RecSettingData オブジェクト

    Returns:
        schemas.RecordSettings: schemas.RecordSettings オブジェクト
    """

    # 録画予約が有効かどうか
    is_enabled: bool = rec_settings_data['rec_mode'] <= 4  # 0 ~ 4 なら有効

    # 録画予約の優先度: 1 ~ 5 の数値で数値が大きいほど優先度が高い
    priority: int = rec_settings_data['priority']

    # 保存先の録画フォルダのパスのリスト
    recording_folders: list[schemas.RecordingFolder] = []
    for key in ('rec_folder_list', 'partial_rec_folder'):
        for rec_folder in rec_settings_data[key]:
            # rec_name_plug_in は ? 以降が録画ファイル名テンプレート (マクロ) の値になっているので抽出
            ## RecName_Macro.dll?$title$.ts のような形式で返ってくる
            recording_file_name_template = rec_folder['rec_name_plug_in'].split('?', 1)[1] if '?' in rec_folder['rec_name_plug_in'] else ''
            recording_folders.append(schemas.RecordingFolder(
                recording_folder_path = rec_folder['rec_folder'],
                recording_file_name_template = recording_file_name_template if recording_file_name_template != '' else None,
                is_oneseg_separate_recording_folder = key == 'partial_rec_folder',
            ))

    # 録画開始マージン (秒) / デフォルト設定に従う場合は None
    recording_start_margin: int | None = None
    if 'start_margin' in rec_settings_data:
        recording_start_margin = rec_settings_data['start_margin']

    # 録画終了マージン (秒) / デフォルト設定に従う場合は None
    recording_end_margin: int | None = None
    if 'end_margin' in rec_settings_data:
        recording_end_margin = rec_settings_data['end_margin']

    # 録画モード: 全サービス / 全サービス (デコードなし) / 指定サービスのみ / 指定サービスのみ (デコードなし) / 視聴
    ## ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-240212/Common/CommonDef.h#L26-L30
    ## ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-240212/Document/Readme_Mod.txt?plain=1#L264-L266
    recording_mode: Literal['AllServices', 'AllServicesWithoutDecoding', 'SpecifiedService', 'SpecifiedServiceWithoutDecoding', 'View'] = 'SpecifiedService'
    if rec_settings_data['rec_mode'] == 0 or rec_settings_data['rec_mode'] == 9:
        recording_mode = 'AllServices'  # 全サービス
    elif rec_settings_data['rec_mode'] == 1 or rec_settings_data['rec_mode'] == 5:
        recording_mode = 'SpecifiedService'  # 指定サービスのみ
    elif rec_settings_data['rec_mode'] == 2 or rec_settings_data['rec_mode'] == 6:
        recording_mode = 'AllServicesWithoutDecoding'  # 全サービス (デコードなし)
    elif rec_settings_data['rec_mode'] == 3 or rec_settings_data['rec_mode'] == 7:
        recording_mode = 'SpecifiedServiceWithoutDecoding'  # 指定サービスのみ (デコードなし)
    elif rec_settings_data['rec_mode'] == 4 or rec_settings_data['rec_mode'] == 8:
        recording_mode = 'View'

    # 字幕データ/データ放送の録画設定は、デフォルト設定を使うか否かを含めすべて下記のビットフラグになっている
    # ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-240212/Common/CommonDef.h#L36-L39
    # #define RECSERVICEMODE_DEF	0x00000000	// デフォルト設定を使用
    # #define RECSERVICEMODE_SET	0x00000001	// 個別の設定値を使用
    # #define RECSERVICEMODE_CAP	0x00000010	// 字幕データを含む
    # #define RECSERVICEMODE_DATA	0x00000020	// データカルーセルを含む

    # 字幕データ/データ放送を録画するかどうか (Default のとき、デフォルト設定に従う)
    caption_recording_mode: Literal['Default', 'Enable', 'Disable']
    data_broadcasting_recording_mode: Literal['Default', 'Enable', 'Disable']
    service_mode = rec_settings_data['service_mode']
    if service_mode & 0x00000001:  # 個別の設定値を使用
        caption_recording_mode = 'Enable' if service_mode & 0x00000010 else 'Disable'
        data_broadcasting_recording_mode = 'Enable' if service_mode & 0x00000020 else 'Disable'
    else:  # デフォルト設定を使用
        caption_recording_mode = 'Default'
        data_broadcasting_recording_mode = 'Default'

    # 録画後動作モード: デフォルト設定に従う / 何もしない / スタンバイ / スタンバイ (復帰後再起動) / 休止 / 休止 (復帰後再起動) / シャットダウン
    # ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-240212/ini/HttpPublic/legacy/util.lua#L522-L528
    post_recording_mode: Literal['Default', 'Nothing', 'Standby', 'StandbyAndReboot', 'Suspend', 'SuspendAndReboot', 'Shutdown'] = 'Default'
    if rec_settings_data['suspend_mode'] == 0:
        post_recording_mode = 'Default'
    elif rec_settings_data['suspend_mode'] == 1 and rec_settings_data['reboot_flag'] is False:
        post_recording_mode = 'Standby'
    elif rec_settings_data['suspend_mode'] == 1 and rec_settings_data['reboot_flag'] is True:
        post_recording_mode = 'StandbyAndReboot'
    elif rec_settings_data['suspend_mode'] == 2 and rec_settings_data['reboot_flag'] is False:
        post_recording_mode = 'Suspend'
    elif rec_settings_data['suspend_mode'] == 2 and rec_settings_data['reboot_flag'] is True:
        post_recording_mode = 'SuspendAndReboot'
    elif rec_settings_data['suspend_mode'] == 3:
        post_recording_mode = 'Shutdown'
    elif rec_settings_data['suspend_mode'] == 4:
        post_recording_mode = 'Nothing'

    # 録画後に実行する bat ファイルのパス / 指定しない場合は None
    post_recording_bat_file_path: str | None = None
    if rec_settings_data['bat_file_path'] != '':
        post_recording_bat_file_path = rec_settings_data['bat_file_path']

    # イベントリレーの追従を行うかどうか
    is_event_relay_follow_enabled: bool = rec_settings_data['tuijyuu_flag']

    # 「ぴったり録画」(録画マージンののりしろを残さず本編のみを正確に録画する？) を行うかどうか
    is_exact_recording_enabled: bool = rec_settings_data['pittari_flag']

    # 録画対象のチャンネルにワンセグ放送が含まれる場合、ワンセグ放送を別ファイルに同時録画するかどうか
    ## partial_rec_flag が 2 の時はワンセグ放送だけを出力できるが、EpgTimer 標準 UI でも設定経路がなく、
    ## KonomiTV でも UI 設計上 0/1 のみを扱う方針のため、2 は非対応とする
    is_oneseg_separate_output_enabled: bool = rec_settings_data['partial_rec_flag'] == 1

    # 同一チャンネルで時間的に隣接した録画予約がある場合に、それらを同一の録画ファイルに続けて出力するかどうか
    is_sequential_recording_in_single_file_enabled: bool = rec_settings_data['continue_rec_flag']

    # チューナーを強制指定する際のチューナー ID / 自動選択の場合は None
    forced_tuner_id: int | None = None
    if rec_settings_data['tuner_id'] != 0:  # 0 は自動選択
        forced_tuner_id = rec_settings_data['tuner_id']

    return schemas.RecordSettings(
        is_enabled = is_enabled,
        priority = priority,
        recording_folders = recording_folders,
        recording_start_margin = recording_start_margin,
        recording_end_margin = recording_end_margin,
        recording_mode = recording_mode,
        caption_recording_mode = caption_recording_mode,
        data_broadcasting_recording_mode = data_broadcasting_recording_mode,
        post_recording_mode = post_recording_mode,
        post_recording_bat_file_path = post_recording_bat_file_path,
        is_event_relay_follow_enabled = is_event_relay_follow_enabled,
        is_exact_recording_enabled = is_exact_recording_enabled,
        is_oneseg_separate_output_enabled = is_oneseg_separate_output_enabled,
        is_sequential_recording_in_single_file_enabled = is_sequential_recording_in_single_file_enabled,
        forced_tuner_id = forced_tuner_id,
    )


def EncodeEDCBRecSettingData(record_settings: schemas.RecordSettings) -> RecSettingDataRequired:
    """
    schemas.RecordSettings オブジェクトを EDCB の RecSettingData オブジェクトに変換する

    Args:
        record_settings (schemas.RecordSettings): schemas.RecordSettings オブジェクト

    Returns:
        RecSettingData: EDCB の RecSettingData オブジェクト
    """

    # 録画モード: 0: 全サービス / 1: 指定サービスのみ / 2: 全サービス (デコードなし) / 3: 指定サービスのみ (デコードなし) / 4: 視聴
    # 5: 指定サービスのみ (無効) / 6: 全サービス (デコードなし) (無効) / 7: 指定サービスのみ (デコードなし) (無効) / 8: 視聴 (無効) / 9: 全サービス (無効)
    ## 歴史的経緯で予約無効を後から追加したためにこうなっているらしい (5 以降の値は無効)
    rec_mode: int = 1
    if record_settings.is_enabled is True:
        if record_settings.recording_mode == 'AllServices':
            rec_mode = 0
        elif record_settings.recording_mode == 'SpecifiedService':
            rec_mode = 1
        elif record_settings.recording_mode == 'AllServicesWithoutDecoding':
            rec_mode = 2
        elif record_settings.recording_mode == 'SpecifiedServiceWithoutDecoding':
            rec_mode = 3
        elif record_settings.recording_mode == 'View':
            rec_mode = 4
    else:
        if record_settings.recording_mode == 'AllServices':
            rec_mode = 9
        elif record_settings.recording_mode == 'SpecifiedService':
            rec_mode = 5
        elif record_settings.recording_mode == 'AllServicesWithoutDecoding':
            rec_mode = 6
        elif record_settings.recording_mode == 'SpecifiedServiceWithoutDecoding':
            rec_mode = 7
        elif record_settings.recording_mode == 'View':
            rec_mode = 8

    # 録画予約の優先度: 1 ~ 5 の数値で数値が大きいほど優先度が高い
    priority: int = record_settings.priority

    # イベントリレーの追従を行うかどうか
    tuijyuu_flag: bool = record_settings.is_event_relay_follow_enabled

    # 字幕データ/データ放送の録画設定
    ## ビットフラグになっているため、それぞれのフラグを立てる
    service_mode: int = 0
    ## 両方が Default ではない場合のみ個別の設定値を使用するフラグを立てる
    if record_settings.caption_recording_mode != 'Default' and record_settings.data_broadcasting_recording_mode != 'Default':
        service_mode = 1  # 個別の設定値を使用する
    ## 字幕データを含むかどうか
    if record_settings.caption_recording_mode == 'Enable':
        service_mode |= 0x00000010
    ## データカルーセルを含むかどうか
    if record_settings.data_broadcasting_recording_mode == 'Enable':
        service_mode |= 0x00000020

    # 「ぴったり録画」(録画マージンののりしろを残さず本編のみを正確に録画する？) を行うかどうか
    pittari_flag: bool = record_settings.is_exact_recording_enabled

    # 録画後に実行する bat ファイルのパス
    bat_file_path: str = ''
    if record_settings.post_recording_bat_file_path is not None:
        bat_file_path = record_settings.post_recording_bat_file_path

    # 保存先の録画フォルダのパスのリスト
    ## 空リストのときはデフォルトの録画フォルダに保存されるため問題ない
    rec_folder_list: list[RecFileSetInfoRequired] = []
    partial_rec_folder: list[RecFileSetInfoRequired] = []
    for recording_folder in record_settings.recording_folders:
        # TS 書き込みプラグインは基本 Write_Default.dll しかないので固定
        ## 一応 Write_OneService.dll や Write_Multi とかがなくもないが、利用用途があるのかすら知らないため無視
        write_plug_in = 'Write_Default.dll'
        # 録画ファイル名変更プラグインは RecName_Macro.dll しかないので固定
        ## 空文字列にすると EpgTimerSrv 設定の「録画時のファイル名に PlugIn を使用する」が有効かどうか次第になるが、
        ## わざわざ無効にするユースケースがほとんどないため、KonomiTV では EpgTimerSrv での設定値に関わらず常に有効化する
        rec_name_plug_in = 'RecName_Macro.dll'
        # ファイル名テンプレートが指定されている場合は ? 以降に RecName_Macro.dll へのオプションとして追加する
        if recording_folder.recording_file_name_template is not None:
            rec_name_plug_in = f'RecName_Macro.dll?{recording_folder.recording_file_name_template}'
        # ワンセグ録画フォルダかどうかで分ける
        if recording_folder.is_oneseg_separate_recording_folder is False:
            rec_folder_list.append({
                'rec_folder': recording_folder.recording_folder_path,
                'write_plug_in': write_plug_in,
                'rec_name_plug_in': rec_name_plug_in,
            })
        else:
            partial_rec_folder.append({
                'rec_folder': recording_folder.recording_folder_path,
                'write_plug_in': write_plug_in,
                'rec_name_plug_in': rec_name_plug_in,
            })

    # 録画後動作モード: デフォルト設定に従う / 何もしない / スタンバイ / スタンバイ (復帰後再起動) / 休止 / 休止 (復帰後再起動) / シャットダウン
    suspend_mode: int = 0
    reboot_flag: bool = False
    if record_settings.post_recording_mode == 'Default':
        suspend_mode = 0
    elif record_settings.post_recording_mode == 'Nothing':
        suspend_mode = 4
    elif record_settings.post_recording_mode == 'Standby':
        suspend_mode = 1
    elif record_settings.post_recording_mode == 'StandbyAndReboot':
        suspend_mode = 1
        reboot_flag = True
    elif record_settings.post_recording_mode == 'Suspend':
        suspend_mode = 2
    elif record_settings.post_recording_mode == 'SuspendAndReboot':
        suspend_mode = 2
        reboot_flag = True
    elif record_settings.post_recording_mode == 'Shutdown':
        suspend_mode = 3

    # 録画開始マージン (秒) / デフォルト設定に従う場合は存在しない (一旦ここでは None にしておく)
    start_margin: int | None = record_settings.recording_start_margin

    # 録画終了マージン (秒) / デフォルト設定に従う場合は存在しない (一旦ここでは None にしておく)
    end_margin: int | None = record_settings.recording_end_margin

    # 同一チャンネルで時間的に隣接した録画予約がある場合に、それらを同一の録画ファイルに続けて出力するかどうか
    continue_rec_flag: bool = record_settings.is_sequential_recording_in_single_file_enabled

    # 録画対象のチャンネルにワンセグ放送が含まれる場合、ワンセグ放送を別ファイルに同時録画するかどうか
    ## partial_rec_flag が 2 の時はワンセグ放送だけを出力できるが、EpgTimer 標準 UI でも設定経路がなく、
    ## KonomiTV でも UI 設計上 0/1 のみを扱う方針のため、2 は非対応とする
    partial_rec_flag: int = 1 if record_settings.is_oneseg_separate_output_enabled is True else 0

    # チューナーを強制指定する際のチューナー ID / 自動選択の場合は 0 を指定
    tuner_id: int = 0
    if record_settings.forced_tuner_id is not None:
        tuner_id = record_settings.forced_tuner_id

    # EDCB の RecSettingData オブジェクトを作成
    rec_setting_data: RecSettingDataRequired = {
        'rec_mode': rec_mode,
        'priority': priority,
        'tuijyuu_flag': tuijyuu_flag,
        'service_mode': service_mode,
        'pittari_flag': pittari_flag,
        'bat_file_path': bat_file_path,
        'rec_folder_list': rec_folder_list,
        'suspend_mode': suspend_mode,
        'reboot_flag': reboot_flag,
        'continue_rec_flag': continue_rec_flag,
        'partial_rec_flag': partial_rec_flag,
        'tuner_id': tuner_id,
        'partial_rec_folder': partial_rec_folder,
    }

    # 録画マージンはデフォルト設定に従う場合は存在しないため、それぞれの値が None でない場合のみ追加する
    if start_margin is not None:
        rec_setting_data['start_margin'] = start_margin
    if end_margin is not None:
        rec_setting_data['end_margin'] = end_margin

    return rec_setting_data


def GetCtrlCmdUtil() -> CtrlCmdUtil:
    """ バックエンドが EDCB かのチェックを行い、EDCB であれば EDCB の CtrlCmdUtil インスタンスを返す """

    if Config().general.backend == 'EDCB':
        return CtrlCmdUtil()
    else:
        logging.warning('[ReservationsRouter][GetCtrlCmdUtil] This API is only available when the backend is EDCB.')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'This API is only available when the backend is EDCB',
        )


async def GetReserveDataList(
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
) -> list[ReserveDataRequired]:
    """ すべての録画予約の情報を取得する """

    # EDCB から録画予約の一覧を取得
    reserve_data_list: list[ReserveDataRequired] | None = await edcb.sendEnumReserve()
    if reserve_data_list is None:
        # None が返ってきた場合はエラーを返す
        logging.error('[ReservationsRouter][GetReserveDataList] Failed to get the list of recording reservations.')
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'Failed to get the list of recording reservations',
        )

    return reserve_data_list


async def GetRequiredProgramsForReservations(reserve_data_list: list[ReserveDataRequired]) -> dict[tuple[int, int, int], Program]:
    """
    録画予約に必要な番組情報を一括取得する

    Args:
        reserve_data_list (list[ReserveDataRequired]): EDCB の ReserveData オブジェクトのリスト

    Returns:
        dict[tuple[int, int, int], Program]: (network_id, service_id, event_id) をキーとした番組情報の辞書
    """

    if not reserve_data_list:
        return {}

    # 録画予約から必要な番組の (network_id, service_id, event_id) の組み合わせを抽出
    program_keys = set()
    for reserve_data in reserve_data_list:
        program_keys.add((reserve_data['onid'], reserve_data['sid'], reserve_data['eid']))

    if not program_keys:
        return {}

    # SQL の検索条件を生成
    ## network_id, service_id, event_id は整数値で SQL インジェクションの心配はないので直接埋め込む
    ## Tortoise ORM の Model.raw() がパラメーターバインディング自体に対応していないのも理由
    safe_conditions = []
    for network_id, service_id, event_id in program_keys:
        safe_conditions.append(f'(network_id = {network_id} AND service_id = {service_id} AND event_id = {event_id})')
    if not safe_conditions:
        return {}

    # 高速化のため生 SQL クエリを実行
    sql = f'''
        SELECT *
        FROM programs
        WHERE {' OR '.join(safe_conditions)}
    '''
    programs = cast(list[Program], await Program.raw(sql))

    # 結果を辞書形式に変換
    programs_dict: dict[tuple[int, int, int], Program] = {}
    for program in programs:
        key = (program.network_id, program.service_id, program.event_id)
        programs_dict[key] = program

    return programs_dict


async def GetReserveData(
    reservation_id: Annotated[int, Path(description='録画予約 ID 。')],
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
) -> ReserveDataRequired:
    """
    指定された録画予約の情報を取得する

    Args:
        reservation_id (int): 録画予約 ID
        edcb (CtrlCmdUtil): EDCB API クライアント

    Returns:
        ReserveDataRequired: EDCB の ReserveData オブジェクト

    Raises:
        HTTPException: 指定された録画予約が見つからなかった場合
    """

    # 指定された録画予約の情報を取得
    for reserve_data in await GetReserveDataList(edcb):
        if reserve_data['reserve_id'] == reservation_id:
            return reserve_data

    # 指定された録画予約が見つからなかった場合はエラーを返す
    logging.error(f'[ReservesRouter][GetReserveData] Specified reservation_id was not found. [reservation_id: {reservation_id}]')
    raise HTTPException(
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail = 'Specified reservation_id was not found',
    )


async def GetServiceEventInfo(
    channel: Channel,
    program: Program,
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
) -> tuple[ServiceEventInfo, EventInfo]:
    """
    EDCB から指定されたチャンネル情報・番組情報に合致する ServiceEventInfo と EventInfo を取得する

    Args:
        channel (Channel): 録画予約対象のチャンネル情報
        program (Program): 録画予約対象として指定された番組情報
        edcb (CtrlCmdUtil): EDCB API クライアント

    Returns:
        tuple[ServiceEventInfo, EventInfo]: 解決できたサービス情報とイベント情報
    """

    def FindEventByEventID(service_event_info_list: list[ServiceEventInfo], event_id: int) -> tuple[ServiceEventInfo, EventInfo] | None:
        """
        ServiceEventInfo リストから、イベント ID が一致する EventInfo を探す

        Args:
            service_event_info_list (list[ServiceEventInfo]): EDCB から取得したサービス情報のリスト
            event_id (int): 探索対象のイベント ID

        Returns:
            tuple[ServiceEventInfo, EventInfo] | None: 一致したサービス情報とイベント情報
        """

        for service_event_info in service_event_info_list:
            for event_info in service_event_info.get('event_list', []):
                if event_info['eid'] == event_id:
                    return service_event_info, event_info
        return None

    def FindOnAirEvent(service_event_info_list: list[ServiceEventInfo], current_time: datetime) -> tuple[ServiceEventInfo, EventInfo] | None:
        """
        ServiceEventInfo リストから、現在放送中の EventInfo を探す

        Args:
            service_event_info_list (list[ServiceEventInfo]): EDCB から取得したサービス情報のリスト
            current_time (datetime): 判定基準時刻

        Returns:
            tuple[ServiceEventInfo, EventInfo] | None: 現在放送中のサービス情報とイベント情報
        """

        for service_event_info in service_event_info_list:
            for event_info in service_event_info.get('event_list', []):
                if 'start_time' not in event_info or 'duration_sec' not in event_info:
                    continue
                event_end_time = event_info['start_time'] + timedelta(seconds=max(event_info['duration_sec'], 1))
                if event_info['start_time'] <= current_time < event_end_time:
                    return service_event_info, event_info
        return None

    # EDCB からサービスと当該番組の開始時刻を指定して番組情報を取得
    ## EIT[p/f] と EIT[schedule] の更新タイミング差で番組開始時刻がずれることがあるため、
    ## まずは番組開始時刻近傍で探索し、それで見つからなければ現在時刻近傍の広い範囲で再探索する
    assert channel.transport_stream_id is not None, 'transport_stream_id is missing.'
    current_time = datetime.now(JST)
    program_start_time = NormalizeToJSTDatetime(program.start_time)
    search_ranges = [
        (program_start_time, program_start_time + timedelta(minutes=1), 'program_time_window'),
        (current_time - timedelta(hours=6), current_time + timedelta(hours=6), 'current_time_wide_window'),
    ]
    latest_service_event_info_list: list[ServiceEventInfo] = []
    for start_time, end_time, search_label in search_ranges:
        service_event_info_list = await edcb.sendEnumPgInfoEx([
            # 絞り込み対象のネットワーク ID・トランスポートストリーム ID・サービス ID に掛けるビットマスク (?????)
            ## 意味が分からないけどとりあえず今回はビットマスクは使用しないので 0 を指定
            0,
            # 絞り込み対象のネットワーク ID・トランスポートストリーム ID・サービス ID
            ## (network_id << 32 | transport_stream_id << 16 | service_id) の形式で指定しなければならないらしい
            channel.network_id << 32 | channel.transport_stream_id << 16 | channel.service_id,
            # 絞り込み対象の番組開始時刻の最小値
            ## datetimeToFileTime() は内部で tz.utcoffset(None) を呼ぶため、
            ## ZoneInfo ではなく固定オフセットの datetime.timezone を渡す必要がある
            EDCBUtil.datetimeToFileTime(start_time, timezone(timedelta(hours=9))),
            # 絞り込み対象の番組開始時刻の最大値
            EDCBUtil.datetimeToFileTime(end_time, timezone(timedelta(hours=9))),
        ])
        if service_event_info_list is None or len(service_event_info_list) == 0:
            logging.warning(
                f'[ReservationsRouter][GetServiceEventInfo] No program information found in search range. [channel_id: {channel.id} / program_id: {program.id} / search_label: {search_label}]',
            )
            continue
        latest_service_event_info_list = service_event_info_list

        # まずイベント ID 一致を最優先で探す
        matched_event = FindEventByEventID(service_event_info_list, program.event_id)
        if matched_event is not None:
            # 一致したイベントが既に終了していて、かつ現在放送中イベントが別に存在する場合は現在放送中イベントへ切り替える
            ## スポーツ延長などで番組詳細パネルの EID が古いまま残ったケースを救済する
            on_air_event = FindOnAirEvent(service_event_info_list, current_time)
            if ('start_time' in matched_event[1] and
                'duration_sec' in matched_event[1] and
                on_air_event is not None and
                on_air_event[1]['eid'] != matched_event[1]['eid']):
                matched_event_end_time = matched_event[1]['start_time'] + timedelta(seconds=max(matched_event[1]['duration_sec'], 1))
                if current_time >= matched_event_end_time:
                    logging.warning(
                        f'[ReservationsRouter][GetServiceEventInfo] Matched event is already ended, switched to on-air event. [channel_id: {channel.id} / program_id: {program.id} / requested_event_id: {program.event_id} / matched_event_id: {matched_event[1]["eid"]} / resolved_event_id: {on_air_event[1]["eid"]}]',
                    )
                    return on_air_event
            return matched_event

    # イベント ID が一致しないとき、番組が既に終了扱いなら現在放送中イベントへフェイルオーバーする
    ## 長時間延長などで EPG の切り替わりが遅延したケースでは、指定 EID が実態とずれていることがある
    requested_program_end_time = program_start_time + timedelta(seconds=max(int(program.duration), 1))
    if latest_service_event_info_list and current_time >= requested_program_end_time:
        on_air_event = FindOnAirEvent(latest_service_event_info_list, current_time)
        if on_air_event is not None:
            logging.warning(
                f'[ReservationsRouter][GetServiceEventInfo] Falling back to on-air event because event_id mismatch. [channel_id: {channel.id} / program_id: {program.id} / requested_event_id: {program.event_id} / resolved_event_id: {on_air_event[1]["eid"]}]',
            )
            return on_air_event

    # 最終的に番組情報が取得できなかった場合はエラーを返す
    logging.error(
        f'[ReservationsRouter][GetServiceEventInfo] Failed to resolve program information from EDCB. [channel_id: {channel.id} / program_id: {program.id} / requested_event_id: {program.event_id}]',
    )
    raise HTTPException(
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail = 'Failed to resolve program information from EDCB',
    )


def ShouldCheckRecordingInProgress(reserve_data: ReserveDataRequired) -> bool:
    """
    録画中判定のために EDCB へ追加問い合わせを行うべきかを判定する。

    Args:
        reserve_data (ReserveDataRequired): 判定対象の予約情報

    Returns:
        bool: 追加問い合わせが必要な場合は True
    """

    # 無効予約・視聴予約は録画ファイルパスが存在しないため、判定 API を呼ばない
    rec_mode = reserve_data.get('rec_setting', {}).get('rec_mode', 1)
    if rec_mode >= 5 or rec_mode == 4:
        return False

    # 録画中判定を行う時間範囲 (現在時刻の2時間前〜2時間後)
    # 番組延長や繰り上げを考慮しつつ、現在時刻から大きく離れた予約には高コストな追加問い合わせを行わない
    current_time = datetime.now(tz=JST)
    recording_check_start = current_time - timedelta(hours=2)
    recording_check_end = current_time + timedelta(hours=2)

    reserve_start_time = NormalizeToJSTDatetime(reserve_data['start_time'])
    reserve_end_time = reserve_start_time + timedelta(seconds=reserve_data['duration_second'])

    return reserve_start_time <= recording_check_end and reserve_end_time >= recording_check_start


async def GetIsRecordingInProgress(reserve_data: ReserveDataRequired, edcb: CtrlCmdUtil) -> bool:
    """
    指定された予約が現在録画中かどうかを判定する。

    Args:
        reserve_data (ReserveDataRequired): 判定対象の予約情報
        edcb (CtrlCmdUtil): EDCB API クライアント

    Returns:
        bool: 録画中の場合は True
    """

    # 録画中判定が不要な予約では追加問い合わせを行わない
    if ShouldCheckRecordingInProgress(reserve_data) is False:
        return False

    # CtrlCmdUtil.sendGetRecFilePath() で「録画中かつ視聴予約でない予約の録画ファイルパス」が返ってくる場合は True、それ以外は False
    ## 歴史的経緯でこう取得することになっているらしい
    return isinstance(await edcb.sendGetRecFilePath(reserve_data['reserve_id']), str)


@router.get(
    '',
    summary = '録画予約情報一覧 API',
    response_description = '録画予約の情報のリスト。',
    response_model = schemas.Reservations,
)
async def ReservationsAPI(
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
):
    """
    すべての録画予約の情報を取得する。
    """

    # EDCB から現在のすべての録画予約の情報を取得
    reserve_data_list: list[ReserveDataRequired] | None = await edcb.sendEnumReserve()
    if reserve_data_list is None:
        # None が返ってきた場合は空のリストを返す
        return schemas.Reservations(total=0, reservations=[])

    # データベースアクセスを伴うので、トランザクション下に入れた上で並行して行う
    async with transactions.in_transaction():

        # 高速化のため、あらかじめ全てのチャンネル情報を取得しておく
        channels = await Channel.all()

        # 高速化のため、録画予約に必要な番組情報を一括取得しておく
        programs = await GetRequiredProgramsForReservations(reserve_data_list)

        # 録画中判定が必要な予約のみ EDCB へ問い合わせる
        # 必要最小限の予約に絞ることで、視聴中の定期更新時の EDCB 負荷を抑える
        is_recording_in_progress_by_reserve_id: dict[int, bool] = {}
        for reserve_data in reserve_data_list:
            is_recording_in_progress_by_reserve_id[reserve_data['reserve_id']] = await GetIsRecordingInProgress(reserve_data, edcb)

        # EDCB の ReserveData オブジェクトを schemas.Reservation オブジェクトに変換
        reserves = await asyncio.gather(*(
            DecodeEDCBReserveData(
                reserve_data,
                channels,
                programs,
                is_recording_in_progress = is_recording_in_progress_by_reserve_id[reserve_data['reserve_id']],
            )
            for reserve_data in reserve_data_list
        ))

    # 録画予約番組の番組開始時刻でソート
    reserves.sort(key=lambda reserve: reserve.program.start_time)

    return schemas.Reservations(total=len(reserve_data_list), reservations=reserves)


@router.post(
    '',
    summary = '録画予約追加 API',
    status_code = status.HTTP_201_CREATED,
)
async def AddReservationAPI(
    reserve_add_request: Annotated[schemas.ReservationAddRequest, Body(description='追加する録画予約の設定。')],
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
):
    """
    録画予約を追加する。
    """

    # 指定された番組 ID の番組があるかを確認
    program = await Program.filter(id=reserve_add_request.program_id).get_or_none()
    if program is None:
        logging.error(f'[ReservesRouter][AddReserveAPI] Specified program was not found. [program_id: {reserve_add_request.program_id}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified program was not found',
        )

    # 指定された番組 ID に関連付けられたチャンネルがあるかを確認
    channel = await Channel.filter(id=program.channel_id).get_or_none()
    if channel is None:
        logging.error(f'[ReservesRouter][AddReserveAPI] Specified channel was not found. [channel_id: {program.channel_id}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified channel was not found',
        )

    # EDCB バックエンド利用時は必ずチャンネル情報に transport_stream_id が含まれる
    assert channel.transport_stream_id is not None, 'transport_stream_id is missing.'

    def HasSameReservation(
        reserve_data_list: list[ReserveDataRequired],
        network_id: int,
        transport_stream_id: int,
        service_id: int,
        event_id: int,
    ) -> bool:
        """
        同一 ONID/TSID/SID/EID の録画予約が既に存在するかを判定する

        Args:
            reserve_data_list (list[ReserveDataRequired]): EDCB から取得した録画予約一覧
            network_id (int): ネットワーク ID (ONID)
            transport_stream_id (int): トランスポートストリーム ID (TSID)
            service_id (int): サービス ID (SID)
            event_id (int): イベント ID (EID)

        Returns:
            bool: 同一予約が存在する場合は True
        """

        for reserve_data in reserve_data_list:
            if (reserve_data['onid'] == network_id and
                reserve_data['tsid'] == transport_stream_id and
                reserve_data['sid'] == service_id and
                reserve_data['eid'] == event_id):
                return True
        return False

    # すでに同じ番組 ID の録画予約が存在するかを確認
    reserve_data_list = await GetReserveDataList(edcb)
    if HasSameReservation(
        reserve_data_list,
        channel.network_id,
        channel.transport_stream_id,
        channel.service_id,
        program.event_id,
    ) is True:
        logging.error(f'[ReservationsRouter][AddReserveAPI] The same program_id is already reserved. [program_id: {reserve_add_request.program_id}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'The same program_id is already reserved',
        )

    # EDCB から録画予約対象の番組に一致する ServiceEventInfo を取得
    ## KonomiTV のデータベースに保存されているチャンネル名・番組名は表示上に半角に加工されているため、EDCB に設定するには不適切
    ## 内部仕様がわからないけど予約に設定されている番組名と EPG 上の番組名が異なると予期せぬ問題が発生しそうな気もする
    ## それ以外にも KonomiTV 側に保存されている情報が古くなっている可能性もあるため、毎回 EDCB から最新の情報を取得する
    service_event_info, event_info = await GetServiceEventInfo(channel, program, edcb)

    # ReserveData オブジェクトに設定するチャンネル情報・番組情報を取得
    ## 放送時間未定運用などでごく稀に取得できないことも考えられるため、その場合は KonomiTV 側が持っている情報にフォールバックする
    ## 当然 TSInformation.formatString() はかけずにそのままの情報を使う
    ## ref: https://github.com/EMWUI/EDCB_Material_WebUI/blob/master/HttpPublic/api/SetReserve#L4-L39
    title: str = program.title
    start_time: datetime = NormalizeToJSTDatetime(program.start_time)
    duration_second: int = max(int(program.duration), 1)
    station_name: str = service_event_info['service_info']['service_name']
    event_id: int = program.event_id
    if 'short_info' in event_info and 'event_name' in event_info['short_info']:
        title = event_info['short_info']['event_name']
    if 'start_time' in event_info:
        start_time = NormalizeToJSTDatetime(event_info['start_time'])
    if 'duration_sec' in event_info:
        duration_second = max(event_info['duration_sec'], 1)
    if 'eid' in event_info:
        event_id = event_info['eid']

    # 実際に予約するイベント ID がリクエストされたイベント ID と異なる場合は重複チェックをやり直す
    ## EPG 更新の遅延でフロントエンドが持つ EID が古い場合で、現在放送中のイベントへフェイルオーバーした時に二重予約を防ぐ
    if event_id != program.event_id:
        if HasSameReservation(
            reserve_data_list,
            channel.network_id,
            channel.transport_stream_id,
            channel.service_id,
            event_id,
        ) is True:
            logging.error(
                f'[ReservationsRouter][AddReserveAPI] The fallback event is already reserved. [program_id: {reserve_add_request.program_id} / requested_event_id: {program.event_id} / resolved_event_id: {event_id}]',
            )
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail = 'The fallback event is already reserved',
            )

    # EDCB の ReserveData オブジェクトを組み立てる
    ## 一見省略しても良さそうな録画予約対象のチャンネル情報や番組情報なども省略せずに全て含める必要がある (さもないと録画予約情報が破壊される…)
    ## ただし reserve_id / overlap_mode / rec_file_name_list は EDCB 側で自動設定される (?) ため省略している
    add_reserve_data: ReserveData = {
        'title': title,
        'start_time': start_time,
        'start_time_epg': start_time,
        'duration_second': duration_second,
        'station_name': station_name,
        'onid': channel.network_id,
        'tsid': channel.transport_stream_id,
        'sid': channel.service_id,
        'eid': event_id,
        'comment': '',  # 単発予約の場合は空文字列で問題ないはず
        'rec_setting': cast(RecSettingData, EncodeEDCBRecSettingData(reserve_add_request.record_settings)),
    }

    # EDCB に録画予約を追加するように指示
    result = await edcb.sendAddReserve([add_reserve_data])
    if result is False:
        # EDCB が「現在時刻で既に放送終了扱い」と判断した可能性がある場合のみ、時刻補正して 1 回だけ再試行する
        current_time = datetime.now(JST)
        reserve_end_time = start_time + timedelta(seconds=max(duration_second, 1))
        if current_time >= reserve_end_time:
            retry_duration_second = max(int((current_time - start_time).total_seconds()) + 120, 120)
            retry_add_reserve_data = dict(add_reserve_data)
            retry_add_reserve_data['duration_second'] = retry_duration_second
            logging.warning(
                f'[ReservationsRouter][AddReserveAPI] Retrying with adjusted duration because reservation window looks expired. [program_id: {reserve_add_request.program_id} / event_id: {event_id} / original_duration_second: {duration_second} / retry_duration_second: {retry_duration_second}]',
            )

            # 再試行前に重複予約を再確認する
            latest_reserve_data_list = await GetReserveDataList(edcb)
            if HasSameReservation(
                latest_reserve_data_list,
                channel.network_id,
                channel.transport_stream_id,
                channel.service_id,
                event_id,
            ) is True:
                logging.error(
                    f'[ReservationsRouter][AddReserveAPI] Reservation already exists before retry. [program_id: {reserve_add_request.program_id} / event_id: {event_id}]',
                )
                raise HTTPException(
                    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail = 'The same program_id is already reserved',
                )

            retry_result = await edcb.sendAddReserve([cast(ReserveData, retry_add_reserve_data)])
            if retry_result is True:
                logging.info(
                    f'[ReservationsRouter][AddReserveAPI] Added reservation with adjusted duration fallback. [program_id: {reserve_add_request.program_id} / event_id: {event_id} / retry_duration_second: {retry_duration_second}]',
                )
                return

        # それでも失敗した場合は、重複・イベント不整合・通信系を判別しやすいログを残したうえでエラーを返す
        latest_reserve_data_list = await GetReserveDataList(edcb)
        if HasSameReservation(
            latest_reserve_data_list,
            channel.network_id,
            channel.transport_stream_id,
            channel.service_id,
            event_id,
        ) is True:
            logging.error(
                f'[ReservationsRouter][AddReserveAPI] Reservation was added by another process concurrently. [program_id: {reserve_add_request.program_id} / event_id: {event_id}]',
            )
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail = 'The same program_id is already reserved',
            )

        logging.error(
            f'[ReservationsRouter][AddReserveAPI] Failed to add a recording reservation. [program_id: {reserve_add_request.program_id} / requested_event_id: {program.event_id} / resolved_event_id: {event_id} / start_time: {start_time.isoformat()} / duration_second: {duration_second}]',
        )
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'Failed to add a recording reservation due to EDCB rejection or event mismatch',
        )

    # どの録画予約 ID で追加されたかは sendAddReserve() のレスポンスからは取れないので、201 Created を返す


@router.get(
    '/{reservation_id}',
    summary = '録画予約情報取得 API',
    response_description = '録画予約の情報。',
    response_model = schemas.Reservation,
)
async def ReservationAPI(
    reserve_data: Annotated[ReserveDataRequired, Depends(GetReserveData)],
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
):
    """
    指定された録画予約の情報を取得する。
    """

    # EDCB の ReserveData オブジェクトを schemas.Reservation オブジェクトに変換して返す
    return await DecodeEDCBReserveData(
        reserve_data,
        is_recording_in_progress = await GetIsRecordingInProgress(reserve_data, edcb),
    )


@router.put(
    '/{reservation_id}',
    summary = '録画予約設定更新 API',
    response_description = '更新された録画予約の情報。',
    response_model = schemas.Reservation,
)
async def UpdateReservationAPI(
    reserve_data: Annotated[ReserveDataRequired, Depends(GetReserveData)],
    reserve_update_request: Annotated[schemas.ReservationUpdateRequest, Body(description='更新する録画予約の設定。')],
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
):
    """
    指定された録画予約の設定を更新する。
    """

    # 現在の録画予約の ReserveData に新しい録画設定を上書きマージする形で EDCB に送信する
    ## 一見省略しても良さそうな録画予約対象のチャンネル情報や番組情報なども省略せずに全て含める必要がある (さもないと録画予約情報が破壊される…)
    reserve_data['rec_setting'] = EncodeEDCBRecSettingData(reserve_update_request.record_settings)

    # EDCB に指定された録画予約を更新するように指示
    result = await edcb.sendChgReserve([cast(ReserveData, reserve_data)])
    if result is False:
        # False が返ってきた場合はエラーを返す
        logging.error('[ReservationsRouter][UpdateReserveAPI] Failed to update the specified recording reservation.')
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'Failed to update the specified recording reservation',
        )

    # 更新された録画予約の情報を schemas.Reservation オブジェクトに変換して返す
    updated_reserve_data = await GetReserveData(reserve_data['reserve_id'], edcb)
    return await DecodeEDCBReserveData(
        updated_reserve_data,
        is_recording_in_progress = await GetIsRecordingInProgress(updated_reserve_data, edcb),
    )


@router.delete(
    '/{reservation_id}',
    summary = '録画予約削除 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def DeleteReservationAPI(
    reserve_data: Annotated[ReserveDataRequired, Depends(GetReserveData)],
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
):
    """
    指定された録画予約を削除する。
    """

    # EDCB に指定された録画予約を削除するように指示
    result = await edcb.sendDelReserve([reserve_data['reserve_id']])
    if result is False:
        # False が返ってきた場合はエラーを返す
        logging.error('[ReservationsRouter][DeleteReserveAPI] Failed to delete the specified recording reservation.')
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'Failed to delete the specified recording reservation',
        )
