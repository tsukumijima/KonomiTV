
from datetime import date
from datetime import datetime
from pydantic import BaseModel
from tortoise.contrib.pydantic import PydanticModel
from typing import Literal, Union


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

class RecordedVideo(PydanticModel):
    id: int
    file_path: str
    file_hash: str
    recording_start_time: datetime | None
    recording_end_time: datetime | None
    duration: float
    container_format: Literal['MPEG-TS']
    video_codec: Literal['MPEG-2', 'H.264', 'H.265']
    video_resolution_width: int
    video_resolution_height: int
    primary_audio_codec: Literal['AAC-LC', 'HE-AAC', 'MP2']
    primary_audio_channel: Literal['Monaural', 'Stereo', '5.1ch']
    primary_audio_sampling_rate: int
    secondary_audio_codec: Literal['AAC-LC', 'HE-AAC', 'MP2'] | None
    secondary_audio_channel: Literal['Monaural', 'Stereo', '5.1ch'] | None
    secondary_audio_sampling_rate: int | None
    cm_sections: list[tuple[float, float]]

class RecordedProgram(PydanticModel):
    id: int
    recorded_video: RecordedVideo
    recording_start_margin: float
    recording_end_margin: float
    is_partially_recorded: bool
    channel_id: str | None
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
    genres: list[dict[str, str]]
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
    genres: list[dict[str, str]]
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
