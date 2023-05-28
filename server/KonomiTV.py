
import argparse
import asyncio
import atexit
import logging
import logging.config
import platform
import psutil
import requests
import subprocess
import sys
import uvicorn
import uvicorn.logging
from pathlib import Path
from pydantic import ValidationError
from typing import Any, cast

from app.constants import (
    AKEBI_LOG_PATH,
    API_REQUEST_HEADERS,
    BASE_DIR,
    CONFIG,
    KONOMITV_ACCESS_LOG_PATH,
    KONOMITV_SERVER_LOG_PATH,
    LIBRARY_PATH,
    LOGGING_CONFIG,
    VERSION,
)


def main():

    # 引数解析
    parser = argparse.ArgumentParser(
        formatter_class = argparse.RawTextHelpFormatter,
        description = 'KonomiTV: Kept Organized, Notably Optimized, Modern Interface TV media server',
    )
    parser.add_argument('--reload', action='store_true', help='start uvicorn in auto-reload mode (Linux only)')
    parser.add_argument('--version', action='version', help='show version information', version=f'KonomiTV version {VERSION}')
    args = parser.parse_args()

    # 前回のログをすべて削除
    try:
        if KONOMITV_SERVER_LOG_PATH.exists():
            KONOMITV_SERVER_LOG_PATH.unlink()
        if KONOMITV_ACCESS_LOG_PATH.exists():
            KONOMITV_ACCESS_LOG_PATH.unlink()
        if AKEBI_LOG_PATH.exists():
            AKEBI_LOG_PATH.unlink()
    except PermissionError:
        pass

    # Uvicorn を起動する前に Uvicorn のロガーを使えるようにする
    logging.config.dictConfig(LOGGING_CONFIG)
    logger = logging.getLogger('uvicorn')

    # バージョン情報をログに出力
    logger.info(f'KonomiTV version {VERSION}')

    # 最低限のバリデーション (万が一 config.yaml 内のキーが抜けていても KeyError で落ちないように)
    try:
        CONFIG['server']['port']
        CONFIG['server']['custom_https_certificate']
        CONFIG['server']['custom_https_private_key']
    except KeyError:
        logger.error('config.yaml のフォーマットが不正なため、KonomiTV を起動できません。')
        logger.error('config.yaml の記述が正しいかを確認してください。')
        sys.exit(1)

    # ***** サポートされているアーキテクチャかのバリデーション *****

    # サポートされているアーキテクチャ
    ## AMD64 : Windows (x64)
    ## x86_64: Linux (x64)
    ## aarch64: Linux (arm64)
    supported_arch = ['AMD64', 'x86_64', 'aarch64']
    current_arch = platform.machine()

    # CPU のアーキテクチャから実行可否を判定
    if current_arch not in supported_arch:
        logger.error(f'KonomiTV は {current_arch} アーキテクチャに対応していません。')
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
            logger.error(f'{library_name} がサードパーティーライブラリとして配置されていないため、KonomiTV を起動できません。')
            logger.error(f'{library_name} が {library_path} に配置されているかを確認してください。')
            sys.exit(1)

    # x64 なのにエンコーダーとして rkmppenc が指定されている場合はエラー
    if current_arch in ['AMD64', 'x86_64'] and CONFIG['general']['encoder'] == 'rkmppenc':
        logger.error('x64 アーキテクチャでは rkmppenc は使用できません。')
        logger.error('利用するエンコーダーを FFmpeg・QSVEncC・NVEncC・VCEEncC のいずれかに変更してください。')
        sys.exit(1)

    # arm64 なのにエンコーダーとして QSVEncC・NVEncC・VCEEncC が指定されている場合はエラー
    if current_arch == 'aarch64' and CONFIG['general']['encoder'] in ['QSVEncC', 'NVEncC', 'VCEEncC']:
        logger.error('arm64 アーキテクチャでは QSVEncC・NVEncC・VCEEncC は使用できません。')
        logger.error('利用するエンコーダーを FFmpeg・rkmppenc のいずれかに変更してください。')
        sys.exit(1)

    # ***** リッスンポートのバリデーション *****

    # リッスンするポート番号
    port = CONFIG['server']['port']
    if type(port) is not int or port < 1024 or port > 65525:
        logger.error('ポート番号の設定が不正なため、KonomiTV を起動できません。')
        logger.error('設定したポート番号が 1024 ~ 65525 (65535 ではない) の間に収まっているかを確認してください。')
        sys.exit(1)

    # 使用中のポートを取得
    # ref: https://qiita.com/skokado/items/6e76762c68866d73570b
    used_ports = [cast(Any, conn.laddr).port for conn in psutil.net_connections() if conn.status == 'LISTEN']

    # リッスンポートと同じポートが使われていたら、エラーを表示する
    # Akebi HTTPS Server のリッスンポートと Uvicorn のリッスンポートの両方をチェック
    if port in used_ports:
        logger.error(f'ポート {port} は他のプロセスで使われているため、KonomiTV を起動できません。')
        logger.error(f'重複して KonomiTV を起動していないか、他のソフトでポート {port} を使っていないかを確認してください。')
        sys.exit(1)
    if (port + 10) in used_ports:
        logger.error(f'ポート {port + 10} は他のプロセスで使われているため、KonomiTV を起動できません。')
        logger.error(f'重複して KonomiTV を起動していないか、他のソフトでポート {port + 10} を使っていないかを確認してください。')
        sys.exit(1)

    # ***** カスタム HTTPS 証明書/秘密鍵のバリデーション *****

    # カスタム HTTPS 証明書/秘密鍵が指定されているとき
    custom_https_certificate = []
    if CONFIG['server']['custom_https_certificate'] is not None and CONFIG['server']['custom_https_private_key'] is not None:
        if (Path(CONFIG['server']['custom_https_certificate']).is_file() is False or
            Path(CONFIG['server']['custom_https_private_key']).is_file() is False):
            logger.error('指定されたカスタム HTTPS 証明書/秘密鍵が存在しないため、KonomiTV を起動できません。')
            logger.error('正しいカスタム HTTPS 証明書/秘密鍵のパスを指定しているかを確認してください。')
            sys.exit(1)
        # 追加の引数リスト
        custom_https_certificate = [
            '--custom-certificate', CONFIG['server']['custom_https_certificate'],
            '--custom-private-key', CONFIG['server']['custom_https_private_key'],
        ]

    # ***** サーバー設定のバリデーション *****

    ## リッスンポートとカスタム HTTPS 証明書/秘密鍵はすでにバリデーション済み
    ## Pydantic のエラーメッセージだけだと分かりづらいので、よくありがちな上2つのエラーに関しては別でエラーメッセージを用意している
    try:
        from app import models  # magic!! (ここでインポートしておかないと app.utils の参照時にエラーが発生する)  # type: ignore
        from app.schemas import ServerSettings
        ServerSettings(**cast(Any, CONFIG))
    except ValidationError as error:
        logger.error('設定内容が不正なため、KonomiTV を起動できません。')
        logger.error('以下のエラーメッセージを参考に、config.yaml の記述が正しいかを確認してください。')
        logger.error(error)
        sys.exit(1)

    # ***** ハードウェアエンコーダーのバリデーション *****

    # HWEncC が指定されているときのみ、--check-hw でハードウェアエンコーダーが利用できるかをチェック
    ## もし利用可能なら標準出力に "H.264/AVC" という文字列が出力されるので、それで判定する
    if CONFIG['general']['encoder'] != 'FFmpeg':
        result = subprocess.run(
            [LIBRARY_PATH[CONFIG['general']['encoder']], '--check-hw'],
            stdout = subprocess.PIPE,
            stderr = subprocess.DEVNULL,
        )
        result_stdout = result.stdout.decode('utf-8')
        result_stdout = '\n'.join([line for line in result_stdout.split('\n') if 'reader:' not in line])
        if 'unavailable.' in result_stdout:
            logger.error(f'お使いの環境では {CONFIG["general"]["encoder"]} がサポートされていないため、KonomiTV を起動できません。')
            logger.error(f'別のエンコーダーを選択するか、{CONFIG["general"]["encoder"]} の動作環境を整備してください。')
            sys.exit(1)
        # H.265/HEVC に対応していない環境では、通信節約モードが利用できない旨を出力する
        if 'H.265/HEVC' not in result_stdout:
            logger.warning(f'お使いの環境では {CONFIG["general"]["encoder"]} での H.265/HEVC エンコードがサポートされていないため、通信節約モードは利用できません。')

    # ***** EDCB / Mirakurun バックエンドへの接続確認 *****

    # EDCB バックエンドの接続確認
    if CONFIG['general']['backend'] == 'EDCB':

        # ここでインポートしないと諸々インポート周りがこじれてしまう
        from app.utils.EDCB import CtrlCmdUtil
        from app.utils.EDCB import EDCBUtil

        # ホスト名またはポートが指定されていない
        if ((EDCBUtil.getEDCBHost() is None) or
            (EDCBUtil.getEDCBPort() is None and EDCBUtil.getEDCBHost() != 'edcb-namedpipe')):
            logger.error('URL 内にホスト名またはポートが指定されていません。')
            logger.error('EDCB の URL を間違えている可能性があります。')
            sys.exit(1)

        # サービス一覧が取得できるか試してみる
        edcb = CtrlCmdUtil()
        edcb.setConnectTimeOutSec(5)  # 5秒後にタイムアウト
        result = asyncio.run(edcb.sendEnumService())
        if result is None:
            logger.error(f'EDCB ({CONFIG["general"]["edcb_url"]}/) にアクセスできませんでした。')
            logger.error('EDCB が起動していないか、URL を間違えている可能性があります。')
            sys.exit(1)

    # Mirakurun バックエンドの接続確認
    elif CONFIG['general']['backend'] == 'Mirakurun':

        # 試しにリクエストを送り、200 (OK) が返ってきたときだけ有効な URL とみなす
        try:
            response = requests.get(
                url = f'{CONFIG["general"]["mirakurun_url"]}/api/version',
                headers = API_REQUEST_HEADERS,
                timeout = 20,  # 久々のアクセスだとどうも時間がかかることがあるため、ここだけタイムアウトを長めに設定
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            logger.error(f'Mirakurun ({CONFIG["general"]["mirakurun_url"]}/) にアクセスできませんでした。')
            logger.error('Mirakurun が起動していないか、URL を間違えている可能性があります。')
            sys.exit(1)
        if response.status_code != 200:
            logger.error(f'{CONFIG["general"]["mirakurun_url"]}/ は Mirakurun の URL ではありません。')
            logger.error('Mirakurun の URL を間違えている可能性があります。')
            sys.exit(1)

    # ***** KonomiTV サーバーを起動 *****

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
            creationflags = (subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0),  # コンソールなしで実行 (Windows)
        )

    # このプロセスが終了されたときに、HTTPS リバースプロキシも一緒に終了する
    atexit.register(lambda: reverse_proxy_process.terminate())

    # Uvicorn を自動リロードモードで起動するかのフラグ
    ## 基本的に開発時用で、コードを変更するとアプリケーションサーバーを自動で再起動してくれる
    is_reload: bool = args.reload
    if sys.platform == 'win32' and is_reload is True:
        logger.warning('Python の asyncio の技術的な制約により、Windows では自動リロードモードは事実上利用できません。')
        logger.warning('なお、外部プロセス実行を伴うストリーミング視聴を行わなければ一応 Windows でも機能します。')

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
        # ロギングの設定
        log_config = LOGGING_CONFIG,
        # インターフェイスとして ASGI3 を選択
        interface = 'asgi3',
        # HTTP プロトコルの実装として httptools を選択
        http = 'httptools',
        # イベントループの実装として Windows では asyncio 、それ以外では uvloop を選択
        loop = ('asyncio' if sys.platform == 'win32' else 'uvloop'),
    )

    # Uvicorn を起動
    ## 以降のサーバーの管理は ServerManager が行う
    from app.utils import ServerManager
    ServerManager.run(config)


if __name__ == '__main__':
    main()
