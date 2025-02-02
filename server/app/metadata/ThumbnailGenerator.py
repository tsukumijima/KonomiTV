
from __future__ import annotations

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
from typing import cast, Any, ClassVar, Literal

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
    FACE_SIZE_WEIGHT: ClassVar[float] = 0.3  # 顔サイズによるスコアの重み（実写向け）
    ANIME_FACE_SIZE_WEIGHT: ClassVar[float] = 0.8  # アニメの顔サイズによるスコアの重み
    FACE_SIZE_BASE_SCORE: ClassVar[float] = 10.0  # 顔サイズの基本スコア

    # レターボックス検出の設定
    LETTERBOX_THRESHOLD: ClassVar[int] = 30  # レターボックス判定の輝度閾値
    LETTERBOX_MIN_HEIGHT_RATIO: ClassVar[float] = 0.05  # 最小の黒帯の高さ比率（画像の高さに対する割合）
    LETTERBOX_MAX_HEIGHT_RATIO: ClassVar[float] = 0.25  # 最大の黒帯の高さ比率
    LETTERBOX_UNIFORMITY_THRESHOLD: ClassVar[float] = 5.0  # 黒帯の一様性判定の閾値（標準偏差）

    # 画質評価の重み付け
    SCORE_WEIGHTS: ClassVar[dict[str, float]] = {
        'std_lum': 0.8,  # 輝度の標準偏差 (全体的な明暗の差)
        'contrast': 1.5,  # コントラスト (明暗の差の大きさ)
        'sharpness': 0.02,  # シャープネス
        'edge_density': 0.8,  # エッジ密度 (情報量の指標)
        'entropy': 1.0,  # エントロピー (情報量の指標)
    }

    # 画質評価のペナルティ
    BRIGHTNESS_PENALTY_THRESHOLD: ClassVar[tuple[int, int]] = (20, 235)  # 輝度のペナルティ閾値 (min, max)
    BRIGHTNESS_PENALTY_VALUE: ClassVar[float] = 50.0  # 輝度のペナルティ値

    # コントラスト評価の設定
    CONTRAST_PERCENTILE_LOW: ClassVar[int] = 5  # コントラスト計算時の下位パーセンタイル
    CONTRAST_PERCENTILE_HIGH: ClassVar[int] = 95  # コントラスト計算時の上位パーセンタイル

    # 情報量評価の設定
    EDGE_DENSITY_TARGET: ClassVar[float] = 0.15  # 目標とするエッジ密度 (0.0 ~ 1.0)
    EDGE_DENSITY_TOLERANCE: ClassVar[float] = 0.1  # エッジ密度の許容範囲
    ENTROPY_TARGET: ClassVar[float] = 5.0  # 目標とするエントロピー値
    ENTROPY_TOLERANCE: ClassVar[float] = 2.0  # エントロピーの許容範囲

    # 顔検出用カスケード分類器のパス
    HUMAN_FACE_CASCADE_PATH: ClassVar[pathlib.Path] = pathlib.Path(cv2.__file__).parent / 'data' / 'haarcascade_frontalface_default.xml'
    ANIME_FACE_CASCADE_PATH: ClassVar[pathlib.Path] = STATIC_DIR / 'lbpcascade_animeface.xml'

    # 単色判定の設定
    COLOR_VARIANCE_THRESHOLD: ClassVar[float] = 10.0  # 各チャンネルの分散がこの値以下なら単色とみなす
    BLACK_THRESHOLD: ClassVar[int] = 30  # 平均輝度がこの値以下なら黒とみなす（ログ出力用）
    WHITE_THRESHOLD: ClassVar[int] = 225  # 平均輝度がこの値以上なら白とみなす（ログ出力用）
    SOLID_COLOR_PENALTY: ClassVar[float] = 2000.0  # 単色フレームに対するペナルティ（すべての単色に対して同じ値）


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
        self.seekbar_thumbnails_tile_path = anyio.Path(str(THUMBNAILS_DIR / f"{file_hash}_seekbar.jpg"))
        self.representative_thumbnail_path = anyio.Path(str(THUMBNAILS_DIR / f"{file_hash}.jpg"))


    @classmethod
    def fromRecordedProgram(cls, recorded_program: schemas.RecordedProgram) -> ThumbnailGenerator:
        """
        RecordedProgram から ThumbnailGenerator を初期化する

        Args:
            recorded_program (schemas.RecordedProgram): 録画番組情報

        Returns:
            ThumbnailGenerator: 初期化された ThumbnailGenerator インスタンス
        """

        # 動画長を取得 (番組長ではなく動画ファイルの実際の長さを使わないと辻褄が合わない)
        duration_sec = recorded_program.recorded_video.duration

        # 録画マージンを除いた有効な時間範囲を計算
        start_time = recorded_program.recording_start_margin
        end_time = duration_sec - recorded_program.recording_end_margin

        # 番組の 23~26% と 60~70% の時間範囲を候補区間とする
        ## OP や CM と被りにくい範囲を選択
        total_time = end_time - start_time
        candidate_time_ranges = [
            # 23~26%
            (start_time + total_time * 0.23, start_time + total_time * 0.26),
            # 60~70%
            (start_time + total_time * 0.60, start_time + total_time * 0.70),
        ]

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
            file_path=anyio.Path(recorded_program.recorded_video.file_path),
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
                logging.error(f'{self.file_path}: Failed to generate seekbar thumbnails tile.')
                return

            # 2. プレイヤーのシークバー用サムネイルタイル画像を読み込み、各タイル(フレーム)を切り出し、
            #    そのタイムスタンプが candidate_intervals に含まれる場合だけ
            #    画質評価 + (必要なら) 顔検出してスコアを計算 → 最良を代表サムネイルとして取得
            best_thumbnail = await self.__extractBestFrameFromThumbnailsTile()
            if best_thumbnail is None:
                logging.error(f'{self.file_path}: Failed to extract best frame from seekbar thumbnails tile.')
                return

            # 3. 代表サムネイル画像をファイルに書き出し
            if not await self.__saveRepresentativeThumbnail(best_thumbnail):
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
                    str(self.seekbar_thumbnails_tile_path),
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

            logging.debug_simple(f'{self.file_path}: Generated seekbar thumbnails tile.')
            return True

        except Exception as ex:
            logging.error(f'{self.file_path}: Error in seekbar thumbnails tile generation:', exc_info=ex)
            return False


    async def __extractBestFrameFromThumbnailsTile(self) -> NDArray[np.uint8] | None:
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
            tile_bgr = await asyncio.to_thread(cv2.imread, str(self.seekbar_thumbnails_tile_path))
            if tile_bgr is None:
                logging.error(f'{self.file_path}: Failed to read seekbar thumbnails tile.')
                return None

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
            elif self.face_detection_mode == 'Anime':
                face_cascade = cv2.CascadeClassifier(str(self.ANIME_FACE_CASCADE_PATH))

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
                    self.__computeImageScore,
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


    async def __saveRepresentativeThumbnail(self, img_bgr: NDArray[np.uint8]) -> bool:
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
            if not await asyncio.to_thread(cv2.imwrite, str(self.representative_thumbnail_path), img_bgr):
                logging.error(f'{self.file_path}: Failed to write representative thumbnail.')
                return False

            logging.debug_simple(f'{self.file_path}: Generated representative thumbnail. (Face detection mode: {self.face_detection_mode})')
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


    def __detectLetterbox(self, img_bgr: NDArray[np.uint8]) -> tuple[slice, slice]:
        """
        レターボックス（上下左右の黒帯）を検出し、有効な映像領域のスライスを返す

        Args:
            img_bgr (NDArray[np.uint8]): 入力画像 (BGR)

        Returns:
            tuple[slice, slice]: (垂直方向のスライス, 水平方向のスライス)
                                黒帯が検出されなかった場合は画像全体のスライスを返す
        """

        height, width = img_bgr.shape[:2]
        min_height = int(height * self.LETTERBOX_MIN_HEIGHT_RATIO)
        max_height = int(height * self.LETTERBOX_MAX_HEIGHT_RATIO)

        # グレースケールに変換
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # 上下の黒帯を検出
        top_border = 0
        bottom_border = height
        # 上から走査
        for y in range(max_height):
            row = cast(NDArray[Any], gray[y:y+min_height])
            mean_val = float(np.mean(row, dtype=np.float64))
            std_val = float(np.std(row, dtype=np.float64))
            # 平均輝度が閾値以下で、かつ一様性が高い（標準偏差が小さい）場合を黒帯とみなす
            if mean_val > self.LETTERBOX_THRESHOLD or std_val > self.LETTERBOX_UNIFORMITY_THRESHOLD:
                top_border = y
                break
        # 下から走査
        for y in range(height - 1, height - max_height - 1, -1):
            row = cast(NDArray[Any], gray[y-min_height:y])
            mean_val = float(np.mean(row, dtype=np.float64))
            std_val = float(np.std(row, dtype=np.float64))
            if mean_val > self.LETTERBOX_THRESHOLD or std_val > self.LETTERBOX_UNIFORMITY_THRESHOLD:
                bottom_border = y
                break

        # 左右の黒帯を検出
        left_border = 0
        right_border = width
        # 左から走査
        for x in range(max_height):
            col = cast(NDArray[Any], gray[:, x:x+min_height])
            mean_val = float(np.mean(col, dtype=np.float64))
            std_val = float(np.std(col, dtype=np.float64))
            if mean_val > self.LETTERBOX_THRESHOLD or std_val > self.LETTERBOX_UNIFORMITY_THRESHOLD:
                left_border = x
                break
        # 右から走査
        for x in range(width - 1, width - max_height - 1, -1):
            col = cast(NDArray[Any], gray[:, x-min_height:x])
            mean_val = float(np.mean(col, dtype=np.float64))
            std_val = float(np.std(col, dtype=np.float64))
            if mean_val > self.LETTERBOX_THRESHOLD or std_val > self.LETTERBOX_UNIFORMITY_THRESHOLD:
                right_border = x
                break

        # 検出された黒帯の範囲を除いたスライスを返す
        return (
            slice(top_border, bottom_border),
            slice(left_border, right_border)
        )


    def __computeImageScore(
        self,
        img_bgr: NDArray[np.uint8],
        face_cascade: cv2.CascadeClassifier | None
    ) -> tuple[float, bool]:
        """
        画質スコア (輝度・コントラスト・シャープネス) を計算し、
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

        # レターボックスを検出し、有効な映像領域を取得
        v_slice, h_slice = self.__detectLetterbox(img_bgr)
        valid_region = img_bgr[v_slice, h_slice]

        # 単色判定
        # 各チャンネルの分散を計算し、すべてのチャンネルの分散が閾値以下なら単色とみなす
        solid_color_penalty = 0.0
        channel_variances = [float(np.var(valid_region[:,:,i])) for i in range(3)]
        is_solid_color = all(var < self.COLOR_VARIANCE_THRESHOLD for var in channel_variances)

        # 単色の場合、どの色かをログ出力用に判定し、一律で強いペナルティを与える
        if is_solid_color:
            mean_intensity = float(np.mean(valid_region))
            # ログ出力用の色判定（デバッグ時に役立つ）
            if mean_intensity < self.BLACK_THRESHOLD:
                logging.debug_simple(f'{self.file_path}: Solid black frame detected. Ignored.')
            elif mean_intensity > self.WHITE_THRESHOLD:
                logging.debug_simple(f'{self.file_path}: Solid white frame detected. Ignored.')
            else:
                # BGRの平均値から色を推定
                mean_colors = [float(np.mean(valid_region[:,:,i])) for i in range(3)]
                logging.debug_simple(f'{self.file_path}: Solid color frame detected (BGR: {mean_colors}). Ignored.')

            # すべての単色に対して同じ強いペナルティを与える
            solid_color_penalty = self.SOLID_COLOR_PENALTY

        # 顔検出
        if face_cascade is not None:
            gray = cv2.cvtColor(valid_region, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=self.FACE_DETECTION_SCALE_FACTOR,
                minNeighbors=self.FACE_DETECTION_MIN_NEIGHBORS
            )
            if len(faces) > 0:
                found_face = True
                # 最も大きい顔を基準にスコアを計算
                max_face_area = max(w * h for (_, _, w, h) in faces)
                img_area = valid_region.shape[0] * valid_region.shape[1]
                # 顔の面積比を計算 (0.0 ~ 1.0)
                face_area_ratio = max_face_area / img_area
                # アニメと実写で異なる重み付けを適用
                face_weight = self.ANIME_FACE_SIZE_WEIGHT if self.face_detection_mode == 'Anime' else self.FACE_SIZE_WEIGHT
                # 基本スコアに面積比を掛けてスコアを計算
                face_size_score = self.FACE_SIZE_BASE_SCORE * face_area_ratio * face_weight

        # スコア計算
        # (1) 輝度 Y
        img_float = valid_region.astype(np.float32)
        y = 0.2126*img_float[:,:,2] + 0.7152*img_float[:,:,1] + 0.0722*img_float[:,:,0]
        mean_lum = np.mean(y)       # 平均輝度
        std_lum  = np.std(y)        # 分散(均一度の逆)

        # (2) コントラスト: より広い範囲のパーセンタイルを使用して、コントラストの差をより正確に評価
        y_flat = y.flatten()
        p_low = np.percentile(y_flat, self.CONTRAST_PERCENTILE_LOW)
        p_high = np.percentile(y_flat, self.CONTRAST_PERCENTILE_HIGH)
        contrast = p_high - p_low

        # コントラストをさらに強調するため、平均輝度が中間値に近いほどボーナスを与える
        # 中間値 (127.5) からの距離に応じてペナルティを与える
        distance_ratio = abs(float(mean_lum) - 127.5) / 127.5
        contrast_bonus = max(0.0, float(1.0 - distance_ratio)) * float(contrast) * 0.5
        contrast += contrast_bonus

        # (3) シャープネス (Laplacian の分散)
        lap = cv2.Laplacian(valid_region, cv2.CV_64F)
        sharpness = lap.var()

        # (4) エッジ密度の計算
        # Cannyエッジ検出を使用して、エッジの密度を計算
        gray = cv2.cvtColor(valid_region, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 100, 200)
        edge_density = float(np.count_nonzero(edges)) / edges.size

        # エッジ密度が目標値に近いほど高いスコアを与える
        edge_density_score = max(0.0, 1.0 - abs(edge_density - self.EDGE_DENSITY_TARGET) / self.EDGE_DENSITY_TOLERANCE)
        # 情報量が多すぎる場合はペナルティを与える
        if edge_density > self.EDGE_DENSITY_TARGET + self.EDGE_DENSITY_TOLERANCE:
            edge_density_score *= 0.5

        # (5) エントロピーの計算
        # グレースケール画像のヒストグラムからエントロピーを計算
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist = hist.flatten() / hist.sum()
        hist = hist[hist > 0]  # 0を除外
        entropy = -np.sum(hist * np.log2(hist))

        # エントロピーが目標値に近いほど高いスコアを与える
        entropy_score = max(0.0, 1.0 - abs(entropy - self.ENTROPY_TARGET) / self.ENTROPY_TOLERANCE)
        # 情報量が多すぎる場合はペナルティを与える
        if entropy > self.ENTROPY_TARGET + self.ENTROPY_TOLERANCE:
            entropy_score *= 0.5

        # スコア計算
        # - mean_lum が極端に暗い or 明るい時は減点
        # - std_lum, contrast, sharpness, edge_density, entropy を加点要素とする
        brightness_penalty = 0.0
        if mean_lum < self.BRIGHTNESS_PENALTY_THRESHOLD[0] or mean_lum > self.BRIGHTNESS_PENALTY_THRESHOLD[1]:
            brightness_penalty = self.BRIGHTNESS_PENALTY_VALUE

        # 重み付けしてスコアを計算 (顔サイズのスコアを追加)
        score = (
            std_lum * self.SCORE_WEIGHTS['std_lum'] +
            contrast * self.SCORE_WEIGHTS['contrast'] +
            sharpness * self.SCORE_WEIGHTS['sharpness'] +
            edge_density_score * self.SCORE_WEIGHTS['edge_density'] +
            entropy_score * self.SCORE_WEIGHTS['entropy'] +
            face_size_score -  # 重み付けは既に face_weight で適用済み
            brightness_penalty -
            solid_color_penalty
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
        print(f"Thumbnail tile -> {generator.seekbar_thumbnails_tile_path}")
        print(f"Representative -> {generator.representative_thumbnail_path}")

    typer.run(main)
