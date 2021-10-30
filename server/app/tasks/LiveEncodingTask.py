
import os
import requests
import subprocess
import threading
import time

from app.constants import CONFIG, LIBRARY_PATH, QUALITY
from app.models import Channels
from app.models import LiveStream
from app.models import Programs
from app.utils import Logging
from app.utils import RunAwait
from app.utils.EDCB import EDCBTuner


class LiveEncodingTask():


    def __init__(self):

        # エンコーダーの最大再起動回数
        # この数を超えた場合はエンコーダーを再起動しない（無限ループ避け）
        self.max_retry_count = 5  # 5 回まで


    def buildFFmpegOptions(self, quality:str, is_dualmono:bool=False) -> list:
        """
        FFmpeg に渡すオプションを組み立てる

        Args:
            quality (str): 映像の品質 (1080p ~ 240p)
            is_dualmono (bool, optional): 放送がデュアルモノかどうか

        Returns:
            list: FFmpeg に渡すオプションが連なる配列
        """

        # オプションの入る配列
        options = []

        # 入力
        ## -analyzeduration をつけることで、ストリームの分析時間を短縮できる
        options.append('-f mpegts -analyzeduration 500000 -i pipe:0')

        # ストリームのマッピング
        # 音声切り替えのため、主音声・副音声両方をエンコード後の TS に含む

        ## 通常放送・音声多重放送向け
        ## 副音声が検出できない場合にエラーにならないよう、? をつけておく
        if is_dualmono is False:
            options.append('-map 0:v:0 -map 0:a:0 -map 0:a:1 -map 0:d? -ignore_unknown')

        ## デュアルモノ向け（Lが主音声・Rが副音声）
        else:
            ## 1440x1080 と 1920x1080 が混在しているので、1080p だけリサイズする解像度を特殊な設定に
            scale = 'scale=-2:1080' if quality == '1080p' else f'scale={QUALITY[quality]["width"]}:{QUALITY[quality]["height"]}'
            # 参考: https://github.com/l3tnun/EPGStation/blob/master/config/enc3.js
            # -filter_complex を使うと -vf や -af が使えなくなるため、デュアルモノのみ -filter_complex に -vf や -af の内容も入れる
            options.append(f'-filter_complex yadif=0:-1:1,{scale};volume=2.0,channelsplit[FL][FR]')
            ## Lを主音声に、Rを副音声にマッピング
            options.append('-map 0:v:0 -map [FL] -map [FR] -map 0:d? -ignore_unknown')

        # フラグ
        ## 主に FFmpeg の起動を高速化するための設定
        options.append('-fflags nobuffer -flags low_delay -max_delay 250000 -max_interleave_delta 1 -threads auto')

        # 映像
        options.append(f'-vcodec libx264 -flags +cgop -vb {QUALITY[quality]["video_bitrate"]} -maxrate {QUALITY[quality]["video_bitrate_max"]}')
        options.append('-aspect 16:9 -r 30000/1001 -g 15 -preset veryfast -profile:v main')
        if is_dualmono is False:  # デュアルモノ以外
            ## 1440x1080 と 1920x1080 が混在しているので、1080p だけリサイズする解像度を特殊な設定に
            if quality == '1080p':
                options.append('-vf yadif=0:-1:1,scale=-2:1080')
            else:
                options.append(f'-vf yadif=0:-1:1,scale={QUALITY[quality]["width"]}:{QUALITY[quality]["height"]}')

        # 音声
        ## 音声が 5.1ch かどうかに関わらず、ステレオにダウンミックスする
        options.append(f'-acodec aac -aac_coder twoloop -ac 2 -ab {QUALITY[quality]["audio_bitrate"]} -ar 48000')
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


    def buildHWEncCOptions(self, encoder_type:str, quality:str, is_dualmono:bool=False) -> list:
        """
        QSVEncC・NVEncC・VCEEncC (便宜上 HWEncC と総称) に渡すオプションを組み立てる

        Args:
            encoder_type (str): エンコーダー (QSVEncC or NVEncC or VCEEncC)
            quality (str): 映像の品質 (1080p ~ 240p)
            is_dualmono (bool, optional): 放送がデュアルモノかどうか

        Returns:
            list: HWEncC に渡すオプションが連なる配列
        """

        # オプションの入る配列
        options = []

        # 入力
        ## --input-probesize, --input-analyze をつけることで、ストリームの分析時間を短縮できる
        ## 両方つけるのが重要で、--input-analyze だけだとエンコーダーがフリーズすることがある
        options.append('--input-format mpegts --fps 30000/1001 --input-probesize 1000K --input-analyze 0.7 --input -')
        ## VCEEncC の HW デコーダーはエラー耐性が低く TS を扱う用途では不安定なので、SW デコーダーを利用する
        if encoder_type == 'VCEEncC':
            options.append('--avsw')
        ## QSVEncC・NVEncC は HW デコーダーを利用する
        else:
            options.append('--avhw')

        # ストリームのマッピング
        # 音声切り替えのため、主音声・副音声両方をエンコード後の TS に含む
        if is_dualmono is False:
            ## 通常放送・音声多重放送向け
            ## 音声が 5.1ch かどうかに関わらず、ステレオにダウンミックスする
            options.append('--audio-stream 1?:stereo --audio-stream 2?:stereo --data-copy timed_id3')
            ## 音声トラックの指定
            audio_track = ''
        else:
            ## デュアルモノ向け（Lが主音声・Rが副音声）
            options.append('--audio-stream 1?FL:stereo,FR:stereo --data-copy timed_id3')
            ## 音声トラックの指定
            ## 明示的に音声トラックを指定しないと、不要な副音声ストリームがコピーされてしまう
            audio_track = '1?'

        # フラグ
        ## 主に HWEncC の起動を高速化するための設定
        options.append('-m fflags:nobuffer -m max_delay:250000 -m max_interleave_delta:1 --output-thread -1 --lowlatency')
        ## その他の設定
        options.append('--avsync forcecfr --max-procfps 60 --log-level debug')

        # 映像
        options.append(f'--vbr {QUALITY[quality]["video_bitrate"]} --max-bitrate {QUALITY[quality]["video_bitrate_max"]}')
        options.append(f'--dar 16:9 --gop-len 15 --profile main --interlace tff')
        ## インターレース解除
        if encoder_type == 'QSVEncC' or encoder_type == 'NVEncC':
            options.append('--vpp-deinterlace normal')
        elif encoder_type == 'VCEEncC':
            options.append('--vpp-afs preset=default')
        ## プリセット
        if encoder_type == 'QSVEncC':
            options.append('--quality balanced')
        elif encoder_type == 'NVEncC':
            options.append('--preset default')
        elif encoder_type == 'VCEEncC':
            options.append('--preset balanced')
        ## 1440x1080 と 1920x1080 が混在しているので、1080p だけリサイズする解像度を指定しない
        ## TODO: 本当は --output-res -2x1080 を使いたいのだが、なぜか 1080x1080 の扱いになってしまうため保留
        if quality != '1080p':
            options.append(f'--output-res {QUALITY[quality]["width"]}x{QUALITY[quality]["height"]}')

        # 音声
        options.append(f'--audio-codec {audio_track}aac:aac_coder=twoloop --audio-bitrate {audio_track}{QUALITY[quality]["audio_bitrate"]}')
        options.append(f'--audio-samplerate {audio_track}48000 --audio-filter {audio_track}volume=2.0 --audio-ignore-decode-error 30')

        # 出力
        options.append('--output-format mpegts')  # MPEG-TS 出力ということを明示
        options.append('--output -')  # 標準入力へ出力

        # オプションをスペースで区切って配列にする
        result = []
        for option in options:
            result += option.split(' ')

        return result


    def run(self, channel_id:str, quality:str) -> None:
        """
        エンコードタスクを実行する

        Args:
            channel_id (str): チャンネルID
            quality (str): 映像の品質 (1080p ~ 240p)
        """

        # ライブストリームのインスタンスを取得する
        livestream = LiveStream(channel_id, quality)

        # まだ Standby になっていなければ、ステータスを Standby に設定
        # 基本はエンコードタスクの呼び出し元である livestream.connect() の方で Standby に設定されるが、再起動の場合はそこを経由しないため必要
        if not (livestream.getStatus()['status'] == 'Standby' and livestream.getStatus()['detail'] == 'エンコーダーを起動しています…'):
            if CONFIG['general']['backend'] == 'Mirakurun':
                livestream.setStatus('Standby', 'エンコーダーを起動しています…')
            elif CONFIG['general']['backend'] == 'EDCB':
                livestream.setStatus('Standby', 'チューナーを起動しています…')

        # チャンネル情報からサービス ID とネットワーク ID を取得する
        channel:Channels = RunAwait(Channels.filter(channel_id=channel_id).first())

        # 現在の番組情報を取得する
        program_present:Programs = RunAwait(channel.getCurrentAndNextProgram())[0]

        ## 番組情報が取得できなければ（放送休止中など）ここで Offline にしてエンコードタスクを停止する
        if program_present is None:
            time.sleep(0.5)  # ちょっと待つのがポイント
            livestream.setStatus('Offline', 'この時間は放送を休止しています。')
            return
        Logging.info(f'LiveStream:{livestream.livestream_id} Title:{program_present.title}')

        # tsreadex
        ## 放送波の前処理を行い、エンコードを安定させるツール
        ## オプション内容は https://github.com/xtne6f/tsreadex を参照
        tsreadex = subprocess.Popen(
            [
                ## tsreadex のパス
                LIBRARY_PATH['tsreadex'],
                # 取り除く TS パケットの10進数の PID
                ## EIT の PID を指定
                '-x', '18/38/39',
                # 特定サービスのみを選択して出力するフィルタを有効にする
                ## 有効にすると、特定のストリームのみ PID を固定して出力される
                '-n', '-1',
                # 主音声ストリームが常に存在する状態にする
                ## ストリームが存在しない場合、無音の AAC ストリームが出力される
                '-a', '1',
                # 副音声ストリームが常に存在する状態にする
                ## ストリームが存在しない場合、無音の AAC ストリームが出力される
                '-b', '1',
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
                # 標準入力を設定
                '-',
            ],
            stdin=subprocess.PIPE,  # 受信した放送波を書き込む
            stdout=subprocess.PIPE,  # エンコーダーに繋ぐ
            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0),  # conhost を開かない
        )

        # エンコーダーのインスタンスが入る変数
        encoder = None

        # Mirakurun バックエンド
        if CONFIG['general']['backend'] == 'Mirakurun':

            # Mirakurun 形式のサービス ID
            # NID と SID を 5 桁でゼロ埋めした上で int に変換する
            mirakurun_service_id = int(str(channel.network_id).zfill(5) + str(channel.service_id).zfill(5))
            # Mirakurun API の URL を作成
            mirakurun_stream_api_url = f'{CONFIG["general"]["mirakurun_url"]}/api/services/{mirakurun_service_id}/stream'

            # HTTP リクエストを開始
            ## stream=True を設定することで、レスポンスの返却を待たずに処理を進められる
            response = requests.get(mirakurun_stream_api_url, headers={'X-Mirakurun-Priority': '0'}, stream=True)

        # EDCB バックエンド
        elif CONFIG['general']['backend'] == 'EDCB':

            # チューナーインスタンスを初期化
            tuner = EDCBTuner(channel.network_id, channel.service_id, channel.transport_stream_id)

            # チューナーを起動する
            # アンロック状態のチューナーインスタンスがあれば、自動的にそのチューナーが再利用される
            is_tuner_opened = RunAwait(tuner.open())

            # チューナーの起動に失敗した
            # 成功時は tuner.close() するか予約などに割り込まれるまで起動しつづけるので注意
            if is_tuner_opened is False:
                livestream.setStatus('Offline', 'チューナーの起動に失敗したため、ライブストリームを開始できません。')
                return

            # チューナーをロックする
            # ロックしないと途中でチューナーの制御を横取りされてしまう
            livestream.setStatus('Standby', 'エンコーダーを起動しています…')
            tuner.lock()

            # チューナーに接続する（放送波が送信される名前付きパイプを見つける）
            edcb_networktv_path = RunAwait(tuner.connect())

            # チューナーへの接続に失敗した
            if edcb_networktv_path is None:
                livestream.setStatus('Offline', 'チューナーへの接続に失敗したため、ライブストリームを開始できません。')
                return

            # ライブストリームにチューナーインスタンスを設定する
            # Idling への切り替え、ONAir への復帰時に LiveStream 側でチューナーのアンロック/ロックが行われる
            livestream.setTunerInstance(tuner)

            # 名前付きパイプを開く
            # R/W バッファ: 188B (TS Packet Size) * 256 = 48128B
            pipe = open(edcb_networktv_path, mode='rb', buffering=48128)

        # ***** エンコーダーへの入力の読み込み *****

        def reader():

            # 受信した放送波が入るイテレータ
            if CONFIG['general']['backend'] == 'Mirakurun':
                # R/W バッファ: 188B (TS Packet Size) * 256 = 48128B
                stream_iterator = response.iter_content(chunk_size=48128)
            elif CONFIG['general']['backend'] == 'EDCB':
                stream_iterator = pipe

            # Mirakurun / EDCB から受信した放送波を随時 tsreadex の入力に書き込む
            try:
                for chunk in stream_iterator:

                    # ストリームデータを tsreadex の標準入力に書き込む
                    try:
                        tsreadex.stdin.write(bytes(chunk))
                    except BrokenPipeError:
                        break
                    except OSError:
                        break

                    # Mirakurun からエラーが返された
                    if CONFIG['general']['backend'] == 'Mirakurun' and response.status_code is not None and response.status_code != 200:
                        # Offline にしてエンコードタスクを停止する
                        if response.status_code == 503:
                            livestream.setStatus('Offline', 'チューナー不足のため、ライブストリームを開始できません。')
                        else:
                            livestream.setStatus('Offline', 'チューナーで不明なエラーが発生したため、ライブストリームを開始できません。')
                        break

                    # 現在 ONAir でかつストリームデータの最終書き込み時刻から 5 秒以上が経過しているなら、エンコーダーがフリーズしたものとみなす
                    # 現在 Standby でかつストリームデータの最終書き込み時刻から 20 秒以上が経過している場合も、エンコーダーがフリーズしたものとみなす
                    # stdout も stderr もブロッキングされてしまっている場合を想定し、このスレッドでも確認する
                    livestream_status = livestream.getStatus()
                    if ((livestream_status['status'] == 'ONAir' and time.time() - livestream.stream_data_written_at > 5) or
                        (livestream_status['status'] == 'Standby' and time.time() - livestream.stream_data_written_at > 20)):

                        # エンコーダーを強制終了させないと次の処理に進まない事が想定されるので、エンコーダーを強制終了
                        if encoder is not None:
                            encoder.kill()

                        # ライブストリームを再起動
                        livestream.setStatus('Restart', 'エンコードが途中で停止しました。ライブストリームを再起動します。')
                        break

                    # tsreadex が既に終了しているか、接続が切断された
                    if ((tsreadex.poll() is not None) or
                        (CONFIG['general']['backend'] == 'Mirakurun' and response.raw.closed is True) or
                        (CONFIG['general']['backend'] == 'EDCB' and pipe.closed is True)):
                        break
            except OSError:
                pass

            # 明示的に接続を閉じる
            if CONFIG['general']['backend'] == 'Mirakurun':
                response.close()
            elif CONFIG['general']['backend'] == 'EDCB':
                pipe.close()

        # スレッドを開始
        thread_reader = threading.Thread(target=reader, name='LiveEncodingTask-Reader')
        thread_reader.start()

        # ***** エンコーダープロセスの作成と実行 *****

        # エンコーダーの種類を取得
        encoder_type = CONFIG['livestream']['encoder']

        ## 画質が 480i なのに 1080p にしてもしょうがないので、指定された画質が 480p 以上なら 480p に固定する
        if program_present.video_resolution == '480i' and int(quality[:-1]) > 480:
            real_quality = '480p'
        else:
            real_quality = quality

        # FFmpeg
        if encoder_type == 'FFmpeg':

            # オプションを取得
            # 現在放送中の番組がデュアルモノの場合、デュアルモノ用のエンコードオプションを取得
            if program_present.primary_audio_type == '1/0+1/0モード(デュアルモノ)':
                encoder_options = self.buildFFmpegOptions(real_quality, is_dualmono=True)
            else:
                encoder_options = self.buildFFmpegOptions(real_quality, is_dualmono=False)
            Logging.info(f'LiveStream:{livestream.livestream_id} FFmpeg Commands:\nffmpeg {" ".join(encoder_options)}')

            # プロセスを非同期で作成・実行
            encoder = subprocess.Popen(
                [LIBRARY_PATH['FFmpeg']] + encoder_options,
                stdin=tsreadex.stdout,  # tsreadex からの入力
                stdout=subprocess.PIPE,  # ストリーム出力
                stderr=subprocess.PIPE,  # ログ出力
                creationflags=(subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0),  # conhost を開かない
            )

        # HWEncC
        elif encoder_type == 'QSVEncC' or encoder_type == 'NVEncC' or encoder_type == 'VCEEncC':

            # オプションを取得
            # 現在放送中の番組がデュアルモノの場合、デュアルモノ用のエンコードオプションを取得
            if program_present.primary_audio_type == '1/0+1/0モード(デュアルモノ)':
                encoder_options = self.buildHWEncCOptions(encoder_type, real_quality, is_dualmono=True)
            else:
                encoder_options = self.buildHWEncCOptions(encoder_type, real_quality, is_dualmono=False)
            Logging.info(f'LiveStream:{livestream.livestream_id} {encoder_type} Commands:\n{encoder_type} {" ".join(encoder_options)}')

            # プロセスを非同期で作成・実行
            encoder = subprocess.Popen(
                [LIBRARY_PATH[encoder_type]] + encoder_options,
                stdin=tsreadex.stdout,  # tsreadex からの入力
                stdout=subprocess.PIPE,  # ストリーム出力
                stderr=subprocess.PIPE,  # ログ出力
                creationflags=(subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0),  # conhost を開かない
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
                    for client in livestream.clients:
                        if client is not None:
                            client.queue.put(None)

                    # この時点で全てのクライアントの接続が切断されているので、クライアントが入るリストをクリアする
                    livestream.clients = list()

                    # ループを抜ける
                    break

        # スレッドを開始
        thread_writer = threading.Thread(target=writer, name='LiveEncodingTask-Writer')
        thread_writer.start()

        # ***** エンコーダーの出力監視と制御 *****

        # エンコード終了後にエンコードタスクを再起動すべきかのフラグ
        is_restart_required = False

        # エンコーダーの出力結果を取得
        line:str = str()
        lines:list = list()
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

                    # リストに追加
                    lines.append(line)

                    # 行バッファを消去
                    linebuffer = bytes()

                    # ストリーム関連のログを表示
                    if 'Stream #0:' in line:
                        Logging.debug_simple(line)

                    # エンコードの進捗を判定し、ステータスを更新する
                    # 誤作動防止のため、ステータスが Standby の間のみ更新できるようにする
                    if livestream_status['status'] == 'Standby':
                        # FFmpeg
                        if encoder_type == 'FFmpeg':
                            if 'libpostproc    55.  9.100 / 55.  9.100' in line:
                                if CONFIG['general']['backend'] == 'Mirakurun':
                                    livestream.setStatus('Standby', 'チューナーを起動しています…')
                            elif 'arib parser was created' in line or 'Invalid frame dimensions 0x0.' in line:
                                livestream.setStatus('Standby', 'エンコードを開始しています…')
                            elif 'frame=    1 fps=0.0 q=0.0' in line:
                                livestream.setStatus('Standby', 'バッファリングしています…')
                            elif 'frame=' in line:
                                livestream.setStatus('ONAir', 'ライブストリームは ONAir です。')
                        ## HWEncC
                        elif encoder_type == 'QSVEncC' or encoder_type == 'NVEncC' or encoder_type == 'VCEEncC':
                            if 'input source set to stdin.' in line:
                                if CONFIG['general']['backend'] == 'Mirakurun':  # EDCB ではすでにチューナーを起動しているため不要
                                    livestream.setStatus('Standby', 'チューナーを起動しています…')
                            elif 'opened file "pipe:0"' in line:
                                livestream.setStatus('Standby', 'エンコードを開始しています…')
                            elif 'starting output thread...' in line:
                                livestream.setStatus('Standby', 'バッファリングしています…')
                            elif 'Encode Thread:' in line:
                                livestream.setStatus('Standby', 'バッファリングしています…')
                            elif ' frames: ' in line:
                                livestream.setStatus('ONAir', 'ライブストリームは ONAir です。')

            # 現在放送中の番組が終了した時
            if program_present is not None and time.time() > program_present.end_time.timestamp():

                # 次の番組情報を取得する
                program_following:Programs = RunAwait(channel.getCurrentAndNextProgram())[0]

                # 次の番組が None でない
                if program_following is not None:

                    # 現在:デュアルモノ以外 → 次:デュアルモノ
                    if (program_present.primary_audio_type != '1/0+1/0モード(デュアルモノ)') and \
                       (program_following.primary_audio_type == '1/0+1/0モード(デュアルモノ)'):
                        # エンコーダーの音声出力をデュアルモノ対応にするため、エンコーダーを再起動する
                        is_restart_required = True
                        livestream.setStatus('Restart', '音声をデュアルモノに切り替えています…')
                        break

                    # 現在:デュアルモノ → 次:デュアルモノ以外
                    if (program_present.primary_audio_type == '1/0+1/0モード(デュアルモノ)') and \
                       (program_following.primary_audio_type != '1/0+1/0モード(デュアルモノ)'):
                        # エンコーダーの音声出力をステレオ対応にするため、エンコーダーを再起動する
                        is_restart_required = True
                        livestream.setStatus('Restart', '音声をステレオに切り替えています…')
                        break

                    Logging.info(f'LiveStream:{livestream.livestream_id} Title:{program_following.title}')

                # 次の番組情報を現在の番組情報にコピー
                program_present = program_following
                del program_following

            # 現在 ONAir でかつクライアント数が 0 なら Idling（アイドリング状態）に移行
            if livestream_status['status'] == 'ONAir' and livestream_status['clients_count'] == 0:
                livestream.setStatus('Idling', 'ライブストリームは Idling です。')

            # 現在 Idling でかつ最終更新から指定された秒数以上経っていたらエンコーダーを終了し、Offline 状態に移行
            if ((livestream_status['status'] == 'Idling') and
                (time.time() - livestream_status['updated_at'] > CONFIG['livestream']['max_alive_time'])):
                livestream.setStatus('Offline', 'ライブストリームは Offline です。')
                break

            # 現在 ONAir でかつストリームデータの最終書き込み時刻から 5 秒以上が経過しているなら、エンコーダーがフリーズしたものとみなす
            # 現在 Standby でかつストリームデータの最終書き込み時刻から 20 秒以上が経過している場合も、エンコーダーがフリーズしたものとみなす
            # 何らかの理由でエンコードが途中で停止した場合、livestream.write() が実行されなくなるのを利用する
            # ステータスを Restart に設定し、エンコードタスクを再起動する
            if ((livestream_status['status'] == 'ONAir' and time.time() - livestream.stream_data_written_at > 5) or
                (livestream_status['status'] == 'Standby' and time.time() - livestream.stream_data_written_at > 20)):
                is_restart_required = True  # エンコーダーの再起動を要求
                livestream.setStatus('Restart', 'エンコードが途中で停止しました。ライブストリームを再起動します。')
                if encoder_type == 'FFmpeg':
                    # 直近 50 件のログを表示
                    for log in lines[-51:-1]:
                        Logging.warning(log)
                    break
                # HWEncC はログを詳細にハンドリングするためにログレベルを debug に設定しているため、FFmpeg よりもログが圧倒的に多い
                elif encoder_type == 'QSVEncC' or encoder_type == 'NVEncC' or encoder_type == 'VCEEncC':
                    # 直近 150 件のログを表示
                    for log in lines[-151:-1]:
                        Logging.warning(log)
                    break

            # すでに Restart 状態になっている場合、エンコーダーを終了する
            # エンコードタスク以外から Restart 状態に設定される事も考えられるため
            if livestream_status['status'] == 'Restart':
                is_restart_required = True  # エンコーダーの再起動を要求
                break

            # すでに Offline 状態になっている場合、エンコーダーを終了する
            # エンコードタスク以外から Offline 状態に設定される事も考えられるため
            if livestream_status['status'] == 'Offline':
                break

            # 特定のエラーログが出力されている場合は回復が見込めないため、エンコーダーを終了する
            # エンコーダーを再起動することで回復が期待できる場合は、ステータスを Restart に設定しエンコードタスクを再起動する
            ## FFmpeg
            if encoder_type == 'FFmpeg':
                if 'Stream map \'0:v:0\' matches no streams.' in line:
                    # 主にチューナー不足が原因のエラーのため、エンコーダーの再起動は行わない
                    livestream.setStatus('Offline', 'チューナー不足のため、ライブストリームを開始できません。')
                    break
                elif 'Conversion failed!' in line:
                    # 捕捉されないエラー
                    is_restart_required = True  # エンコーダーの再起動を要求
                    livestream.setStatus('Restart', 'エンコード中に予期しないエラーが発生しました。ライブストリームを再起動します。')
                    # 直近 50 件のログを表示
                    for log in lines[-51:-1]:
                        Logging.warning(log)
                    break
            ## HWEncC
            elif encoder_type == 'QSVEncC' or encoder_type == 'NVEncC' or encoder_type == 'VCEEncC':
                if 'error finding stream information.' in line:
                    # 主にチューナー不足が原因のエラーのため、エンコーダーの再起動は行わない
                    livestream.setStatus('Offline', 'チューナー不足のため、ライブストリームを開始できません。')
                    break
                elif 'due to the NVIDIA\'s driver limitation.' in line:
                    # NVEncC で、同時にエンコードできるセッション数 (Geforceだと3つ) を全て使い果たしている時のエラー
                    livestream.setStatus('Offline', 'NVENC のエンコードセッションが不足しているため、ライブストリームを開始できません。')
                    break
                elif 'unable to decode by qsv.' in line:
                    # QSVEncC 非対応の環境
                    livestream.setStatus('Offline', 'QSVEncC 非対応の環境のため、ライブストリームを開始できません。')
                    break
                elif 'CUDA not available.' in line:
                    # NVEncC 非対応の環境
                    livestream.setStatus('Offline', 'NVEncC 非対応の環境のため、ライブストリームを開始できません。')
                    break
                elif 'Failed to initalize VCE factory:' in line:
                    # VCEEncC 非対応の環境
                    livestream.setStatus('Offline', 'VCEEncC 非対応の環境のため、ライブストリームを開始できません。')
                    break
                elif 'Consider increasing the value for the --input-analyze and/or --input-probesize!' in line:
                    # --input-probesize or --input-analyze の期間内に入力ストリームの解析が終わらなかった
                    is_restart_required = True  # エンコーダーの再起動を要求
                    livestream.setStatus('Restart', '入力ストリームの解析に失敗しました。ライブストリームを再起動します。')
                    break
                elif 'finished with error!' in line:
                    # 捕捉されないエラー
                    is_restart_required = True  # エンコーダーの再起動を要求
                    livestream.setStatus('Restart', 'エンコード中に予期しないエラーが発生しました。ライブストリームを再起動します。')
                    # 直近 150 件のログを表示
                    for log in lines[-151:-1]:
                        Logging.warning(log)
                    break

            # エンコーダーが意図せず終了した場合、エンコーダーを（明示的に）終了する
            if not buffer and encoder.poll() is not None:
                # エンコーダーの再起動を要求
                is_restart_required = True
                # エンコーダーの再起動前提のため、あえて Offline にはせず Restart とする
                livestream.setStatus('Restart', 'エンコーダーが強制終了されました。ライブストリームを再起動します。')
                if encoder_type == 'FFmpeg':
                    # 直近 50 件のログを表示
                    for log in lines[-51:-1]:
                        Logging.warning(log)
                    break
                # HWEncC はログを詳細にハンドリングするためにログレベルを debug に設定しているため、FFmpeg よりもログが圧倒的に多い
                elif encoder_type == 'QSVEncC' or encoder_type == 'NVEncC' or encoder_type == 'VCEEncC':
                    # 直近 150 件のログを表示
                    for log in lines[-151:-1]:
                        Logging.warning(log)
                    break
                break

        # ***** エンコード終了後の処理 *****

        # 明示的にプロセスを終了する
        tsreadex.kill()
        encoder.kill()

        # エンコードタスクを再起動する（エンコーダーの再起動が必要な場合）
        if is_restart_required is True:

            # チューナーをアンロックする（ EDCB バックエンドのみ）
            # 新しいエンコードタスクが今回立ち上げたチューナーを再利用できるようにする
            # エンコーダーの再起動が必要なだけでチューナー自体はそのまま使えるし、わざわざ閉じてからもう一度開くのは無駄
            if CONFIG['general']['backend'] == 'EDCB':
                tuner.unlock()

            # 最大再起動回数が 0 より上であれば
            if self.max_retry_count > 0:
                time.sleep(0.1)  # 少し待つ
                self.max_retry_count = self.max_retry_count - 1  # カウントを減らす
                self.run(channel_id, quality)  # 新しいタスクを立ち上げる

            # 最大再起動回数を使い果たしたので、Offline にする
            else:

                # Offline に設定
                livestream.setStatus('Offline', 'ライブストリームの再起動に失敗しました。')

                # チューナーを終了する（ EDCB バックエンドのみ）
                if CONFIG['general']['backend'] == 'EDCB':
                    RunAwait(tuner.close())

        # 通常終了
        else:

            # EDCB バックエンドのみ
            if CONFIG['general']['backend'] == 'EDCB':

                # チャンネル切り替え時にチューナーが再利用されるように、3秒ほど待つ
                # 3秒間の間にチューナーの制御権限が新しいエンコードタスクに委譲されれば、下記の通り実際にチューナーが閉じられることはない
                time.sleep(3)

                # チューナーを終了する（まだ制御を他のチューナーインスタンスに委譲していない場合）
                # Idling に移行しアンロック状態になっている間にチューナーが再利用された場合、制御権限をもう持っていないため実際には何も起こらない
                RunAwait(tuner.close())
