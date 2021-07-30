
from pydantic import BaseModel
from typing import List

from app.models import ChannelsPydantic


class ChannelsAPIResponse(BaseModel):
    GR: List[ChannelsPydantic]
    BS: List[ChannelsPydantic]
    CS: List[ChannelsPydantic]
    SKY: List[ChannelsPydantic]
