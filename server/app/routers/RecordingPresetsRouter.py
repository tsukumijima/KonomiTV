
import configparser
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status

from app import logging, schemas
from app.routers.ReservationsRouter import GetCtrlCmdUtil
from app.utils.edcb.CtrlCmdUtil import CtrlCmdUtil
from app.utils.edcb.EDCBUtil import EDCBUtil


# ルーター
router = APIRouter(
    tags = ['Recording Presets'],
    prefix = '/api/recording',
)


def ParseGlobalDefaults(config: configparser.ConfigParser) -> schemas.RecordSettingsGlobalDefaults:
    """
    EpgTimerSrv.ini の [SET] セクションからグローバルデフォルト値をパースする。
    グローバルデフォルト値は、各録画設定の「デフォルト設定を使う」選択時に実際に適用される値。

    Args:
        config (configparser.ConfigParser): パース済みの ini ファイル

    Returns:
        schemas.RecordSettingsGlobalDefaults: グローバルデフォルト値
    """

    set_section = config['SET'] if 'SET' in config else {}

    # 録画開始マージン (デフォルト: 5秒)
    recording_start_margin = int(set_section.get('StartMargin', '5'))

    # 録画終了マージン (デフォルト: 2秒)
    recording_end_margin = int(set_section.get('EndMargin', '2'))

    # 字幕録画 (デフォルト: 1 = 録画する)
    caption_value = int(set_section.get('Caption', '1'))
    caption_recording_mode: Literal['Enable', 'Disable'] = 'Enable' if caption_value != 0 else 'Disable'

    # データ放送録画 (デフォルト: 0 = 録画しない)
    data_value = int(set_section.get('Data', '0'))
    data_broadcasting_recording_mode: Literal['Enable', 'Disable'] = 'Enable' if data_value != 0 else 'Disable'

    # 録画後動作 (RecEndMode と Reboot の組み合わせ)
    ## RecEndMode: 0=何もしない, 1=スタンバイ, 2=休止, 3=シャットダウン
    ## Reboot: 0=再起動しない, 1=再起動する
    rec_end_mode = int(set_section.get('RecEndMode', '2'))
    reboot = int(set_section.get('Reboot', '0'))
    post_recording_mode: Literal['Nothing', 'Standby', 'StandbyAndReboot', 'Suspend', 'SuspendAndReboot', 'Shutdown']
    if rec_end_mode == 1 and reboot == 0:
        post_recording_mode = 'Standby'
    elif rec_end_mode == 1 and reboot != 0:
        post_recording_mode = 'StandbyAndReboot'
    elif rec_end_mode == 2 and reboot == 0:
        post_recording_mode = 'Suspend'
    elif rec_end_mode == 2 and reboot != 0:
        post_recording_mode = 'SuspendAndReboot'
    elif rec_end_mode == 3:
        post_recording_mode = 'Shutdown'
    else:
        # rec_end_mode == 0 または範囲外 (何もしない)
        post_recording_mode = 'Nothing'

    return schemas.RecordSettingsGlobalDefaults(
        recording_start_margin = recording_start_margin,
        recording_end_margin = recording_end_margin,
        caption_recording_mode = caption_recording_mode,
        data_broadcasting_recording_mode = data_broadcasting_recording_mode,
        post_recording_mode = post_recording_mode,
    )


def ParseRecordingFolders(
    config: configparser.ConfigParser,
    section_name: str,
    is_oneseg: bool,
) -> list[schemas.RecordingFolder]:
    """
    EpgTimerSrv.ini の録画フォルダセクションをパースする。

    Args:
        config (configparser.ConfigParser): パース済みの ini ファイル
        section_name (str): セクション名 (例: 'REC_DEF_FOLDER', 'REC_DEF_FOLDER_1SEG1')
        is_oneseg (bool): ワンセグ録画フォルダかどうか

    Returns:
        list[schemas.RecordingFolder]: 録画フォルダ情報のリスト
    """

    folders: list[schemas.RecordingFolder] = []
    if section_name not in config:
        return folders

    section = config[section_name]
    folder_count = int(section.get('Count', '0'))
    for i in range(folder_count):
        folder_path = section.get(str(i), '')
        if folder_path == '':
            continue

        # RecNamePlugIn から ? 以降のファイル名テンプレート部分を抽出
        ## RecName_Macro.dll?$title$.ts のような形式で格納されている
        rec_name_plug_in = section.get(f'RecNamePlugIn{i}', '')
        recording_file_name_template: str | None = None
        if '?' in rec_name_plug_in:
            template = rec_name_plug_in.split('?', 1)[1]
            if template != '':
                recording_file_name_template = template

        folders.append(schemas.RecordingFolder(
            recording_folder_path = folder_path,
            recording_file_name_template = recording_file_name_template,
            is_oneseg_separate_recording_folder = is_oneseg,
        ))

    return folders


def ParsePreset(
    config: configparser.ConfigParser,
    preset_id: int,
) -> schemas.RecordSettingsPreset:
    """
    EpgTimerSrv.ini から指定された ID の録画設定プリセットをパースする。
    EDCB の PresetItem.cs の LoadPresetData() のロジックを移植している。

    Args:
        config (configparser.ConfigParser): パース済みの ini ファイル
        preset_id (int): プリセット ID (0 がデフォルト)

    Returns:
        schemas.RecordSettingsPreset: プリセット情報
    """

    # セクション名の決定
    # ID=0 のデフォルトプリセットは [REC_DEF], それ以外は [REC_DEF{ID}]
    id_suffix = '' if preset_id == 0 else str(preset_id)
    section_name = f'REC_DEF{id_suffix}'
    section = config[section_name] if section_name in config else {}

    # プリセット名 (デフォルト: 「デフォルト」)
    preset_name = section.get('SetName', 'デフォルト')

    # RecMode: 0-4=有効, 5-9=無効
    ## EDCB の PresetItem.cs のロジック:
    ## IsEnable = RecMode / 5 % 2 == 0 (つまり RecMode <= 4 なら有効)
    ## 無効時は NoRecMode を使って実際のモードを取得
    raw_rec_mode = int(section.get('RecMode', '1'))
    no_rec_mode = int(section.get('NoRecMode', '1'))
    is_enabled = raw_rec_mode <= 4
    effective_rec_mode = raw_rec_mode if is_enabled is True else no_rec_mode

    # 録画モードの変換
    recording_mode_map: dict[int, Literal['AllServices', 'AllServicesWithoutDecoding', 'SpecifiedService', 'SpecifiedServiceWithoutDecoding', 'View']] = {
        0: 'AllServices',
        1: 'SpecifiedService',
        2: 'AllServicesWithoutDecoding',
        3: 'SpecifiedServiceWithoutDecoding',
        4: 'View',
    }
    recording_mode = recording_mode_map.get(effective_rec_mode, 'SpecifiedService')

    # 優先度 (デフォルト: 2, 範囲: 1-5)
    priority = max(1, min(5, int(section.get('Priority', '2'))))

    # イベントリレー追従 (デフォルト: 1 = 有効)
    is_event_relay_follow_enabled = int(section.get('TuijyuuFlag', '1')) != 0

    # 字幕/データ放送の service_mode ビットフラグ
    ## ref: EDCB CommonDef.h
    ## 0x00000001: 個別の設定値を使用 (これが 0 ならデフォルト設定を使う)
    ## 0x00000010: 字幕データを含む
    ## 0x00000020: データカルーセルを含む
    service_mode = int(section.get('ServiceMode', '0'))
    caption_recording_mode: Literal['Default', 'Enable', 'Disable']
    data_broadcasting_recording_mode: Literal['Default', 'Enable', 'Disable']
    if service_mode & 0x01:
        caption_recording_mode = 'Enable' if service_mode & 0x10 else 'Disable'
        data_broadcasting_recording_mode = 'Enable' if service_mode & 0x20 else 'Disable'
    else:
        caption_recording_mode = 'Default'
        data_broadcasting_recording_mode = 'Default'

    # ぴったり録画 (デフォルト: 0 = 無効)
    is_exact_recording_enabled = int(section.get('PittariFlag', '0')) != 0

    # 録画後 bat ファイルパス
    bat_file_path_raw = section.get('BatFilePath', '')
    post_recording_bat_file_path: str | None = bat_file_path_raw if bat_file_path_raw != '' else None

    # 録画後動作
    ## SuspendMode: 0=デフォルト設定を使う, 1=スタンバイ, 2=休止, 3=シャットダウン, 4=何もしない
    ## RebootFlag: 0=再起動しない, 1=復帰後再起動する
    suspend_mode = int(section.get('SuspendMode', '0'))
    reboot_flag = int(section.get('RebootFlag', '0')) != 0
    post_recording_mode: Literal['Default', 'Nothing', 'Standby', 'StandbyAndReboot', 'Suspend', 'SuspendAndReboot', 'Shutdown']
    if suspend_mode == 0:
        post_recording_mode = 'Default'
    elif suspend_mode == 1 and reboot_flag is False:
        post_recording_mode = 'Standby'
    elif suspend_mode == 1 and reboot_flag is True:
        post_recording_mode = 'StandbyAndReboot'
    elif suspend_mode == 2 and reboot_flag is False:
        post_recording_mode = 'Suspend'
    elif suspend_mode == 2 and reboot_flag is True:
        post_recording_mode = 'SuspendAndReboot'
    elif suspend_mode == 3:
        post_recording_mode = 'Shutdown'
    elif suspend_mode == 4:
        post_recording_mode = 'Nothing'
    else:
        post_recording_mode = 'Default'

    # マージン設定
    ## UseMargineFlag: 0=グローバルデフォルトを使う, 1=個別指定
    ## EDCB のスペルミス ("Margine") をそのまま使う
    use_margin_flag = int(section.get('UseMargineFlag', '0')) != 0
    recording_start_margin: int | None = None
    recording_end_margin: int | None = None
    if use_margin_flag is True:
        recording_start_margin = int(section.get('StartMargine', '5'))
        recording_end_margin = int(section.get('EndMargine', '2'))

    # 連続録画 (デフォルト: 0 = 無効)
    is_sequential_recording_in_single_file_enabled = int(section.get('ContinueRec', '0')) != 0

    # ワンセグ分離出力 (デフォルト: 0 = 無効)
    is_oneseg_separate_output_enabled = int(section.get('PartialRec', '0')) == 1

    # チューナー強制指定 (デフォルト: 0 = 自動選択)
    tuner_id_raw = int(section.get('TunerID', '0'))
    forced_tuner_id: int | None = tuner_id_raw if tuner_id_raw != 0 else None

    # 録画フォルダ情報のパース
    recording_folders: list[schemas.RecordingFolder] = []
    # 通常録画フォルダ: [REC_DEF_FOLDER] or [REC_DEF_FOLDER{ID}]
    recording_folders.extend(ParseRecordingFolders(config, f'REC_DEF_FOLDER{id_suffix}', is_oneseg=False))
    # ワンセグ録画フォルダ: [REC_DEF_FOLDER_1SEG] or [REC_DEF_FOLDER_1SEG{ID}]
    recording_folders.extend(ParseRecordingFolders(config, f'REC_DEF_FOLDER_1SEG{id_suffix}', is_oneseg=True))

    return schemas.RecordSettingsPreset(
        id = preset_id,
        name = preset_name,
        record_settings = schemas.RecordSettings(
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
        ),
    )


@router.get(
    '/presets',
    summary = '録画設定プリセット一覧 API',
    response_description = 'グローバルデフォルト値と録画設定プリセットの一覧。',
    response_model = schemas.RecordSettingsPresets,
)
async def RecordingPresetsAPI(
    edcb: Annotated[CtrlCmdUtil, Depends(GetCtrlCmdUtil)],
) -> schemas.RecordSettingsPresets:
    """
    EDCB の EpgTimerSrv.ini から録画設定プリセット一覧を取得する。<br>
    グローバルデフォルト値 (`[SET]` セクション) と、各録画設定プリセットを返す。<br>
    この API は EDCB バックエンド選択時のみ利用可能。
    """

    # EDCB から EpgTimerSrv.ini を取得
    files = await edcb.sendFileCopy2(['EpgTimerSrv.ini'])
    if files is None or len(files) == 0:
        logging.error('[RecordingPresetsRouter][RecordingPresetsAPI] Failed to get EpgTimerSrv.ini from EDCB.')
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'Failed to get EpgTimerSrv.ini from EDCB',
        )

    ini_data = files[0]['data']
    if not ini_data:
        logging.error('[RecordingPresetsRouter][RecordingPresetsAPI] EpgTimerSrv.ini is empty.')
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'EpgTimerSrv.ini is empty',
        )

    # バイナリデータを文字列に変換 (BOM 判定付き)
    ini_text = EDCBUtil.convertBytesToString(ini_data)

    # configparser でパース
    ## Python の configparser はキー名をデフォルトで小文字に変換するため、optionxform を str に設定して PascalCase を保持する
    ## interpolation=None を指定して補間を無効化する
    ## (BatFilePath に %SystemDrive% 等の Windows 環境変数が含まれている場合、デフォルトの BasicInterpolation だと
    ##  InterpolationSyntaxError が発生するため)
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str  # type: ignore
    config.read_string(ini_text)

    # グローバルデフォルト値のパース
    try:
        global_defaults = ParseGlobalDefaults(config)
    except Exception as ex:
        logging.error('[RecordingPresetsRouter][RecordingPresetsAPI] Failed to parse global defaults from EpgTimerSrv.ini:', exc_info=ex)
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'Failed to parse global defaults from EpgTimerSrv.ini',
        )

    # プリセット一覧のパース
    presets: list[schemas.RecordSettingsPreset] = []

    # ID=0 のデフォルトプリセットは仕様上常に存在する
    try:
        presets.append(ParsePreset(config, 0))
    except Exception as ex:
        logging.error('[RecordingPresetsRouter][RecordingPresetsAPI] Failed to parse default preset (ID=0):', exc_info=ex)
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = 'Failed to parse default preset from EpgTimerSrv.ini',
        )

    # カスタムプリセットの ID リストを [SET] セクションの PresetID キーから取得
    ## PresetID の値はカンマ区切りの ID リスト (例: "1,2,3,")
    ## 末尾にカンマが付くことがあるため空文字列のスキップが必要
    set_section = config['SET'] if 'SET' in config else {}
    preset_id_str = set_section.get('PresetID', '')
    if preset_id_str != '':
        for id_str in preset_id_str.split(','):
            id_str = id_str.strip()
            if id_str == '':
                continue
            try:
                preset_id = int(id_str)
            except ValueError:
                continue
            # ID=0 は既に追加済みなのでスキップ
            if preset_id == 0:
                continue
            # カスタムプリセットのパース (失敗した場合はスキップして続行)
            try:
                presets.append(ParsePreset(config, preset_id))
            except Exception as ex:
                logging.warning(f'[RecordingPresetsRouter][RecordingPresetsAPI] Failed to parse preset (ID: {preset_id}), skipping:', exc_info=ex)
                continue

    return schemas.RecordSettingsPresets(
        global_defaults = global_defaults,
        presets = presets,
    )
