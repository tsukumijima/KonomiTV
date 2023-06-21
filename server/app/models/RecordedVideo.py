
import json
from datetime import datetime
from tortoise import fields
from tortoise import models


class RecordedVideo(models.Model):

    # データベース上のテーブル名
    class Meta:  # type: ignore
        table: str = 'recorded_videos'

    # テーブル設計は Notion を参照のこと
    id: int = fields.IntField(pk=True)  # type: ignore
    file_path: str = fields.TextField()  # type: ignore
    file_hash: str = fields.TextField()  # type: ignore
    recording_start_time: datetime | None = fields.DatetimeField(null=True)  # type: ignore
    recording_end_time: datetime | None = fields.DatetimeField(null=True)  # type: ignore
    recording_start_margin: float | None = fields.FloatField(null=True)  # type: ignore
    recording_end_margin: float | None = fields.FloatField(null=True)  # type: ignore
    duration: float = fields.FloatField()  # type: ignore
    container_format: str = fields.CharField(255)  # type: ignore
    video_codec: str = fields.TextField()  # type: ignore
    video_resolution: str = fields.TextField()  # type: ignore
    primary_audio_codec: str = fields.TextField()  # type: ignore
    primary_audio_channel: str = fields.TextField()  # type: ignore
    secondary_audio_codec: str | None = fields.TextField(null=True)  # type: ignore
    secondary_audio_channel: str | None = fields.TextField(null=True)  # type: ignore
    cm_intervals: list[tuple[float, float]] | None = \
        fields.JSONField(null=True, encoder=lambda x: json.dumps(x, ensure_ascii=False))  # type: ignore
