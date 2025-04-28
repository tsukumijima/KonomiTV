
import hashlib
import io
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, cast
from zoneinfo import ZoneInfo

import typer
from biim.mpeg2ts import ts
from pymediainfo import MediaInfo
from rich import print

from app import logging, schemas
from app.config import Config, LoadConfig
from app.constants import LIBRARY_DIR
from app.metadata.TSInfoAnalyzer import TSInfoAnalyzer
from app.utils import ClosestMultiple, GetPlatformEnvironment
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
        このメソッドは同期的なため、非同期メソッドから実行する際は asyncio.to_thread() または ProcessPoolExecutor で実行すること

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
        container_format: Literal['MPEG-TS', 'MPEG-4'] | None = None
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

        # MediaInfo から録画ファイルのメディア情報を取得
        ## 取得に失敗した場合は KonomiTV で再生可能なファイルではないと判断し、None を返す
        result = self.analyzeMediaInfo()
        if result is None:
            return None
        full_media_info, sample_media_info, end_ts_offset = result
        logging.debug_simple(f'{self.recorded_file_path}: MediaInfo analysis completed.')

        # メディア情報から録画ファイルのメタデータを取得
        ## 全体解析: コンテナ情報、録画時間などを取得
        for track in full_media_info.tracks:

            # 全般（コンテナ情報）
            if track.track_type == 'General':
                # この時点で duration は確実に取得されているはず
                duration = float(track.duration) / 1000  # ミリ秒を秒に変換
                if track.format in ('MPEG-TS', 'MPEG-4'):
                    container_format = track.format
                else:
                    # 上記以外のコンテナ形式は KonomiTV で再生できない
                    continue
                # 情報が存在する場合のみ、録画開始時刻と録画終了時刻を算出
                # MPEG-TS 内に TOT が含まれていない場合は録画開始時刻・録画終了時刻は算出できない
                if hasattr(track, 'start_time') and track.start_time is not None:
                    ## 録画開始時刻は MediaInfo から "start_time" として取得できる (ただし小数点以下は省略されている)
                    ## "start_time" は "UTC 2023-06-26 23:59:52" のフォーマットになっているが、実際には JST の時刻が返される
                    ## ちゃんと JST のタイムゾーンが指定された datetime として扱うためには、datetime.fromisoformat() でパースする必要がある
                    ## 一度 ISO8601 に変換してからパースする
                    raw_time = str(track.start_time)
                    # 正規表現で日付と時刻（例: 2024-09-13 と 01:05:00）を抽出する
                    match = re.search(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})', raw_time)
                    if match is not None:
                        # 抽出した値を使用して ISO 8601 形式に整形する
                        start_time_iso8601 = f'{match.group(1)}T{match.group(2)}+09:00'
                    else:
                        # マッチしなかった場合は元の方法で変換を試みる
                        start_time_iso8601 = raw_time.replace('UTC ', '').replace(' ', 'T').replace('TUTC', '') + '+09:00'
                    recording_start_time = datetime.fromisoformat(start_time_iso8601)
                    ## duration は小数点以下も含めた値が取得できるので、録画開始時刻を duration のうち小数点以下の部分を2で割った値だけ削る
                    ## これでかなり正確な録画開始時刻が算出できる
                    duration_miliseconds = (duration * 1000) % 1000
                    recording_start_time = recording_start_time - timedelta(milliseconds=duration_miliseconds / 2)
                    ## 録画終了時刻は MediaInfo から "end_time" として取得できるが、値が不正確なので、録画開始時刻から録画時間を足したものを使用する
                    recording_end_time = recording_start_time + timedelta(seconds=duration)

        ## 部分解析: 映像・音声情報を取得
        is_video_track_read = False
        is_primary_audio_track_read = False
        is_secondary_audio_track_read = False
        for track in sample_media_info.tracks:

            # 映像
            if track.track_type == 'Video' and is_video_track_read is False:
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
                    # MPEG-2, H.264, H.265 以外のコーデックは KonomiTV で再生できない
                    continue
                # format_profile は Main@High や High@L5 など @ 区切りで Level や Tier などが付与されている場合があるので、それらを除去する
                video_codec_profile = cast(Literal['High', 'High 10', 'Main', 'Main 10', 'Baseline'], track.format_profile.split('@')[0])
                # scan_type は現在一般的なプログレッシブ映像では属性自体が存在しないことが多いので、存在しない場合はプログレッシブとして扱う
                if hasattr(track, 'scan_type') and track.scan_type == 'Interlaced':
                    video_scan_type = 'Interlaced'
                else:
                    video_scan_type = 'Progressive'
                if hasattr(track, 'frame_rate') is False or track.frame_rate is None:
                    logging.warning(f'{self.recorded_file_path}: Frame rate information is missing.')
                    continue
                video_frame_rate = float(track.frame_rate)
                if hasattr(track, 'width') is False or track.width is None:
                    logging.warning(f'{self.recorded_file_path}: Width information is missing.')
                    continue
                video_resolution_width = int(track.width)
                if hasattr(track, 'height') is False or track.height is None:
                    logging.warning(f'{self.recorded_file_path}: Height information is missing.')
                    continue
                video_resolution_height = int(track.height)
                is_video_track_read = True

            # 主音声
            elif track.track_type == 'Audio' and is_primary_audio_track_read is False:
                # 長さが取得できない音声トラックは基本的に不正なため無視する
                # 録画マージンに音声多重放送が含まれているなど、録画データの一部分のみに副音声トラックが含まれている場合に発生する
                if hasattr(track, 'duration') is False or track.duration is None:
                    continue
                if track.format == 'AAC' and hasattr(track, 'format_additionalfeatures') and track.format_additionalfeatures == 'LC':
                    primary_audio_codec = 'AAC-LC'
                else:
                    # AAC-LC 以外のコーデックは KonomiTV で再生できない
                    continue
                # この時点で channel_s は必ず存在するはず
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
                if hasattr(track, 'sampling_rate') is False or track.sampling_rate is None:
                    logging.warning(f'{self.recorded_file_path}: Sampling rate information is missing.')
                    continue
                primary_audio_sampling_rate = int(track.sampling_rate)
                is_primary_audio_track_read = True

            # 副音声（存在する場合）
            elif track.track_type == 'Audio' and is_secondary_audio_track_read is False:
                # 長さが取得できない音声トラックは基本的に不正なため無視する
                # 録画マージンに音声多重放送が含まれているなど、録画データの一部分のみに副音声トラックが含まれている場合に発生する
                if hasattr(track, 'duration') is False or track.duration is None:
                    continue
                if track.format == 'AAC' and hasattr(track, 'format_additionalfeatures') and track.format_additionalfeatures == 'LC':
                    secondary_audio_codec = 'AAC-LC'
                else:
                    # AAC-LC 以外のフォーマットは当面 KonomiTV で再生できない
                    continue
                # この時点で channel_s は必ず存在するはず
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
                if hasattr(track, 'sampling_rate') is False or track.sampling_rate is None:
                    logging.warning(f'{self.recorded_file_path}: Sampling rate information is missing.')
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
        if container_format == 'MPEG-TS':
            with self.recorded_file_path.open('rb') as f:
                if f.read(1)[0] != 0x47:
                    logging.warning(f'{self.recorded_file_path}: sync_byte is missing. ignored.')
                    return None

        # ファイルハッシュを計算
        try:
            file_hash = self.calculateFileHash()
        except ValueError:
            logging.warning(f'{self.recorded_file_path}: File size is too small. ignored.')
            return None

        # 録画ファイル情報を表すモデルを作成
        now = datetime.now(tz=ZoneInfo('Asia/Tokyo'))
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
            created_at = now,
            updated_at = now,
        )

        recorded_program = None
        if container_format == 'MPEG-TS':
            # TS ファイルに含まれる番組情報・チャンネル情報を解析する
            recorded_program = TSInfoAnalyzer(recorded_video, end_ts_offset).analyze()  # 取得失敗時は None が返る
            if recorded_program is not None:
                logging.debug_simple(f'{self.recorded_file_path}: MPEG-TS SDT/EIT analysis completed.')
            else:
                # 取得失敗時、最終更新日時が現在時刻から30秒以内ならまだ録画中の可能性が高いので、None を返し DB には保存しない
                if (now - recorded_video.file_modified_at).total_seconds() < 30:
                    logging.warning(f'{self.recorded_file_path}: MPEG-TS SDT/EIT analysis failed. (still recording?)')
                    return None
        else:
            # 何らかのメタ情報から番組情報・チャンネル情報を解析する
            analyzer = TSInfoAnalyzer(recorded_video)
            recorded_program = analyzer.analyze()  # 取得失敗時は None が返る
            if recorded_program is not None:
                logging.debug_simple(f'{self.recorded_file_path}: {container_format} Service/Event analysis completed.')
                # 録画開始時刻と録画終了時刻も解析する
                recording_time = analyzer.analyzeRecordingTime()
                if recording_time is not None:
                    recorded_video.recording_start_time = recording_time[0]
                    recorded_video.recording_end_time = recording_time[1]

        # MPEG-TS 形式ではなくメタ情報も存在しなければ番組情報は取得できないので、ファイル名などから最低限の情報を設定する
        # MPEG-TS 形式だが TS ファイルからチャンネル情報・番組情報を取得できなかった場合も同様
        ## 他の値は RecordedProgram モデルで設定されたデフォルト値が自動的に入るので、タイトルと日時だけここで設定する
        if recorded_program is None:
            ## 録画開始時刻を取得できている場合は、それを番組開始時刻として使用する
            if recorded_video.recording_start_time is not None:
                recording_start_time = recorded_video.recording_start_time
            ## 録画開始時刻を取得できていない場合、ファイルの更新日時 - 動画長を番組開始時刻として使用する
            ## 作成日時だとコピー/移動した際にコピーが完了した日時に変更されることがあるため、更新日時ベースの方が適切
            ## 変更を加えていない録画 TS ファイルであれば、ファイルの更新日時は録画終了時刻に近い値になるはず
            else:
                recording_start_time = datetime.fromtimestamp(
                    self.recorded_file_path.stat().st_mtime,
                    tz = ZoneInfo('Asia/Tokyo'),
                ) - timedelta(seconds=recorded_video.duration)
            ## 拡張子を除いたファイル名をフォーマットした上でタイトルとして使用する
            title = TSInformation.formatString(self.recorded_file_path.stem)
            recorded_program = schemas.RecordedProgram(
                recorded_video = recorded_video,
                title = title,
                start_time = recording_start_time,
                end_time = recording_start_time + timedelta(seconds=recorded_video.duration),
                duration = recorded_video.duration,
                # 必須フィールドのため作成日時・更新日時は適当に現在時刻を入れている
                # この値は参照されず、DB の値は別途自動生成される
                created_at = datetime.now(tz=ZoneInfo('Asia/Tokyo')),
                updated_at = datetime.now(tz=ZoneInfo('Asia/Tokyo')),
            )

        return recorded_program


    def calculateFileHash(self, chunk_size: int = 1024 * 1024, num_chunks: int = 3) -> str:
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


    def calculateTSFileDuration(self, search_block_size: int = 1024 * 1024) -> tuple[float, int] | None:
        """
        TS ファイル内の最初と最後の有効な PCR タイムスタンプから再生時間（秒）を算出する (written with o3-mini)
        MediaInfo から再生時間を取得できなかった場合のフォールバックとして利用する
        録画ファイルは録画時にスパースファイル（ゼロ埋めされた領域を含む）となる可能性があるため、
        ファイル末尾はゼロ埋め領域を高速に検出し、実際にデータが存在する部分と区別している

        Args:
            search_block_size (int): PCR 抽出時に読み込むブロックサイズ (バイト単位). デフォルト: 1MB

        Returns:
            tuple[float, int] | None: (再生時間（秒）, 有効な TS データの終了位置) のタプル
                （抽出できなかった場合は None を返す）
        """

        try:
            # ファイルサイズを取得
            file_size = self.recorded_file_path.stat().st_size

            with self.recorded_file_path.open('rb') as f:
                # --- 先頭ブロックからの PCR 抽出 ---
                # 基本的にはファイル先頭の最初の TS パケットから PCR を取得する
                f.seek(0)
                head_data = f.read(search_block_size)
                # 先頭ブロックが TS 同期バイト (0x47) で始まっていない場合、1バイトずつ探索して
                # 最初の同期バイトの位置を特定する
                if head_data and head_data[0] != ts.SYNC_BYTE[0]:
                    logging.info('Head data is not aligned; searching for sync byte...')
                    corrected_offset = None
                    for idx in range(len(head_data)):
                        if head_data[idx] == ts.SYNC_BYTE[0]:
                            corrected_offset = idx
                            break
                    if corrected_offset is not None:
                        head_data = head_data[corrected_offset:]
                    else:
                        logging.error('Failed to find sync byte in head data.')
                        return None

                first_timestamp: float | None = None
                for i in range(0, len(head_data), ts.PACKET_SIZE):
                    packet = head_data[i : i + ts.PACKET_SIZE]
                    if len(packet) < ts.PACKET_SIZE:
                        break
                    if packet[0] != ts.SYNC_BYTE[0]:
                        continue
                    pcr_val = ts.pcr(packet)
                    if pcr_val is not None:
                        # PCR 値を ts.HZ (90000Hz) で割り、秒単位に変換する
                        first_timestamp = pcr_val / ts.HZ
                        break

                if first_timestamp is None:
                    logging.error('Failed to extract first PCR timestamp.')
                    return None

                # --- 末尾のゼロ埋め領域の境界をバイナリサーチで検出 ---
                # TS ファイルは録画後にゼロ埋め領域が存在する場合があるため、
                # 正常なデータが存在する最後のオフセット (valid_data_end) を求める
                block_check_size = 4096  # ゼロ埋め判定用の小ブロックサイズ (4KB)
                low = 0
                high = file_size
                zero_boundary = file_size  # もしゼロブロックが見つからなければ有効データはファイル全体とする

                while low <= high:
                    mid = (low + high) // 2
                    f.seek(mid)
                    candidate = f.read(block_check_size)
                    if candidate and all(byte == 0 for byte in candidate):
                        # candidate が全て 0x00 ならば、ゼロ埋め領域の一部と見なし、境界を mid に更新
                        zero_boundary = mid
                        high = mid - 1
                    else:
                        low = mid + 1

                # valid_data_end はゼロ埋めが始まる境界、つまり有効データの終了位置
                valid_data_end = zero_boundary if zero_boundary < file_size else file_size

                # --- 末尾領域から最後の有効な PCR の取得 ---
                # 有効データ領域の終端から search_block_size 分の範囲を読み込み、TS パケット単位で同期を取る
                start_offset = valid_data_end - search_block_size
                if start_offset < 0:
                    start_offset = 0
                # TS パケット境界に合わせるため、start_offset を ts.PACKET_SIZE の倍数に補正
                start_offset = (start_offset // ts.PACKET_SIZE) * ts.PACKET_SIZE
                f.seek(start_offset)
                tail_chunk = f.read(valid_data_end - start_offset)

                # --- TS パケット同期の調整 ---
                # 読み込んだ tail_chunk の先頭が TS 同期バイト (0x47) でない場合、同期位置を調整する
                offset_in_chunk = 0
                if tail_chunk and tail_chunk[0] != ts.SYNC_BYTE[0]:
                    for idx in range(len(tail_chunk)):
                        if tail_chunk[idx] == ts.SYNC_BYTE[0]:
                            offset_in_chunk = idx
                            break

                # --- tail_chunk 内の TS パケットから有効な PCR 値を収集 ---
                valid_pcrs: list[float] = []
                for j in range(offset_in_chunk, len(tail_chunk) - ts.PACKET_SIZE + 1, ts.PACKET_SIZE):
                    packet = tail_chunk[j : j + ts.PACKET_SIZE]
                    if packet[0] != ts.SYNC_BYTE[0]:
                        continue
                    pcr_val = ts.pcr(packet)
                    if pcr_val is not None:
                        valid_pcrs.append(pcr_val / ts.HZ)

                if not valid_pcrs:
                    logging.error('Failed to extract last PCR in tail region.')
                    return None

                last_timestamp = valid_pcrs[-1]

                # --- PCR ラップアラウンドの補正 ---
                # もし末尾の PCR が先頭の PCR より小さい場合は、PCR のラップアラウンドが発生しているとみなし、
                # PCR の最大値に相当する秒数を加算する
                if last_timestamp < first_timestamp:
                    PCR_MAX_SECONDS = ts.PCR_CYCLE / ts.HZ
                    last_timestamp += PCR_MAX_SECONDS

                # --- 再生時間の算出 ---
                # 先頭と末尾の PCR 値から再生時間（秒）を算出する
                duration = last_timestamp - first_timestamp
                logging.debug_simple(f'{self.recorded_file_path}: Duration calculated: {duration} seconds.')

                return (duration, valid_data_end)

        except Exception as ex:
            logging.error('Error in fallback duration calculation:', exc_info=ex)
            return None


    def analyzeMediaInfo(self) -> tuple[MediaInfo, MediaInfo, int | None] | None:
        """
        録画ファイルのメディア情報を MediaInfo を使って解析する
        全体解析と部分解析の2段階で解析を行う
        全体解析では全般情報（コンテナ情報、録画時間など）を、部分解析では映像・音声情報を取得する

        Returns:
            tuple[MediaInfo, MediaInfo, int | None] | None: 全体解析と部分解析の結果、有効な TS データの終了位置のタプル
                (KonomiTV で再生可能なファイルではない場合は None が返される)
        """

        # libmediainfo のパス (Linux のみ指定が必要、Windows では Wheel に含まれているため不要)
        if GetPlatformEnvironment() == 'Windows':
            libmediainfo_path = None
        else:
            libmediainfo_path = str(LIBRARY_DIR / 'Library/libmediainfo.so.0')

        # 全体解析: 録画ファイル全体のメディア情報を取得する
        try:
            full_media_info = cast(MediaInfo, MediaInfo.parse(str(self.recorded_file_path), library_file=libmediainfo_path))
        except Exception as ex:
            logging.warning(f'{self.recorded_file_path}: Failed to parse full media info.', exc_info=ex)
            return None

        # 部分解析: 録画ファイルの30%位置から30秒程度のデータを取得し、メディア情報を解析する
        duration_result: tuple[float, int] | None = None
        try:
            # MPEG-TS 形式の場合のみ実行
            if full_media_info.general_tracks and full_media_info.general_tracks[0].format == 'MPEG-TS':
                # ファイルを開く
                with open(self.recorded_file_path, 'rb') as f:
                    # 25%位置にシーク (TS パケットサイズに合わせて切り出す)
                    file_size = self.recorded_file_path.stat().st_size
                    offset = ClosestMultiple(int(file_size * 0.25), ts.PACKET_SIZE)
                    f.seek(offset)
                    # 30秒程度のデータを読み込む (ビットレートを 18Mbps と仮定)
                    ## サンプルとして MediaInfo に渡すデータが30秒より短いと正確に解析できないことがある
                    sample_size = ClosestMultiple(18 * 1024 * 1024 * 30 // 8, ts.PACKET_SIZE)  # TS パケットサイズに合わせて切り出す
                    sample_data = f.read(sample_size)
                    # サンプルデータが全てゼロ埋めされているかチェック
                    if all(byte == 0 for byte in sample_data):
                        # ゼロ埋め領域の境界を取得するため calculateTSFileDuration を実行
                        duration_result = self.calculateTSFileDuration()
                        if duration_result is None:
                            logging.warning(f'{self.recorded_file_path}: Failed to calculate duration.')
                            return None
                        # ゼロ埋め領域を除いた有効データ範囲から再度サンプルを取得
                        # 有効データ範囲の25%位置にシーク
                        _, end_ts_offset = duration_result
                        offset = ClosestMultiple(int(end_ts_offset * 0.25), ts.PACKET_SIZE)
                        f.seek(offset)
                        # 30秒程度のデータを読み込む (ビットレートを 18Mbps と仮定)
                        sample_size = min(sample_size, end_ts_offset - offset)  # 有効データ範囲を超えないようにする
                        sample_data = f.read(sample_size)
                    # BytesIO オブジェクトを作成
                    sample_io = io.BytesIO(sample_data)
                    # メディア情報を解析
                    ## 重要: バッファサイズを TS パケットサイズの100倍程度に抑えないと、ファイルによっては不正確な結果が返ってくることがある
                    ## なぜバッファサイズ次第で解析結果が変わるのか不可解だが、一回の送信サイズを小さく保った方が不正確な結果を避けられそう…？
                    ## 素直にファイルに書き出してから参照させるのが最も確実だが、比較的容量の大きいファイルをこのためだけに書き込むのは気が引ける
                    sample_media_info = cast(MediaInfo, MediaInfo.parse(sample_io, buffer_size=ts.PACKET_SIZE * 100, library_file=libmediainfo_path))
            else:
                # MPEG-TS 形式でない場合は部分解析はせず、全体解析の結果をそのまま設定
                sample_media_info = full_media_info
        except Exception as ex:
            logging.warning(f'{self.recorded_file_path}: Failed to parse sample media info.', exc_info=ex)
            return None

        # 最低限 KonomiTV で再生可能なファイルであるかのバリデーションを行う
        ## この処理だけでエラーが発生する (=参照しているキーが MediaInfo から提供されていない) 場合、
        ## 基本的に KonomiTV で再生可能なファイルではないので None を返す
        try:
            # TS 内に含まれる各トラックの情報を取得する
            for track in full_media_info.tracks:

                # 全般 (TS コンテナの情報)
                if track.track_type == 'General':
                    # 再生可能なコンテナではない
                    ## "BDAV" も MPEG-TS だが、TS パケット長が 192 byte で ariblib でパースできないため現状非対応
                    if track.format not in ('MPEG-TS', 'MPEG-4'):
                        logging.warning(f'{self.recorded_file_path}: Container format "{track.format}" is not supported.')
                        return None
                    # 映像 or 音声ストリームが存在しない
                    if track.count_of_video_streams == 0 and track.count_of_audio_streams == 0:
                        logging.warning(f'{self.recorded_file_path}: Video or audio stream is missing.')
                        return None
                    # MediaInfo から再生時間が取得できない
                    # 録画中などでファイルアロケーションされており、ファイル後半がゼロ埋めされているケースで発生しやすい
                    if hasattr(track, 'duration') is False or track.duration is None:
                        # MPEG-TS 形式の場合のみ、フォールバックとして自前で長さを算出する
                        if track.format == 'MPEG-TS' and duration_result is None:
                            # まだ calculateTSFileDuration() が実行されていない場合のみここで実行する
                            duration_result = self.calculateTSFileDuration()
                        if duration_result is not None:
                            # 再生時間を算出できた場合は代わりに算出した値を設定する
                            duration, _ = duration_result
                            track.duration = duration * 1000  # ミリ秒に変換
                        else:
                            # 再生時間を算出できなかった (ファイルが破損しているなど)
                            logging.warning(f'{self.recorded_file_path}: Duration is missing.')
                            return None

            # サンプルデータからも同様にバリデーションを行う
            for track in sample_media_info.tracks:

                # 映像ストリーム
                if track.track_type == 'Video':
                    # スクランブルが解除されていない
                    if track.encryption == 'Encrypted':
                        logging.warning(f'{self.recorded_file_path}: Video stream is encrypted.')
                        return None
                    # MPEG-2, H.264, H.265 以外のコーデックは KonomiTV で再生できない
                    if track.format not in ['MPEG Video', 'AVC', 'HEVC']:
                        logging.warning(f'{self.recorded_file_path}: Video codec "{track.format}" is not supported.')
                        return None

                # 音声ストリーム
                elif track.track_type == 'Audio':
                    # スクランブルが解除されていない
                    if track.encryption == 'Encrypted':
                        logging.warning(f'{self.recorded_file_path}: Audio stream is encrypted.')
                        return None
                    # コーデックが "MPEG Audio" (=MP3) または "0" になっている場合は誤解析の可能性が高いので、やむを得ず AAC-LC ということにする
                    # 現実的に放送波で MP3 が流れてくることはないし、エンコード後でも MP3 になることはほとんどないはず
                    ## 稀に発生するが条件が本当に謎… MediaInfo の中身はブラックボックスなのでかなり不可解だが MediaInfo だけでは現状どうしようもない…
                    if track.format == 'MPEG Audio' or str(track.format) == '0':
                        track.format = 'AAC'
                        track.format_additionalfeatures = 'LC'
                        track.sampling_rate = 48000  # サンプリングレートは 48000Hz に固定 (放送波は通常 48000Hz でエンコードされる)
                        if track.format == 'MPEG Audio':
                            logging.warning(f'{self.recorded_file_path}: MPEG Audio is detected. Assuming AAC-LC. (Is MediaInfo misinterpreting the audio?)')
                        elif str(track.format) == '0':
                            logging.warning(f'{self.recorded_file_path}: Unknown audio codec "0" is detected. Assuming AAC-LC. (Is MediaInfo misinterpreting the audio?)')
                    # AAC-LC 以外のコーデックは KonomiTV で再生できない
                    if track.format not in ['AAC']:
                        logging.warning(f'{self.recorded_file_path}: Audio codec "{track.format}" is not supported.')
                        return None
                    # チャンネル数情報が存在しない
                    # コーデック情報が取得できるのにチャンネル数情報が取得できないことはあまり考えられないので、誤解析と判断し channel_s を 2 に固定する
                    if hasattr(track, 'channel_s') is False or track.channel_s is None:
                        logging.warning(f'{self.recorded_file_path}: Channel count information is missing. (Is MediaInfo misinterpreting the audio?)')
                        track.channel_s = 2
                    # 1ch, 2ch, 5.1ch 以外の音声チャンネル数は KonomiTV で再生できないが、
                    # 実際に上記以外の音声チャンネル数でエンコードされることはまずない (少なくとも放送仕様上は発生し得ない) ため、
                    # 22 とか 8 とか突拍子ない値が返ってきた場合は何らかの理由で MediaInfo が誤解析してしまっている可能性の方が高い
                    # 実際は普通のステレオ音声だと考えられるため、エラーにはせず、channel_s の値を 2 に固定する
                    if int(track.channel_s) not in [1, 2, 6]:
                        logging.warning(f'{self.recorded_file_path}: {track.channel_s} channels detected. (Is MediaInfo misinterpreting the audio?)')
                        track.channel_s = 2

        except Exception as ex:
            logging.warning(f'{self.recorded_file_path}: Failed to validate media info.', exc_info=ex)
            return None

        # 解析処理中に calculateTSFileDuration() を実行している場合は、有効な TS データの終了位置も一緒に返す
        ## calculateTSFileDuration() が実行されている時点で、当該録画ファイルの後半部分にゼロ埋めデータが存在することを示す
        ## この値は TSInfoAnalyzer で番組情報を解析する際に利用される
        if duration_result is not None:
            _, end_ts_offset = duration_result
            return full_media_info, sample_media_info, end_ts_offset
        else:
            return full_media_info, sample_media_info, None


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
            logging.error('Not a KonomiTV playable TS file.')
    typer.run(main)
