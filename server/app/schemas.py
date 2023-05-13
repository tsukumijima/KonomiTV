
from datetime import datetime
from pydantic import AnyHttpUrl, BaseModel, confloat, DirectoryPath, Field, FilePath, PositiveInt
from pydantic.networks import stricturl
from tortoise.contrib.pydantic import PydanticModel
from typing import Literal, Union


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

# モデルを表す Pydantic モデル
# Pydantic モデルに含まれていないカラムは、API レスポンス返却時に自動で除外される (パスワードなど)
# 以前は pydantic_model_creator() で自動生成していたが、だんだん実態と合わなくなってきたため手動で定義している
# PydanticModel を使うところがポイント (BaseModel だとバリデーションエラーが発生する)

class Program(PydanticModel):
    id: str
    channel_id: str
    network_id: int
    service_id: int
    event_id: int
    title: str
    description: str
    detail: dict[str, str]
    start_time: datetime
    end_time: datetime
    duration: float
    is_free: bool
    class Genres(BaseModel):
        major: str
        middle: str
    genres: list[Genres]
    video_type: str | None
    video_codec: str | None
    video_resolution: str | None
    primary_audio_type: str
    primary_audio_language: str
    primary_audio_sampling_rate: str
    secondary_audio_type: str | None
    secondary_audio_language: str | None
    secondary_audio_sampling_rate: str | None

class Channel(PydanticModel):
    id: str
    display_channel_id: str
    network_id: int
    service_id: int
    transport_stream_id: int | None
    remocon_id: int
    channel_number: str
    type: str
    name: str
    jikkyo_force: int | None
    is_subchannel: bool
    is_radiochannel: bool
    is_watchable: bool
    is_display: bool  # 追加カラム
    viewer_count: int  # 追加カラム
    program_present: Program | None  # 追加カラム
    program_following: Program | None  # 追加カラム

class LiveStream(BaseModel):
    status: Literal['Offline', 'Standby', 'ONAir', 'Idling', 'Restart']
    detail: str
    started_at: float
    updated_at: float
    client_count: int

class TwitterAccount(PydanticModel):
    id: int
    name: str
    screen_name: str
    icon_url: str
    is_oauth_session: bool  # 追加カラム
    created_at: datetime
    updated_at: datetime

class User(PydanticModel):
    id: int
    name: str
    is_admin: bool
    niconico_user_id: int | None
    niconico_user_name: str | None
    niconico_user_premium: bool | None
    twitter_accounts: list[TwitterAccount]  # 追加カラム
    created_at: datetime
    updated_at: datetime

# API リクエストに利用する Pydantic モデル
# リクエストボティの JSON 構造を表す

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
# レスポンスボディの JSON 構造を表す

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

class ThirdpartyAuthURL(BaseModel):
    authorization_url: str

class TweetUser(BaseModel):
    id: str
    name: str
    screen_name: str
    icon_url: str

class Tweet(BaseModel):
    id: str
    created_at: datetime
    user: TweetUser
    text: str
    lang: str
    via: str
    image_urls: list[str] | None
    movie_url: str | None
    retweet_count: int
    retweeted: bool
    favorite_count: int
    favorited: bool
    retweeted_tweet: Union['Tweet', None]
    quoted_tweet: Union['Tweet', None]

class Tweets(BaseModel):
    __root__: list[Tweet]

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
    environment: Literal['Windows', 'Linux', 'Linux-Docker', 'Linux-ARM']
    backend: Literal['EDCB', 'Mirakurun']
    encoder: Literal['FFmpeg', 'QSVEncC', 'NVEncC', 'VCEEncC', 'rkmppenc']
