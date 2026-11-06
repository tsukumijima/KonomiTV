from datetime import datetime, tzinfo
from typing import Any, Literal

import app.models.Program
from app.config import Config, LoadConfig


# 番組情報の更新処理が参照する現在時刻を、テストで固定するための補助関数群
## 別プロセスでの番組情報の更新では、子プロセスがこのモジュールを読み込んで同じ時刻を適用する
## 読み込むだけで一時フォルダの作成などが走る tests/conftest.py とは別のモジュールにし、依存先を app 以下のモジュールだけにしている


def CreateFrozenDatetime(now: datetime) -> type:
    """
    app/models/Program.py の datetime を置き換える、now() だけが固定した時刻を返すクラスを作成する

    Args:
        now (datetime): 現在時刻として扱う時刻

    Returns:
        type: datetime の代わりに使用するクラス
    """

    # 番組情報の更新処理は datetime で生成した日時をそのまま DB に保存するが、sqlite3 は datetime のサブクラスを保存できない
    ## このため datetime は継承せず、日時の生成 (コンストラクタと fromtimestamp()) は通常の datetime に委譲する
    class FrozenDatetime:
        def __new__(cls, *args: Any, **kwargs: Any) -> datetime:
            return datetime(*args, **kwargs)

        fromtimestamp = datetime.fromtimestamp

        @staticmethod
        def now(tz: tzinfo | None = None) -> datetime:
            return now.astimezone(tz)

    return FrozenDatetime


def InitializeProgramUpdateProcess(now: datetime, backend: Literal['Mirakurun', 'EDCB']) -> None:
    """
    別プロセスで番組情報を更新する子プロセスの起動時に、メインプロセスと同じ現在時刻とバックエンドを適用する
    forkserver で起動した子プロセスは config.test.yaml の設定と実際の時刻で動作するため、ProcessPoolExecutor の initializer として渡す

    Args:
        now (datetime): 現在時刻として扱う時刻
        backend (Literal['Mirakurun', 'EDCB']): 番組情報を取得するバックエンド
    """

    # 子プロセスはサーバー設定を読み込んでいないため、メインプロセスと同じテスト用のサーバー設定を読み込んでからバックエンドを設定する
    ## メインプロセスと同じく、ポート番号の検査を省いて読み込む
    LoadConfig(bypass_validation=True)
    Config().general.backend = backend

    # 番組情報の更新処理が参照する現在時刻を固定する
    setattr(app.models.Program, 'datetime', CreateFrozenDatetime(now))
