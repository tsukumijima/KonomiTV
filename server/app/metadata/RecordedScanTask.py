
from __future__ import annotations

import asyncio
import concurrent.futures
import pathlib
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Literal, cast
from zoneinfo import ZoneInfo

import anyio
from fastapi import HTTPException, status
from tortoise import transactions
from watchfiles import Change, awatch

from app import logging, schemas
from app.config import Config
from app.constants import THUMBNAILS_DIR
from app.metadata.CMSectionsDetector import CMSectionsDetector
from app.metadata.KeyFrameAnalyzer import KeyFrameAnalyzer
from app.metadata.MetadataAnalyzer import MetadataAnalyzer
from app.metadata.ThumbnailGenerator import ThumbnailGenerator
from app.models.Channel import Channel
from app.models.RecordedProgram import RecordedProgram
from app.models.RecordedVideo import RecordedVideo
from app.utils.DriveIOLimiter import DriveIOLimiter
from app.utils.ProcessLimiter import ProcessLimiter


@dataclass(slots=True)
class FileRecordingInfo:
    """
    - last_modified: ファイルの最終更新日時
    - last_checked: ファイルの最終チェック日時
    - file_size: ファイルのサイズ
    - mtime_continuous_start_at: ファイルの最終更新日時が継続的に更新されている場合の継続更新の開始日時
    """
    last_modified: datetime
    last_checked: datetime
    file_size: int
    mtime_continuous_start_at: datetime | None


@dataclass(slots=True)
class RecordedVideoSummary:
    """
    RecordedScanTask.runBatchScan() 内でのメモリ使用量を抑えるため、RecordedVideo のうち必要最低限の情報のみを保持する軽量データ構造
    slots=True を指定し、メモリ使用量を抑える
    """

    id: int
    file_path: str
    created_at: datetime
    recorded_program_id: int
    status: Literal['Recording', 'Recorded', 'AnalysisFailed']
    file_created_at: datetime
    file_modified_at: datetime
    file_size: int
    file_hash: str


class RecordedScanTask:
    """
    録画フォルダの監視とメタデータの DB への同期を行うタスク
    サーバーの起動中は常時稼働し続け、以下の処理を担う
    - サーバー起動時の録画フォルダの一括スキャン・同期
    - 録画フォルダ以下のファイルシステム変更の監視を開始し、変更があれば随時メタデータを解析後、DB に永続化
    - 録画中ファイルの状態管理
    """

    # シングルトンインスタンス
    __instance: ClassVar[RecordedScanTask | None] = None

    # スキャン対象の拡張子
    SCAN_TARGET_EXTENSIONS: ClassVar[list[str]] = ['.ts', '.m2t', '.m2ts', '.mts', '.mp4']

    # 録画中ファイルの更新イベントを間引く間隔 (ログ出力用) (秒)
    UPDATE_THROTTLE_SECONDS: ClassVar[int] = 30

    # 録画完了と判断するまでの無更新時間 (秒)
    RECORDING_COMPLETE_SECONDS: ClassVar[int] = 15

    # 録画中と判断する最大の経過時間 (秒)
    RECORDING_MAX_AGE_SECONDS: ClassVar[int] = 300  # 5分

    # 録画中ファイルの最小データ長 (秒)
    MINIMUM_RECORDING_SECONDS: ClassVar[int] = 60

    # 継続更新を録画中と判断する最小時間 (秒)
    CONTINUOUS_UPDATE_THRESHOLD_SECONDS: ClassVar[int] = 60

    # 継続更新を強制的に完了とする時間 (秒)
    CONTINUOUS_UPDATE_MAX_SECONDS: ClassVar[int] = 86400  # 24時間

    # 既知のハッシュ衝突が発生しうる file_hash の集合
    KNOWN_COLLISION_FILE_HASHES: ClassVar[set[str]] = {
        'd1dd210d6b1312cb342b56d02bd5e651',
    }


    def __new__(cls) -> RecordedScanTask:
        """
        シングルトンインスタンスを作成または取得する
        既にインスタンスが存在する場合はそれを返し、存在しない場合は新規作成する

        Returns:
            RecordedScanTask: シングルトンインスタンス
        """

        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance


    def __init__(self) -> None:
        """
        録画フォルダの監視タスクを初期化する
        """

        # 初期化済みの場合は何もしない
        if hasattr(self, '_initialized') and self._initialized:
            return

        # 設定を読み込む
        self.config = Config()
        self.recorded_folders = [anyio.Path(folder) for folder in self.config.video.recorded_folders]

        # 録画中ファイルの状態管理
        self._recording_files: dict[anyio.Path, FileRecordingInfo] = {}

        # タスクの状態管理
        self._is_running = False
        self._task: asyncio.Task[None] | None = None

        # 録画フォルダ以下の一括スキャンを実行中かどうか
        self._is_batch_scan_running = False

        # バックグラウンドタスクの状態管理
        self._background_tasks: dict[anyio.Path, asyncio.Task[None]] = {}

        # シンボリックリンクの元パスと実体パスのマッピング
        self._symlink_path_map: dict[str, str] = {}
        self._symlink_path_map_lock = asyncio.Lock()

        # ファイルパスごとのロックを管理する辞書
        self._file_locks: dict[anyio.Path, asyncio.Lock] = {}
        # _file_locks 辞書自体へのアクセスを保護するためのロック
        self._file_locks_dict_lock = asyncio.Lock()

        # 初期化済みフラグをセット
        self._initialized = True


    async def start(self) -> None:
        """
        録画フォルダの監視タスクを開始する
        このメソッドはサーバー起動時に app.py から自動的に呼ばれ、サーバーの起動中は常時稼働し続ける
        """

        # 既に実行中の場合は何もしない
        if self._is_running:
            return
        self._is_running = True

        # バックグラウンドタスクとして実行
        self._task = asyncio.create_task(self.run())


    async def stop(self) -> None:
        """
        録画フォルダの監視タスクを停止する
        このメソッドはサーバー終了時に app.py から自動的に呼ばれる
        """

        # 既に停止中の場合は何もしない
        if not self._is_running:
            return

        # 実行中タスクを停止
        self._is_running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


    async def run(self) -> None:
        """
        録画フォルダ以下の一括スキャンと DB への同期と録画フォルダ以下のファイルシステム変更の監視を開始し、
        変更があれば随時メタデータを解析後、DB に永続化する
        このメソッドは start() 経由でサーバー起動時に app.py から自動的に呼ばれ、サーバーの起動中は常時稼働し続ける
        """

        try:
            # runBatchScan() が完了しなくても新しく録画されたファイルの監視を開始するため、同時に実行する
            await asyncio.gather(
                # サーバー起動時の一括スキャン・同期を実行
                self.runBatchScan(),
                # 録画フォルダの監視を開始
                self.watchRecordedFolders(),
            )
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            logging.error('Error in RecordedScanTask:', exc_info=ex)
        finally:
            self._is_running = False


    async def runBatchScan(self) -> None:
        """
        録画フォルダ以下の一括スキャンと DB への同期を実行する
        - 録画フォルダ内の全 TS ファイルをスキャン
        - 追加・変更があったファイルのみメタデータを解析し、DB に永続化
        - 存在しない録画ファイルに対応するレコードを一括削除
        """

        # 既に一括スキャンを実行中の場合は HTTPException を発生させる
        # API から手動で一括スキャンを実行した際に重複して実行されないようにするためのバリデーション
        if self._is_batch_scan_running:
            raise HTTPException(
                status_code = status.HTTP_429_TOO_MANY_REQUESTS,
                detail = 'Batch scan of recording folders is already running',
            )

        logging.info('Batch scan of recording folders has been started.')
        self._is_batch_scan_running = True

        # 現在登録されている全ての RecordedVideo レコードの情報をキャッシュ
        ## すべての情報をキャッシュすると key_frames フィールドのデータ量が大きすぎてメモリとディスク I/O を大量に食うため、
        ## 必要最低限の情報のみをキャッシュする
        logging.info('Gathering all recorded video records...')
        all_video_rows = await RecordedVideo.all().values(
            'id',
            'file_path',
            'created_at',
            'recorded_program_id',
            'status',
            'file_created_at',
            'file_modified_at',
            'file_size',
            'file_hash',
        )
        videos_by_path: dict[str, list[RecordedVideoSummary]] = {}
        videos_to_keep: list[RecordedVideoSummary] = []  # 保持するレコードのリスト
        for index, row in enumerate(all_video_rows, start=1):
            recorded_video_summary = RecordedVideoSummary(
                id = row['id'],
                file_path = row['file_path'],
                created_at = row['created_at'],
                recorded_program_id = row['recorded_program_id'],
                status = row['status'],
                file_created_at = row['file_created_at'],
                file_modified_at = row['file_modified_at'],
                file_size = row['file_size'],
                file_hash = row['file_hash'],
            )
            if recorded_video_summary.file_path not in videos_by_path:
                videos_by_path[recorded_video_summary.file_path] = []
            videos_by_path[recorded_video_summary.file_path].append(recorded_video_summary)
            if index % 100 == 0:
                # 起動時にイベントループが他のタスクを処理できるよう定期的に制御を返す
                await asyncio.sleep(0)

        # 同一ファイルパスに対応するレコードが複数存在する場合、最新のものを保持して残りを削除する
        ## 重複削除処理をトランザクション配下で実行
        logging.info('Checking for duplicate recorded video records...')
        duplicates_found = False
        total_deleted_count = 0
        async with transactions.in_transaction():
            for index, (file_path, videos) in enumerate(videos_by_path.items(), start=1):
                if len(videos) > 1:
                    duplicates_found = True
                    logging.warning(f'{file_path}: Found {len(videos)} duplicate records. Keeping the latest one.')
                    # created_at でソートして最新のレコードを特定
                    videos.sort(key=lambda v: v.created_at, reverse=True)
                    latest_video = videos[0]
                    videos_to_keep.append(latest_video)  # 最新のものを保持リストに追加
                    # 最新以外のレコードを削除
                    for video_to_delete in videos[1:]:
                        try:
                            # RecordedProgram を削除 (CASCADE により RecordedVideo も削除される)
                            await RecordedProgram.filter(id=video_to_delete.recorded_program_id).delete()
                            logging.info(
                                f'{file_path}: Deleted duplicate record. [deleted recorded_program_id: {video_to_delete.recorded_program_id}] '
                                f'[kept recorded_program_id: {latest_video.recorded_program_id}]'
                            )
                        except Exception as ex_del:
                            logging.error(
                                f'{file_path}: Failed to delete duplicate record. [deleted recorded_program_id: {video_to_delete.recorded_program_id}]',
                                exc_info=ex_del,
                            )
                    # 削除対象のレコード数をカウント
                    deleted_count = len(videos) - 1  # -1 は最新のレコードを除いた数
                    total_deleted_count += deleted_count
                else:
                    # 重複がない場合も保持リストに追加
                    videos_to_keep.append(videos[0])
                if index % 50 == 0:
                    # 重複チェックがループを占有し続けないよう適宜制御を返す
                    await asyncio.sleep(0)
        if duplicates_found:
            logging.info(f'Duplicate record cleanup finished. Total {total_deleted_count} duplicate records were deleted.')
        else:
            logging.info('No duplicate records found.')

        # 現在登録されている全ての RecordedVideo レコードをキャッシュ
        ## 重複削除処理で保持すると判断されたレコードのみを使う
        existing_db_recorded_videos = {}
        for video in videos_to_keep:
            # 既存レコードのファイルパスもシンボリックリンクを解決して正規化する
            canonical_path = await self.resolveRecordedPath(anyio.Path(video.file_path))
            video.file_path = str(canonical_path)
            existing_db_recorded_videos[anyio.Path(video.file_path)] = video

        # 各録画フォルダをスキャン
        logging.info('Scanning recorded folders...')
        processed_canonical_paths: set[str] = set()
        for folder in self.recorded_folders:
            async for file_path in folder.rglob('*'):
                try:
                    # Mac の metadata ファイルをスキップ
                    if file_path.name.startswith('._'):
                        continue
                    # シンボリックリンクを含むパスは実体に解決して処理する
                    canonical_path = await self.resolveRecordedPath(file_path)
                    original_path_str = str(file_path)
                    canonical_path_str = str(canonical_path)
                    # シンボリックリンクのマッピングを更新する
                    await self.__updateSymlinkMapping(original_path_str, canonical_path_str)
                    if await canonical_path.is_dir():
                        continue
                    # 対象拡張子のファイル以外をスキップ
                    if canonical_path.suffix.lower() not in self.SCAN_TARGET_EXTENSIONS:
                        continue
                    # 録画ファイルが確実に存在することを確認する
                    ## 環境次第では、稀に glob で取得したファイルが既に存在しなくなっているケースがある
                    if not await self.isFileExists(canonical_path):
                        continue
                    if canonical_path_str in processed_canonical_paths:
                        continue
                    processed_canonical_paths.add(canonical_path_str)

                    # 見つかったファイルを処理
                    await self.processRecordedFile(
                        file_path = canonical_path,
                        original_path = file_path,
                        existing_db_recorded_videos = existing_db_recorded_videos,
                    )
                except Exception as ex:
                    logging.error(f'{file_path}: Failed to process recorded file:', exc_info=ex)

        # 存在しない録画ファイルに対応するレコードを一括削除
        ## トランザクション配下に入れることでパフォーマンスが向上する
        logging.info('Deleting records for non-existent files...')
        async with transactions.in_transaction():
            for index, (file_path, existing_recorded_video_summary) in enumerate(existing_db_recorded_videos.items(), start=1):
                # ファイルの存在確認を非同期に行う
                if not await self.isFileExists(file_path):
                    # RecordedVideo の親テーブルである RecordedProgram を削除すると、
                    # CASCADE 制約により RecordedVideo も同時に削除される (Channel は親テーブルにあたるため削除されない)
                    await RecordedProgram.filter(id=existing_recorded_video_summary.recorded_program_id).delete()
                    logging.info(f'{file_path}: Deleted record for non-existent file.')
                if index % 50 == 0:
                    # 既存レコードの走査が長時間化しないよう適宜制御を返す
                    await asyncio.sleep(0)

        # DB に存在する全ての RecordedVideo レコードのハッシュを取得
        logging.info('Gathering all recorded video hashes...')
        db_recorded_video_hashes = set(
            cast(list[str], await RecordedVideo.all().values_list('file_hash', flat=True))
        )

        # サムネイルフォルダ内の全ファイルをスキャンし、不要なサムネイルファイルを削除
        logging.info('Deleting orphaned thumbnail files...')
        thumbnails_dir = anyio.Path(str(THUMBNAILS_DIR))
        if await thumbnails_dir.is_dir():
            async for thumbnail_path in thumbnails_dir.glob('*'):
                try:
                    # .git から始まるファイルは無視
                    if thumbnail_path.name.startswith('.git'):
                        continue

                    # ファイル名からハッシュを抽出
                    ## ファイル名は "{hash}.webp" または "{hash}_tile.webp" の形式
                    ## JPEG フォールバックの場合は ".jpg" の可能性もある
                    file_name = thumbnail_path.stem
                    if file_name.endswith('_tile'):
                        file_hash = file_name[:-5]  # "_tile" を除去
                    else:
                        file_hash = file_name

                    # DB に存在しないハッシュのファイルを削除
                    if file_hash not in db_recorded_video_hashes:
                        await thumbnail_path.unlink()
                        logging.info(f'{thumbnail_path.name}: Deleted orphaned thumbnail file.')
                except Exception as ex:
                    logging.error(f'{thumbnail_path}: Error deleting orphaned thumbnail file:', exc_info=ex)

        # かつてのバグで RecordedVideo.file_hash が衝突している録画ファイルのメタデータを再解析する
        ## トランザクション配下に入れることでパフォーマンスが向上する
        ## ref: https://github.com/tsukumijima/KonomiTV/commit/92e8630f41b6440ebd10defa5fdde1489ac7376a
        async with transactions.in_transaction():
            collision_videos = await RecordedVideo.filter(
                file_hash__in=list(self.KNOWN_COLLISION_FILE_HASHES),
            ).all()
            processed_collision_paths: set[str] = set()
            if len(collision_videos) > 0:
                logging.info(f'Found {len(collision_videos)} videos affected by known hash collisions. Reanalyzing...')
                for collision_video in collision_videos:
                    file_path_str = collision_video.file_path
                    # 既に処理済みのファイルはスキップ
                    if file_path_str in processed_collision_paths:
                        continue
                    # 録画中のファイルは今後の解析に任せる
                    if collision_video.status == 'Recording':
                        continue
                    file_path = anyio.Path(file_path_str)
                    # ファイルが存在しない場合はスキップ
                    if not await self.isFileExists(file_path):
                        continue
                    try:
                        # メタデータ再解析を実行
                        logging.info(f'{file_path}: Reanalyzing due to known hash collision ({collision_video.file_hash}).')
                        await self.processRecordedFile(
                            file_path = file_path,
                            force_update = True,
                        )
                        # 処理済みファイルに追加
                        processed_collision_paths.add(file_path_str)
                        logging.info(f'{file_path}: Reanalysis completed.')
                    except Exception as ex:
                        logging.error(f'{file_path}: Failed to reanalyze known hash collision file:', exc_info=ex)

        logging.info('Batch scan of recording folders has been completed.')
        self._is_batch_scan_running = False


    async def processRecordedFile(
        self,
        file_path: anyio.Path,
        original_path: anyio.Path | None = None,
        existing_db_recorded_videos: dict[anyio.Path, RecordedVideoSummary] | None = None,
        force_update: bool = False,
        wait_background_analysis: bool = False,
    ) -> None:
        """
        指定された録画ファイルのメタデータを解析し、DB に永続化する
        既に当該ファイルの情報が DB に登録されており、ファイル内容に変更がない場合は何も行われない

        Args:
            file_path (anyio.Path): 処理対象のファイルパス
            original_path (anyio.Path | None): シンボリックリンクなどで取得した元のファイルパス
            existing_db_recorded_videos (dict[anyio.Path, RecordedVideoSummary] | None): 既に DB に永続化されている録画ファイルパスと RecordedVideo のサマリーデータのマッピング
                (ファイル変更イベントから呼ばれた場合、watchfiles 初期化時に取得した全レコードと今で状態が一致しているとは限らないため、None が入る)
            force_update (bool): 既に DB に登録されている録画ファイルのメタデータを強制的に再解析するかどうか (デフォルト: False)
            wait_background_analysis (bool): バックグラウンド解析が完了するまで待つかどうか (デフォルト: False)
        """

        # ファイルパスに対応するロックを取得または作成
        file_path = await self.resolveRecordedPath(file_path)
        file_path_str = str(file_path)
        original_path_str = str(original_path) if original_path is not None else None
        async with self._file_locks_dict_lock:
            if file_path not in self._file_locks:
                self._file_locks[file_path] = asyncio.Lock()
            file_lock = self._file_locks[file_path]

        # 同一ファイルパスへの DB レコード操作を排他制御する
        async with file_lock:
            try:
                # 万が一この時点でファイルが存在しない場合はスキップ
                # ファイル変更イベント発火後に即座にファイルが削除される可能性も考慮
                if not await self.isFileExists(file_path):
                    logging.warning(f'{file_path}: File does not exist after acquiring lock! ignored.')
                    # ロック管理辞書から不要になったロックを削除
                    async with self._file_locks_dict_lock:
                        if file_path in self._file_locks and not file_lock.locked():
                           self._file_locks.pop(file_path, None)
                    return

                # ファイルの状態をチェック
                stat = await file_path.stat()
                now = datetime.now(tz=ZoneInfo('Asia/Tokyo'))
                file_size = stat.st_size
                file_created_at = datetime.fromtimestamp(stat.st_ctime, tz=ZoneInfo('Asia/Tokyo'))
                file_modified_at = datetime.fromtimestamp(stat.st_mtime, tz=ZoneInfo('Asia/Tokyo'))

                # 全く録画できていない0バイトのファイルをスキップ
                if file_size == 0:
                    logging.warning(f'{file_path}: File size is 0. ignored.')
                    return

                # シンボリックリンク経由で検出した場合は元パスと実体パスのマッピングを保持する
                if original_path_str is not None:
                    await self.__updateSymlinkMapping(original_path_str, file_path_str)

                # 同じファイルパスの既存レコードのサマリーがあれば取り出す
                if existing_db_recorded_videos is not None:
                    existing_recorded_video_summary = existing_db_recorded_videos.pop(file_path, None)
                    if existing_recorded_video_summary is None and original_path_str is not None:
                        existing_recorded_video_summary = existing_db_recorded_videos.pop(anyio.Path(original_path_str), None)
                else:
                    existing_recorded_video_summary = None

                # この時点でサマリーがない場合、DB に同一ファイルパスのレコードがないか最小限のカラムで取得する
                ## ファイル変更イベントから呼ばれた場合は existing_db_recorded_videos は None となるが、
                ## DB には同一ファイルパスのレコードが存在する可能性がある
                if existing_recorded_video_summary is None:
                    query_paths = [file_path_str]
                    if original_path_str is not None and original_path_str not in query_paths:
                        query_paths.append(original_path_str)
                    summary_rows = await RecordedVideo.filter(
                        file_path__in=query_paths
                    ).values(
                        'id',
                        'file_path',
                        'created_at',
                        'recorded_program_id',
                        'status',
                        'file_created_at',
                        'file_modified_at',
                        'file_size',
                        'file_hash',
                    )
                    if len(summary_rows) > 0:
                        row = summary_rows[0]
                        existing_recorded_video_summary = RecordedVideoSummary(
                            id = row['id'],
                            file_path = row['file_path'],
                            created_at = row['created_at'],
                            recorded_program_id = row['recorded_program_id'],
                            status = row['status'],
                            file_created_at = row['file_created_at'],
                            file_modified_at = row['file_modified_at'],
                            file_size = row['file_size'],
                            file_hash = row['file_hash'],
                        )
                        existing_recorded_video_summary.file_path = file_path_str

                # 同じファイルパスの既存レコードがあり、ファイルの基本情報（作成日時、更新日時、サイズ）が前回と一致した場合、
                # ファイル内容は変更されておらず、レコード内容は更新不要と判断してスキップ
                ## こうすることで、録画済みファイルに対しては HDD への I/O 負荷が高いハッシュ算出やメタデータ解析処理を省略できる
                ## 万が一前回実行時からファイルサイズや最終更新日時の変更を伴わずに録画が完了した場合に状態を適切に反映できるよう、録画中はスキップしない
                if (force_update is False and
                    existing_recorded_video_summary is not None and
                    existing_recorded_video_summary.status == 'Recorded'):
                    if (existing_recorded_video_summary.file_created_at == file_created_at and
                        existing_recorded_video_summary.file_modified_at == file_modified_at and
                        existing_recorded_video_summary.file_size == file_size):
                        # logging.debug(f'{file_path}: File metadata unchanged, skipping...')
                        return

                # 現在録画中とマークされているファイルの処理
                is_recording = file_path in self._recording_files
                if is_recording:
                    # 既に DB に登録済みで録画中の場合は再解析しない
                    if (existing_recorded_video_summary is not None and
                        existing_recorded_video_summary.status == 'Recording'):
                        return
                    # まだ DB に登録されていない＆ファイルサイズが前回から変化していない場合
                    recording_info = self._recording_files[file_path]
                    last_size = recording_info.file_size
                    mtime_continuous_start_at = recording_info.mtime_continuous_start_at
                    if file_size == last_size:
                        # 最終更新日時の継続更新中でない場合はスキップ
                        if mtime_continuous_start_at is None:
                            logging.warning(f'{file_path}: File is not recording. ignored.')
                            return
                        # 最終更新日時の継続更新が1分未満の場合もスキップ
                        continuous_duration = (now - mtime_continuous_start_at).total_seconds()
                        if continuous_duration < self.CONTINUOUS_UPDATE_THRESHOLD_SECONDS:
                            return
                        # 最終更新日時の継続更新が24時間を超えた場合は何かがおかしい可能性が高いため打ち切る
                        if continuous_duration >= self.CONTINUOUS_UPDATE_MAX_SECONDS:
                            logging.warning(f'{file_path}: Continuous mtime updates for {continuous_duration:.1f} seconds. (> {self.CONTINUOUS_UPDATE_MAX_SECONDS}s) ignored.')
                            return
                        # ここまで到達した時点で（ファイルサイズこそ変化していないが）最終更新日時の推移から1分以上ファイル内容の更新が続いているとみなし、
                        # 後続の処理でメタデータを解析し、解析に成功次第 DB に録画中として登録する
                        # 録画開始前にファイルアロケーションを行う録画予約ソフトでは、録画中も表面上ファイルサイズが変化しない問題への対処
                        pass

                # ProcessPoolExecutor を使い、別プロセス上でメタデータを解析
                ## メタデータ解析処理は実装上同期 I/O で実装されており、また CPU-bound な処理のため、別プロセスで実行している
                ## with 文で括ることで、with 文を抜けたときに ProcessPoolExecutor がクリーンアップされるようにする
                ## さもなければサーバーの終了後もプロセスが残り続けてゾンビプロセス化し、メモリリークを引き起こしてしまう
                loop = asyncio.get_running_loop()
                analyzer = MetadataAnalyzer(pathlib.Path(str(file_path)))  # anyio.Path -> pathlib.Path に変換
                try:
                    with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
                        recorded_program = await loop.run_in_executor(executor, analyzer.analyze)
                    if recorded_program is None:
                        logging.error(f'{file_path}: Failed to analyze metadata.')
                        # メタデータ解析に失敗したがこの時点ですでに DB にエントリが存在している場合は、UI から判別できるようステータスを更新する
                        ## 本来メタデータ解析に失敗した録画ファイルは DB には登録されないが、「録画中は問題なく解析できていたが、録画完了後に解析できなくなった」
                        ## といったシチュエーションも稀に考えられなくもないため、そうした場合の保険として実装した
                        if existing_recorded_video_summary is not None:
                            await RecordedVideo.filter(id=existing_recorded_video_summary.id).update(status='AnalysisFailed')
                            existing_recorded_video_summary.status = 'AnalysisFailed'
                        self._recording_files.pop(file_path, None)  # もし録画中扱いであればここで削除
                        return
                except Exception as ex:
                    logging.error(f'{file_path}: Error analyzing metadata:', exc_info=ex)
                    # メタデータ解析中に例外が発生した場合も、この時点ですでに DB にエントリが存在している場合は、UI から判別できるようステータスを更新する
                    if existing_recorded_video_summary is not None:
                        await RecordedVideo.filter(id=existing_recorded_video_summary.id).update(status='AnalysisFailed')
                        existing_recorded_video_summary.status = 'AnalysisFailed'
                    self._recording_files.pop(file_path, None)  # もし録画中扱いであればここで削除
                    return

                # 60秒未満のファイルは録画失敗または切り抜きとみなしてスキップ
                # 録画中だがまだ60秒に満たない場合、今後のファイル変更イベント発火時に60秒を超えていれば録画中ファイルとして処理される
                if recorded_program.recorded_video.duration < self.MINIMUM_RECORDING_SECONDS:
                    logging.debug(f'{file_path}: This file is too short. (duration {recorded_program.recorded_video.duration:.1f}s < {self.MINIMUM_RECORDING_SECONDS}s) Skipped.')
                    return

                # 前回の DB 取得からメタデータ解析までの間に他のタスクがレコードを作成/更新している可能性があるため、
                # メタデータ解析後に再度ファイルパスに対応するレコードを取得する
                existing_db_recorded_video_after_analyze = await RecordedVideo.get_or_none(
                    file_path=file_path_str
                ).select_related('recorded_program', 'recorded_program__channel')
                if existing_db_recorded_video_after_analyze is None and original_path_str is not None:
                    existing_db_recorded_video_after_analyze = await RecordedVideo.get_or_none(
                        file_path=original_path_str
                    ).select_related('recorded_program', 'recorded_program__channel')

                # 同じファイルパスの既存レコードがあり、先ほど計算した最新のハッシュと変わっていない場合は、レコード内容は更新不要と判断してスキップ
                ## 万が一前回実行時からファイルサイズや最終更新日時の変更を伴わずに録画が完了した場合に状態を適切に反映できるよう、録画中はスキップしない
                if (force_update is False and
                    existing_db_recorded_video_after_analyze is not None and
                    existing_db_recorded_video_after_analyze.status == 'Recorded' and
                    existing_db_recorded_video_after_analyze.file_hash == recorded_program.recorded_video.file_hash):
                    return

                # 録画中のファイルとして処理
                ## 他ドライブからファイルコピー中のファイルも、実際の録画処理より高速に書き込まれるだけで随時書き込まれることに変わりはないので、
                ## 録画中として判断されることがある（その場合、ファイルコピーが完了した段階で「録画完了」扱いとなる）
                if is_recording or (now - file_modified_at).total_seconds() < self.RECORDING_COMPLETE_SECONDS:
                    # status を Recording に設定
                    recorded_program.recorded_video.status = 'Recording'
                    # 状態を更新
                    self._recording_files[file_path] = FileRecordingInfo(
                        last_modified = file_modified_at,
                        last_checked = now,
                        file_size = file_size,
                        mtime_continuous_start_at = file_modified_at,  # 初回は必ず mtime_continuous_start_at を設定
                    )
                    logging.debug(f'{file_path}: This file is recording or copying. (duration {recorded_program.recorded_video.duration:.1f}s >= {self.MINIMUM_RECORDING_SECONDS}s)')
                else:
                    # status を Recorded に設定
                    # MetadataAnalyzer 側で既に Recorded に設定されているが、念のため
                    recorded_program.recorded_video.status = 'Recorded'
                    # 録画完了後のバックグラウンド解析タスクを開始
                    if file_path not in self._background_tasks:
                        task = asyncio.create_task(self.__runBackgroundAnalysis(recorded_program))
                        self._background_tasks[file_path] = task

                # DB に永続化
                # メタデータ解析後の最新のデータベース情報を使う
                await self.__saveRecordedMetadataToDB(recorded_program, existing_db_recorded_video_after_analyze)
                logging.info(f'{file_path}: {"Updated" if existing_db_recorded_video_after_analyze else "Saved"} metadata to DB. (status: {recorded_program.recorded_video.status})')

                # wait_background_analysis が True の場合のみ、バックグラウンド解析タスクが完了するまで待つ
                # 録画番組メタデータ再解析 API では、API レスポンスの返却をもってメタデータ再解析が完全に完了したことをユーザーに伝える必要があるため
                if wait_background_analysis is True and file_path in self._background_tasks:
                    await self._background_tasks[file_path]

            except Exception as ex:
                logging.error(f'{file_path}: Error processing file inside lock:', exc_info=ex)
            finally:
                # 不要になったロックを管理辞書から削除 (ロックが解放された後に行う)
                async with self._file_locks_dict_lock:
                     if file_path in self._file_locks and not file_lock.locked():
                        self._file_locks.pop(file_path, None)


    @staticmethod
    async def isFileExists(file_path: anyio.Path) -> bool:
        """
        ファイルが存在し、通常のファイルであるかを安全にチェックする。
        PermissionError やその他のファイルアクセスエラーが発生した場合は False を返す。

        Args:
            file_path (anyio.Path): チェックするファイルパス

        Returns:
            bool: ファイルが存在し、通常のファイルであるかどうか
        """
        try:
            return await file_path.is_file()
        except PermissionError:
            logging.warning(f'{file_path}: Permission denied when checking file.')
            return False
        except FileNotFoundError:
            return False
        except OSError as e:
            logging.warning(f'{file_path}: OSError during is_file() check:', exc_info=e)
            return False


    @staticmethod
    async def resolveRecordedPath(file_path: anyio.Path) -> anyio.Path:
        """
        シンボリックリンクを解決して実体のパスを取得する。解決に失敗した場合は元のパスを返す。

        Args:
            file_path (anyio.Path): ファイルパス

        Returns:
            anyio.Path: シンボリックの参照先である実体のパス
        """
        try:
            return await file_path.resolve()
        except (OSError, RuntimeError) as ex:
            logging.warning(f'{file_path}: Failed to resolve symlink. Using original path:', exc_info=ex)
            return file_path


    async def __updateSymlinkMapping(self, original_path_str: str | None, canonical_path_str: str) -> None:
        """
        シンボリックリンクの元パスと実体パスのマッピングを管理する。

        Args:
            original_path_str (str | None): シンボリックリンクの元パス
            canonical_path_str (str): シンボリックリンクの実体パス
        """
        if original_path_str is None:
            return
        async with self._symlink_path_map_lock:
            if original_path_str == canonical_path_str:
                self._symlink_path_map.pop(original_path_str, None)
            else:
                self._symlink_path_map[original_path_str] = canonical_path_str


    @staticmethod
    async def __saveRecordedMetadataToDB(
        recorded_program: schemas.RecordedProgram,
        existing_db_recorded_video: RecordedVideo | None,
    ) -> None:
        """
        録画ファイルのメタデータ解析結果を DB に保存する
        既存レコードがある場合は更新し、ない場合は新規作成する

        Args:
            recorded_program (schemas.RecordedProgram): 保存する録画番組情報
            existing_db_recorded_video (RecordedVideo | None): 既に DB に永続化されている録画ファイルの RecordedVideo レコード
        """

        # トランザクション配下に入れることでパフォーマンスが向上する
        async with transactions.in_transaction():

            # Channel の保存（まだ当該チャンネルが DB に存在しない場合のみ）
            db_channel = None
            if recorded_program.channel is not None:
                db_channel = await Channel.get_or_none(id=recorded_program.channel.id)
                if db_channel is None:
                    db_channel = Channel()
                    db_channel.id = recorded_program.channel.id
                    db_channel.display_channel_id = recorded_program.channel.display_channel_id
                    db_channel.network_id = recorded_program.channel.network_id
                    db_channel.service_id = recorded_program.channel.service_id
                    db_channel.transport_stream_id = recorded_program.channel.transport_stream_id
                    db_channel.remocon_id = recorded_program.channel.remocon_id
                    db_channel.channel_number = recorded_program.channel.channel_number
                    db_channel.type = recorded_program.channel.type
                    db_channel.name = recorded_program.channel.name
                    db_channel.jikkyo_force = recorded_program.channel.jikkyo_force
                    db_channel.is_subchannel = recorded_program.channel.is_subchannel
                    db_channel.is_radiochannel = recorded_program.channel.is_radiochannel
                    db_channel.is_watchable = recorded_program.channel.is_watchable
                    await db_channel.save()

            # RecordedProgram の保存または更新
            if existing_db_recorded_video is not None:
                db_recorded_program = existing_db_recorded_video.recorded_program
            else:
                db_recorded_program = RecordedProgram()

            # RecordedProgram の属性を設定 (id, created_at, updated_at は自動生成のため指定しない)
            db_recorded_program.recording_start_margin = recorded_program.recording_start_margin
            db_recorded_program.recording_end_margin = recorded_program.recording_end_margin
            db_recorded_program.is_partially_recorded = recorded_program.is_partially_recorded
            db_recorded_program.channel = db_channel  # type: ignore
            db_recorded_program.network_id = recorded_program.network_id
            db_recorded_program.service_id = recorded_program.service_id
            db_recorded_program.event_id = recorded_program.event_id
            db_recorded_program.series_id = recorded_program.series_id
            db_recorded_program.series_broadcast_period_id = recorded_program.series_broadcast_period_id
            db_recorded_program.title = recorded_program.title
            db_recorded_program.series_title = recorded_program.series_title
            db_recorded_program.episode_number = recorded_program.episode_number
            db_recorded_program.subtitle = recorded_program.subtitle
            db_recorded_program.description = recorded_program.description
            db_recorded_program.detail = recorded_program.detail
            db_recorded_program.start_time = recorded_program.start_time
            db_recorded_program.end_time = recorded_program.end_time
            db_recorded_program.duration = recorded_program.duration
            db_recorded_program.is_free = recorded_program.is_free
            db_recorded_program.genres = recorded_program.genres
            db_recorded_program.primary_audio_type = recorded_program.primary_audio_type
            db_recorded_program.primary_audio_language = recorded_program.primary_audio_language
            db_recorded_program.secondary_audio_type = recorded_program.secondary_audio_type
            db_recorded_program.secondary_audio_language = recorded_program.secondary_audio_language
            await db_recorded_program.save()

            # RecordedVideo の保存または更新
            if existing_db_recorded_video is not None:
                db_recorded_video = existing_db_recorded_video
            else:
                db_recorded_video = RecordedVideo()

            # RecordedVideo の属性を設定 (id, created_at, updated_at は自動生成のため指定しない)
            db_recorded_video.recorded_program = db_recorded_program
            db_recorded_video.status = recorded_program.recorded_video.status
            db_recorded_video.file_path = str(recorded_program.recorded_video.file_path)
            db_recorded_video.file_hash = recorded_program.recorded_video.file_hash
            db_recorded_video.file_size = recorded_program.recorded_video.file_size
            db_recorded_video.file_created_at = recorded_program.recorded_video.file_created_at
            db_recorded_video.file_modified_at = recorded_program.recorded_video.file_modified_at
            db_recorded_video.recording_start_time = recorded_program.recorded_video.recording_start_time
            db_recorded_video.recording_end_time = recorded_program.recorded_video.recording_end_time
            db_recorded_video.duration = recorded_program.recorded_video.duration
            db_recorded_video.container_format = recorded_program.recorded_video.container_format
            db_recorded_video.video_codec = recorded_program.recorded_video.video_codec
            db_recorded_video.video_codec_profile = recorded_program.recorded_video.video_codec_profile
            db_recorded_video.video_scan_type = recorded_program.recorded_video.video_scan_type
            db_recorded_video.video_frame_rate = recorded_program.recorded_video.video_frame_rate
            db_recorded_video.video_resolution_width = recorded_program.recorded_video.video_resolution_width
            db_recorded_video.video_resolution_height = recorded_program.recorded_video.video_resolution_height
            db_recorded_video.primary_audio_codec = recorded_program.recorded_video.primary_audio_codec
            db_recorded_video.primary_audio_channel = recorded_program.recorded_video.primary_audio_channel
            db_recorded_video.primary_audio_sampling_rate = recorded_program.recorded_video.primary_audio_sampling_rate
            db_recorded_video.secondary_audio_codec = recorded_program.recorded_video.secondary_audio_codec
            db_recorded_video.secondary_audio_channel = recorded_program.recorded_video.secondary_audio_channel
            db_recorded_video.secondary_audio_sampling_rate = recorded_program.recorded_video.secondary_audio_sampling_rate
            # この時点では CM 区間情報は未解析なので、明示的に未解析を表す None を設定する (デフォルトで None だが念のため)
            # 「解析したが CM 区間がなかった/検出に失敗した」場合、CMSectionsDetector 側で [] が設定される
            db_recorded_video.cm_sections = None
            await db_recorded_video.save()


    async def __runBackgroundAnalysis(self, recorded_program: schemas.RecordedProgram) -> None:
        """
        録画完了後のバックグラウンド解析タスク
        - キーフレーム解析
        - サムネイル生成
        - CM区間検出
        など、時間のかかる処理を非同期に同時実行する

        Args:
            recorded_program (schemas.RecordedProgram): 解析対象の録画番組情報
        """

        # 録画ファイルのパスを anyio.Path に変換
        file_path = anyio.Path(recorded_program.recorded_video.file_path)

        try:
            logging.info(f'{file_path}: Starting background analysis task...')
            # ProcessLimiter で稼働中のバックグラウンドタスクの同時実行数を CPU コア数の 50% に制限
            async with ProcessLimiter.getSemaphore('RecordedScanTask'):
                # DriveIOLimiter で同一 HDD に対してのバックグラウンドタスクの同時実行数を原則1セッションに制限
                async with DriveIOLimiter.getSemaphore(file_path):
                    await asyncio.gather(
                        # 録画ファイルのキーフレーム情報を解析し DB に保存
                        KeyFrameAnalyzer(file_path, recorded_program.recorded_video.container_format).analyzeAndSave(),
                        # 録画ファイルの CM 区間を検出し DB に保存
                        CMSectionsDetector(file_path, recorded_program.recorded_video.duration).detectAndSave(),
                        # シークバー用サムネイルとリスト表示用の代表サムネイルの両方を生成
                        ThumbnailGenerator.fromRecordedProgram(recorded_program).generateAndSave(),
                    )
            logging.info(f'{file_path}: Background analysis task completed.')

        except Exception as ex:
            logging.error(f'{file_path}: Error in background analysis task:', exc_info=ex)
        finally:
            # 完了したタスクを管理対象から削除
            self._background_tasks.pop(file_path, None)


    async def watchRecordedFolders(self) -> None:
        """
        録画フォルダ以下のファイルシステム変更の監視を開始し、変更があれば随時メタデータを解析後、DB に永続化する
        """

        logging.info('Starting file system watch of recording folders.')

        # 監視対象のディレクトリを設定
        watch_paths = [str(path) for path in self.recorded_folders]

        # 録画完了チェック用のタスク
        completion_check_task = asyncio.create_task(self.__checkRecordingCompletion())

        try:
            # watchfiles によるファイル監視
            async for changes in awatch(*watch_paths, recursive=True):
                if not self._is_running:
                    break

                # 変更があったファイルごとに処理
                for change_type, file_path_str in changes:
                    if not self._is_running:
                        break

                    file_path = anyio.Path(file_path_str)
                    # Mac の metadata ファイルをスキップ
                    if file_path.name.startswith('._'):
                        continue
                    # シンボリックリンクを含むパスは実体に解決して処理する
                    canonical_path = await self.resolveRecordedPath(file_path)
                    if await canonical_path.is_dir():
                        continue
                    # 対象拡張子のファイル以外は無視
                    if canonical_path.suffix.lower() not in self.SCAN_TARGET_EXTENSIONS:
                        continue

                    try:
                        # 追加 or 変更イベント
                        if change_type == Change.added or change_type == Change.modified:
                            await self.__handleFileChange(canonical_path, original_file_path=file_path)
                        # 削除イベント
                        elif change_type == Change.deleted:
                            await self.__handleFileDeletion(canonical_path, original_file_path=file_path)
                    except Exception as ex:
                        logging.error(f'{file_path}: Error handling file change:', exc_info=ex)

        except asyncio.CancelledError:
            raise
        except Exception as ex:
            logging.error('Error in file system watch of recording folders:', exc_info=ex)
        finally:
            completion_check_task.cancel()
            try:
                await completion_check_task
            except asyncio.CancelledError:
                pass
            logging.info('File system watch of recording folders has been stopped.')


    async def __handleFileChange(self, file_path: anyio.Path, original_file_path: anyio.Path | None = None) -> None:
        """
        ファイル追加・変更イベントを受け取り、適切な頻度で __processFile() を呼び出す
        - 録画中ファイルの状態管理
        - メタデータ解析のスロットリング
        - 最終更新日時の継続更新検出による録画中判定

        Args:
            file_path (anyio.Path): 解決後のファイルパス
            original_file_path (anyio.Path | None): 監視で検知した元のファイルパス
        """

        try:
            # ファイルの状態をチェック
            stat = await file_path.stat()
            last_modified = datetime.fromtimestamp(stat.st_mtime, tz=ZoneInfo('Asia/Tokyo'))
            now = datetime.now(tz=ZoneInfo('Asia/Tokyo'))
            file_size = stat.st_size

            # 既に録画中とマークされているファイルの処理
            if file_path in self._recording_files:
                recording_info = self._recording_files[file_path]
                last_checked = recording_info.last_checked
                last_size = recording_info.file_size
                mtime_continuous_start_at = recording_info.mtime_continuous_start_at

                # 前回のチェックから UPDATE_THROTTLE_SECONDS 秒以上経過していない場合はログを間引く（状態自体は更新する）
                throttle_event = False
                if (now - last_checked).total_seconds() < self.UPDATE_THROTTLE_SECONDS:
                    throttle_event = True

                # ファイルサイズが変化している場合は継続更新判定をリセット
                if file_size != last_size:
                    mtime_continuous_start_at = None
                    if not throttle_event:
                        logging.debug(f'{file_path}: File size changed.')
                # mtime が変化している場合は継続更新判定を更新
                elif last_modified > recording_info.last_modified:
                    if mtime_continuous_start_at is None:
                        mtime_continuous_start_at = last_modified
                        if not throttle_event:
                            logging.debug(f'{file_path}: File modified time changed.')
                    else:
                        continuous_duration = (now - mtime_continuous_start_at).total_seconds()
                        if continuous_duration >= self.CONTINUOUS_UPDATE_THRESHOLD_SECONDS:
                            if not throttle_event:
                                logging.debug(f'{file_path}: Still recording. (continuous mtime updates for {continuous_duration:.1f} seconds)')

                # 状態を更新
                recording_info.last_modified = last_modified
                # 前回のチェックから UPDATE_THROTTLE_SECONDS 秒以上経過していない場合は前回のチェック日時を使う
                recording_info.last_checked = last_checked if throttle_event else now
                recording_info.file_size = file_size
                recording_info.mtime_continuous_start_at = mtime_continuous_start_at

                # メタデータ解析を実行
                await self.processRecordedFile(file_path, original_file_path)

            # まだ録画中とマークされていないファイルの処理
            else:
                # 最終更新時刻から一定時間以上経過している場合は録画中とみなさない
                # それ以外の場合、今後継続的に追記されていく（＝録画中）可能性もあるので、録画中マークをつけておく
                if (now - last_modified).total_seconds() <= self.RECORDING_MAX_AGE_SECONDS:
                    self._recording_files[file_path] = FileRecordingInfo(
                        last_modified = last_modified,
                        last_checked = now,
                        file_size = file_size,
                        mtime_continuous_start_at = last_modified,  # 初回は必ず mtime_continuous_start_at を設定
                    )
                    logging.info(f'{file_path}: New recording or copying file detected.')

                # メタデータ解析を実行
                await self.processRecordedFile(file_path, original_file_path)

        except FileNotFoundError:
            # ファイルが既に削除されている場合
            pass
        except Exception as ex:
            logging.error(f'{file_path}: Error handling file change:', exc_info=ex)


    async def __handleFileDeletion(self, file_path: anyio.Path, original_file_path: anyio.Path | None = None) -> None:
        """
        ファイル削除イベントを受け取り、DB からレコードを削除する

        Args:
            file_path (anyio.Path): 解決後の削除対象ファイルパス
            original_file_path (anyio.Path | None): 監視で検知した元のファイルパス
        """

        # ファイルパスに対応するロックを取得または作成
        async with self._file_locks_dict_lock:
            if file_path not in self._file_locks:
                self._file_locks[file_path] = asyncio.Lock()
            file_lock = self._file_locks[file_path]

        # 同一ファイルパスへの DB レコード操作を排他制御する
        async with file_lock:
            try:
                mapped_canonical_path: str | None = None
                async with self._symlink_path_map_lock:
                    if original_file_path is not None:
                        mapped_canonical_path = self._symlink_path_map.pop(str(original_file_path), None)
                    if mapped_canonical_path is None:
                        mapped_canonical_path = self._symlink_path_map.pop(str(file_path), None)
                if mapped_canonical_path is not None:
                    file_path = anyio.Path(mapped_canonical_path)

                # 録画中とマークされていたファイルの場合は記録から削除
                self._recording_files.pop(file_path, None)

                # DB からレコードを削除
                db_recorded_video = await RecordedVideo.get_or_none(file_path=str(file_path))
                if db_recorded_video is None and original_file_path is not None:
                    db_recorded_video = await RecordedVideo.get_or_none(file_path=str(original_file_path))
                if db_recorded_video is not None:
                    # RecordedVideo の親テーブルである RecordedProgram を削除すると、
                    # CASCADE 制約により RecordedVideo も同時に削除される (Channel は親テーブルにあたるため削除されない)
                    await db_recorded_video.recorded_program.delete()
                    logging.info(f'{file_path}: Deleted record for removed file.')

            except Exception as ex:
                logging.error(f'{file_path}: Error handling file deletion inside lock:', exc_info=ex)
            finally:
                # 不要になったロックを管理辞書から削除 (ロックが解放された後に行う)
                async with self._file_locks_dict_lock:
                    if file_path in self._file_locks and not file_lock.locked():
                        self._file_locks.pop(file_path, None)


    async def __checkRecordingCompletion(self) -> None:
        """
        録画 (またはファイルコピー) の完了状態を定期的にチェックする
        - 30秒間ファイルの更新がない場合に録画完了 (またはファイルコピー完了) と判断
        - 完了したファイルは再度メタデータを解析して DB に保存
        """

        while self._is_running:
            try:
                now = datetime.now(tz=ZoneInfo('Asia/Tokyo'))
                completed_files: list[anyio.Path] = []

                # 録画中ファイルをチェック
                for file_path, recording_info in self._recording_files.items():
                    try:
                        # ファイルの現在の状態を取得
                        stat = await file_path.stat()
                        current_modified = datetime.fromtimestamp(stat.st_mtime, tz=ZoneInfo('Asia/Tokyo'))
                        current_size = stat.st_size

                        # RECORDING_COMPLETE_SECONDS 秒以上更新がなく、かつファイルサイズが変化していない場合は録画完了と判断
                        if ((now - current_modified).total_seconds() >= self.RECORDING_COMPLETE_SECONDS and
                            current_size == recording_info.file_size):
                            completed_files.append(file_path)
                    except FileNotFoundError:
                        # ファイルが削除された場合は記録から削除
                        completed_files.append(file_path)
                    except Exception as ex:
                        logging.error(f'{file_path}: Error checking recording completion:', exc_info=ex)

                # 完了したファイルを処理
                for file_path in completed_files:
                    try:
                        # 記録から削除
                        self._recording_files.pop(file_path, None)

                        # ファイルが存在する場合のみ再解析
                        if await self.isFileExists(file_path):
                            # この時点で、録画（またはファイルコピー）が確実に完了しているはず
                            logging.info(f'{file_path}: Recording or copying has just completed or has already completed.')
                            await self.processRecordedFile(file_path)
                    except Exception as ex:
                        logging.error(f'{file_path}: Error processing completed file:', exc_info=ex)

            except asyncio.CancelledError:
                raise
            except Exception as ex:
                logging.error('Error in recording completion check:', exc_info=ex)

            # 5秒待機
            await asyncio.sleep(5)
