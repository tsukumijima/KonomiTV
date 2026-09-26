# 旧バージョンの KonomiTV インストーラー向けの Poetry 互換モジュール
# サードパーティーライブラリ内の Python の site-packages に poetry パッケージとして配置される
## KonomiTV は依存パッケージの管理を Poetry から uv に移行したが、旧バージョンのインストーラーで「開発版をインストール」
## 「開発版へアップデート」を選ぶと、最新のサードパーティーライブラリ内の Python で `python -m poetry ...` が実行される
## このモジュールは、旧バージョンのインストーラーが実行する次の Poetry コマンドだけを uv の操作に読み替えて互換性を保つ
## - poetry env use <Python のパス>: uv sync が仮想環境を作成するため、何もせずに成功を返す
## - poetry install --only main --no-root: uv sync --frozen --no-dev に読み替える
## - poetry run python KonomiTV-Service.py ...: 仮想環境の Python で KonomiTV-Service.py を直接実行する (v0.13.0 以前の Windows 版)
## 旧バージョンのインストーラーが十分使われなくなったら、このモジュールは削除する

import subprocess
import sys
from pathlib import Path


def RunUvSync() -> int:
    """
    カレントディレクトリ (server/) で uv sync を実行し、仮想環境の作成と依存パッケージのインストールを行う

    Returns:
        int: uv sync の終了コード
    """

    # 新しいインストーラーが実行する uv sync と同じオプションで実行する
    ## この Python 自身 (サードパーティーライブラリ内の Python) を仮想環境の Python として明示的に指定する
    return subprocess.run(
        [sys.executable, '-m', 'uv', 'sync', '--frozen', '--no-dev', '--link-mode', 'copy', '--python', sys.executable],
    ).returncode


def RunInVirtualEnvironment(args: list[str]) -> int:
    """
    カレントディレクトリ (server/) の仮想環境内のコマンドを実行する (poetry run 相当)

    Args:
        args (list[str]): 実行するコマンドと引数

    Returns:
        int: 実行したコマンドの終了コード
    """

    # 仮想環境内の実行ファイルのあるフォルダ (Windows と Linux で異なる)
    venv_bin_dir = Path.cwd() / '.venv' / ('Scripts' if sys.platform == 'win32' else 'bin')

    # コマンド名を仮想環境内の実行ファイルのパスに置き換える
    ## 見つからない場合は、コマンド名のまま実行する (PATH から探される)
    command = args[0]
    executable_name = f'{command}.exe' if sys.platform == 'win32' else command
    if (venv_bin_dir / executable_name).exists():
        command = str(venv_bin_dir / executable_name)

    # シェルを介さずに実行し、引数中の記号がシェルに解釈されないようにする
    return subprocess.run([command, *args[1:]]).returncode


def main() -> int:
    """
    poetry コマンドの引数を解釈し、対応する uv の操作を実行する

    Returns:
        int: 終了コード
    """

    args = sys.argv[1:]

    # poetry env use <Python のパス>
    if args[:2] == ['env', 'use']:
        print('Poetry compatibility shim: skipping "poetry env use" (the virtual environment is created by uv sync).')
        return 0

    # poetry install (--only main --no-root)
    if args[:1] == ['install']:
        # 標準出力がパイプの場合はバッファリングされ、後から実行する uv の出力より後に表示されてしまうため、すぐに書き出す
        print('Poetry compatibility shim: running "uv sync --frozen --no-dev" instead of "poetry install".', flush=True)
        return RunUvSync()

    # poetry run <コマンド> [引数...]
    if args[:1] == ['run'] and len(args) >= 2:
        return RunInVirtualEnvironment(args[1:])

    # poetry --version
    if args[:1] == ['--version']:
        print('Poetry compatibility shim for KonomiTV (uv is used instead of Poetry)')
        return 0

    # それ以外のコマンドには対応しない
    print(f'Poetry compatibility shim: unsupported command: poetry {" ".join(args)}')
    print('KonomiTV now uses uv instead of Poetry. Please download and use the latest KonomiTV installer.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
