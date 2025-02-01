
import anyio
import asyncio
import json
import time

from app import logging
from app import schemas
from app.constants import LIBRARY_PATH
from app.models.RecordedVideo import RecordedVideo


class KeyFrameAnalyzer:
    """
    録画ファイルのキーフレーム情報を解析するクラス
    ffprobe を使用して、録画ファイルのキーフレーム情報を取得し、DB に保存する
    解析した情報はストリーミング再生時に活用される
    """

    def __init__(self, file_path: anyio.Path) -> None:
        """
        録画ファイルのキーフレーム情報を解析するクラスを初期化する

        Args:
            file_path (anyio.Path): 解析対象の録画ファイルのパス
        """

        self.file_path = file_path


    async def analyze(self) -> None:
        """
        録画ファイルのキーフレーム情報を解析し、DB に保存する
        ffprobe を使い、録画ファイルから以下の情報を取得して、DB に保存する
        - キーフレームの位置 (ファイル内のバイトオフセット)
        - キーフレームの DTS (Decoding Time Stamp)
        - キーフレームの PTS (Presentation Time Stamp)
        """

        start_time = time.time()
        try:
            # ffprobe のオプションを設定
            ## -i: 入力ファイルを指定
            ## -select_streams v:0: 最初の映像ストリームのみを選択
            ## -show_packets: パケット情報を表示
            ## -show_entries packet=pts,dts,flags,pos: パケットの PTS, DTS, フラグ, 位置を表示
            ## -of json: JSON 形式で出力
            options = [
                '-i', str(self.file_path),
                '-select_streams', 'v:0',
                '-show_packets',
                '-show_entries', 'packet=pts,dts,flags,pos',
                '-of', 'json',
            ]

            # ffprobe を実行
            ffprobe_process = await asyncio.subprocess.create_subprocess_exec(
                LIBRARY_PATH['FFprobe'],
                *options,
                stdout = asyncio.subprocess.PIPE,
                stderr = asyncio.subprocess.PIPE,
            )

            # ffprobe の出力を取得
            stdout, stderr = await ffprobe_process.communicate()

            # 終了コードを確認
            if ffprobe_process.returncode != 0:
                error_message = stderr.decode('utf-8', errors='ignore')
                logging.error(f'{self.file_path}: ffprobe analysis failed with return code {ffprobe_process.returncode}. Error: {error_message}')
                return

            # ffprobe の出力を JSON としてパース
            try:
                packets = json.loads(stdout.decode('utf-8'))['packets']
            except (json.JSONDecodeError, KeyError) as ex:
                logging.error(f'{self.file_path}: Failed to parse ffprobe output:', exc_info=ex)
                return

            # キーフレーム情報を抽出
            ## flags に 'K' が含まれているパケットがキーフレーム
            ## pos はファイル内のバイトオフセット
            ## dts は Decoding Time Stamp (デコード時刻)
            ## pts は Presentation Time Stamp (表示時刻)
            key_frames: list[schemas.KeyFrame] = []
            for packet in packets:
                # 必要なフィールドが存在することを確認
                if not all(field in packet for field in ['flags', 'pos', 'dts', 'pts']):
                    logging.error(f'{self.file_path}: Invalid packet data found in ffprobe output')
                    return

                # キーフレームのみを抽出
                if 'K' in packet['flags']:
                    key_frames.append({
                        'offset': int(packet['pos']),
                        'dts': int(packet['dts']),
                        'pts': int(packet['pts']),
                    })

            # パケットが1つも見つからなかった場合
            if not packets:
                logging.error(f'{self.file_path}: No packets found in ffprobe output')
                return

            # 最後のフレームが非キーフレームの場合、シーク可能性のために追加
            if 'K' not in packets[-1]['flags']:
                key_frames.append({
                    'offset': int(packets[-1]['pos']),
                    'dts': int(packets[-1]['dts']),
                    'pts': int(packets[-1]['pts']),
                })

            # キーフレームが1つも見つからなかった場合
            if not key_frames:
                logging.error(f'{self.file_path}: No keyframes found in the video')
                return

            # DB に保存
            ## ファイルパスから対応する RecordedVideo レコードを取得
            db_recorded_video = await RecordedVideo.get_or_none(file_path=str(self.file_path))
            if db_recorded_video is not None:
                # キーフレーム情報を更新
                db_recorded_video.key_frames = key_frames
                await db_recorded_video.save()
                logging.info(f'{self.file_path}: Keyframe analysis completed. ({len(key_frames)} keyframes found / {time.time() - start_time:.2f} sec)')
            else:
                logging.warning(f'{self.file_path}: RecordedVideo record not found.')

        except Exception as ex:
            logging.error(f'{self.file_path}: Error in keyframe analysis:', exc_info=ex)
