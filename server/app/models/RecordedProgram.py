
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

from tortoise import fields
from tortoise.fields import Field as TortoiseField
from tortoise.models import Model as TortoiseModel

from app.schemas import Genre


if TYPE_CHECKING:
    from app.models.Channel import Channel
    from app.models.RecordedVideo import RecordedVideo
    from app.models.Series import Series
    from app.models.SeriesBroadcastPeriod import SeriesBroadcastPeriod


class RecordedProgram(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'recorded_programs'

    id = fields.IntField(pk=True)
    recorded_video: fields.OneToOneRelation[RecordedVideo]
    recording_start_margin = fields.FloatField()
    recording_end_margin = fields.FloatField()
    is_partially_recorded = fields.BooleanField()
    channel: fields.ForeignKeyNullableRelation[Channel] = \
        fields.ForeignKeyField('models.Channel', related_name=None, null=True, on_delete=fields.CASCADE)
    channel_id: str | None
    network_id = cast(TortoiseField[int | None], fields.IntField(null=True))
    service_id = cast(TortoiseField[int | None], fields.IntField(null=True))
    event_id = cast(TortoiseField[int | None], fields.IntField(null=True))
    series: fields.ForeignKeyNullableRelation[Series] = \
        fields.ForeignKeyField('models.Series', related_name=None, null=True, on_delete=fields.CASCADE)
    series_id: int | None
    series_broadcast_period: fields.ForeignKeyNullableRelation[SeriesBroadcastPeriod] = \
        fields.ForeignKeyField('models.SeriesBroadcastPeriod', related_name='recorded_programs', null=True, on_delete=fields.CASCADE)
    series_broadcast_period_id: int | None
    title = fields.TextField()
    series_title = cast(TortoiseField[str | None], fields.TextField(null=True))
    episode_number = cast(TortoiseField[str | None], fields.CharField(255, null=True))
    subtitle = cast(TortoiseField[str | None], fields.TextField(null=True))
    description = fields.TextField()
    detail = cast(TortoiseField[dict[str, str]], fields.JSONField(default={}, encoder=lambda x: json.dumps(x, ensure_ascii=False)))  # type: ignore
    start_time = fields.DatetimeField()
    end_time = fields.DatetimeField()
    duration = fields.FloatField()
    is_free = fields.BooleanField()
    genres = cast(TortoiseField[list[Genre]], fields.JSONField(default=[], encoder=lambda x: json.dumps(x, ensure_ascii=False)))  # type: ignore
    primary_audio_type = fields.TextField()
    primary_audio_language = fields.TextField()
    secondary_audio_type = cast(TortoiseField[str | None], fields.TextField(null=True))
    secondary_audio_language = cast(TortoiseField[str | None], fields.TextField(null=True))
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
