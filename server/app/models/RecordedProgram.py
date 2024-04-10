
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import json
from tortoise import fields
from tortoise.fields import Field as TortoiseField
from tortoise.models import Model as TortoiseModel
from typing import cast, TYPE_CHECKING

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

    # テーブル設計は Notion を参照のこと
    id = fields.IntField(pk=True)
    recorded_video: fields.OneToOneRelation[RecordedVideo]
    recording_start_margin = fields.FloatField(default=0.0)
    recording_end_margin = fields.FloatField(default=0.0)
    is_partially_recorded = fields.BooleanField(default=False)
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
    description = fields.TextField(default='番組情報を取得できませんでした。')
    detail = cast(TortoiseField[dict[str, str]], fields.JSONField(default={}, encoder=lambda x: json.dumps(x, ensure_ascii=False)))  # type: ignore
    start_time = fields.DatetimeField()
    end_time = fields.DatetimeField()
    duration = fields.FloatField()
    is_free = fields.BooleanField(default=True)
    genres = cast(TortoiseField[list[Genre]], fields.JSONField(default=[], encoder=lambda x: json.dumps(x, ensure_ascii=False)))  # type: ignore
    primary_audio_type = fields.TextField(default='2/0モード(ステレオ)')
    primary_audio_language = fields.TextField(default='日本語')
    secondary_audio_type = cast(TortoiseField[str | None], fields.TextField(null=True))
    secondary_audio_language = cast(TortoiseField[str | None], fields.TextField(null=True))
