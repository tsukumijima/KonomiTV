import asyncio
import os
import tempfile
import unittest
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, NamedTuple
from unittest.mock import AsyncMock, call, patch

import anyio
import ruamel.yaml
from pydantic import ValidationError
from watchfiles import Change
from watchfiles.main import RustNotify

from app.config import SaveConfig, ServerSettings, _ServerSettingsVideo
from app.metadata.RecordedScanTask import RecordedScanTask


class Partition(NamedTuple):
    """監視方式の判定に必要なマウント情報だけを保持するテスト用データ。"""

    mountpoint: str
    fstype: str


class VideoPollingSettingsTests(unittest.TestCase):
    """既存の設定ファイルとの互換性とポーリング間隔のバリデーションを確認する。"""

    def testMissingPollingIntervalDefaultsToOneMinute(self) -> None:
        # 新しいキーを持たない既存の config.yaml でも60秒を採用する
        settings = _ServerSettingsVideo.model_validate({'recorded_folders': [], 'exclude_scan_paths': []})
        self.assertEqual(settings.recorded_folders_polling_interval, 60)

    def testCustomPollingInterval(self) -> None:
        settings = _ServerSettingsVideo(recorded_folders_polling_interval=180)
        self.assertEqual(settings.recorded_folders_polling_interval, 180)

    def testPollingIntervalRequiresPositiveInteger(self) -> None:
        # ミリ秒変換に曖昧さが生じる値や、無効な間隔を設定の読み込み時に拒否する
        for value in (0, -1, 1.5, '60', True, None):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                _ServerSettingsVideo.model_validate({'recorded_folders_polling_interval': value})

    def testSaveConfigPreservesCustomPollingInterval(self) -> None:
        # サーバー設定画面から他の項目を保存した場合も、YAML で指定した間隔を保持する
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / 'config.yaml'
            config_path.write_text('video:\n    # Preserve this comment\n    recorded_folders: []\n', encoding='utf-8')
            settings = ServerSettings.model_construct(video=_ServerSettingsVideo(recorded_folders_polling_interval=180))
            with (
                patch('app.config._CONFIG_YAML_PATH', config_path),
                patch('app.utils.GetPlatformEnvironment', return_value='Linux'),
            ):
                SaveConfig(settings)
            content = config_path.read_text(encoding='utf-8')
            self.assertIn('# Preserve this comment', content)
            self.assertEqual(ruamel.yaml.YAML().load(content)['video']['recorded_folders_polling_interval'], 180)


class RecordedScanWatchTests(unittest.IsolatedAsyncioTestCase):
    """実際の DB や録画ファイルに触れず、監視方式とイベント処理・停止処理を確認する。"""

    def setUp(self) -> None:
        """
        各テスト専用の監視インスタンスとマウント情報・環境変数を用意する。

        Args:
            None

        Returns:
            None
        """

        # シングルトンの初期化を迂回し、実行中サーバーの設定や DB を参照しない
        self.scanner = object.__new__(RecordedScanTask)
        self.scanner.config = ServerSettings.model_construct(video=_ServerSettingsVideo())
        self.scanner.recorded_folders = []
        self.scanner._is_running = True
        self.expect_watch_error = False

        # 実行環境のマウント構成・強制ポーリング設定にテスト結果が依存しないようにする
        self.enterContext(patch.dict(os.environ, {'WATCHFILES_FORCE_POLLING': '', 'WATCHFILES_POLL_DELAY_MS': ''}))
        self.enterContext(patch('app.metadata.RecordedScanTask.psutil.LINUX', True))
        self.partitions = self.enterContext(patch('app.metadata.RecordedScanTask.psutil.disk_partitions', return_value=[]))
        self.enterContext(patch('app.metadata.RecordedScanTask.logging.info'))
        self.warning = self.enterContext(patch('app.metadata.RecordedScanTask.logging.warning'))
        self.error = self.enterContext(patch('app.metadata.RecordedScanTask.logging.error'))
        self.completion_check = self.enterContext(patch.object(
            self.scanner, '_RecordedScanTask__checkRecordingCompletion', new_callable=AsyncMock,
        ))

        # ファイルを作成するテストも一時ディレクトリ内だけで実行する
        directory = tempfile.TemporaryDirectory(prefix='konomitv-watch-test-')
        self.addCleanup(directory.cleanup)
        self.directory = anyio.Path(directory.name)

    def tearDown(self) -> None:
        """
        正常系のテストで監視エラーが握りつぶされていないことを確認する。

        Args:
            None

        Returns:
            None
        """

        if not self.expect_watch_error:
            self.error.assert_not_called()

    async def testDockerNFSAndLocalFoldersUseSeparateGroups(self) -> None:
        self.scanner.recorded_folders = [anyio.Path(path) for path in (
            '/host-rootfs/mnt/hdd0', '/host-rootfs/mnt/hdd1', '/host-rootfs/mnt/test',
        )]
        self.partitions.return_value = [
            Partition('/', 'overlay'), Partition('/host-rootfs', 'ext4'),
            Partition('/host-rootfs/mnt/hdd0', 'nfs4'), Partition('/host-rootfs/mnt/hdd1', 'nfs'),
        ]
        self.assertEqual(await self.scanner._RecordedScanTask__getRecordingWatchPaths(), (
            ['/host-rootfs/mnt/test'], ['/host-rootfs/mnt/hdd0', '/host-rootfs/mnt/hdd1'],
        ))
        self.partitions.assert_called_once_with(True)

    async def testDeepestMountTakesPrecedence(self) -> None:
        self.scanner.recorded_folders = [anyio.Path('/mnt/nfs/local/recordings')]
        self.partitions.return_value = [Partition('/', 'ext4'), Partition('/mnt/nfs', 'nfs4'), Partition('/mnt/nfs/local', 'ext4')]
        self.assertEqual(await self.scanner._RecordedScanTask__getRecordingWatchPaths(), (['/mnt/nfs/local/recordings'], []))

    async def testMountMatchingUsesPathComponents(self) -> None:
        self.scanner.recorded_folders = [anyio.Path('/mnt/hdd01')]
        self.partitions.return_value = [Partition('/', 'ext4'), Partition('/mnt/hdd0', 'nfs4')]
        self.assertEqual(await self.scanner._RecordedScanTask__getRecordingWatchPaths(), (['/mnt/hdd01'], []))

    async def testNFSSubmountRequiresPollingOfRecursiveWatchRoot(self) -> None:
        self.scanner.recorded_folders = [anyio.Path('/mnt/recordings')]
        self.partitions.return_value = [Partition('/', 'ext4'), Partition('/mnt/recordings/archive', 'nfs4')]
        self.assertEqual(await self.scanner._RecordedScanTask__getRecordingWatchPaths(), ([], ['/mnt/recordings']))

    async def testLastEntryWinsForOvermountedFilesystem(self) -> None:
        self.scanner.recorded_folders = [anyio.Path('/mnt/recordings')]
        self.partitions.return_value = [Partition('/', 'ext4'), Partition('/mnt/recordings', 'nfs4'), Partition('/mnt/recordings', 'ext4')]
        self.assertEqual(await self.scanner._RecordedScanTask__getRecordingWatchPaths(), (['/mnt/recordings'], []))

    async def testSymlinkUsesTargetFilesystemButPreservesWatchPath(self) -> None:
        target = self.directory / 'nfs'
        link = self.directory / 'recordings'
        await target.mkdir()
        await link.symlink_to(target, target_is_directory=True)
        self.scanner.recorded_folders = [link]
        self.partitions.return_value = [Partition('/', 'ext4'), Partition(str(target), 'nfs4')]
        self.assertEqual(await self.scanner._RecordedScanTask__getRecordingWatchPaths(), ([], [str(link)]))

    async def testNonLinuxRetainsWatchfilesDefaults(self) -> None:
        self.scanner.recorded_folders = [anyio.Path('/mnt/recordings')]
        with patch('app.metadata.RecordedScanTask.psutil.LINUX', False):
            self.assertEqual(await self.scanner._RecordedScanTask__getRecordingWatchPaths(), (['/mnt/recordings'], []))
        self.partitions.assert_not_called()

    async def testExplicitForcePollingEnvironmentOverrideIsPreserved(self) -> None:
        self.scanner.recorded_folders = [anyio.Path('/mnt/nfs')]
        # 空でない値の解釈は watchfiles に委ね、有効化だけでなく false 等の無効化も優先する
        for value in ('true', 'false', 'disable', 'disabled', '0'):
            with self.subTest(value=value), patch.dict(os.environ, {'WATCHFILES_FORCE_POLLING': value}):
                self.assertEqual(await self.scanner._RecordedScanTask__getRecordingWatchPaths(), (['/mnt/nfs'], []))
        self.partitions.assert_not_called()

    async def testMountDetectionFailureFallsBackToDefaultWatch(self) -> None:
        self.scanner.recorded_folders = [anyio.Path('/mnt/recordings')]
        self.partitions.side_effect = OSError('Mount information unavailable')
        self.assertEqual(await self.scanner._RecordedScanTask__getRecordingWatchPaths(), (['/mnt/recordings'], []))
        self.warning.assert_called_once()

    async def testPathResolutionFailureFallsBackToDefaultWatch(self) -> None:
        self.scanner.recorded_folders = [anyio.Path('/mnt/recordings')]
        with patch.object(anyio.Path, 'resolve', side_effect=OSError('Cannot resolve folder')):
            self.assertEqual(await self.scanner._RecordedScanTask__getRecordingWatchPaths(), (['/mnt/recordings'], []))
        self.warning.assert_called_once()

    async def testGroupsShareCompletionCheckAndUseConfiguredInterval(self) -> None:
        self.scanner.config.video.recorded_folders_polling_interval = 180
        with (
            patch.object(self.scanner, '_RecordedScanTask__getRecordingWatchPaths', return_value=(['/local'], ['/nfs'])),
            patch('app.metadata.RecordedScanTask.awatch') as watch,
        ):
            await self.scanner.watchRecordedFolders()
            watch.assert_has_calls([
                call('/local', recursive=True, force_polling=None, poll_delay_ms=180000),
                call('/nfs', recursive=True, force_polling=True, poll_delay_ms=180000),
            ], any_order=True)
        self.completion_check.assert_awaited_once()

    async def testNoRecordingFoldersStartsNoWatcherOrCompletionTask(self) -> None:
        with patch('app.metadata.RecordedScanTask.awatch') as watch:
            await self.scanner.watchRecordedFolders()
            watch.assert_not_called()
        self.completion_check.assert_not_awaited()

    async def testWatchfilesEnvironmentOverridesReachBackendUnchanged(self) -> None:
        self.scanner.recorded_folders = [anyio.Path('/mnt/nfs')]
        self.partitions.return_value = [Partition('/', 'ext4'), Partition('/mnt/nfs', 'nfs4')]
        # KonomiTV の自動判定後も、watchfiles 自身が環境変数の監視方式・ミリ秒単位の間隔を優先する
        for value, expected_polling in (('', True), ('true', True), ('false', False), ('disable', False), ('disabled', False)):
            with (
                self.subTest(value=value),
                patch.dict(os.environ, {'WATCHFILES_FORCE_POLLING': value, 'WATCHFILES_POLL_DELAY_MS': '1234'}),
                patch('watchfiles.main.RustNotify') as backend,
            ):
                backend.return_value.__enter__.return_value.watch.return_value = 'stop'
                await self.scanner.watchRecordedFolders()
                backend.assert_called_once()
                self.assertEqual(backend.call_args.args[2], expected_polling)
                self.assertEqual(backend.call_args.args[3], 1234)

    async def testBothModesUseExistingEventHandlersAndFilters(self) -> None:
        accepted = self.directory / 'recording.ts'
        excluded = self.directory / 'excluded' / 'recording.ts'
        self.scanner.config.video.exclude_scan_paths = [str(excluded.parent), '']
        changes = {
            (Change.added, str(accepted)), (Change.modified, str(accepted)), (Change.deleted, str(accepted)),
            (Change.added, str(excluded)), (Change.added, str(self.directory / 'notes.txt')),
            (Change.added, str(self.directory / '._recording.ts')),
        }

        async def WatchChanges(*args: Any, **kwargs: Any) -> AsyncGenerator[set[tuple[Change, str]]]:
            """Args: 監視引数。Returns: テスト用の変更イベント。"""
            yield changes

        async def ResolvePath(path: anyio.Path) -> anyio.Path:
            """Args: 元のパス。Returns: DB を使わず解決したパス。"""
            return path

        for force_polling in (None, True):
            with (
                self.subTest(force_polling=force_polling),
                patch('app.metadata.RecordedScanTask.awatch', side_effect=WatchChanges),
                patch.object(self.scanner, 'resolveRecordedPath', side_effect=ResolvePath),
                patch.object(self.scanner, '_RecordedScanTask__handleFileChange', new_callable=AsyncMock) as changed,
                patch.object(self.scanner, '_RecordedScanTask__handleFileDeletion', new_callable=AsyncMock) as deleted,
            ):
                await self.scanner._RecordedScanTask__watchRecordingPaths(
                    [str(self.directory)], [str(excluded.parent)], force_polling=force_polling, poll_delay_ms=60000,
                )
                self.assertEqual(changed.await_count, 2)
                changed.assert_awaited_with(accepted, original_file_path=accepted)
                deleted.assert_awaited_once_with(accepted, original_file_path=accepted)

    async def testCancellationClosesBothWatchersAndCompletionCheck(self) -> None:
        await self.checkWatcherCleanup(fail_watcher=False)

    async def testWatcherFailureClosesSiblingAndCompletionCheck(self) -> None:
        self.expect_watch_error = True
        await self.checkWatcherCleanup(fail_watcher=True)
        self.error.assert_called_once()

    async def checkWatcherCleanup(self, *, fail_watcher: bool) -> None:
        """
        全監視タスクが開始した後に停止・エラーを発生させ、すべて回収されることを確認する。

        Args:
            fail_watcher (bool): False はキャンセル、True は監視エラーを発生させる

        Returns:
            None
        """

        all_started = asyncio.Event()
        started: set[str] = set()
        stopped: set[str] = set()

        async def WatchPaths(path: str, **kwargs: Any) -> AsyncGenerator[set[tuple[Change, str]]]:
            """Args: 監視対象。Returns: 停止まで待機する変更イベント生成器。"""
            started.add(path)
            if len(started) == 2:
                all_started.set()
            try:
                await all_started.wait()
                if fail_watcher and path == '/nfs':
                    raise OSError('Watcher failed')
                await asyncio.Event().wait()
                yield set()
            finally:
                stopped.add(path)

        async def CheckCompletion() -> None:
            """Args: None。Returns: None。"""
            try:
                await asyncio.Event().wait()
            finally:
                stopped.add('completion')

        self.completion_check.side_effect = CheckCompletion
        with (
            patch.object(self.scanner, '_RecordedScanTask__getRecordingWatchPaths', return_value=(['/local'], ['/nfs'])),
            patch('app.metadata.RecordedScanTask.awatch', side_effect=WatchPaths),
        ):
            task = asyncio.create_task(self.scanner.watchRecordedFolders())
            try:
                await asyncio.wait_for(all_started.wait(), timeout=5)
                if not fail_watcher:
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                else:
                    await asyncio.wait_for(task, timeout=5)
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        self.assertEqual(stopped, {'/local', '/nfs', 'completion'})
        self.completion_check.assert_awaited_once()

    async def testRealPollingDetectsCreateModifyAndDelete(self) -> None:
        # マウント判定のみ NFS として模擬し、watchfiles 自体は実際のポーリングで検証する
        # 実 NFS サーバー側からの変更検証とは区別し、DB・メタデータ解析は呼び出さない
        self.scanner.recorded_folders = [self.directory]
        self.scanner.config.video.recorded_folders_polling_interval = 1
        self.partitions.return_value = [Partition('/', 'ext4'), Partition(str(self.directory), 'nfs4')]
        changed_events: asyncio.Queue[anyio.Path] = asyncio.Queue()
        deleted_events: asyncio.Queue[anyio.Path] = asyncio.Queue()
        initial_snapshot_ready = asyncio.Event()
        file_path = self.directory / 'recording.ts'

        def CreateWatcher(*args: Any, **kwargs: Any) -> RustNotify:
            """Args: watchfiles の監視引数。Returns: 初回スナップショットを取得した実際の監視バックエンド。"""
            # RustNotify の初期化が完了するまで待ち、実行環境の速度に依存する固定待ち時間を使わない
            watcher = RustNotify(*args, **kwargs)
            initial_snapshot_ready.set()
            return watcher

        async def ResolvePath(path: anyio.Path) -> anyio.Path:
            """Args: 元のパス。Returns: DB を使わず解決したパス。"""
            return path

        async def HandleChange(path: anyio.Path, original_file_path: anyio.Path | None = None) -> None:
            """Args: 変更されたパスと元のパス。Returns: None。"""
            changed_events.put_nowait(path)

        async def HandleDeletion(path: anyio.Path, original_file_path: anyio.Path | None = None) -> None:
            """Args: 削除されたパスと元のパス。Returns: None。"""
            deleted_events.put_nowait(path)

        with (
            patch('watchfiles.main.RustNotify', side_effect=CreateWatcher),
            patch.object(self.scanner, 'resolveRecordedPath', side_effect=ResolvePath),
            patch.object(self.scanner, '_RecordedScanTask__handleFileChange', side_effect=HandleChange),
            patch.object(self.scanner, '_RecordedScanTask__handleFileDeletion', side_effect=HandleDeletion),
        ):
            task = asyncio.create_task(self.scanner.watchRecordedFolders())
            try:
                # 最初のスナップショットの取得後にファイルを置く（初回スナップショットは変更通知にならない）
                await asyncio.wait_for(initial_snapshot_ready.wait(), timeout=5)
                await file_path.write_bytes(b'initial recording')
                self.assertEqual(await asyncio.wait_for(changed_events.get(), timeout=5), file_path)
                # 秒単位の mtime を比較するバックエンドでも確実に更新を検知できるようにする
                await asyncio.sleep(1.1)
                await file_path.write_bytes(b'updated and larger recording')
                self.assertEqual(await asyncio.wait_for(changed_events.get(), timeout=5), file_path)
                await file_path.unlink()
                self.assertEqual(await asyncio.wait_for(deleted_events.get(), timeout=5), file_path)
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
