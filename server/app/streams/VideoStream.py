
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from rich import print
from typing import Callable, ClassVar

from app.constants import LIBRARY_PATH, QUALITY_TYPES
from app.models.RecordedProgram import RecordedProgram
from app.streams.VideoEncodingTask import VideoEncodingTask
from app.utils import Logging
from app.utils import SetTimeout


@dataclass
class VideoStreamSegment:
    """
    ビデオストリームの HLS セグメントを表すデータクラス
    当初 Pydantic モデルにしていたが、Pydantic モデルは非プリミティブ値を含められないようなので dataclass に変更した
    """

    # HLS セグメントの開始タイムスタンプ (PTS)
    # この PTS を元に HLS セグメントが録画データから切り出される
    start_offset_timestamp: float

    # HLS セグメント長 (秒)
    # 基本 SEGMENT_DURATION_SECOND に近い値になるが、キーフレーム単位で切り出すために少し長くなる
    duration: float

    # HLS セグメントのエンコード済み MPEG-TS データが返る asyncio.Future
    segment_ts_future: asyncio.Future[bytes]

    # 現在 HLS セグメントをエンコード中かどうか
    # エンコード中であれば True、エンコードが完了していれば False
    is_encode_processing: bool = False


class VideoStream:
    """ ビデオストリームを管理するクラス """

    # ビデオストリームの操作がなかった場合にタイムアウトするまでの時間 (秒)
    # この時間が経過すると、ビデオストリームのインスタンスは自動的に破棄される
    VIDEO_STREAM_TIMEOUT: ClassVar[float] = float(30)

    # ビデオストリームのインスタンスが入る、ビデオストリーム ID をキーとした辞書
    # この辞書にビデオストリームに関する全てのデータが格納されている
    __instances: ClassVar[dict[str, VideoStream]] = {}


    # 必ずビデオストリーム ID ごとに1つのインスタンスになるように (Singleton)
    def __new__(cls, recorded_program: RecordedProgram, quality: QUALITY_TYPES) -> VideoStream:

        # まだ同じビデオストリーム ID のインスタンスがないときだけ、インスタンスを生成する
        # (録画番組ID (5桁埋め))-(映像の品質) で一意な ID になる
        video_stream_id: str = f'{recorded_program.id:05}-{quality}'
        if video_stream_id not in cls.__instances:

            # 新しいビデオストリームのインスタンスを生成する
            instance = super(VideoStream, cls).__new__(cls)

            # ビデオストリーム ID を設定
            instance.video_stream_id = video_stream_id

            # 録画番組の情報と映像の品質を設定
            instance.recorded_program = recorded_program
            instance.quality = quality

            # セグメントの URL のキャッシュ避けとして使うインスタンス生成時刻のハッシュ
            instance.time_hash = int(time.time())

            # HLS セグメントを格納するリスト
            instance.segments = []

            # 現在実行中のエンコードタスク
            instance._encoding_task = None

            # キャンセルされない限り VIDEO_STREAM_TIMEOUT 秒後にインスタンスを破棄するタイマー
            # cancel_destroy_timer() を呼び出すことでタイマーをキャンセルできる
            instance._cancel_destroy_timer = SetTimeout(lambda: instance.destroy(), cls.VIDEO_STREAM_TIMEOUT)

            # 生成したインスタンスを登録する
            cls.__instances[video_stream_id] = instance

            Logging.info(f'[Video: {instance.video_stream_id}] Streaming Session Started.')

        # 登録されているインスタンスを返す
        return cls.__instances[video_stream_id]


    def __init__(self, recorded_program: RecordedProgram, quality: QUALITY_TYPES) -> None:
        """
        ビデオストリームのインスタンスを取得する

        Args:
            recorded_program (RecordedProgram): 録画番組の情報
            quality (QUALITY_TYPES): 映像の品質 (1080p-60fps ~ 240p)
        """

        # インスタンス変数の型ヒントを定義
        # Singleton のためインスタンスの生成は __new__() で行うが、__init__() も定義しておかないと補完がうまく効かない
        self.video_stream_id: str
        self.recorded_program: RecordedProgram
        self.quality: QUALITY_TYPES
        self.time_hash: int

        # HLS セグメントを格納するリスト
        ## 一旦録画データの長さすべての VideoStreamSegment を作成したあと、必要に応じてエンコードしていく
        ## VideoStream と VideoEncodingTask 以外から直接アクセスしてはならない
        self.segments: list[VideoStreamSegment]

        # 現在実行中のエンコードタスク
        self._encoding_task: VideoEncodingTask | None

        # キャンセルされない限り VIDEO_STREAM_TIMEOUT 秒後にインスタンスを破棄するタイマー
        self._cancel_destroy_timer: Callable[[], None]


    def keepAlive(self) -> None:
        """
        ビデオストリームのアクティブ状態を維持する
        番組の視聴中は定期的にこのメソッドを呼び出す必要があり、呼び出されなくなった場合は自動的に終了処理が行われる
        """

        # 前回のタイマーをキャンセルする
        self._cancel_destroy_timer()

        # キャンセルされない限り VIDEO_STREAM_TIMEOUT 秒後にインスタンスを破棄するタイマーを設定する
        self._cancel_destroy_timer = SetTimeout(lambda: self.destroy(), self.VIDEO_STREAM_TIMEOUT)


    async def getVirtualPlaylist(self) -> str:
        """
        仮想 HLS M3U8 プレイリストを取得する
        返却時点では仮想 HLS M3U8 プレイリストに記載されているセグメントのデータは存在せず (「仮想」のゆえん)、随時エンコードされる

        Returns:
            str: 仮想 HLS M3U8 プレイリスト
        """

        # ビデオストリームのアクティブ状態を維持する
        self.keepAlive()

        # まだ HLS セグメントリストから空なら、キーフレームパケットの PTS (秒換算) のリストを取得した上ですべてのセグメント分作成する
        # この時点では入れ物を作るだけで、実際にエンコードされるわけではない
        ## TODO: この値はキャッシュされるべき
        if len(self.segments) == 0:

            # ffprobe で映像パケットの PTS (秒換算) のリストを取得する
            ## ffprobe で取得できる PTS は小数点6桁までの精度なので、それに合わせる
            ffprobe_options = ['-show_frames', '-select_streams', 'v:0', '-of', 'json']
            ffprobe_result = await asyncio.subprocess.create_subprocess_exec(
                *[LIBRARY_PATH['FFprobe'], *ffprobe_options, self.recorded_program.recorded_video.file_path],
                stdout = asyncio.subprocess.PIPE,
                stderr = asyncio.subprocess.DEVNULL,  # ログは使用しない
            )

            # 映像の最初のキーフレームの PTS (秒換算) を取得
            assert ffprobe_result.stdout is not None
            frames = json.loads((await ffprobe_result.stdout.read()).decode('utf-8'))
            first_pts: float = 0
            for frame in frames['frames']:
                if int(frame['key_frame']) == 1:
                    first_pts = float(frame['pts_time'])
                    break

            # 映像の最後のフレーム (キーフレームかどうかは問わない) の PTS (秒換算) を取得
            last_pts = float(frames['frames'][-1]['pts_time'])

            # キーフレームのタイムスタンプを抽出
            # 最初の PTS (秒換算) を引いて、動画の先頭を 0 秒した場合の相対値 (秒) にする
            keyframe_timestamps = [
                # 小数点6桁までに丸める
                round(float(frame['pts_time']) - first_pts, 6)
                for frame in frames['frames'] if int(frame['key_frame']) == 1
            ]
            print('keyframe_timestamps: ', end = '')
            print(keyframe_timestamps)

            # 映像の最後のフレームのタイムスタンプを取得
            # 同じく最初の PTS (秒換算) を引いて、動画の先頭を 0 秒した場合の相対値 (秒) にする
            last_timestamp = round(last_pts - first_pts, 6)
            print(f"last_timestamp: {last_timestamp}")

            # VideoStreamSegment を作成する
            ## セグメントは SEGMENT_DURATION_SECOND 秒ごとに作成するが、キーフレームがピッタリ合うことはまずないので、
            # SEGMENT_DURATION_SECOND 秒を超えた時点で一番近いキーフレームのタイムスタンプを探してセグメントを作成する
            ## 先頭のセグメント
            self.segments.append(VideoStreamSegment(
                start_offset_timestamp = 0,
                duration = 0,  # 仮の値
                segment_ts_future = asyncio.Future(),  # dataclass 側に書くと全ての参照が同じになってしまうので毎回新たに生成する
            ))
            ## キーフレーム自体放送波の場合 0.2 秒など基本高頻度で送出されているので、ちょうどいいタイミングで区切る
            for keyframe_timestamp in keyframe_timestamps:
                # 前のセグメントの開始タイムスタンプから SEGMENT_DURATION_SECOND 秒以上離れている場合のみ新たにセグメントを作成する
                # セグメント長はおそらく 10.203350 秒とかになるはず
                if keyframe_timestamp - self.segments[-1].start_offset_timestamp >= VideoEncodingTask.SEGMENT_DURATION_SECOND:
                    # 前のセグメントの長さを確定する
                    # 小数点6桁までに丸める
                    self.segments[-1].duration = round(keyframe_timestamp - self.segments[-1].start_offset_timestamp, 6)
                    # セグメントを作成する
                    self.segments.append(VideoStreamSegment(
                        start_offset_timestamp = keyframe_timestamp,
                        duration = 0,  # 仮の値
                        segment_ts_future = asyncio.Future(),  # dataclass 側に書くと全ての参照が同じになってしまうので毎回新たに生成する
                    ))
            ## 最後のセグメントの長さを確定する
            self.segments[-1].duration = round(last_timestamp - self.segments[-1].start_offset_timestamp, 6)

        # 仮想 HLS M3U8 プレイリストを生成
        virtual_playlist = ''
        virtual_playlist += f'#EXTM3U\n'
        virtual_playlist += f'#EXT-X-VERSION:6\n'
        virtual_playlist += f'#EXT-X-PLAYLIST-TYPE:VOD\n'

        # HLS セグメントの実時間の最大値を指定する (SEGMENT_DURATION_SECOND + 2 秒程度の余裕を持たせる)
        virtual_playlist += f'#EXT-X-TARGETDURATION:{int(VideoEncodingTask.SEGMENT_DURATION_SECOND + 2)}\n'

        # 事前に算出したセグメントをすべて記述する
        for index, segment in enumerate(self.segments):
            virtual_playlist += f'#EXTINF:{segment.duration},\n'
            virtual_playlist += f'segment?sequence={index}&_={self.time_hash}\n'  # キャッシュ避けのためにタイムスタンプを付与する

        virtual_playlist += f'#EXT-X-ENDLIST\n'
        print('virtual_playlist: ', end = '')
        print(virtual_playlist)
        return virtual_playlist


    async def getSegment(self, segment_sequence: int) -> bytes | None:
        """
        エンコードされた HLS セグメントを取得する
        呼び出された時点でエンコードされていない場合は既存のエンコードタスクを終了し、
        segment_index の HLS セグメントが含まれる範囲から新たにエンコードタスクを開始する

        Args:
            segment_sequence (int): HLS セグメントのシーケンス番号 (self.segments のインデックスと一致する)

        Returns:
            bytes | None: HLS セグメントとしてエンコードされた MPEG-TS ストリーム (シーケンス番号が不正な場合は None)
        """

        # ビデオストリームのアクティブ状態を維持する
        self.keepAlive()

        # セグメントのシーケンス番号が不正な場合は None を返す
        if segment_sequence < 0 or segment_sequence >= len(self.segments):
            return None

        # シーケンス番号に対応する HLS セグメントを取得する
        segment = self.segments[segment_sequence]

        # まだエンコードタスクが一度も実行されていない場合は、このセグメントからエンコードタスクを非同期で開始する
        if self._encoding_task is None:
            self._encoding_task = VideoEncodingTask(self)
            asyncio.create_task(self._encoding_task.run(segment_sequence))
            Logging.info(f'[Video: {self.video_stream_id}][Segment {segment_sequence}] New Encoding Task Started.')

        # エンコードタスクは既に起動しているがこの時点でまだセグメントのエンコードが完了していなければ、このセグメントからエンコードタスクを非同期で開始する
        # この HLS セグメントのエンコード処理が現在進行中の場合は完了まで待つ
        elif segment.segment_ts_future.done() is False and segment.is_encode_processing is False:

            # 0.5 秒待ってみて、それでも同じ状態のときだけエンコードタスクを再起動する
            # タイミングの関係であともう少しだけ待てば当該セグメントのエンコードが開始するのに…！という場合に備える
            await asyncio.sleep(0.5)
            if segment.segment_ts_future.done() is False and segment.is_encode_processing is False:

                # 以前のエンコードタスクをキャンセルする
                # この時点で以前のエンコードタスクでエンコードが完了していたセグメントに関してはそのまま self.segments に格納されている
                self._encoding_task.cancel()
                Logging.info(f'[Video: {self.video_stream_id}][Segment {segment_sequence}] Previous Encoding Task Canceled.')

                # 新たにエンコードタスクを非同期で開始する
                self._encoding_task = VideoEncodingTask(self)
                asyncio.create_task(self._encoding_task.run(segment_sequence))
                Logging.info(f'[Video: {self.video_stream_id}][Segment {segment_sequence}] New Encoding Task Started.')

        # セグメントデータの Future が完了したらそのデータを返す
        segment_ts = await asyncio.shield(segment.segment_ts_future)
        return segment_ts


    def destroy(self) -> None:
        """
        ビデオストリームで実行中のエンコードなどの処理を終了し、ビデオストリームを破棄する
        ユーザーが番組の視聴を終了した (keepAlive() が呼び出されなくなった) 場合に自動的に呼び出される
        """

        # 起動中のエンコードタスクがあればキャンセルする
        # この時点ですでにエンコードを完了して終了している場合もある
        if self._encoding_task is not None:
            self._encoding_task.cancel()
            self._encoding_task = None

        # すべての HLS セグメントを削除する
        self.segments = []

        # アクティブな間保持されていたインスタンスを削除する
        ## これにより、このインスタンスには誰も参照できなくなるため、ガベージコレクションによりメモリから解放される (はず)
        ## 今後同じビデオストリーム ID が指定された場合は新たに別のインスタンスが生成される
        self.__instances.pop(self.video_stream_id)

        Logging.info(f'[Video: {self.video_stream_id}] Streaming Session Finished.')
