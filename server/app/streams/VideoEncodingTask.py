
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import asyncio
import math
import os
import sys
from typing import TYPE_CHECKING, ClassVar, Literal, cast

from biim.mpeg2ts import ts
from biim.mpeg2ts.h264 import H264PES
from biim.mpeg2ts.h265 import H265PES
from biim.mpeg2ts.packetize import packetize_pes, packetize_section
from biim.mpeg2ts.parser import PESParser, SectionParser
from biim.mpeg2ts.pat import PATSection
from biim.mpeg2ts.pes import PES
from biim.mpeg2ts.pmt import PMTSection

from app import logging
from app.config import Config
from app.constants import LIBRARY_PATH, QUALITY, QUALITY_TYPES


if TYPE_CHECKING:
    from app.streams.VideoStream import VideoStream, VideoStreamSegment


class VideoEncodingTask:

    # エンコード後のストリームの GOP 長 (秒)
    ## ライブではないため、GOP 長は H.264 / H.265 共通で長めに設定する
    ## TODO: 実際のセグメント長が GOP 長で割り切れない場合にどうするか考える (特に tsreplace された TS)
    GOP_LENGTH_SECOND: ClassVar[float] = float(3)  # 3秒

    # エンコードタスクの最大リトライ回数
    ## この数を超えた場合はエンコードタスクを再起動しない（無限ループを避ける）
    MAX_RETRY_COUNT: ClassVar[int] = 10  # 10回まで


    def __init__(self, video_stream: VideoStream) -> None:
        """
        エンコードタスクのインスタンスを初期化する

        Args:
            video_stream (VideoStream): エンコードタスクが紐づく録画視聴セッションのインスタンス
        """

        # このエンコードタスクが紐づく録画視聴セッションのインスタンス
        self.video_stream = video_stream

        # psisimux と tsreadex とエンコーダーのプロセス
        self._psisimux_process: asyncio.subprocess.Process | None = None
        self._tsreadex_process: asyncio.subprocess.Process | None = None
        self._encoder_process: asyncio.subprocess.Process | None = None

        # エンコードタスクを完了済みかどうか
        self._is_finished: bool = False

        # 破棄されているかどうか
        self._is_cancelled: bool = False

        # 現在処理中のセグメント
        self._current_segment: VideoStreamSegment | None = None

        # MPEG-TS セクションパーサーを初期化
        self._pat_parser: SectionParser[PATSection] = SectionParser(PATSection)
        self._pmt_parser: SectionParser[PMTSection] = SectionParser(PMTSection)
        self._video_parser: PESParser[PES] = PESParser(PES)
        self._audio_parser: PESParser[PES] = PESParser(PES)

        # PID と CC (Continuity Counter) を管理
        self._pmt_pid: int | None = None
        self._pat_cc: int = 0
        self._pmt_cc: int = 0
        self._video_pid: int | None = None
        self._video_cc: int = 0
        self._audio_pid: int | None = None
        self._audio_cc: int = 0

        # エンコードタスクのリトライ回数のカウント
        self._retry_count: int = 0


    def buildFFmpegOptions(self,
        quality: QUALITY_TYPES,
        output_ts_offset: float,
    ) -> list[str]:
        """
        FFmpeg に渡すオプションを組み立てる

        Args:
            quality (QUALITY_TYPES): 映像の品質
            output_ts_offset (float): 出力 TS のタイムスタンプオフセット (秒)

        Returns:
            list[str]: FFmpeg に渡すオプションが連なる配列
        """

        # オプションの入る配列
        options: list[str] = []

        # 入力ストリームの解析時間
        analyzeduration = round(500000 + (self._retry_count * 250000))  # リトライ回数に応じて少し増やす
        if self.video_stream.recorded_program.recorded_video.video_codec != 'MPEG-2':
            # MPEG-2 以外のコーデックではは入力ストリームの解析時間を長めにする (その方がうまくいく)
            analyzeduration += 500000

        # 入力
        ## -analyzeduration をつけることで、ストリームの分析時間を短縮できる
        options.append(f'-f mpegts -analyzeduration {analyzeduration} -i pipe:0')

        # ストリームのマッピング
        ## 音声切り替えのため、主音声・副音声両方をエンコード後の TS に含む
        options.append('-map 0:v:0 -map 0:a:0 -map 0:a:1 -map 0:d? -ignore_unknown')

        # フラグ
        ## 主に FFmpeg の起動を高速化するための設定
        ## max_interleave_delta: mux 時に影響するオプションで、ライブ再生では増やしすぎると CM で詰まりがちになる
        ## 録画再生では逆に大きめでないと映像/音声のずれが大きくなりセグメント分割時に問題が生じるため、
        ## 5000K (5秒) に設定し、リトライ回数に応じて 500K (0.5秒) ずつ増やす
        max_interleave_delta = round(5000 + (self._retry_count * 500))
        options.append(f'-fflags nobuffer -flags low_delay -max_delay 0 -tune zerolatency -max_interleave_delta {max_interleave_delta}K -threads auto')

        # 映像
        ## コーデック
        if QUALITY[quality].is_hevc is True:
            options.append('-vcodec libx265')  # H.265/HEVC (通信節約モード)
        else:
            options.append('-vcodec libx264')  # H.264

        ## ビットレートと品質
        options.append(f'-flags +cgop+global_header -vb {QUALITY[quality].video_bitrate} -maxrate {QUALITY[quality].video_bitrate_max}')
        options.append('-preset veryfast -aspect 16:9 -pix_fmt:v yuv420p')
        if QUALITY[quality].is_hevc is True:
            options.append('-profile:v main')
        else:
            options.append('-profile:v high')

        ## 指定された品質の解像度が 1440×1080 (1080p) かつ入力ストリームがフル HD (1920×1080) の場合のみ、
        ## 特別に縦解像度を 1920 に変更してフル HD (1920×1080) でエンコードする
        video_width = QUALITY[quality].width
        video_height = QUALITY[quality].height
        if (video_width == 1440 and video_height == 1080) and \
            (self.video_stream.recorded_program.recorded_video.video_resolution_width == 1920 and \
             self.video_stream.recorded_program.recorded_video.video_resolution_height == 1080):
            video_width = 1920

        ## インターレース映像のみ
        if self.video_stream.recorded_program.recorded_video.video_scan_type == 'Interlaced':
            ## インターレース解除 (60i → 60p (フレームレート: 60fps))
            if QUALITY[quality].is_60fps is True:
                options.append(f'-vf yadif=mode=1:parity=-1:deint=1,scale={video_width}:{video_height}')
                options.append(f'-r 60000/1001 -g {int(self.GOP_LENGTH_SECOND * 60)}')
            ## インターレース解除 (60i → 30p (フレームレート: 30fps))
            else:
                options.append(f'-vf yadif=mode=0:parity=-1:deint=1,scale={video_width}:{video_height}')
                options.append(f'-r 30000/1001 -g {int(self.GOP_LENGTH_SECOND * 30)}')
        ## プログレッシブ映像
        ## プログレッシブ映像の場合は 60fps 化する方法はないため、無視して入力ファイルと同じ fps でエンコードする
        elif self.video_stream.recorded_program.recorded_video.video_scan_type == 'Progressive':
            int_fps = math.ceil(self.video_stream.recorded_program.recorded_video.video_frame_rate)  # 29.97 -> 30
            options.append(f'-vf scale={video_width}:{video_height}')
            options.append(f'-g {int(self.GOP_LENGTH_SECOND * int_fps)}')

        # 音声
        ## 音声が 5.1ch かどうかに関わらず、ステレオにダウンミックスする
        options.append(f'-acodec aac -aac_coder twoloop -ac 2 -ab {QUALITY[quality].audio_bitrate} -ar 48000 -af volume=2.0')

        # 出力 TS のタイムスタンプオフセット
        options.append(f'-output_ts_offset {output_ts_offset}')

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
        output_ts_offset: float,
    ) -> list[str]:
        """
        QSVEncC・NVEncC・VCEEncC・rkmppenc (便宜上 HWEncC と総称) に渡すオプションを組み立てる

        Args:
            quality (QUALITY_TYPES): 映像の品質
            encoder_type (Literal['QSVEncC', 'NVEncC', 'VCEEncC', 'rkmppenc']): エンコーダー (QSVEncC or NVEncC or VCEEncC or rkmppenc)
            output_ts_offset (float): 出力 TS のタイムスタンプオフセット (秒)

        Returns:
            list[str]: HWEncC に渡すオプションが連なる配列
        """

        # オプションの入る配列
        options: list[str] = []

        # 入力ストリームの解析時間
        input_probesize = round(1000 + (self._retry_count * 500))  # リトライ回数に応じて少し増やす
        input_analyze = round(0.7 + (self._retry_count * 0.5), 1)  # リトライ回数に応じて少し増やす
        if self.video_stream.recorded_program.recorded_video.video_codec != 'MPEG-2':
            # MPEG-2 以外のコーデックではは入力ストリームの解析時間を長めにする (その方がうまくいく)
            input_probesize += 1000
            input_analyze += 4.3

        # 入力
        ## --input-probesize, --input-analyze をつけることで、ストリームの分析時間を短縮できる
        ## 両方つけるのが重要で、--input-analyze だけだとエンコーダーがフリーズすることがある
        options.append(f'--input-format mpegts --input-probesize {input_probesize}K --input-analyze {input_analyze} --input -')
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
        ## max_interleave_delta: mux 時に影響するオプションで、ライブ再生では増やしすぎると CM で詰まりがちになる
        ## 録画再生では逆に大きめでないと映像/音声のずれが大きくなりセグメント分割時に問題が生じるため、
        ## 5000K (5秒) に設定し、リトライ回数に応じて 500K (0.5秒) ずつ増やす
        max_interleave_delta = round(5000 + (self._retry_count * 500))
        options.append('-m avioflags:direct -m fflags:nobuffer+flush_packets -m flush_packets:1 -m max_delay:0')
        options.append(f'-m max_interleave_delta:{max_interleave_delta}K')
        ## QSVEncC と rkmppenc では OpenCL を使用しないので、無効化することで初期化フェーズを高速化する
        if encoder_type == 'QSVEncC' or encoder_type == 'rkmppenc':
            options.append('--disable-opencl')
        ## NVEncC では NVML によるモニタリングと DX11, Vulkan を無効化することで初期化フェーズを高速化する
        if encoder_type == 'NVEncC':
            options.append('--disable-nvml 1 --disable-dx11 --disable-vulkan')

        # 映像
        ## コーデック
        if QUALITY[quality].is_hevc is True:
            options.append('--codec hevc')  # H.265/HEVC (通信節約モード)
        else:
            options.append('--codec h264')  # H.264

        ## ビットレート
        ## H.265/HEVC かつ QSVEncC の場合のみ、--qvbr (品質ベース可変ビットレート) モードでエンコードする
        ## それ以外は --vbr (可変ビットレート) モードでエンコードする
        if QUALITY[quality].is_hevc is True and encoder_type == 'QSVEncC':
            options.append(f'--qvbr {QUALITY[quality].video_bitrate} --fallback-rc')
        else:
            options.append(f'--vbr {QUALITY[quality].video_bitrate}')
        options.append(f'--max-bitrate {QUALITY[quality].video_bitrate_max}')

        ## H.265/HEVC の高圧縮化調整
        if QUALITY[quality].is_hevc is True:
            if encoder_type == 'QSVEncC':
                options.append('--qvbr-quality 20 --extbrc --mbbrc --scenario-info game_streaming --tune perceptual')
                options.append('--i-adapt --b-adapt --b-pyramid --weightp --weightb --adapt-ref --adapt-ltr --adapt-cqm')
            elif encoder_type == 'NVEncC':
                # --weightp は過去の GPU 世代で不安定な場合があるので使用しない
                options.append('--qp-min 23:26:30 --lookahead 16 --multipass 2pass-full --bref-mode middle --aq --aq-temporal')

        ## ヘッダ情報制御 (GOP ごとにヘッダを再送する)
        ## VCEEncC ではデフォルトで有効であり、当該オプションは存在しない
        if encoder_type != 'VCEEncC':
            options.append('--repeat-headers')

        ## GOP 長を固定
        ## VCEEncC / rkmppenc では下記オプションは存在しない
        if encoder_type == 'QSVEncC':
            options.append('--strict-gop')
        elif encoder_type == 'NVEncC':
            options.append('--no-i-adapt')

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
        options.append('--dar 16:9')

        ## インターレース映像のみ
        if self.video_stream.recorded_program.recorded_video.video_scan_type == 'Interlaced':
            # インターレース映像として読み込む
            options.append('--interlace tff')
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
                options.append(f'--avsync vfr --gop-len {int(self.GOP_LENGTH_SECOND * 60)}')
            ## インターレース解除 (60i → 30p (フレームレート: 30fps))
            ## NVEncC の --vpp-deinterlace normal は GPU 機種次第では稀に解除漏れのジャギーが入るらしいので、代わりに --vpp-afs を使う
            ## NVIDIA GPU は当然ながら Intel の内蔵 GPU よりも性能が高いので、GPU フィルタを使ってもパフォーマンスに問題はないと判断
            ## VCEEncC では --vpp-deinterlace 自体が使えないので、代わりに --vpp-afs を使う (ただし、 timestamp を変えないよう coeff_shift=0 を指定する)
            else:
                if encoder_type == 'QSVEncC':
                    options.append('--vpp-deinterlace normal')
                elif encoder_type == 'NVEncC' or encoder_type == 'VCEEncC':
                    options.append('--vpp-afs preset=default,coeff_shift=0')
                elif encoder_type == 'rkmppenc':
                    options.append('--vpp-deinterlace normal_i5')
                options.append(f'--avsync vfr --gop-len {int(self.GOP_LENGTH_SECOND * 30)}')
        ## プログレッシブ映像
        ## プログレッシブ映像の場合は 60fps 化する方法はないため、無視して入力ファイルと同じ fps でエンコードする
        elif self.video_stream.recorded_program.recorded_video.video_scan_type == 'Progressive':
            int_fps = math.ceil(self.video_stream.recorded_program.recorded_video.video_frame_rate)  # 29.97 -> 30
            options.append(f'--avsync vfr --gop-len {int(self.GOP_LENGTH_SECOND * int_fps)}')

        ## 指定された品質の解像度が 1440×1080 (1080p) かつ入力ストリームがフル HD (1920×1080) の場合のみ、
        ## 特別に縦解像度を 1920 に変更してフル HD (1920×1080) でエンコードする
        video_width = QUALITY[quality].width
        video_height = QUALITY[quality].height
        if (video_width == 1440 and video_height == 1080) and \
            (self.video_stream.recorded_program.recorded_video.video_resolution_width == 1920 and \
             self.video_stream.recorded_program.recorded_video.video_resolution_height == 1080):
            video_width = 1920
        options.append(f'--output-res {video_width}x{video_height}')

        # 音声
        options.append(f'--audio-codec aac:aac_coder=twoloop --audio-bitrate {QUALITY[quality].audio_bitrate}')
        options.append('--audio-samplerate 48000 --audio-filter volume=2.0 --audio-ignore-decode-error 30')

        # 出力 TS のタイムスタンプオフセット
        options.append(f'-m output_ts_offset:{output_ts_offset}')
        # dts 合わせにするため、B フレームによる pts-dts ずれ量を補正する
        options.append('--offset-video-dts-advance')

        # 出力
        options.append('--output-format mpegts')  # MPEG-TS 出力ということを明示
        options.append('--output -')  # 標準入力へ出力

        # オプションをスペースで区切って配列にする
        result: list[str] = []
        for option in options:
            result += option.split(' ')

        return result


    async def run(self, start_sequence: int) -> None:
        """
        エンコードタスクを実行する
        LiveEncodingTask と異なり状態が多いため、複数回実行できる設計にはなっていない（使い捨て）
        biim の pseudo.py の実装を KonomiTV 向けに移植したもの
        ref: https://github.com/tsukumijima/biim/blob/main/pseudo.py

        Args:
            start_sequence (int): エンコードを開始するセグメントのシーケンス番号
        """

        # エンコーダーの種類を取得
        CONFIG = Config()
        ENCODER_TYPE = CONFIG.general.encoder

        # 新しいエンコードタスクを起動させた時点で既にエンコード済みのセグメントは使えなくなるので、すべてリセットする
        for segment in self.video_stream.segments:
            if segment.encode_status != 'Pending':
                await segment.resetState()

        # 処理対象の VideoStreamSegment を取得し、エンコード中状態に設定
        current_sequence = start_sequence
        self._current_segment = self.video_stream.segments[current_sequence]
        self._current_segment.encode_status = 'Encoding'
        logging.info(f'{self.video_stream.log_prefix}[Segment {current_sequence}] Starting the Encoder...')

        # エンコーダーに渡す出力 TS のタイムスタンプオフセットを算出
        output_ts_offset: float = 0.0
        for kf in self.video_stream.recorded_program.recorded_video.key_frames:
            # セグメント開始位置よりも後のキーフレームは採用せず、直前の DTS を記録
            if kf['offset'] > self._current_segment.start_file_position:
                break
            output_ts_offset = kf['dts'] / ts.HZ  # 秒単位

        # MPEG-TS 形式の場合のみ、録画ファイルを開く
        # それ以外の場合は一旦 None とする
        file = None
        if self.video_stream.recorded_program.recorded_video.container_format == 'MPEG-TS':
            file = open(self.video_stream.recorded_program.recorded_video.file_path, 'rb')

        # 切り出した HLS セグメント用 MPEG-TS パケットを一時的に保持するバッファ
        encoded_segment = bytearray()

        try:
            # 最大 MAX_RETRY_COUNT 回までリトライする
            while self._retry_count < self.MAX_RETRY_COUNT:

               # 念のため MPEG-TS セクションパーサーを初期化
                self._pat_parser: SectionParser[PATSection] = SectionParser(PATSection)
                self._pmt_parser: SectionParser[PMTSection] = SectionParser(PMTSection)
                self._video_parser: PESParser[PES] = PESParser(PES)
                self._audio_parser: PESParser[PES] = PESParser(PES)
                # PID と CC (Continuity Counter) をリセット
                self._pmt_pid = None
                self._pat_cc = 0
                self._pmt_cc = 0
                self._video_pid = None
                self._video_cc = 0
                self._audio_pid = None
                self._audio_cc = 0

                # 録画ファイルが MPEG-4 形式の場合、psisimux で MPEG-TS に変換し、
                # TS ファイル入力の代わりに psisimux からの出力を tsreadex への入力として渡す
                psisimux_read_pipe = None
                if self.video_stream.recorded_program.recorded_video.container_format == 'MPEG-4':
                    assert file is None

                    # psisimux のオプション
                    ## MPEG-4 コンテナに字幕や PSI/SI を結合して MPEG-TS にするツール
                    ## オプション内容は https://github.com/xtne6f/psisimux を参照
                    psisimux_options = [
                        # 出力ファイルのミリ秒単位の初期シーク量
                        '-m', str(int(output_ts_offset * 1000)),
                        # NetworkID/TransportStreamID/ServiceID
                        '-b', '1/2/3' if self.video_stream.recorded_program.channel is None else \
                            f'{self.video_stream.recorded_program.channel.network_id}/' \
                            f'{self.video_stream.recorded_program.channel.transport_stream_id}/' \
                            f'{self.video_stream.recorded_program.channel.service_id}',
                        # 文字コードが UTF-8 の字幕を ARIB8 単位符号に変換する
                        '-8',
                        # 字幕ファイルの拡張子
                        '-x', '.vtt',
                        # 入力ファイル名
                        self.video_stream.recorded_program.recorded_video.file_path,
                        # 標準出力
                        '-',
                    ]

                    # psisimux の読み込み用パイプと書き込み用パイプを作成
                    psisimux_read_pipe, psisimux_write_pipe = os.pipe()

                    # psisimux のプロセスを作成・実行
                    self._psisimux_process = await asyncio.subprocess.create_subprocess_exec(
                        LIBRARY_PATH['psisimux'], *psisimux_options,
                        stdin = asyncio.subprocess.DEVNULL,  # 利用しない
                        stdout = psisimux_write_pipe,  # tsreadex に繋ぐ
                        stderr = asyncio.subprocess.DEVNULL,  # 利用しない
                    )

                    # psisimux の書き込み用パイプを閉じる
                    os.close(psisimux_write_pipe)
                else:
                    # ファイルポインタを移動
                    assert file is not None
                    file.seek(self._current_segment.start_file_position)

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
                    '-n', f'{self.video_stream.recorded_program.channel.service_id}' \
                        if self.video_stream.recorded_program.channel is not None else '-1',
                    # 主音声ストリームが常に存在する状態にする
                    ## ストリームが存在しない場合、無音の AAC ストリームが出力される
                    ## 音声がモノラルであればステレオにする
                    ## デュアルモノを2つのモノラル音声に分離し、右チャンネルを副音声として扱う
                    '-a', '13',
                    # 副音声ストリームが常に存在する状態にする
                    ## ストリームが存在しない場合、無音の AAC ストリームが出力される
                    ## 音声がモノラルであればステレオにする
                    '-b', '7',
                    # 字幕ストリームが常に存在する状態にする
                    ## ストリームが存在しない場合、PMT の項目が補われて出力される
                    ## 実際の字幕データが現れない場合に5秒ごとに非表示の適当なデータを挿入する
                    '-c', '5',
                    # 文字スーパーストリームが常に存在する状態にする
                    ## ストリームが存在しない場合、PMT の項目が補われて出力される
                    '-u', '1',
                    # 字幕と文字スーパーを aribb24.js が解釈できる ID3 timed-metadata に変換する
                    ## +4: FFmpeg のバグを打ち消すため、変換後のストリームに規格外の5バイトのデータを追加する
                    ## +8: FFmpeg のエラーを防ぐため、変換後のストリームの PTS が単調増加となるように調整する
                    ## +4 は FFmpeg 6.1 以降不要になった (付与していると字幕が表示されなくなる) ため、
                    ## FFmpeg 4.4 系に依存している Linux 版 HWEncC 利用時のみ付与する
                    '-d', '13' if ENCODER_TYPE != 'FFmpeg' and sys.platform == 'linux' else '9',
                    # 標準入力からの入力を受け付ける
                    '-',
                ]

                # tsreadex の読み込み用パイプと書き込み用パイプを作成
                tsreadex_read_pipe, tsreadex_write_pipe = os.pipe()

                # tsreadex のプロセスを作成・実行
                self._tsreadex_process = await asyncio.subprocess.create_subprocess_exec(
                    LIBRARY_PATH['tsreadex'], *tsreadex_options,
                    stdin = file or psisimux_read_pipe,  # シークされたファイルポインタか psisimux からの入力を渡す
                    stdout = tsreadex_write_pipe,  # エンコーダーに繋ぐ
                    stderr = asyncio.subprocess.DEVNULL,  # 利用しない
                )

                # tsreadex の書き込み用パイプを閉じる
                os.close(tsreadex_write_pipe)

                # FFmpeg
                if ENCODER_TYPE == 'FFmpeg':
                    # オプションを取得
                    encoder_options = self.buildFFmpegOptions(self.video_stream.quality, output_ts_offset)
                    logging.info(f'{self.video_stream.log_prefix} FFmpeg Commands:\nffmpeg {" ".join(encoder_options)}')

                    # エンコーダープロセスを作成・実行
                    self._encoder_process = await asyncio.subprocess.create_subprocess_exec(
                        LIBRARY_PATH['FFmpeg'], *encoder_options,
                        stdin = tsreadex_read_pipe,  # tsreadex からの入力
                        stdout = asyncio.subprocess.PIPE,  # ストリーム出力
                        stderr = asyncio.subprocess.PIPE,  # ストリーム出力
                    )

                # HWEncC
                else:
                    # オプションを取得
                    encoder_options = self.buildHWEncCOptions(self.video_stream.quality, ENCODER_TYPE, output_ts_offset)
                    logging.info(f'{self.video_stream.log_prefix} {ENCODER_TYPE} Commands:\n{ENCODER_TYPE} {" ".join(encoder_options)}')

                    # エンコーダープロセスを作成・実行
                    self._encoder_process = await asyncio.subprocess.create_subprocess_exec(
                        LIBRARY_PATH[ENCODER_TYPE], *encoder_options,
                        stdin = tsreadex_read_pipe,  # tsreadex からの入力
                        stdout = asyncio.subprocess.PIPE,  # ストリーム出力
                        stderr = asyncio.subprocess.PIPE,  # ストリーム出力
                    )

                # エンコーダーの出力を読み取り、MPEG-TS パーサーでパースする
                assert self._encoder_process is not None and self._encoder_process.stdout is not None

                # 最新の PAT と PMT を保持
                latest_pat: PATSection | None = None
                latest_pmt: PMTSection | None = None

                # エンコーダーの出力読み取りタイムアウトを設定
                read_timeout = 10.0  # 10秒
                last_read_time = asyncio.get_running_loop().time()

                # 新しいセグメントのエンコードを開始するため、バッファをリセット
                encoded_segment = bytearray()
                # セグメント境界を IDR/CRA に合わせるためのフラグ
                is_split_pending = False

                # PTS/DTS の 33bit ラップアラウンドを展開して、DB に保存されている ffprobe の単調増加 DTS に合わせる
                ## ffmpeg/ffprobe は 2^33 を超えた場合も内部的に単調増加の DTS として扱うため、
                ## DB 側のキーフレーム DTS は“展開された”値で保存されているはず
                ## 一方 MPEG-TS 自体の PTS/DTS は 33bit に制限されているので、ここで wrap を数えて展開する
                first_video_timestamp_33bit: int | None = None
                last_video_timestamp_33bit: int | None = None
                wrap_offset_ticks: int = 0
                # エンコードタスク開始時点のセグメント開始 DTS を保存しておく
                first_segment_start_dts: int = self._current_segment.start_dts

                while True:
                    # エンコードタスクがキャンセルされた場合、処理を中断する
                    if self._is_cancelled is True:
                        break

                    # エンコーダーの出力読み取りタイムアウトをチェック
                    current_time = asyncio.get_running_loop().time()
                    if current_time - last_read_time > read_timeout:
                        logging.warning(f'{self.video_stream.log_prefix}[Segment {current_sequence}] Encoder output read timeout.')
                        break

                    # 同期バイトを探す
                    isEOF = False
                    while True:
                        try:
                            # この時点で既にエンコーダープロセスが終了していたら処理中断
                            if self._encoder_process is None:
                                break
                            sync_byte = await self._encoder_process.stdout.readexactly(1)
                            if sync_byte == ts.SYNC_BYTE:
                                break
                            elif sync_byte == b'':
                                isEOF = True
                                break
                        except asyncio.IncompleteReadError:
                            isEOF = True
                        break
                    if isEOF:
                        break

                    # TS パケットを読み込む
                    try:
                        # この時点で既にエンコーダープロセスが終了していたら処理中断
                        if self._encoder_process is None:
                            break
                        packet = ts.SYNC_BYTE + await self._encoder_process.stdout.readexactly(ts.PACKET_SIZE - 1)
                        last_read_time = current_time  # 正常に読み取れた場合はタイムアウトをリセット
                    except asyncio.IncompleteReadError:
                        break

                    # PID を取得
                    pid = ts.pid(packet)

                    # PAT (Program Association Table)
                    if pid == 0x00:
                        self._pat_parser.push(packet)
                        for pat in self._pat_parser:
                            if pat.CRC32() != 0:
                                continue
                            latest_pat = pat

                            # PMT の PID を取得
                            for program_number, program_map_pid in pat:
                                if program_number == 0:
                                    continue
                                self._pmt_pid = program_map_pid

                            # PAT を再構築して candidate に追加
                            for packet in packetize_section(pat, False, False, 0, 0, self._pat_cc):
                                encoded_segment += packet
                                self._pat_cc = (self._pat_cc + 1) & 0x0F

                    # PMT (Program Map Table)
                    elif pid == self._pmt_pid:
                        self._pmt_parser.push(packet)
                        for pmt in self._pmt_parser:
                            if pmt.CRC32() != 0:
                                continue
                            latest_pmt = pmt

                            # ストリームの PID を取得
                            for stream_type, elementary_pid, _ in pmt:
                                if stream_type == 0x1b:  # H.264
                                    if self._video_pid is None:
                                        self._video_pid = elementary_pid
                                        # H.264 映像 PES を解析できるようパーサーを差し替える
                                        self._video_parser = PESParser(H264PES)
                                        logging.debug_simple(f'{self.video_stream.log_prefix} H.264 PID: 0x{elementary_pid:04x}')
                                elif stream_type == 0x24:  # H.265
                                    if self._video_pid is None:
                                        self._video_pid = elementary_pid
                                        # H.265 映像 PES を解析できるようパーサーを差し替える
                                        self._video_parser = PESParser(H265PES)
                                        logging.debug_simple(f'{self.video_stream.log_prefix} H.265 PID: 0x{elementary_pid:04x}')
                                elif stream_type == 0x0F:  # AAC
                                    if self._audio_pid is None:
                                        self._audio_pid = elementary_pid
                                        logging.debug_simple(f'{self.video_stream.log_prefix} AAC PID: 0x{elementary_pid:04x}')
                            # PMT を再構築して candidate に追加
                            for packet in packetize_section(pmt, False, False, cast(int, self._pmt_pid), 0, self._pmt_cc):
                                encoded_segment += packet
                                self._pmt_cc = (self._pmt_cc + 1) & 0x0F

                    # 映像ストリーム
                    elif pid == self._video_pid:
                        self._video_parser.push(packet)
                        for video in self._video_parser:
                            # 現在の PES の 33bit タイムスタンプ (DTS 優先, 90kHz)
                            current_timestamp_33bit = cast(int, video.dts() or video.pts())

                            # 最初のフレームでアンカーを確定
                            if first_video_timestamp_33bit is None:
                                first_video_timestamp_33bit = current_timestamp_33bit
                                last_video_timestamp_33bit = current_timestamp_33bit

                            # wrap-around 検出 (大きく逆行した場合のみ wrap とみなす)
                            assert last_video_timestamp_33bit is not None
                            if current_timestamp_33bit < last_video_timestamp_33bit and (last_video_timestamp_33bit - current_timestamp_33bit) > (ts.PCR_CYCLE // 2):
                                wrap_offset_ticks += ts.PCR_CYCLE
                            last_video_timestamp_33bit = current_timestamp_33bit

                            # 単調増加となるよう展開した現在の DTS (DB 上の単調増加 DTS に揃える)
                            assert first_video_timestamp_33bit is not None
                            current_timestamp_unwrapped = first_segment_start_dts + (current_timestamp_33bit - first_video_timestamp_33bit + wrap_offset_ticks)

                            # Future がまだ未完了の場合にのみ実行
                            if self._current_segment is not None:
                                # 判定に用いる次セグメント開始時刻
                                next_segment_start_timestamp = self._current_segment.start_dts + int(round(self._current_segment.duration_seconds * ts.HZ))
                                # logging.debug_simple(
                                #     f'{self.video_stream.log_prefix} Current Timestamp: {current_timestamp_unwrapped} / '
                                #     f'Next Segment Start Timestamp: {next_segment_start_timestamp}'
                                # )

                                # 現在の映像 PES が (H.264: IDR, H.265: IDR/CRA) フレームかを判定
                                def _has_idr_frame(pes: PES) -> bool:
                                    try:
                                        if isinstance(pes, H264PES):
                                            for ebsp in pes.ebsps:
                                                nal_unit_type = ebsp[0] & 0x1f
                                                if nal_unit_type == 0x05:
                                                    return True
                                        elif isinstance(pes, H265PES):
                                            for ebsp in pes.ebsps:
                                                nal_unit_type = (ebsp[0] >> 1) & 0x3f
                                                # biim に合わせて IDR/CRA のみを採用 (BLA は除外)
                                                if nal_unit_type in (19, 20, 21):
                                                    return True
                                    except Exception:
                                        pass
                                    return False
                                has_idr_frame = _has_idr_frame(video)

                                # 次のセグメントの開始時刻以上になったら、現在のセグメントを確定して次のセグメントへ移行
                                is_reached_planned_boundary = (current_timestamp_unwrapped >= next_segment_start_timestamp)
                                is_should_finalize_now = False
                                if is_split_pending is True:
                                    # 次に来た (H.264: IDR, H.265: IDR/CRA) フレームで確定する
                                    if has_idr_frame:
                                        is_should_finalize_now = True
                                else:
                                    if is_reached_planned_boundary is True:
                                        if has_idr_frame:
                                            is_should_finalize_now = True
                                        else:
                                            # (H.264: IDR, H.265: IDR/CRA) フレームまで現在のセグメントを延長
                                            is_split_pending = True

                                # 無事セグメントを安全に分割できる地点に到達したので、現在のセグメントを確定
                                if is_should_finalize_now is True:
                                    if not self._current_segment.encoded_segment_ts_future.done():
                                        self._current_segment.encoded_segment_ts_future.set_result(bytes(encoded_segment))
                                    self._current_segment.encode_status = 'Completed'
                                    logging.info(f'{self.video_stream.log_prefix}[Segment {current_sequence}] Successfully Encoded HLS Segment.')

                                    # 次のセグメントへ移行
                                    current_sequence += 1

                                    # 最終セグメントの場合はループを抜ける
                                    if current_sequence >= len(self.video_stream.segments):
                                        logging.info(f'{self.video_stream.log_prefix} Reached the final segment.')
                                        break

                                    # 新しいセグメント用のデータと状態を初期化
                                    ## ここで encoded_segment は空の bytearray にリセットされる
                                    logging.info(f'{self.video_stream.log_prefix}[Segment {current_sequence}] Encoding...')
                                    self._current_segment = self.video_stream.segments[current_sequence]
                                    self._current_segment.encode_status = 'Encoding'
                                    encoded_segment = bytearray()
                                    is_split_pending = False

                                    # 新しいセグメントの先頭に PAT と PMT を追加
                                    if latest_pat is not None:
                                        for packet in packetize_section(latest_pat, False, False, 0, 0, self._pat_cc):
                                            encoded_segment += packet
                                            self._pat_cc = (self._pat_cc + 1) & 0x0F
                                    if latest_pmt is not None:
                                        for packet in packetize_section(latest_pmt, False, False, cast(int, self._pmt_pid), 0, self._pmt_cc):
                                            encoded_segment += packet
                                            self._pmt_cc = (self._pmt_cc + 1) & 0x0F

                            # 現在の映像 PES をパケット化して、現在処理対象のセグメントに追加
                            for packet in packetize_pes(video, False, False, cast(int, self._video_pid), 0, self._video_cc):
                                encoded_segment += packet
                                self._video_cc = (self._video_cc + 1) & 0x0F

                    # 音声ストリーム
                    elif pid == self._audio_pid:
                        self._audio_parser.push(packet)
                        for audio in self._audio_parser:
                            # PES パケットを再構築して candidate に追加
                            for packet in packetize_pes(audio, False, False, cast(int, self._audio_pid), 0, self._audio_cc):
                                encoded_segment += packet
                                self._audio_cc = (self._audio_cc + 1) & 0x0F

                    # その他のパケット
                    else:
                        encoded_segment += packet

                    # 最終セグメントの場合はループを抜ける
                    if current_sequence >= len(self.video_stream.segments):
                        break

                # エンコーダープロセスを終了
                if self._encoder_process is not None:
                    try:
                        if self._encoder_process.returncode is None:
                            self._encoder_process.kill()
                            try:
                                # プロセスの終了を待機
                                await asyncio.wait_for(self._encoder_process.wait(), timeout=5.0)
                            except (TimeoutError, asyncio.CancelledError):
                                # 稀に終了待ちがタイムアウト/キャンセルすることがあるが致命的ではない
                                logging.warning(f'{self.video_stream.log_prefix} Encoder process termination wait timed out or cancelled.')
                    except Exception as ex:
                        logging.error(f'{self.video_stream.log_prefix} Failed to terminate encoder process:', exc_info=ex)

                # tsreadex プロセスを終了
                if self._tsreadex_process is not None:
                    try:
                        if self._tsreadex_process.returncode is None:
                            self._tsreadex_process.kill()
                            try:
                                # プロセスの終了を待機
                                await asyncio.wait_for(self._tsreadex_process.wait(), timeout=5.0)
                            except (TimeoutError, asyncio.CancelledError):
                                # 稀に終了待ちがタイムアウト/キャンセルすることがあるが致命的ではない
                                logging.warning(f'{self.video_stream.log_prefix} tsreadex process termination wait timed out or cancelled.')
                    except Exception as ex:
                        logging.error(f'{self.video_stream.log_prefix} Failed to terminate tsreadex process:', exc_info=ex)

                # psisimux プロセスを終了
                if self._psisimux_process is not None:
                    try:
                        if self._psisimux_process.returncode is None:
                            self._psisimux_process.kill()
                            try:
                                # プロセスの終了を待機
                                await asyncio.wait_for(self._psisimux_process.wait(), timeout=5.0)
                            except (TimeoutError, asyncio.CancelledError):
                                # 稀に終了待ちがタイムアウト/キャンセルすることがあるが致命的ではない
                                logging.warning(f'{self.video_stream.log_prefix} psisimux process termination wait timed out or cancelled.')
                    except Exception as ex:
                        logging.error(f'{self.video_stream.log_prefix} Failed to terminate psisimux process:', exc_info=ex)
                    self._psisimux_process = None

                # この時点で video_pid と audio_pid が取得できていない場合、正常にエンコード済み TS が出力されていないと考えられるため、
                # エンコーダー起動をリトライする
                if self._video_pid is None or self._audio_pid is None:
                    self._retry_count += 1
                    if self._retry_count < self.MAX_RETRY_COUNT:
                        logging.warning(f'{self.video_stream.log_prefix} Failed to get video/audio PID. Retrying... ({self._retry_count}/{self.MAX_RETRY_COUNT})')
                        # エンコーダーのデバッグログが有効な場合のみ、全てのログを出力
                        if CONFIG.general.debug_encoder is True:
                            logging.debug_simple(f'{self.video_stream.log_prefix} Encoder stderr:')
                            assert self._encoder_process.stderr is not None
                            while True:
                                try:
                                    line = await self._encoder_process.stderr.readline()
                                    if not line:  # EOF
                                        break
                                    logging.debug_simple(f'{self.video_stream.log_prefix} [{ENCODER_TYPE}] {line.decode("utf-8").strip()}')
                                except Exception:
                                    pass
                        self._encoder_process = None
                        self._tsreadex_process = None
                        continue
                    else:
                        logging.error(f'{self.video_stream.log_prefix} Failed to get video/audio PID after {self.MAX_RETRY_COUNT} retries.')
                        break

                # 正常に最終セグメントまでエンコードできたか途中でキャンセルされたと考えられるため、リトライループを抜ける
                break

        finally:
            if not file:
                # psisimux プロセスを強制終了する
                if self._psisimux_process is not None:
                    try:
                        self._psisimux_process.kill()
                    except Exception as ex:
                        logging.error(f'{self.video_stream.log_prefix} Failed to terminate psisimux process:', exc_info=ex)
                    self._psisimux_process = None
            else:
                # ファイルを閉じる
                file.close()

            # エンコーダーのデバッグログが有効 or リトライ失敗時のみ、全てのログを出力
            if CONFIG.general.debug_encoder is True or self._retry_count >= self.MAX_RETRY_COUNT:
                logging.debug_simple(f'{self.video_stream.log_prefix} Encoder stderr:')
                assert self._encoder_process is not None and self._encoder_process.stderr is not None
                while True:
                    try:
                        line = await self._encoder_process.stderr.readline()
                        if not line:  # EOF
                            break
                        logging.debug_simple(f'{self.video_stream.log_prefix} [{ENCODER_TYPE}] {line.decode("utf-8").strip()}')
                    except Exception:
                        pass
            self._encoder_process = None
            self._tsreadex_process = None

            # このエンコードタスクがキャンセルされている場合は何もしない
            if self._is_cancelled is True:
                return

            # 最後のセグメントが完了していない場合は、現在のバッファを future にセット
            if self._current_segment is not None and not self._current_segment.encoded_segment_ts_future.done():
                self._current_segment.encoded_segment_ts_future.set_result(bytes(encoded_segment))
                self._current_segment.encode_status = 'Completed'
                logging.info(f'{self.video_stream.log_prefix}[Segment {current_sequence}] Successfully Encoded Final HLS Segment.')

            # エンコードタスクでのすべての処理を完了した
            self._is_finished = True
            logging.info(f'{self.video_stream.log_prefix} Finished the Encoding Task.')


    async def cancel(self) -> None:
        """
        起動中のエンコードタスクをキャンセルし、起動中の外部プロセスを終了する
        """

        # すでにエンコードタスクが完了している場合は何もしない
        if self._is_finished is True:
            logging.info(f'{self.video_stream.log_prefix} The Encoding Task is already finished.')
            return

        if self._is_cancelled is False:

            # エンコードタスクがキャンセルされたことを示すフラグを立てる
            ## この時点でまだ run() やエンコーダーが実行中であれば、run() やエンコーダーはこのフラグを見て自ら終了する
            ## できるだけ早い段階でフラグを立てておくことが重要
            self._is_cancelled = True

            # psisimux プロセスを強制終了する
            if self._psisimux_process is not None:
                try:
                    self._psisimux_process.kill()
                except Exception as ex:
                    logging.error(f'{self.video_stream.log_prefix} Failed to terminate psisimux process:', exc_info=ex)
                self._psisimux_process = None

            # tsreadex プロセスを強制終了する
            if self._tsreadex_process is not None:
                try:
                    if self._tsreadex_process.returncode is None:
                        self._tsreadex_process.kill()
                except Exception as ex:
                    logging.error(f'{self.video_stream.log_prefix} Failed to terminate tsreadex process:', exc_info=ex)

            # エンコーダープロセスを強制終了する
            if self._encoder_process is not None:
                try:
                    if self._encoder_process.returncode is None:
                        self._encoder_process.kill()
                except Exception as ex:
                    logging.error(f'{self.video_stream.log_prefix} Failed to terminate encoder process:', exc_info=ex)

            # 少し待ってから完全に破棄
            await asyncio.sleep(0.1)
            self._tsreadex_process = None
            self._encoder_process = None
