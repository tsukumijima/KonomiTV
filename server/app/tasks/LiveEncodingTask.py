
import os
import subprocess
import threading

from app.constants import CONFIG
from app.constants import LIBRARY_PATH
from app.models import Channels
from app.utils import LiveStream
from app.utils import Logging
from app.utils import RunAwait


class LiveEncodingTask():


    def buildFFmpegOptions(self, quality:str, is_dualmono:bool=False) -> list:
        """FFmpeg に渡すオプションを組み立てる

        Args:
            quality (str): 映像の品質 (1080p ~ 360p)
            is_dualmono (bool, optional): 放送がデュアルモノかどうか

        Returns:
            list: FFmpeg に渡すオプションが連なる配列
        """

        # オプションの入る配列
        options = []

        # 入力
        ## analyzeduration をつけることで、ストリームの分析時間を短縮できる
        options.append('-f mpegts -analyzeduration 500000 -i pipe:0')

        # ストリームのマッピング
        # 主音声・副音声両方をエンコード後の TS に含む（将来の音声切替対応へ準備）
        ## 通常放送・音声多重放送向け
        ## 副音声が検出できない場合にエラーにならないよう、? をつけておく
        if is_dualmono is False:
            options.append('-map 0:v:0 -map 0:a:0 -map 0:a:1? -map 0:d? -ignore_unknown')

        ## デュアルモノ向け（Lが主音声・Rが副音声）
        else:
            # 参考: https://github.com/l3tnun/EPGStation/blob/master/config/enc3.js
            # -filter_complex を使うと -vf や -af が使えなくなるため、デュアルモノのみ -filter_complex に -vf や -af の内容も入れる
            ## 1440x1080 と 1920x1080 が混在しているので、1080p だけリサイズする解像度を指定しない
            scale = '' if quality == '1080p' else f',scale={LiveStream.quality[quality]["width"]}:{LiveStream.quality[quality]["height"]}'
            options.append(f'-filter_complex yadif=0:-1:1{scale};volume=2.0,channelsplit[FL][FR]')
            ## Lを主音声に、Rを副音声にマッピング
            options.append('-map 0:v:0 -map [FL] -map [FR] -map 0:d? -ignore_unknown')

        # フラグ
        ## 主に ffmpeg の起動を高速化するための設定
        options.append('-fflags nobuffer -flags low_delay -max_delay 250000 -max_interleave_delta 1 -threads auto')

        # 映像
        options.append(f'-vcodec libx264 -flags +cgop -vb {LiveStream.quality[quality]["video_bitrate"]} -maxrate {LiveStream.quality[quality]["video_bitrate_max"]}')
        options.append('-aspect 16:9 -r 30000/1001 -g 15 -preset veryfast -profile:v main')
        if is_dualmono is False:  # デュアルモノ以外
            ## 1440x1080 と 1920x1080 が混在しているので、1080p だけリサイズする解像度を指定しない
            if quality == '1080p':
                options.append('-vf yadif=0:-1:1')
            else:
                options.append(f'-vf yadif=0:-1:1,scale={LiveStream.quality[quality]["width"]}:{LiveStream.quality[quality]["height"]}')

        # 音声
        options.append(f'-acodec aac -ac 2 -ab {LiveStream.quality[quality]["audio_bitrate"]} -ar 48000')
        if is_dualmono is False:  # デュアルモノ以外
            options.append('-af volume=2.0')

        # 出力
        options.append('-y -f mpegts')  # MPEG-TS 出力ということを明示
        options.append('pipe:1')  # 標準入力へ出力

        # オプションをスペースで区切って配列にする
        result = []
        for option in options:
            result += option.split(' ')

        Logging.info(f'ffmpeg commands: ffmpeg {" ".join(result)}')

        return result


    def run(self, channel_id:str, quality:str, encoder_type:str='ffmpeg', is_dualmono:bool=False) -> None:

        # チャンネル ID からサービス ID とネットワーク ID を取得する
        channel = RunAwait(Channels.filter(channel_id=channel_id).first())
        service_id = channel.service_id
        network_id = channel.network_id

        # Mirakurun 形式のサービス ID
        # NID と SID を 5 桁でゼロ埋めした上で int に変換する
        mirakurun_service_id = int(str(network_id).zfill(5) + str(service_id).zfill(5))
        # Mirakurun API の URL を作成
        mirakurun_stream_api_url = f'{CONFIG["mirakurun_url"]}/api/services/{mirakurun_service_id}/stream'


        # ***** arib-subtitle-timedmetadater プロセスの作成と実行 *****

        # arib-subtitle-timedmetadater
        ## プロセスを非同期で作成・実行
        ast = subprocess.Popen(
            [LIBRARY_PATH['arib-subtitle-timedmetadater'], '--http', mirakurun_stream_api_url],
            stdout=subprocess.PIPE,  # ffmpeg に繋ぐ
            creationflags=subprocess.CREATE_NO_WINDOW,  # conhost を開かない
        )


        # ***** エンコーダープロセスの作成と実行 *****

        ## ffmpeg
        if encoder_type == 'ffmpeg':

            ## オプションを取得
            encoder_options = self.buildFFmpegOptions(quality, is_dualmono=is_dualmono)

            ## プロセスを非同期で作成・実行
            encoder = subprocess.Popen(
                [LIBRARY_PATH['ffmpeg']] + encoder_options,
                stdin=ast.stdout,  # arib-subtitle-timedmetadater からの入力
                stdout=subprocess.PIPE,  # ストリーム出力
                stderr=subprocess.PIPE,  # ログ出力
                creationflags=subprocess.CREATE_NO_WINDOW,  # conhost を開かない
            )


        # ***** エンコーダーの出力の書き込み *****

        # 新しいライブストリームを作成
        livestream = LiveStream(channel_id, quality)

        def writer():

            # 非同期でエンコーダーから受けた出力を随時 Queue に書き込む
            while True:

                # エンコーダーの出力をライブストリームに書き込む
                # R/W バッファ: 188B (TS Packet Size) * 256 = 48128B
                livestream.write(encoder.stdout.read(48128))

                # エンコーダープロセスが終了していたら、ライブストリームを終了する
                if encoder.poll() is not None:

                    # ライブストリームを終了する
                    livestream.destroy()

                    # ループを抜ける
                    break

        # スレッドを開始
        thread_writer = threading.Thread(target=writer)
        thread_writer.start()


        # ***** エンコーダーの出力監視と制御 *****

        # エンコーダーの出力結果を取得
        line:str = str()
        linebuffer:bytes = bytes()
        while True:

            # 1バイトずつ読み込む
            buffer:bytes = encoder.stderr.read(1)
            if buffer:  # データがあれば

                # 行バッファに追加
                linebuffer = linebuffer + buffer

                # 画面更新 or 改行があれば
                linebreak = b'\r' if os.name == 'nt' else b'\n'
                if (b'\r' in buffer) or (linebreak in buffer):

                    # 行（文字列）を取得
                    try:
                        # 余計な改行や空白を削除
                        # インデントが消えるので見栄えは悪いけど、プログラムで扱う分にはちょうどいい
                        line = linebuffer.decode('utf-8').strip()
                    # UnicodeDecodeError は握りつぶす（どっちみちチャンネル名とか解読できないし）
                    except UnicodeDecodeError:
                        pass

                    # 行バッファを消去
                    linebuffer = bytes()

                    # 行の内容を表示
                    #print(line)
                    Logging.debug(line)

            # プロセスが終了したらループ停止
            if not buffer and encoder.poll() is not None:
                Logging.info(f'Encoder polled. ReturnCode: {str(encoder.returncode)}')
                Logging.info(f'Last Message: {line}')
                break


        # ***** エンコード終了後の処理 *****

        # 明示的にプロセスを終了する
        ast.kill()
        encoder.kill()

        # エラー終了の場合はタスクを再起動する
        # 本番実装のときは再起動条件にいろいろ加わるが、今は簡易的に
        if encoder.returncode != 0:
            #self.run(channel_id, quality encoder_type=encoder_type, audio_type=audio_type)
            pass
