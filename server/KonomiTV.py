
# タイムゾーンを常に Asia/Tokyo に設定する (Linux のみ)
## タイムゾーンが UTC の環境ではログの日時が日本時間より9時間遅れてしまうため
## デフォルトを Asia/Tokyo に変更することで、万が一のタイムゾーン関連のバグを防ぐ防波堤としての意味合いもある
## Windows ではタイムゾーンを変更することができないため、何もしない
import os  # noqa: I001
import sys
import time
if sys.platform != 'win32':
    os.environ['TZ'] = 'Asia/Tokyo'
    # Linux でもなぜか time.tzset() が使えないことがあるので、try-except で囲む
    try:
        time.tzset()
    except AttributeError:
        pass

import asyncio
import atexit
import logging
import platform
import subprocess
from pathlib import Path

import typer
import uvicorn
from aerich import Command
from tortoise import Tortoise
from uvicorn.supervisors.watchfilesreload import WatchFilesReload

from app.config import LoadConfig
from app.constants import (
    AKEBI_LOG_PATH,
    BASE_DIR,
    DATABASE_CONFIG,
    KONOMITV_ACCESS_LOG_PATH,
    KONOMITV_SERVER_LOG_PATH,
    LIBRARY_PATH,
    LOGGING_CONFIG,
    RESTART_REQUIRED_LOCK_PATH,
    VERSION,
)


# passlib が送出する bcrypt のバージョン差異による警告を無視
# ref: https://github.com/pyca/bcrypt/issues/684
logging.getLogger('passlib').setLevel(logging.ERROR)

cli = typer.Typer()

def version(value: bool):
    if value is True:
        typer.echo(f'KonomiTV version {VERSION}')
        raise typer.Exit()

@cli.command(help='KonomiTV: Kept Organized, Notably Optimized, Modern Interface TV media server')
def main(
    reload: bool = typer.Option(False, '--reload', help='Start Uvicorn in auto-reload mode. (Linux only)'),
    version: bool = typer.Option(None, '--version', callback=version, is_eager=True, help='Show version information.'),
):

    # 前回のログをすべて削除する
    try:
        if KONOMITV_SERVER_LOG_PATH.exists():
            KONOMITV_SERVER_LOG_PATH.unlink()
        if KONOMITV_ACCESS_LOG_PATH.exists():
            KONOMITV_ACCESS_LOG_PATH.unlink()
        if AKEBI_LOG_PATH.exists():
            AKEBI_LOG_PATH.unlink()
    except PermissionError:
        pass

    # もし何らかの理由でロックファイルが残っていた場合は削除する
    if RESTART_REQUIRED_LOCK_PATH.exists():
        RESTART_REQUIRED_LOCK_PATH.unlink()

    # ここでロガーとユーティリティをインポートする
    ## 前回のログを削除する前でないと正しく動作しない
    ## ロギング設定は logging.py が読み込まれた瞬間に行われるが、その際に前回のログファイルが残っているとエラーになる
    ## 前回のログをすべて削除する処理を logging.py 自体に記述してしまうとマルチプロセス実行時や自動リロードモード時に意図せずファイルが削除されてしまう
    ## constants.py は内部モジュールへの依存がなく、config.py も constants.py 以外への依存はないので、この2つのみトップレベルでインポートしている
    from app import logging
    from app.utils import IsRunningAsWindowsService

    # バージョン情報をログに出力
    logging.info(f'KonomiTV version {VERSION}')

    # Aerich でデータベースをアップグレードする
    ## 特にデータベースのアップグレードが必要ない場合は何も起こらない
    async def UpgradeDatabase():
        command = Command(tortoise_config=DATABASE_CONFIG, app='models', location='./app/migrations/')
        await command.init()
        migrated = await command.upgrade(run_in_transaction=True)
        await Tortoise.close_connections()
        if not migrated:
            logging.info('No database migration is required.')
        else:
            for version_file in migrated:
                logging.info(f'Successfully migrated to {version_file}.')
    asyncio.run(UpgradeDatabase())

    # ***** サポートされているアーキテクチャかのバリデーション *****

    # CPU のアーキテクチャから実行可否を判定
    ## サポートされているアーキテクチャ
    ## AMD64 : Windows (x64)
    ## x86_64: Linux (x64)
    ## aarch64: Linux (arm64)
    current_arch = platform.machine()
    if current_arch not in ['AMD64', 'x86_64', 'aarch64']:
        logging.error(f'KonomiTV は {current_arch} アーキテクチャに対応していません。')
        sys.exit(1)

    # ***** サードパーティーライブラリが配置されているかのバリデーション *****

    # すべてのサードパーティーライブラリの配置をチェック
    for library_name, library_path in LIBRARY_PATH.items():
        # x64 の場合、ARM のみの rkmppenc はチェックしない
        if current_arch in ['AMD64', 'x86_64'] and library_name == 'rkmppenc':
            continue
        # arm64 の場合、x64 のみの QSVEncC・NVEncC・VCEEncC はチェックしない
        if current_arch == 'aarch64' and library_name in ['QSVEncC', 'NVEncC', 'VCEEncC']:
            continue
        if Path(library_path).is_file() is False:
            logging.error(f'{library_name} がサードパーティーライブラリとして配置されていないため、KonomiTV を起動できません。')
            logging.error(f'{library_name} が {library_path} に配置されているかを確認してください。')
            sys.exit(1)

    # ***** サーバー設定データのロード *****

    # サーバー設定データのロードとバリデーションを行う
    ## ここでロードしたサーバー設定データが Config() で参照される
    ## config.yaml が配置されていなかったりバリデーションエラーが発生した際は、
    ## LoadConfig() 内でエラーログを出力した後、sys.exit(1) でサーバーが終了される
    CONFIG = LoadConfig()

    # ***** KonomiTV サーバーを起動 *****

    # カスタム HTTPS 証明書/秘密鍵が指定されているとき
    custom_https_certificate: list[str] = []
    if CONFIG.server.custom_https_certificate is not None and CONFIG.server.custom_https_private_key is not None:
        custom_https_certificate = [
            '--custom-certificate', str(CONFIG.server.custom_https_certificate),
            '--custom-private-key', str(CONFIG.server.custom_https_private_key),
        ]

    # Akebi HTTPS Server (HTTPS リバースプロキシ) を起動
    ## HTTP/2 対応と HTTPS 化を一手に行う Golang 製の特殊なリバースプロキシサーバー
    ## ログは server/logs/Akebi-HTTPS-Server.log に出力する
    ## ref: https://github.com/tsukumijima/Akebi
    with open(AKEBI_LOG_PATH, mode='w', encoding='utf-8') as file:
        reverse_proxy_process = subprocess.Popen(
            [
                LIBRARY_PATH['Akebi'],
                '--listen-address', f'0.0.0.0:{CONFIG.server.port}',
                '--proxy-pass-url', f'http://127.0.0.77:{CONFIG.server.port + 10}/',
                '--keyless-server-url', 'https://akebi.konomi.tv/',
                *custom_https_certificate,  # カスタム HTTPS 証明書/秘密鍵を指定する引数を追加（指定されているときのみ）
            ],
            stdout = file,
            stderr = file,
            creationflags = (subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0),  # コンソールなしで実行 (Windows)
        )

    # このプロセスが終了されたときに、HTTPS リバースプロキシも一緒に終了する
    atexit.register(lambda: reverse_proxy_process.terminate())

    # Uvicorn の設定
    server_config = uvicorn.Config(
        # 起動するアプリケーション
        app = 'app.app:app',
        # リッスンするアドレス
        ## サーバーへのすべてのアクセスには一度 Akebi のリバースプロキシを通す
        ## 混乱を避けるため、容易にアクセスされないだろう 127.0.0.77 のみでリッスンしている
        host = '127.0.0.77',
        # リッスンするポート番号
        ## 指定されたポートに 10 を足したもの
        port = CONFIG.server.port + 10,
        # 自動リロードモードモードで起動するか
        reload = reload,
        # リロードするフォルダ
        reload_dirs = str(BASE_DIR / 'app') if reload else None,
        # ロギングの設定
        log_config = LOGGING_CONFIG,
        # インターフェイスとして ASGI3 を選択
        interface = 'asgi3',
        # HTTP プロトコルの実装として httptools を選択
        http = 'httptools',
        # イベントループのセットアップは自前で行うため、ここでは none を指定
        loop = 'none',
        # ストリーミング配信中にサーバーシャットダウンを要求された際、強制的に接続を切断するまでの秒数
        timeout_graceful_shutdown = 1,
    )

    # Uvicorn のサーバーインスタンスを初期化
    server = uvicorn.Server(server_config)

    # Linux では Uvloop をイベントループとして利用する
    # Windows では Winloop をイベントループとして利用する予定だったが、2025年3月時点では
    # キャプチャ保存時 (?) に稀にプロセスごと無言で落ちる問題があるため、当面は通常の asyncio (ProactorEventLoop) を利用する
    # ref: https://github.com/Vizonex/Winloop
    if sys.platform == 'win32':
        if reload is True:
            logging.warning('Python の asyncio の技術的な制約により、Windows では自動リロードモードは正常に動作しません。')
            logging.warning('なお、外部プロセス実行を伴うストリーミング視聴を行わなければ一応 Windows でも機能します。')
        # Aerich 0.8.2 以降では Windows のみインポート時にイベントループポリシーが SelectorEventLoop に変更されてしまうが、
        # asyncio.subprocess.create_subprocess_exec() は ProactorEventLoop でないと動作しないため、明示的に ProactorEventLoop に戻す
        # psycopg3 バックエンドが SelectorEventLoop しか対応していない件の対策らしいが、KonomiTV では SQLite を利用しているため問題ない
        # ref: https://github.com/tortoise/aerich/pull/251
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    else:
        import uvloop
        uvloop.install()

    # Uvicorn を起動
    ## 自動リロードモードと通常時で呼び方が異なる
    ## ここで終了までブロッキングされる（非同期 I/O のエントリーポイント）
    ## ref: https://github.com/encode/uvicorn/blob/0.18.2/uvicorn/main.py#L568-L575
    try:
        if server_config.should_reload:
            # 自動リロードモード (Linux 専用)
            ## Windows で自動リロードモードを機能させるには SelectorEventLoop が必要だが、外部プロセス実行に利用している
            ## asyncio.subprocess.create_subprocess_exec() は ProactorEventLoop でないと動作しないため、Windows では事実上利用できない
            ## 外部プロセス実行を伴うストリーミング視聴を行わなければ一応 Windows でも機能する
            sock = server_config.bind_socket()
            WatchFilesReload(server_config, target=server.run, sockets=[sock]).run()
        else:
            # 通常時
            server.run()
    except KeyboardInterrupt:
        # Uvicorn のサーバーインスタンスから KeyboardInterrupt が送出された場合は一旦無視して、HTTPS リバースプロキシを確実に終了する
        # 少し前の Uvicorn は KeyboardInterrupt を内部で握り潰していたが、最近のバージョンから送出するようになった
        pass

    # HTTPS リバースプロキシを終了
    reverse_proxy_process.terminate()

    # この時点ではタイミングの関係でまだロックファイルが作成されていないことがあるので、1秒待機する
    time.sleep(1)

    # もしこの時点で再起動が必要であることを示すロックファイルが存在する場合、KonomiTV サーバーを再起動する
    ## このロックファイルは ServerRestartAPI によって作成される
    if RESTART_REQUIRED_LOCK_PATH.exists():
        logging.warning('Server restart requested. Restarting...')

        # Windows サービスとして実行されている場合は、Windows サービス側で再起動処理が行われるので、確実にプロセスを終了する
        if IsRunningAsWindowsService():
            os._exit(0)  # type: ignore

        # os.execv() で現在のプロセスを新規に起動したプロセスに置き換える
        ## os.execv() は戻らないので、事前にロックファイルを削除しておく
        RESTART_REQUIRED_LOCK_PATH.unlink()
        os.execv(sys.executable, [sys.executable, *sys.argv])


if __name__ == '__main__':
    cli()
