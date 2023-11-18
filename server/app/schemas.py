
import warnings
from datetime import date
from datetime import datetime
from pydantic import BaseModel
from pydantic import RootModel
from typing import Literal, Union
from typing_extensions import TypedDict

# Tortoise ORM がまだ Pydantic V2 に移行できていないため、インポート時や Pydantic モデル定義時に
# 非推奨 API が利用されていることを示す UserWarning が出力される
# 毎回警告が出るのは邪魔なため、このモジュールの読み込みが終わるまで一時的に UserWarning を抑制する
warnings.filterwarnings('ignore', category=UserWarning)
from tortoise.contrib.pydantic import PydanticModel


# モデルを表す Pydantic モデル
# Pydantic モデルに含まれていないカラムは、API レスポンス返却時に自動で除外される (パスワードなど)
# 以前は pydantic_model_creator() で自動生成していたが、だんだん実態と合わなくなってきたため手動で定義している
# PydanticModel を使うところがポイント (BaseModel だとバリデーションエラーが発生する)

class Genre(TypedDict):
    major: str
    middle: str

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
    genres: list[Genre]
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

class LiveChannel(Channel):
    # 以下はすべて動的に生成される TV ライブストリーミング用の追加カラム
    is_display: bool
    viewer_count: int
    program_present: Program | None
    program_following: Program | None

class CMSection(TypedDict):
    start_time: float
    end_time: float

class RecordedVideo(PydanticModel):
    id: int
    file_path: str
    file_hash: str
    file_size: int
    recording_start_time: datetime | None
    recording_end_time: datetime | None
    duration: float
    container_format: Literal['MPEG-TS']
    video_codec: Literal['MPEG-2', 'H.264', 'H.265']
    video_codec_profile: Literal['High', 'High 10', 'Main', 'Main 10', 'Baseline']
    video_scan_type: Literal['Interlaced', 'Progressive']
    video_frame_rate: float
    video_resolution_width: int
    video_resolution_height: int
    primary_audio_codec: Literal['AAC-LC', 'HE-AAC', 'MP2']
    primary_audio_channel: Literal['Monaural', 'Stereo', '5.1ch']
    primary_audio_sampling_rate: int
    secondary_audio_codec: Literal['AAC-LC', 'HE-AAC', 'MP2'] | None
    secondary_audio_channel: Literal['Monaural', 'Stereo', '5.1ch'] | None
    secondary_audio_sampling_rate: int | None
    cm_sections: list[CMSection]

class RecordedProgram(PydanticModel):
    id: int
    recorded_video: RecordedVideo
    recording_start_margin: float
    recording_end_margin: float
    is_partially_recorded: bool
    channel: Channel | None
    network_id: int | None
    service_id: int | None
    event_id: int | None
    series_id: int | None
    series_broadcast_period_id: int | None
    title: str
    series_title: str | None
    episode_number: str | None
    subtitle: str | None
    description: str
    detail: dict[str, str]
    start_time: datetime
    end_time: datetime
    duration: float
    is_free: bool
    genres: list[Genre]
    primary_audio_type: str
    primary_audio_language: str
    secondary_audio_type: str | None
    secondary_audio_language: str | None

class RecordedPrograms(BaseModel):
    total: int
    recorded_programs: list[RecordedProgram]

class SeriesBroadcastPeriod(PydanticModel):
    channel: Channel
    start_date: date
    end_date: date
    recorded_programs: list[RecordedProgram]

class Series(PydanticModel):
    id: int
    title: str
    description: str
    genres: list[Genre]
    broadcast_periods: list[SeriesBroadcastPeriod]
    updated_at: datetime

class SeriesList(BaseModel):
    total: int
    series_list: list[Series]

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
    username: str | None = None
    password: str | None = None

class UserUpdateRequestForAdmin(BaseModel):
    username: str | None = None
    password: str | None = None
    is_admin: bool | None = None

class TwitterPasswordAuthRequest(BaseModel):
    screen_name: str
    password: str

# API レスポンスに利用する Pydantic モデル
# レスポンスボディの JSON 構造を表す

class LiveChannels(BaseModel):
    GR: list[LiveChannel]
    BS: list[LiveChannel]
    CS: list[LiveChannel]
    CATV: list[LiveChannel]
    SKY: list[LiveChannel]
    STARDIGIO: list[LiveChannel]

class JikkyoComment(BaseModel):
    time: float
    type: Literal['top', 'right', 'bottom']
    size: Literal['big', 'medium', 'small']
    color: str
    author: str
    text: str

class JikkyoComments(BaseModel):
    is_success: bool
    comments: list[JikkyoComment]
    detail: str

class JikkyoSession(BaseModel):
    is_success: bool
    audience_token: str | None = None
    detail: str

class LiveStreamStatus(BaseModel):
    status: Literal['Offline', 'Standby', 'ONAir', 'Idling', 'Restart']
    detail: str
    started_at: float
    updated_at: float
    client_count: int

class LiveStreamStatuses(BaseModel):
    Restart: dict[str, LiveStreamStatus]
    Idling: dict[str, LiveStreamStatus]
    ONAir: dict[str, LiveStreamStatus]
    Standby: dict[str, LiveStreamStatus]
    Offline: dict[str, LiveStreamStatus]

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

class Tweets(RootModel[list[Tweet]]):
    pass

class TweetResult(BaseModel):
    is_success: bool
    tweet_url: str | None = None
    detail: str

class Users(RootModel[list[User]]):
    pass

class UserAccessToken(BaseModel):
    access_token: str
    token_type: str

class VersionInformation(BaseModel):
    version: str
    latest_version: str | None
    environment: Literal['Windows', 'Linux', 'Linux-Docker', 'Linux-ARM']
    backend: Literal['EDCB', 'Mirakurun']
    encoder: Literal['FFmpeg', 'QSVEncC', 'NVEncC', 'VCEEncC', 'rkmppenc']

# UserWarning を再度有効化
warnings.filterwarnings('default', category=UserWarning)
