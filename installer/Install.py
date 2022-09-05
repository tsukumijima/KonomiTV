
from rich import print
from rich.padding import Padding
from rich.text import Text


def Install(version: str) -> None:
    """
    KonomiTV をインストールする (インストーラーの実装)

    Args:
        version (str): KonomiTV をインストールするバージョン
    """

    print(Padding(Text(
        'インストーラーはまだ実装されていません。'
    ), (1, 2, 0, 2)))
