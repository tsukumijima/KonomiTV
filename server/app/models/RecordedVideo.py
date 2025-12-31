
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import json
from datetime import datetime
from typing import Literal, cast

from tortoise import fields
from tortoise.fields import Field as TortoiseField
from tortoise.models import Model as TortoiseModel

from app.models.RecordedProgram import RecordedProgram
from app.schemas import CMSection, KeyFrame


class RecordedVideo(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'recorded_videos'

    id = fields.IntField(pk=True)
    recorded_program: fields.OneToOneRelation[RecordedProgram] = \
        fields.OneToOneField('models.RecordedProgram', related_name='recorded_video', on_delete=fields.CASCADE)
    recorded_program_id: int
    status = cast(TortoiseField[Literal['Recording', 'Recorded', 'AnalysisFailed']], fields.CharField(255))
    file_path = fields.TextField()  # ファイルパスは可変長だが、TextField には unique 制約が付けられない
    file_hash = fields.TextField()
    file_size = fields.IntField()
    file_created_at = fields.DatetimeField()
    file_modified_at = fields.DatetimeField()
    recording_start_time = cast(TortoiseField[datetime | None], fields.DatetimeField(null=True))
    recording_end_time = cast(TortoiseField[datetime | None], fields.DatetimeField(null=True))
    duration = fields.FloatField()
    container_format = cast(TortoiseField[Literal['MPEG-TS', 'MPEG-4']], fields.CharField(255))
    video_codec = cast(TortoiseField[Literal['MPEG-2', 'H.264', 'H.265']], fields.CharField(255))
    # プロファイルは他にも多くあるが、現実的に使われそうなものだけを列挙
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
    key_frames = cast(TortoiseField[list[KeyFrame]],
        fields.JSONField(default=[], encoder=lambda x: json.dumps(x, ensure_ascii=False)))  # type: ignore
    cm_sections = cast(TortoiseField[list[CMSection] | None],
        # None は未解析状態を表す ([] は解析したが CM 区間がなかった/検出に失敗したことを表す)
        fields.JSONField(default=None, encoder=lambda x: json.dumps(x, ensure_ascii=False), null=True))  # type: ignore
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    @property
    def has_key_frames(self) -> bool:
        return len(self.key_frames) > 0
