# ruff: noqa: RUF006 <= 将来改修予定

# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import asyncio
import math
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar, Literal

from biim.mpeg2ts import ts
from fastapi import HTTPException, status

from app import logging
from app.constants import QUALITY_TYPES
from app.models.RecordedProgram import RecordedProgram
from app.streams.VideoEncodingTask import VideoEncodingTask
from app.utils import SetTimeout


@dataclass
class VideoStreamSegment:
    """
    ビデオストリームの HLS セグメントを表すデータクラス
    """

    # HLS セグメントのシーケンス番号
    ## リストのインデックスと一致する (0 から始まるので注意)
    sequence_index: int
    # HLS セグメントの切り出しを開始するファイルの位置 (バイト)
    start_file_position: int
    # HLS セグメントの開始タイムスタンプ (90kHz)
    start_dts: int
    # HLS セグメント長 (秒単位)
    ## 無変換の TS では通常 SEGMENT_DURATION_SECONDS と一致するが、キーフレーム単位で切り出すため録画データによってはさらに長くなる
    ## tsreplace で H.264 / H.265 化した TS で顕著で、例えば GOP 長が4秒の録画データなら、実際のセグメント長は6秒を超えて8秒になる
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
        asyncio.Future を初期化するにはイベントループ上でなければならないらしいので、このメソッドを非同期関数にしている
        """
        if not self.encoded_segment_ts_future.done():
            self.encoded_segment_ts_future.set_result(b'')  # 前の Future がまだ完了していない場合は空のデータで完了させる
        self.encode_status = 'Pending'
        self.encoded_segment_ts_future = asyncio.Future()  # asyncio.Future を再初期化
        self.is_encoded_segment_ts_future_readed = False


class VideoStream:
    """ 録画視聴セッションを管理するクラス """

    # 録画視聴セッションが再生されていない場合にタイムアウトするまでの時間 (秒)
    # この時間が経過すると、録画視聴セッションのインスタンスは自動的に破棄される
    SESSION_TIMEOUT: ClassVar[float] = float(10)  # 10 秒

    # 一度でも読み取られた HLS セグメントの最大保持数
    MAX_READED_SEGMENTS: ClassVar[int] = 10

    # エンコードする HLS セグメントの最低長さ (秒)
    SEGMENT_DURATION_SECONDS: ClassVar[float] = float(6)  # 6秒

    # 録画視聴セッションのインスタンスが入る、セッション ID をキーとした辞書
    # この辞書に録画視聴セッションに関する全てのデータが格納されている
    __instances: ClassVar[dict[str, VideoStream]] = {}


    # 必ずセッション ID ごとに1つのインスタンスになるように (Singleton)
    def __new__(cls, session_id: str, recorded_program: RecordedProgram, quality: QUALITY_TYPES) -> VideoStream:

        # まだ同じセッション ID のインスタンスがないときだけ、インスタンスを生成する
        if session_id not in cls.__instances:

            # 新しい録画視聴セッションのインスタンスを生成する
            instance = super().__new__(cls)

            # セッション ID を設定
            instance.session_id = session_id

            # 録画番組の情報と映像の品質を設定
            instance.recorded_program = recorded_program
            instance.quality = quality

            # 基準となる DTS (最初のキーフレームの DTS)
            instance._base_dts = 0

            # HLS セグメントを格納するリスト
            instance._segments = []

            # 現在実行中のエンコードタスク
            instance._encoding_task = VideoEncodingTask(instance)

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
                logging.error(f'{instance.log_prefix} Session exists but program_id or quality mismatch. [program_id: {recorded_program.id}, quality: {quality}]')
                raise HTTPException(
                    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail = 'Session exists but program_id or quality mismatch',
                )

        # 登録されているインスタンスを返す
        return cls.__instances[session_id]


    def __init__(self, session_id: str, recorded_program: RecordedProgram, quality: QUALITY_TYPES) -> None:
        """
        録画視聴セッションのインスタンスを取得する

        Args:
            session_id (str): セッション ID
            recorded_program (RecordedProgram): 録画番組の情報
            quality (QUALITY_TYPES): 映像の品質 (1080p-60fps ~ 240p)
        """

        # インスタンス変数の型ヒントを定義
        # Singleton のためインスタンスの生成は __new__() で行うが、__init__() も定義しておかないと補完がうまく効かない
        self.session_id: str
        self.recorded_program: RecordedProgram
        self.quality: QUALITY_TYPES
        self._base_dts: int
        self._segments: list[VideoStreamSegment]
        self._encoding_task: VideoEncodingTask
        self._cancel_destroy_timer: Callable[[], None]


    @property
    def log_prefix(self) -> str:
        """
        ログのプレフィックス
        """
        return f'[Video: {self.recorded_program.id}/{self.session_id}/{self.quality}]'


    @property
    def segments(self) -> tuple[VideoStreamSegment, ...]:
        """
        HLS セグメントを格納するリスト (読み取り専用)
        一旦録画データの長さすべての VideoStreamSegment を作成したあと、必要に応じてエンコードしていく
        基本一度 VideoStream 内部でセットされたら外部から変更されるべきではないので、読み取り専用にしている
        """
        return tuple(self._segments)


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
            buffer_start = (first_segment.start_dts - self._base_dts) / ts.HZ
            buffer_end = (last_segment.start_dts - self._base_dts) / ts.HZ + last_segment.duration_seconds
            return (buffer_start, buffer_end)
        else:
            # エンコード済みのセグメントがない場合は (0, 0) を返す
            return (0, 0)


    async def getVirtualPlaylist(self, cache_key: str | None = None) -> str:
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

        # まだ HLS セグメントリストが空なら、キーフレーム情報から VideoStreamSegment を作成する
        if len(self._segments) == 0:
            # キーフレーム情報が存在しない場合は500エラー
            if not self.recorded_program.recorded_video.has_key_frames:
                logging.error(f'{self.log_prefix} Keyframe information is not available.')
                raise HTTPException(
                    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail = 'Keyframe information is not available',
                )

            # キーフレーム情報を取得
            key_frames = self.recorded_program.recorded_video.key_frames
            if len(key_frames) < 2:  # 最低2つのキーフレームが必要
                logging.error(f'{self.log_prefix} Not enough keyframes.')
                raise HTTPException(
                    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail = 'Not enough keyframes',
                )

            # 最初のキーフレームの DTS を基準として保存する
            self._base_dts = key_frames[0]['dts']

            # キーフレーム間隔の最大値を計算する
            max_key_frame_interval = 0.0
            for i in range(1, len(key_frames)):
                current_frame = key_frames[i - 1]
                next_frame = key_frames[i]
                interval = (next_frame['dts'] - current_frame['dts']) / ts.HZ
                max_key_frame_interval = max(max_key_frame_interval, interval)

            segment_sequence = 0
            accumulated_duration: float = 0.0
            # セグメントの開始フレーム（フレーム情報全体を保持）
            segment_start_frame = key_frames[0]

            # キーフレーム情報を先頭から順に処理し、各間隔を累積していく
            for i in range(1, len(key_frames)):
                current_frame = key_frames[i - 1]
                next_frame = key_frames[i]
                # 各キーフレーム間の時間差を算出
                duration = (next_frame['dts'] - current_frame['dts']) / ts.HZ
                accumulated_duration += duration

                # キーフレーム間隔が SEGMENT_DURATION_SECONDS 以上になったら、新しいセグメントに切り替える
                if accumulated_duration >= self.SEGMENT_DURATION_SECONDS:
                    self._segments.append(VideoStreamSegment(
                        sequence_index = segment_sequence,
                        start_file_position = segment_start_frame['offset'],
                        start_dts = segment_start_frame['dts'],
                        duration_seconds = accumulated_duration,
                        encode_status = 'Pending',
                        encoded_segment_ts_future = asyncio.Future(),
                    ))
                    segment_sequence += 1
                    # 次のセグメントの開始フレームとして、現在の next_frame を設定
                    segment_start_frame = next_frame
                    accumulated_duration = 0.0

            # ループ後に、残りの時間がある場合は最後のセグメントとして追加
            if accumulated_duration > 0:
                self._segments.append(VideoStreamSegment(
                    sequence_index = segment_sequence,
                    start_file_position = segment_start_frame['offset'],
                    start_dts = segment_start_frame['dts'],
                    duration_seconds = accumulated_duration,
                    encode_status = 'Pending',
                    encoded_segment_ts_future = asyncio.Future(),
                ))

            # HLS セグメント長の最小値・最大値・平均値をロギング
            # 最後のセグメントの長さは通常 SEGMENT_DURATION_SECONDS と一致しないので統計から除外している
            if len(self._segments) > 0:
                min_duration = min(segment.duration_seconds for segment in self._segments[:-1])
                max_duration = max(segment.duration_seconds for segment in self._segments[:-1])
                avg_duration = sum(segment.duration_seconds for segment in self._segments[:-1]) / (len(self._segments) - 1)
                logging.info(
                    f'{self.log_prefix} Total {len(self._segments)} segments (min: {min_duration:.2f}s, max: {max_duration:.2f}s, avg: {avg_duration:.2f}s)'
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
            # 既存のエンコードタスクをキャンセル
            await self._encoding_task.cancel()
            logging.info(f'{self.log_prefix}[Segment {segment_sequence}] Previous Encoding Task Canceled.')

            # 新しいエンコードタスクのインスタンスを初期化
            ## エンコードタスクは基本使い回せないので、再度新しく初期化する
            self._encoding_task = VideoEncodingTask(self)

            # 新しいエンコードタスクを開始
            asyncio.create_task(self._encoding_task.run(segment_sequence))
            logging.info(f'{self.log_prefix}[Segment {segment_sequence}] New Encoding Task Started.')

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


    async def destroy(self) -> None:
        """
        録画視聴セッションで実行中のエンコードなどの処理を終了し、録画視聴セッションを破棄する
        ユーザーが番組の視聴を終了した (keepAlive() が呼び出されなくなった) 場合に自動的に呼び出される
        """

        # 起動中のエンコードタスクがあればキャンセルする
        # この時点ですでにエンコードを完了して終了している場合もある
        await self._encoding_task.cancel()

        # すべての HLS セグメントを削除する
        self._segments = []

        # アクティブな間保持されていたインスタンスを削除する
        ## これにより、このインスタンスには誰も参照できなくなるため、ガベージコレクションによりメモリから解放される (はず)
        ## 今後同じセッション ID が指定された場合は新たに別のインスタンスが生成される
        self.__instances.pop(self.session_id)

        logging.info(f'{self.log_prefix} Streaming Session Finished.')
