
import ariblib
from pathlib import Path

from app.models import Channel
from app.models import RecordedProgram
from app.models import RecordedVideo


class TSInfoAnalyzer:
    """ 録画 TS ファイル内に含まれる番組情報を解析するクラス """

    def __init__(self, recorded_ts_path: Path) -> None:
        """
        録画 TS ファイル内に含まれる番組情報を解析するクラスを初期化する

        Args:
            recorded_ts_path (Path): 録画 TS ファイルのパス
        """

        # TS ファイルを開く
        # チャンクは 1000（だいたい 0.1 ～ 0.2 秒間隔）に設定
        self.ts = ariblib.tsopen(recorded_ts_path, chunk=1000)


    def analyze(self, recorded_video: RecordedVideo) -> tuple[RecordedProgram, Channel | None]:
        """
        録画 TS ファイル内に含まれる番組情報を解析し、データベースに格納するモデルを作成する

        Args:
            recorded_video (RecordedVideo): 録画ファイル情報を表すモデル

        Returns:
            tuple[RecordedProgram, Channel | None]: 録画番組情報とチャンネル情報を表すモデルのタプル
        """

        # TODO!!!!!

        # 録画番組情報のモデルを作成
        recorded_program = RecordedProgram()

        # チャンネル情報のモデルを作成
        channel = Channel()

        return recorded_program, channel
