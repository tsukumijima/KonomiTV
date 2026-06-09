
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import asyncio
import bisect
import math
import time
import uuid
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

from biim.mpeg2ts import ts
from fastapi import HTTPException, status
from tortoise import transactions

from app import logging
from app.config import Config
from app.constants import QUALITY_TYPES
from app.models.RecordedProgram import RecordedProgram
from app.models.RecordedVideo import RecordedVideo
from app.schemas import KeyFrame, SegmentMapEntry
from app.streams.StreamEncodingOptions import StreamEncodingOptions
from app.streams.VideoEncodingTask import VideoEncodingTask
from app.streams.VideoSegmentPlanner import VideoSegmentPlanner
from app.utils import SetTimeout
from app.utils.MP4KeyFrameParser import MP4KeyFrameParser
from app.utils.TSKeyFrameSeeker import TSKeyFrameSeeker, TSStreamInfo


@dataclass
class VideoStreamSegment:
    """
    ビデオストリームの HLS セグメントを表すデータクラス
    """

    # HLS セグメントのシーケンス番号
    ## リストのインデックスと一致する (0 から始まるので注意)
    sequence_index: int
    # HLS プレイリスト上の開始時刻 (秒)
    ## 入力ソース側の DTS とは別物で、仮想プレイリストを等間隔で作るための再生時刻
    playlist_start_seconds: float
    # エンコードを開始する入力ファイルの位置 (バイト)
    ## TS コンテナはオンデマンド探索または segment_map で解決し、MP4 は psisimux に時刻を渡すため None のまま扱う
    source_file_position: int | None
    # エンコードを開始する入力ソース側の DTS (90kHz)
    ## プレイリスト上の開始時刻以前で最も近いキーフレーム DTS が入り、未解決の間は None
    source_start_dts: int | None
    # HLS セグメント長 (秒単位)
    ## プレイリストはフレームレートから算出した固定長で作り、実際の入力開始位置は再生時に別途解決する
    duration_seconds: float
    # HLS セグメントのエンコードの状態
    encode_status: Literal['Pending', 'Encoding', 'Completed']
    # HLS セグメントのエンコード済み MPEG-TS データが返る asyncio.Future
    encoded_segment_ts_future: asyncio.Future[bytes]
    # HLS セグメントのエンコード済み MPEG-TS データが既にクライアントによって読み取られているかを表すフラグ
    ## このフラグが True の VideoStreamSegment は、メモリ節約のため順に破棄される (readed と意図的に過去形にしている)
    is_encoded_segment_ts_future_readed: bool = False

    async def resetState(self) -> None:
        """
        このセグメントの状態をリセットする
        リセットすると保持されている asyncio.Future は初期化され、ステータスも Pending に戻る
        実行中のイベントループ上でのみ呼び出される前提のため、呼び出し側でもその制約が見えるよう敢えて async def で定義している
        """
        if not self.encoded_segment_ts_future.done():
            self.encoded_segment_ts_future.set_result(b'')  # 前の Future がまだ完了していない場合は空のデータで完了させる
        self.encode_status = 'Pending'

        # 新しい Future は、現在実行中のイベントループに明示的に紐付けて再初期化する
        ## これにより「イベントループ上で呼び出す前提」がコード上でも明確になる
        self.encoded_segment_ts_future = asyncio.get_running_loop().create_future()
        self.is_encoded_segment_ts_future_readed = False


class VideoStream:
    """ 録画視聴セッションを管理するクラス """

    # 録画視聴セッションが再生されていない場合にタイムアウトするまでの時間 (秒)
    # この時間が経過すると、録画視聴セッションのインスタンスは自動的に破棄される
    SESSION_TIMEOUT: ClassVar[float] = float(10)  # 10 秒

    # 一度でも読み取られた HLS セグメントの最大保持数
    MAX_READED_SEGMENTS: ClassVar[int] = 10

    # QSVEncC でエンコードを開始する際、入力 DTS が 33bit ラップアラウンド直前だと時刻補正でフレーム間隔がズレる問題を回避するための余裕
    DTS_WRAP_AVOIDANCE_SECONDS: ClassVar[int] = 60

    # DTS ラップ回避で遡る最大セグメント数
    ## 通常は 10 セグメント前後で抜けるが、万が一 segment_map が壊れている場合に無制限にソース位置解決が走る事態を防ぐ
    DTS_WRAP_AVOIDANCE_MAX_BACKTRACK_SEGMENTS: ClassVar[int] = 40

    # 再生しながら見つけたキーフレーム位置を segment_map として保存する最小件数
    ## DB 書き込みを HLS セグメントごとに発生させず、再生済み範囲をある程度まとめて保存する
    SEGMENT_MAP_SAVE_BATCH_SIZE: ClassVar[int] = 16

    # 録画視聴セッションのインスタンスが入る、セッション ID をキーとした辞書
    # この辞書に録画視聴セッションに関する全てのデータが格納されている
    __instances: ClassVar[dict[str, VideoStream]] = {}

    # recorded_videos.segment_map の JSON 更新を録画ファイル単位で直列化するロック
    ## SQLite の select_for_update() だけでは同一プロセス内の別視聴セッション同士の読み直し競合を十分に避けられない
    ## ロックを使い終えた録画 ID は自動的に辞書から消し、長期稼働時に録画 ID 分だけ残り続ける状態を避ける
    __segment_map_save_locks: ClassVar[weakref.WeakValueDictionary[int, asyncio.Lock]] = weakref.WeakValueDictionary()


    # 必ずセッション ID ごとに1つのインスタンスになるように (Singleton)
    def __new__(
        cls,
        session_id: str,
        recorded_program: RecordedProgram,
        quality: QUALITY_TYPES,
        encoding_options: StreamEncodingOptions | None = None,
        is_new_session_allowed: bool = False,
    ) -> VideoStream:

        # まだ同じセッション ID のインスタンスがないときだけ、インスタンスを生成する
        if session_id not in cls.__instances:

            # 録画視聴セッションは、プレイリスト API での初回作成時だけ新規作成を許可する
            ## セグメント取得や Keep-Alive が未知の session_id を指定した場合に、初期化情報の欠けたセッションを作らない
            if is_new_session_allowed is False or encoding_options is None:
                # まだ VideoStream インスタンスが存在しないため、ここだけは要求された品質からログの接頭辞を組み立てる
                ## 追加オプションが渡されている場合は、セッション不在のエラーログにも同じ品質文字列を出す
                requested_encoding_options = encoding_options or StreamEncodingOptions()
                logging.error(
                    f'[Video: {recorded_program.id}/{session_id}/{quality}{requested_encoding_options.buildSuffix()}] '
                    f'Session does not exist.'
                )
                raise HTTPException(
                    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail = 'Session does not exist',
                )

            # 新しい録画視聴セッションのインスタンスを生成する
            instance = super().__new__(cls)

            # セッション ID を設定
            instance.session_id = session_id

            # 録画番組の情報と映像の品質を設定
            instance.recorded_program = recorded_program
            instance.quality = quality
            instance.encoding_options = encoding_options

            # HLS セグメントの基準長 (秒)
            ## 録画ファイルのフレームレートから算出し、プレイリスト生成とオンデマンド探索で共通利用する
            instance._segment_duration_seconds = VideoSegmentPlanner.computeSegmentDurationSeconds(
                recorded_program.recorded_video.video_frame_rate,
            )

            # HLS セグメントを格納するリスト
            instance._segments = []

            # segment_map はシーケンス番号で参照するため、視聴セッション内では辞書として保持する
            ## DB には JSON 配列のまま保存し、検索時だけ辞書化することで保存形式を増やさずに参照コストを下げる
            instance._segment_map_by_sequence = {
                entry['sequence_index']: entry
                for entry in recorded_program.recorded_video.segment_map
            }

            # 入力ソース位置のオンデマンド解決で使うキャッシュ
            ## TS コンテナでは PAT/PMT から得た PID 情報と先頭 DTS を、MP4 では moov 由来の同期サンプル DTS 一覧を保持する
            instance._ts_stream_info = None
            instance._ts_source_base_dts = None
            instance._mp4_keyframe_dts_list = None
            instance._source_position_lock = asyncio.Lock()

            # 現在実行中の VideoEncodingTask のインスタンス
            ## 録画再生時は、シークによりエンコーダーの再起動が必要になる度に、新しい VideoEncodingTask を都度作り直す
            ## なお、エンコードタスクの停止時は Task.cancel() ではなく VideoEncodingTask.cancel() を使い
            ## 外部プロセスを即座に停止させる必要があるため、Task への参照とは別に、VideoEncodingTask のインスタンス自体も保持している
            instance._video_encoding_task = VideoEncodingTask(instance)
            # セグメント要求の多重実行時に、エンコードタスクの停止と起動が競合しないよう直列化する
            instance._video_encoding_task_lock = asyncio.Lock()
            # 現在実行中の VideoEncodingTask のタスクへの参照
            # ref: https://docs.astral.sh/ruff/rules/asyncio-dangling-task/
            instance._video_encoding_task_ref = None
            # 終了待機がタイムアウトした古い VideoEncodingTask のタスクへの参照
            # イベントループ上の Task は弱参照で管理されるため、自然終了するまでここで強参照を保持する
            instance._detached_video_encoding_task_refs = set()

            # キャンセルされない限り SESSION_TIMEOUT 秒後にインスタンスを破棄するタイマー
            # cancel_destroy_timer() を呼び出すことでタイマーをキャンセルできる
            instance._cancel_destroy_timer = SetTimeout(lambda: asyncio.create_task(instance.destroy()), cls.SESSION_TIMEOUT)

            # 生成したインスタンスを登録する
            cls.__instances[session_id] = instance

            logging.info(f'{instance.log_prefix} Streaming Session Started.')

        else:
            # 既存のインスタンスを取得
            instance = cls.__instances[session_id]

            # 録画番組 ID と画質が一致するか確認
            if instance.recorded_program.id != recorded_program.id or instance.quality != quality:
                # 既存セッション側と要求側の品質を両方出し、session_id 再利用ミスをログから判別しやすくする
                requested_encoding_options = encoding_options or StreamEncodingOptions()
                logging.error(
                    f'{instance.log_prefix} Session exists but program_id or quality mismatch. '
                    f'[program_id: {recorded_program.id}, '
                    f'quality: {quality}{requested_encoding_options.buildSuffix()}]'
                )
                raise HTTPException(
                    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail = 'Session exists but program_id or quality mismatch',
                )

            # プレイリスト再取得時に同じ session_id で別の追加オプションが指定された場合は異常として扱う
            ## session_id は録画視聴セッションを識別する値なので、初回作成時と異なるオプションを後から混ぜるとエンコード状態が曖昧になる
            if encoding_options is not None and instance.encoding_options != encoding_options:
                logging.error(
                    f'{instance.log_prefix} Session exists but encoding options mismatch. '
                    f'[is_hevc_10bit_enabled: {encoding_options.is_hevc_10bit_enabled}, '
                    f'is_24fps_mode_enabled: {encoding_options.is_24fps_mode_enabled}]'
                )
                raise HTTPException(
                    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail = 'Session exists but encoding options mismatch',
                )

        # 登録されているインスタンスを返す
        return cls.__instances[session_id]


    def __init__(
        self,
        session_id: str,
        recorded_program: RecordedProgram,
        quality: QUALITY_TYPES,
        encoding_options: StreamEncodingOptions | None = None,
        is_new_session_allowed: bool = False,
    ) -> None:
        """
        録画視聴セッションのインスタンスを取得する

        Args:
            session_id (str): セッション ID
            recorded_program (RecordedProgram): 録画番組の情報
            quality (QUALITY_TYPES): 映像の品質 (1080p-60fps ~ 240p)
            encoding_options (StreamEncodingOptions | None): ベース画質に追加するエンコードオプション
            is_new_session_allowed (bool): セッションが存在しない場合に新規作成を許可するかどうか
        """

        # インスタンス変数の型ヒントを定義
        # Singleton のためインスタンスの生成は __new__() で行うが、__init__() も定義しておかないと補完がうまく効かない
        self.session_id: str
        self.recorded_program: RecordedProgram
        self.quality: QUALITY_TYPES
        self.encoding_options: StreamEncodingOptions
        self._segment_duration_seconds: float
        self._segments: list[VideoStreamSegment]
        self._segment_map_by_sequence: dict[int, SegmentMapEntry]
        self._ts_stream_info: TSStreamInfo | None
        self._ts_source_base_dts: int | None
        self._mp4_keyframe_dts_list: list[int] | None
        self._source_position_lock: asyncio.Lock
        self._video_encoding_task: VideoEncodingTask
        self._video_encoding_task_lock: asyncio.Lock
        self._video_encoding_task_ref: asyncio.Task[None] | None
        self._detached_video_encoding_task_refs: set[asyncio.Task[None]]
        self._cancel_destroy_timer: Callable[[], None]


    @property
    def log_prefix(self) -> str:
        """
        ログのプレフィックス
        """
        return f'[Video: {self.recorded_program.id}/{self.session_id}/{self.quality}{self.encoding_options.buildSuffix()}]'


    @property
    def segments(self) -> tuple[VideoStreamSegment, ...]:
        """
        HLS セグメントを格納するリスト (読み取り専用)
        一旦録画データの長さすべての VideoStreamSegment を作成したあと、必要に応じてエンコードしていく
        基本一度 VideoStream 内部でセットされたら外部から変更されるべきではないので、読み取り専用にしている
        """
        return tuple(self._segments)


    @property
    def ts_stream_info(self) -> TSStreamInfo | None:
        """
        MPEG-TS のオンデマンド探索で得たストリーム情報

        Returns:
            TSStreamInfo | None: 映像 PID などのストリーム情報 (未解決の場合は None)
        """

        return self._ts_stream_info


    @property
    def ts_source_base_dts(self) -> int | None:
        """
        MPEG-TS の先頭キーフレーム DTS

        Returns:
            int | None: 先頭キーフレーム DTS (未解決の場合は None)
        """

        return self._ts_source_base_dts


    async def ensureTSKeyFrameContext(self) -> None:
        """
        MPEG-TS のキーフレーム解析に必要なストリーム情報と先頭 DTS を用意する
        """

        recorded_video = self.recorded_program.recorded_video
        if recorded_video.container_format != 'MPEG-TS':
            return

        async with self._source_position_lock:
            file_path = Path(recorded_video.file_path)

            # segment_map キャッシュから再生を開始した場合、ソース位置は即時解決できても PID 情報が未取得のままになる
            ## 再生中のキーフレーム収集は入力 TS の PES を読むため、必要になった時点で一度だけ PAT/PMT を読む
            if self._ts_stream_info is None:
                self._ts_stream_info = await asyncio.to_thread(
                    TSKeyFrameSeeker.findStreamInfo,
                    file_path,
                )

            # segment_map をプレイリスト時刻へ対応させるには、録画先頭の DTS が基準として必要になる
            ## ここも同一セッション内で変わらないため、未取得のときだけ読み込む
            if self._ts_source_base_dts is None:
                self._ts_source_base_dts = await asyncio.to_thread(
                    TSKeyFrameSeeker.findBaseDTS,
                    file_path,
                    self._ts_stream_info,
                )


    def __registerVideoEncodingTaskRef(self, video_encoding_task_ref: asyncio.Task[None]) -> None:
        """
        VideoEncodingTask の完了時に不要な参照を解放するコールバックを登録する

        Args:
            video_encoding_task_ref (asyncio.Task[None]): 参照管理対象の VideoEncodingTask
        """

        def OnVideoEncodingTaskDone(done_task: asyncio.Task[None]) -> None:
            self._detached_video_encoding_task_refs.discard(done_task)
            # 現在実行中の VideoEncodingTask のタスクが終了待機を打ち切ったタスクだった場合は、その参照を None にする
            if self._video_encoding_task_ref == done_task:
                self._video_encoding_task_ref = None

        video_encoding_task_ref.add_done_callback(OnVideoEncodingTaskDone)


    def __detachVideoEncodingTaskRef(self, video_encoding_task_ref: asyncio.Task[None]) -> None:
        """
        終了待機を打ち切った VideoEncodingTask のタスクへの参照を保持する

        Args:
            video_encoding_task_ref (asyncio.Task[None]): 自然終了待ちに移行する VideoEncodingTask
        """

        # すでに完了済みのタスクなら done callback 側で参照は解放済みなので、保持し直す必要はない
        if video_encoding_task_ref.done() is True:
            return

        # 終了待機を打ち切った VideoEncodingTask のタスクへの参照を保持する
        self._detached_video_encoding_task_refs.add(video_encoding_task_ref)


    def keepAlive(self) -> None:
        """
        録画視聴セッションのアクティブ状態を維持する
        番組の視聴中は定期的にこのメソッドを呼び出す必要があり、呼び出されなくなった場合は自動的に終了処理が行われる
        """

        # 前回のタイマーをキャンセルする
        self._cancel_destroy_timer()

        # キャンセルされない限り SESSION_TIMEOUT 秒後にインスタンスを破棄するタイマーを設定する
        self._cancel_destroy_timer = SetTimeout(lambda: asyncio.create_task(self.destroy()), self.SESSION_TIMEOUT)


    def getBufferRange(self) -> tuple[float, float]:
        """
        エンコード完了済みの HLS セグメントのバッファ範囲 (秒) を返す

        Returns:
            tuple[float, float]: バッファ範囲 (開始時刻, 終了時刻)
        """

        # エンコード済みの全セグメントの範囲を計算する
        # エンコード済み (Completed) のセグメントのみを対象とする
        encoded_segments = [s for s in self._segments if s.encode_status == 'Completed']
        if encoded_segments:
            # エンコード済みの最初のセグメントの開始時刻から最後のセグメントの終了時刻までを計算
            first_segment = encoded_segments[0]
            last_segment = encoded_segments[-1]
            buffer_start = first_segment.playlist_start_seconds
            buffer_end = last_segment.playlist_start_seconds + last_segment.duration_seconds
            return (buffer_start, buffer_end)
        else:
            # エンコード済みのセグメントがない場合は (0, 0) を返す
            return (0, 0)


    def getVirtualPlaylist(self, cache_key: str | None = None) -> str:
        """
        仮想 HLS M3U8 プレイリストを取得する
        返却時点では仮想 HLS M3U8 プレイリストに記載されているセグメントのデータは存在せず (「仮想」のゆえん)、随時エンコードされる

        Args:
            cache_key (str | None): キャッシュ制御用のキー (None の場合は新しいキーを生成する)

        Returns:
            str: 仮想 HLS M3U8 プレイリスト
        """

        # セッションのアクティブ状態を維持する
        self.keepAlive()

        # まだ HLS セグメントリストが空なら、録画時間とフレームレートから仮想セグメントを作成する
        if len(self._segments) == 0:
            segment_count = max(1, math.ceil(self.recorded_program.recorded_video.duration / self._segment_duration_seconds))
            for segment_sequence in range(segment_count):
                playlist_start_seconds = segment_sequence * self._segment_duration_seconds
                remaining_duration = self.recorded_program.recorded_video.duration - playlist_start_seconds
                duration_seconds = min(self._segment_duration_seconds, max(remaining_duration, 0.001))
                self._segments.append(VideoStreamSegment(
                    sequence_index = segment_sequence,
                    playlist_start_seconds = playlist_start_seconds,
                    source_file_position = None,
                    source_start_dts = None,
                    duration_seconds = duration_seconds,
                    encode_status = 'Pending',
                    encoded_segment_ts_future = asyncio.Future(),
                ))

            logging.info(
                f'{self.log_prefix} Total {len(self._segments)} virtual segments '
                f'(segment_duration: {self._segment_duration_seconds:.6f}s).'
            )

        # キャッシュキーが指定されていない場合は UUID の - で区切って一番左側のみを使う
        if cache_key is None:
            cache_key = uuid.uuid4().hex.split('-')[0]

        # 仮想 HLS M3U8 プレイリストを生成
        virtual_playlist = ''
        virtual_playlist += '#EXTM3U\n'
        virtual_playlist += '#EXT-X-VERSION:6\n'
        virtual_playlist += '#EXT-X-PLAYLIST-TYPE:VOD\n'

        # HLS セグメントの実時間の最大値を指定する (小数点以下は切り上げ)
        target_duration = max(s.duration_seconds for s in self._segments)
        virtual_playlist += f'#EXT-X-TARGETDURATION:{math.ceil(target_duration)}\n'

        # 事前に算出したセグメントをすべて記述する
        for segment in self._segments:
            # セグメントの長さ (秒, 小数点以下6桁まで)
            virtual_playlist += f'#EXTINF:{segment.duration_seconds:.6f},\n'
            # キャッシュ避けのためにキャッシュキーを付与する
            virtual_playlist += f'segment?session_id={self.session_id}&sequence={segment.sequence_index}&cache_key={cache_key}\n'

        virtual_playlist += '#EXT-X-ENDLIST\n'
        return virtual_playlist


    async def resolveSegmentSourcePosition(self, segment_sequence: int) -> None:
        """
        指定セグメントをエンコード開始点として使えるよう、入力ソース側の位置と DTS を解決する

        Args:
            segment_sequence (int): 解決対象セグメントのシーケンス番号
        """

        resolve_start_time = time.perf_counter()
        segment = self._segments[segment_sequence]

        # 既に解決済みなら、エンコードタスク側でそのまま利用できる
        if segment.source_start_dts is not None:
            logging.debug(
                f'{self.log_prefix}[Segment {segment_sequence}] '
                f'Segment source position already resolved. '
                f'[elapsed: {(time.perf_counter() - resolve_start_time) * 1000:.1f}ms]'
            )
            return

        async with self._source_position_lock:
            # 多重リクエストでロック待ちの間に別リクエストが解決している可能性がある
            segment = self._segments[segment_sequence]
            if segment.source_start_dts is not None:
                logging.debug(
                    f'{self.log_prefix}[Segment {segment_sequence}] '
                    f'Segment source position resolved while waiting for lock. '
                    f'[elapsed: {(time.perf_counter() - resolve_start_time) * 1000:.1f}ms]'
                )
                return

            recorded_video = self.recorded_program.recorded_video
            file_path = Path(recorded_video.file_path)

            if recorded_video.container_format == 'MPEG-TS':
                # segment_map は再生開始位置のキャッシュなので、見つかればファイル I/O なしで即座に使う
                segment_map_entry = self._segment_map_by_sequence.get(segment_sequence)
                if segment_map_entry is not None:
                    segment.source_file_position = segment_map_entry['source_file_position']
                    segment.source_start_dts = segment_map_entry['source_start_dts']
                    logging.debug(
                        f'{self.log_prefix}[Segment {segment_sequence}] '
                        f'Segment source position resolved from segment_map. '
                        f'[elapsed: {(time.perf_counter() - resolve_start_time) * 1000:.1f}ms]'
                    )
                    return

                # PAT/PMT と先頭 DTS は同一視聴セッション内で変わらないため、最初の探索時だけ読む
                if self._ts_stream_info is None:
                    self._ts_stream_info = await asyncio.to_thread(
                        TSKeyFrameSeeker.findStreamInfo,
                        file_path,
                    )
                if self._ts_source_base_dts is None:
                    self._ts_source_base_dts = await asyncio.to_thread(
                        TSKeyFrameSeeker.findBaseDTS,
                        file_path,
                        self._ts_stream_info,
                    )

                source_position = await asyncio.to_thread(
                    TSKeyFrameSeeker.seek,
                    file_path,
                    self._ts_stream_info,
                    segment.playlist_start_seconds,
                    self._ts_source_base_dts,
                    round(self._segment_duration_seconds * ts.HZ),
                )
                segment.source_file_position = source_position.source_file_position
                segment.source_start_dts = source_position.source_start_dts

                # オンデマンド探索の結果は次回以降のシークを軽くするため DB に保存する
                ## 保存失敗は再生失敗に直結しないため、ログだけ残してエンコード開始は続行する
                assert source_position.source_file_position is not None
                segment_map_entry = SegmentMapEntry(
                    sequence_index = segment_sequence,
                    source_file_position = source_position.source_file_position,
                    source_start_dts = source_position.source_start_dts,
                )
                await self.saveSegmentMapEntries([segment_map_entry])
                logging.info(
                    f'{self.log_prefix}[Segment {segment_sequence}] '
                    f'Segment source position resolved by TS seek. '
                    f'[elapsed: {(time.perf_counter() - resolve_start_time) * 1000:.1f}ms]'
                )
                return

            # MP4 は moov 内テーブルから同期サンプル DTS を短時間で復元できるため、DB キャッシュを作らない
            if self._mp4_keyframe_dts_list is None:
                self._mp4_keyframe_dts_list = await asyncio.to_thread(
                    MP4KeyFrameParser.readVideoKeyFrameDTS,
                    file_path,
                )
            source_start_dts = MP4KeyFrameParser.findKeyFrameDTSBefore(
                self._mp4_keyframe_dts_list,
                segment.playlist_start_seconds,
            )
            segment.source_file_position = None
            segment.source_start_dts = source_start_dts
            logging.debug(
                f'{self.log_prefix}[Segment {segment_sequence}] '
                f'Segment source position resolved from MP4 keyframe table. '
                f'[elapsed: {(time.perf_counter() - resolve_start_time) * 1000:.1f}ms]'
            )


    def createSegmentMapEntriesFromKeyFrames(self, key_frames: list[KeyFrame]) -> list[SegmentMapEntry]:
        """
        再生中に見つかった入力 TS キーフレームから segment_map 保存候補を作る

        Args:
            key_frames (list[KeyFrame]): 入力 TS から収集したキーフレーム一覧

        Returns:
            list[SegmentMapEntry]: まだ保存されていないセグメント開始位置キャッシュ
        """

        # 2つ目のキーフレームまで読めて初めて、先頭キーフレームを使える区間の終端が分かる
        ## 最後に見つかったキーフレームは、後続キーフレームが来るまで未来の全セグメントに誤割当される可能性があるため保存しない
        if len(key_frames) < 2 or self._ts_source_base_dts is None:
            return []

        segment_duration_ticks = round(self._segment_duration_seconds * ts.HZ)
        # bisect で二分探索するために DTS だけを昇順リストとして抜き出す
        dts_list = [key_frame['dts'] for key_frame in key_frames]
        segment_map_entries: list[SegmentMapEntry] = []

        # 全セグメントを走査し、キーフレーム一覧から対応する開始位置を割り当てる
        for segment in self._segments:
            # 既存 cache にあるシーケンスは、人間のシークや別セッションで既に検証済みの値として優先する
            if segment.sequence_index in self._segment_map_by_sequence:
                continue

            # プレイリスト上の時刻に対し、その時刻以前で最も近い入力キーフレームを採用する
            ## 最後の収集キーフレームは終端未確認なので、候補に使うのは次のキーフレームが存在する場合だけに限定する
            target_dts = self._ts_source_base_dts + round(segment.playlist_start_seconds * ts.HZ)
            key_frame_index = bisect.bisect_right(dts_list, target_dts) - 1
            if key_frame_index < 0 or key_frame_index >= len(key_frames) - 1:
                continue

            key_frame = key_frames[key_frame_index]
            # キーフレームがセグメント目標 DTS からどれだけ手前にあるかを算出する
            ## 1セグメント分以上離れている場合は、そのキーフレームは別セグメントの管轄なのでスキップする
            keyframe_age_ticks = target_dts - key_frame['dts']
            if keyframe_age_ticks < 0 or keyframe_age_ticks >= segment_duration_ticks:
                continue

            segment_map_entry = SegmentMapEntry(
                sequence_index = segment.sequence_index,
                source_file_position = key_frame['offset'],
                source_start_dts = key_frame['dts'],
            )

            # 同じ入力位置を複数セグメントへ保存すると、再シーク時に同じ範囲を何度も再エンコードする
            ## 既存値と今回候補の両方を見て重複を避け、長い GOP 区間は従来どおりオンデマンド探索へ任せる
            if (
                any(
                    saved_segment_map_entry['source_file_position'] == segment_map_entry['source_file_position'] and
                    saved_segment_map_entry['source_start_dts'] == segment_map_entry['source_start_dts']
                    for saved_segment_map_entry in self._segment_map_by_sequence.values()
                ) is True or
                any(
                    saved_segment_map_entry['source_file_position'] == segment_map_entry['source_file_position'] and
                    saved_segment_map_entry['source_start_dts'] == segment_map_entry['source_start_dts']
                    for saved_segment_map_entry in segment_map_entries
                ) is True
            ):
                continue

            segment_map_entries.append(segment_map_entry)

        return segment_map_entries


    async def saveSegmentMapEntries(self, segment_map_entries: list[SegmentMapEntry]) -> None:
        """
        オンデマンド探索や再生中解析で得た segment_map エントリを録画レコードへまとめて保存する

        Args:
            segment_map_entries (list[SegmentMapEntry]): 保存対象のセグメント開始位置キャッシュ
        """

        if len(segment_map_entries) == 0:
            return

        try:
            # セッション生成時に受け取った ORM インスタンスへ、保存後の最新 JSON を反映する
            ## 実際のマージは DB から読み直した RecordedVideo に対して行う
            recorded_video = self.recorded_program.recorded_video

            # 同じ録画への segment_map 保存は、DB からの読み直しから JSON 保存までを1本ずつ処理する
            ## 同一プロセス内の競合をここで止めることで、別視聴セッションが直前に保存したエントリを取りこぼさない
            ## WeakValueDictionary なので、ロックへの参照がなくなった録画 ID のエントリは自動的に消える
            segment_map_save_lock = self.__segment_map_save_locks.setdefault(recorded_video.id, asyncio.Lock())
            async with segment_map_save_lock:
                # 同一バッチ内で同じシーケンスが重複した場合は、先に見つけた値を採用する
                ## オンデマンド探索結果と再生中解析結果が混ざっても、既存値を不用意に置き換えない
                deduplicated_entries_by_sequence: dict[int, SegmentMapEntry] = {}
                for segment_map_entry in segment_map_entries:
                    if segment_map_entry['sequence_index'] in deduplicated_entries_by_sequence:
                        continue
                    deduplicated_entries_by_sequence[segment_map_entry['sequence_index']] = segment_map_entry

                if len(deduplicated_entries_by_sequence) == 0:
                    return

                # 別セッションのオンデマンド探索結果を上書きしないよう、保存直前に DB から最新値を読み直す
                ## SQLite では行ロックの効き方に制約があるため、プロセス内ロックと組み合わせて JSON 更新の取りこぼしを避ける
                async with transactions.in_transaction():
                    latest_recorded_video = await RecordedVideo.select_for_update().get_or_none(id=recorded_video.id)
                    if latest_recorded_video is None:
                        logging.warning(f'{self.log_prefix} RecordedVideo was not found while saving segment map entries.')
                        return

                    # DB から読み直した最新の segment_map をベースに、今回の候補をマージしていく
                    updated_segment_map = [
                        entry
                        for entry in latest_recorded_video.segment_map
                    ]
                    # 既存エントリのシーケンス番号と入力位置のセットを作り、重複判定に使う
                    existing_sequences = {
                        entry['sequence_index']
                        for entry in updated_segment_map
                    }
                    existing_positions = {
                        (entry['source_file_position'], entry['source_start_dts'])
                        for entry in updated_segment_map
                    }
                    saved_count = 0
                    for segment_map_entry in deduplicated_entries_by_sequence.values():
                        # 最新 DB に同じシーケンスがある場合は、別セッションが先に保存した値をそのまま使う
                        ## ついで解析の候補はローカルの古いスナップショットから作られるため、保存直前に読んだ DB の値を優先する
                        if segment_map_entry['sequence_index'] in existing_sequences:
                            continue

                        # 既存の別シーケンスと同じ入力位置を指す候補は保存しない
                        ## 長い GOP や局所的な解析不足で同一開始位置が複数セグメントに割り当たると、次回以降のシーク精度が落ちる
                        position_key = (
                            segment_map_entry['source_file_position'],
                            segment_map_entry['source_start_dts'],
                        )
                        if position_key in existing_positions:
                            continue
                        updated_segment_map.append(segment_map_entry)
                        existing_sequences.add(segment_map_entry['sequence_index'])
                        existing_positions.add(position_key)
                        saved_count += 1

                    if saved_count == 0:
                        # 追加保存する候補がなくても、最新 DB には別セッションが保存した値が含まれている可能性がある
                        ## このセッション側のキャッシュだけ古いままだと、同じ視聴中に不要なオンデマンド探索を繰り返してしまう
                        recorded_video.segment_map = updated_segment_map
                        self._segment_map_by_sequence = {
                            entry['sequence_index']: entry
                            for entry in updated_segment_map
                        }
                        return

                    updated_segment_map.sort(key=lambda entry: entry['sequence_index'])
                    latest_recorded_video.segment_map = updated_segment_map
                    await latest_recorded_video.save(update_fields=['segment_map'])

            # 保存済みの最新値を現在の視聴セッションにも反映し、次回の同じセグメント要求を DB なしで返す
            recorded_video.segment_map = updated_segment_map
            self._segment_map_by_sequence = {
                entry['sequence_index']: entry
                for entry in updated_segment_map
            }
            logging.info(f'{self.log_prefix} Segment map entries saved. [count: {saved_count}]')
        except Exception as ex:
            logging.warning(f'{self.log_prefix} Failed to save segment map entries:', exc_info=ex)


    async def getSegment(self, segment_sequence: int) -> bytes | None:
        """
        エンコードされた HLS セグメントを取得する
        呼び出された時点でエンコードされていない場合は既存のエンコードタスクを終了し、
        segment_sequence の HLS セグメントが含まれる範囲から新たにエンコードタスクを開始する

        Args:
            segment_sequence (int): HLS セグメントのシーケンス番号 (self.segments のインデックスと一致する)

        Returns:
            bytes | None: HLS セグメントとしてエンコードされた MPEG-TS ストリーム (シーケンス番号が不正な場合は None)
        """

        # セッションのアクティブ状態を維持する
        self.keepAlive()

        # セグメントのシーケンス番号が不正な場合は None を返す
        if segment_sequence < 0 or segment_sequence >= len(self._segments):
            return None

        # シーケンス番号に対応する HLS セグメントを取得する
        segment = self._segments[segment_sequence]

        # 当該セグメントのエンコードがまだ完了していない場合は、エンコードタスクを非同期で開始する
        if segment.encode_status == 'Pending':
            async with self._video_encoding_task_lock:
                # ロック待ちの間に他のリクエストがすでにエンコードを開始している可能性があるため再確認する
                if segment.encode_status == 'Pending':
                    # シークでは旧エンコーダーが同じ録画ファイルを読み続けていると、未キャッシュ区間の探索と I/O が競合する
                    ## そのため source position 解決より前に旧タスクへキャンセルを投げ、探索が録画ファイルを読みやすい状態へ寄せる
                    if self._video_encoding_task_ref is not None:
                        await self.__cancelVideoEncodingTask(should_wait_for_runner = False)
                        logging.info(
                            f'{self.log_prefix}[Segment {segment_sequence}] '
                            f'Previous Encoding Task Canceled before source position resolution.'
                        )

                    # このセグメントからエンコーダーを起動するため、入力ソース上の開始位置を先に確定する
                    await self.resolveSegmentSourcePosition(segment_sequence)
                    encoding_start_sequence = segment_sequence

                    # QSVEncC では MPEG-TS の入力 DTS が 33bit ラップ直前にある状態で起動すると、
                    ## `check_pts()` が後続フレームの時刻を逆行扱いして小刻みな PTS 補正を入れてしまい、結果盛大に音ズレする既知の問題がある
                    ## 同一ファイルでも FFmpeg / NVEncC では正常な間隔でエンコードできているため、QSVEncC のみ少し手前から連続エンコードする
                    ## 映像ストリーム構成が途中で変わる録画は VideoEncodingTask 側で FFmpeg に固定されるため、この QSVEncC 専用の回避策は適用不要
                    if (
                        Config().general.encoder == 'QSVEncC' and
                        self.recorded_program.recorded_video.container_format == 'MPEG-TS' and
                        self.recorded_program.recorded_video.has_video_stream_changes is False
                    ):
                        wrap_avoidance_ticks = self.DTS_WRAP_AVOIDANCE_SECONDS * ts.HZ
                        backtrack_iterations = 0
                        while encoding_start_sequence > 0:
                            backtrack_iterations += 1
                            if backtrack_iterations > self.DTS_WRAP_AVOIDANCE_MAX_BACKTRACK_SEGMENTS:
                                logging.warning(
                                    f'{self.log_prefix}[Segment {segment_sequence}] '
                                    f'QSVEncC DTS wrap avoidance reached the backtrack limit. '
                                    f'[encoding_start_sequence: {encoding_start_sequence}]'
                                )
                                break
                            encoding_start_segment = self._segments[encoding_start_sequence]
                            if encoding_start_segment.source_start_dts is None:
                                await self.resolveSegmentSourcePosition(encoding_start_sequence)
                                encoding_start_segment = self._segments[encoding_start_sequence]
                            assert encoding_start_segment.source_start_dts is not None
                            distance_to_wrap = ts.PCR_CYCLE - (encoding_start_segment.source_start_dts % ts.PCR_CYCLE)
                            if distance_to_wrap > wrap_avoidance_ticks:
                                break
                            encoding_start_sequence -= 1

                        if encoding_start_sequence != segment_sequence:
                            logging.info(
                                f'{self.log_prefix}[Segment {segment_sequence}] '
                                f'QSVEncC start adjusted to Segment {encoding_start_sequence} to avoid DTS wrap.',
                            )

                    # 新しいエンコードタスクのインスタンスを初期化
                    ## エンコードタスクは基本使い回せないので、再度新しく初期化する
                    self._video_encoding_task = VideoEncodingTask(self)

                    # 新しいエンコードタスクを開始
                    self._video_encoding_task_ref = asyncio.create_task(self._video_encoding_task.run(encoding_start_sequence))
                    self.__registerVideoEncodingTaskRef(self._video_encoding_task_ref)
                    logging.info(f'{self.log_prefix}[Segment {encoding_start_sequence}] New Encoding Task Started.')

        # セグメントデータの Future が完了したらそのデータを返す
        encoded_segment_ts = await asyncio.shield(segment.encoded_segment_ts_future)
        segment.is_encoded_segment_ts_future_readed = True

        # 読み取り済みのセグメントが MAX_READED_SEGMENTS 個以上ある場合、一番古いセグメントのデータを初期化する
        readed_segments = [s for s in self._segments if s.is_encoded_segment_ts_future_readed]
        if len(readed_segments) >= self.MAX_READED_SEGMENTS:
            # 一番古いセグメントを取得し、状態をリセットする
            oldest_segment = readed_segments[0]
            await oldest_segment.resetState()
            logging.info(f'{self.log_prefix}[Segment {oldest_segment.sequence_index}] Reset segment data to free memory.')

        return encoded_segment_ts


    async def __cancelVideoEncodingTask(
        self,
        should_wait_for_runner: bool = True,
        timeout_seconds: float = 0.5,
    ) -> None:
        """
        現在のエンコードタスクをキャンセルし、必要に応じて短時間だけ終了を待機する

        Args:
            should_wait_for_runner (bool): エンコードタスク本体の終了を待機するかどうか
            timeout_seconds (float): エンコードタスクの終了を待機する最大時間 (秒)
        """

        # 現在実行中のエンコードタスクをキャンセルする
        self._video_encoding_task.cancel()

        # この時点で既にエンコードタスクが実行中でない場合は何もしない
        if self._video_encoding_task_ref is None:
            return

        # 待機対象をローカル変数に退避しておく
        ## cancelEncodingTask() 完了後に新しいタスクへ差し替えられても、旧タスクの参照を見失わないようにする
        encoding_task_runner = self._video_encoding_task_ref

        # 録画再生の critical path では旧タスクの完全終了を待たず、
        ## 強参照だけ detached set に移して自然終了に任せる
        if should_wait_for_runner is False:
            self.__detachVideoEncodingTaskRef(encoding_task_runner)
            if self._video_encoding_task_ref == encoding_task_runner:
                self._video_encoding_task_ref = None
            return

        # エンコードタスクの終了を待機する
        try:
            await asyncio.wait_for(asyncio.shield(encoding_task_runner), timeout=timeout_seconds)
        except TimeoutError:
            # タイムアウト後も旧タスクは自然終了を続ける可能性があるため、
            # 新しいタスクを起動する前に強参照を別管理へ移し、完了時に解放する
            self.__detachVideoEncodingTaskRef(encoding_task_runner)
            if self._video_encoding_task_ref == encoding_task_runner:
                self._video_encoding_task_ref = None
            logging.warning(f'{self.log_prefix} Encoding task shutdown timed out. Proceeding with restart.')
        except Exception as ex:
            # 予期しない例外で終了待機に失敗した場合も、旧タスクの参照を見失うと dangling-task が再発する
            self.__detachVideoEncodingTaskRef(encoding_task_runner)
            if self._video_encoding_task_ref == encoding_task_runner:
                self._video_encoding_task_ref = None
            logging.error(f'{self.log_prefix} Error while waiting for encoding task shutdown:', exc_info=ex)
        finally:
            if encoding_task_runner.done() and self._video_encoding_task_ref == encoding_task_runner:
                self._video_encoding_task_ref = None


    async def destroy(self) -> None:
        """
        録画視聴セッションで実行中のエンコードなどの処理を終了し、録画視聴セッションを破棄する
        ユーザーが番組の視聴を終了した (keepAlive() が呼び出されなくなった) 場合に自動的に呼び出される
        """

        # 起動中のエンコードタスクがあればキャンセルする
        # この時点ですでにエンコードを完了して終了している場合もある
        async with self._video_encoding_task_lock:
            await self.__cancelVideoEncodingTask()

        # すべての HLS セグメントを削除する
        self._segments = []

        # アクティブな間保持されていたインスタンスを削除する
        ## これにより、このインスタンスには誰も参照できなくなるため、ガベージコレクションによりメモリから解放される (はず)
        ## 今後同じセッション ID が指定された場合は新たに別のインスタンスが生成される
        self.__instances.pop(self.session_id)

        logging.info(f'{self.log_prefix} Streaming Session Finished.')
