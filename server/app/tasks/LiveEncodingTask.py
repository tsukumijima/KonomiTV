
import asyncio
import os
import re
import requests
import socket
import subprocess
import threading
import time
from datetime import datetime
from io import TextIOWrapper
from tortoise import timezone
from typing import BinaryIO, cast, Iterator, Literal

from app.constants import API_REQUEST_HEADERS, CONFIG, LIBRARY_PATH, LOGS_DIR, QUALITY, QUALITY_TYPES
from app.models import Channel
from app.models import LiveStream
from app.models import Program
from app.utils import Logging
from app.utils.EDCB import EDCBTuner
from app.utils.hls import LiveLLHLSSegmenter


class LiveEncodingTask:

    # H.264 再生時のエンコード後のストリームの GOP 長 (秒)
    GOP_LENGTH_SECOND_H264 = 0.5

    # H.265 再生時のエンコード後のストリームの GOP 長 (秒)
    GOP_LENGTH_SECOND_H265 = 2

    # チューナーから放送波 TS を読み取る際のタイムアウト (秒)
    TUNER_TS_READ_TIMEOUT = 15

    # エンコーダーの出力を読み取る際のタイムアウト (Standby 時) (秒)
    ENCODER_TS_READ_TIMEOUT_STANDBY = 20

    # エンコーダーの出力を読み取る際のタイムアウト (ONAir 時) (秒)
    ENCODER_TS_READ_TIMEOUT_ONAIR = 5


    def __init__(self, livestream: LiveStream) -> None:
        """
        LiveStream のインスタンスに基づくライブエンコードタスクを初期化する
        このエンコードタスクが LiveStream を実質的に制御する形になる

        Args:
            livestream (LiveStream): LiveStream のインスタンス
        """

        # ライブストリームのインスタンスをセット
        self.livestream = livestream

        # エンコードタスクのリトライ回数のカウント
        self._retry_count = 0

        # エンコードタスクの最大リトライ回数
        ## この数を超えた場合はエンコードタスクを再起動しない（無限ループを避ける）
        self._max_retry_count = 5  # 5 回まで


    def isFullHDChannel(self, network_id: int, service_id: int) -> bool:
        """
        ネットワーク ID とサービス ID から、そのチャンネルでフル HD 放送が行われているかを返す
        放送波の PSI/SI から映像の横解像度を取得する手段がないので、現状 ID 決め打ちになっている
        ref: https://twitter.com/highwaymovies/status/1201282179390562305
        ref: https://twitter.com/fkcb222/status/1630877111677485056
        ref: https://scrapbox.io/ci7lus/%E5%9C%B0%E4%B8%8A%E6%B3%A2%E3%81%AA%E3%81%AE%E3%81%ABFHD%E3%81%AE%E6%94%BE%E9%80%81%E5%B1%80%E6%83%85%E5%A0%B1

        Args:
            network_id (int): ネットワーク ID
            service_id (int): サービス ID

        Returns:
            bool: フル HD 放送が行われているチャンネルかどうか
        """

        # 地デジでフル HD 放送を行っているチャンネルのネットワーク ID と一致する
        ## テレビ宮崎, あいテレビ, びわ湖放送, 奈良テレビ, KBS京都, KNB北日本放送, とちぎテレビ, ABS秋田放送
        if network_id in [31811, 31940, 32038, 32054, 32102, 32162, 32311, 32466]:
            return True

        # BS でフル HD 放送を行っているチャンネルのサービス ID と一致する
        ## NHK BSプレミアム・WOWOWプライム・WOWOWライブ・WOWOWシネマ・BS11
        if network_id == 4 and service_id in [103, 191, 192, 193, 211]:
            return True

        return False


    def buildFFmpegOptions(self,
        quality: QUALITY_TYPES,
        is_fullhd_channel: bool = False,
        is_sphd_channel: bool = False,
    ) -> list:
        """
        FFmpeg に渡すオプションを組み立てる

        Args:
            quality (QUALITY_TYPES): 映像の品質
            is_fullhd_channel (bool): フル HD 放送が実施されているチャンネルかどうか
            is_sphd_channel (bool): スカパー！プレミアムサービスのチャンネルかどうか

        Returns:
            list: FFmpeg に渡すオプションが連なる配列
        """

        # オプションの入る配列
        options = []

        # 入力ストリームの解析時間
        analyzeduration = round(500000 + (self._retry_count * 200000))  # リトライ回数に応じて少し増やす
        if is_sphd_channel is True:
            # スカパー！プレミアムサービスのチャンネルは入力ストリームの解析時間を長めにする (その方がうまくいく)
            ## ほかと違い H.264 コーデックが採用されていることが影響しているのかも
            analyzeduration += 200000

        # 入力
        ## -analyzeduration をつけることで、ストリームの分析時間を短縮できる
        options.append(f'-f mpegts -analyzeduration {analyzeduration} -i pipe:0')

        # ストリームのマッピング
        ## 音声切り替えのため、主音声・副音声両方をエンコード後の TS に含む
        ## 副音声が検出できない場合にエラーにならないよう、? をつけておく
        options.append('-map 0:v:0 -map 0:a:0 -map 0:a:1 -map 0:d? -ignore_unknown')

        # フラグ
        ## 主に FFmpeg の起動を高速化するための設定
        max_interleave_delta = round(1 + self._retry_count) * 100
        options.append(f'-fflags nobuffer -flags low_delay -max_delay 250000 -max_interleave_delta {max_interleave_delta}K -threads auto')

        # 映像
        ## コーデック
        if QUALITY[quality].is_hevc is True:
            options.append('-vcodec libx265')  # H.265/HEVC (通信節約モード)
        else:
            options.append('-vcodec libx264')  # H.264

        ## ビットレートと品質
        options.append(f'-flags +cgop -vb {QUALITY[quality].video_bitrate} -maxrate {QUALITY[quality].video_bitrate_max}')
        options.append('-profile:v main -preset veryfast -aspect 16:9')

        ## フル HD 放送が行われているチャンネルかつ、指定された品質の解像度が 1440×1080 (1080p) の場合のみ、
        ## 特別に縦解像度を 1920 に変更してフル HD (1920×1080) でエンコードする
        video_width = QUALITY[quality].width
        video_height = QUALITY[quality].height
        if video_width == 1440 and video_height == 1080 and is_fullhd_channel is True:
            video_width = 1920

        ## 最大 GOP 長 (秒)
        ## 30fps なら ×30 、 60fps なら ×60 された値が --gop-len で使われる
        gop_length_second = self.GOP_LENGTH_SECOND_H264
        if QUALITY[quality].is_hevc is True:
            ## H.265/HEVC では高圧縮化のため、最大 GOP 長を長くする
            gop_length_second = self.GOP_LENGTH_SECOND_H265

        ## インターレース解除 (60i → 60p (フレームレート: 60fps))
        if QUALITY[quality].is_60fps is True:
            options.append(f'-r 60000/1001 -g {int(gop_length_second * 60)}')
            options.append(f'-vf yadif=mode=1:parity=-1:deint=1,scale={video_width}:{video_height}')
        ## インターレース解除 (60i → 30p (フレームレート: 30fps))
        else:
            options.append(f'-r 30000/1001 -g {int(gop_length_second * 30)}')
            options.append(f'-vf yadif=mode=0:parity=-1:deint=1,scale={video_width}:{video_height}')

        # 音声
        ## 音声が 5.1ch かどうかに関わらず、ステレオにダウンミックスする
        options.append(f'-acodec aac -aac_coder twoloop -ac 2 -ab {QUALITY[quality].audio_bitrate} -ar 48000 -af volume=2.0')

        # 出力
        options.append('-y -f mpegts')  # MPEG-TS 出力ということを明示
        options.append('pipe:1')  # 標準入力へ出力

        # オプションをスペースで区切って配列にする
        result = []
        for option in options:
            result += option.split(' ')

        return result


    def buildFFmpegOptionsForRadio(self) -> list:
        """
        FFmpeg に渡すオプションを組み立てる（ラジオチャンネル向け）
        音声の品質は変えたところでほとんど差がないため、1つだけに固定されている
        品質が固定ならコードにする必要は基本ないんだけど、可読性を高めるために敢えてこうしてある

        Returns:
            list: FFmpeg に渡すオプションが連なる配列
        """

        # オプションの入る配列
        options = []

        # 入力
        ## -analyzeduration をつけることで、ストリームの分析時間を短縮できる
        analyzeduration = round(500000 + (self._retry_count * 200000))  # リトライ回数に応じて少し増やす
        options.append(f'-f mpegts -analyzeduration {analyzeduration} -i pipe:0')

        # ストリームのマッピング
        # 音声切り替えのため、主音声・副音声両方をエンコード後の TS に含む
        options.append('-map 0:a:0 -map 0:a:1 -map 0:d? -ignore_unknown')

        # フラグ
        ## 主に FFmpeg の起動を高速化するための設定
        max_interleave_delta = round(1 + self._retry_count) * 100
        options.append(f'-fflags nobuffer -flags low_delay -max_delay 250000 -max_interleave_delta {max_interleave_delta}K -threads auto')

        # 音声
        ## 音声が 5.1ch かどうかに関わらず、ステレオにダウンミックスする
        options.append(f'-acodec aac -aac_coder twoloop -ac 2 -ab 192K -ar 48000 -af volume=2.0')

        # 出力
        options.append('-y -f mpegts')  # MPEG-TS 出力ということを明示
        options.append('pipe:1')  # 標準入力へ出力

        # オプションをスペースで区切って配列にする
        result = []
        for option in options:
            result += option.split(' ')

        return result


    def buildHWEncCOptions(self,
        quality: QUALITY_TYPES,
        encoder_type: Literal['QSVEncC', 'NVEncC', 'VCEEncC'],
        is_fullhd_channel: bool = False,
        is_sphd_channel: bool = False,
    ) -> list:
        """
        QSVEncC・NVEncC・VCEEncC (便宜上 HWEncC と総称) に渡すオプションを組み立てる

        Args:
            quality (QUALITY_TYPES): 映像の品質
            encoder_type (Literal['QSVEncC', 'NVEncC', 'VCEEncC']): エンコーダー (QSVEncC or NVEncC or VCEEncC)
            is_fullhd_channel (bool): フル HD 放送が実施されているチャンネルかどうか
            is_sphd_channel (bool): スカパー！プレミアムサービスのチャンネルかどうか

        Returns:
            list: HWEncC に渡すオプションが連なる配列
        """

        # オプションの入る配列
        options = []

        # 入力ストリームの解析時間
        input_probesize = round(1000 + (self._retry_count * 500))  # リトライ回数に応じて少し増やす
        input_analyze = round(0.7 + (self._retry_count * 0.2), 1)  # リトライ回数に応じて少し増やす
        if is_sphd_channel is True:
            # スカパー！プレミアムサービスのチャンネルは入力ストリームの解析時間を長めにする (その方がうまくいく)
            ## ほかと違い H.264 コーデックが採用されていることが影響しているのかも
            input_probesize += 500
            input_analyze += 0.2

        # 入力
        ## --input-probesize, --input-analyze をつけることで、ストリームの分析時間を短縮できる
        ## 両方つけるのが重要で、--input-analyze だけだとエンコーダーがフリーズすることがある
        options.append(f'--input-format mpegts --fps 30000/1001 --input-probesize {input_probesize}K --input-analyze {input_analyze} --input -')
        ## VCEEncC の HW デコーダーはエラー耐性が低く TS を扱う用途では不安定なので、SW デコーダーを利用する
        if encoder_type == 'VCEEncC':
            options.append('--avsw')
        ## QSVEncC・NVEncC は HW デコーダーを利用する
        else:
            options.append('--avhw')

        # ストリームのマッピング
        ## 音声切り替えのため、主音声・副音声両方をエンコード後の TS に含む
        ## 音声が 5.1ch かどうかに関わらず、ステレオにダウンミックスする
        options.append('--audio-stream 1?:stereo --audio-stream 2?:stereo --data-copy timed_id3')

        # フラグ
        ## 主に HWEncC の起動を高速化するための設定
        max_interleave_delta = round(1 + self._retry_count) * 100
        options.append(f'-m avioflags:direct -m fflags:nobuffer+flush_packets -m flush_packets:1 -m max_delay:250000 -m max_interleave_delta:{max_interleave_delta}K --output-thread 0 --lowlatency')
        ## その他の設定
        options.append('--log-level debug')

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

        ## 品質
        if encoder_type == 'QSVEncC':
            options.append('--quality balanced')
        elif encoder_type == 'NVEncC':
            options.append('--preset default')
        elif encoder_type == 'VCEEncC':
            options.append('--preset balanced')
        options.append(f'--profile main --interlace tff --dar 16:9')

        ## 最大 GOP 長 (秒)
        ## 30fps なら ×30 、 60fps なら ×60 された値が --gop-len で使われる
        gop_length_second = self.GOP_LENGTH_SECOND_H264
        if QUALITY[quality].is_hevc is True:
            ## H.265/HEVC では高圧縮化のため、最大 GOP 長を長くする
            gop_length_second = self.GOP_LENGTH_SECOND_H265

        ## インターレース解除 (60i → 60p (フレームレート: 60fps))
        ## NVEncC の --vpp-deinterlace bob は品質が悪いので、代わりに --vpp-yadif を使う
        ## VCEEncC では --vpp-deinterlace 自体が使えないので、代わりに --vpp-yadif を使う
        if QUALITY[quality].is_60fps is True:
            if encoder_type == 'QSVEncC':
                options.append('--vpp-deinterlace bob')
            elif encoder_type == 'NVEncC' or encoder_type == 'VCEEncC':
                options.append('--vpp-yadif mode=bob')
            options.append(f'--avsync cfr --gop-len {int(gop_length_second * 60)}')
        ## インターレース解除 (60i → 30p (フレームレート: 30fps))
        ## VCEEncC では --vpp-deinterlace 自体が使えないので、代わりに --vpp-afs を使う
        else:
            if encoder_type == 'QSVEncC' or encoder_type == 'NVEncC':
                options.append(f'--vpp-deinterlace normal')
            elif encoder_type == 'VCEEncC':
                options.append(f'--vpp-afs preset=default')
            options.append(f'--avsync forcecfr --gop-len {int(gop_length_second * 30)}')

        ## フル HD 放送が行われているチャンネルかつ、指定された品質の解像度が 1440×1080 (1080p) の場合のみ、
        ## 特別に縦解像度を 1920 に変更してフル HD (1920×1080) でエンコードする
        video_width = QUALITY[quality].width
        video_height = QUALITY[quality].height
        if video_width == 1440 and video_height == 1080 and is_fullhd_channel is True:
            video_width = 1920
        options.append(f'--output-res {video_width}x{video_height}')

        # 音声
        options.append(f'--audio-codec aac:aac_coder=twoloop --audio-bitrate {QUALITY[quality].audio_bitrate}')
        options.append(f'--audio-samplerate 48000 --audio-filter volume=2.0 --audio-ignore-decode-error 30')

        # 出力
        options.append('--output-format mpegts')  # MPEG-TS 出力ということを明示
        options.append('--output -')  # 標準入力へ出力

        # オプションをスペースで区切って配列にする
        result = []
        for option in options:
            result += option.split(' ')

        return result


    async def run(self) -> None:
        """
        エンコードタスクを実行する
        """

        # まだ Standby になっていなければ、ステータスを Standby に設定
        # 基本はエンコードタスクの呼び出し元である self.livestream.connect() の方で Standby に設定されるが、再起動の場合はそこを経由しないため必要
        if not (self.livestream.getStatus()['status'] == 'Standby' and self.livestream.getStatus()['detail'] == 'エンコードタスクを起動しています…'):
            self.livestream.setStatus('Standby', 'エンコードタスクを起動しています…')

        # LL-HLS Segmenter に渡す今回のエンコードタスクの GOP 長 (H.264 と H.265 で異なる)
        gop_length_second = self.GOP_LENGTH_SECOND_H264
        if QUALITY[self.livestream.quality].is_hevc is True:
            gop_length_second = self.GOP_LENGTH_SECOND_H265

        # LL-HLS Segmenter を初期化
        ## iPhone Safari は mpegts.js でのストリーミングに対応していないため、フォールバックとして LL-HLS で配信する必要がある
        ## できるだけ早い段階で初期化しておかないと、初期化より前に iOS Safari からプレイリストにアクセスが来てしまい
        ## LL-HLS Segmenter is not running エラーが発生してしまう
        self.livestream.segmenter = LiveLLHLSSegmenter(gop_length_second)

        # チャンネル情報からサービス ID とネットワーク ID を取得する
        channel = await Channel.filter(channel_id=self.livestream.channel_id).first()

        # 現在の番組情報を取得する
        program_present: Program | None = (await channel.getCurrentAndNextProgram())[0]

        # 現在の番組情報が取得できなかった場合、「番組情報がありません」という仮の番組情報を入れておく（実装上の都合）
        ## このデータは UI 上には表示されないし、データベースにも保存されない
        if program_present is None:
            program_present = Program()
            program_present.id = f'NID{channel.network_id}-SID{channel.service_id}-EID99999'
            program_present.network_id = channel.network_id
            program_present.service_id = channel.service_id
            program_present.event_id = 99999  # 適当に 99999 に設定
            program_present.channel_id = channel.channel_id
            program_present.title = '番組情報がありません'
            program_present.description = ''
            program_present.start_time = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.get_default_timezone())
            program_present.end_time = datetime(2099, 1, 1, 0, 0, 0, tzinfo=timezone.get_default_timezone())
            program_present.duration = (program_present.end_time - program_present.start_time).total_seconds()
            program_present.is_free = True
            program_present.genre = []

        Logging.info(f'[Live: {self.livestream.livestream_id}] Title:{program_present.title}')

        # tsreadex のオプション
        ## 放送波の前処理を行い、エンコードを安定させるツール
        ## オプション内容は https://github.com/xtne6f/tsreadex を参照
        tsreadex_options = [
            # 取り除く TS パケットの10進数の PID
            ## EIT の PID を指定
            '-x', '18/38/39',
            # 特定サービスのみを選択して出力するフィルタを有効にする
            ## 有効にすると、特定のストリームのみ PID を固定して出力される
            ## 視聴対象のチャンネルのサービス ID を指定する
            '-n', f'{channel.service_id}',
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
        ]

        if 'debug_mode_ts_path' not in CONFIG['tv'] or CONFIG['tv']['debug_mode_ts_path'] is None:
            # 通常は標準入力を指定
            tsreadex_options.append('-')
        else:
            # デバッグモード: 指定された TS ファイルを読み込む
            ## 読み込み速度を 2350KB/s (18.8Mbps) に制限
            ## 1倍速に近い値だが、TS のビットレートはチャンネルや番組、シーンによって変動するため完全な1倍速にはならない
            tsreadex_options += [
                '-l', '2350',
                CONFIG['tv']['debug_mode_ts_path']
            ]

        # tsreadex の読み込み用パイプと書き込み用パイプを作成
        tsreadex_read_pipe, tsreadex_write_pipe = os.pipe()

        # tsreadex の起動
        ## Reader だけ同期関数なので、asyncio.subprocess ではなく通常の subprocess を使っている (苦肉の策)
        tsreadex: subprocess.Popen = subprocess.Popen(
            [LIBRARY_PATH['tsreadex'], *tsreadex_options],
            stdin = asyncio.subprocess.PIPE,  # 受信した放送波を書き込む
            stdout = tsreadex_write_pipe,  # エンコーダーに繋ぐ
        )

        # tsreadex の書き込み用パイプを閉じる
        os.close(tsreadex_write_pipe)

        # ***** エンコーダープロセスの作成と実行 *****

        # エンコーダーの起動には時間がかかるので、先にエンコーダーを起動しておいた後、あとからチューナーを起動する
        # チューナーの起動後にエンコーダー (正確には tsreadex) に受信した放送波が書き込まれる
        # チューナーの起動にも時間がかかるが、エンコーダーの起動は非同期なのに対し、チューナーの起動は EDCB の場合は同期的

        # フル HD 放送が行われているチャンネルかを取得
        is_fullhd_channel = self.isFullHDChannel(channel.network_id, channel.service_id)

        # エンコーダーの種類を取得
        encoder_type: Literal['FFmpeg', 'QSVEncC', 'NVEncC', 'VCEEncC'] = CONFIG['general']['encoder']
        ## ラジオチャンネルでは HW エンコードの意味がないため、FFmpeg に固定する
        if channel.is_radiochannel is True:
            encoder_type = 'FFmpeg'

        # FFmpeg
        if encoder_type == 'FFmpeg':

            # オプションを取得
            # ラジオチャンネルかどうかでエンコードオプションを切り替え
            if channel.is_radiochannel is True:
                encoder_options = self.buildFFmpegOptionsForRadio()
            else:
                encoder_options = self.buildFFmpegOptions(self.livestream.quality, is_fullhd_channel, channel.channel_type == 'SKY')
            Logging.info(f'[Live: {self.livestream.livestream_id}] FFmpeg Commands:\nffmpeg {" ".join(encoder_options)}')

            # プロセスを非同期で作成・実行
            encoder: asyncio.subprocess.Process = await asyncio.subprocess.create_subprocess_exec(
                *[LIBRARY_PATH['FFmpeg'], *encoder_options],
                stdin = tsreadex_read_pipe,  # tsreadex からの入力
                stdout = asyncio.subprocess.PIPE,  # ストリーム出力
                stderr = asyncio.subprocess.PIPE,  # ログ出力
            )

        # HWEncC
        elif encoder_type == 'QSVEncC' or encoder_type == 'NVEncC' or encoder_type == 'VCEEncC':

            # オプションを取得
            encoder_options = self.buildHWEncCOptions(self.livestream.quality, encoder_type, is_fullhd_channel, channel.channel_type == 'SKY')
            Logging.info(f'[Live: {self.livestream.livestream_id}] {encoder_type} Commands:\n{encoder_type} {" ".join(encoder_options)}')

            # プロセスを非同期で作成・実行
            encoder: asyncio.subprocess.Process = await asyncio.subprocess.create_subprocess_exec(
                *[LIBRARY_PATH[encoder_type], *encoder_options],
                stdin = tsreadex_read_pipe,  # tsreadex からの入力
                stdout = asyncio.subprocess.PIPE,  # ストリーム出力
                stderr = asyncio.subprocess.PIPE,  # ログ出力
            )

        # tsreadex の読み込み用パイプを閉じる
        os.close(tsreadex_read_pipe)

        # ***** チューナーの起動と接続 *****

        # エンコードタスクが稼働中かどうか
        is_running: bool = True

        # EDCB のチューナーインスタンス (Mirakurun バックエンド利用時は常に None)
        tuner: EDCBTuner | None = None

        # Mirakurun バックエンド
        if CONFIG['general']['backend'] == 'Mirakurun':

            # Mirakurun 形式のサービス ID
            # NID と SID を 5 桁でゼロ埋めした上で int に変換する
            mirakurun_service_id = int(str(channel.network_id).zfill(5) + str(channel.service_id).zfill(5))
            # Mirakurun API の URL を作成
            mirakurun_stream_api_url = f'{CONFIG["general"]["mirakurun_url"]}/api/services/{mirakurun_service_id}/stream'

            # Mirakurun の Service Stream API へ HTTP リクエストを開始
            ## stream=True を設定することで、レスポンスの返却を待たずに処理を進められる
            try:
                self.livestream.setStatus('Standby', 'チューナーを起動しています…')
                response = await asyncio.to_thread(requests.get,
                    url = mirakurun_stream_api_url,
                    headers = {**API_REQUEST_HEADERS, 'X-Mirakurun-Priority': '0'},
                    stream = True,
                    timeout = 15,
                )
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                # 番組名に「放送休止」などが入っていれば停波によるものとみなし、そうでないならチューナーへの接続に失敗したものとする
                if program_present.isOffTheAirProgram():
                    self.livestream.setStatus('Offline', 'この時間は放送を休止しています。')
                else:
                    self.livestream.setStatus('Offline', 'チューナーへの接続に失敗しました。チューナー側に何らかの問題があるかもしれません。')

                # すべての視聴中クライアントのライブストリームへの接続を切断する
                self.livestream.disconnectAll()

                # LL-HLS Segmenter を破棄する
                if self.livestream.segmenter is not None:
                    self.livestream.segmenter.destroy()
                    self.livestream.segmenter = None

                # エンコードタスクを停止する
                return

        # EDCB バックエンド
        elif CONFIG['general']['backend'] == 'EDCB':

            # チューナーインスタンスを初期化
            tuner = EDCBTuner(channel.network_id, channel.service_id, cast(int, channel.transport_stream_id))

            # チューナーを起動する
            # アンロック状態のチューナーインスタンスがあれば、自動的にそのチューナーが再利用される
            self.livestream.setStatus('Standby', 'チューナーを起動しています…')
            is_tuner_opened = await tuner.open()

            # チューナーの起動に失敗した
            # ほとんどがチューナー不足によるものなので、ステータス詳細でもそのように表示する
            # 成功時は tuner.close() するか予約などに割り込まれるまで起動しつづけるので注意
            if is_tuner_opened is False:
                self.livestream.setStatus('Offline', 'チューナーの起動に失敗しました。チューナー不足が原因かもしれません。')

                # チューナーを閉じる
                await tuner.close()

                # すべての視聴中クライアントのライブストリームへの接続を切断する
                self.livestream.disconnectAll()

                # LL-HLS Segmenter を破棄する
                if self.livestream.segmenter is not None:
                    self.livestream.segmenter.destroy()
                    self.livestream.segmenter = None

                # エンコードタスクを停止する
                return

            # チューナーをロックする
            # ロックしないと途中でチューナーの制御を横取りされてしまう
            tuner.lock()

            # チューナーに接続する
            # 放送波が送信される TCP ソケットまたは名前付きパイプを取得する
            self.livestream.setStatus('Standby', 'チューナーに接続しています…')
            pipe_or_socket: BinaryIO | socket.socket | None = await tuner.connect()

            # チューナーへの接続に失敗した
            if pipe_or_socket is None:
                self.livestream.setStatus('Offline', 'チューナーへの接続に失敗しました。チューナー側に何らかの問題があるかもしれません。')

                # チューナーを閉じる
                await tuner.close()

                # すべての視聴中クライアントのライブストリームへの接続を切断する
                self.livestream.disconnectAll()

                # LL-HLS Segmenter を破棄する
                if self.livestream.segmenter is not None:
                    self.livestream.segmenter.destroy()
                    self.livestream.segmenter = None

                # エンコードタスクを停止する
                return

            # ライブストリームにチューナーインスタンスを設定する
            # Idling への切り替え、ONAir への復帰時に LiveStream 側でチューナーのアンロック/ロックが行われる
            self.livestream.tuner = tuner

        # ***** チューナーからの出力の読み込み → tsreadex・エンコーダーへの書き込み *****

        # チューナーからの放送波 TS の最終読み取り時刻 (単調増加時間)
        ## 単に時刻を比較する用途でしか使わないので、time.monotonic() から取得した単調増加時間が入る
        ## Unix Time とかではないので注意
        tuner_ts_read_at: float = time.monotonic()
        tuner_ts_read_at_lock = threading.Lock()

        # Reader だけ同期関数に依存しているので、別スレッドで実行する
        def Reader():

            nonlocal tuner_ts_read_at

            # 受信した放送波が入るイテレータ
            # R/W バッファ: 188B (TS Packet Size) * 256 = 48128B
            ## EDCB
            if CONFIG['general']['backend'] == 'EDCB':
                if type(pipe_or_socket) is socket.socket:
                    # EDCB の TCP ソケットから受信
                    stream_iterator = iter(lambda: cast(socket.socket, pipe_or_socket).recv(48128), b'')
                else:
                    # EDCB の名前付きパイプから受信
                    stream_iterator = iter(lambda: cast(BinaryIO, pipe_or_socket).read(48128), b'')
            ## Mirakurun
            elif CONFIG['general']['backend'] == 'Mirakurun':
                # Mirakurun の HTTP API から受信
                stream_iterator: Iterator[bytes] = response.iter_content(chunk_size=48128)

            # EDCB / Mirakurun から受信した放送波を随時 tsreadex の入力に書き込む
            try:
                for chunk in stream_iterator:  # type: ignore

                    # チューナーからの放送波 TS の最終読み取り時刻を更新
                    with tuner_ts_read_at_lock:
                        tuner_ts_read_at = time.monotonic()

                    # ストリームデータを tsreadex の標準入力に書き込む
                    ## BrokenPipeError や OSError が発生した場合は回復不可能なため、タスクを終了
                    try:
                        tsreadex.stdin.write(bytes(chunk))
                    except BrokenPipeError:
                        break
                    except OSError:
                        break

                    # エンコードタスクが終了しているか既にエンコーダープロセスが終了していたら、タスクを終了
                    if is_running is False or tsreadex.returncode is not None or encoder.returncode is not None:
                        break

            except OSError:
                pass

            # タスクを終える前に、チューナーとの接続を明示的に閉じる
            try:
                tsreadex.stdin.close()
            except OSError:
                pass
            if CONFIG['general']['backend'] == 'EDCB':
                pipe_or_socket.close()
            elif CONFIG['general']['backend'] == 'Mirakurun':
                response.close()

        # threading を使うのが重要、asyncio.to_thread() を使うとボトルネックになる
        threading.Thread(target=Reader).start()

        # ***** tsreadex・エンコーダーからの出力の読み込み → ライブストリームへの書き込み *****

        # エンコーダーの出力のチャンクが積み増されていくバッファ
        chunk_buffer: bytearray = bytearray()

        # チャンクの最終書き込み時刻 (単調増加時間)
        ## 単に時刻を比較する用途でしか使わないので、time.monotonic() から取得した単調増加時間が入る
        ## Unix Time とかではないので注意
        chunk_written_at: float = 0

        # Writer の排他ロック
        ## タスク間共有の変数を Writer() タスクと SubWriter() タスクの両方から読み書きするため、
        ## chunk_buffer / chunk_written_at にアクセスする際は排他ロックを掛けておく必要がある
        ## そうしないと稀にパケロスするらしく、ブラウザ側で突如再生できなくなることがある
        writer_lock = asyncio.Lock()

        async def Writer():

            nonlocal chunk_buffer, chunk_written_at, writer_lock

            while True:
                try:

                    # エンコーダーからの出力を読み取る
                    ## TS パケットのサイズが 188 bytes なので、1回の readexactly() で 188 bytes ずつ読み取る
                    ## read() ではなく厳密な readexactly() を使わないとぴったり 188 bytes にならない場合がある
                    chunk = await cast(asyncio.StreamReader, encoder.stdout).readexactly(188)

                    # 受け取った TS パケットを LL-HLS Segmenter に渡す
                    if self.livestream.segmenter is not None:
                        self.livestream.segmenter.pushTSPacketData(chunk)

                    # 同時に chunk_buffer / chunk_written_at にアクセスするタスクが1つだけであることを保証する (排他ロック)
                    async with writer_lock:

                        # 188 bytes ごとに区切られた、エンコーダーの出力のチャンクをバッファに貯める
                        chunk_buffer.extend(chunk)

                        # チャンクバッファが 65536 bytes (64KB) 以上になった時のみ
                        if len(chunk_buffer) >= 65536:

                            # エンコーダーからの出力をライブストリームの Queue に書き込む
                            await self.livestream.writeStreamData(bytes(chunk_buffer))
                            # print(f'Writer:    Chunk size: {len(chunk_buffer):05} / Time: {time.time()}')

                            # チャンクバッファを空にする（重要）
                            chunk_buffer = bytearray()

                            # チャンクの最終書き込み時刻を更新
                            chunk_written_at = time.monotonic()

                # もし 188 bytes に満たないデータが返ってきたら、エンコーダーが終了したと判断してタスクを終了
                except asyncio.IncompleteReadError:
                    break

                # エンコードタスクが終了しているか既にエンコーダープロセスが終了していたら、タスクを終了
                if is_running is False or tsreadex.returncode is not None or encoder.returncode is not None:
                    break

        # 前回のチャンク書き込みから 0.025 秒以上経ったもののチャンクが 64KB に達していない際に Writer に代わってチャンク書き込みを行うタスク
        ## ラジオチャンネルは通常のチャンネルと比べてデータ量が圧倒的に少ないため、64KB に達することは稀で SubWriter でのチャンク書き込みがメインになる
        async def SubWriter():

            nonlocal tuner_ts_read_at, tuner_ts_read_at_lock, chunk_buffer, chunk_written_at, writer_lock

            while True:

                # チャンクバッファを 0.025 秒間隔でチェックする
                await asyncio.sleep(0.025)

                # 同時に chunk_buffer / chunk_written_at にアクセスするタスクが1つだけであることを保証する (排他ロック)
                async with writer_lock:

                    # 前回チャンクを書き込んでから 0.025 秒以上経過している & チャンクバッファに何かしらデータが入っている時のみ
                    # チャンクをできるだけ等間隔でクライアントに送信するために、バッファが 64KB 分溜まるのを待たずに送信する
                    if (time.monotonic() - chunk_written_at) > 0.025 and (len(chunk_buffer) > 0):

                        # エンコーダーからの出力をライブストリームの Queue に書き込む
                        await self.livestream.writeStreamData(bytes(chunk_buffer))
                        # print(f'SubWriter: Chunk size: {len(chunk_buffer):05} / Time: {time.time()}')

                        # チャンクバッファを空にする（重要）
                        chunk_buffer = bytearray()

                        # チャンクの最終書き込み時刻を更新
                        chunk_written_at = time.monotonic()

                # エンコードタスクが終了しているか既にエンコーダープロセスが終了していたら、タスクを終了
                if is_running is False or tsreadex.returncode is not None or encoder.returncode is not None:
                    break

        # タスクを非同期で実行
        asyncio.create_task(Writer())
        asyncio.create_task(SubWriter())

        # ***** エンコーダーの状態監視 *****

        # エンコーダーの出力ログのリスト
        lines: list[str] = []

        async def EncoderObServer():

            # 1つ上のスコープ (Enclosing Scope) の変数を書き替えるために必要
            # ref: https://excel-ubara.com/python/python014.html#sec04
            nonlocal lines, program_present

            # 既にエンコーダーのログファイルが存在していた場合は上書きしないようにリネーム
            ## ref: https://note.nkmk.me/python-pathlib-name-suffix-parent/
            count = 1
            encoder_log_path = LOGS_DIR / f'KonomiTV-Encoder-{self.livestream.livestream_id}.log'
            while encoder_log_path.exists():
                encoder_log_path = LOGS_DIR / f'KonomiTV-Encoder-{self.livestream.livestream_id}-{count}.log'
                count += 1

            # エンコーダーのログファイルを開く (エンコーダーログ有効時のみ)
            encoder_log: TextIOWrapper | None = None
            if CONFIG['general']['debug_encoder'] is True:
                encoder_log = open(encoder_log_path, mode='w', encoding='utf-8')

            # エンコーダーの出力結果を取得
            while True:

                # 行ごとに随時読み込む
                ## 1バイトずつ読み込み、\r か \n が来たら行としてデコード
                ## FFmpeg はコンソールの行を上書きするために frame= の進捗ログで \r しか出力しないため、readline() を使うと
                ## 進捗ログを取得できずに永遠に Standby から ONAir に移行しない不具合が発生する
                buffer = bytearray()
                while True:
                    byte = await encoder.stderr.read(1)
                    buffer += byte
                    if byte == b'\r' or byte == b'\n':
                        break
                    if byte == b'':
                        break

                # 空のデータが返ってきたら、エンコーダーが終了したと判断してタスクを終了
                if len(buffer) == 0:
                    break

                try:
                    line = buffer.decode('utf-8').strip()
                except UnicodeDecodeError:
                    continue

                # エンコード進捗のログだったら、正規表現で余計なゴミを取り除く
                ## HWEncC は内部で使われている FFmpeg 側の大量に出るデバッグログと衝突してログがごちゃまぜになりがち…
                ## FFmpeg 側のログ（ゴミ）と完全に混ざっていると完全に除去できずに frames: の数値が桁が飛んだような出力になるけどご愛嬌…
                match1 = re.fullmatch(r'^.*?([1-9][0-9]+ frames: [0-9\.]+ fps, [0-9]+ kb/s, GPU [0-9]+%, VE [0-9]+%, VD [0-9]+%)$', line)
                match2 = re.fullmatch(r'^.*?([1-9][0-9]+ frames: [0-9\.]+ fps, [0-9]+ kb/s, GPU [0-9]+%, VD [0-9]+%)$', line)
                match3 = re.fullmatch(r'^.*?([1-9][0-9]+ frames: [0-9\.]+ fps, [0-9]+ kb/s)$', line)
                if match1 is not None:
                    line = match1.groups()[0]
                elif match2 is not None:
                    line = match2.groups()[0]
                elif match3 is not None:
                    line = match3.groups()[0]

                # 山ほど出力されるメッセージと空行をログから除外
                ## 元は "Delay between the first packet and last packet in the muxing queue is xxxxxx > 1: forcing output" と
                ## "removing 2 bytes from input bitstream not read by decoder." という2つのメッセージで、実害はない
                ## FFmpeg と HWEncC のログが衝突して行の先頭が欠けることがあるので、できるだけ多く弾けるように部分一致にしている
                if (('removing 2 bytes from input bitstream not read by decoder.' not in line) and
                    ('Delay between the' not in line) and
                    ('packet in the muxing queue' not in line) and ('ing output' not in line) and
                    ('ng output' != line) and ('g output' != line) and (' output' != line) and ('output' != line) and
                    ('utput' != line) and ('tput' != line) and ('put' != line) and ('ut' != line) and ('t' != line) and
                    ('' != line)):

                    # ログリストに行単位で追加
                    lines.append(line)

                    # ストリーム関連のログを表示
                    ## エンコーダーのログ出力が有効なら、ストリーム関連に限らずすべてのログを出力する
                    if 'Stream #0:' in line or CONFIG['general']['debug_encoder'] is True:
                        Logging.debug_simple(f'[Live: {self.livestream.livestream_id}] [{encoder_type}] ' + line)

                    # エンコーダーのログ出力が有効なら、エンコーダーのログファイルに書き込む
                    if CONFIG['general']['debug_encoder'] is True:
                        encoder_log.write(line.strip('\r\n') + '\n')
                        encoder_log.flush()

                # ライブストリームのステータスを取得
                livestream_status = self.livestream.getStatus()

                # エンコードの進捗を判定し、ステータスを更新する
                # 誤作動防止のため、ステータスが Standby の間のみ更新できるようにする
                if livestream_status['status'] == 'Standby':
                    # FFmpeg
                    if encoder_type == 'FFmpeg':
                        if 'arib parser was created' in line or 'Invalid frame dimensions 0x0.' in line:
                            self.livestream.setStatus('Standby', 'エンコードを開始しています…')
                        elif 'frame=    1 fps=0.0 q=0.0' in line or 'size=       0kB time=00:00' in line:
                            self.livestream.setStatus('Standby', 'バッファリングしています…')
                        elif 'frame=' in line or 'bitrate=' in line:
                            self.livestream.setStatus('ONAir', 'ライブストリームは ONAir です。')
                            # エラーから回復した場合は、エンコードタスクの再起動回数のカウントをリセットする
                            if self._retry_count > 0:
                                self._retry_count = 0
                    ## HWEncC
                    elif encoder_type == 'QSVEncC' or encoder_type == 'NVEncC' or encoder_type == 'VCEEncC':
                        if 'opened file "pipe:0"' in line:
                            self.livestream.setStatus('Standby', 'エンコードを開始しています…')
                        elif 'starting output thread...' in line:
                            self.livestream.setStatus('Standby', 'バッファリングしています…')
                        elif 'Encode Thread:' in line:
                            self.livestream.setStatus('Standby', 'バッファリングしています…')
                        elif ' frames: ' in line:
                            self.livestream.setStatus('ONAir', 'ライブストリームは ONAir です。')
                            # エラーから回復した場合は、エンコードタスクの再起動回数のカウントをリセットする
                            if self._retry_count > 0:
                                self._retry_count = 0

                # 特定のエラーログが出力されている場合は回復が見込めないため、エンコーダーを終了する
                ## エンコーダーを再起動することで回復が期待できる場合は、ステータスを Restart に設定しエンコードタスクを再起動する
                ## FFmpeg
                if encoder_type == 'FFmpeg':
                    if 'Stream map \'0:v:0\' matches no streams.' in line:
                        # 何らかの要因で tsreadex から放送波が受信できなかったことによるエラーのため、エンコーダーの再起動は行わない
                        ## 番組名に「放送休止」などが入っていれば停波によるものとみなし、そうでないなら放送波の受信に失敗したものとする
                        if program_present.isOffTheAirProgram():
                            self.livestream.setStatus('Offline', 'この時間は放送を休止しています。')
                        else:
                            self.livestream.setStatus('Offline', 'チューナーからの放送波の受信に失敗したため、エンコードを開始できません。')
                    elif 'Conversion failed!' in line:
                        # 捕捉されないエラー
                        ## エンコーダーの再起動で復帰できる可能性があるので、エンコードタスクを再起動する
                        self.livestream.setStatus('Restart', 'エンコード中に予期しないエラーが発生しました。エンコードタスクを再起動します。')
                        # 直近 50 件のログを表示
                        for log in lines[-51:-1]:
                            Logging.warning(log)
                ## HWEncC
                elif encoder_type == 'QSVEncC' or encoder_type == 'NVEncC' or encoder_type == 'VCEEncC':
                    if 'error finding stream information.' in line:
                        # 何らかの要因で tsreadex から放送波が受信できなかったことによるエラーのため、エンコーダーの再起動は行わない
                        ## 番組名に「放送休止」などが入っていれば停波によるものとみなし、そうでないなら放送波の受信に失敗したものとする
                        if program_present.isOffTheAirProgram():
                            self.livestream.setStatus('Offline', 'この時間は放送を休止しています。')
                        else:
                            self.livestream.setStatus('Offline', 'チューナーからの放送波の受信に失敗したため、エンコードを開始できません。')
                    elif encoder_type == 'NVEncC' and 'due to the NVIDIA\'s driver limitation.' in line:
                        # NVEncC で、同時にエンコードできるセッション数 (Geforceだと3つ) を全て使い果たしている時のエラー
                        self.livestream.setStatus('Offline', 'NVENC のエンコードセッションが不足しているため、エンコードを開始できません。')
                    elif encoder_type == 'QSVEncC' and ('unable to decode by qsv.' in line or 'No device found for QSV encoding!' in line):
                        # QSVEncC 非対応の環境
                        self.livestream.setStatus('Offline', 'お使いの PC 環境は QSVEncC エンコーダーに対応していません。')
                    elif encoder_type == 'QSVEncC' and 'iHD_drv_video.so init failed' in line:
                        # QSVEncC 非対応の環境 (Linux かつ第5世代以前の Intel CPU)
                        self.livestream.setStatus('Offline', 'お使いの PC 環境は Linux 版 QSVEncC エンコーダーに対応していません。第5世代以前の古い CPU をお使いの可能性があります。')
                    elif encoder_type == 'NVEncC' and 'CUDA not available.' in line:
                        # NVEncC 非対応の環境
                        self.livestream.setStatus('Offline', 'お使いの PC 環境は NVEncC エンコーダーに対応していません。')
                    elif encoder_type == 'VCEEncC' and \
                        ('Failed to initalize VCE factory:' in line or 'Assertion failed:Init() failed to vkCreateInstance' in line):
                        # VCEEncC 非対応の環境
                        self.livestream.setStatus('Offline', 'お使いの PC 環境は VCEEncC エンコーダーに対応していません。')
                    elif encoder_type == 'QSVEncC' and 'HEVC encoding is not supported on current platform.' in line:
                        # QSVEncC: H.265/HEVC でのエンコードに非対応の環境
                        self.livestream.setStatus('Offline', 'お使いの Intel GPU は H.265/HEVC でのエンコードに対応していません。')
                    elif encoder_type == 'NVEncC' and 'does not support H.265/HEVC encoding.' in line:
                        # NVEncC: H.265/HEVC でのエンコードに非対応の環境
                        self.livestream.setStatus('Offline', 'お使いの NVIDIA GPU は H.265/HEVC でのエンコードに対応していません。')
                    elif encoder_type == 'VCEEncC' and 'HW Acceleration of H.265/HEVC is not supported on this platform.' in line:
                        # VCEEncC: H.265/HEVC でのエンコードに非対応の環境
                        self.livestream.setStatus('Offline', 'お使いの AMD GPU は H.265/HEVC でのエンコードに対応していません。')
                    elif 'Consider increasing the value for the --input-analyze and/or --input-probesize!' in line:
                        # --input-probesize or --input-analyze の期間内に入力ストリームの解析が終わらなかった
                        ## エンコーダーの再起動で復帰できる可能性があるので、エンコードタスクを再起動する
                        self.livestream.setStatus('Restart', '入力ストリームの解析に失敗しました。エンコードタスクを再起動します。')
                    elif 'finished with error!' in line:
                        # 捕捉されないエラー
                        ## エンコーダーの再起動で復帰できる可能性があるので、エンコードタスクを再起動する
                        self.livestream.setStatus('Restart', 'エンコード中に予期しないエラーが発生しました。エンコードタスクを再起動します。')
                        # 直近 150 件のログを表示
                        for log in lines[-151:-1]:
                            Logging.warning(log)

                # エンコードタスクが終了しているか既にエンコーダープロセスが終了していたら、タスクを終了
                if is_running is False or tsreadex.returncode is not None or encoder.returncode is not None:
                    break

            # タスクを終える前にエンコーダーのログファイルを閉じる
            if CONFIG['general']['debug_encoder'] is True:
                encoder_log.close()

        # タスクを非同期で実行
        asyncio.create_task(EncoderObServer())

        # ***** エンコードタスク全体の制御 *****

        async def Controller():

            # 1つ上のスコープ (Enclosing Scope) の変数を書き替えるために必要
            # ref: https://excel-ubara.com/python/python014.html#sec04
            nonlocal lines, program_present

            while True:

                # ライブストリームのステータスを取得
                livestream_status = self.livestream.getStatus()

                # 現在放送中の番組が終了した際に program_present に保存している現在の番組情報を新しいものに更新する
                if program_present is not None and time.time() > program_present.end_time.timestamp():

                    # 新しい現在放送中の番組情報を取得する
                    program_following: Program = (await channel.getCurrentAndNextProgram())[0]
                    if program_following is not None:

                        # 現在の番組のタイトルをログに出力
                        ## TODO: 番組の解像度が変わった際にエンコーダーがクラッシュorフリーズする可能性があるが、
                        ## その場合はここでエンコードタスクを再起動させる必要があるかも
                        Logging.info(f'[Live: {self.livestream.livestream_id}] Title:{program_following.title}')

                    program_present = program_following
                    del program_following

                # 現在 ONAir でかつクライアント数が 0 なら Idling（アイドリング状態）に移行
                if livestream_status['status'] == 'ONAir' and livestream_status['clients_count'] == 0:
                    self.livestream.setStatus('Idling', 'ライブストリームは Idling です。')

                # 現在 Idling でかつ最終更新から max_alive_time 秒以上経っていたらエンコーダーを終了し、Offline 状態に移行
                if ((livestream_status['status'] == 'Idling') and
                    (time.time() - livestream_status['updated_at'] > CONFIG['tv']['max_alive_time'])):
                    self.livestream.setStatus('Offline', 'ライブストリームは Offline です。')

                # ***** 異常処理 (エンコードタスク再起動による回復が不可能) *****

                # 前回チューナーからの放送波 TS を読み取ってから TUNER_TS_READ_TIMEOUT 秒以上経過していたら、
                # 停波中もしくはチューナーからの放送波 TS の送信が停止したと判断して Offline に移行
                with tuner_ts_read_at_lock:
                    if (time.monotonic() - tuner_ts_read_at) > self.TUNER_TS_READ_TIMEOUT:

                        # 番組名に「放送休止」などが入っていれば停波の可能性が高い
                        if program_present.isOffTheAirProgram():
                            self.livestream.setStatus('Offline', 'この時間は放送を休止しています。')

                        # それ以外なら、チューナーへの接続に失敗したものとする
                        else:
                            self.livestream.setStatus('Offline', 'チューナーへの接続に失敗しました。チューナー側に何らかの問題があるかもしれません。')

                # Mirakurun の Service Stream API からエラーが返された場合
                if CONFIG['general']['backend'] == 'Mirakurun' and response.status_code is not None and response.status_code != 200:
                    # Offline にしてエンコードタスクを停止する
                    if response.status_code == 503:
                        self.livestream.setStatus('Offline', 'チューナーの起動に失敗しました。チューナー不足が原因かもしれません。')
                    else:
                        self.livestream.setStatus('Offline', 'チューナーで不明なエラーが発生しました。Mirakurun 側に問題があるかもしれません。')
                    break

                # ***** 異常処理 (エンコードタスク再起動による回復が可能) *****

                # 現在 Standby でかつストリームデータの最終書き込み時刻から
                # ENCODER_TS_READ_TIMEOUT_STANDBY 秒以上が経過しているなら、エンコーダーがフリーズしたものとみなす
                # 現在 ONAir でかつストリームデータの最終書き込み時刻から
                # ENCODER_TS_READ_TIMEOUT_ONAIR 秒以上が経過している場合も、エンコーダーがフリーズしたものとみなす
                ## 何らかの理由でエンコードが途中で停止した場合、livestream.write() が実行されなくなることを利用している
                stream_data_last_write_time = time.time() - self.livestream.getStreamDataWrittenAt()
                if ((livestream_status['status'] == 'Standby' and stream_data_last_write_time > self.ENCODER_TS_READ_TIMEOUT_STANDBY) or
                    (livestream_status['status'] == 'ONAir' and stream_data_last_write_time > self.ENCODER_TS_READ_TIMEOUT_ONAIR)):

                    # 番組名に「放送休止」などが入っている場合、チューナーから出力された放送波 TS に映像/音声ストリームが
                    # 含まれていない可能性が高いので、ここでエンコードタスクを停止する
                    ## 映像/音声ストリームが含まれていない場合は当然ながらエンコーダーはフリーズする
                    if program_present.isOffTheAirProgram():
                        self.livestream.setStatus('Offline', 'この時間は放送を休止しています。')

                    # それ以外なら、エンコーダーの再起動で復帰できる可能性があるのでエンコードタスクを再起動する
                    else:

                        # できるだけエンコーダーのエラーメッセージを拾ってログを出力してから終了したいので、1秒間実行を待機する
                        await asyncio.sleep(1)

                        # エンコードタスクを再起動
                        self.livestream.setStatus('Restart', 'エンコードが途中で停止しました。エンコードタスクを再起動します。')

                        # エンコーダーのログを表示 (FFmpeg は最後の50行、HWEncC は最後の150行を表示)
                        if encoder_type == 'FFmpeg':
                            for log in lines[-51:-1]:
                                Logging.warning(log)
                        elif encoder_type == 'QSVEncC' or encoder_type == 'NVEncC' or encoder_type == 'VCEEncC':
                            for log in lines[-151:-1]:
                                Logging.warning(log)

                # エンコーダーが意図せず終了した場合
                if encoder.returncode is not None:

                    # エンコードタスクを再起動
                    self.livestream.setStatus('Restart', 'エンコーダーが強制終了されました。エンコードタスクを再起動します。')

                    # エンコーダーのログを表示 (FFmpeg は最後の50行、HWEncC は最後の150行を表示)
                    if encoder_type == 'FFmpeg':
                        for log in lines[-51:-1]:
                            Logging.warning(log)
                    elif encoder_type == 'QSVEncC' or encoder_type == 'NVEncC' or encoder_type == 'VCEEncC':
                        for log in lines[-151:-1]:
                            Logging.warning(log)

                # tsreadex が意図せず終了したか、チューナーとの接続が切断された場合
                ## エンコーダーが異常終了した場合、パイプが閉じられることで tsreadex も同時に終了してしまうため、
                ## エンコーダーの異常終了判定を終えた後にチェックする必要がある
                ## ref: https://stackoverflow.com/a/45251241/17124142
                if ((tsreadex.returncode is not None) or
                    (CONFIG['general']['backend'] == 'Mirakurun' and response.raw.closed is True) or
                    (CONFIG['general']['backend'] == 'EDCB' and type(pipe_or_socket) is socket.socket and pipe_or_socket.fileno() < 0) or
                    (CONFIG['general']['backend'] == 'EDCB' and type(pipe_or_socket) is BinaryIO and pipe_or_socket.closed is True)):

                    # エンコードタスクを再起動
                    self.livestream.setStatus('Restart', 'チューナーとの接続が切断されました。エンコードタスクを再起動します。')

                # この時点で最新のライブストリームのステータスが Offline か Restart に変更されていたら、エンコードタスクの終了処理に移る
                livestream_status = self.livestream.getStatus()  # 更新されているかもしれないので再取得
                if livestream_status['status'] == 'Offline' or livestream_status['status'] == 'Restart':
                    break

                # ビジーにならないように 0.1 秒待機
                await asyncio.sleep(0.1)

        # エンコードタスクの終了を待つ
        await Controller()

        # ***** エンコードタスクの終了処理 *****

        # 稼働中フラグをオフにし、Reader・Writer・SubWriter・EncoderObServer のすべての非同期タスクを終了させる
        is_running = False

        # 明示的にエンコーダープロセスを終了する
        ## 何らかの理由で既に終了している場合は何もしない
        try:
            tsreadex.kill()
            encoder.kill()
        except:
            pass

        # すべての視聴中クライアントのライブストリームへの接続を切断する
        self.livestream.disconnectAll()

        # LL-HLS Segmenter を破棄する
        if self.livestream.segmenter is not None:
            self.livestream.segmenter.destroy()
            self.livestream.segmenter = None

        # エンコードタスクを再起動する（エンコーダーの再起動が必要な場合）
        if self.livestream.getStatus()['status'] == 'Restart':

            # チューナーをアンロックする (EDCB バックエンドのみ)
            ## 新しいエンコードタスクが今回立ち上げたチューナーを再利用できるようにする
            ## エンコーダーの再起動が必要なだけでチューナー自体はそのまま使えるし、わざわざ閉じてからもう一度開くのは無駄
            if CONFIG['general']['backend'] == 'EDCB':
                tuner.unlock()

            # 再起動回数が最大再起動回数に達していなければ、再起動する
            if self._retry_count < self._max_retry_count:
                self._retry_count += 1  # カウントを増やす
                await asyncio.sleep(0.1)  # 少し待つ
                asyncio.create_task(self.run())  # 新しいタスクを立ち上げる

            # 最大再起動回数を使い果たしたので、Offline にする
            else:

                # Offline に設定
                if program_present.is_free == True:
                    # 無料番組
                    self.livestream.setStatus('Offline', 'ライブストリームの再起動に失敗しました。')
                else:
                    # 有料番組（契約されていないことが原因の可能性が高いため、そのように表示する）
                    self.livestream.setStatus('Offline', 'ライブストリームの再起動に失敗しました。契約されていないため視聴できません。')

                # チューナーを終了する (EDCB バックエンドのみ)
                ## tuner.close() した時点でそのチューナーインスタンスは意味をなさなくなるので、LiveStream インスタンスのプロパティからも削除する
                if CONFIG['general']['backend'] == 'EDCB':
                    await tuner.close()
                    self.livestream.tuner = None

        # 通常終了
        else:

            # EDCB バックエンドのみ
            if CONFIG['general']['backend'] == 'EDCB':

                # チャンネル切り替え時にチューナーが再利用されるように、3秒ほど待つ
                # 3秒間の間にチューナーの制御権限が新しいエンコードタスクに委譲されれば、下記の通り実際にチューナーが閉じられることはない
                await asyncio.sleep(3)

                # チューナーを終了する（まだ制御を他のチューナーインスタンスに委譲していない場合）
                # Idling に移行しアンロック状態になっている間にチューナーが再利用された場合、制御権限をもう持っていないため実際には何も起こらない
                ## tuner.close() した時点でそのチューナーインスタンスは意味をなさなくなるので、LiveStream インスタンスのプロパティからも削除する
                await tuner.close()
                self.livestream.tuner = None
