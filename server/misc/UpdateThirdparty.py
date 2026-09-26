#!/usr/bin/env python3

# Usage: uv run python -m misc.UpdateThirdparty DOWNLOAD_VERSION
# サーバー稼働状態だと正常に動作しません。必ず KonomiTV サービスが停止している状態で実行してください。
# 最新版のナイトリービルドをダウンロードする場合は、DOWNLOAD_VERSION に latest を指定する (開発版ではナイトリービルドを推奨)
# 安定版をダウンロードする場合は、DOWNLOAD_VERSION にバージョン番号を指定する (例: 0.7.1)

import platform
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Literal

import elevate
import py7zr
import requests
import typer
from rich import print
from rich.padding import Padding
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)


app = typer.Typer()

@app.command(help=(
    'サードパーティーライブラリを更新するユーティリティスクリプトです。\n'
    'サーバー稼働状態だと正常に動作しません。必ず KonomiTV サービスが停止している状態で実行してください。\n'
    '最新版のナイトリービルドをダウンロードする場合は、DOWNLOAD_VERSION に latest を指定します。(開発版ではナイトリービルドを推奨)\n'
    '安定版をダウンロードする場合は、DOWNLOAD_VERSION にバージョン番号を指定します。(例: 0.7.1)'
))
def main(
    download_version: str = typer.Argument(help='ダウンロードするサードパーティーライブラリのバージョン (例: 0.7.1) 。最新版のナイトリービルドをダウンロードする場合は latest と指定してください。'),
):
    download_version = download_version.replace('v', '').strip()

    # KonomiTV がインストールされているベースディレクトリ
    INSTALLED_DIR = Path(__file__).resolve().parent.parent.parent

    # サードパーティーライブラリのダウンロードベース URL
    if download_version == 'latest':
        THIRDPARTY_BASE_URL = 'https://nightly.link/tsukumijima/KonomiTV/workflows/build_thirdparty.yaml/master/'
    else:
        THIRDPARTY_BASE_URL = f'https://github.com/tsukumijima/KonomiTV/releases/download/v{download_version}/'

    # ***** 以下はアップデーターのサードパーティーライブラリの更新処理をベースに実装したもの *****

    platform_type: Literal['Windows', 'Linux'] = 'Windows' if sys.platform == 'win32' else 'Linux'
    is_arm_device = platform.machine() == 'aarch64'

    # Linux では elevate で root 権限に昇格 (KonomiTV サーバー自体が root 権限で動作しているため)
    if platform_type == 'Linux':
        elevate.elevate(graphical=False)

    # サードパーティーライブラリを随時ダウンロードし、進捗を表示
    # ref: https://github.com/Textualize/rich/blob/master/examples/downloader.py
    print(Padding('サードパーティーライブラリをダウンロードしています…', (1, 2, 0, 2)))
    progress = Progress(
        TextColumn(' '),
        BarColumn(bar_width=9999),
        '[progress.percentage]{task.percentage:>3.1f}%',
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        TextColumn(' '),
    )

    # ダウンロードするサードパーティーライブラリの URL を決定
    thirdparty_compressed_file_name = 'thirdparty-windows.7z'
    if platform_type == 'Linux' and is_arm_device is False:
        thirdparty_compressed_file_name = 'thirdparty-linux.tar.xz'
    elif platform_type == 'Linux' and is_arm_device is True:
        thirdparty_compressed_file_name = 'thirdparty-linux-arm.tar.xz'
    thirdparty_url = THIRDPARTY_BASE_URL + thirdparty_compressed_file_name
    if download_version == 'latest':
        thirdparty_url = thirdparty_url + '.zip'

    # GitHub からサードパーティーライブラリをダウンロード
    thirdparty_response = requests.get(thirdparty_url, stream=True)
    if thirdparty_response.headers.get('Content-length') is not None:
        task_id = progress.add_task('', total=float(thirdparty_response.headers['Content-length']))
    else:
        task_id = progress.add_task('', total=None)

    # ダウンロードしたデータを随時一時ファイルに書き込む
    thirdparty_compressed_file = tempfile.NamedTemporaryFile(mode='wb', delete=False)
    with progress:
        for chunk in thirdparty_response.iter_content(chunk_size=1048576):  # サイズが大きいので1MBごとに読み込み
            thirdparty_compressed_file.write(chunk)
            progress.update(task_id, advance=len(chunk))
    thirdparty_compressed_file.close()  # 解凍する前に close() してすべて書き込ませておくのが重要

    # サードパーティーライブラリを解凍して展開
    print(Padding('サードパーティーライブラリを更新しています… (数秒～数十秒かかります)', (1, 2, 0, 2)))
    progress = Progress(
        TextColumn(' '),
        BarColumn(bar_width=9999),
        TimeElapsedColumn(),
        TextColumn(' '),
    )
    progress.add_task('', total=None)
    with progress:

        # 自分自身が動いている Python を上書きしてしまうと途中で終了してしまうので、一旦インストールディレクトリ直下に解凍し、
        # 最後に (インストールディレクトリ)/server/ 内に移動する

        # latest のみ、圧縮ファイルがさらに zip で包まれているので、それを解凍
        thirdparty_compressed_file_path = thirdparty_compressed_file.name
        if download_version == 'latest':
            with zipfile.ZipFile(thirdparty_compressed_file.name, mode='r') as zip_file:
                zip_file.extractall(INSTALLED_DIR)
            thirdparty_compressed_file_path = INSTALLED_DIR / thirdparty_compressed_file_name
            Path(thirdparty_compressed_file.name).unlink()

        if platform_type == 'Windows':
            # Windows: 7-Zip 形式のアーカイブを解凍
            with py7zr.SevenZipFile(thirdparty_compressed_file_path, mode='r') as seven_zip:
                seven_zip.extractall(INSTALLED_DIR)
        elif platform_type == 'Linux':
            # Linux: tar.xz 形式のアーカイブを解凍
            ## 7-Zip だと (おそらく) ファイルパーミッションを保持したまま圧縮することができない？ため、あえて tar.xz を使っている
            ## アーカイブ内のパスが展開先の外を指すエントリ (../ や絶対パス) を拒否するため、tar フィルタを指定する
            with tarfile.open(thirdparty_compressed_file_path, mode='r:xz') as tar_xz:
                tar_xz.extractall(INSTALLED_DIR, filter='tar')
        Path(thirdparty_compressed_file_path).unlink()
        if Path(INSTALLED_DIR / 'thirdparty/.gitkeep').exists() is False:
            Path(INSTALLED_DIR / 'thirdparty/.gitkeep').touch()

    print(Padding('サードパーティーライブラリを更新しました。', (1, 2, 1, 2)))

    def GetEncoderVersion(encoder_name: str) -> None:
        # エンコーダーのバージョン情報を取得する
        ## バージョン情報は出力の1行目にある
        extension = 'exe' if platform_type == 'Windows' else 'elf'
        result = subprocess.run(
            [INSTALLED_DIR / 'thirdparty' / encoder_name / f'{encoder_name.replace("FFmpeg", "ffmpeg")}.{extension}', '--version'],
            stdout = subprocess.PIPE,
            stderr = subprocess.STDOUT,
        )
        encoder_version = result.stdout.decode('utf-8').split('\n')[0]
        ## Copyright (FFmpeg) と by rigaya (HWEncC) 以降の文字列を削除
        encoder_version = re.sub(r' Copyright.*$', '', encoder_version)
        encoder_version = re.sub(r' by rigaya.*$', '', encoder_version)
        encoder_version = encoder_version.replace('ffmpeg', 'FFmpeg').strip()
        print(Padding(f'{encoder_name:<8}: {encoder_version}', (0, 2, 0, 2)))

    # エンコーダーのバージョンを出力する
    encoder_list = ['FFmpeg', 'QSVEncC', 'NVEncC', 'VCEEncC']
    if is_arm_device is True:
        encoder_list = ['FFmpeg', 'rkmppenc']
    for encoder_name in encoder_list:
        GetEncoderVersion(encoder_name)

    # 空行を出力
    print()

    # 新しいサードパーティーライブラリに含まれる Python と、server/.venv/ の仮想環境の Python のマイナーバージョンを比較する
    ## server/.venv/ は server/thirdparty/Python/ を元に作られているため、Python のマイナーバージョンが変わると、
    ## .venv/ 内の C 拡張 (pywin32 など) が新しい Python から読み込めなくなり、KonomiTV サーバーが起動しなくなる
    ## この時点では新しい Python はインストールディレクトリ直下に展開されただけなので、差し替える前に検出して作り直しの手順を案内する
    if platform_type == 'Windows':
        new_python_path = INSTALLED_DIR / 'thirdparty/Python/python.exe'
    else:
        new_python_path = INSTALLED_DIR / 'thirdparty/Python/bin/python'
    new_python_result = subprocess.run(
        [new_python_path, '-c', 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'],
        stdout = subprocess.PIPE,
        stderr = subprocess.DEVNULL,
    )
    new_python_version = new_python_result.stdout.decode('utf-8').strip() if new_python_result.returncode == 0 else None

    # server/.venv/pyvenv.cfg から、仮想環境を作成したときの Python のバージョンを取得する
    ## uv と virtualenv (以前利用していた Poetry が利用) は version_info に、標準ライブラリの venv は version にバージョンを記録する
    venv_config_path = INSTALLED_DIR / 'server/.venv/pyvenv.cfg'
    venv_python_version: str | None = None
    if venv_config_path.exists():
        for line in venv_config_path.read_text(encoding='utf-8').splitlines():
            key, _, value = line.partition('=')
            if key.strip() in ('version_info', 'version'):
                venv_python_version = '.'.join(value.strip().split('.')[:2])
                break

    # マイナーバージョンが異なる場合は、仮想環境を作り直すよう案内する
    ## 自動で作り直さないのは、このスクリプト自体がまさにその仮想環境の Python で動いているため
    if new_python_version is not None and venv_python_version is not None and new_python_version != venv_python_version:
        if platform_type == 'Windows':
            installed_python_path = r'.\thirdparty\Python\python.exe'
        else:
            installed_python_path = './thirdparty/Python/bin/python'
        print(Padding(
            f'[yellow]サードパーティーライブラリの Python のバージョンが {venv_python_version} から {new_python_version} に変わりました。[/yellow]\n'
            f'server/.venv/ の仮想環境は Python {venv_python_version} で作成されているため、このままでは KonomiTV サーバーが起動しません。\n'
            'このスクリプトの終了後、server/ で次のコマンドを実行し、仮想環境を作り直してください。\n'
            '(指定した Python と仮想環境の Python が異なる場合、uv が仮想環境を自動的に作り直します)',
            (0, 2, 1, 2),
        ))
        # コマンドはそのままコピーして実行できるよう、Rich による折り返しを受けない標準出力へ直接書き出す
        ## サードパーティーライブラリ内の Python には uv も含まれているため、グローバルに uv がインストールされていなくても実行できる
        sys.stdout.write(f'  {installed_python_path} -m uv sync --python {installed_python_path}\n\n')

    # 最後に server/thirdparty/ を削除した後、インストールディレクトリ直下から server/ に移動する
    ## この処理のみ、subprocess で外部コマンドで実行する必要がある (実行中の Python の実行ファイル自身を上書きするため)
    ## このプロセスが終了した1秒後に非同期で実行される
    if platform_type == 'Windows':
        command = (
            'powershell -Command "Get-Process | Where-Object { $_.Path -eq \'' +
                str(INSTALLED_DIR / 'server\\thirdparty\\Python\\python.exe') + '\' } | Stop-Process -Force" &&'
            f'rmdir /S /Q {INSTALLED_DIR / "server/thirdparty"!s} > nul &&'
            f'move /Y {INSTALLED_DIR / "thirdparty"!s} {INSTALLED_DIR / "server"!s} > nul'
        )
    elif platform_type == 'Linux':
        command = (
            f'rm -rf {INSTALLED_DIR / "server/thirdparty"!s} &&'
            f'mv {INSTALLED_DIR / "thirdparty"!s} {INSTALLED_DIR / "server"!s}'
        )

    def RunCommandLater(command: str, wait_time: int):
        if sys.platform == 'win32':
            subprocess.Popen(
                f"ping localhost -n {wait_time + 1} > nul && {command}",
                shell = True,
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            )
        else:
            subprocess.Popen(
                f"sleep {wait_time} && {command}",
                shell = True,
            )
    RunCommandLater(command, 2)  # 2秒後に実行する
    sys.exit(0)


if __name__ == '__main__':
    app()
