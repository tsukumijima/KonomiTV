
import celery
import celery.utils.log
import os
import subprocess
from django.conf import settings


class LiveEncodingTask(celery.Task):

    def __init__(self):

        # タスク名
        self.name = 'LiveEncodingTask'

        # ロガー
        self.logger = celery.utils.log.get_task_logger(__name__)

        # 映像・音声の品質定義
        self.quality = {
            '1080p': {
                'width': None,  # 縦解像度：1080p のみソースの解像度を使うため指定しない
                'height': None,  # 横解像度：1080p のみソースの解像度を使うため指定しない
                'video_bitrate': '6500K',  # 映像ビットレート
                'video_bitrate_max': '9000K',  # 映像最大ビットレート
                'audio_bitrate': '192K',  # 音声ビットレート
            },
            '720p': {
                'width': 1280,
                'height': 720,
                'video_bitrate': '4500K',
                'video_bitrate_max': '6200K',
                'audio_bitrate': '192K',  # 音声ビットレート
            },
            '540p': {
                'width': 940,
                'height': 540,
                'video_bitrate': '3000K',
                'video_bitrate_max': '4100K',
                'audio_bitrate': '192K',  # 音声ビットレート
            },
            '360p': {
                'width': 640,
                'height': 360,
                'video_bitrate': '1500K',
                'video_bitrate_max': '2000K',
                'audio_bitrate': '128K',  # 音声ビットレート
            },
        }


    def buildFFmpegOptions(self, quality:str, audiotype:str='normal') -> list:
        """FFmpeg に渡すオプションを組み立てる

        Args:
            quality (str): 映像の品質 (1080p ~ 360p)
            audiotype ([type], optional): 音声種別（ normal:通常・multiplex:音声多重放送・dualmono:デュアルモノ から選択）

        Returns:
            list: FFmpeg に渡すオプションが連なる配列
        """

        # オプションの入る配列
        options = []

        # 入力
        options.append('-f mpegts -analyzeduration 500000 -i pipe:0')

        # ストリームのマッピング
        # 音声多重放送・デュアルモノの場合も主音声・副音声両方をエンコード後の TS に含む（将来の音声切替対応へ準備）
        ## 通常向け
        if audiotype == 'normal':
            options.append('-map 0:v:0 -map 0:a:0 -map 0:d?')

        ## 音声多重放送向け
        ## 副音声が検出できない場合にエラーにならないよう、? をつけておく
        elif audiotype == 'multiplex':
            options.append('-map 0:v:0 -map 0:a:0 -map 0:a:1? -map 0:d?')

        ## デュアルモノ向け（Lが主音声・Rが副音声）
        elif audiotype == 'dualmono':
            # 参考: https://github.com/l3tnun/EPGStation/blob/master/config/enc3.js
            # -filter_complex を使うと -vf や -af が使えなくなるため、デュアルモノのみ -filter_complex に -vf や -af の内容も入れる
            ## 1440x1080 と 1920x1080 が混在しているので、1080p だけリサイズする解像度を指定しない
            scale = '' if quality == '1080p' else f',scale={self.quality[quality]["width"]}:{self.quality[quality]["height"]}'
            options.append(f'-filter_complex yadif=0:-1:1{scale};volume=2.0,channelsplit[FL][FR]')
            ## Lを主音声に、Rを副音声にマッピング
            options.append('-map 0:v:0 -map [FL] -map [FR] -map 0:d?')

        # 映像
        options.append(f'-vcodec libx264 -vb {self.quality[quality]["video_bitrate"]} -maxrate {self.quality[quality]["video_bitrate_max"]}')
        options.append('-aspect 16:9 -r 30000/1001 -preset veryfast -profile:v main -flags +cgop')
        if audiotype != 'dualmono':  # デュアルモノ以外
            ## 1440x1080 と 1920x1080 が混在しているので、1080p だけリサイズする解像度を指定しない
            if quality == '1080p':
                options.append('-vf yadif=0:-1:1')
            else:
                options.append(f'-vf yadif=0:-1:1,scale={self.quality[quality]["width"]}:{self.quality[quality]["height"]}')

        # 音声
        options.append(f'-acodec aac -ac 2 -ab {self.quality[quality]["audio_bitrate"]} -ar 48000')
        if audiotype != 'dualmono':  # デュアルモノ以外
            options.append('-af volume=2.0')

        # フラグ
        options.append('-threads auto -fflags nobuffer -flags low_delay -max_delay 250000 -max_interleave_delta 1')

        # 出力
        options.append('test.ts')

        # オプションをスペースで区切って配列にする
        result = []
        for option in options:
            result += option.split(' ')

        return result


    def run(self, encoder_type='ffmpeg'):

        # ストリームの URL（暫定で決め打ち）
        stream_url = 'http://192.168.1.28:40772/api/services/3273601024/stream'

        # arib-subtitle-timedmetadater
        ## プロセスを非同期で作成・実行
        ast = subprocess.Popen(
            [settings.LIBRARY_PATH['arib-subtitle-timedmetadater'], '--http', stream_url],
            stdout=subprocess.PIPE,  # ffmpeg に繋ぐ
            creationflags=subprocess.CREATE_NO_WINDOW,  # conhost を開かない
            bufsize=1000000,  # バッファサイズを 1MB に設定
        )

        # ffmpeg
        if encoder_type == 'ffmpeg':

            ## オプションを取得
            encoder_options = self.buildFFmpegOptions('1080p', audiotype='normal')
            ## プロセスを非同期で作成・実行
            encoder = subprocess.Popen(
                [settings.LIBRARY_PATH['ffmpeg']] + encoder_options,
                stdin=ast.stdout,  # arib-subtitle-timedmetadater からの入力
                stderr=subprocess.PIPE,  # ログ出力
                creationflags=subprocess.CREATE_NO_WINDOW,  # conhost を開かない
                bufsize=1000000,  # バッファサイズを 1MB に設定
            )

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
                    print(line)
                    self.logger.info(line)

            # プロセスが終了したらループ停止
            if not buffer and encoder.poll() is not None:
                print(f'ReturnCode: {str(encoder.returncode)}')
                print(f'Last Message: {line}')
                break
