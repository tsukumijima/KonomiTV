
import os
from pathlib import Path
from typing import Any

import ruamel.yaml
from rich import print
from rich.padding import Padding

from Utils import (
    AskWindowsServiceAccount,
    CreateTable,
    GetLogFileSizes,
    InstallerAnswers,
    InstallWindowsService,
    IsNetworkPath,
    RunKonomiTVServiceWaiter,
    ShowPanel,
)


def ServiceAccountChanger(answers: InstallerAnswers) -> bool:
    """
    インストール済みの KonomiTV の Windows サービスの実行アカウントを変更する
    LocalSystem でインストールしたあとにネットワークドライブを使いたくなった場合や、
    Windows のパスワードを変更してサービスを起動できなくなった場合に利用する

    Args:
        answers (InstallerAnswers): 質問への回答

    Returns:
        bool: 実行アカウントの変更に成功したかどうか
    """

    # Windows サービスの実行アカウントは Windows にだけ存在する
    if os.name != 'nt':
        ShowPanel([
            '[red]サービスの実行アカウントの変更は、Windows でのみ利用できます。[/red]',
        ])
        return False  # 処理中断

    # ***** 実行アカウントを変更する KonomiTV のフォルダのパス *****

    table_02 = CreateTable()
    table_02.add_column('02. 実行アカウントを変更する KonomiTV のフォルダのパスを入力してください。')
    table_02.add_row('例: C:\\DTV\\KonomiTV')
    print(Padding(table_02, (1, 2, 1, 2)))

    # 実行アカウントを変更する KonomiTV のフォルダを取得
    install_path: Path
    while True:

        # 入力プロンプト (バリデーションに失敗し続ける限り何度でも表示される)
        install_path = Path(answers.ask('install_path', '実行アカウントを変更する KonomiTV のフォルダのパス'))

        # バリデーション
        if install_path.is_absolute() is False:
            answers.showInvalidInput('実行アカウントを変更する KonomiTV のフォルダは絶対パスで入力してください。')
            continue
        if install_path.exists() is False:
            answers.showInvalidInput('実行アカウントを変更する KonomiTV のフォルダが存在しません。')
            continue

        # 指定されたフォルダにインストール済みの KonomiTV がない
        ## サービスの登録には、仮想環境の Python 実行ファイルと Windows サービス管理スクリプト、サーバー設定ファイルが必要
        if not (
            (install_path / 'config.yaml').exists() and
            (install_path / 'server/.venv/Scripts/python.exe').exists() and
            (install_path / 'server/KonomiTV-Service.py').exists()
        ):
            answers.showInvalidInput('指定されたフォルダにインストール済みの KonomiTV が見つかりません。')
            continue

        # すべてのバリデーションを通過したのでループを抜ける
        break

    # インストール済みのサービス管理スクリプトが、実行アカウントの選択に対応しているかを確認する
    ## 対応していない古いバージョンでは LocalSystem で登録できないため、先にアップデートしてもらう
    service_script = (install_path / 'server/KonomiTV-Service.py').read_text(encoding='utf-8')
    if '\'--local-system\'' not in service_script:
        ShowPanel([
            '[red]この KonomiTV は、サービスの実行アカウントの変更に対応していないバージョンです。[/red]',
            'インストーラーで KonomiTV をアップデートしてから、もう一度実行してください。',
        ])
        return False  # 処理中断

    # 録画フォルダとキャプチャ画像の保存先のうち、ネットワーク上にあるフォルダを取得する
    ## ネットワーク上のフォルダがある場合は、ユーザーの権限で実行するのを既定の実行アカウントにする
    ## 利用者が編集した config.yaml では項目が欠けていることがあるため、欠けている項目は空のリストとして扱う
    config_dict: dict[str, Any]
    with open(install_path / 'config.yaml', encoding='utf-8') as file:
        config_dict = dict(ruamel.yaml.YAML().load(file))
    folders: list[Any] = [
        *(config_dict.get('video') or {}).get('recorded_folders', []),
        *(config_dict.get('capture') or {}).get('upload_folders', []),
    ]
    network_folders: list[str] = []
    for folder in folders:
        if IsNetworkPath(str(folder)) is True:
            network_folders.append(str(folder))

    # ***** Windows サービスの実行アカウントの変更・起動 *****

    # 実行アカウントを質問し、ユーザーの権限で実行する場合はパスワードを検証する
    service_account = AskWindowsServiceAccount(answers, 3, network_folders, is_account_selection_supported=True)

    # サービスの起動を待つ処理で今回の起動のログだけを読むため、サービスを起動する前のログファイルのサイズを取得しておく
    initial_log_sizes = GetLogFileSizes(install_path)

    # 選ばれた実行アカウントで Windows サービスを登録し直し、起動する
    ## インストーラーと共通の処理
    ## 実行アカウントの変更は次にサービスを起動したときに反映されるため、アカウントの選択とパスワードの検証が済んでから、
    ## 起動中のサービスを終了して登録し直す (パスワードの入力を間違えても KonomiTV は起動したままになる)
    result = InstallWindowsService(
        install_path,
        answers,
        service_account,
        question_number = 3,
        network_folders = network_folders,
        is_account_selection_supported = True,
        stop_running_service = True,
    )
    if result is False:
        return False  # 処理中断

    # ***** サービスの起動を待機 *****

    # KonomiTV サービスの起動を監視して起動完了を待機する処理はインストーラーと共通
    if RunKonomiTVServiceWaiter('Windows', install_path, initial_log_sizes) is False:
        return False  # 処理中断

    ShowPanel([
        'KonomiTV の Windows サービスの実行アカウントを変更しました。',
    ])

    return True
