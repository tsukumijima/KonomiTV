
import asyncio
import concurrent.futures
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Any, Literal, cast

import httpx
import psutil
import ruamel.yaml
import ruamel.yaml.scalarstring
from pydantic import (
    BaseModel,
    DirectoryPath,
    FilePath,
    PositiveFloat,
    PositiveInt,
    UrlConstraints,
    ValidationError,
    ValidationInfo,
    confloat,
    field_validator,
)
from pydantic_core import Url

from app.constants import (
    API_REQUEST_HEADERS,
    BASE_DIR,
    LIBRARY_PATH,
)
from app.utils.TSInformation import TerrestrialRegion


# クライアント設定を表す Pydantic モデル (クライアント設定同期用 API で利用)
# デバイス間で同期するとかえって面倒なことになりそうな設定は除外されている
# 詳細は client/src/services/Settings.ts と client/src/stores/SettingsStore.ts を参照

class ClientSettings(BaseModel):
    last_synced_at: Annotated[float, PositiveFloat] = 0.0
    # showed_panel_last_time: 同期無効
    # selected_twitter_account_id: 同期無効
    saved_twitter_hashtags: list[str] = []
    mylist: list[dict[str, Any]] = []
    watched_history: list[dict[str, Any]] = []
    # lshaped_screen_crop_enabled: 同期無効
    # lshaped_screen_crop_zoom_level: 同期無効
    # lshaped_screen_crop_x_position: 同期無効
    # lshaped_screen_crop_y_position: 同期無効
    # lshaped_screen_crop_zoom_origin: 同期無効
    pinned_channel_ids: list[str] = []
    timetable_channel_width: Literal['Wide', 'Normal', 'Narrow'] = 'Normal'
    timetable_hour_height: Literal['Wide', 'Normal', 'Narrow'] = 'Normal'
    timetable_hover_expand: bool = False
    timetable_dim_shopping_programs: bool = True
    # 番組表のジャンル別のハイライト色
    # キーはジャンル名 (大分類)、値はハイライトカラー
    # クライアント側の ILocalClientSettingsDefault.timetable_genre_colors と一致させる必要がある
    timetable_genre_colors: dict[str, Literal['White', 'Pink', 'Red', 'Orange', 'Yellow', 'Lime', 'Teal', 'Cyan', 'Blue', 'Ochre', 'Brown']] = {
        'ニュース・報道': 'White',
        '情報・ワイドショー': 'White',
        'ドキュメンタリー・教養': 'Blue',
        'スポーツ': 'Cyan',
        'ドラマ': 'Pink',
        'アニメ・特撮': 'Yellow',
        'バラエティ': 'Lime',
        '音楽': 'Orange',
        '映画': 'Brown',
        '劇場・公演': 'Ochre',
        '趣味・教育': 'Teal',
        '福祉': 'White',
        'その他': 'White',
    }
    show_player_background_image: bool = True
    use_pure_black_player_background: bool = False
    tv_channel_selection_requires_alt_key: bool = False
    use_28hour_clock: bool = False
    show_original_broadcast_time_during_playback: bool = False
    panel_display_state: Literal['RestorePreviousState', 'AlwaysDisplay', 'AlwaysFold'] = 'RestorePreviousState'
    tv_panel_active_tab: Literal['Program', 'Channel', 'Comment', 'Twitter'] = 'Program'
    video_panel_active_tab: Literal['RecordedProgram', 'Series', 'Comment', 'Twitter'] = 'RecordedProgram'
    video_watched_history_max_count: Annotated[int, PositiveInt] = 50
    # tv_streaming_quality: 同期無効
    # tv_streaming_quality_cellular: 同期無効
    # tv_data_saver_mode: 同期無効
    # tv_data_saver_mode_cellular: 同期無効
    # tv_low_latency_mode: 同期無効
    # tv_low_latency_mode_cellular: 同期無効
    # video_streaming_quality: 同期無効
    # video_streaming_quality_cellular: 同期無効
    # video_data_saver_mode: 同期無効
    # video_data_saver_mode_cellular: 同期無効
    caption_font: str = 'Windows TV MaruGothic'
    always_border_caption_text: bool = True
    specify_caption_opacity: bool = False
    caption_opacity: Annotated[float, confloat(ge=0.0, le=1.0)] = 1.0
    tv_show_superimpose: bool = True
    video_show_superimpose: bool = False
    # tv_show_data_broadcasting: 同期無効
    # enable_internet_access_from_data_broadcasting: 同期無効
    capture_save_mode: Literal['Browser', 'UploadServer', 'Both'] = 'UploadServer'
    capture_caption_mode: Literal['VideoOnly', 'CompositingCaption', 'Both'] = 'Both'
    capture_filename_pattern: str = 'Capture_%date%-%time%'
    # capture_copy_to_clipboard: 同期無効
    # sync_settings: 同期無効
    prefer_posting_to_nicolive: bool = True
    comment_speed_rate: Annotated[float, PositiveFloat] = 1.0
    comment_font_size: Annotated[int, PositiveInt] = 34
    close_comment_form_after_sending: bool = True
    mute_vulgar_comments: bool = True
    mute_abusive_discriminatory_prejudiced_comments: bool = True
    mute_big_size_comments: bool = True
    mute_fixed_comments: bool = False
    mute_colored_comments: bool = False
    mute_consecutive_same_characters_comments: bool = False
    muted_comment_keywords: list[dict[str, str]] = []
    muted_niconico_user_ids: list[str] = []
    fold_panel_after_sending_tweet: bool = False
    reset_hashtag_when_program_switches: bool = True
    auto_add_watching_channel_hashtag: bool = True
    twitter_active_tab: Literal['Search', 'Timeline', 'Capture'] = 'Capture'
    tweet_hashtag_position: Literal['Prepend', 'Append', 'PrependWithLineBreak', 'AppendWithLineBreak'] = 'Append'
    tweet_capture_watermark_position: Literal['None', 'TopLeft', 'TopRight', 'BottomLeft', 'BottomRight'] = 'None'


# サーバー設定を表す Pydantic モデル
# config.yaml のバリデーションは設定データをこの Pydantic モデルに通すことで行う

class _ServerSettingsGeneral(BaseModel):
    backend: Literal['EDCB', 'Mirakurun'] = 'EDCB'
    always_receive_tv_from_mirakurun: bool = False
    edcb_url: Annotated[Url, UrlConstraints(allowed_schemes=['tcp'])] = Url('tcp://127.0.0.1:4510/')
    mirakurun_url: Annotated[Url, UrlConstraints(allowed_schemes=['http', 'https'])] = Url('http://127.0.0.1:40772/')
    encoder: Literal['FFmpeg', 'QSVEncC', 'NVEncC', 'VCEEncC', 'rkmppenc'] = 'FFmpeg'
    program_update_interval: Annotated[float, confloat(ge=0.1)] = 5.0
    debug: bool = False
    debug_encoder: bool = False

    @field_validator('edcb_url')
    def validate_edcb_url(cls, edcb_url: Url, info: ValidationInfo) -> Url:
        # URL を末尾のスラッシュありに統一
        edcb_url = Url(str(edcb_url).rstrip('/') + '/')
        # バリデーションをスキップする場合はここで終了
        if type(info.context) is dict and info.context.get('bypass_validation') is True:
            return edcb_url
        # EDCB バックエンドの接続確認
        if info.data.get('backend') == 'EDCB':
            # 循環参照を避けるために遅延インポート
            from app.utils.edcb.EDCBUtil import EDCBUtil
            # edcb_url を明示的に指定
            ## edcb_url を省略すると内部で再帰的に LoadConfig() が呼ばれてしまい RecursionError が発生する
            edcb_host = EDCBUtil.getEDCBHost(edcb_url)
            edcb_port = EDCBUtil.getEDCBPort(edcb_url)
            # ホスト名またはポートが指定されていない
            if ((edcb_host is None) or (edcb_port is None and edcb_host != 'edcb-namedpipe')):
                raise ValueError(
                    'URL 内にホスト名またはポートが指定されていません。\n'
                    'EDCB の URL を間違えている可能性があります。'
                )
            # 現在の EpgTimerSrv の動作ステータスを取得できるか試してみる
            ## RecursionError 回避のために edcb_url を明示的に指定
            ## ThreadPoolExecutor 上で実行し、自動リロードモード時に発生するイベントループ周りの謎エラーを回避する
            with concurrent.futures.ThreadPoolExecutor(1) as executor:
                result = executor.submit(asyncio.run, EDCBUtil.getEDCBStatus(edcb_url)).result()
            if result == 'Unknown':
                raise ValueError(
                    f'EDCB ({edcb_url}) にアクセスできませんでした。\n'
                    'EDCB が起動していないか、URL を間違えている可能性があります。'
                )
            from app import logging
            logging.info(f'Backend: EDCB ({edcb_url}) Status: {result}')
        return edcb_url

    @field_validator('mirakurun_url')
    def validate_mirakurun_url(cls, mirakurun_url: Url, info: ValidationInfo) -> Url:
        # URL を末尾のスラッシュありに統一
        ## HTTP/HTTPS URL では Pydantic の Url インスタンスが自動的に末尾のスラッシュを付けてしまうようだが、
        ## 挙動が変わらないとも限らないので、一応明示的に付けておく
        mirakurun_url = Url(str(mirakurun_url).rstrip('/') + '/')
        # バリデーションをスキップする場合はここで終了
        if type(info.context) is dict and info.context.get('bypass_validation') is True:
            return mirakurun_url
        # Mirakurun バックエンドの接続確認
        if info.data.get('backend') == 'Mirakurun' or info.data.get('always_receive_tv_from_mirakurun') is True:
            # 試しにリクエストを送り、200 (OK) が返ってきたときだけ有効な URL とみなす
            try:
                response = httpx.get(
                    # Mirakurun API は http://127.0.0.1:40772//api/tuners のような二重スラッシュを許容しないので、
                    # mirakurun_url の末尾のスラッシュを削除してから endpoint を追加する必要がある
                    ## 従来は /api/version にアクセスしていたが、Mirakurun 4.0.0-beta.5 以下のバージョンには
                    ## API 実行時に録画中のストリームがドロップする重大なバグがあるため、他のエンドポイントを使うようにした
                    ## ref: https://github.com/Chinachu/Mirakurun/commit/27fccf9cd9dd08e56614dabf2ceb1b27a6096f0e
                    url = str(mirakurun_url).rstrip('/') + '/api/tuners',
                    headers = API_REQUEST_HEADERS,
                    timeout = 20,  # 久々のアクセスだとなぜか時間がかかることがあるため、ここだけタイムアウトを長めに設定
                )
                # レスポンスヘッダーの Server から Mirakurun か mirakc かを判定
                server_header = response.headers.get('server', '').lower()
                if 'mirakc' in server_header:
                    mirakurun_or_mirakc = 'mirakc'
                    # Server ヘッダーからバージョン情報を抽出 (例: mirakc/3.4.4)
                    version_info = server_header.split('/')[-1] if '/' in server_header else 'unknown'
                else:
                    mirakurun_or_mirakc = 'Mirakurun'
                    # Server ヘッダーからバージョン情報を抽出 (例: Mirakurun/3.9.0-rc.4)
                    version_info = server_header.split('/')[-1] if '/' in server_header else 'unknown'
            except (httpx.NetworkError, httpx.TimeoutException):
                raise ValueError(
                    f'Mirakurun / mirakc ({mirakurun_url}) にアクセスできませんでした。\n'
                    'Mirakurun / mirakc が起動していないか、URL を間違えている可能性があります。'
                )
            try:
                response_json = response.json()
                if response.status_code != 200 or not isinstance(response_json, list) or version_info == 'unknown':
                    raise ValueError()
            except Exception:
                raise ValueError(
                    f'{mirakurun_url} は {mirakurun_or_mirakc} の URL ではありません。\n'
                    f'{mirakurun_or_mirakc} の URL を間違えている可能性があります。'
                )
            from app import logging
            logging.info(f'Backend: {mirakurun_or_mirakc} {version_info} ({mirakurun_url})')
            if info.data.get('always_receive_tv_from_mirakurun') is True:
                logging.info(f'Always receive TV from {mirakurun_or_mirakc}.')
        return mirakurun_url

    @field_validator('encoder')
    def validate_encoder(cls, encoder: str, info: ValidationInfo) -> str:
        # バリデーションをスキップする場合はここで終了
        if type(info.context) is dict and info.context.get('bypass_validation') is True:
            return encoder
        from app import logging
        current_arch = platform.machine()
        # x64 なのにエンコーダーとして rkmppenc が指定されている場合
        if current_arch in ['AMD64', 'x86_64'] and encoder == 'rkmppenc':
            raise ValueError(
                'x64 アーキテクチャでは rkmppenc は使用できません。\n'
                '利用するエンコーダーを FFmpeg・QSVEncC・NVEncC・VCEEncC のいずれかに変更してください。'
            )
        # arm64 なのにエンコーダーとして QSVEncC・NVEncC・VCEEncC が指定されている場合
        if current_arch == 'aarch64' and encoder in ['QSVEncC', 'NVEncC', 'VCEEncC']:
            raise ValueError(
                'arm64 アーキテクチャでは QSVEncC・NVEncC・VCEEncC は使用できません。\n'
                '利用するエンコーダーを FFmpeg・rkmppenc のいずれかに変更してください。'
            )
        # HWEncC が指定されているときのみ、--check-hw でハードウェアエンコーダーが利用できるかをチェック
        ## もし利用可能なら標準出力に "H.264/AVC" という文字列が出力されるので、それで判定する
        if encoder != 'FFmpeg':
            result = subprocess.run(
                [LIBRARY_PATH[encoder], '--check-hw'],
                stdout = subprocess.PIPE,
                stderr = subprocess.DEVNULL,
            )
            result_stdout = result.stdout.decode('utf-8')
            result_stdout = '\n'.join([line for line in result_stdout.split('\n') if 'reader:' not in line])
            if 'unavailable.' in result_stdout:
                raise ValueError(
                    f'お使いの環境では {encoder} がサポートされていないため、KonomiTV を起動できません。\n'
                    f'別のエンコーダーを選択するか、{encoder} の動作環境を整備してください。'
                )
            # H.265/HEVC に対応していない環境では、通信節約モードが利用できない旨を出力する
            if 'H.265/HEVC' not in result_stdout:
                logging.warning(f'お使いの環境では {encoder} での H.265/HEVC エンコードがサポートされていないため、通信節約モードは利用できません。')
        # エンコーダーのバージョン情報を取得する
        ## バージョン情報は出力の1行目にある
        result = subprocess.run(
            [LIBRARY_PATH[encoder], '--version'],
            stdout = subprocess.PIPE,
            stderr = subprocess.STDOUT,
        )
        encoder_version = result.stdout.decode('utf-8').split('\n')[0]
        ## Copyright (FFmpeg) と by rigaya (HWEncC) 以降の文字列を削除
        encoder_version = re.sub(r' Copyright.*$', '', encoder_version)
        encoder_version = re.sub(r' by rigaya.*$', '', encoder_version)
        encoder_version = encoder_version.replace('ffmpeg', 'FFmpeg').strip()
        logging.info(f'Encoder: {encoder_version}')
        return encoder

class _ServerSettingsServer(BaseModel):
    port: PositiveInt = 7000
    custom_https_certificate: FilePath | None = None
    custom_https_private_key: FilePath | None = None

    @field_validator('port')
    def validate_port(cls, port: int, info: ValidationInfo) -> int:
        # バリデーションをスキップする場合はここで終了
        if type(info.context) is dict and info.context.get('bypass_validation') is True:
            return port
        # リッスンするポート番号が 1024 ~ 65525 の間に収まっているかをチェック
        if port < 1024 or port > 65525:
            raise ValueError(
                'ポート番号の設定が不正なため、KonomiTV を起動できません。\n'
                '設定したポート番号が 1024 ~ 65525 (65535 ではない) の間に収まっているかを確認してください。'
            )
        # 使用中のポートを取得
        # ref: https://qiita.com/skokado/items/6e76762c68866d73570b
        current_process = psutil.Process()
        used_ports: list[int] = []
        for conn in psutil.net_connections():
            if conn.status == 'LISTEN':
                if conn.pid is None:
                    continue
                # 自分自身のプロセスは除外
                ## サーバーの起動中に再度バリデーションが実行された際に、ポートが使用中と判定されてしまうのを防ぐためのもの
                ## 自動リロードモードでの reloader process や Akebi は KonomiTV サーバーの子プロセスになるので、
                ## プロセスの親プロセスの PID が一致するかもチェックする
                try:
                    process = psutil.Process(conn.pid)
                    if ((process.pid == current_process.pid) or
                        (process.pid == current_process.ppid()) or
                        (process.ppid() == current_process.pid) or
                        (process.ppid() == current_process.ppid())):
                        continue
                except Exception:
                    pass
                # 使用中のポートに追加
                if conn.laddr is not None:
                    used_ports.append(cast(Any, conn.laddr).port)
        # リッスンポートと同じポートが使われていたら、エラーを表示する
        # Akebi HTTPS Server のリッスンポートと Uvicorn のリッスンポートの両方をチェック
        if port in used_ports:
            raise ValueError(
                f'ポート {port} は他のプロセスで使われているため、KonomiTV を起動できません。\n'
                f'重複して KonomiTV を起動していないか、他のソフトでポート {port} を使っていないかを確認してください。'
            )
        if (port + 10) in used_ports:
            raise ValueError(
                f'ポート {port + 10} ({port} + 10) は他のプロセスで使われているため、KonomiTV を起動できません。\n'
                f'重複して KonomiTV を起動していないか、他のソフトでポート {port + 10} を使っていないかを確認してください。'
            )
        return port

class _ServerSettingsTV(BaseModel):
    preferred_terrestrial_region: TerrestrialRegion | None = None
    max_alive_time: PositiveInt = 10
    debug_mode_ts_path: FilePath | None = None

class _ServerSettingsVideo(BaseModel):
    recorded_folders: list[DirectoryPath] = []
    exclude_scan_paths: list[str] = []

class _ServerSettingsCapture(BaseModel):
    upload_folders: list[DirectoryPath] = []

class ServerSettings(BaseModel):
    general: _ServerSettingsGeneral = _ServerSettingsGeneral()
    server: _ServerSettingsServer = _ServerSettingsServer()
    tv: _ServerSettingsTV = _ServerSettingsTV()
    video: _ServerSettingsVideo = _ServerSettingsVideo()
    capture: _ServerSettingsCapture = _ServerSettingsCapture()


# サーバー設定データと読み込み・保存用の関数
# _CONFIG には config.yaml から読み込んだ KonomiTV サーバーの設定データが保持される
# _CONFIG には直接アクセスせず、Config() 関数を通してアクセスする

_CONFIG: ServerSettings | None = None
_CONFIG_YAML_PATH = BASE_DIR.parent / 'config.yaml'
_DOCKER_PATH_PREFIX = '/host-rootfs'


def LoadConfig(bypass_validation: bool = False) -> ServerSettings:
    """
    config.yaml からサーバー設定データのロードとバリデーションを行い、グローバル変数に格納する
    基本 KonomiTV サーバー起動時に一度だけ呼び出されるが、自動リロードモードやマルチプロセス実行時にも呼び出される
    いずれの場合でも、1プロセス内で複数回呼び出されることはない

    Args:
        bypass_validation (bool): バリデーションをスキップするかどうか

    Raises:
        SystemExit: 設定ファイルが配置されていなかったり、設定内容が不正な場合はサーバーを起動できないため、プロセスを終了する

    Returns:
        ServerSettings: 読み込んだサーバー設定データ
    """

    def MergeConfigWithDefaults(config_dict: dict[str, Any]) -> dict[str, Any]:
        """
        config.yaml の読み込み結果をデフォルト設定とマージする

        Args:
            config_dict (dict[str, Any]): config.yaml から読み込んだ設定データ

        Returns:
            dict[str, Any]: デフォルト設定とマージ済みの設定データ
        """

        def merge_dicts(base_dict: dict[str, Any], override_dict: dict[str, Any]) -> dict[str, Any]:
            merged_dict = dict(base_dict)
            for key, value in override_dict.items():
                if (
                    key in merged_dict
                    and isinstance(merged_dict[key], dict)
                    and isinstance(value, dict)
                ):
                    merged_dict[key] = merge_dicts(merged_dict[key], value)
                else:
                    merged_dict[key] = value
            return merged_dict

        default_config_dict = ServerSettings().model_dump(mode='json')
        return merge_dicts(default_config_dict, config_dict)

    global _CONFIG, _CONFIG_YAML_PATH, _DOCKER_PATH_PREFIX
    assert _CONFIG is None, 'LoadConfig() has already been called.'

    # 循環参照を避けるために遅延インポート
    from app import logging
    from app.utils import GetPlatformEnvironment

    # 設定ファイルが配置されていない場合、エラーを表示して終了する
    if Path.exists(_CONFIG_YAML_PATH) is False:
        logging.error('設定ファイルが配置されていないため、KonomiTV を起動できません。')
        logging.error('config.example.yaml を config.yaml にコピーし、お使いの環境に合わせて編集してください。')
        sys.exit(1)

    # 設定ファイルからサーバー設定をロードする
    try:
        with open(_CONFIG_YAML_PATH, encoding='utf-8') as file:
            config_raw = ruamel.yaml.YAML().load(file)
            if config_raw is None:
                logging.error('設定ファイルが空のため、KonomiTV を起動できません。')
                logging.error('config.example.yaml を config.yaml にコピーし、お使いの環境に合わせて編集してください。')
                sys.exit(1)
        config_dict: dict[str, dict[str, Any]] = dict(config_raw)
    except Exception as error:
        logging.error('設定ファイルのロード中にエラーが発生したため、KonomiTV を起動できません。')
        logging.error(f'{type(error).__name__}: {error}')
        sys.exit(1)

    try:
        # config.yaml に存在しない設定値はデフォルト値で補完する
        config_dict = MergeConfigWithDefaults(config_dict)

        # Docker 上で実行されているとき、サーバー設定のうちパス指定の項目に Docker 環境向けの Prefix (/host-rootfs) を付ける
        ## /host-rootfs (docker-compose.yaml で定義) を通してホストマシンのファイルシステムにアクセスできる
        if GetPlatformEnvironment() == 'Linux-Docker':
            config_dict['video']['recorded_folders'] = [_DOCKER_PATH_PREFIX + folder for folder in config_dict['video']['recorded_folders']]
            if 'exclude_scan_paths' in config_dict['video']:
                # 空文字や空白だけのパスは無視する
                ## 空文字が Docker 用 Prefix に変換されると、全パスが除外対象になってしまうため
                exclude_scan_paths = [
                    pattern.strip()
                    for pattern in config_dict['video']['exclude_scan_paths']
                    if type(pattern) is str and pattern.strip() != ''
                ]
                config_dict['video']['exclude_scan_paths'] = [
                    _DOCKER_PATH_PREFIX + pattern
                    for pattern in exclude_scan_paths
                ]
            config_dict['capture']['upload_folders'] = [_DOCKER_PATH_PREFIX + folder for folder in config_dict['capture']['upload_folders']]
            if type(config_dict['tv']['debug_mode_ts_path']) is str:
                config_dict['tv']['debug_mode_ts_path'] = _DOCKER_PATH_PREFIX + config_dict['tv']['debug_mode_ts_path']
    except Exception:
        pass  # config.yaml の記述が不正な場合は何もしない（どっちみち後のバリデーション処理で弾かれる）

    # サーバー設定のバリデーションを実行
    if bypass_validation is False:
        try:
            _CONFIG = ServerSettings.model_validate(config_dict, context={'bypass_validation': False})
            logging.debug('Server settings loaded.')
        except ValidationError as error:

            # エラーのうちどれか一つでもカスタムバリデーターからのエラーだった場合、エラーメッセージを表示して終了する
            ## カスタムバリデーターからのエラーメッセージかどうかは ctx に error が含まれているかどうかで判定する
            custom_error = False
            for error_message in error.errors():
                if 'ctx' in error_message and 'error' in error_message['ctx'] and type(error_message['ctx']['error']) is str:
                    custom_error = True
                    for message in error_message['ctx']['error'].split('\n'):
                        logging.error(message)
            if custom_error is True:
                sys.exit(1)

            # それ以外のバリデーションエラー
            logging.error('設定内容が不正なため、KonomiTV を起動できません。')
            logging.error('以下のエラーメッセージを参考に、config.yaml の記述が正しいかを確認してください。')
            logging.error(error)
            sys.exit(1)
    else:
        _CONFIG = ServerSettings.model_validate(config_dict, context={'bypass_validation': True})
        # logging.debug('Server settings loaded (bypassed validation).')

    return _CONFIG


def SaveConfig(config: ServerSettings) -> None:
    """
    変更されたサーバー設定データを、コメントやフォーマットを保持した形で config.yaml に書き込む
    この関数は _CONFIG を更新しないため、設定変更を反映するにはサーバーを再起動する必要がある
    (仮に _CONFIG を更新するよう実装しても、すでに Config() から取得した値を使って実行されている処理は更新できない)

    Args:
        config (ServerSettings): 変更されたサーバー設定データ
    """

    global _CONFIG_YAML_PATH, _DOCKER_PATH_PREFIX

    # 循環参照を避けるために遅延インポート
    from app.utils import GetPlatformEnvironment

    # ServerSettings の Pydantic モデルを辞書に変換
    config_dict = config.model_dump(mode='json')

    # Docker 上で実行されているとき、サーバー設定のうちパス指定の項目に付与されている Docker 環境向けの Prefix (/host-rootfs) を外す
    ## LoadConfig() で実行されている処理と逆の処理を行う
    if GetPlatformEnvironment() == 'Linux-Docker':
        config_dict['video']['recorded_folders'] = [str(folder).replace(_DOCKER_PATH_PREFIX, '') for folder in config_dict['video']['recorded_folders']]
        config_dict['video']['exclude_scan_paths'] = [str(pattern).replace(_DOCKER_PATH_PREFIX, '') for pattern in config_dict['video']['exclude_scan_paths']]
        config_dict['capture']['upload_folders'] = [str(folder).replace(_DOCKER_PATH_PREFIX, '') for folder in config_dict['capture']['upload_folders']]
        if type(config_dict['tv']['debug_mode_ts_path']) is str or config_dict['tv']['debug_mode_ts_path'] is Path:
            config_dict['tv']['debug_mode_ts_path'] = str(config_dict['tv']['debug_mode_ts_path']).replace(_DOCKER_PATH_PREFIX, '')

    # config.yaml の内容をロード
    yaml = ruamel.yaml.YAML()
    yaml.default_flow_style = None  # None を使うと、スカラー以外のものはブロックスタイルになる
    yaml.preserve_quotes = True
    yaml.width = 20
    yaml.indent(mapping=4, sequence=4, offset=4)
    try:
        with open(_CONFIG_YAML_PATH, encoding='utf-8') as file:
            config_raw = yaml.load(file)
    except Exception as error:
        # 回復不可能
        raise RuntimeError(f'Failed to load config.yaml: {error}')

    # config.yaml の内容を更新して保存
    # コメントやフォーマットを保持して保存するために更新方法を工夫している
    for key in config_dict:
        # config.yaml 側に存在しないセクションがある場合は新規で作成する
        if key not in config_raw or config_raw[key] is None:
            config_raw[key] = ruamel.yaml.CommentedMap()
        for sub_key in config_dict[key]:
            # config.yaml 側に存在しないキーがある場合は新規で作成する
            if sub_key not in config_raw[key]:
                if type(config_dict[key][sub_key]) is list:
                    config_raw[key][sub_key] = ruamel.yaml.CommentedSeq()
                else:
                    config_raw[key][sub_key] = None
            # 文字列のリストを更新する場合は clear() と extend() を使う
            if type(config_dict[key][sub_key]) is list:
                if type(config_raw[key][sub_key]) is ruamel.yaml.CommentedSeq:
                    config_raw[key][sub_key].clear()
                    for item in config_dict[key][sub_key]:
                        config_raw[key][sub_key].append(ruamel.yaml.scalarstring.SingleQuotedScalarString(item))
                else:
                    config_raw[key][sub_key] = ruamel.yaml.CommentedSeq(config_dict[key][sub_key])
            # 文字列は明示的に SingleQuotedScalarString に変換する
            elif type(config_dict[key][sub_key]) is str:
                config_raw[key][sub_key] = ruamel.yaml.scalarstring.SingleQuotedScalarString(config_dict[key][sub_key])
            else:
                config_raw[key][sub_key] = config_dict[key][sub_key]

    # None を null として出力するようにする
    yaml.Representer.add_representer(type(None), lambda self, data: self.represent_scalar('tag:yaml.org,2002:null', 'null'))  # type: ignore

    # 配列の末尾の "']" を "',\n    ]" に変換する transform 関数を定義
    # 基本的に recorded_folders 用 (ruamel.yaml がフロースタイルの改行などを保持できないための苦肉の策)
    def transform(value: str) -> str:
        return value.replace("']", "',\n    ]")

    with open(_CONFIG_YAML_PATH, mode='w', encoding='utf-8') as file:
        yaml.dump(config_raw, file, transform=transform)


def Config() -> ServerSettings:
    """
    LoadConfig() でグローバル変数に格納したサーバー設定データを取得する
    この関数は、LoadConfig() を実行した後に呼び出さなければならない

    Returns:
        ServerSettings: サーバー設定データ
    """

    global _CONFIG
    assert _CONFIG is not None, 'Server settings have not been initialized.'
    return _CONFIG


def GetServerPort() -> int:
    """
    サーバーのポート番号を返す (KonomiTV-Service.py でポート番号を取得するために使用)
    KonomiTV-Service.py ではバリデーションは行いたくないので、Pydantic には通さずに config.yaml から直接ロードする

    Returns:
        int: サーバーのポート番号
    """

    try:

        # 設定ファイルからサーバー設定をロードし、ポート番号だけを返す
        with open(_CONFIG_YAML_PATH, encoding='utf-8') as file:
            config_dict: dict[str, dict[str, Any]] = dict(ruamel.yaml.YAML().load(file))
        return config_dict['server']['port']

    # 処理中にエラーが発生した (config.yaml が存在しない・フォーマットが不正など) 場合は、デフォルトのポート番号を返す
    except Exception:
        return 7000
