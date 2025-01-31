
import ariblib.constants
from datetime import datetime
from datetime import timedelta
from fastapi import APIRouter
from fastapi import Body
from fastapi import Depends
from typing import Annotated, cast
from zoneinfo import ZoneInfo

from app import schemas
from app.routers.ReservationConditionsRouter import EncodeEDCBSearchKeyInfo
from app.routers.ReservationsRouter import GetCtrlCmdUtil
from app.utils.edcb import EventInfo
from app.utils.edcb import SearchKeyInfo
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
    start_time = event_info.get('start_time', datetime(1970, 1, 1, 9, tzinfo=ZoneInfo('Asia/Tokyo')))

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
    search_key_info = await EncodeEDCBSearchKeyInfo(program_search_condition)

    # EDCB の EPG ストアに保存されているすべての番組情報を検索
    ## 過去番組は検索対象外
    event_info_list: list[EventInfo] | None = await edcb.sendSearchPg([cast(SearchKeyInfo, search_key_info)])
    if event_info_list is None:
        # None が返ってきた場合は空のリストを返す
        return schemas.Programs(total=0, programs=[])

    # EDCB の EventInfo オブジェクトを schemas.Program オブジェクトに変換
    programs = [DecodeEDCBEventInfo(event_info) for event_info in event_info_list]

    return schemas.Programs(total=len(programs), programs=programs)
