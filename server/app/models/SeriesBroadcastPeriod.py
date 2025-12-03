
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields
from tortoise.models import Model as TortoiseModel


if TYPE_CHECKING:
    from app.models.Channel import Channel
    from app.models.RecordedProgram import RecordedProgram
    from app.models.Series import Series


class SeriesBroadcastPeriod(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'series_broadcast_periods'

    id = fields.IntField(pk=True)
    series: fields.ForeignKeyRelation[Series] = \
        fields.ForeignKeyField('models.Series', related_name='broadcast_periods', on_delete=fields.CASCADE)
    series_id: int
    channel: fields.ForeignKeyRelation[Channel] = \
        fields.ForeignKeyField('models.Channel', related_name=None, on_delete=fields.CASCADE)
    channel_id: str
    start_date = fields.DateField()
    end_date = fields.DateField()
    recorded_programs: fields.ReverseRelation[RecordedProgram]
