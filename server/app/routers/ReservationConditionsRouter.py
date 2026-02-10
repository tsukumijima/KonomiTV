
import re
from typing import Annotated, Any, Literal, cast

import ariblib.constants
from fastapi import APIRouter, Body, Depends, HTTPException, Path, status

from app import logging, schemas
from app.routers.ReservationsRouter import (
    DecodeEDCBRecSettingData,
    EncodeEDCBRecSettingData,
    GetCtrlCmdUtil,
)
from app.utils.edcb import (
    AutoAddData,
    AutoAddDataRequired,
    ChSet5Item,
    ContentData,
    RecSettingData,
    SearchDateInfoRequired,
    SearchKeyInfo,
    SearchKeyInfoRequired,
)
from app.utils.edcb.CtrlCmdUtil import CtrlCmdUtil
from app.utils.edcb.EDCBUtil import EDCBUtil


# ルーター
router = APIRouter(
    tags = ['Reservation Conditions'],
    prefix = '/api/recording/conditions',
)


async def DecodeEDCBAutoAddData(
    auto_add_data: AutoAddDataRequired,
    edcb: CtrlCmdUtil,
    chset5_services: list[ChSet5Item] | None = None,
) -> schemas.ReservationCondition:
    """
    EDCB の AutoAddData オブジェクトを schemas.ReservationCondition オブジェクトに変換する

    Args:
        auto_add_data (AutoAddDataRequired): EDCB の AutoAddData オブジェクト
        edcb (CtrlCmdUtil): EDCB API クライアント
        chset5_services (list[ChSet5Item] | None): 事前取得済みの ChSet5 サービス情報

    Returns:
        schemas.ReservationCondition: schemas.ReservationCondition オブジェクト
    """

    # キーワード自動予約条件 ID
    reservation_condition_id = auto_add_data['data_id']

    # このキーワード自動予約条件で登録されている録画予約の数
    reserve_count = auto_add_data['add_count']

    # 番組検索条件
    program_search_condition = await DecodeEDCBSearchKeyInfo(
        auto_add_data['search_info'],
        edcb,
        chset5_services,
    )

    # 録画設定
    record_settings = DecodeEDCBRecSettingData(auto_add_data['rec_setting'])

    return schemas.ReservationCondition(
        id = reservation_condition_id,
        reservation_count = reserve_count,
        program_search_condition = program_search_condition,
        record_settings = record_settings,
    )


async def DecodeEDCBSearchKeyInfo(
    search_info: SearchKeyInfoRequired,
    edcb: CtrlCmdUtil,
    chset5_services: list[ChSet5Item] | None = None,
) -> schemas.ProgramSearchCondition:
    """
    EDCB の SearchKeyInfo オブジェクトを schemas.ProgramSearchCondition オブジェクトに変換する

    Args:
        search_info (SearchKeyInfoRequired): EDCB の SearchKeyInfo オブジェクト
        edcb (CtrlCmdUtil): EDCB API クライアント
        chset5_services (list[ChSet5Item] | None): 事前取得済みの ChSet5 サービス情報

    Returns:
        schemas.ProgramSearchCondition: schemas.ProgramSearchCondition オブジェクト
    """

    # 番組検索条件が有効かどうか
    is_enabled: bool = not search_info['key_disabled']

    # 検索キーワード
    keyword: str = search_info['and_key']

    # 除外キーワード
    ## 後述のメモ欄が :note: から始まる除外キーワードになっているので除去している
    ## ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-240221/EpgTimer/EpgTimer/DefineClass/EpgAutoDataItem.cs#L35-L38
    exclude_keyword: str = re.sub(r'^:note:[^ 　]*[ 　]?', '', search_info['not_key'])

    # メモ欄
    ## EDCB の内部実装上は :note: から始まる除外キーワードになっているので抽出する
    ## ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-240221/EpgTimer/EpgTimer/DefineClass/EpgAutoDataItem.cs#L39-L50
    note: str = ''
    note_match = re.match(r"^:note:([^ 　]*)", search_info['not_key'])
    if note_match is not None:
        note = note_match.group(1).replace('\\s', ' ').replace('\\m', '　').replace('\\\\', '\\')

    # 番組名のみを検索対象とするかどうか
    is_title_only: bool = search_info['title_only_flag']

    # 大文字小文字を区別するかどうか
    is_case_sensitive: bool = search_info['case_sensitive']

    # あいまい検索を行うかどうか
    is_fuzzy_search_enabled: bool = search_info['aimai_flag']

    # 正規表現で検索するかどうか
    is_regex_search_enabled: bool = search_info['reg_exp_flag']

    # 検索対象を絞り込むチャンネル範囲のリスト
    ## None を指定すると全てのチャンネルが検索対象になる
    ## ジャンル範囲や放送日時範囲とは異なり、全チャンネルが検索対象の場合は空リストにはならず、全チャンネルの ID が返ってくる
    ## 全てのチャンネルを検索対象にすると検索処理が比較的重くなるので、可能であれば絞り込む方が望ましいとのこと
    ## ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-240212/Document/Readme_Mod.txt?plain=1#L165-L170
    service_ranges: list[schemas.ProgramSearchConditionService] | None = []
    for service in search_info['service_list']:
        # service_list は (NID << 32 | TSID << 16 | SID) のリストになっているので、まずはそれらの値を分解する
        network_id = service >> 32
        transport_stream_id = (service >> 16) & 0xffff
        service_id = service & 0xffff
        # schemas.ProgramSearchConditionChannel オブジェクトを作成
        service_ranges.append(schemas.ProgramSearchConditionService(
            network_id = network_id,
            transport_stream_id = transport_stream_id,
            service_id = service_id,
        ))
    ## この時点で service_ranges の内容がデフォルトの番組検索条件のチャンネル範囲のリスト (全チャンネルが検索対象) と一致する場合、
    ## 全チャンネルを検索対象にしているのと同義なので、None に変換する
    ## 一旦リストの中の Pydantic モデルを dict に変換し、サービス ID でソートして条件を整えてから比較している
    default_service_ranges = await GetDefaultServiceRanges(edcb, chset5_services)
    if (sorted(
            [service.model_dump() for service in service_ranges],
            key=lambda x: (x['network_id'], x['transport_stream_id'], x['service_id']),
        ) ==
        sorted(
            [service.model_dump() for service in default_service_ranges],
            key=lambda x: (x['network_id'], x['transport_stream_id'], x['service_id']),
        )):
        service_ranges = None

    # 検索対象を絞り込むジャンル範囲のリスト
    ## None を指定すると全てのジャンルが検索対象になる
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
    is_exclude_genre_ranges: bool = search_info['not_contet_flag']

    # 検索対象を絞り込む放送日時範囲のリスト
    ## None を指定すると全ての放送日時が検索対象になる
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
    is_exclude_date_ranges: bool = search_info['not_date_flag']

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
        note = note,
        is_title_only = is_title_only,
        is_case_sensitive = is_case_sensitive,
        is_fuzzy_search_enabled = is_fuzzy_search_enabled,
        is_regex_search_enabled = is_regex_search_enabled,
        service_ranges = cast(Any, service_ranges),
        genre_ranges = genre_ranges,
        is_exclude_genre_ranges = is_exclude_genre_ranges,
        date_ranges = date_ranges,
        is_exclude_date_ranges = is_exclude_date_ranges,
        duration_range_min = duration_range_min,
        duration_range_max = duration_range_max,
        broadcast_type = broadcast_type,
        duplicate_title_check_scope = duplicate_title_check_scope,
        duplicate_title_check_period_days = duplicate_title_check_period_days,
    )


async def EncodeEDCBSearchKeyInfo(
    program_search_condition: schemas.ProgramSearchCondition,
    edcb: CtrlCmdUtil,
    chset5_services: list[ChSet5Item] | None = None,
) -> SearchKeyInfoRequired:
    """
    schemas.ProgramSearchCondition オブジェクトを EDCB の SearchKeyInfo オブジェクトに変換する

    Args:
        program_search_condition (schemas.ProgramSearchCondition): schemas.ProgramSearchCondition オブジェクト
        edcb (CtrlCmdUtil): EDCB API クライアント
        chset5_services (list[ChSet5Item] | None): 事前取得済みの ChSet5 サービス情報

    Returns:
        SearchKeyInfoRequired: EDCB の SearchKeyInfo オブジェクト
    """

    ## メモ欄は EDCB の内部実装上は :note: から始まる除外キーワードになっているので再構築する
    ## ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-240221/EpgTimer/EpgTimer/UserCtrlView/SearchKeyView.xaml.cs#L141-L142
    not_key: str = program_search_condition.exclude_keyword
    if program_search_condition.note != '':
        not_key = ':note:' + program_search_condition.note.replace('\\', '\\\\').replace(' ', '\\s').replace('　', '\\m')
        if program_search_condition.exclude_keyword != '':
            not_key += f' {program_search_condition.exclude_keyword}'  # 半角スペースを挟んでから元の除外キーワードを追加

    # 番組の放送種別で絞り込む: すべて / 無料のみ / 有料のみ
    free_ca_flag: int = 0
    if program_search_condition.broadcast_type == 'All':
        free_ca_flag = 0
    elif program_search_condition.broadcast_type == 'FreeOnly':
        free_ca_flag = 1
    elif program_search_condition.broadcast_type == 'PaidOnly':
        free_ca_flag = 2

    # 検索対象を絞り込むチャンネル範囲のリスト
    ## service_list は (NID << 32 | TSID << 16 | SID) のリストになっている
    ## ジャンル範囲や放送日時範囲とは異なり、空リストにしても全チャンネルが検索対象にはならないため、
    ## もし service_ranges が None だった場合はデフォルトの番組検索条件のチャンネル範囲のリスト (全チャンネルが検索対象) を設定する
    service_list: list[int] = []
    for channel in program_search_condition.service_ranges or await GetDefaultServiceRanges(edcb, chset5_services):
        service_list.append(channel.network_id << 32 | channel.transport_stream_id << 16 | channel.service_id)

    # 検索対象を絞り込むジャンル範囲のリスト
    ## 空リストを指定すると全てのジャンルが検索対象になる
    ## content_list は ContentData のリストになっている
    content_list: list[ContentData] = []
    if program_search_condition.genre_ranges is not None:
        for genre in program_search_condition.genre_ranges:
            # KonomiTV では見栄えのために ／ を ・ に置換しているので、ここで元に戻す
            major = genre['major'].replace('・', '／')
            middle = genre['middle'].replace('・', '／')
            # 万が一見つからなかった場合のデフォルト値
            content_nibble_level1 = 0xF  # "その他"
            content_nibble_level2 = 0xF  # "その他"
            user_nibble = 0x0  # user_nibble はユーザージャンルがある場合のみ値が入る
            # ariblib.constants.CONTENT_TYPE から文字列表現と一致する値を探す
            for major_key, major_value in ariblib.constants.CONTENT_TYPE.items():
                if major_value[0] == major:
                    # content_nibble_level1 には大分類の値を入れる
                    content_nibble_level1 = major_key
                    # もし大分類が "拡張" の時のみ、中分類の文字列表現に当てはまるBS/地上デジタル放送用番組付属情報を探す
                    # TODO: 本来は広帯域CSデジタル放送用拡張にも対応すべきだが、ariblib に対応する定数がなく各所で対応できてないため今のところ未対応
                    if content_nibble_level1 == 0xE:
                        for user_key, user_value in ariblib.constants.USER_TYPE.items():
                            if user_value == middle:
                                # content_nibble_level2 にはBS/地上デジタル放送用番組付属情報を示す値を入れる
                                content_nibble_level2 = 0x0
                                # user_nibble には中分類の値を入れる
                                user_nibble = user_key
                                break
                    # もし中分類の文字列が "すべて" だった場合、その大分類の全ての中分類を検索対象にする
                    elif middle == 'すべて':
                        # 0xFF は全ての中分類を示す (おそらく EDCB 独自仕様？)
                        ## 本来の放送波に含まれる content_nibble_level2 は 4 ビットの値なので本来は 0x0 ~ 0xF までの値が入る
                        content_nibble_level2 = 0xFF
                        break
                    # 中分類の値を探す
                    else:
                        for middle_key, middle_value in major_value[1].items():
                            if middle_value == middle:
                                # content_nibble_level2 には中分類の値を入れる
                                content_nibble_level2 = middle_key
                                break
            # EDCB の ContentData の content_nibble は content_nibble_level1 * 256 + content_nibble_level2 になっている
            ## ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-240221/Document/Readme_Mod.txt?plain=1#L1450
            content_list.append({
                'content_nibble': content_nibble_level1 * 256 + content_nibble_level2,
                'user_nibble': user_nibble,
            })

    # 検索対象を絞り込む放送日時範囲のリスト
    ## 空リストを指定すると全ての放送日時が検索対象になる
    ## date_list は SearchDateInfoRequired のリストになっている
    date_list: list[SearchDateInfoRequired] = []
    if program_search_condition.date_ranges is not None:
        for date in program_search_condition.date_ranges:
            # これだけデータ構造がキー名以外 EDCB と KonomiTV で同一なのでそのまま追加
            date_list.append({
                'start_day_of_week': date.start_day_of_week,
                'start_hour': date.start_hour,
                'start_min': date.start_minute,
                'end_day_of_week': date.end_day_of_week,
                'end_hour': date.end_hour,
                'end_min': date.end_minute,
            })

    # EDCB の SearchKeyInfo オブジェクトを作成
    search_info: SearchKeyInfoRequired = {
        'and_key': program_search_condition.keyword,
        'not_key': not_key,
        'key_disabled': not program_search_condition.is_enabled,
        'case_sensitive': program_search_condition.is_case_sensitive,
        'reg_exp_flag': program_search_condition.is_regex_search_enabled,
        'title_only_flag': program_search_condition.is_title_only,
        'content_list': content_list,
        'date_list': date_list,
        'service_list': service_list,
        # KonomiTV の番組検索 UI では映像 / 音声コンポーネント条件を提供していないため、
        # video_list / audio_list は常に空配列で送信する
        ## EDCB 側実装では条件が入っていれば検索フィルタとして評価されるが、
        ## EpgTimer 標準 UI でも通常は設定されない項目であり、現時点では非対応とする
        'video_list': [],
        'audio_list': [],
        'aimai_flag': program_search_condition.is_fuzzy_search_enabled,
        'not_contet_flag': program_search_condition.is_exclude_genre_ranges,
        'not_date_flag': program_search_condition.is_exclude_date_ranges,
        'free_ca_flag': free_ca_flag,
        'chk_rec_end': program_search_condition.duplicate_title_check_scope != 'None',
        'chk_rec_day': program_search_condition.duplicate_title_check_period_days,
        'chk_rec_no_service': program_search_condition.duplicate_title_check_scope == 'AllChannels',
        'chk_duration_min': program_search_condition.duration_range_min if program_search_condition.duration_range_min is not None else 0,
        'chk_duration_max': program_search_condition.duration_range_max if program_search_condition.duration_range_max is not None else 0,
    }

    return search_info


async def GetChSet5Services(
    edcb: CtrlCmdUtil,
    chset5_services: list[ChSet5Item] | None = None,
) -> list[ChSet5Item]:
    """
    ChSet5.txt を解析したサービス一覧を取得する。

    Args:
        edcb (CtrlCmdUtil): EDCB API クライアント
        chset5_services (list[ChSet5Item] | None): 事前取得済みの ChSet5 サービス情報

    Returns:
        list[ChSet5Item]: ChSet5.txt を解析したサービス一覧
    """

    # 呼び出し元で既に取得済みの場合は再取得しない
    if chset5_services is not None:
        return chset5_services

    chset5_txt = await edcb.sendFileCopy('ChSet5.txt')
    if chset5_txt is None:
        logging.error('[ReservationConditionsRouter][GetChSet5Services] Failed to get ChSet5.txt from EDCB.')
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'Failed to get ChSet5.txt from EDCB',
        )

    return EDCBUtil.parseChSet5(EDCBUtil.convertBytesToString(chset5_txt))


async def GetDefaultServiceRanges(
    edcb: CtrlCmdUtil,
    chset5_services: list[ChSet5Item] | None = None,
) -> list[schemas.ProgramSearchConditionService]:
    """
    デフォルトの番組検索条件のチャンネル範囲のリスト (全チャンネルが検索対象) を取得する
    EpgTimer の ChSet5.ChListSelected と整合するよう、EDCB の ChSet5.txt を一次ソースとして扱う

    Returns:
        list[schemas.ProgramSearchConditionService]: デフォルトの番組検索条件のチャンネル範囲のリスト
    """

    # ChSet5.txt は EpgTimer 側のサービス選択状態を保持しているため、
    # 番組検索条件の「全チャンネル」は ChSet5 ベースで組み立てる
    chset5_services = await GetChSet5Services(edcb, chset5_services)

    # EpgTimer の ChSet5 は同一サービスが重複する可能性があるため、
    # ONID / TSID / SID の組で先勝ちにして重複を除去する
    unique_service_keys: set[tuple[int, int, int]] = set()
    default_service_ranges: list[schemas.ProgramSearchConditionService] = []
    for service in chset5_services:
        service_key = (service['onid'], service['tsid'], service['sid'])
        if service_key in unique_service_keys:
            continue
        unique_service_keys.add(service_key)
        default_service_ranges.append(schemas.ProgramSearchConditionService(
            network_id = service['onid'],
            transport_stream_id = service['tsid'],
            service_id = service['sid'],
        ))

    return default_service_ranges


async def GetAutoAddDataList(
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
) -> list[AutoAddDataRequired]:
    """ すべてのキーワード自動予約条件の情報を取得する """

    # EDCB から現在のすべてのキーワード自動予約条件の情報を取得
    auto_add_data_list: list[AutoAddDataRequired] | None = await edcb.sendEnumAutoAdd()
    if auto_add_data_list is None:
        # None が返ってきた場合はエラーを返す
        logging.error('[ReservationConditionsRouter][GetAutoAddDataList] Failed to get the list of reserve conditions.')
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'Failed to get the list of reserve conditions',
        )

    return auto_add_data_list


async def GetAutoAddData(
    reservation_condition_id: Annotated[int, Path(description='キーワード自動予約条件 ID 。')],
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
) -> AutoAddDataRequired:
    """ 指定されたキーワード自動予約条件の情報を取得する """

    # 指定されたキーワード自動予約条件の情報を取得
    for auto_add_data in await GetAutoAddDataList(edcb):
        if auto_add_data['data_id'] == reservation_condition_id:
            return auto_add_data

    # 指定されたキーワード自動予約条件が見つからなかった場合はエラーを返す
    logging.error('[ReservationConditionsRouter][GetAutoAddData] Specified reservation_condition_id was not found. '
                    f'[reservation_condition_id: {reservation_condition_id}]')
    raise HTTPException(
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail = 'Specified reservation_condition_id was not found',
    )


@router.get(
    '',
    summary = 'キーワード自動予約条件一覧 API',
    response_description = 'キーワード自動予約条件のリスト。',
    response_model = schemas.ReservationConditions,
)
async def ReservationConditionsAPI(
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
):
    """
    すべてのキーワード自動予約条件 (EPG 予約) の情報を取得する。
    """

    # EDCB から現在のすべてのキーワード自動予約条件の情報を取得
    auto_add_data_list: list[AutoAddDataRequired] | None = await edcb.sendEnumAutoAdd()
    if auto_add_data_list is None:
        # None が返ってきた場合は空のリストを返す
        return schemas.ReservationConditions(total=0, reservation_conditions=[])

    # 同一リクエスト内での ChSet5.txt 再取得を避けるため、先に 1 回だけ取得して全変換処理で使い回す
    chset5_services = await GetChSet5Services(edcb)

    # EDCB の AutoAddData オブジェクトを schemas.ReservationCondition オブジェクトに変換
    reserve_conditions = [
        await DecodeEDCBAutoAddData(auto_add_data, edcb, chset5_services)
        for auto_add_data in auto_add_data_list
    ]

    return schemas.ReservationConditions(total=len(reserve_conditions), reservation_conditions=reserve_conditions)


@router.post(
    '',
    summary = 'キーワード自動予約条件登録 API',
    status_code = status.HTTP_201_CREATED,
)
async def RegisterReservationConditionAPI(
    reserve_condition_add_request: Annotated[schemas.ReservationConditionAddRequest, Body(description='登録するキーワード自動予約条件。')],
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
):
    """
    キーワード自動予約条件を登録する。
    """

    # EDCB の AutoAddData オブジェクトを組み立てる
    ## data_id は EDCB 側で自動で割り振られるため省略している
    chset5_services = await GetChSet5Services(edcb)
    auto_add_data: AutoAddData = {
        'search_info': cast(SearchKeyInfo, await EncodeEDCBSearchKeyInfo(
            reserve_condition_add_request.program_search_condition,
            edcb,
            chset5_services,
        )),
        'rec_setting': cast(RecSettingData, EncodeEDCBRecSettingData(reserve_condition_add_request.record_settings)),
    }

    # EDCB にキーワード自動予約条件を登録するように指示
    result = await edcb.sendAddAutoAdd([auto_add_data])
    if result is False:
        # False が返ってきた場合はエラーを返す
        logging.error('[ReservationConditionsRouter][RegisterReservationConditionAPI] Failed to register the reserve condition.')
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'Failed to register the reserve condition',
        )

    # どのキーワード自動予約条件 ID で追加されたかは sendAddAutoAdd() のレスポンスからは取れないので、201 Created を返す


@router.get(
    '/{reservation_condition_id}',
    summary = 'キーワード自動予約条件取得 API',
    response_description = 'キーワード自動予約条件。',
    response_model = schemas.ReservationCondition,
)
async def ReservationConditionAPI(
    auto_add_data: Annotated[AutoAddDataRequired, Depends(GetAutoAddData)],
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
):
    """
    指定されたキーワード自動予約条件の情報を取得する。
    """

    # EDCB の AutoAddData オブジェクトを schemas.ReservationCondition オブジェクトに変換して返す
    chset5_services = await GetChSet5Services(edcb)
    return await DecodeEDCBAutoAddData(auto_add_data, edcb, chset5_services)


@router.put(
    '/{reservation_condition_id}',
    summary = 'キーワード自動予約条件更新 API',
    response_description = '更新されたキーワード自動予約条件。',
    response_model = schemas.ReservationCondition,
)
async def UpdateReservationConditionAPI(
    auto_add_data: Annotated[AutoAddDataRequired, Depends(GetAutoAddData)],
    reserve_condition_update_request: Annotated[schemas.ReservationConditionUpdateRequest, Body(description='更新するキーワード自動予約条件。')],
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
):
    """
    指定されたキーワード自動予約条件を更新する。
    """

    # 現在のキーワード自動予約条件の AutoAddData に新しい検索条件・録画設定を上書きマージする形で EDCB に送信する
    chset5_services = await GetChSet5Services(edcb)
    auto_add_data['search_info'] = await EncodeEDCBSearchKeyInfo(
        reserve_condition_update_request.program_search_condition,
        edcb,
        chset5_services,
    )
    auto_add_data['rec_setting'] = EncodeEDCBRecSettingData(reserve_condition_update_request.record_settings)

    # EDCB に指定されたキーワード自動予約条件を更新するように指示
    result = await edcb.sendChgAutoAdd([cast(AutoAddData, auto_add_data)])
    if result is False:
        # False が返ってきた場合はエラーを返す
        logging.error('[ReservationConditionsRouter][UpdateReservationConditionAPI] Failed to update the specified reserve condition. '
                      f'[reservation_condition_id: {auto_add_data["data_id"]}]')
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'Failed to update the specified reserve condition',
        )

    # 更新されたキーワード自動予約条件の情報を schemas.ReservationCondition オブジェクトに変換して返す
    return await DecodeEDCBAutoAddData(
        await GetAutoAddData(auto_add_data['data_id'], edcb),
        edcb,
        chset5_services,
    )


@router.delete(
    '/{reservation_condition_id}',
    summary = 'キーワード自動予約条件削除 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def DeleteReservationConditionAPI(
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
        logging.error('[ReservationConditionsRouter][DeleteReservationConditionAPI] Failed to delete the specified reserve condition. '
                      f'[reservation_condition_id: {auto_add_data["data_id"]}]')
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'Failed to delete the specified reserve condition',
        )
