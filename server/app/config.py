
import logging.config
import ruamel.yaml
import logging
import sys
from pydantic import AnyHttpUrl, BaseModel, confloat, DirectoryPath, Field, FilePath, PositiveInt
from pydantic.networks import stricturl
from pathlib import Path
from typing import Any, Literal

from app.constants import (
    AKEBI_LOG_PATH,
    BASE_DIR,
    KONOMITV_ACCESS_LOG_PATH,
    KONOMITV_SERVER_LOG_PATH,
    LOGGING_CONFIG,
)


# クライアント設定を表す Pydantic モデル (クライアント設定同期用 API で利用)
# デバイス間で同期するとかえって面倒なことになりそうな設定は除外されている
# 詳細は client/src/services/Settings.ts と client/src/store/SettingsStore.ts を参照

class ClientSettings(BaseModel):
    pinned_channel_ids: list[str] = Field([])
    # showed_panel_last_time: 同期無効
    # selected_twitter_account_id: 同期無効
    saved_twitter_hashtags: list[str] = Field([])
    # tv_streaming_quality: 同期無効
    # tv_data_saver_mode: 同期無効
    # tv_low_latency_mode: 同期無効
    panel_display_state: Literal['RestorePreviousState', 'AlwaysDisplay', 'AlwaysFold'] = Field('RestorePreviousState')
    tv_panel_active_tab: Literal['Program', 'Channel', 'Comment', 'Twitter'] = Field('Program')
    tv_channel_selection_requires_alt_key: bool = Field(False)
    caption_font: str = Field('Windows TV MaruGothic')
    always_border_caption_text: bool = Field(True)
    specify_caption_opacity: bool = Field(False)
    caption_opacity: float = Field(1.0)
    tv_show_superimpose: bool = Field(True)
    # tv_show_data_broadcasting: 同期無効
    # capture_copy_to_clipboard: 同期無効
    capture_save_mode: Literal['Browser', 'UploadServer', 'Both'] = Field('UploadServer')
    capture_caption_mode: Literal['VideoOnly', 'CompositingCaption', 'Both'] = Field('Both')
    # sync_settings: 同期無効
    comment_speed_rate: float = Field(1)
    comment_font_size: int = Field(34)
    close_comment_form_after_sending: bool = Field(True)
    muted_comment_keywords: list[dict[str, str]] = Field([])
    muted_niconico_user_ids: list[str] = Field([])
    mute_vulgar_comments: bool = Field(True)
    mute_abusive_discriminatory_prejudiced_comments: bool = Field(True)
    mute_big_size_comments: bool = Field(True)
    mute_fixed_comments: bool = Field(False)
    mute_colored_comments: bool = Field(False)
    mute_consecutive_same_characters_comments: bool = Field(False)
    fold_panel_after_sending_tweet: bool = Field(False)
    reset_hashtag_when_program_switches: bool = Field(True)
    auto_add_watching_channel_hashtag: bool = Field(True)
    twitter_active_tab: Literal['Search', 'Timeline', 'Capture'] = Field('Capture')
    tweet_hashtag_position: Literal['Prepend', 'Append', 'PrependWithLineBreak', 'AppendWithLineBreak'] = Field('Append')
    tweet_capture_watermark_position: Literal['None', 'TopLeft', 'TopRight', 'BottomLeft', 'BottomRight'] = Field('None')

# サーバー設定を表す Pydantic モデル
# config.yaml のバリデーションは設定データをこの Pydantic モデルに通すことで行う

class ServerSettings(BaseModel):
    class General(BaseModel):
        backend: Literal['EDCB', 'Mirakurun']
        mirakurun_url: AnyHttpUrl
        edcb_url: stricturl(allowed_schemes={'tcp'}, tld_required=False)  # type: ignore
        encoder: Literal['FFmpeg', 'QSVEncC', 'NVEncC', 'VCEEncC', 'rkmppenc']
        program_update_interval: confloat(ge=0.1)  # type: ignore
        debug: bool
        debug_encoder: bool
    class Server(BaseModel):
        port: PositiveInt
        custom_https_certificate: FilePath | None
        custom_https_private_key: FilePath | None
    class TV(BaseModel):
        max_alive_time: PositiveInt
        debug_mode_ts_path: FilePath | None
    class Capture(BaseModel):
        upload_folder: DirectoryPath
    class Twitter(BaseModel):
        consumer_key: str | None
        consumer_secret: str | None
    general: General
    server: Server
    tv: TV
    capture: Capture
    twitter: Twitter

# 設定ファイルのパス
CONFIG_YAML = BASE_DIR.parent / 'config.yaml'

# 設定ファイルが配置されていない場合
if Path.exists(CONFIG_YAML) is False:

    # 前回のログをすべて削除
    try:
        if KONOMITV_SERVER_LOG_PATH.exists():
            KONOMITV_SERVER_LOG_PATH.unlink()
        if KONOMITV_ACCESS_LOG_PATH.exists():
            KONOMITV_ACCESS_LOG_PATH.unlink()
        if AKEBI_LOG_PATH.exists():
            AKEBI_LOG_PATH.unlink()
    except PermissionError:
        pass

    # Uvicorn を起動する前に Uvicorn のロガーを使えるようにする
    logging.config.dictConfig(LOGGING_CONFIG)
    __logger = logging.getLogger('uvicorn')

    # 処理を続行できないのでここで終了する
    __logger.error('設定ファイルが配置されていないため、KonomiTV を起動できません。')
    __logger.error('config.example.yaml を config.yaml にコピーし、お使いの環境に合わせて編集してください。')
    sys.exit(1)

# 設定ファイルからサーバー設定を読み込む
with open(CONFIG_YAML, encoding='utf-8') as file:
    CONFIG: dict[str, dict[str, Any]] = dict(ruamel.yaml.YAML().load(file))

    # EDCB / Mirakurun の URL の末尾のスラッシュをなしに統一
    ## これをやっておかないと Mirakurun の URL の末尾にスラッシュが入ってきた場合に接続に失敗する
    ## EDCB に関しては統一する必要はないが、念のため
    CONFIG['general']['edcb_url'] = CONFIG['general']['edcb_url'].rstrip('/')
    CONFIG['general']['mirakurun_url'] = CONFIG['general']['mirakurun_url'].rstrip('/')

    # Docker 上で実行されているとき、サーバー設定のうち、パス指定の項目に Docker 環境向けの Prefix (/host-rootfs) を付ける
    ## /host-rootfs (docker-compose.yaml で定義) を通してホストマシンのファイルシステムにアクセスできる
    if Path.exists(Path('/.dockerenv')) is True:
        __docker_fs_prefix = '/host-rootfs'
        CONFIG['capture']['upload_folder'] = __docker_fs_prefix + CONFIG['capture']['upload_folder']
        if type(CONFIG['tv']['debug_mode_ts_path']) is str:
            CONFIG['tv']['debug_mode_ts_path'] = __docker_fs_prefix + CONFIG['tv']['debug_mode_ts_path']
