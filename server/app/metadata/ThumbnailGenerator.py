
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
import av
import cv2
import numpy as np
import typer
from numpy.typing import NDArray
from tortoise import Tortoise

from app import logging, schemas
from app.config import Config, LoadConfig
from app.constants import DATABASE_CONFIG, LIBRARY_PATH, STATIC_DIR, THUMBNAILS_DIR
from app.models.RecordedVideo import RecordedVideo


class ThumbnailGenerator:
    """
    プレイヤーのシークバー用タイル画像と、候補区間内で最も良い1枚の代表サムネイルを生成するクラス
    (with o1 pro / Claude 3.5 Sonnet -> Claude Opus 4.5)
    """

    # サムネイルのタイル化の設定
    BASE_DURATION_MIN: ClassVar[int] = 30  # 基準となる動画の長さ (30分)
    BASE_INTERVAL_SEC: ClassVar[float] = 5.0  # 基準となる間隔 (5秒)
    MAX_INTERVAL_SEC: ClassVar[float] = 30.0  # 最大間隔 (30秒)
    SCORING_SCALE: ClassVar[tuple[int, int]] = (480, 270)  # スコアリング・代表サムネイル選定時の解像度 (顔検出精度のため維持)
    TILE_SCALE: ClassVar[tuple[int, int]] = (320, 180)  # タイル化時の1フレーム解像度 (width, height)
    LEGACY_TILE_SCALE: ClassVar[tuple[int, int]] = (480, 270)  # 旧タイルの1フレーム解像度 (width, height)
    LEGACY_TILE_COLS: ClassVar[int] = 34  # 旧タイルの列数

    # WebP 出力の設定
    WEBP_QUALITY_REPRESENTATIVE: ClassVar[int] = 80  # 代表サムネイルの WebP 品質 (0-100)
    WEBP_QUALITY_TILE: ClassVar[int] = 71  # シークバーサムネイルタイルの WebP 品質 (0-100)
    WEBP_COMPRESSION: ClassVar[int] = 6  # WebP 圧縮レベル (0-6)
    WEBP_MAX_SIZE: ClassVar[int] = 16383  # WebP の最大サイズ制限 (px)
    FFMPEG_TIMEOUT: ClassVar[int] = 300  # FFmpeg サブプロセスのタイムアウト時間 (秒)

    # サムネイル情報のバージョン
    THUMBNAIL_INFO_VERSION: ClassVar[int] = 1

    # サムネイルタイル移行時のバックアップ設定 (デバッグ用)
    MIGRATION_BACKUP_ENABLED: ClassVar[bool] = False
    MIGRATION_BACKUP_DIR_NAME: ClassVar[str] = 'old'

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
        self.base_tile_interval_sec = self.__calculateBaseTileInterval(duration_sec)

        # タイル情報を計算して初期化
        ## コンストラクタで計算することで、以降のメソッドで None チェックが不要になる
        (
            self.tile_interval_sec,
            self.tile_cols,
            self.tile_rows,
            self.total_tiles,
            self.tile_image_width,
            self.tile_image_height,
        ) = self.__calculateTileLayout()

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


    @classmethod
    def forMigration(cls, file_path: str, file_hash: str, duration_sec: float) -> ThumbnailGenerator:
        """
        既存サムネイルのマイグレーション専用のファクトリメソッド
        タイルレイアウト計算に必要な最低限の情報のみで ThumbnailGenerator を初期化する
        代表サムネイル生成に必要な candidate_time_ranges や face_detection_mode は使用しないため、ダミー値を設定

        Args:
            file_path (str): 録画ファイルのパス (ログ出力用)
            file_hash (str): 録画ファイルのハッシュ
            duration_sec (float): 動画の長さ (秒)

        Returns:
            ThumbnailGenerator: マイグレーション用に初期化された ThumbnailGenerator インスタンス
        """

        return cls(
            file_path = anyio.Path(file_path),
            container_format = 'MPEG-TS',  # マイグレーション処理では使用しないためダミー値
            file_hash = file_hash,
            duration_sec = duration_sec,
            candidate_time_ranges = [],  # マイグレーション処理では使用しないため空リスト
            face_detection_mode = None,  # マイグレーション処理では使用しないため None
        )


    async def generateAndSave(self) -> None:
        """
        プレイヤーのシークバー用サムネイルタイル画像を生成し、
        さらに候補区間内のフレームから最も良い1枚を選び、代表サムネイルとして出力する

        処理フロー:
        1. サブプロセス内で PyAV でフレーム抽出 + スコアリング
        2. サブプロセス内で代表サムネイルを保存
        3. サブプロセス内でタイル画像を生成・保存
        """

        start_time = time.time()
        logging.info(f'{self.file_path}: Generating thumbnail... / Face detection mode: {self.face_detection_mode}')

        try:
            # 万が一出力先ディレクトリが無い場合は作成 (通常存在するはず)
            thumbnails_dir = anyio.Path(str(THUMBNAILS_DIR))
            if not await thumbnails_dir.is_dir():
                await thumbnails_dir.mkdir(parents=True, exist_ok=True)

            # 1. 候補オフセットを計算
            candidate_offsets = self.__calculateCandidateOffsets()

            # 2. フレーム抽出 + タイル画像生成・保存 + 代表サムネイル保存をサブプロセス内で完結させる
            ## 親プロセスへのフレーム配列転送を避け、メモリ使用量とコピーコストを抑制する
            loop = asyncio.get_running_loop()
            with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
                success = await loop.run_in_executor(
                    executor,
                    self._generateAndSaveThumbnails,
                    candidate_offsets,
                    self.tile_rows,
                )

            if not success:
                logging.error(f'{self.file_path}: Failed to generate thumbnails in subprocess.')
                return

            # 3. サムネイル情報を DB に保存
            await self.__saveThumbnailInfoToDB()

            logging.info(f'{self.file_path}: Thumbnail generation completed. (Total: {time.time() - start_time:.2f} sec)')
            logging.debug(f'Thumbnail tile -> {self.seekbar_thumbnails_tile_path.name}')
            logging.debug(f'Representative -> {self.representative_thumbnail_path.name}')

        except Exception as ex:
            # 予期せぬエラーのみここでキャッチ
            logging.error(f'{self.file_path}: Unexpected error in thumbnail generation:', exc_info=ex)
            return


    def __calculateBaseTileInterval(self, duration_sec: float) -> float:
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
        logging.debug(
            f'{self.file_path}: Long video ({duration_min} min), '
            f'using dynamic interval of {interval:.1f} sec. '
            f'Expected {expected_tiles:.1f} tiles (x{increase_ratio:.2f} of base).'
        )
        return interval


    def __calculateTileLayout(self) -> tuple[float, int, int, int, int, int]:
        """
        WebP の最大サイズ制限と動画長に基づき、タイルの間隔とレイアウトを確定する
        上限を超える場合は間隔を引き上げ、必ず WebP の制限内に収める

        Returns:
            tuple[float, int, int, int, int, int]: (tile_interval_sec, tile_cols, tile_rows, total_tiles, tile_image_width, tile_image_height)
        """

        # タイルの幅と高さを取得
        tile_width, tile_height = self.TILE_SCALE
        # WebP の最大サイズ制限から、1行あたりの最大列数と最大行数を算出
        max_cols = max(1, self.WEBP_MAX_SIZE // tile_width)
        max_rows = max(1, self.WEBP_MAX_SIZE // tile_height)
        # WebP に収められる最大タイル数
        max_tiles = max_cols * max_rows

        # 基準間隔で動画全体をカバーした場合の期待タイル数を算出
        expected_tiles = math.ceil(self.duration_sec / self.base_tile_interval_sec)
        # もし期待タイル数が WebP の制限を超える場合は、間隔を引き上げて調整
        if expected_tiles > max_tiles:
            # 最大タイル数に収まるように間隔を再計算（0.1秒単位で切り上げ）
            adjusted_interval = math.ceil((self.duration_sec / max_tiles) * 10) / 10
            # 基準間隔より短くならないように調整
            tile_interval_sec = max(self.base_tile_interval_sec, adjusted_interval)
            logging.warning(
                f'{self.file_path}: Tile count exceeds WebP limit. '
                f'Adjusting interval to {tile_interval_sec:.1f} sec '
                f'(base: {self.base_tile_interval_sec:.1f} sec, max tiles: {max_tiles}).'
            )
        else:
            # WebP の制限内に収まる場合は基準間隔をそのまま使用
            tile_interval_sec = self.base_tile_interval_sec

        # 調整後の間隔で実際に生成されるタイル数を算出
        total_tiles = math.ceil(self.duration_sec / tile_interval_sec)
        if total_tiles < 1:
            total_tiles = 1
        # タイル数から必要な行数を算出
        tile_rows = math.ceil(total_tiles / max_cols)
        # もし行数が最大行数を超える場合は、さらに間隔を引き上げて収める
        if tile_rows > max_rows:
            # 念のため、上限を超える場合はさらに間隔を引き上げて収める
            total_tiles = max_cols * max_rows
            tile_interval_sec = math.ceil((self.duration_sec / total_tiles) * 10) / 10
            tile_rows = max_rows
            logging.warning(
                f'{self.file_path}: Tile rows still exceed WebP limit. '
                f'Adjusting interval again to {tile_interval_sec:.1f} sec.'
            )

        # タイル画像全体の幅と高さを算出
        tile_cols = max_cols
        tile_image_width = tile_width * tile_cols
        tile_image_height = tile_height * tile_rows

        logging.debug(
            f'{self.file_path}: Tile layout -> '
            f'interval: {tile_interval_sec:.1f} sec, '
            f'cols: {tile_cols}, rows: {tile_rows}, total: {total_tiles}, '
            f'image: {tile_image_width}x{tile_image_height}'
        )

        return (tile_interval_sec, tile_cols, tile_rows, total_tiles, tile_image_width, tile_image_height)


    def __calculateCandidateOffsets(self) -> list[float]:
        """
        動画の長さと tile_interval_sec から、各候補フレームの抽出開始位置（秒）のリストを算出する

        Returns:
            list[float]: 各候補フレームの抽出開始位置（秒）のリスト
        """

        # 各候補フレーム抽出の開始位置（秒）を算出（動画末尾の場合は調整する）
        candidate_offsets: list[float] = []
        for i in range(self.total_tiles):
            offset = i * self.tile_interval_sec
            # もし候補フレームの開始位置 + 0.01秒が動画長を超える場合、抽出可能な位置に調整する
            if offset + 0.01 > self.duration_sec:
                offset = max(0, self.duration_sec - 0.02)
            candidate_offsets.append(offset)

        return candidate_offsets


    def _generateAndSaveThumbnails(
        self,
        candidate_offsets: list[float],
        tile_rows: int,
    ) -> bool:
        """
        サブプロセス内でフレーム抽出・スコアリング・タイル生成・代表サムネイル保存まで行う
        PyAV (FFmpeg) によるデコードや OpenCV での画像処理が CPU-bound のため、ProcessPoolExecutor 上で実行する
        ProcessPoolExecutor で実行されるエントリーポイントなので、あえて prefix のアンダースコアは1つとしている
        (別プロセスで実行されるため、__ を付けるとマングリングにより正常に実行できない)

        Args:
            candidate_offsets (list[float]): 抽出するフレームのタイムスタンプ (秒) のリスト
            tile_rows (int): タイルの行数

        Returns:
            bool: 成功時は True、失敗時は False
        """

        # もし Config() の実行時に AssertionError が発生した場合は、LoadConfig() を実行してサーバー設定データをロードする
        ## ProcessPoolExecutor で実行した場合、自動リロードモード時にグローバル変数が引き継がれないことがあるため
        try:
            Config()
        except AssertionError:
            LoadConfig(bypass_validation=True)

        # 1. PyAV でフレーム抽出を実行し、候補区間内のフレームをスコアリングして最良フレームを特定する
        result = self.__extractAndScoreFrames(candidate_offsets)
        if result is None:
            logging.error(f'{self.file_path}: Failed to extract and score frames.')
            return False

        all_frames, best_frame_index = result
        if len(all_frames) == 0:
            logging.error(f'{self.file_path}: No frames extracted at all.')
            return False

        # 2. 代表サムネイルを先に保存（ユーザー体験を優先）
        start_time_representative = time.time()
        if best_frame_index is not None:
            best_frame = all_frames[best_frame_index]
        else:
            # 候補区間内にフレームがない場合はランダムに選択
            logging.warning(f'{self.file_path}: No frames found in candidate intervals. Selecting a random frame.')
            best_frame = random.choice(all_frames)

        if not self.__saveRepresentativeThumbnail(best_frame):
            logging.error(f'{self.file_path}: Failed to save representative thumbnail.')
            return False

        logging.info(f'{self.file_path}: Representative thumbnail saved. ({time.time() - start_time_representative:.2f} sec)')

        # 3. タイル画像を生成・保存
        start_time_tile = time.time()
        if not self.__generateAndSaveTileImage(all_frames, tile_rows):
            logging.error(f'{self.file_path}: Failed to generate and save tile image.')
            return False

        logging.info(f'{self.file_path}: Tile image generation completed. ({time.time() - start_time_tile:.2f} sec)')
        return True


    def __extractAndScoreFrames(
        self,
        candidate_offsets: list[float],
    ) -> tuple[list[NDArray[np.uint8]], int | None] | None:
        """
        PyAV でフレーム抽出し、候補区間内のフレームをスコアリングして最良フレームを特定する

        Args:
            candidate_offsets (list[float]): 抽出するフレームのタイムスタンプ (秒) のリスト

        Returns:
            tuple[list[NDArray[np.uint8]], int | None] | None:
                - 全フレームの BGR 配列リスト (SCORING_SCALE)
                - 最良フレームのインデックス (候補区間内にフレームがない場合は None)
                - エラー時は None
        """

        try:
            start_time_frame_extraction = time.time()

            # 結果を格納するリスト
            scoring_width, scoring_height = self.SCORING_SCALE
            bgr_frames: list[NDArray[np.uint8]] = []

            # MPEG-TS の場合は format を明示的に指定
            format_name = 'mpegts' if self.container_format == 'MPEG-TS' else None

            # シーケンシャルにフレームを抽出（HDD への負荷を考慮）
            container = av.open(str(self.file_path), format=format_name)
            # PyAV で video stream が存在しない場合は、明示的にエラーとして扱う
            if len(container.streams.video) == 0:
                logging.error(f'{self.file_path}: No video stream found in ThumbnailGenerator.')
                raise ValueError('No video stream found in ThumbnailGenerator.')
            video_stream = container.streams.video[0]
            try:
                # コンテナは 1 回だけ開き、各フレーム抽出で seek を繰り返す
                ## MPEG-TS でも実測で問題なければ再オープンを避けられるため、まずは 1 回オープンで検証する
                # I フレームのみデコードする設定（FFmpeg の -skip_frame nointra 相当）
                video_stream.codec_context.skip_frame = 'NONINTRA'

                for i, offset_sec in enumerate(candidate_offsets):
                    try:
                        # 指定位置にシーク
                        # MPEG-TS では start_time が 0 から始まらないことがあるため、start_time を考慮する必要がある
                        # start_time は pts 単位（90kHz クロックで表現された開始位置）なので、
                        # offset_sec を pts 単位に変換してから start_time を加算する
                        if video_stream.time_base is None:
                            # time_base が None の場合はコンテナ形式に応じてフォールバックする
                            if self.container_format == 'MPEG-TS':
                                time_base = 1 / 90000
                                logging.warning(f'{self.file_path}: time_base is None in ThumbnailGenerator, using fallback: {time_base}')
                            else:
                                logging.error(f'{self.file_path}: time_base is None in ThumbnailGenerator for non-TS container.')
                                raise ValueError('time_base is None in ThumbnailGenerator for non-TS container.')
                        else:
                            time_base = float(video_stream.time_base)
                        start_time = video_stream.start_time if video_stream.start_time else 0
                        target_ts = int(start_time + offset_sec / time_base)
                        container.seek(target_ts, backward=True, any_frame=False, stream=video_stream)

                        # seek 後のデコーダ内部状態を初期化し、前回のデコード状態を引きずらないようにする
                        video_stream.codec_context.flush_buffers()

                        # シーク後、最初のフレームを取得
                        frame: av.VideoFrame | None = None
                        for packet in container.demux(video_stream):
                            for decoded_frame in packet.decode():
                                frame = cast(av.VideoFrame, decoded_frame)
                                break
                            if frame is not None:
                                break

                        if frame is None:
                            # フレームが取得できなかった場合は黒画像を使用
                            logging.warning(f'{self.file_path}: Failed to extract frame at {offset_sec:.2f}s. Using black image.')
                            black_frame = np.zeros((scoring_height, scoring_width, 3), dtype=np.uint8)
                            bgr_frames.append(black_frame)
                            continue

                        # フレームを numpy 配列に変換
                        img_rgb = frame.to_ndarray(format='rgb24')

                        # リサイズを実行
                        ## 1440x1080 から一気に 480x270 まで縮小するため INTER_AREA を使う
                        img_resized = cv2.resize(img_rgb, (scoring_width, scoring_height), interpolation=cv2.INTER_AREA)

                        # RGB から OpenCV 向けの BGR に変換して bgr_frames に追加する
                        img_bgr = cast(NDArray[np.uint8], cv2.cvtColor(img_resized, cv2.COLOR_RGB2BGR))
                        bgr_frames.append(img_bgr)

                        # 進捗ログ（50フレームごと）
                        if (i + 1) % 50 == 0:
                            logging.debug(f'{self.file_path}: Extracted {i + 1}/{len(candidate_offsets)} frames')

                    except Exception as ex:
                        # 個別のフレーム抽出エラーは警告にとどめ、黒画像で代替
                        logging.warning(
                            f'{self.file_path}: Error extracting frame at {offset_sec:.2f}s.',
                            exc_info=ex,
                        )
                        black_frame = np.zeros((scoring_height, scoring_width, 3), dtype=np.uint8)
                        bgr_frames.append(black_frame)

                        # 一時的なデマルチプレクサの不調を想定し、念のためコンテナを再オープンして継続
                        try:
                            container.close()
                        except Exception as close_ex:
                            logging.warning(
                                f'{self.file_path}: Failed to close container after error.',
                                exc_info=close_ex,
                            )
                        try:
                            container = av.open(str(self.file_path), format=format_name)
                            video_stream = container.streams.video[0]
                            video_stream.codec_context.skip_frame = 'NONINTRA'
                        except Exception as reopen_ex:
                            logging.error(
                                f'{self.file_path}: Failed to reopen container after error.',
                                exc_info=reopen_ex,
                            )
                            return None
            finally:
                container.close()

            logging.info(f'{self.file_path}: All {len(bgr_frames)} frames extraction completed. ({time.time() - start_time_frame_extraction:.2f} sec)')

            # ========== スコアリング処理 ==========

            start_time_scoring = time.time()

            # 顔検出器のロード (必要な場合のみ)
            face_cascade = None
            auxiliary_face_cascade = None
            if self.face_detection_mode == 'Human':
                face_cascade = cv2.CascadeClassifier(str(self.HUMAN_FACE_CASCADE_PATH))
            elif self.face_detection_mode == 'Anime':
                face_cascade = cv2.CascadeClassifier(str(self.ANIME_FACE_CASCADE_PATH))
                # アニメ顔検出時は精度向上のため、実写顔検出器を併用
                auxiliary_face_cascade = cv2.CascadeClassifier(str(self.HUMAN_FACE_CASCADE_PATH))

            # 候補区間内のフレームを収集してスコアリング
            # (index, score, found_face) のリスト
            scored_frames: list[tuple[int, float, bool]] = []
            total_frames = len(bgr_frames)
            cols = self.tile_cols
            for idx in range(total_frames):
                # このフレームの動画内時間(秒)
                time_offset = idx * self.tile_interval_sec
                # 候補区間に含まれているかどうか
                if not self.__inCandidateIntervals(time_offset):
                    continue

                # タイル上の座標（ログ出力用）
                row = idx // cols + 1
                col = idx % cols + 1

                # スコアを計算
                frame_bgr = bgr_frames[idx]
                score, found_face = self.__computeImageScore(frame_bgr, face_cascade, auxiliary_face_cascade, row, col)
                scored_frames.append((idx, score, found_face))

            # 最良フレームのインデックスを特定
            best_frame_index: int | None = None
            if scored_frames:
                # 顔ありフレームだけ抜き出す
                face_frames = [(idx, sc, True) for (idx, sc, f) in scored_frames if f]

                if self.face_detection_mode is not None and face_frames:
                    # 顔ありのみから最大スコアを選ぶ
                    best_idx, _, _ = max(face_frames, key=lambda x: x[1])
                    best_row = best_idx // cols + 1
                    best_col = best_idx % cols + 1
                    logging.debug(f'Best frame selected. (face found / row:{best_row}, col:{best_col})')
                    best_frame_index = best_idx
                else:
                    # 顔検出無し or 一つも顔が見つからなかった場合
                    best_idx, _, _ = max(scored_frames, key=lambda x: x[1])
                    best_row = best_idx // cols + 1
                    best_col = best_idx % cols + 1
                    logging.debug(f'Best frame selected. (face not found / row:{best_row}, col:{best_col})')
                    best_frame_index = best_idx
            else:
                # 候補区間内のフレームが1枚もない場合
                logging.warning(f'{self.file_path}: No frames found in candidate intervals.')

            logging.info(f'{self.file_path}: Frame scoring completed. ({time.time() - start_time_scoring:.2f} sec)')
            return (bgr_frames, best_frame_index)

        except Exception as ex:
            logging.error(f'{self.file_path}: Error in PyAV frame extraction and scoring:', exc_info=ex)
            return None


    def __saveRepresentativeThumbnail(self, img_bgr: NDArray[np.uint8]) -> bool:
        """
        代表サムネイルを WebP ファイルに同期的に保存する

        Args:
            img_bgr (NDArray[np.uint8]): 保存する画像データ (BGR)

        Returns:
            bool: 成功時は True、失敗時は False
        """

        try:
            # 万が一出力先ディレクトリが無い場合は作成 (通常存在するはず)
            thumbnails_dir = THUMBNAILS_DIR
            if not thumbnails_dir.is_dir():
                thumbnails_dir.mkdir(parents=True, exist_ok=True)

            # WebP ファイルを書き込む
            if not cv2.imwrite(str(self.representative_thumbnail_path), img_bgr, [
                cv2.IMWRITE_WEBP_QUALITY, self.WEBP_QUALITY_REPRESENTATIVE,
            ]):
                logging.error(f'{self.file_path}: Failed to write representative thumbnail.')
                return False

            return True

        except Exception as ex:
            logging.error(f'{self.file_path}: Error in representative thumbnail saving:', exc_info=ex)
            return False


    def __generateAndSaveTileImage(
        self,
        bgr_frames: list[NDArray[np.uint8]],
        tile_rows: int,
    ) -> bool:
        """
        BGR フレームからタイル画像を生成し、WebP として保存する
        フレームは SCORING_SCALE で抽出されているため、TILE_SCALE にリサイズしてからタイル化する
        (SCORING_SCALE == TILE_SCALE の場合はリサイズ不要)

        Args:
            bgr_frames (list[NDArray[np.uint8]]): BGR フレームのリスト (SCORING_SCALE)
            tile_rows (int): タイルの行数

        Returns:
            bool: 成功時は True、失敗時は False
        """

        try:
            tile_width, tile_height = self.TILE_SCALE
            scoring_width, scoring_height = self.SCORING_SCALE

            # SCORING_SCALE と TILE_SCALE が異なる場合はリサイズ
            ## 縮小前ローパス、LANCZOS4 縮小、クロマモアレ抑制、Yアンシャープを組み合わせた高品質な縮小処理を適用
            if (tile_width, tile_height) != (scoring_width, scoring_height):
                resized_frames = [
                    self.downscaleWithAntiMoire(frame, tile_width, tile_height)
                    for frame in bgr_frames
                ]
            else:
                resized_frames = bgr_frames

            # OpenCV を用いてタイル化処理を行う
            rows = []
            num_cols = self.tile_cols
            for r in range(tile_rows):
                row_images = list(resized_frames[r * num_cols: (r + 1) * num_cols])
                # 最終行が列数に満たない場合、黒画像で埋める
                if len(row_images) < num_cols:
                    black_image = np.zeros((tile_height, tile_width, 3), dtype=np.uint8)
                    while len(row_images) < num_cols:
                        row_images.append(black_image)
                row_concat = cv2.hconcat(row_images)
                rows.append(row_concat)
            tile_image = cast(NDArray[np.uint8], cv2.vconcat(rows))

            # タイル画像を WebP としてエンコードし、ファイルに保存する
            if not self.__encodeTileImageToWebP(tile_image, pathlib.Path(str(self.seekbar_thumbnails_tile_path)), str(self.file_path)):
                return False

            return True

        except Exception as ex:
            logging.error(f'{self.file_path}: Error in tile image generation and saving:', exc_info=ex)
            return False


    def downscaleWithAntiMoire(
        self,
        bgr: NDArray[np.uint8],
        out_width: int,
        out_height: int,
        pre_lp_sigma: float = 0.50,
        chroma_sigma: float = 1.0,
        unsharp_sigma: float = 0.8,
        unsharp_amount: float = 0.28,
    ) -> NDArray[np.uint8]:
        """
        縮小前ローパス、LANCZOS4 縮小、クロマモアレ抑制、Yアンシャープを組み合わせた高品質な縮小処理
        モアレを抑制しつつ、シャープネスを維持する

        Args:
            bgr (NDArray[np.uint8]): 入力画像データ (BGR)
            out_width (int): 出力幅
            out_height (int): 出力高さ
            pre_lp_sigma (float): 縮小前ローパスの強さ (デフォルト: 0.50、モアレ抑制とシャープさのバランス)
            chroma_sigma (float): クロマ後処理の強さ (デフォルト: 1.0)
            unsharp_sigma (float): アンシャープ用ぼかしの標準偏差 (デフォルト: 0.8)
            unsharp_amount (float): アンシャープマスクの強度 (デフォルト: 0.28、モアレ抑制とシャープさのバランス)

        Returns:
            NDArray[np.uint8]: 処理後の画像データ (BGR)
        """

        # 縮小率に応じてローパスとシャープの強さを自動調整
        ## 480x270 -> 256x144 の縮小はモアレが出やすいため、縮小率が小さいほど抑制を強める
        in_height, in_width = bgr.shape[:2]
        scale_x = out_width / max(1, in_width)
        scale_y = out_height / max(1, in_height)
        scale = min(scale_x, scale_y)
        scale = float(np.clip(scale, 0.05, 1.0))
        pre_lp_sigma_scaled = float(np.clip(pre_lp_sigma + (1.0 - scale) * 0.35, 0.35, 0.95))
        unsharp_amount_scaled = float(np.clip(unsharp_amount + (1.0 - scale) * 0.20, 0.20, 0.55))
        unsharp_sigma_scaled = float(np.clip(unsharp_sigma + (1.0 - scale) * 0.15, 0.7, 1.1))

        # 強い縮小時は 2 段階で縮小し、折り返し歪みを緩和する
        use_two_step = scale < 0.72
        mid_width = out_width
        mid_height = out_height
        if use_two_step is True:
            mid_scale = (scale + 1.0) / 2.0
            mid_width = round(in_width * mid_scale)
            mid_height = round(in_height * mid_scale)
            if mid_width <= out_width or mid_height <= out_height:
                use_two_step = False

        # 1) YCrCb に分離（Y = 輝度、Cr/Cb = 色差）
        ycc = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
        y, cr, cb = cv2.split(ycc)

        # 2) 縮小前ローパス：Y だけ "ごく弱く"
        ## 色は後で別途やるので、まずは輝度の高周波だけ少し落とす
        y_lp = cv2.GaussianBlur(y, (0, 0), sigmaX=pre_lp_sigma_scaled)

        # 3) LANCZOS4 で縮小（Y はローパス後、Cr/Cb はそのまま縮小）
        ## 強い縮小時は一度 INTER_AREA で中間サイズまで落としてから LANCZOS4 で仕上げる
        if use_two_step is True:
            y_mid = cv2.resize(y_lp, (mid_width, mid_height), interpolation=cv2.INTER_AREA)
            cr_mid = cv2.resize(cr, (mid_width, mid_height), interpolation=cv2.INTER_AREA)
            cb_mid = cv2.resize(cb, (mid_width, mid_height), interpolation=cv2.INTER_AREA)
            y_s = cv2.resize(y_mid, (out_width, out_height), interpolation=cv2.INTER_LANCZOS4)
            cr_s = cv2.resize(cr_mid, (out_width, out_height), interpolation=cv2.INTER_LANCZOS4)
            cb_s = cv2.resize(cb_mid, (out_width, out_height), interpolation=cv2.INTER_LANCZOS4)
        else:
            y_s = cv2.resize(y_lp, (out_width, out_height), interpolation=cv2.INTER_LANCZOS4)
            cr_s = cv2.resize(cr, (out_width, out_height), interpolation=cv2.INTER_LANCZOS4)
            cb_s = cv2.resize(cb, (out_width, out_height), interpolation=cv2.INTER_LANCZOS4)

        # 4) モアレ推定マスク（クロマの細かい揺れを見てマスク化）
        cr_bl = cv2.GaussianBlur(cr_s, (0, 0), sigmaX=chroma_sigma)
        cb_bl = cv2.GaussianBlur(cb_s, (0, 0), sigmaX=chroma_sigma)
        score = cv2.absdiff(cr_s, cr_bl).astype(np.uint16) + cv2.absdiff(cb_s, cb_bl).astype(np.uint16)

        # 閾値は素材で動くのでまずは 12 を試す
        threshold = 10 if scale < 0.6 else 12
        mask = (score > threshold).astype(np.uint8) * 255
        mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
        mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=1.0).astype(np.float32) / 255.0  # 0..1

        # 5) クロマだけ平滑化（モアレ領域ほど強めに）
        cr_strong = cv2.GaussianBlur(cr_s, (0, 0), sigmaX=chroma_sigma * 1.6)
        cb_strong = cv2.GaussianBlur(cb_s, (0, 0), sigmaX=chroma_sigma * 1.6)
        cr2 = (cr_s.astype(np.float32) * (1 - mask) + cr_strong.astype(np.float32) * mask).astype(np.uint8)
        cb2 = (cb_s.astype(np.float32) * (1 - mask) + cb_strong.astype(np.float32) * mask).astype(np.uint8)

        # 6) Y だけアンシャープ。エッジ限定 + モアレ領域では弱める
        ## エッジ以外は極力触らず、線のソリッド感だけを引き出す
        y_bl = cv2.GaussianBlur(y_s, (0, 0), sigmaX=unsharp_sigma_scaled)
        detail = (y_s.astype(np.float32) - y_bl.astype(np.float32))
        sobel_x = cv2.Sobel(y_s.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(y_s.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
        edge_mag = cv2.magnitude(sobel_x, sobel_y)
        edge_mag_array = np.asarray(edge_mag, dtype=np.float32)
        edge_ref = float(np.percentile(edge_mag_array, 95))
        if edge_ref < 1.0:
            edge_ref = 1.0
        edge_norm = cast(NDArray[np.float32], np.clip(edge_mag_array / edge_ref, 0.0, 1.0))
        edge_mask = cast(NDArray[np.float32], np.clip((edge_norm - 0.05) / 0.20, 0.0, 1.0))
        edge_mask = cast(NDArray[np.float32], cv2.GaussianBlur(edge_mask, (0, 0), sigmaX=0.3))

        # モアレ領域は最大70%弱める
        ## エッジのソリッド感を優先するため、エッジ領域は弱めすぎない
        moire_suppress = 1.0 - 0.40 * mask
        edge_boost = 0.34 + 1.45 * edge_mask
        base_amount = unsharp_amount_scaled * 0.34
        amount_local = (unsharp_amount_scaled * edge_boost + base_amount) * moire_suppress
        y2 = np.clip(y_s.astype(np.float32) + detail * amount_local, 0, 255).astype(np.uint8)

        out = cv2.merge([y2, cr2, cb2])
        return cast(NDArray[np.uint8], cv2.cvtColor(out, cv2.COLOR_YCrCb2BGR))


    def __encodeTileImageToWebP(
        self,
        tile_image: NDArray[np.uint8],
        output_path: pathlib.Path,
        log_prefix: str,
    ) -> bool:
        """
        タイル画像を WebP としてエンコードし、ファイルに保存する

        Args:
            tile_image (NDArray[np.uint8]): タイル画像 (BGR)
            output_path (pathlib.Path): 出力先のパス
            log_prefix (str): ログに表示するファイルパスまたは識別子

        Returns:
            bool: 成功時は True、失敗時は False
        """

        # タイル画像を PNG としてメモリ上にエンコード
        _, tile_png_data = cv2.imencode('.png', tile_image)
        if tile_png_data is None:
            logging.error(f'{log_prefix}: Failed to encode tile image as PNG.')
            return False

        # FFmpeg でタイル画像を WebP に圧縮保存
        # 出力形式を -f webp で明示的に指定することで、.tmp などの拡張子でも正しく出力できる
        preset = 'drawing' if self.face_detection_mode == 'Anime' else 'picture'
        process = subprocess.Popen(
            [
                LIBRARY_PATH['FFmpeg'],
                '-y',
                '-nostdin',
                '-f', 'image2pipe',
                '-codec:v', 'png',
                '-i', 'pipe:0',
                '-codec:v', 'webp',
                '-quality', str(ThumbnailGenerator.WEBP_QUALITY_TILE),
                '-compression_level', str(ThumbnailGenerator.WEBP_COMPRESSION),
                '-preset', preset,
                '-threads', 'auto',
                '-f', 'webp',
                str(output_path),
            ],
            stdin = subprocess.PIPE,
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE,
        )

        # FFmpeg プロセスの実行とタイムアウト処理
        try:
            _, stderr_data = process.communicate(input=tile_png_data.tobytes(), timeout=ThumbnailGenerator.FFMPEG_TIMEOUT)
        except subprocess.TimeoutExpired:
            # タイムアウトが発生した場合、プロセスを強制終了してパイプをフラッシュ
            process.kill()
            process.communicate()
            logging.error(f'{log_prefix}: FFmpeg tile image compression timed out after {ThumbnailGenerator.FFMPEG_TIMEOUT} seconds.')
            return False

        if process.returncode != 0:
            error_message = stderr_data.decode('utf-8', errors='ignore')
            logging.error(f'{log_prefix}: FFmpeg tile image compression failed with error: {error_message}')
            return False

        return True


    async def __saveThumbnailInfoToDB(self) -> None:
        """
        生成済みサムネイル情報を DB に保存する
        再生成の場合、既存のサムネイル情報は上書きされる（この時点でサムネイル自体が上書き保存されているので正常な挙動）
        """

        # DB から RecordedVideo を取得
        db_recorded_video = await RecordedVideo.get_or_none(file_path=str(self.file_path))
        if db_recorded_video is None:
            logging.warning(f'{self.file_path}: RecordedVideo not found for thumbnail metadata update.')
            return

        tile_width, tile_height = self.TILE_SCALE
        scoring_width, scoring_height = self.SCORING_SCALE

        # サムネイル情報を DB に保存
        db_recorded_video.thumbnail_info = schemas.ThumbnailInfo(
            version = self.THUMBNAIL_INFO_VERSION,
            representative = schemas.ThumbnailImageInfo(
                format = 'WebP',
                width = scoring_width,
                height = scoring_height,
            ),
            tile = schemas.ThumbnailTileInfo(
                format = 'WebP',
                image_width = self.tile_image_width,
                image_height = self.tile_image_height,
                tile_width = tile_width,
                tile_height = tile_height,
                total_tiles = self.total_tiles,
                column_count = self.tile_cols,
                row_count = self.tile_rows,
                interval_sec = self.tile_interval_sec,
            ),
        )
        await db_recorded_video.save()


    async def migrateFromLegacyTile(self) -> bool:
        """
        既存のサムネイルタイル画像を新仕様に合わせて再タイル化し、サムネイル情報を DB に保存する

        旧仕様 (480x270, 34列) で生成されたタイル画像を読み込み、新仕様 (192x108, 85列) にリサイズ・再タイル化する
        処理は ProcessPoolExecutor で別プロセスで実行され、完了後に旧タイルをバックアップしてから新タイルに置換する
        このメソッドは RecordedScanTask から呼び出される

        Returns:
            bool: 成功時は True、失敗時は False
        """

        # 出力先パスと一時ファイルパスを設定
        ## タイル画像のパスはインスタンス変数 seekbar_thumbnails_tile_path として既に保持されている
        output_tile_path = self.seekbar_thumbnails_tile_path
        temp_tile_path = anyio.Path(f'{output_tile_path}.tmp')

        # ProcessPoolExecutor を使用して別プロセスで画像変換を実行
        ## 画像処理は CPU-bound な処理のため、別プロセスで実行している
        ## anyio.Path は同期関数では実行できないため、pathlib.Path に変換して渡す
        loop = asyncio.get_running_loop()
        try:
            with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
                success = await loop.run_in_executor(
                    executor,
                    self._convertLegacyTileImage,
                    pathlib.Path(str(output_tile_path)),
                    pathlib.Path(str(temp_tile_path)),
                )
        except Exception as ex:
            logging.error(f'{self.file_path}: Error converting legacy tile:', exc_info=ex)
            return False

        # 変換失敗時はエラーログを出力して終了
        if not success:
            logging.error(f'{self.file_path}: Legacy tile migration failed.')
            return False

        # 一時ファイルが生成されていない場合はエラー
        if not await temp_tile_path.is_file():
            logging.error(f'{self.file_path}: Migrated tile file was not created.')
            return False

        # 旧タイルをバックアップしてから新タイルに置換
        backup_dir = anyio.Path(str(THUMBNAILS_DIR / self.MIGRATION_BACKUP_DIR_NAME))

        # バックアップが有効な場合
        backup_path: anyio.Path | None = None
        if self.MIGRATION_BACKUP_ENABLED:
            # バックアップディレクトリを作成
            await backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / output_tile_path.name
            # 同名のバックアップが既に存在する場合はタイムスタンプを付与
            if await backup_path.is_file():
                timestamp = int(time.time())
                backup_path = backup_dir / f'{output_tile_path.stem}_{timestamp}{output_tile_path.suffix}'
            # 旧タイルをバックアップディレクトリに移動
            await output_tile_path.replace(backup_path)
            try:
                # 新タイルを旧タイルのパスに移動
                await temp_tile_path.replace(output_tile_path)
            except Exception as ex:
                # 失敗した場合はバックアップから復元 (ロールバック)
                if await backup_path.is_file():
                    await backup_path.replace(output_tile_path)
                raise ex
        else:
            # バックアップが無効な場合は単純に置換
            await temp_tile_path.replace(output_tile_path)

        if backup_path is not None:
            logging.info(f'{self.file_path}: Legacy tile backed up to {backup_path}.')

        logging.info(
            f'{self.file_path}: Legacy tile converted. '
            f'interval: {self.tile_interval_sec:.1f} sec, '
            f'cols: {self.tile_cols}, rows: {self.tile_rows}, total: {self.total_tiles}.'
        )

        # サムネイル情報を DB に保存
        await self.__saveThumbnailInfoToDB()

        return True


    def _convertLegacyTileImage(
        self,
        legacy_tile_path: pathlib.Path,
        output_tile_path: pathlib.Path,
    ) -> bool:
        """
        既存のタイル画像を読み込み、新しい解像度に合わせて再タイル化する
        旧仕様 (480x270, 34列) で生成されたタイル画像を、新仕様 (192x108, 85列) に変換する
        ProcessPoolExecutor で実行されるエントリーポイントなので、あえて prefix のアンダースコアは1つとしている
        (別プロセスで実行されるため、__ を付けるとマングリングにより正常に実行できない)

        Args:
            legacy_tile_path (pathlib.Path): 変換元のタイル画像パス
            output_tile_path (pathlib.Path): 変換後のタイル画像パス

        Returns:
            bool: 成功時は True、失敗時は False
        """

        # 旧タイル画像を読み込む
        legacy_tile = cv2.imread(str(legacy_tile_path), cv2.IMREAD_COLOR)
        if legacy_tile is None:
            logging.error(f'{self.file_path}: Failed to read legacy tile image.')
            return False

        # 旧タイルの解像度情報を取得
        legacy_width, legacy_height = self.LEGACY_TILE_SCALE
        new_width, new_height = self.TILE_SCALE
        legacy_image_height, legacy_image_width = legacy_tile.shape[:2]
        # 旧タイル画像のサイズから実際の行数・列数を計算
        legacy_rows = legacy_image_height // legacy_height
        legacy_cols = legacy_image_width // legacy_width

        # 期待する列数と実際の列数が一致しない場合は警告を出力
        if legacy_cols != self.LEGACY_TILE_COLS:
            logging.warning(
                f'{self.file_path}: Legacy tile columns mismatch. '
                f'expected: {self.LEGACY_TILE_COLS}, detected: {legacy_cols}.'
            )

        # 旧タイル画像に含まれるタイル数の上限を計算
        max_tiles = legacy_rows * legacy_cols
        total_tiles = self.total_tiles
        # 要求されたタイル数が上限を超える場合は上限に合わせる
        if total_tiles > max_tiles:
            logging.warning(
                f'{self.file_path}: Total tiles exceed legacy tile image. '
                f'using {max_tiles} tiles instead of {total_tiles}.'
            )
            total_tiles = max_tiles

        # 旧タイルからフレームを切り出し、新しいサイズへリサイズ
        resized_frames: list[NDArray[np.uint8]] = []
        for idx in range(total_tiles):
            # タイルの位置 (行・列) を計算
            row = idx // legacy_cols
            col = idx % legacy_cols
            # 切り出し座標を計算
            y0 = row * legacy_height
            y1 = y0 + legacy_height
            x0 = col * legacy_width
            x1 = x0 + legacy_width
            # フレームを切り出し
            frame = legacy_tile[y0:y1, x0:x1]
            # 新しいサイズにリサイズ
            ## 縮小前ローパス、LANCZOS4 縮小、クロマモアレ抑制、Yアンシャープを組み合わせた高品質な縮小処理を適用
            resized_frame = self.downscaleWithAntiMoire(cast(NDArray[np.uint8], frame), new_width, new_height)
            resized_frames.append(resized_frame)

        # 新しい列数でタイル化
        ## リサイズしたフレームを新しい列数で並べ直し、1枚のタイル画像を生成する
        rows = []
        tile_cols = self.tile_cols
        tile_rows = self.tile_rows
        for r in range(tile_rows):
            # この行に含まれるフレームを取得
            row_images = list(resized_frames[r * tile_cols: (r + 1) * tile_cols])
            # 最終行が列数に満たない場合は黒画像で埋める
            if len(row_images) < tile_cols:
                black_image = np.zeros((new_height, new_width, 3), dtype=np.uint8)
                while len(row_images) < tile_cols:
                    row_images.append(black_image)
            # 横方向に連結
            row_concat = cv2.hconcat(row_images)
            rows.append(row_concat)
        # 全ての行を縦方向に連結してタイル画像を完成
        tile_image = cast(NDArray[np.uint8], cv2.vconcat(rows))

        # WebP にエンコードして保存
        return self.__encodeTileImageToWebP(tile_image, output_tile_path, str(self.file_path))


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
            logging.debug(f'Letterbox detected. Penalty applied. (row:{row}, col:{col})')
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
                logging.debug(f'Solid black frame detected. Ignored. (row:{row}, col:{col})')
            elif mean_intensity > self.WHITE_THRESHOLD:
                logging.debug(f'Solid white frame detected. Ignored. (row:{row}, col:{col})')
            else:
                # BGRの平均値から色を推定
                mean_colors = [float(np.mean(valid_region[:,:,i])) for i in range(3)]
                logging.debug(f'Solid color frame detected. (BGR: {mean_colors}). Ignored. (row:{row}, col:{col})')

            # すべての単色に対して同じ強いペナルティを与える
            solid_color_penalty = self.SOLID_COLOR_PENALTY

        # 画面端の単色領域を検出（白/黒に限定）
        edge_penalty, edge_reason = self.__detectEdgeBorderIssues(valid_region)
        if edge_penalty > 0:
            logging.debug(f'{edge_reason} (row:{row}, col:{col})')

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
                        logging.debug(f'Human face detected in anime mode. Ignoring anime face. (row:{row}, col:{col})')
                        found_face = False
                        face_size_score = 0.0
                    else:
                        found_face = True
                        logging.debug(f'Anime face detected. Face area ratio: {face_area_ratio:.2f} (row:{row}, col:{col})')

                        # アニメの場合、最適な面積比を超えると緩やかにスコアを低下
                        if face_area_ratio > self.ANIME_FACE_OPTIMAL_RATIO:
                            # 超過分に対して緩やかな減衰を適用
                            excess_ratio = (face_area_ratio - self.ANIME_FACE_OPTIMAL_RATIO) / self.ANIME_FACE_OPTIMAL_RATIO
                            reduction_factor = 1.0 - (excess_ratio * self.ANIME_FACE_RATIO_FALLOFF)
                            reduction_factor = max(0.5, reduction_factor)  # 最低でも50%は維持
                            face_area_ratio = self.ANIME_FACE_OPTIMAL_RATIO + (face_area_ratio - self.ANIME_FACE_OPTIMAL_RATIO) * reduction_factor
                            logging.debug(f'Large anime face detected. Score adjusted by factor {reduction_factor:.2f}.')

                        # アニメ顔のスコアを計算（アニメ用の重み付けを適用）
                        face_size_score = self.FACE_SIZE_BASE_SCORE * face_area_ratio * self.ANIME_FACE_SIZE_WEIGHT

                # 実写モードの場合の処理
                else:
                    found_face = True
                    logging.debug(f'Face detected. Face area ratio: {face_area_ratio:.2f} (row:{row}, col:{col})')
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
        logging.debug(f'Score: (row:{row}, col:{col}):')
        logging.debug(f'  Luminance STD: {std_lum_score:.2f} / Contrast: {contrast_score:.2f} / Sharpness: {sharpness_score:.2f} / Edge Density: {edge_density_weighted:.2f}')
        logging.debug(f'  Entropy: {entropy_weighted:.2f} / Face Size: {face_size_score:.2f} / Color Balance: {color_balance_score:.2f}')
        logging.debug(f'  Solid Color Penalty: -{solid_color_penalty:.2f} / Letterbox Penalty: -{letterbox_penalty:.2f} / Edge Penalty: -{edge_penalty:.2f}')
        logging.debug(f'  = Final Score: {score:.2f}')

        return (score, found_face)


if __name__ == "__main__":
    # デバッグ用 CLI
    # Usage:
    #   poetry run python -m app.metadata.ThumbnailGenerator generate /path/to/recorded_file.ts
    #   poetry run python -m app.metadata.ThumbnailGenerator migrate <file_hash> <duration_sec>
    app = typer.Typer()

    @app.command()
    def generate(
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
        asyncio.run(generator.generateAndSave())

    @app.command()
    def migrate(
        recorded_video_id: int = typer.Argument(
            ...,
            help="対象の録画ファイルの ID",
        ),
    ) -> None:
        """
        既存のサムネイルタイル画像を新仕様にマイグレーションする
        旧仕様 (480x270, 34列) から新仕様 (192x108, 85列) に変換する
        """

        async def run() -> bool:

            # データベースを初期化
            await Tortoise.init(config=DATABASE_CONFIG)

            try:
                # RecordedVideo を取得
                db_recorded_video = await RecordedVideo.get_or_none(id=recorded_video_id)
                if db_recorded_video is None:
                    logging.error(f'RecordedVideo not found: {recorded_video_id}')
                    return False

                # 既に thumbnail_info が設定されている場合はマイグレーション済みなのでスキップ
                if db_recorded_video.thumbnail_info is not None:
                    logging.info(f'RecordedVideo {recorded_video_id}: Already migrated. Skipping.')
                    return True

                file_path = db_recorded_video.file_path
                file_hash = db_recorded_video.file_hash
                duration_sec = db_recorded_video.duration

                tile_path = THUMBNAILS_DIR / f'{file_hash}_tile.webp'
                thumbnail_path = THUMBNAILS_DIR / f'{file_hash}.webp'

                logging.info(f'RecordedVideo ID: {recorded_video_id}')
                logging.info(f'File path: {file_path}')
                logging.info(f'File hash: {file_hash}')
                logging.info(f'Duration: {duration_sec} sec')
                logging.info(f'Tile path: {tile_path}')
                logging.info(f'Thumbnail path: {thumbnail_path}')

                # ファイルの存在確認
                if not tile_path.exists():
                    logging.error(f'Tile file not found: {tile_path}')
                    return False
                if not thumbnail_path.exists():
                    logging.error(f'Thumbnail file not found: {thumbnail_path}')
                    return False

                generator = ThumbnailGenerator.forMigration(
                    file_path = file_path,
                    file_hash = file_hash,
                    duration_sec = duration_sec,
                )

                logging.info('Tile layout:')
                logging.info(f'  interval: {generator.tile_interval_sec:.1f} sec')
                logging.info(f'  cols: {generator.tile_cols}')
                logging.info(f'  rows: {generator.tile_rows}')
                logging.info(f'  total: {generator.total_tiles}')
                logging.info(f'  image: {generator.tile_image_width}x{generator.tile_image_height}')

                logging.info('Starting migration...')
                return await generator.migrateFromLegacyTile()

            finally:
                # データベース接続を閉じる（必須）
                await Tortoise.close_connections()

        # 設定を読み込む (必須)
        LoadConfig(bypass_validation=True)

        success = asyncio.run(run())

        if success:
            logging.info('Migration succeeded!')
        else:
            logging.error('Migration failed!')
            raise typer.Exit(1)

    app()
