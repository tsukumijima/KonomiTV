
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

from datetime import datetime
from typing import Literal, cast

from tortoise import fields
from tortoise.fields import Field as TortoiseField
from tortoise.models import Model as TortoiseModel

from app.models.RecordedVideo import RecordedVideo


class ClipVideo(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'clip_videos'

    # テーブル設計
    id = fields.IntField(pk=True)
    recorded_video: fields.ForeignKeyRelation[RecordedVideo] = \
        fields.ForeignKeyField('models.RecordedVideo', related_name='clip_videos', on_delete=fields.CASCADE)
    recorded_video_id: int
    title = fields.TextField()  # クリップのタイトル (元の番組タイトル + 時間範囲)
    file_path = fields.TextField()  # クリップファイルのパス
    file_hash = fields.TextField()
    file_size = fields.IntField()
    start_time = fields.FloatField()  # 元動画での開始時刻 (秒)
    end_time = fields.FloatField()  # 元動画での終了時刻 (秒)
    duration = fields.FloatField()  # クリップの長さ (秒)
    container_format = cast(TortoiseField[Literal['MPEG-TS', 'MPEG-4']], fields.CharField(255))
    video_codec = cast(TortoiseField[Literal['MPEG-2', 'H.264', 'H.265']], fields.CharField(255))
    video_codec_profile = cast(TortoiseField[Literal['High', 'High 10', 'Main', 'Main 10', 'Baseline']], fields.CharField(255))
    video_scan_type = cast(TortoiseField[Literal['Interlaced', 'Progressive']], fields.CharField(255))
    video_frame_rate = fields.FloatField()
    video_resolution_width = fields.IntField()
    video_resolution_height = fields.IntField()
    primary_audio_codec = cast(TortoiseField[Literal['AAC-LC']], fields.CharField(255))
    primary_audio_channel = cast(TortoiseField[Literal['Monaural', 'Stereo', '5.1ch']], fields.CharField(255))
    primary_audio_sampling_rate = fields.IntField()
    secondary_audio_codec = cast(TortoiseField[Literal['AAC-LC'] | None], fields.CharField(255, null=True))
    secondary_audio_channel = cast(TortoiseField[Literal['Monaural', 'Stereo', '5.1ch'] | None], fields.CharField(255, null=True))
    secondary_audio_sampling_rate = cast(TortoiseField[int | None], fields.IntField(null=True))
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
