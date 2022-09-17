
import os
from pathlib import Path
from rich import box
from rich import print
from rich.padding import Padding
from rich.style import Style
from rich.table import Table
from typing import Literal, cast

from Utils import CustomPrompt


def Install(version: str) -> None:
    """
    KonomiTV をインストールする (インストーラーの実装)

    Args:
        version (str): KonomiTV をインストールするバージョン
    """

    # ***** KonomiTV をインストールするフォルダのパス *****

    table_02 = Table(expand=True, box=box.SQUARE, border_style=Style(color='#E33157'))
    table_02.add_column('02. KonomiTV をインストールするフォルダのパスを入力してください。')
    if os.name == 'nt':
        table_02.add_row('なお、C:\\Users・C:\\Program Files 以下と、日本語(全角)が含まれるパス、')
        table_02.add_row('半角スペースを含むパスは不具合の原因となるため、避けてください。')
        table_02.add_row('例: C:\\DTV\\KonomiTV')
    else:
        table_02.add_row('なお、日本語(全角)が含まれるパス、半角スペースを含むパスは不具合の原因となるため、避けてください。')
        table_02.add_row('例: /opt/KonomiTV')
    print(Padding(table_02, (1, 2, 1, 2)))

    # インストール先のフォルダを取得
    install_path = Path(CustomPrompt.ask('KonomiTV をインストールするフォルダのパス'))
    while install_path.is_absolute() is False or install_path.exists():
        if install_path.is_absolute() is False:
            print(Padding('[red]インストール先のフォルダは絶対パスで入力してください。', (0, 2, 0, 2)))
            install_path = Path(CustomPrompt.ask('KonomiTV をインストールするフォルダのパス'))
        elif install_path.exists():
            print(Padding('[red]インストール先のフォルダがすでに存在します。', (0, 2, 0, 2)))
            install_path = Path(CustomPrompt.ask('KonomiTV をインストールするフォルダのパス'))

    # インストール先のフォルダを作成
    is_mkdir_success = False
    while is_mkdir_success is False:
        try:
            install_path.mkdir(parents=True, exist_ok=False)
            is_mkdir_success = True
        except Exception as e:
            print(e)
            print(Padding('[red]インストール先のフォルダを作成できませんでした。', (0, 2, 0, 2)))
            install_path = Path(CustomPrompt.ask('KonomiTV をインストールするフォルダのパス'))

    # ***** 利用するバックエンド *****

    table_03 = Table(expand=True, box=box.SQUARE, border_style=Style(color='#E33157'))
    table_03.add_column('03. 利用するバックエンドを EDCB・Mirakurun から選択してください。')
    table_03.add_row('バックエンドは、テレビチューナーへのアクセスや番組情報の取得などに利用します。')
    table_03.add_row('EDCB は、220122 以降のバージョンの xtne6f 版または tkntrec 版の EDCB にのみ対応しています。')
    table_03.add_row('KonomiTV と連携するには、別途 EDCB に事前の設定が必要です。')
    table_03.add_row('Mirakurun は、3.9.0 以降のバージョンを推奨します。3.8.0 以前でも動作しますが、非推奨です。')
    print(Padding(table_03, (1, 2, 1, 2)))

    # 利用するバックエンドを取得
    backend = cast(Literal['EDCB'] | Literal['Mirakurun'], CustomPrompt.ask('利用するバックエンド', default='EDCB', choices=['EDCB', 'Mirakurun']))

    # ***** EDCB (EpgTimerNW) の TCP API の URL *****

    if backend == 'EDCB':

        table_04 = Table(expand=True, box=box.SQUARE, border_style=Style(color='#E33157'))
        table_04.add_column('04. EDCB (EpgTimerNW) の TCP API の URL を入力してください。')
        table_04.add_row('tcp://192.168.1.11:4510/ のような形式の URL で指定します。')
        table_04.add_row('tcp://edcb-namedpipe/ と指定すると、TCP API の代わりに')
        table_04.add_row('名前付きパイプを使って通信します(同じ PC で EDCB が稼働している場合のみ)。')
        print(Padding(table_04, (1, 2, 1, 2)))

        # EDCB (EpgTimerNW) の TCP API の URL を取得
        edcb_url = Path(CustomPrompt.ask('EDCB (EpgTimerNW) の TCP API の URL'))

    # ***** Mirakurun の HTTP API の URL *****

    if backend == 'Mirakurun':

        table_04 = Table(expand=True, box=box.SQUARE, border_style=Style(color='#E33157'))
        table_04.add_column('04. Mirakurun の HTTP API の URL を入力してください。')
        table_04.add_row('http://192.168.1.28:40772/ のような形式の URL で指定します。')
        print(Padding(table_04, (1, 2, 1, 2)))

        # Mirakurun の HTTP API の URL を取得
        mirakurun_url = Path(CustomPrompt.ask('Mirakurun の HTTP API の URL'))










