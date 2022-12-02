
import ctypes
import distro
import elevate
import os
import platform
import signal
import subprocess
import threading
import traceback
from rich import box
from rich import print
from rich.padding import Padding
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.style import Style
from rich.table import Table

from Installer import Installer
from Uninstaller import Uninstaller
from Updater import Updater
from Utils import CustomPrompt
from Utils import GetNetworkDriveList


# インストール or アップデート対象の KonomiTV バージョン
TARGET_VERSION = '0.6.2'

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
                        timeout = 3,  # マウントできたかに関わらず、3秒でタイムアウト
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

    print(Padding(Rule(
        title = f'KonomiTV version {TARGET_VERSION} Installer',
        characters = '─',
        style = Style(color='#E33157'),
        align = 'center',
    ), (1, 2, 0, 2)))

    print(Padding('KonomiTV のインストール/アップデート/アンインストールを行うインストーラーです。', (1, 2, 0, 2)))

    # サポートされているアーキテクチャ
    ## AMD64 : Windows (x64)
    ## x86_64: Linux (x64)
    supported_arch = ['AMD64', 'x86_64']

    # CPU のアーキテクチャから実行可否を判定
    # arm64 で実行できないようにする
    if platform.machine() not in supported_arch:
        print(Padding(Panel(
            f'[red]KonomiTV は {platform.machine()} アーキテクチャに対応していません。[/red]\n'
            f'Linux (arm64) には今後のアップデートで対応予定ですが、現時点では arm64 向けの\n'
            'サードパーティーライブラリを用意できていないため、正常に動作しません。',
            box = box.SQUARE,
            border_style = Style(color='#E33157'),
        ), (1, 2, 0, 2)))
        return  # 処理中断

    # Ubuntu 20.04 LTS 以降以外の Linux ディストリビューションの場合
    ## Ubuntu 20.04 LTS 以降以外の Linux ディストリビューションは正式にサポートされていない旨を表示する
    ## Linux ディストリビューションは数が多すぎるので、すべて動作確認なんてやってられない……
    if os.name != 'nt' and not (distro.id() == 'ubuntu' and int(distro.major_version()) >= 20):
        table = Table(expand=True, box=box.SQUARE, border_style=Style(color='#E33157'))
        table.add_column(
            f'[yellow]注意: KonomiTV は {distro.name(pretty=True)} を正式にサポートしていません。[/yellow]\n'
            '動作する可能性はありますが、動作しない場合もサポートは一切できません。\n'
            '特に glibc 2.31 未満の OS では、サードパーティーライブラリの関係で動作しません。\n'
            '対応コストを鑑み、Ubuntu 以外のサポート予定はありません。予めご了承ください。'
        )
        table.add_row(
            'なお、Docker でインストールする場合の OS は Ubuntu 22.04 LTS ベースのため、\n'
            'ホスト OS が Ubuntu 以外でも動作することが期待されます。\n'
            'Ubuntu 以外の OS にインストールする際は、Docker でのインストールを推奨します。'
        )
        print(Padding(table, (1, 2, 0, 2)))

    print(Padding(Panel(
        '01. KonomiTV をインストールするときは 1 を、アップデートするときは 2 を、\n'
        '    アンインストールするときは 3 を入力してください。',
        box = box.SQUARE,
        border_style = Style(color='#E33157'),
    ), (1, 2, 1, 2)))

    # 実行タイプ (インストール or アップデート or アンインストール)
    ## choices を指定することで、自動的にバリデーションが行われる（超便利）
    run_type = int(CustomPrompt.ask('インストール(1) / アップデート(2) / アンインストール(3)', default='1', choices=['1', '2', '3']))

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


if __name__ == '__main__':

    # Nuitka の onefile モードでビルドした実行ファイルだと Windows でうまく Ctrl+C がキャッチできない問題の回避策
    ## KeyboardInterrupt が複数回送出されないようにする
    ## ref: https://github.com/Nuitka/Nuitka/issues/1477
    keyboard_interrupted = False
    def keyboard_interrupt_handler(signal_number, frame):
        global keyboard_interrupted
        if keyboard_interrupted is False:
            keyboard_interrupted = True
            raise KeyboardInterrupt()
    signal.signal(signal.SIGINT, keyboard_interrupt_handler)

    try:

        # 管理者権限 (Windows) / root 権限 (Linux) に昇格
        ## Windows 向けに配布する .exe では既に Nuitka 側の機能 (--windows-uac-admin) を使い管理者に昇格しているため、何も行われない
        ## graphical=False で pkexec を使わずに sudo コマンドで root 権限に昇格するようにしている (pkexec だと諸々問題がある)
        elevate.elevate(graphical=False)

    # UAC がキャンセルされるなどして管理者権限が得られなかったとき
    except OSError:

        print(Padding(Rule(
            title = f'KonomiTV version {TARGET_VERSION} Installer',
            characters='─',
            style = Style(color='#E33157'),
            align = 'center',
        ), (1, 2, 0, 2)))

        if os.name == 'nt':
            print(Padding(Panel(
                '[yellow]KonomiTV のインストール/アップデート/アンインストールには管理者権限が必要です。[/yellow]\n'
                '「このアプリがデバイスに変更を加えることを許可しますか？」のダイヤログで [はい] をクリックしてください。',
                box = box.SQUARE,
                border_style = Style(color='#E33157'),
            ), (1, 2, 0, 2)))
        else:
            print(Padding(Panel(
                '[yellow]KonomiTV のインストール/アップデート/アンインストールには root 権限が必要です。[/yellow]',
                box = box.SQUARE,
                border_style = Style(color='#E33157'),
            ), (1, 2, 0, 2)))

    # main() を実行
    else:
        try:
            main()
        except KeyboardInterrupt:
            print(Padding(Panel(
                '[yellow]Ctrl+C が押されたため、処理を中断しました。[/yellow]',
                box = box.SQUARE,
                border_style = Style(color='#E33157'),
            ), (1, 2, 0, 2)))
        except:
            print(Padding(Panel(
                '[red]インストーラーの処理中に予期しないエラーが発生しました。[/red]\n'
                'お手数をおかけしますが、下記のログを開発者に報告してください。',
                box = box.SQUARE,
                border_style = Style(color='#E33157'),
            ), (1, 2, 0, 2)))
            print(Padding(Panel(
                traceback.format_exc().rstrip(),
                box = box.SQUARE,
                border_style = Style(color='#E33157'),
            ), (0, 2, 0, 2)))

    # 終了時のプロンプト (Windows のみ)
    ## 処理がなくなると conhost.exe のウインドウも消滅し、メッセージが読めなくなるため
    if os.name == 'nt':
        print()  # 改行
        try:
            Prompt.ask('  終了するには何かキーを押してください')
        except:
            pass

    print(Padding(Rule(
        style = Style(color='#E33157'),
        align = 'center',
    ), (1, 2, 1, 2)))
