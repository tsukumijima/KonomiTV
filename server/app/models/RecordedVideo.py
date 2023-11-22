
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import asyncio
import concurrent.futures
import gc
import os
import json
import time
import traceback
from datetime import datetime
from pathlib import Path
from tortoise import connections
from tortoise import exceptions
from tortoise import fields
from tortoise import models
from tortoise import Tortoise
from tortoise import transactions
from typing import Literal

from app.config import Config
from app.config import LoadConfig
from app.constants import DATABASE_CONFIG
from app.models.Channel import Channel
from app.models.RecordedProgram import RecordedProgram
from app.schemas import CMSection
from app.utils import Logging


class RecordedVideo(models.Model):

    # データベース上のテーブル名
    class Meta:  # type: ignore
        table: str = 'recorded_videos'

    # テーブル設計は Notion を参照のこと
    id: int = fields.IntField(pk=True)  # type: ignore
    recorded_program: fields.OneToOneRelation[RecordedProgram] = \
        fields.OneToOneField('models.RecordedProgram', related_name='recorded_video', on_delete=fields.CASCADE)
    recorded_program_id: int
    file_path: str = fields.TextField()  # type: ignore
    file_hash: str = fields.TextField()  # type: ignore
    file_size: int = fields.IntField()  # type: ignore
    recording_start_time: datetime | None = fields.DatetimeField(null=True)  # type: ignore
    recording_end_time: datetime | None = fields.DatetimeField(null=True)  # type: ignore
    duration: float = fields.FloatField()  # type: ignore
    # 万が一将来他のコンテナ形式をサポートすることになった時のために一応定義しているが、当面の間 MPEG-TS 以外はサポートしない
    container_format: Literal['MPEG-TS'] = fields.CharField(255)  # type: ignore
    video_codec: Literal['MPEG-2', 'H.264', 'H.265'] = fields.CharField(255)  # type: ignore
    # プロファイルは他にも多くあるが、現実的に使われそうなものだけを列挙
    video_codec_profile: Literal['High', 'High 10', 'Main', 'Main 10', 'Baseline'] = fields.CharField(255)  # type: ignore
    video_scan_type: Literal['Interlaced', 'Progressive'] = fields.CharField(255)  # type: ignore
    video_frame_rate: float = fields.FloatField()  # type: ignore
    video_resolution_width: int = fields.IntField()  # type: ignore
    video_resolution_height: int = fields.IntField()  # type: ignore
    primary_audio_codec: Literal['AAC-LC'] = fields.CharField(255)  # type: ignore
    primary_audio_channel: Literal['Monaural', 'Stereo', '5.1ch'] = fields.CharField(255)  # type: ignore
    primary_audio_sampling_rate: int = fields.IntField()  # type: ignore
    secondary_audio_codec: Literal['AAC-LC'] | None = fields.CharField(255, null=True)  # type: ignore
    secondary_audio_channel: Literal['Monaural', 'Stereo', '5.1ch'] | None = fields.CharField(255, null=True)  # type: ignore
    secondary_audio_sampling_rate: int | None = fields.IntField(null=True)  # type: ignore
    cm_sections: list[CMSection] = \
        fields.JSONField(default=[], encoder=lambda x: json.dumps(x, ensure_ascii=False))  # type: ignore


    @classmethod
    async def update(cls) -> None:
        """
        録画ファイルのメタデータを更新する
        ProcessPoolExecutor を使い、複数のディレクトリを並列に処理する
        """

        timestamp = time.time()
        Logging.info('Recorded videos updating...')

        # サーバー設定から録画フォルダリストを取得
        recorded_folders = Config().video.recorded_folders

        # もし録画フォルダリストが空だったら、RecordedProgram をすべて削除して終了
        ## RecordedProgram に紐づく RecordedVideo も CASCADE 制約で同時に削除される
        ## この処理により、録画フォルダリストが空の状態でサーバーを起動した場合、すべての録画番組が DB 上から削除される
        if len(recorded_folders) == 0:
            Logging.info('No recorded folders are specified. Delete all recorded videos.')
            await RecordedProgram.all().delete()
            return

        # 動作中のイベントループを取得
        loop = asyncio.get_running_loop()

        # 複数のディレクトリを ProcessPoolExecutor で並列に処理する
        ## with 文で括ることで、with 文を抜けたときに Executor がクリーンアップされるようにする
        ## さもなければプロセスが残り続けてゾンビプロセス化し、メモリリークを引き起こしてしまう
        with concurrent.futures.ProcessPoolExecutor() as executor:
            tasks = [loop.run_in_executor(executor, cls.updateDirectoryForMultiProcess, directory) for directory in recorded_folders]
            tasks = await asyncio.gather(*tasks)

        # スキャンで見つかったすべての録画ファイルのフルパスのリストを取得
        ## このリストに含まれる録画ファイルは基本すべて DB に保存されているはず (エラーが発生する録画ファイルを除く)
        existing_files: list[str] = []
        for task in tasks:
            existing_files.extend(task)

        # トランザクション配下に入れることでパフォーマンスが向上する
        async with transactions.in_transaction():
            # スキャン結果に含まれない録画ファイルが DB に存在する場合は削除する
            ## RecordedProgram に紐づく RecordedVideo も CASCADE 制約で同時に削除される
            ## Channel (is_watchable=False) は他の録画ファイルから参照されている可能性があるため、削除されない
            for recorded_video in await RecordedVideo.all().select_related('recorded_program'):
                if recorded_video.file_path not in existing_files:
                    await recorded_video.recorded_program.delete()
                    Logging.info(f'Delete Recorded: {Path(recorded_video.file_path).name}')

        Logging.info(f'Recorded videos update complete. ({round(time.time() - timestamp, 3)} sec)')


    @classmethod
    async def updateDirectory(cls, directory: Path) -> list[str]:
        """
        指定されたディレクトリ以下の録画ファイルのメタデータを更新する
        ProcessPoolExecutor 内で実行されることを想定している

        Args:
            directory (Path): 録画ファイルが格納されているディレクトリ

        Returns:
            list[str]: スキャンで見つかったすべての録画ファイルのフルパスのリスト
        """

        # 循環参照を避けるために遅延インポート
        from app.metadata.MetadataAnalyzer import MetadataAnalyzer

        # Tortoise ORM を再初期化する前に、既存のコネクションを破棄
        ## これをやっておかないとなぜか正常に初期化できず、DB 操作でフリーズする…
        ## Windows だとこれをやらなくても問題ないが、Linux だと必要 (Tortoise ORM あるいは aiosqlite のマルチプロセス時のバグ？)
        connections.discard('default')

        # マルチプロセス時は既存のコネクションが使えないため、Tortoise ORM を初期化し直す
        # ref: https://tortoise-orm.readthedocs.io/en/latest/setup.html
        await Tortoise.init(config=DATABASE_CONFIG)

        # 録画ファイルの変更を DB に保存するタスクの引数を格納するリスト
        ## リスト内のタスクはスキャン完了後に一括で実行される
        save_args_list: list[tuple[
            RecordedVideo | None,
            RecordedVideo,
            RecordedProgram,
            Channel | None,
        ]] = []

        # 指定されたディレクトリ以下のファイルを再帰的に走査する
        ## シンボリックリンクにより同一ファイルが複数回スキャンされることを防ぐため、followlinks=False に設定している
        ## 本来同期関数の os.walk を非同期関数の中で使うのは望ましくないが (イベントループがブロッキングされるため)、
        ## この関数自体が ProcessPoolExecutor 内でそれぞれ別プロセスで実行されるため問題ない
        existing_files: list[str] = []
        try:
            for dir_path, _, file_names in os.walk(directory, followlinks=False):
                for file_name in file_names:

                    # 録画ファイルのフルパス
                    file_path = Path(dir_path) / file_name

                    # 録画ファイルが確実に存在することを確認する (環境次第で稀に os.walk で見つかるファイルが既に存在しなくなっているケースがある)
                    if file_path.is_file() is False:
                        continue

                    # バリデーション
                    ## ._ から始まるファイルは Mac が勝手に作成するファイルなので無視する
                    if file_path.name.startswith('._'):
                        continue
                    ## 当面 TS ファイルのみを対象とする
                    if file_path.suffix not in ['.ts', '.m2t', '.m2ts', '.mts']:
                        continue
                    ## 最終更新日時が 30 秒以内 (=現在録画中) のファイルを無視する
                    ## 録画中のファイルはメタデータの解析に失敗したり、不正確なメタデータが取得される可能性があるため
                    if (time.time() - file_path.stat().st_mtime) < 30:
                        Logging.warning(f'{file_path}: File is being recorded. ignored.')
                        continue

                    existing_files.append(str(file_path))

                    # 録画ファイルのハッシュを取得
                    ## 高速化のためにあえて asyncio.to_thread() を使っていない
                    ## イベントループは ProcessPoolExecutor 内で実行されているため、他の非同期タスクをブロッキングすることはない
                    try:
                        file_hash = MetadataAnalyzer(file_path).calculateTSFileHash()
                    except ValueError:
                        Logging.warning(f'{file_path}: File size is too small. ignored.')
                        continue

                    # 同一のパスを持つ録画ファイルが DB に存在するか確認する
                    current_recorded_video = await RecordedVideo.get_or_none(file_path=str(file_path)).select_related('recorded_program')

                    # 同一のパスを持つ録画ファイルが存在しないか、ハッシュが異なる場合はメタデータを取得する
                    if current_recorded_video is None or current_recorded_video.file_hash != file_hash:

                        # TODO: CMSectionDetector とシリーズタイトル・話数・サブタイトルの取得処理を並列化する
                        # どちらも MetadataAnalyzer だけで完結する処理と比較して時間がかかる想定なので、処理の完了を待つべきではない

                        # MetadataAnalyzer でメタデータを解析し、RecordedVideo, RecordedProgram, Channel (is_watchable=False) モデルを取得する
                        ## メタデータの解析に失敗した (KonomiTV で再生できない形式など) 場合は None が返るのでスキップする
                        ## Channel モデルは録画ファイルから番組情報を取得できなかった場合は None になる
                        ## asyncio.to_thread() で非同期に実行しないと内部で DB アクセスしている箇所でエラーが発生する
                        try:
                            result = await asyncio.to_thread(MetadataAnalyzer(file_path).analyze)
                            if result is None:
                                # メタデータの解析に失敗するファイルが出ることは一定数想定されうるので warning 扱い
                                Logging.warning(f'{file_path}: Failed to analyze metadata. ignored.')
                                continue
                            recorded_video, recorded_program, channel = result
                        except Exception:
                            # メタデータの解析中に予期せぬエラーが発生した場合
                            # ログ出力した上でスキップする
                            Logging.error(f'{file_path}: Unexpected error occurred while analyzing metadata. ignored.')
                            Logging.error(traceback.format_exc())
                            continue

                        # メタデータの解析に成功したなら DB に保存するタスクの引数を追加する
                        # 録画ファイルのスキャン完了後に引数を表すタプルが save() の引数に渡され、一括で DB に保存される
                        ## スキャン中に DB への書き込みを行うと並列処理の関係でデータベースロックエラーが発生することがあるほか、
                        ## スキャン用ループのパフォーマンス低下につながるため、敢えて遅延させている
                        ## 以前は Coroutine を直接追加していたが、Coroutine は一度実行するとエラーが起きても再利用できないため、この実装に変更した
                        save_args_list.append((current_recorded_video, recorded_video, recorded_program, channel))

                        if current_recorded_video is None:
                            Logging.info(f'Add Recorded: {file_path.name}')
                        else:
                            Logging.info(f'Update Recorded: {file_path.name}')
                    else:
                        #Logging.debug(f'Skip Recorded: {file_path.name}')
                        pass

            async def save(
                current_recorded_video: RecordedVideo | None,
                recorded_video: RecordedVideo,
                recorded_program: RecordedProgram,
                channel: Channel | None,
            ) -> None:
                """
                録画ファイルの変更を DB に保存する
                スキャン時にこの関数に渡す引数を作成した後、スキャン終了後に一括で実行する
                """

                # TODO: 完成形ではこの時点で recorded_program 内にシリーズタイトル・話数・サブタイトルが取得できているはずだが、
                # Series と SeriesBroadcastPeriod モデル自体は作成および紐付けされていないので、別途それを行う必要がある
                ## もちろんすべて（あるいはいずれか）が取得できない場合もあるので、取得できる限られた情報から判断するように実装する必要がある

                # 既に同一の ID を持つ Channel が存在する場合は、既存の Channel を使う
                if channel is not None:
                    exists_channel = await Channel.get_or_none(id=channel.id)
                    if exists_channel is not None:
                        channel = exists_channel

                # 同一のパスを持つ録画ファイルが存在するがハッシュが異なる場合、一旦削除する
                ## この処理が実行されている時点で、同一のパスを持つ録画ファイルが存在する場合、ハッシュが異なることが確定している
                ## RecordedProgram に紐づく RecordedVideo も CASCADE 制約で同時に削除される
                ## Channel (is_watchable=False) は他の録画ファイルから参照されている可能性があるため、削除されない
                if current_recorded_video is not None:
                    await current_recorded_video.recorded_program.delete()

                # メタデータの解析に成功したなら DB に保存する
                ## 子テーブルを保存した後、それらを親テーブルに紐付けて保存する
                if channel is not None:
                    await channel.save()
                    recorded_program.channel_id = channel.id
                await recorded_program.save()
                recorded_video.recorded_program_id = recorded_program.id
                await recorded_video.save()

            retry_count = 10
            while retry_count > 0:
                try:
                    # トランザクション配下に入れることでパフォーマンスが向上する
                    async with transactions.in_transaction():

                        # DB に保存するタスクを一括実行する
                        ## DB 書き込みは並行だとパフォーマンスが出ないので、普通に for ループで実行する
                        for save_args in save_args_list:
                            await save(*save_args)

                        # 正常に DB に保存できたならループを抜ける
                        break

                # DB が他のプロセスによってロックされている場合は、少し待ってからリトライする
                ## SQLite は複数プロセスから同時に書き込むことができないため、リトライ処理が必要
                except exceptions.OperationalError as ex:
                    if 'database is locked' in str(ex).lower():
                        retry_count -= 1
                        Logging.warning(f'Failed to save to database. Retrying... ({retry_count}/10)')
                        await asyncio.sleep(0.25)
                    else:
                        # 予期せぬ OperationalError が発生した場合はリトライせずに例外を投げる
                        raise ex

            if 0 < retry_count < 10:
                Logging.info(f'Succeeded to save to database after retrying.')
            elif retry_count == 0:
                Logging.error(f'Failed to save to database after retrying. ignored.')

        # 明示的に例外を拾わないとなぜかメインプロセスも含め全体がフリーズしてしまう
        except Exception:
            Logging.error(traceback.format_exc())

        # 開いた Tortoise ORM のコネクションを明示的に閉じる
        # コネクションを閉じないと Ctrl+C を押下しても終了できない
        finally:
            await Tortoise.close_connections()

        # 強制的にガベージコレクションを実行する
        gc.collect()

        return existing_files


    @classmethod
    def updateDirectoryForMultiProcess(cls, directory: Path) -> list[str]:
        """
        RecordedVideo.updateDirectory() の同期版 (ProcessPoolExecutor でのマルチプロセス実行用)

        Args:
            directory (Path): 録画ファイルが格納されているディレクトリ

        Returns:
            list[str]: スキャンで見つかったすべての録画ファイルのフルパスのリスト
        """

        # もし Config() の実行時に AssertionError が発生した場合は、LoadConfig() を実行してサーバー設定データをロードする
        ## 通常ならマルチプロセス実行時もサーバー設定データがロードされているはずだが、
        ## 自動リロードモード時のみなぜかグローバル変数がマルチプロセスに引き継がれないため、明示的にロードさせる必要がある
        try:
            Config()
        except AssertionError:
            # バリデーションは既にサーバー起動時に行われているためスキップする
            LoadConfig(bypass_validation=True)

        # asyncio.run() で非同期メソッドの実行が終わるまで待つ
        return asyncio.run(cls.updateDirectory(directory))
