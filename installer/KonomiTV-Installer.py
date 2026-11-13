
import argparse
import ctypes
import os
import platform
import signal
import subprocess
import sys
import threading
import traceback
from typing import Any

import distro
import elevate
from rich import print
from rich.padding import Padding
from rich.prompt import Prompt
from rich.rule import Rule
from rich.style import Style

from Installer import Installer
from ServiceAccountChanger import ServiceAccountChanger
from Uninstaller import Uninstaller
from Updater import Updater
from Utils import (
    CreateTable,
    CustomPrompt,
    EmitJSONProgress,
    EnableJSONProgress,
    GetNetworkDriveList,
    InstallerAbortError,
    InstallerAnswers,
    ShowPanel,
)


# インストール or アップデート対象の KonomiTV バージョン
TARGET_VERSION = '0.14.1'

def ShowHeader():
    print(Padding(Rule(
        title = f'KonomiTV version {TARGET_VERSION} Installer',
        characters='─',
        style = Style(color='#E33157'),
        align = 'center',
    ), (1, 2, 0, 2)))

# main() 関数内のすべての処理は管理者権限 (Windows) / root 権限 (Linux) で実行される
def main(args: argparse.Namespace) -> bool:
    """
    インストーラーのメイン処理

    Args:
        args (argparse.Namespace): コマンドライン引数 (サブコマンドを省略した場合は、実行する処理をメニューから選ばせる)

    Returns:
        bool: 選ばれた処理に成功したかどうか
    """

    # Windows のみ、コンソールにタイトルを設定
    ## 基本的には UAC で昇格した時点で conhost.exe が起動されるため、タイトルが設定されていないとみすぼらしい
    # ref: https://stackoverflow.com/a/20864842/17124142
    if os.name == 'nt':
        ctypes.windll.kernel32.SetConsoleTitleW(f'KonomiTV version {TARGET_VERSION} Installer')

    # Windows のみ、ログオン中ユーザーのすべてのネットワークドライブのマウントを試みる
    ## UAC で昇格した環境では、ログオン中ユーザーのネットワークドライブはマウントされていない (Windows の制限)
    ## そこで、レジストリから取得したネットワークドライブのリストからネットワークドライブをマウントする
    ## マウントには時間がかかることがあるため、threading で並列に実行する (ThreadPoolExecutor はなぜか動かなかった)
    if os.name == 'nt':

        # ログオン中ユーザーがマウントしているネットワークドライブごとに実行
        threads: list[threading.Thread] = []
        for network_drive in GetNetworkDriveList():

            # net use コマンドでネットワークドライブをマウントするスレッドを作成し、リストに追加
            def run():
                try:
                    subprocess.run(
                        ['net', 'use', f'{network_drive["drive_letter"]}:', network_drive['remote_path']],
                        stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                        stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
                        timeout = 5,  # マウントできたかに関わらず、5秒でタイムアウト
                    )
                except subprocess.TimeoutExpired:
                    pass  # タイムアウトになっても何もしない
            thread = threading.Thread(target=run)
            threads.append(thread)

            # スレッドを実行開始
            thread.start()

        # すべてのスレッドの実行を待機する
        for thread in threads:
            thread.join()

    # ヘッダーを表示
    ShowHeader()

    print(Padding('KonomiTV のインストール/アップデート/アンインストールを行うインストーラーです。', (1, 2, 0, 2)))

    # サポートされているアーキテクチャ
    ## AMD64 : Windows (x64)
    ## x86_64: Linux (x64)
    ## aarch64: Linux (arm64)
    supported_arch = ['AMD64', 'x86_64', 'aarch64']
    current_arch = platform.machine()

    # CPU のアーキテクチャから実行可否を判定
    if current_arch not in supported_arch:
        ShowPanel([
            f'[red]KonomiTV は {current_arch} アーキテクチャに対応していません。[/red]',
        ])
        return False  # 処理中断

    # Ubuntu 20.04 LTS / Debian 11 以降以外の Linux ディストリビューションの場合
    ## Ubuntu 20.04 LTS / Debian 11 以降以外の Linux ディストリビューションは正式にサポートされていない旨を表示する
    ## Debian 11 の glibc バージョンは 2.31 で、Ubuntu 20.04 LTS (更新版) の glibc バージョンと同じ
    ## Linux ディストリビューションは数が多すぎるので、すべて動作確認なんてやってられない……
    if os.name != 'nt' and not (distro.id() == 'ubuntu' and int(distro.major_version()) >= 20) and \
        not (distro.id() == 'debian' and int(distro.major_version()) >= 11):
        table = CreateTable()
        table.add_column(
            f'[yellow]注意: KonomiTV は {distro.name(pretty=True)} を正式にサポートしていません。[/yellow]\n'
            '動作する可能性はありますが、動作しない場合もサポートは一切できません。\n'
            '特に glibc 2.31 未満の OS では、サードパーティーライブラリの関係で動作しません。\n'
            '対応コストを鑑み、Ubuntu/Debian 以外のサポート予定はありません。予めご了承ください。'
        )
        if current_arch == 'x86_64':
            table.add_row(
                'なお、Docker でインストールする場合の OS は Ubuntu 22.04 LTS ベースのため、\n'
                'ホスト OS が Ubuntu/Debian 以外でも動作することが期待されます。\n'
                'Ubuntu/Debian 以外の OS にインストールする際は、Docker でのインストールを推奨します。'
            )
        print(Padding(table, (1, 2, 0, 2)))

    # サブコマンドが指定されている場合は、メニューを表示せずにその処理を実行する
    command: str | None = args.command
    is_development_version: bool = args.dev if command in ('install', 'update') else False
    if command is None:

        menu_lines = [
            f'01. この PC 上に KonomiTV (version {TARGET_VERSION}) を[bold]新規インストール[/bold]するには [bold cyan]1[/bold cyan] を、',
            f'    この PC 上の KonomiTV を version {TARGET_VERSION} へ[bold]アップデート[/bold]するには [bold cyan]2[/bold cyan] を、',
            '    この PC 上の KonomiTV を[bold]アンインストール[/bold]するには [bold cyan]3[/bold cyan] を入力してください。',
            '',
            '    master ブランチの最新コミットが反映されている[bold]開発版をインストール[/bold]するには [bold cyan]4[/bold cyan] を、',
            '    [bold]開発版へアップデート[/bold]するには [bold cyan]5[/bold cyan] を入力してください。',
            '    なお、開発版の安定動作は保証されていないため、予めご了承の上ご利用ください。',
        ]
        run_type_prompt = f'v{TARGET_VERSION} をインストール (1) / v{TARGET_VERSION} へアップデート (2) / アンインストール (3)\n  開発版をインストール (4) / 開発版へアップデート (5)'
        run_type_choices = ['1', '2', '3', '4', '5']

        # Windows のみ、Windows サービスの実行アカウントの変更をメニューに追加する
        if os.name == 'nt':
            menu_lines += [
                '',
                '    この PC 上の KonomiTV の Windows サービスの[bold]実行アカウントを変更[/bold]するには [bold cyan]6[/bold cyan] を入力してください。',
                '    ネットワークドライブや NAS を使いたくなったときや、Windows のパスワードを変更したときに利用します。',
            ]
            run_type_prompt += ' / 実行アカウントを変更 (6)'
            run_type_choices.append('6')
        ShowPanel(menu_lines, padding=(1, 2, 1, 2))

        # 実行タイプ (インストール or アップデート or アンインストール or 実行アカウントの変更)
        ## choices を指定することで、自動的にバリデーションが行われる（超便利）
        run_type = int(CustomPrompt.ask(run_type_prompt, default='1', choices=run_type_choices))
        command = {1: 'install', 2: 'update', 3: 'uninstall', 4: 'install', 5: 'update', 6: 'change-service-account'}[run_type]
        is_development_version = run_type in (4, 5)

    # 質問への回答をコマンドライン引数から取得する
    ## 回答として扱うのは質問に対応するコマンドライン引数だけで、実行する処理の選択やモードを表すコマンドライン引数は除外する
    answers_dict: dict[str, str | list[str] | bool] = {}
    for key, value in vars(args).items():
        if key in ('command', 'dev', 'non_interactive', 'json_progress') or value is None:
            continue
        answers_dict[key] = value

    answers = InstallerAnswers(answers_dict, is_non_interactive=args.command is not None and args.non_interactive is True)

    # Windows: コンソール出力前のおまじないとして、適当な PowerShell コマンドを実行する
    ## なぜ直るのかは全くもって謎だが、一度 PowerShell コマンドを実行しておくことで、print(Padding('Test', (1, 2, 0, 2)) のように
    ## Padding ありで print() した際に余計な改行が入る問題 (Rich または conhost.exe のバグ？) を回避することができる
    ## なお、Python 側から何か出力する前に下記のコマンドを実行すると効果がない（ただしなぜか Rich からレガシーコンソール扱いされなくなる）
    ## conhost.exe、早く絶滅してくれ……
    if os.name == 'nt':
        subprocess.run(
            args = ['powershell', '-Command', 'echo $PSVersionTable'],
            stdout = subprocess.DEVNULL,  # 標準出力を表示しない
            stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
        )

    # 実行タイプごとにそれぞれの実装を呼び出す
    ## 開発版では、master ブランチの最新コミットをインストール・アップデートする
    version = 'latest' if is_development_version is True else TARGET_VERSION
    if command == 'install':
        return Installer(version, answers)
    elif command == 'update':
        return Updater(version, answers)
    elif command == 'uninstall':
        return Uninstaller(answers)
    else:
        return ServiceAccountChanger(answers)


def ParseArguments() -> argparse.Namespace:
    """
    コマンドライン引数を解析する
    サブコマンドを省略すると、従来どおりメニューから実行する処理を選ぶ対話モードで起動する
    サブコマンドを指定すると、コマンドライン引数で指定されなかった質問だけを対話的に質問する
    さらに --non-interactive を指定すると一切質問せず、回答が足りないか不正なときは終了コード 2 で終了する

    Returns:
        argparse.Namespace: 解析したコマンドライン引数
    """

    parser = argparse.ArgumentParser(
        prog = 'KonomiTV-Installer',
        description = f'KonomiTV version {TARGET_VERSION} Installer',
    )
    subparsers = parser.add_subparsers(dest='command')

    # すべてのサブコマンドに共通のコマンドライン引数
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument('--non-interactive', action='store_true',
        help='Do not ask any questions. Exit with code 2 if a required answer is missing or invalid.')
    common_parser.add_argument('--json-progress', action='store_true',
        help='Write progress as JSON Lines to stdout. Human-readable output is written to stderr.')

    # Windows サービスの実行アカウントに関するコマンドライン引数 (インストールと実行アカウントの変更で共通)
    service_account_parser = argparse.ArgumentParser(add_help=False)
    service_account_parser.add_argument('--service-account', choices=['LocalSystem', 'User'],
        help='(Windows) Account under which KonomiTV service runs. Defaults to User if a folder is on the network, otherwise LocalSystem.')
    service_account_parser.add_argument('--service-user',
        help='(Windows) Username under which KonomiTV service runs when --service-account is User. Defaults to the current user.')
    service_account_parser.add_argument('--service-password',
        help='(Windows) Password of --service-user when --service-account is User.')

    install_parser = subparsers.add_parser('install', parents=[common_parser, service_account_parser], help='Install KonomiTV.')
    install_parser.add_argument('--dev', action='store_true', help='Install the latest development version (master branch).')
    install_parser.add_argument('--install-path', help='Folder to install KonomiTV into.')
    install_parser.add_argument('--backend', choices=['EDCB', 'Mirakurun'], help='Backend to use. Defaults to EDCB.')
    install_parser.add_argument('--edcb-url', help='URL of the EDCB (EpgTimerNW) TCP API. e.g. tcp://127.0.0.1:4510/')
    install_parser.add_argument('--mirakurun-url', help='URL of the Mirakurun / mirakc HTTP API. e.g. http://127.0.0.1:40772/')
    install_parser.add_argument('--encoder', choices=['FFmpeg', 'QSVEncC', 'NVEncC', 'VCEEncC', 'rkmppenc'],
        help='Encoder to use. Defaults to the one detected from the GPU.')
    install_parser.add_argument('--recorded-folder', action='append', help='Recorded folder. Can be specified multiple times.')
    install_parser.add_argument('--capture-upload-folder', action='append', help='Folder to save uploaded captures. Can be specified multiple times.')
    install_parser.add_argument('--docker', action=argparse.BooleanOptionalAction, default=None,
        help='(Linux) Install with Docker + Docker Compose. Defaults to yes if Docker is installed.')

    update_parser = subparsers.add_parser('update', parents=[common_parser], help='Update KonomiTV.')
    update_parser.add_argument('--dev', action='store_true', help='Update to the latest development version (master branch).')
    update_parser.add_argument('--update-path', help='Folder where KonomiTV is installed.')

    uninstall_parser = subparsers.add_parser('uninstall', parents=[common_parser], help='Uninstall KonomiTV.')
    uninstall_parser.add_argument('--uninstall-path', help='Folder where KonomiTV is installed.')
    uninstall_parser.add_argument('--yes', action='store_true', default=None,
        help='Confirm the uninstallation. Required with --non-interactive.')

    change_service_account_parser = subparsers.add_parser('change-service-account', parents=[common_parser, service_account_parser],
        help='(Windows) Change the account under which KonomiTV service runs.')
    change_service_account_parser.add_argument('--install-path', help='Folder where KonomiTV is installed.')

    return parser.parse_args()


if __name__ == '__main__':

    # コマンドライン引数を解析する
    ## 引数が不正な場合は、argparse がエラーメッセージを表示して終了コード 2 で終了する
    args = ParseArguments()
    is_non_interactive: bool = args.command is not None and args.non_interactive is True

    # --json-progress が指定された場合は、標準出力に JSON の進捗を出力する
    if args.command is not None and args.json_progress is True:
        EnableJSONProgress()

    # 終了コード
    ## 0: 成功・1: 失敗 (処理の中断・予期しないエラーを含む)・2: 非対話モードで回答が足りないか不正
    exit_code = 1

    ## KeyboardInterrupt が複数回送出されないようにする
    ## ref: https://github.com/Nuitka/Nuitka/issues/1477
    keyboard_interrupted = False
    def keyboard_interrupt_handler(signal_number: int, frame: Any):
        global keyboard_interrupted
        if keyboard_interrupted is False:
            keyboard_interrupted = True
            raise KeyboardInterrupt()
    signal.signal(signal.SIGINT, keyboard_interrupt_handler)

    try:

        # 管理者権限 (Windows) / root 権限 (Linux) に昇格
        ## Windows 向けに配布する .exe では既に PyInstaller 側の機能 (--uac-admin) を使い管理者に昇格しているため、何も行われない
        ## graphical=False で pkexec を使わずに sudo コマンドで root 権限に昇格するようにしている (pkexec だと諸々問題がある)
        elevate.elevate(graphical=False)

    # UAC がキャンセルされるなどして管理者権限が得られなかったとき
    except OSError:
        # ヘッダーを表示
        ShowHeader()
        if os.name == 'nt':
            ShowPanel([
                '[yellow]KonomiTV のインストール/アップデート/アンインストールには管理者権限が必要です。[/yellow]',
                '「このアプリがデバイスに変更を加えることを許可しますか？」のダイヤログで [はい] をクリックしてください。',
            ])
        else:
            ShowPanel([
                '[yellow]KonomiTV のインストール/アップデート/アンインストールには root 権限が必要です。[/yellow]',
            ])

    # main() を実行
    else:
        try:
            exit_code = 0 if main(args) is True else 1
        except InstallerAbortError as ex:
            # 非対話モードで回答が足りないか不正なため、理由を表示して終了コード 2 で終了する
            ShowPanel([
                '[red]非対話モードで実行しているため、処理を中断しました。[/red]',
                str(ex),
            ])
            exit_code = 2
        except KeyboardInterrupt:
            ShowPanel([
                '[yellow]Ctrl+C が押されたため、処理を中断しました。[/yellow]',
            ])
        except Exception:
            ShowPanel([
                '[red]インストーラーの処理中に予期しないエラーが発生しました。[/red]',
                'お手数をおかけしますが、下記のログを開発者に報告してください。',
            ])
            ShowPanel([
                traceback.format_exc().rstrip(),
            ], padding=(0, 2, 0, 2))

    # 終了時のプロンプト (Windows のみ)
    ## 処理がなくなると conhost.exe のウインドウも消滅し、メッセージが読めなくなるため
    ## 非対話モードでは、呼び出し元のアプリケーションが終了を待っているため、プロンプトを省略してすぐに終了する
    if os.name == 'nt' and is_non_interactive is False:
        print()  # 改行
        try:
            Prompt.ask('  終了するには何かキーを押してください')
        except Exception:
            pass

    print(Padding(Rule(
        style = Style(color='#E33157'),
        align = 'center',
    ), (1, 2, 1, 2)))

    EmitJSONProgress('result', success=exit_code == 0, exit_code=exit_code)
    sys.exit(exit_code)
