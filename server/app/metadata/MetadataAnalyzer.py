
import hashlib
import typer
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from pprint import pprint
from pymediainfo import MediaInfo
from typing import cast
from zoneinfo import ZoneInfo

from app.constants import LIBRARY_DIR
from app.metadata.CMSectionsDetector import CMSectionsDetector
from app.metadata.TSInfoAnalyzer import TSInfoAnalyzer
from app.models.Channel import Channel
from app.models.RecordedProgram import RecordedProgram
from app.models.RecordedVideo import RecordedVideo
from app.utils import GetPlatformEnvironment
from app.utils import Logging
from app.utils.TSInformation import TSInformation


class MetadataAnalyzer:
    """
    録画ファイルのメタデータを解析するクラス
    app.metadata モジュール内の各クラスを統括し、録画ファイルから取り出せるだけのメタデータを取り出す
    """

    def __init__(self, recorded_file_path: Path) -> None:
        """
        録画ファイルのメタデータを解析するクラスを初期化する

        Args:
            recorded_file_path (Path): 録画ファイルのパス
        """

        self.recorded_file_path = recorded_file_path


    def analyze(self) -> tuple[RecordedVideo, RecordedProgram, Channel | None] | None:
        """
        録画ファイル内のメタデータを解析し、データベースに格納するモデルを作成する
        各モデルの紐付けは行われていないので、子レコード作成後に別途紐付ける必要がある

        Returns:
            tuple[RecordedVideo, RecordedProgram, Channel | None] | None: 録画ファイル・番組情報・チャンネルを表すモデル
                (KonomiTV で再生可能なファイルではない場合は None が返される)
        """

        # 録画ファイルを表すモデルを作成
        recorded_video = RecordedVideo()
        recorded_video.file_path = str(self.recorded_file_path)

        # 録画ファイルのハッシュを計算
        try:
            recorded_video.file_hash = self.calculateTSFileHash()
        except ValueError:
            Logging.warning(f'{self.recorded_file_path}: File size is too small. ignored.')
            return None

        # MediaInfo から録画ファイルのメディア情報を取得
        ## 取得に失敗した場合は KonomiTV で再生可能なファイルではないと判断し、None を返す
        media_info = self.__analyzeMediaInfo()
        if media_info is None:
            return None

        # メディア情報から録画ファイルのメタデータを取得
        is_video_track_read = False
        is_primary_audio_track_read = False
        is_secondary_audio_track_read = False
        for track in media_info.tracks:

            # 全般（コンテナ情報）
            if track.track_type == 'General':
                recorded_video.duration = float(track.duration) / 1000  # ミリ秒を秒に変換
                # 今のところ MPEG-TS 固定
                if track.format == 'MPEG-TS':
                    recorded_video.container_format = 'MPEG-TS'
                if hasattr(track, 'start_time') and track.start_time is not None:
                    # 録画開始時刻と録画終了時刻を算出
                    ## 録画開始時刻は MediaInfo から "start_time" として取得できる (ただし小数点以下は省略されている)
                    ## "start_time" は "UTC 2023-06-26 23:59:52" のフォーマットになっているが、実際には JST の時刻が返される
                    ## ちゃんと JST のタイムゾーンが指定された datetime として扱うためには、datetime.fromisoformat() でパースする必要がある
                    ## 一度 ISO8601 に変換してからパースする
                    start_time_iso8601 = str(track.start_time).replace('UTC ', '').replace(' ', 'T') + '+09:00'
                    recorded_video.recording_start_time = datetime.fromisoformat(start_time_iso8601)
                    ## duration は小数点以下も含めた値が取得できるので、録画開始時刻を duration のうち小数点以下の部分を2で割った値だけ削る
                    ## これでかなり正確な録画開始時刻が算出できる
                    duration_miliseconds = (recorded_video.duration * 1000) % 1000
                    recorded_video.recording_start_time = recorded_video.recording_start_time - timedelta(milliseconds=duration_miliseconds / 2)
                    ## 録画終了時刻は MediaInfo から "end_time" として取得できるが、値が不正確なので、録画開始時刻から録画時間を足したものを使用する
                    recorded_video.recording_end_time = recorded_video.recording_start_time + timedelta(seconds=recorded_video.duration)
                else:
                    recorded_video.recording_start_time = None
                    recorded_video.recording_end_time = None

            # 映像
            elif track.track_type == 'Video' and is_video_track_read is False:
                # 長さが取得できない映像トラックは基本的に不正なため無視する
                # 録画データの一部分のみに主映像と異なる映像トラックが含まれている場合に発生する可能性がある (基本ないはずだが…)
                if hasattr(track, 'duration') is False or track.duration is None:
                    continue
                if track.format == 'MPEG Video':
                    recorded_video.video_codec = 'MPEG-2'
                elif track.format == 'AVC':
                    recorded_video.video_codec = 'H.264'
                elif track.format == 'HEVC':
                    recorded_video.video_codec = 'H.265'
                recorded_video.video_resolution_width = int(track.width)
                recorded_video.video_resolution_height = int(track.height)
                is_video_track_read = True

            # 主音声
            elif track.track_type == 'Audio' and is_primary_audio_track_read is False:
                # 長さが取得できない音声トラックは基本的に不正なため無視する
                # 録画マージンに音声多重放送が含まれているなど、録画データの一部分のみに副音声トラックが含まれている場合に発生する
                if hasattr(track, 'duration') is False or track.duration is None:
                    continue
                # 長さが取得できるが、全体の長さの 80% 以下の場合は不正なトラックと判断する
                if float(track.duration) / 1000 < recorded_video.duration * 0.8:
                    continue
                if track.format == 'AAC' and track.format_additionalfeatures == 'LC':
                    recorded_video.primary_audio_codec = 'AAC-LC'
                elif track.format == 'AAC' and track.format_additionalfeatures == 'HE-AAC':
                    recorded_video.primary_audio_codec = 'HE-AAC'
                elif track.format == 'MPEG Audio':
                    recorded_video.primary_audio_codec = 'MP2'
                if int(track.channel_s) == 1:
                    recorded_video.primary_audio_channel = 'Monaural'
                elif int(track.channel_s) == 2:
                    # デュアルモノも Stereo として判定される可能性がある (別途 RecordedProgram の primary_audio_type で判定すべき)
                    recorded_video.primary_audio_channel = 'Stereo'
                elif int(track.channel_s) == 6:
                    recorded_video.primary_audio_channel = '5.1ch'
                recorded_video.primary_audio_sampling_rate = int(track.sampling_rate)
                is_primary_audio_track_read = True

            # 副音声（存在する場合）
            elif track.track_type == 'Audio' and is_secondary_audio_track_read is False:
                # 長さが取得できない音声トラックは基本的に不正なため無視する
                # 録画マージンに音声多重放送が含まれているなど、録画データの一部分のみに副音声トラックが含まれている場合に発生する
                if hasattr(track, 'duration') is False or track.duration is None:
                    continue
                # 長さが取得できるが、全体の長さの 80% 以下の場合は不正なトラックと判断する
                if float(track.duration) / 1000 < recorded_video.duration * 0.8:
                    continue
                if track.format == 'AAC' and track.format_additionalfeatures == 'LC':
                    recorded_video.secondary_audio_codec = 'AAC-LC'
                elif track.format == 'AAC' and track.format_additionalfeatures == 'HE-AAC':
                    recorded_video.secondary_audio_codec = 'HE-AAC'
                elif track.format == 'MPEG Audio':
                    recorded_video.secondary_audio_codec = 'MP2'
                if int(track.channel_s) == 1:
                    recorded_video.secondary_audio_channel = 'Monaural'
                elif int(track.channel_s) == 2:
                    # デュアルモノも Stereo として判定される可能性がある (別途 RecordedProgram の secondary_audio_type で判定すべき)
                    recorded_video.secondary_audio_channel = 'Stereo'
                elif int(track.channel_s) == 6:
                    recorded_video.secondary_audio_channel = '5.1ch'
                recorded_video.secondary_audio_sampling_rate = int(track.sampling_rate)
                is_secondary_audio_track_read = True

        # 最低でも映像トラックと主音声トラックが含まれている必要がある
        # 映像か主音声、あるいは両方のトラックが含まれていない場合は None を返す
        if is_video_track_read is False or is_primary_audio_track_read is False:
            Logging.warning(f'{self.recorded_file_path}: Video or primary audio track is missing. ignored.')
            return None

        # duration が1分未満の場合は短すぎるので None を返す
        if recorded_video.duration < 60:
            Logging.warning(f'{self.recorded_file_path}: Duration is too short. ignored.')
            return None

        # MPEG-TS 形式のみ、TS ファイルに含まれる番組情報・チャンネル情報を解析する
        recorded_program = None
        channel = None
        if recorded_video.container_format == 'MPEG-TS':
            program_analyzer = TSInfoAnalyzer(recorded_video)
            result = program_analyzer.analyze()
            if result is not None:
                recorded_program, channel = result

        # それ以外の形式では番組情報を取得できないので、ファイル名などから最低限の情報を設定する
        # MPEG-TS 形式だが TS ファイルからチャンネル情報を取得できなかった場合も同様
        ## 他の値は RecordedProgram モデルで設定されたデフォルト値が自動的に入るので、タイトルと日時だけここで設定する
        if recorded_program is None:
            ## ファイルの作成日時を番組開始時刻として使用する
            ## 録画開始時刻が取得できる場合は、それを番組開始時刻として使用する
            ## ソートなど諸々の関係で日時が DB に入ってないと面倒くさいのでやむを得ず適当な値を入れている
            start_time = datetime.fromtimestamp(self.recorded_file_path.stat().st_ctime, tz=ZoneInfo('Asia/Tokyo'))
            if recorded_video.recording_start_time is not None:
                start_time = recorded_video.recording_start_time
            ## 拡張子を除いたファイル名をフォーマットした上でタイトルとして使用する
            title = TSInformation.formatString(self.recorded_file_path.stem)
            recorded_program = RecordedProgram(
                title = title,
                start_time = start_time,
                end_time = start_time + timedelta(seconds=recorded_video.duration),
                duration = recorded_video.duration,
            )

        # TODO: シリーズタイトル・話数・サブタイトルを取得する処理を追加する

        # CM 区間を検出する (MPEG-TS 形式のみ)
        ## 時間がかかるので最後に実行する
        if recorded_video.container_format == 'MPEG-TS':
            cm_sections_detector = CMSectionsDetector(recorded_video)
            recorded_video.cm_sections = cm_sections_detector.detect()
        else:
            recorded_video.cm_sections = []

        return recorded_video, recorded_program, channel


    def calculateTSFileHash(self, chunk_size: int = 1024 * 1024, num_chunks: int = 3) -> str:
        """
        録画ファイルのハッシュを計算する
        録画ファイル全体をハッシュ化すると時間がかかるため、ファイルの先頭、中央、末尾の3箇所のみをハッシュ化する

        Args:
            chunk_size (int, optional): チャンクのサイズ. Defaults to 1024 * 1024.
            num_chunks (int, optional): チャンクの数. Defaults to 3.

        Raises:
            ValueError: ファイルサイズが小さい場合に発生する

        Returns:
            str: 録画ファイルのハッシュ
        """

        # ファイルのサイズを取得する
        file_size = self.recorded_file_path.stat().st_size

        # ファイルサイズが`chunk_size * num_chunks`より小さい場合は十分な数のチャンクが取得できないため例外を発生させる
        if file_size < chunk_size * num_chunks:
            raise ValueError(f'File size must be at least {chunk_size * num_chunks} bytes.')

        with self.recorded_file_path.open('rb') as file:

            # SHA-256 だとハッシュ化に時間がかかるため、高速化のために MD5 を使用する
            ## 録画ファイルのハッシュを取りたいだけなのでセキュリティの考慮は不要
            hash_obj = hashlib.md5(usedforsecurity=False)

            # 指定された数のチャンクを読み込み、ハッシュを計算する
            for chunk_index in range(num_chunks):

                # 現在のチャンクのバイトオフセットを計算する
                offset = (file_size // (num_chunks + 1)) * (chunk_index + 1)
                file.seek(offset)

                # チャンクを読み込み、ハッシュオブジェクトを更新する
                chunk = file.read(chunk_size)
                hash_obj.update(chunk)

        # ハッシュの16進数表現を返す
        return hash_obj.hexdigest()


    def __analyzeMediaInfo(self) -> MediaInfo | None:
        """
        録画ファイルのメディア情報を MediaInfo を使って解析する
        KonomiTV で再生可能なファイルではない場合は None を返す

        Returns:
            MediaInfo | None: 録画ファイルのメディア情報 (KonomiTV で再生可能なファイルではない場合は None)
        """

        # libmediainfo のパス (Linux のみ指定が必要、Windows では Wheel に含まれているため不要)
        if GetPlatformEnvironment() == 'Windows':
            libmediainfo_path = None
        else:
            libmediainfo_path = str(LIBRARY_DIR / 'Library/libmediainfo.so.0')

        # 録画ファイルのメディア情報を取得する
        try:
            media_info = cast(MediaInfo, MediaInfo.parse(str(self.recorded_file_path), library_file=libmediainfo_path))
        except Exception as ex:
            Logging.warning(f'{self.recorded_file_path}: Failed to parse media info.')
            Logging.warning(ex)
            return None

        # 最低限 KonomiTV で再生可能なファイルであるかのバリデーションを行う
        ## この処理だけでエラーが発生する (=参照しているキーが MediaInfo から提供されていない) 場合、
        ## 基本的に KonomiTV で再生可能なファイルではないので None を返す
        try:
            # TS 内に含まれる各トラックの情報を取得する
            for track in media_info.tracks:

                # 全般 (TS コンテナの情報)
                if track.track_type == 'General':
                    # MPEG-TS コンテナではない (当面 MPEG-TS のみ対応)
                    ## BDAV も MPEG-TS だが、TS パケット長が 192 byte で ariblib でパースできないため現状非対応
                    if track.format != 'MPEG-TS':
                        Logging.warning(f'{self.recorded_file_path}: {track.format} is not supported.')
                        return None
                    # 映像 or 音声ストリームが存在しない
                    if track.count_of_video_streams == 0 and track.count_of_audio_streams == 0:
                        Logging.warning(f'{self.recorded_file_path}: Video or audio stream is missing.')
                        return None
                    # 長さが取得できない
                    if hasattr(track, 'duration') is False or track.duration is None:
                        Logging.warning(f'{self.recorded_file_path}: Duration is missing.')
                        return None

                # 映像ストリーム
                elif track.track_type == 'Video':
                    # スクランブルが解除されていない
                    if track.encryption == 'Encrypted':
                        Logging.warning(f'{self.recorded_file_path}: Video stream is encrypted.')
                        return None

                # 音声ストリーム
                elif track.track_type == 'Audio':
                    # スクランブルが解除されていない
                    if track.encryption == 'Encrypted':
                        Logging.warning(f'{self.recorded_file_path}: Audio stream is encrypted.')
                        return None

        except Exception as ex:
            Logging.warning(f'{self.recorded_file_path}: Failed to validate media info.')
            Logging.warning(ex)
            return None

        return media_info


if __name__ == '__main__':
    # デバッグ用: 録画ファイルのパスを引数に取り、そのファイルのメタデータを解析する
    # Usage: pipenv run python -m app.metadata.MetadataAnalyzer /path/to/recorded_file.ts
    def main(recorded_file_path: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True)):
        metadata_analyzer = MetadataAnalyzer(recorded_file_path)
        results = metadata_analyzer.analyze()
        if results:
            for result in results:
                if result is not None:
                    pprint(dict(result))
        else:
            typer.echo('Not a KonomiTV playable TS file.')
    typer.run(main)
