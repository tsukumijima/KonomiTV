from __future__ import annotations

import asyncio
import hashlib
import io
import os
import re
import struct
from array import array
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, ClassVar, Literal, Self, TypedDict, cast
from weakref import WeakValueDictionary

import anyio
import psutil
from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError
from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from tortoise import connections, transactions
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.exceptions import IntegrityError, OperationalError
from tortoise.expressions import Q
from watchfiles import Change, awatch

from app import logging, schemas
from app.config import Config
from app.constants import JST
from app.models.Capture import Capture, CaptureFile, CaptureProgram
from app.utils.DriveIOLimiter import DriveIOLimiter


class CaptureExif(BaseModel):
    """
    キャプチャの EXIF の XPComment に KonomiTV が書き込む番組情報 (新旧の形式で共通)
    """

    captured_at: Annotated[datetime, Field(validation_alias=AliasChoices('captured_at', 'capture_time'))]
    captured_playback_position: Annotated[float, Field(allow_inf_nan=False)]
    # ARIB の番組の ID はどれも16ビットなので、範囲外の値は壊れたメタデータとして扱う (DB の整数に収まらない値も弾く)
    ## 番組情報のない録画などで撮ったキャプチャは、不明な ID を -1 にして書き込むので、-1 も受け付ける (番組とは結び付けない)
    network_id: Annotated[int, Field(ge=-1, le=0xFFFF)]
    service_id: Annotated[int, Field(ge=-1, le=0xFFFF)]
    event_id: Annotated[int, Field(ge=-1, le=0xFFFF)]
    start_time: datetime
    # 放送時間未定 (EIT[p/f] の終了時間未定) の番組で撮ったキャプチャは、番組の長さを null にして書き込むので、終了時刻と長さは None になる
    end_time: datetime | None
    duration: Annotated[float, Field(allow_inf_nan=False)] | None
    title: str
    description: str
    caption_text: str | None = None
    is_caption_composited: bool = False
    is_comment_composited: bool = False

    @field_validator('captured_at', 'start_time', 'end_time')
    @classmethod
    def normalizeDateTime(cls, value: datetime | None) -> datetime | None:
        """
        タイムゾーンを省略した旧形式の日時も JST に揃える

        Args:
            value (datetime | None): EXIF の日時

        Returns:
            datetime | None: JST のタイムゾーン付き日時
        """

        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=JST)
        return value.astimezone(JST)

    @model_validator(mode='before')
    @classmethod
    def fillPlaybackPositionOfLiveCapture(cls, data: Any) -> Any:
        """
        2022年10月までの KonomiTV が書き込んだ、再生位置のない番組情報に再生位置を補う
        当時の KonomiTV はライブ視聴のキャプチャだけを撮っていたので、現在のライブ視聴のキャプチャと同じく、
        番組の開始時刻から撮影日時までの秒数を再生位置にする

        Args:
            data (Any): XPComment の JSON を読み込んだ値

        Returns:
            Any: 再生位置を補った値
        """

        # 撮影日時を capture_time のキーで書き込んだ形式で、再生位置がないときだけ補う
        ## 日時が読めないときはそのまま返し、フィールドの検証で壊れたメタデータとして扱う
        if isinstance(data, dict) and 'capture_time' in data and 'captured_playback_position' not in data:
            try:
                captured_at = datetime.fromisoformat(data['capture_time'])
                start_time = datetime.fromisoformat(data['start_time'])
                data = {**data, 'captured_playback_position': (captured_at - start_time).total_seconds()}
            except (KeyError, TypeError, ValueError):
                pass
        return data

    @model_validator(mode='after')
    def clearEndTimeOfUndecidedProgram(self) -> Self:
        """
        放送時間未定の番組で撮ったキャプチャの終了時刻を None にする
        KonomiTV のクライアントは、放送時間未定の番組の終了時刻に開始時刻と同じ値を入れて書き込むため、終了時刻としては使えない

        Returns:
            Self: 終了時刻を整えた番組情報
        """

        if self.duration is None:
            self.end_time = None
        return self


@dataclass(slots=True)
class CaptureImageInfo:
    """
    ファイルの読み込みと解析を終えた画像の情報 (DB のトランザクションへ渡す)
    """

    file_hash: bytes
    image_width: int
    image_height: int
    captured_at: datetime
    metadata_status: Literal['Parsed', 'NoMetadata', 'Invalid']
    metadata: CaptureExif | None


class CaptureFileSnapshot(TypedDict):
    """
    一括スキャンで照合に使う、キャプチャの場所の情報
    """

    id: int
    file_path: str
    file_size: int
    file_created_at: datetime
    file_modified_at: datetime
    status: Literal['Available', 'Missing', 'Invalid']
    missing_since: datetime | None


@dataclass(slots=True)
class CaptureFolderListing:
    """
    一括スキャンでフォルダを1つ列挙した結果
    KonomiTV からのアップロードは保存先の直下に置くため、1つのフォルダに十数万〜百万枚の画像が並ぶ
    画像ごとにパスと日時のオブジェクトを作ると百万枚で約 300MB になるため、画像はファイル名と、サイズ・作成日時・更新日時の数値の配列で保持する
    画像は名前の昇順に並べてあり、同じ位置の要素が同じ画像を表す
    """

    # 子フォルダのパスと更新日時
    directories: list[tuple[str, float]]
    # 画像のファイル名 (パスは、走査しているフォルダのパスと連結して作る)
    file_names: list[str]
    file_sizes: array[int]
    # 画像の stat の st_ctime・st_mtime の値 (塊ごとに datetime に変換する)
    file_created_timestamps: array[float]
    file_modified_timestamps: array[float]


@dataclass(slots=True)
class CaptureRootScanResult:
    """
    保存先ごとの走査の結果 (全保存先の移動の照合が終わってから、消えたファイルを確定するために使う)
    登録済みの場所は百万件を超えることがあるため、行の内容は保持せず、場所の ID で引ける配列に走査を始めた時点の状態と見つかったかどうかだけを記録する
    """

    # 走査した保存先 (None は、設定から外した保存先にあった場所のように、設定されたどの保存先にも属さない場所をまとめて確認した結果)
    root: str | None
    # この結果が扱う場所を DB から絞り込む条件
    file_path_filters: list[Q]
    started_at: datetime
    # 走査を始めた時点で、この保存先に登録済みだった場所の最大の ID (これより後に登録された場所は、消えたファイルの確定の対象にしない)
    max_file_id: int
    # 場所の ID ごとの、走査を始めた時点のサイズ・作成日時・更新日時のハッシュ値 (走査のあとで行が変わったかどうかの判定に使う)
    file_state_hashes: array[int]
    # 走査で見つかった場所の ID に 1 を記録する
    seen_file_ids: bytearray
    original_count: int  # 走査を始めた時点で Missing でなかった場所の数
    found_count: int  # 走査で見つかった画像の数
    is_complete: bool


def NormalizeCapturePath(path: str | Path | anyio.Path) -> str:
    """
    すべての取り込みの経路で、同じ形の絶対パスを作る
    Docker のパスは、設定の読み込み時に付けた /host-rootfs をそのまま残し、実際のアクセスにも同じ値を使う
    大文字と小文字は、画面にそのまま表示できるよう実際の表記のまま残す (同じファイルかどうかは CapturePathKey() で判定する)

    Args:
        path (str | Path | anyio.Path): ファイルまたはフォルダのパス

    Returns:
        str: 区切りを揃えた絶対パス
    """

    return os.path.abspath(os.path.normpath(str(path)))


def CapturePathKey(path: str) -> str:
    """
    同じファイルを指すパスかどうかを判定するためのキーを作る
    Windows のファイルシステムは大文字と小文字を区別しないため、表記だけが異なるパスを同じキーにする (Linux ではパスをそのまま返す)

    Args:
        path (str): NormalizeCapturePath() で正規化したパス

    Returns:
        str: パスの同一性の判定に使うキー
    """

    return os.path.normcase(path)


@asynccontextmanager
async def InWriteTransaction() -> AsyncGenerator[BaseDBAsyncClient]:
    """
    最初の SQL 文で書き込みのロックを取るトランザクションを開始する
    番組情報の更新は別のプロセスから別の DB 接続で書き込むため、読み取りから始めたトランザクションが書き込みを始めると、
    ロック待ちのタイムアウト (busy_timeout) を待たずに即座に SQLITE_BUSY のエラー (database is locked) になる
    行を更新しない UPDATE 文を最初に実行して書き込みのロックを取り、ほかの接続の書き込みが完了するまで待ってから読み取りを始める

    Yields:
        BaseDBAsyncClient: トランザクションの DB 接続
    """

    async with transactions.in_transaction() as connection:
        await connection.execute_query('UPDATE capture_files SET id = id WHERE 0')
        yield connection


def ReadCaptureImage(data: bytes, filename: str, modified_at: datetime) -> CaptureImageInfo:
    """
    画像の検証・ハッシュの計算・EXIF の解析を行う (DB のロックを取る前に、ワーカースレッドで実行する)

    Args:
        data (bytes): 画像全体
        filename (str): ファイル名
        modified_at (datetime): ファイルの更新日時

    Returns:
        CaptureImageInfo: 撮影日時と画像の情報
    """

    # JPEG か PNG の画像として最後まで読めるかを検査する
    with Image.open(io.BytesIO(data)) as image:
        if image.format not in ('JPEG', 'PNG'):
            raise UnidentifiedImageError('Unsupported image format')
        width, height = image.size
        # JPEG の verify() は圧縮されたデータを展開せず、途中で切れた画像も通すため、実際に展開して検査する
        ## 1/8 の大きさで展開しても圧縮されたデータは最後まで読むので、途中で切れていれば OSError になる
        ## 縦か横が 8px 未満の画像では、draft() に 0 を渡すと Pillow の内部で 0 除算になるため、1px 以上にする
        if image.format == 'JPEG':
            image.draft('RGB', (max(1, width // 8), max(1, height // 8)))
            image.load()
        # PNG の verify() はチャンクの CRC まで検査する (PNG の getexif() は内部で読み込みを進めるため、先に verify() を済ませる)
        else:
            image.verify()

    # EXIF から、KonomiTV が書き込んだ番組情報 (XPComment) と撮影日時 (DateTimeOriginal) を取り出す
    ## EXIF が途中で切れていると、Pillow は struct.error を送出するので、画像は閲覧できるようにしたまま、壊れたメタデータとして扱う
    raw_comment = None
    original_time = None
    is_exif_broken = False
    with Image.open(io.BytesIO(data)) as image:
        try:
            exif = image.getexif()
            raw_comment = exif.get(40092)
            if 34665 in exif:
                original_time = exif.get_ifd(34665).get(36867)
            else:
                original_time = exif.get(36867)
        except struct.error:
            is_exif_broken = True

    # XPComment だけが壊れている場合も、画像は閲覧できるようにする
    metadata = None
    metadata_status = 'NoMetadata'
    if is_exif_broken is True:
        metadata_status = 'Invalid'
    if raw_comment is not None:
        try:
            # XPComment は BYTE 型なので、バイト列か値の並びのときだけ読む
            ## 整数の値を bytes() に渡すと、その数のバイトを確保してしまう
            if not isinstance(raw_comment, (bytes, tuple)):
                raise TypeError(f'Unexpected XPComment type: {type(raw_comment).__name__}')
            comment = bytes(raw_comment).decode('utf-16-le').rstrip('\x00')
            metadata = CaptureExif.model_validate_json(comment)
            # 有限の数値でも日時として表せない再生位置は、壊れたメタデータとして扱う
            _ = metadata.start_time + timedelta(seconds=metadata.captured_playback_position)
            metadata_status = 'Parsed'
        except (ValueError, TypeError, ValidationError, OverflowError):
            metadata = None
            metadata_status = 'Invalid'

    # 撮影日時は、番組情報の撮影日時 → EXIF の DateTimeOriginal → ファイルの更新日時の順に優先する
    captured_at = modified_at.astimezone(JST)
    if metadata is not None:
        captured_at = metadata.captured_at
    else:
        # コピーで更新日時が変わったときは、KonomiTV のファイル名に入っている時刻を優先する
        filename_match = re.fullmatch(r'Capture_(\d{8}-\d{6})(?:[-_].*)?\.(?:jpe?g|png)', filename, re.IGNORECASE)
        if filename_match is not None:
            try:
                filename_time = datetime.strptime(filename_match[1], '%Y%m%d-%H%M%S').replace(tzinfo=JST)
                difference_seconds = abs((filename_time - captured_at).total_seconds())
                # 時刻を12時間表記で名前に入れるソフトで撮ったキャプチャは、午後の時刻が午前の時刻として名前に入り、
                # 更新日時とちょうど12時間ずれるので、コピーではなく名前の表記の違いとみなして、更新日時を使う
                is_twelve_hour_notation = abs(difference_seconds - 12 * 60 * 60) < 600
                if difference_seconds >= 600 and is_twelve_hour_notation is False:
                    captured_at = filename_time
            except ValueError:
                pass
        if isinstance(original_time, str):
            try:
                captured_at = datetime.strptime(original_time, '%Y:%m:%d %H:%M:%S').replace(tzinfo=JST)
            except ValueError:
                pass

    return CaptureImageInfo(
        file_hash = hashlib.sha256(data).digest(),
        image_width = width,
        image_height = height,
        captured_at = captured_at,
        metadata_status = metadata_status,
        metadata = metadata,
    )


class CaptureScanTask:
    """
    キャプチャの保存先フォルダの一括スキャンと監視、キャプチャの登録と実体ファイルの削除を担うクラス
    """

    # ネットワークドライブで同時に読み込むキャプチャの数 (ローカルのドライブは常に1つずつ読み込む)
    NETWORK_DRIVE_CONCURRENCY: ClassVar[int] = 4

    # 一括スキャンで1度に一覧から取り出して処理するファイルの数
    SCAN_CHUNK_SIZE: ClassVar[int] = 2000

    # 一括スキャンで、登録済みの場所を DB から1度に取得する行数
    SNAPSHOT_PAGE_SIZE: ClassVar[int] = 2000

    # キャプチャとして扱う画像の拡張子
    CAPTURE_EXTENSIONS: ClassVar[tuple[str, ...]] = ('.jpg', '.jpeg', '.png')

    # 保存先の中にあっても走査と監視の対象にしないフォルダの名前 (小文字で比べる)
    ## ドライブや共有フォルダのルートを保存先にすると、OS や NAS のごみ箱・スナップショット・サムネイルのフォルダが中に入る
    ## ごみ箱へ移したキャプチャを移動として付け替えたり、NAS が作る縮小画像をキャプチャとして登録したりしないよう、中身ごと外す
    ## Linux のファイルマネージャーのごみ箱 (.Trash-1000 など) は、名前が .trash で始まるかで判定する
    EXCLUDED_FOLDER_NAMES: ClassVar[frozenset[str]] = frozenset({
        '$recycle.bin',  # Windows のごみ箱
        'system volume information',  # Windows のシステムの領域
        '#recycle',  # Synology のごみ箱
        '#snapshot',  # Synology のスナップショット
        '@eadir',  # Synology のサムネイル
        '@recycle',  # QNAP のごみ箱
        '@recently-snapshot',  # QNAP のスナップショット
        '.@__thumb',  # QNAP のサムネイル
    })

    # シングルトンインスタンス
    _instance: ClassVar[CaptureScanTask | None] = None


    def __new__(cls) -> CaptureScanTask:
        """
        シングルトンインスタンスを作成または取得する
        パスのロックと進捗を、登録・画像の配信・削除・一括スキャンで共有するため、インスタンスは1つだけにする

        Returns:
            CaptureScanTask: シングルトンインスタンス
        """

        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance


    def __init__(self) -> None:
        """
        パスのロック・一括スキャンの進捗・日付ごとの件数のキャッシュを初期化する
        """

        # 初期化済みの場合は何もしない
        if hasattr(self, 'batch_scan_status'):
            return

        # パスごとのロック
        ## 登録 (registerFile)・画像の配信 (CaptureImageAPI)・削除 (deleteCapture)・移動の照合で共有する
        ## 使われなくなったロックは WeakValueDictionary から自然に消える
        self.path_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()

        # runBatchScan() を同時に1つだけ実行するためのロック
        ## 監視 (watchFolders) は、このロックが空いているときだけ一括スキャンを始める
        self.scan_lock = asyncio.Lock()

        # 一括スキャンの進捗 (実行中かどうかと、処理したキャプチャの件数)
        ## 起動時の自動スキャンと手動スキャンの両方で更新し、CaptureScanStatusAPI が参照する
        self.batch_scan_status = schemas.MaintenanceTaskStatus()

        # start() で作り、stop() で止める、起動時のスキャンと監視の親タスク
        self.task: asyncio.Task[None] | None = None

        # 絞り込みなしの日付ごとの件数のキャッシュ (CaptureSectionsAPI が参照する)
        ## 集計の途中で DB が変わった場合に古い集計を書き戻さないよう、invalidateSections() と addCaptureToSections() のたびに世代番号を進める
        self.sections_generation = 0
        self.sections_cache: dict[tuple[str, int], schemas.CaptureSections] = {}


    def invalidateSections(self) -> None:
        """
        DB の変更をコミットした直後に呼び、日付ごとの件数のキャッシュを捨てる
        """

        self.sections_generation += 1
        self.sections_cache.clear()


    def addCaptureToSections(self, capture: Capture) -> None:
        """
        新しく登録したキャプチャの登録をコミットした直後に呼び、日付ごとの件数のキャッシュで、そのキャプチャの日付の件数を1つ増やす
        百万枚規模では集計し直すのに数秒かかり、その間ほかの API のクエリも待たされるため、キャプチャが増えただけのときはキャッシュを捨てない

        Args:
            capture (Capture): 新しく登録したキャプチャ
        """

        # 集計の途中だった CaptureSectionsAPI の結果は、このキャプチャを含むかどうか分からないので、キャッシュに書き戻させない
        self.sections_generation += 1

        for (axis, day_start_hour), cached in list(self.sections_cache.items()):

            # CaptureSectionsAPI の集計と同じく、日本時間の日時を日付の境目の時刻の分だけずらした日付で数える
            ## 放送日時の分からないキャプチャは、放送日時の軸の件数には含めない
            if axis == 'CapturedAt':
                value = capture.captured_at
            else:
                value = capture.broadcast_at
            if value is None:
                continue
            date = (value.astimezone(JST) - timedelta(hours=day_start_hour)).date().isoformat()

            # その日の件数を1つ増やす (その日のキャプチャがまだなければ、新しい日付を新しい順の位置に追加する)
            sections: list[schemas.CaptureSection] = []
            is_counted = False
            for section in cached.sections:
                if section.date == date:
                    sections.append(schemas.CaptureSection(date=date, count=section.count + 1))
                    is_counted = True
                else:
                    sections.append(section)
            if is_counted is False:
                sections.append(schemas.CaptureSection(date=date, count=1))
                sections.sort(key=lambda section: section.date, reverse=True)
            self.sections_cache[(axis, day_start_hour)] = schemas.CaptureSections(sections=sections, total=cached.total + 1)


    def getPathLock(self, path: str) -> asyncio.Lock:
        """
        パスごとのロックを取得する

        Args:
            path (str): 正規化した絶対パス

        Returns:
            asyncio.Lock: そのパスを扱うすべての処理で共通のロック
        """

        # Windows で大文字と小文字だけが異なるパスも、同じファイルなので同じロックにする
        key = CapturePathKey(path)
        lock = self.path_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self.path_locks[key] = lock
        return lock


    async def start(self) -> None:
        """
        起動時の一括スキャンと、保存先フォルダの監視を並行して始める
        """

        if self.task is None:
            self.task = asyncio.create_task(self.run())


    async def stop(self) -> None:
        """
        起動時の一括スキャンと監視を止め、終わるまで待つ
        """

        if self.task is not None:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        self.task = None


    async def run(self) -> None:
        """
        起動時の一括スキャンと、保存先フォルダの監視を同時に実行する
        """

        # 実装側の誤りで止まったときは、監視も一緒に止まったことが分かるよう、例外の内容をログに残してから送出する
        ## 例外はこのタスクの中に残るだけで、ほかにはどこにも表示されないため
        try:
            async with asyncio.TaskGroup() as group:
                group.create_task(self.runBatchScan())
                group.create_task(self.watchFolders())
        except* Exception as ex_group:
            for ex in ex_group.exceptions:
                logging.error('Capture scan task stopped unexpectedly:', exc_info=ex)
            raise


    async def registerFile(self, path: str, *, data: bytes | None = None, force: bool = False) -> Capture | None:
        """
        キャプチャを1件登録する
        アップロード・監視・一括スキャンのすべてがこのメソッドを通る (パスのロックを取ってから呼ぶ)

        Args:
            path (str): 正規化したファイルパス
            data (bytes | None): アップロードされた内容 (省略時はファイルから読む)
            force (bool): サイズと作成日時・更新日時が同じでも読み直すかどうか

        Returns:
            Capture | None: 登録したキャプチャ (画像として読めない場合は None)
        """

        file = anyio.Path(path)
        stat_before = await file.stat()
        created_at = datetime.fromtimestamp(stat_before.st_ctime, JST)
        modified_at = datetime.fromtimestamp(stat_before.st_mtime, JST)
        existing_file = await CaptureFile.get_or_none(file_path=path)

        # サイズと作成日時・更新日時が登録済みの値と同じなら、中身は読まずに登録済みのキャプチャを返す
        is_unchanged = (
            existing_file is not None and
            existing_file.file_size == stat_before.st_size and
            existing_file.file_created_at == created_at and
            existing_file.file_modified_at == modified_at
        )
        if force is False and existing_file is not None and is_unchanged is True:

            # 見つからなくなっていたファイルが同じ場所に戻ってきた場合は、利用できる状態に戻す
            if existing_file.status == 'Missing':
                async with transactions.in_transaction():
                    if existing_file.capture_id is not None:
                        restored_status = 'Available'
                    else:
                        restored_status = 'Invalid'
                    await CaptureFile.filter(id=existing_file.id).update(
                        status = restored_status,
                        missing_since = None,
                    )
                self.invalidateSections()

            if existing_file.capture_id is None:
                return None
            return await Capture.get_or_none(id=existing_file.capture_id)

        # ファイルを読み込んで、画像の検証・ハッシュの計算・EXIF の解析を行う
        if data is None:
            data = await file.read_bytes()
        try:
            info = await asyncio.to_thread(ReadCaptureImage, data, file.name, modified_at)
        except (UnidentifiedImageError, SyntaxError, ValueError, Image.DecompressionBombError, OSError) as ex:
            # 通信や権限のエラーは上の read_bytes() がそのまま送出するので、ここで受け止めるのは画像として読めないものだけ
            logging.warning(f'Invalid capture image: {path}', exc_info=ex)
            info = None

        # 読み込んでいる間にファイルが書き換わっていたら、書きかけのファイルなので登録しない
        stat_after = await file.stat()
        if (stat_before.st_size, stat_before.st_mtime_ns) != (stat_after.st_size, stat_after.st_mtime_ns):
            raise OSError('Capture changed while being read')

        # ファイルの読み込みと画像の解析を終えてから、SQLite の接続のロックを取る
        async with InWriteTransaction():
            capture = None
            # まだどこにもない内容のキャプチャを、新しく登録したかどうか
            is_capture_created = False
            if info is not None:
                capture = await Capture.get_or_none(file_hash=info.file_hash)
                if capture is None:
                    # 番組情報があれば、放送回を取得するか作る
                    ## ネットワーク ID などが負の値の番組情報は、録画番組と結び付けられないので放送回にしない
                    metadata = info.metadata
                    program: CaptureProgram | None = None
                    if metadata is not None and min(metadata.network_id, metadata.service_id, metadata.event_id) >= 0:
                        program, _ = await CaptureProgram.get_or_create(
                            network_id = metadata.network_id,
                            service_id = metadata.service_id,
                            event_id = metadata.event_id,
                            start_time = metadata.start_time,
                            defaults = {
                                'end_time': metadata.end_time,
                                'duration': metadata.duration,
                                'title': metadata.title,
                                'description': metadata.description,
                            },
                        )
                        # 放送時間未定のときに撮ったキャプチャで作った放送回は、長さが決まってから撮ったキャプチャが来たら、終了時刻と長さを埋める
                        if program.duration is None and metadata.duration is not None:
                            program.end_time = metadata.end_time
                            program.duration = metadata.duration
                            await program.save(update_fields=['end_time', 'duration', 'updated_at'])

                    # 番組情報から取り出す値 (番組情報がないキャプチャでは空にする)
                    capture_program_id: int | None = None
                    playback_position: float | None = None
                    caption_text: str | None = None
                    is_caption_composited = False
                    is_comment_composited = False
                    if metadata is not None:
                        playback_position = metadata.captured_playback_position
                        caption_text = metadata.caption_text
                        is_caption_composited = metadata.is_caption_composited
                        is_comment_composited = metadata.is_comment_composited

                    # 放送日時は、番組の開始時刻に再生位置を足して求める
                    broadcast_at: datetime | None = None
                    if program is not None and playback_position is not None:
                        capture_program_id = program.id
                        broadcast_at = program.start_time + timedelta(seconds=playback_position)

                    # 同じハッシュのキャプチャを同時に登録しようとしても1件になるよう、get_or_create で登録する
                    capture, is_capture_created = await Capture.get_or_create(
                        file_hash = info.file_hash,
                        defaults = {
                            'image_width': info.image_width,
                            'image_height': info.image_height,
                            'file_size': len(data),
                            'captured_at': info.captured_at,
                            'broadcast_at': broadcast_at,
                            'capture_program_id': capture_program_id,
                            'playback_position': playback_position,
                            'caption_text': caption_text,
                            'is_caption_composited': is_caption_composited,
                            'is_comment_composited': is_comment_composited,
                            'metadata_status': info.metadata_status,
                        },
                    )

                # どの場所にも置かれていなかったキャプチャが、また置かれた場合は、削除の期限を外す
                if capture.detached_since is not None:
                    await Capture.filter(id=capture.id).update(detached_since=None)

            # このパスの場所を、新しい内容のキャプチャに付け替える (画像として読めなかったファイルは Invalid にする)
            capture_id: int | None = None
            file_status = 'Invalid'
            if capture is not None:
                capture_id = capture.id
                file_status = 'Available'
            await CaptureFile.update_or_create(
                file_path = path,
                defaults = {
                    'capture_id': capture_id,
                    'file_name': file.name,
                    'file_size': stat_before.st_size,
                    'file_created_at': created_at,
                    'file_modified_at': modified_at,
                    'status': file_status,
                    'missing_since': None,
                },
            )

            # 上書きされる前のキャプチャが、ほかのどの場所にも置かれていなければ、この時刻から1週間だけ残す
            if existing_file is not None and existing_file.capture_id is not None and existing_file.capture_id != capture_id:
                has_other_files = await CaptureFile.filter(capture_id=existing_file.capture_id).exists()
                if has_other_files is False:
                    await Capture.filter(id=existing_file.capture_id).update(detached_since=datetime.now(JST))

        # 新しいキャプチャが、このパスにあったほかのキャプチャを置き換えずに増えたときは、日付ごとの件数を1つ増やすだけにする
        ## 同じ内容のキャプチャが別の場所にも置かれたときや、上書きで別のキャプチャが見えなくなったときは、件数が変わるかどうかが分からないので集計し直す
        is_capture_replaced = existing_file is not None and existing_file.capture_id is not None
        if capture is not None and is_capture_created is True and is_capture_replaced is False:
            self.addCaptureToSections(capture)
        else:
            self.invalidateSections()
        return capture


    async def processFile(self, path: str) -> bool:
        """
        監視と一括スキャンで見つかったキャプチャを1件登録する

        Args:
            path (str): 対象の絶対パス

        Returns:
            bool: 登録できたか、変更がないことを確かめられた場合は True
        """

        # 同じドライブへの同時の読み込みを、録画ファイルの解析と共通の DriveIOLimiter で制限する
        semaphore = DriveIOLimiter.getSemaphore(
            anyio.Path(path),
            network_concurrency = self.NETWORK_DRIVE_CONCURRENCY,
        )
        async with semaphore, self.getPathLock(path):
            try:
                await self.registerFile(path)
                return True
            # 見つけたあとで消されたファイルは、登録するものがないので失敗として数えない (消えたことは次の一括スキャンで確定する)
            except FileNotFoundError:
                return True
            # 読み込みや DB の一時的な失敗 (読んでいる間の書き換えを含む) は、1件の失敗として次のファイルへ進む
            ## 画像として読めないファイルは registerFile() の中で Invalid として登録しているので、ここに来るのは外の世界の失敗だけにする
            ## AttributeError や TypeError のような実装側の誤りは、全件で同じく起きるので受け止めずに呼び出し元へ伝える
            except (OSError, OperationalError, IntegrityError) as ex:
                logging.warning(f'Cannot index capture: {path}', exc_info=ex)
                return False


    async def moveFile(self, path: str, size: int, created_at: datetime, modified_at: datetime, seen_file_ids: bytearray) -> bool:
        """
        一括スキャンと監視で新しく見つかったパスが、消えたパスからの移動なら、DB の場所を付け替える
        移動かどうかは、中身を読まずにファイル名・サイズ・更新日時の一致だけで判定する
        作成日時は移動で変わる (Linux では名前の変更で更新され、ドライブをまたぐ移動ではファイルが作り直される) ため照合に使わず、付け替えるときに新しい値で更新する

        Args:
            path (str): 新しく見つかったパス
            size (int): 新しく見つかったファイルのサイズ
            created_at (datetime): 新しく見つかったファイルの作成日時
            modified_at (datetime): 新しく見つかったファイルの更新日時
            seen_file_ids (bytearray): 一括スキャンで見つかった場所の ID に 1 を記録した配列 (監視からは空の配列を渡す)

        Returns:
            bool: 移動として場所を付け替えた場合は True
        """

        file_name = Path(path).name

        # すべての保存先から、ファイル名・サイズ・更新日時が同じ場所を候補として DB から探す
        ## capture_files_name_size_modified_at のインデックスで引けるので、新しく見つかったパスごとに問い合わせても軽い
        candidate_rows = await CaptureFile.filter(
            file_name = file_name,
            file_size = size,
            file_modified_at = modified_at,
        ).values('id', 'file_path')

        for candidate_row in candidate_rows:
            old_id: int = candidate_row['id']
            old_path: str = candidate_row['file_path']
            if CapturePathKey(old_path) == CapturePathKey(path):
                continue

            # この走査ですでに見つかった場所は、古いパスにファイルがあるので候補から外す
            if old_id < len(seen_file_ids) and seen_file_ids[old_id] == 1:
                continue

            # 古いパスと新しいパスの両方のロックを、パスの順に取る (取る順を揃えてデッドロックを避ける)
            async with AsyncExitStack() as stack:
                for locked_path in sorted((old_path, path), key=CapturePathKey):
                    await stack.enter_async_context(self.getPathLock(locked_path))

                # 古いパスにまだファイルがあれば移動ではない (読めない場合も移動とは判定しない)
                try:
                    await anyio.Path(old_path).stat()
                    continue
                except FileNotFoundError:
                    pass
                except OSError:
                    continue

                # ロックを取るまでの間に、古い場所の行や新しいファイルが変わっていないかを確かめる
                current_file = await CaptureFile.get_or_none(id=old_id, file_path=old_path)
                if current_file is None:
                    continue
                new_stat = await anyio.Path(path).stat()
                is_same_file = (
                    current_file.file_size == size and
                    current_file.file_modified_at == modified_at and
                    new_stat.st_size == size and
                    datetime.fromtimestamp(new_stat.st_mtime, JST) == modified_at
                )
                if is_same_file is False:
                    continue

                # 新しいパスがまだ登録されていなければ、古い場所の行を新しいパスに付け替える
                is_moved = False
                async with InWriteTransaction():
                    if not await CaptureFile.filter(file_path=path).exists():
                        if current_file.capture_id is not None:
                            moved_status = 'Available'
                        else:
                            moved_status = 'Invalid'
                        await CaptureFile.filter(id=current_file.id).update(
                            file_path = path,
                            file_name = file_name,
                            file_created_at = created_at,
                            status = moved_status,
                            missing_since = None,
                        )
                        # 付け替えた場所は、消えたファイルの候補から外す
                        if old_id < len(seen_file_ids):
                            seen_file_ids[old_id] = 1
                        is_moved = True

                if is_moved is True:
                    self.invalidateSections()
                    return True

        return False


    async def runBatchScan(self, folders: list[str] | None = None) -> bool:
        """
        保存先フォルダ以下の一括スキャンと DB への同期を実行する
        - 追加・変更があった画像だけを解析して DB に登録する
        - 別の保存先へ移動した画像は、中身を読まずに場所だけを付け替える
        - 最後まで正常に走査できた保存先だけ、消えたファイルと期限切れの行を確定する
        - すべての保存先を走査するときは、設定から外した保存先にあった場所も、ファイルが消えていれば同じく確定する

        Args:
            folders (list[str] | None): 対象の保存先 (省略時は設定されたすべての保存先)

        Returns:
            bool: すべての保存先を最後まで走査できた場合は True (読めなかったフォルダや、途中で失敗した処理があった場合は False)
        """

        # 既に一括スキャンを実行中の場合は HTTPException を発生させる
        if self.scan_lock.locked():
            raise HTTPException(
                status_code = status.HTTP_429_TOO_MANY_REQUESTS,
                detail = 'Batch scan of capture folders is already running',
            )

        async with self.scan_lock:
            self.batch_scan_status = schemas.MaintenanceTaskStatus(is_running=True)
            try:
                # 設定されたすべての保存先を走査するかどうか (監視からは一部の保存先だけを走査する)
                ## 保存先がネットワーク上の1つだけのときの定期の走査のように、渡された保存先がすべての保存先を含む場合も含める
                configured_folders = {NormalizeCapturePath(folder) for folder in Config().capture.upload_folders}
                if folders is None:
                    folders = [str(folder) for folder in Config().capture.upload_folders]
                is_all_folders = configured_folders.issubset({NormalizeCapturePath(folder) for folder in folders})

                # 対象の保存先を正規化し、ほかの保存先の下にある保存先は親の走査に任せる
                normalized_folders = sorted({NormalizeCapturePath(folder) for folder in folders}, key=len)
                roots: list[str] = []
                for folder in normalized_folders:
                    is_nested = any(Path(folder).is_relative_to(root) for root in roots)
                    if is_nested is False:
                        roots.append(folder)

                # 進捗の総数には、録画の一括スキャンと同じく登録済みのファイル数を使う
                ## 新しく見つかったファイルの分は、処理した件数が総数を超えた時点で総数を増やして合わせる
                ## 保存先がドライブのルート (F:\ や /) のときも区切りが二重にならないよう、末尾の区切りを os.path.join() で1つにそろえる
                for root in roots:
                    registered_count = await CaptureFile.filter(file_path__startswith=os.path.join(root, '')).count()
                    self.batch_scan_status.total_count += registered_count
                # 登録済みのキャプチャがあれば、画面では初回のスキャンではなく、追加・変更されたキャプチャを探していると表示する
                self.batch_scan_status.has_registered_files = self.batch_scan_status.total_count > 0

                # 保存先を1つずつ走査する
                results: list[CaptureRootScanResult] = []
                for root in roots:
                    results.append(await self.scanRoot(root))

                # 設定から外した保存先にあった場所のように、どの保存先にも属さない場所は、すべての保存先を走査するときだけ確認する
                ## 保存先の走査のあとに確認するので、外した保存先からほかの保存先へ移した画像は、先に移動として付け替わっている
                if is_all_folders is True:
                    results.append(await self.scanRoot(None))

                # 別の保存先へ移動した画像の照合を全保存先で終えてから、消えたファイルと期限を確定する
                ## 期限による削除は、すべての保存先を最後まで走査できたときだけ行う
                ## 読めなかった保存先へ移した画像は移動として照合できていないので、移す前の場所を削除すると、お気に入りやタグごと消えてしまうため
                ## 保存先に画像が1枚も見えないとき (マウントが外れて空のフォルダが見えているときなど) や、新しく消えたファイルが2割を超えるときも、
                ## その保存先へ移した画像をほかの保存先から削除しないよう、すべての保存先で削除を見送る (消えたファイルは Missing にして一覧から隠す)
                ## 利用者が自分で大量に消した場合も、次の走査からはすでに Missing の場所を除いて数えるので、割合が下がって1週間後に削除される
                can_delete_expired = is_all_folders
                for result in results:
                    if result.is_complete is False:
                        can_delete_expired = False

                    # 走査で見つからなかった場所の数と、そのうち新しく見つからなくなった場所の数を数える
                    unseen_count = 0
                    newly_missing_count = 0
                    async for snapshot in self.iterateUnseenFiles(result):
                        unseen_count += 1
                        if snapshot['status'] != 'Missing':
                            newly_missing_count += 1

                    # どの保存先にも属さない場所は、マウントが外れて空に見える保存先がないので、1枚も見つからなくても削除を見送らない
                    ## 外した保存先の画像を利用者がすべて消した場合も、1週間後に削除される
                    if result.root is not None and result.found_count == 0 and unseen_count > 0:
                        can_delete_expired = False
                    if result.original_count > 0 and newly_missing_count / result.original_count > 0.2:
                        can_delete_expired = False
                is_complete = True
                for result in results:
                    if await self.reconcileRoot(result, can_delete_expired) is False:
                        is_complete = False

                # 上書きでどの場所にも置かれていなくなったキャプチャは、どの保存先にも属さないので、
                # 期限による削除を行えるときだけ、1週間たったものを削除する
                if len(roots) > 0 and is_complete is True and can_delete_expired is True:
                    expired_before = (datetime.now(JST) - timedelta(days=7)).isoformat(' ')
                    removed_count, _ = await connections.get('default').execute_query("""
                        DELETE FROM captures
                        WHERE detached_since < ? AND NOT EXISTS (
                            SELECT 1 FROM capture_files f
                            WHERE f.capture_id = captures.id
                        )
                    """, [expired_before])
                    if removed_count > 0:
                        self.invalidateSections()

            # DB の一時的な失敗は記録して、次の一括スキャンに任せる
            ## 実装側の誤りは受け止めずに呼び出し元へ伝え、手動の一括スキャンの API は失敗を返す
            except (OSError, OperationalError, IntegrityError) as ex:
                logging.error('Capture batch scan failed.', exc_info=ex)
                return False
            finally:
                self.batch_scan_status.is_running = False

            return is_complete


    async def scanRoot(self, root: str | None) -> CaptureRootScanResult:
        """
        保存先を1つ、フォルダ単位で走査する
        新しく見つかったパスは、消えたパスとファイル名・サイズ・更新日時が一致すれば移動として扱い、それ以外は登録する
        登録済みの場所は、一覧から取り出した塊ごとにパスで DB から取得し、走査を始めた時点の状態と見つかったかどうかだけを場所の ID ごとに記録する
        百万件規模の保存先でも、登録済みの場所を Python のオブジェクトとしてまとめて保持せずに走査できる
        保存先の代わりに None を渡すと、設定から外した保存先にあった場所のように、設定されたどの保存先にも属さない場所を、
        録画の一括スキャンと同じく、ファイルがまだあるかどうかだけで確認する

        Args:
            root (str | None): 正規化した保存先 (None なら、どの保存先にも属さない場所を確認する)

        Returns:
            CaptureRootScanResult: 全保存先の走査のあとで、消えたファイルを確定するための情報
        """

        scan_started_at = datetime.now(JST)

        # この走査で扱う場所を DB から絞り込む条件
        ## 保存先がドライブのルート (F:\ や /) のときも区切りが二重にならないよう、末尾の区切りを os.path.join() で1つにそろえる
        ## どの保存先にも属さない場所は、設定されたすべての保存先の外にある場所に絞り込む
        file_path_filters: list[Q] = []
        if root is not None:
            file_path_filters.append(Q(file_path__startswith=os.path.join(root, '')))
        else:
            for folder in Config().capture.upload_folders:
                file_path_filters.append(~Q(file_path__startswith=os.path.join(NormalizeCapturePath(folder), '')))

        # 走査を始めた時点で、この保存先に登録済みの場所の最大の ID を取得する
        ## 走査の途中でアップロードや監視が登録した場所は、これより大きな ID になるので、消えたファイルの確定の対象から外れる
        max_file_id = 0
        max_file_ids = await CaptureFile.filter(*file_path_filters).order_by('-id').limit(1).values_list('id', flat=True)
        if len(max_file_ids) > 0:
            max_file_id = cast(int, max_file_ids[0])

        # 場所の ID ごとに、走査を始めた時点の状態のハッシュ値 (1件8バイト) と、見つかったかどうか (1件1バイト) を記録する配列
        ## 百万件でも合わせて約 9MB に収まる
        file_state_hashes = array('q', [0]) * (max_file_id + 1)
        seen_file_ids = bytearray(max_file_id + 1)

        # 消えたファイルの割合は、すでに Missing の場所を除いて数える
        original_count = 0

        # この保存先に登録済みの場所を、ID の順に一定の件数ずつ取得して、状態のハッシュ値を記録する
        ## Tortoise ORM は取得した行を変換する処理をイベントループ上で実行するため、一度に取得するとその間ほかのすべての API が応答しなくなる
        last_id = 0
        while True:
            rows = await CaptureFile.filter(
                *file_path_filters,
                id__gt = last_id,
                id__lte = max_file_id,
            ).order_by('id').limit(self.SNAPSHOT_PAGE_SIZE).values_list(
                'id',
                'file_size',
                'file_created_at',
                'file_modified_at',
                'status',
            )
            if len(rows) == 0:
                break
            last_id = rows[-1][0]
            for file_id, file_size, file_created_at, file_modified_at, file_status in rows:
                file_state_hashes[file_id] = hash((file_size, file_created_at, file_modified_at))
                if file_status != 'Missing':
                    original_count += 1

        found_count = 0
        is_complete = True

        # どの保存先にも属さない場所は、列挙するフォルダがないので、場所ごとにファイルがまだあるかを確かめ、あれば見つかったものとして記録する
        ## 録画の一括スキャンと同じく、ファイルがまだある場所は、保存先から外したあとも画像を開けるのでそのまま残す
        ## 読めない場所 (通信エラーなど) は、消えたとは確定できないので、見つかったものとして扱う
        if root is None:
            last_id = 0
            while True:
                rows = await CaptureFile.filter(
                    *file_path_filters,
                    id__gt = last_id,
                    id__lte = max_file_id,
                ).order_by('id').limit(self.SNAPSHOT_PAGE_SIZE).values_list('id', 'file_path', 'status')
                if len(rows) == 0:
                    break
                last_id = rows[-1][0]
                for file_id, file_path, file_status in rows:
                    try:
                        await anyio.Path(file_path).stat()
                    except FileNotFoundError:
                        continue
                    except OSError:
                        seen_file_ids[file_id] = 1
                        found_count += 1
                        continue
                    seen_file_ids[file_id] = 1
                    found_count += 1

                    # 見つからなくなっていたファイルが戻ってきた場合 (マウントが間に合わなかったフォルダや、ごみ箱から戻した画像) は、
                    # 保存先の走査と同じく registerFile() で利用できる状態に戻す
                    ## 読み込みや DB の一時的な失敗で戻せなかった場合は、保存先の走査と同じく、走査を完了できなかったものとして扱う
                    if file_status == 'Missing' and await self.processFile(file_path) is False:
                        is_complete = False

        # rglob は走査中の OSError を黙って捨てるので、フォルダを1つずつ列挙して、読めなかったフォルダを数える
        pending_folders: list[anyio.Path] = []
        if root is not None:
            pending_folders.append(anyio.Path(root))
        while len(pending_folders) > 0:
            folder = pending_folders.pop()
            try:
                listing = await asyncio.to_thread(self.listFolder, folder)
            # 保存先の中の、権限がなくて読めないフォルダ (ドライブのルートの System Volume Information や lost+found など) は、走査の対象から外す
            ## 中に登録済みの場所があっても、そのファイルの stat も権限で失敗するので、消えたファイルとしては確定されない
            except PermissionError as ex:
                if str(folder) == root:
                    is_complete = False
                    logging.warning(f'Cannot list capture folder: {folder}', exc_info=ex)
                else:
                    logging.warning(f'Skipped capture folder without read permission: {folder}')
                continue
            except OSError as ex:
                is_complete = False
                logging.warning(f'Cannot list capture folder: {folder}', exc_info=ex)
                continue
            found_count += len(listing.file_names)

            # 子フォルダは更新日時の古い順に積み、新しいフォルダから先に取り出す
            for directory, _ in sorted(listing.directories, key=lambda item: item[1]):
                pending_folders.append(anyio.Path(directory))

            # 名前の昇順に並んだ画像を、新しい塊から順に処理し、塊の中は HDD の読み取りが速い名前の昇順に読む
            for chunk_end in range(len(listing.file_names), 0, -self.SCAN_CHUNK_SIZE):

                # 塊の画像だけ、パスと日時のオブジェクトを作る
                chunk: list[tuple[str, int, datetime, datetime]] = []
                for index in range(max(0, chunk_end - self.SCAN_CHUNK_SIZE), chunk_end):
                    chunk.append((
                        NormalizeCapturePath(os.path.join(folder, listing.file_names[index])),
                        listing.file_sizes[index],
                        datetime.fromtimestamp(listing.file_created_timestamps[index], JST),
                        datetime.fromtimestamp(listing.file_modified_timestamps[index], JST),
                    ))

                # この塊のパスで登録済みの場所を、まとめて DB から取得する (file_path の UNIQUE 制約のインデックスで引ける)
                chunk_paths: list[str] = []
                for entry in chunk:
                    chunk_paths.append(entry[0])
                known_rows = await CaptureFile.filter(file_path__in=chunk_paths).values(
                    'id',
                    'file_path',
                    'file_size',
                    'file_created_at',
                    'file_modified_at',
                    'status',
                    'missing_since',
                )
                known_files: dict[str, CaptureFileSnapshot] = {}
                for known_row in cast(list[CaptureFileSnapshot], known_rows):
                    known_files[known_row['file_path']] = known_row

                async def Process(entry: tuple[str, int, datetime, datetime]) -> None:
                    nonlocal is_complete
                    path, size, created_at, modified_at = entry
                    try:
                        known = known_files.get(path)
                        if known is not None:

                            # 走査を始めた時点で登録済みだった場所は、見つかったことを記録して、消えたファイルの候補から外す
                            if known['id'] <= max_file_id:
                                seen_file_ids[known['id']] = 1

                            # 2回目以降の走査では、一覧の stat の情報だけで変更のないファイルを飛ばす
                            is_unchanged = (
                                known['file_size'] == size and
                                known['file_created_at'] == created_at and
                                known['file_modified_at'] == modified_at and
                                known['status'] != 'Missing'
                            )
                            if is_unchanged is True:
                                return

                        # 新しく見つかったパスは、まず別の場所からの移動かを照合する
                        else:
                            is_moved = await self.moveFile(path, size, created_at, modified_at, seen_file_ids)
                            if is_moved is True:
                                return

                        if await self.processFile(path) is False:
                            is_complete = False

                    # 一覧を取ったあとで消されたファイルは、消えたファイルとして次の走査で確定するので、この保存先の走査は不完全にしない
                    except FileNotFoundError:
                        pass

                    # 移動の照合の読み込みや DB の一時的な失敗は、この保存先の走査を不完全として扱い、消えたファイルの確定を見送る
                    ## 実装側の誤りは受け止めずに一括スキャンの呼び出し元へ伝える
                    except (OSError, OperationalError, IntegrityError) as ex:
                        is_complete = False
                        logging.warning(f'Cannot inspect capture: {path}', exc_info=ex)

                    finally:
                        self.batch_scan_status.processed_count += 1
                        self.batch_scan_status.total_count = max(
                            self.batch_scan_status.total_count,
                            self.batch_scan_status.processed_count,
                        )

                # ネットワークドライブで同時に読み込める数ずつ、タスクを作って処理する
                ## ローカルのドライブでは、processFile() の中の DriveIOLimiter が1つずつに絞る
                for offset in range(0, len(chunk), self.NETWORK_DRIVE_CONCURRENCY):
                    entries = chunk[offset:offset + self.NETWORK_DRIVE_CONCURRENCY]
                    await asyncio.gather(*(Process(entry) for entry in entries))

        return CaptureRootScanResult(
            root = root,
            file_path_filters = file_path_filters,
            started_at = scan_started_at,
            max_file_id = max_file_id,
            file_state_hashes = file_state_hashes,
            seen_file_ids = seen_file_ids,
            original_count = original_count,
            found_count = found_count,
            is_complete = is_complete,
        )


    async def reconcileRoot(self, result: CaptureRootScanResult, can_delete_expired: bool) -> bool:
        """
        最後まで正常に走査できた保存先について、消えたファイルを Missing にし、1週間たった行を削除する

        Args:
            result (CaptureRootScanResult): 走査と移動の照合を終えた保存先の情報
            can_delete_expired (bool): 期限による削除を行ってよいか (すべての保存先を最後まで走査でき、削除を見送る保存先がないときだけ True)

        Returns:
            bool: 消えたファイルを確定した場合は True (走査が不完全なときは False)
        """

        # 走査が不完全なときは、期限による削除も含めて確定を見送る
        if result.is_complete is False:
            return False

        scan_started_at = result.started_at
        expired_before = scan_started_at - timedelta(days=7)
        async for snapshot in self.iterateUnseenFiles(result):
            path = snapshot['file_path']

            # すでに Missing の場所は、期限による削除を行えて1週間たったときだけ確定し直す
            ## 期限前の場所まで毎回確定し直すと、外でファイルが消されるたびの一括スキャンで、保留中の場所の数だけ書き込みが走ってしまう
            if snapshot['status'] == 'Missing':
                is_expired = snapshot['missing_since'] is not None and snapshot['missing_since'] <= expired_before
                if can_delete_expired is False or is_expired is False:
                    continue

            async with self.getPathLock(path):

                # 走査のあとで同じパスに戻ってきていれば、消えていないので何もしない (読めない場合も確定しない)
                try:
                    await anyio.Path(path).stat()
                except FileNotFoundError:
                    pass
                except OSError:
                    continue
                else:
                    # 一覧には出てこないのに、このパスでファイルを開けるのは、Windows で名前の大文字と小文字だけが変わった場合
                    ## 走査は実際の表記の新しいパスで同じキャプチャの場所を登録しているので、古い表記の場所を削除して、1つのファイルに場所が2つ残らないようにする
                    ## 同じキーのパスは同じロックなので、新しい表記の場所もこのロックの中で扱える
                    ## Linux では、ほかの場所のパスが同じキーになることはないので、何も削除しない
                    if snapshot['status'] != 'Invalid':
                        async with InWriteTransaction():
                            current_file = await CaptureFile.get_or_none(id=snapshot['id'], file_path=path)
                            if current_file is not None and current_file.capture_id is not None:
                                for other_path in await CaptureFile.filter(
                                    capture_id = current_file.capture_id,
                                    id__not = current_file.id,
                                ).values_list('file_path', flat=True):
                                    if CapturePathKey(cast(str, other_path)) == CapturePathKey(path):
                                        await current_file.delete()
                                        break
                    continue

                async with InWriteTransaction():

                    # 走査を始めたあとに行が変わっていたら (アップロードや付け替え)、確定しない
                    current_file = await CaptureFile.get_or_none(id=snapshot['id'], file_path=path)
                    if current_file is None:
                        continue
                    current_state_hash = hash((current_file.file_size, current_file.file_created_at, current_file.file_modified_at))
                    if current_state_hash != result.file_state_hashes[current_file.id]:
                        continue
                    capture = None
                    if current_file.capture_id is not None:
                        capture = await Capture.get_or_none(id=current_file.capture_id)

                    # 初めて見つからなかった場合は Missing にし、1週間たっても戻らなければ削除する
                    if current_file.missing_since is None:
                        await CaptureFile.filter(id=current_file.id).update(
                            status = 'Missing',
                            missing_since = scan_started_at,
                        )
                    elif can_delete_expired is True and current_file.missing_since <= expired_before:
                        await current_file.delete()
                        # 場所が1つも残っていないキャプチャも一緒に削除する
                        if capture is not None and not await CaptureFile.filter(capture_id=capture.id).exists():
                            await capture.delete()

                self.invalidateSections()

        return True


    async def iterateUnseenFiles(self, result: CaptureRootScanResult) -> AsyncGenerator[CaptureFileSnapshot]:
        """
        走査を始めた時点で保存先に登録済みだった場所のうち、走査で見つからなかった場所を ID の順に返す
        一定の件数ずつ DB から取得し直すため、百万件規模の保存先でもまとめて保持しない

        Args:
            result (CaptureRootScanResult): 走査と移動の照合を終えた保存先の情報

        Yields:
            CaptureFileSnapshot: 走査で見つからなかった場所
        """

        # 保存先のパスで絞り込むので、走査のあとで別の保存先へ付け替えられた場所は対象から外れる
        last_id = 0
        while True:
            rows = await CaptureFile.filter(
                *result.file_path_filters,
                id__gt = last_id,
                id__lte = result.max_file_id,
            ).order_by('id').limit(self.SNAPSHOT_PAGE_SIZE).values(
                'id',
                'file_path',
                'file_size',
                'file_created_at',
                'file_modified_at',
                'status',
                'missing_since',
            )
            if len(rows) == 0:
                break
            last_id = rows[-1]['id']
            for snapshot in cast(list[CaptureFileSnapshot], rows):
                if result.seen_file_ids[snapshot['id']] == 0:
                    yield snapshot


    @classmethod
    def listFolder(cls, folder: anyio.Path) -> CaptureFolderListing:
        """
        フォルダを1つだけ列挙し、画像を名前の昇順に並べる (読めなかった場合は OSError を送出する)
        百万枚のフォルダでは並べ替えに数百ミリ秒かかるため、ワーカースレッドで実行する

        Args:
            folder (anyio.Path): 対象のフォルダ

        Returns:
            CaptureFolderListing: 子フォルダとその更新日時、名前の昇順に並べた画像のファイル名とサイズ・作成日時・更新日時
        """

        directories: list[tuple[str, float]] = []
        file_names: list[str] = []
        file_sizes = array('q')
        file_created_timestamps = array('d')
        file_modified_timestamps = array('d')
        with os.scandir(str(folder)) as iterator:
            for entry in iterator:

                # シンボリックリンクは、外部へのリンクや循環を避けるため飛ばす
                if entry.is_symlink():
                    continue

                if entry.is_dir(follow_symlinks=False):
                    # ごみ箱やスナップショットのフォルダは、中身ごと走査の対象から外す
                    folder_name = entry.name.lower()
                    if folder_name in cls.EXCLUDED_FOLDER_NAMES or folder_name.startswith('.trash'):
                        continue
                    directory_stat = entry.stat(follow_symlinks=False)
                    directories.append((NormalizeCapturePath(entry.path), directory_stat.st_mtime))
                    continue

                # 拡張子は Path(entry.name).suffix と同じ規則 (先頭の . は拡張子に数えない) で、Path を作らずに取り出す
                ## Path() は名前を sys.intern() に通すため、その名前を一覧に保持すると、百万枚のフォルダではインターンした文字列の辞書が百万件分に広がり、
                ## 走査を終えたあともその大きさのまま残る
                dot_index = entry.name.rfind('.')
                suffix = ''
                if 0 < dot_index < len(entry.name) - 1:
                    suffix = entry.name[dot_index:].lower()

                # 画像の stat の値は一覧を取るときに記録し、塊を処理するときにそのまま使う (Windows では一覧の取得と同時に得られ、ネットワーク越しでも追加の通信なしで済む)
                if entry.is_file(follow_symlinks=False) and suffix in cls.CAPTURE_EXTENSIONS:
                    file_stat = entry.stat(follow_symlinks=False)
                    file_names.append(entry.name)
                    file_sizes.append(file_stat.st_size)
                    file_created_timestamps.append(file_stat.st_ctime)
                    file_modified_timestamps.append(file_stat.st_mtime)

        # 画像を名前の昇順に並べ替える
        ## 画像ごとのタプルを作らずに済むよう、名前の昇順に並べたときの位置の一覧を求めてから、それぞれの配列をその順に作り直す
        order = sorted(range(len(file_names)), key=file_names.__getitem__)
        return CaptureFolderListing(
            directories = directories,
            file_names = [file_names[index] for index in order],
            file_sizes = array('q', (file_sizes[index] for index in order)),
            file_created_timestamps = array('d', (file_created_timestamps[index] for index in order)),
            file_modified_timestamps = array('d', (file_modified_timestamps[index] for index in order)),
        )


    async def watchFolders(self) -> None:
        """
        保存先の変更を OS の変更通知で監視する
        Linux で NFS や SMB (CIFS) などネットワーク上のファイルシステムに置かれた保存先は、変更通知が届かないため、設定した間隔で一括スキャンする
        """

        roots = list({NormalizeCapturePath(path) for path in Config().capture.upload_folders})

        # 保存先を、変更通知で監視するものと、設定した間隔で一括スキャンするものに分ける
        ## Linux のネットワーク上のファイルシステムでは、ほかの機械からの変更が inotify に届かない
        ## Windows は SMB 越しでも変更通知が届くので、すべて変更通知で監視する
        local_roots: list[str] = []
        network_roots: list[str] = []
        if psutil.LINUX:
            partitions = await asyncio.to_thread(psutil.disk_partitions, all=True)
        else:
            partitions = []
        for root in roots:
            is_network = False
            deepest_mountpoint = ''
            # シンボリックリンクで設定された保存先は、リンクの先のマウントで判定する (保存先のパス自体はリンクのまま使う)
            resolved_root = await asyncio.to_thread(os.path.realpath, root)
            for partition in partitions:
                is_network_filesystem = partition.fstype.lower() in DriveIOLimiter.NETWORK_FILESYSTEMS

                # 保存先を含むマウントのうち、最も深いマウントのファイルシステムで判定する
                is_root_under_mountpoint = Path(resolved_root).is_relative_to(partition.mountpoint)
                if is_root_under_mountpoint is True and len(partition.mountpoint) > len(deepest_mountpoint):
                    deepest_mountpoint = partition.mountpoint
                    is_network = is_network_filesystem

                # 保存先自体がローカルでも、その下にネットワークのファイルシステムがマウントされていれば対象にする
                is_mounted_under_root = Path(partition.mountpoint).is_relative_to(resolved_root) and partition.mountpoint != resolved_root
                if is_mounted_under_root is True and is_network_filesystem is True:
                    is_network = True
                    break

            if is_network is True:
                network_roots.append(root)
            else:
                local_roots.append(root)

        async def Watch() -> None:
            """
            ローカルの保存先の変更を監視し、追加・変更された画像を登録する
            """

            if len(local_roots) == 0:
                return

            # 消えたファイルを確定するために始めた一括スキャンのタスク (終わるまで参照を持っておく)
            scan_tasks: set[asyncio.Task[None]] = set()
            # まだ一括スキャンを始めていない、待っている間のタスク (同じ変化のために何度も一括スキャンしないよう、1つだけ持つ)
            waiting_scan_task: asyncio.Task[None] | None = None

            async def ScanAfterCurrent() -> None:
                """
                実行中の一括スキャンが終わるのを待ってから、ローカルの保存先を一括スキャンする
                実行中の一括スキャンがすでに通り過ぎた場所の変化は、その一括スキャンでは拾えないため、終わってからもう一度走査する
                """

                nonlocal waiting_scan_task
                while self.scan_lock.locked():
                    await asyncio.sleep(1)
                waiting_scan_task = None
                try:
                    await self.runBatchScan(local_roots)
                except HTTPException:
                    # 待っている間に別の一括スキャンが始まったときは、変化のあとに始まったその一括スキャンに任せる
                    pass

            async def WatchRoot(root: str) -> None:
                """
                保存先を1つ監視する
                保存先が見えなくなったときは、この保存先だけを再試行し、ほかの保存先の監視を続ける
                """

                nonlocal waiting_scan_task

                def IsWatchTarget(change: Change, path: str) -> bool:
                    """
                    一括スキャンと同じく、ごみ箱やスナップショットのフォルダの中の変化を監視の対象から外す

                    Args:
                        change (Change): 変化の種類
                        path (str): 変化したパス

                    Returns:
                        bool: 監視の対象にする場合は True
                    """

                    for part in Path(path).relative_to(root).parts:
                        folder_name = part.lower()
                        if folder_name in self.EXCLUDED_FOLDER_NAMES or folder_name.startswith('.trash'):
                            return False
                    return True

                # 監視が止まったあとで、保存先が見えるようになったら一括スキャンするか
                ## awatch() を作り直しても、止まっている間に増えた画像は通知されないため、一括スキャンで取りこぼしを回収する
                needs_scan_on_resume = False
                while True:
                    try:
                        if needs_scan_on_resume is True and await anyio.Path(root).is_dir():
                            needs_scan_on_resume = False
                            if waiting_scan_task is None:
                                waiting_scan_task = asyncio.create_task(ScanAfterCurrent())
                                scan_tasks.add(waiting_scan_task)
                                waiting_scan_task.add_done_callback(scan_tasks.discard)
                        # 保存先の中の権限がなくて読めないフォルダ (lost+found など) は、一括スキャンと同じく監視の対象から外す
                        ## 外さないと Linux では監視を始められず、5秒ごとの再試行のたびに一括スキャンを繰り返してしまう
                        async for changes in awatch(
                            root,
                            force_polling = False,
                            watch_filter = IsWatchTarget,
                            ignore_permission_denied = True,
                        ):

                            # 追加・変更された画像を登録する
                            for change, path in changes:
                                if change == Change.deleted or Path(path).suffix.lower() not in self.CAPTURE_EXTENSIONS:
                                    continue
                                normalized_path = NormalizeCapturePath(path)

                                # 追加されたパスは、一括スキャンと同じく、まず別の場所からの移動かを照合する
                                ## 保存先の中での移動や名前の変更では、画像を読み直さずに同じ場所の行を付け替える
                                if change == Change.added:
                                    try:
                                        file_stat = await anyio.Path(normalized_path).stat()
                                        is_moved = await self.moveFile(
                                            normalized_path,
                                            file_stat.st_size,
                                            datetime.fromtimestamp(file_stat.st_ctime, JST),
                                            datetime.fromtimestamp(file_stat.st_mtime, JST),
                                            bytearray(),
                                        )
                                    except FileNotFoundError:
                                        continue
                                    # 移動の照合の一時的な失敗は、画像を読み込んで登録する処理に任せる
                                    except (OSError, OperationalError, IntegrityError) as ex:
                                        logging.warning(f'Cannot check moved capture: {normalized_path}', exc_info=ex)
                                        is_moved = False
                                    if is_moved is True:
                                        continue

                                await self.processFile(normalized_path)

                            # 消えたファイルは、通信エラーと見分けるため、一括スキャンで全体を列挙してから確定する
                            ## フォルダごと移してきた画像は、フォルダの追加しか通知されないので、これも一括スキャンで登録する
                            ## 百万枚規模では一括スキャンに数分以上かかるので、別のタスクで実行し、その間も追加・変更された画像を登録し続ける
                            needs_scan = False
                            for change, path in changes:
                                if change == Change.deleted:

                                    # 登録済みの場所がないパスの削除は、確定するものがないので一括スキャンを始めずに次の通知へ進む
                                    ## KonomiTV が削除したキャプチャは、ファイルを削除した直後に DB の行も削除しているので、ここで該当しなくなる
                                    ## DB を読めないときは、確定を一括スキャンに任せる
                                    deleted_path = NormalizeCapturePath(path)
                                    try:
                                        # 削除されたパスそのものが登録済みかを、file_path の UNIQUE 制約のインデックスで引く
                                        is_registered = await CaptureFile.filter(file_path=deleted_path).exists()

                                        # フォルダごと消されたときは、フォルダの中に登録済みの場所があるかで判定する
                                        ## LIKE による前方一致はインデックスを使えずに全件を走査するため、パスの文字列の範囲で絞り込む
                                        ## 区切り文字の次の文字を上限にすると、フォルダの区切りの後に続くパスだけが範囲に入る
                                        ## 画像の拡張子で終わる名前のフォルダもあるため、パスの形では省略せずに判定する
                                        if is_registered is False:
                                            is_registered = await CaptureFile.filter(
                                                file_path__gte = os.path.join(deleted_path, ''),
                                                file_path__lt = deleted_path + chr(ord(os.sep) + 1),
                                            ).exists()
                                    except OperationalError:
                                        is_registered = True
                                    if is_registered is True:
                                        needs_scan = True
                                        break
                                    continue

                                if change == Change.added and Path(path).suffix.lower() not in self.CAPTURE_EXTENSIONS:
                                    if await anyio.Path(path).is_dir():
                                        needs_scan = True
                                        break
                            if needs_scan is True and waiting_scan_task is None:
                                waiting_scan_task = asyncio.create_task(ScanAfterCurrent())
                                scan_tasks.add(waiting_scan_task)
                                waiting_scan_task.add_done_callback(scan_tasks.discard)

                            # 保存先そのものが消えたり移されたりしたときは、同じパスに作り直されても通知が届かなくなるため、監視を作り直す
                            ## 作り直すまでの間に置かれた画像は、保存先が見えるようになってからの一括スキャンで登録する
                            root_deleted = False
                            for change, path in changes:
                                if change == Change.deleted and Path(path) == Path(root):
                                    root_deleted = True
                                    break
                            if root_deleted is True:
                                logging.warning(f'{root}: Capture folder was removed; restarting the watcher.')
                                needs_scan_on_resume = True
                                break

                    except OSError as ex:
                        logging.warning(f'{root}: Capture watcher failed; retrying.', exc_info=ex)
                        needs_scan_on_resume = True
                        await asyncio.sleep(5)

            # 保存先ごとに監視する (まとめて監視すると、1つの保存先が見えないだけで、すべての保存先の監視が止まるため)
            ## 監視を止めるときは、監視から始めた一括スキャンも一緒に止め、DB を閉じたあとまで走査が続かないようにする
            try:
                await asyncio.gather(*(WatchRoot(root) for root in local_roots))
            finally:
                for scan_task in scan_tasks:
                    scan_task.cancel()

        async def Poll() -> None:
            """
            ネットワークドライブの保存先があるとき、設定した間隔で保存先フォルダ全体を一括スキャンする (間隔が 0 の場合は何もしない)
            """

            interval = Config().capture.upload_folders_polling_interval
            if len(network_roots) == 0 or interval == 0:
                return

            # ローカルの保存先と併用していても、すべての保存先を走査した一括スキャンにして、期限による削除まで行う
            while True:
                await asyncio.sleep(interval * 60)
                if not self.scan_lock.locked():
                    await self.runBatchScan()

        async with asyncio.TaskGroup() as group:
            group.create_task(Watch())
            group.create_task(Poll())


    async def deleteCapture(self, capture_id: int) -> bool:
        """
        キャプチャのすべての実体ファイルを削除し、すべて削除できた場合だけ DB の行を削除する

        Args:
            capture_id (int): 削除するキャプチャの ID

        Returns:
            bool: すべての実体ファイルと DB の行を削除できた場合は True
        """

        # 削除の前に照合する中身のハッシュを取得する (キャプチャがなければ、消すものがないので削除できたものとして扱う)
        capture = await Capture.get_or_none(id=capture_id)
        if capture is None:
            return True
        files = await CaptureFile.filter(capture_id=capture_id)
        async with AsyncExitStack() as stack:

            # 削除の途中で一括スキャンが登録し直さないよう、すべての場所のロックを取る
            ## 移動の照合と同じく、ロックのキーの順に取る (取る順を揃えてデッドロックを避ける)
            ## Windows で大文字と小文字だけが異なるパスの場所が2つあると、同じロックを2回待って止まってしまうため、同じキーのロックは1回だけ取る
            files.sort(key=lambda file: CapturePathKey(file.file_path))
            locked_keys: set[str] = set()
            for file in files:
                key = CapturePathKey(file.file_path)
                if key in locked_keys:
                    continue
                locked_keys.add(key)
                await stack.enter_async_context(self.getPathLock(file.file_path))

            # すべての場所のファイルを削除する
            for file in files:
                try:
                    # 登録したあとに別の内容に置き換わっていたり、移動の照合 (ファイル名・サイズ・更新日時だけで行う) で
                    # 同じ属性の別の画像に付け替わっていたりすることがあるため、取り消せない削除の前に中身のハッシュを照合する
                    ## 別の画像なら読んだ内容で登録し直して、削除を中断する
                    ## 照合には中身のハッシュだけを使う (SMB などのネットワーク上の保存先では、アップロードの直後に記録した作成日時と更新日時が、
                    ## 保存先のサーバーが確定した日時と食い違うことがあり、日時で照合すると中身が同じでも削除できなくなるため)
                    data = await anyio.Path(file.file_path).read_bytes()
                    digest = await asyncio.to_thread(lambda: hashlib.sha256(data).digest())
                    if digest != bytes(capture.file_hash):
                        await self.registerFile(file.file_path, data=data, force=True)
                        return False
                    await anyio.Path(file.file_path).unlink()
                except FileNotFoundError:
                    continue
                except OSError as ex:
                    logging.warning(f'Cannot delete capture: {file.file_path}', exc_info=ex)
                    return False

            # 削除の途中で場所が追加されたり、移動の照合で別のパスへ付け替えられたりしていたら、DB の行は残す
            ## 付け替えられた場所は古いパスの削除が FileNotFoundError で飛ばされ、移動先の画像が残っているため、ID とパスの組で照合する
            async with InWriteTransaction():
                current_files: set[tuple[int, str]] = set()
                for current_file in await CaptureFile.filter(capture_id=capture_id).values('id', 'file_path'):
                    current_files.add((current_file['id'], current_file['file_path']))
                deleted_files: set[tuple[int, str]] = set()
                for file in files:
                    deleted_files.add((file.id, file.file_path))
                if current_files != deleted_files:
                    return False
                await Capture.filter(id=capture_id).delete()

            self.invalidateSections()

        return True
