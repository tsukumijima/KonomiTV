
from pydantic import AnyHttpUrl, BaseModel, PositiveInt
from pydantic.networks import stricturl
from tortoise.contrib.pydantic import pydantic_model_creator
from typing import Any, Dict, List, Literal, Optional

from app import models


# 環境設定を表す Pydantic モデル
# バリデーションは環境設定をこの Pydantic モデルに通して行う
class Config(BaseModel):

    class General(BaseModel):
        debug: bool
        backend: Literal['Mirakurun', 'EDCB']
        mirakurun_url: AnyHttpUrl
        edcb_url: stricturl(allowed_schemes={'tcp'}, tld_required=False)

    class LiveStream(BaseModel):
        encoder: Literal['FFmpeg', 'QSVEncC', 'NVEncC', 'VCEEncC']
        max_alive_time: PositiveInt

    general: General
    livestream: LiveStream

# モデルを表す Pydantic モデル
# 基本的には pydantic_model_creator() で Tortoise ORM モデルから変換したものを継承
# JSONField など変換だけでは補いきれない部分や、新しく追加したいカラムなどを追加で定義する

# Channel モデルで Program モデルを使っているため、先に定義する
class Program(pydantic_model_creator(models.Program, name='Program')):
    class Genre(BaseModel):
        major:str
        middle:str
    detail: Dict[str, str]
    genre: List[Genre]

class Channel(pydantic_model_creator(models.Channel, name='Channel')):
    is_display: bool = True  # 追加カラム
    viewers: int
    program_present: Optional[Program]  # 追加カラム
    program_following: Optional[Program]  # 追加カラム

class LiveStream(BaseModel):
    # LiveStream は特殊なモデルのため、ここで全て定義する
    status: str
    detail: str
    updated_at: float
    clients_count: int

class User(pydantic_model_creator(models.User, name='User',
    exclude=('password', 'niconico_access_token', 'niconico_refresh_token'))):
    client_settings: Dict[str, Any]

# API リクエストに利用する Pydantic モデル
# リクエストボティの JSON の構造を表す
class UserCreateRequest(BaseModel):
    username: str
    password: str

class UserUpdateRequest(BaseModel):
    username: Optional[str]
    password: Optional[str]

class UserUpdateRequestForAdmin(BaseModel):
    username: Optional[str]
    password: Optional[str]
    is_admin: Optional[bool]

# API レスポンスに利用する Pydantic モデル
# モデルを List や Dict でまとめたものが中心

class Channels(BaseModel):
    GR: List[Channel]
    BS: List[Channel]
    CS: List[Channel]
    CATV: List[Channel]
    SKY: List[Channel]
    STARDIGIO: List[Channel]

class JikkyoSession(BaseModel):
    is_success: bool
    audience_token: Optional[str]
    detail: str

class LiveStreams(BaseModel):
    Restart: Dict[str, LiveStream]
    Idling: Dict[str, LiveStream]
    ONAir: Dict[str, LiveStream]
    Standby: Dict[str, LiveStream]
    Offline: Dict[str, LiveStream]

class Users(BaseModel):
    __root__: List[User]

class UserAccessToken(BaseModel):
    access_token: str
    token_type: str
