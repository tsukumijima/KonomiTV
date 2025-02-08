
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import asyncio
import os
import sys
from biim.mpeg2ts import ts
from biim.mpeg2ts.parser import SectionParser, PESParser
from biim.mpeg2ts.pat import PATSection
from biim.mpeg2ts.pmt import PMTSection
from biim.mpeg2ts.pes import PES
from biim.mpeg2ts.packetize import packetize_section, packetize_pes
from typing import cast, ClassVar, Literal, TYPE_CHECKING

from app import logging
from app.config import Config
from app.constants import LIBRARY_PATH, QUALITY, QUALITY_TYPES

if TYPE_CHECKING:
    from app.streams.VideoStream import VideoStream, VideoStreamSegment


class VideoEncodingTask:

    # エンコードする HLS セグメントの長さ (秒)
    SEGMENT_DURATION_SECONDS: ClassVar[float] = float(10)  # 10秒

    # エンコード後のストリームの GOP 長 (秒)
    ## ライブではないため、GOP 長は H.264 / H.265 共通で長めに設定する
    GOP_LENGTH_SECOND: ClassVar[float] = float(2.5)  # 2.5秒


    def __init__(self, video_stream: VideoStream) -> None:
        """
        エンコードタスクのインスタンスを初期化する

        Args:
            video_stream (VideoStream): エンコードタスクが紐づく録画視聴セッションのインスタンス
        """

        # このエンコードタスクが紐づく録画視聴セッションのインスタンス
        self.video_stream = video_stream

        # tsreadex とエンコーダーのプロセス
        self._tsreadex_process: asyncio.subprocess.Process | None = None
        self._encoder_process: asyncio.subprocess.Process | None = None

        # エンコードタスクを完了済みかどうか
        self._is_finished: bool = False

        # 破棄されているかどうか
        self._is_cancelled: bool = False

        # 現在処理中のセグメント
        self._current_segment: VideoStreamSegment | None = None

        # エンコーダーの出力を一時的に保持するバッファ
        self._candidate = bytearray()

        # MPEG-TS パーサーを初期化
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


    def buildFFmpegOptions(self,
        quality: QUALITY_TYPES,
    ) -> list[str]:
        """
        FFmpeg に渡すオプションを組み立てる

        Args:
            quality (QUALITY_TYPES): 映像の品質

        Returns:
            list[str]: FFmpeg に渡すオプションが連なる配列
        """

        # オプションの入る配列
        options: list[str] = []

        # 入力
        ## -analyzeduration をつけることで、ストリームの分析時間を短縮できる
        ## -copyts で入力のタイムスタンプを出力にコピーする
        options.append('-f mpegts -analyzeduration 500000 -copyts -i pipe:0')

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
            (self.video_stream.recorded_program.recorded_video.video_resolution_width == 1920 and \
             self.video_stream.recorded_program.recorded_video.video_resolution_height == 1080):
            video_width = 1920

        # インターレース映像のみ
        if self.video_stream.recorded_program.recorded_video.video_scan_type == 'Interlaced':
            ## インターレース解除 (60i → 60p (フレームレート: 60fps))
            if QUALITY[quality].is_60fps is True:
                options.append(f'-vf yadif=mode=1:parity=-1:deint=1,scale={video_width}:{video_height}')
                options.append(f'-r 60000/1001 -g {int(self.GOP_LENGTH_SECOND * 60)}')
            ## インターレース解除 (60i → 30p (フレームレート: 30fps))
            else:
                options.append(f'-vf yadif=mode=0:parity=-1:deint=1,scale={video_width}:{video_height}')
                options.append(f'-r 30000/1001 -g {int(self.GOP_LENGTH_SECOND * 30)}')
        # プログレッシブ映像
        ## プログレッシブ映像の場合は 60fps 化する方法はないため、無視して元映像と同じフレームレートでエンコードする
        ## GOP は 30fps だと仮定して設定する
        elif self.video_stream.recorded_program.recorded_video.video_scan_type == 'Progressive':
            options.append(f'-vf scale={video_width}:{video_height}')
            options.append(f'-r 30000/1001 -g {int(self.GOP_LENGTH_SECOND * 30)}')

        # 音声
        ## 音声が 5.1ch かどうかに関わらず、ステレオにダウンミックスする
        options.append(f'-acodec aac -aac_coder twoloop -ac 2 -ab {QUALITY[quality].audio_bitrate} -ar 48000 -af volume=2.0')

        # 出力 TS のタイムスタンプオフセット
        if self._current_segment is not None:
            key_frames = self.video_stream.recorded_program.recorded_video.key_frames
            for key_frame in key_frames:
                if key_frame['offset'] == self._current_segment.start_file_position:
                    output_ts_offset = key_frame['dts'] / ts.HZ
                    options.append(f'-output_ts_offset {output_ts_offset}')
                    break

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
        ## QSVEncC と rkmppenc では OpenCL を使用しないので、無効化することで初期化フェーズを高速化する
        if encoder_type == 'QSVEncC' or encoder_type == 'rkmppenc':
            options.append('--disable-opencl')
        ## NVEncC では NVML によるモニタリングと DX11 を無効化することで初期化フェーズを高速化する
        if encoder_type == 'NVEncC':
            options.append('--disable-nvml 1 --disable-dx11')

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
        options.append('--dar 16:9')

        # GOP 長を固定にする
        if encoder_type == 'QSVEncC':
            options.append('--strict-gop')
        elif encoder_type == 'NVEncC':
            options.append('--no-i-adapt')

        # インターレース映像のみ
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
            ## VCEEncC では --vpp-deinterlace 自体が使えないので、代わりに --vpp-afs を使う
            else:
                if encoder_type == 'QSVEncC':
                    options.append('--vpp-deinterlace normal')
                elif encoder_type == 'NVEncC' or encoder_type == 'VCEEncC':
                    options.append('--vpp-afs preset=default')
                elif encoder_type == 'rkmppenc':
                    options.append('--vpp-deinterlace normal_i5')
                options.append(f'--avsync vfr --gop-len {int(self.GOP_LENGTH_SECOND * 30)}')
        # プログレッシブ映像
        ## プログレッシブ映像の場合は 60fps 化する方法はないため、無視して元映像と同じフレームレートでエンコードする
        ## GOP は 30fps だと仮定して設定する
        elif self.video_stream.recorded_program.recorded_video.video_scan_type == 'Progressive':
            options.append(f'--avsync vfr --gop-len {int(self.GOP_LENGTH_SECOND * 30)}')

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
        if self._current_segment is not None:
            key_frames = self.video_stream.recorded_program.recorded_video.key_frames
            for key_frame in key_frames:
                if key_frame['offset'] == self._current_segment.start_file_position:
                    output_ts_offset = key_frame['dts'] / ts.HZ
                    options.append(f'-m output_ts_offset:{output_ts_offset}')
                    break

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
        biim の pseudo.py の実装を KonomiTV 向けに移植したもの
        ref: https://github.com/tsukumijima/biim/blob/main/pseudo.py

        Args:
            start_sequence (int): エンコードを開始するセグメントのシーケンス番号
        """

        # エンコーダーの種類を取得
        ENCODER_TYPE = Config().general.encoder

        # 新しいエンコードタスクを起動させた時点で既にエンコード済みのセグメントは使えなくなるので、すべて破棄する
        for segment in self.video_stream.segments:
            if segment.encode_status != 'Pending':
                if not segment.encoded_segment_ts_future.done():
                    segment.encoded_segment_ts_future.set_result(b'')
                segment.encoded_segment_ts_future = asyncio.Future()  # 破棄したセグメントの future を再生成
                segment.encode_status = 'Pending'

        # 対象のセグメントを取得
        self._current_segment = self.video_stream.segments[start_sequence]

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

        # 録画ファイルを開く
        file = open(self.video_stream.recorded_program.recorded_video.file_path, 'rb')
        encoded_segment = bytearray()
        current_sequence = start_sequence

        try:
            while current_sequence < len(self.video_stream.segments) and not self._is_cancelled:

                # 処理対象の VideoStreamSegment を取得し、エンコード中状態に設定
                self._current_segment = self.video_stream.segments[current_sequence]
                self._current_segment.encode_status = 'Encoding'
                logging.info(f'[Video: {self.video_stream.session_id}][Segment {current_sequence}] Starting the Encoder...')

                # ファイルポインタを移動
                file.seek(self._current_segment.start_file_position)

                # tsreadex の読み込み用パイプと書き込み用パイプを作成
                tsreadex_read_pipe, tsreadex_write_pipe = os.pipe()

                # tsreadex のプロセスを作成・実行
                self._tsreadex_process = await asyncio.subprocess.create_subprocess_exec(
                    LIBRARY_PATH['tsreadex'], *tsreadex_options,
                    stdin = file,  # シークされたファイルポインタを直接渡す
                    stdout = tsreadex_write_pipe,  # エンコーダーに繋ぐ
                    stderr = asyncio.subprocess.DEVNULL,  # 利用しない
                )

                # tsreadex の書き込み用パイプを閉じる
                os.close(tsreadex_write_pipe)

                # FFmpeg
                if ENCODER_TYPE == 'FFmpeg':
                    # オプションを取得
                    encoder_options = self.buildFFmpegOptions(self.video_stream.quality)
                    logging.info(f'[Video: {self.video_stream.session_id}] FFmpeg Commands:\nffmpeg {" ".join(encoder_options)}')

                    # エンコーダープロセスを作成・実行
                    self._encoder_process = await asyncio.subprocess.create_subprocess_exec(
                        LIBRARY_PATH['FFmpeg'], *encoder_options,
                        stdin = tsreadex_read_pipe,  # tsreadex からの入力
                        stdout = asyncio.subprocess.PIPE,  # ストリーム出力
                        stderr = asyncio.subprocess.DEVNULL,  # デバッグ用
                    )

                # HWEncC
                else:
                    # オプションを取得
                    encoder_options = self.buildHWEncCOptions(self.video_stream.quality, ENCODER_TYPE)
                    logging.info(f'[Video: {self.video_stream.session_id}] {ENCODER_TYPE} Commands:\n{ENCODER_TYPE} {" ".join(encoder_options)}')

                    # エンコーダープロセスを作成・実行
                    self._encoder_process = await asyncio.subprocess.create_subprocess_exec(
                        LIBRARY_PATH[ENCODER_TYPE], *encoder_options,
                        stdin = tsreadex_read_pipe,  # tsreadex からの入力
                        stdout = asyncio.subprocess.PIPE,  # ストリーム出力
                        stderr = asyncio.subprocess.DEVNULL,  # デバッグ用
                    )

                # エンコーダーの出力を読み取り、MPEG-TS パーサーでパースする
                assert self._encoder_process is not None and self._encoder_process.stdout is not None

                # 最新の PAT と PMT を保持
                latest_pat: PATSection | None = None
                latest_pmt: PMTSection | None = None

                # エンコーダーの出力読み取りタイムアウトを設定
                read_timeout = 10.0  # 10秒
                last_read_time = asyncio.get_event_loop().time()

                while True:
                    # エンコードタスクがキャンセルされた場合、処理を中断する
                    if self._is_cancelled is True:
                        break

                    # エンコーダーの出力読み取りタイムアウトをチェック
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_read_time > read_timeout:
                        logging.warning(f'[Video: {self.video_stream.session_id}][Segment {current_sequence}] Encoder output read timeout.')
                        break

                    # 同期バイトを探す
                    try:
                        if self._encoder_process is None:
                            # もしエンコーダープロセスが終了していたら処理を中断する
                            break
                        sync_byte = await asyncio.wait_for(self._encoder_process.stdout.readexactly(1), timeout=5.0)
                        if sync_byte == b'':
                            break
                        if sync_byte != ts.SYNC_BYTE:
                            continue
                        last_read_time = current_time  # 正常に読み取れた場合はタイムアウトをリセット
                    except (asyncio.IncompleteReadError, asyncio.TimeoutError):
                        break

                    # TS パケットを読み込む
                    try:
                        if self._encoder_process is None:
                            # もしエンコーダープロセスが終了していたら処理を中断する
                            break
                        packet = sync_byte + await asyncio.wait_for(self._encoder_process.stdout.readexactly(ts.PACKET_SIZE - 1), timeout=5.0)
                        last_read_time = current_time  # 正常に読み取れた場合はタイムアウトをリセット
                    except (asyncio.IncompleteReadError, asyncio.TimeoutError):
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
                                        logging.debug_simple(f'[Video: {self.video_stream.session_id}] H.264 PID: 0x{elementary_pid:04x}')
                                elif stream_type == 0x24:  # H.265
                                    if self._video_pid is None:
                                        self._video_pid = elementary_pid
                                        logging.debug_simple(f'[Video: {self.video_stream.session_id}] H.265 PID: 0x{elementary_pid:04x}')
                                elif stream_type == 0x0F:  # AAC
                                    if self._audio_pid is None:
                                        self._audio_pid = elementary_pid
                                        logging.debug_simple(f'[Video: {self.video_stream.session_id}] AAC PID: 0x{elementary_pid:04x}')
                            # PMT を再構築して candidate に追加
                            for packet in packetize_section(pmt, False, False, cast(int, self._pmt_pid), 0, self._pmt_cc):
                                encoded_segment += packet
                                self._pmt_cc = (self._pmt_cc + 1) & 0x0F

                    # 映像ストリーム
                    elif pid == self._video_pid:
                        self._video_parser.push(packet)
                        for video in self._video_parser:
                            timestamp = cast(int, video.dts() or video.pts()) / ts.HZ

                            # セグメントの終了時刻を超えたら、現在のセグメントを確定して次のセグメントへ
                            if self._current_segment is not None and \
                                timestamp >= (self._current_segment.start_dts + self._current_segment.duration_seconds * ts.HZ) / ts.HZ:
                                # Future がまだ未完了の場合にのみ結果を設定する
                                if not self._current_segment.encoded_segment_ts_future.done():
                                    self._current_segment.encoded_segment_ts_future.set_result(bytes(encoded_segment))
                                self._current_segment.encode_status = 'Completed'
                                logging.info(f'[Video: {self.video_stream.session_id}][Segment {current_sequence}] Successfully Encoded HLS Segment.')

                                # 次のセグメントへ移行
                                current_sequence += 1

                                # 最終セグメントの場合はループを抜ける
                                if current_sequence >= len(self.video_stream.segments):
                                    logging.info(f'[Video: {self.video_stream.session_id}] Reached the final segment.')
                                    break

                                logging.info(f'[Video: {self.video_stream.session_id}][Segment {current_sequence}] Encoding...')
                                self._current_segment = self.video_stream.segments[current_sequence]
                                self._current_segment.encode_status = 'Encoding'
                                encoded_segment = bytearray()

                                # 新しいセグメントの先頭に PAT と PMT を追加
                                if latest_pat is not None:
                                    for packet in packetize_section(latest_pat, False, False, 0, 0, self._pat_cc):
                                        encoded_segment += packet
                                        self._pat_cc = (self._pat_cc + 1) & 0x0F
                                if latest_pmt is not None:
                                    for packet in packetize_section(latest_pmt, False, False, cast(int, self._pmt_pid), 0, self._pmt_cc):
                                        encoded_segment += packet
                                        self._pmt_cc = (self._pmt_cc + 1) & 0x0F

                                break

                            # PES パケットを再構築して candidate に追加
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

                # エンコーダープロセスを終了
                if self._encoder_process is not None:
                    try:
                        if self._encoder_process.returncode is None:
                            self._encoder_process.kill()
                            await asyncio.wait_for(self._encoder_process.wait(), timeout=5.0)  # プロセスの終了を待機
                    except (Exception, asyncio.TimeoutError) as ex:
                        logging.error(f'[Video: {self.video_stream.session_id}] Failed to terminate encoder process:', exc_info=ex)
                    self._encoder_process = None

                # tsreadex プロセスを終了
                if self._tsreadex_process is not None:
                    try:
                        if self._tsreadex_process.returncode is None:
                            self._tsreadex_process.kill()
                            await asyncio.wait_for(self._tsreadex_process.wait(), timeout=5.0)  # プロセスの終了を待機
                    except (Exception, asyncio.TimeoutError) as ex:
                        logging.error(f'[Video: {self.video_stream.session_id}] Failed to terminate tsreadex process:', exc_info=ex)
                    self._tsreadex_process = None

                # 最終セグメントの場合はループを抜ける
                if current_sequence >= len(self.video_stream.segments):
                    break

        finally:
            # ファイルを閉じる
            file.close()

            # 最後のセグメントが完了していない場合は、現在のバッファを future にセット
            if self._current_segment is not None and not self._is_cancelled and not self._current_segment.encoded_segment_ts_future.done():
                self._current_segment.encoded_segment_ts_future.set_result(bytes(encoded_segment))
                self._current_segment.encode_status = 'Completed'
                logging.info(f'[Video: {self.video_stream.session_id}][Segment {current_sequence}] Successfully Encoded Final HLS Segment.')

            # エンコードタスクでのすべての処理を完了した
            self._is_finished = True
            logging.info(f'[Video: {self.video_stream.session_id}] Finished the Encoding Task.')


    async def cancel(self) -> None:
        """
        起動中のエンコードタスクをキャンセルし、起動中の外部プロセスを終了する
        """

        # すでにエンコードタスクが完了している場合は何もしない
        if self._is_finished is True:
            logging.info(f'[Video: {self.video_stream.session_id}] The Encoding Task is already finished.')
            return

        if self._is_cancelled is False:

            # エンコードタスクがキャンセルされたことを示すフラグを立てる
            ## この時点でまだ run() やエンコーダーが実行中であれば、run() やエンコーダーはこのフラグを見て自ら終了する
            ## できるだけ早い段階でフラグを立てておくことが重要
            self._is_cancelled = True

            # tsreadex プロセスを強制終了する
            if self._tsreadex_process is not None:
                try:
                    if self._tsreadex_process.returncode is None:
                        self._tsreadex_process.kill()
                except Exception as ex:
                    logging.error(f'[Video: {self.video_stream.session_id}] Failed to terminate tsreadex process:', exc_info=ex)
                self._tsreadex_process = None

            # エンコーダープロセスを強制終了する
            if self._encoder_process is not None:
                try:
                    if self._encoder_process.returncode is None:
                        self._encoder_process.kill()
                except Exception as ex:
                    logging.error(f'[Video: {self.video_stream.session_id}] Failed to terminate encoder process:', exc_info=ex)
                self._encoder_process = None
