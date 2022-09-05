
import ctypes
import elevate
import os
import subprocess
import threading
from rich import print
from rich import box
from rich.padding import Padding
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.style import Style
from rich.text import Text
from typing import List

from Install import Install
from Uninstall import Uninstall
from Update import Update
from Utils import CustomPrompt
from Utils import GetNetworkDriveList


# インストール or アップデート対象の KonomiTV バージョン
INSTALLER_VERSION = '0.6.0'

# main() 関数内のすべての処理は管理者権限 (Windows) / root 権限 (Linux) で実行される
def main():

    # Windows のみ、コンソールにタイトルを設定
    ## 基本的には UAC で昇格した時点で conhost.exe が起動されるため、タイトルが設定されていないとみすぼらしい
    # ref: https://stackoverflow.com/a/20864842/17124142
    if os.name == 'nt':
        ctypes.windll.kernel32.SetConsoleTitleW(f'KonomiTV version {INSTALLER_VERSION} Installer')

    # Windows のみ、ログオン中ユーザーのすべてのネットワークドライブのマウントを試みる
    ## UAC で昇格した環境では、ログオン中ユーザーのネットワークドライブはマウントされていない (Windows の制限)
    ## そこで、レジストリから取得したネットワークドライブのリストからネットワークドライブをマウントする
    ## マウントには時間がかかることがあるため、threading で並列に実行する (ThreadPoolExecutor はなぜか動かなかった)
    if os.name == 'nt':

        # ログオン中ユーザーがマウントしているネットワークドライブごとに実行
            threads: List[threading.Thread] = []
            for network_drive in GetNetworkDriveList():

                # net use コマンドでネットワークドライブをマウントするスレッドを作成し、リストに追加
                def run():
                    try:
                        subprocess.run(
                            ['net', 'use', f'{network_drive["drive_letter"]}:', network_drive['remote_path']],
                            stdout = subprocess.DEVNULL,  # 標準出力を表示しない
                            stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
                            timeout = 2,  # マウントできたかに関わらず、2秒でタイムアウト
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
        title = f'KonomiTV version {INSTALLER_VERSION} Installer', characters='─',
        style = Style(color='#E33157'),
        align = 'center',
    ), (1, 2, 0, 2)))

    print(Padding(Text(
        'KonomiTV のインストール/アップデート/アンインストールを行うインストーラーです。'
    ), (1, 2, 0, 2)))

    print(Padding(Panel(
        '01. KonomiTV をインストールするときは 1 を、アップデートするときは 2 を、\n'
        '    アンインストールするときは 3 を入力してください。',
        box = box.SQUARE,
        border_style = Style(color='#E33157')
    ), (1, 2, 1, 2)))

    # 実行タイプ (インストール or アップデート or アンインストール)
    ## choices を指定することで、自動的にバリデーションが行われる（超便利）
    run_type = int(CustomPrompt.ask('インストール(1) / アップデート(2) / アンインストール(3)', default='1', choices=['1', '2', '3']))

    # 実行タイプごとにそれぞれの実装を呼び出す
    if run_type == 1:
        Install(INSTALLER_VERSION)
    elif run_type == 2:
        Update(INSTALLER_VERSION)
    elif run_type == 3:
        Uninstall()


if __name__ == "__main__":

    try:

        # 管理者権限 (Windows) / root 権限 (Linux) に昇格
        ## Windows 向けに配布する .exe では既に Nuitka 側の機能 (--windows-uac-admin) を使い管理者に昇格しているため、何も行われない
        elevate.elevate()

        # main() を実行
        main()

    # UAC がキャンセルされるなどして管理者権限が得られなかったとき
    except OSError:

        print(Padding(Rule(
            title = f'KonomiTV version {INSTALLER_VERSION} Installer', characters='─',
            style = Style(color='#E33157'),
            align = 'center',
        ), (1, 2, 0, 2)))

        if os.name == 'nt':
            print(Padding(Text(
                f'KonomiTV のインストール/アップデート/アンインストールには管理者権限が必要です。\n'
                '「このアプリがデバイスに変更を加えることを許可しますか？」のダイヤログで [はい] をクリックしてください。'
            ), (1, 2, 0, 2)))
        else:
            print(Padding(Text(
                f'KonomiTV のインストール/アップデート/アンインストールには root 権限が必要です。'
            ), (1, 2, 0, 2)))

    print(Padding(Rule(
        style = Style(color='#E33157'),
        align = 'center',
    ), (1, 2, 1, 2)))

    # 終了時のプロンプト (Windows のみ)
    ## 処理がなくなると conhost.exe のウインドウも消滅し、メッセージが読めなくなるため
    if os.name == 'nt':
        Prompt.ask('  終了するには何かキーを押してください')
        print()  # 改行
