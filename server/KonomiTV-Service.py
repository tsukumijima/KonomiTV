
# Windows サービスを実装するコード
# ref: https://metallapan.se/post/windows-service-pywin32-pyinstaller/

# Windows 以外では動作しないので終了
import sys  # noqa: I001
if sys.platform != 'win32':
    print('KonomiTV-Service.py is for Windows only. Doesn\'t work on Linux.')
    sys.exit(1)

import os
import subprocess
import threading
import winreg
from pathlib import Path
from typing import Any, cast

import httpx
import psutil
import pywintypes
import servicemanager
import typer
import win32api
import win32con
import win32security
import win32service
import win32serviceutil


# KonomiTV サーバーのベースディレクトリ
BASE_DIR = Path(__file__).parent


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
    _exe_name_ = f'{BASE_DIR / ".venv/Scripts/python.exe"}'  # 実行ファイルのパス (venv の仮想環境下の python.exe への絶対パス)
    _exe_args_ = f'-u -E "{BASE_DIR / "KonomiTV-Service.py"}"'  # サービス起動時の引数 (この KonomiTV-Service.py への絶対パス)


    def __init__(self, args: Any) -> None:
        super().__init__(args)
        self.is_running = False
        self.server_process: subprocess.Popen[bytes] | None = None
        self.ctrl_c_handler_installed = False  # CTRL+C を無視するハンドラが登録されているか


    @staticmethod
    def _IgnoreCtrlCHandler(ctrl_type: int) -> bool:
        """CTRL+C シグナルだけを捕捉して無視する"""

        return ctrl_type == win32con.CTRL_C_EVENT


    @staticmethod
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
                            name, data, _ = winreg.EnumValue(key, sub_key)

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


    def SvcDoRun(self):
        """ Windows サービスのメインループ """

        # Windows サービスのステータスを起動待機中に設定
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)

        # ログオン中ユーザーのすべてのネットワークドライブのマウントを試みる
        ## Windows サービスは異なるセッションで実行されるため、既定では（ユーザー権限で動作していても）ネットワークドライブはマウントされていない
        ## そこで、レジストリから取得したネットワークドライブのリストからネットワークドライブをマウントする
        ## マウントには時間がかかることがあるため、threading で並列に実行する (ThreadPoolExecutor はなぜか動かなかった)
        threads: list[threading.Thread] = []
        for network_drive in self.GetNetworkDriveList():

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

        # 万が一ポートが衝突する Akebi HTTPS Server があったら終了させる
        # ポートが衝突する Akebi HTTPS Server があると KonomiTV サーバーの起動に失敗するため
        try:
            from app.config import GetServerPort
            for process in psutil.process_iter(attrs=('name', 'pid', 'cmdline')):
                process_info: dict[str, Any] = cast(Any, process).info
                if ('akebi-https-server.exe' == process_info.get('name', None) and
                    f'--listen-address 0.0.0.0:{GetServerPort()}' in ' '.join(process_info.get('cmdline', []))):
                    process.kill()
        except Exception:
            pass

        # Windows サービスのステータスを起動中に設定
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)

        # 稼働中フラグが降ろされるか、プロセスが終了し再起動が不要になるまでループ
        from app.constants import RESTART_REQUIRED_LOCK_PATH
        self.is_running = True
        self.server_process = None
        try:
            # サービスプロセス側では CTRL+C を一時的に無視し、子プロセスのみがシグナルを受け取れるようにする
            try:
                win32api.SetConsoleCtrlHandler(self._IgnoreCtrlCHandler, True)
                self.ctrl_c_handler_installed = True
            except Exception as ex:
                servicemanager.LogWarningMsg(f'[KonomiTV-Service][SvcDoRun] Failed to ignore CTRL_C_EVENT: {ex!r}')

            while self.is_running is True:

                # 仮想環境上の Python から KonomiTV のサーバープロセス (Uvicorn) を起動
                self.server_process = subprocess.Popen(
                    [self._exe_name_, '-X', 'utf8', str(BASE_DIR / 'KonomiTV.py')],
                    cwd = BASE_DIR,  # カレントディレクトリを指定
                )

                # プロセスが終了するまで待つ
                ## Windows サービスではメインループが終了してしまうとサービスも終了扱いになってしまう
                while True:
                    try:
                        self.server_process.wait()
                        break
                    except KeyboardInterrupt:
                        continue  # 子プロセスの再起動/停止で CTRL_C_EVENT が飛んできたケースに備える
                self.server_process = None

                # プロセス終了後、もしこの時点で再起動が必要であることを示すロックファイルが存在する場合、KonomiTV サーバーを再起動する
                if RESTART_REQUIRED_LOCK_PATH.exists():
                    RESTART_REQUIRED_LOCK_PATH.unlink()
                    continue

                # それ以外の場合は、そのまま Windows サービスを終了する
                break
        finally:
            if self.ctrl_c_handler_installed is True:
                try:
                    win32api.SetConsoleCtrlHandler(self._IgnoreCtrlCHandler, False)
                except Exception:
                    pass
                self.ctrl_c_handler_installed = False  # 無視設定を戻して次のループに備える


    def SvcStop(self):
        """ Windows サービスを停止する """

        # Windows サービスのステータスを停止待機中に設定
        self.is_running = False
        try:
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        except pywintypes.error as ex:
            servicemanager.LogErrorMsg(f'[KonomiTV-Service][SvcStop] SetServiceStatus failed: {ex!r}')
        except Exception as ex:
            servicemanager.LogErrorMsg(f'[KonomiTV-Service][SvcStop] Unexpected error while reporting stop: {ex!r}')

        # KonomiTV サーバーのシャットダウン API にリクエストしてサーバーを終了させる
        ## 通常管理者ユーザーでログインしていないと実行できないが、特別に 127.0.0.77:7010 に直接アクセスすると無認証で実行できる
        shutdown_requested = False
        try:
            from app.config import GetServerPort
            response = httpx.post(
                f'http://127.0.0.77:{GetServerPort() + 10}/api/maintenance/shutdown',
                timeout = 5.0,
            )
            if 200 <= response.status_code <= 299:
                shutdown_requested = True
            else:
                servicemanager.LogWarningMsg(
                    f'[KonomiTV-Service][SvcStop] Shutdown API returned status {response.status_code}',
                )
        except KeyboardInterrupt:
            shutdown_requested = True  # CTRL_C_EVENT が飛んできた場合は子プロセス側でシャットダウン処理が進行している
        except Exception as ex:
            servicemanager.LogWarningMsg(f'[KonomiTV-Service][SvcStop] Shutdown API request failed: {ex!r}')

        # サーバーシャットダウン API へのリクエストが成功した場合は、サービスを終了する
        if shutdown_requested is True:
            return

        # サーバーシャットダウン API へのリクエストが失敗したが、サーバープロセスが既に終了している場合は、サービスを終了する
        if self.server_process is None or self.server_process.poll() is not None:
            return

        # サーバーシャットダウン API へのリクエストが失敗したため、サーバープロセスを終了する
        try:
            psutil.Process(self.server_process.pid).terminate()
        except psutil.NoSuchProcess:
            return
        except Exception as ex:
            servicemanager.LogErrorMsg(f'[KonomiTV-Service][SvcStop] Failed to terminate server process: {ex!r}')


app = typer.Typer(help='KonomiTV Windows Service Launcher.')

@app.command(help='Install KonomiTV service.')
def install(
    username: str = typer.Option(..., help='Username under which KonomiTV service runs.'),
    password: str = typer.Option(..., help='Password of the user under which KonomiTV service runs.'),
):
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

@app.command(help='Uninstall KonomiTV service.')
def uninstall():
    win32serviceutil.HandleCommandLine(cls=KonomiTVServiceFramework, argv=[sys.argv[0], 'remove'])

@app.command(help='Start KonomiTV service.')
def start():
    win32serviceutil.HandleCommandLine(cls=KonomiTVServiceFramework, argv=[sys.argv[0], 'start'])

@app.command(help='Stop KonomiTV service.')
def stop():
    win32serviceutil.HandleCommandLine(cls=KonomiTVServiceFramework, argv=[sys.argv[0], 'stop'])

@app.command(help='Restart KonomiTV service.')
def restart():
    win32serviceutil.HandleCommandLine(cls=KonomiTVServiceFramework, argv=[sys.argv[0], 'restart'])

if __name__ == '__main__':
    if len(sys.argv) == 1:
        # サービスを起動
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(KonomiTVServiceFramework)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        app()
