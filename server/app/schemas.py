
from pydantic import AnyHttpUrl, BaseModel, PositiveInt
from pydantic.networks import stricturl
from tortoise.contrib.pydantic import pydantic_model_creator
from typing import Dict, List, Literal, Optional

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

class Program(pydantic_model_creator(models.Programs, name='Program')):
    class Genre(BaseModel):
        major:str
        middle:str
    detail: Dict[str, str]
    genre: List[Genre]

class Channel(pydantic_model_creator(models.Channels, name='Channel')):
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

# API レスポンスに利用する Pydantic モデル
# モデルを List や Dict でまとめたものが中心

class Channels(BaseModel):
    GR: List[Channel]
    BS: List[Channel]
    CS: List[Channel]
    CATV: List[Channel]
    SKY: List[Channel]
    STARDIGIO: List[Channel]

class LiveStreams(BaseModel):
    Restart: Dict[str, LiveStream]
    Idling: Dict[str, LiveStream]
    ONAir: Dict[str, LiveStream]
    Standby: Dict[str, LiveStream]
    Offline: Dict[str, LiveStream]
