
import hashlib
import typer
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from pymediainfo import MediaInfo
from rich import print
from typing import cast, Literal
from zoneinfo import ZoneInfo

from app import logging
from app import schemas
from app.config import Config, LoadConfig
from app.constants import LIBRARY_DIR
from app.metadata.TSInfoAnalyzer import TSInfoAnalyzer
from app.utils import GetPlatformEnvironment
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


    def analyze(self) -> schemas.RecordedProgram | None:
        """
        録画ファイル内のメタデータを解析する

        Returns:
            schemas.RecordedProgram | None: 録画番組情報（中に録画ファイル情報・チャンネル情報が含まれる）を表すモデル
                (KonomiTV で再生可能なファイルではない場合は None が返される)
        """

        # もし Config() の実行時に AssertionError が発生した場合は、LoadConfig() を実行してサーバー設定データをロードする
        ## 通常ならこの関数を ProcessPoolExecutor で実行した場合もサーバー設定データはロード状態になっているはずだが、
        ## 自動リロードモード時のみなぜかグローバル変数がマルチプロセスに引き継がれないため、明示的にロードさせる必要がある
        try:
            Config()
        except AssertionError:
            # バリデーションは既にサーバー起動時に行われているためスキップする
            LoadConfig(bypass_validation=True)

        # 必要な情報を一旦変数として保持
        recording_start_time: datetime | None = None
        recording_end_time: datetime | None = None
        duration: float | None = None
        container_format: Literal['MPEG-TS'] | None = None
        video_codec: Literal['MPEG-2', 'H.264', 'H.265'] | None = None
        video_codec_profile: Literal['High', 'High 10', 'Main', 'Main 10', 'Baseline'] | None = None
        video_scan_type: Literal['Interlaced', 'Progressive'] | None = None
        video_frame_rate: float | None = None
        video_resolution_width: int | None = None
        video_resolution_height: int | None = None
        primary_audio_codec: Literal['AAC-LC'] | None = None
        primary_audio_channel: Literal['Monaural', 'Stereo', '5.1ch'] | None = None
        primary_audio_sampling_rate: int | None = None
        secondary_audio_codec: Literal['AAC-LC'] | None = None
        secondary_audio_channel: Literal['Monaural', 'Stereo', '5.1ch'] | None = None
        secondary_audio_sampling_rate: int | None = None

        # 録画ファイルのハッシュを計算
        try:
            file_hash = self.calculateTSFileHash()
        except ValueError:
            logging.warning(f'{self.recorded_file_path}: File size is too small. ignored.')
            return None

        # MediaInfo から録画ファイルのメディア情報を取得
        ## 取得に失敗した場合は KonomiTV で再生可能なファイルではないと判断し、None を返す
        ## TODO: サブチャンネルの 480p 番組で誤って 1080p や音声多重放送と判断されることがある件の修正が必要
        media_info = self.__analyzeMediaInfo()
        if media_info is None:
            return None
        logging.debug_simple(f'{self.recorded_file_path}: MediaInfo analysis completed.')

        # メディア情報から録画ファイルのメタデータを取得
        is_video_track_read = False
        is_primary_audio_track_read = False
        is_secondary_audio_track_read = False
        for track in media_info.tracks:

            # 全般（コンテナ情報）
            if track.track_type == 'General':
                duration = float(track.duration) / 1000  # ミリ秒を秒に変換
                # 今のところ MPEG-TS 固定
                if track.format == 'MPEG-TS':
                    container_format = 'MPEG-TS'
                else:
                    # MPEG-TS 以外のコンテナは KonomiTV で再生できない
                    continue
                if hasattr(track, 'start_time') and track.start_time is not None:
                    # 録画開始時刻と録画終了時刻を算出
                    ## 録画開始時刻は MediaInfo から "start_time" として取得できる (ただし小数点以下は省略されている)
                    ## "start_time" は "UTC 2023-06-26 23:59:52" のフォーマットになっているが、実際には JST の時刻が返される
                    ## ちゃんと JST のタイムゾーンが指定された datetime として扱うためには、datetime.fromisoformat() でパースする必要がある
                    ## 一度 ISO8601 に変換してからパースする
                    start_time_iso8601 = str(track.start_time).replace('UTC ', '').replace(' ', 'T') + '+09:00'
                    recording_start_time = datetime.fromisoformat(start_time_iso8601)
                    ## duration は小数点以下も含めた値が取得できるので、録画開始時刻を duration のうち小数点以下の部分を2で割った値だけ削る
                    ## これでかなり正確な録画開始時刻が算出できる
                    duration_miliseconds = (duration * 1000) % 1000
                    recording_start_time = recording_start_time - timedelta(milliseconds=duration_miliseconds / 2)
                    ## 録画終了時刻は MediaInfo から "end_time" として取得できるが、値が不正確なので、録画開始時刻から録画時間を足したものを使用する
                    recording_end_time = recording_start_time + timedelta(seconds=duration)

            # 映像
            elif track.track_type == 'Video' and is_video_track_read is False:
                # 長さが取得できない映像トラックは基本的に不正なため無視する
                # 録画データの一部分のみに主映像と異なる映像トラックが含まれている場合に発生する可能性がある (基本ないはずだが…)
                if hasattr(track, 'duration') is False or track.duration is None:
                    continue
                if track.format == 'MPEG Video':
                    video_codec = 'MPEG-2'
                elif track.format == 'AVC':
                    video_codec = 'H.264'
                elif track.format == 'HEVC':
                    video_codec = 'H.265'
                else:
                    # MPEG-2, H.264, H.265 以外のフォーマットは KonomiTV で再生できない
                    continue
                # format_profile は Main@High や High@L5 など @ 区切りで Level や Tier などが付与されている場合があるので、それらを除去する
                video_codec_profile = cast(Literal['High', 'High 10', 'Main', 'Main 10', 'Baseline'], track.format_profile.split('@')[0])
                # scan_type は現在一般的なプログレッシブ映像では属性自体が存在しないことが多いので、存在しない場合はプログレッシブとして扱う
                if hasattr(track, 'scan_type') and track.scan_type == 'Interlaced':
                    video_scan_type = 'Interlaced'
                else:
                    video_scan_type = 'Progressive'
                video_frame_rate = float(track.frame_rate)
                video_resolution_width = int(track.width)
                video_resolution_height = int(track.height)
                is_video_track_read = True

            # 主音声
            elif track.track_type == 'Audio' and is_primary_audio_track_read is False:
                # 長さが取得できない音声トラックは基本的に不正なため無視する
                # 録画マージンに音声多重放送が含まれているなど、録画データの一部分のみに副音声トラックが含まれている場合に発生する
                if hasattr(track, 'duration') is False or track.duration is None:
                    continue
                # 長さが取得できるが、全体の長さの 80% 以下の場合は不正なトラックと判断する
                assert duration is not None
                if float(track.duration) / 1000 < duration * 0.8:
                    continue
                if track.format == 'AAC' and hasattr(track, 'format_additionalfeatures') and track.format_additionalfeatures == 'LC':
                    primary_audio_codec = 'AAC-LC'
                else:
                    # AAC-LC 以外のフォーマットは KonomiTV で再生できない
                    continue
                if int(track.channel_s) == 1:
                    primary_audio_channel = 'Monaural'
                elif int(track.channel_s) == 2:
                    # デュアルモノも Stereo として判定される可能性がある (別途 RecordedProgram の primary_audio_type で判定すべき)
                    primary_audio_channel = 'Stereo'
                elif int(track.channel_s) == 6:
                    primary_audio_channel = '5.1ch'
                else:
                    # 1ch, 2ch, 5.1ch 以外の音声チャンネル数は KonomiTV で再生できない
                    continue
                primary_audio_sampling_rate = int(track.sampling_rate)
                is_primary_audio_track_read = True

            # 副音声（存在する場合）
            elif track.track_type == 'Audio' and is_secondary_audio_track_read is False:
                # 長さが取得できない音声トラックは基本的に不正なため無視する
                # 録画マージンに音声多重放送が含まれているなど、録画データの一部分のみに副音声トラックが含まれている場合に発生する
                if hasattr(track, 'duration') is False or track.duration is None:
                    continue
                # 長さが取得できるが、全体の長さの 80% 以下の場合は不正なトラックと判断する
                assert duration is not None
                if float(track.duration) / 1000 < duration * 0.8:
                    continue
                if track.format == 'AAC' and hasattr(track, 'format_additionalfeatures') and track.format_additionalfeatures == 'LC':
                    secondary_audio_codec = 'AAC-LC'
                else:
                    # AAC-LC 以外のフォーマットは当面 KonomiTV で再生できない
                    continue
                if int(track.channel_s) == 1:
                    secondary_audio_channel = 'Monaural'
                elif int(track.channel_s) == 2:
                    # デュアルモノも Stereo として判定される可能性がある (別途 RecordedProgram の secondary_audio_type で判定すべき)
                    secondary_audio_channel = 'Stereo'
                elif int(track.channel_s) == 6:
                    secondary_audio_channel = '5.1ch'
                else:
                    # 1ch, 2ch, 5.1ch 以外の音声チャンネル数は KonomiTV で再生できない
                    continue
                secondary_audio_sampling_rate = int(track.sampling_rate)
                is_secondary_audio_track_read = True

        # 最低でも映像トラックと主音声トラックが含まれている必要がある
        # 映像か主音声、あるいは両方のトラックが含まれていない場合は None を返す
        if is_video_track_read is False or is_primary_audio_track_read is False:
            logging.warning(f'{self.recorded_file_path}: Video or primary audio track is missing or invalid. ignored.')
            return None

        # 必要な情報が全て揃っていることを保証
        assert duration is not None, 'duration not found.'
        assert container_format is not None, 'container_format not found.'
        assert video_codec is not None, 'video_codec not found.'
        assert video_codec_profile is not None, 'video_codec_profile not found.'
        assert video_scan_type is not None, 'video_scan_type not found.'
        assert video_frame_rate is not None, 'video_frame_rate not found.'
        assert video_resolution_width is not None, 'video_resolution_width not found.'
        assert video_resolution_height is not None, 'video_resolution_height not found.'
        assert primary_audio_codec is not None, 'primary_audio_codec not found.'
        assert primary_audio_channel is not None, 'primary_audio_channel not found.'
        assert primary_audio_sampling_rate is not None, 'primary_audio_sampling_rate not found.'

        ## 現状 ariblib は先頭が sync_byte でない or 途中で同期が壊れる (破損した TS パケットが存在する) TS ファイルを想定していないため、
        ## ariblib に入力する録画ファイルは必ず正常な TS ファイルである必要がある
        ## ファイルの末尾の TS パケットだけ破損してるだけなら再生できるのでファイルサイズはチェックせず、ファイルの先頭が sync_byte であるかだけチェックする
        ## ファイルの先頭1バイトだけを読み込んで sync_byte をチェックする
        with self.recorded_file_path.open('rb') as f:
            if container_format == 'MPEG-TS' and f.read(1)[0] != 0x47:
                logging.warning(f'{self.recorded_file_path}: sync_byte is missing. ignored.')
                return None

        # 録画ファイル情報を表すモデルを作成
        stat_info = self.recorded_file_path.stat()
        recorded_video = schemas.RecordedVideo(
            status = 'Recorded',  # この時点では録画済みとしておく
            file_path = str(self.recorded_file_path),
            file_hash = file_hash,
            file_size = stat_info.st_size,
            file_created_at = datetime.fromtimestamp(stat_info.st_ctime, tz=ZoneInfo('Asia/Tokyo')),
            file_modified_at = datetime.fromtimestamp(stat_info.st_mtime, tz=ZoneInfo('Asia/Tokyo')),
            recording_start_time = recording_start_time,
            recording_end_time = recording_end_time,
            duration = duration,
            container_format = container_format,
            video_codec = video_codec,
            video_codec_profile = video_codec_profile,
            video_scan_type = video_scan_type,
            video_frame_rate = video_frame_rate,
            video_resolution_width = video_resolution_width,
            video_resolution_height = video_resolution_height,
            primary_audio_codec = primary_audio_codec,
            primary_audio_channel = primary_audio_channel,
            primary_audio_sampling_rate = primary_audio_sampling_rate,
            secondary_audio_codec = secondary_audio_codec,
            secondary_audio_channel = secondary_audio_channel,
            secondary_audio_sampling_rate = secondary_audio_sampling_rate,
            # 必須フィールドのため作成日時・更新日時は適当に現在時刻を入れている
            # この値は参照されず、DB の値は別途自動生成される
            created_at = datetime.now(tz=ZoneInfo('Asia/Tokyo')),
            updated_at = datetime.now(tz=ZoneInfo('Asia/Tokyo')),
        )

        # MPEG-TS 形式のみ、TS ファイルに含まれる番組情報・チャンネル情報を解析する
        recorded_program = None
        if container_format == 'MPEG-TS':
            recorded_program = TSInfoAnalyzer(recorded_video).analyze()
            logging.debug_simple(f'{self.recorded_file_path}: MPEG-TS SDT/EIT analysis completed.')

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
            recorded_program = schemas.RecordedProgram(
                recorded_video = recorded_video,
                title = title,
                start_time = start_time,
                end_time = start_time + timedelta(seconds=recorded_video.duration),
                duration = recorded_video.duration,
                # 必須フィールドのため作成日時・更新日時は適当に現在時刻を入れている
                # この値は参照されず、DB の値は別途自動生成される
                created_at = datetime.now(tz=ZoneInfo('Asia/Tokyo')),
                updated_at = datetime.now(tz=ZoneInfo('Asia/Tokyo')),
            )

        return recorded_program


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
            logging.warning(f'{self.recorded_file_path}: Failed to parse media info.')
            logging.warning(ex)
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
                    ## "BDAV" も MPEG-TS だが、TS パケット長が 192 byte で ariblib でパースできないため現状非対応
                    if track.format != 'MPEG-TS':
                        logging.warning(f'{self.recorded_file_path}: {track.format} is not supported.')
                        return None
                    # 映像 or 音声ストリームが存在しない
                    if track.count_of_video_streams == 0 and track.count_of_audio_streams == 0:
                        logging.warning(f'{self.recorded_file_path}: Video or audio stream is missing.')
                        return None
                    # 長さが取得できない
                    if hasattr(track, 'duration') is False or track.duration is None:
                        logging.warning(f'{self.recorded_file_path}: Duration is missing.')
                        return None

                # 映像ストリーム
                elif track.track_type == 'Video':
                    # スクランブルが解除されていない
                    if track.encryption == 'Encrypted':
                        logging.warning(f'{self.recorded_file_path}: Video stream is encrypted.')
                        return None
                    # MPEG-2, H.264, H.265 以外のフォーマットは KonomiTV で再生できない
                    if track.format not in ['MPEG Video', 'AVC', 'HEVC']:
                        logging.warning(f'{self.recorded_file_path}: {track.format} is not supported.')
                        return None

                # 音声ストリーム
                elif track.track_type == 'Audio':
                    # スクランブルが解除されていない
                    if track.encryption == 'Encrypted':
                        logging.warning(f'{self.recorded_file_path}: Audio stream is encrypted.')
                        return None
                    # AAC-LC 以外のフォーマットは KonomiTV で再生できない
                    if track.format not in ['AAC']:
                        logging.warning(f'{self.recorded_file_path}: {track.format} is not supported.')
                        return None
                    # 1ch, 2ch, 5.1ch 以外の音声チャンネル数は KonomiTV で再生できない
                    if int(track.channel_s) not in [1, 2, 6]:
                        logging.warning(f'{self.recorded_file_path}: {track.channel_s} channels are not supported.')
                        return None

        except Exception as ex:
            logging.warning(f'{self.recorded_file_path}: Failed to validate media info.')
            logging.warning(ex)
            return None

        return media_info


if __name__ == '__main__':
    # デバッグ用: 録画ファイルのパスを引数に取り、そのファイルのメタデータを解析する
    # Usage: poetry run python -m app.metadata.MetadataAnalyzer /path/to/recorded_file.ts
    def main(recorded_file_path: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True)):
        LoadConfig(bypass_validation=True)  # 一度実行しておかないと設定値を参照できない
        metadata_analyzer = MetadataAnalyzer(recorded_file_path)
        result = metadata_analyzer.analyze()
        if result is not None:
            print(result)
        else:
            print('Not a KonomiTV playable TS file.')
    typer.run(main)
