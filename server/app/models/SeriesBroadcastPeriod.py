
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

from tortoise import fields
from tortoise import models
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.Channel import Channel
    from app.models.Series import Series
    from app.models.RecordedProgram import RecordedProgram


class SeriesBroadcastPeriod(models.Model):

    # データベース上のテーブル名
    class Meta:  # type: ignore
        table: str = 'series_broadcast_periods'

    # テーブル設計は Notion を参照のこと
    id: int = fields.IntField(pk=True)  # type: ignore
    series: fields.ForeignKeyRelation[Series] = \
        fields.ForeignKeyField('models.Series', related_name='broadcast_periods', on_delete=fields.CASCADE)  # type: ignore
    series_id: int
    channel: fields.ForeignKeyRelation[Channel] = \
        fields.ForeignKeyField('models.Channel', related_name=None, on_delete=fields.CASCADE)  # type: ignore
    channel_id: str
    start_date = fields.DateField()
    end_date = fields.DateField()
    recorded_programs: fields.ReverseRelation[RecordedProgram]
