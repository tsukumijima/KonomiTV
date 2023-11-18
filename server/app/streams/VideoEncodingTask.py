
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import asyncio
import aiofiles
import os
from biim.mpeg2ts import ts
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
    SEGMENT_DURATION_SECOND: ClassVar[float] = float(10)  # 10秒

    # エンコード後のストリームの GOP 長 (秒)
    ## LiveEncodingTask と異なりライブではないため、GOP 長は H.264 / H.265 共通で長めに設定する
    GOP_LENGTH_SECOND: ClassVar[float] = float(2.5)  # 2.5秒


    def __init__(self, video_stream: VideoStream) -> None:
        """
        VideoStream のインスタンスに基づくビデオエンコードタスクを初期化する

        Args:
            video_stream (VideoStream): VideoStream のインスタンス
        """

        # ビデオストリームのインスタンスをセット
        self.video_stream = video_stream

        # tsreadex とエンコーダーのプロセス
        self._tsreadex_process: asyncio.subprocess.Process | None = None
        self._encoder_process: asyncio.subprocess.Process | None = None

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
        start_offset_timestamp: float,
    ) -> list[str]:
        """
        FFmpeg に渡すオプションを組み立てる

        Args:
            quality (QUALITY_TYPES): 映像の品質
            start_offset_timestamp (float): セグメントの開始タイムスタンプ (録画データの先頭からの経過秒数)

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
        ## 副音声が検出できない場合にエラーにならないよう、? をつけておく
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
        options.append(f'-output_ts_offset {start_offset_timestamp}')

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
        start_offset_timestamp: float,
    ) -> list[str]:
        """
        QSVEncC・NVEncC・VCEEncC・rkmppenc (便宜上 HWEncC と総称) に渡すオプションを組み立てる

        Args:
            quality (QUALITY_TYPES): 映像の品質
            encoder_type (Literal['QSVEncC', 'NVEncC', 'VCEEncC', 'rkmppenc']): エンコーダー (QSVEncC or NVEncC or VCEEncC or rkmppenc)
            start_offset_timestamp (float): セグメントの開始タイムスタンプ (録画データの先頭からの経過秒数)

        Returns:
            list[str]: HWEncC に渡すオプションが連なる配列
        """

        # オプションの入る配列
        options: list[str] = []

        # 入力
        ## --input-probesize, --input-analyze をつけることで、ストリームの分析時間を短縮できる
        ## 両方つけるのが重要で、--input-analyze だけだとエンコーダーがフリーズすることがある
        options.append('--input-format mpegts --fps 30000/1001 --input-probesize 1000K --input-analyze 0.7 --input -')
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
        ## その他の設定
        options.append('--log-level debug')

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

        # 音声
        options.append(f'--audio-codec aac:aac_coder=twoloop --audio-bitrate {QUALITY[quality].audio_bitrate}')
        options.append('--audio-samplerate 48000 --audio-filter volume=2.0 --audio-ignore-decode-error 30')

        # 出力するセグメント TS のタイムスタンプのオフセット
        # タイムスタンプが前回エンコードしたセグメントの続きになるようにする
        options.append(f'-m output_ts_offset:{start_offset_timestamp}')

        # 出力
        options.append('--output-format mpegts')  # MPEG-TS 出力ということを明示
        options.append('--output -')  # 標準入力へ出力

        # オプションをスペースで区切って配列にする
        result: list[str] = []
        for option in options:
            result += option.split(' ')

        return result


    async def __runEncoder(self, segment: VideoStreamSegment) -> bool:
        """
        録画 TS データから直接切り出した生の MPEG-TS チャンクをエンコードするエンコーダープロセスを開始し、
        エンコード済みのセグメントデータを VideoStreamSegment に書き込む
        チャンクの投入は別途 self.__pushTSPacketDataToEncoder() で行う必要がある

        このメソッドはエンコードが完了するか、エンコードに失敗するか、エンコードタスクがキャンセルされるまで戻らない
        このメソッドを並列に実行してはならない

        Args:
            start_offset_timestamp (float): セグメントの開始タイムスタンプ (録画データの先頭からの経過秒数)

        Returns:
            bool: 最終的にエンコードが成功したかどうか
        """

        # まだエンコーダーが起動している場合はエラー
        assert self._tsreadex_process is None, 'tsreadex process is already running.'
        assert self._encoder_process is None, 'encoder process is already running.'

        # 処理対象の VideoStreamSegment をエンコード中に設定
        segment.is_encode_processing = True

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

        # tsreadex の読み込み用パイプと書き込み用パイプを作成
        tsreadex_read_pipe, tsreadex_write_pipe = os.pipe()

        # tsreadex のプロセスを非同期で作成・実行
        self._tsreadex_process = await asyncio.subprocess.create_subprocess_exec(
            *[LIBRARY_PATH['tsreadex'], *tsreadex_options],
            stdin = asyncio.subprocess.PIPE,  # 録画 TS データから直接切り出した生の MPEG-TS チャンクを書き込む
            stdout = tsreadex_write_pipe,  # エンコーダーに繋ぐ
            stderr = asyncio.subprocess.DEVNULL,  # 利用しない
        )

        # tsreadex の書き込み用パイプを閉じる
        os.close(tsreadex_write_pipe)

        # ***** エンコーダープロセスの作成と実行 *****

        # エンコーダーの種類を取得
        encoder_type = Config().general.encoder
        encoder_type = 'FFmpeg'  # 当面固定

        # FFmpeg
        if encoder_type == 'FFmpeg':

            # オプションを取得
            encoder_options = self.buildFFmpegOptions(self.video_stream.quality, segment.start_offset_timestamp)
            Logging.info(f'[Video: {self.video_stream.video_stream_id}] FFmpeg Commands:\nffmpeg {" ".join(encoder_options)}')

            # エンコーダープロセスを非同期で作成・実行
            self._encoder_process = await asyncio.subprocess.create_subprocess_exec(
                *[LIBRARY_PATH['FFmpeg'], *encoder_options],
                stdin = tsreadex_read_pipe,  # tsreadex からの入力
                stdout = asyncio.subprocess.PIPE,  # ストリーム出力
                # stderr = None,  # デバッグ用で当面そのまま出力する
                stderr = asyncio.subprocess.DEVNULL,
            )

        # HWEncC
        else:

            # オプションを取得
            encoder_options = self.buildHWEncCOptions(self.video_stream.quality, encoder_type, segment.start_offset_timestamp)
            Logging.info(f'[Video: {self.video_stream.video_stream_id}] {encoder_type} Commands:\n{encoder_type} {" ".join(encoder_options)}')

            # エンコーダープロセスを非同期で作成・実行
            self._encoder_process = await asyncio.subprocess.create_subprocess_exec(
                *[LIBRARY_PATH[encoder_type], *encoder_options],
                stdin = tsreadex_read_pipe,  # tsreadex からの入力
                stdout = asyncio.subprocess.PIPE,  # ストリーム出力
                # stderr = None,  # デバッグ用で当面そのまま出力する
                stderr = asyncio.subprocess.DEVNULL,
            )

        # tsreadex の読み込み用パイプを閉じる
        os.close(tsreadex_read_pipe)

        # ***** エンコーダーの出力の読み取り *****

        assert self._tsreadex_process.returncode is None, f'tsreadex exited with exit code {self._tsreadex_process.returncode}.'
        assert self._encoder_process.returncode is None, f'{encoder_type} exited with exit code {self._encoder_process.returncode}.'

        # エンコーダーが完了するまで待機し、エンコード済みのセグメントデータを取得する
        assert self._encoder_process.stdout is not None
        segment_ts = await self._encoder_process.stdout.read()

        # この時点でエンコードタスクがキャンセルされていればエンコード済みのセグメントデータを放棄して中断する
        if self._is_cancelled is True:
            Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}] Discarded encoded segment data because VideoEncodingTask is cancelled.')
            self.__terminateEncoder()
            return False

        # この時点でエンコーダーの exit code が 0 か None (まだプロセスが起動している) でなければ何らかの理由でエンコードに失敗している
        if self._encoder_process.returncode != 0 and self._encoder_process.returncode is not None:
            Logging.error(f'[Video: {self.video_stream.video_stream_id}] {encoder_type} exited with non-zero exit code.')
            self.__terminateEncoder()
            return False

        # この時点で tsreadex とエンコーダーは終了しているはずだが、念のため強制終了しておく
        # 上記の判定を行った後に行うのが重要 (kill すると exit code が 0 以外になる可能性があるため)
        self.__terminateEncoder()

        # 処理対象の VideoStreamSegment をエンコード完了に設定
        segment.is_encode_processing = False

        # エンコード後のセグメントデータを VideoStreamSegment に書き込む
        # ここで設定したエンコード済みのセグメントデータが API で返される
        assert segment.segment_ts_future.done() is False  # すでに完了しているはずはない
        segment.segment_ts_future.set_result(segment_ts)
        return True


    async def __pushTSPacketDataToEncoder(self, packet: bytes | None) -> None:
        """
        録画 TS データから直接切り出した生の MPEG-TS セグメントのチャンクをエンコーダー (正確にはその前段にある tsreadex) に投入する
        188 bytes ぴったりで送信する必要はない (が、運用上常に 188 bytes ぴったりになっている)
        これ以上エンコーダーに投入するパケットがなくなったら (エンコーダーを終了させたくなったら) None を渡す

        Args:
            packet (bytes): MPEG2-TS パケット or これ以上エンコーダーに投入するパケットがない場合は None
        """

        # まだエンコーダープロセスが起動していない場合は起動するまで待機する
        while self._tsreadex_process is None or self._encoder_process is None:
            await asyncio.sleep(0.01)

        # これ以上エンコーダーに投入するパケットがない場合は tsreadex の標準入力を閉じる
        assert self._tsreadex_process.stdin is not None
        if packet is None:
            self._tsreadex_process.stdin.close()
            return

        # tsreadex に TS パケットを送信する
        self._tsreadex_process.stdin.write(packet)
        await self._tsreadex_process.stdin.drain()


    def __terminateEncoder(self) -> None:
        """
        起動中のエンコーダープロセスを強制終了する
        """

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


    async def run(self, first_segment_index: int) -> None:
        """
        HLS エンコードタスクを実行する
        biim の実装をかなり参考にした
        TODO: 現状 PCR や PTS が一周した時の処理は何も考えてない
        ref: https://github.com/monyone/biim/blob/other/static-ondemand-hls/seekable.py
        ref: https://github.com/monyone/biim/blob/other/static-ondemand-hls/vod_main.py
        ref: https://github.com/monyone/biim/blob/other/static-ondemand-hls/vod_fmp4.py

        Args:
            first_segment_index (int): エンコードを開始する HLS セグメントのインデックス (HLS セグメントのシーケンス番号と一致する)
        """

        # first_segment_index が self.video_stream.segments の範囲外
        if first_segment_index < 0 or first_segment_index >= len(self.video_stream.segments):
            assert False, f'first_segment_index ({first_segment_index}) is out of range, allowed range is 0 to {len(self.video_stream.segments) - 1}.'

        # すでにキャンセルされている
        if self._is_cancelled is True:
            assert False, 'VideoEncodingTask is already cancelled.'

        Logging.info(f'[Video: {self.video_stream.video_stream_id}] VideoEncodingTask started.')

        # 視聴対象の録画番組が放送されたチャンネルのサービス ID
        SERVICE_ID: int | None = self.recorded_program.channel.service_id if self.recorded_program.channel is not None else None

        # 各 MPEG-TS パケットの PID
        PAT_PID: int = 0x00
        PMT_PID: int | None = None
        PCR_PID: int | None = None
        MPEG2_PID: int | None = None
        H264_PID: int | None = None
        H265_PID: int | None = None

        # 映像ストリームの概算バイトレート
        BYTE_RATE: float | None = None

        # 映像ストリームの最初の DTS
        FIRST_DTS: int | None = None

        # PAT / PMT パーサー
        pat_parser: SectionParser[PATSection] = SectionParser(PATSection)
        pmt_parser: SectionParser[PMTSection] = SectionParser(PMTSection)

        # 事前に当該 MPEG-TS 内の各トラックの PID とシーク時用のバイトレート (B/s) を概算する
        latest_pcr_value: int | None = None  # 前回の PCR 値
        latest_pcr_ts_packet_bytes: int | None = None  # 最初の PCR 値を取得してから読み取った TS パケットの累計バイト数
        pcr_remain_count: int = 30  # 30 回分の PCR 値を取得する (PCR を取得するたびに 1 減らす)
        async with aiofiles.open(self.recorded_video.file_path, 'rb') as reader:
            while True:
                while True:
                    sync_byte = await reader.read(1)
                    if sync_byte == ts.SYNC_BYTE:
                        break
                    elif sync_byte == b'':
                        assert False, 'Invalid TS file.'

                # 1つずつ TS パケットを読み込む
                packet = ts.SYNC_BYTE + await reader.read(ts.PACKET_SIZE - 1)
                if len(packet) != ts.PACKET_SIZE:
                    assert False, 'Invalid TS file. Packet size is not 188 bytes.'

                # TS パケットの PID を取得する
                PID = ts.pid(packet)

                # PAT: Program Association Table
                if PID == PAT_PID:
                    pat_parser.push(packet)
                    for PAT in pat_parser:
                        if PAT.CRC32() != 0:
                            continue
                        for program_number, program_map_PID in PAT:
                            if program_number == 0:
                                continue
                            # PMT の PID を取得する
                            if program_number == SERVICE_ID:
                                PMT_PID = program_map_PID
                            elif not PMT_PID and not SERVICE_ID:
                                PMT_PID = program_map_PID

                # PMT: Program Map Table
                elif PID == PMT_PID:
                    pmt_parser.push(packet)
                    for PMT in pmt_parser:
                        if PMT.CRC32() != 0:
                            continue
                        PCR_PID = PMT.PCR_PID
                        # 映像ストリームの PID を取得する
                        for stream_type, elementary_PID, _ in PMT:
                            if stream_type == 0x02:
                                if MPEG2_PID is None:
                                    Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}] MPEG-2 PID: 0x{elementary_PID:04x}')
                                MPEG2_PID = elementary_PID
                            elif stream_type == 0x1b:
                                if H264_PID is None:
                                    Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}] H.264 PID: 0x{elementary_PID:04x}')
                                H264_PID = elementary_PID
                            elif stream_type == 0x24:
                                if H265_PID is None:
                                    Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}] H.265 PID: 0x{elementary_PID:04x}')
                                H265_PID = elementary_PID

                # PCR: Program Clock Reference
                elif PID == PCR_PID and ts.has_pcr(packet):
                    if latest_pcr_value is None:
                        # 最初の PCR 値を取得する
                        latest_pcr_value = cast(int, ts.pcr(packet))
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
                                ((cast(int, ts.pcr(packet)) - latest_pcr_value + ts.PCR_CYCLE) % ts.PCR_CYCLE)
                            )
                            assert BYTE_RATE is not None
                            Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}] Approximate Bitrate: {(BYTE_RATE / 1024 / 1024 * 8):.3f} Mbps')

                # 最初の PCR 値を取得してから読み取った TS パケットの累計バイト数を更新する
                # 最初の PCR 値が取得されるまではカウントしない
                if latest_pcr_ts_packet_bytes is not None:
                    latest_pcr_ts_packet_bytes += ts.PACKET_SIZE

                # 各 PID と概算バイトレートの両方が取得できたらループを抜ける
                if (PMT_PID is not None) and \
                   (PCR_PID is not None) and \
                   (MPEG2_PID is not None or H264_PID is not None or H265_PID is not None) and \
                   (BYTE_RATE is not None):
                    break

        assert BYTE_RATE is not None, 'Byte Rate is not found.'

        # 次に、映像ストリーム (MPEG-2 or H.264 or H.265) の最初の DTS を取得する
        ## 上のループで一緒にやってしまうとまだ映像ストリームの PID が取得できていない頃のパケットを読み飛ばしてしまうので、あえて別のループにしている
        async with aiofiles.open(self.recorded_video.file_path, 'rb') as reader:
            while True:
                while True:
                    sync_byte = await reader.read(1)
                    if sync_byte == ts.SYNC_BYTE:
                        break
                    elif sync_byte == b'':
                        assert False, 'Invalid TS file.'

                # 1つずつ TS パケットを読み込む
                packet = ts.SYNC_BYTE + await reader.read(ts.PACKET_SIZE - 1)
                if len(packet) != ts.PACKET_SIZE:
                    assert False, 'Invalid TS file. Packet size is not 188 bytes.'

                # TS パケットの PID を取得する
                PID = ts.pid(packet)

                # 映像ストリーム (MPEG-2 or H.264 or H.265) の最初の DTS を取得する
                if PID == MPEG2_PID or PID == H264_PID or PID == H265_PID:
                    if ts.payload_unit_start_indicator(packet):
                        mpeg2_or_h264_or_h265 = PES(ts.payload(packet))
                        dts_or_pts = cast(int, mpeg2_or_h264_or_h265.dts() if mpeg2_or_h264_or_h265.has_dts() else mpeg2_or_h264_or_h265.pts())
                        FIRST_DTS = dts_or_pts
                        Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}] First DTS (Seconds): {FIRST_DTS / ts.HZ}')
                        break

        assert FIRST_DTS is not None, 'First DTS is not found.'

        # 現在シーク (大雑把にシークした後、実際の出力開始位置まで録画データを細かく読み出して調整する) 処理中かどうか
        is_seeking = True

        # 現在処理中のセグメントのインデックス (HLS セグメントのシーケンス番号と一致する)
        ## self.video_stream.segments[segment_index] が処理中のセグメントになる
        ## 初回は first_segment_index に 1 引いた値をセットする
        segment_index: int = first_segment_index - 1

        # 現在処理中のセグメントのバイト数カウント
        segment_bytes_count: int = 0

        # 現在処理中のセグメントのエンコーダープロセスが完了するまでの待機タスク
        ## このタスクが完了するまで次のセグメントのエンコードを開始してはならない (エンコーダーを並列実行してはならない)
        segment_encoding_task: asyncio.Task[bool] | None = None

        # 取得した概算バイトレートをもとに、指定された開始タイムスタンプに近い位置までシークする
        # バイトレートの変動が激しい場合はぴったりシークできるとは限らないので、指定された開始タイムスタンプの 30 秒から読み取りを開始する
        async with aiofiles.open(self.recorded_video.file_path, 'rb') as reader:
            seek_offset_second = max(0, self.video_stream.segments[first_segment_index].start_offset_timestamp - 30)
            await reader.seek(int(seek_offset_second * BYTE_RATE))
            Logging.info(f'[Video: {self.video_stream.video_stream_id}] Seeked to roughly {seek_offset_second} seconds.')

            while True:
                while True:
                    sync_byte = await reader.read(1)
                    if sync_byte == ts.SYNC_BYTE:
                        break
                    elif sync_byte == b'':
                        assert False, 'Invalid TS file.'

                # 1つずつ TS パケットを読み込む
                packet = ts.SYNC_BYTE + await reader.read(ts.PACKET_SIZE - 1)
                if len(packet) != ts.PACKET_SIZE:
                    assert False, 'Invalid TS file. Packet size is not 188 bytes.'

                # TS パケットの PID を取得する
                PID = ts.pid(packet)

                # PAT: Program Association Table
                if PID == PAT_PID:
                    pat_parser.push(packet)
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
                            elif not PMT_PID and not SERVICE_ID:
                                PMT_PID = program_map_PID

                # PMT: Program Map Table
                elif PID == PMT_PID:
                    pmt_parser.push(packet)
                    for PMT in pmt_parser:
                        if PMT.CRC32() != 0:
                            continue
                        PCR_PID = PMT.PCR_PID
                        # 映像ストリームの PID を取得する
                        ## この時点ではすでに取得されているはずだが、映像ストリームの PID が録画データの途中で変更されている場合に備える
                        for stream_type, elementary_PID, _ in PMT:
                            if stream_type == 0x02:
                                MPEG2_PID = elementary_PID
                            elif stream_type == 0x1b:
                                H264_PID = elementary_PID
                            elif stream_type == 0x24:
                                H265_PID = elementary_PID

                # 映像ストリーム (MPEG-2 or H.264 or H.265)
                elif PID == MPEG2_PID or PID == H264_PID or PID == H265_PID:
                    if ts.payload_unit_start_indicator(packet):
                        mpeg2_or_h264_or_h265 = PES(ts.payload(packet))
                        dts_or_pts = cast(int, mpeg2_or_h264_or_h265.dts() if mpeg2_or_h264_or_h265.has_dts() else mpeg2_or_h264_or_h265.pts())

                        # 映像ストリームの最初の DTS (≒ 録画データの先頭) からの経過秒数を算出する
                        current_relative_timestamp = (dts_or_pts - FIRST_DTS) / ts.HZ

                        # 録画データの先頭からの経過秒数が次のセグメントの開始タイムスタンプよりも大きい場合
                        # まだシーク中だった場合はシークを完了し、次のセグメントに切り替えてエンコードを開始する
                        if current_relative_timestamp >= self.video_stream.segments[segment_index + 1].start_offset_timestamp:

                            if is_seeking is True:
                                # ここを通った時点で確実に first_segment_index のセグメントまでのシークが完了している
                                is_seeking = False
                                Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}] '
                                                    f'Current DTS (Seconds): {dts_or_pts / ts.HZ}')
                                Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}] '
                                                    f'Current Relative Timestamp: {current_relative_timestamp}')
                                Logging.info(f'[Video: {self.video_stream.video_stream_id}] Seeked to {current_relative_timestamp} seconds.')
                            else:
                                # ここを通った時点で前のセグメントの切り出しが完了している
                                Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}][Segment {segment_index}] '
                                                    f'Current DTS (Seconds): {dts_or_pts / ts.HZ}')
                                Logging.debug_simple(f'[Video: {self.video_stream.video_stream_id}][Segment {segment_index}] '
                                                    f'Current Relative Timestamp: {current_relative_timestamp}')
                                Logging.info(f'[Video: {self.video_stream.video_stream_id}][Segment {segment_index}] '
                                             f'Cut out {segment_bytes_count / 1024 / 1024:.3f} MiB.')

                            # まだ前のセグメントのエンコーダーが起動している場合
                            if segment_encoding_task is not None and segment_encoding_task.done() is False:

                                # もう投入するパケットがないことを通知する (これで tsreadex の標準入力が閉じられ、エンコードが完了する)
                                await self.__pushTSPacketDataToEncoder(None)

                                # エンコードが完了するまで待機する
                                result = await segment_encoding_task
                                if result is True:
                                    Logging.info(f'[Video: {self.video_stream.video_stream_id}][Segment {segment_index}] Successfully encoded HLS segment.')
                                else:
                                    Logging.error(f'[Video: {self.video_stream.video_stream_id}][Segment {segment_index}] Failed to encode HLS segment.')

                            # この時点で次のセグメントのエンコードがすでに完了している場合、これ以上エンコードタスクを動かす必要はないのでループを抜ける
                            ## 例えば 15 分地点からエンコードタスクが開始されて 30 分地点までエンコードした後、
                            ## ユーザー操作により巻き戻って 5 分地点からエンコードタスクが開始された場合、15 分地点に到達した時点でエンコードタスクを終了する
                            if self.video_stream.segments[segment_index + 1].segment_ts_future.done() is True:
                                break

                            # 次のセグメントのインデックスに切り替える
                            segment_index += 1
                            Logging.info(f'[Video: {self.video_stream.video_stream_id}] Switched to next segment: {segment_index}')

                            # 非同期でエンコーダーを起動する
                            segment = self.video_stream.segments[segment_index]
                            segment_bytes_count = 0  # バイト数カウントをリセットする
                            segment_encoding_task = asyncio.create_task(self.__runEncoder(segment))
                            Logging.info(f'[Video: {self.video_stream.video_stream_id}][Segment {segment_index}] '
                                         f'Start: {segment.start_offset_timestamp} / End: {segment.start_offset_timestamp + segment.duration}')

                # シーク中でなければ (PAT と PMT は例外的にシーク中でも処理する)
                if is_seeking is False or PID == PAT_PID or PID == PMT_PID:
                    # 現在処理中のセグメントのデータをエンコーダーに投入する
                    await self.__pushTSPacketDataToEncoder(packet)
                    segment_bytes_count += ts.PACKET_SIZE  # バイト数カウントを更新する

                # 途中でエンコードタスクがキャンセルされた場合は処理中のセグメントがあるかに関わらずループを抜ける
                # このとき、エンコード中のセグメントはエンコードの完了を待つことなく破棄される
                if self._is_cancelled is True:
                    break

        # この時点でエンコードタスクがキャンセルされている場合は、このままエンコードタスクを終了する
        if self._is_cancelled is True:
            return

        # この時点で録画データの MPEG-TS をすべて読み出し切ったか、次に処理予定だったセグメントのエンコードが既に完了している状態になっているはず
        Logging.info(f'[Video: {self.video_stream.video_stream_id}] VideoEncodingTask finished.')


    def cancel(self) -> None:
        """
        起動中のエンコードタスクをキャンセルし、起動中の外部プロセスを終了する
        """

        # tsreadex とエンコーダーのプロセスを強制終了する
        self.__terminateEncoder()

        # エンコードタスクがキャンセルされたことを示すフラグを立てる
        # この時点でまだ run() が実行中であれば、run() はこのフラグを見て自ら終了する
        if self._is_cancelled is False:
            self._is_cancelled = True
            Logging.info(f'[Video: {self.video_stream.video_stream_id}] VideoEncodingTask cancelled.')
