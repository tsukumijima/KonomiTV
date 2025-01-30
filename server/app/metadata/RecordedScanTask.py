from __future__ import annotations

import anyio
import asyncio
import concurrent.futures
from datetime import datetime
from pathlib import Path
from tortoise import transactions
from typing import AsyncIterator
from watchfiles import awatch, Change
from zoneinfo import ZoneInfo

from app import logging
from app import schemas
from app.config import Config
from app.metadata.MetadataAnalyzer import MetadataAnalyzer
from app.models.Channel import Channel
from app.models.RecordedProgram import RecordedProgram
from app.models.RecordedVideo import RecordedVideo


class RecordedScanTask:
    """
    録画フォルダの監視とメタデータの同期を行うタスク
    以下の処理を担う
    - 起動時の一括同期
    - watchfiles による継続的な監視
    - メタデータ解析と DB への永続化
    - 録画中ファイルの状態管理
    """

    # 録画中ファイルの更新イベントを間引く間隔 (秒)
    __UPDATE_THROTTLE_SECONDS: int = 30

    # 録画完了と判断するまでの無更新時間 (秒)
    __RECORDING_COMPLETE_SECONDS: int = 30

    # 録画中ファイルの最小データ長 (秒)
    __MINIMUM_RECORDING_SECONDS: int = 60


    def __init__(self) -> None:
        """
        録画フォルダの監視タスクを初期化する
        """

        # 設定を読み込む
        self.config = Config()
        self.recorded_folders = [anyio.Path(folder) for folder in self.config.video.recorded_folders]

        # 録画中ファイルの状態管理
        ## path: (last_modified, last_checked, file_size)
        self._recording_files: dict[anyio.Path, tuple[datetime, datetime, int]] = {}

        # タスクの状態管理
        self._is_running = False
        self._task: asyncio.Task[None] | None = None

        # バックグラウンドタスクの状態管理
        self._background_tasks: dict[anyio.Path, asyncio.Task[None]] = {}


    async def start(self) -> None:
        """
        録画フォルダの監視タスクを開始する
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
        初回に録画フォルダ以下の録画フォルダをスキャン・同期した後、
        watchfiles による継続的な監視を開始する
        """

        try:
            # 起動時の一括同期を実行
            await self.__runInitialScan()
            # ファイル監視を開始
            await self.__watchDirectories()
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            logging.error('Error in RecordedScanTask:', exc_info=ex)
        finally:
            self._is_running = False


    async def __runInitialScan(self) -> None:
        """
        起動時の一括同期を実行する
        - 録画フォルダ内の全 TS ファイルをスキャン
        - 変更があったファイルのみメタデータを解析
        - DB に永続化
        """

        logging.info('Initial scan started.')

        # 現在の RecordedVideo レコードをキャッシュ
        existing_videos = {
            anyio.Path(video.file_path): video for video in await RecordedVideo.all().select_related('recorded_program')
        }

        # 各録画フォルダを非同期にスキャン
        for folder in self.recorded_folders:
            async for file_path in self.__scanDirectory(folder):
                try:
                    await self.__processFile(file_path, existing_videos)
                except Exception as ex:
                    logging.error(f'{file_path}: Failed to process file:', exc_info=ex)

        # 存在しないファイルのレコードを一括削除
        # トランザクション配下に入れることでパフォーマンスが向上する
        async with transactions.in_transaction():
            for video_path, video in existing_videos.items():
                # ファイルの存在確認を非同期に行う
                if not await video_path.exists():
                    await video.delete()
                    logging.info(f'{video_path}: Deleted record for non-existent file.')

        logging.info('Initial scan completed.')


    async def __runBackgroundAnalysis(self, file_path: anyio.Path) -> None:
        """
        録画完了後のバックグラウンド解析タスク
        - キーフレーム解析
        - CM区間解析
        など、時間のかかる処理を非同期に実行する

        Args:
            file_path (anyio.Path): 解析対象のファイルパス
        """

        try:
            # TODO: 実際のキーフレーム解析・CM区間解析の実装
            # 現状はダミー実装
            await asyncio.sleep(5)  # 重い処理を想定した待機
            logging.info(f'{file_path}: Background analysis completed.')

        except Exception as ex:
            logging.error(f'{file_path}: Error in background analysis:', exc_info=ex)
        finally:
            # 完了したタスクを管理対象から削除
            self._background_tasks.pop(file_path, None)


    async def __scanDirectory(self, directory: anyio.Path) -> AsyncIterator[anyio.Path]:
        """
        ディレクトリを非同期に走査する
        anyio.Path を使用して非同期にファイルを列挙する

        Args:
            directory (anyio.Path): 走査対象のディレクトリ

        Yields:
            anyio.Path: 見つかった TS ファイルのパス
        """

        # 非同期にディレクトリを走査
        async for file_path in directory.rglob('*'):
            try:
                # ファイルの検証
                if not await file_path.is_file():
                    continue
                # Mac の metadata ファイルをスキップ
                if file_path.name.startswith('._'):
                    continue
                # TS ファイル以外をスキップ
                if file_path.suffix.lower() not in ['.ts', '.m2t', '.m2ts', '.mts']:
                    continue
                yield file_path
            except Exception:
                continue


    async def __processFile(
        self,
        file_path: anyio.Path,
        existing_videos: dict[anyio.Path, RecordedVideo],
    ) -> None:
        """
        指定された録画ファイルのメタデータを解析し、DB に永続化する

        Args:
            file_path (anyio.Path): 処理対象のファイルパス
            existing_videos (dict[anyio.Path, RecordedVideo]): 既存の RecordedVideo レコード
        """

        try:
            # ファイルの状態をチェック
            stat = await file_path.stat()
            last_modified = datetime.fromtimestamp(stat.st_mtime, tz=ZoneInfo('Asia/Tokyo'))
            now = datetime.now(tz=ZoneInfo('Asia/Tokyo'))
            file_size = stat.st_size

            # 既存レコードをチェック
            existing_video = existing_videos.pop(file_path, None)

            # 録画中ファイルの処理
            is_recording = file_path in self._recording_files
            if is_recording:
                # 既に DB に登録済みで録画中の場合は再解析しない
                if existing_video is not None and existing_video.status == 'Recording':
                    return
                # ファイルサイズが前回と変わっていない場合はスキップ
                last_size = self._recording_files[file_path][2]
                if file_size == last_size:
                    return

            # ProcessPoolExecutor でメタデータを解析
            ## with 文で括ることで、with 文を抜けたときに ProcessPoolExecutor がクリーンアップされるようにする
            ## さもなければプロセスが残り続けてゾンビプロセス化し、メモリリークを引き起こしてしまう
            loop = asyncio.get_running_loop()
            analyzer = MetadataAnalyzer(Path(str(file_path)))  # anyio.Path -> pathlib.Path に変換
            with concurrent.futures.ProcessPoolExecutor() as executor:
                recorded_program = await loop.run_in_executor(executor, analyzer.analyze)

            if recorded_program is None:
                # メタデータ解析に失敗した場合はエラーとして扱う
                logging.error(f'{file_path}: Failed to analyze metadata.')
                return

            # 60秒未満のファイルは録画中として記録するのみ
            if recorded_program.recorded_video.duration < self.__MINIMUM_RECORDING_SECONDS:
                self._recording_files[file_path] = (last_modified, now, file_size)
                return

            # 録画中のファイルとして処理
            if is_recording or (now - last_modified).total_seconds() < self.__RECORDING_COMPLETE_SECONDS:
                # status を Recording に設定
                recorded_program.recorded_video.status = 'Recording'
                # 状態を更新
                self._recording_files[file_path] = (last_modified, now, file_size)
            else:
                # 録画完了後のバックグラウンド解析タスクを開始
                if file_path not in self._background_tasks:
                    task = asyncio.create_task(self.__runBackgroundAnalysis(file_path))
                    self._background_tasks[file_path] = task

            # DB に永続化
            await self.__saveRecordedMetadataToDB(recorded_program)
            logging.info(f'{file_path}: Processed file.')

        except Exception as ex:
            logging.error(f'{file_path}: Error processing file:', exc_info=ex)
            raise


    @staticmethod
    async def __saveRecordedMetadataToDB(recorded_program: schemas.RecordedProgram) -> None:
        """
        録画ファイルのメタデータ解析結果を DB に保存する
        id, created_at, updated_at は自動生成されるため、明示的に除外している

        Args:
            recorded_program (schemas.RecordedProgram): 保存する録画番組情報
        """

        # トランザクション配下に入れることでパフォーマンスが向上する
        async with transactions.in_transaction():

            # Channel の保存（まだ当該チャンネルが DB に存在しない場合のみ）
            channel = None
            if recorded_program.channel is not None:
                channel = await Channel.get_or_none(id=recorded_program.channel.id)
                if channel is None:
                    channel = Channel(
                        id = recorded_program.channel.id,
                        display_channel_id = recorded_program.channel.display_channel_id,
                        network_id = recorded_program.channel.network_id,
                        service_id = recorded_program.channel.service_id,
                        transport_stream_id = recorded_program.channel.transport_stream_id,
                        remocon_id = recorded_program.channel.remocon_id,
                        channel_number = recorded_program.channel.channel_number,
                        type = recorded_program.channel.type,
                        name = recorded_program.channel.name,
                        jikkyo_force = recorded_program.channel.jikkyo_force,
                        is_subchannel = recorded_program.channel.is_subchannel,
                        is_radiochannel = recorded_program.channel.is_radiochannel,
                        is_watchable = recorded_program.channel.is_watchable,
                    )
                    await channel.save()

            # RecordedProgram の保存
            db_recorded_program = RecordedProgram(
                recording_start_margin = recorded_program.recording_start_margin,
                recording_end_margin = recorded_program.recording_end_margin,
                is_partially_recorded = recorded_program.is_partially_recorded,
                channel = channel,
                network_id = recorded_program.network_id,
                service_id = recorded_program.service_id,
                event_id = recorded_program.event_id,
                series_id = recorded_program.series_id,
                series_broadcast_period_id = recorded_program.series_broadcast_period_id,
                title = recorded_program.title,
                series_title = recorded_program.series_title,
                episode_number = recorded_program.episode_number,
                subtitle = recorded_program.subtitle,
                description = recorded_program.description,
                detail = recorded_program.detail,
                start_time = recorded_program.start_time,
                end_time = recorded_program.end_time,
                duration = recorded_program.duration,
                is_free = recorded_program.is_free,
                genres = recorded_program.genres,
                primary_audio_type = recorded_program.primary_audio_type,
                primary_audio_language = recorded_program.primary_audio_language,
                secondary_audio_type = recorded_program.secondary_audio_type,
                secondary_audio_language = recorded_program.secondary_audio_language,
            )
            await db_recorded_program.save()

            # RecordedVideo の保存
            db_recorded_video = RecordedVideo(
                recorded_program = db_recorded_program,
                status = recorded_program.recorded_video.status,
                file_path = str(recorded_program.recorded_video.file_path),
                file_hash = recorded_program.recorded_video.file_hash,
                file_size = recorded_program.recorded_video.file_size,
                file_created_at = recorded_program.recorded_video.file_created_at,
                file_modified_at = recorded_program.recorded_video.file_modified_at,
                recording_start_time = recorded_program.recorded_video.recording_start_time,
                recording_end_time = recorded_program.recorded_video.recording_end_time,
                duration = recorded_program.recorded_video.duration,
                container_format = recorded_program.recorded_video.container_format,
                video_codec = recorded_program.recorded_video.video_codec,
                video_codec_profile = recorded_program.recorded_video.video_codec_profile,
                video_scan_type = recorded_program.recorded_video.video_scan_type,
                video_frame_rate = recorded_program.recorded_video.video_frame_rate,
                video_resolution_width = recorded_program.recorded_video.video_resolution_width,
                video_resolution_height = recorded_program.recorded_video.video_resolution_height,
                primary_audio_codec = recorded_program.recorded_video.primary_audio_codec,
                primary_audio_channel = recorded_program.recorded_video.primary_audio_channel,
                primary_audio_sampling_rate = recorded_program.recorded_video.primary_audio_sampling_rate,
                secondary_audio_codec = recorded_program.recorded_video.secondary_audio_codec,
                secondary_audio_channel = recorded_program.recorded_video.secondary_audio_channel,
                secondary_audio_sampling_rate = recorded_program.recorded_video.secondary_audio_sampling_rate,
                key_frames = recorded_program.recorded_video.key_frames,
                cm_sections = recorded_program.recorded_video.cm_sections,
            )
            await db_recorded_video.save()

            logging.info(f'{recorded_program.recorded_video.file_path}: Saved metadata to DB.')


    async def __watchDirectories(self) -> None:
        """watchfiles による継続的な監視を実行する"""
        logging.info('Starting file system watch.')

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
                for change_type, file_path in changes:
                    if not self._is_running:
                        break

                    # TS ファイル以外は無視
                    path = anyio.Path(file_path)
                    if path.suffix.lower() not in ['.ts', '.m2t', '.m2ts', '.mts']:
                        continue

                    try:
                        # 追加 or 変更イベント
                        if change_type == Change.added or change_type == Change.modified:
                            await self.__handleFileChange(path)
                        # 削除イベント
                        elif change_type == Change.deleted:
                            await self.__handleFileDeletion(path)
                    except Exception as ex:
                        logging.error(f'{path}: Error handling file change:', exc_info=ex)

        except asyncio.CancelledError:
            raise
        except Exception as ex:
            logging.error('Error in file system watch:', exc_info=ex)
        finally:
            completion_check_task.cancel()
            try:
                await completion_check_task
            except asyncio.CancelledError:
                pass
            logging.info('File system watch stopped.')


    async def __handleFileChange(self, file_path: anyio.Path) -> None:
        """
        ファイル追加・変更イベントを受け取り、適切な頻度で __processFile() を呼び出す
        - 録画中ファイルの状態管理
        - メタデータ解析のスロットリング

        Args:
            path (anyio.Path): 追加・変更があったファイルのパス
        """

        try:
            # ファイルの状態をチェック
            stat = await file_path.stat()
            last_modified = datetime.fromtimestamp(stat.st_mtime, tz=ZoneInfo('Asia/Tokyo'))
            now = datetime.now(tz=ZoneInfo('Asia/Tokyo'))
            file_size = stat.st_size

            # 録画中ファイルの処理
            if file_path in self._recording_files:
                last_checked = self._recording_files[file_path][1]
                # 前回のチェックから30秒以上経過していない場合はスキップ
                if (now - last_checked).total_seconds() < self.__UPDATE_THROTTLE_SECONDS:
                    return
                # 状態を更新して処理
                await self.__processFile(file_path, {})
                return

            # 新規ファイルの処理
            self._recording_files[file_path] = (last_modified, now, file_size)
            await self.__processFile(file_path, {})

        except FileNotFoundError:
            # ファイルが既に削除されている場合
            pass
        except Exception as ex:
            logging.error(f'{file_path}: Error handling file change:', exc_info=ex)


    async def __handleFileDeletion(self, file_path: anyio.Path) -> None:
        """
        ファイル削除イベントを受け取り、DB からレコードを削除する

        Args:
            file_path (anyio.Path): 削除されたファイルのパス
        """

        try:
            # 録画中ファイルの場合は記録を削除
            self._recording_files.pop(file_path, None)

            # DB からレコードを削除
            video = await RecordedVideo.get_or_none(file_path=str(file_path))
            if video is not None:
                await video.delete()
                logging.info(f'{file_path}: Deleted record for removed file.')

        except Exception as ex:
            logging.error(f'{file_path}: Error handling file deletion:', exc_info=ex)


    async def __checkRecordingCompletion(self) -> None:
        """
        録画完了状態を定期的にチェックする
        - 30秒間ファイルの更新がない場合に録画完了と判断
        - 完了したファイルは再度メタデータを解析して DB に保存
        """

        while self._is_running:
            try:
                now = datetime.now(tz=ZoneInfo('Asia/Tokyo'))
                completed_files = []

                # 録画中ファイルをチェック
                for file_path, (_, _, last_size) in self._recording_files.items():
                    try:
                        # ファイルの現在の状態を取得
                        stat = await file_path.stat()
                        current_modified = datetime.fromtimestamp(stat.st_mtime, tz=ZoneInfo('Asia/Tokyo'))
                        current_size = stat.st_size

                        # 30秒以上更新がなく、かつファイルサイズが変化していない場合は録画完了と判断
                        if ((now - current_modified).total_seconds() >= self.__RECORDING_COMPLETE_SECONDS and
                            current_size == last_size):
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
                        if await file_path.exists():
                            logging.info(f'{file_path}: Recording completed.')
                            await self.__processFile(file_path, {})
                    except Exception as ex:
                        logging.error(f'{file_path}: Error processing completed file:', exc_info=ex)

            except asyncio.CancelledError:
                raise
            except Exception as ex:
                logging.error('Error in recording completion check:', exc_info=ex)

            # 5秒待機
            await asyncio.sleep(5)
