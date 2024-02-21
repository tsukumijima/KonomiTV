
import asyncio
from datetime import datetime
from datetime import timedelta
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Path
from fastapi import status
from tortoise import transactions
from typing import Annotated, Any, cast, Literal

from app import schemas
from app.config import Config
from app.models.Channel import Channel
from app.models.Program import Program
from app.utils.EDCB import CtrlCmdUtil
from app.utils.EDCB import RecSettingDataRequired
from app.utils.EDCB import ReserveDataRequired
from app.utils.TSInformation import TSInformation


# ルーター
router = APIRouter(
    tags = ['Reserves'],
    prefix = '/api/reserves',
)


async def ConvertEDCBReserveDataToReserve(reserve_data: ReserveDataRequired, channels: list[Channel] | None = None) -> schemas.Reserve:
    """
    EDCB の ReserveData オブジェクトを schemas.Reserve オブジェクトに変換する

    Args:
        reserve_data (ReserveDataRequired): EDCB の ReserveData オブジェクト
        channels (list[Channel] | None): あらかじめ全てのチャンネル情報を取得しておく場合はそのリスト、そうでない場合は None

    Returns:
        schemas.Reserve: schemas.Reserve オブジェクト
    """

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
            channel.remocon_id = channel.calculateRemoconID()
        # チャンネル番号を算出
        channel.channel_number = await channel.calculateChannelNumber()
        # 改めて表示用チャンネル ID を算出
        channel.display_channel_id = channel.type.lower() + channel.channel_number
        # このチャンネルがサブチャンネルかを算出
        channel.is_subchannel = channel.calculateIsSubchannel()

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
    program: Program | None = await Program.filter(network_id=channel.network_id, service_id=channel.service_id, event_id=event_id).get_or_none()
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

    # 録画予約が現在進行中かどうか
    ## CtrlCmdUtil.sendGetRecFilePath() で「録画中かつ視聴予約でない予約の録画ファイルパス」が返ってくる場合は True、それ以外は False
    ## 歴史的経緯でこう取得することになっているらしい
    edcb = CtrlCmdUtil()
    is_recording_in_progress: bool = type(await edcb.sendGetRecFilePath(reserve_id)) is str

    # 録画予約の被り状態: 被りなし (予約可能) / 被ってチューナー足りない予約あり / チューナー足りないため予約できない
    # ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-240212/Common/CommonDef.h#L32-L34
    # ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-240212/Common/StructDef.h#L62
    overlap_status: Literal['NoOverlap', 'HasOverlap', 'CannotReserve'] = 'NoOverlap'
    if reserve_data['overlap_mode'] == 1:
        overlap_status = 'HasOverlap'
    elif reserve_data['overlap_mode'] == 2:
        overlap_status = 'CannotReserve'

    # コメント: EPG 予約で自動追加された予約なら "EPG自動予約" と入る
    comment: str = reserve_data['comment']

    # 録画予定のファイル名
    ## EDCB からのレスポンスでは配列になっているが、大半の場合は 1 つしかないため単一の値としている
    scheduled_recording_file_name: str = ''
    if len(reserve_data['rec_file_name_list']) > 0:
        scheduled_recording_file_name = reserve_data['rec_file_name_list'][0]

    # 録画設定
    record_settings: schemas.RecordSettings = ConvertEDCBRecSettingDataToReRecordSettings(reserve_data['rec_setting'])

    # Tortoise ORM モデルは本来 Pydantic モデルと型が非互換だが、FastAPI がよしなに変換してくれるので雑に Any にキャストしている
    ## 逆に自前で変換する方法がわからない…
    return schemas.Reserve(
        id = reserve_id,
        channel = cast(Any, channel),
        program = cast(Any, program),
        is_recording_in_progress = is_recording_in_progress,
        overlap_status = overlap_status,
        comment = comment,
        scheduled_recording_file_name = scheduled_recording_file_name,
        record_settings = record_settings,
    )


def ConvertEDCBRecSettingDataToReRecordSettings(rec_settings_data: RecSettingDataRequired) -> schemas.RecordSettings:
    """
    EDCB の RecSettingData オブジェクトを schemas.RecordSettings オブジェクトに変換する

    Args:
        rec_settings_data (RecSettingDataRequired): EDCB の RecSettingData オブジェクト

    Returns:
        schemas.RecordSettings: schemas.RecordSettings オブジェクト
    """

    # 録画モード: 全サービス / 全サービス (デコードなし) / 指定サービスのみ / 指定サービスのみ (デコードなし) / 視聴
    # 通常の用途では「指定サービスのみ」以外はまず使わない
    ## ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-240212/Common/CommonDef.h#L26-L30
    ## ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-240212/Document/Readme_Mod.txt#L264-L266
    record_mode: Literal['AllService', 'AllServiceWithoutDecoding', 'SpecifiedService', 'SpecifiedServiceWithoutDecoding', 'View'] = 'SpecifiedService'
    if rec_settings_data['rec_mode'] == 0 or rec_settings_data['rec_mode'] == 9:
        record_mode = 'AllService'  # 全サービス
    elif rec_settings_data['rec_mode'] == 1 or rec_settings_data['rec_mode'] == 5:
        record_mode = 'SpecifiedService'  # 指定サービスのみ
    elif rec_settings_data['rec_mode'] == 2 or rec_settings_data['rec_mode'] == 6:
        record_mode = 'AllServiceWithoutDecoding'  # 全サービス (デコードなし)
    elif rec_settings_data['rec_mode'] == 3 or rec_settings_data['rec_mode'] == 7:
        record_mode = 'SpecifiedServiceWithoutDecoding'  # 指定サービスのみ (デコードなし)
    elif rec_settings_data['rec_mode'] == 4 or rec_settings_data['rec_mode'] == 8:
        record_mode = 'View'

    # 録画予約が有効かどうか
    is_enabled: bool = rec_settings_data['rec_mode'] <= 4  # 0 ~ 4 なら有効

    # 録画予約の優先度: 1 ~ 5 の数値で数値が大きいほど優先度が高い
    priority: int = rec_settings_data['priority']

    # 録画開始マージン (秒) / デフォルト設定に従う場合は None
    recording_start_margin: int | None = None
    if 'start_margin' in rec_settings_data:
        recording_start_margin = rec_settings_data['start_margin']

    # 録画終了マージン (秒) / デフォルト設定に従う場合は None
    recording_end_margin: int | None = None
    if 'end_margin' in rec_settings_data:
        recording_end_margin = rec_settings_data['end_margin']

    # 録画後の動作モード: デフォルト設定に従う / 何もしない / スタンバイ / 休止 / シャットダウン / 再起動
    # ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-240212/ini/HttpPublic/legacy/util.lua#L522-L528
    post_recording_mode: Literal['Default', 'Nothing', 'Standby', 'Suspend', 'Shutdown', 'Reboot'] = 'Default'
    if rec_settings_data['suspend_mode'] == 0:
        post_recording_mode = 'Default'
    elif rec_settings_data['suspend_mode'] == 1:
        post_recording_mode = 'Standby'
    elif rec_settings_data['suspend_mode'] == 2:
        post_recording_mode = 'Suspend'
    elif rec_settings_data['suspend_mode'] == 3:
        post_recording_mode = 'Shutdown'
    elif rec_settings_data['suspend_mode'] == 4:
        post_recording_mode = 'Nothing'
    if rec_settings_data['reboot_flag'] is True:  # なぜか再起動フラグだけ分かれているが、KonomiTV では同一の Literal 値にまとめている
        post_recording_mode = 'Reboot'

    # 録画後に実行する bat ファイルのパス / 指定しない場合は None
    post_recording_bat_file_path: str | None = None
    if rec_settings_data['bat_file_path'] != '':
        post_recording_bat_file_path = rec_settings_data['bat_file_path']

    # 保存先の録画フォルダのパスのリスト
    recording_folders: list[str] = []
    for rec_folder in rec_settings_data['rec_folder_list']:
        recording_folders.append(rec_folder['rec_folder'])

    # イベントリレーの追従を行うかどうか
    is_event_relay_follow_enabled: bool = rec_settings_data['tuijyuu_flag']

    # 「ぴったり録画」(録画マージンののりしろを残さず本編のみを正確に録画する？) を行うかどうか
    is_exact_recording_enabled: bool = rec_settings_data['pittari_flag']

    # 録画対象のチャンネルにワンセグ放送が含まれる場合、ワンセグ放送を別ファイルに同時録画するかどうか
    is_oneseg_separate_output_enabled: bool = rec_settings_data['partial_rec_flag'] == 1  # これだけ何故かフラグなのに int で返ってくる…

    # 同一チャンネルで時間的に隣接した録画予約がある場合に、それらを同一の録画ファイルに続けて出力するかどうか
    is_sequential_recording_in_single_file_enabled: bool = rec_settings_data['continue_rec_flag']

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

    # チューナーを強制指定する際のチューナー ID / 自動選択の場合は None
    forced_tuner_id: int | None = None
    if rec_settings_data['tuner_id'] != 0:  # 0 は自動選択
        forced_tuner_id = rec_settings_data['tuner_id']

    return schemas.RecordSettings(
        record_mode = record_mode,
        is_enabled = is_enabled,
        priority = priority,
        recording_start_margin = recording_start_margin,
        recording_end_margin = recording_end_margin,
        post_recording_mode = post_recording_mode,
        post_recording_bat_file_path = post_recording_bat_file_path,
        recording_folders = recording_folders,
        is_event_relay_follow_enabled = is_event_relay_follow_enabled,
        is_exact_recording_enabled = is_exact_recording_enabled,
        is_oneseg_separate_output_enabled = is_oneseg_separate_output_enabled,
        is_sequential_recording_in_single_file_enabled = is_sequential_recording_in_single_file_enabled,
        caption_recording_mode = caption_recording_mode,
        data_broadcasting_recording_mode = data_broadcasting_recording_mode,
        forced_tuner_id = forced_tuner_id,
    )


async def GetCtrlCmdUtil() -> CtrlCmdUtil:
    """ バックエンドが EDCB かのチェックを行い、EDCB であれば EDCB の CtrlCmdUtil インスタンスを返す """
    if Config().general.backend == 'EDCB':
        return CtrlCmdUtil()
    else:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'This API is only available when the backend is EDCB',
        )


async def GetReserveData(
    reserve_id: Annotated[int, Path(description='録画予約 ID 。')],
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
) -> ReserveDataRequired:
    """ EDCB から指定された録画予約の情報を取得する """
    # EDCB から現在のすべての録画予約の情報を取得
    reserves: list[ReserveDataRequired] | None = await edcb.sendEnumReserve()
    if reserves is None:
        # None が返ってきた場合はエラーを返す
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'Failed to get the list of recording reservations',
        )
    # 指定された録画予約の情報を取得
    reserve_data: ReserveDataRequired | None = None
    for reserve in reserves:
        if reserve['reserve_id'] == reserve_id:
            reserve_data = reserve
            break
    # 指定された録画予約が見つからなかった場合はエラーを返す
    if reserve_data is None:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified reserve_id was not found',
        )
    return reserve_data


@router.get(
    '',
    summary = '録画予約情報一覧 API',
    response_description = '録画予約情報のリスト。',
    response_model = schemas.ReserveList,
)
async def ReservesAPI(
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
):
    """
    EDCB からすべての録画予約の情報を取得する。
    """

    # EDCB から現在のすべての録画予約の情報を取得
    edcb_reserves: list[ReserveDataRequired] | None = await edcb.sendEnumReserve()
    if edcb_reserves is None:
        # None が返ってきた場合は空のリストを返す
        return schemas.ReserveList(total=0, reserves=[])

    # データベースアクセスを伴うので、トランザクション下に入れた上で並行して行う
    async with transactions.in_transaction():

        # 高速化のため、あらかじめ全てのチャンネル情報を取得しておく
        channels = await Channel.all()

        # EDCB の ReserveData オブジェクトを schemas.Reserve オブジェクトに変換
        reserves = await asyncio.gather(*(ConvertEDCBReserveDataToReserve(reserve_data, channels) for reserve_data in edcb_reserves))

    # 録画予約番組の番組開始時刻でソート
    reserves.sort(key=lambda reserve: reserve.program.start_time)

    return schemas.ReserveList(total=len(edcb_reserves), reserves=reserves)


@router.get(
    '/{reserve_id}',
    summary = '録画予約情報取得 API',
    response_description = '録画予約情報。',
    response_model = schemas.Reserve,
)
async def ReserveAPI(
    reserve_data: Annotated[ReserveDataRequired, Depends(GetReserveData)],
):
    """
    EDCB から指定された録画予約の情報を取得する。
    """

    # EDCB の ReserveData オブジェクトを schemas.Reserve オブジェクトに変換して返す
    return await ConvertEDCBReserveDataToReserve(reserve_data)


@router.delete(
    '/{reserve_id}',
    summary = '録画予約削除 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def DeleteReserveAPI(
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
    reserve_data: Annotated[ReserveDataRequired, Depends(GetReserveData)],
):
    """
    EDCB から指定された録画予約を削除する。
    """

    # EDCB に指定された録画予約を削除するように指示
    result = await edcb.sendDelReserve([reserve_data['reserve_id']])
    if result is False:
        # False が返ってきた場合はエラーを返す
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'Failed to delete the specified recording reservation',
        )
