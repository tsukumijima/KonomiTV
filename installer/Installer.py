
import asyncio
import getpass
import ifaddr
import json
import os
import psutil
import py7zr
import re
import requests
import ruamel.yaml
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.parse
from pathlib import Path
from rich import box
from rich import print
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from typing import Any, cast, Literal
from watchdog.events import FileCreatedEvent
from watchdog.events import FileModifiedEvent
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from Utils import CreateBasicInfiniteProgress
from Utils import CreateDownloadProgress
from Utils import CreateDownloadInfiniteProgress
from Utils import CtrlCmdConnectionCheckUtil
from Utils import CustomConfirm
from Utils import CustomPrompt
from Utils import IsDockerComposeV2
from Utils import IsDockerInstalled
from Utils import IsGitInstalled
from Utils import RemoveEmojiIfLegacyTerminal
from Utils import SaveConfigYaml


def Installer(version: str) -> None:
    """
    KonomiTV のインストーラーの実装

    Args:
        version (str): KonomiTV をインストールするバージョン
    """

    # プラットフォームタイプ
    ## Windows・Linux・Linux (Docker)
    platform_type: Literal['Windows', 'Linux', 'Linux-Docker'] = 'Windows' if os.name == 'nt' else 'Linux'

    # Linux: Docker がインストールされている場合、Docker + Docker Compose を使ってインストールするかを訊く
    if platform_type == 'Linux':

        is_install_with_docker: bool = False

        # Docker + Docker Compose がインストールされているかを検出
        is_docker_installed = IsDockerInstalled()
        if is_docker_installed is True:
            print(Padding(Panel(
                'お使いの PC には Docker と Docker Compose がインストールされています。\n'
                'Docker + Docker Compose を使ってインストールしますか？',
                box = box.SQUARE,
                border_style = Style(color='#E33157'),
            ), (1, 2, 1, 2)))

            # Docker を使ってインストールするかを訊く (Y/N)
            is_install_with_docker = bool(CustomConfirm.ask('Docker + Docker Compose でインストールする', default=True))
            if is_install_with_docker is True:
                platform_type = 'Linux-Docker'  # プラットフォームタイプを Linux-Docker にセット

        # Docker 使ってインストールしない場合、pm2 コマンドがインストールされていなければここで終了する
        ## PM2 がインストールされていないと PM2 サービスでの自動起動ができないため
        if is_install_with_docker is False:
            result = subprocess.run(
                args = ['/usr/bin/bash', '-c', 'type pm2'],
                stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            )
            if result.returncode != 0:
                print(Padding(Panel(
                    '[yellow]KonomiTV を Docker を使わずにインストールするには PM2 が必要です。[/yellow]\n'
                    'PM2 は、KonomiTV サービスのプロセスマネージャーとして利用しています。\n'
                    'Node.js が導入されていれば、[cyan]sudo npm install -g pm2[/cyan] でインストールできます。',
                    box = box.SQUARE,
                    border_style = Style(color='#E33157'),
                ), (1, 2, 0, 2)))
                return  # 処理中断

    # Docker Compose V2 かどうかでコマンド名を変える
    ## Docker Compose V1 は docker-compose 、V2 は docker compose という違いがある
    ## Docker がインストールされていない場合は V1 のコマンドが代入されるが、そもそも非 Docker インストールでは参照されない
    docker_compose_command = ['docker-compose'] if IsDockerComposeV2() else ['docker', 'compose']

    # ***** KonomiTV をインストールするフォルダのパス *****

    table_02 = Table(expand=True, box=box.SQUARE, border_style=Style(color='#E33157'))
    table_02.add_column('02. KonomiTV をインストールするフォルダのパスを入力してください。')
    if platform_type == 'Windows':
        table_02.add_row('なお、C:\\Users・C:\\Program Files 以下と、日本語(全角)が含まれるパス、')
        table_02.add_row('半角スペースを含むパスは不具合の原因となるため、避けてください。')
        table_02.add_row('例: C:\\DTV\\KonomiTV')
    elif platform_type == 'Linux' or platform_type == 'Linux-Docker':
        table_02.add_row('なお、日本語(全角)が含まれるパス、半角スペースを含むパスは')
        table_02.add_row('不具合の原因となるため、避けてください。')
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
    table_03.add_row('EDCB は、220122 以降のバージョンの xtne6f / tkntrec 版の EDCB にのみ対応しています。')
    table_03.add_row('KonomiTV と連携するには、別途 EDCB に事前の設定が必要です。')
    table_03.add_row('Mirakurun は、3.9.0 以降のバージョンを推奨します。')
    table_03.add_row('3.8.0 以下のバージョンでも動作しますが、諸問題で推奨しません。')
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
        table_04.add_row('EDCB と同じ PC に KonomiTV をインストールしようとしている場合は、')
        table_04.add_row('tcp://localhost:4510/ または tcp://127.0.0.1:4510/ と入力してください。')
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
                print(Padding(str(
                    f'[red]EDCB ({edcb_url}) にアクセスできませんでした。\nEDCB が起動していないか、URL を間違えている可能性があります。',
                ), (0, 2, 0, 2)))
                continue

            # すべてのバリデーションを通過したのでループを抜ける
            break

    # ***** Mirakurun の HTTP API の URL *****

    elif backend == 'Mirakurun':

        table_04 = Table(expand=True, box=box.SQUARE, border_style=Style(color='#E33157'))
        table_04.add_column('04. Mirakurun の HTTP API の URL を入力してください。')
        table_04.add_row('http://192.168.1.11:40772/ のような形式の URL で指定します。')
        table_04.add_row('Mirakurun と同じ PC に KonomiTV をインストールしようとしている場合は、')
        table_04.add_row('http://localhost:40772/ または http://127.0.0.1:40772/ と入力してください。')
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
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.InvalidURL,
                requests.exceptions.MissingSchema,
                requests.exceptions.Timeout,
            ) as ex:
                print(Padding(str(
                    f'[red]Mirakurun ({mirakurun_url}) にアクセスできませんでした。\n'
                    'Mirakurun が起動していないか、URL を間違えている可能性があります。',
                ), (0, 2, 0, 2)))
                continue
            if response.status_code != 200:
                print(Padding(str(
                    f'[red]{mirakurun_url} は Mirakurun の URL ではありません。\n'
                    'Mirakurun の URL を間違えている可能性があります。',
                ), (0, 2, 0, 2)))
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
    if platform_type == 'Windows':
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

    # Linux / Linux-Docker: lshw コマンドを使って取得できる
    elif platform_type == 'Linux' or platform_type == 'Linux-Docker':
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
    table_05.add_row(RemoveEmojiIfLegacyTerminal(f'QSVEncC: {qsvencc_available}'))
    table_05.add_row(RemoveEmojiIfLegacyTerminal(f'NVEncC : {nvencc_available}'))
    table_05.add_row(RemoveEmojiIfLegacyTerminal(f'VCEEncC: {vceencc_available}'))
    print(Padding(table_05, (1, 2, 1, 2)))

    # 利用するエンコーダーを取得
    encoder = cast(
        Literal['FFmpeg', 'QSVEncC', 'NVEncC', 'VCEEncC'],
        CustomPrompt.ask('利用するエンコーダー', default=default_encoder, choices=['FFmpeg', 'QSVEncC', 'NVEncC', 'VCEEncC']),
    )

    # ***** アップロードしたキャプチャ画像の保存先フォルダのパス *****

    table_06 = Table(expand=True, box=box.SQUARE, border_style=Style(color='#E33157'))
    table_06.add_column('06. アップロードしたキャプチャ画像の保存先フォルダのパスを入力してください。')
    table_06.add_row('クライアントの [キャプチャの保存先] 設定で [KonomiTV サーバーにアップロード] または')
    table_06.add_row('[ブラウザでのダウンロードと、KonomiTV サーバーへのアップロードを両方行う] を選択したときに利用されます。')
    if platform_type == 'Windows':
        table_06.add_row('例: E:\\TV-Capture')
    elif platform_type == 'Linux' or platform_type == 'Linux-Docker':
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

    # Git コマンドがインストールされているかどうか
    is_git_installed = IsGitInstalled()

    # Git コマンドがインストールされている場合: git clone でダウンロード
    if is_git_installed is True:

        # git clone でソースコードをダウンロード
        print(Padding('KonomiTV のソースコードを Git でダウンロードしています…', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:
            subprocess.run(
                # TODO: v0.6.0 リリース前に master から変更必須
                args = ['git', 'clone', '-b', 'master', 'https://github.com/tsukumijima/KonomiTV.git', install_path.name],
                cwd = install_path.parent,
                stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            )

    # Git コマンドがインストールされていない場合: zip でダウンロード
    else:

        # ソースコードを随時ダウンロードし、進捗を表示
        # ref: https://github.com/Textualize/rich/blob/master/examples/downloader.py
        print(Padding('KonomiTV のソースコードをダウンロードしています…', (1, 2, 0, 2)))
        progress = CreateDownloadInfiniteProgress()

        # GitHub からソースコードをダウンロード
        # TODO: v0.6.0 リリース前に変更必須
        #source_code_response = requests.get(f'https://codeload.github.com/tsukumijima/KonomiTV/zip/refs/tags/v{version}')
        source_code_response = requests.get('https://github.com/tsukumijima/KonomiTV/archive/refs/heads/master.zip')
        task_id = progress.add_task('', total=None)

        # ダウンロードしたデータを随時一時ファイルに書き込む
        source_code_file = tempfile.NamedTemporaryFile(mode='wb', delete=False)
        with progress:
            for chunk in source_code_response.iter_content(chunk_size=1024):
                source_code_file.write(chunk)
                progress.update(task_id, advance=len(chunk))
            source_code_file.seek(0, os.SEEK_END)
            progress.update(task_id, total=source_code_file.tell())
        source_code_file.close()  # 解凍する前に close() してすべて書き込ませておくのが重要

        # ソースコードを解凍して展開
        shutil.unpack_archive(source_code_file.name, install_path.parent, format='zip')
        #shutil.move(install_path.parent / f'KonomiTV-{version}', install_path)  # TODO: v0.6.0 リリース前に変更必須
        shutil.move(install_path.parent / 'KonomiTV-master', install_path)
        Path(source_code_file.name).unlink()

    # ***** リッスンポートの重複チェック *****

    # 使用中のポートを取得
    # ref: https://qiita.com/skokado/items/6e76762c68866d73570b
    used_ports = [cast(Any, conn.laddr).port for conn in psutil.net_connections() if conn.status == 'LISTEN']

    # 空いてるリッスンポートを探す
    ## 7000 ポートが空いていたら、それがそのまま使われる
    server_port: int = 7000
    while True:

        # ポート 7000 (Akebi HTTPS Server) または 7010 (Uvicorn) が既に使われている場合
        ## リッスンポートを +100 して次のループへ
        if server_port in used_ports or (server_port + 10) in used_ports:
            server_port += 100  # +100 ずつ足していく
            continue

        # server_port が未使用のポートになったタイミングでループを抜ける
        break

    # 結果的にデフォルトのリッスンポートが 7000 以外になった場合の注意メッセージ
    if server_port != 7000:
        print(Padding(Panel(
            '[yellow]注意: デフォルトのリッスンポート (7000) がほかのサーバーソフトと重複しています。[/yellow]\n'
            f'代わりのリッスンポートとして、ポート {server_port} を選択します。\n'
            'リッスンポートは、config.yaml を編集すると変更できます。',
            box = box.SQUARE,
            border_style = Style(color='#E33157'),
        ), (1, 2, 0, 2)))

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
        config_data['server']['port'] = server_port
        config_data['capture']['upload_folder'] = str(capture_upload_folder)

        # 環境設定データを保存
        SaveConfigYaml(install_path / 'config.yaml', config_data)

    # Windows・Linux: KonomiTV のインストール処理
    ## Linux-Docker では Docker イメージの構築時に各種インストール処理も行われるため、実行の必要がない
    python_executable_path = ''
    if platform_type == 'Windows' or platform_type == 'Linux':

        # ***** サードパーティーライブラリのダウンロード *****

        # サードパーティーライブラリを随時ダウンロードし、進捗を表示
        # ref: https://github.com/Textualize/rich/blob/master/examples/downloader.py
        print(Padding('サードパーティーライブラリをダウンロードしています…', (1, 2, 0, 2)))
        progress = CreateDownloadProgress()

        # GitHub からサードパーティーライブラリをダウンロード
        #thirdparty_base_url = f'https://github.com/tsukumijima/KonomiTV/releases/download/v{version}/'  # TODO: v0.6.0 リリース前に変更必須
        thirdparty_base_url = 'https://github.com/tsukumijima/Storehouse/releases/download/KonomiTV-Thirdparty-Libraries-Prerelease/'
        thirdparty_url = thirdparty_base_url + ('thirdparty-windows.7z' if platform_type == 'Windows' else 'thirdparty-linux.tar.xz')
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
        print(Padding('サードパーティーライブラリを解凍しています… (数秒～数十秒かかります)', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:
            if platform_type == 'Windows':
                # Windows: 7-Zip 形式のアーカイブを解凍
                with py7zr.SevenZipFile(thirdparty_file.name, mode='r') as seven_zip:
                    seven_zip.extractall(install_path / 'server/')
            elif platform_type == 'Linux':
                # Linux: tar.xz 形式のアーカイブを解凍
                ## 7-Zip だと (おそらく) ファイルパーミッションを保持したまま圧縮することができない？ため、あえて tar.xz を使っている
                with tarfile.open(thirdparty_file.name, mode='r:xz') as tar_xz:
                    tar_xz.extractall(install_path / 'server/')
            Path(thirdparty_file.name).unlink()

        # ***** pipenv 環境の構築 (依存パッケージのインストール) *****

        # Python の実行ファイルのパス (Windows と Linux で異なる)
        if platform_type == 'Windows':
            python_executable_path = install_path / 'server/thirdparty/Python/python.exe'
        elif platform_type == 'Linux':
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
                args = [python_executable_path, '-m', 'pipenv', 'run', 'aerich', 'upgrade'],
                cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            )

    # Linux-Docker: docker-compose.yaml を生成し、Docker イメージをビルド
    elif platform_type == 'Linux-Docker':

        # ***** docker-compose.yaml の生成 *****

        print(Padding('docker-compose.yaml を生成しています…', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:

            # docker-compose.example.yaml を docker-compose.yaml にコピー
            shutil.copyfile(install_path / 'docker-compose.example.yaml', install_path / 'docker-compose.yaml')

            # NVEncC が利用できそうな場合、NVIDIA GPU が Docker コンテナ内で使えるように docker-compose.yaml の当該記述をコメントアウト
            ## NVIDIA GPU が使える環境以外でコメントアウトすると
            ## 正攻法で YAML でコメントアウトする方法が思いつかなかったので、正規表現でゴリ押し……
            if '✅利用できます' in nvencc_available:
                with open(install_path / 'docker-compose.yaml', mode='r', encoding='utf-8') as file:
                    text = file.read()
                replaced_text_1 = '            - driver: nvidia'
                replaced_text_2 = '              capabilities: [compute, utility, video]'
                text = re.sub(r'.*?#.*?- driver: nvidia', replaced_text_1, text)
                text = re.sub(r'.*?#.*?  capabilities: \[compute, utility, video\]', replaced_text_2, text)
                with open(install_path / 'docker-compose.yaml', mode='w', encoding='utf-8') as file:
                    file.write(text)

        # ***** Docker イメージのビルド *****

        # docker compose build --no-cache で Docker イメージをビルド
        ## 万が一以前ビルドしたキャッシュが残っていたときに備え、キャッシュを使わずにビルドさせる
        print(Padding('Docker イメージをビルドしています… (数分～数十分かかります)', (1, 2, 1, 2)))
        print(Rule(style=Style(color='cyan'), align='center'))
        subprocess.run(
            args = [*docker_compose_command, 'build', '--no-cache'],
            cwd = install_path,  # カレントディレクトリを KonomiTV のインストールフォルダに設定
        )
        print(Rule(style=Style(color='cyan'), align='center'))

    # ***** Linux / Linux-Docker: QSVEncC / NVEncC / VCEEncC の動作チェック *****

    if platform_type == 'Linux' or platform_type == 'Linux-Docker':

        # エンコーダーに QSVEncC が選択されているとき
        ## Linux-Docker では Docker イメージの中に Intel Media Driver が含まれているため、
        ## QSV が使える CPU であれば基本的に動作するはず (動作チェックはしない)
        if encoder == 'QSVEncC' and platform_type == 'Linux':

            # QSVEncC の --check-hw オプションの終了コードが 0 なら利用可能、それ以外なら利用不可
            result = subprocess.run(
                args = [install_path / 'server/thirdparty/QSVEncC/QSVEncC.elf', '--check-hw'],
                stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                stderr = subprocess.STDOUT,  # 標準エラー出力を標準出力にリダイレクト
                text = True,  # 出力をテキストとして取得する
            )

            # QSVEncC が利用できない結果になった場合は Intel Media Driver がインストールされていない可能性が高いので、
            # 適宜 Intel Media Driver をインストールするように催促する
            ## Intel Media Driver は iGPU 本体のものとは切り離されているので、インストールが比較的容易
            ## Intel Graphics そのもののドライバーは Linux カーネルに組み込まれている
            ## インストールコマンドが複雑なので、コマンド例を明示する
            if result.returncode != 0:
                print(Padding(Panel(
                    '[yellow]注意: この PC では QSVEncC が利用できない状態です。[/yellow]\n'
                    'Intel QSV の利用に必要な Intel Media Driver が\n'
                    'インストールされていない可能性があります。',
                    box = box.SQUARE,
                    border_style = Style(color='#E33157'),
                ), (1, 2, 0, 2)))
                print(Padding(Panel(
                    'Intel Media Driver は以下のコマンドでインストールできます。\n'
                    '[cyan]curl -fsSL https://repositories.intel.com/graphics/intel-graphics.key | gpg --dearmor -o /usr/share/keyrings/intel-graphics-keyring.gpg && echo \'deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics-keyring.gpg] https://repositories.intel.com/graphics/ubuntu focal main\' > /etc/apt/sources.list.d/intel-graphics.list && sudo apt update -y && sudo apt install -y intel-media-va-driver-non-free intel-opencl-icd[/cyan]',
                    box = box.SQUARE,
                    border_style = Style(color='#E33157'),
                ), (0, 2, 0, 2)))
                print(Padding(Panel(
                    'Alder Lake (第12世代) 以降の CPU では、追加で以下のコマンドを実行してください。\n'
                    'なお、libmfx-gen1.2 パッケージは Ubuntu 22.04 LTS にしか存在しないため、 \n'
                    'Ubuntu 20.04 LTS では、Alder Lake 以降の CPU の Intel QSV を利用できません。\n'
                    '[cyan]sudo apt install -y libmfx-gen1.2[/cyan]',
                    box = box.SQUARE,
                    border_style = Style(color='#E33157'),
                ), (0, 2, 0, 2)))
                print(Padding(Panel(
                    'QSVEncC のログ:\n' + result.stdout.strip(),
                    box = box.SQUARE,
                    border_style = Style(color='#E33157'),
                ), (0, 2, 0, 2)))

        # エンコーダーに NVEncC が選択されているとき
        elif encoder == 'NVEncC':

            # 実行コマンド (Linux-Docker では docker-compose run を介して実行する)
            command = [install_path / 'server/thirdparty/NVEncC/NVEncC.elf', '--check-hw']
            if platform_type == 'Linux-Docker':
                command = [*docker_compose_command, 'run', '--rm',
                    '--entrypoint', '/bin/bash -c "/code/server/thirdparty/NVEncC/NVEncC.elf --check-hw"', 'konomitv']

            # NVEncC の --check-hw オプションの終了コードが 0 なら利用可能、それ以外なら利用不可
            result = subprocess.run(
                args = command,
                stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                stderr = subprocess.STDOUT,  # 標準エラー出力を標準出力にリダイレクト
                text = True,  # 出力をテキストとして取得する
            )

            # NVEncC が利用できない結果になった場合はドライバーがインストールされていない or 古い可能性が高いので、
            # 適宜ドライバーをインストール/アップデートするように催促する
            ## NVEncC は NVIDIA Graphics Driver さえインストールされていれば動作する
            if result.returncode != 0:
                print(Padding(Panel(
                    '[yellow]注意: この PC では NVEncC が利用できない状態です。[/yellow]\n'
                    'NVENC の利用に必要な NVIDIA Graphics Driver がインストールされていないか、\n'
                    'NVIDIA Graphics Driver のバージョンが古い可能性があります。\n'
                    'NVIDIA Graphics Driver をインストール/最新バージョンに更新してください。',
                    box = box.SQUARE,
                    border_style = Style(color='#E33157'),
                ), (1, 2, 0, 2)))
                print(Padding(Panel(
                    'NVEncC のログ:\n' + result.stdout.strip(),
                    box = box.SQUARE,
                    border_style = Style(color='#E33157'),
                ), (0, 2, 0, 2)))

        # エンコーダーに VCEEncC が選択されているとき
        elif encoder == 'VCEEncC':

            # 実行コマンド (Linux-Docker では docker-compose run を介して実行する)
            command = [install_path / 'server/thirdparty/VCEEncC/VCEEncC.elf', '--check-hw']
            if platform_type == 'Linux-Docker':
                command = [*docker_compose_command, 'run', '--rm',
                    '--entrypoint', '/bin/bash -c "/code/server/thirdparty/VCEEncC/VCEEncC.elf --check-hw"', 'konomitv']

            # VCEEncC の --check-hw オプションの終了コードが 0 なら利用可能、それ以外なら利用不可
            result = subprocess.run(
                args = command,
                stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                stderr = subprocess.STDOUT,  # 標準エラー出力を標準出力にリダイレクト
                text = True,  # 出力をテキストとして取得する
            )

            # VCEEncC が利用できない結果になった場合はドライバーがインストールされていない or 古い可能性が高いので、
            # 適宜ドライバーをインストール/アップデートするように催促する
            ## VCEEncC は AMDGPU-PRO Driver さえインストールされていれば動作する
            if result.returncode != 0:
                print(Padding(Panel(
                    '[yellow]注意: この PC では VCEEncC が利用できない状態です。[/yellow]\n'
                    'AMD VCE の利用に必要な AMDGPU-PRO Driver がインストールされていないか、\n'
                    'AMDGPU-PRO Driver のバージョンが古い可能性があります。\n'
                    'AMDGPU-PRO Driver をインストール/最新バージョンに更新してください。\n'
                    'AMDGPU-PRO Driver のインストール方法は以下のページに記載されています。\n'
                    '[blue]https://github.com/rigaya/VCEEnc/blob/master/Install.ja.md#linux-ubuntu-2004[/blue]',
                    box = box.SQUARE,
                    border_style = Style(color='#E33157'),
                ), (1, 2, 0, 2)))
                print(Padding(Panel(
                    'VCEEncC のログ:\n' + result.stdout.strip(),
                    box = box.SQUARE,
                    border_style = Style(color='#E33157'),
                ), (0, 2, 0, 2)))

    # ***** Windows: Windows サービスのインストール・起動 *****

    if platform_type == 'Windows':

        # 現在ログオン中のユーザー名を取得
        current_user_name = getpass.getuser()

        table_07 = Table(expand=True, box=box.SQUARE, border_style=Style(color='#E33157'))
        table_07.add_column(f'07. ログオン中のユーザー ({current_user_name}) のパスワードを入力してください。')
        table_07.add_row('KonomiTV の Windows サービスを一般ユーザーの権限で起動するために利用します。')
        table_07.add_row('入力されたパスワードがそれ以外の用途に利用されることはありません。')
        table_07.add_row('間違ったパスワードを入力すると、KonomiTV が起動できなくなります。')
        table_07.add_row('Enter キーを押す前に、正しいパスワードかどうか今一度確認してください。')
        print(Padding(table_07, (1, 2, 1, 2)))

        # 現在ログオン中のユーザーのパスワードを取得
        while True:

            # 入力プロンプト (サービスのインストールに失敗し続ける限り何度でも表示される)
            ## バリデーションのしようがないので、バリデーションは行わない
            current_user_password = CustomPrompt.ask(f'ログオン中のユーザー ({current_user_name}) のパスワード')

            if current_user_password == '':
                print(Padding(f'[red]ログオン中のユーザー ({current_user_name}) のパスワードが空です。', (0, 2, 0, 2)))
                continue

            # 入力された資格情報をもとに、Windows サービスをインストール
            ## すでに KonomiTV Service がインストールされている場合は上書きされる
            print(Padding('Windows サービスをインストールしています…', (1, 2, 0, 2)))
            progress = CreateBasicInfiniteProgress()
            progress.add_task('', total=None)
            with progress:
                service_install_result = subprocess.run(
                    args = [
                        python_executable_path, '-m', 'pipenv', 'run', 'python', 'KonomiTV-Service.py', 'install',
                        '--username', current_user_name, '--password', current_user_password,
                    ],
                    cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                    stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                    stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
                    text = True,  # 出力をテキストとして取得する
                )

            # Windows サービスのインストールに失敗
            if 'Error installing service' in service_install_result.stdout:
                print(Padding(str(
                    '[red]Windows サービスのインストールに失敗しました。\n'
                    '入力されたログオン中ユーザーのパスワードが間違っている可能性があります。',
                ), (1, 2, 1, 2)))
                continue

            # Windows サービスを起動
            print(Padding('Windows サービスを起動しています…', (1, 2, 0, 2)))
            progress = CreateBasicInfiniteProgress()
            progress.add_task('', total=None)
            with progress:
                service_start_result = subprocess.run(
                    args = [python_executable_path, '-m', 'pipenv', 'run', 'python', 'KonomiTV-Service.py', 'start'],
                    cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                    stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                    stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
                    text = True,  # 出力をテキストとして取得する
                )

            # Windows サービスの起動に失敗
            if 'Error starting service' in service_start_result.stdout:
                print(Padding(str(
                    '[red]Windows サービスの起動に失敗しました。\n'
                    '入力されたログオン中ユーザーのパスワードが間違っている可能性があります。',
                ), (1, 2, 0, 2)))
                print(Padding('[red]エラーログ:\n' + service_start_result.stdout.strip(), (1, 2, 1, 2)))
                continue

            # エラーが出ていなければおそらく正常にサービスがインストールできているはずなので、ループを抜ける
            break

    # ***** Linux: PM2 サービスのインストール・起動 *****

    elif platform_type == 'Linux':

        # PM2 サービスをインストール
        ## インストーラーは強制的に root 権限で実行されるので、ここで実行する PM2 も root ユーザーとして動いているものになる
        ## Mirakurun や EPGStation 同様、PM2 はユーザー権限よりも root 権限で動かしたほうが何かとよさそう
        print(Padding('PM2 サービスをインストールしています…', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:
            subprocess.run(
                args = ['/usr/bin/env', 'pm2', 'start', '.venv/bin/python', '--name', 'KonomiTV', '--', 'KonomiTV.py'],
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

    # ***** Linux-Docker: Docker コンテナの起動 *****

    elif platform_type == 'Linux-Docker':

        print(Padding('Docker コンテナを起動しています…', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:

            # docker compose up -d --force-recreate で Docker コンテナを起動
            ## 念のためコンテナを強制的に再作成させる
            subprocess.run(
                args = [*docker_compose_command, 'up', '-d', '--force-recreate'],
                cwd = install_path,  # カレントディレクトリを KonomiTV のインストールフォルダに設定
                stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            )

    # ***** サービスの起動を待機 *****

    # サービスが起動したかのフラグ
    is_service_started = False

    # KonomiTV サーバーが（番組情報更新などを終えて）起動したかのフラグ
    is_server_started = False

    # ログフォルダ以下のファイルに変更があったときのイベントハンドラー
    class LogFolderWatchHandler(FileSystemEventHandler):

        # 何かしらログフォルダに新しいファイルが作成されたら、サービスが起動したものとみなす
        def on_created(self, event: FileCreatedEvent) -> None:
            nonlocal is_service_started
            is_service_started = True

        # ログファイルが更新されたら、ログの中に Application startup complete. という文字列が含まれていないかを探す
        # ログの中に Application startup complete. という文字列が含まれていたら、KonomiTV サーバーの起動が完了したとみなす
        def on_modified(self, event: FileModifiedEvent) -> None:
            # もし on_created をハンドリングできなかった場合に備え、on_modified でもサービス起動フラグを立てる
            nonlocal is_service_started, is_server_started
            is_service_started = True
            # ファイルのみに限定（フォルダの変更も検知されることがあるが、当然フォルダは開けないのでエラーになる）
            if Path(event.src_path).is_file() is True:
                with open(event.src_path, mode='r', encoding='utf-8') as log:
                    text = log.read()
                    if 'Application startup complete.' in text:
                        # このログが出力されているということはサーバーの起動が完了した事が想定されるので、サーバー起動フラグを立てる
                        is_server_started = True

    # Watchdog を起動
    observer = Observer()
    observer.schedule(LogFolderWatchHandler(), str(install_path / 'server/logs/'), recursive=True)
    observer.start()

    # サービスが起動するまで待つ
    print(Padding('サービスの起動を待っています… (時間がかかることがあります)', (1, 2, 0, 2)))
    progress = CreateBasicInfiniteProgress()
    progress.add_task('', total=None)
    with progress:
        while is_service_started is False:
            time.sleep(0.1)

    # KonomiTV サーバーが起動するまで待つ
    print(Padding('KonomiTV サーバーの起動を待っています… (数秒～数分かかります)', (1, 2, 0, 2)))
    progress = CreateBasicInfiniteProgress()
    progress.add_task('', total=None)
    with progress:
        while is_server_started is False:
            time.sleep(0.1)

    # ***** インストール完了 *****

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
    table_07.add_column(RemoveEmojiIfLegacyTerminal(
        'インストールが完了しました！🎉🎊 すぐに使いはじめられます！🎈\n'
        '下記の URL から、KonomiTV の Web UI にアクセスしてみましょう！\n'
        'ブラウザで [アプリをインストール] または [ホーム画面に追加] を押すと、\n'
        'ショートカットやホーム画面からすぐに KonomiTV にアクセスできます！\n'
        'もし KonomiTV にアクセスできない場合は、ファイアウォールの設定を確認してみてください。',
    ))

    # アクセス可能な URL のリストを IP アドレスごとに表示
    ## ローカルホスト (127.0.0.1) だけは https://my.local.konomi.tv:7000/ というエイリアスが使える
    urls = [f'https://{ip_address[0].replace(".", "-")}.local.konomi.tv:{server_port}/' for ip_address in ip_addresses]
    table_07.add_row(f'{f"https://my.local.konomi.tv:{server_port}/": <{max([len(url) for url in urls])}} (ローカルホスト)')
    for index, url in enumerate(urls):
        table_07.add_row(f'{url: <{max([len(url) for url in urls])}} ({ip_addresses[index][1]})')

    print(Padding(table_07, (1, 2, 0, 2)))
