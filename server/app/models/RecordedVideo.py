
import json
from datetime import datetime
from tortoise import fields
from tortoise import models
from typing import Literal


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
    duration: float = fields.FloatField()  # type: ignore
    container_format: Literal['MPEG-TS'] = fields.CharField(255)  # type: ignore
    video_codec: Literal['MPEG-2', 'H.264', 'H.265'] = fields.CharField(255)  # type: ignore
    video_resolution_width: int = fields.IntField()  # type: ignore
    video_resolution_height: int = fields.IntField()  # type: ignore
    primary_audio_codec: Literal['AAC-LC', 'HE-AAC', 'MP2'] = fields.CharField(255)  # type: ignore
    primary_audio_channel: Literal['Monaural', 'Stereo', '5.1ch'] = fields.CharField(255)  # type: ignore
    primary_audio_sampling_rate: int = fields.IntField()  # type: ignore
    secondary_audio_codec: Literal['AAC-LC', 'HE-AAC', 'MP2'] | None = fields.CharField(255, null=True)  # type: ignore
    secondary_audio_channel: Literal['Monaural', 'Stereo', '5.1ch'] | None = fields.CharField(255, null=True)  # type: ignore
    secondary_audio_sampling_rate: int | None = fields.IntField(null=True)  # type: ignore
    cm_intervals: list[tuple[float, float]] = \
        fields.JSONField(default=[], encoder=lambda x: json.dumps(x, ensure_ascii=False))  # type: ignore
