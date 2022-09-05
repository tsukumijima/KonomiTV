
import os
from rich.console import Console
from rich.padding import Padding
from rich.prompt import Prompt
from rich.text import TextType
from typing import Dict, List, Optional


class CustomPrompt(Prompt):
    """ カスタムの Rich プロンプトの実装 """

    def __init__(
        self,
        prompt: TextType = "",
        *,
        console: Optional[Console] = None,
        password: bool = False,
        choices: Optional[List[str]] = None,
        show_default: bool = True,
        show_choices: bool = True,
    ) -> None:

        if type(prompt) is str:
            prompt = f'  {prompt}'  # 左に半角スペース2つ分余白を空ける

        # 親クラスのコンストラクタを実行
        super().__init__(prompt, console=console, password=password, choices=choices, show_default=show_default, show_choices=show_choices)

        if self.choices is not None:
            self.illegal_choice_message = Padding(f'[prompt.invalid.choice][{"/".join(self.choices)}] のいずれかを選択してください！', (0, 2, 0, 2))


def GetNetworkDriveList() -> List[Dict[str, str]]:
    """
    レジストリからログオン中のユーザーがマウントしているネットワークドライブのリストを取得する
    KonomiTV-Service.py で利用されているものと基本同じ

    Returns:
        List[Dict[str, str]]: ネットワークドライブのドライブレターとパスのリスト
    """

    # Windows 以外では実行しない
    if os.name != 'nt': return []

    # winreg (レジストリを操作するための標準ライブラリ (Windows 限定) をインポート)
    import winreg

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
