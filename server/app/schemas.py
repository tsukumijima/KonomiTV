
from enum import Enum
from pydantic import AnyHttpUrl, BaseModel, PositiveInt, validator
from tortoise.contrib.pydantic import pydantic_model_creator
from typing import Dict, List, Optional

from app import models
from app.constants import QUALITY


# 環境設定を表す Pydantic モデル
# バリデーションを兼ねる
class Config(BaseModel):
    class General(BaseModel):
        debug: bool
        mirakurun_url: AnyHttpUrl
    class LiveStream(BaseModel):
        class Encoder(Enum):
            ffmpeg = 'ffmpeg'
            QSVEncC = 'QSVEncC'
            NVEncC = 'NVEncC'
            VCEEncC = 'VCEEncC'
        preferred_encoder: Encoder
        preferred_quality: str
        max_alive_time: PositiveInt
        @validator('preferred_quality')
        def check_quality(cls, value):
            if value not in QUALITY:
                raise ValueError(f'{value} という画質は定義されていません。')
            return value
    general: General
    livestream: LiveStream

# モデルを表す Pydantic モデル
# 基本的には pydantic_model_creator() で Tortoise ORM モデルから変換したものを継承
# JSONField など変換だけでは補いきれない部分や、新しく追加したいカラムなどを追加で定義する

class Program(pydantic_model_creator(models.Programs, name='Program')):
    class Genre(BaseModel):
        major:str
        middle:str
    detail: Dict[str, str]
    genre: List[Genre]

class Channel(pydantic_model_creator(models.Channels, name='Channel')):
    is_display: bool = True  # 追加カラム
    watching: int
    program_present: Optional[Program]  # 追加カラム
    program_following: Optional[Program]  # 追加カラム

class LiveStream(BaseModel):
    # LiveStream は特殊なモデルのため、ここで全て定義する
    status: str
    detail: str
    updated_at: float
    clients_count: int

# API レスポンスに利用する Pydantic モデル
# モデルを List や Dict でまとめたものが中心

class Channels(BaseModel):
    GR: List[Channel]
    BS: List[Channel]
    CS: List[Channel]
    SKY: List[Channel]

class LiveStreams(BaseModel):
    Restart: Dict[str, LiveStream]
    Idling: Dict[str, LiveStream]
    ONAir: Dict[str, LiveStream]
    Standby: Dict[str, LiveStream]
    Offline: Dict[str, LiveStream]
