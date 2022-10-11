
import os
import subprocess
import shutil
from pathlib import Path
from rich import box
from rich import print
from rich.padding import Padding
from rich.panel import Panel
from rich.style import Style
from rich.table import Table
from typing import Literal

from Utils import CreateBasicInfiniteProgress
from Utils import CustomConfirm
from Utils import CustomPrompt
from Utils import IsDockerComposeV2
from Utils import IsDockerInstalled


def Uninstaller() -> None:
    """
    KonomiTV のアンインストーラーの実装
    """

    # プラットフォームタイプ
    ## Windows・Linux・Linux (Docker)
    platform_type: Literal['Windows', 'Linux', 'Linux-Docker'] = 'Windows' if os.name == 'nt' else 'Linux'

    # ***** アンインストール対象の KonomiTV のフォルダのパス *****

    table_02 = Table(expand=True, box=box.SQUARE, border_style=Style(color='#E33157'))
    table_02.add_column('02. アンインストール対象の KonomiTV のフォルダのパスを入力してください。')
    if platform_type == 'Windows':
        table_02.add_row('例: C:\\DTV\\KonomiTV')
    elif platform_type == 'Linux' or platform_type == 'Linux-Docker':
        table_02.add_row('例: /opt/KonomiTV')
    print(Padding(table_02, (1, 2, 1, 2)))

    # アンインストール対象の KonomiTV のフォルダを取得
    uninstall_path: Path
    while True:

        # 入力プロンプト (バリデーションに失敗し続ける限り何度でも表示される)
        uninstall_path = Path(CustomPrompt.ask('アンインストール対象の KonomiTV のフォルダのパス'))

        # バリデーション
        if uninstall_path.is_absolute() is False:
            print(Padding('[red]アンインストール対象の KonomiTV のフォルダは絶対パスで入力してください。', (0, 2, 0, 2)))
            continue
        if uninstall_path.exists() is False:
            print(Padding('[red]アンインストール対象の KonomiTV のフォルダが存在しません。', (0, 2, 0, 2)))
            continue

        # 指定されたフォルダが KonomiTV のフォルダ/ファイル配置と異なる
        ## 大まかにフォルダ/ファイル配置をチェック (すべてのファイル、フォルダがあれば OK)
        if not (
            (uninstall_path / 'config.example.yaml').exists() and
            (uninstall_path / 'License.txt').exists() and
            (uninstall_path / 'Readme.md').exists() and
            (uninstall_path / 'client/').exists() and
            (uninstall_path / 'installer/').exists() and
            (uninstall_path / 'server/').exists() and
            (uninstall_path / 'server/app/').exists() and
            (uninstall_path / 'server/data/').exists() and
            (uninstall_path / 'server/logs/').exists() and
            (uninstall_path / 'server/static/').exists() and
            (uninstall_path / 'server/thirdparty/').exists()
        ):
            print(Padding('[red]指定されたフォルダは KonomiTV のフォルダ/ファイル配置と異なります。', (0, 2, 0, 2)))
            continue

        # すべてのバリデーションを通過したのでループを抜ける
        break

    # Linux: Docker + Docker Compose がインストールされている & アンインストールフォルダに docker-compose.yaml があれば
    # Docker でインストールしたことが推測されるので、プラットフォームタイプを Linux-Docker に切り替える
    ## インストーラーで Docker を使わずにインストールした場合は docker-compose.yaml は生成されない
    if platform_type == 'Linux' and IsDockerInstalled() and Path(uninstall_path / 'docker-compose.yaml').exists():
        platform_type = 'Linux-Docker'

    # アンインストールするかの最終確認
    print(Padding(Panel(
        '[yellow]KonomiTV サーバーに保存されているすべてのユーザーデータが削除されます。\n'
        'もとに戻すことはできません。本当に KonomiTV をアンインストールしますか？[/yellow]\n'
        'なお、config.yaml で指定されたフォルダに保存されているキャプチャ画像は\n'
        'アンインストール後も引き続き残りますので、ご安心ください。',
        box = box.SQUARE,
        border_style = Style(color='#E33157'),
    ), (1, 2, 1, 2)))

    # Docker を使ってインストールするかを訊く (Y/N)
    ## 誤実行防止のため、デフォルトは N にしておく
    confirm_uninstall = bool(CustomConfirm.ask('KonomiTV のアンインストール', default=False))
    if confirm_uninstall is False:
        print(Padding('KonomiTV のアンインストールをキャンセルしました。', (1, 2, 0, 2)))
        return  # 処理を中断

    # ***** Windows: Windows サービスの終了・アンインストール *****

    if platform_type == 'Windows':

        # Windows サービスを終了
        print(Padding('Windows サービスを終了しています…', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:
            python_executable_path = uninstall_path / 'server/thirdparty/Python/python.exe'
            subprocess.run(
                args = [python_executable_path, '-m', 'pipenv', 'run', 'python', 'KonomiTV-Service.py', 'stop'],
                cwd = uninstall_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            )

        # Windows サービスをアンインストール
        print(Padding('Windows サービスをアンインストールしています…', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:
            python_executable_path = uninstall_path / 'server/thirdparty/Python/python.exe'
            subprocess.run(
                args = [python_executable_path, '-m', 'pipenv', 'run', 'python', 'KonomiTV-Service.py', 'remove'],
                cwd = uninstall_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            )

    # ***** Linux: PM2 サービスの終了・アンインストール *****

    elif platform_type == 'Linux':

        # PM2 サービスを終了
        print(Padding('PM2 サービスを終了しています…', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:
            subprocess.run(
                args = ['/usr/bin/env', 'pm2', 'stop', 'KonomiTV'],
                cwd = uninstall_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            )

        # PM2 サービスをアンインストール
        print(Padding('PM2 サービスをアンインストールしています…', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:
            subprocess.run(
                args = ['/usr/bin/env', 'pm2', 'delete', 'KonomiTV'],
                cwd = uninstall_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            )
            subprocess.run(
                args = ['/usr/bin/env', 'pm2', 'save'],
                cwd = uninstall_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            )

    # ***** Linux-Docker: Docker イメージ/コンテナの削除 *****

    elif platform_type == 'Linux-Docker':

        # Docker Compose V2 かどうかでコマンド名を変える
        ## Docker Compose V1 は docker-compose 、V2 は docker compose という違いがある
        ## Docker がインストールされていない場合は V1 のコマンドが代入されるが、そもそも非 Docker インストールでは参照されない
        docker_compose_command = ['docker-compose'] if IsDockerComposeV2() else ['docker', 'compose']

        # docker compose stop で Docker コンテナを終了
        print(Padding('Docker コンテナを終了しています…', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:
            subprocess.run(
                args = [*docker_compose_command, 'stop'],
                cwd = uninstall_path,  # カレントディレクトリを KonomiTV のアンインストールフォルダに設定
                stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            )

        # docker compose up -d --force-recreate で Docker コンテナを削除
        ## アンインストールなので、Docker イメージも同時に削除する
        print(Padding('Docker イメージ/コンテナを削除しています…', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:
            subprocess.run(
                args = [*docker_compose_command, 'down', '--rmi', 'all', '--volumes', '--remove-orphans'],
                cwd = uninstall_path,  # カレントディレクトリを KonomiTV のアンインストールフフォルダに設定
                stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            )

    # アンインストール対象の KonomiTV のフォルダを削除
    ## サービスを終了・アンインストールしたあとなので、心置きなく削除できる
    ## TODO: Windows で Git インストールすると一部の Git ファイルが削除できないっぽい…？
    print(Padding('インストールされているファイルを削除しています…', (1, 2, 0, 2)))
    progress = CreateBasicInfiniteProgress()
    progress.add_task('', total=None)
    with progress:
        shutil.rmtree(uninstall_path, ignore_errors=True)

    # アンインストール完了
    print(Padding(Panel(
        'KonomiTV のアンインストールが完了しました。\n'
        '今まで利用していただきありがとうございました！',
        box = box.SQUARE,
        border_style = Style(color='#E33157'),
    ), (1, 2, 0, 2)))
