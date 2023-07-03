
from pathlib import Path

from app.models.RecordedVideo import RecordedVideo


class CMSectionsDetector:
    """ 録画 TS ファイルに含まれる CM 区間を検出するクラス """

    def __init__(self, recorded_ts_path: Path) -> None:
        """
        録画 TS ファイルに含まれる CM 区間を検出するクラスを初期化する

        Args:
            recorded_ts_path (Path): 録画 TS ファイルのパス
        """

        self.recorded_ts_path = recorded_ts_path


    def detect(self, recorded_video: RecordedVideo) -> list[tuple[float, float]]:
        """
        CM 区間を検出する

        Args:
            recorded_video (RecordedVideo): 録画ファイル情報を表すモデル

        Returns:
            list[tuple[float, float]]: CM 区間 (開始時刻, 終了時刻) のリスト
        """

        # TODO: CM 区間を検出する処理を実装する
        cm_sections = []
        return cm_sections
