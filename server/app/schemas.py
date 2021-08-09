
from pydantic import BaseModel
from typing import Dict, List

from app.models import ChannelsPydantic


class ChannelsAPIResponse(BaseModel):
    GR: List[ChannelsPydantic]
    BS: List[ChannelsPydantic]
    CS: List[ChannelsPydantic]
    SKY: List[ChannelsPydantic]

class LiveStreamAPIResponse(BaseModel):
    status: str
    detail: str
    updated_at: float
    client_count: int

class LiveStreamListAPIResponse(BaseModel):
    Idling: Dict[str, LiveStreamAPIResponse]
    ONAir: Dict[str, LiveStreamAPIResponse]
    Standby: Dict[str, LiveStreamAPIResponse]
    Offline: Dict[str, LiveStreamAPIResponse]
