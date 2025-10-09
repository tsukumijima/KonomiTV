
import asyncio
import json
import os
import signal
import sys
import threading
import time
from collections.abc import Coroutine
from typing import Annotated, Any, Literal

import anyio
import psutil
from fastapi import APIRouter, Depends, Path, Request, status
from fastapi.exceptions import HTTPException
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordBearer
from sse_starlette.sse import EventSourceResponse

from app import logging, schemas
from app.config import Config
from app.constants import (
    KONOMITV_ACCESS_LOG_PATH,
    KONOMITV_SERVER_LOG_PATH,
    RESTART_REQUIRED_LOCK_PATH,
    THUMBNAILS_DIR,
)
from app.metadata.CMSectionsDetector import CMSectionsDetector
from app.metadata.KeyFrameAnalyzer import KeyFrameAnalyzer
from app.metadata.RecordedScanTask import RecordedScanTask
from app.metadata.ThumbnailGenerator import ThumbnailGenerator
from app.models.Channel import Channel
from app.models.Program import Program
from app.models.RecordedProgram import RecordedProgram
from app.models.RecordedVideo import RecordedVideo
from app.models.TwitterAccount import TwitterAccount
from app.models.User import User
from app.routers.UsersRouter import GetCurrentAdminUser, GetCurrentUser


# ルーター
router = APIRouter(
    tags = ['Maintenance'],
    prefix = '/api/maintenance',
)

# 録画フォルダの一括スキャン・バックグラウンド解析タスクの asyncio.Task インスタンス
batch_scan_task: asyncio.Task[None] | None = None
background_analysis_task: asyncio.Task[None] | None = None


async def GetCurrentAdminUserOrLocal(
    request: Request,
    token: Annotated[str | None, Depends(OAuth2PasswordBearer(tokenUrl='users/token', auto_error=False))],
) -> User | None:
    """
    現在管理者ユーザーでログインしているか、http://127.0.0.77:7010 からのアクセスであるかを確認する
    KonomiTV の Windows サービスからサーバーをシャットダウンするために必要
    """

    # HTTP リクエストの Host ヘッダーが 127.0.0.77:7010 である場合、Windows サービスプロセスからのアクセスと見なす
    ## 通常アクセス時の Host ヘッダーは 192-168-1-11.local.konomi.tv:7000 のような形式になる
    valid_host = f'127.0.0.77:{Config().server.port + 10}'
    if request.headers.get('host', '').strip() == valid_host:
        return None

    # それ以外である場合、管理者ユーザーでログインしているかを確認する
    if token is None:
        logging.error('[MaintenanceRouter][GetCurrentAdminUserOrLocal] Not authenticated.')
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = 'Not authenticated',
            headers = {'WWW-Authenticate': 'Bearer'},
        )
    return await GetCurrentAdminUser(await GetCurrentUser(token))


@router.get(
    '/logs/{log_type}',
    summary = 'サーバーログストリーミング API',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'サーバーログまたはアクセスログが随時配信されるイベントストリーム。',
            'content': {'text/event-stream': {}},
        }
    }
)
def LogStreamAPI(
    log_type: Annotated[Literal['server', 'access'], Path(description='ログの種類。server: サーバーログ、access: アクセスログ')],
    current_user: Annotated[User, Depends(GetCurrentAdminUser)],
):
    """
    サーバーログまたはアクセスログを Server-Sent Events で随時配信する。

    イベントには、
    - 初回にログファイルの先頭から現在の最新行までのすべての行を送信する **initial_log_update**
    - リアルタイムに追加されたログを送信する **log_update**
    の2種類がある。

    初回接続時にはログファイルの先頭から現在の最新行までのすべての行が initial_log_update イベントで一括送信され、<br>
    その後ログに更新があれば log_update イベントで1行ずつ送信される。

    ファイル I/O を伴うため敢えて同期関数として実装している。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    # ログファイルのパスを決定
    log_path = KONOMITV_SERVER_LOG_PATH if log_type == 'server' else KONOMITV_ACCESS_LOG_PATH

    # ログファイルが存在しない場合はエラー
    if not log_path.exists():
        logging.error(f'[MaintenanceRouter][LogStreamAPI] Log file not found: {log_path}')
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = f'Log file not found: {log_path}',
        )

    # ログの変更を監視し、変更があればログ行をイベントストリームとして出力する
    def generator():
        """イベントストリームを出力するジェネレーター"""

        # ファイルを開く
        with open(log_path, encoding='utf-8') as f:
            # 初回接続時に全ての行を送信
            all_lines = [line.rstrip('\n') for line in f.readlines() if line.strip()]  # 空行は除外
            yield {
                'event': 'initial_log_update',
                'data': json.dumps(all_lines, ensure_ascii=False),
            }

            # ファイルの現在位置を記録
            current_position = f.tell()

            # 継続的に新しい行を監視
            while True:
                # ファイルが更新されたかチェック
                f.seek(0, os.SEEK_END)
                if f.tell() > current_position:
                    # ファイルが更新された場合、前回の位置に戻る
                    f.seek(current_position)

                    # 新しい行を読み込む
                    for line in f:
                        line = line.rstrip('\n')
                        if line:  # 空行は送信しない
                            yield {
                                'event': 'log_update',
                                'data': json.dumps(line, ensure_ascii=False),
                            }

                    # 現在位置を更新
                    current_position = f.tell()

                # 少し待機
                time.sleep(0.5)

    # EventSourceResponse でイベントストリームを配信する
    return EventSourceResponse(generator())


@router.post(
    '/update-database',
    summary = 'データベース更新 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def UpdateDatabaseAPI():
    """
    データベースに保存されている、チャンネル情報・番組情報・Twitter アカウント情報などの外部 API に依存するデータをすべて更新する。<br>
    即座に外部 API からのデータ更新を反映させたい場合に利用する。<br>
    このメンテナンス機能は管理者ユーザーでなくてもアクセスできる。
    """

    await Channel.update()
    await Channel.updateJikkyoStatus()
    await Program.update(multiprocess=True)
    await TwitterAccount.updateAccountsInformation()


@router.post(
    '/run-batch-scan',
    summary = '録画フォルダ一括スキャン API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def BatchScanAPI():
    """
    録画フォルダ内の全 TS ファイルをスキャンし、メタデータを解析して DB に永続化する。<br>
    追加・変更があったファイルのみメタデータを解析し、DB に永続化する。<br>
    存在しない録画ファイルに対応するレコードを一括削除する。<br>
    このメンテナンス機能は管理者ユーザーでなくてもアクセスできる。
    """

    global batch_scan_task

    async def BatchScan():
        global batch_scan_task
        logging.info('Manual batch scan of recording folders has started.')

        # 一括スキャンを実行
        await RecordedScanTask().runBatchScan()

        # 一括スキャンが完了した
        logging.info('Manual batch scan of recording folders has finished.')
        batch_scan_task = None  # 再度新しいタスクを作成できるように None にする

    # タスクが実行中でない場合、新しくタスクを作成して実行
    ## asyncio.create_task() で実行することで、API への HTTP コネクションが切断されてもタスクが継続される
    if batch_scan_task is None:
        batch_scan_task = asyncio.create_task(BatchScan())
        # タスクの実行が完了するまで待機
        await batch_scan_task
    else:
        logging.warning('[MaintenanceRouter][BatchScanAPI] Batch scan of recording folders is already running.')
        raise HTTPException(
            status_code = status.HTTP_429_TOO_MANY_REQUESTS,
            detail = 'Batch scan of recording folders is already running',
        )


@router.post(
    '/run-background-analysis',
    summary = 'バックグラウンド解析タスク手動実行 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def BackgroundAnalysisAPI():
    """
    キーフレーム情報が未解析の録画ファイルに対してキーフレーム情報を解析し、<br>
    サムネイルが未生成の録画ファイルに対してサムネイルを生成する。<br>
    このメンテナンス機能は管理者ユーザーでなくてもアクセスできる。
    """

    global background_analysis_task

    async def BackgroundAnalysis():
        global background_analysis_task
        logging.info('Manual background analysis has started.')

        # キーフレーム情報が未生成、またはサムネイルが未生成の録画ファイルを取得
        db_recorded_videos = await RecordedVideo.filter(status='Recorded')

        # 各録画ファイルに対して直列にバックグラウンド解析タスクを実行
        ## HDD は並列アクセスが遅いため、随時直列に実行していった方が結果的に早いことが多い
        ## すべて直列なので ProcessLimiter や DriveIOLimiter での制限は掛けていない
        for db_recorded_video in db_recorded_videos:
            file_path = anyio.Path(db_recorded_video.file_path)
            try:
                if not await file_path.is_file():
                    logging.warning(f'{file_path}: File not found. Skipping...')
                    continue

                # キーフレーム情報解析とサムネイル生成を同時に実行
                tasks: list[Coroutine[Any, Any, None]] = []

                # キーフレーム情報が未解析の場合、タスクに追加
                if not db_recorded_video.has_key_frames:
                    tasks.append(KeyFrameAnalyzer(file_path, db_recorded_video.container_format).analyzeAndSave())

                # CM 区間情報が未解析の場合、タスクに追加
                ## cm_sections が [] の時は「解析はしたが CM 区間がなかった/検出に失敗した」ことを表している
                ## CM 区間解析はかなり計算コストが高い処理のため、一度解析に失敗した録画ファイルは再解析しない
                if db_recorded_video.cm_sections is None:
                    tasks.append(CMSectionsDetector(
                        file_path = anyio.Path(db_recorded_video.file_path),
                        duration_sec = db_recorded_video.duration,
                    ).detectAndSave())

                # サムネイルが未生成の場合、タスクに追加
                # どちらか片方だけがないパターンも考えられるので、その場合もサムネイル生成を実行する
                thumbnail_tile_path = anyio.Path(str(THUMBNAILS_DIR)) / f'{db_recorded_video.file_hash}_tile.webp'
                thumbnail_path = anyio.Path(str(THUMBNAILS_DIR)) / f'{db_recorded_video.file_hash}.webp'
                if (not await thumbnail_tile_path.is_file()) or (not await thumbnail_path.is_file()):
                    # 録画番組情報を取得
                    db_recorded_program = await RecordedProgram.all() \
                        .select_related('recorded_video') \
                        .select_related('channel') \
                        .get_or_none(id=db_recorded_video.id)
                    if db_recorded_program is not None:
                        # RecordedProgram モデルを schemas.RecordedProgram に変換
                        recorded_program = schemas.RecordedProgram.model_validate(db_recorded_program, from_attributes=True)
                        tasks.append(ThumbnailGenerator.fromRecordedProgram(recorded_program).generateAndSave(skip_tile_if_exists=True))

                # タスクが存在する場合、同時実行
                if tasks:
                    await asyncio.gather(*tasks)

            except Exception as ex:
                logging.error(f'{file_path}: Error in background analysis:', exc_info=ex)
                continue

        # すべての録画ファイルのバックグラウンド解析が完了した
        logging.info('Manual background analysis has finished processing all recorded files.')
        background_analysis_task = None  # 再度新しいタスクを作成できるように None にする

    # タスクが実行中でない場合、新しくタスクを作成して実行
    ## asyncio.create_task() で実行することで、API への HTTP コネクションが切断されてもタスクが継続される
    if background_analysis_task is None:
        background_analysis_task = asyncio.create_task(BackgroundAnalysis())
        # タスクの実行が完了するまで待機
        await background_analysis_task
    else:
        logging.warning('[MaintenanceRouter][BackgroundAnalysisAPI] Background analysis task is already running.')
        raise HTTPException(
            status_code = status.HTTP_429_TOO_MANY_REQUESTS,
            detail = 'Background analysis task is already running',
        )


@router.post(
    '/restart',
    summary = 'サーバー再起動 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
def ServerRestartAPI(
    current_user: Annotated[User | None, Depends(GetCurrentAdminUserOrLocal)],
):
    """
    KonomiTV サーバーを再起動する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    def Restart():

        # シグナルの送信対象の PID
        ## --reload フラグが付与されている場合のみ、Reloader の起動元である親プロセスの PID を利用する
        target_process = psutil.Process(os.getpid())
        if '--reload' in sys.argv:
            parent_process = target_process.parent()
            if parent_process is not None:
                target_process = parent_process

        # 現在の Uvicorn サーバーを終了する
        if sys.platform == 'win32':
            target_process.send_signal(signal.CTRL_C_EVENT)
        else:
            target_process.send_signal(signal.SIGINT)

        # Uvicorn 終了後に再起動が必要であることを示すロックファイルを作成する
        # Uvicorn 終了後、KonomiTV.py でロックファイルの存在が確認され、もし存在していればサーバー再起動が行われる
        RESTART_REQUIRED_LOCK_PATH.touch(exist_ok=True)

    # バックグラウンドでサーバー再起動を開始
    threading.Thread(target=Restart).start()


@router.post(
    '/shutdown',
    summary = 'サーバー終了 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
def ServerShutdownAPI(
    current_user: Annotated[User | None, Depends(GetCurrentAdminUserOrLocal)],
):
    """
    KonomiTV サーバーを終了する。<br>
    なお、PM2 環境 / Docker 環境ではサーバー終了後に自動的にプロセスが再起動されるため、事実上 /api/maintenance/restart と等価。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    def Shutdown():

        # シグナルの送信対象の PID
        ## --reload フラグが付与されている場合のみ、Reloader の起動元である親プロセスの PID を利用する
        target_process = psutil.Process(os.getpid())
        if '--reload' in sys.argv:
            parent_process = target_process.parent()
            if parent_process is not None:
                target_process = parent_process

        # 現在の Uvicorn サーバーを終了する
        if sys.platform == 'win32':
            target_process.send_signal(signal.CTRL_C_EVENT)
        else:
            target_process.send_signal(signal.SIGINT)

    # バックグラウンドでサーバー終了を開始
    threading.Thread(target=Shutdown).start()
