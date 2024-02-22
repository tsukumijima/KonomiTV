
import ariblib.constants
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Path
from fastapi import status
from typing import Annotated, Any, cast, Literal

from app import logging
from app import schemas
from app.models.Channel import Channel
from app.routers.ReservesRouter import ConvertEDCBRecSettingDataToRecordSettings
from app.routers.ReservesRouter import GetCtrlCmdUtil
from app.utils.EDCB import CtrlCmdUtil
from app.utils.EDCB import AutoAddDataRequired
from app.utils.EDCB import SearchKeyInfoRequired
from app.utils.TSInformation import TSInformation


# ルーター
router = APIRouter(
    tags = ['ReserveConditions'],
    prefix = '/api/reserve-conditions',
)


async def ConvertEDCBAutoAddDataToReserveCondition(auto_add_data: AutoAddDataRequired) -> schemas.ReserveCondition:
    """
    EDCB の AutoAddData オブジェクトを schemas.ReserveCondition オブジェクトに変換する

    Args:
        auto_add_data (AutoAddDataRequired): EDCB の AutoAddData オブジェクト

    Returns:
        schemas.ReserveCondition: schemas.ReserveCondition オブジェクト
    """

    # キーワード自動予約条件 ID
    reserve_condition_id = auto_add_data['data_id']

    # このキーワード自動予約条件で登録されている録画予約の数
    reserve_count = auto_add_data['add_count']

    # 番組検索条件
    program_search_condition = await ConvertEDCBSearchKeyInfoToProgramSearchCondition(auto_add_data['search_info'])

    # 録画設定
    record_settings = ConvertEDCBRecSettingDataToRecordSettings(auto_add_data['rec_setting'])

    return schemas.ReserveCondition(
        id = reserve_condition_id,
        reserve_count = reserve_count,
        program_search_condition = program_search_condition,
        record_settings = record_settings,
    )


async def ConvertEDCBSearchKeyInfoToProgramSearchCondition(search_info: SearchKeyInfoRequired) -> schemas.ProgramSearchCondition:
    """
    EDCB の SearchKeyInfo オブジェクトを schemas.ProgramSearchCondition オブジェクトに変換する

    Args:
        search_info (SearchKeyInfoRequired): EDCB の SearchKeyInfo オブジェクト

    Returns:
        schemas.ProgramSearchCondition: schemas.ProgramSearchCondition オブジェクト
    """

    # 高速化のため、あらかじめ全てのチャンネル情報を取得し、ID がキー、チャンネル情報が値の辞書を作成しておく
    ## チャンネル ID は NID32736-SID1024 の形式なので、ネットワーク ID とサービス ID があればそれをキーにしてチャンネル情報を即座に取得できる
    channels_dict = {channel.id: channel for channel in await Channel.all()}

    # 番組検索条件が有効かどうか
    is_enabled: bool = not search_info['key_disabled']

    # 検索キーワード
    keyword: str = search_info['and_key']

    # 除外キーワード
    exclude_keyword: str = search_info['not_key']

    # 番組名のみを検索対象とするかどうか
    is_title_only: bool = search_info['title_only_flag']

    # 大文字小文字を区別するかどうか
    is_case_sensitive: bool = search_info['case_sensitive']

    # あいまい検索を行うかどうか
    is_fuzzy_search_enabled: bool = search_info['aimai_flag']

    # 正規表現で検索するかどうか
    is_regex_search_enabled: bool = search_info['reg_exp_flag']

    # 検索対象を絞り込むチャンネル範囲ののリスト
    ## 指定しない場合は None になる
    channel_ranges: list[Channel] | None = None
    for service in search_info['service_list']:
        if channel_ranges is None:
            channel_ranges = []
        # service_list は (NID << 32 | TSID << 16 | SID) のリストになっているので、まずはそれらの値を分解する
        network_id = service >> 32
        transport_stream_id = (service >> 16) & 0xffff
        service_id = service & 0xffff
        # チャンネル ID を組み立てる
        channel_id = f'NID{network_id}-SID{service_id}'
        # チャンネル ID が channels_dict に存在する場合はそのチャンネル情報を取得し、リストに追加する
        if channel_id in channels_dict:
            channel_ranges.append(channels_dict[channel_id])
        # 取得できなかった場合のみ、上記の限定的な情報を使って間に合わせのチャンネル情報を作成する
        # 通常ここでチャンネル情報が取得できないのはワンセグやデータ放送など KonomiTV ではサポートしていないサービスを予約している場合だけのはず
        else:
            channel = Channel(
                id = channel_id,
                display_channel_id = 'gr001',  # 取得できないため一旦 'gr001' を設定
                network_id = network_id,
                service_id = service_id,
                transport_stream_id = transport_stream_id,
                remocon_id = 0,  # 取得できないため一旦 0 を設定
                channel_number = '001',  # 取得できないため一旦 '001' を設定
                type = TSInformation.getNetworkType(network_id),
                name = f'Unknown Channel (NID:{network_id} / SID: {service_id})',
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
            channel_ranges.append(channel)

    # 検索対象を絞り込むジャンルの範囲のリスト
    ## 指定しない場合は None になる
    ## 以下の処理は app.models.Program から移植して少し調整したもの
    genre_ranges: list[schemas.Genre] | None = None
    for content in search_info['content_list']:  # ジャンルごとに
        # 大まかなジャンルを取得
        genre_tuple = ariblib.constants.CONTENT_TYPE.get(content['content_nibble'] >> 8)
        if genre_tuple is not None:
            # major … 大分類
            # middle … 中分類
            genre_dict: schemas.Genre = {
                'major': genre_tuple[0].replace('／', '・'),
                'middle': genre_tuple[1].get(content['content_nibble'] & 0xf, '未定義').replace('／', '・'),
            }
            # もし content_nibble & 0xff が 0xff なら、その大分類ジャンルの配下のすべての中分類ジャンルが検索対象になる
            if content['content_nibble'] & 0xff == 0xff:
                genre_dict['middle'] = 'すべて'
            # BS/地上デジタル放送用番組付属情報がジャンルに含まれている場合、user_nibble から値を取得して書き換える
            # たとえば「中止の可能性あり」や「延長の可能性あり」といった情報が取れる
            if genre_dict['major'] == '拡張':
                if genre_dict['middle'] == 'BS/地上デジタル放送用番組付属情報':
                    user_nibble = (content['user_nibble'] >> 8 << 4) | (content['user_nibble'] & 0xf)
                    genre_dict['middle'] = ariblib.constants.USER_TYPE.get(user_nibble, '未定義')
                # 「拡張」はあるがBS/地上デジタル放送用番組付属情報でない場合はなんの値なのかわからないのでパス
                else:
                    continue
            # ジャンルを追加
            if genre_ranges is None:
                genre_ranges = []
            genre_ranges.append(genre_dict)

    # genre_ranges で指定したジャンルを逆に検索対象から除外するかどうか
    is_exclude_genres: bool = search_info['not_contet_flag']

    # 検索対象を絞り込む放送日時の範囲のリスト
    ## 指定しない場合は None になる
    date_ranges: list[schemas.ProgramSearchConditionDate] | None = None
    for date in search_info['date_list']:
        if date_ranges is None:
            date_ranges = []
        date_ranges.append(schemas.ProgramSearchConditionDate(
            start_day_of_week = date['start_day_of_week'],
            start_hour = date['start_hour'],
            start_minute = date['start_min'],
            end_day_of_week = date['end_day_of_week'],
            end_hour = date['end_hour'],
            end_minute = date['end_min'],
        ))

    # date_ranges で指定した放送日時を逆に検索対象から除外するかどうか
    is_exclude_dates: bool = search_info['not_date_flag']

    # 番組長で絞り込む最小範囲 (秒)
    ## 指定しない場合は None になる
    duration_range_min: int | None = None
    if search_info['chk_duration_min'] > 0:
        duration_range_min = search_info['chk_duration_min']

    # 番組長で絞り込む最大範囲 (秒)
    ## 指定しない場合は None になる
    duration_range_max: int | None = None
    if search_info['chk_duration_max'] > 0:
        duration_range_max = search_info['chk_duration_max']

    # 番組の放送種別で絞り込む: すべて / 無料のみ / 有料のみ
    ## ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-240212/Document/Readme_Mod.txt?plain=1#L1443
    broadcast_type: Literal['All', 'FreeOnly', 'PaidOnly'] = 'All'
    if search_info['free_ca_flag'] == 0:
        broadcast_type = 'All'
    elif search_info['free_ca_flag'] == 1:
        broadcast_type = 'FreeOnly'
    elif search_info['free_ca_flag'] == 2:
        broadcast_type = 'PaidOnly'

    # 同じ番組名の既存録画との重複チェック: 何もしない / 同じチャンネルのみ対象にする / 全てのチャンネルを対象にする
    ## 同じチャンネルのみ対象にする: 同じチャンネルで同名の番組が既に録画されていれば、新しい予約を無効状態で登録する
    ## 全てのチャンネルを対象にする: 任意のチャンネルで同名の番組が既に録画されていれば、新しい予約を無効状態で登録する
    ## 仕様上予約自体を削除してしまうとすぐ再登録されてしまうので、無効状態で登録することで有効になるのを防いでいるらしい
    duplicate_title_check_scope: Literal['None', 'SameChannelOnly', 'AllChannels'] = 'None'
    if search_info['chk_rec_end'] is True:
        if search_info['chk_rec_no_service'] is True:
            duplicate_title_check_scope = 'AllChannels'
        else:
            duplicate_title_check_scope = 'SameChannelOnly'

    # 同じ番組名の既存録画との重複チェックの対象期間 (日単位)
    duplicate_title_check_period_days: int = search_info['chk_rec_day']

    return schemas.ProgramSearchCondition(
        is_enabled = is_enabled,
        keyword = keyword,
        exclude_keyword = exclude_keyword,
        is_title_only = is_title_only,
        is_case_sensitive = is_case_sensitive,
        is_fuzzy_search_enabled = is_fuzzy_search_enabled,
        is_regex_search_enabled = is_regex_search_enabled,
        channel_ranges = cast(Any, channel_ranges),
        genre_ranges = genre_ranges,
        is_exclude_genres = is_exclude_genres,
        date_ranges = date_ranges,
        is_exclude_dates = is_exclude_dates,
        duration_range_min = duration_range_min,
        duration_range_max = duration_range_max,
        broadcast_type = broadcast_type,
        duplicate_title_check_scope = duplicate_title_check_scope,
        duplicate_title_check_period_days = duplicate_title_check_period_days,
    )


async def GetAutoAddDataList(
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
) -> list[AutoAddDataRequired]:
    """ すべてのキーワード自動予約条件の情報を取得する """
    # EDCB から現在のすべてのキーワード自動予約条件の情報を取得
    auto_add_data_list: list[AutoAddDataRequired] | None = await edcb.sendEnumAutoAdd()
    if auto_add_data_list is None:
        # None が返ってきた場合はエラーを返す
        logging.error('[ReserveConditionsRouter][GetAutoAddDataList] Failed to get the list of reserve conditions')
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'Failed to get the list of reserve conditions',
        )
    return auto_add_data_list


async def GetAutoAddData(
    reserve_condition_id: Annotated[int, Path(description='キーワード自動予約条件 ID 。')],
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
) -> AutoAddDataRequired:
    """ 指定されたキーワード自動予約条件の情報を取得する """
    # 指定されたキーワード自動予約条件の情報を取得
    for auto_add_data in await GetAutoAddDataList(edcb):
        if auto_add_data['data_id'] == reserve_condition_id:
            return auto_add_data
    # 指定されたキーワード自動予約条件が見つからなかった場合はエラーを返す
    logging.error('[ReserveConditionsRouter][GetAutoAddData] Specified reserve_condition_id was not found '
                    f'[reserve_condition_id: {reserve_condition_id}]')
    raise HTTPException(
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail = 'Specified reserve_condition_id was not found',
    )


@router.get(
    '',
    summary = 'キーワード自動予約条件一覧 API',
    response_description = 'キーワード自動予約条件のリスト。',
    response_model = schemas.ReserveConditions,
)
async def ReserveConditionsAPI(
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
):
    """
    すべてのキーワード自動予約条件 (EPG 予約) の情報を取得する。
    """

    # EDCB から現在のすべてのキーワード自動予約条件の情報を取得
    auto_add_data_list: list[AutoAddDataRequired] | None = await edcb.sendEnumAutoAdd()
    if auto_add_data_list is None:
        # None が返ってきた場合は空のリストを返す
        return schemas.ReserveConditions(total=0, reserve_conditions=[])

    # EDCB の AutoAddData オブジェクトを schemas.ReserveCondition オブジェクトに変換
    reserve_conditions = [await ConvertEDCBAutoAddDataToReserveCondition(auto_add_data) for auto_add_data in auto_add_data_list]

    return schemas.ReserveConditions(total=len(reserve_conditions), reserve_conditions=reserve_conditions)


@router.get(
    '/{reserve_condition_id}',
    summary = 'キーワード自動予約条件取得 API',
    response_description = 'キーワード自動予約条件。',
    response_model = schemas.ReserveCondition,
)
async def ReserveConditionAPI(
    auto_add_data: Annotated[AutoAddDataRequired, Depends(GetAutoAddData)],
):
    """
    指定されたキーワード自動予約条件の情報を取得する。
    """

    # EDCB の AutoAddData オブジェクトを schemas.ReserveCondition オブジェクトに変換して返す
    return await ConvertEDCBAutoAddDataToReserveCondition(auto_add_data)


@router.delete(
    '/{reserve_condition_id}',
    summary = 'キーワード自動予約条件削除 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def DeleteReserveConditionAPI(
    auto_add_data: Annotated[AutoAddDataRequired, Depends(GetAutoAddData)],
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
):
    """
    指定されたキーワード自動予約条件を削除する。
    """

    # TODO: キーワード自動予約条件を削除した後に残った予約をクリーンアップする処理を追加する

    # EDCB に指定されたキーワード自動予約条件を削除するように指示
    result = await edcb.sendDelAutoAdd([auto_add_data['data_id']])
    if result is False:
        # False が返ってきた場合はエラーを返す
        logging.error('[ReserveConditionsRouter][DeleteReserveConditionAPI] Failed to delete the specified reserve condition '
                      f'[reserve_condition_id: {auto_add_data["data_id"]}]')
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'Failed to delete the specified reserve condition',
        )
