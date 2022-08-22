
import argparse
import asyncio
import atexit
import logging
import os
import psutil
import subprocess
import sys
import uvicorn
import uvicorn.logging
from typing import Any, cast
from uvicorn.supervisors import ChangeReload

from app.constants import AKEBI_LOG_PATH, BASE_DIR, CONFIG, KONOMITV_ACCESS_LOG_PATH, KONOMITV_SERVER_LOG_PATH, LIBRARY_PATH, VERSION


def main():

    # 引数解析
    parser = argparse.ArgumentParser(
        formatter_class = argparse.RawTextHelpFormatter,
        description = 'KonomiTV: Kind and Optimized Next On-broadcasting watching and Management Infrastructure for TV',
    )
    parser.add_argument('--reload', action='store_true', help='start uvicorn in auto-reload mode')
    parser.add_argument('--version', action='version', help='show version information', version=f'KonomiTV version {VERSION}')
    args = parser.parse_args()

    # Uvicorn を自動リロードモードで起動するかのフラグ
    ## 基本的に開発時用で、コードを変更するとアプリケーションサーバーを自動で再起動してくれる
    is_reload: bool = args.reload

    # 前回のログをすべて削除
    try:
        if os.path.exists(KONOMITV_SERVER_LOG_PATH):
            os.remove(KONOMITV_SERVER_LOG_PATH)
        if os.path.exists(KONOMITV_ACCESS_LOG_PATH):
            os.remove(KONOMITV_ACCESS_LOG_PATH)
        if os.path.exists(AKEBI_LOG_PATH):
            os.remove(AKEBI_LOG_PATH)
    except PermissionError:
        pass

    # ランチャー上で Logging モジュールをインポートするといろいろこじれるので、独自にロギングを設定
    logger = logging.getLogger('KonomiTV-Launcher')
    handler = logging.StreamHandler()
    handler.setFormatter(uvicorn.logging.DefaultFormatter(
        fmt = '[%(asctime)s] %(levelprefix)s %(message)s',
        datefmt = '%Y/%m/%d %H:%M:%S',
        use_colors = sys.stderr.isatty(),
    ))
    logger.addHandler(handler)

    # リッスンするポート番号
    port = CONFIG['server']['port']
    if type(port) is not int or port < 1024 or port > 65525:
        logger.error(
            f'ポート番号の設定が不正なため、KonomiTV を起動できません。\n'
            '                                '  # インデント用
            f'設定したポート番号が 1024 ~ 65525 (65535 ではない) の間に収まっているかを確認してください。'
        )
        sys.exit(1)

    # 使用中のポートを取得
    # ref: https://qiita.com/skokado/items/6e76762c68866d73570b
    used_ports = [cast(Any, conn.laddr).port for conn in psutil.net_connections() if conn.status == 'LISTEN']

    # リッスンするポートと同じポートが使われていたら、エラーを表示する
    if port in used_ports:
        logger.error(
            f'ポート {port} は他のプロセスで使われているため、KonomiTV を起動できません。\n'
            '                                '  # インデント用
            f'重複して KonomiTV を起動していないか、他のソフトでポート {port} を使っていないかを確認してください。'
        )
        sys.exit(1)

    # カスタム HTTPS 証明書/秘密鍵が指定されているとき
    custom_https_certificate = []
    if CONFIG['server']['custom_https_certificate'] is not None and CONFIG['server']['custom_https_private_key'] is not None:
        if (os.path.exists(CONFIG['server']['custom_https_certificate']) is False or
            os.path.exists(CONFIG['server']['custom_https_private_key']) is False):
            logger.error(
                f'指定されたカスタム HTTPS 証明書/秘密鍵が存在しないため、KonomiTV を起動できません。\n'
                '                                '  # インデント用
                f'正しいカスタム HTTPS 証明書/秘密鍵のパスを指定しているかを確認してください。'
            )
            sys.exit(1)
        # 追加の引数リスト
        custom_https_certificate = [
            '--custom-certificate', CONFIG['server']['custom_https_certificate'],
            '--custom-private-key', CONFIG['server']['custom_https_private_key'],
        ]

    # Akebi HTTPS Server (HTTPS リバースプロキシ) を起動
    ## HTTP/2 対応と HTTPS 化を一手に行う Golang 製の特殊なリバースプロキシサーバー
    ## ログは server/logs/Akebi-HTTPS-Server.log に出力する
    ## ref: https://github.com/tsukumijima/Akebi
    with open(AKEBI_LOG_PATH, 'w', encoding='utf-8') as file:
        reverse_proxy_process = subprocess.Popen(
            [
                LIBRARY_PATH['Akebi'],
                '--listen-address', f'0.0.0.0:{port}',
                '--proxy-pass-url', f'http://127.0.0.77:{port + 10}/',
                '--keyless-server-url', 'https://akebi.konomi.tv/',
                *custom_https_certificate,  # カスタム HTTPS 証明書/秘密鍵を指定する引数を追加（指定されているときのみ）
            ],
            stdout = file,
            stderr = file,
            creationflags = (subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0),  # コンソールなしで実行 (Windows)
        )

    # このプロセスが終了されたときに、HTTPS リバースプロキシも一緒に終了する
    atexit.register(lambda: reverse_proxy_process.terminate())

    # Windows でもイベントループに SelectorEventLoop を利用する
    ## Python 3.8 以降で Windows での既定のイベントループとなっている ProactorEventLoop は不具合が多いらしく、
    ## subprocess 周りの一部のメソッドが使えない事を除くと（今のところ使っていないので問題ない）、SelectorEventLoop の方が安定している印象
    ## ref: https://github.com/aio-libs/aiohttp/issues/4324
    ## ref: https://github.com/encode/uvicorn/pull/1257
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Uvicorn の設定
    config = uvicorn.Config(
        # 起動するアプリケーション
        app = 'app.app:app',
        # リッスンするアドレス
        ## サーバーへのすべてのアクセスには一度 Akebi のリバースプロキシを通す
        ## 混乱を避けるため、容易にアクセスされないだろう 127.0.0.77 のみでリッスンしている
        host = '127.0.0.77',
        # リッスンするポート番号
        ## 指定されたポートに 10 を足したもの
        port = port + 10,
        # 自動リロードモードモードで起動するか
        reload = is_reload,
        # リロードするフォルダ
        reload_dirs = str(BASE_DIR / 'app') if is_reload else None,
        # ロギングフォーマットの設定
        ## Uvicorn のもとの DictConfig を参考にして作成した
        ## ref: https://github.com/encode/uvicorn/blob/0.18.2/uvicorn/config.py#L95-L126
        log_config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                # サーバーログ用のログフォーマッター
                'default': {
                    '()': 'uvicorn.logging.DefaultFormatter',
                    'datefmt': '%Y/%m/%d %H:%M:%S',
                    'format': '[%(asctime)s] %(levelprefix)s %(message)s',
                },
                'default_file': {
                    '()': 'uvicorn.logging.DefaultFormatter',
                    'datefmt': '%Y/%m/%d %H:%M:%S',
                    'format': '[%(asctime)s] %(levelprefix)s %(message)s',
                    'use_colors': False,  # ANSI エスケープシーケンスを出力しない
                },
                # アクセスログ用のログフォーマッター
                'access': {
                    '()': 'uvicorn.logging.AccessFormatter',
                    'datefmt': '%Y/%m/%d %H:%M:%S',
                    'format': '[%(asctime)s] %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
                },
                'access_file': {
                    '()': 'uvicorn.logging.AccessFormatter',
                    'datefmt': '%Y/%m/%d %H:%M:%S',
                    'format': '[%(asctime)s] %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
                    'use_colors': False,  # ANSI エスケープシーケンスを出力しない
                },
            },
            'handlers': {
                ## サーバーログは標準エラー出力と server/logs/KonomiTV-Server.log の両方に出力する
                'default': {
                    'formatter': 'default',
                    'class': 'logging.StreamHandler',
                    'stream': 'ext://sys.stderr',
                },
                'default_file': {
                    'formatter': 'default_file',
                    'class': 'logging.FileHandler',
                    'filename': KONOMITV_SERVER_LOG_PATH,
                    'mode': 'a',
                    'encoding': 'utf-8',
                },
                ## アクセスログは標準出力と server/logs/KonomiTV-Access.log の両方に出力する
                'access': {
                    'formatter': 'access',
                    'class': 'logging.StreamHandler',
                    'stream': 'ext://sys.stdout',
                },
                'access_file': {
                    'formatter': 'access_file',
                    'class': 'logging.FileHandler',
                    'filename': KONOMITV_ACCESS_LOG_PATH,
                    'mode': 'a',
                    'encoding': 'utf-8',
                },
            },
            'loggers': {
                'uvicorn': {'handlers': ['default', 'default_file'], 'level': 'INFO'},
                'uvicorn.error': {'level': 'INFO'},
                'uvicorn.access': {'handlers': ['access', 'access_file'], 'level': 'INFO', 'propagate': False},
            },
        },
        # インターフェイスとして ASGI3 を選択
        interface = 'asgi3',
        # HTTP プロトコルの実装として httptools を選択
        http = 'httptools',
        # イベントループの実装として Windows では asyncio 、それ以外では uvloop を選択
        loop = ('asyncio' if os.name == 'nt' else 'uvloop'),
    )

    # Uvicorn のサーバーインスタンスを初期化
    server = uvicorn.Server(config)

    # Uvicorn を起動
    ## 自動リロードモードと通常時で呼び方が異なる
    ## ここで終了までブロッキングされる（非同期 I/O のエントリーポイント）
    ## ref: https://github.com/encode/uvicorn/blob/0.18.2/uvicorn/main.py#L568-L575
    if config.should_reload:
        # 自動リロードモード
        sock = config.bind_socket()
        ChangeReload(config, target=server.run, sockets=[sock]).run()
    else:
        # 通常時
        server.run()


if __name__ == '__main__':
    main()
