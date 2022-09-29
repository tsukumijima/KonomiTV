
from rich import print
from rich.padding import Padding
from rich.text import Text


def Updater(version: str) -> None:
    """
    KonomiTV のアップデーターの実装

    Args:
        version (str): KonomiTV をアップデートするバージョン
    """

    print(Padding(Text(
        'アップデーターはまだ実装されていません。'
    ), (1, 2, 0, 2)))
