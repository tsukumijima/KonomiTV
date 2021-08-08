
import os
import subprocess
import threading
import time

from app.constants import CONFIG
from app.constants import LIBRARY_PATH
from app.constants import LIVESTREAM_QUALITY
from app.models import Channels
from app.utils import LiveStream
from app.utils import Logging


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
            scale = '' if quality == '1080p' else f',scale={LIVESTREAM_QUALITY[quality]["width"]}:{LIVESTREAM_QUALITY[quality]["height"]}'
            options.append(f'-filter_complex yadif=0:-1:1{scale};volume=2.0,channelsplit[FL][FR]')
            ## Lを主音声に、Rを副音声にマッピング
            options.append('-map 0:v:0 -map [FL] -map [FR] -map 0:d? -ignore_unknown')

        # フラグ
        ## 主に ffmpeg の起動を高速化するための設定
        options.append('-fflags nobuffer -flags low_delay -max_delay 250000 -max_interleave_delta 1 -threads auto')

        # 映像
        options.append(f'-vcodec libx264 -flags +cgop -vb {LIVESTREAM_QUALITY[quality]["video_bitrate"]} -maxrate {LIVESTREAM_QUALITY[quality]["video_bitrate_max"]}')
        options.append('-aspect 16:9 -r 30000/1001 -g 15 -preset veryfast -profile:v main')
        if is_dualmono is False:  # デュアルモノ以外
            ## 1440x1080 と 1920x1080 が混在しているので、1080p だけリサイズする解像度を指定しない
            if quality == '1080p':
                options.append('-vf yadif=0:-1:1')
            else:
                options.append(f'-vf yadif=0:-1:1,scale={LIVESTREAM_QUALITY[quality]["width"]}:{LIVESTREAM_QUALITY[quality]["height"]}')

        # 音声
        options.append(f'-acodec aac -ac 2 -ab {LIVESTREAM_QUALITY[quality]["audio_bitrate"]} -ar 48000')
        if is_dualmono is False:  # デュアルモノ以外
            options.append('-af volume=2.0')

        # 出力
        options.append('-y -f mpegts')  # MPEG-TS 出力ということを明示
        options.append('pipe:1')  # 標準入力へ出力

        # オプションをスペースで区切って配列にする
        result = []
        for option in options:
            result += option.split(' ')

        return result


    def run(self, channel_id:str, quality:str, encoder_type:str, is_dualmono:bool=False) -> None:

        # ライブストリームのインスタンスを取得する
        livestream = LiveStream(channel_id, quality)

        # ステータスを Standby に設定
        livestream.setStatus('Standby', 'エンコーダーを起動しています…')

        # チャンネル ID からサービス ID とネットワーク ID を取得する
        from app.utils import RunAwait  # 循環インポートを防ぐため、あえてここでインポートする
        channel = RunAwait(Channels.filter(channel_id=channel_id).first())
        service_id = channel.service_id
        network_id = channel.network_id

        # Mirakurun 形式のサービス ID
        # NID と SID を 5 桁でゼロ埋めした上で int に変換する
        mirakurun_service_id = int(str(network_id).zfill(5) + str(service_id).zfill(5))
        # Mirakurun API の URL を作成
        mirakurun_stream_api_url = f'{CONFIG["general"]["mirakurun_url"]}/api/services/{mirakurun_service_id}/stream'

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
            Logging.info(f'***** {livestream.livestream_id} FFmpeg Commands *****\nffmpeg {" ".join(encoder_options)}')

            ## プロセスを非同期で作成・実行
            encoder = subprocess.Popen(
                [LIBRARY_PATH['ffmpeg']] + encoder_options,
                stdin=ast.stdout,  # arib-subtitle-timedmetadater からの入力
                stdout=subprocess.PIPE,  # ストリーム出力
                stderr=subprocess.PIPE,  # ログ出力
                creationflags=subprocess.CREATE_NO_WINDOW,  # conhost を開かない
            )

        # ***** エンコーダーの出力の書き込み *****

        def writer():

            # 非同期でエンコーダーから受けた出力を随時 Queue に書き込む
            while True:

                # エンコーダーの出力をライブストリームに書き込む
                # R/W バッファ: 188B (TS Packet Size) * 256 = 48128B
                livestream.write(encoder.stdout.read(48128))

                # エンコーダープロセスが終了していたらループを抜ける
                if encoder.poll() is not None:

                    # ループを抜ける前に、接続している全てのクライアントの Queue にライブストリームの終了を知らせる None を書き込む
                    # クライアントは None を受信した場合、ストリーミングを終了するようになっている
                    # これがないとクライアントはライブストリームが終了した事に気づかず、Queue を取り出そうとしてずっとブロッキングされてしまう
                    for client in livestream.livestream['client']:
                        if client is not None:
                            client['queue'].put(None)

                    # ループを抜ける
                    break

        # スレッドを開始
        thread_writer = threading.Thread(target=writer)
        thread_writer.start()

        # ***** エンコーダーの出力監視と制御 *****

        # エンコード終了後にエンコードタスクを再起動すべきかのフラグ
        is_restart_required = False

        # エンコーダーの出力結果を取得
        line:str = str()
        linebuffer:bytes = bytes()
        while True:

            # ライブストリームのステータスを取得
            livestream_status = livestream.getStatus()

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

                    #Logging.info(line)

                    # エンコードの進捗を判定し、ステータスを更新する
                    # 誤作動防止のため、ステータスが Standby の間のみ更新できるようにする
                    if livestream_status['status'] == 'Standby':

                        # ffmpeg
                        if encoder_type == 'ffmpeg':
                            if 'libpostproc    55.  9.100 / 55.  9.100' in line:
                                livestream.setStatus('Standby', 'チューナーを開いています…')
                            elif 'arib parser was created' in line:
                                livestream.setStatus('Standby', 'エンコードを開始しています…')
                            elif 'frame=    1 fps=0.0 q=0.0' in line:
                                livestream.setStatus('Standby', 'バッファリングしています…')
                            elif 'frame=' in line:
                                livestream.setStatus('ONAir', 'ライブストリームは ONAir です。')

            # 現在 ONAir でかつクライアント数が 0 なら Idling（アイドリング状態）に移行
            if livestream_status['status'] == 'ONAir' and livestream_status['client_count'] == 0:
                livestream.setStatus('Idling', 'ライブストリームは Idling です。')

            # 現在 Idling でかつ最終更新から指定された秒数以上経っていたらエンコーダーを終了し、Offline 状態に移行
            if (livestream_status['status'] == 'Idling') and \
               (time.time() - livestream_status['updated_at'] > CONFIG['livestream']['max_alive_time']):
                livestream.setStatus('Offline', 'ライブストリームは Offline です。')
                break

            # すでに Offline 状態になっている場合、エンコーダーを終了する
            # エンコードタスク以外から Offline 状態に移行される事もあり得るため
            if livestream_status['status'] == 'Offline':
                break

            # 特定のエラーログが出力されている場合は回復が見込めないため、エンコーダーを終了する
            ## ffmpeg
            if encoder_type == 'ffmpeg':
                if 'Stream map \'0:v:0\' matches no streams.' in line:
                    # 主にチューナー不足が原因のエラーのため、エンコーダーの再起動は行わない
                    livestream.setStatus('Offline', 'チューナー不足のため、ライブストリームを開始できません。')
                    break
                if 'Conversion failed!' in line:
                    is_restart_required = True  # エンコーダーの再起動を要求
                    livestream.setStatus('Offline', 'エンコードの継続に失敗しました。ライブストリームを再起動します。')
                    break

            # エンコーダーが意図せず終了した場合、エンコーダーを（明示的に）終了する
            if not buffer and encoder.poll() is not None:
                is_restart_required = True  # エンコーダーの再起動を要求
                livestream.setStatus('Offline', 'エンコーダーが強制終了されました。ライブストリームを再起動します。')
                break

        # ***** エンコード終了後の処理 *****

        # 明示的にプロセスを終了する
        ast.kill()
        encoder.kill()

        # エンコードタスクを再起動する（エンコーダーの再起動が必要な場合）
        if is_restart_required is True:
            self.run(channel_id, quality, encoder_type=encoder_type, is_dualmono=False)
