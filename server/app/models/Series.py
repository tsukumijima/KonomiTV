
import json
from tortoise import fields
from tortoise import models

from app.models import SeriesBroadcastPeriod


class Series(models.Model):

    # データベース上のテーブル名
    class Meta:  # type: ignore
        table: str = 'series'

    # テーブル設計は Notion を参照のこと
    id: int = fields.IntField(pk=True)  # type: ignore
    title: str = fields.TextField()  # type: ignore
    description: str = fields.TextField()  # type: ignore
    genres: list[dict[str, str]] = fields.JSONField(encoder=lambda x: json.dumps(x, ensure_ascii=False))  # type: ignore
    broadcast_periods: fields.ReverseRelation[SeriesBroadcastPeriod]
    updated_at = fields.DatetimeField(auto_now=True)
