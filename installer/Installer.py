
import asyncio
import getpass
import ifaddr
import json
import os
import py7zr
import requests
import ruamel.yaml
import shutil
import subprocess
import tarfile
import tempfile
import urllib.parse
from pathlib import Path
from rich import box
from rich import print
from rich.padding import Padding
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from typing import Any, cast, Literal

from Utils import CreateBasicInfiniteProgress
from Utils import CreateDownloadProgress
from Utils import CreateDownloadInfiniteProgress
from Utils import CtrlCmdConnectionCheckUtil
from Utils import CustomPrompt
from Utils import SaveConfigYaml


def Installer(version: str) -> None:
    """
    KonomiTV のインストーラーの実装

    Args:
        version (str): KonomiTV をインストールするバージョン
    """

    # ***** KonomiTV をインストールするフォルダのパス *****

    table_02 = Table(expand=True, box=box.SQUARE, border_style=Style(color='#E33157'))
    table_02.add_column('02. KonomiTV をインストールするフォルダのパスを入力してください。')
    if os.name == 'nt':
        table_02.add_row('なお、C:\\Users・C:\\Program Files 以下と、日本語(全角)が含まれるパス、')
        table_02.add_row('半角スペースを含むパスは不具合の原因となるため、避けてください。')
        table_02.add_row('例: C:\\DTV\\KonomiTV')
    else:
        table_02.add_row('なお、日本語(全角)が含まれるパス、半角スペースを含むパスは不具合の原因となるため、避けてください。')
        table_02.add_row('例: /opt/KonomiTV')
    print(Padding(table_02, (1, 2, 1, 2)))

    # インストール先のフォルダを取得
    install_path: Path
    while True:

        # 入力プロンプト (バリデーションに失敗し続ける限り何度でも表示される)
        install_path = Path(CustomPrompt.ask('KonomiTV をインストールするフォルダのパス'))

        # バリデーション
        if install_path.is_absolute() is False:
            print(Padding('[red]インストール先のフォルダは絶対パスで入力してください。', (0, 2, 0, 2)))
            continue
        if install_path.exists():
            print(Padding('[red]インストール先のフォルダがすでに存在します。', (0, 2, 0, 2)))
            continue

        # インストール先のフォルダを作成できるかテスト
        try:
            install_path.mkdir(parents=True, exist_ok=False)
        except Exception as ex:
            print(ex)
            print(Padding('[red]インストール先のフォルダを作成できませんでした。', (0, 2, 0, 2)))
            continue
        install_path.rmdir()  # フォルダを作成できるか試すだけなので一旦消す

        # すべてのバリデーションを通過したのでループを抜ける
        break

    # ***** 利用するバックエンド *****

    table_03 = Table(expand=True, box=box.SQUARE, border_style=Style(color='#E33157'))
    table_03.add_column('03. 利用するバックエンドを EDCB・Mirakurun から選択してください。')
    table_03.add_row('バックエンドは、テレビチューナーへのアクセスや番組情報の取得などに利用します。')
    table_03.add_row('EDCB は、220122 以降のバージョンの xtne6f 版または tkntrec 版の EDCB にのみ対応しています。')
    table_03.add_row('KonomiTV と連携するには、別途 EDCB に事前の設定が必要です。')
    table_03.add_row('Mirakurun は、3.9.0 以降のバージョンを推奨します。3.8.0 以前でも動作しますが、非推奨です。')
    print(Padding(table_03, (1, 2, 1, 2)))

    # 利用するバックエンドを取得
    backend = cast(Literal['EDCB', 'Mirakurun'], CustomPrompt.ask('利用するバックエンド', default='EDCB', choices=['EDCB', 'Mirakurun']))

    # ***** EDCB (EpgTimerNW) の TCP API の URL *****

    edcb_url: str = ''
    mirakurun_url: str = ''
    if backend == 'EDCB':

        table_04 = Table(expand=True, box=box.SQUARE, border_style=Style(color='#E33157'))
        table_04.add_column('04. EDCB (EpgTimerNW) の TCP API の URL を入力してください。')
        table_04.add_row('tcp://192.168.1.11:4510/ のような形式の URL で指定します。')
        table_04.add_row('tcp://edcb-namedpipe/ と指定すると、TCP API の代わりに')
        table_04.add_row('名前付きパイプを使って通信します(同じ PC で EDCB が稼働している場合のみ)。')
        print(Padding(table_04, (1, 2, 1, 2)))

        # EDCB (EpgTimerNW) の TCP API の URL を取得
        while True:

            # 入力プロンプト (バリデーションに失敗し続ける限り何度でも表示される)
            ## 末尾のスラッシュは常に付与する
            edcb_url: str = CustomPrompt.ask('EDCB (EpgTimerNW) の TCP API の URL').rstrip('/') + '/'

            # バリデーション
            ## 入力された URL がちゃんとパースできるかを確認
            edcb_url_parse = urllib.parse.urlparse(edcb_url)
            if edcb_url_parse.scheme != 'tcp':
                print(Padding('[red]URL が不正です。EDCB の URL を間違えている可能性があります。', (0, 2, 0, 2)))
                continue
            if ((edcb_url_parse.hostname is None) or
                (edcb_url_parse.port is None and edcb_url_parse.hostname != 'edcb-namedpipe')):
                print(Padding('[red]URL 内にホスト名またはポートが指定されていません。\nEDCB の URL を間違えている可能性があります。', (0, 2, 0, 2)))
                continue
            edcb_host = edcb_url_parse.hostname
            edcb_port = edcb_url_parse.port
            ## 接続できたかの確認として、サービス一覧が取得できるか試してみる
            edcb = CtrlCmdConnectionCheckUtil(edcb_host, edcb_port)
            result = asyncio.run(edcb.sendEnumService())
            if result is None:
                print(Padding(
                    f'[red]EDCB ({edcb_url}) にアクセスできませんでした。\nEDCB が起動していないか、URL を間違えている可能性があります。',
                    pad = (0, 2, 0, 2),
                ))
                continue

            # すべてのバリデーションを通過したのでループを抜ける
            break

    # ***** Mirakurun の HTTP API の URL *****

    elif backend == 'Mirakurun':

        table_04 = Table(expand=True, box=box.SQUARE, border_style=Style(color='#E33157'))
        table_04.add_column('04. Mirakurun の HTTP API の URL を入力してください。')
        table_04.add_row('http://192.168.1.11:40772/ のような形式の URL で指定します。')
        print(Padding(table_04, (1, 2, 1, 2)))

        # Mirakurun の HTTP API の URL を取得
        while True:

            # 入力プロンプト (バリデーションに失敗し続ける限り何度でも表示される)
            ## 末尾のスラッシュは常に付与する
            mirakurun_url = CustomPrompt.ask('Mirakurun の HTTP API の URL').rstrip('/') + '/'

            # バリデーション
            ## 試しにリクエストを送り、200 (OK) が返ってきたときだけ有効な URL とみなす
            try:
                response = requests.get(f'{mirakurun_url.rstrip("/")}/api/version', timeout=3)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as ex:
                print(Padding(
                    f'[red]Mirakurun ({mirakurun_url}) にアクセスできませんでした。\n'
                    'Mirakurun が起動していないか、URL を間違えている可能性があります。',
                    pad = (0, 2, 0, 2),
                ))
                continue
            if response.status_code != 200:
                print(Padding(
                    f'[red]{mirakurun_url} は Mirakurun の URL ではありません。\n'
                    'Mirakurun の URL を間違えている可能性があります。',
                    pad = (0, 2, 0, 2),
                ))
                continue

            # すべてのバリデーションを通過したのでループを抜ける
            break

    # ***** 利用するエンコーダー *****

    # PC に接続されている GPU の型番を取得し、そこから QSVEncC / NVEncC / VCEEncC の利用可否を大まかに判断する
    gpu_names: list[str] = []
    qsvencc_available: str = '❌利用できません'
    nvencc_available: str = '❌利用できません'
    vceencc_available: str = '❌利用できません'

    # Windows: PowerShell の Get-WmiObject と ConvertTo-Json の合わせ技で取得できる
    if os.name == 'nt':
        gpu_info_json = subprocess.run(
            args = ['powershell', '-Command', 'Get-WmiObject Win32_VideoController | ConvertTo-Json'],
            stdout = subprocess.PIPE,  # 標準出力をキャプチャする
            stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            text = True,  # 出力をテキストとして取得する
        )
        # コマンド成功時のみ
        if gpu_info_json.returncode == 0:
            # GPU が1個しか接続されないときは直接 dict[str, Any] に、2個以上あるときは list[dict[str, Any]] で出力されるので、場合分け
            gpu_info_data = json.loads(gpu_info_json.stdout)
            gpu_infos: list[dict[str, Any]]
            if type(gpu_info_data is dict):
                gpu_infos = [gpu_info_data]
            else:
                gpu_infos = gpu_info_data
            # 接続されている GPU 名を取得してリストに追加
            for gpu_info in gpu_infos:
                gpu_names.append(gpu_info['Name'])

    # Linux: lshw コマンドを使って取得できる
    else:
        gpu_info_json = subprocess.run(
            args = ['lshw', '-class', 'display', '-json'],
            stdout = subprocess.PIPE,  # 標準出力をキャプチャする
            stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            text = True,  # 出力をテキストとして取得する
        )
        # コマンド成功時のみ
        if gpu_info_json.returncode == 0:
            # 接続されている GPU 名を取得してリストに追加
            for gpu_info in json.loads(gpu_info_json.stdout):
                gpu_names.append(f'{gpu_info["vendor"]} {gpu_info["product"]}')

    # Intel 製 GPU なら QSVEncC が、NVIDIA 製 GPU (Geforce) なら NVEncC が、AMD 製 GPU (Radeon) なら VCEEncC が使える
    ## もちろん機種によって例外はあるけど、ダウンロード前だとこれくらいの大雑把な判定しかできない…
    ## VCEEncC は安定性があまり良くなく、NVEncC は性能は良いものの Geforce だと同時エンコード本数の制限があるので、
    ## 複数の GPU が接続されている場合は QSVEncC が一番優先されるようにする
    default_encoder: Literal['FFmpeg', 'QSVEncC', 'NVEncC', 'VCEEncC'] = 'FFmpeg'
    for gpu_name in gpu_names:
        if 'AMD' in gpu_name or 'Radeon' in gpu_name:
            vceencc_available = f'✅利用できます (AMD GPU: {gpu_name})'
            default_encoder = 'VCEEncC'
        elif 'NVIDIA' in gpu_name or 'Geforce' in gpu_name:
            nvencc_available = f'✅利用できます (NVIDIA GPU: {gpu_name})'
            default_encoder = 'NVEncC'
        elif 'Intel' in gpu_name:
            qsvencc_available = f'✅利用できます (Intel GPU: {gpu_name})'
            default_encoder = 'QSVEncC'

    table_05 = Table(expand=True, box=box.SQUARE, border_style=Style(color='#E33157'))
    table_05.add_column('05. 利用するエンコーダーを FFmpeg・QSVEncC・NVEncC・VCEEncC から選択してください。')
    table_05.add_row('FFmpeg はソフトウェアエンコーダーです。')
    table_05.add_row('すべての PC で利用できますが、CPU に多大な負荷がかかり、パフォーマンスが悪いです。')
    table_05.add_row('QSVEncC・NVEncC・VCEEncC はハードウェアエンコーダーです。')
    table_05.add_row('FFmpeg と比較して CPU 負荷が低く、パフォーマンスがとても高いです（おすすめ）。')
    table_05.add_row(Rule(characters='─', style=Style(color='#E33157')))
    table_05.add_row(f'QSVEncC: {qsvencc_available}')
    table_05.add_row(f'NVEncC : {nvencc_available}')
    table_05.add_row(f'VCEEncC: {vceencc_available}')
    print(Padding(table_05, (1, 2, 1, 2)))

    # 利用するエンコーダーを取得
    encoder = cast(
        Literal['FFmpeg', 'QSVEncC', 'NVEncC', 'VCEEncC'],
        CustomPrompt.ask('利用するエンコーダー', default=default_encoder, choices=['FFmpeg', 'QSVEncC', 'NVEncC', 'VCEEncC']),
    )

    # ***** アップロードしたキャプチャ画像の保存先フォルダのパス *****

    table_06 = Table(expand=True, box=box.SQUARE, border_style=Style(color='#E33157'))
    table_06.add_column('06.  アップロードしたキャプチャ画像の保存先フォルダのパスを入力してください。')
    table_06.add_row('クライアントの [キャプチャの保存先] 設定で [KonomiTV サーバーにアップロード] または')
    table_06.add_row('[ブラウザでのダウンロードと、KonomiTV サーバーへのアップロードを両方行う] を選択したときに利用されます。')
    if os.name == 'nt':
        table_06.add_row('例: E:\\TV-Capture')
    else:
        table_06.add_row('例: /mnt/hdd/TV-Capture')
    print(Padding(table_06, (1, 2, 1, 2)))

    # キャプチャ画像の保存先フォルダのパスを取得
    capture_upload_folder: Path
    while True:

        # 入力プロンプト (バリデーションに失敗し続ける限り何度でも表示される)
        capture_upload_folder = Path(CustomPrompt.ask('アップロードしたキャプチャ画像の保存先フォルダのパス'))

        # バリデーション
        if capture_upload_folder.is_absolute() is False:
            print(Padding('[red]アップロードしたキャプチャ画像の保存先フォルダは絶対パスで入力してください。', (0, 2, 0, 2)))
            continue
        if capture_upload_folder.exists() is False:
            print(Padding('[red]アップロードしたキャプチャ画像の保存先フォルダが存在しません。', (0, 2, 0, 2)))
            continue

        # すべてのバリデーションを通過したのでループを抜ける
        break

    # ***** ソースコードのダウンロード *****

    # ソースコードを随時ダウンロードし、進捗を表示
    # ref: https://github.com/Textualize/rich/blob/master/examples/downloader.py
    print(Padding('KonomiTV のソースコードをダウンロードしています…', (1, 2, 0, 2)))
    progress = CreateDownloadInfiniteProgress()

    # GitHub からソースコードをダウンロード
    # source_code_response = requests.get(f'https://codeload.github.com/tsukumijima/KonomiTV/zip/refs/tags/{version}')
    source_code_response = requests.get('https://github.com/tsukumijima/KonomiTV/archive/refs/heads/master.zip')
    task_id = progress.add_task('', total=None)

    # ダウンロードしたデータを随時一時ファイルに書き込む
    source_code_file = tempfile.NamedTemporaryFile(mode='wb', delete=False)
    with progress:
        for chunk in source_code_response.iter_content(chunk_size=1024):
            source_code_file.write(chunk)
            progress.update(task_id, advance=len(chunk))
    source_code_file.close()  # 解凍する前に close() してすべて書き込ませておくのが重要

    # ソースコードを解凍して展開
    shutil.unpack_archive(source_code_file.name, install_path.parent, format='zip')
    # shutil.move(install_path.parent / f'KonomiTV-{version}', install_path)
    shutil.move(install_path.parent / 'KonomiTV-master', install_path)
    Path(source_code_file.name).unlink()

    # ***** サードパーティーライブラリのダウンロード *****

    # サードパーティーライブラリを随時ダウンロードし、進捗を表示
    # ref: https://github.com/Textualize/rich/blob/master/examples/downloader.py
    print(Padding('サードパーティーライブラリをダウンロードしています…', (1, 2, 0, 2)))
    progress = CreateDownloadProgress()

    # GitHub からサードパーティーライブラリをダウンロード
    thirdparty_base_url = 'https://github.com/tsukumijima/Storehouse/releases/download/KonomiTV-Thirdparty-Libraries-Prerelease/'
    thirdparty_url = thirdparty_base_url + ('thirdparty-windows.7z' if os.name == 'nt' else 'thirdparty-linux.7z')
    thirdparty_response = requests.get(thirdparty_url, stream=True)
    task_id = progress.add_task('', total=float(thirdparty_response.headers['Content-length']))

    # ダウンロードしたデータを随時一時ファイルに書き込む
    thirdparty_file = tempfile.NamedTemporaryFile(mode='wb', delete=False)
    with progress:
        for chunk in thirdparty_response.iter_content(chunk_size=1048576):  # サイズが大きいので1MBごとに読み込み
            thirdparty_file.write(chunk)
            progress.update(task_id, advance=len(chunk))
    thirdparty_file.close()  # 解凍する前に close() してすべて書き込ませておくのが重要

    # サードパーティライブラリを解凍して展開
    print(Padding('サードパーティーライブラリを解凍しています… (数十秒かかります)', (1, 2, 0, 2)))
    progress = CreateBasicInfiniteProgress()
    progress.add_task('', total=None)
    with progress:
        if os.name == 'nt':
            # Windows: 7-Zip 形式のアーカイブを解凍
            with py7zr.SevenZipFile(thirdparty_file.name, mode='r') as seven_zip:
                seven_zip.extractall(install_path / 'server/')
        else:
            # Linux: tar.xz 形式のアーカイブを解凍
            # 7-Zip だと (おそらく) ファイルパーミッションを保持したまま圧縮することができない？ため、あえて tar.xz を使っている
            with tarfile.open(thirdparty_file.name, mode='r:xz') as tar_xz:
                tar_xz.extractall(install_path / 'server/')
        Path(thirdparty_file.name).unlink()

    # ***** pipenv 環境の構築 (依存パッケージのインストール) *****

    # Python の実行ファイルのパス (Windows と Linux で異なる)
    if os.name == 'nt':
        python_executable_path = install_path / 'server/thirdparty/Python/python.exe'
    else:
        python_executable_path = install_path / 'server/thirdparty/Python/bin/python'

    # pipenv sync を実行
    ## server/.venv/ に pipenv の仮想環境を構築するため、PIPENV_VENV_IN_PROJECT 環境変数をセットした状態で実行している
    print(Padding('依存パッケージをインストールしています…', (1, 2, 1, 2)))
    print(Rule(style=Style(color='cyan'), align='center'))
    environment = os.environ.copy()
    environment['PIPENV_VENV_IN_PROJECT'] = 'true'
    subprocess.run(
        args = [python_executable_path, '-m', 'pipenv', 'sync', f'--python={python_executable_path}'],
        cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
        env = environment,  # 環境変数を設定
    )
    print(Rule(style=Style(color='cyan'), align='center'))

    # ***** データベースのアップグレード *****

    print(Padding('データベースをアップグレードしています…', (1, 2, 0, 2)))
    progress = CreateBasicInfiniteProgress()
    progress.add_task('', total=None)
    with progress:
        subprocess.run(
            args = [python_executable_path, '-m', 'pipenv', 'run' 'aerich' 'upgrade'],
            cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
            stdout = subprocess.DEVNULL,  # 標準出力を表示しない
            stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
        )

    # ***** 環境設定ファイルの生成 *****

    print(Padding('環境設定ファイルを生成しています…', (1, 2, 0, 2)))
    progress = CreateBasicInfiniteProgress()
    progress.add_task('', total=None)
    with progress:

        # config.example.yaml を config.yaml にコピー
        shutil.copyfile(install_path / 'config.example.yaml', install_path / 'config.yaml')

        # config.yaml から既定の設定値を取得
        config_data: dict[str, dict[str, int | float | bool | str | None]]
        with open(install_path / 'config.yaml', mode='r', encoding='utf-8') as fp:
            config_data = dict(ruamel.yaml.YAML().load(fp))

        # 環境設定データの一部を事前に取得しておいた値で置き換え
        ## インストーラーで置換するのはバックエンドや EDCB / Mirakurun の URL など、サーバーの起動に不可欠な値のみ
        config_data['general']['backend'] = backend
        if backend == 'EDCB':
            config_data['general']['edcb_url'] = edcb_url
        elif backend == 'Mirakurun':
            config_data['general']['mirakurun_url'] = mirakurun_url
        config_data['general']['encoder'] = encoder
        config_data['capture']['upload_folder'] = str(capture_upload_folder)

        # 環境設定データを保存
        SaveConfigYaml(install_path / 'config.yaml', config_data)

    # ***** Windows: Windows サービスのインストール *****

    if os.name == 'nt':

        # 現在ログオン中のユーザー名を取得
        current_user_name = getpass.getuser()

        table_07 = Table(expand=True, box=box.SQUARE, border_style=Style(color='#E33157'))
        table_07.add_column(f'07. ログオン中のユーザー ({current_user_name}) のパスワードを入力してください。')
        table_07.add_row('KonomiTV の Windows サービスをユーザー権限で起動するために利用します。')
        table_07.add_row('入力されたパスワードがそれ以外の用途に利用されることはありません。')
        table_07.add_row('間違ったパスワードを入力すると、KonomiTV が起動できなくなります。')
        table_07.add_row('Enter キーを押す前に、正しいパスワードかどうか今一度確認してください。')
        print(Padding(table_07, (1, 2, 1, 2)))

        # 現在ログオン中のユーザーのパスワードを取得
        while True:

            # 入力プロンプト (サービスのインストールに失敗し続ける限り何度でも表示される)
            ## バリデーションのしようがないので、バリデーションは行わない
            current_user_password = CustomPrompt.ask(f'ログオン中のユーザー ({current_user_name}) のパスワード')

            # 入力された資格情報をもとに、Windows サービスをインストール
            ## すでに KonomiTV Service がインストールされている場合は上書きされる
            print(Padding('Windows サービスをインストールしています…', (1, 2, 0, 2)))
            progress = CreateBasicInfiniteProgress()
            progress.add_task('', total=None)
            with progress:
                service_install_result = subprocess.run(
                    args = [
                        python_executable_path, '-m', 'pipenv', 'run' 'python' 'KonomiTV-Service.py',
                        '--install', current_user_name, '--password', current_user_password,
                    ],
                    cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                    stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                    stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
                    text = True,  # 出力をテキストとして取得する
                )

            # Windows サービスのインストールに失敗
            if 'Error installing service' in service_install_result.stdout:
                print(Padding(
                    '[red]Windows サービスのインストールに失敗しました。'
                    '入力されたログオン中ユーザーのパスワードが間違っている可能性があります。',
                    pad = (1, 2, 1, 2),
                ))
                continue

            # Windows サービスを起動
            print(Padding('Windows サービスを起動しています…', (1, 2, 0, 2)))
            progress = CreateBasicInfiniteProgress()
            progress.add_task('', total=None)
            with progress:
                service_start_result = subprocess.run(
                    args = [python_executable_path, '-m', 'pipenv', 'run' 'python' 'KonomiTV-Service.py', 'start'],
                    cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                    stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                    stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
                    text = True,  # 出力をテキストとして取得する
                )

            # Windows サービスの起動に失敗
            if 'Error starting service' in service_start_result.stdout:
                print(Padding(
                    '[red]Windows サービスの起動に失敗しました。'
                    '入力されたログオン中ユーザーのパスワードが間違っている可能性があります。',
                    pad = (0, 2, 0, 2),
                ))
                continue

            # エラーが出ていなければおそらく正常にサービスがインストールできているはずなので、ループを抜ける
            break

    # ***** Linux: PM2 サービスのインストール *****

    else:

        # PM2 サービスをインストール
        ## インストーラーは強制的に root 権限で実行されるので、ここで実行する PM2 も root ユーザーとして動いているものになる
        ## Mirakurun や EPGStation 同様、PM2 はユーザー権限よりも root 権限で動かしたほうが何かとよさそう
        print(Padding('PM2 サービスをインストールしています…', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:
            subprocess.run(
                args = ['/usr/bin/env', 'pm2', 'start', '.venv/bin/python', '--name' 'KonomiTV' '--' 'KonomiTV.py'],
                cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            )
            subprocess.run(
                args = ['/usr/bin/env', 'pm2', 'save'],
                cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            )

        # PM2 サービスを起動
        print(Padding('PM2 サービスを起動しています…', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:
            subprocess.run(
                args = ['/usr/bin/env', 'pm2', 'start', 'KonomiTV'],
                cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            )

    # IPv4 かつループバックアドレスとリンクローカルアドレスでない IP アドレスを取得
    ip_addresses: list[tuple[str, str]] = []
    for nic in ifaddr.get_adapters():
        for ip in nic.ips:
            if ip.is_IPv4:
                # ループバック (127.x.x.x) とリンクローカル (169.254.x.x) を除外
                if cast(str, ip.ip).startswith('127.') is False and cast(str, ip.ip).startswith('169.254.') is False:
                    ip_addresses.append((cast(str, ip.ip), ip.nice_name))  # IP アドレスとインターフェイス名

    # IP アドレス昇順でソート
    ip_addresses.sort(key=lambda key: key[0])

    # インストール完了メッセージを表示
    table_07 = Table(expand=True, box=box.SQUARE, border_style=Style(color='#E33157'))
    table_07.add_column(
        'インストールが完了しました！🎉🎊 すぐに使いはじめられます！🎈\n'
        '下記の URL から、KonomiTV の Web UI にアクセスしてみましょう！\n'
        'ブラウザで [アプリをインストール] または [ホーム画面に追加] を押すと、\n'
        'ショートカットやホーム画面からすぐに KonomiTV にアクセスできます！',
    )

    # アクセス可能な URL のリストを IP アドレスごとに表示
    ## ローカルホスト (127.0.0.1) だけは https://my.local.konomi.tv:7000/ というエイリアスが使える
    urls = [f'https://{ip_address[0].replace(".", "-")}.local.konomi.tv:7000/' for ip_address in ip_addresses]
    table_07.add_row(f'{"https://my.local.konomi.tv:7000/": <{max([len(url) for url in urls])}} (ローカルホスト)')
    for index, url in enumerate(urls):
        table_07.add_row(f'{url: <{max([len(url) for url in urls])}} ({ip_addresses[index][1]})')

    print(Padding(table_07, (1, 2, 0, 2)))
