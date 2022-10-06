
# Windows サービスを実装するコード
# ref: https://metallapan.se/post/windows-service-pywin32-pyinstaller/

# Windows 以外では動作しないので終了
import os
import sys
if os.name != 'nt':
    print('KonomiTV-Service.py is for Windows only. Doesn\'t work on Linux.')
    sys.exit(1)

# 標準パッケージ
import argparse
import ctypes
import pathlib
import shutil
import site
import subprocess
import time
import threading
import winreg
from typing import Any, Dict, List, cast

# サービスからの起動では、pipenv (venv) の仮想環境にあるパッケージが読み込めない
# そのため、手動で venv の site-packages のパスを追加する
# ref: https://github.com/mhammond/pywin32/issues/1450#issuecomment-564717340
base_dir = pathlib.Path(__file__).parent
site.addsitedir(str(base_dir / '.venv/Lib/site-packages'))

# psutil をインポート
# psutil は外部ライブラリなので、パスを追加した後でないと動かない
import psutil

# pywin32 のライブラリ群をインポート
# site-packages のパスを修正した後にインポートしないとサービスが起動できない
import servicemanager
import win32service
import win32serviceutil


def GetNetworkDriveList() -> List[Dict[str, str]]:
    """
    レジストリからログオン中のユーザーがマウントしているネットワークドライブのリストを取得する

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
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f'Network\\{drive_letter}') as key:
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

        # ログオン中ユーザーのすべてのネットワークドライブのマウントを試みる
        ## Windows サービスは異なるセッションで実行されるため、既定では（ユーザー権限で動作していても）ネットワークドライブはマウントされていない
        ## そこで、レジストリから取得したネットワークドライブのリストからネットワークドライブをマウントする
        ## マウントには時間がかかることがあるため、threading で並列に実行する (ThreadPoolExecutor はなぜか動かなかった)
        threads: List[threading.Thread] = []
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

        # 万が一ポートが衝突する Akebi HTTPS Server があったら終了させる
        # ポートが衝突する Akebi HTTPS Server があると KonomiTV サーバーの起動に失敗するため
        from app.constants import CONFIG
        for process in psutil.process_iter(attrs=('name', 'pid', 'cmdline')):
            process_info: Dict[str, Any] = cast(Any, process).info
            if ('akebi-https-server.exe' == process_info['name'] and
                f'--listen-address 0.0.0.0:{CONFIG["server"]["port"]}' in ' '.join(process_info['cmdline'])):
                process.kill()

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
        servicemanager.PrepareToHostSingle(KonomiTVServiceFramework)  # type: ignore
        servicemanager.StartServiceCtrlDispatcher()

    else:

        # 引数設定
        ## ref: https://sig9.org/archives/4478
        parser = argparse.ArgumentParser(
            formatter_class = argparse.RawTextHelpFormatter,
            description = 'KonomiTV Windows Service Launcher.',
        )
        subparsers = parser.add_subparsers()
        parser_install = subparsers.add_parser('install', help='install KonomiTV service')
        parser_install.add_argument('--username', help='username under which KonomiTV service runs', required=True)
        parser_install.add_argument('--password', help='password of the user under which KonomiTV service runs', required=True)
        parser_uninstall = subparsers.add_parser('uninstall', help='uninstall KonomiTV service')
        parser_start = subparsers.add_parser('start', help='start KonomiTV service')
        parser_restart = subparsers.add_parser('restart', help='restart KonomiTV service')
        parser_stop = subparsers.add_parser('stop', help='stop KonomiTV service')

        # サービスインストール時のイベント
        def install_handler(args):

            # インストールする前に、python310.dll を pythonservice.exe のある .venv/Lib/site-packages/win32/ フォルダにコピーする
            # python310.dll がないと pythonservice.exe が Python を実行できず、サービスの起動に失敗する
            if os.path.exists(base_dir / '.venv/Lib/site-packages/win32/python310.dll') is False:
                shutil.copy(
                    base_dir / 'thirdparty/Python/python310.dll',
                    base_dir / '.venv/Lib/site-packages/win32/python310.dll',
                )

            # インストールする前に、.venv/Lib/site-packages/ 以下の pywin32_system32 フォルダから必要な DLL を
            # pythonservice.exe のある .venv/Lib/site-packages/win32/ フォルダにコピーする
            # pythoncom310.dll / pywintypes310.dll がないと pythonservice.exe が Python を実行できず、サービスの起動に失敗する
            if os.path.exists(base_dir / '.venv/Lib/site-packages/win32/pythoncom310.dll') is False:
                shutil.copy(
                    base_dir / '.venv/Lib/site-packages/pywin32_system32/pythoncom310.dll',
                    base_dir / '.venv/Lib/site-packages/win32/pythoncom310.dll',
                )
            if os.path.exists(base_dir / '.venv/Lib/site-packages/win32/pywintypes310.dll') is False:
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
                # 「自動 (遅延開始)」(delayed) でインストールする
                ## 「自動」(auto) だと EDCB や Mirakurun のサービスが起動していない段階で実行されてしまい、EDCB または Mirakurun にアクセスできず起動に失敗する
                ## 「自動 (遅延開始)」だとシステム起動から2分ほど遅れて実行されるが、上記の問題があるため致し方ない
                argv = [sys.argv[0], '--startup', 'delayed', '--username', f'.\\{username}', '--password', password, 'install'],
            )

        # サブコマンドのイベントを登録
        # install コマンド以外は HandleCommandLine() のサブコマンドのエイリアス
        parser_install.set_defaults(handler=install_handler)
        parser_uninstall.set_defaults(handler=lambda args: win32serviceutil.HandleCommandLine(
            cls = KonomiTVServiceFramework, argv = [sys.argv[0], 'remove'],
        ))
        parser_start.set_defaults(handler=lambda args: win32serviceutil.HandleCommandLine(
            cls = KonomiTVServiceFramework, argv = [sys.argv[0], 'start'],
        ))
        parser_restart.set_defaults(handler=lambda args: win32serviceutil.HandleCommandLine(
            cls = KonomiTVServiceFramework, argv = [sys.argv[0], 'restart'],
        ))
        parser_stop.set_defaults(handler=lambda args: win32serviceutil.HandleCommandLine(
            cls = KonomiTVServiceFramework, argv = [sys.argv[0], 'stop'],
        ))

        args = parser.parse_args()
        if hasattr(args, 'handler'):
            args.handler(args)
        else:
            parser.print_help()


if __name__ == '__main__':
    init()
