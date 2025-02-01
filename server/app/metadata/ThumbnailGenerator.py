
import anyio
import asyncio
import cv2
import math
import numpy as np
import pathlib
import random
import time
import typer
from numpy.typing import NDArray
from typing import cast, ClassVar, Literal

from app import logging
from app import schemas
from app.config import LoadConfig
from app.constants import LIBRARY_PATH, STATIC_DIR, THUMBNAILS_DIR


class ThumbnailGenerator:
    """
    プレイヤーのシークバー用タイル画像と、候補区間内で最も良い1枚の代表サムネイルを生成するクラス (with o1-pro)
    """

    # サムネイルのタイル化の設定
    TILE_INTERVAL_SEC: ClassVar[float] = 5.0  # タイル化する間隔 (秒)
    TILE_SCALE: ClassVar[tuple[int, int]] = (480, 270)  # タイル化時の1フレーム解像度 (width, height)
    TILE_COLS: ClassVar[int] = 16  # タイルの横方向枚数 (480px * 16 = 7680px)

    # 顔検出の設定
    FACE_DETECTION_SCALE_FACTOR: ClassVar[float] = 1.2  # 顔検出時のスケールファクター
    FACE_DETECTION_MIN_NEIGHBORS: ClassVar[int] = 3  # 顔検出時の最小近傍数
    FACE_SIZE_WEIGHT: ClassVar[float] = 0.3  # 顔サイズによるスコアの重み
    FACE_SIZE_BASE_SCORE: ClassVar[float] = 10.0  # 顔サイズの基本スコア

    # 画質評価の重み付け
    SCORE_WEIGHTS: ClassVar[dict[str, float]] = {
        'std_lum': 1.0,  # 輝度の標準偏差
        'contrast': 0.8,  # コントラスト
        'sharpness': 0.02,  # シャープネス
    }

    # 画質評価のペナルティ
    BRIGHTNESS_PENALTY_THRESHOLD: ClassVar[tuple[int, int]] = (30, 225)  # 輝度のペナルティ閾値 (min, max)
    BRIGHTNESS_PENALTY_VALUE: ClassVar[float] = 50.0  # 輝度のペナルティ値

    # 顔検出用カスケード分類器のパス
    HUMAN_FACE_CASCADE_PATH: ClassVar[pathlib.Path] = pathlib.Path(cv2.__file__).parent / 'data' / 'haarcascade_frontalface_default.xml'
    ANIME_FACE_CASCADE_PATH: ClassVar[pathlib.Path] = STATIC_DIR / 'lbpcascade_animeface.xml'


    def __init__(
        self,
        file_path: anyio.Path,
        file_hash: str,
        duration_sec: float,
        candidate_time_ranges: list[tuple[float, float]],
        face_detection_mode: Literal['Human', 'Anime'] | None = None,
    ) -> None:
        """
        プレイヤーのシークバー用タイル画像と、候補区間内で最も良い1枚の代表サムネイルを生成するクラスを初期化する

        Args:
            file_path (anyio.Path): 動画ファイルのパス
            file_hash (str): 動画ファイルのハッシュ値（ファイル名の一意性を保証するため）
            duration_sec (float): 動画の再生時間(秒)
            candidate_time_ranges (list[tuple[float, float]]): 代表サムネ候補とする区間 [(start, end), ...]
            face_detection_mode (Literal['Human', 'Anime'] | None): 顔検出モード (デフォルト: None)
        """

        self.file_path = file_path
        self.duration_sec = duration_sec
        self.candidate_intervals = candidate_time_ranges
        self.face_detection_mode = face_detection_mode

        # ファイルハッシュをベースにしたファイル名を生成
        self.seekbar_tile_path = anyio.Path(str(THUMBNAILS_DIR / f"{file_hash}_seekbar.jpg"))
        self.representative_path = anyio.Path(str(THUMBNAILS_DIR / f"{file_hash}.jpg"))


    @classmethod
    def fromRecordedProgram(cls, recorded_program: schemas.RecordedProgram) -> 'ThumbnailGenerator':
        """
        RecordedProgram から ThumbnailGenerator を初期化する

        Args:
            recorded_program (schemas.RecordedProgram): 録画番組情報

        Returns:
            ThumbnailGenerator: 初期化された ThumbnailGenerator インスタンス
        """

        # ファイルパスと動画長を取得
        file_path = anyio.Path(recorded_program.recorded_video.file_path)
        duration_sec = recorded_program.duration

        # 録画マージンを除いた有効な時間範囲を計算
        start_time = recorded_program.recording_start_margin
        end_time = duration_sec - recorded_program.recording_end_margin

        # 番組前半の 25~40% の時間範囲を候補区間とする
        ## ネタバレ防止のため後半は避け、OP や CM と被りにくい範囲を選択
        middle_time = (end_time - start_time) / 2
        candidate_start = start_time + (middle_time - start_time) * 0.25
        candidate_end = start_time + (middle_time - start_time) * 0.40
        candidate_time_ranges = [(candidate_start, candidate_end)]

        # ジャンル情報から顔検出の要否を判断
        ## アニメが含まれている場合はアニメ顔検出を優先
        ## それ以外は実写人物が重要なジャンルかどうかで判断
        face_detection_mode: Literal['Human', 'Anime'] | None = None
        if recorded_program.genres:
            # アニメが含まれている場合はアニメ顔検出を優先
            if any('アニメ' in g['major'] or 'アニメ' in g['middle'] for g in recorded_program.genres):
                face_detection_mode = 'Anime'
            else:
                # 実写人物がサムネイルに写っていることが重要なジャンル
                human_face_genres = [
                    'ニュース・報道',
                    '情報・ワイドショー',
                    'ドラマ',
                    'バラエティ',
                    '映画',
                ]
                # 最初のジャンルの major を取得
                first_genre_major = recorded_program.genres[0]['major']
                if any(genre in first_genre_major for genre in human_face_genres):
                    face_detection_mode = 'Human'

        # コンストラクタに渡す
        return cls(
            file_path=file_path,
            file_hash=recorded_program.recorded_video.file_hash,
            duration_sec=duration_sec,
            candidate_time_ranges=candidate_time_ranges,
            face_detection_mode=face_detection_mode,
        )


    async def generate(self) -> None:
        """
        プレイヤーのシークバー用サムネイルタイル画像を生成し、
        さらに候補区間内のフレームから最も良い1枚を選び、代表サムネイルとして出力する
        """

        start_time = time.time()
        try:
            # 1. プレイヤーのシークバー用サムネイルタイル画像を生成
            if not await self.__generateThumbnailsTile():
                logging.error(f'{self.file_path}: Failed to generate seekbar tile image.')
                return

            # 2. プレイヤーのシークバー用サムネイルタイル画像を読み込み、各タイル(フレーム)を切り出し、
            #    そのタイムスタンプが candidate_intervals に含まれる場合だけ
            #    画質評価 + (必要なら) 顔検出してスコアを計算 → 最良を代表サムネイルとして取得
            best_thumbnail = await self.__extractBestFrameFromThumbnailTile()
            if best_thumbnail is None:
                logging.error(f'{self.file_path}: Failed to extract best frame from tile.')
                return

            # 3. 代表サムネイル画像をファイルに書き出し
            if not await self.__saveRepresentative(best_thumbnail):
                logging.error(f'{self.file_path}: Failed to save representative thumbnail.')
                return

            logging.info(f'{self.file_path}: Thumbnail generation completed. ({time.time() - start_time:.2f} sec)')

        except Exception as ex:
            # 予期せぬエラーのみここでキャッチ
            logging.error(f'{self.file_path}: Unexpected error in thumbnail generation:', exc_info=ex)
            return


    async def __generateThumbnailsTile(self) -> bool:
        """
        FFmpeg を使い、録画ファイル全体を対象にプレイヤーのシークバー用サムネイルタイル画像を生成する
        5秒ごとにフレームを抽出し、タイル化する

        Returns:
            bool: 成功時は True、失敗時は False
        """

        try:
            # フレーム数 = ceil(duration_sec / tile_interval_sec)
            # ※ ceil() を使うことで、端数でも切り捨てずに確実にすべての区間をカバー
            total_frames = int(math.ceil(self.duration_sec / self.TILE_INTERVAL_SEC))
            if total_frames < 1:
                # 短すぎるか、tile_interval_secが大きすぎる場合
                total_frames = 1

            # 実際の行数(縦のタイル数) = ceil(total_frames / tile_cols)
            # ※ ceil() を使うことで、最後の行が一部空いていても、すべてのフレームを表示
            tile_rows = math.ceil(total_frames / self.TILE_COLS)

            width, height = self.TILE_SCALE

            # フィルターチェーンを構築
            # 1. fps=1/N: N秒ごとにフレームを抽出
            # 2. scale=width:height: 指定サイズにリサイズ
            # 3. tile=WxH:padding=0:margin=0: タイル化 (余白なし)
            filter_chain = [
                # 5秒ごとにフレームを抽出
                f'fps=1/{self.TILE_INTERVAL_SEC}',
                # リサイズしてタイル化
                f'scale={width}:{height}',
                f'tile={self.TILE_COLS}x{tile_rows}:padding=0:margin=0',
            ]

            # 出力先ディレクトリが無い場合は作成
            thumbnails_dir = anyio.Path(str(THUMBNAILS_DIR))
            if not await thumbnails_dir.is_dir():
                await thumbnails_dir.mkdir(parents=True, exist_ok=True)

            # 非同期でプロセスを実行
            process = await asyncio.create_subprocess_exec(
                *[
                    LIBRARY_PATH['FFmpeg'],
                    # 上書きを許可
                    '-y',
                    # 入力ファイル
                    '-i', str(self.file_path),
                    # 1枚の出力画像
                    '-frames:v', '1',
                    # フィルターチェーンを結合
                    '-vf', ','.join(filter_chain),
                    # JPEG 品質 (2=高品質)
                    '-q:v', '2',
                    # 出力ファイル
                    str(self.seekbar_tile_path),
                ],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()

            # エラーチェック
            if process.returncode != 0:
                error_message = stderr.decode('utf-8', errors='ignore')
                logging.error(f'{self.file_path}: FFmpeg failed with return code {process.returncode}. Error: {error_message}')
                return False

            logging.info(f'{self.file_path}: Generated seekbar tile image.')
            return True

        except Exception as ex:
            logging.error(f'{self.file_path}: Error in seekbar tile generation:', exc_info=ex)
            return False


    async def __extractBestFrameFromThumbnailTile(self) -> NDArray[np.uint8] | None:
        """
        生成したシークバー用タイル画像から、候補区間内に相当するフレームだけを
        スコアリングし、最良の1枚を返す (画像は OpenCV 形式の BGR NDArray)
        顔検出オプションが指定されている場合は顔があるフレームのみ優先し、なければ全フレームから選ぶ
        スコアリングで適切な候補が見つからない場合は、ランダムに1枚を選択する

        Returns:
            NDArray[np.uint8] | None: 最良フレーム (BGR) / 予期せぬエラーが発生した場合のみ None
        """

        try:
            # タイル画像を読み込み (同期 I/O なので asyncio.to_thread() でラップ)
            tile_bgr = await asyncio.to_thread(cv2.imread, str(self.seekbar_tile_path))
            if tile_bgr is None:
                raise RuntimeError('Failed to read seekbar tile image.')

            height, width, _ = tile_bgr.shape
            tile_w, tile_h = self.TILE_SCALE

            # 総フレーム数を計算 ( rows * cols )
            # ※ rows = height / tile_h, cols = width / tile_w
            #   (タイルの端数が出る場合もあるが、ここでは切り捨て等で対処)
            cols = width // tile_w
            rows = height // tile_h
            total_frames = rows * cols

            # 顔検出器のロード (必要な場合のみ)
            face_cascade = None
            if self.face_detection_mode == 'Human':
                face_cascade = cv2.CascadeClassifier(str(self.HUMAN_FACE_CASCADE_PATH))
                logging.debug_simple(f'{self.file_path}: Loaded human face cascade.')
            elif self.face_detection_mode == 'Anime':
                face_cascade = cv2.CascadeClassifier(str(self.ANIME_FACE_CASCADE_PATH))
                logging.debug_simple(f'{self.file_path}: Loaded anime face cascade.')

            # いったん全フレームを評価して保持し、後で「顔あり」→無ければ「全体」という二段階で決める
            frames_info: list[tuple[int, float, bool, NDArray[np.uint8]]] = []
            # (index, score, found_face, sub_img)

            # 候補区間内のフレームを収集
            candidate_frames: list[tuple[int, NDArray[np.uint8]]] = []
            # (index, sub_img)

            for idx in range(total_frames):
                # このフレームの動画内時間(秒)
                time_offset = idx * self.TILE_INTERVAL_SEC
                # 候補区間に含まれているかどうか
                if not self.__inCandidateIntervals(time_offset):
                    continue

                # タイル上の座標
                row = idx // cols
                col = idx % cols
                y_start = row * tile_h
                x_start = col * tile_w
                sub_img = cast(NDArray[np.uint8], tile_bgr[y_start:y_start+tile_h, x_start:x_start+tile_w])

                # 候補区間内のフレームを収集
                candidate_frames.append((idx, sub_img))

                # スコア計算＋顔検出
                score, found_face = await asyncio.to_thread(
                    self.__computeScoreWithFace,
                    sub_img,
                    face_cascade
                )
                frames_info.append((idx, score, found_face, sub_img))

            # 候補区間内のフレームが1枚もない場合は、全フレームから1枚をランダムに選択
            if not candidate_frames:
                logging.warning(f'{self.file_path}: No frames found in candidate intervals. Selecting a random frame.')
                idx = random.randint(0, total_frames - 1)
                row = idx // cols
                col = idx % cols
                y_start = row * tile_h
                x_start = col * tile_w
                return cast(NDArray[np.uint8], tile_bgr[y_start:y_start+tile_h, x_start:x_start+tile_w])

            # スコアリングで適切な候補を選定
            if frames_info:
                # 顔ありフレームだけ抜き出す
                face_frames = [(idx, sc, True, im) for (idx, sc, f, im) in frames_info if f]

                if face_cascade is not None and face_frames:
                    # 顔ありのみから最大スコアを選ぶ
                    _, _, _, best_img = max(face_frames, key=lambda x: x[1])
                    return best_img
                else:
                    # 顔検出無し or 一つも顔が見つからなかった場合
                    _, _, _, best_img = max(frames_info, key=lambda x: x[1])
                    return best_img

            # スコアリングで適切な候補が見つからなかった場合は、候補区間内からランダムに1枚を選択
            logging.warning(f'{self.file_path}: No suitable frame found by scoring. Selecting a random frame from candidate intervals.')
            _, best_img = random.choice(candidate_frames)
            return best_img

        except Exception as ex:
            logging.error(f'{self.file_path}: Error in best frame extraction:', exc_info=ex)
            return None


    async def __saveRepresentative(self, img_bgr: NDArray[np.uint8]) -> bool:
        """
        代表サムネイルを JPEG ファイルに保存する

        Args:
            img_bgr (NDArray[np.uint8]): 保存する画像データ (BGR)

        Returns:
            bool: 成功時は True、失敗時は False
        """

        try:
            # 万が一出力先ディレクトリが無い場合は作成 (通常存在するはず)
            thumbnails_dir = anyio.Path(str(THUMBNAILS_DIR))
            if not await thumbnails_dir.is_dir():
                await thumbnails_dir.mkdir(parents=True, exist_ok=True)

            # 書き込み
            if not await asyncio.to_thread(cv2.imwrite, str(self.representative_path), img_bgr):
                logging.error(f'{self.file_path}: Failed to write representative thumbnail.')
                return False

            logging.info(f'{self.file_path}: Saved representative thumbnail.')
            return True

        except Exception as ex:
            logging.error(f'{self.file_path}: Error in representative thumbnail saving:', exc_info=ex)
            return False


    def __inCandidateIntervals(self, sec: float) -> bool:
        """
        sec(秒)が candidate_intervals (start, end) のいずれかに入っているかどうか

        Args:
            sec (float): 判定する時刻 (秒)

        Returns:
            bool: 候補区間内なら True
        """

        for (start, end) in self.candidate_intervals:
            if start <= sec <= end:
                return True
        return False


    def __computeScoreWithFace(
        self,
        img_bgr: NDArray[np.uint8],
        face_cascade: cv2.CascadeClassifier | None
    ) -> tuple[float, bool]:
        """
        画質スコア(輝度・コントラスト・シャープネス)を計算し、
        顔検出があれば found_face=True を返す
        顔が検出された場合、その大きさに応じてスコアを加算する

        Args:
            img_bgr (NDArray[np.uint8]): 評価する画像データ (BGR)
            face_cascade (cv2.CascadeClassifier | None): 顔検出器

        Returns:
            tuple[float, bool]: (score, found_face)
        """

        found_face = False
        face_size_score = 0.0

        # 顔検出
        if face_cascade is not None:
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=self.FACE_DETECTION_SCALE_FACTOR,
                minNeighbors=self.FACE_DETECTION_MIN_NEIGHBORS
            )
            if len(faces) > 0:
                found_face = True
                # 最も大きい顔を基準にスコアを計算
                max_face_area = max(w * h for (_, _, w, h) in faces)
                img_area = img_bgr.shape[0] * img_bgr.shape[1]
                # 顔の面積比を計算 (0.0 ~ 1.0)
                face_area_ratio = max_face_area / img_area
                # 基本スコアに面積比を掛けてスコアを計算
                face_size_score = self.FACE_SIZE_BASE_SCORE * face_area_ratio

        # スコア計算
        # (1) 輝度 Y
        img_float = img_bgr.astype(np.float32)
        y = 0.2126*img_float[:,:,2] + 0.7152*img_float[:,:,1] + 0.0722*img_float[:,:,0]
        mean_lum = np.mean(y)       # 平均輝度
        std_lum  = np.std(y)        # 分散(均一度の逆)

        # (2) コントラスト: 10%タイルと90%タイルの差
        y_flat = y.flatten()
        p10 = np.percentile(y_flat, 10)
        p90 = np.percentile(y_flat, 90)
        contrast = p90 - p10

        # (3) シャープネス (Laplacian の分散)
        lap = cv2.Laplacian(img_bgr, cv2.CV_64F)
        sharpness = lap.var()

        # スコア計算
        # - mean_lum が極端に暗い or 明るい時は減点
        # - std_lum, contrast, sharpness を加点要素とする
        brightness_penalty = 0.0
        if mean_lum < self.BRIGHTNESS_PENALTY_THRESHOLD[0] or mean_lum > self.BRIGHTNESS_PENALTY_THRESHOLD[1]:
            brightness_penalty = self.BRIGHTNESS_PENALTY_VALUE

        # 重み付けしてスコアを計算 (顔サイズのスコアを追加)
        score = (
            std_lum * self.SCORE_WEIGHTS['std_lum'] +
            contrast * self.SCORE_WEIGHTS['contrast'] +
            sharpness * self.SCORE_WEIGHTS['sharpness'] +
            face_size_score * self.FACE_SIZE_WEIGHT -
            brightness_penalty
        )

        return (score, found_face)


if __name__ == "__main__":
    # デバッグ用: サムネイル画像を生成する
    # Usage: poetry run python -m app.metadata.ThumbnailGenerator /path/to/recorded_file.ts
    def main(
        file_path: pathlib.Path = typer.Argument(
            ...,
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="録画ファイルのパス",
        ),
        candidate_start: float | None = typer.Option(
            None,
            "--start",
            "-s",
            help="候補区間の開始時刻 (秒) / 指定しない場合はメタデータから自動取得",
        ),
        candidate_end: float | None = typer.Option(
            None,
            "--end",
            "-e",
            help="候補区間の終了時刻 (秒) / 指定しない場合はメタデータから自動取得",
        ),
        face_detection_mode: Literal['Human', 'Anime'] | None = typer.Option(
            None,
            "--face-detection",
            "-f",
            help="顔検出モード (Human/Anime) / 指定しない場合はメタデータから自動取得",
        ),
    ) -> None:
        """
        録画ファイルからサムネイルを生成する
        メタデータ解析結果を用いて自動的にパラメータを設定するが、
        オプションで明示的に指定された場合はそちらを優先する
        """

        # 設定を読み込む (必須)
        LoadConfig(bypass_validation=True)

        # メタデータを解析
        from app.metadata.MetadataAnalyzer import MetadataAnalyzer
        analyzer = MetadataAnalyzer(file_path)
        recorded_program = analyzer.analyze()
        if recorded_program is None:
            print(f'Error: {file_path} is not a valid recorded file.')
            return

        # ThumbnailGenerator を初期化
        ## オプションで指定されていない場合は、メタデータから自動的にパラメータを設定
        generator = ThumbnailGenerator.fromRecordedProgram(recorded_program)

        # オプションで指定されたパラメータがある場合は上書き
        if candidate_start is not None and candidate_end is not None:
            generator.candidate_intervals = [(candidate_start, candidate_end)]
        if face_detection_mode is not None:
            generator.face_detection_mode = face_detection_mode

        # サムネイルを生成
        asyncio.run(generator.generate())
        print(f"Seekbar tile   -> {generator.seekbar_tile_path}")
        print(f"Representative -> {generator.representative_path}")

    typer.run(main)
