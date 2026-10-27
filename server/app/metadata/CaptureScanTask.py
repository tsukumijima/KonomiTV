from __future__ import annotations

import asyncio
import hashlib
import io
import os
import re
from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, ClassVar, Literal, TypedDict, cast
from weakref import WeakValueDictionary

import anyio
import psutil
from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError
from pydantic import AliasChoices, BaseModel, Field, ValidationError, field_validator
from tortoise import connections, transactions
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
    network_id: int
    service_id: int
    event_id: int
    start_time: datetime
    end_time: datetime
    duration: Annotated[float, Field(allow_inf_nan=False)]
    title: str
    description: str
    caption_text: str | None = None
    is_caption_composited: bool = False
    is_comment_composited: bool = False

    @field_validator('captured_at', 'start_time', 'end_time')
    @classmethod
    def normalizeDateTime(cls, value: datetime) -> datetime:
        """
        タイムゾーンを省略した旧形式の日時も JST に揃える

        Args:
            value (datetime): EXIF の日時

        Returns:
            datetime: JST のタイムゾーン付き日時
        """

        if value.tzinfo is None:
            return value.replace(tzinfo=JST)
        return value.astimezone(JST)


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
    走査を始めた時点の、キャプチャの場所の情報
    """

    id: int
    file_path: str
    file_name: str
    file_size: int
    file_created_at: datetime
    file_modified_at: datetime
    capture_id: int | None
    status: Literal['Available', 'Missing', 'Invalid']
    missing_since: datetime | None


@dataclass(slots=True)
class CaptureRootScanResult:
    """
    保存先ごとの走査の結果 (全保存先の移動の照合が終わってから、消えたファイルを確定するために使う)
    """

    unseen: dict[str, CaptureFileSnapshot]
    started_at: datetime
    original_count: int
    is_complete: bool


def NormalizeCapturePath(path: str | Path | anyio.Path) -> str:
    """
    すべての取り込みの経路で、同じ形の絶対パスを作る
    Docker のパスは、設定の読み込み時に付けた /host-rootfs をそのまま残し、実際のアクセスにも同じ値を使う

    Args:
        path (str | Path | anyio.Path): ファイルまたはフォルダのパス

    Returns:
        str: Windows の大文字小文字と区切りも揃えた絶対パス
    """

    return os.path.normcase(os.path.abspath(os.path.normpath(str(path))))


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
        if image.format == 'JPEG':
            image.draft('RGB', (width // 8, height // 8))
            image.load()
        # PNG の verify() はチャンクの CRC まで検査する (PNG の getexif() は内部で読み込みを進めるため、先に verify() を済ませる)
        else:
            image.verify()

    # EXIF から、KonomiTV が書き込んだ番組情報 (XPComment) と撮影日時 (DateTimeOriginal) を取り出す
    with Image.open(io.BytesIO(data)) as image:
        exif = image.getexif()
        raw_comment = exif.get(40092)
        if 34665 in exif:
            original_time = exif.get_ifd(34665).get(36867)
        else:
            original_time = exif.get(36867)

    # XPComment だけが壊れている場合も、画像は閲覧できるようにする
    metadata = None
    metadata_status = 'NoMetadata'
    if raw_comment is not None:
        try:
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
                if abs((filename_time - captured_at).total_seconds()) >= 600:
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

    # キャプチャとして扱う画像の拡張子
    CAPTURE_EXTENSIONS: ClassVar[tuple[str, ...]] = ('.jpg', '.jpeg', '.png')

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
        ## 集計の途中で DB が変わった場合に古い集計を書き戻さないよう、invalidateSections() のたびに世代番号を進める
        self.sections_generation = 0
        self.sections_cache: dict[tuple[str, int], schemas.CaptureSections] = {}


    def invalidateSections(self) -> None:
        """
        DB の変更をコミットした直後に呼び、日付ごとの件数のキャッシュを捨てる
        """

        self.sections_generation += 1
        self.sections_cache.clear()


    def getPathLock(self, path: str) -> asyncio.Lock:
        """
        パスごとのロックを取得する

        Args:
            path (str): 正規化した絶対パス

        Returns:
            asyncio.Lock: そのパスを扱うすべての処理で共通のロック
        """

        lock = self.path_locks.get(path)
        if lock is None:
            lock = asyncio.Lock()
            self.path_locks[path] = lock
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

        async with asyncio.TaskGroup() as group:
            group.create_task(self.runBatchScan())
            group.create_task(self.watchFolders())


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
        async with transactions.in_transaction():
            capture = None
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
                    capture, _ = await Capture.get_or_create(
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
            except Exception as ex:
                logging.warning(f'Cannot index capture: {path}', exc_info=ex)
                return False


    async def runBatchScan(self, folders: list[str] | None = None) -> None:
        """
        保存先フォルダ以下の一括スキャンと DB への同期を実行する
        - 追加・変更があった画像だけを解析して DB に登録する
        - 別の保存先へ移動した画像は、中身を読まずに場所だけを付け替える
        - 最後まで正常に走査できた保存先だけ、消えたファイルと期限切れの行を確定する

        Args:
            folders (list[str] | None): 対象の保存先 (省略時は設定されたすべての保存先)
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
                is_all_folders = folders is None

                # 対象の保存先を正規化し、ほかの保存先の下にある保存先は親の走査に任せる
                if folders is None:
                    folders = [str(folder) for folder in Config().capture.upload_folders]
                normalized_folders = sorted({NormalizeCapturePath(folder) for folder in folders}, key=len)
                roots: list[str] = []
                for folder in normalized_folders:
                    is_nested = any(Path(folder).is_relative_to(root) for root in roots)
                    if is_nested is False:
                        roots.append(folder)

                # 進捗の総数には、録画の一括スキャンと同じく登録済みのファイル数を使う
                ## 新しく見つかったファイルの分は、処理した件数が総数を超えた時点で総数を増やして合わせる
                for root in roots:
                    registered_count = await CaptureFile.filter(file_path__startswith=root + os.sep).count()
                    self.batch_scan_status.total_count += registered_count

                # 保存先を1つずつ走査する
                results: list[CaptureRootScanResult] = []
                for root in roots:
                    results.append(await self.scanRoot(root))

                # 別の保存先へ移動した画像の照合を全保存先で終えてから、消えたファイルと期限を確定する
                is_complete = True
                for result in results:
                    if await self.reconcileRoot(result) is False:
                        is_complete = False

                # 上書きでどの場所にも置かれていなくなったキャプチャは、どの保存先にも属さないので、
                # すべての保存先を最後まで走査できたときだけ、1週間たったものを削除する
                if is_all_folders is True and len(roots) > 0 and is_complete is True:
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

            except asyncio.CancelledError:
                raise
            except Exception as ex:
                logging.error('Capture batch scan failed.', exc_info=ex)
            finally:
                self.batch_scan_status.is_running = False


    async def scanRoot(self, root: str) -> CaptureRootScanResult:
        """
        保存先を1つ、フォルダ単位で走査する
        新しく見つかったパスは、消えたパスとファイル名・サイズ・更新日時が一致すれば移動として扱い、それ以外は登録する

        Args:
            root (str): 正規化した保存先

        Returns:
            CaptureRootScanResult: 全保存先の走査のあとで、消えたファイルを確定するための情報
        """

        scan_started_at = datetime.now(JST)

        # この保存先に登録済みの場所を取得する (メモリを抑えるため、照合に使う列だけを取得する)
        rows = await CaptureFile.filter(file_path__startswith=root + os.sep).values(
            'id',
            'file_path',
            'file_name',
            'file_size',
            'file_created_at',
            'file_modified_at',
            'capture_id',
            'status',
            'missing_since',
        )
        snapshots = cast(list[CaptureFileSnapshot], rows)

        # 走査でまだ見つかっていない場所 (走査が終わった時点で残っているものが、消えたファイルの候補になる)
        unseen: dict[str, CaptureFileSnapshot] = {}
        for snapshot in snapshots:
            unseen[str(snapshot['file_path'])] = snapshot

        # 移動の照合に使う、ファイル名・サイズ・更新日時から登録済みのパスを引く辞書
        paths_by_signature: dict[tuple[str, int, datetime], list[str]] = {}
        for snapshot in snapshots:
            signature = (snapshot['file_name'], snapshot['file_size'], snapshot['file_modified_at'])
            paths_by_signature.setdefault(signature, []).append(snapshot['file_path'])

        original_count = len(unseen)
        is_complete = True

        async def MoveCaptureFile(path: str, size: int, created_at: datetime, modified_at: datetime) -> bool:
            """
            新しく見つかったパスが、消えたパスからの移動なら、DB の場所を付け替える
            移動かどうかは、中身を読まずにファイル名・サイズ・更新日時の一致だけで判定する
            作成日時は移動で変わる (Linux では名前の変更で更新され、ドライブをまたぐ移動ではファイルが作り直される) ため照合に使わず、付け替えるときに新しい値で更新する

            Args:
                path (str): 新しく見つかったパス
                size (int): 新しく見つかったファイルのサイズ
                created_at (datetime): 新しく見つかったファイルの作成日時
                modified_at (datetime): 新しく見つかったファイルの更新日時

            Returns:
                bool: 移動として場所を付け替えた場合は True
            """

            file_name = Path(path).name

            # 同じ保存先の中で、ファイル名・サイズ・更新日時が同じで、まだ見つかっていない場所を候補にする
            candidate_ids: dict[str, int] = {}
            for candidate_path in paths_by_signature.get((file_name, size, modified_at), []):
                if candidate_path in unseen:
                    candidate_ids[candidate_path] = unseen[candidate_path]['id']

            # 同じ保存先に候補がなければ、保存先をまたぐ移動の候補を DB から探す
            if len(candidate_ids) == 0:
                candidate_rows = await CaptureFile.filter(
                    file_name = file_name,
                    file_size = size,
                    file_modified_at = modified_at,
                ).values('id', 'file_path')
                for candidate_row in candidate_rows:
                    candidate_ids[candidate_row['file_path']] = candidate_row['id']

            for old_path, old_id in candidate_ids.items():
                if old_path == path:
                    continue

                # 古いパスと新しいパスの両方のロックを、パスの順に取る (取る順を揃えてデッドロックを避ける)
                async with AsyncExitStack() as stack:
                    for locked_path in sorted((old_path, path)):
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
                    async with transactions.in_transaction():
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
                            unseen.pop(old_path, None)
                            is_moved = True

                    if is_moved is True:
                        self.invalidateSections()
                        return True

            return False


        # rglob は走査中の OSError を黙って捨てるので、フォルダを1つずつ列挙して、読めなかったフォルダを数える
        pending_folders = [anyio.Path(root)]
        while len(pending_folders) > 0:
            folder = pending_folders.pop()
            try:
                directories, files = await asyncio.to_thread(self.listFolder, folder)
            except OSError as ex:
                is_complete = False
                logging.warning(f'Cannot list capture folder: {folder}', exc_info=ex)
                continue

            # 子フォルダは更新日時の古い順に積み、新しいフォルダから先に取り出す
            for directory, _ in sorted(directories, key=lambda item: item[1]):
                pending_folders.append(anyio.Path(directory))

            # 新しい塊から順に処理し、塊の中は HDD の読み取りが速い名前の昇順に読む
            files.sort(key=lambda item: item[0])
            for chunk_end in range(len(files), 0, -self.SCAN_CHUNK_SIZE):
                chunk = files[max(0, chunk_end - self.SCAN_CHUNK_SIZE):chunk_end]

                async def Process(entry: tuple[str, int, datetime, datetime]) -> None:
                    nonlocal is_complete
                    path, size, created_at, modified_at = entry
                    try:
                        # 2回目以降の走査では、一覧の stat の情報だけで変更のないファイルを飛ばす
                        known = unseen.get(path)
                        if known is not None:
                            is_unchanged = (
                                known['file_size'] == size and
                                known['file_created_at'] == created_at and
                                known['file_modified_at'] == modified_at and
                                known['status'] != 'Missing'
                            )
                            if is_unchanged is True:
                                return

                        # 新しく見つかったパスは、まず別の場所からの移動かを照合する
                        if path not in unseen:
                            is_moved = await MoveCaptureFile(path, size, created_at, modified_at)
                            if is_moved is True:
                                return

                        if await self.processFile(path) is False:
                            is_complete = False

                    except Exception as ex:
                        is_complete = False
                        logging.warning(f'Cannot inspect capture: {path}', exc_info=ex)

                    finally:
                        unseen.pop(path, None)
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
            unseen = unseen,
            started_at = scan_started_at,
            original_count = original_count,
            is_complete = is_complete,
        )


    async def reconcileRoot(self, result: CaptureRootScanResult) -> bool:
        """
        最後まで正常に走査できた保存先について、消えたファイルを Missing にし、1週間たった行を削除する

        Args:
            result (CaptureRootScanResult): 走査と移動の照合を終えた保存先の情報

        Returns:
            bool: 消えたファイルを確定した場合は True (走査が不完全なときや、消えたファイルが多すぎるときは False)
        """

        # 走査が不完全なときや、消えたファイルが2割を超えるときは、期限による削除も含めて確定を見送る
        if result.is_complete is False:
            return False
        if result.original_count > 0 and len(result.unseen) / result.original_count > 0.2:
            return False

        scan_started_at = result.started_at
        for path, snapshot in result.unseen.items():
            async with self.getPathLock(path):

                # 走査のあとで同じパスに戻ってきていれば、消えていないので何もしない (読めない場合も確定しない)
                try:
                    await anyio.Path(path).stat()
                    continue
                except FileNotFoundError:
                    pass
                except OSError:
                    continue

                async with transactions.in_transaction():

                    # 走査を始めたあとに行が変わっていたら (アップロードや付け替え)、確定しない
                    current_file = await CaptureFile.get_or_none(id=snapshot['id'], file_path=path)
                    if current_file is None:
                        continue
                    is_changed = (
                        current_file.file_size != snapshot['file_size'] or
                        current_file.file_created_at != snapshot['file_created_at'] or
                        current_file.file_modified_at != snapshot['file_modified_at']
                    )
                    if is_changed is True:
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
                    elif current_file.missing_since <= scan_started_at - timedelta(days=7):
                        await current_file.delete()
                        # 場所が1つも残っていないキャプチャも一緒に削除する
                        if capture is not None and not await CaptureFile.filter(capture_id=capture.id).exists():
                            await capture.delete()

                self.invalidateSections()

        return True


    @classmethod
    def listFolder(cls, folder: anyio.Path) -> tuple[list[tuple[str, float]], list[tuple[str, int, datetime, datetime]]]:
        """
        フォルダを1つだけ列挙する (読めなかった場合は OSError を送出する)

        Args:
            folder (anyio.Path): 対象のフォルダ

        Returns:
            tuple[list[tuple[str, float]], list[tuple[str, int, datetime, datetime]]]: 子フォルダとその更新日時、画像ファイルとそのサイズ・作成日時・更新日時
        """

        directories: list[tuple[str, float]] = []
        files: list[tuple[str, int, datetime, datetime]] = []
        with os.scandir(str(folder)) as iterator:
            for entry in iterator:

                # シンボリックリンクは、外部へのリンクや循環を避けるため飛ばす
                if entry.is_symlink():
                    continue

                if entry.is_dir(follow_symlinks=False):
                    directory_stat = entry.stat(follow_symlinks=False)
                    directories.append((NormalizeCapturePath(entry.path), directory_stat.st_mtime))
                    continue

                if entry.is_file(follow_symlinks=False) and Path(entry.name).suffix.lower() in cls.CAPTURE_EXTENSIONS:
                    file_stat = entry.stat(follow_symlinks=False)
                    files.append((
                        NormalizeCapturePath(entry.path),
                        file_stat.st_size,
                        datetime.fromtimestamp(file_stat.st_ctime, JST),
                        datetime.fromtimestamp(file_stat.st_mtime, JST),
                    ))

        return directories, files


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
            for partition in partitions:
                is_network_filesystem = partition.fstype.lower() in DriveIOLimiter.NETWORK_FILESYSTEMS

                # 保存先を含むマウントのうち、最も深いマウントのファイルシステムで判定する
                is_root_under_mountpoint = Path(root).is_relative_to(partition.mountpoint)
                if is_root_under_mountpoint is True and len(partition.mountpoint) > len(deepest_mountpoint):
                    deepest_mountpoint = partition.mountpoint
                    is_network = is_network_filesystem

                # 保存先自体がローカルでも、その下にネットワークのファイルシステムがマウントされていれば対象にする
                is_mounted_under_root = Path(partition.mountpoint).is_relative_to(root) and partition.mountpoint != root
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

            while True:
                try:
                    async for changes in awatch(*local_roots, force_polling=False):

                        # 追加・変更された画像を登録する
                        for change, path in changes:
                            if change != Change.deleted and Path(path).suffix.lower() in self.CAPTURE_EXTENSIONS:
                                await self.processFile(NormalizeCapturePath(path))

                        # 消えたファイルは、通信エラーと見分けるため、一括スキャンで全体を列挙してから確定する
                        has_deleted = any(change == Change.deleted for change, _ in changes)
                        if has_deleted is True and not self.scan_lock.locked():
                            await self.runBatchScan(local_roots)

                except OSError as ex:
                    logging.warning('Capture watcher failed; retrying.', exc_info=ex)
                    await asyncio.sleep(5)

        async def Poll() -> None:
            """
            ネットワークドライブの保存先を、設定した間隔で一括スキャンする (間隔が 0 の場合は何もしない)
            """

            interval = Config().capture.upload_folders_polling_interval
            if len(network_roots) == 0 or interval == 0:
                return

            while True:
                await asyncio.sleep(interval * 60)
                if not self.scan_lock.locked():
                    await self.runBatchScan(network_roots)

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
        files = await CaptureFile.filter(capture_id=capture_id).order_by('file_path')
        async with AsyncExitStack() as stack:

            # 削除の途中で一括スキャンが登録し直さないよう、すべての場所のロックを取る
            for file in files:
                await stack.enter_async_context(self.getPathLock(file.file_path))

            # すべての場所のファイルを削除する
            for file in files:
                try:
                    # 登録したあとに別の内容に置き換わっていたら、削除せずに中断する
                    file_stat = await anyio.Path(file.file_path).stat()
                    is_replaced = (
                        file_stat.st_size != file.file_size or
                        datetime.fromtimestamp(file_stat.st_ctime, JST) != file.file_created_at or
                        datetime.fromtimestamp(file_stat.st_mtime, JST) != file.file_modified_at
                    )
                    if is_replaced is True:
                        return False

                    # 移動の照合はファイル名・サイズ・更新日時だけで行うため、同じ属性の別の画像に付け替わっていることがある
                    ## 取り消せない削除の前に中身のハッシュを照合し、別の画像なら読んだ内容で登録し直して、削除を中断する
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

            # 削除の途中で場所が追加されていたら、DB の行は残す
            async with transactions.in_transaction():
                current_ids = set(await CaptureFile.filter(capture_id=capture_id).values_list('id', flat=True))
                if current_ids != {file.id for file in files}:
                    return False
                await Capture.filter(id=capture_id).delete()

            self.invalidateSections()

        return True
