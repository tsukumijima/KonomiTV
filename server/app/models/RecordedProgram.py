
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import json
from datetime import datetime
from tortoise import fields
from tortoise import models
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.Channel import Channel
    from app.models.RecordedVideo import RecordedVideo
    from app.models.Series import Series
    from app.models.SeriesBroadcastPeriod import SeriesBroadcastPeriod


class RecordedProgram(models.Model):

    # データベース上のテーブル名
    class Meta:  # type: ignore
        table: str = 'recorded_programs'

    # テーブル設計は Notion を参照のこと
    id: int = fields.IntField(pk=True)  # type: ignore
    recorded_video: fields.OneToOneRelation[RecordedVideo]
    recording_start_margin: float = fields.FloatField(default=0.0)  # type: ignore
    recording_end_margin: float = fields.FloatField(default=0.0)  # type: ignore
    is_partially_recorded: bool = fields.BooleanField(default=False)  # type: ignore
    channel: fields.ForeignKeyNullableRelation[Channel] = \
        fields.ForeignKeyField('models.Channel', related_name=None, null=True, on_delete=fields.CASCADE)
    channel_id: str | None
    network_id: int | None = fields.IntField(null=True)  # type: ignore
    service_id: int | None = fields.IntField(null=True)  # type: ignore
    event_id: int | None = fields.IntField(null=True)  # type: ignore
    series: fields.ForeignKeyNullableRelation[Series] = \
        fields.ForeignKeyField('models.Series', related_name=None, null=True, on_delete=fields.CASCADE)
    series_id: int | None
    series_broadcast_period: fields.ForeignKeyNullableRelation[SeriesBroadcastPeriod] = \
        fields.ForeignKeyField('models.SeriesBroadcastPeriod', related_name='recorded_programs', null=True, on_delete=fields.CASCADE)
    series_broadcast_period_id: int | None
    title: str = fields.TextField()  # type: ignore
    series_title: str | None = fields.TextField(null=True)  # type: ignore
    episode_number: str | None = fields.CharField(255, null=True)  # type: ignore
    subtitle: str | None = fields.TextField(null=True)  # type: ignore
    description: str = fields.TextField(default='番組情報を取得できませんでした。')  # type: ignore
    detail: dict[str, str] = fields.JSONField(default={}, encoder=lambda x: json.dumps(x, ensure_ascii=False))  # type: ignore
    start_time: datetime = fields.DatetimeField()  # type: ignore
    end_time: datetime = fields.DatetimeField()  # type: ignore
    duration: float = fields.FloatField()  # type: ignore
    is_free: bool = fields.BooleanField(default=True)  # type: ignore
    genres: list[dict[str, str]] = fields.JSONField(default=[], encoder=lambda x: json.dumps(x, ensure_ascii=False))  # type: ignore
    primary_audio_type: str = fields.TextField(default='2/0モード(ステレオ)')  # type: ignore
    primary_audio_language: str = fields.TextField(default='日本語')  # type: ignore
    secondary_audio_type: str | None = fields.TextField(null=True)  # type: ignore
    secondary_audio_language: str | None = fields.TextField(null=True)  # type: ignore
