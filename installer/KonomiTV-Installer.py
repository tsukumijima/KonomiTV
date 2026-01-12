
import ctypes
import os
import platform
import signal
import subprocess
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
from Uninstaller import Uninstaller
from Updater import Updater
from Utils import CreateTable, CustomPrompt, GetNetworkDriveList, ShowPanel


# インストール or アップデート対象の KonomiTV バージョン
TARGET_VERSION = '0.13.0'

def ShowHeader():
    print(Padding(Rule(
        title = f'KonomiTV version {TARGET_VERSION} Installer',
        characters='─',
        style = Style(color='#E33157'),
        align = 'center',
    ), (1, 2, 0, 2)))

# main() 関数内のすべての処理は管理者権限 (Windows) / root 権限 (Linux) で実行される
def main():

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
        return  # 処理中断

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

    ShowPanel([
        f'01. この PC 上に KonomiTV (version {TARGET_VERSION}) を[bold]新規インストール[/bold]するには [bold cyan]1[/bold cyan] を、',
        f'    この PC 上の KonomiTV を version {TARGET_VERSION} へ[bold]アップデート[/bold]するには [bold cyan]2[/bold cyan] を、',
        '    この PC 上の KonomiTV を[bold]アンインストール[/bold]するには [bold cyan]3[/bold cyan] を入力してください。',
        '',
        '    master ブランチの最新コミットが反映されている[bold]開発版をインストール[/bold]するには [bold cyan]4[/bold cyan] を、',
        '    [bold]開発版へアップデート[/bold]するには [bold cyan]5[/bold cyan] を入力してください。',
        '    なお、開発版の安定動作は保証されていないため、予めご了承の上ご利用ください。',
    ], padding=(1, 2, 1, 2))

    # 実行タイプ (インストール or アップデート or アンインストール)
    ## choices を指定することで、自動的にバリデーションが行われる（超便利）
    run_type = int(CustomPrompt.ask(f'v{TARGET_VERSION} をインストール (1) / v{TARGET_VERSION} へアップデート (2) / アンインストール (3)\n  開発版をインストール (4) / 開発版へアップデート (5)', default='1', choices=['1', '2', '3', '4', '5']))

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
    if run_type == 1:
        Installer(TARGET_VERSION)
    elif run_type == 2:
        Updater(TARGET_VERSION)
    elif run_type == 3:
        Uninstaller()
    elif run_type == 4:
        Installer('latest')
    elif run_type == 5:
        Updater('latest')


if __name__ == '__main__':

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
            main()
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
    if os.name == 'nt':
        print()  # 改行
        try:
            Prompt.ask('  終了するには何かキーを押してください')
        except Exception:
            pass

    print(Padding(Rule(
        style = Style(color='#E33157'),
        align = 'center',
    ), (1, 2, 1, 2)))
