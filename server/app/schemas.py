
from pydantic import BaseModel
from tortoise.contrib.pydantic import pydantic_model_creator
from typing import Dict, List, Optional

from app import models


# モデルを表す Pydantic モデル
# 基本的には pydantic_model_creator() で Tortoise ORM モデルから変換したものを継承
# JSONField など変換だけでは補いきれない部分や、新しく追加したいカラムなどを追加で定義する

class Program(pydantic_model_creator(models.Programs, name='Programs')):
    class Genre(BaseModel):
        major:str
        middle:str
    detail: Dict[str, str]
    genre: List[Genre]

class Channel(pydantic_model_creator(models.Channels, name='Channels')):
    program_current: Optional[Program]  # 追加カラム
    program_next: Optional[Program]  # 追加カラム

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
    Idling: Dict[str, LiveStream]
    ONAir: Dict[str, LiveStream]
    Standby: Dict[str, LiveStream]
    Offline: Dict[str, LiveStream]
