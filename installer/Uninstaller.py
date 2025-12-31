
import os
import platform
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any, Literal

from rich import print
from rich.padding import Padding

from Utils import (
    CreateBasicInfiniteProgress,
    CreateTable,
    CustomConfirm,
    CustomPrompt,
    IsDockerComposeV2,
    IsDockerInstalled,
    RunSubprocess,
    ShowPanel,
    ShowSubProcessErrorLog,
)


def Uninstaller() -> None:
    """
    KonomiTV のアンインストーラーの実装
    """

    # プラットフォームタイプ
    ## Windows・Linux・Linux (Docker)
    platform_type: Literal['Windows', 'Linux', 'Linux-Docker'] = 'Windows' if os.name == 'nt' else 'Linux'

    # ARM デバイスかどうか
    is_arm_device = platform.machine() == 'aarch64'

    # ***** アンインストール対象の KonomiTV のフォルダのパス *****

    table_02 = CreateTable()
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

    # Linux: インストールフォルダに docker-compose.yaml があれば
    # Docker でインストールしたことが推測されるので、プラットフォームタイプを Linux-Docker に切り替える
    ## インストーラーで Docker を使わずにインストールした場合は docker-compose.yaml は生成されないことを利用している
    if platform_type == 'Linux' and is_arm_device is False and Path(uninstall_path / 'docker-compose.yaml').exists():

        # 前回 Docker を使ってインストールされているが、今 Docker がインストールされていない
        if IsDockerInstalled() is False:
            ShowPanel([
                '[yellow]この KonomiTV をアンインストールするには、Docker のインストールが必要です。[/yellow]',
                'この KonomiTV は Docker を使ってインストールされていますが、現在 Docker が',
                'インストールされていないため、アンインストールすることができません。',
            ])
            return  # 処理中断

        # プラットフォームタイプを Linux-Docker にセット
        platform_type = 'Linux-Docker'

        # Docker がインストールされているものの Docker サービスが停止している場合に備え、Docker サービスを起動しておく
        ## すでに起動している場合は何も起こらない
        subprocess.run(
            args = ['systemctl', 'start', 'docker'],
            stdout = subprocess.DEVNULL,  # 標準出力を表示しない
            stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
        )

    # アンインストールするかの最終確認
    ShowPanel([
        '[yellow]KonomiTV サーバーに保存されているすべてのユーザーデータが削除されます。',
        'もとに戻すことはできません。本当に KonomiTV をアンインストールしますか？[/yellow]',
        'なお、config.yaml で指定されたフォルダに保存されている録画ファイルや',
        'キャプチャ画像はアンインストール後も引き続き残りますので、ご安心ください。',
    ], padding=(1, 2, 1, 2))

    ## 誤実行防止のため、デフォルトは N にしておく
    confirm_uninstall = bool(CustomConfirm.ask('KonomiTV のアンインストール', default=False))
    if confirm_uninstall is False:
        print(Padding('KonomiTV のアンインストールをキャンセルしました。', (1, 2, 0, 2)))
        return  # 処理を中断

    # ***** Windows: Windows サービスの終了・アンインストール *****

    if platform_type == 'Windows':

        python_executable_path = uninstall_path / 'server/thirdparty/Python/python.exe'

        # Windows サービスを終了
        print(Padding('Windows サービスを終了しています…', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:
            service_stop_result = subprocess.run(
                args = [python_executable_path, '-m', 'poetry', 'run', 'python', 'KonomiTV-Service.py', 'stop'],
                cwd = uninstall_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
                text = True,  # 出力をテキストとして取得する
            )
        # 1060: ERROR_SERVICE_DOES_NOT_EXIST はサービスが存在しない場合に発生するエラーのため無視する
        # 1062: ERROR_SERVICE_NOT_ACTIVE はサービスが起動していない場合に発生するエラーのため無視する
        if 'Error stopping service' in service_stop_result.stdout and \
            '(1060)' not in service_stop_result.stdout and '(1062)' not in service_stop_result.stdout:
            ShowSubProcessErrorLog(
                error_message = 'Windows サービスの終了中に予期しないエラーが発生しました。',
                error_log = service_stop_result.stdout.strip(),
            )
            return  # 処理中断

        # Windows サービスをアンインストール
        print(Padding('Windows サービスをアンインストールしています…', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:
            service_uninstall_result = subprocess.run(
                args = [python_executable_path, '-m', 'poetry', 'run', 'python', 'KonomiTV-Service.py', 'uninstall'],
                cwd = uninstall_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
                text = True,  # 出力をテキストとして取得する
            )
        # 1060: ERROR_SERVICE_DOES_NOT_EXIST はサービスが存在しない場合に発生するエラーのため無視する
        if 'Error removing service' in service_uninstall_result.stdout and '(1060)' not in service_uninstall_result.stdout:
            ShowSubProcessErrorLog(
                error_message = 'Windows サービスのアンインストール中に予期しないエラーが発生しました。',
                error_log = service_uninstall_result.stdout.strip(),
            )
            return  # 処理中断

    # ***** Linux: PM2 サービスの終了・アンインストール *****

    elif platform_type == 'Linux':

        # PM2 サービスを終了
        result = RunSubprocess(
            'PM2 サービスを終了しています…',
            ['/usr/bin/env', 'pm2', 'stop', 'KonomiTV'],
            cwd = uninstall_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
            error_message = 'PM2 サービスの終了中に予期しないエラーが発生しました。',
            error_log_name = 'PM2 のエラーログ',
        )
        if result is False:
            return  # 処理中断

        # PM2 サービスをアンインストール
        result = RunSubprocess(
            'PM2 サービスをアンインストールしています…',
            ['/usr/bin/env', 'pm2', 'delete', 'KonomiTV'],
            cwd = uninstall_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
            error_message = 'PM2 サービスのアンインストール中に予期しないエラーが発生しました。',
            error_log_name = 'PM2 のエラーログ',
        )
        if result is False:
            return  # 処理中断

        # PM2 サービスの状態を保存
        result = RunSubprocess(
            'PM2 サービスの状態を保存しています…',
            ['/usr/bin/env', 'pm2', 'save'],
            cwd = uninstall_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
            error_message = 'PM2 サービスの状態の保存中に予期しないエラーが発生しました。',
            error_log_name = 'PM2 のエラーログ',
        )
        if result is False:
            return  # 処理中断

    # ***** Linux-Docker: Docker イメージ/コンテナの削除 *****

    elif platform_type == 'Linux-Docker':

        # Docker Compose V2 かどうかでコマンド名を変える
        ## Docker Compose V1 は docker-compose 、V2 は docker compose という違いがある
        ## Docker がインストールされていない場合は V1 のコマンドが代入されるが、そもそも非 Docker インストールでは参照されない
        docker_compose_command = ['docker', 'compose'] if IsDockerComposeV2() else ['docker-compose']

        # docker compose stop で Docker コンテナを終了
        result = RunSubprocess(
            'Docker コンテナを終了しています…',
            [*docker_compose_command, 'stop'],
            cwd = uninstall_path,  # カレントディレクトリを KonomiTV のアンインストールフォルダに設定
            error_message = 'Docker コンテナの終了中に予期しないエラーが発生しました。',
            error_log_name = 'Docker Compose のエラーログ',
        )
        if result is False:
            return  # 処理中断

        # docker compose up -d --force-recreate で Docker コンテナを削除
        ## アンインストールなので、Docker イメージも同時に削除する
        result = RunSubprocess(
            'Docker イメージ/コンテナを削除',
            [*docker_compose_command, 'down', '--rmi', 'all', '--volumes', '--remove-orphans'],
            cwd = uninstall_path,  # カレントディレクトリを KonomiTV のアンインストールフォルダに設定
            error_message = 'Docker イメージ/コンテナの削除中に予期しないエラーが発生しました。',
            error_log_name = 'Docker Compose のエラーログ',
        )
        if result is False:
            return  # 処理中断

    # ***** Windows: Windows Defender ファイアウォールから受信規則を削除 *****

    if platform_type == 'Windows':

        print(Padding('Windows Defender ファイアウォールから受信規則を削除しています…', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:

            # 既存の受信規則を削除
            subprocess.run(
                args = ['netsh', 'advfirewall', 'firewall', 'delete', 'rule', 'name=KonomiTV Service'],
                stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            )

    # アンインストール対象の KonomiTV のフォルダを削除
    ## サービスを終了・アンインストールしたあとなので、心置きなく削除できる
    print(Padding('インストールされているファイルを削除しています…', (1, 2, 0, 2)))
    progress = CreateBasicInfiniteProgress()
    progress.add_task('', total=None)
    with progress:
        # .git/ 以下の読み取り専用ファイルを削除できるようにする
        # ref: https://stackoverflow.com/a/4829285/17124142
        def on_rm_error(func: Any, path: str, exc_info: Any):
            os.chmod(path, stat.S_IWRITE)
            os.unlink(path)
        shutil.rmtree(uninstall_path, onerror=on_rm_error)

    # アンインストール完了
    ShowPanel([
        'KonomiTV のアンインストールが完了しました。',
        '今まで利用していただきありがとうございました！',
    ])
