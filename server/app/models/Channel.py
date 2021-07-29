
from typing import Tuple
from tortoise import fields
from tortoise import models


class Channel(models.Model):

    # 定義は Notion を参照のこと
    id = fields.TextField(pk=True)
    service_id = fields.IntField()
    network_id = fields.IntField()
    channel_id = fields.TextField()
    channel_number = fields.TextField()
    channel_name = fields.TextField()
    channel_type = fields.TextField()
    channel_force = fields.IntField(null=True)
    is_subchannel = fields.BooleanField()
