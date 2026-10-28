# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal, cast

from tortoise import fields
from tortoise.fields import Field as TortoiseField
from tortoise.models import Model as TortoiseModel


if TYPE_CHECKING:
    from app.models.User import User


class Capture(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'captures'

    id = fields.IntField(pk=True)
    # キャプチャの同一性は画像の内容の SHA-256 で決める (同じ内容の画像が複数の場所にあっても1枚として扱う)
    ## BinaryField は unique をサポートしないため、マイグレーションで一意索引を作成している
    file_hash = fields.BinaryField()
    file_size = fields.BigIntField()
    # 撮影日時
    captured_at = fields.DatetimeField()
    # 放送日時 (番組の開始時刻 + 再生位置。番組の情報がないキャプチャでは NULL)
    broadcast_at = cast(TortoiseField[datetime | None], fields.DatetimeField(null=True))
    image_width = fields.IntField()
    image_height = fields.IntField()
    # EXIF に格納されているメタデータの解析ステータス
    metadata_status = cast(TortoiseField[Literal['Parsed', 'NoMetadata', 'Invalid']], fields.CharField(max_length=16))
    # 番組の開始からの再生位置 (秒)
    playback_position = cast(TortoiseField[float | None], fields.FloatField(null=True))
    # 撮影した瞬間に表示されていた字幕
    caption_text = cast(TortoiseField[str | None], fields.TextField(null=True))
    # 字幕・コメントを画像に合成して撮ったかどうか
    is_caption_composited = fields.BooleanField(default=False)
    is_comment_composited = fields.BooleanField(default=False)
    # キャプチャを撮った放送回の番組
    ## 録画番組とは番組キー (network_id・service_id・event_id・開始時刻) で問い合わせのときに結び付けるので、録画番組の ID は持たない
    capture_program: fields.ForeignKeyNullableRelation[CaptureProgram] = \
        fields.ForeignKeyField('models.CaptureProgram', related_name='captures', null=True, on_delete=fields.SET_NULL)
    capture_program_id: int | None
    # キャプチャの実体ファイルへの参照
    files: fields.ReverseRelation[CaptureFile]
    # キャプチャをお気に入りに追加したユーザーへの参照
    favorites: fields.ReverseRelation[CaptureFavorite]
    # キャプチャをタグ付けしたタグへの参照
    tag_items: fields.ReverseRelation[CaptureTagItem]
    # 同じパスのファイルが別の内容に上書きされ、どの場所にも置かれていなくなった時刻 (場所があるキャプチャでは NULL)
    ## お気に入りとタグを残したまま、この時刻から1週間だけ残してから削除する
    detached_since = cast(TortoiseField[datetime | None], fields.DatetimeField(null=True))
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)


class CaptureFile(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'capture_files'

    id = fields.IntField(pk=True)
    # このファイルの内容のキャプチャ (画像として読めなかったファイルでは NULL)
    capture: fields.ForeignKeyNullableRelation[Capture] = \
        fields.ForeignKeyField('models.Capture', related_name='files', null=True, on_delete=fields.CASCADE)
    capture_id: int | None
    file_path = fields.CharField(max_length=4096, unique=True)
    # 検索に使うファイル名 (絶対パスで検索するとフォルダ名まで当たるため、別に持つ)
    file_name = fields.CharField(max_length=1024)
    file_size = fields.BigIntField()
    file_created_at = fields.DatetimeField()
    file_modified_at = fields.DatetimeField()
    # ファイルの状態
    status = cast(TortoiseField[Literal['Available', 'Missing', 'Invalid']], fields.CharField(max_length=16))
    # 最初に見つからなかった時刻 (この時刻から1週間たったら行を削除する)
    missing_since = cast(TortoiseField[datetime | None], fields.DatetimeField(null=True))
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)


class CaptureProgram(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'capture_programs'
        unique_together = (('network_id', 'service_id', 'event_id', 'start_time'),)

    id = fields.IntField(pk=True)
    # キャプチャの EXIF に書き込まれた放送回の番組情報
    ## 番組キー (network_id・service_id・event_id・開始時刻) で、録画番組と問い合わせのときに結び付ける
    network_id = fields.IntField()
    service_id = fields.IntField()
    event_id = fields.IntField()
    start_time = fields.DatetimeField()
    # 放送時間未定 (EIT[p/f] の終了時間未定) の番組で撮ったキャプチャだけで作った放送回は、終了時刻と番組長が不明なので NULL にする
    end_time = cast(TortoiseField[datetime | None], fields.DatetimeField(null=True))
    duration = cast(TortoiseField[float | None], fields.FloatField(null=True))
    title = fields.TextField()
    description = fields.TextField()
    captures: fields.ReverseRelation[Capture]
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)


class CaptureFavorite(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'capture_favorites'
        unique_together = (('user', 'capture'),)

    id = fields.IntField(pk=True)
    # お気に入りに追加したユーザー (お気に入りはアカウントごとに持つ)
    user: fields.ForeignKeyRelation[User] = \
        fields.ForeignKeyField('models.User', related_name='capture_favorites', on_delete=fields.CASCADE)
    user_id: int
    capture: fields.ForeignKeyRelation[Capture] = \
        fields.ForeignKeyField('models.Capture', related_name='favorites', on_delete=fields.CASCADE)
    capture_id: int
    created_at = fields.DatetimeField(auto_now_add=True)


class CaptureTag(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'capture_tags'
        unique_together = (('user', 'name'),)

    id = fields.IntField(pk=True)
    # タグの持ち主 (タグはアカウントごとに持ち、本人だけが編集・参照できる)
    user: fields.ForeignKeyRelation[User] = \
        fields.ForeignKeyField('models.User', related_name='capture_tags', on_delete=fields.CASCADE)
    user_id: int
    name = fields.CharField(max_length=255)
    items: fields.ReverseRelation[CaptureTagItem]
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)


class CaptureTagItem(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'capture_tag_items'
        unique_together = (('tag', 'capture'),)

    id = fields.IntField(pk=True)
    tag: fields.ForeignKeyRelation[CaptureTag] = \
        fields.ForeignKeyField('models.CaptureTag', related_name='items', on_delete=fields.CASCADE)
    tag_id: int
    capture: fields.ForeignKeyRelation[Capture] = \
        fields.ForeignKeyField('models.Capture', related_name='tag_items', on_delete=fields.CASCADE)
    capture_id: int
    created_at = fields.DatetimeField(auto_now_add=True)
