
from pathlib import Path
from app.models.RecordedVideo import RecordedVideo
from app.schemas import CMSection
from app import logging


class CMSectionsDetector:
    """ 録画 TS ファイルに含まれる CM 区間を検出するクラス """

    def __init__(self, recorded_video: RecordedVideo) -> None:
        """
        録画 TS ファイルに含まれる CM 区間を検出するクラスを初期化する

        Args:
            recorded_video (RecordedVideo): 録画ファイル情報を表すモデル
        """

        self.recorded_video = recorded_video

    def _time_to_seconds(self, time_str: str) -> float:
        """
        時刻文字列 (HH:MM:SS.mmm) を秒単位の float に変換する

        Args:
            time_str (str): 時刻文字列 (HH:MM:SS.mmm)

        Returns:
            float: 秒単位の時刻
        """

        # 時、分、秒をそれぞれ分割
        hours, minutes, seconds = time_str.strip().split(':')
        # 時と分は整数に、秒は小数に変換して合計を返す
        return float(hours) * 3600 + float(minutes) * 60 + float(seconds)

    def _detect_from_chapter_file(self, chapter_file_path: Path) -> list[CMSection]:
        """
        チャプターファイルからCM区間を検出する

        Args:
            chapter_file_path (Path): チャプターファイルのパス

        Returns:
            list[CMSection]: CM区間のリスト
        """

        # チャプター情報を格納するリスト
        chapters: list[tuple[int, str, float]] = []  # (番号, 名前, 時刻)
        cm_sections: list[CMSection] = []

        # チャプターファイルを読み込む
        try:
            with open(chapter_file_path, 'r') as f:
                lines = f.readlines()
        except Exception as ex:
            logging.error(f'{chapter_file_path}: チャプターファイルの読み込みに失敗しました:', exc_info=ex)
            return []

        # 2行ずつ処理 (チャプター時刻行とチャプター名行)
        for i in range(0, len(lines), 2):
            if i + 1 >= len(lines):
                break

            time_line = lines[i].strip()
            name_line = lines[i + 1].strip()

            # チャプター行のフォーマット確認
            if not (time_line.startswith('CHAPTER') and name_line.startswith('CHAPTER') and
                   'NAME' in name_line):
                continue

            try:
                # チャプター番号を取得
                chapter_num = int(time_line[7:9])
                # チャプター時刻を取得
                chapter_time = self._time_to_seconds(time_line.split('=')[1])
                # チャプター名を取得
                chapter_name = name_line.split('=')[1]

                if chapter_time <= float(self.recorded_video.duration):
                    chapters.append((chapter_num, chapter_name, chapter_time))
                else:
                    logging.warning(f'{chapter_file_path}: チャプター時刻 {chapter_time} が動画再生時間 {self.recorded_video.duration} を超えています。スキップします。')
            except Exception as ex:
                logging.warning(f'{chapter_file_path}: チャプターデータの解析に失敗しました (行 {i}-{i+1}): {time_line}, {name_line}', exc_info=ex)
                continue

        # CM 区間を検出
        current_cm_start: float | None = None

        for i, (_, name, time) in enumerate(chapters):
            # CM 開始位置を検出
            if name.startswith('CM') and current_cm_start is None:
                current_cm_start = time
            # CM 終了位置を検出
            elif not name.startswith('CM') and current_cm_start is not None:
                cm_sections.append({
                    'start_time': current_cm_start,
                    'end_time': time,
                })
                current_cm_start = None

        # 最後のチャプターが CM で終わっている場合
        if current_cm_start is not None:
            cm_sections.append({
                'start_time': current_cm_start,
                'end_time': float(self.recorded_video.duration),
            })

        return cm_sections

    def detect(self) -> list[CMSection]:
        """
        CM 区間を検出する

        Returns:
            list[CMSection]: CM 区間 (開始時刻, 終了時刻) のリスト
        """

        # チャプターファイル (ファイル名のみ取得し、拡張子を .chapter.txt に変更)
        file_path = Path(self.recorded_video.file_path)
        chapter_file_path = file_path.with_name(f"{file_path.stem}.chapter.txt")

        # チャプターファイルが存在する場合はチャプターファイルから CM 区間を検出
        if chapter_file_path.exists():
            return self._detect_from_chapter_file(chapter_file_path)

         # TODO: CM 区間を検出する処理を実装する
        return []

    async def save_to_db(self) -> None:
        """
        CM 区間を検出し、データベースに保存する

        Returns:
            None
        """
        try:
            # CM 区間を検出
            cm_sections = self.detect()

            # 検出結果をデータベースに保存
            if cm_sections and len(cm_sections) > 0:
                # logging.debugで各セクションの時間をprint
                for cm_section in cm_sections:
                    logging.debug(f'{self.recorded_video.file_path}: CM section detected: {cm_section["start_time"]} - {cm_section["end_time"]}')
                self.recorded_video.cm_sections = cm_sections
                await self.recorded_video.save()
                logging.info(f'{self.recorded_video.file_path}: Detected and saved {len(cm_sections)} CM sections.')
            else:
                logging.info(f'{self.recorded_video.file_path}: No CM sections detected.')
        except Exception as ex:
            logging.error(f'{self.recorded_video.file_path}: Error saving CM sections to DB:', exc_info=ex)
