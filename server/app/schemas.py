
from datetime import datetime
from pydantic import AnyHttpUrl, BaseModel, confloat, DirectoryPath, Field, FilePath, PositiveInt
from pydantic.networks import stricturl
from tortoise.contrib.pydantic import pydantic_model_creator
from typing import Literal

from app import models


# 環境設定を表す Pydantic モデル
# バリデーションは環境設定をこの Pydantic モデルに通すことで行う

class Config(BaseModel):
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

# モデルを表す Pydantic モデル
# 基本的には pydantic_model_creator() で Tortoise ORM モデルから変換したものを継承
# JSONField など変換だけでは補いきれない部分や、新しく追加したいカラムなどを追加で定義する

# Channel モデルで Program モデルを使っているため、先に定義する
class Program(pydantic_model_creator(models.Program, name='Program')):
    class Genre(BaseModel):
        major: str
        middle: str
    detail: dict[str, str]
    genre: list[Genre]

class Channel(pydantic_model_creator(models.Channel, name='Channel')):
    is_display: bool = True  # 追加カラム
    viewers: int
    program_present: Program | None  # 追加カラム
    program_following: Program | None  # 追加カラム

class LiveStream(BaseModel):
    # LiveStream は特殊なモデルのため、ここで全て定義する
    status: Literal['Offline', 'Standby', 'ONAir', 'Idling', 'Restart']
    detail: str
    started_at: float
    updated_at: float
    clients_count: int

class TwitterAccount(pydantic_model_creator(models.TwitterAccount, name='TwitterAccount',
    exclude=('access_token', 'access_token_secret', 'created_at', 'updated_at'))):
    is_oauth_session: bool  # 追加カラム
    created_at: datetime  # is_oauth_session の下に配置するために、一旦 exclude した上で再度定義する
    updated_at: datetime  # is_oauth_session の下に配置するために、一旦 exclude した上で再度定義する
    pass

class User(pydantic_model_creator(models.User, name='User',
    exclude=('password', 'client_settings', 'niconico_access_token', 'niconico_refresh_token', 'created_at', 'updated_at'))):
    twitter_accounts: list[TwitterAccount]  # 追加カラム
    created_at: datetime  # twitter_accounts の下に配置するために、一旦 exclude した上で再度定義する
    updated_at: datetime  # twitter_accounts の下に配置するために、一旦 exclude した上で再度定義する

# API リクエストに利用する Pydantic モデル
# リクエストボティの JSON の構造を表す

class UserCreateRequest(BaseModel):
    username: str
    password: str

class UserUpdateRequest(BaseModel):
    username: str | None
    password: str | None

class UserUpdateRequestForAdmin(BaseModel):
    username: str | None
    password: str | None
    is_admin: bool | None

class TwitterPasswordAuthRequest(BaseModel):
    screen_name: str
    password: str

# API レスポンスに利用する Pydantic モデル
# モデルを List や Dict でまとめたものが中心

class Channels(BaseModel):
    GR: list[Channel]
    BS: list[Channel]
    CS: list[Channel]
    CATV: list[Channel]
    SKY: list[Channel]
    STARDIGIO: list[Channel]

class JikkyoSession(BaseModel):
    is_success: bool
    audience_token: str | None
    detail: str

class LiveStreams(BaseModel):
    Restart: dict[str, LiveStream]
    Idling: dict[str, LiveStream]
    ONAir: dict[str, LiveStream]
    Standby: dict[str, LiveStream]
    Offline: dict[str, LiveStream]

class LiveStreamLLHLSClientID(BaseModel):
    client_id: str

class ClientSettings(BaseModel):
    # 詳細は client/src/services/Settings.ts と client/src/store/SettingsStore.ts を参照
    # デバイス間で同期するとかえって面倒なことになりそうな設定は除外している
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
    specify_caption_background_color: bool = Field(False)
    caption_background_color: str = Field('#00000080')
    tv_show_superimpose: bool = Field(True)
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

class ThirdpartyAuthURL(BaseModel):
    authorization_url: str

class TweetResult(BaseModel):
    is_success: bool
    tweet_url: str | None
    detail: str

class Users(BaseModel):
    __root__: list[User]

class UserAccessToken(BaseModel):
    access_token: str
    token_type: str

class VersionInformation(BaseModel):
    version: str
    latest_version: str | None
    environment: Literal['Windows', 'Linux', 'Linux-Docker']
    backend: Literal['EDCB', 'Mirakurun']
    encoder: Literal['FFmpeg', 'QSVEncC', 'NVEncC', 'VCEEncC', 'rkmppenc']
