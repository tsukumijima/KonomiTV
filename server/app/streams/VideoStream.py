
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import asyncio
import json
import queue
import time
from biim.mpeg2ts import ts
from dataclasses import dataclass
from rich import print
from typing import Any, Callable, ClassVar, Literal

from app.config import Config
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
    TODO: 普通のクラスにしてカプセル化を図るべきかもしれない
    """

    # HLS セグメントのシーケンス番号
    ## リストのインデックスと一致する (0 から始まるので注意)
    sequence_index: int

    # HLS セグメントの切り出しを開始する映像パケットの PTS (秒ではないので注意)
    ## この PTS を元に HLS セグメントが録画データから切り出される
    ## DTS だと必ずしも表示順にならず本来切り出すべきパケットをロストしてしまうことがあるため、PTS を使用する
    start_pts: int

    # HLS セグメントの切り出しを開始する映像パケットがあるファイルの位置 (バイト)
    start_file_position: int

    # HLS セグメントの切り出しを終了する映像パケットの PTS (秒ではないので注意)
    ## この PTS を元に HLS セグメントが録画データから切り出される
    ## DTS だと必ずしも表示順にならず本来切り出すべきパケットをロストしてしまうことがあるため、PTS を使用する
    end_pts: int

    # HLS セグメントの切り出しを終了する映像パケットがあるファイルの位置 (バイト)
    end_file_position: int

    # HLS セグメント長 (秒単位)
    ## 基本 SEGMENT_DURATION_SECONDS に近い値になるが、キーフレーム単位で切り出すために少し長くなる
    duration_seconds: float

    # 上記の情報に基づいて切り出された HLS セグメントの MPEG-TS データを入れる Queue (エンコーダーが同期関数なので同期用の Queue にしている)
    ## 切り出す際に随時入れられた後、同時に稼働中のエンコーダーに投入するために取り出される
    ## None が入れられたらこれ以上データは入らないことを示す
    ## TS パケットは最大 10000 個までに制限されている (188 * 10000 = 1880000 バイト = 1.88 MB)
    ## Queue に TS パケットが溜まりすぎてもエンコーダーが追いつかないので、256 個以上溜まったら一旦読み取りを中断してエンコーダーに投入されるようにする
    segment_ts_packet_queue: queue.Queue[bytes | None]

    # HLS セグメントのエンコード済み MPEG-TS データが返る asyncio.Future
    encoded_segment_ts_future: asyncio.Future[bytes]

    # このセグメントの TS 切り出しなどの一連の処理が開始されたかどうか
    ## 一度 True になるとリセットされない限り False には戻らない
    is_started: bool = False

    # HLS セグメントのエンコードの状態
    encode_status: Literal['Pending', 'Encoding', 'Completed'] = 'Pending'


    async def resetState(self) -> None:
        """
        このセグメントの状態をリセットする
        主にエンコード中にエンコードタスクがキャンセルされたか、セグメントのエンコードが失敗した場合に呼び出される
        asyncio.Future を初期化するにはイベントループ上でなければならないらしいので、このメソッドを非同期関数にしている
        """

        self.segment_ts_packet_queue = queue.Queue(maxsize=188 * 10000)
        self.encoded_segment_ts_future = asyncio.Future()
        self.is_started = False
        self.encode_status = 'Pending'


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
            instance._time_hash = int(time.time())

            # HLS セグメントを格納するリスト
            instance._segments = []

            # 現在実行中のエンコードタスク
            instance._encoding_task = None

            # キャンセルされない限り VIDEO_STREAM_TIMEOUT 秒後にインスタンスを破棄するタイマー
            # cancel_destroy_timer() を呼び出すことでタイマーをキャンセルできる
            instance._cancel_destroy_timer = SetTimeout(lambda: asyncio.create_task(instance.destroy()), cls.VIDEO_STREAM_TIMEOUT)

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

        # セグメントの URL のキャッシュ避けとして使うインスタンス生成時刻のハッシュ
        self._time_hash: int

        # HLS セグメントを格納するリスト
        ## 一旦録画データの長さすべての VideoStreamSegment を作成したあと、必要に応じてエンコードしていく
        self._segments: list[VideoStreamSegment]

        # 現在実行中のエンコードタスク
        self._encoding_task: VideoEncodingTask | None

        # キャンセルされない限り VIDEO_STREAM_TIMEOUT 秒後にインスタンスを破棄するタイマー
        self._cancel_destroy_timer: Callable[[], None]


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
        ビデオストリームのアクティブ状態を維持する
        番組の視聴中は定期的にこのメソッドを呼び出す必要があり、呼び出されなくなった場合は自動的に終了処理が行われる
        """

        # 前回のタイマーをキャンセルする
        self._cancel_destroy_timer()

        # キャンセルされない限り VIDEO_STREAM_TIMEOUT 秒後にインスタンスを破棄するタイマーを設定する
        self._cancel_destroy_timer = SetTimeout(lambda: asyncio.create_task(self.destroy()), self.VIDEO_STREAM_TIMEOUT)


    async def getVirtualPlaylist(self) -> str:
        """
        仮想 HLS M3U8 プレイリストを取得する
        返却時点では仮想 HLS M3U8 プレイリストに記載されているセグメントのデータは存在せず (「仮想」のゆえん)、随時エンコードされる

        Returns:
            str: 仮想 HLS M3U8 プレイリスト
        """

        # ビデオストリームのアクティブ状態を維持する
        self.keepAlive()

        # まだ HLS セグメントリストから空なら、ffprobe で映像パケットの情報を取得した上でセグメントの切り出し位置などを算出する
        # この時点では入れ物を作るだけで、実際にエンコードされるわけではない
        ## TODO: この値はキャッシュされるべき
        ## TODO: キーフレームの収集中にもう一回プレイリストが叩かれるとバグる (録画データの収集時に事前にやっておくべき)
        if len(self._segments) == 0:

            # ffprobe で映像パケットの情報を取得する
            ffprobe_options = ['-select_streams', 'v:0', '-show_packets', '-show_entries', 'packet=pts,dts,flags,pos', '-of', 'json']
            ffprobe_result = await asyncio.subprocess.create_subprocess_exec(
                *[LIBRARY_PATH['FFprobe'], *ffprobe_options, self.recorded_program.recorded_video.file_path],
                stdout = asyncio.subprocess.PIPE,
                stderr = asyncio.subprocess.DEVNULL,  # ログは使用しない
            )
            assert ffprobe_result.stdout is not None
            packets: list[dict[str, Any]] = json.loads((await ffprobe_result.stdout.read()).decode('utf-8'))['packets']

            # 各セグメントの切り出し位置などを算出する
            ## セグメントは SEGMENT_DURATION_SECONDS 秒ごとに作成するが、キーフレームがピッタリ合うことはまずないので、
            ## SEGMENT_DURATION_SECONDS 秒を超えた時点で一番 PTS が近いキーフレームを探してセグメントを作成する
            is_first_keyframe_found = False
            segment_sequence = 0
            for packet in packets:

                # 最初 (先頭) のキーフレーム
                if 'K' in str(packet['flags']) and is_first_keyframe_found is False:

                    # 最初 (先頭) のセグメントを作成する
                    self._segments.append(VideoStreamSegment(
                        sequence_index = segment_sequence,
                        start_pts = int(packet['pts']),  # 映像の最初のパケットの PTS
                        start_file_position = int(packet['pos']),  # 映像の最初のパケットのファイル上の位置 (バイト)
                        end_pts = 0,  # 仮の値
                        end_file_position = 0,  # 仮の値
                        duration_seconds = 0,  # 仮の値
                        segment_ts_packet_queue = queue.Queue(maxsize=188 * 10000),  # dataclass 側に書くと全ての参照が同じになってしまうので毎回新たに生成する
                        encoded_segment_ts_future = asyncio.Future(),  # dataclass 側に書くと全ての参照が同じになってしまうので毎回新たに生成する
                    ))
                    is_first_keyframe_found = True
                    segment_sequence += 1
                    continue

                # 2番目以降のキーフレーム
                elif 'K' in str(packet['flags']) and is_first_keyframe_found is True:

                    # 前のセグメントの start_pts から SEGMENT_DURATION_SECONDS 秒以上離れている場合のみ新たにセグメントを作成する
                    ## PTS は整数値なので、比較するときは ts.HZ (90000) で割って秒単位にする
                    ## セグメント長は 10.203350 秒など 10 秒より若干長いくらいになるはず
                    if ((int(packet['pts']) - self._segments[-1].start_pts) / ts.HZ) >= VideoEncodingTask.SEGMENT_DURATION_SECONDS:

                        # 前のセグメントの終了位置と長さを確定する
                        self._segments[-1].end_pts = int(packet['pts']) - 1  # - 1 して次のセグメントの開始 PTS と重複しないようにする
                        self._segments[-1].end_file_position = int(packet['pos']) - 1   # - 1 して次のセグメントの開始位置と重複しないようにする
                        self._segments[-1].duration_seconds = (self._segments[-1].end_pts - self._segments[-1].start_pts + 1) / ts.HZ

                        # 次のセグメントを作成する
                        self._segments.append(VideoStreamSegment(
                            sequence_index = segment_sequence,
                            start_pts = int(packet['pts']),
                            start_file_position = int(packet['pos']),
                            end_pts = 0,  # 仮の値
                            end_file_position = 0,  # 仮の値
                            duration_seconds = 0,  # 仮の値
                            segment_ts_packet_queue = queue.Queue(maxsize=188 * 10000),  # dataclass 側に書くと全ての参照が同じになってしまうので毎回新たに生成する
                            encoded_segment_ts_future = asyncio.Future(),  # dataclass 側に書くと全ての参照が同じになってしまうので毎回新たに生成する
                        ))
                        segment_sequence += 1

            # 映像の最後のフレーム (キーフレームかどうかは問わない) の情報から最後のセグメントの終了位置と長さを確定する
            self._segments[-1].end_pts = packets[-1]['pts']  # 次のセグメントはないので、最後のパケットの PTS をそのまま採用する
            self._segments[-1].end_file_position = packets[-1]['pos']  # 次のセグメントはないので、最後のパケットのファイル上の位置をそのまま採用する
            self._segments[-1].duration_seconds = (self._segments[-1].end_pts - self._segments[-1].start_pts + 1) / ts.HZ

        if Config().general.debug is True:
            print(f'[Video: {self.video_stream_id}] Segments:')
            print(self._segments)

        # 仮想 HLS M3U8 プレイリストを生成
        virtual_playlist = ''
        virtual_playlist += '#EXTM3U\n'
        virtual_playlist += '#EXT-X-VERSION:6\n'
        virtual_playlist += '#EXT-X-PLAYLIST-TYPE:VOD\n'

        # HLS セグメントの実時間の最大値を指定する (SEGMENT_DURATION_SECONDS + 1 秒程度の余裕を持たせる)
        virtual_playlist += f'#EXT-X-TARGETDURATION:{int(VideoEncodingTask.SEGMENT_DURATION_SECONDS + 1)}\n'

        # 事前に算出したセグメントをすべて記述する
        for segment in self._segments:
            virtual_playlist += f'#EXTINF:{segment.duration_seconds:.6f},\n'  # セグメントの長さ (秒, 小数点以下6桁まで)
            virtual_playlist += f'segment?sequence={segment.sequence_index}&_={self._time_hash}\n'  # キャッシュ避けのためにタイムスタンプを付与する

        virtual_playlist += f'#EXT-X-ENDLIST\n'
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
        if segment_sequence < 0 or segment_sequence >= len(self._segments):
            return None

        # シーケンス番号に対応する HLS セグメントを取得する
        segment = self._segments[segment_sequence]

        # まだエンコードタスクが一度も実行されていない場合は、このセグメントからエンコードタスクを非同期で開始する
        if self._encoding_task is None:
            self._encoding_task = VideoEncodingTask(self)
            asyncio.create_task(self._encoding_task.run(segment_sequence))
            Logging.info(f'[Video: {self.video_stream_id}][Segment {segment_sequence}] New Encoding Task Started.')

        # エンコードタスクは既に起動しているがこの時点でまだセグメントのエンコードが開始されていなければ、このセグメントからエンコードタスクを非同期で開始する
        # この HLS セグメントのエンコード処理が現在進行中の場合は完了まで待つ
        elif segment.encoded_segment_ts_future.done() is False and segment.encode_status == 'Pending':

            # 0.5 秒待ってみて、それでも同じ状態のときだけエンコードタスクを再起動する
            # タイミングの関係であともう少しだけ待てば当該セグメントのエンコードが開始するのに…！という場合に備える
            await asyncio.sleep(0.5)
            if segment.encoded_segment_ts_future.done() is False and segment.encode_status == 'Pending':

                # 以前のエンコードタスクをキャンセルする
                # この時点で以前のエンコードタスクでエンコードが完了していたセグメントに関してはそのまま self.segments に格納されている
                await self._encoding_task.cancel()
                Logging.info(f'[Video: {self.video_stream_id}][Segment {segment_sequence}] Previous Encoding Task Canceled.')

                # 新たにエンコードタスクを非同期で開始する
                self._encoding_task = VideoEncodingTask(self)
                asyncio.create_task(self._encoding_task.run(segment_sequence))
                Logging.info(f'[Video: {self.video_stream_id}][Segment {segment_sequence}] New Encoding Task Started.')

        # セグメントデータの Future が完了したらそのデータを返す
        encoded_segment_ts = await asyncio.shield(segment.encoded_segment_ts_future)
        return encoded_segment_ts


    async def destroy(self) -> None:
        """
        ビデオストリームで実行中のエンコードなどの処理を終了し、ビデオストリームを破棄する
        ユーザーが番組の視聴を終了した (keepAlive() が呼び出されなくなった) 場合に自動的に呼び出される
        """

        # 起動中のエンコードタスクがあればキャンセルする
        # この時点ですでにエンコードを完了して終了している場合もある
        if self._encoding_task is not None:
            await self._encoding_task.cancel()
            self._encoding_task = None

        # すべての HLS セグメントを削除する
        self._segments = []

        # アクティブな間保持されていたインスタンスを削除する
        ## これにより、このインスタンスには誰も参照できなくなるため、ガベージコレクションによりメモリから解放される (はず)
        ## 今後同じビデオストリーム ID が指定された場合は新たに別のインスタンスが生成される
        self.__instances.pop(self.video_stream_id)

        Logging.info(f'[Video: {self.video_stream_id}] Streaming Session Finished.')
