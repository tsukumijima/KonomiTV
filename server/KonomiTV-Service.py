
# Windows サービスを実装するコード
# ref: https://metallapan.se/post/windows-service-pywin32-pyinstaller/

# Windows 以外では動作しないので終了
import os
import sys
if os.name != 'nt':
    print('KonomiTV-Service.py is for Windows only. Doesn\'t work on Linux.')
    sys.exit(1)

# 標準モジュール
import argparse
import ctypes
import psutil
import subprocess
import time
import threading
import winreg
from pathlib import Path
from typing import Any, cast

# pywin32 モジュール
import servicemanager
import win32api
import win32security
import win32service
import win32serviceutil

# KonomiTV サーバーのベースディレクトリ
base_dir = Path(__file__).parent


def GetNetworkDriveList() -> list[dict[str, str]]:
    """
    レジストリからログオン中のユーザーがマウントしているネットワークドライブのリストを取得する

    Returns:
        list[dict[str, str]]: ネットワークドライブのドライブレターとパスのリスト
    """

    # ネットワークドライブの情報が入る辞書のリスト
    network_drives: list[dict[str, str]] = []

    # ネットワークドライブの情報が格納されているレジストリの HKEY_CURRENT_USER\Network を開く
    # ref: https://itasuke.hatenablog.com/entry/2018/01/08/133510
    try:
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

    # なぜかエラーが出ることがあるが、その際は無視する
    except FileNotFoundError:
        pass

    return network_drives


def AddLogOnAsAServicePrivilege(account_name: str) -> None:
    """
    "サービスとしてログオン" (SeServiceLogonRight) 権限をユーザーアカウントに付与する
    "サービスとしてログオン" 権限が付与されていないと、ユーザー権限で Windows サービスを起動することができない
    サービスのインストール/アンインストール同様に、実行には管理者権限が必要
    Python での実装例を見つけるのが大変だった……
    ref: https://github.com/project-renard-survey/xerox-parc-uplib-mirror/blob/master/win32/install-script.py#L445-L461
    ref: https://github.com/flathub/buildbot/blob/flathub/worker/buildbot_worker/scripts/windows_service.py#L480-L508

    Args:
        account_name (str): accountName(str): Windows ユーザーアカウントの名前
    """

    # コンピューター名とユーザーアカウント名から SID を取得
    if '\\' not in account_name or account_name.startswith('.\\'):
        computer_name = os.environ['COMPUTERNAME']
        if not computer_name:
            computer_name: str = win32api.GetComputerName()
            if not computer_name:
                print('Error: Cannot determine computer name.')
                return
        account_name = computer_name + '\\' + account_name.lstrip('.\\')
    account_sid = win32security.LookupAccountName(None, account_name)[0]

    # ユーザーアカウントに SeServiceLogonRight 権限を付与
    policy_handle = win32security.GetPolicyHandle('', win32security.POLICY_ALL_ACCESS)
    win32security.LsaAddAccountRights(policy_handle, account_sid, ('SeServiceLogonRight',))
    win32security.LsaClose(policy_handle)


class KonomiTVServiceFramework(win32serviceutil.ServiceFramework):

    _svc_name_ = 'KonomiTV Service'
    _svc_display_name_ = 'KonomiTV Service'
    _svc_description_ = 'KonomiTV Windows Service.'

    # pythonservice.exe を使わずに Windows サービスを起動する
    ## pythonservice.exe には、環境変数 PATH に Python が登録されている or
    ## DLL を特定フォルダにコピーしないと動作しないなどの問題があり、venv の仮想環境下で動かすのが難しい
    ## そこで、pythonservice.exe は使わず、代わりに venv の仮想環境下の python.exe で直接 Windows サービスを起動する
    ## 公式ドキュメントには何も記述がないが、なぜか動く…
    ## ref: https://stackoverflow.com/a/72134400/17124142
    _exe_name_ = f'{base_dir / ".venv/Scripts/python.exe"}'  # 実行ファイルのパス (venv の仮想環境下の python.exe への絶対パス)
    _exe_args_ = f'-u -E "{base_dir / "KonomiTV-Service.py"}"'  # サービス起動時の引数 (この KonomiTV-Service.py への絶対パス)


    def SvcDoRun(self):
        """ Windows サービスのメインループ """

        # Windows サービスのステータスを起動待機中に設定
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)

        # ログオン中ユーザーのすべてのネットワークドライブのマウントを試みる
        ## Windows サービスは異なるセッションで実行されるため、既定では（ユーザー権限で動作していても）ネットワークドライブはマウントされていない
        ## そこで、レジストリから取得したネットワークドライブのリストからネットワークドライブをマウントする
        ## マウントには時間がかかることがあるため、threading で並列に実行する (ThreadPoolExecutor はなぜか動かなかった)
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

        # 万が一ポートが衝突する Akebi HTTPS Server があったら終了させる
        # ポートが衝突する Akebi HTTPS Server があると KonomiTV サーバーの起動に失敗するため
        from app.constants import CONFIG
        for process in psutil.process_iter(attrs=('name', 'pid', 'cmdline')):
            process_info: dict[str, Any] = cast(Any, process).info
            if ('akebi-https-server.exe' == process_info['name'] and
                f'--listen-address 0.0.0.0:{CONFIG["server"]["port"]}' in ' '.join(process_info['cmdline'])):
                process.kill()

        # 仮想環境上の Python から KonomiTV のサーバープロセス (Uvicorn) を起動
        self.process = subprocess.Popen(
            [base_dir / '.venv/Scripts/python.exe', '-X', 'utf8', base_dir / 'KonomiTV.py'],
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

            # ユーザー名とパスワードを取得
            username: str = args.username
            password: str = args.password

            # 指定されたユーザーアカウントに "サービスとしてログオン" (SeServiceLogonRight) 権限を付与する
            ## "サービスとしてログオン" 権限が付与されていないと、ユーザー権限で Windows サービスを起動することができない
            ## 手動でサービス管理ツールから操作すると自動的に付与されるらしく、気づくのに時間が掛かった…
            AddLogOnAsAServicePrivilege(username)

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
