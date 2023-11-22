
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import asyncio
import os
import subprocess
import threading
import time
from biim.mpeg2ts import ts
from biim.mpeg2ts.packetize import packetize_section
from biim.mpeg2ts.pat import PATSection
from biim.mpeg2ts.pmt import PMTSection
from biim.mpeg2ts.pes import PES
from biim.mpeg2ts.parser import SectionParser
from typing import cast, ClassVar, Literal, TYPE_CHECKING

from app.config import Config
from app.constants import LIBRARY_PATH, QUALITY, QUALITY_TYPES
from app.models.RecordedProgram import RecordedProgram
from app.models.RecordedVideo import RecordedVideo
from app.utils import Logging

if TYPE_CHECKING:
    from app.streams.VideoStream import VideoStream
    from app.streams.VideoStream import VideoStreamSegment


class VideoEncodingTask:

    # エンコードする HLS セグメントの長さ (秒)
    SEGMENT_DURATION_SECONDS: ClassVar[float] = float(10)  # 10秒

    # エンコード後のストリームの GOP 長 (秒)
    ## LiveEncodingTask と異なりライブではないため、GOP 長は H.264 / H.265 共通で長めに設定する
    GOP_LENGTH_SECOND: ClassVar[float] = float(5)  # 5秒


    def __init__(self, video_stream: VideoStream) -> None:
        """
        VideoStream のインスタンスに基づくビデオエンコードタスクを初期化する

        Args:
            video_stream (VideoStream): VideoStream のインスタンス
        """

        # ビデオストリームのインスタンスをセット
        self.video_stream = video_stream

        # 現在実行中のイベントループ
        self._loop = asyncio.get_running_loop()

        # tsreadex とエンコーダーのプロセス
        self._tsreadex_process: subprocess.Popen[bytes] | None = None
        self._encoder_process: subprocess.Popen[bytes] | None = None

        # エンコードタスクを完了済みかどうか
        self._is_finished: bool = False

        # 破棄されているかどうか
        self._is_cancelled: bool = False


    @property
    def recorded_program(self) -> RecordedProgram:
        """ self.video_stream.recorded_program が長いのでエイリアス """
        return self.video_stream.recorded_program

    @property
    def recorded_video(self) -> RecordedVideo:
        """ self.video_stream.recorded_program.recorded_video が長いのでエイリアス """
        return self.video_stream.recorded_program.recorded_video


    def buildFFmpegOptions(self,
        quality: QUALITY_TYPES,
        output_timestamp_offset: float,
    ) -> list[str]:
        """
        FFmpeg に渡すオプションを組み立てる

        Args:
            quality (QUALITY_TYPES): 映像の品質
            output_timestamp_offset (float): セグメントを出力する際のタイムスタンプ類のオフセット (PTS)

        Returns:
            list[str]: FFmpeg に渡すオプションが連なる配列
        """

        # オプションの入る配列
        options: list[str] = []

        # 入力
        ## -analyzeduration をつけることで、ストリームの分析時間を短縮できる
        options.append('-f mpegts -analyzeduration 500000 -i pipe:0')

        # ストリームのマッピング
        ## 音声切り替えのため、主音声・副音声両方をエンコード後の TS に含む
        options.append('-map 0:v:0 -map 0:a:0 -map 0:a:1 -map 0:d? -ignore_unknown')

        # フラグ
        ## 主に FFmpeg の起動を高速化するための設定
        options.append('-fflags nobuffer -flags low_delay -max_delay 0 -max_interleave_delta 500K -threads auto')

        # 映像
        ## コーデック
        if QUALITY[quality].is_hevc is True:
            options.append('-vcodec libx265')  # H.265/HEVC (通信節約モード)
        else:
            options.append('-vcodec libx264')  # H.264

        ## バイトレートと品質
        options.append(f'-flags +cgop -vb {QUALITY[quality].video_bitrate} -maxrate {QUALITY[quality].video_bitrate_max}')
        options.append('-preset veryfast -aspect 16:9')
        if QUALITY[quality].is_hevc is True:
            options.append('-profile:v main')
        else:
            options.append('-profile:v high')

        ## 指定された品質の解像度が 1440×1080 (1080p) かつ入力ストリームがフル HD (1920×1080) の場合のみ、
        ## 特別に縦解像度を 1920 に変更してフル HD (1920×1080) でエンコードする
        video_width = QUALITY[quality].width
        video_height = QUALITY[quality].height
        if (video_width == 1440 and video_height == 1080) and \
           (self.recorded_video.video_resolution_width == 1920 and self.recorded_video.video_resolution_height == 1080):
            video_width = 1920

        ## 最大 GOP 長 (秒)
        ## 30fps なら ×30 、 60fps なら ×60 された値が --gop-len で使われる
        gop_length_second = self.GOP_LENGTH_SECOND

        # インターレース映像のみ
        if self.recorded_video.video_scan_type == 'Interlaced':
            ## インターレース解除 (60i → 60p (フレームレート: 60fps))
            if QUALITY[quality].is_60fps is True:
                options.append(f'-vf yadif=mode=1:parity=-1:deint=1,scale={video_width}:{video_height}')
                options.append(f'-r 60000/1001 -g {int(gop_length_second * 60)}')
            ## インターレース解除 (60i → 30p (フレームレート: 30fps))
            else:
                options.append(f'-vf yadif=mode=0:parity=-1:deint=1,scale={video_width}:{video_height}')
                options.append(f'-r 30000/1001 -g {int(gop_length_second * 30)}')
        # プログレッシブ映像
        ## プログレッシブ映像の場合は 60fps 化する方法はないため、無視して元映像と同じフレームレートでエンコードする
        ## GOP は 30fps だと仮定して設定する
        elif self.recorded_video.video_scan_type == 'Progressive':
            options.append(f'-r 30000/1001 -g {int(gop_length_second * 30)}')

        # 音声
        ## 音声が 5.1ch かどうかに関わらず、ステレオにダウンミックスする
        options.append(f'-acodec aac -aac_coder twoloop -ac 2 -ab {QUALITY[quality].audio_bitrate} -ar 48000 -af volume=2.0')

        # 出力するセグメント TS のタイムスタンプのオフセット
        # タイムスタンプが前回エンコードしたセグメントの続きになるようにする
        options.append(f'-output_ts_offset {output_timestamp_offset}')

        # 出力
        options.append('-y -f mpegts')  # MPEG-TS 出力ということを明示
        options.append('pipe:1')  # 標準入力へ出力

        # オプションをスペースで区切って配列にする
        result: list[str] = []
        for option in options:
            result += option.split(' ')

        return result


    def buildHWEncCOptions(self,
        quality: QUALITY_TYPES,
        encoder_type: Literal['QSVEncC', 'NVEncC', 'VCEEncC', 'rkmppenc'],
    ) -> list[str]:
        """
        QSVEncC・NVEncC・VCEEncC・rkmppenc (便宜上 HWEncC と総称) に渡すオプションを組み立てる

        Args:
            quality (QUALITY_TYPES): 映像の品質
            encoder_type (Literal['QSVEncC', 'NVEncC', 'VCEEncC', 'rkmppenc']): エンコーダー (QSVEncC or NVEncC or VCEEncC or rkmppenc)

        Returns:
            list[str]: HWEncC に渡すオプションが連なる配列
        """

        # オプションの入る配列
        options: list[str] = []

        # 入力
        ## --input-probesize, --input-analyze をつけることで、ストリームの分析時間を短縮できる
        ## 両方つけるのが重要で、--input-analyze だけだとエンコーダーがフリーズすることがある
        options.append('--input-format mpegts --input-probesize 1000K --input-analyze 0.7 --input -')
        ## VCEEncC の HW デコーダーはエラー耐性が低く TS を扱う用途では不安定なので、SW デコーダーを利用する
        if encoder_type == 'VCEEncC':
            options.append('--avsw')
        ## QSVEncC・NVEncC・rkmppenc は HW デコーダーを利用する
        else:
            options.append('--avhw')

        # ストリームのマッピング
        ## 音声切り替えのため、主音声・副音声両方をエンコード後の TS に含む
        ## 音声が 5.1ch かどうかに関わらず、ステレオにダウンミックスする
        options.append('--audio-stream 1?:stereo --audio-stream 2?:stereo --data-copy timed_id3')

        # フラグ
        ## 主に HWEncC の起動を高速化するための設定
        options.append('-m avioflags:direct -m fflags:nobuffer+flush_packets -m flush_packets:1 -m max_delay:250000')
        options.append('-m max_interleave_delta:500K --output-thread 0 --lowlatency')

        # 映像
        ## コーデック
        if QUALITY[quality].is_hevc is True:
            options.append('--codec hevc')  # H.265/HEVC (通信節約モード)
        else:
            options.append('--codec h264')  # H.264

        ## バイトレート
        ## H.265/HEVC かつ QSVEncC の場合のみ、--qvbr (品質ベース可変バイトレート) モードでエンコードする
        ## それ以外は --vbr (可変バイトレート) モードでエンコードする
        if QUALITY[quality].is_hevc is True and encoder_type == 'QSVEncC':
            options.append(f'--qvbr {QUALITY[quality].video_bitrate} --fallback-rc')
        else:
            options.append(f'--vbr {QUALITY[quality].video_bitrate}')
        options.append(f'--max-bitrate {QUALITY[quality].video_bitrate_max}')

        ## H.265/HEVC の高圧縮化調整
        if QUALITY[quality].is_hevc is True:
            if encoder_type == 'QSVEncC':
                options.append('--qvbr-quality 30')
            elif encoder_type == 'NVEncC':
                options.append('--qp-min 23:26:30 --lookahead 16 --multipass 2pass-full --weightp --bref-mode middle --aq --aq-temporal')

        ## ヘッダ情報制御 (GOP ごとにヘッダを再送する)
        ## VCEEncC ではデフォルトで有効であり、当該オプションは存在しない
        if encoder_type != 'VCEEncC':
            options.append('--repeat-headers')

        ## 品質
        if encoder_type == 'QSVEncC':
            options.append('--quality balanced')
        elif encoder_type == 'NVEncC':
            options.append('--preset default')
        elif encoder_type == 'VCEEncC':
            options.append('--preset balanced')
        elif encoder_type == 'rkmppenc':
            options.append('--preset best')
        if QUALITY[quality].is_hevc is True:
            options.append('--profile main')
        else:
            options.append('--profile high')
        options.append(f'--interlace tff --dar 16:9')

        ## 最大 GOP 長 (秒)
        ## 30fps なら ×30 、 60fps なら ×60 された値が --gop-len で使われる
        gop_length_second = self.GOP_LENGTH_SECOND

        # インターレース映像
        if self.recorded_video.video_scan_type == 'Interlaced':
            ## インターレース解除 (60i → 60p (フレームレート: 60fps))
            ## NVEncC の --vpp-deinterlace bob は品質が悪いので、代わりに --vpp-yadif を使う
            ## NVIDIA GPU は当然ながら Intel の内蔵 GPU よりも性能が高いので、GPU フィルタを使ってもパフォーマンスに問題はないと判断
            ## VCEEncC では --vpp-deinterlace 自体が使えないので、代わりに --vpp-yadif を使う
            if QUALITY[quality].is_60fps is True:
                if encoder_type == 'QSVEncC':
                    options.append('--vpp-deinterlace bob')
                elif encoder_type == 'NVEncC' or encoder_type == 'VCEEncC':
                    options.append('--vpp-yadif mode=bob')
                elif encoder_type == 'rkmppenc':
                    options.append('--vpp-deinterlace bob_i5')
                options.append(f'--avsync vfr --gop-len {int(gop_length_second * 60)}')
            ## インターレース解除 (60i → 30p (フレームレート: 30fps))
            ## NVEncC の --vpp-deinterlace normal は GPU 機種次第では稀に解除漏れのジャギーが入るらしいので、代わりに --vpp-afs を使う
            ## NVIDIA GPU は当然ながら Intel の内蔵 GPU よりも性能が高いので、GPU フィルタを使ってもパフォーマンスに問題はないと判断
            ## VCEEncC では --vpp-deinterlace 自体が使えないので、代わりに --vpp-afs を使う
            else:
                if encoder_type == 'QSVEncC':
                    options.append(f'--vpp-deinterlace normal')
                elif encoder_type == 'NVEncC' or encoder_type == 'VCEEncC':
                    options.append(f'--vpp-afs preset=default')
                elif encoder_type == 'rkmppenc':
                    options.append('--vpp-deinterlace normal_i5')
                options.append(f'--avsync vfr --gop-len {int(gop_length_second * 30)}')
        # プログレッシブ映像
        ## プログレッシブ映像の場合は 60fps 化する方法はないため、無視して元映像と同じフレームレートでエンコードする
        ## GOP は 30fps だと仮定して設定する
        elif self.recorded_video.video_scan_type == 'Progressive':
            options.append(f'--avsync vfr --gop-len {int(gop_length_second * 30)}')

        ## 指定された品質の解像度が 1440×1080 (1080p) かつ入力ストリームがフル HD (1920×1080) の場合のみ、
        ## 特別に縦解像度を 1920 に変更してフル HD (1920×1080) でエンコードする
        video_width = QUALITY[quality].width
        video_height = QUALITY[quality].height
        if (video_width == 1440 and video_height == 1080) and \
           (self.recorded_video.video_resolution_width == 1920 and self.recorded_video.video_resolution_height == 1080):
            video_width = 1920
        options.append(f'--output-res {video_width}x{video_height}')

        # 入力のタイムスタンプを出力にコピーする
        options.append(f'--timestamp-passthrough')

        # 音声
        options.append(f'--audio-codec aac:aac_coder=twoloop --audio-bitrate {QUALITY[quality].audio_bitrate}')
        options.append('--audio-samplerate 48000 --audio-filter volume=2.0 --audio-ignore-decode-error 30')

        # 出力
        options.append('--output-format mpegts')  # MPEG-TS 出力ということを明示
        options.append('--output -')  # 標準入力へ出力

        # オプションをスペースで区切って配列にする
        result: list[str] = []
        for option in options:
            result += option.split(' ')

        return result


    def __runEncoder(self, segment: VideoStreamSegment) -> None:
        """
        録画 TS データから直接切り出した生の MPEG-TS チャンクをエンコードするエンコーダープロセスを開始する
        セグメントのキューに入れられた TS パケットをエンコーダーに順次投入し、エンコード済みのセグメントデータを VideoStreamSegment に書き込む
        非同期 (asyncio.create_task()) で実行するとイベントループがビジーになったりなど厄介な問題が発生するため同期メソッドとしている
        このメソッドはエンコードが完了/失敗するか、エンコードタスクがキャンセルされるまでブロックする

        Args:
            segment (VideoStreamSegment): エンコード対象の VideoStreamSegment のデータ
        """

        # エンコーダーの種類を取得
        ENCODER_TYPE = Config().general.encoder

        # まだエンコーダーが起動している場合、前のエンコーダーが終了するまで待つ
        ## ファイルの読み取りよりエンコードの方が基本的に遅いので、前のセグメントのエンコード中に次のエンコードを開始しないようにする
        if self._encoder_process is not None:
            Logging.info(f'[Video: {self.video_stream.video_stream_id}][Segment {segment.sequence_index}] '
                         f'Waiting previous {ENCODER_TYPE} to finish...')
            self._encoder_process.wait()
            time.sleep(0.1)  # ちょっと待つ

        # 待機後にエンコードタスクがキャンセルされた場合、処理を中断する
        if self._is_cancelled is True:
            return  # メソッドの実行自体を終了する

        Logging.info(f'[Video: {self.video_stream.video_stream_id}][Segment {segment.sequence_index}] Encoding HLS segment...')

        # ***** tsreadex プロセスの作成と実行 *****

        # tsreadex のオプション
        ## 放送波の前処理を行い、エンコードを安定させるツール
        ## オプション内容は https://github.com/xtne6f/tsreadex を参照
        tsreadex_options = [
            # 取り除く TS パケットの10進数の PID
            ## EIT の PID を指定
            '-x', '18/38/39',
            # 特定サービスのみを選択して出力するフィルタを有効にする
            ## 有効にすると、特定のストリームのみ PID を固定して出力される
            ## 視聴対象の録画番組が放送されたチャンネルのサービス ID があれば指定する
            '-n', f'{self.recorded_program.channel.service_id}' if self.recorded_program.channel is not None else '-1',
            # 主音声ストリームが常に存在する状態にする
            ## ストリームが存在しない場合、無音の AAC ストリームが出力される
            ## 音声がモノラルであればステレオにする
            ## デュアルモノを2つのモノラル音声に分離し、右チャンネルを副音声として扱う
            '-a', '13',
            # 副音声ストリームが常に存在する状態にする
            ## ストリームが存在しない場合、無音の AAC ストリームが出力される
            ## 音声がモノラルであればステレオにする
            '-b', '5',
            # 字幕ストリームが常に存在する状態にする
            ## ストリームが存在しない場合、PMT の項目が補われて出力される
            '-c', '1',
            # 文字スーパーストリームが常に存在する状態にする
            ## ストリームが存在しない場合、PMT の項目が補われて出力される
            '-u', '1',
            # 字幕と文字スーパーを aribb24.js が解釈できる ID3 timed-metadata に変換する
            ## +4: FFmpeg のバグを打ち消すため、変換後のストリームに規格外の5バイトのデータを追加する
            ## +8: FFmpeg のエラーを防ぐため、変換後のストリームの PTS が単調増加となるように調整する
            '-d', '13',
            # 標準入力からの入力を受け付ける
            '-',
        ]

        # tsreadex のプロセスを非同期で作成・実行
        self._tsreadex_process = subprocess.Popen(
            [LIBRARY_PATH['tsreadex'], *tsreadex_options],
            stdin = subprocess.PIPE,  # 録画 TS データから直接切り出した生の MPEG-TS チャンクを書き込む
            stdout = subprocess.PIPE,  # エンコーダーに繋ぐ
            stderr = subprocess.DEVNULL,  # 利用しない
        )

        # ***** エンコーダープロセスの作成と実行 *****

        # FFmpeg
        if ENCODER_TYPE == 'FFmpeg':

            # オプションを取得
            encoder_options = self.buildFFmpegOptions(self.video_stream.quality, segment.start_pts / ts.HZ)
            Logging.info(f'[Video: {self.video_stream.video_stream_id}][Segment {segment.sequence_index}] '
                         f'FFmpeg Commands:\nffmpeg {" ".join(encoder_options)}')

            # エンコーダープロセスを非同期で作成・実行
            self._encoder_process = subprocess.Popen(
                [LIBRARY_PATH['FFmpeg'], *encoder_options],
                stdin = self._tsreadex_process.stdout,  # tsreadex からの入力
                stdout = subprocess.PIPE,  # ストリーム出力
                # stderr = subprocess.DEVNULL,
                stderr = None,  # デバッグ用
            )

        # HWEncC
        else:

            # オプションを取得
            encoder_options = self.buildHWEncCOptions(self.video_stream.quality, ENCODER_TYPE)
            Logging.info(f'[Video: {self.video_stream.video_stream_id}][Segment {segment.sequence_index}] '
                         f' {ENCODER_TYPE} Commands:\n{ENCODER_TYPE} {" ".join(encoder_options)}')

            # エンコーダープロセスを非同期で作成・実行
            self._encoder_process = subprocess.Popen(
                [LIBRARY_PATH[ENCODER_TYPE], *encoder_options],
                stdin = self._tsreadex_process.stdout,  # tsreadex からの入力
                stdout = subprocess.PIPE,  # ストリーム出力
                # stderr = subprocess.DEVNULL,
                stderr = None,  # デバッグ用
            )

        # 処理対象の VideoStreamSegment をエンコード中状態に設定
        segment.encode_status = 'Encoding'

        # 受信したエンコード済み TS パケットのバッファ
        ## 最終的に単一のセグメントのすべての TS パケットが入る
        encoded_ts_packet_buffer = bytearray()

        # ***** 切り出した TS パケットをエンコーダーに送信するスレッド *****

        def Writer() -> None:

            # 送信する TS パケットのバッファ
            # バッファサイズ: 188B (TS Packet Size) * 256 = 48128B
            ts_packet_buffer = bytearray()

            # エンコーダーに投入した TS パケットのバイト数
            segment_bytes_count = 0

            while True:

                # すでにエンコーダーが強制終了されているならループを抜ける
                ## 強制終了された後は None になるのを利用する
                ## エンコードタスクがキャンセルされた時にしか発生しないはず
                if self._tsreadex_process is None or self._encoder_process is None or self._is_cancelled is True:
                    break

                # Queue から切り出された TS パケットを随時取得
                ts_packet = segment.segment_ts_packet_queue.get()
                if ts_packet is not None:
                    ts_packet_buffer += ts_packet

                # 48128B に到達した or これ以上エンコーダーに投入するパケットがなくなったら、
                # バッファをエンコーダー (正確にはその前段の tsreadex) に投入
                if len(ts_packet_buffer) >= 188 * 256 or ts_packet is None:
                    try:
                        if self._tsreadex_process is not None:  # 念のため
                            assert self._tsreadex_process.stdin is not None
                            self._tsreadex_process.stdin.write(ts_packet_buffer)
                            self._tsreadex_process.stdin.flush()
                    except Exception as ex:
                        Logging.error(f'[Video: {self.video_stream.video_stream_id}][Segment {segment.sequence_index}] '
                                    f'Failed to write TS packets to {ENCODER_TYPE}. ({ex})')

                    # エンコーダーに投入した TS パケットのバイト数を加算
                    segment_bytes_count += len(ts_packet_buffer)

                    # バッファを空にする
                    ts_packet_buffer = bytearray()

                # これ以上エンコーダーに投入するパケットがなくなったら tsreadex の標準入力を閉じ、エンコーダーの出力の読み取りを待つ
                if ts_packet is None:  # None はこれ以上投入するパケットがないことを示す
                    Logging.info(f'[Video: {self.video_stream.video_stream_id}][Segment {segment.sequence_index}] '
                                f'Cut out {segment_bytes_count / 1024 / 1024:.3f} MiB.')
                    Logging.info(f'[Video: {self.video_stream.video_stream_id}][Segment {segment.sequence_index}] '
                                f'Waiting for {ENCODER_TYPE} to finish...')
                    if self._tsreadex_process is not None:  # 念のため
                        assert self._tsreadex_process.stdin is not None
                        self._tsreadex_process.stdin.close()
                    break  # ループを抜ける

        # ***** エンコード済み TS パケット (セグメントデータ) をエンコーダーから受信するスレッド *****

        def Reader() -> None:
            nonlocal encoded_ts_packet_buffer

            while True:

                # すでにエンコーダーが強制終了されているならループを抜ける
                ## 強制終了された後は None になるのを利用する
                ## エンコードタスクがキャンセルされた時にしか発生しないはず
                if self._tsreadex_process is None or self._encoder_process is None or self._is_cancelled is True:
                    break

                if self._encoder_process is not None:  # 念のため
                    try:
                        # エンコーダーの出力を 48128B (188 * 256) ずつ受信してバッファに保存する
                        assert self._encoder_process.stdout is not None
                        ts_packets = self._encoder_process.stdout.read(188 * 256)

                        # 出力の終端に到達したらループを抜ける
                        if ts_packets == b'':
                            break

                        # バッファに受信したエンコード済み TS パケットを追加
                        encoded_ts_packet_buffer += ts_packets

                    except Exception as ex:
                        Logging.error(f'[Video: {self.video_stream.video_stream_id}][Segment {segment.sequence_index}] '
                                        f'Failed to read encoded TS packets from {ENCODER_TYPE}. ({ex})')

        # ***** Writer と Reader の終了後、エンコード済み TS パケットを VideoStreamSegment に書き込む *****

        # Writer と Reader を同時実行して、スレッドを終了するまで待つ
        writer_thread = threading.Thread(target=Writer, daemon=True)
        reader_thread = threading.Thread(target=Reader, daemon=True)
        writer_thread.start()
        reader_thread.start()
        writer_thread.join()
        reader_thread.join()

        # この時点でエンコードタスクがキャンセルされていればエンコード済みのセグメントデータを放棄して中断する
        ## この時点でエンコーダープロセスが None になっている場合もキャンセルされたと判断する
        if self._is_cancelled is True or self._encoder_process is None:
            self.__terminateEncoder()
            Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}][Segment {segment.sequence_index}] '
                                'Discarded encoded segment data because cancelled.')

            # エンコード作業自体を中断したので、このセグメントの状態をリセットする
            ## resetState() は asyncio.Future() を作り直す関係で非同期なので、メインスレッドに移譲して実行する
            asyncio.run_coroutine_threadsafe(segment.resetState(), self._loop)

            # エンコードタスクの完了フラグを立てる
            ## 完了フラグを立てたタイミングで cancel() が戻る
            self._is_finished = True
            return

        # この時点でエンコーダーの exit code が None (まだプロセスが起動している) か 0 でなければ何らかの理由でエンコードに失敗している
        if self._encoder_process.poll() is not None and self._encoder_process.poll() != 0:
            self.__terminateEncoder()
            Logging.error(f'[Video: {self.video_stream.video_stream_id}][Segment {segment.sequence_index}] '
                        f'{ENCODER_TYPE} exited with exit code {self._encoder_process.poll()}.')

            # おそらく復旧しようがないが、一応このセグメントの状態をリセットする
            ## resetState() は asyncio.Future() を作り直す関係で非同期なので、メインスレッドに移譲して実行する
            asyncio.run_coroutine_threadsafe(segment.resetState(), self._loop)
            return

        # 処理対象の VideoStreamSegment をエンコード完了状態に設定
        segment.encode_status = 'Completed'

        # エンコード後のセグメントデータを VideoStreamSegment に書き込む
        # ここで設定したエンコード済みのセグメントデータが API で返される
        segment.encoded_segment_ts_future.set_result(bytes(encoded_ts_packet_buffer))
        Logging.info(f'[Video: {self.video_stream.video_stream_id}][Segment {segment.sequence_index}] Successfully encoded HLS segment.')

        # この時点で tsreadex とエンコーダーは終了しているはずだが、念のため強制終了しておく
        # 最後に行うのが重要 (kill すると exit code が 0 以外になる可能性があるため)
        self.__terminateEncoder()


    def __terminateEncoder(self) -> None:
        """
        起動中のエンコーダープロセスを強制終了する
        """

        # エンコーダーの種類を取得
        ENCODER_TYPE = Config().general.encoder

        # tsreadex プロセスを強制終了する
        if self._tsreadex_process is not None:
            try:
                self._tsreadex_process.kill()
            except Exception:
                pass
            self._tsreadex_process = None

        # エンコーダープロセスを強制終了する
        if self._encoder_process is not None:
            try:
                self._encoder_process.kill()
            except Exception:
                pass
            self._encoder_process = None
            Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}] Terminated {ENCODER_TYPE} process.')


    def __run(self, first_segment_index: int) -> None:
        """
        HLS エンコードタスクを実行する
        非同期 (asyncio.create_task()) で実行するとイベントループがビジーになったりなど厄介な問題が発生するため、意図的に同期メソッドとしている
        aiofiles は単に裏でスレッドプールに投げてるだけなので、それなら全部別スレッドで実行したほうがパフォーマンスが良いと判断
        TODO: 現状 PCR や PTS が一周した時の処理は何も考えてない

        biim の実装をめちゃくちゃ参考にした (圧倒的感謝…!!)
        ref: https://github.com/monyone/biim/blob/other/static-ondemand-hls/seekable.py
        ref: https://github.com/monyone/biim/blob/other/static-ondemand-hls/vod_main.py
        ref: https://github.com/monyone/biim/blob/other/static-ondemand-hls/vod_fmp4.py

        Args:
            first_segment_index (int): エンコードを開始する HLS セグメントのインデックス (HLS セグメントのシーケンス番号と一致する)
        """

        # first_segment_index が self.video_stream.segments の範囲外
        if first_segment_index < 0 or first_segment_index >= len(self.video_stream.segments):
            assert False, f'first_segment_index ({first_segment_index}) is out of range, allowed range is 0 to {len(self.video_stream.segments) - 1}.'

        # すでにタスクが完了している
        if self._is_finished is True:
            assert False, 'VideoEncodingTask is already finished.'

        # すでにエンコードタスクがキャンセルされている
        if self._is_cancelled is True:
            assert False, 'VideoEncodingTask is already cancelled.'

        Logging.info(f'[Video: {self.video_stream.video_stream_id}] VideoEncodingTask started.')

        # エンコーダーの種類を取得
        ENCODER_TYPE = Config().general.encoder

        # 視聴対象の録画番組が放送されたチャンネルのサービス ID
        SERVICE_ID: int | None = self.recorded_program.channel.service_id if self.recorded_program.channel is not None else None

        # 各 MPEG-TS パケットの PID
        PAT_PID: int = 0x00
        PMT_PID: int | None = None
        PCR_PID: int | None = None
        VIDEO_PID: int | None = None
        PRIMARY_AUDIO_PID: int | None = None
        SECONDARY_AUDIO_PID: int | None = None
        PES_PIDS: list[int] = []

        # 映像ストリームの概算バイトレート
        BYTE_RATE: float | None = None

        # PAT / PMT パーサー
        pat_parser: SectionParser[PATSection] = SectionParser(PATSection)
        pmt_parser: SectionParser[PMTSection] = SectionParser(PMTSection)

        # 事前に当該 MPEG-TS 内の各ストリームの PID を取得し、シーク時用のバイトレート (B/s) を概算する
        latest_pcr_value: int | None = None  # 前回の PCR 値
        latest_pcr_ts_packet_bytes: int | None = None  # 最初の PCR 値を取得してから読み取った TS パケットの累計バイト数
        pcr_remain_count: int = 30  # 30 回分の PCR 値を取得する (PCR を取得するたびに 1 減らす)
        with open(self.recorded_video.file_path, 'rb') as reader:
            while True:

                # 同期バイトを探す
                while True:
                    sync_byte: bytes = reader.read(1)
                    if sync_byte == ts.SYNC_BYTE:
                        break
                    elif sync_byte == b'':
                        # このループでファイルの終端に達することは基本ないはず
                        assert False, 'Invalid TS file. Sync byte is not found.'

                # 速度向上のため 188 * 10000 バイトのチャンクで一気に読み込んだ後、188 バイトごとの TS パケットに分割して処理する
                chunk = ts.SYNC_BYTE + reader.read((ts.PACKET_SIZE * 10000) - 1)
                for ts_packet in [chunk[i:i + ts.PACKET_SIZE] for i in range(0, len(chunk), ts.PACKET_SIZE)]:
                    if len(ts_packet) != ts.PACKET_SIZE:
                        Logging.error(f'[Video: {self.video_stream.video_stream_id}] Packet size is not 188 bytes.')
                        continue

                    # TS パケットの PID を取得する
                    PID = ts.pid(ts_packet)

                    # PAT: Program Association Table
                    if PID == PAT_PID:
                        pat_parser.push(ts_packet)
                        for PAT in pat_parser:
                            if PAT.CRC32() != 0:
                                continue
                            for program_number, program_map_PID in PAT:
                                if program_number == 0:
                                    continue

                                # PMT の PID を取得する
                                if program_number == SERVICE_ID:
                                    PMT_PID = program_map_PID
                                elif not SERVICE_ID:
                                    PMT_PID = program_map_PID
                                    break  # 先頭の PMT の PID のみ取得する

                    # PMT: Program Map Table
                    elif PID == PMT_PID:
                        pmt_parser.push(ts_packet)
                        for PMT in pmt_parser:
                            if PMT.CRC32() != 0:
                                continue
                            PCR_PID = PMT.PCR_PID

                            PES_PIDS.clear()  # 前の PMT から取得した PES パケットの PID をクリアする
                            is_video_pid_found = False
                            is_primary_audio_pid_found = False
                            is_secondary_audio_pid_found = False
                            for stream_type, elementary_PID, _ in PMT:

                                # PMT に記載されているのはすべて PES パケットの PID
                                PES_PIDS.append(elementary_PID)

                                # 映像ストリームの PID を取得する
                                ## PMT のうち、常に最初に出現する映像ストリームの PID を取得する
                                if not is_video_pid_found:
                                    if stream_type == 0x02:
                                        if VIDEO_PID != elementary_PID:
                                            Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}] MPEG-2 PID: 0x{elementary_PID:04x}')
                                        VIDEO_PID = elementary_PID
                                        is_video_pid_found = True
                                    elif stream_type == 0x1b:
                                        if VIDEO_PID != elementary_PID:
                                            Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}] H.264 PID: 0x{elementary_PID:04x}')
                                        VIDEO_PID = elementary_PID
                                        is_video_pid_found = True
                                    elif stream_type == 0x24:
                                        if VIDEO_PID != elementary_PID:
                                            Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}] H.265 PID: 0x{elementary_PID:04x}')
                                        VIDEO_PID = elementary_PID
                                        is_video_pid_found = True
                                # 主音声ストリームの PID を取得する
                                if not is_primary_audio_pid_found:
                                    if stream_type == 0x0f:
                                        if PRIMARY_AUDIO_PID != elementary_PID:
                                            Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}] Primary AAC PID: 0x{elementary_PID:04x}')
                                        PRIMARY_AUDIO_PID = elementary_PID
                                        is_primary_audio_pid_found = True
                                # 副音声ストリームの PID を取得する
                                ## 主音声ストリームが見つかった後のみ取得する
                                elif not is_secondary_audio_pid_found:
                                    if stream_type == 0x0f:
                                        if SECONDARY_AUDIO_PID != elementary_PID:
                                            Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}] Secondary AAC PID: 0x{elementary_PID:04x}')
                                        SECONDARY_AUDIO_PID = elementary_PID
                                        is_secondary_audio_pid_found = True

                    # PCR: Program Clock Reference
                    elif PID == PCR_PID and ts.has_pcr(ts_packet):
                        if latest_pcr_value is None:
                            # 最初の PCR 値を取得する
                            latest_pcr_value = cast(int, ts.pcr(ts_packet))
                            latest_pcr_ts_packet_bytes = 0  # 0 で初期化する
                        elif pcr_remain_count > 0:
                            pcr_remain_count -= 1  # PCR 値を取得するたびに 1 減らす
                        else:
                            # 30 回分の PCR パケットを読み取ったので、バイトレートを概算する
                            if BYTE_RATE is None:
                                # 初回のみ代入する (後のパケットで上書きしないようにする)
                                assert latest_pcr_ts_packet_bytes is not None
                                BYTE_RATE = (
                                    (latest_pcr_ts_packet_bytes + ts.PACKET_SIZE) * ts.HZ /
                                    ((cast(int, ts.pcr(ts_packet)) - latest_pcr_value + ts.PCR_CYCLE) % ts.PCR_CYCLE)
                                )
                                assert BYTE_RATE is not None
                                Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}] '
                                                     f'Approximate Bitrate: {(BYTE_RATE / 1024 / 1024 * 8):.3f} Mbps')

                    # 最初の PCR 値を取得してから読み取った TS パケットの累計バイト数を更新する
                    # 最初の PCR 値が取得されるまではカウントしない
                    if latest_pcr_ts_packet_bytes is not None:
                        latest_pcr_ts_packet_bytes += ts.PACKET_SIZE

                    # 各 PID と概算バイトレートの両方が取得できたらループを抜ける
                    ## 副音声ストリームは存在しない場合があるので、SECONDARY_AUDIO_PID は None のままでもよい
                    if (PMT_PID is not None) and \
                       (PCR_PID is not None) and \
                       (VIDEO_PID is not None) and \
                       (PRIMARY_AUDIO_PID is not None) and \
                       (BYTE_RATE is not None):
                        break

                # 多重ループを抜けられるようにする
                # ref: https://note.nkmk.me/python-break-nested-loops/
                else:
                    continue
                break

        # この時点で各ストリームの PID とシーク時用のバイトレート (B/s) が取得できているはず
        ## 実際の処理を始める前に取得しておくことで、最初の PMT の送出位置より前の TS パケットを取りこぼさずに済む
        assert PMT_PID is not None, 'PMT PID is not found.'
        assert PCR_PID is not None, 'PCR PID is not found.'
        assert VIDEO_PID is not None, 'Video PID is not found.'
        assert PRIMARY_AUDIO_PID is not None, 'Primary Audio PID is not found.'
        assert BYTE_RATE is not None, 'Byte Rate is not found.'

        # 最後に取得した packetize 済み PAT / PMT パケット
        latest_pat_packets: list[bytes] = []
        latest_pmt_packets: list[bytes] = []
        pat_continuity_counter: int = 0
        pmt_continuity_counter: int = 0

        # 最後に取得した PES ヘッダーとその PID
        latest_pes_header: PES | None = None
        latest_pes_header_pid: int | None = None

        # 現在処理中のセグメントのインデックス (HLS セグメントのシーケンス番号と一致する)
        ## self.video_stream.segments[monotonic_segment_index] が処理中のセグメントになる
        ## PTS がある PES パケットではこの値に関わらず PTS レンジに一致するセグメントに TS パケットが投入されるが、
        ## PTS のない TS パケットは単体では基準となるタイムスタンプを持たないため、この値をもとにセグメントを切り替える
        ## この値は映像 PES の PTS がセグメントの切り出し開始 PTS と一致した時のみ、単調増加する (要はセグメントの最初のキーフレームが出てきたタイミングで区切る)
        ## OpenGOP など一部 TS ではこの値がカウントアップした後に前のセグメント用のフレームが出てくることもあるが、その場合でも値が減ることはない
        monotonic_segment_index: int = -99999  # -99999 は初期値で、この値のときは TS パケットの投入は行われない

        # 取得した概算バイトレートをもとに、指定された開始タイムスタンプに近い位置までシークする
        # 余裕を持ってエンコードを開始する HLS セグメントのファイル上の位置 - 5 秒分の位置にシークする
        with open(self.recorded_video.file_path, 'rb') as reader:
            seek_offset_bytes = int(max(0, self.video_stream.segments[first_segment_index].start_file_position - (5 * BYTE_RATE)))
            reader.seek(seek_offset_bytes, os.SEEK_SET)
            Logging.info(f'[Video: {self.video_stream.video_stream_id}] Seeked to {seek_offset_bytes} bytes.')

            while True:

                # 同期バイトを探す
                isEOF = False
                while True:
                    sync_byte: bytes = reader.read(1)
                    if sync_byte == ts.SYNC_BYTE:
                        break
                    elif sync_byte == b'':
                        # ファイルの終端に達した場合はループを抜けて終了する
                        isEOF = True
                        Logging.info(f'[Video: {self.video_stream.video_stream_id}] Reached end of file.')
                        break

                # ファイルの終端に達した場合はループを抜けて終了する
                if isEOF is True:
                    break

                # 速度向上のため 188 * 10000 バイトのチャンクで一気に読み込んだ後、188 バイトごとの TS パケットに分割して処理する
                chunk = ts.SYNC_BYTE + reader.read((ts.PACKET_SIZE * 10000) - 1)
                for ts_packet in [chunk[i:i + ts.PACKET_SIZE] for i in range(0, len(chunk), ts.PACKET_SIZE)]:
                    if len(ts_packet) != ts.PACKET_SIZE:
                        Logging.error(f'[Video: {self.video_stream.video_stream_id}] Packet size is not 188 bytes.')
                        continue

                    # TS パケットの PID を取得する
                    PID = ts.pid(ts_packet)

                    # PES かつ PES パケットヘッダがあれば取得する
                    ## payload_unit_start_indicator フラグは PSI/SI でも使われているので、PES パケットの PID かを確認している
                    pes_header: PES | None = None
                    if PID in PES_PIDS and ts.payload_unit_start_indicator(ts_packet) is True:
                        pes_header = PES(ts.payload(ts_packet))

                    # PAT: Program Association Table
                    if PID == PAT_PID:
                        pat_parser.push(ts_packet)
                        for PAT in pat_parser:
                            if PAT.CRC32() != 0:
                                continue
                            for program_number, program_map_PID in PAT:
                                if program_number == 0:
                                    continue

                                # PMT の PID を取得する
                                ## この時点ではすでに取得されているはずだが、PMT の PID が録画データの途中で変更されている場合に備える
                                if program_number == SERVICE_ID:
                                    PMT_PID = program_map_PID
                                elif not SERVICE_ID:
                                    PMT_PID = program_map_PID
                                    break  # 先頭の PMT の PID のみ取得する

                            # PAT をパケット化して投入 (処理中のセグメントのエンコードが完了していない場合のみ)
                            ## monotonic_segment_index が初期値のときは TS パケットの投入は行われない
                            pat_packets = packetize_section(PAT, False, False, PAT_PID, 0, pat_continuity_counter)
                            pat_continuity_counter = (pat_continuity_counter + len(pat_packets)) & 0x0F  # Continuity Counter を更新
                            if monotonic_segment_index >= 0 and self.video_stream.segments[monotonic_segment_index].encode_status != 'Completed':
                                for pat_packet in pat_packets:
                                    self.video_stream.segments[monotonic_segment_index].segment_ts_packet_queue.put(pat_packet)
                            # 最新のパケット化済み PAT を保持する
                            ## エンコーダーに投入したかに関わらず常に保持する必要がある
                            latest_pat_packets = pat_packets

                    # PMT: Program Map Table
                    elif PID == PMT_PID:
                        pmt_parser.push(ts_packet)
                        for PMT in pmt_parser:
                            if PMT.CRC32() != 0:
                                continue
                            PCR_PID = PMT.PCR_PID

                            ## この時点では PID 類はすでに取得されているはずだが、各ストリームの PID が録画データの途中で変更されている場合に備える
                            PES_PIDS.clear()  # 前の PMT から取得した PES パケットの PID をクリアする
                            is_video_pid_found = False
                            is_primary_audio_pid_found = False
                            is_secondary_audio_pid_found = False
                            for stream_type, elementary_PID, _ in PMT:

                                # PMT に記載されているのはすべて PES パケットの PID
                                PES_PIDS.append(elementary_PID)

                                # 映像ストリームの PID を取得する
                                ## PMT のうち、常に最初に出現する映像ストリームの PID を取得する
                                if not is_video_pid_found:
                                    if stream_type == 0x02:
                                        if VIDEO_PID != elementary_PID:
                                            Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}] MPEG-2 PID: 0x{elementary_PID:04x}')
                                        VIDEO_PID = elementary_PID
                                        is_video_pid_found = True
                                    elif stream_type == 0x1b:
                                        if VIDEO_PID != elementary_PID:
                                            Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}] H.264 PID: 0x{elementary_PID:04x}')
                                        VIDEO_PID = elementary_PID
                                        is_video_pid_found = True
                                    elif stream_type == 0x24:
                                        if VIDEO_PID != elementary_PID:
                                            Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}] H.265 PID: 0x{elementary_PID:04x}')
                                        VIDEO_PID = elementary_PID
                                        is_video_pid_found = True
                                # 主音声ストリームの PID を取得する
                                if not is_primary_audio_pid_found:
                                    if stream_type == 0x0f:
                                        if PRIMARY_AUDIO_PID != elementary_PID:
                                            Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}] Primary AAC PID: 0x{elementary_PID:04x}')
                                        PRIMARY_AUDIO_PID = elementary_PID
                                        is_primary_audio_pid_found = True
                                # 副音声ストリームの PID を取得する
                                ## 主音声ストリームが見つかった後のみ取得する
                                elif not is_secondary_audio_pid_found:
                                    if stream_type == 0x0f:
                                        if SECONDARY_AUDIO_PID != elementary_PID:
                                            Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}] Secondary AAC PID: 0x{elementary_PID:04x}')
                                        SECONDARY_AUDIO_PID = elementary_PID
                                        is_secondary_audio_pid_found = True

                            # PMT をパケット化して投入 (処理中のセグメントのエンコードが完了していない場合のみ)
                            ## monotonic_segment_index が初期値のときは TS パケットの投入は行われない
                            pmt_packets = packetize_section(PMT, False, False, PMT_PID, 0, pmt_continuity_counter)
                            pmt_continuity_counter = (pmt_continuity_counter + len(pmt_packets)) & 0x0F  # Continuity Counter を更新
                            if monotonic_segment_index >= 0 and self.video_stream.segments[monotonic_segment_index].encode_status != 'Completed':
                                for pmt_packet in pmt_packets:
                                    self.video_stream.segments[monotonic_segment_index].segment_ts_packet_queue.put(pmt_packet)
                            # 最新のパケット化済み PMT を保持する
                            ## エンコーダーに投入したかに関わらず常に保持する必要がある
                            latest_pmt_packets = pmt_packets

                    # ヘッダ付きの先頭の PES パケット (映像・音声・字幕・メタデータ) かつ PTS が含まれている場合
                    elif PID in PES_PIDS and pes_header is not None and pes_header.has_pts() is True:

                        # 今回取得した PES ヘッダーを保持する
                        latest_pes_header = pes_header
                        latest_pes_header_pid = PID

                        # インデックスが first_segment_index 以降のセグメントの中から、
                        # 開始 PTS 〜 終了 PTS のレンジに一致するセグメントが持つ Queue に TS パケットを投入する
                        ## TS は OpenGOP や送出タイミング (音声は映像より先行して送出されることが多い) の関係で
                        ## 特定のファイル位置以前と以降の境目ではきれいに分割することができないため、
                        ## 送出順 (符号化順) に関わらず PTS を基準に投入先のセグメントを振り分ける
                        for segment in self.video_stream.segments[first_segment_index:]:

                            # 現在の PES パケットの PTS を取得する
                            current_pts = pes_header.pts()
                            assert current_pts is not None

                            # PTS がレンジ内にあれば
                            if segment.start_pts <= current_pts <= segment.end_pts:

                                # この時点で前のセグメントのエンコードが終わっておらず、かつ現在の PTS が切り出し終了 PTS から 3 秒以上が経過している場合、
                                # もう前のセグメントに該当するパケットは降ってこないだろうと判断し、もう投入するパケットがないことをエンコーダーに通知する
                                ## これで tsreadex の標準入力が閉じられ、エンコードが完了する
                                if (segment.sequence_index - 1 >= 0) and \
                                   (self.video_stream.segments[segment.sequence_index - 1].encode_status != 'Completed') and \
                                   (current_pts - self.video_stream.segments[segment.sequence_index - 1].end_pts >= 3 * ts.HZ):
                                    self.video_stream.segments[segment.sequence_index - 1].segment_ts_packet_queue.put(None)

                                    # もう投入するパケットがないことを通知したので、エンコーダーの終了を待つ (重要)
                                    ## ファイルの読み取りよりエンコードの方が基本的に遅いので、前のセグメントのエンコード中に次のエンコードを開始しないようにする
                                    if self._encoder_process is not None:
                                        Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}][Segment {segment.sequence_index - 1}]'
                                                             f' Waiting for {ENCODER_TYPE} process to exit...')
                                        self._encoder_process.wait()

                                    # 待機後にエンコードタスクがキャンセルされた場合、処理を中断してエンコードタスクを終了する
                                    if self._is_cancelled is True:
                                        return  # メソッドの実行自体を終了する

                                # 当該セグメントのエンコードがすでに完了している場合は何もしない
                                ## 中間に数個だけ既にエンコードされているセグメントがあるケースでは、
                                ## それらのエンコード完了済みセグメントの切り出し&エンコード処理をスキップして次のセグメントに進むことになる
                                if segment.encode_status == 'Completed':
                                    break

                                # 当該セグメントの PTS レンジに一致する最初のパケットのみ、Queue への投入前に非同期でエンコーダーを起動する
                                if segment.is_started is False:

                                    # バックグラウンドでエンコーダーを起動する
                                    ## 実際にエンコーダーが起動するタイミングは前のセグメントのエンコーダーが終了した後になる
                                    Logging.info(f'[Video: {self.video_stream.video_stream_id}] Switched to next segment: {segment.sequence_index}')
                                    Logging.info(f'[Video: {self.video_stream.video_stream_id}][Segment {segment.sequence_index}] '
                                        f'Start: {(segment.start_pts - self.video_stream.segments[0].start_pts) / ts.HZ:.3f} / '
                                        f'End: {((segment.start_pts - self.video_stream.segments[0].start_pts) / ts.HZ) + segment.duration_seconds:.3f}')
                                    threading.Thread(target=self.__runEncoder, args=(segment,), daemon=True).start()

                                    # 前回取得した最新の PAT / PMT を投入する
                                    ## エンコーダーは最初の PAT / PMT より前のデータをデコードできないため、最初のパケットを投入する前に入れておく必要がある
                                    for pat_packet in latest_pat_packets:
                                        segment.segment_ts_packet_queue.put(pat_packet)
                                    for pmt_packet in latest_pmt_packets:
                                        segment.segment_ts_packet_queue.put(pmt_packet)

                                    # このタイミングで monotonic_segment_index が初期値の場合のみ、
                                    # PTS が存在しないパケットがどのセグメントに TS パケットを投入すれば良いかのインデックスを切り替える
                                    ## 通常は映像パケットの PTS がセグメントの開始 PTS と一致した時にキーフレームの境目で切り替えるが、
                                    ## 音声が映像より先行して送出されている場合もあるので、処理対象の最初のセグメントに到達した時点で切り替える
                                    if monotonic_segment_index < 0:
                                        monotonic_segment_index = segment.sequence_index

                                    # セグメントの開始フラグを立てる
                                    segment.is_started = True

                                # 映像パケットかつ PTS がセグメントの開始 PTS と完全に一致した場合
                                # PTS が存在しないパケットがどのセグメントに TS パケットを投入すれば良いかのインデックスを切り替える
                                ## OpenGOP など一部 TS ではこの値がカウントアップした後に前のセグメント用のフレームが出てくることもあるが、
                                ## インデックスは単調増加のため一度カウントアップしたらカウントが減ることはない
                                if PID == VIDEO_PID and segment.start_pts == current_pts and monotonic_segment_index < segment.sequence_index:
                                    monotonic_segment_index = segment.sequence_index

                                # ここで Queue に投入したパケットがそのまま tsreadex → エンコーダーに投入される
                                ## セグメント間で PTS レンジが重複することはないので、最初に一致したセグメントの Queue だけ処理すればよい
                                segment.segment_ts_packet_queue.put(ts_packet)
                                break

                    # ヘッダなしの続きの PES パケット (映像・音声・字幕・メタデータ) かつ、PID が一致する前回取得した PES ヘッダに PTS が含まれている場合
                    ## PES は当然ほとんどの場合 188 バイトには収まりきらないので、複数の TS パケットに分割されている
                    ## PES ヘッダは分割された PES の最初の TS パケットにのみ含まれる (はず)
                    elif PID in PES_PIDS and pes_header is None and \
                         PID == latest_pes_header_pid and latest_pes_header is not None and latest_pes_header.has_pts() is True:

                        # インデックスが first_segment_index 以降のセグメントの中から、
                        # 開始 PTS 〜 終了 PTS のレンジに一致するセグメントが持つ Queue に TS パケットを投入する
                        ## TS は OpenGOP や送出タイミング (音声は映像より先行して送出されることが多い) の関係で
                        ## 特定のファイル位置以前と以降の境目ではきれいに分割することができないため、
                        ## 送出順 (符号化順) に関わらず PTS を基準に投入先のセグメントを振り分ける
                        for segment in self.video_stream.segments[first_segment_index:]:

                            # 現在の PES パケットの PTS を前回取得した PES ヘッダから取得する
                            current_pts = latest_pes_header.pts()
                            assert current_pts is not None

                            # PTS がレンジ内にあれば
                            if segment.start_pts <= current_pts <= segment.end_pts:

                                # ここで Queue に投入したパケットがそのまま tsreadex → エンコーダーに投入される
                                ## セグメント間で PTS レンジが重複することはないので、最初に一致したセグメントの Queue だけ処理すればよい
                                segment.segment_ts_packet_queue.put(ts_packet)
                                break

                    # PSI/SI などのセクションパケットの場合
                    ## PAT / PMT は別途投入済みなのでここには含まれない
                    else:

                        # monotonic_segment_index が正の値である (初期値でない) ことを確認する
                        if monotonic_segment_index >= 0:

                            # 当該セグメントのエンコードが完了していない場合のみ、TS パケットを投入する
                            ## 中間に数個だけ既にエンコードされているセグメントがあるケースでは、
                            ## それらのエンコード完了済みセグメントの切り出し&エンコード処理をスキップして次のセグメントに進むことになる
                            if self.video_stream.segments[monotonic_segment_index].encode_status != 'Completed':
                                self.video_stream.segments[monotonic_segment_index].segment_ts_packet_queue.put(ts_packet)

                    # 途中でエンコードタスクがキャンセルされた場合、処理中のセグメントがあるかに関わらずエンコードタスクを終了する
                    # このとき、エンコーダーの出力はエンコードの完了を待つことなく破棄され、セグメントは処理開始前の状態にリセットされる
                    if self._is_cancelled is True:
                        return  # メソッドの実行自体を終了する

        # エンコードタスクでのすべての処理を完了した
        self._is_finished = True
        Logging.info(f'[Video: {self.video_stream.video_stream_id}] VideoEncodingTask finished.')


    async def run(self, first_segment_index: int) -> None:
        """
        HLS エンコードタスクを実行する
        実際は asyncio.to_thread で別スレッドで実行される

        Args:
            first_segment_index (int): エンコードを開始する HLS セグメントのインデックス (HLS セグメントのシーケンス番号と一致する)
        """

        await asyncio.to_thread(self.__run, first_segment_index)


    async def cancel(self) -> None:
        """
        起動中のエンコードタスクをキャンセルし、起動中の外部プロセスを終了する
        """

        # すでにエンコードタスクが完了している場合は何もしない
        if self._is_finished is True:
            Logging.info(f'[Video: {self.video_stream.video_stream_id}] VideoEncodingTask is already finished.')
            return

        if self._is_cancelled is False:

            # エンコードタスクがキャンセルされたことを示すフラグを立てる
            ## この時点でまだ run() やエンコーダーが実行中であれば、run() やエンコーダーはこのフラグを見て自ら終了する
            ## できるだけ早い段階でフラグを立てておくことが重要
            self._is_cancelled = True

            # tsreadex とエンコーダーのプロセスを強制終了する
            Logging.info(f'[Video: {self.video_stream.video_stream_id}] VideoEncodingTask cancelling...')
            self.__terminateEncoder()

            # 完全に終了するまで待機する
            while self._is_finished is False:
                await asyncio.sleep(0.1)

            Logging.info(f'[Video: {self.video_stream.video_stream_id}] VideoEncodingTask cancelled.')
