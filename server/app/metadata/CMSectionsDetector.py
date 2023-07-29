
from app.models.RecordedVideo import RecordedVideo
from app.schemas import CMSection


class CMSectionsDetector:
    """ 録画 TS ファイルに含まれる CM 区間を検出するクラス """

    def __init__(self, recorded_video: RecordedVideo) -> None:
        """
        録画 TS ファイルに含まれる CM 区間を検出するクラスを初期化する

        Args:
            recorded_video (RecordedVideo): 録画ファイル情報を表すモデル
        """

        self.recorded_video = recorded_video


    def detect(self) -> list[CMSection]:
        """
        CM 区間を検出する

        Returns:
            list[CMSection]: CM 区間 (開始時刻, 終了時刻) のリスト
        """

        # TODO: CM 区間を検出する処理を実装する
        cm_sections = []
        return cm_sections
