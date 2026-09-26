
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Literal, cast

import py7zr
import requests
import ruamel.yaml
from rich import print
from rich.padding import Padding

from Utils import (
    CreateBasicInfiniteProgress,
    CreateDownloadInfiniteProgress,
    CreateDownloadProgress,
    CreateTable,
    CustomPrompt,
    GetNetworkInterfaceInformation,
    IsDockerComposeV2,
    IsDockerInstalled,
    IsGitInstalled,
    RemoveEmojiIfLegacyTerminal,
    RunKonomiTVServiceWaiter,
    RunSubprocess,
    RunSubprocessDirectLogOutput,
    SaveConfig,
    ShowPanel,
    ShowSubProcessErrorLog,
)


def Updater(version: str) -> None:
    """
    KonomiTV のアップデーターの実装

    Args:
        version (str): KonomiTV をアップデートするバージョン
    """

    ShowPanel([
        '[yellow]注意: このアップデーターは現時点では動作しない可能性があります。',
        'KonomiTV は鋭意開発中のため、現在破壊的な構成変更が頻繁に行われています。',
        '破壊的変更が続く中アップデーターの機能を維持することは難しいため、',
        '安定版リリースまでの当面の間、アップデーターは最低限のメンテナンスのみ行っています。',
        'もしアップデーターが動作しない場合は、適宜 DB や設定ファイルなどをバックアップの上で',
        '一旦アンインストールし、新規でインストールし直していただきますようお願いいたします。[/yellow]',
    ])

    # 設定データの対話的な取得とエンコーダーの動作確認を行わない以外は、インストーラーの処理内容と大体同じ

    # プラットフォームタイプ
    ## Windows・Linux・Linux (Docker)
    platform_type: Literal['Windows', 'Linux', 'Linux-Docker'] = 'Windows' if os.name == 'nt' else 'Linux'

    # ARM デバイスかどうか
    is_arm_device = platform.machine() == 'aarch64'

    # ***** アップデート対象の KonomiTV のフォルダのパス *****

    table_02 = CreateTable()
    table_02.add_column('02. アップデート対象の KonomiTV のフォルダのパスを入力してください。')
    if platform_type == 'Windows':
        table_02.add_row('例: C:\\DTV\\KonomiTV')
    elif platform_type == 'Linux' or platform_type == 'Linux-Docker':
        table_02.add_row('例: /opt/KonomiTV')
    print(Padding(table_02, (1, 2, 1, 2)))

    # アップデート対象の KonomiTV のフォルダを取得
    update_path: Path
    while True:

        # 入力プロンプト (バリデーションに失敗し続ける限り何度でも表示される)
        update_path = Path(CustomPrompt.ask('アップデート対象の KonomiTV のフォルダのパス'))

        # バリデーション
        if update_path.is_absolute() is False:
            print(Padding('[red]アップデート対象の KonomiTV のフォルダは絶対パスで入力してください。', (0, 2, 0, 2)))
            continue
        if update_path.exists() is False:
            print(Padding('[red]アップデート対象の KonomiTV のフォルダが存在しません。', (0, 2, 0, 2)))
            continue

        # 指定されたフォルダが KonomiTV のフォルダ/ファイル配置と異なる
        ## 大まかにフォルダ/ファイル配置をチェック (すべてのファイル、フォルダがあれば OK)
        if not (
            (update_path / 'config.example.yaml').exists() and
            (update_path / 'License.txt').exists() and
            (update_path / 'Readme.md').exists() and
            (update_path / 'client/').exists() and
            (update_path / 'installer/').exists() and
            (update_path / 'server/').exists() and
            (update_path / 'server/app/').exists() and
            (update_path / 'server/data/').exists() and
            (update_path / 'server/logs/').exists() and
            (update_path / 'server/static/').exists() and
            (update_path / 'server/thirdparty/').exists()
        ):
            print(Padding('[red]指定されたフォルダは KonomiTV のフォルダ/ファイル配置と異なります。', (0, 2, 0, 2)))
            continue

        # すべてのバリデーションを通過したのでループを抜ける
        break

    # Linux: インストールフォルダに docker-compose.yaml があれば
    # Docker でインストールしたことが推測されるので、プラットフォームタイプを Linux-Docker に切り替える
    ## インストーラーで Docker を使わずにインストールした場合は docker-compose.yaml は生成されないことを利用している
    if platform_type == 'Linux' and is_arm_device is False and Path(update_path / 'docker-compose.yaml').exists():

        # 前回 Docker を使ってインストールされているが、今 Docker がインストールされていない
        if IsDockerInstalled() is False:
            ShowPanel([
                '[yellow]この KonomiTV をアップデートするには、Docker のインストールが必要です。[/yellow]',
                'この KonomiTV は Docker を使ってインストールされていますが、現在 Docker が',
                'インストールされていないため、アップデートすることができません。',
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

    # Docker Compose V2 かどうかでコマンド名を変える
    ## Docker Compose V1 は docker-compose 、V2 は docker compose という違いがある
    ## Docker がインストールされていない場合は V1 のコマンドが代入されるが、そもそも非 Docker インストールでは参照されない
    docker_compose_command = ['docker', 'compose'] if IsDockerComposeV2() else ['docker-compose']

    # Python の実行ファイルのパス (Windows と Linux で異なる)
    ## Linux-Docker では利用されない
    python_executable_path = ''
    venv_python_executable_path: str | Path = ''
    if platform_type == 'Windows':
        python_executable_path = update_path / 'server/thirdparty/Python/python.exe'
        # Windows サービス管理スクリプトはパッケージマネージャー経由ではなく、仮想環境の Python 実行ファイルを直接実行する
        ## 以前 Poetry 経由で実行していた際、Windows で shell 解釈の影響を受けて引数中の記号が崩れる問題があったため
        venv_python_executable_path = update_path / 'server/.venv/Scripts/python.exe'
    elif platform_type == 'Linux':
        python_executable_path = update_path / 'server/thirdparty/Python/bin/python'

    # ***** Windows: 起動中の Windows サービスの終了 *****

    if platform_type == 'Windows':

        # Windows サービスを終了
        print(Padding('起動中の Windows サービスを終了しています…', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:
            service_stop_result = subprocess.run(
                args = [venv_python_executable_path, 'KonomiTV-Service.py', 'stop'],
                cwd = update_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
                text = True,  # 出力をテキストとして取得する
            )
        # 1062: ERROR_SERVICE_NOT_ACTIVE はサービスが起動していない場合に発生するエラーのため無視する
        if 'Error stopping service' in service_stop_result.stdout and '(1062)' not in service_stop_result.stdout:
            ShowSubProcessErrorLog(
                error_message = '起動中の Windows サービスの終了中に予期しないエラーが発生しました。',
                error_log = service_stop_result.stdout.strip(),
            )
            return  # 処理中断

    # ***** Linux: 起動中の PM2 サービスの終了 *****

    elif platform_type == 'Linux':

        # PM2 サービスを終了
        result = RunSubprocess(
            '起動中の PM2 サービスを終了しています…',
            ['/usr/bin/env', 'pm2', 'stop', 'KonomiTV'],
            cwd = update_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
            error_message = '起動中の PM2 サービスの終了中に予期しないエラーが発生しました。',
            error_log_name = 'PM2 のエラーログ',
        )
        if result is False:
            return  # 処理中断

    # ***** Linux-Docker: 起動中の Docker コンテナの終了 *****

    elif platform_type == 'Linux-Docker':

        # docker compose stop で Docker コンテナを終了
        result = RunSubprocess(
            '起動中の Docker コンテナを終了しています…',
            [*docker_compose_command, 'stop'],
            cwd = update_path,  # カレントディレクトリを KonomiTV のアンインストールフォルダに設定
            error_message = '起動中の Docker コンテナの終了中に予期しないエラーが発生しました。',
            error_log_name = 'PM2 のエラーログ',
        )
        if result is False:
            return  # 処理中断

    # ***** ソースコードの更新 *****

    # Git を使ってインストールされているか
    ## Git のインストール状況に関わらず、.git フォルダが存在する場合は Git を使ってインストールされていると判断する
    is_installed_by_git = Path(update_path / '.git').exists()

    # Git を使ってインストールされている場合: git fetch & git checkout でソースコードを更新
    if is_installed_by_git is True:

        # 前回 Git を使ってインストールされているが、今 Git がインストールされていない
        if IsGitInstalled() is False:
            ShowPanel([
                '[yellow]この KonomiTV をアップデートするには、Git のインストールが必要です。[/yellow]',
                'KonomiTV は初回インストール時に Git がインストールされている場合は、',
                '自動的に Git を使ってインストールされます。',
                'この KonomiTV は Git を使ってインストールされていますが、現在 Git が',
                'インストールされていないため、アップデートすることができません。',
            ])
            return  # 処理中断

        # リモートの変更内容とタグを取得
        result = RunSubprocess(
            'KonomiTV のソースコードを Git でダウンロードしています…',
            ['git', 'fetch', 'origin', '--tags'],
            cwd = update_path,  # カレントディレクトリを KonomiTV のインストールフォルダに設定
            error_message = 'KonomiTV のソースコードのダウンロード中に予期しないエラーが発生しました。',
            error_log_name = 'Git のエラーログ',
        )
        if result is False:
            return  # 処理中断

        # 新しいバージョンのコードをチェックアウト
        ## latest の場合は master ブランチを、それ以外は指定されたバージョンのタグをチェックアウト
        ## git fetch はローカルの master ブランチを更新しないため、latest の場合は -B でローカルの master ブランチを
        ## リモートの最新 (origin/master) に合わせて作り直してからチェックアウトする
        ## 単に master をチェックアウトすると、初回インストール時点などの古いローカルの master ブランチのままになってしまう
        checkout_args: list[str | Path]
        if version == 'latest':
            checkout_args = ['git', 'checkout', '--force', '-B', 'master', 'origin/master']
        else:
            checkout_args = ['git', 'checkout', '--force', f'v{version}']
        result = RunSubprocess(
            'KonomiTV のソースコードを更新しています…',
            checkout_args,
            cwd = update_path,  # カレントディレクトリを KonomiTV のインストールフォルダに設定
            error_message = 'KonomiTV のソースコードの更新中に予期しないエラーが発生しました。',
            error_log_name = 'Git のエラーログ',
        )
        if result is False:
            return  # 処理中断

    # Git を使ってインストールされていない場合: zip からソースコードを更新
    else:

        # 以前のバージョンにはあったものの、現在のバージョンにはないファイルを削除する
        ## 事前に config.yaml・venv の仮想環境・ユーザーデータ・ログ以外のファイル/フォルダをすべて削除してから、
        ## ダウンロードした新しいソースコードで上書き更新する
        ## Git でインストールされている場合は、作業ツリーの更新を Git がよしなにやってくれるため不要
        shutil.rmtree(update_path / '.github/', ignore_errors=True)
        shutil.rmtree(update_path / '.vscode/', ignore_errors=True)
        shutil.rmtree(update_path / 'client/', ignore_errors=True)
        shutil.rmtree(update_path / 'installer/', ignore_errors=True)
        shutil.rmtree(update_path / 'server/app/', ignore_errors=True)
        shutil.rmtree(update_path / 'server/misc/', ignore_errors=True)
        shutil.rmtree(update_path / 'server/static/', ignore_errors=True)
        Path(update_path / 'server/KonomiTV.py').unlink(missing_ok=True)
        Path(update_path / 'server/KonomiTV-Service.py').unlink(missing_ok=True)
        Path(update_path / 'server/Pipfile').unlink(missing_ok=True)
        Path(update_path / 'server/Pipfile.lock').unlink(missing_ok=True)
        Path(update_path / 'server/poetry.lock').unlink(missing_ok=True)
        Path(update_path / 'server/poetry.toml').unlink(missing_ok=True)
        Path(update_path / 'server/pyproject.toml').unlink(missing_ok=True)
        Path(update_path / 'server/uv.lock').unlink(missing_ok=True)
        Path(update_path / '.dockerignore').unlink(missing_ok=True)
        Path(update_path / '.editorconfig').unlink(missing_ok=True)
        Path(update_path / '.gitignore').unlink(missing_ok=True)
        Path(update_path / 'config.example.yaml').unlink(missing_ok=True)
        Path(update_path / 'docker-compose.example.yaml').unlink(missing_ok=True)
        Path(update_path / 'Dockerfile').unlink(missing_ok=True)
        Path(update_path / 'License.txt').unlink(missing_ok=True)
        Path(update_path / 'Readme.md').unlink(missing_ok=True)
        Path(update_path / 'vetur.config.js').unlink(missing_ok=True)

        # ソースコードを随時ダウンロードし、進捗を表示
        # ref: https://github.com/Textualize/rich/blob/master/examples/downloader.py
        print(Padding('KonomiTV のソースコードを更新しています…', (1, 2, 0, 2)))
        progress = CreateDownloadInfiniteProgress()

        # GitHub からソースコードをダウンロード
        ## latest の場合は master ブランチを、それ以外は指定されたバージョンのタグをダウンロード
        if version == 'latest':
            source_code_response = requests.get('https://codeload.github.com/tsukumijima/KonomiTV/zip/refs/heads/master')
        else:
            source_code_response = requests.get(f'https://codeload.github.com/tsukumijima/KonomiTV/zip/refs/tags/v{version}')
        task_id = progress.add_task('', total=None)

        # ダウンロードしたデータを随時一時ファイルに書き込む
        source_code_file = tempfile.NamedTemporaryFile(mode='wb', delete=False)
        with progress:
            for chunk in source_code_response.iter_content(chunk_size=1024):
                source_code_file.write(chunk)
                progress.update(task_id, advance=len(chunk))
            source_code_file.seek(0, os.SEEK_END)
            progress.update(task_id, total=source_code_file.tell())
        source_code_file.close()  # 解凍する前に close() してすべて書き込ませておくのが重要

        # ソースコードを解凍して展開
        shutil.unpack_archive(source_code_file.name, update_path.parent, format='zip')
        if version == 'latest':
            shutil.copytree(update_path.parent / 'KonomiTV-master/', update_path, dirs_exist_ok=True)
            shutil.rmtree(update_path.parent / 'KonomiTV-master/', ignore_errors=True)
        else:
            shutil.copytree(update_path.parent / f'KonomiTV-{version}/', update_path, dirs_exist_ok=True)
            shutil.rmtree(update_path.parent / f'KonomiTV-{version}/', ignore_errors=True)
        Path(source_code_file.name).unlink()

    # ***** サーバー設定ファイル (config.yaml) の更新 *****

    # サーバーのリッスンポート
    server_port: int = 7000

    print(Padding('サーバー設定ファイル (config.yaml) を更新しています…', (1, 2, 0, 2)))
    progress = CreateBasicInfiniteProgress()
    progress.add_task('', total=None)
    with progress:

        # 旧バージョンの config.yaml の設定値を取得
        ## config.yaml の上書き更新前に行うのが重要
        config_dict: dict[str, dict[str, Any]]
        with open(update_path / 'config.yaml', encoding='utf-8') as file:
            config_dict = dict(ruamel.yaml.YAML().load(file))
            # 0.9.0 -> 0.10.0: config_dict['capture']['upload_folder'] (str) を config_dict['capture']['upload_folders'] (list[str]) に移行
            if 'upload_folder' in config_dict['capture']:
                config_dict['capture']['upload_folders'] = [config_dict['capture']['upload_folder']]
                del config_dict['capture']['upload_folder']

        # サーバーのリッスンポートの設定値を取得
        server_port = cast(int, config_dict['server']['port'])

        # 新しい config.example.yaml を config.yaml に上書きコピーし、新しいフォーマットに更新
        shutil.copyfile(update_path / 'config.example.yaml', update_path / 'config.yaml')

        # 旧バージョンの config.yaml の設定値を復元
        SaveConfig(update_path / 'config.yaml', config_dict)

    # Windows・Linux: KonomiTV のアップデート処理
    ## Linux-Docker では Docker イメージの再構築時に各種アップデート処理も行われるため、実行の必要がない
    if platform_type == 'Windows' or platform_type == 'Linux':

        # ***** サードパーティーライブラリの更新 *****

        # サードパーティーライブラリを随時ダウンロードし、進捗を表示
        # ref: https://github.com/Textualize/rich/blob/master/examples/downloader.py
        print(Padding('サードパーティーライブラリをダウンロードしています…', (1, 2, 0, 2)))
        progress = CreateDownloadProgress()

        # GitHub からサードパーティーライブラリをダウンロード
        if version == 'latest':
            thirdparty_base_url = 'https://nightly.link/tsukumijima/KonomiTV/workflows/build_thirdparty.yaml/master/'
        else:
            thirdparty_base_url = f'https://github.com/tsukumijima/KonomiTV/releases/download/v{version}/'
        thirdparty_compressed_file_name = 'thirdparty-windows.7z'
        if platform_type == 'Linux' and is_arm_device is False:
            thirdparty_compressed_file_name = 'thirdparty-linux.tar.xz'
        elif platform_type == 'Linux' and is_arm_device is True:
            thirdparty_compressed_file_name = 'thirdparty-linux-arm.tar.xz'
        thirdparty_url = thirdparty_base_url + thirdparty_compressed_file_name
        if version == 'latest':
            thirdparty_url = thirdparty_url + '.zip'
        thirdparty_response = requests.get(thirdparty_url, stream=True)
        task_id = progress.add_task('', total=float(thirdparty_response.headers['Content-length']))

        # ダウンロードしたデータを随時一時ファイルに書き込む
        thirdparty_compressed_file = tempfile.NamedTemporaryFile(mode='wb', delete=False)
        with progress:
            for chunk in thirdparty_response.iter_content(chunk_size=1048576):  # サイズが大きいので1MBごとに読み込み
                thirdparty_compressed_file.write(chunk)
                progress.update(task_id, advance=len(chunk))
        thirdparty_compressed_file.close()  # 解凍する前に close() してすべて書き込ませておくのが重要

        # サードパーティーライブラリを解凍して展開
        print(Padding('サードパーティーライブラリを更新しています… (数秒～数十秒かかります)', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:

            # 更新前に、前バージョンの古いサードパーティーライブラリを削除
            shutil.rmtree(update_path / 'server/thirdparty/', ignore_errors=True)

            # latest のみ、圧縮ファイルがさらに zip で包まれているので、それを解凍
            thirdparty_compressed_file_path = thirdparty_compressed_file.name
            if version == 'latest':
                with zipfile.ZipFile(thirdparty_compressed_file.name, mode='r') as zip_file:
                    zip_file.extractall(update_path / 'server/')
                thirdparty_compressed_file_path = update_path / 'server' / thirdparty_compressed_file_name
                Path(thirdparty_compressed_file.name).unlink()

            if platform_type == 'Windows':
                # Windows: 7-Zip 形式のアーカイブを解凍
                with py7zr.SevenZipFile(thirdparty_compressed_file_path, mode='r') as seven_zip:
                    seven_zip.extractall(update_path / 'server/')
            elif platform_type == 'Linux':
                # Linux: tar.xz 形式のアーカイブを解凍
                ## 7-Zip だと (おそらく) ファイルパーミッションを保持したまま圧縮することができない？ため、あえて tar.xz を使っている
                ## アーカイブ内のパスが展開先の外を指すエントリ (../ や絶対パス) を拒否するため、tar フィルタを指定する
                with tarfile.open(thirdparty_compressed_file_path, mode='r:xz') as tar_xz:
                    tar_xz.extractall(update_path / 'server/', filter='tar')
            Path(thirdparty_compressed_file_path).unlink()
            # server/thirdparty/.gitkeep が消えてたらもう一度作成しておく
            if Path(update_path / 'server/thirdparty/.gitkeep').exists() is False:
                Path(update_path / 'server/thirdparty/.gitkeep').touch()

        # ***** 依存パッケージの更新 *****

        # すでに仮想環境があると稀に更新がうまく行かないことがあるため、アップデート毎に作り直す
        shutil.rmtree(update_path / 'server/.venv/', ignore_errors=True)

        # uv sync を実行
        ## サードパーティーライブラリ内の Python を明示的に指定して、server/.venv/ に仮想環境を作成し、依存パッケージをインストールする
        ## --frozen: uv.lock を更新せず、記録されているバージョンのままインストールする
        ## --no-dev: 開発時にのみ利用する依存パッケージ (Ruff・Pyright など) をインストールしない
        ## --link-mode copy: uv のキャッシュとインストール先が別のドライブにあるとハードリンクに失敗して警告が出るため、最初からコピーする
        ## --python: Python の実行ファイルのパスを指定しているため、uv が別の Python を自動でダウンロードすることはない
        result = RunSubprocessDirectLogOutput(
            '依存パッケージを更新しています…',
            [python_executable_path, '-m', 'uv', 'sync', '--frozen', '--no-dev', '--link-mode', 'copy', '--python', python_executable_path],
            cwd = update_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
            error_message = '依存パッケージの更新中に予期しないエラーが発生しました。',
        )
        if result is False:
            return  # 処理中断

    # Linux-Docker: Docker イメージを再ビルド
    elif platform_type == 'Linux-Docker':

        # docker compose build --no-cache --pull で Docker イメージをビルド
        ## 万が一以前ビルドしたキャッシュが残っていたときに備え、キャッシュを使わずにビルドさせる
        result = RunSubprocessDirectLogOutput(
            'Docker イメージを再ビルドしています… (数分～数十分かかります)',
            [*docker_compose_command, 'build', '--no-cache', '--pull'],
            cwd = update_path,  # カレントディレクトリを KonomiTV のインストールフォルダに設定
            error_message = 'Docker イメージの再ビルド中に予期しないエラーが発生しました。',
        )
        if result is False:
            return  # 処理中断

    # ***** Windows: Windows サービスの起動 *****

    if platform_type == 'Windows':

        # Windows サービスを起動
        print(Padding('Windows サービスを起動しています…', (1, 2, 0, 2)))
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:
            service_start_result = subprocess.run(
                args = [venv_python_executable_path, 'KonomiTV-Service.py', 'start'],
                cwd = update_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
                text = True,  # 出力をテキストとして取得する
            )
        if 'Error starting service' in service_start_result.stdout:
            ShowSubProcessErrorLog(
                error_message = 'Windows サービスの起動中に予期しないエラーが発生しました。',
                error_log = service_start_result.stdout.strip(),
            )
            return  # 処理中断

    # ***** Linux: PM2 サービスの起動 *****

    elif platform_type == 'Linux':

        # PM2 サービスを起動
        result = RunSubprocess(
            'PM2 サービスを起動しています…',
            ['/usr/bin/env', 'pm2', 'start', 'KonomiTV'],
            cwd = update_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
            error_message = 'PM2 サービスの起動中に予期しないエラーが発生しました。',
            error_log_name = 'PM2 のエラーログ',
        )
        if result is False:
            return  # 処理中断

    # ***** Linux-Docker: Docker コンテナの起動 *****

    elif platform_type == 'Linux-Docker':

        # Docker コンテナを起動
        result = RunSubprocess(
            'Docker コンテナを起動しています…',
            [*docker_compose_command, 'up', '-d', '--force-recreate'],
            cwd = update_path,  # カレントディレクトリを KonomiTV のインストールフォルダに設定
            error_message = 'Docker コンテナの起動中に予期しないエラーが発生しました。',
            error_log_name = 'Docker Compose のエラーログ',
        )
        if result is False:
            return  # 処理中断

    # ***** サービスの起動を待機 *****

    # KonomiTV サービスの起動を監視して起動完了を待機する処理はインストーラーと共通
    RunKonomiTVServiceWaiter(platform_type, update_path)

    # ***** アップデート完了 *****

    # ループバックアドレスまたはリンクローカルアドレスでない IPv4 アドレスとインターフェイス名を取得
    nic_infos = GetNetworkInterfaceInformation()

    # アップデート完了メッセージを表示
    table_done = CreateTable()
    table_done.add_column(RemoveEmojiIfLegacyTerminal(
        'アップデートが完了しました！🎉🎊 すぐに使いはじめられます！🎈\n'
        '下記の URL から、KonomiTV の Web UI にアクセスしてみましょう！\n'
        'もし KonomiTV にアクセスできない場合は、ファイアウォールの設定を確認してみてください。',
    ))

    # アクセス可能な URL のリストを IP アドレスごとに表示
    ## ローカルホスト (127.0.0.1) だけは https://my.local.konomi.tv:7000/ というエイリアスが使える
    urls = [f'https://{nic_info[0].replace(".", "-")}.local.konomi.tv:{server_port}/' for nic_info in nic_infos]
    urls_max_length = max([len(url) for url in urls])  # URL の最大文字長を取得
    table_done.add_row(f'[bright_blue]{f"https://my.local.konomi.tv:{server_port}/": <{urls_max_length}}[/bright_blue] (ローカルホスト)')
    for index, url in enumerate(urls):
        table_done.add_row(f'[bright_blue]{url: <{urls_max_length}}[/bright_blue] ({nic_infos[index][1]})')

    print(Padding(table_done, (1, 2, 0, 2)))
