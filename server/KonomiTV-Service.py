
# Windows サービスを実装するコード
# ref: https://metallapan.se/post/windows-service-pywin32-pyinstaller/

import argparse
import ctypes
import pathlib
import shutil
import site
import subprocess
import sys
import time
import threading
import winreg
from typing import Dict, List

# サービスからの起動では、pipenv (venv) の仮想環境にあるパッケージが読み込めない
# そのため、手動で venv の site-packages のパスを追加する
# ref: https://github.com/mhammond/pywin32/issues/1450#issuecomment-564717340
base_dir = pathlib.Path(__file__).parent
site.addsitedir(str(base_dir / '.venv/Lib/site-packages'))

# pywin32 のライブラリ群をインポート
# site-packages のパスを修正した後にインポートしないとサービスが起動できない
import servicemanager
import win32service
import win32serviceutil


def GetNetworkDriveList() -> List[Dict[str, str]]:
    """
    レジストリからログイン中のユーザーがマウントしているネットワークドライブのリストを取得する

    Returns:
        List[Dict[str, str]]: ネットワークドライブのドライブレターとパスのリスト
    """

    # ネットワークドライブの情報が入る辞書のリスト
    network_drives: List[Dict[str, str]] = []

    # ネットワークドライブの情報が格納されているレジストリの HKEY_CURRENT_USER\Network を開く
    # ref: https://itasuke.hatenablog.com/entry/2018/01/08/133510
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Network') as root_key:

        # HKEY_CURRENT_USER\Network 以下のキーを列挙
        for key in range(winreg.QueryInfoKey(root_key)[0]):
            drive_letter = winreg.EnumKey(root_key, key)

            # HKEY_CURRENT_USER\Network 以下のキーをそれぞれ開く
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f'Network\{drive_letter}') as key:
                for sub_key in range(winreg.QueryInfoKey(key)[1]):

                    # 値の名前、データ、データ型を取得
                    name, data, regtype = winreg.EnumValue(key, sub_key)

                    # リストに追加
                    if name == 'RemotePath':
                        network_drives.append({
                            'drive_letter': drive_letter,
                            'remote_path': data,
                        })

    return network_drives


class KonomiTVServiceFramework(win32serviceutil.ServiceFramework):

    _svc_name_ = 'KonomiTV Service'
    _svc_display_name_ = 'KonomiTV Service'
    _svc_description_ = 'KonomiTV Windows Service.'


    def SvcDoRun(self):
        """ Windows サービスのメインループ """

        # Windows サービスのステータスを起動待機中に設定
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)

        # 取得したすべてのネットワークドライブのマウントを試みる
        ## Windows サービスは異なるセッションで実行されるため、既定では（ユーザー権限で動作していても）ネットワークドライブはマウントされない
        ## そこで、レジストリから取得したネットワークドライブのリストからネットワークドライブをマウントする
        ## マウントには時間がかかることがあるため、threading で並列に実行する (ThreadPoolExecutor はなぜか動かなかった)
        threads: List[threading.Thread] = []
        for network_drive in GetNetworkDriveList():
            thread = threading.Thread(target=lambda: subprocess.run([
                'net', 'use', f'{network_drive["drive_letter"]}:', network_drive['remote_path'],
            ]))
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join()

        # 仮想環境上の Python から KonomiTV のサーバープロセス (Uvicorn) を起動
        self.process = subprocess.Popen(
            [base_dir / ".venv/Scripts/python.exe", '-X', 'utf8', base_dir / 'KonomiTV.py'],
            cwd = base_dir,  # カレントディレクトリを指定
        )

        # Windows サービスのステータスを起動中に設定
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)

        # プロセスが終了するまで待つ
        ## Windows サービスではメインループが終了してしまうとサービスも終了扱いになってしまう
        self.process.wait()


    def SvcStop(self):
        """ Windows サービスを停止する """

        # Windows サービスのステータスを停止待機中に設定
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)

        ## Windows サービス上からはなぜか process.send_signal() や os.kill() が使えない
        ## そのため、Windows API を直で叩いて Ctrl+C のシグナル (SIGINT) を送る
        ## ref: https://gist.github.com/chikatoike/5424539
        CTRL_C_EVENT = 0
        ctypes.windll.kernel32.FreeConsole() # 現在のコンソールプロセスを解放
        ctypes.windll.kernel32.AttachConsole(self.process.pid)  # Uvicorn のコンソールプロセスにアタッチ
        ctypes.windll.kernel32.SetConsoleCtrlHandler(0, 1)  # これがないと自分自身も SIGINT で終了してしまう

        # SIGINT を送って Uvicorn を終了させる
        ## subprocess.terminate() だとシグナルではなく直接プロセスが終了されてしまうため、
        ## atexit などのシグナルベースのクリーンアップ処理が実行されない
        ctypes.windll.kernel32.GenerateConsoleCtrlEvent(CTRL_C_EVENT, 0)

        # Waiting for connections to close. となって終了できない場合があるので、少し待ってからもう一度シグナルを送る
        time.sleep(0.5)
        ctypes.windll.kernel32.GenerateConsoleCtrlEvent(CTRL_C_EVENT, 0)

        # 現在のコンソールプロセスを解放
        ## これがないとイベントログに The Python service control handler failed. と謎のエラーが記録されてしまう
        ## アタッチしたコンソールは解放するのがお作法なんだろうか…
        ctypes.windll.kernel32.FreeConsole()

        # 3秒待ってまだプロセスが終了していなければ、プロセスを強制終了する
        ## エンコードタスクが動作中の場合に起きやすい
        ## クリーンアップ処理はすでに行われているので、強制終了してしまっても問題ない
        time.sleep(3)
        if self.process.poll() is None:
            self.process.terminate()

        # Windows サービスのステータスを停止中に設定
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)


def init():

    if len(sys.argv) == 1:

        # サービスを起動
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(KonomiTVServiceFramework)
        servicemanager.StartServiceCtrlDispatcher()

    else:

        # サービスインストール時のイベント
        def Install(args):

            # インストールする前に、.venv/Lib/site-packages 以下の pywin32_system32 フォルダから必要な DLL を win32 フォルダにコピーする
            # これをやっておかないとサービスが起動できない
            shutil.copy(
                base_dir / '.venv/Lib/site-packages/pywin32_system32/pythoncom310.dll',
                base_dir / '.venv/Lib/site-packages/win32/pythoncom310.dll',
            )
            shutil.copy(
                base_dir / '.venv/Lib/site-packages/pywin32_system32/pywintypes310.dll',
                base_dir / '.venv/Lib/site-packages/win32/pywintypes310.dll',
            )

            # ユーザー名とパスワードを取得
            username: str = args.username
            password: str = args.password

            # HandleCommandLine に直接引数を指定して、サービスのインストールを実行
            win32serviceutil.HandleCommandLine(
                cls = KonomiTVServiceFramework,
                argv = [sys.argv[0], '--startup', 'auto', '--username', f'.\{username}', '--password', password, 'install'],
            )

        # サービスアンインストール時のイベント
        def Uninstall(args):

            # HandleCommandLine に直接引数を指定して、サービスのアンインストールを実行
            win32serviceutil.HandleCommandLine(
                cls = KonomiTVServiceFramework,
                argv = [sys.argv[0], 'remove'],
            )

        # 引数解析
        ## "install" と "uninstall" の2つのサブコマンドを実装している
        ## ref: https://sig9.org/archives/4478
        parser = argparse.ArgumentParser(
            formatter_class = argparse.RawTextHelpFormatter,
            description = 'KonomiTV Windows Service Launcher.',
        )
        subparsers = parser.add_subparsers()
        parser_install = subparsers.add_parser('install', help='install KonomiTV service')
        parser_install.add_argument('--username', help='username under which KonomiTV service runs', required=True)
        parser_install.add_argument('--password', help='password of the user under which KonomiTV service runs', required=True)
        parser_install.set_defaults(handler=Install)
        parser_uninstall = subparsers.add_parser('uninstall', help='uninstall KonomiTV service')
        parser_uninstall.set_defaults(handler=Uninstall)
        args = parser.parse_args()
        if hasattr(args, 'handler'):
            args.handler(args)
        else:
            parser.print_help()


if __name__ == '__main__':
    init()
