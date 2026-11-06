
from __future__ import annotations

import asyncio
import sys
import time
from typing import Any, ClassVar

import anyio
import psutil


class DriveIOLimiter:
    """
    HDD ごとの同時実行を制限するクラス
    同一 HDD に対して同時に1つまでしかバックグラウンドタスクを実行できないようにする
    ネットワークドライブは、呼び出し元が指定した本数まで同時に実行できる
    """

    # ネットワークドライブとみなすファイルシステムの種類 (Linux)
    NETWORK_FILESYSTEMS: ClassVar[tuple[str, ...]] = ('cifs', 'smb', 'smbfs', 'smb3', 'nfs', 'nfs4', 'fuse.sshfs')

    # クラス変数として Semaphore の辞書を保持
    # key: ドライブ識別子と同時実行数の組
    # value: その HDD 用の Semaphore
    _drive_semaphores: ClassVar[dict[tuple[str, int], asyncio.Semaphore]] = {}

    # Linux のマウントの一覧と、取得した時刻 (time.monotonic() の値)
    ## キャプチャの一括スキャンはファイルごとにドライブを判定するため、毎回取得すると百万枚で合計数分イベントループを占有する
    ## マウントの追加や解除を反映できるよう、一定の時間がたったら取得し直す
    ## psutil は型の情報を同梱していないため、要素の型は Any にする
    _partitions: ClassVar[list[Any]] = []
    _partitions_fetched_at: ClassVar[float | None] = None

    # マウントの一覧を取得し直すまでの秒数
    PARTITIONS_CACHE_SECONDS: ClassVar[float] = 60.0


    @classmethod
    def getDriveID(cls, target_path: anyio.Path) -> tuple[str, bool]:
        """
        パスからドライブを特定し、ドライブ識別子と、ネットワークドライブかどうかを返す
        Windows の場合はドライブレター (UNC の場合はサーバーと共有名)、Linux の場合はマウントしているデバイスを返す

        Args:
            target_path (anyio.Path): 対象ファイルパス

        Returns:
            tuple[str, bool]: ドライブ識別子と、ネットワークドライブかどうか
        """

        try:
            # パスを文字列に変換（psutilで使用するため）
            target_path_str = str(target_path)

            if psutil.WINDOWS:
                # UNC はドライブレターを持たないため、サーバーと共有名を識別子にする
                if target_path_str.startswith('\\\\'):
                    return '\\'.join(target_path_str.split('\\')[:4]).lower(), True
                # Windows の場合はドライブレターを返す
                return target_path_str[0].upper() + ':', False
            else:
                # Linux の場合はマウントポイントを取得 (一定の時間は前回取得した一覧を使う)
                now = time.monotonic()
                if cls._partitions_fetched_at is None or now - cls._partitions_fetched_at >= cls.PARTITIONS_CACHE_SECONDS:
                    cls._partitions = psutil.disk_partitions(all=True)
                    cls._partitions_fetched_at = now
                partitions = cls._partitions
                matched_partition = None
                target_parts = target_path.parts

                # 最も適切なマウントポイントを探す
                for partition in partitions:
                    mount_path = anyio.Path(partition.mountpoint)
                    mount_parts = mount_path.parts

                    # マウントポイントがターゲットパスの先頭部分と完全に一致するか確認
                    if (len(mount_parts) <= len(target_parts) and
                        all(mp == tp for mp, tp in zip(mount_parts, target_parts)) and
                        (matched_partition is None or len(partition.mountpoint) > len(matched_partition.mountpoint))):
                        matched_partition = partition

                if matched_partition is None:
                    # マウントポイントが見つからない場合はパスをそのまま返す
                    return target_path_str, False

                # 同じデバイスを複数の場所にマウントしていても同じドライブとみなすため、デバイスを返す
                is_network = matched_partition.fstype.lower() in cls.NETWORK_FILESYSTEMS or 'remote' in matched_partition.opts.split(',')
                return matched_partition.device, is_network

        except Exception:
            # エラー時はパスをそのまま返す
            return str(target_path), False


    @classmethod
    def getSemaphore(cls, path: anyio.Path, network_concurrency: int = 1) -> asyncio.Semaphore:
        """
        指定されたパスの HDD 用の Semaphore を取得する
        同一 HDD に対して同時に1つまでしかバックグラウンドタスクを実行できないようにする
        ネットワークドライブでは、network_concurrency に指定した本数まで同時に実行できる

        Args:
            path (anyio.Path): 対象ファイルパス
            network_concurrency (int): ネットワークドライブで同時に実行できる数 (録画ファイルの解析は 1、キャプチャの読み込みは 4)

        Returns:
            asyncio.Semaphore: 対応する HDD 用の Semaphore
        """

        # ドライブの識別子を取得
        drive_id, is_network = cls.getDriveID(path)

        # 同時実行数ごとのセマフォがなければ作成
        ## ローカルのドライブは呼び出し元にかかわらず1つにして、録画ファイルの解析とキャプチャの読み込みで取り合う
        concurrency = network_concurrency if is_network is True else 1
        if (drive_id, concurrency) not in cls._drive_semaphores:
            cls._drive_semaphores[(drive_id, concurrency)] = asyncio.Semaphore(concurrency)

        return cls._drive_semaphores[(drive_id, concurrency)]


if __name__ == '__main__':
    print(DriveIOLimiter.getDriveID(anyio.Path(sys.argv[1])))
