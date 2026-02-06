
from __future__ import annotations

import asyncio
import heapq
from typing import TYPE_CHECKING

import anyio

from app import logging


if TYPE_CHECKING:
    from app.metadata.RecordedScanTask import PrioritizedFile


class FileProcessingQueue:
    """
    録画ファイル処理の優先度付きキューを管理するクラス

    このクラスは録画フォルダのバッチスキャンとファイル監視の両方で使用され、
    新しい録画ファイルを優先的に処理するための優先度管理を行う

    主な責務:
    - バッチスキャン時のファイルを新しい順（file_created_at 降順）にソートして処理
    - ファイル監視イベントで検出された新規ファイルを優先キューに追加
    - 優先キューのファイルをバッチスキャンの残りファイルより先に処理
    - 重複処理の防止

    内部実装:
    - heapq を使用したミニヒープで優先度管理を行う
    - heapq は最小値を先に取り出すため、priority には負のタイムスタンプを使用する
      （新しいファイル = 大きいタイムスタンプ = 負にすると小さい値 = 高優先度）

    使用例:
        queue = FileProcessingQueue()

        # バッチスキャン開始時: 収集したファイルをロード
        await queue.loadBatchFiles(collected_files)

        # ファイル監視で新規ファイル検出時: 優先キューに追加
        await queue.addPriorityFile(new_prioritized_file)

        # 処理ループ: 次のファイルを取得して処理
        while (file := await queue.getNextFile()) is not None:
            await process_file(file)
            await queue.markProcessed(file.file_path)
    """

    def __init__(self) -> None:
        """
        ファイル処理キューを初期化する
        """

        # 優先キュー（ファイル監視で検出された新規ファイル用）
        # heapq で管理し、新しいファイルを優先して処理する
        # バッチスキャン中にファイル監視で検出されたファイルは、このキューに追加される
        # このキューのファイルはバッチスキャンの残りファイルより先に処理される
        self._priority_heap: list[PrioritizedFile] = []

        # バッチスキャン用のファイルリスト（ソート済み）
        # バッチスキャン開始時に loadBatchFiles() で一括ロードされる
        # 優先キューが空の時にこのリストからファイルが取り出される
        self._batch_files: list[PrioritizedFile] = []

        # バッチスキャン用リストの現在のインデックス
        # getNextFile() で次に取り出すファイルの位置を示す
        self._batch_index: int = 0

        # 処理済みファイルパスのセット（重複処理を防ぐため）
        # ファイルパスは文字列として保存される
        self._processed_paths: set[str] = set()

        # asyncio 環境でのスレッドセーフなアクセスのためのロック
        # 複数の asyncio タスクから同時にアクセスされる可能性があるため必要
        self._lock: asyncio.Lock = asyncio.Lock()

    async def loadBatchFiles(self, files: list[PrioritizedFile]) -> None:
        """
        バッチスキャン対象のファイルを一括ロードする

        渡されたファイルリストは priority 順（新しい順）にソートされ、
        以降 getNextFile() で順次取り出されるようになる

        Args:
            files: PrioritizedFile のリスト（RecordedScanTask で収集されたファイル）

        Note:
            このメソッドは通常バッチスキャン開始時に1回だけ呼び出される
            ソートは priority フィールドの昇順で行われる（負のタイムスタンプのため新しいファイルが先）
        """

        async with self._lock:
            # priority でソート（小さい = 新しい = 先に処理）
            # PrioritizedFile は order=True で定義されているため、そのまま sorted() で比較可能
            self._batch_files = sorted(files, key=lambda f: f.priority)
            self._batch_index = 0
            logging.info(f'FileProcessingQueue: Loaded {len(self._batch_files)} files for batch processing.')

    async def addPriorityFile(self, prioritized_file: PrioritizedFile) -> None:
        """
        優先キューに新規ファイルを追加する

        このメソッドはファイル監視で新規ファイルが検出された際に呼び出される
        追加されたファイルは、バッチスキャンの残りファイルより先に処理される

        Args:
            prioritized_file: 追加するファイル（PrioritizedFile インスタンス）

        Note:
            - 既に処理済みのファイルは追加されない（重複防止）
            - heapq.heappush() により O(log n) の計算量で挿入される
        """

        async with self._lock:
            # 既に処理済みのファイルは追加しない
            if str(prioritized_file.file_path) in self._processed_paths:
                return
            heapq.heappush(self._priority_heap, prioritized_file)
            logging.debug(f'FileProcessingQueue: Added priority file: {prioritized_file.file_path}')

    async def getNextFile(self) -> PrioritizedFile | None:
        """
        次に処理すべきファイルを取得する

        優先キューにファイルがあればそちらを優先して返し、
        なければバッチリストから順次取り出して返す
        両方が空の場合は None を返す

        Returns:
            PrioritizedFile | None: 次に処理すべきファイル、または None（キューが空の場合）

        Note:
            - 既に処理済みのファイルは自動的にスキップされる
            - 優先キューからは heapq.heappop() で取り出されるため、常に最新のファイルが返される
        """

        async with self._lock:
            # 優先キューを先にチェック（ファイル監視で検出された新規ファイルを優先）
            while self._priority_heap:
                file = heapq.heappop(self._priority_heap)
                # 既に処理済みならスキップ
                if str(file.file_path) not in self._processed_paths:
                    return file

            # 優先キューが空ならバッチリストから取得
            while self._batch_index < len(self._batch_files):
                file = self._batch_files[self._batch_index]
                self._batch_index += 1
                # 既に処理済みならスキップ
                if str(file.file_path) not in self._processed_paths:
                    return file

            return None

    async def markProcessed(self, file_path: anyio.Path) -> None:
        """
        ファイルを処理済みとしてマークする

        このメソッドはファイルの処理が完了した後に呼び出され、
        同じファイルが再度処理されないようにする

        Args:
            file_path: 処理済みのファイルパス
        """

        async with self._lock:
            self._processed_paths.add(str(file_path))

    async def isProcessed(self, file_path: anyio.Path) -> bool:
        """
        ファイルが既に処理済みかどうかを確認する

        Args:
            file_path: 確認するファイルパス

        Returns:
            bool: 処理済みの場合 True、未処理の場合 False
        """

        async with self._lock:
            return str(file_path) in self._processed_paths

    async def clear(self) -> None:
        """
        キューをクリアする

        すべての内部状態（優先キュー、バッチリスト、処理済みセット）をリセットする
        通常、バッチスキャンが完了した後や、新しいスキャンを開始する前に呼び出される
        """

        async with self._lock:
            self._priority_heap.clear()
            self._batch_files.clear()
            self._batch_index = 0
            self._processed_paths.clear()

    async def getPendingCount(self) -> int:
        """
        未処理のファイル数を取得する

        Returns:
            int: 優先キューとバッチリストの残りファイル数の合計

        Note:
            この数値は概算であり、処理済みとしてマークされているがキューに残っている
            ファイルも含まれる可能性がある
        """

        async with self._lock:
            priority_count = len(self._priority_heap)
            batch_remaining = len(self._batch_files) - self._batch_index
            return priority_count + batch_remaining
