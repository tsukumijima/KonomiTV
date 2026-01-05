
import asyncio
import json
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.parse
import zipfile
from pathlib import Path
from typing import Any, Literal, cast

import psutil
import py7zr
import requests
import ruamel.yaml
from rich import print
from rich.padding import Padding

from Utils import (
    CreateBasicInfiniteProgress,
    CreateDownloadInfiniteProgress,
    CreateDownloadProgress,
    CreateRule,
    CreateTable,
    CtrlCmdConnectionCheckUtil,
    CustomConfirm,
    CustomPrompt,
    GetNetworkInterfaceInformation,
    IsDockerComposeV2,
    IsDockerInstalled,
    IsGitInstalled,
    RemoveEmojiIfLegacyTerminal,
    RunKonomiTVServiceWaiter,
    RunSubprocess,
    RunSubprocessDirectLogOutput,
    SaveConfig,
    ShowPanel,
)


def Installer(version: str) -> None:
    """
    KonomiTV のインストーラーの実装

    Args:
        version (str): KonomiTV をインストールするバージョン
    """

    # プラットフォームタイプ
    ## Windows・Linux・Linux (Docker)
    platform_type: Literal['Windows', 'Linux', 'Linux-Docker'] = 'Windows' if os.name == 'nt' else 'Linux'

    # ARM デバイスかどうか
    is_arm_device = platform.machine() == 'aarch64'

    # Linux: Docker がインストールされている場合、Docker + Docker Compose を使ってインストールするかを訊く
    if platform_type == 'Linux':

        is_install_with_docker: bool = False

        # Docker + Docker Compose がインストールされているかを検出
        ## 現状 ARM 環境では Docker を使ったインストール方法はサポートしていない
        is_docker_installed = IsDockerInstalled()
        if is_docker_installed is True and is_arm_device is False:
            ShowPanel([
                f'お使いの PC には Docker と Docker Compose {"V2 以降" if IsDockerComposeV2() else "V1"} がインストールされています。',
                'Docker + Docker Compose を使ってインストールしますか？',
            ], padding=(1, 2, 1, 2))

            # Docker を使ってインストールするかを訊く (Y/N)
            is_install_with_docker = bool(CustomConfirm.ask('Docker + Docker Compose でインストールする', default=True))
            if is_install_with_docker is True:

                # プラットフォームタイプを Linux-Docker にセット
                platform_type = 'Linux-Docker'

                # Docker がインストールされているものの Docker サービスが停止している場合に備え、Docker サービスを起動しておく
                ## すでに起動している場合は何も起こらない
                subprocess.run(
                    args = ['systemctl', 'start', 'docker'],
                    stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                    stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
                )

        # Docker 使ってインストールしない場合、pm2 コマンドがインストールされていなければここで終了する
        ## PM2 がインストールされていないと PM2 サービスでの自動起動ができないため
        if is_install_with_docker is False:
            result = subprocess.run(
                args = ['/usr/bin/bash', '-c', 'type pm2'],
                stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            )
            if result.returncode != 0:
                ShowPanel([
                    '[yellow]KonomiTV を Docker を使わずにインストールするには PM2 が必要です。[/yellow]',
                    'PM2 は、KonomiTV サービスのプロセスマネージャーとして利用しています。',
                    'Node.js が導入されていれば、[cyan]sudo npm install -g pm2[/cyan] でインストールできます。',
                ])
                return  # 処理中断

    # Docker Compose V2 かどうかでコマンド名を変える
    ## Docker Compose V1 は docker-compose 、V2 は docker compose という違いがある
    ## Docker がインストールされていない場合は V1 のコマンドが代入されるが、そもそも非 Docker インストールでは参照されない
    docker_compose_command = ['docker', 'compose'] if IsDockerComposeV2() else ['docker-compose']

    # ***** KonomiTV をインストールするフォルダのパス *****

    table_02 = CreateTable()
    table_02.add_column('02. KonomiTV をインストールするフォルダのパスを入力してください。')
    table_02.add_row('インストール先のフォルダは、インストール時に自動で作成されます。')
    if platform_type == 'Windows':
        table_02.add_row('なお、C:\\Users・C:\\Program Files 以下と、日本語(全角)が含まれるパス、')
        table_02.add_row('半角スペースを含むパスは不具合の原因となるため、避けてください。')
        table_02.add_row('入力例: C:\\DTV\\KonomiTV')
    elif platform_type == 'Linux' or platform_type == 'Linux-Docker':
        table_02.add_row('なお、日本語(全角)が含まれるパス、半角スペースを含むパスは')
        table_02.add_row('不具合の原因となるため、避けてください。')
        table_02.add_row('入力例: /opt/KonomiTV')
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
        if '#' in str(install_path):
            print(Padding('[red]インストール先のパスには # を含めないでください。', (0, 2, 0, 2)))
            continue
        if install_path.exists():
            # 指定されたフォルダが空フォルダだったときは、ユーザーがわざわざ手動でインストール先のフォルダを
            # 作成してくれている可能性があるので、実装の都合上一度削除しつつ、バリデーションには引っかからないようにする
            ## rmdir() が中身が空のフォルダしか削除できず、中身が空でないフォルダを削除しようとすると
            ## OSError が発生するのを利用している
            try:
                # ここで削除が成功すれば空のフォルダだったことが確定するので、処理を続行
                install_path.rmdir()
            except OSError:
                # 削除に失敗した場合は中身が空でないフォルダ (=インストールしてはいけないフォルダ) という事が
                # 確定するので、もう一度パスを入力させる
                ## 中身が空でないフォルダにインストールしようとすると、当然ながら大変なことになる
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

    table_03 = CreateTable()
    table_03.add_column('03. 利用するバックエンドを EDCB・Mirakurun から選んで入力してください。')
    table_03.add_row('バックエンドは、テレビチューナーへのアクセスや番組情報の取得などに利用します。')
    table_03.add_row(CreateRule())
    table_03.add_row('EDCB は、220122 以降のバージョンの xtne6f / tkntrec 版の EDCB にのみ対応しています。')
    table_03.add_row('「人柱版10.66」などの古いバージョンをお使いの場合は、EDCB のアップグレードが必要です。')
    table_03.add_row('KonomiTV と連携するには、さらに EDCB に事前の設定が必要になります。')
    table_03.add_row('詳しくは [bright_blue]https://github.com/tsukumijima/KonomiTV[/bright_blue] をご覧ください。')
    table_03.add_row(CreateRule())
    table_03.add_row('Mirakurun は、3.9.0 以降のバージョンを推奨します。')
    table_03.add_row('3.8.0 以下のバージョンでも動作しますが、諸問題で推奨しません。')
    print(Padding(table_03, (1, 2, 1, 2)))

    # 利用するバックエンドを取得
    backend = cast(Literal['EDCB', 'Mirakurun'], CustomPrompt.ask('利用するバックエンド', default='EDCB', choices=['EDCB', 'Mirakurun']))

    # ***** EDCB (EpgTimerNW) の TCP API の URL *****

    edcb_url: str = ''
    mirakurun_url: str = ''
    if backend == 'EDCB':

        table_04 = CreateTable()
        table_04.add_column('04. EDCB (EpgTimerNW) の TCP API の URL を入力してください。')
        table_04.add_row('tcp://192.168.1.11:4510/ のような形式の URL で指定します。')
        table_04.add_row('EDCB と同じ PC に KonomiTV をインストールしようとしている場合は、')
        table_04.add_row('tcp://127.0.0.1:4510/ と入力してください。')
        table_04.add_row('tcp://edcb-namedpipe/ と指定すると、TCP API の代わりに')
        table_04.add_row('名前付きパイプを使って通信します(同じ PC で EDCB が稼働している場合のみ)。')
        print(Padding(table_04, (1, 2, 1, 2)))

        # EDCB (EpgTimerNW) の TCP API の URL を取得
        while True:

            # 入力プロンプト (バリデーションに失敗し続ける限り何度でも表示される)
            ## 末尾のスラッシュは常に付与する
            edcb_url: str = CustomPrompt.ask('EDCB (EpgTimerNW) の TCP API の URL').rstrip('/') + '/'
            ## localhost を 127.0.0.1 に置き換え (localhost だと一部 Windows 環境で TCP API への接続が遅くなる)
            edcb_url = edcb_url.replace('localhost', '127.0.0.1')

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
            ## 接続できたかの確認として、現在の EpgTimerSrv の動作ステータスを取得できるか試してみる
            edcb = CtrlCmdConnectionCheckUtil(edcb_host, edcb_port)
            result = asyncio.run(edcb.sendGetNotifySrvStatus())
            if result is None:
                print(Padding(str(
                    f'[red]EDCB ({edcb_url}) にアクセスできませんでした。\n'
                    'EDCB が起動していないか、URL を間違えている可能性があります。\n'
                    'また、EDCB の設定で [ネットワーク接続を許可する (EpgTimerNW 用)] に\n'
                    'チェックが入っているか確認してください。',
                ), (0, 2, 0, 2)))
                continue

            # すべてのバリデーションを通過したのでループを抜ける
            break

    # ***** Mirakurun / mirakc の HTTP API の URL *****

    elif backend == 'Mirakurun':

        table_04 = CreateTable()
        table_04.add_column('04. Mirakurun / mirakc の HTTP API の URL を入力してください。')
        table_04.add_row('http://192.168.1.11:40772/ のような形式の URL で指定します。')
        table_04.add_row('Mirakurun / mirakc と同じ PC に KonomiTV をインストールしようとしている場合は、')
        table_04.add_row('http://127.0.0.1:40772/ と入力してください。')
        print(Padding(table_04, (1, 2, 1, 2)))

        # Mirakurun / mirakc の HTTP API の URL を取得
        while True:

            # 入力プロンプト (バリデーションに失敗し続ける限り何度でも表示される)
            ## 末尾のスラッシュは常に付与する
            mirakurun_url = CustomPrompt.ask('Mirakurun / mirakc の HTTP API の URL').rstrip('/') + '/'
            ## localhost を 127.0.0.1 に置き換え (localhost だと一部 Windows 環境で TCP API への接続が遅くなる)
            mirakurun_url = mirakurun_url.replace('localhost', '127.0.0.1')

            # バリデーション
            ## 試しにリクエストを送り、200 (OK) が返ってきたときだけ有効な URL とみなす
            ## 10秒でタイムアウト
            try:
                response = requests.get(f'{mirakurun_url.rstrip("/")}/api/version', timeout=20)
            except Exception:
                print(Padding(str(
                    f'[red]Mirakurun / mirakc ({mirakurun_url}) にアクセスできませんでした。\n'
                    'Mirakurun / mirakc が起動していないか、URL を間違えている可能性があります。',
                ), (0, 2, 0, 2)))
                continue
            if response.status_code != 200:
                print(Padding(str(
                    f'[red]{mirakurun_url} は Mirakurun / mirakc の URL ではありません。\n'
                    'Mirakurun / mirakc の URL を間違えている可能性があります。',
                ), (0, 2, 0, 2)))
                continue

            # すべてのバリデーションを通過したのでループを抜ける
            break

    # ***** 利用するエンコーダー *****

    # PC に接続されている GPU の型番を取得し、そこから QSVEncC / NVEncC / VCEEncC の利用可否を大まかに判断する
    gpu_names: list[str] = []
    default_encoder: Literal['FFmpeg', 'QSVEncC', 'NVEncC', 'VCEEncC', 'rkmppenc'] = 'FFmpeg'
    qsvencc_available: str = '❌利用できません'
    nvencc_available: str = '❌利用できません'
    vceencc_available: str = '❌利用できません'
    rkmppenc_available: str = '❌利用できません'

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
            try:
                # GPU が1個だけ搭載されている環境では直接 dict[str, Any] 、2個以上搭載されている環境は list[dict[str, Any]] の形で出力される
                gpu_info_data = json.loads(gpu_info_json.stdout)
                gpu_infos: list[dict[str, Any]]
                if type(gpu_info_data) is dict:
                    # GPU が1個だけ搭載されている環境
                    gpu_infos = [gpu_info_data]
                else:
                    # GPU が2個以上搭載されている環境
                    gpu_infos = gpu_info_data
                # 搭載されている GPU 名を取得してリストに追加
                for gpu_info in gpu_infos:
                    if 'Name' in gpu_info:
                        gpu_names.append(gpu_info['Name'])
            except json.decoder.JSONDecodeError:
                pass

    # Linux / Linux-Docker: lshw コマンドを使って取得できる
    elif platform_type == 'Linux' or platform_type == 'Linux-Docker':
        # もし lshw コマンドがインストールされていなかったらインストールする
        if shutil.which('lshw') is None:
            subprocess.run(
                args = ['apt-get', 'install', '-y', 'lshw'],
                stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            )
        # lshw コマンドを実行して GPU 情報を取得
        gpu_info_json = subprocess.run(
            args = ['lshw', '-class', 'display', '-json'],
            stdout = subprocess.PIPE,  # 標準出力をキャプチャする
            stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            text = True,  # 出力をテキストとして取得する
        )
        # コマンド成功時のみ
        if gpu_info_json.returncode == 0:
            try:
                # 接続されている GPU 名を取得してリストに追加
                for gpu_info in json.loads(gpu_info_json.stdout):
                    if 'vendor' in gpu_info and 'product' in gpu_info:
                        gpu_names.append(f'{gpu_info["vendor"]} {gpu_info["product"]}')
            except json.decoder.JSONDecodeError:
                pass

        # ARM 環境のみ、もし  /proc/device-tree/compatible が存在し、その中に "rockchip" と "rk35" という文字列が含まれていたら、
        # Rockchip SoC 搭載の ARM SBC と判断して rkmppenc を利用可能とする
        if platform_type == 'Linux' and Path('/proc/device-tree/compatible').exists():
            with open('/proc/device-tree/compatible', encoding='utf-8') as compatible_file:
                compatible_data = compatible_file.read()
                if 'rockchip' in compatible_data and 'rk35' in compatible_data:
                    rkmppenc_available = '✅利用できます'
                    default_encoder = 'rkmppenc'

    # Intel 製 GPU なら QSVEncC が、NVIDIA 製 GPU (Geforce) なら NVEncC が、AMD 製 GPU (Radeon) なら VCEEncC が使える
    # また、RK3588 などの Rockchip SoC 搭載の ARM SBC なら、rkmppenc が使える
    ## もちろん機種によって例外はあるけど、ダウンロード前だとこれくらいの大雑把な判定しかできない…
    ## VCEEncC は安定性があまり良くなく、NVEncC は性能は良いものの Geforce だと同時エンコード本数の制限があるので、
    ## 複数の GPU が接続されている場合は QSVEncC が一番優先されるようにする
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

    table_05 = CreateTable()
    if is_arm_device is False:
        table_05.add_column('05. 利用するエンコーダーを FFmpeg・QSVEncC・NVEncC・VCEEncC から選んで入力してください。')
    else:
        table_05.add_column('05. 利用するエンコーダーを FFmpeg・rkmppenc から選んで入力してください。')
    table_05.add_row('FFmpeg はソフトウェアエンコーダーです。')
    table_05.add_row('すべての PC で利用できますが、CPU に多大な負荷がかかり、パフォーマンスが悪いです。')
    if is_arm_device is False:
        table_05.add_row('QSVEncC・NVEncC・VCEEncC はハードウェアエンコーダーです。')
    else:
        table_05.add_row('rkmppenc はハードウェアエンコーダーです。')
    table_05.add_row('FFmpeg と比較して CPU 負荷が低く、パフォーマンスがとても高いです（おすすめ）。')
    table_05.add_row(CreateRule())
    if is_arm_device is False:
        table_05.add_row(RemoveEmojiIfLegacyTerminal(f'QSVEncC: {qsvencc_available}'))
        table_05.add_row(RemoveEmojiIfLegacyTerminal(f'NVEncC : {nvencc_available}'))
        table_05.add_row(RemoveEmojiIfLegacyTerminal(f'VCEEncC: {vceencc_available}'))
    else:
        table_05.add_row(RemoveEmojiIfLegacyTerminal(f'rkmppenc: {rkmppenc_available}'))
    print(Padding(table_05, (1, 2, 1, 2)))

    # 利用するエンコーダーを取得
    if is_arm_device is False:
        encoder = cast(
            Literal['FFmpeg', 'QSVEncC', 'NVEncC', 'VCEEncC'],
            CustomPrompt.ask('利用するエンコーダー', default=default_encoder, choices=['FFmpeg', 'QSVEncC', 'NVEncC', 'VCEEncC']),
        )
    else:
        encoder = cast(
            Literal['FFmpeg', 'rkmppenc'],
            CustomPrompt.ask('利用するエンコーダー', default=default_encoder, choices=['FFmpeg', 'rkmppenc']),
        )

    # ***** 録画済み番組の保存先フォルダのパス *****

    table_06 = CreateTable()
    table_06.add_column('06. 録画済み番組の保存先フォルダを入力してください。')
    if platform_type == 'Windows':
        table_06.add_row('入力例: E:\\TV-Record')
    elif platform_type == 'Linux' or platform_type == 'Linux-Docker':
        table_06.add_row('入力例: /mnt/hdd/TV-Record')
    table_06.add_row('複数のフォルダを指定するには、パスを1つずつ入力してください。')
    table_06.add_row('入力を終了する場合は、何も入力せずに Enter キーを押してください。')
    print(Padding(table_06, (1, 2, 1, 2)))

    # 録画フォルダのリスト
    recorded_folders: list[str] = []

    # 録画フォルダを1つずつ入力
    while True:
        # 入力プロンプト (バリデーションに失敗し続ける限り何度でも表示される)
        recorded_folder = CustomPrompt.ask('録画フォルダのパス')

        # 何も入力されなかった場合は入力を終了
        if recorded_folder == '':
            # 1つも入力されていない場合は再度入力を促す
            if len(recorded_folders) == 0:
                print(Padding('[red]少なくとも1つの録画フォルダを指定してください。', (0, 2, 0, 2)))
                continue
            break

        # 入力されたパスを Path オブジェクトに変換
        recorded_folder_path = Path(recorded_folder)

        # バリデーション
        if recorded_folder_path.is_absolute() is False:
            print(Padding('[red]録画フォルダは絶対パスで入力してください。', (0, 2, 0, 2)))
            continue
        if recorded_folder_path.exists() is False:
            print(Padding('[red]指定された録画フォルダが存在しません。', (0, 2, 0, 2)))
            continue
        if recorded_folder_path.is_dir() is False:
            print(Padding('[red]指定されたパスはフォルダではありません。', (0, 2, 0, 2)))
            continue

        # 現在指定されているフォルダの一覧を表示
        recorded_folders.append(str(recorded_folder_path))
        print(Padding(f'[green]現在指定されている録画フォルダ: {", ".join(recorded_folders)}', (0, 2, 0, 2)))

    # ***** アップロードしたキャプチャ画像の保存先フォルダのパス *****

    table_07 = CreateTable()
    table_07.add_column('07. アップロードしたキャプチャ画像の保存先フォルダのパスを入力してください。')
    table_07.add_row('クライアントの [キャプチャの保存先] 設定で [KonomiTV サーバーにアップロード] または')
    table_07.add_row('[ブラウザでのダウンロードと、KonomiTV サーバーへのアップロードを両方行う] を選択したときに利用されます。')
    if platform_type == 'Windows':
        table_07.add_row('入力例: E:\\TV-Capture')
    elif platform_type == 'Linux' or platform_type == 'Linux-Docker':
        table_07.add_row('入力例: /mnt/hdd/TV-Capture')
    table_07.add_row('複数のフォルダを指定するには、パスを1つずつ入力してください。')
    table_07.add_row('入力を終了する場合は、何も入力せずに Enter キーを押してください。')
    print(Padding(table_07, (1, 2, 1, 2)))

    # キャプチャ画像の保存フォルダのリスト
    capture_upload_folders: list[str] = []

    # 録画フォルダを1つずつ入力
    while True:
        # 入力プロンプト (バリデーションに失敗し続ける限り何度でも表示される)
        capture_upload_folder = CustomPrompt.ask('アップロードしたキャプチャ画像の保存先フォルダのパス')

        # 何も入力されなかった場合は入力を終了
        if capture_upload_folder == '':
            # 1つも入力されていない場合は再度入力を促す
            if len(capture_upload_folders) == 0:
                print(Padding('[red]少なくとも1つのキャプチャ画像の保存先フォルダを指定してください。', (0, 2, 0, 2)))
                continue
            break

        # 入力されたパスを Path オブジェクトに変換
        capture_upload_folder_path = Path(capture_upload_folder)

        # バリデーション
        if capture_upload_folder_path.is_absolute() is False:
            print(Padding('[red]キャプチャ画像の保存先フォルダは絶対パスで入力してください。', (0, 2, 0, 2)))
            continue
        if capture_upload_folder_path.exists() is False:
            print(Padding('[red]指定されたキャプチャ画像の保存先フォルダが存在しません。', (0, 2, 0, 2)))
            continue
        if capture_upload_folder_path.is_dir() is False:
            print(Padding('[red]指定されたパスはフォルダではありません。', (0, 2, 0, 2)))
            continue

        # 現在指定されているフォルダの一覧を表示
        capture_upload_folders.append(str(capture_upload_folder_path))
        print(Padding(f'[green]現在指定されているキャプチャ画像の保存先フォルダ: {", ".join(capture_upload_folders)}', (0, 2, 0, 2)))

    # ***** ソースコードのダウンロード *****

    # Git コマンドがインストールされているかどうか
    is_git_installed = IsGitInstalled()

    # Git コマンドがインストールされている場合: git clone でダウンロード
    if is_git_installed is True:

        # git clone でソースコードをダウンロード
        ## latest の場合は master ブランチを、それ以外は指定されたバージョンのタグをチェックアウト
        revision = 'master' if version == 'latest' else f'v{version}'
        result = RunSubprocess(
            'KonomiTV のソースコードを Git でダウンロードしています…',
            ['git', 'clone', '-b', revision, 'https://github.com/tsukumijima/KonomiTV.git', install_path.name],
            cwd = install_path.parent,
            error_message = 'KonomiTV のソースコードのダウンロード中に予期しないエラーが発生しました。',
            error_log_name = 'Git のエラーログ',
        )
        if result is False:
            return  # 処理中断

    # Git コマンドがインストールされていない場合: zip でダウンロード
    else:

        # ソースコードを随時ダウンロードし、進捗を表示
        # ref: https://github.com/Textualize/rich/blob/master/examples/downloader.py
        print(Padding('KonomiTV のソースコードをダウンロードしています…', (1, 2, 0, 2)))
        progress = CreateDownloadInfiniteProgress()

        # GitHub からソースコードをダウンロード
        ## latest の場合は master ブランチを、それ以外は指定されたバージョンのタグをダウンロード
        if version == 'latest':
            source_code_response = requests.get('https://codeload.github.com/tsukumijima/KonomiTV/zip/refs/heads/master')
        else:
            source_code_response = requests.get(f'https://codeload.github.com/tsukumijima/KonomiTV/zip/refs/tags/v{version}')
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
        if version == 'latest':
            shutil.move(install_path.parent / 'KonomiTV-master/', install_path)
        else:
            shutil.move(install_path.parent / f'KonomiTV-{version}/', install_path)
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
        ShowPanel([
            '[yellow]注意: デフォルトのリッスンポート (7000) がほかのサーバーソフトと重複しています。[/yellow]',
            f'代わりのリッスンポートとして、ポート {server_port} を選択します。',
            'リッスンポートは、サーバー設定ファイル (config.yaml) を編集すると変更できます。',
        ])

    # ***** サーバー設定ファイル (config.yaml) の生成 *****

    print(Padding('サーバー設定ファイル (config.yaml) を生成しています…', (1, 2, 0, 2)))
    progress = CreateBasicInfiniteProgress()
    progress.add_task('', total=None)
    with progress:

        # config.example.yaml を config.yaml にコピー
        shutil.copyfile(install_path / 'config.example.yaml', install_path / 'config.yaml')

        # config.yaml から既定の設定値を取得
        config_dict: dict[str, dict[str, Any]]
        with open(install_path / 'config.yaml', encoding='utf-8') as file:
            config_dict = dict(ruamel.yaml.YAML().load(file))

        # サーバー設定データの一部を事前に取得しておいた値で置き換え
        ## インストーラーで置換するのはバックエンドや EDCB / Mirakurun の URL など、サーバーの起動に不可欠な値のみ
        config_dict['general']['backend'] = backend
        if backend == 'EDCB':
            config_dict['general']['edcb_url'] = edcb_url
        elif backend == 'Mirakurun':
            config_dict['general']['mirakurun_url'] = mirakurun_url
        config_dict['general']['encoder'] = encoder
        config_dict['server']['port'] = server_port
        config_dict['video']['recorded_folders'] = recorded_folders
        config_dict['capture']['upload_folders'] = capture_upload_folders

        # サーバー設定データを保存
        SaveConfig(install_path / 'config.yaml', config_dict)

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
        if version == 'latest':
            thirdparty_base_url = 'https://nightly.link/tsukumijima/KonomiTV/workflows/build_thirdparty.yaml/master/'
        else:
            thirdparty_base_url = f'https://github.com/tsukumijima/KonomiTV/releases/download/v{version}/'
        thirdparty_compressed_file_name = 'thirdparty-windows.7z'
        if platform_type == 'Linux' and is_arm_device is False:
            thirdparty_compressed_file_name = 'thirdparty-linux.tar.xz'
        elif platform_type == 'Linux' and is_arm_device is True:
            thirdparty_compressed_file_name = 'thirdparty-linux-arm.tar.xz'
        thirdparty_url = thirdparty_base_url + thirdparty_compressed_file_name
        if version == 'latest':
            thirdparty_url = thirdparty_url + '.zip'
        thirdparty_response = requests.get(thirdparty_url, stream=True)
        task_id = progress.add_task('', total=float(thirdparty_response.headers['Content-length']))

        # ダウンロードしたデータを随時一時ファイルに書き込む
        thirdparty_compressed_file = tempfile.NamedTemporaryFile(mode='wb', delete=False)
        with progress:
            for chunk in thirdparty_response.iter_content(chunk_size=1048576):  # サイズが大きいので1MBごとに読み込み
                thirdparty_compressed_file.write(chunk)
                progress.update(task_id, advance=len(chunk))
        thirdparty_compressed_file.close()  # 解凍する前に close() してすべて書き込ませておくのが重要

        # サードパーティーライブラリを解凍して展開
        print(Padding('サードパーティーライブラリを展開しています… (数秒～数十秒かかります)', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:

            # latest のみ、圧縮ファイルがさらに zip で包まれているので、それを解凍
            thirdparty_compressed_file_path = thirdparty_compressed_file.name
            if version == 'latest':
                with zipfile.ZipFile(thirdparty_compressed_file.name, mode='r') as zip_file:
                    zip_file.extractall(install_path / 'server/')
                thirdparty_compressed_file_path = install_path / 'server' / thirdparty_compressed_file_name
                Path(thirdparty_compressed_file.name).unlink()

            if platform_type == 'Windows':
                # Windows: 7-Zip 形式のアーカイブを解凍
                with py7zr.SevenZipFile(thirdparty_compressed_file_path, mode='r') as seven_zip:
                    seven_zip.extractall(install_path / 'server/')
            elif platform_type == 'Linux':
                # Linux: tar.xz 形式のアーカイブを解凍
                ## 7-Zip だと (おそらく) ファイルパーミッションを保持したまま圧縮することができない？ため、あえて tar.xz を使っている
                with tarfile.open(thirdparty_compressed_file_path, mode='r:xz') as tar_xz:
                    tar_xz.extractall(install_path / 'server/')
            Path(thirdparty_compressed_file_path).unlink()
            # server/thirdparty/.gitkeep が消えてたらもう一度作成しておく
            if Path(install_path / 'server/thirdparty/.gitkeep').exists() is False:
                Path(install_path / 'server/thirdparty/.gitkeep').touch()

        # ***** poetry 環境の構築 (依存パッケージのインストール) *****

        # Python の実行ファイルのパス (Windows と Linux で異なる)
        if platform_type == 'Windows':
            python_executable_path = install_path / 'server/thirdparty/Python/python.exe'
        elif platform_type == 'Linux':
            python_executable_path = install_path / 'server/thirdparty/Python/bin/python'

        # poetry env use を実行
        result = RunSubprocessDirectLogOutput(
            'Python の仮想環境を作成しています…',
            [python_executable_path, '-m', 'poetry', 'env', 'use', python_executable_path],
            cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
            environment = {'PYTHON_KEYRING_BACKEND': 'keyring.backends.null.Keyring'},  # Windows で SSH 接続時に発生するエラーを回避
            error_message = 'Python の仮想環境の作成中に予期しないエラーが発生しました。',
        )
        if result is False:
            return  # 処理中断

        # poetry install を実行
        # --no-root: プロジェクトのルートパッケージをインストールしない
        result = RunSubprocessDirectLogOutput(
            '依存パッケージをインストールしています…',
            [python_executable_path, '-m', 'poetry', 'install', '--only', 'main', '--no-root'],
            cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
            environment = {'PYTHON_KEYRING_BACKEND': 'keyring.backends.null.Keyring'},  # Windows で SSH 接続時に発生するエラーを回避
            error_message = '依存パッケージのインストール中に予期しないエラーが発生しました。',
        )
        if result is False:
            return  # 処理中断

    # Linux-Docker: docker-compose.yaml を生成し、Docker イメージをビルド
    elif platform_type == 'Linux-Docker':

        # ***** docker-compose.yaml の生成 *****

        print(Padding('docker-compose.yaml を生成しています…', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:

            # docker-compose.example.yaml を docker-compose.yaml にコピー
            shutil.copyfile(install_path / 'docker-compose.example.yaml', install_path / 'docker-compose.yaml')

            # docker-compose.yaml の内容を読み込む
            with open(install_path / 'docker-compose.yaml', encoding='utf-8') as file:
                text = file.read()

            # GPU が1個も搭載されていない特殊な環境の場合
            ## /dev/dri/ 以下のデバイスファイルが存在しないので、デバイスのマウント設定をコメントアウトしないとコンテナが起動できない
            if Path('/dev/dri/').is_dir() is False:
                # デフォルト (置換元) の config.yaml の記述
                old_text = (
                    '    devices:\n'
                    '      - \'/dev/dri/:/dev/dri/\''
                )
                # 置換後の config.yaml の記述
                new_text = (
                    '    # devices:\n'
                    '    #   - \'/dev/dri/:/dev/dri/\''
                )
                text = text.replace(old_text, new_text)

            # NVEncC が利用できそうな場合、NVIDIA GPU が Docker コンテナ内で使えるように docker-compose.yaml の当該記述をコメントアウト
            ## NVIDIA GPU が使える環境以外でコメントアウトすると
            ## 正攻法で YAML でコメントアウトする方法が思いつかなかったので、ゴリ押しで置換……
            if '利用できます' in nvencc_available:
                # デフォルト (置換元) の config.yaml の記述
                old_text = (
                    '    # deploy:\n'
                    '    #   resources:\n'
                    '    #     reservations:\n'
                    '    #       devices:\n'
                    '    #         - driver: nvidia\n'
                    '    #           count: all\n'
                    '    #           capabilities: [compute, utility, video]'
                )
                # 置換後の config.yaml の記述
                new_text = (
                    '    deploy:\n'
                    '      resources:\n'
                    '        reservations:\n'
                    '          devices:\n'
                    '            - driver: nvidia\n'
                    '              count: all\n'
                    '              capabilities: [compute, utility, video]'
                )
                text = text.replace(old_text, new_text)

            # docker-compose.yaml を書き換え
            with open(install_path / 'docker-compose.yaml', mode='w', encoding='utf-8') as file:
                file.write(text)

        # ***** Docker イメージのビルド *****

        # docker compose build --no-cache --pull で Docker イメージをビルド
        ## 万が一以前ビルドしたキャッシュが残っていたときに備え、キャッシュを使わずにビルドさせる
        result = RunSubprocessDirectLogOutput(
            'Docker イメージをビルドしています… (数分～数十分かかります)',
            [*docker_compose_command, 'build', '--no-cache', '--pull'],
            cwd = install_path,  # カレントディレクトリを KonomiTV のインストールフォルダに設定
            error_message = 'Docker イメージのビルド中に予期しないエラーが発生しました。',
        )
        if result is False:
            return  # 処理中断

    # ***** Linux / Linux-Docker: QSVEncC / NVEncC / VCEEncC の動作チェック *****

    if platform_type == 'Linux' or platform_type == 'Linux-Docker':

        # エンコーダーに QSVEncC が選択されているとき
        if encoder == 'QSVEncC':

            # 実行コマンド1 (Linux-Docker では docker-compose run を介して実行する)
            command1 = [install_path / 'server/thirdparty/QSVEncC/QSVEncC.elf', '--check-hw']
            if platform_type == 'Linux-Docker':
                command1 = [*docker_compose_command, 'run', '--rm',
                    '--entrypoint', '/bin/bash -c "/code/server/thirdparty/QSVEncC/QSVEncC.elf --check-hw"', 'konomitv']

            # QSVEncC の --check-hw オプションの終了コードが 0 なら利用可能、それ以外なら利用不可
            result1 = subprocess.run(
                args = command1,
                cwd = install_path,  # カレントディレクトリを KonomiTV のインストールフォルダに設定
                stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                stderr = subprocess.STDOUT,  # 標準エラー出力を標準出力にリダイレクト
                text = True,  # 出力をテキストとして取得する
            )

            # 実行コマンド2 (Linux-Docker では docker-compose run を介して実行する)
            command2 = [install_path / 'server/thirdparty/QSVEncC/QSVEncC.elf', '--check-clinfo']
            if platform_type == 'Linux-Docker':
                command2 = [*docker_compose_command, 'run', '--rm',
                    '--entrypoint', '/bin/bash -c "/code/server/thirdparty/QSVEncC/QSVEncC.elf --check-clinfo"', 'konomitv']

            # QSVEncC の --check-clinfo オプションの終了コードが 0 なら利用可能、それ以外なら利用不可
            ## libva-intel-driver (i965-va-driver) はインストールされているが、
            ## QSVEncC の動作に必要な intel-media-driver はインストールされていないケースを弾く (--check-hw では弾けない)
            result2 = subprocess.run(
                args = command2,
                cwd = install_path,  # カレントディレクトリを KonomiTV のインストールフォルダに設定
                stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                stderr = subprocess.STDOUT,  # 標準エラー出力を標準出力にリダイレクト
                text = True,  # 出力をテキストとして取得する
            )

            # Linux のみ
            if platform_type == 'Linux':

                # Intel Media Driver が /usr/lib/x86_64-linux-gnu/dri/iHD_drv_video.so に配置されているか
                ## Intel Media Driver がインストールされていればここに配置されるはずなので、配置されていないということは
                ## おそらくインストールされていないと考えられる
                ## ref: https://packages.ubuntu.com/ja/focal/amd64/intel-media-va-driver-non-free/filelist
                is_intel_media_driver_installed = Path('/usr/lib/x86_64-linux-gnu/dri/iHD_drv_video.so').exists()

                # QSVEncC が利用できない結果になった場合は Intel Media Driver がインストールされていない可能性が高いので、
                # 適宜 Intel Media Driver をインストールするように催促する
                ## Intel Media Driver は Intel Graphics 本体のドライバーとは切り離されているので、インストールが比較的容易
                ## Intel Graphics 本体のドライバーは Linux カーネルに組み込まれている
                ## インストールコマンドが複雑なので、コマンド例を明示する
                if result1.returncode != 0 or result2.returncode != 0 or is_intel_media_driver_installed is False:
                    ShowPanel([
                        '[yellow]注意: この PC では QSVEncC が利用できない状態です。[/yellow]',
                        'Intel QSV の利用に必要な Intel Media Driver が',
                        'インストールされていない可能性があります。',
                    ])
                    ShowPanel([
                        'Intel Media Driver は以下のコマンドでインストールできます。',
                        'Ubuntu 24.04 LTS:',
                        '[cyan]curl -fsSL https://repositories.intel.com/gpu/intel-graphics.key | sudo gpg --yes --dearmor --output /usr/share/keyrings/intel-graphics-keyring.gpg && echo \'deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics-keyring.gpg] https://repositories.intel.com/gpu/ubuntu noble unified\' | sudo tee /etc/apt/sources.list.d/intel-gpu-noble.list > /dev/null && sudo apt update && sudo apt install -y intel-media-va-driver-non-free intel-opencl-icd libigfxcmrt7 libmfx1 libmfxgen1 libva-drm2 libva-x11-2[/cyan]',
                        'Ubuntu 22.04 LTS:',
                        '[cyan]curl -fsSL https://repositories.intel.com/gpu/intel-graphics.key | sudo gpg --yes --dearmor --output /usr/share/keyrings/intel-graphics-keyring.gpg && echo \'deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics-keyring.gpg] https://repositories.intel.com/gpu/ubuntu jammy unified\' | sudo tee /etc/apt/sources.list.d/intel-gpu-jammy.list > /dev/null && sudo apt update && sudo apt install -y intel-media-va-driver-non-free intel-opencl-icd libigfxcmrt7 libmfx1 libmfxgen1 libva-drm2 libva-x11-2[/cyan]',
                        'Ubuntu 20.04 LTS:',
                        '[cyan]curl -fsSL https://repositories.intel.com/gpu/intel-graphics.key | sudo gpg --yes --dearmor --output /usr/share/keyrings/intel-graphics-keyring.gpg && echo \'deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics-keyring.gpg] https://repositories.intel.com/gpu/ubuntu focal client\' | sudo tee /etc/apt/sources.list.d/intel-graphics.list > /dev/null && sudo apt update && sudo apt install -y intel-media-va-driver-non-free intel-opencl-icd libigfxcmrt7 libmfx1 libmfxgen1 libva-drm2 libva-x11-2[/cyan]',
                    ], padding=(0, 2, 0, 2))
                    ShowPanel([
                        'QSVEncC (--check-hw) のログ:\n' + result1.stdout.strip(),
                    ], padding=(0, 2, 0, 2))
                    ShowPanel([
                        'QSVEncC (--check-clinfo) のログ:\n' + result2.stdout.strip(),
                    ], padding=(0, 2, 0, 2))

            # Linux-Docker のみ
            elif platform_type == 'Linux-Docker':

                # Linux-Docker では Docker イメージの中に Intel Media Driver が含まれているため、基本的には動作するはず
                ## もしそれでも動作しない場合は、Intel QSV に対応していない古い Intel CPU である可能性が高い
                if result1.returncode != 0 or result2.returncode != 0:
                    ShowPanel([
                        '[yellow]注意: この PC では QSVEncC が利用できない状態です。[/yellow]',
                        'お使いの CPU が古く、Intel QSV に対応していない可能性があります。',
                        'Linux 版の Intel QSV は、Broadwell (第5世代) 以上の Intel CPU でのみ利用できます。',
                        'そのため、Haswell (第4世代) 以下の CPU では、QSVEncC を利用できません。',
                        'なお、Windows 版の Intel QSV は、Haswell (第4世代) 以下の CPU でも利用できます。',
                    ])
                    ShowPanel([
                        'QSVEncC (--check-hw) のログ:\n' + result1.stdout.strip(),
                    ], padding=(0, 2, 0, 2))
                    ShowPanel([
                        'QSVEncC (--check-clinfo) のログ:\n' + result2.stdout.strip(),
                    ], padding=(0, 2, 0, 2))

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
                cwd = install_path,  # カレントディレクトリを KonomiTV のインストールフォルダに設定
                stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                stderr = subprocess.STDOUT,  # 標準エラー出力を標準出力にリダイレクト
                text = True,  # 出力をテキストとして取得する
            )

            # NVEncC が利用できない結果になった場合はドライバーがインストールされていない or 古い可能性が高いので、
            # 適宜ドライバーをインストール/アップデートするように催促する
            ## NVEncC は NVIDIA Graphics Driver さえインストールされていれば動作する
            if result.returncode != 0:
                ShowPanel([
                    '[yellow]注意: この PC では NVEncC が利用できない状態です。[/yellow]',
                    'NVENC の利用に必要な NVIDIA Graphics Driver がインストールされていないか、',
                    'NVIDIA Graphics Driver のバージョンが古い可能性があります。',
                    'NVIDIA Graphics Driver をインストール/最新バージョンに更新してください。',
                    'インストール/アップデート完了後は、システムの再起動が必要です。',
                ])
                ShowPanel([
                    'NVEncC のログ:\n' + result.stdout.strip(),
                ], padding=(0, 2, 0, 2))

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
                cwd = install_path,  # カレントディレクトリを KonomiTV のインストールフォルダに設定
                stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                stderr = subprocess.STDOUT,  # 標準エラー出力を標準出力にリダイレクト
                text = True,  # 出力をテキストとして取得する
            )

            # VCEEncC が利用できない結果になった場合はドライバーがインストールされていない or 古い可能性が高いので、
            # 適宜ドライバーをインストール/アップデートするように催促する
            ## VCEEncC は AMDGPU-PRO Driver さえインストールされていれば動作する
            if result.returncode != 0:
                ShowPanel([
                    '[yellow]注意: この PC では VCEEncC が利用できない状態です。[/yellow]',
                    'AMD VCE の利用に必要な AMDGPU-PRO Driver がインストールされていないか、',
                    'AMDGPU-PRO Driver のバージョンが古い可能性があります。',
                    'AMDGPU-PRO Driver をインストール/最新バージョンに更新してください。',
                ])
                ShowPanel([
                    'AMDGPU-PRO Driver のインストーラーは以下のコマンドでダウンロードできます。',
                    'Ubuntu 24.04 LTS: [cyan]curl -LO https://repo.radeon.com/amdgpu-install/6.4.4/ubuntu/noble/amdgpu-install_6.4.60404-1_all.deb[/cyan]',
                    'Ubuntu 22.04 LTS: [cyan]curl -LO https://repo.radeon.com/amdgpu-install/6.4.4/ubuntu/jammy/amdgpu-install_6.4.60404-1_all.deb[/cyan]',
                ], padding=(0, 2, 0, 2))
                ShowPanel([
                    'AMDGPU-PRO Driver は以下のコマンドでインストール/アップデートできます。',
                    '事前に AMDGPU-PRO Driver のインストーラーをダウンロードしてから実行してください。',
                    'インストール/アップデート完了後は、システムの再起動が必要です。',
                    '[cyan]sudo apt install -y ./amdgpu-install_6.4.60404-1_all.deb && sudo apt update && sudo amdgpu-install -y --accept-eula --usecase=graphics,amf,opencl --opencl=rocr --vulkan=amdvlk --no-32[/cyan]',
                ], padding=(0, 2, 0, 2))
                ShowPanel([
                    'VCEEncC のログ:\n' + result.stdout.strip(),
                ], padding=(0, 2, 0, 2))

        # エンコーダーに rkmppenc が選択されているとき
        elif encoder == 'rkmppenc':

            # 実行コマンド
            command = [install_path / 'server/thirdparty/rkmppenc/rkmppenc.elf', '--check-hw']

            # rkmppenc の --check-hw オプションの終了コードが 0 なら利用可能、それ以外なら利用不可
            result = subprocess.run(
                args = command,
                cwd = install_path,  # カレントディレクトリを KonomiTV のインストールフォルダに設定
                stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                stderr = subprocess.STDOUT,  # 標準エラー出力を標準出力にリダイレクト
                text = True,  # 出力をテキストとして取得する
            )

            # rkmppenc が利用できない結果になった場合は必要な設定とパッケージをインストールするように細則する
            if result.returncode != 0:
                ShowPanel([
                    '[yellow]注意: この PC では rkmppenc が利用できない状態です。[/yellow]',
                    'Rockchip MPP の利用に必要な Mali GPU Driver がインストールされていないか、',
                    'お使いの SoC が Rockchip MPP に対応していない可能性があります。',
                ])
                ShowPanel([
                    'RK3588/RK3588S 向けの Mali GPU Driver は、以下のコマンドでインストールできます。',
                    'インストール完了後は、システムの再起動が必要です。',
                    '[cyan]curl -LO https://github.com/tsukumijima/libmali-rockchip/releases/download/v1.9-1-3238416/libmali-valhall-g610-g13p0-wayland-gbm_1.9-1_arm64.deb && sudo apt install -y ./libmali-valhall-g610-g13p0-wayland-gbm_1.9-1_arm64.deb && rm libmali-valhall-g610-g13p0-wayland-gbm_1.9-1_arm64.deb && curl -LO https://github.com/tsukumijima/rockchip-multimedia-config/releases/download/v1.0.2-1/rockchip-multimedia-config_1.0.2-1_all.deb && sudo apt install -y ./rockchip-multimedia-config_1.0.2-1_all.deb && rm rockchip-multimedia-config_1.0.2-1_all.deb[/cyan]',
                ], padding=(0, 2, 0, 2))
                ShowPanel([
                    'rkmppenc のログ:\n' + result.stdout.strip(),
                ], padding=(0, 2, 0, 2))

    # ***** Windows: Windows Defender ファイアウォールに受信規則を追加 *****

    if platform_type == 'Windows':

        print(Padding('Windows Defender ファイアウォールに受信規則を追加しています…', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:

            # 一旦既存の受信規則を削除
            subprocess.run(
                args = ['netsh', 'advfirewall', 'firewall', 'delete', 'rule', 'name=KonomiTV Service'],
                stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            )

            # "プライベート" と "パブリック" で有効な受信規則を追加
            subprocess.run(
                args = [
                    'netsh', 'advfirewall', 'firewall', 'add', 'rule', 'name=KonomiTV Service', 'description=KonomiTV Windows Service.',
                    'profile=private,public', 'enable=yes', 'action=allow', 'dir=in', 'protocol=TCP',
                    f'program={install_path / "server/thirdparty/Akebi/akebi-https-server.exe"}',
                ],
                stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            )

    # ***** Windows: Windows サービスのインストール・起動 *****

    if platform_type == 'Windows':

        # 現在ログオン中のユーザー名を取得
        ## PowerShell の [Environment]::UserName を使う
        current_user_name_default = subprocess.run(
            args = ['powershell', '-Command', '[Environment]::UserName'],
            stdout = subprocess.PIPE,  # 標準出力をキャプチャする
            stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            text = True,  # 出力をテキストとして取得する
        ).stdout.strip()

        table_08 = CreateTable()
        table_08.add_column('08. KonomiTV の Windows サービスの実行ユーザー名を入力してください。')
        table_08.add_row('KonomiTV の Windows サービスを一般ユーザーの権限で起動するために利用します。')
        table_08.add_row('ほかのユーザー権限で実行したい場合は、そのユーザー名を入力してください。')
        table_08.add_row(f'Enter キーを押すと、現在ログオン中のユーザー ({current_user_name_default}) が利用されます。')
        print(Padding(table_08, (0, 2, 0, 2)))

        # ユーザー名を入力
        current_user_name: str = CustomPrompt.ask('KonomiTV の Windows サービスの実行ユーザー名', default=current_user_name_default)

        table_09 = CreateTable()
        table_09.add_column(f'09. ユーザー ({current_user_name}) のパスワードを入力してください。')
        table_09.add_row('KonomiTV の Windows サービスを一般ユーザーの権限で起動するために利用します。')
        table_09.add_row('入力されたパスワードがそれ以外の用途に利用されることはありません。')
        table_09.add_row('間違ったパスワードを入力すると、KonomiTV が起動できなくなります。')
        table_09.add_row('Enter キーを押す前に、正しいパスワードかどうか今一度確認してください。')
        table_09.add_row('なお、PIN などのほかの認証方法には対応していません。')
        table_09.add_row(CreateRule())
        table_09.add_row('ログオン中のユーザーにパスワードを設定していない場合は、簡単なものでいいので')
        table_09.add_row('何かパスワードを設定してから、その設定したパスワードを入力してください。')
        table_09.add_row('なお、パスワードの設定後にインストーラーを起動し直す必要はありません。')
        table_09.add_row(CreateRule())
        table_09.add_row('ごく稀に、正しいパスワードを指定したのにログオンできない場合があります。')
        table_09.add_row('その場合は、一度インストーラーを Ctrl+C で中断し、インストーラーの')
        table_09.add_row('実行ファイルを Shift + 右クリック → [別のユーザーとして実行] から、')
        table_09.add_row('ログオン中のユーザーとパスワードを指定して再度実行してみてください。')
        print(Padding(table_09, (1, 2, 1, 2)))

        # ユーザーのパスワードを取得
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
                        python_executable_path, '-m', 'poetry', 'run', 'python', 'KonomiTV-Service.py', 'install',
                        '--username', current_user_name, '--password', current_user_password,
                    ],
                    cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                    stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                    stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
                    text = True,  # 出力をテキストとして取得する
                )
            if 'Error installing service' in service_install_result.stdout:
                print(Padding(str(
                    '[red]Windows サービスのインストールに失敗しました。\n'
                    '入力されたログオン中ユーザーのパスワードが間違っているか、\n'
                    'すでに KonomiTV がインストールされている可能性があります。',
                ), (1, 2, 0, 2)))
                print(Padding('[red]エラーログ:\n' + service_install_result.stdout.strip(), (1, 2, 1, 2)))
                continue

            # Windows サービスを起動
            print(Padding('Windows サービスを起動しています…', (1, 2, 0, 2)))
            progress = CreateBasicInfiniteProgress()
            progress.add_task('', total=None)
            with progress:
                service_start_result = subprocess.run(
                    args = [python_executable_path, '-m', 'poetry', 'run', 'python', 'KonomiTV-Service.py', 'start'],
                    cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                    stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                    stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
                    text = True,  # 出力をテキストとして取得する
                )
            if 'Error starting service' in service_start_result.stdout:
                print(Padding(str(
                    '[red]Windows サービスの起動に失敗しました。\n'
                    '入力されたログオン中ユーザーのパスワードが間違っているか、\n'
                    'すでに KonomiTV がインストールされている可能性があります。',
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
        result = RunSubprocess(
            'PM2 サービスをインストールしています…',
            ['/usr/bin/env', 'pm2', 'start', '.venv/bin/python', '--name', 'KonomiTV', '--', 'KonomiTV.py'],
            cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
            error_message = 'PM2 サービスのインストール中に予期しないエラーが発生しました。',
            error_log_name = 'PM2 のエラーログ',
        )
        if result is False:
            return  # 処理中断

        # PM2 のスタートアップ設定を行う
        ## これにより、PM2 サービスは OS 起動時に自動的に起動されるようになる
        result = RunSubprocess(
            'PM2 サービスのスタートアップ設定を行っています…',
            ['/usr/bin/env', 'pm2', 'startup'],
            cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
            error_message = 'PM2 サービスのスタートアップ設定中に予期しないエラーが発生しました。',
            error_log_name = 'PM2 のエラーログ',
        )
        if result is False:
            return  # 処理中断

        # PM2 への変更を保存
        result = RunSubprocess(
            'PM2 サービスの状態を保存しています…',
            ['/usr/bin/env', 'pm2', 'save'],
            cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
            error_message = 'PM2 サービスの状態の保存中に予期しないエラーが発生しました。',
            error_log_name = 'PM2 のエラーログ',
        )
        if result is False:
            return  # 処理中断

        # PM2 サービスを起動
        result = RunSubprocess(
            'PM2 サービスを起動しています…',
            ['/usr/bin/env', 'pm2', 'start', 'KonomiTV'],
            cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
            error_message = 'PM2 サービスの起動中に予期しないエラーが発生しました。',
            error_log_name = 'PM2 のエラーログ',
        )
        if result is False:
            return  # 処理中断

    # ***** Linux-Docker: Docker コンテナの起動 *****

    elif platform_type == 'Linux-Docker':

        # Docker コンテナを起動
        result = RunSubprocess(
            'Docker コンテナを起動しています…',
            [*docker_compose_command, 'up', '-d', '--force-recreate'],
            cwd = install_path,  # カレントディレクトリを KonomiTV のインストールフォルダに設定
            error_message = 'Docker コンテナの起動中に予期しないエラーが発生しました。',
            error_log_name = 'Docker Compose のエラーログ',
        )
        if result is False:
            return  # 処理中断

    # ***** サービスの起動を待機 *****

    # KonomiTV サービスの起動を監視して起動完了を待機する処理はアップデーターと共通
    RunKonomiTVServiceWaiter(platform_type, install_path)

    # ***** インストール完了 *****

    # ループバックアドレスまたはリンクローカルアドレスでない IPv4 アドレスとインターフェイス名を取得
    nic_infos = GetNetworkInterfaceInformation()

    # インストール完了メッセージを表示
    table_done = CreateTable()
    table_done.add_column(RemoveEmojiIfLegacyTerminal(
        'インストールが完了しました！🎉🎊 すぐに使いはじめられます！🎈\n'
        '下記の URL から、KonomiTV の Web UI にアクセスしてみましょう！\n'
        'ブラウザで [アプリをインストール] または [ホーム画面に追加] を押すと、\n'
        'ショートカットやホーム画面からすぐに KonomiTV にアクセスできます！\n'
        'もし KonomiTV にアクセスできない場合は、ファイアウォールの設定を確認してみてください。',
    ))

    # アクセス可能な URL のリストを IP アドレスごとに表示
    ## ローカルホスト (127.0.0.1) だけは https://my.local.konomi.tv:7000/ というエイリアスが使える
    urls = [f'https://{nic_info[0].replace(".", "-")}.local.konomi.tv:{server_port}/' for nic_info in nic_infos]
    urls_max_length = max([len(url) for url in urls])  # URL の最大文字長を取得
    table_done.add_row(f'[bright_blue]{f"https://my.local.konomi.tv:{server_port}/": <{urls_max_length}}[/bright_blue] (ローカルホスト)')
    for index, url in enumerate(urls):
        table_done.add_row(f'[bright_blue]{url: <{urls_max_length}}[/bright_blue] ({nic_infos[index][1]})')

    print(Padding(table_done, (1, 2, 0, 2)))
