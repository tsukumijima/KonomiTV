
from __future__ import annotations

import asyncio
import concurrent.futures
import math
import pathlib
import random
import subprocess
import time
from typing import ClassVar, Literal, cast

import anyio
import cv2
import numpy as np
import typer
from numpy.typing import NDArray

from app import logging, schemas
from app.config import Config, LoadConfig
from app.constants import LIBRARY_PATH, STATIC_DIR, THUMBNAILS_DIR


class ThumbnailGenerator:
    """
    プレイヤーのシークバー用タイル画像と、候補区間内で最も良い1枚の代表サムネイルを生成するクラス (with o1 pro / Claude 3.5 Sonnet)
    """

    # サムネイルのタイル化の設定
    BASE_DURATION_MIN: ClassVar[int] = 30  # 基準となる動画の長さ (30分)
    BASE_INTERVAL_SEC: ClassVar[float] = 5.0  # 基準となる間隔 (5秒)
    MIN_INTERVAL_SEC: ClassVar[float] = 5.0  # 最小間隔 (5秒)
    MAX_INTERVAL_SEC: ClassVar[float] = 30.0  # 最大間隔 (30秒)
    TILE_SCALE: ClassVar[tuple[int, int]] = (480, 270)  # タイル化時の1フレーム解像度 (width, height)
    TILE_COLS: ClassVar[int] = 34   # WebP の最大サイズ制限 (16383px) を考慮し、1行あたりの最大フレーム数を設定

    # WebP 出力の設定
    WEBP_QUALITY: ClassVar[int] = 68  # WebP 品質 (0-100)
    WEBP_COMPRESSION: ClassVar[int] = 6  # WebP 圧縮レベル (0-6)
    WEBP_MAX_SIZE: ClassVar[int] = 16383  # WebP の最大サイズ制限 (px)

    # JPEG フォールバック時の設定
    JPEG_QUALITY: ClassVar[int] = 90  # JPEG 品質 (0-100)
    JPEG_OPTIMIZE: ClassVar[bool] = True  # JPEG 最適化

    # 顔検出用カスケード分類器のパス
    HUMAN_FACE_CASCADE_PATH: ClassVar[pathlib.Path] = pathlib.Path(cv2.__file__).parent / 'data' / 'haarcascade_frontalface_default.xml'
    ANIME_FACE_CASCADE_PATH: ClassVar[pathlib.Path] = STATIC_DIR / 'lbpcascade_animeface.xml'

    # 顔検出の設定
    HUMAN_FACE_DETECTION_SCALE_FACTOR: ClassVar[float] = 1.05  # 実写顔検出時のスケールファクター
    HUMAN_FACE_DETECTION_MIN_NEIGHBORS: ClassVar[int] = 3  # 実写顔検出時の最小近傍数
    ANIME_FACE_DETECTION_SCALE_FACTOR: ClassVar[float] = 1.01  # アニメ顔検出時のスケールファクター (より時間をかけて精度を重視)
    ANIME_FACE_DETECTION_MIN_NEIGHBORS: ClassVar[int] = 2  # アニメ顔検出時の最小近傍数（より緩い判定）
    NON_ANIME_FACE_DETECTION_SCALE_FACTOR: ClassVar[float] = 1.10  # アニメ顔検出時に補助的に用いる実写顔検出のスケールファクター
    NON_ANIME_FACE_DETECTION_MIN_NEIGHBORS: ClassVar[int] = 5  # アニメ顔検出時に補助的に用いる実写顔検出の最小近傍数
    HUMAN_FACE_SIZE_WEIGHT: ClassVar[float] = 1.5  # 顔サイズによるスコアの重み（実写向け）
    ANIME_FACE_SIZE_WEIGHT: ClassVar[float] = 8.0  # アニメの顔サイズによるスコアの重み (アニメは顔が大きく映っているシーンを重視)
    FACE_SIZE_BASE_SCORE: ClassVar[float] = 20.0  # 顔サイズの基本スコア（実写・アニメ共通）
    ANIME_FACE_OPTIMAL_RATIO: ClassVar[float] = 0.23  # アニメの顔の最適な面積比（これを超えると緩やかにスコアを低下）
    ANIME_FACE_RATIO_FALLOFF: ClassVar[float] = 0.6  # アニメの顔が大きすぎる場合のスコア低下率

    # レターボックス検出の設定
    LETTERBOX_MIN_HEIGHT_RATIO: ClassVar[float] = 0.05  # 最小の黒帯の高さ比率（画像の高さに対する割合）
    LETTERBOX_MAX_HEIGHT_RATIO: ClassVar[float] = 0.25  # 最大の黒帯の高さ比率
    LETTERBOX_AREA_THRESHOLD: ClassVar[float] = 0.4  # レターボックスの面積比率の閾値（これを超えると除外）
    LETTERBOX_LUMINANCE_THRESHOLD: ClassVar[int] = 45  # レターボックスの輝度閾値（これ以下を黒帯候補とする）
    LETTERBOX_CONTINUOUS_RATIO: ClassVar[float] = 0.7  # 連続性判定の閾値（この割合以上が類似していれば連続とみなす）
    LETTERBOX_EDGE_THRESHOLD: ClassVar[float] = 0.05  # エッジ密度の閾値（これ以下なら一様な領域とみなす）

    # 画質評価の重み付け（実写向け）
    SCORE_WEIGHTS: ClassVar[dict[str, float]] = {
        'std_lum': 0.6,  # 輝度の標準偏差 (全体的な明暗の差)
        'contrast': 0.4,  # コントラスト (明暗の差の大きさ)
        'sharpness': 0.5,  # シャープネス
        'edge_density': 0.4,  # エッジ密度 (情報量の指標)
        'entropy': 0.3,  # エントロピー (情報量の指標)
    }

    # 画質評価の重み付け（アニメ向け）
    ANIME_SCORE_WEIGHTS: ClassVar[dict[str, float]] = {
        'std_lum': 0.4,  # 輝度の標準偏差 (全体的な明暗の差)
        'contrast': 0.3,  # コントラスト (明暗の差の大きさ)
        'sharpness': 0.15,  # シャープネス
        'edge_density': 0.2,  # エッジ密度 (情報量の指標)
        'entropy': 0.4,  # エントロピー (情報量の指標)
    }

    # 画質評価のペナルティ
    BRIGHTNESS_PENALTY_THRESHOLD: ClassVar[tuple[int, int]] = (20, 235)  # 輝度のペナルティ閾値 (min, max)
    BRIGHTNESS_PENALTY_VALUE: ClassVar[float] = 20.0  # 輝度のペナルティ値

    # コントラスト評価の設定
    CONTRAST_PERCENTILE_LOW: ClassVar[int] = 5  # コントラスト計算時の下位パーセンタイル
    CONTRAST_PERCENTILE_HIGH: ClassVar[int] = 95  # コントラスト計算時の上位パーセンタイル

    # 情報量評価の設定
    EDGE_DENSITY_TARGET: ClassVar[float] = 0.15  # 目標とするエッジ密度 (0.0 ~ 1.0)
    EDGE_DENSITY_TOLERANCE: ClassVar[float] = 0.1  # エッジ密度の許容範囲
    ENTROPY_TARGET: ClassVar[float] = 5.0  # 目標とするエントロピー値
    ENTROPY_TOLERANCE: ClassVar[float] = 2.0  # エントロピーの許容範囲

    # 単色判定の設定
    COLOR_VARIANCE_THRESHOLD: ClassVar[float] = 10.0  # 各チャンネルの分散がこの値以下なら単色とみなす
    BLACK_THRESHOLD: ClassVar[int] = 30  # 平均輝度がこの値以下なら黒とみなす
    WHITE_THRESHOLD: ClassVar[int] = 225  # 平均輝度がこの値以上なら白とみなす
    SOLID_COLOR_PENALTY: ClassVar[float] = 100.0  # 単色フレームに対するペナルティ

    # 画面端の単色領域検出の設定
    EDGE_MARGIN_RATIO: ClassVar[float] = 0.08  # 画面端から何割をエッジ領域とするか
    EDGE_CONTACT_THRESHOLD: ClassVar[float] = 0.6  # エッジ領域の何割が単色である必要があるか
    MIN_EDGES_REQUIRED: ClassVar[int] = 2  # 最低何辺が単色である必要があるか
    EDGE_COLOR_RANGE: ClassVar[float] = 30.0  # エッジ領域内での色の許容範囲
    EDGE_BORDER_PENALTY: ClassVar[float] = 90.0  # 画面端の単色ペナルティ

    # 演出効果を考慮した画面端の単色判定の設定を追加
    EDGE_LUMINANCE_THRESHOLD: ClassVar[float] = 30.0  # エッジ領域の輝度閾値（これ以下を暗部とみなす）
    EDGE_CONTINUOUS_RATIO: ClassVar[float] = 0.8  # 連続性判定の閾値（この割合以上が類似していれば連続とみなす）
    EDGE_DARK_RATIO_THRESHOLD: ClassVar[float] = 0.85  # 暗部ピクセルの必要割合

    # レターボックス検出のペナルティ設定
    LETTERBOX_PENALTY: ClassVar[float] = 50.0  # レターボックスがある場合のペナルティ値

    # アニメの色バランス評価の設定
    COLOR_BALANCE_K: ClassVar[int] = 3  # 抽出する主要な色の数
    COLOR_BALANCE_WEIGHT: ClassVar[float] = 0.5  # アニメの色バランススコアの重み
    COLOR_BALANCE_MIN_RATIO: ClassVar[float] = 0.15  # 主要な色の最小占有率 (これ以下は無視)
    COLOR_BALANCE_MAX_RATIO: ClassVar[float] = 0.7  # 主要な色の最大占有率 (これを超えると単調な画像とみなす)
    COLOR_BALANCE_MIN_DISTANCE: ClassVar[float] = 30.0  # 主要な色同士の最小距離 (Lab色空間)


    def __init__(
        self,
        file_path: anyio.Path,
        container_format: Literal['MPEG-TS', 'MPEG-4'],
        file_hash: str,
        duration_sec: float,
        candidate_time_ranges: list[tuple[float, float]],
        face_detection_mode: Literal['Human', 'Anime'] | None = None,
    ) -> None:
        """
        プレイヤーのシークバー用タイル画像と、候補区間内で最も良い1枚の代表サムネイルを生成するクラスを初期化する

        Args:
            file_path (anyio.Path): 動画ファイルのパス
            container_format (Literal['MPEG-TS', 'MPEG-4']): 動画ファイルのコンテナ形式
            file_hash (str): 動画ファイルのハッシュ値（ファイル名の一意性を保証するため）
            duration_sec (float): 動画の再生時間(秒)
            candidate_time_ranges (list[tuple[float, float]]): 代表サムネ候補とする区間 [(start, end), ...]
            face_detection_mode (Literal['Human', 'Anime'] | None): 顔検出モード (デフォルト: None)
        """

        self.file_path = file_path
        self.container_format = container_format
        self.duration_sec = duration_sec
        self.candidate_intervals = candidate_time_ranges
        self.face_detection_mode = face_detection_mode

        # 動画の長さに応じて適切なタイル化間隔を計算
        self.tile_interval_sec = self.__calculateTileInterval(duration_sec)

        # ファイルハッシュをベースにしたファイル名を生成
        self.seekbar_thumbnails_tile_path = anyio.Path(str(THUMBNAILS_DIR / f"{file_hash}_tile.webp"))
        self.representative_thumbnail_path = anyio.Path(str(THUMBNAILS_DIR / f"{file_hash}.webp"))


    @classmethod
    def fromRecordedProgram(cls, recorded_program: schemas.RecordedProgram) -> ThumbnailGenerator:
        """
        RecordedProgram から ThumbnailGenerator を初期化する

        Args:
            recorded_program (schemas.RecordedProgram): 録画番組情報

        Returns:
            ThumbnailGenerator: 初期化された ThumbnailGenerator インスタンス
        """

        def IsAnimeGenre(genre: schemas.Genre) -> bool:
            """ 指定されたジャンルが確実にアニメとして扱うべきジャンルかどうかを判定 """
            major = genre['major']
            middle = genre['middle']

            # アニメ・特撮の場合、特撮以外はアニメ
            if major == 'アニメ・特撮' and middle != '特撮':
                return True
            # 映画の場合、アニメのみアニメ
            if major == '映画' and middle == 'アニメ':
                return True

            return False

        def IsLiveActionGenre(genre: schemas.Genre) -> bool:
            """ 指定されたジャンルが確実に実写人物が重要なジャンルかどうかを判定 """
            major = genre['major']
            middle = genre['middle']

            # 一律で実写人物が重要なジャンルとして扱うメジャージャンル
            if major in {
                'ニュース・報道',
                '情報・ワイドショー',
                'ドラマ',
                '劇場・公演',
            }:
                return True
            # バラエティの場合、お笑い・コメディ以外は実写番組
            ## 「アニメ・特撮/国内アニメ」が指定されているが、「お笑い・コメディ」以外のバラエティジャンルが指定されている場合は
            ## 実写の声優特番などである可能性が高い
            if major == 'バラエティ' and middle != 'お笑い・コメディ':
                return True
            # アニメ・特撮の場合、特撮は実写番組
            if major == 'アニメ・特撮' and middle == '特撮':
                return True
            # 映画の場合、アニメ以外は実写番組
            if major == '映画' and middle != 'アニメ':
                return True
            # ドキュメンタリー・教養の場合、特定のミドルジャンルは実写人物が重要
            if major == 'ドキュメンタリー・教養' and middle in {
                '社会・時事',
                '歴史・紀行',
                'インタビュー・討論',
            }:
                return True

            return False

        def DetermineFaceDetectionMode(genres: list[schemas.Genre]) -> Literal['Human', 'Anime'] | None:
            """ 番組のジャンル情報から顔検出モードを決定（ジャンル情報は ariblib/constants.py の CONTENT_TYPE を参照） """
            if len(genres) == 0:
                return None

            # アニメとして扱うべきジャンルが含まれているかチェック
            has_anime = any(IsAnimeGenre(g) for g in genres)
            # アニメとして扱うべきジャンルが含まれていて、かつ実写人物が重要なジャンルが含まれていない場合はアニメ顔検出を優先
            # 実写人物が重要なジャンルが含まれている場合は、アニメ顔検出は使わない
            if has_anime and not any(IsLiveActionGenre(g) for g in genres):
                return 'Anime'
            # 実写人物が重要なジャンルが含まれているかチェック
            if any(IsLiveActionGenre(g) for g in genres):
                return 'Human'
            # アニメも実写人物が重要なジャンルも両方含まれていない場合は顔検出しない
            # 実際には顔検出しない場合でも実写番組の場合は往々にしてあるが、ジャンルによっては必ずしもサムネで顔アップが求められるわけではない
            return None

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

        # ジャンル情報から顔検出の要否・アニメ or 実写人物が重要なジャンルを判断
        face_detection_mode = DetermineFaceDetectionMode(recorded_program.genres)

        # コンストラクタに渡す
        return cls(
            file_path = anyio.Path(recorded_program.recorded_video.file_path),
            container_format = recorded_program.recorded_video.container_format,
            file_hash = recorded_program.recorded_video.file_hash,
            duration_sec = duration_sec,
            candidate_time_ranges = candidate_time_ranges,
            face_detection_mode = face_detection_mode,
        )


    async def generateAndSave(self, skip_tile_if_exists: bool = False) -> None:
        """
        プレイヤーのシークバー用サムネイルタイル画像を生成し、
        さらに候補区間内のフレームから最も良い1枚を選び、代表サムネイルとして出力する

        Args:
            skip_tile_if_exists (bool): True の場合、既に存在する場合はサムネイルタイルの生成をスキップするかどうか (デフォルト: False)
        """

        start_time = time.time()
        logging.info(f'{self.file_path}: Generating thumbnail... / Face detection mode: {self.face_detection_mode}')
        try:
            # 1. プレイヤーのシークバー用サムネイルタイル画像を生成
            tile_exists = await self.seekbar_thumbnails_tile_path.is_file()
            tile_exists_jpg = False
            if not tile_exists:
                ## WebP が存在しない場合は JPEG も確認
                jpg_path = self.seekbar_thumbnails_tile_path.with_suffix('.jpg')
                tile_exists_jpg = await jpg_path.is_file()
                if tile_exists_jpg:
                    self.seekbar_thumbnails_tile_path = jpg_path
                    tile_exists = True
            tile_is_not_empty = tile_exists and (await self.seekbar_thumbnails_tile_path.stat()).st_size > 0
            if tile_is_not_empty and skip_tile_if_exists:
                ## ファイルが存在し、かつ0バイトでないなら生成済みとみなしてスキップ
                logging.info(f'{self.file_path}: Seekbar thumbnail tile already exists. Skipping generation.')
            else:
                ## まだシークバー用サムネイルタイルが生成されていなければ生成
                if not await self.__generateThumbnailTile():
                    logging.error(f'{self.file_path}: Failed to generate seekbar thumbnail tile.')
                    return
                logging.info(f'{self.file_path}: Seekbar thumbnail generation completed. ({time.time() - start_time:.2f} sec)')

            # 2. プレイヤーのシークバー用サムネイルタイル画像を読み込み、各タイル(フレーム)を切り出し、
            #    そのタイムスタンプが candidate_intervals に含まれる場合だけ
            #    画質評価 + (必要なら) 顔検出してスコアを計算 → 最良を代表サムネイルとして取得
            start_time_best_frame = time.time()
            best_thumbnail = await self.__extractBestFrameFromThumbnailTile()
            if best_thumbnail is None:
                logging.error(f'{self.file_path}: Failed to extract best frame from seekbar thumbnail tile.')
                return

            # 3. 代表サムネイル画像をファイルに書き出し
            if not await self.__saveRepresentativeThumbnail(best_thumbnail):
                logging.error(f'{self.file_path}: Failed to save representative thumbnail.')
                return

            logging.info(f'{self.file_path}: Thumbnail generation completed. ({time.time() - start_time_best_frame:.2f} sec / Total: {time.time() - start_time:.2f} sec)')
            logging.debug_simple(f'Thumbnail tile -> {self.seekbar_thumbnails_tile_path.name}')
            logging.debug_simple(f'Representative -> {self.representative_thumbnail_path.name}')

        except Exception as ex:
            # 予期せぬエラーのみここでキャッチ
            logging.error(f'{self.file_path}: Unexpected error in thumbnail generation:', exc_info=ex)
            return


    def __calculateTileInterval(self, duration_sec: float) -> float:
        """
        動画の長さに応じて適切なタイル化間隔を計算する
        30分以下の番組は5秒間隔固定とし、それより長い番組は対数関数的にサムネイル数の増加を抑制する
        録画マージンを考慮し、分単位で切り捨てて計算する

        Args:
            duration_sec (float): 動画の長さ (秒)

        Returns:
            float: タイル化間隔 (秒)
        """

        # 録画マージンを考慮し、分単位で切り捨て
        duration_min = int(duration_sec / 60)

        # 30分以下は一律5秒間隔
        if duration_min <= self.BASE_DURATION_MIN:
            return self.BASE_INTERVAL_SEC

        # 30分超の場合は対数関数的に増加を抑制
        # duration_ratio = 2 (1時間) の時に、increase_ratio が約1.5になるように調整
        duration_ratio = duration_min / self.BASE_DURATION_MIN
        # log(1 + x) の代わりに log(1 + x/2) を使うことで、1時間の時に1.5倍程度になるよう調整
        interval = min(
            self.MAX_INTERVAL_SEC,
            round(self.BASE_INTERVAL_SEC * duration_ratio / math.log2(1 + duration_ratio/2), 1)
        )

        # 計算結果をログ出力
        expected_tiles = duration_sec / interval
        base_tiles = (self.BASE_DURATION_MIN * 60) / self.BASE_INTERVAL_SEC
        increase_ratio = expected_tiles / base_tiles
        logging.debug_simple(
            f'{self.file_path}: Long video ({duration_min} min), '
            f'using dynamic interval of {interval:.1f} sec. '
            f'Expected {expected_tiles:.1f} tiles (x{increase_ratio:.2f} of base).'
        )
        return interval


    def __formatTime(self, seconds: float) -> str:
        """
        秒数を HH:MM:SS または HH:MM:SS.xx 形式の文字列に変換するヘルパー関数。
        秒数が整数に近い場合は HH:MM:SS、そうでなければ小数第2位まで出力する。

        Args:
            seconds (float): 秒数

        Returns:
            str: フォーマットされた時間文字列
        """
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = seconds % 60
        # 整数に近い場合は小数部を省略
        if abs(secs - round(secs)) < 0.001:
            return f'{hrs:02}:{mins:02}:{int(secs):02}'
        else:
            return f'{hrs:02}:{mins:02}:{secs:05.2f}'


    async def __generateThumbnailTile(self) -> bool:
        """
        FFmpeg を使い、録画ファイルから各候補フレームを直列に抽出し、メモリ上で OpenCV によるタイル化を行う実装
        ・各候補フレームは、指定オフセットから1フレームのみ抽出することで全編のデコードと I/O 負荷の増大を回避
        ・抽出時は個別コマンドで出力をパイプで受け取り、中間ファイルを作らずメモリ上で画像変換を実施
        ・全候補画像は OpenCV の hconcat/vconcat を用いてタイル状に連結し、最終的なサムネイルタイル画像としてディスク出力する

        Returns:
            bool: 成功時は True、失敗時は False
        """

        try:
            # 動画の長さと tile_interval_sec から候補フレーム数を算出
            # ※ ceil() を使うことで、端数でも切り捨てずに確実にすべての区間をカバー
            num_candidates = int(math.ceil(self.duration_sec / self.tile_interval_sec))
            if num_candidates < 1:
                num_candidates = 1

            # タイルの行数を計算（列数は self.TILE_COLS 固定）
            tile_rows = math.ceil(num_candidates / self.TILE_COLS)
            width, height = self.TILE_SCALE
            total_width = width * self.TILE_COLS
            total_height = height * tile_rows

            # WebP の最大サイズ制限をチェック（制限内なら WebP、越える場合は JPEG にフォールバック）
            use_webp = total_width <= self.WEBP_MAX_SIZE and total_height <= self.WEBP_MAX_SIZE
            if not use_webp:
                self.seekbar_thumbnails_tile_path = self.seekbar_thumbnails_tile_path.with_suffix('.jpg')
                logging.warning(f'{self.file_path}: Image size ({total_width}x{total_height}) exceeds WebP limits. Falling back to JPEG.')

            # 各候補フレーム抽出の開始位置（秒）を算出（動画末尾の場合は調整する）
            candidate_offsets = []
            for i in range(num_candidates):
                offset = i * self.tile_interval_sec
                # もし候補フレームの開始位置 + 0.01秒が動画長を超える場合、抽出可能な位置に調整する
                if offset + 0.01 > self.duration_sec:
                    offset = max(0, self.duration_sec - 0.02)
                candidate_offsets.append(offset)

            # 万が一出力先ディレクトリが無い場合は作成 (通常存在するはず)
            thumbnails_dir = anyio.Path(str(THUMBNAILS_DIR))
            if not await thumbnails_dir.is_dir():
                await thumbnails_dir.mkdir(parents=True, exist_ok=True)

            # 非同期キューの準備
            frame_queue: asyncio.Queue[tuple[float, bytes]] = asyncio.Queue()

            # エラー通知用のイベント
            error_event = asyncio.Event()

            async def ExtractSingleFrame(offset: float, worker_name: str) -> bytes | None:
                """ FFmpeg を使い1フレームを抽出する共通処理 """

                # オフセットを HH:MM:SS または HH:MM:SS.xx 形式に変換
                formatted_offset = self.__formatTime(offset)

                # 個別に1枚抽出するための FFmpeg コマンドを実行
                ## 試行錯誤の結果、数フレーム読み取るだけのためにハードウェアアクセラレーションを使うと
                ## HW デコーダーの初期化などでむしろ遅くなることが判明したため、-hwaccel はあえて指定していない
                process = await asyncio.create_subprocess_exec(
                    LIBRARY_PATH['FFmpeg'],
                    *[
                        # 上書きを許可
                        '-y',
                        # 非対話モードで実行し、不意のフリーズを回避する
                        '-nostdin',
                        # 入力フォーマットを指定
                        '-f', 'mpegts' if self.container_format == 'MPEG-TS' else 'mp4',
                        # I フレームのみをデコードする (nokey ではなく nointra でないと一部フレームが緑色になる…)
                        '-skip_frame', 'nointra',
                        # 抽出開始位置
                        '-ss', formatted_offset,
                        # 入力ファイル
                        '-i', str(self.file_path),
                        # 音声ストリームを無効化し若干の高速化を図る
                        '-an',
                        # 画像サイズを調整（タイル化時に各画像は self.TILE_SCALE になるように）
                        '-vf', f'scale={width}:{height}',
                        # 1フレーム分のみ抽出する
                        '-frames:v', '1',
                        # エンコード負荷低減のため、中間フォーマットには PNG を使う
                        '-codec:v', 'png',
                        # スレッド数を自動で設定する
                        '-threads', 'auto',
                        # 標準出力にパイプ出力する
                        '-f', 'image2pipe',
                        'pipe:1',
                    ],
                    # 明示的に標準入力を無効化しないと、親プロセスの標準入力が引き継がれてしまう
                    stdin = asyncio.subprocess.DEVNULL,
                    # 標準出力・標準エラー出力をパイプで受け取る
                    stdout = asyncio.subprocess.PIPE,
                    stderr = asyncio.subprocess.PIPE,
                )

                # プロセス終了を待ち、エラー出力を取得
                stdout, stderr = await process.communicate()
                if process.returncode != 0:
                    error_message = stderr.decode('utf-8', errors='ignore')
                    logging.error(f'{self.file_path}: [{worker_name}] FFmpeg candidate extraction failed at offset {formatted_offset} with error: {error_message}')
                    return None

                # PNG バイナリをそのまま返す
                return stdout

            async def ExtractFramesWorker(
                offsets: list[float],
                worker_name: str,
                start_delay: float = 0.0
            ) -> None:
                """ フレーム抽出ワーカー """
                try:
                    # オフセットを WORKER_SYNC_COUNT 個ずつに分割
                    for i in range(0, len(offsets), WORKER_SYNC_COUNT):
                        # バッチの開始時にディレイを適用
                        if start_delay > 0:
                            await asyncio.sleep(start_delay)

                        batch_offsets = offsets[i:i + WORKER_SYNC_COUNT]

                        for offset in batch_offsets:
                            # エラーチェック（他のワーカーでエラーが発生していたら終了）
                            if error_event.is_set():
                                return

                            # FFmpegでフレーム抽出
                            frame = await ExtractSingleFrame(offset, worker_name)
                            if frame is None:
                                error_event.set()
                                return

                            # キューに結果を格納
                            await frame_queue.put((offset, frame))

                            # 同期カウンターをインクリメント
                            nonlocal sync_counter
                            sync_counter += 1
                            if sync_counter >= sync_target:
                                # 同期イベントを発火
                                sync_event.set()

                        try:
                            # 同期イベントが発火するまで待機（キャンセル可能）
                            await asyncio.wait_for(sync_event.wait(), timeout=30.0)
                        except (TimeoutError, asyncio.CancelledError):
                            # キャンセルまたはタイムアウト時は即座に終了
                            return
                        finally:
                            # 次のバッチに向けて同期イベントをクリア
                            sync_event.clear()
                            # 同期カウンターをリセット
                            sync_counter = 0

                except asyncio.CancelledError:
                    # キャンセル時は即座に終了
                    return
                except Exception as ex:
                    logging.error(f'{self.file_path}: [{worker_name}] Unexpected error:', exc_info=ex)
                    error_event.set()

            try:
                # オフセットを WORKER_COUNT 個に分割 (0,5,10,...), (1,6,11,...), (2,7,12,...), (3,8,13,...), (4,9,14,...)
                # 1プロセスの実行に約1秒弱かかるため、WORKER_DELAY 秒間隔で起動することで
                # プロセス起動のタイミングを分散させつつ、なるべくシーケンシャルなアクセスになるよう調整
                WORKER_COUNT = 5
                WORKER_DELAY = 0.18
                # 同期を取る間隔（各ワーカーがこの数だけフレームを取得したら同期を取る）
                WORKER_SYNC_COUNT = 10

                # オフセットをワーカー数で分割
                worker_offsets = [
                    candidate_offsets[i::WORKER_COUNT] for i in range(WORKER_COUNT)
                ]

                # 同期用のイベント
                sync_event = asyncio.Event()
                sync_counter = 0
                sync_target = WORKER_COUNT * WORKER_SYNC_COUNT

                # WORKER_COUNT 個のワーカーを WORKER_DELAY 秒間隔で起動
                start_time = time.time()
                workers = [
                    ExtractFramesWorker(worker_offsets[i], f'Worker {i}', start_delay=i * WORKER_DELAY)
                    for i in range(WORKER_COUNT)
                ]

                # 全フレームの収集を待機
                frames_dict: dict[float, bytes] = {}
                expected_frames = len(candidate_offsets)

                # ワーカータスクを開始
                worker_tasks = [asyncio.create_task(w) for w in workers]

                try:
                    # フレーム収集ループ
                    while len(frames_dict) < expected_frames:
                        if error_event.is_set():
                            # エラーが発生した場合は中断
                            raise RuntimeError('Error occurred in worker task')

                        try:
                            # タイムアウト付きでキューから結果を取得
                            offset, frame = await asyncio.wait_for(frame_queue.get(), timeout=30.0)
                            frames_dict[offset] = frame
                            # 進捗をログ出力
                            # logging.debug_simple(
                            #     f'{self.file_path}: Frame collected {len(frames_dict)}/{expected_frames} '
                            #     f'(offset: {self.__formatTime(offset)})'
                            # )

                            # 全フレームの収集が完了したら、残りのワーカータスクをキャンセル
                            if len(frames_dict) >= expected_frames:
                                # 全ワーカーをキャンセル
                                for task in worker_tasks:
                                    task.cancel()
                                # キャンセルされたタスクの完了を待機（エラーは無視）
                                await asyncio.gather(*worker_tasks, return_exceptions=True)
                                break

                        except TimeoutError:
                            # タイムアウト時はエラーとして扱う
                            raise RuntimeError('Timeout while waiting for frame')

                except Exception as ex:
                    # エラー発生時は全ワーカーを確実にキャンセル
                    error_event.set()
                    for task in worker_tasks:
                        task.cancel()
                    # キャンセルされたタスクの完了を待機
                    await asyncio.gather(*worker_tasks, return_exceptions=True)
                    raise ex

                # 時系列順にフレームを並べ直す
                png_frames = [
                    frames_dict[offset] for offset in candidate_offsets
                ]
                logging.debug_simple(
                    f'{self.file_path}: All frames collected and sorted in chronological order. ({time.time() - start_time:.2f} sec)'
                )

            except Exception as ex:
                logging.error(f'{self.file_path}: Error in parallel thumbnail generation:', exc_info=ex)
                return False

            # PNG 画像のフレームを繋ぎ合わせてタイル画像を生成し、FFmpeg で WebP または JPEG として保存
            ## CPU バウンドな処理なので、イベントループをブロックしないよう ProcessPoolExecutor で実行する
            loop = asyncio.get_running_loop()
            with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
                success = await loop.run_in_executor(
                    executor,
                    self._generateAndSaveTileImage,
                    png_frames,
                    tile_rows,
                    height,
                    width,
                    use_webp,
                )
                if not success:
                    logging.error(f'{self.file_path}: Failed to generate and save tile image.')
                    return False

            return True

        except Exception as ex:
            logging.error(f'{self.file_path}: Error in seekbar thumbnail tile generation:', exc_info=ex)
            return False


    def _generateAndSaveTileImage(
        self,
        png_frames: list[bytes],
        tile_rows: int,
        height: int,
        width: int,
        use_webp: bool,
    ) -> bool:
        """
        PNG フレームからタイル画像を生成し、WebP または JPEG として保存する
        ProcessPoolExecutor で実行されるため、あえて prefix のアンダースコアは1つとしている

        Args:
            png_frames (list[bytes]): PNG フレームのバイナリデータのリスト
            tile_rows (int): タイルの行数
            height (int): タイルの高さ
            width (int): タイルの幅
            use_webp (bool): WebP として保存するかどうか (False の場合は JPEG)

        Returns:
            bool: 成功時は True、失敗時は False
        """

        try:
            # PNG フレームを OpenCV の画像データに変換
            candidate_images = []
            for i in range(len(png_frames)):
                frame = None
                if not png_frames[i]:
                    # 動画末尾付近はその先に I フレームがないことが多くこのときその要素は空になる
                    # この条件は頻繁なので、先頭要素でなく以降の要素がすべて空であるなら警告は出さない
                    for j in range(i, len(png_frames)):
                        if j == 0 or png_frames[j]:
                            logging.warning(f'{self.file_path}: Failed to extract PNG frame. Using black image instead.')
                            break
                else:
                    try:
                        # PNG バイナリを numpy 配列に変換
                        image_data = np.frombuffer(png_frames[i], dtype=np.uint8)
                        # OpenCV で画像デコード
                        frame = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
                        if frame is None:
                            logging.warning(f'{self.file_path}: Failed to decode PNG frame. Using black image instead.')
                    except Exception as ex:
                        logging.warning(f'{self.file_path}: Exception occurred while decoding PNG frame. Using black image instead:', exc_info=ex)
                if frame is None:
                    # 黒画像を代わりに使用
                    frame = np.zeros((height, width, 3), dtype=np.uint8)
                candidate_images.append(frame)

            # OpenCV を用いてタイル化処理を行う
            rows = []
            num_cols = self.TILE_COLS
            for r in range(tile_rows):
                row_images = candidate_images[r * num_cols: (r + 1) * num_cols]
                # 最終行が列数に満たない場合、黒画像で埋める
                if len(row_images) < num_cols:
                    black_image = np.zeros((height, width, 3), dtype=np.uint8)
                    while len(row_images) < num_cols:
                        row_images.append(black_image)
                row_concat = cv2.hconcat(row_images)
                rows.append(row_concat)
            tile_image = cv2.vconcat(rows)

            # タイル画像を PNG としてメモリ上にエンコード
            _, tile_png_data = cv2.imencode('.png', tile_image)
            if tile_png_data is None:
                logging.error(f'{self.file_path}: Failed to encode tile image as PNG.')
                return False

            # FFmpeg でタイル画像を WebP または JPEG に圧縮保存
            # これで最終的なタイル画像がディスクへ書き込まれる
            process = subprocess.Popen(
                [
                    LIBRARY_PATH['FFmpeg'],
                    # 上書きを許可
                    '-y',
                    # 非対話モードで実行し、不意のフリーズを回避する
                    '-nostdin',
                    # 入力フォーマットを指定
                    '-f', 'image2pipe',
                    # 入力コーデックを指定
                    '-codec:v', 'png',
                    # 標準入力からパイプ入力
                    '-i', 'pipe:0',
                    # WebP または JPEG 出力設定
                    *([
                        '-codec:v', 'webp',
                        '-quality', str(self.WEBP_QUALITY),  # 品質設定
                        '-compression_level', str(self.WEBP_COMPRESSION),  # 圧縮レベル
                        '-preset', 'picture',  # 写真向けプリセット
                    ] if use_webp else [
                        '-codec:v', 'mjpeg',
                        '-qmin', '1',  # 最小品質
                        '-qmax', '1',  # 最大品質
                        '-qscale:v', str(int((100 - self.JPEG_QUALITY) / 4)),  # 品質設定 (JPEG の場合は 1-31 のスケール)
                    ]),
                    # スレッド数を自動で設定する
                    '-threads', 'auto',
                    # 出力ファイル
                    str(self.seekbar_thumbnails_tile_path),
                ],
                # 明示的に標準入力を有効化
                stdin = subprocess.PIPE,
                # 標準出力・標準エラー出力をパイプで受け取る
                stdout = subprocess.PIPE,
                stderr = subprocess.PIPE,
            )

            # 画像データを標準入力に書き込み、プロセス終了を待つ
            _, stderr_data = process.communicate(input=tile_png_data.tobytes())
            if process.returncode != 0:
                error_message = stderr_data.decode('utf-8', errors='ignore')
                logging.error(f'{self.file_path}: FFmpeg tile image compression failed with error: {error_message}')
                return False

            return True

        except Exception as ex:
            logging.error(f'{self.file_path}: Error in tile image generation and saving:', exc_info=ex)
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
            tile_bgr = await asyncio.to_thread(cv2.imread, str(self.seekbar_thumbnails_tile_path))
            if tile_bgr is None:
                logging.error(f'{self.file_path}: Failed to read seekbar thumbnail tile.')
                return None

            height, width, _ = tile_bgr.shape
            tile_w, tile_h = self.TILE_SCALE

            # 総フレーム数を計算 ( rows * cols )
            # ※ rows = height / tile_h, cols = width / tile_w
            #   (タイルの端数が出る場合もあるが、ここでは切り捨て等で対処)
            cols = width // tile_w
            rows = height // tile_h
            total_frames = rows * cols

            # 候補区間内のフレームを収集
            frames_data: list[tuple[int, NDArray[np.uint8], int, int, NDArray[np.uint8]]] = []
            # (index, frame_bgr, row, col, sub_img)

            for idx in range(total_frames):
                # このフレームの動画内時間(秒)
                time_offset = idx * self.tile_interval_sec
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
                frames_data.append((idx, sub_img, row + 1, col + 1, sub_img))

            # 候補区間内のフレームが1枚もない場合は、全フレームから1枚をランダムに選択
            if not frames_data:
                logging.warning(f'{self.file_path}: No frames found in candidate intervals. Selecting a random frame.')
                idx = random.randint(0, total_frames - 1)
                row = idx // cols
                col = idx % cols
                y_start = row * tile_h
                x_start = col * tile_w
                logging.debug_simple(f'Random frame selected. (row:{row + 1}, col:{col + 1})')
                return cast(NDArray[np.uint8], tile_bgr[y_start:y_start+tile_h, x_start:x_start+tile_w])

            # 外部プロセスでスコア計算を実行
            loop = asyncio.get_running_loop()
            with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
                frames_info = await loop.run_in_executor(executor, self._computeImageScores, frames_data)

            # スコアリングで適切な候補を選定
            if frames_info:
                # 顔ありフレームだけ抜き出す
                face_frames = [(idx, sc, True, im) for (idx, sc, f, im) in frames_info if f]

                if self.face_detection_mode is not None and face_frames:
                    # 顔ありのみから最大スコアを選ぶ
                    best_idx, _, _, best_img = max(face_frames, key=lambda x: x[1])
                    best_row = best_idx // cols
                    best_col = best_idx % cols
                    logging.debug_simple(f'Best frame selected. (face found / row:{best_row + 1}, col:{best_col + 1})')
                    return best_img
                else:
                    # 顔検出無し or 一つも顔が見つからなかった場合
                    best_idx, _, _, best_img = max(frames_info, key=lambda x: x[1])
                    best_row = best_idx // cols
                    best_col = best_idx % cols
                    logging.debug_simple(f'Best frame selected. (face not found / row:{best_row + 1}, col:{best_col + 1})')
                    return best_img

            # スコアリングで適切な候補が見つからなかった場合は、候補区間内からランダムに1枚を選択
            logging.warning(f'{self.file_path}: No suitable frame found by scoring. Selecting a random frame from candidate intervals.')
            _, _, _, _, best_img = random.choice(frames_data)  # タプルのアンパックを修正
            return best_img

        except Exception as ex:
            logging.error(f'{self.file_path}: Error in best frame extraction:', exc_info=ex)
            return None


    async def __saveRepresentativeThumbnail(self, img_bgr: NDArray[np.uint8]) -> bool:
        """
        代表サムネイルを WebP ファイルに保存する

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

            # WebP 出力用のパラメータを設定
            params = [
                cv2.IMWRITE_WEBP_QUALITY, self.WEBP_QUALITY,
            ]

            # WebP ファイルを書き込む
            if not await asyncio.to_thread(cv2.imwrite, str(self.representative_thumbnail_path), img_bgr, params):
                logging.error(f'{self.file_path}: Failed to write representative thumbnail.')
                return False

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


    def __detectLetterbox(self, img_bgr: NDArray[np.uint8]) -> tuple[slice, slice] | None:
        """
        レターボックス（上下左右の黒帯）を検出し、有効な映像領域のスライスを返す
        レターボックス範囲が大きすぎる場合は None を返す

        レターボックスの判定条件:
        1. 輝度が一定以下の領域が存在
        2. その領域のエッジ密度が低い（一様な領域である）
        3. 一定の幅で連続している（ただし完全な連続性は要求しない）

        Args:
            img_bgr (NDArray[np.uint8]): 入力画像 (BGR)

        Returns:
            tuple[slice, slice] | None: (垂直方向のスライス, 水平方向のスライス)
                                      レターボックス範囲が大きすぎる場合は None
        """

        height, width = img_bgr.shape[:2]
        min_height = int(height * self.LETTERBOX_MIN_HEIGHT_RATIO)
        max_height = int(height * self.LETTERBOX_MAX_HEIGHT_RATIO)

        def CheckLetterboxRegion(
            img_slice: NDArray[np.uint8],
            width: int,
            is_vertical: bool = True,
        ) -> tuple[bool, int]:
            """
            指定された領域がレターボックスかどうかを判定する
            輝度とエッジ密度の両方を考慮する

            Args:
                img_slice (NDArray[np.uint8]): 確認する画像の一部
                width (int): 確認する幅
                is_vertical (bool): 垂直方向の確認かどうか

            Returns:
                tuple[bool, int]: (レターボックスと判定されたか, 見つかった場合はその幅)
            """

            # グレースケールに変換
            gray = cv2.cvtColor(img_slice, cv2.COLOR_BGR2GRAY)

            # 輝度の平均を計算
            if is_vertical:
                # 垂直方向の場合は、各行の平均を計算
                luminance = np.asarray(gray[:width]).mean(axis=1, dtype=np.float32)
            else:
                # 水平方向の場合は、各列の平均を計算
                luminance = np.asarray(gray[:, :width]).mean(axis=0, dtype=np.float32)

            # 暗い画素の割合を計算
            dark_ratio = np.sum(luminance <= self.LETTERBOX_LUMINANCE_THRESHOLD) / len(luminance)

            # エッジ検出
            edges = cv2.Canny(gray, 50, 150)
            if is_vertical:
                edge_density = np.sum(edges[:width]) / (width * edges.shape[1])
            else:
                edge_density = np.sum(edges[:, :width]) / (width * edges.shape[0])

            # 暗い領域が一定割合以上で、かつエッジが少ない場合をレターボックスと判定
            if dark_ratio >= self.LETTERBOX_CONTINUOUS_RATIO and edge_density <= self.LETTERBOX_EDGE_THRESHOLD:
                return True, width

            # より狭い範囲で再帰的に確認
            if width > min_height * 2:
                return CheckLetterboxRegion(img_slice, width // 2, is_vertical)

            return False, 0

        # 上下のレターボックスを検出
        top_border = 0
        bottom_border = height

        # 上から走査
        is_letterbox, top_width = CheckLetterboxRegion(
            img_bgr[:max_height],
            max_height,
            is_vertical=True,
        )
        if is_letterbox:
            top_border = top_width

        # 下から走査
        is_letterbox, bottom_width = CheckLetterboxRegion(
            img_bgr[height-max_height:],
            max_height,
            is_vertical=True,
        )
        if is_letterbox:
            bottom_border = height - bottom_width

        # 左右のレターボックスを検出
        left_border = 0
        right_border = width

        # 左から走査
        is_letterbox, left_width = CheckLetterboxRegion(
            img_bgr[:, :max_height],
            max_height,
            is_vertical=False,
        )
        if is_letterbox:
            left_border = left_width

        # 右から走査
        is_letterbox, right_width = CheckLetterboxRegion(
            img_bgr[:, width-max_height:],
            max_height,
            is_vertical=False,
        )
        if is_letterbox:
            right_border = width - right_width

        # レターボックスの面積比率を計算
        total_area = height * width
        valid_area = (bottom_border - top_border) * (right_border - left_border)
        letterbox_ratio = 1.0 - (valid_area / total_area)

        # レターボックス範囲が大きすぎる場合は None を返す
        if letterbox_ratio > self.LETTERBOX_AREA_THRESHOLD:
            return None

        # 検出された黒帯の範囲を除いたスライスを返す
        return (
            slice(top_border, bottom_border),
            slice(left_border, right_border),
        )


    def __checkEdgeRegion(
        self,
        img_slice: NDArray[np.uint8],
        is_vertical: bool = True,
        is_dark: bool = True,
    ) -> tuple[bool, float]:
        """
        指定された領域が暗い（黒に近い）または明るい（白に近い）かどうかを判定する
        演出効果による微細な変化は許容する

        Args:
            img_slice (NDArray[np.uint8]): 確認する画像の一部
            is_vertical (bool): 垂直方向の確認かどうか
            is_dark (bool): 暗部を検出するかどうか（False の場合は明部を検出）

        Returns:
            tuple[bool, float]: (暗部/明部と判定されたか, その割合)
        """

        # グレースケールに変換
        gray = cv2.cvtColor(img_slice, cv2.COLOR_BGR2GRAY)

        # 暗部または明部を検出
        if is_dark:
            mask = gray <= self.EDGE_LUMINANCE_THRESHOLD
        else:
            mask = gray >= self.WHITE_THRESHOLD

        if is_vertical:
            # 垂直方向の場合は、各行のピクセルの割合を計算
            ratios = np.mean(mask, axis=1)
        else:
            # 水平方向の場合は、各列のピクセルの割合を計算
            ratios = np.mean(mask, axis=0)

        # 連続性を考慮した判定
        # 暗部/明部の割合が閾値を超える行/列の数をカウント
        continuous = np.sum(ratios >= self.EDGE_CONTINUOUS_RATIO)
        total_lines = ratios.shape[0]

        # 全体に対する暗部/明部の割合を計算
        ratio = continuous / total_lines

        # 暗部/明部の割合が閾値を超えていれば真
        return ratio >= self.EDGE_DARK_RATIO_THRESHOLD, ratio


    def __detectEdgeBorderIssues(self, img_bgr: NDArray[np.uint8]) -> tuple[float, str]:
        """
        画面の端に接する白/黒の領域を検出する
        演出効果による微細な変化は許容しつつ、画面端の単色領域を検出する

        Args:
            img_bgr (NDArray[np.uint8]): 評価する画像データ (BGR)

        Returns:
            tuple[float, str]: (ペナルティスコア, 検出理由の説明)
        """

        height, width = img_bgr.shape[:2]
        edge_margin_h = int(height * self.EDGE_MARGIN_RATIO)
        edge_margin_w = int(width * self.EDGE_MARGIN_RATIO)

        # エッジ領域を抽出
        edges = {
            'top': img_bgr[:edge_margin_h, :],
            'bottom': img_bgr[-edge_margin_h:, :],
            'left': img_bgr[:, :edge_margin_w],
            'right': img_bgr[:, -edge_margin_w:],
        }

        affected_edges = []
        total_penalty = 0.0
        edge_ratios = []
        edge_types = []

        for edge_name, edge_region in edges.items():
            # 暗部と明部の両方を検出（演出効果を許容）
            is_vertical = edge_name in ['top', 'bottom']
            is_dark_edge, dark_ratio = self.__checkEdgeRegion(edge_region, is_vertical, is_dark=True)
            is_bright_edge, bright_ratio = self.__checkEdgeRegion(edge_region, is_vertical, is_dark=False)

            if is_dark_edge or is_bright_edge:
                affected_edges.append(edge_name)
                edge_ratio = dark_ratio if is_dark_edge else bright_ratio
                edge_ratios.append(edge_ratio)
                edge_types.append('dark' if is_dark_edge else 'bright')
                # エッジごとにペナルティを加算（ただし最大値は超えない）
                total_penalty = min(
                    total_penalty + self.EDGE_BORDER_PENALTY * (edge_ratio / len(edges)),
                    self.EDGE_BORDER_PENALTY
                )

        # 結果の判定
        if len(affected_edges) >= self.MIN_EDGES_REQUIRED:
            edges_str = ', '.join(f'{edge}({ratio:.2f}/{type})' for edge, ratio, type in zip(affected_edges, edge_ratios, edge_types))
            return total_penalty, f'Border effect detected on edges: {edges_str}'

        return 0.0, ''


    def __computeColorBalanceScore(self, img_bgr: NDArray[np.uint8]) -> float:
        """
        画像の色のバランスを評価する (アニメ向け)
        k-means 法で主要な色を抽出し、その分布を評価する

        Args:
            img_bgr (NDArray[np.uint8]): 評価する画像データ (BGR)

        Returns:
            float: 色バランススコア (0.0 ~ 1.0)
        """

        # 計算を軽くするため画像を縮小
        height, width = img_bgr.shape[:2]
        scale = min(1.0, math.sqrt(128 * 128 / (height * width)))
        if scale < 1.0:
            small_img = cv2.resize(img_bgr, None, fx=scale, fy=scale)
        else:
            small_img = img_bgr

        # Lab 色空間に変換 (知覚的な色差を計算するため)
        lab_img = cv2.cvtColor(small_img, cv2.COLOR_BGR2Lab)
        pixels = lab_img.reshape(-1, 3).astype(np.float32)

        # k-means 法で主要な色を抽出
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels, centers = cv2.kmeans(
            pixels,
            self.COLOR_BALANCE_K,
            np.array([]),
            criteria,
            10,
            cv2.KMEANS_PP_CENTERS,
        )

        # 各クラスタの占有率を計算
        total_pixels = len(labels)
        ratios = np.bincount(labels.flatten()) / total_pixels

        # 主要な色の評価
        ## 1. 最大の占有率が大きすぎる場合は単調な画像とみなしスコアを下げる
        if np.max(ratios) > self.COLOR_BALANCE_MAX_RATIO:
            return 0.2

        ## 2. 一定以上の占有率を持つ色の数をカウント
        significant_colors = np.sum(ratios >= self.COLOR_BALANCE_MIN_RATIO)
        if significant_colors < 2:
            return 0.3

        ## 3. 主要な色同士の距離を計算
        min_distance = float('inf')
        for i in range(len(centers)):
            for j in range(i + 1, len(centers)):
                if ratios[i] >= self.COLOR_BALANCE_MIN_RATIO and ratios[j] >= self.COLOR_BALANCE_MIN_RATIO:
                    # Lab色空間でのユークリッド距離
                    distance = float(np.linalg.norm(centers[i] - centers[j]))
                    min_distance = min(min_distance, distance)

        ## 4. 色の距離が近すぎる場合はスコアを下げる
        if min_distance < self.COLOR_BALANCE_MIN_DISTANCE:
            return 0.4

        ## 5. 最終スコアの計算
        ## - 有意な色の数が多いほど高スコア
        ## - 色の距離が大きいほど高スコア
        ## - 占有率のばらつきが適度にあるほど高スコア
        score = float(
            (significant_colors / self.COLOR_BALANCE_K) * 0.4 +  # 有意な色の数
            (min(min_distance / 100.0, 1.0)) * 0.3 +  # 色の距離
            (1.0 - abs(np.std(ratios) - 0.2)) * 0.3  # 占有率の分散
        )

        return score


    def _computeImageScores(
        self,
        frames_data: list[tuple[int, NDArray[np.uint8], int, int, NDArray[np.uint8]]],
    ) -> list[tuple[int, float, bool, NDArray[np.uint8]]]:
        """
        複数フレームのスコアを一括で計算する
        ProcessPoolExecutor で実行されるため、あえて prefix のアンダースコアは1つとしている

        Args:
            frames_data (list[tuple[int, NDArray[np.uint8], int, int, NDArray[np.uint8]]]): (index, frame_bgr, row, col, sub_img) のリスト

        Returns:
            list[tuple[int, float, bool, NDArray[np.uint8]]]: (index, score, found_face, sub_img) のリスト
        """

        # もし Config() の実行時に AssertionError が発生した場合は、LoadConfig() を実行してサーバー設定データをロードする
        ## 通常ならこの関数を ProcessPoolExecutor で実行した場合もサーバー設定データはロード状態になっているはずだが、
        ## 自動リロードモード時のみなぜかグローバル変数がマルチプロセスに引き継がれないため、明示的にロードさせる必要がある
        try:
            Config()
        except AssertionError:
            # バリデーションは既にサーバー起動時に行われているためスキップする
            LoadConfig(bypass_validation=True)

        # 顔検出器のロード (必要な場合のみ)
        face_cascade = None
        auxiliary_face_cascade = None
        if self.face_detection_mode == 'Human':
            face_cascade = cv2.CascadeClassifier(str(self.HUMAN_FACE_CASCADE_PATH))
        elif self.face_detection_mode == 'Anime':
            face_cascade = cv2.CascadeClassifier(str(self.ANIME_FACE_CASCADE_PATH))
            # アニメ顔検出時は精度向上のため、実写顔検出器を併用
            auxiliary_face_cascade = cv2.CascadeClassifier(str(self.HUMAN_FACE_CASCADE_PATH))

        # 各フレームのスコアを計算
        results: list[tuple[int, float, bool, NDArray[np.uint8]]] = []
        for idx, frame_bgr, row, col, sub_img in frames_data:
            score, found_face = self.__computeImageScore(frame_bgr, face_cascade, auxiliary_face_cascade, row, col)
            results.append((idx, score, found_face, sub_img))

        return results


    def __computeImageScore(
        self,
        img_bgr: NDArray[np.uint8],
        face_cascade: cv2.CascadeClassifier | None,
        auxiliary_face_cascade: cv2.CascadeClassifier | None,
        row: int,
        col: int,
    ) -> tuple[float, bool]:
        """
        画質スコア (輝度・コントラスト・シャープネス) を計算し、
        顔検出があれば found_face=True を返す
        顔が検出された場合、その大きさに応じてスコアを加算する

        Args:
            img_bgr (NDArray[np.uint8]): 評価する画像データ (BGR)
            face_cascade (cv2.CascadeClassifier | None): 顔検出器
            row (int): 評価する画像の行番号
            col (int): 評価する画像の列番号

        Returns:
            tuple[float, bool]: (score, found_face)
        """

        found_face = False
        face_size_score = 0.0

        # レターボックスを検出
        letterbox_result = self.__detectLetterbox(img_bgr)
        letterbox_penalty = 0.0
        if letterbox_result is None:
            # レターボックスが多すぎる場合は最低スコアを返す
            return (-1000.0, False)
        elif letterbox_result != (slice(0, img_bgr.shape[0]), slice(0, img_bgr.shape[1])):
            logging.debug_simple(f'Letterbox detected. Penalty applied. (row:{row}, col:{col})')
            # レターボックスが検出された場合はペナルティを与える
            letterbox_penalty = self.LETTERBOX_PENALTY
            # レターボックスを除外した有効領域を取得
            v_slice, h_slice = letterbox_result
            valid_region = img_bgr[v_slice, h_slice]
        else:
            # レターボックスがない場合は画像全体を使用
            valid_region = img_bgr

        # グレースケール変換（複数の処理で使用）
        gray = cv2.cvtColor(valid_region, cv2.COLOR_BGR2GRAY)

        # 単色判定
        solid_color_penalty = 0.0
        channel_variances = [float(np.var(valid_region[:,:,i])) for i in range(3)]
        is_solid_color = all(var < self.COLOR_VARIANCE_THRESHOLD for var in channel_variances)

        # 単色の場合、どの色かをログ出力用に判定し、一律で強いペナルティを与える
        if is_solid_color:
            mean_intensity = float(np.mean(valid_region))
            # ログ出力用の色判定（デバッグ時に役立つ）
            if mean_intensity < self.BLACK_THRESHOLD:
                logging.debug_simple(f'Solid black frame detected. Ignored. (row:{row}, col:{col})')
            elif mean_intensity > self.WHITE_THRESHOLD:
                logging.debug_simple(f'Solid white frame detected. Ignored. (row:{row}, col:{col})')
            else:
                # BGRの平均値から色を推定
                mean_colors = [float(np.mean(valid_region[:,:,i])) for i in range(3)]
                logging.debug_simple(f'Solid color frame detected. (BGR: {mean_colors}). Ignored. (row:{row}, col:{col})')

            # すべての単色に対して同じ強いペナルティを与える
            solid_color_penalty = self.SOLID_COLOR_PENALTY

        # 画面端の単色領域を検出（白/黒に限定）
        edge_penalty, edge_reason = self.__detectEdgeBorderIssues(valid_region)
        if edge_penalty > 0:
            logging.debug_simple(f'{edge_reason} (row:{row}, col:{col})')

        # 顔検出
        if face_cascade is not None:
            # アニメとそれ以外で異なるパラメータを使う
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor = self.ANIME_FACE_DETECTION_SCALE_FACTOR if self.face_detection_mode == 'Anime' else self.HUMAN_FACE_DETECTION_SCALE_FACTOR,
                minNeighbors = self.ANIME_FACE_DETECTION_MIN_NEIGHBORS if self.face_detection_mode == 'Anime' else self.HUMAN_FACE_DETECTION_MIN_NEIGHBORS,
            )

            # 顔が検出された場合の処理
            if len(faces) > 0:
                # 最も大きい顔を基準にスコアを計算
                max_face_area = max(w * h for (_, _, w, h) in faces)
                img_area = valid_region.shape[0] * valid_region.shape[1]
                # 顔の面積比を計算 (0.0 ~ 1.0)
                face_area_ratio = max_face_area / img_area

                # アニメモードの場合の処理
                if self.face_detection_mode == 'Anime':
                    # 実写顔を検出
                    assert auxiliary_face_cascade is not None
                    human_faces = auxiliary_face_cascade.detectMultiScale(
                        gray,
                        scaleFactor = self.NON_ANIME_FACE_DETECTION_SCALE_FACTOR,
                        minNeighbors = self.NON_ANIME_FACE_DETECTION_MIN_NEIGHBORS,
                    )
                    # 実写顔が検出された場合はアニメ顔を無効化
                    if len(human_faces) > 0:
                        logging.debug_simple(f'Human face detected in anime mode. Ignoring anime face. (row:{row}, col:{col})')
                        found_face = False
                        face_size_score = 0.0
                    else:
                        found_face = True
                        logging.debug_simple(f'Anime face detected. Face area ratio: {face_area_ratio:.2f} (row:{row}, col:{col})')

                        # アニメの場合、最適な面積比を超えると緩やかにスコアを低下
                        if face_area_ratio > self.ANIME_FACE_OPTIMAL_RATIO:
                            # 超過分に対して緩やかな減衰を適用
                            excess_ratio = (face_area_ratio - self.ANIME_FACE_OPTIMAL_RATIO) / self.ANIME_FACE_OPTIMAL_RATIO
                            reduction_factor = 1.0 - (excess_ratio * self.ANIME_FACE_RATIO_FALLOFF)
                            reduction_factor = max(0.5, reduction_factor)  # 最低でも50%は維持
                            face_area_ratio = self.ANIME_FACE_OPTIMAL_RATIO + (face_area_ratio - self.ANIME_FACE_OPTIMAL_RATIO) * reduction_factor
                            logging.debug_simple(f'Large anime face detected. Score adjusted by factor {reduction_factor:.2f}.')

                        # アニメ顔のスコアを計算（アニメ用の重み付けを適用）
                        face_size_score = self.FACE_SIZE_BASE_SCORE * face_area_ratio * self.ANIME_FACE_SIZE_WEIGHT

                # 実写モードの場合の処理
                else:
                    found_face = True
                    logging.debug_simple(f'Face detected. Face area ratio: {face_area_ratio:.2f} (row:{row}, col:{col})')
                    # 実写顔のスコアを計算（実写用の重み付けを適用）
                    face_size_score = self.FACE_SIZE_BASE_SCORE * face_area_ratio * self.HUMAN_FACE_SIZE_WEIGHT

        # アニメの場合は色のバランスも評価
        color_balance_score = 0.0
        if self.face_detection_mode == 'Anime':
            color_balance_score = self.__computeColorBalanceScore(valid_region) * self.COLOR_BALANCE_WEIGHT

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
        contrast_bonus = max(0.0, float(1.0 - distance_ratio)) * float(contrast) * 0.1  # ボーナスの影響を抑制
        contrast += contrast_bonus

        # (3) シャープネス (Laplacian の分散)
        lap = cv2.Laplacian(valid_region, cv2.CV_64F)
        sharpness = float(lap.var()) / 2000.0  # シャープネスの値をより強く正規化

        # (4) エッジ密度の計算
        edges = cv2.Canny(gray, 100, 200)
        edge_density = float(np.count_nonzero(edges)) / edges.size

        # エッジ密度が目標値に近いほど高いスコアを与える
        edge_density_score = max(0.0, 1.0 - abs(edge_density - self.EDGE_DENSITY_TARGET) / self.EDGE_DENSITY_TOLERANCE)
        # 情報量が多すぎる場合はペナルティを与える
        if edge_density > self.EDGE_DENSITY_TARGET + self.EDGE_DENSITY_TOLERANCE:
            edge_density_score *= 0.7  # ペナルティを緩和

        # (5) エントロピーの計算
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist = hist.flatten() / hist.sum()
        hist = hist[hist > 0]  # 0を除外
        entropy = -np.sum(hist * np.log2(hist))

        # エントロピーが目標値に近いほど高いスコアを与える
        entropy_score = max(0.0, 1.0 - abs(entropy - self.ENTROPY_TARGET) / self.ENTROPY_TOLERANCE)
        # 情報量が多すぎる場合はペナルティを与える
        if entropy > self.ENTROPY_TARGET + self.ENTROPY_TOLERANCE:
            entropy_score *= 0.7  # ペナルティを緩和

        # スコア計算
        weights = self.ANIME_SCORE_WEIGHTS if self.face_detection_mode == 'Anime' else self.SCORE_WEIGHTS

        # 各指標のスコアを正規化して計算
        std_lum_score = (std_lum / 50.0) * weights['std_lum'] * 100  # 輝度の標準偏差を正規化
        contrast_score = (contrast / 200.0) * weights['contrast'] * 100  # コントラストを正規化
        sharpness_score = min(sharpness * weights['sharpness'] * 100, 100)  # シャープネスに上限を設定
        edge_density_weighted = edge_density_score * weights['edge_density'] * 100
        entropy_weighted = entropy_score * weights['entropy'] * 100

        # 最終スコアを計算
        score = float(
            std_lum_score +
            contrast_score +
            sharpness_score +
            edge_density_weighted +
            entropy_weighted +
            face_size_score +
            color_balance_score -  # アニメの場合の色バランススコア
            solid_color_penalty -
            letterbox_penalty -
            edge_penalty
        )

        # 各指標のスコアをログ出力
        logging.debug_simple(f'Score: (row:{row}, col:{col}):')
        logging.debug_simple(f'  Luminance STD: {std_lum_score:.2f} / Contrast: {contrast_score:.2f} / Sharpness: {sharpness_score:.2f} / Edge Density: {edge_density_weighted:.2f}')
        logging.debug_simple(f'  Entropy: {entropy_weighted:.2f} / Face Size: {face_size_score:.2f} / Color Balance: {color_balance_score:.2f}')
        logging.debug_simple(f'  Solid Color Penalty: -{solid_color_penalty:.2f} / Letterbox Penalty: -{letterbox_penalty:.2f} / Edge Penalty: -{edge_penalty:.2f}')
        logging.debug_simple(f'  = Final Score: {score:.2f}')

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
        face_detection_mode: str | None = typer.Option(
            None,
            "--face-detection",
            "-f",
            help="顔検出モード (Human/Anime) / 指定しない場合はメタデータから自動取得",
        ),
        skip_tile_if_exists: bool = typer.Option(
            False,
            "--skip-tile",
            help="サムネイルタイルが既に存在する場合は再生成をスキップ",
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
        asyncio.run(generator.generateAndSave(skip_tile_if_exists=skip_tile_if_exists))

    typer.run(main)
