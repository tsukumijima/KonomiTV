
from tortoise import fields
from tortoise import models

from app.models import Channel
from app.models import Series
from app.models import RecordedProgram


class SeriesBroadcastPeriod(models.Model):

    # データベース上のテーブル名
    class Meta:  # type: ignore
        table: str = 'series_broadcast_periods'

    # テーブル設計は Notion を参照のこと
    id: int = fields.IntField(pk=True)  # type: ignore
    series: fields.ForeignKeyRelation[Series] = fields.ForeignKeyField('models.Series', related_name='broadcast_periods')
    series_id: int
    channel: fields.ForeignKeyRelation[Channel] = fields.ForeignKeyField('models.Channel', related_name=None)
    channel_id: int
    start_date = fields.DateField()
    end_date = fields.DateField()
    recorded_programs: fields.ReverseRelation[RecordedProgram]
