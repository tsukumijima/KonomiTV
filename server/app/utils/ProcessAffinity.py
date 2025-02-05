
from __future__ import annotations

import psutil
import time
from typing import ClassVar


class ProcessAffinity:
    """
    バックグラウンドプロセスの CPU アフィニティを管理するユーティリティクラス
    負荷の低いコアを選択して割り当てることで、他のプロセスへの影響を最小限に抑える
    """

    # 負荷を監視する期間 (秒)
    MONITORING_PERIOD: ClassVar[float] = 1.0

    # 最後に CPU 使用率を取得した時刻
    _last_check_time: ClassVar[float] = 0.0
    # 前回取得した CPU 使用率
    _last_cpu_percent: ClassVar[list[float]] | None = None


    @classmethod
    def getLeastLoadedCPU(cls) -> int:
        """
        現在最も負荷の低い CPU コアのインデックスを取得する
        CPU 使用率の取得は MONITORING_PERIOD 秒ごとにキャッシュを更新する

        Returns:
            int: 最も負荷の低い CPU コアのインデックス
        """

        # 前回の取得から MONITORING_PERIOD 秒以上経過していたら CPU 使用率を再取得
        current_time = time.time()
        if cls._last_check_time == 0.0 or current_time - cls._last_check_time >= cls.MONITORING_PERIOD:
            # CPU ごとの使用率を取得 (interval=None で前回値との比較による計算を行わない)
            cls._last_cpu_percent = psutil.cpu_percent(interval=None, percpu=True)
            cls._last_check_time = current_time

        # 最も負荷の低い CPU コアのインデックスを返す
        assert cls._last_cpu_percent is not None
        return cls._last_cpu_percent.index(min(cls._last_cpu_percent))


    @classmethod
    def setProcessAffinity(cls, pid: int) -> None:
        """
        指定されたプロセスの CPU アフィニティを、現在最も負荷の低い CPU コアに設定する
        これにより、当該プロセスの CPU 使用率を1コアに集中させ、他のプロセスへの影響を最小限に抑える

        Args:
            pid (int): 対象プロセスの PID
        """

        try:
            # プロセスオブジェクトを取得
            process = psutil.Process(pid)
            # 最も負荷の低い CPU コアを取得
            cpu_index = cls.getLeastLoadedCPU()
            # CPU アフィニティを設定 (指定したコアのみを使用)
            process.cpu_affinity([cpu_index])

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            # プロセスが存在しない、アクセス権がない、タイムアウトした場合は無視
            pass
