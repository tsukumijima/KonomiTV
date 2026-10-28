
import json
import shutil
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx2 as httpx
import pytest
import pytest_asyncio
from aerich import Command
from asgi_lifespan import LifespanManager
from syrupy.assertion import SnapshotAssertion
from syrupy.extensions.json import JSONSnapshotExtension
from tortoise import Tortoise

from app.config import LoadConfig
from app.constants import (
    ACCOUNT_ICON_DIR,
    BASE_DIR,
    DATA_DIR,
    DATABASE_CONFIG,
    IS_TEST,
    RESTART_REQUIRED_LOCK_PATH,
    TEST_SUFFIX,
    THUMBNAILS_DIR,
    TWITTER_DEBUG_SCREENSHOTS_DIR,
)
from tests.MockMirakurun import MockMirakurun


# テスト用のファイル (実際の録画やキャプチャから作ったもの) があるディレクトリ
FIXTURES_DIR = Path(__file__).resolve().parent / 'fixtures'

# テストの実行中にサーバーが読み込む設定ファイルのパス
## app/config.py の _CONFIG_YAML_PATH と同じ場所で、テストのたびに書き出す
CONFIG_PATH = BASE_DIR.parent / f'config{TEST_SUFFIX}.yaml'

# テストの実行中に使う一時フォルダと偽の Mirakurun
## pytest_configure() で中身を用意して起動し、pytest_unconfigure() で片付ける
## 録画フォルダとキャプチャの保存先は、テストのたびに空のフォルダから始める
TEMP_DIR = Path(tempfile.mkdtemp(prefix='KonomiTV-Test-'))
RECORDED_FOLDER = TEMP_DIR / 'recorded'
CAPTURE_FOLDER = TEMP_DIR / 'captures'
FAKE_MIRAKURUN = MockMirakurun()


def pytest_configure(config: pytest.Config) -> None:
    """
    テストの収集より前に、テスト用の DB・設定・保存先を用意し、サーバー設定を読み込む
    サーバーのモジュールの多くは読み込み時にサーバー設定を参照するため、テストのモジュールを読み込む前に済ませる

    Args:
        config (pytest.Config): pytest の設定
    """

    # 書き込みが発生するファイルとフォルダが、テスト用の名前に切り替わっていることを確かめる
    ## pyproject.toml の [tool.pytest_env] で KONOMITV_TEST が設定されていなければ、実際に使っている DB や設定を書き換えてしまう
    assert IS_TEST is True, 'KONOMITV_TEST must be set to 1 by pytest-env.'

    # 前回のテストが残したファイルとフォルダを消し、空の状態から始める
    ## いずれも名前に .test が付いた、テストだけが書き込むファイルとフォルダ
    database_path = DATA_DIR / f'database{TEST_SUFFIX}.sqlite'
    for path in [
        database_path,
        database_path.with_name(f'{database_path.name}-wal'),
        database_path.with_name(f'{database_path.name}-shm'),
        RESTART_REQUIRED_LOCK_PATH,
        CONFIG_PATH,
    ]:
        assert '.test' in path.name
        path.unlink(missing_ok=True)
    for path in [THUMBNAILS_DIR, ACCOUNT_ICON_DIR, TWITTER_DEBUG_SCREENSHOTS_DIR]:
        assert path.name.endswith('.test')
        shutil.rmtree(path, ignore_errors=True)
    THUMBNAILS_DIR.mkdir()
    ACCOUNT_ICON_DIR.mkdir()

    # 録画フォルダとキャプチャの保存先を作る
    RECORDED_FOLDER.mkdir()
    CAPTURE_FOLDER.mkdir()

    # 放送のバックエンドとして偽の Mirakurun を起動する
    FAKE_MIRAKURUN.start()

    # テスト用のサーバー設定を書き出して読み込む
    ## JSON は YAML としても読めるので、そのまま config.test.yaml に書き出す
    ## 開発サーバーが使っているポートと重なってポート番号の検査に失敗するため、自動リロードモードと同じく検査を省いて読み込む
    config_dict = {
        'general': {
            'backend': 'Mirakurun',
            'mirakurun_url': FAKE_MIRAKURUN.url,
            'encoder': 'FFmpeg',
        },
        'video': {
            'recorded_folders': [str(RECORDED_FOLDER)],
        },
        'capture': {
            'upload_folders': [str(CAPTURE_FOLDER)],
        },
    }
    CONFIG_PATH.write_text(json.dumps(config_dict, ensure_ascii=False, indent=4), encoding='utf-8')
    LoadConfig(bypass_validation=True)


def pytest_unconfigure(config: pytest.Config) -> None:
    """
    テストの終了後に、偽の Mirakurun を止め、一時フォルダを片付ける

    Args:
        config (pytest.Config): pytest の設定
    """

    FAKE_MIRAKURUN.stop()
    shutil.rmtree(TEMP_DIR, ignore_errors=True)


@pytest.fixture
def snapshot_json(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """
    syrupy で JSON をスナップショットするためのフィクスチャ

    Args:
        snapshot (SnapshotAssertion): syrupy のスナップショット

    Returns:
        SnapshotAssertion: JSON の形式で保存するスナップショット
    """

    return snapshot.use_extension(JSONSnapshotExtension)


@pytest_asyncio.fixture(scope='session', loop_scope='session', autouse=True)
async def database() -> AsyncGenerator[None]:
    """
    本番の起動 (KonomiTV.py) と同じく、Aerich のマイグレーションで空のテスト用の DB に表を作る
    """

    command = Command(tortoise_config=DATABASE_CONFIG, app='models', location=str(BASE_DIR / 'app/migrations'))
    await command.init()
    await command.upgrade(run_in_transaction=True)
    await Tortoise.close_connections()
    yield


@pytest_asyncio.fixture(scope='session', loop_scope='session')
async def client() -> AsyncGenerator[httpx.AsyncClient]:
    """
    サーバーの起動処理 (チャンネル・番組情報の更新、録画とキャプチャのスキャンの開始) を実際に動かし、
    起動したアプリケーションへリクエストを送る HTTP クライアントを返す

    Returns:
        AsyncGenerator[httpx.AsyncClient]: アプリケーションへ直接リクエストを送る HTTP クライアント
    """

    # サーバー設定を読み込んだ後で、FastAPI のアプリケーションを読み込む
    from app.app import app
    from app.utils.JikkyoClient import JikkyoClient

    with pytest.MonkeyPatch.context() as monkeypatch:

        # ニコニコ実況の状態の取得はインターネット上の API を使うため、何もしない処理に差し替える
        async def UpdateStatuses() -> None:
            return
        monkeypatch.setattr(JikkyoClient, 'updateStatuses', UpdateStatuses)

        async with LifespanManager(app, startup_timeout=60, shutdown_timeout=60) as manager:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=manager.app), base_url='http://test') as client:
                yield client


@pytest_asyncio.fixture(scope='session', loop_scope='session')
async def admin_headers(client: httpx.AsyncClient) -> dict[str, str]:
    """
    管理者のアカウントを作成してログインし、認証が必要な API に付けるヘッダーを返す
    最初に作成したアカウントは管理者になる

    Args:
        client (httpx.AsyncClient): アプリケーションへの HTTP クライアント

    Returns:
        dict[str, str]: Authorization ヘッダー
    """

    response = await client.post('/api/users', json={'username': 'admin', 'password': 'password'})
    assert response.status_code == 201, response.text
    response = await client.post('/api/users/token', data={'username': 'admin', 'password': 'password'})
    assert response.status_code == 200, response.text
    return {'Authorization': f'Bearer {response.json()["access_token"]}'}


@pytest.fixture
def recorded_folder() -> Path:
    """
    テストの実行中にサーバーが監視する録画フォルダのパスを返す

    Returns:
        Path: 録画フォルダのパス
    """

    return RECORDED_FOLDER


@pytest.fixture
def capture_folder() -> Path:
    """
    テストの実行中にサーバーがキャプチャを保存するフォルダのパスを返す

    Returns:
        Path: キャプチャの保存先フォルダのパス
    """

    return CAPTURE_FOLDER
