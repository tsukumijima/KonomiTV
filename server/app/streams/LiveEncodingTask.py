
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import asyncio
import gc
import os
import re
import sys
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, ClassVar, Literal, cast

import aiofiles
import aiohttp
import anyio
import httpx
from aiofiles.threadpool.text import AsyncTextIOWrapper
from biim.mpeg2ts import ts

from app import logging
from app.config import Config
from app.constants import (
    API_REQUEST_HEADERS,
    HTTPX_CLIENT,
    LIBRARY_PATH,
    LOGS_DIR,
    QUALITY,
    QUALITY_TYPES,
)
from app.models.Channel import Channel
from app.streams.LivePSIDataArchiver import LivePSIDataArchiver
from app.utils import GetMirakurunAPIEndpointURL
from app.utils.edcb.EDCBTuner import EDCBTuner
from app.utils.edcb.PipeStreamReader import PipeStreamReader


if TYPE_CHECKING:
    from app.streams.LiveStream import LiveStream


class LiveEncodingTask:

    # H.264 再生時のエンコード後のストリームの GOP 長 (秒)
    GOP_LENGTH_SECONDS_H264: ClassVar[float] = 0.5

    # H.265 再生時のエンコード後のストリームの GOP 長 (秒)
    GOP_LENGTH_SECONDS_H265: ClassVar[float] = float(2)

    # エンコードタスクの最大リトライ回数
    ## この数を超えた場合はエンコードタスクを再起動しない（無限ループを避ける）
    MAX_RETRY_COUNT: ClassVar[int] = 10  # 10回まで

    # チューナーから放送波 TS を読み取る際のタイムアウト (秒)
    TUNER_TS_READ_TIMEOUT: ClassVar[int] = 15

    # エンコーダーの出力を読み取る際のタイムアウト (Standby 時) (秒)
    ENCODER_TS_READ_TIMEOUT_STANDBY: ClassVar[int] = 20

    # エンコーダーの出力を読み取る際のタイムアウト (ONAir 時) (秒)
    # VCEEncC 利用時のみ起動時に OpenCL シェーダーがコンパイルされる関係で起動が遅いため、10 秒に設定
    ENCODER_TS_READ_TIMEOUT_ONAIR: ClassVar[int] = 5
    ENCODER_TS_READ_TIMEOUT_ONAIR_VCEENCC: ClassVar[int] = 10


    def __init__(self, live_stream: LiveStream) -> None:
        """
        LiveStream のインスタンスに基づくライブエンコードタスクを初期化する
        このエンコードタスクが LiveStream を実質的に制御する形になる

        Args:
            live_stream (LiveStream): LiveStream のインスタンス
        """

        # ライブストリームのインスタンスをセット
        self.live_stream = live_stream

        # エンコードタスクのリトライ回数のカウント
        self._retry_count = 0


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
        ## テレビ宮崎, あいテレビ, びわ湖放送, KNB北日本放送, とちぎテレビ, ABS秋田放送
        if network_id in [31811, 31940, 32038, 32162, 32311, 32466]:
            return True

        # BS でフル HD 放送を行っているチャンネルのサービス ID と一致する
        ## NHK BSプレミアム・WOWOWプライム・WOWOWライブ・WOWOWシネマ・BS11
        if network_id == 0x0004 and service_id in [103, 191, 192, 193, 211]:
            return True

        # BS4K・CS4K (放送終了) は 4K 放送なのでフル HD 扱いとする
        # 現在の KonomiTV は 1920×1080 以上の解像度へのエンコードをサポートしていない
        if network_id == 0x000B or network_id == 0x000C:
            return True

        return False


    def buildFFmpegOptions(self,
        quality: QUALITY_TYPES,
        channel_type: Literal['GR', 'BS', 'CS', 'CATV', 'SKY', 'BS4K'],
        is_fullhd_channel: bool,
    ) -> list[str]:
        """
        FFmpeg に渡すオプションを組み立てる

        Args:
            quality (QUALITY_TYPES): 映像の品質
            channel_type (Literal['GR', 'BS', 'CS', 'CATV', 'SKY', 'BS4K']): チャンネルの種類
            is_fullhd_channel (bool): フル HD 放送が実施されているチャンネルかどうか

        Returns:
            list[str]: FFmpeg に渡すオプションが連なる配列
        """

        # オプションの入る配列
        options: list[str] = []

        # 入力ストリームの解析時間
        analyzeduration = round(500000 + (self._retry_count * 200000))  # リトライ回数に応じて少し増やす
        if channel_type == 'SKY':
            # スカパー！プレミアムサービスのチャンネルは入力ストリームの解析時間を長めにする (その方がうまくいく)
            ## ほかと違い H.264 コーデックが採用されていることが影響しているのかも
            analyzeduration += 200000

        # 入力
        ## -analyzeduration をつけることで、ストリームの分析時間を短縮できる
        options.append(f'-f mpegts -analyzeduration {analyzeduration} -i pipe:0')

        # ストリームのマッピング
        ## 音声切り替えのため、主音声・副音声両方をエンコード後の TS に含む
        options.append('-map 0:v:0 -map 0:a:0 -map 0:a:1 -map 0:d? -ignore_unknown')

        # フラグ
        ## 主に FFmpeg の起動を高速化するための設定
        ## max_interleave_delta: mux 時に影響するオプションで、増やしすぎると CM で詰まりがちになる
        ## リトライなしの場合は 500K (0.5秒) に設定し、リトライ回数に応じて 100K (0.1秒) ずつ増やす
        max_interleave_delta = round(500 + (self._retry_count * 100))
        options.append(f'-fflags nobuffer -flags low_delay -max_delay 250000 -max_interleave_delta {max_interleave_delta}K -threads auto')

        # 映像
        ## コーデック
        if QUALITY[quality].is_hevc is True:
            options.append('-vcodec libx265')  # H.265/HEVC (通信節約モード)
        else:
            options.append('-vcodec libx264')  # H.264

        ## ビットレートと品質
        options.append(f'-flags +cgop -vb {QUALITY[quality].video_bitrate} -maxrate {QUALITY[quality].video_bitrate_max}')
        options.append('-preset veryfast -aspect 16:9')
        if QUALITY[quality].is_hevc is True:
            options.append('-profile:v main')
        else:
            options.append('-profile:v high')

        ## フル HD 放送が行われているチャンネルかつ、指定された品質の解像度が 1440×1080 (1080p) の場合のみ、
        ## 特別に縦解像度を 1920 に変更してフル HD (1920×1080) でエンコードする
        video_width = QUALITY[quality].width
        video_height = QUALITY[quality].height
        if video_width == 1440 and video_height == 1080 and is_fullhd_channel is True:
            video_width = 1920

        ## 最大 GOP 長 (秒)
        ## 30fps なら ×30 、 60fps なら ×60 された値が --gop-len で使われる
        gop_length_second = self.GOP_LENGTH_SECONDS_H264
        if QUALITY[quality].is_hevc is True:
            ## H.265/HEVC では高圧縮化のため、最大 GOP 長を長くする
            gop_length_second = self.GOP_LENGTH_SECONDS_H265

        ## BS4K は 60p (プログレッシブ) で放送されているので、インターレース解除を行わず 60fps でエンコードする
        if channel_type == "BS4K":
            options.append(f'-vf scale={video_width}:{video_height}')
            options.append(f'-r 60000/1001 -g {int(gop_length_second * 60)}')
        else:
            ## インターレース解除 (60i → 60p (フレームレート: 60fps))
            if QUALITY[quality].is_60fps is True:
                options.append(f'-vf yadif=mode=1:parity=-1:deint=1,scale={video_width}:{video_height}')
                options.append(f'-r 60000/1001 -g {int(gop_length_second * 60)}')
            ## インターレース解除 (60i → 30p (フレームレート: 30fps))
            else:
                options.append(f'-vf yadif=mode=0:parity=-1:deint=1,scale={video_width}:{video_height}')
                options.append(f'-r 30000/1001 -g {int(gop_length_second * 30)}')

        # 音声
        ## 音声が 5.1ch かどうかに関わらず、ステレオにダウンミックスする
        options.append(f'-acodec aac -aac_coder twoloop -ac 2 -ab {QUALITY[quality].audio_bitrate} -ar 48000 -af volume=2.0')

        # 出力
        options.append('-y -f mpegts')  # MPEG-TS 出力ということを明示
        options.append('pipe:1')  # 標準入力へ出力

        # オプションをスペースで区切って配列にする
        result: list[str] = []
        for option in options:
            result += option.split(' ')

        return result


    def buildFFmpegOptionsForRadio(self) -> list[str]:
        """
        FFmpeg に渡すオプションを組み立てる（ラジオチャンネル向け）
        音声の品質は変えたところでほとんど差がないため、1つだけに固定されている
        品質が固定ならコードにする必要は基本ないんだけど、可読性を高めるために敢えてこうしてある

        Returns:
            list[str]: FFmpeg に渡すオプションが連なる配列
        """

        # オプションの入る配列
        options: list[str] = []

        # 入力
        ## -analyzeduration をつけることで、ストリームの分析時間を短縮できる
        analyzeduration = round(500000 + (self._retry_count * 200000))  # リトライ回数に応じて少し増やす
        options.append(f'-f mpegts -analyzeduration {analyzeduration} -i pipe:0')

        # ストリームのマッピング
        # 音声切り替えのため、主音声・副音声両方をエンコード後の TS に含む
        options.append('-map 0:a:0 -map 0:a:1 -map 0:d? -ignore_unknown')

        # フラグ
        ## 主に FFmpeg の起動を高速化するための設定
        ## max_interleave_delta: mux 時に影響するオプションで、増やしすぎると CM で詰まりがちになる
        ## リトライなしの場合は 500K (0.5秒) に設定し、リトライ回数に応じて 100K (0.1秒) ずつ増やす
        max_interleave_delta = round(500 + (self._retry_count * 100))
        options.append(f'-fflags nobuffer -flags low_delay -max_delay 250000 -max_interleave_delta {max_interleave_delta}K -threads auto')

        # 音声
        ## 音声が 5.1ch かどうかに関わらず、ステレオにダウンミックスする
        options.append('-acodec aac -aac_coder twoloop -ac 2 -ab 192K -ar 48000 -af volume=2.0')

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
        channel_type: Literal['GR', 'BS', 'CS', 'CATV', 'SKY', 'BS4K'],
        is_fullhd_channel: bool,
    ) -> list[str]:
        """
        QSVEncC・NVEncC・VCEEncC・rkmppenc (便宜上 HWEncC と総称) に渡すオプションを組み立てる

        Args:
            quality (QUALITY_TYPES): 映像の品質
            encoder_type (Literal['QSVEncC', 'NVEncC', 'VCEEncC', 'rkmppenc']): エンコーダー (QSVEncC or NVEncC or VCEEncC or rkmppenc)
            channel_type (Literal['GR', 'BS', 'CS', 'CATV', 'SKY', 'BS4K']): チャンネルの種類
            is_fullhd_channel (bool): フル HD 放送が実施されているチャンネルかどうか

        Returns:
            list[str]: HWEncC に渡すオプションが連なる配列
        """

        # オプションの入る配列
        options: list[str] = []

        # 入力ストリームの解析時間
        input_probesize = round(1000 + (self._retry_count * 500))  # リトライ回数に応じて少し増やす
        input_analyze = round(0.7 + (self._retry_count * 0.2), 1)  # リトライ回数に応じて少し増やす
        if channel_type == 'SKY':
            # スカパー！プレミアムサービスのチャンネルは入力ストリームの解析時間を長めにする (その方がうまくいく)
            ## ほかと違い H.264 コーデックが採用されていることが影響しているのかも
            input_probesize += 500
            input_analyze += 0.2

        # 入力
        ## --input-probesize, --input-analyze をつけることで、ストリームの分析時間を短縮できる
        ## 両方つけるのが重要で、--input-analyze だけだとエンコーダーがフリーズすることがある
        options.append(f'--input-format mpegts --input-probesize {input_probesize}K --input-analyze {input_analyze}')
        ## BS4K 以外では 29.97fps (59.94i) を指定する
        if channel_type != 'BS4K':
            options.append('--fps 30000/1001')
        ## 入力を指定する
        options.append('--input -')
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
        ## max_interleave_delta: mux 時に影響するオプションで、増やしすぎると CM で詰まりがちになる
        ## リトライなしの場合は 500K (0.5秒) に設定し、リトライ回数に応じて 100K (0.1秒) ずつ増やす
        max_interleave_delta = round(500 + (self._retry_count * 100))
        options.append('-m avioflags:direct -m fflags:nobuffer+flush_packets -m flush_packets:1 -m max_delay:250000')
        options.append(f'-m max_interleave_delta:{max_interleave_delta}K --output-thread 0 --lowlatency')
        ## その他の設定
        options.append('--log-level debug')
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

        ## 最大 GOP 長 (秒)
        ## 30fps なら ×30 、 60fps なら ×60 された値が --gop-len で使われる
        gop_length_second = self.GOP_LENGTH_SECONDS_H264
        if QUALITY[quality].is_hevc is True:
            ## H.265/HEVC では高圧縮化のため、最大 GOP 長を長くする
            gop_length_second = self.GOP_LENGTH_SECONDS_H265

        ## BS4K は 60p (プログレッシブ) で放送されているので、インターレース解除を行わず 60fps でエンコードする
        if channel_type == "BS4K":
            options.append(f'--avsync vfr --gop-len {int(gop_length_second * 60)}')
        else:
            ## インターレース映像として読み込む
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
                options.append(f'--avsync vfr --gop-len {int(gop_length_second * 60)}')
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
                options.append(f'--avsync vfr --gop-len {int(gop_length_second * 30)}')

        ## フル HD 放送が行われているチャンネルかつ、指定された品質の解像度が 1440×1080 (1080p) の場合のみ、
        ## 特別に縦解像度を 1920 に変更してフル HD (1920×1080) でエンコードする
        video_width = QUALITY[quality].width
        video_height = QUALITY[quality].height
        if video_width == 1440 and video_height == 1080 and is_fullhd_channel is True:
            video_width = 1920
        options.append(f'--output-res {video_width}x{video_height}')

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


    async def acquireMirakurunTuner(self, channel_type: Literal['GR', 'BS', 'CS', 'CATV', 'SKY', 'BS4K']) -> bool:
        """
        Mirakurun / mirakc で空きチューナーを確保できるまで待機する
        mirakc は空きチューナーがない場合に 404 を返すので (バグ？) 、それを避けるために予め空きチューナーがあるかどうかを確認する
        0.5 秒間待機しても空きチューナーがなければ False を返す (共聴できる場合もあるので、受信できないとは限らない)

        Args:
            channel_type (Literal['GR', 'BS', 'CS', 'CATV', 'SKY', 'BS4K']): チャンネルタイプ

        Returns:
            bool: チューナーを確保できたかどうか
        """

        CONFIG = Config()
        BACKEND_TYPE: Literal['EDCB', 'Mirakurun'] = 'Mirakurun' if CONFIG.general.always_receive_tv_from_mirakurun is True else CONFIG.general.backend
        assert BACKEND_TYPE == 'Mirakurun', 'This method is only for Mirakurun backend.'

        # Mirakurun / mirakc は通常チャンネルタイプが GR, BS, CS, SKY しかないので、
        # フォールバックとして BS4K を BS に、CATV を CS に変換する
        fallback_channel_type = channel_type
        if channel_type == 'BS4K':
            fallback_channel_type = 'BS'
        elif channel_type == 'CATV':
            fallback_channel_type = 'CS'

        mirakurun_or_mirakc = 'Mirakurun'
        async with HTTPX_CLIENT() as client:

            # 0.1 秒間隔で最大 0.5 秒間チューナーの空きを確認する
            ## 空きチューナーがなくても利用状況によっては共聴できるので、あまり待ちすぎると無駄な時間がかかる
            ## Mirakurun / mirakc はチャンネル切り替え時に 1 秒弱使い終わった前チャンネルのチューナープロセスが残るので、シングルチューナー環境では
            ## それを解放し終わってからチューナーを起動できるようにする (実際はだいたい 0.25 秒程度で空きチューナーを確保できる)
            ## 複数チューナーがある場合は他の空きチューナーを使って起動できるため、待ち時間はほとんどかからない
            start_time = time.time()
            for _ in range(int(0.5 / 0.1)):

                # Mirakurun / mirakc からチューナーの状態を取得
                try:
                    response = await client.get(GetMirakurunAPIEndpointURL('/api/tuners'), timeout=5)
                    # レスポンスヘッダーの server が mirakc であれば mirakc と判定できる
                    if ('server' in response.headers) and ('mirakc' in response.headers['server']):
                        mirakurun_or_mirakc = 'mirakc'
                    tuners = response.json()
                except httpx.NetworkError:
                    logging.error('Failed to get tuner statuses from Mirakurun / mirakc. (Network Error)')
                    return False
                except httpx.TimeoutException:
                    logging.error('Failed to get tuner statuses from Mirakurun / mirakc. (Connection Timeout)')
                    return False

                # 指定されたチャンネルタイプが受信可能なチューナーが1つでも利用可能であれば True を返す
                for tuner in tuners:
                    if tuner['isAvailable'] is True and tuner['isFree'] is True and channel_type in tuner['types']:
                        logging.info(f'Acquired a tuner from {mirakurun_or_mirakc}.')
                        logging.info(f'Tuner: {tuner["name"]} / Type: {channel_type}) / Acquired in {round(time.time() - start_time, 2)} seconds')
                        return True
                    if tuner['isAvailable'] is True and tuner['isFree'] is True and fallback_channel_type in tuner['types']:
                        logging.info(f'Acquired a tuner from {mirakurun_or_mirakc}. ({channel_type} -> {fallback_channel_type})')
                        logging.info(f'Tuner: {tuner["name"]} / Type: {fallback_channel_type}) / Acquired in {round(time.time() - start_time, 2)} seconds')
                        return True

                await asyncio.sleep(0.1)

        # 空きチューナーは確保できなかったが、同じチャンネルが受信中であれば共聴することは可能なので warning に留める
        logging.warning(f'Failed to acquire a tuner from {mirakurun_or_mirakc}.')
        logging.warning('If the same channel is being received, it can be shared with the same tuner.')
        return False


    async def run(self) -> None:
        """
        エンコードタスクを実行する
        """

        CONFIG = Config()

        # バックエンドの種類を取得
        ## always_receive_tv_from_mirakurun が True なら、バックエンドに関わらず常に Mirakurun / mirakc から受信する
        BACKEND_TYPE: Literal['EDCB', 'Mirakurun'] = 'Mirakurun' if CONFIG.general.always_receive_tv_from_mirakurun is True else CONFIG.general.backend

        # エンコーダーの種類を取得
        ENCODER_TYPE = CONFIG.general.encoder

        # まだ Standby になっていなければ、ステータスを Standby に設定
        # 基本はエンコードタスクの呼び出し元である self.live_stream.connect() の方で Standby に設定されるが、再起動の場合はそこを経由しないため必要
        if not (self.live_stream.getStatus().status == 'Standby' and self.live_stream.getStatus().detail == 'エンコードタスクを起動しています…'):
            self.live_stream.setStatus('Standby', 'エンコードタスクを起動しています…')

        # チャンネル情報からサービス ID とネットワーク ID を取得する
        channel = cast(Channel, await Channel.filter(display_channel_id=self.live_stream.display_channel_id).first())

        # 現在の番組情報を取得する
        program_present = (await channel.getCurrentAndNextProgram())[0]
        if program_present is not None:
            logging.info(f'[Live: {self.live_stream.live_stream_id}] Title: {program_present.title}')
        else:
            logging.info(f'[Live: {self.live_stream.live_stream_id}] Title: 番組情報がありません')

        # PSI/SI データアーカイバーを初期化
        ## psisiarc は API リクエストがある度に都度起動される
        self.live_stream.psi_data_archiver = LivePSIDataArchiver(channel.service_id)

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
            ## 視聴対象のチャンネルのサービス ID を指定する
            '-n', f'{channel.service_id}' if CONFIG.tv.debug_mode_ts_path is None else '-1',
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
        ]

        if CONFIG.tv.debug_mode_ts_path is None:
            # 通常は標準入力を指定
            tsreadex_options.append('-')
        else:
            # デバッグモード: 指定された TS ファイルを読み込む
            ## 読み込み速度を 2350KB/s (18.8Mbps) に制限
            ## 1倍速に近い値だが、TS のビットレートはチャンネルや番組、シーンによって変動するため完全な1倍速にはならない
            tsreadex_options += [
                '-l', '2350',
                CONFIG.tv.debug_mode_ts_path
            ]

        # tsreadex の読み込み用パイプと書き込み用パイプを作成
        tsreadex_read_pipe, tsreadex_write_pipe = os.pipe()

        # tsreadex のプロセスを非同期で作成・実行
        tsreadex = await asyncio.subprocess.create_subprocess_exec(
            *[LIBRARY_PATH['tsreadex'], *tsreadex_options],
            stdin = asyncio.subprocess.PIPE,  # 受信した放送波を書き込む
            stdout = tsreadex_write_pipe,  # エンコーダーに繋ぐ
            stderr = asyncio.subprocess.DEVNULL,  # 利用しない
        )

        # tsreadex の書き込み用パイプを閉じる
        os.close(tsreadex_write_pipe)

        # ***** エンコーダープロセスの作成と実行 *****

        # エンコーダーの起動には時間がかかるので、先にエンコーダーを起動しておいた後、あとからチューナーを起動する
        # チューナーの起動後にエンコーダー (正確には tsreadex) に受信した放送波が書き込まれる
        # チューナーの起動にも時間がかかるが、エンコーダーの起動は非同期なのに対し、チューナーの起動は EDCB の場合は同期的

        # フル HD 放送が行われているチャンネルかを取得
        is_fullhd_channel = self.isFullHDChannel(channel.network_id, channel.service_id)

        ## ラジオチャンネルでは HW エンコードの意味がないため、FFmpeg に固定する
        if channel.is_radiochannel is True:
            ENCODER_TYPE = 'FFmpeg'

        # FFmpeg
        if ENCODER_TYPE == 'FFmpeg':

            # オプションを取得
            # ラジオチャンネルかどうかでエンコードオプションを切り替え
            if channel.is_radiochannel is True:
                encoder_options = self.buildFFmpegOptionsForRadio()
            else:
                encoder_options = self.buildFFmpegOptions(self.live_stream.quality, channel.type, is_fullhd_channel)
            logging.info(f'[Live: {self.live_stream.live_stream_id}] FFmpeg Commands:\nffmpeg {" ".join(encoder_options)}')

            # エンコーダープロセスを非同期で作成・実行
            encoder = await asyncio.subprocess.create_subprocess_exec(
                *[LIBRARY_PATH['FFmpeg'], *encoder_options],
                stdin = tsreadex_read_pipe,  # tsreadex からの入力
                stdout = asyncio.subprocess.PIPE,  # ストリーム出力
                stderr = asyncio.subprocess.PIPE,  # ログ出力
            )

        # HWEncC
        else:

            # オプションを取得
            encoder_options = self.buildHWEncCOptions(self.live_stream.quality, ENCODER_TYPE, channel.type, is_fullhd_channel)
            logging.info(f'[Live: {self.live_stream.live_stream_id}] {ENCODER_TYPE} Commands:\n{ENCODER_TYPE} {" ".join(encoder_options)}')

            # エンコーダープロセスを非同期で作成・実行
            encoder = await asyncio.subprocess.create_subprocess_exec(
                *[LIBRARY_PATH[ENCODER_TYPE], *encoder_options],
                stdin = tsreadex_read_pipe,  # tsreadex からの入力
                stdout = asyncio.subprocess.PIPE,  # ストリーム出力
                stderr = asyncio.subprocess.PIPE,  # ログ出力
            )

        # tsreadex の読み込み用パイプを閉じる
        os.close(tsreadex_read_pipe)

        # ***** チューナーの起動と接続 *****

        # エンコードタスクが稼働中かどうか
        is_running: bool = True

        # 放送波の MPEG2-TS を受信する StreamReader
        stream_reader: asyncio.StreamReader | PipeStreamReader | aiohttp.StreamReader | None = None

        # Mirakurun の aiohttp セッション (EDCB バックエンド利用時は常に None)
        response: aiohttp.ClientResponse | None = None
        session: aiohttp.ClientSession | None = None

        # Mirakurun バックエンド
        if BACKEND_TYPE == 'Mirakurun':

            # チューナーを確保できるまで待機する
            ## 確保できなかった場合でも共聴で受信できる可能性があるので、戻り値は無視する
            self.live_stream.setStatus('Standby', 'チューナーを確保しています…')
            await self.acquireMirakurunTuner(channel.type)

            # Mirakurun 形式のサービス ID
            # NID と SID を 5 桁でゼロ埋めした上で int に変換する
            mirakurun_service_id = int(str(channel.network_id).zfill(5) + str(channel.service_id).zfill(5))

            # Mirakurun の Service Stream API へ HTTP リクエストを開始
            self.live_stream.setStatus('Standby', 'チューナーを起動しています…')
            session = aiohttp.ClientSession()
            try:
                response = await session.get(
                    url = GetMirakurunAPIEndpointURL(f'/api/services/{mirakurun_service_id}/stream'),
                    headers = {**API_REQUEST_HEADERS, 'X-Mirakurun-Priority': '0'},
                    timeout = aiohttp.ClientTimeout(connect=15, sock_connect=15, sock_read=15)
                )
            except (TimeoutError, aiohttp.ClientConnectorError):

                # 番組名に「放送休止」などが入っていれば停波によるものとみなし、そうでないならチューナーへの接続に失敗したものとする
                if program_present is None or program_present.isOffTheAirProgram():
                    self.live_stream.setStatus('Offline', 'この時間は放送を休止しています。(E-01M)')
                else:
                    self.live_stream.setStatus('Offline', 'チューナーへの接続に失敗しました。チューナー側に何らかの問題があるかもしれません。(E-01M)')

                # すべての視聴中クライアントのライブストリームへの接続を切断する
                self.live_stream.disconnectAll()

                # PSI/SI データアーカイバーを終了・破棄する
                if self.live_stream.psi_data_archiver is not None:
                    self.live_stream.psi_data_archiver.destroy()
                    self.live_stream.psi_data_archiver = None

                # エンコードタスクを停止する
                await session.close()
                return

            # 放送波の MPEG2-TS の受信元の StreamReader として設定
            stream_reader = response.content

        # EDCB バックエンド
        elif BACKEND_TYPE == 'EDCB':

            # チューナーインスタンスを初期化
            ## Idling への切り替え、ONAir への復帰時に LiveStream 側でチューナーのアンロック/ロックが行われる
            self.live_stream.tuner = EDCBTuner(channel.network_id, channel.service_id, cast(int, channel.transport_stream_id))

            # チューナーを起動する
            # アンロック状態のチューナーインスタンスがあれば、自動的にそのチューナーが再利用される
            logging.debug_simple(f'[Live: {self.live_stream.live_stream_id}] EDCB NetworkTV ID: {self.live_stream.tuner.getEDCBNetworkTVID()}')
            self.live_stream.setStatus('Standby', 'チューナーを起動しています…')
            is_tuner_opened = await self.live_stream.tuner.open()

            # チューナーの起動に失敗した
            # ほとんどがチューナー不足によるものなので、ステータス詳細でもそのように表示する
            # 成功時は tuner.close() するか予約などに割り込まれるまで起動しつづけるので注意
            if is_tuner_opened is False:
                self.live_stream.setStatus('Offline', 'チューナーの起動に失敗しました。空きチューナーが不足していると考えられます。(E-02E)')

                # チューナーを閉じる
                await self.live_stream.tuner.close()

                # すべての視聴中クライアントのライブストリームへの接続を切断する
                self.live_stream.disconnectAll()

                # PSI/SI データアーカイバーを終了・破棄する
                if self.live_stream.psi_data_archiver is not None:
                    self.live_stream.psi_data_archiver.destroy()
                    self.live_stream.psi_data_archiver = None

                # エンコードタスクを停止する
                return

            # チューナーをロックする
            # ロックしないと途中でチューナーの制御を横取りされてしまう
            self.live_stream.tuner.lock()

            # チューナーに接続する
            # 放送波が送信される TCP ソケットまたは名前付きパイプを取得する
            self.live_stream.setStatus('Standby', 'チューナーに接続しています…')
            reader = await self.live_stream.tuner.connect()

            # チューナーへの接続に失敗した
            if reader is None:
                self.live_stream.setStatus('Offline', 'チューナーへの接続に失敗しました。チューナー側に何らかの問題があるかもしれません。(E-03E)')

                # チューナーを閉じる
                await self.live_stream.tuner.close()

                # すべての視聴中クライアントのライブストリームへの接続を切断する
                self.live_stream.disconnectAll()

                # PSI/SI データアーカイバーを終了・破棄する
                if self.live_stream.psi_data_archiver is not None:
                    self.live_stream.psi_data_archiver.destroy()
                    self.live_stream.psi_data_archiver = None

                # エンコードタスクを停止する
                return

            # 放送波の MPEG2-TS の受信元の StreamReader として設定
            stream_reader = reader

        # ***** チューナーからの出力の読み込み → tsreadex・エンコーダーへの書き込み *****

        # 実行中のタスクへの参照を保持しておく
        ## run() の実行が完了するまで、ガベージコレクタによりタスクが勝手に破棄されることを防ぐ
        ## ref: https://docs.astral.sh/ruff/rules/asyncio-dangling-task/
        background_tasks: set[asyncio.Task[None]] = set()

        # チューナーからの放送波 TS の最終読み取り時刻 (単調増加時間)
        ## 単に時刻を比較する用途でしか使わないので、time.monotonic() から取得した単調増加時間が入る
        ## Unix Time とかではないので注意
        tuner_ts_read_at: float = time.monotonic()
        tuner_ts_read_at_lock = asyncio.Lock()

        async def Reader() -> None:
            nonlocal tuner_ts_read_at

            # 受信した放送波が入るイテレータを作成
            # R/W バッファ: 188B (TS Packet Size) * 256 = 48128B
            async def GetIterator(
                    stream_reader: asyncio.StreamReader | PipeStreamReader | aiohttp.StreamReader,
                    chunk_size: int = ts.PACKET_SIZE * 256,
                ) -> AsyncIterator[bytes]:
                while True:
                    try:
                        yield await stream_reader.readexactly(chunk_size)
                    except asyncio.IncompleteReadError as ex:
                        # もし残りのバイトがあれば、 break 前にそれらを yield する
                        if ex.partial:
                            yield ex.partial
                        break

            assert stream_reader is not None
            stream_iterator = GetIterator(stream_reader)

            # EDCB / Mirakurun から受信した放送波を随時 tsreadex の入力に書き込む
            try:
                async for chunk in stream_iterator:

                    # チューナーからの放送波 TS の最終読み取り時刻を更新
                    async with tuner_ts_read_at_lock:
                        tuner_ts_read_at = time.monotonic()

                    # tsreadex の標準入力が閉じられていたら、タスクを終了
                    if cast(asyncio.StreamWriter, tsreadex.stdin).is_closing():
                        break

                    try:
                        # ストリームデータを tsreadex の標準入力に書き込む
                        cast(asyncio.StreamWriter, tsreadex.stdin).write(chunk)
                        await cast(asyncio.StreamWriter, tsreadex.stdin).drain()

                        # 生の放送波の TS パケットを PSI/SI データアーカイバーに送信する
                        ## 放送波の tsreadex への書き込みを最優先で行うため、非同期タスクとして実行する
                        ## ここで tsreadex への書き込みがブロックされると放送波の受信ループが止まり、ライブストリームの異常終了に繋がりかねない
                        if self.live_stream.psi_data_archiver is not None:
                            background_tasks.add(asyncio.create_task(self.live_stream.psi_data_archiver.pushTSPacketData(chunk)))

                    # 並列タスク処理中に何らかの例外が発生した
                    # BrokenPipeError・asyncio.TimeoutError などが想定されるが、何が発生するかわからないためすべての例外をキャッチする
                    except Exception:
                        break

                    # エンコードタスクが終了しているか既にエンコーダープロセスが終了していたら、タスクを終了
                    if is_running is False or tsreadex.returncode is not None or encoder.returncode is not None:
                        break

            except OSError:
                pass

            # タスクを終える前に、チューナーとの接続を明示的に閉じる
            try:
                cast(asyncio.StreamWriter, tsreadex.stdin).close()
            except OSError:
                pass

            ## 並行している別の非同期タスクとのタイミングの関係で 0.1 秒待ってからクリーンアップする
            await asyncio.sleep(0.1)

            # EDCB バックエンド: チューナーとのストリーミング接続を閉じる
            ## チャンネル切り替え時に再利用するため、ここではチューナー自体は閉じない
            if BACKEND_TYPE == 'EDCB' and self.live_stream.tuner is not None:
                await self.live_stream.tuner.disconnect()

            # Mirakurun バックエンド: Service Stream API とのストリーミング接続を閉じる
            if BACKEND_TYPE == 'Mirakurun' and response is not None and session is not None:
                await session.close()
                response.close()

        # タスクを非同期で実行
        background_tasks.add(asyncio.create_task(Reader()))

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

        async def Writer() -> None:

            nonlocal chunk_buffer, chunk_written_at, writer_lock

            while True:
                try:

                    # エンコーダーからの出力を読み取る
                    ## TS パケットのサイズが 188 bytes なので、1回の readexactly() で 188 bytes ずつ読み取る
                    ## read() ではなく厳密な readexactly() を使わないとぴったり 188 bytes にならない場合がある
                    chunk = await cast(asyncio.StreamReader, encoder.stdout).readexactly(ts.PACKET_SIZE)

                    # 同時に chunk_buffer / chunk_written_at にアクセスするタスクが1つだけであることを保証する (排他ロック)
                    async with writer_lock:

                        # 188 bytes ごとに区切られた、エンコーダーの出力のチャンクをバッファに貯める
                        chunk_buffer += chunk

                        # チャンクバッファが 65536 bytes (64KB) 以上になった時のみ
                        if len(chunk_buffer) >= 65536:

                            # エンコーダーからの出力をライブストリームの Queue に書き込む
                            await self.live_stream.writeStreamData(bytes(chunk_buffer))
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
        async def SubWriter() -> None:

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
                        await self.live_stream.writeStreamData(bytes(chunk_buffer))
                        # print(f'SubWriter: Chunk size: {len(chunk_buffer):05} / Time: {time.time()}')

                        # チャンクバッファを空にする（重要）
                        chunk_buffer = bytearray()

                        # チャンクの最終書き込み時刻を更新
                        chunk_written_at = time.monotonic()

                # エンコードタスクが終了しているか既にエンコーダープロセスが終了していたら、タスクを終了
                if is_running is False or tsreadex.returncode is not None or encoder.returncode is not None:
                    break

        # タスクを非同期で実行
        background_tasks.add(asyncio.create_task(Writer()))
        background_tasks.add(asyncio.create_task(SubWriter()))

        # ***** エンコーダーの状態監視 *****

        # エンコーダーの出力ログのリスト
        lines: list[str] = []

        async def EncoderObServer() -> None:

            # 1つ上のスコープ (Enclosing Scope) の変数を書き替えるために必要
            # ref: https://excel-ubara.com/python/python014.html#sec04
            nonlocal lines, program_present

            # 既にエンコーダーのログファイルが存在していた場合は上書きしないようにリネーム
            ## ref: https://note.nkmk.me/python-pathlib-name-suffix-parent/
            count = 1
            encoder_log_path = LOGS_DIR / f'KonomiTV-Encoder-{self.live_stream.live_stream_id}.log'
            while await anyio.Path(str(encoder_log_path)).exists():
                encoder_log_path = LOGS_DIR / f'KonomiTV-Encoder-{self.live_stream.live_stream_id}-{count}.log'
                count += 1

            # エンコーダーのログファイルを開く (エンコーダーログ有効時のみ)
            encoder_log: AsyncTextIOWrapper | None = None
            if CONFIG.general.debug_encoder is True:
                encoder_log = await aiofiles.open(encoder_log_path, mode='w', encoding='utf-8')

            # エンコーダーの出力結果を取得
            while True:

                # 行ごとに随時読み込む
                ## 1バイトずつ読み込み、\r か \n が来たら行としてデコード
                ## FFmpeg はコンソールの行を上書きするために frame= の進捗ログで \r しか出力しないため、readline() を使うと
                ## 進捗ログを取得できずに永遠に Standby から ONAir に移行しない不具合が発生する
                buffer = bytearray()
                while True:
                    byte = await cast(asyncio.StreamReader, encoder.stderr).read(1)
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
                    ('[h264_metadata' not in line) and
                    ('[hevc_metadata' not in line) and
                    ('packet in the muxing queue' not in line) and ('ing output' not in line) and
                    ('ng output' != line) and ('g output' != line) and (' output' != line) and ('output' != line) and
                    ('utput' != line) and ('tput' != line) and ('put' != line) and ('ut' != line) and ('t' != line) and
                    ('' != line)):

                    # ログリストに行単位で追加
                    lines.append(line)

                    # ストリーム関連のログを表示
                    ## エンコーダーのログ出力が有効なら、ストリーム関連に限らずすべてのログを出力する
                    if 'Stream #0:' in line or CONFIG.general.debug_encoder is True:
                        logging.debug_simple(f'[Live: {self.live_stream.live_stream_id}] [{ENCODER_TYPE}] ' + line)

                    # エンコーダーのログ出力が有効なら、エンコーダーのログファイルに書き込む
                    if CONFIG.general.debug_encoder is True and encoder_log is not None:
                        await encoder_log.write(line.strip('\r\n') + '\n')
                        await encoder_log.flush()

                # ライブストリームのステータスを取得
                live_stream_status = self.live_stream.getStatus()

                # エンコードの進捗を判定し、ステータスを更新する
                # 誤作動防止のため、ステータスが Standby の間のみ更新できるようにする
                if live_stream_status.status == 'Standby':
                    # FFmpeg
                    if ENCODER_TYPE == 'FFmpeg':
                        if 'arib parser was created' in line or 'Invalid frame dimensions 0x0.' in line:
                            self.live_stream.setStatus('Standby', 'エンコードを開始しています…')
                        elif 'frame=    1 fps=0.0 q=0.0' in line or 'size=       0kB time=00:00' in line:
                            self.live_stream.setStatus('Standby', 'バッファリングしています…')
                        elif 'frame=' in line or 'bitrate=' in line:
                            self.live_stream.setStatus('ONAir', 'ライブストリームは ONAir です。')
                            # エラーから回復した場合は、エンコードタスクの再起動回数のカウントをリセットする
                            if self._retry_count > 0:
                                self._retry_count = 0
                    ## HWEncC
                    else:
                        if 'opened file "pipe:0"' in line:
                            self.live_stream.setStatus('Standby', 'エンコードを開始しています…')
                        elif 'starting output thread...' in line:
                            self.live_stream.setStatus('Standby', 'バッファリングしています…')
                        elif 'Encode Thread:' in line:
                            self.live_stream.setStatus('Standby', 'バッファリングしています…')
                        elif ' frames: ' in line:
                            self.live_stream.setStatus('ONAir', 'ライブストリームは ONAir です。')
                            # エラーから回復した場合は、エンコードタスクの再起動回数のカウントをリセットする
                            if self._retry_count > 0:
                                self._retry_count = 0

                # 特定のエラーログが出力されている場合は回復が見込めないため、エンコーダーを終了する
                ## エンコーダーを再起動することで回復が期待できる場合は、ステータスを Restart に設定しエンコードタスクを再起動する
                ## FFmpeg
                if ENCODER_TYPE == 'FFmpeg':
                    if 'Stream map \'0:v:0\' matches no streams.' in line:
                        # 何らかの要因で tsreadex から放送波が受信できなかったことによるエラーのため、エンコーダーの再起動は行わない
                        ## 番組名に「放送休止」などが入っていれば停波によるものとみなし、そうでないなら放送波の受信に失敗したものとする
                        if program_present is None or program_present.isOffTheAirProgram():
                            self.live_stream.setStatus('Offline', 'この時間は放送を休止しています。(E-04F)')
                        else:
                            self.live_stream.setStatus('Offline', 'チューナーからの放送波の受信に失敗したため、エンコードを開始できません。(E-04F)')
                    elif 'Conversion failed!' in line:
                        # 捕捉されないエラー
                        ## エンコーダーの再起動で復帰できる可能性があるので、エンコードタスクを再起動する
                        result = self.live_stream.setStatus('Restart', 'エンコード中に予期しないエラーが発生しました。エンコードタスクを再起動しています… (ER-01F)')
                        # 直近 50 件のログを表示
                        if result is True:
                            for log in lines[-51:-1]:
                                logging.warning(log)
                ## HWEncC
                else:
                    if 'error finding stream information.' in line:
                        # 何らかの要因で tsreadex から放送波が受信できなかったことによるエラーのため、エンコーダーの再起動は行わない
                        ## 番組名に「放送休止」などが入っていれば停波によるものとみなし、そうでないなら放送波の受信に失敗したものとする
                        if program_present is None or program_present.isOffTheAirProgram():
                            self.live_stream.setStatus('Offline', 'この時間は放送を休止しています。(E-05H)')
                        else:
                            self.live_stream.setStatus('Offline', 'チューナーからの放送波の受信に失敗したため、エンコードを開始できません。(E-05H)')
                    elif ENCODER_TYPE == 'NVEncC' and 'due to the NVIDIA\'s driver limitation.' in line:
                        # NVEncC で、同時にエンコードできるセッション数 (Geforceだと5つ) を全て使い果たしている時のエラー
                        self.live_stream.setStatus('Offline', 'NVENC のエンコードセッションが不足しているため、エンコードを開始できません。(E-06HN)')
                    elif ENCODER_TYPE == 'QSVEncC' and ('unable to decode by qsv.' in line or 'No device found for QSV encoding!' in line):
                        # QSVEncC 非対応の環境
                        self.live_stream.setStatus('Offline', 'お使いの PC 環境は QSVEncC エンコーダーに対応していません。(E-07HQ)')
                    elif ENCODER_TYPE == 'QSVEncC' and 'iHD_drv_video.so init failed' in line:
                        # QSVEncC 非対応の環境 (Linux かつ第5世代以前の Intel CPU)
                        self.live_stream.setStatus('Offline', 'お使いの PC 環境は Linux 版 QSVEncC エンコーダーに対応していません。第5世代以前の古い CPU をお使いの可能性があります。(E-08HQ)')
                    elif ENCODER_TYPE == 'NVEncC' and 'CUDA not available.' in line:
                        # NVEncC 非対応の環境
                        self.live_stream.setStatus('Offline', 'お使いの PC 環境は NVEncC エンコーダーに対応していません。(E-09HN)')
                    elif ENCODER_TYPE == 'VCEEncC' and \
                        ('Failed to initalize VCE factory:' in line or 'Assertion failed:Init() failed to vkCreateInstance' in line):
                        # VCEEncC 非対応の環境
                        self.live_stream.setStatus('Offline', 'お使いの PC 環境は VCEEncC エンコーダーに対応していません。(E-10HV)')
                    elif 'Consider increasing the value for the --input-analyze and/or --input-probesize!' in line:
                        # --input-probesize or --input-analyze の期間内に入力ストリームの解析が終わらなかった
                        ## エンコーダーの再起動で復帰できる可能性があるので、エンコードタスクを再起動する
                        self.live_stream.setStatus('Restart', '入力ストリームの解析に失敗しました。エンコードタスクを再起動しています… (ER-02H)')
                    elif 'finished with error!' in line:
                        # 捕捉されないエラー
                        ## Controller 非同期タスク側で完全にエンコーダープロセスが落ちたタイミングで HEVC 非対応かなどを判断しているため、
                        ## ここで 0.5 秒待機してから実行する
                        await asyncio.sleep(0.5)
                        ## エンコーダーの再起動で復帰できる可能性があるので、エンコードタスクを再起動する
                        result = self.live_stream.setStatus('Restart', 'エンコード中に予期しないエラーが発生しました。エンコードタスクを再起動しています… (ER-03H)')
                        # 直近 150 件のログを表示
                        if result is True:
                            for log in lines[-151:-1]:
                                logging.warning(log)

                # エンコードタスクが終了しているか既にエンコーダープロセスが終了していたら、タスクを終了
                if is_running is False or tsreadex.returncode is not None or encoder.returncode is not None:
                    break

            # タスクを終える前にエンコーダーのログファイルを閉じる
            if CONFIG.general.debug_encoder is True and encoder_log is not None:
                await encoder_log.close()

        # タスクを非同期で実行
        background_tasks.add(asyncio.create_task(EncoderObServer()))

        # ***** エンコードタスク全体の制御 *****

        async def Controller() -> None:

            # 1つ上のスコープ (Enclosing Scope) の変数を書き替えるために必要
            # ref: https://excel-ubara.com/python/python014.html#sec04
            nonlocal lines, program_present

            while True:

                # ライブストリームのステータスを取得
                live_stream_status = self.live_stream.getStatus()

                # 現在放送中の番組が終了した際に program_present に保存している現在の番組情報を新しいものに更新する
                # TODO: 番組情報のない時間帯から番組情報のある時間帯に移行する場合の処理が考慮されていない
                if program_present is not None and time.time() > program_present.end_time.timestamp():

                    # 新しい現在放送中の番組情報を取得する
                    program_following = (await channel.getCurrentAndNextProgram())[0]
                    if program_following is not None:

                        # 現在の番組のタイトルをログに出力
                        ## TODO: 番組の解像度が変わった際にエンコーダーがクラッシュorフリーズする可能性があるが、
                        ## その場合はここでエンコードタスクを再起動させる必要があるかも
                        logging.info(f'[Live: {self.live_stream.live_stream_id}] Title: {program_following.title}')

                    program_present = program_following
                    del program_following

                # 現在 ONAir でかつクライアント数が 0 なら Idling（アイドリング状態）に移行
                if live_stream_status.status == 'ONAir' and live_stream_status.client_count == 0:
                    self.live_stream.setStatus('Idling', 'ライブストリームは Idling です。')

                # 現在 Idling でかつ最終更新から max_alive_time 秒以上経っていたらエンコーダーを終了し、Offline 状態に移行
                if ((live_stream_status.status == 'Idling') and
                    (time.time() - live_stream_status.updated_at > CONFIG.tv.max_alive_time)):
                    self.live_stream.setStatus('Offline', 'ライブストリームは Offline です。')

                # ***** 異常処理 (エンコードタスク再起動による回復が不可能) *****

                # 前回チューナーからの放送波 TS を読み取ってから TUNER_TS_READ_TIMEOUT 秒以上経過していたら、
                # 停波中もしくはチューナーからの放送波 TS の送信が停止したと判断して Offline に移行
                async with tuner_ts_read_at_lock:
                    if (time.monotonic() - tuner_ts_read_at) > self.TUNER_TS_READ_TIMEOUT:

                        # 番組名に「放送休止」などが入っていれば停波の可能性が高い
                        if program_present is None or program_present.isOffTheAirProgram():
                            self.live_stream.setStatus('Offline', 'この時間は放送を休止しています。(E-11)')

                        # それ以外は受信エラーとする
                        else:
                            self.live_stream.setStatus('Offline', 'チューナーからの放送波の受信がタイムアウトしました。チューナー側に何らかの問題があるかもしれません。(E-11)')

                # Mirakurun の Service Stream API からエラーが返された場合
                if BACKEND_TYPE == 'Mirakurun' and response is not None and response.status != 200:
                    # レスポンスヘッダーの server が mirakc であれば mirakc と判定できる
                    if ('server' in response.headers) and ('mirakc' in response.headers['server']):
                        mirakurun_or_mirakc = 'mirakc'
                    else:
                        mirakurun_or_mirakc = 'Mirakurun'
                    # Offline にしてエンコードタスクを停止する
                    ## mirakc はなぜかチューナー不足時に 503 ではなく 404 を返すことがある (バグ?)
                    if response.status == 503 or (response.status == 404 and mirakurun_or_mirakc == 'mirakc'):
                        self.live_stream.setStatus('Offline', 'チューナーの起動に失敗しました。空きチューナーが不足している可能性があります。(E-12M)')
                    elif response.status == 404:
                        self.live_stream.setStatus('Offline', f'現在このチャンネルは受信できません。{mirakurun_or_mirakc} 側に問題があるかもしれません。(HTTP Error {response.status}) (E-12M)')
                    else:
                        self.live_stream.setStatus('Offline', f'チューナーで不明なエラーが発生しました。{mirakurun_or_mirakc} 側に問題があるかもしれません。(HTTP Error {response.status}) (E-12M)')
                    break

                # ***** 異常処理 (エンコードタスク再起動による回復が可能) *****

                # 現在 Standby でかつストリームデータの最終書き込み時刻から
                # ENCODER_TS_READ_TIMEOUT_STANDBY 秒以上が経過しているなら、エンコーダーがフリーズしたものとみなす
                # 現在 ONAir でかつストリームデータの最終書き込み時刻から
                # ENCODER_TS_READ_TIMEOUT_ONAIR 秒以上が経過している場合も、エンコーダーがフリーズしたものとみなす
                ## 何らかの理由でエンコードが途中で停止した場合、live_stream.write() が実行されなくなることを利用している
                encoder_ts_read_timeout_onair = \
                    self.ENCODER_TS_READ_TIMEOUT_ONAIR_VCEENCC if ENCODER_TYPE == 'VCEEncC' else self.ENCODER_TS_READ_TIMEOUT_ONAIR
                stream_data_last_write_time = time.time() - self.live_stream.getStreamDataWrittenAt()
                if ((live_stream_status.status == 'Standby' and stream_data_last_write_time > self.ENCODER_TS_READ_TIMEOUT_STANDBY) or
                    (live_stream_status.status == 'ONAir' and stream_data_last_write_time > encoder_ts_read_timeout_onair)):

                    # 番組名に「放送休止」などが入っている場合、チューナーから出力された放送波 TS に映像/音声ストリームが
                    # 含まれていない可能性が高いので、ここでエンコードタスクを停止する
                    ## 映像/音声ストリームが含まれていない場合は当然ながらエンコーダーはフリーズする
                    if program_present is None or program_present.isOffTheAirProgram():
                        self.live_stream.setStatus('Offline', 'この時間は放送を休止しています。(E-13)')

                    # それ以外なら、エンコーダーの再起動で復帰できる可能性があるのでエンコードタスクを再起動する
                    else:

                        # できるだけエンコーダーのエラーメッセージを拾ってログを出力してから終了したいので、1秒間実行を待機する
                        await asyncio.sleep(1)

                        # エンコードタスクを再起動
                        result = self.live_stream.setStatus('Restart', 'エンコードが途中で停止しました。エンコードタスクを再起動しています… (ER-04)')

                        # エンコーダーのログを表示 (FFmpeg は最後の50行、HWEncC は最後の150行を表示)
                        if result is True:
                            if ENCODER_TYPE == 'FFmpeg':
                                for log in lines[-51:-1]:
                                    logging.warning(log)
                            else:
                                for log in lines[-151:-1]:
                                    logging.warning(log)

                # チューナーとの接続が切断された場合
                ## ref: https://stackoverflow.com/a/45251241/17124142
                if ((BACKEND_TYPE == 'Mirakurun' and response is not None and response.closed is True) or
                    (BACKEND_TYPE == 'EDCB' and self.live_stream.tuner is not None and self.live_stream.tuner.isDisconnected() is True)):

                    # エンコードタスクを再起動
                    self.live_stream.setStatus('Restart', 'チューナーとの接続が切断されました。エンコードタスクを再起動しています… (ER-05)')

                # エンコーダーが意図せず終了した場合
                if encoder.returncode is not None:

                    # 複数 GPU が搭載されていてかつ片方のみ H.265/HEVC でのエンコードに対応している環境も考えられるので、
                    # H.265/HEVC でのエンコードに非対応かは実際にエンコーダーが落ちた後に確認する
                    # もし H.265/HEVC 非対応なのが原因で落ちていた場合は復帰の見込みはないので、エンコードタスクを停止する
                    # 基本的にこれらのエラーでリトライが発生することはないので、初回のみチェックする (偽陽性を減らす意味合いもある)
                    if self._retry_count == 0:
                        for line in lines:
                            # QSVEncC: H.265/HEVC でのエンコードに非対応の環境
                            if ENCODER_TYPE == 'QSVEncC' and 'HEVC encoding is not supported on current platform.' in line:
                                self.live_stream.setStatus('Offline', 'お使いの Intel GPU は H.265/HEVC でのエンコードに対応していません。(E-14HQ)')
                                break
                            # NVEncC: H.265/HEVC でのエンコードに非対応の環境
                            elif ENCODER_TYPE == 'NVEncC' and 'does not support H.265/HEVC encoding.' in line:
                                # 他の行に available for encode. という文字列が含まれている場合は除外
                                available_for_encode = False
                                for line2 in lines:
                                    if 'available for encode.' in line2:
                                        available_for_encode = True
                                        break
                                if not available_for_encode:
                                    self.live_stream.setStatus('Offline', 'お使いの NVIDIA GPU は H.265/HEVC でのエンコードに対応していません。(E-15HN)')
                                    break
                            # VCEEncC: H.265/HEVC でのエンコードに非対応の環境
                            elif ENCODER_TYPE == 'VCEEncC' and 'HW Acceleration of H.265/HEVC is not supported on this platform.' in line:
                                self.live_stream.setStatus('Offline', 'お使いの AMD GPU は H.265/HEVC でのエンコードに対応していません。(E-16HV)')
                                break

                    # それ以外なら、エンコーダーの再起動で復帰できる可能性があるのでエンコードタスクを再起動する
                    if self.live_stream.getStatus().status == 'Offline':

                        # エンコードタスクを再起動
                        result = self.live_stream.setStatus('Restart', 'エンコーダーが強制終了されました。エンコードタスクを再起動しています… (ER-06)')

                        # エンコーダーのログを表示 (FFmpeg は最後の50行、HWEncC は最後の150行を表示)
                        if result is True:
                            if ENCODER_TYPE == 'FFmpeg':
                                for log in lines[-51:-1]:
                                    logging.warning(log)
                            else:
                                for log in lines[-151:-1]:
                                    logging.warning(log)

                # この時点で最新のライブストリームのステータスが Offline か Restart に変更されていたら、エンコードタスクの終了処理に移る
                live_stream_status = self.live_stream.getStatus()  # 更新されているかもしれないので再取得
                if live_stream_status.status == 'Offline' or live_stream_status.status == 'Restart':
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
        except Exception:
            pass

        # すべての視聴中クライアントのライブストリームへの接続を切断する
        self.live_stream.disconnectAll()

        # PSI/SI データアーカイバーを終了・破棄する
        if self.live_stream.psi_data_archiver is not None:
            self.live_stream.psi_data_archiver.destroy()
            self.live_stream.psi_data_archiver = None

        # エンコードタスクを再起動する（エンコーダーの再起動が必要な場合）
        if self.live_stream.getStatus().status == 'Restart':

            # チューナーをアンロックする (EDCB バックエンドのみ)
            ## 新しいエンコードタスクが今回立ち上げたチューナーを再利用できるようにする
            ## エンコーダーの再起動が必要なだけでチューナー自体はそのまま使えるし、わざわざ閉じてからもう一度開くのは無駄
            if BACKEND_TYPE == 'EDCB' and self.live_stream.tuner is not None:
                self.live_stream.tuner.unlock()

            # 再起動回数が最大再起動回数に達していなければ、再起動する
            if self._retry_count < self.MAX_RETRY_COUNT:
                self._retry_count += 1  # カウントを増やす
                await asyncio.sleep(0.1)  # 少し待つ
                background_tasks.add(asyncio.create_task(self.run()))  # 新しいタスクを立ち上げる

            # 最大再起動回数を使い果たしたので、Offline にする
            else:

                # Offline に設定
                if program_present is None or program_present.is_free is True:
                    # 無料番組
                    self.live_stream.setStatus('Offline', 'ライブストリームの再起動に失敗しました。(E-17)')
                else:
                    # 有料番組（契約されていないことが原因の可能性が高いため、そのように表示する）
                    self.live_stream.setStatus('Offline', 'ライブストリームの再起動に失敗しました。契約されていないため視聴できません。(E-17)')

                # チューナーを終了する (EDCB バックエンドのみ)
                ## tuner.close() した時点でそのチューナーインスタンスは意味をなさなくなるので、LiveStream インスタンスのプロパティからも削除する
                if BACKEND_TYPE == 'EDCB' and self.live_stream.tuner is not None:
                    await self.live_stream.tuner.close()
                    self.live_stream.tuner = None

        # 通常終了
        else:

            # EDCB バックエンドのみ
            if BACKEND_TYPE == 'EDCB' and self.live_stream.tuner is not None:

                # チャンネル切り替え時にチューナーが再利用されるように、3秒ほど待つ
                # 3秒間の間にチューナーの制御権限が新しいエンコードタスクに委譲されれば、下記の通り実際にチューナーが閉じられることはない
                await asyncio.sleep(3)

                # チューナーを終了する（まだ制御を他のチューナーインスタンスに委譲していない場合）
                # Idling に移行しアンロック状態になっている間にチューナーが再利用された場合、制御権限をもう持っていないため実際には何も起こらない
                ## tuner.close() した時点でそのチューナーインスタンスは意味をなさなくなるので、LiveStream インスタンスのプロパティからも削除する
                await self.live_stream.tuner.close()
                self.live_stream.tuner = None

        # 強制的にガベージコレクションを実行する
        gc.collect()
