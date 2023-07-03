
import json
from datetime import datetime
from tortoise import fields
from tortoise import models

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
    recorded_video: fields.ForeignKeyRelation[RecordedVideo] = \
        fields.ForeignKeyField('models.RecordedVideo', related_name=None)
    recorded_video_id: int
    channel: fields.ForeignKeyRelation[Channel] | None = fields.ForeignKeyField('models.Channel', related_name=None, null=True)
    channel_id: str | None
    network_id: int | None = fields.IntField(null=True)  # type: ignore
    service_id: int | None = fields.IntField(null=True)  # type: ignore
    event_id: int | None = fields.IntField(null=True)  # type: ignore
    series: fields.ForeignKeyRelation[Series] | None = \
        fields.ForeignKeyField('models.Series', related_name=None, null=True)
    series_id: int | None
    series_broadcast_period: fields.ForeignKeyRelation[SeriesBroadcastPeriod] | None = \
        fields.ForeignKeyField('models.SeriesBroadcastPeriod', related_name='recorded_programs', null=True)
    series_broadcast_period_id: int | None
    title: str = fields.TextField()  # type: ignore
    episode_number: str | None = fields.CharField(255, null=True)  # type: ignore
    subtitle: str | None = fields.TextField(null=True)  # type: ignore
    description: str = fields.TextField()  # type: ignore
    detail: dict[str, str] = fields.JSONField(default={}, encoder=lambda x: json.dumps(x, ensure_ascii=False))  # type: ignore
    start_time: datetime = fields.DatetimeField()  # type: ignore
    end_time: datetime = fields.DatetimeField()  # type: ignore
    duration: float = fields.FloatField()  # type: ignore
    is_free: bool = fields.BooleanField()  # type: ignore
    genres: list[dict[str, str]] = fields.JSONField(default=[], encoder=lambda x: json.dumps(x, ensure_ascii=False))  # type: ignore
    primary_audio_type: str = fields.TextField(default='2/0モード(ステレオ)')  # type: ignore
    primary_audio_language: str = fields.TextField(default='日本語')  # type: ignore
    secondary_audio_type: str | None = fields.TextField(null=True)  # type: ignore
    secondary_audio_language: str | None = fields.TextField(null=True)  # type: ignore
