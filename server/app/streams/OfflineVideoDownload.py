
from __future__ import annotations

import asyncio
import re
import shutil
import time
from collections.abc import Coroutine
from typing import Any, ClassVar, Literal

import anyio
from fastapi import HTTPException
from pydantic import BaseModel

from app import logging
from app.constants import DATA_DIR, QUALITY
from app.schemas import OfflineVideoStreamMetadata
from app.streams.VideoStream import VideoStream


class OfflineVideoDownloadManifest(BaseModel):
    """ 再起動後も同じ変換結果を配信するための一時保存台帳 """

    metadata: OfflineVideoStreamMetadata
    state: Literal['Encoding', 'Completed', 'Failed'] = 'Encoding'
    expires_at: float
    reserved_bytes: int
    segments: list[OfflineVideoDownloadSegment] = []


class OfflineVideoDownloadSegment(BaseModel):
    """ ディスクへの保存が完了したセグメントの長さとサイズ """

    duration_milliseconds: int
    size: int


class OfflineVideoDownload:
    """ 通信切断から独立して変換結果を一時保存し、同じ TS バイト列の再送と期限管理を行う """

    CACHE_DIR: ClassVar[anyio.Path] = anyio.Path(DATA_DIR / 'offline-downloads')
    RETENTION_SECONDS: ClassVar[int] = 30 * 60
    MAX_CACHE_BYTES: ClassVar[int] = 50 * 1024 ** 3
    MIN_FREE_BYTES: ClassVar[int] = 2 * 1024 ** 3
    # 作成・削除を直列化し、容量予約とダウンロード中のファイルの保護を両立する
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _active: ClassVar[dict[str, OfflineVideoDownload]] = {}
    _readers: ClassVar[dict[str, int]] = {}

    def __init__(self, download_id: str, manifest: OfflineVideoDownloadManifest) -> None:
        """
        検証済みの一時保存 ID と台帳から、配信と変換タスクの管理状態を初期化する。

        Args:
            download_id (str): 検証済みの 32 桁の一時保存 ID
            manifest (OfflineVideoDownloadManifest): 確定済みセグメントの台帳
        Returns:
            None
        """
        # create()/open() で検証した ID を保持し、release() と変換終了時の管理表の更新に使う
        self.download_id = download_id
        # 検証済み ID に対応する専用ディレクトリ。getSegment() と台帳・セグメントの書き込みで参照する
        self.directory = self.CACHE_DIR / download_id
        # getSegment() が参照する確定済みセグメントと変換状態。書き込み成功後にだけ更新する
        self.manifest = manifest
        # _produce() がセグメント確定・変換終了を通知し、getSegment() の待機を解除する
        self._changed = asyncio.Event()
        # delete()/shutdown() は _produce() の開始を待ち、finally に入る前のキャンセルによる変換枠の漏れを防ぐ
        self._started = asyncio.Event()
        # 通信切断後も変換を継続するための強参照。生成後は delete()/shutdown() で停止と終了待機に使う
        self._task: asyncio.Task[None] | None = None

    @classmethod
    async def create(cls, stream: VideoStream, metadata: OfflineVideoStreamMetadata,
        semaphore: asyncio.Semaphore) -> OfflineVideoDownload:
        """
        一時保存の容量を予約し、通信接続から独立した変換タスクを開始する。

        Args:
            stream (VideoStream): セグメント一覧を初期化済みの新しい変換セッション
            metadata (OfflineVideoStreamMetadata): ファイル・品質と一時保存 ID
            semaphore (asyncio.Semaphore): 呼び出し元が取得済みの変換枠。成功後は生成タスクが解放する
        Returns:
            OfflineVideoDownload: 読み取り権を取得済みの一時保存
        """
        assert metadata.download_id is not None and re.fullmatch(r'[0-9a-f]{32}', metadata.download_id)
        await cls.cleanupExpired()
        async with cls._lock:
            await cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            directory = cls.CACHE_DIR / metadata.download_id
            if await directory.exists():
                raise HTTPException(409, 'Offline download ID is already in use')
            # 最大ビットレートと TS/字幕の余裕から予約量を見積もり、並列変換で空き容量を取り合わない
            quality = QUALITY[stream.quality]
            bitrate = (int(quality.video_bitrate_max.removesuffix('K')) + 2 * int(quality.audio_bitrate.removesuffix('K'))) * 1000
            reserved = max(1024 ** 2, int(metadata.duration_seconds * bitrate / 8 * 1.3))
            occupied = 0
            async for path in cls.CACHE_DIR.glob('*/manifest.json'):
                try:
                    occupied += OfflineVideoDownloadManifest.model_validate_json(await path.read_text()).reserved_bytes
                except (OSError, ValueError):
                    # 壊れた台帳の容量も無視しない
                    async for data in path.parent.iterdir():
                        if await data.is_file():
                            occupied += (await data.stat()).st_size
            free = (await asyncio.to_thread(shutil.disk_usage, str(cls.CACHE_DIR))).free
            pending = sum(max(0, job.manifest.reserved_bytes - sum(s.size for s in job.manifest.segments)) for job in cls._active.values())
            if occupied + reserved > cls.MAX_CACHE_BYTES or reserved + pending + cls.MIN_FREE_BYTES > free:
                raise HTTPException(507, 'Insufficient space for offline download cache')
            manifest = OfflineVideoDownloadManifest(metadata=metadata, expires_at=time.time() + cls.RETENTION_SECONDS, reserved_bytes=reserved)
            job = cls(metadata.download_id, manifest)
            await directory.mkdir()
            await job._writeManifest(manifest)
            cls._active[job.download_id] = job
            cls._readers[job.download_id] = 1
            stream.is_encoding_restart_allowed = False
            job._task = asyncio.create_task(job._produce(stream, semaphore))
            return job

    @classmethod
    async def open(cls, download_id: str, token: str, video_id: int, quality: str) -> OfflineVideoDownload:
        """
        録画・変換条件と有効期限を確認し、既存の一時保存の読み取り権を取得する。

        Args:
            download_id (str): 一時保存 ID
            token (str): 現在の録画と変換条件の識別子
            video_id (int): 録画 ID
            quality (str): API 上の画質
        Returns:
            OfflineVideoDownload: 読み取り権を取得済みの一時保存
        """
        async with cls._lock:
            if not re.fullmatch(r'[0-9a-f]{32}', download_id):
                raise HTTPException(410, 'Offline download cache is unavailable')
            job = cls._active.get(download_id)
            if job is None:
                try:
                    manifest = OfflineVideoDownloadManifest.model_validate_json(await (cls.CACHE_DIR / download_id / 'manifest.json').read_text())
                except (OSError, ValueError) as ex:
                    raise HTTPException(410, 'Offline download cache is unavailable') from ex
                # サーバー停止で変換が中断したものを再エンコードすると接続を保証できないため、完成品だけ復元する
                if manifest.state != 'Completed' or len(manifest.segments) != manifest.metadata.segment_count or manifest.expires_at <= time.time():
                    raise HTTPException(410, 'Offline download cache expired or encoding was interrupted')
                job = cls(download_id, manifest)
            metadata = job.manifest.metadata
            if metadata.video_id != video_id or metadata.quality != quality or metadata.resume_token != token:
                raise HTTPException(409, 'Offline source or encoding settings changed')
            if job.manifest.state == 'Failed':
                raise HTTPException(410, 'Offline encoding failed')
            cls._readers[download_id] = cls._readers.get(download_id, 0) + 1
            return job

    def release(self) -> None:
        """
        この応答の読み取り権を返し、読み手がいなくなった一時保存を期限回収の対象に戻す。

        Args:
            None
        Returns:
            None
        """
        count = self._readers.get(self.download_id, 0)
        if count <= 1:
            self._readers.pop(self.download_id, None)
        else:
            self._readers[self.download_id] = count - 1

    async def getSegment(self, sequence: int) -> tuple[OfflineVideoDownloadSegment, bytes]:
        """
        指定セグメントの確定を待ち、一時保存した TS データを変更せず読み出す。

        Args:
            sequence (int): 必要なセグメント番号
        Returns:
            tuple[OfflineVideoDownloadSegment, bytes]: 保存された長さ情報と、変更していない TS データ
        """
        while sequence >= len(self.manifest.segments):
            if self.manifest.state != 'Encoding':
                raise RuntimeError('Offline encoding did not complete')
            self._changed.clear()
            await self._changed.wait()
        segment = self.manifest.segments[sequence]
        data = await (self.directory / f'{sequence}.ts').read_bytes()
        if len(data) != segment.size:
            raise RuntimeError('Offline cached segment is incomplete')
        return segment, data

    @staticmethod
    async def _waitForFileWrite(operation: Coroutine[Any, Any, object]) -> None:
        """
        ファイル操作が終わるまで待ち、待機中のキャンセルはその後に伝える。

        Args:
            operation (Coroutine[Any, Any, object]): ファイルの書き込みまたは置換
        Returns:
            None
        """
        task = asyncio.create_task(operation)
        cancelled = False
        # Task.cancel() では AnyIO の書き込みスレッドが止まらないため、終了前に一時ファイルを削除させない
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                # 削除と終了処理が重なって再度キャンセルされても、実行中の操作を待ち続ける
                cancelled = True
        task.result()
        # 正常に書き終えてもキャンセル要求は失わず、呼び出し元の後始末へ進める
        if cancelled:
            raise asyncio.CancelledError

    async def _writeManifest(self, manifest: OfflineVideoDownloadManifest) -> None:
        """
        台帳を一時ファイルへ書き込み、置換が成功した後にメモリ上の状態へ反映する。

        Args:
            manifest (OfflineVideoDownloadManifest): 次に公開する台帳
        Returns:
            None
        """
        # TS を先に書き切り、台帳を atomic rename してから読み手へ公開する
        temporary = self.directory / 'manifest.tmp'
        await self._waitForFileWrite(temporary.write_text(manifest.model_dump_json(), encoding='utf-8'))
        await self._waitForFileWrite(temporary.replace(self.directory / 'manifest.json'))
        self.manifest = manifest

    async def _produce(self, stream: VideoStream, semaphore: asyncio.Semaphore) -> None:
        """
        単一の変換結果を順次保存し、完了・失敗・キャンセル時に変換セッションと実行枠を解放する。

        Args:
            stream (VideoStream): この一時保存だけが所有する変換セッション
            semaphore (asyncio.Semaphore): 終了時に返す変換枠
        Returns:
            None
        """
        async def KeepAlive() -> None:
            """
            HTTP 接続が切れても、一時保存の生成が終わるまで変換セッションを維持する。

            Args:
                None
            Returns:
                None
            """
            # 1 セグメントの生成に時間がかかっても、セッションのタイムアウトを迎えないよう定期更新する
            while True:
                stream.keepAlive()
                await asyncio.sleep(5)

        keep_alive = asyncio.create_task(KeepAlive())
        size = 0
        self._started.set()
        try:
            for segment in stream.segments:
                # 続けて同じプロセスの出力を保存する。HTTP 切断ではこのタスクを停止しない
                data = await asyncio.wait_for(stream.getSegment(segment.sequence_index), 300)
                if not data:
                    raise RuntimeError('Offline segment generation failed')
                size += len(data)
                free = (await asyncio.to_thread(shutil.disk_usage, str(self.directory))).free
                if size > self.manifest.reserved_bytes or free < self.MIN_FREE_BYTES + len(data):
                    raise OSError('Offline download cache capacity exceeded')
                await self._waitForFileWrite((self.directory / f'{segment.sequence_index}.ts').write_bytes(data))
                cached_segment = OfflineVideoDownloadSegment(duration_milliseconds=max(1, round(segment.duration_seconds * 1000)), size=len(data))
                # 再起動後に復元する完成品だけ永続化し、最終セグメントは台帳の保存成功後に公開する
                if len(self.manifest.segments) + 1 == self.manifest.metadata.segment_count:
                    manifest = self.manifest.model_copy(deep=True)
                    manifest.segments.append(cached_segment)
                    manifest.expires_at = time.time() + self.RETENTION_SECONDS
                    manifest.state = 'Completed'
                    manifest.reserved_bytes = size
                    await self._writeManifest(manifest)
                else:
                    # 変換途中はメモリ上の台帳で配信でき、ディスクには作成時の容量予約だけ残せばよい
                    self.manifest.segments.append(cached_segment)
                self._changed.set()
        except (Exception, asyncio.CancelledError) as ex:
            logging.warning(f'[OfflineVideoDownload: {self.download_id}] Encoding interrupted: {ex}')
            # 未完の台帳は再起動後の復元対象外なので、失敗時も再保存せず待機中の応答だけを終了する
            self.manifest.state = 'Failed'
        finally:
            self._changed.set()
            keep_alive.cancel()
            await asyncio.gather(keep_alive, return_exceptions=True)
            try:
                await stream.destroy()
            except Exception as ex:
                logging.warning(f'[OfflineVideoDownload: {self.download_id}] Failed to close encoding session: {ex}')
            finally:
                semaphore.release()
                self._active.pop(self.download_id, None)

    @classmethod
    async def delete(cls, download_id: str, video_id: int, quality: str) -> None:
        """
        録画 ID と画質が一致する一時保存の生成を停止し、保存ディレクトリを削除する。

        Args:
            download_id (str): 明示的にキャンセル/完了された一時保存 ID
            video_id (int): 録画 ID
            quality (str): API 上の画質
        Returns:
            None
        """
        async with cls._lock:
            if not re.fullmatch(r'[0-9a-f]{32}', download_id):
                return
            directory = cls.CACHE_DIR / download_id
            try:
                manifest = OfflineVideoDownloadManifest.model_validate_json(await (directory / 'manifest.json').read_text())
            except (OSError, ValueError):
                return
            if manifest.metadata.video_id != video_id or manifest.metadata.quality != quality:
                raise HTTPException(409, 'Offline download does not match the recording')
            job = cls._active.get(download_id)
            if job and job._task:
                await job._started.wait()
                job._task.cancel()
                await asyncio.gather(job._task, return_exceptions=True)
            await cls._removeDirectory(directory)

    @classmethod
    async def _removeDirectory(cls, directory: anyio.Path) -> None:
        """
        専用キャッシュディレクトリ直下であることを確認してから、一時保存を再帰削除する。

        Args:
            directory (anyio.Path): 削除対象の一時保存ディレクトリ
        Returns:
            None
        """
        # 誤ったパスやシンボリックリンクを再帰削除しない。解決後も専用ディレクトリ直下であることを確認する
        if not re.fullmatch(r'[0-9a-f]{32}', directory.name) or await directory.is_symlink():
            return
        resolved = await directory.resolve()
        if resolved.parent != await cls.CACHE_DIR.resolve():
            raise ValueError('Offline cache directory escaped its root')
        await asyncio.to_thread(shutil.rmtree, str(resolved))

    @classmethod
    async def cleanupExpired(cls) -> None:
        """
        変換中・配信中のデータを保護し、期限切れまたは復元できない一時保存を削除する。

        Args:
            None
        Returns:
            None
        """
        async with cls._lock:
            if not await cls.CACHE_DIR.exists():
                return
            async for directory in cls.CACHE_DIR.iterdir():
                if not re.fullmatch(r'[0-9a-f]{32}', directory.name) or directory.name in cls._active or directory.name in cls._readers:
                    continue
                try:
                    manifest = OfflineVideoDownloadManifest.model_validate_json(await (directory / 'manifest.json').read_text())
                    expired = manifest.expires_at <= time.time() or manifest.state != 'Completed'
                except (OSError, ValueError):
                    expired = True
                if expired:
                    await cls._removeDirectory(directory)

    @classmethod
    async def shutdown(cls) -> None:
        """
        実行中の変換タスクを停止し、リソースが解放されるまで待つ。完成した一時保存は残す。

        Args:
            None
        Returns:
            None
        """
        jobs = list(cls._active.values())
        await asyncio.gather(*(job._started.wait() for job in jobs))
        tasks = [job._task for job in jobs if job._task is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
