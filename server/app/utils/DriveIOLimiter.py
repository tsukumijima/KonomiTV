
from __future__ import annotations

import asyncio
import sys
from typing import ClassVar

import anyio
import psutil


class DriveIOLimiter:
    """
    HDD ごとの同時実行を制限するクラス
    同一 HDD に対して同時に1つまでしかバックグラウンドタスクを実行できないようにする
    """

    # クラス変数として Semaphore の辞書を保持
    # key: ドライブ識別子 (Windows) またはマウントポイント (Linux)
    # value: その HDD 用の Semaphore
    _drive_semaphores: ClassVar[dict[str, asyncio.Semaphore]] = {}


    @staticmethod
    def getDriveID(target_path: anyio.Path) -> str:
        """
        パスからドライブまたはマウントポイントを特定し、そのパスを ID として返す
        Windows の場合はドライブレター、Linux の場合はマウントポイントを返す

        Args:
            path (anyio.Path): 対象ファイルパス

        Returns:
            str: ドライブ識別子 (Windows) またはマウントポイント (Linux)
        """

        try:
            # パスを文字列に変換（psutilで使用するため）
            target_path_str = str(target_path)

            if psutil.WINDOWS:
                # Windows の場合はドライブレターを返す
                return target_path_str[0].upper() + ':'
            else:
                # Linux の場合はマウントポイントを取得
                partitions = psutil.disk_partitions(all=True)
                mount_point = ''
                target_parts = target_path.parts

                # 最も適切なマウントポイントを探す
                for partition in partitions:
                    mount_path = anyio.Path(partition.mountpoint)
                    mount_parts = mount_path.parts

                    # マウントポイントがターゲットパスの先頭部分と完全に一致するか確認
                    if (len(mount_parts) <= len(target_parts) and
                        all(mp == tp for mp, tp in zip(mount_parts, target_parts)) and
                        len(str(mount_path)) > len(mount_point)):
                        mount_point = str(mount_path)

                if not mount_point:
                    # マウントポイントが見つからない場合はパスをそのまま返す
                    return target_path_str

                # マウントポイントを返す
                return mount_point

        except Exception:
            # エラー時はパスをそのまま返す
            return str(target_path)


    @classmethod
    def getSemaphore(cls, path: anyio.Path) -> asyncio.Semaphore:
        """
        指定されたパスの HDD 用の Semaphore を取得する
        同一 HDD に対して同時に1つまでしかバックグラウンドタスクを実行できないようにする

        Args:
            path (anyio.Path): 対象ファイルパス

        Returns:
            asyncio.Semaphore: 対応する HDD 用の Semaphore
        """

        # ドライブの識別子を取得
        drive_id = cls.getDriveID(path)

        # HDD ごとのセマフォがなければ作成
        if drive_id not in cls._drive_semaphores:
            # 同時に1つのタスクしか実行できないようにする
            cls._drive_semaphores[drive_id] = asyncio.Semaphore(1)

        return cls._drive_semaphores[drive_id]


if __name__ == '__main__':
    print(DriveIOLimiter.getDriveID(anyio.Path(sys.argv[1])))
