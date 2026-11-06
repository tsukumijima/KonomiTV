"""番組情報の更新 (Program.update) の E2E テスト。"""

import asyncio
import concurrent.futures
import functools
import json
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from typing import Any, Literal

import httpx2 as httpx
import pytest
import pytest_asyncio
from syrupy.assertion import SnapshotAssertion
from tortoise import transactions

from app.config import Config
from app.constants import JST
from app.models.Channel import Channel
from app.models.Program import Program
from tests.conftest import FAKE_EDCB, FAKE_MIRAKURUN, FIXTURES_DIR
from tests.FrozenDatetime import CreateFrozenDatetime, InitializeProgramUpdateProcess


# tests/fixtures/programs/ の番組情報を、実際の Mirakurun と EDCB から取得した時刻
## 番組情報の更新処理は現在時刻より12時間以上前に終了した番組を除外するため、テストではこの時刻を現在時刻として扱う
CAPTURED_AT = datetime(2026, 10, 29, 9, 47, 15, tzinfo=JST)

# EDCB の番組情報は TSID まで一致するチャンネルにのみ保存されるため、BS のチャンネルに設定する TSID
## Mirakurun の /api/services の応答には TSID が含まれず、偽の Mirakurun から生成された BS のチャンネルの TSID は空になる
## 地上波のチャンネルには、NID と同じ値が TSID として設定される
EDCB_TRANSPORT_STREAM_IDS = {
    'NID4-SID101': 16625,
    'NID4-SID260': 18803,
}


def FreezeNow(monkeypatch: pytest.MonkeyPatch, now: datetime) -> None:
    """
    番組情報の更新処理が現在時刻として参照する datetime.now() を、指定した時刻に固定する
    別プロセスで番組情報を更新する場合は、子プロセスにも InitializeProgramUpdateProcess() で同じ時刻を適用する必要がある

    Args:
        monkeypatch (pytest.MonkeyPatch): pytest の monkeypatch
        now (datetime): 現在時刻として扱う時刻
    """

    monkeypatch.setattr('app.models.Program.datetime', CreateFrozenDatetime(now))


async def UpdatePrograms(backend: Literal['Mirakurun', 'EDCB']) -> None:
    """
    サーバーの起動時と同じく、指定したバックエンドから同一プロセス内で番組情報を更新する

    Args:
        backend (Literal['Mirakurun', 'EDCB']): 番組情報を取得するバックエンド
    """

    if backend == 'Mirakurun':
        await Program.updateFromMirakurun()
    else:
        await Program.updateFromEDCB()


async def DumpPrograms() -> dict[str, dict[str, Any]]:
    """
    DB に保存された番組情報を、スナップショットと比較できるよう番組 ID をキーにした辞書で返す

    Returns:
        dict[str, dict[str, Any]]: 番組 ID の順に並べた番組情報 (日時は ISO 8601 形式の文字列に変換する)
    """

    programs: dict[str, dict[str, Any]] = {}
    for program in await Program.all().order_by('id').values():
        for key, value in program.items():
            if isinstance(value, datetime):
                program[key] = value.isoformat()
        programs[program['id']] = program
    return programs


@pytest_asyncio.fixture(params=['Mirakurun', 'EDCB'])
async def backend(
    request: pytest.FixtureRequest,
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[Literal['Mirakurun', 'EDCB']]:
    """
    偽の Mirakurun と EDCB が tests/fixtures/programs/ の番組情報を返すように設定し、番組情報が空の状態からテストを開始する
    サーバーの起動処理 (client) でチャンネル情報を登録してから使用する

    Args:
        request (pytest.FixtureRequest): テストするバックエンド ('Mirakurun' または 'EDCB') を param に持つリクエスト
        client (httpx.AsyncClient): サーバーの起動処理を済ませたアプリケーションへの HTTP クライアント
        monkeypatch (pytest.MonkeyPatch): pytest の monkeypatch

    Returns:
        AsyncGenerator[Literal['Mirakurun', 'EDCB']]: テストするバックエンド
    """

    backend: Literal['Mirakurun', 'EDCB'] = request.param
    FreezeNow(monkeypatch, CAPTURED_AT)

    # 偽の Mirakurun と EDCB が、実際に取得した番組情報を返すように設定する
    FAKE_MIRAKURUN.programs = json.loads((FIXTURES_DIR / 'programs' / 'mirakurun-programs.json').read_text(encoding='utf-8'))
    original_edcb_programs = FAKE_EDCB.programs
    FAKE_EDCB.programs = (FIXTURES_DIR / 'programs' / 'edcb-programs.bin').read_bytes()

    # EDCB から更新する場合は、バックエンドが EDCB のときと同じく BS のチャンネルにも TSID を設定する
    if backend == 'EDCB':
        for channel_id, transport_stream_id in EDCB_TRANSPORT_STREAM_IDS.items():
            await Channel.filter(id=channel_id).update(transport_stream_id=transport_stream_id)

    await Program.all().delete()
    try:
        yield backend

    # ほかのテストに影響しないよう、番組情報とチャンネルの TSID を元に戻す
    finally:
        await Program.all().delete()
        if backend == 'EDCB':
            await Channel.filter(id__in=list(EDCB_TRANSPORT_STREAM_IDS.keys())).update(transport_stream_id=None)
        FAKE_MIRAKURUN.programs = []
        FAKE_EDCB.programs = original_edcb_programs


# -------------------------------------------------------------------------------------
# 番組情報の更新 (Program.updateFromMirakurun / Program.updateFromEDCB) - 正常系
# -------------------------------------------------------------------------------------


async def test_update_programs(backend: Literal['Mirakurun', 'EDCB'], monkeypatch: pytest.MonkeyPatch, snapshot_json: SnapshotAssertion) -> None:
    """
    実際の番組情報から番組を追加し、再度更新すると DB と番組表の差異を番組表に合わせて修正し、
    時間が経過すると12時間以上前に終了した番組を削除する
    """

    # 番組情報が空の状態から更新すると、登録済みのチャンネルのメインの番組のみを追加する
    await UpdatePrograms(backend)
    programs = await DumpPrograms()
    assert programs == snapshot_json(name='added')

    # DB の番組情報と番組表に差異がある状態で、再度更新する
    ## 番組名が変更された番組は番組表の内容に戻し、DB から削除された番組は再度追加し、番組表に存在しない番組は削除する
    ## Mirakurun で終了時刻が未定の番組 (NID32736-SID1024-EID6473) は、初回の更新で仮に設定した終了時刻をそのまま使う
    stale_program = await Program.get(id='NID32736-SID1024-EID4494')
    stale_program.id = 'NID32736-SID1024-EID0'
    stale_program.event_id = 0
    await stale_program.save(force_create=True)
    await Program.filter(id='NID32736-SID1024-EID4494').update(title='番組表と食い違う番組名')
    await Program.filter(id='NID4-SID260-EID25033').delete()
    await UpdatePrograms(backend)
    assert await DumpPrograms() == programs

    # 6時間後に再度更新すると、その時点で12時間以上前に終了した番組を削除する
    FreezeNow(monkeypatch, CAPTURED_AT + timedelta(hours=6))
    await UpdatePrograms(backend)
    updated_programs = await DumpPrograms()
    deleted_program_ids: list[str] = []
    for program_id in programs:
        if program_id not in updated_programs:
            deleted_program_ids.append(program_id)
    changed_programs: list[dict[str, Any]] = []
    for program_id, program in updated_programs.items():
        if programs.get(program_id) != program:
            changed_programs.append(program)
    assert {'deleted': deleted_program_ids, 'changed': changed_programs} == snapshot_json(name='six_hours_later')


# -------------------------------------------------------------------------------------
# 別プロセスで番組情報を更新している間に、メインプロセスが DB へ書き込むフロー
# (Program.update(multiprocess=True) → メインプロセスの書き込み) - 正常系
# -------------------------------------------------------------------------------------


async def test_update_programs__in_another_process_while_main_process_writes(backend: Literal['Mirakurun', 'EDCB'], monkeypatch: pytest.MonkeyPatch) -> None:
    """
    サーバーの定期更新と同じく別プロセスで番組情報を更新し、その間にメインプロセスが DB への書き込みを続けても、
    同一プロセスで更新した場合と同じ番組をすべて保存できる
    """

    # 同一プロセスで更新した結果を期待値とする
    await UpdatePrograms(backend)
    expected_programs = await DumpPrograms()
    await Program.all().delete()

    # Program.update() は設定されたバックエンドから番組情報を取得する
    monkeypatch.setattr(Config().general, 'backend', backend)

    # 別プロセスで番組情報を更新する子プロセスにも、固定した現在時刻とバックエンドを適用する
    ## forkserver で起動した子プロセスは、メインプロセスで monkeypatch した値ではなく、config.test.yaml の設定と実際の時刻で動作する
    monkeypatch.setattr(concurrent.futures, 'ProcessPoolExecutor', functools.partial(
        concurrent.futures.ProcessPoolExecutor,
        initializer = InitializeProgramUpdateProcess,
        initargs = (CAPTURED_AT, backend),
    ))
    programs_requested = FAKE_MIRAKURUN.programs_requested if backend == 'Mirakurun' else FAKE_EDCB.programs_requested
    programs_requested.clear()
    is_update_finished = asyncio.Event()

    async def WriteFromMainProcess() -> None:
        """
        ニコニコ実況の勢いの更新や録画のスキャンのように、メインプロセスから DB への書き込みを続ける
        """

        # 書き込みのたびに、チャンネルの実況の勢いを前回と異なる値に更新する
        ## SQLite は値が変わらない UPDATE ではデータベースを変更しないため、別プロセスのスナップショットが古くならず、書き込みの衝突を再現できない
        jikkyo_force = 0

        # 別プロセスが番組情報の取得を終えて DB の読み取りを始めるまで、書き込みのトランザクションを維持する
        async with transactions.in_transaction():
            jikkyo_force += 1
            await Channel.filter(id='NID32736-SID1024').update(jikkyo_force=jikkyo_force)
            while programs_requested.is_set() is False and is_update_finished.is_set() is False:
                await asyncio.sleep(0.01)
            await asyncio.sleep(0.5)

        # その後も、番組情報の更新が完了するまで短い書き込みを繰り返す
        while is_update_finished.is_set() is False:
            jikkyo_force += 1
            await Channel.filter(id='NID32736-SID1024').update(jikkyo_force=jikkyo_force)
            await asyncio.sleep(0.05)

    writer = asyncio.create_task(WriteFromMainProcess())
    try:
        await asyncio.wait_for(Program.update(multiprocess=True), timeout=30)
    finally:
        is_update_finished.set()
        await writer
        await Channel.filter(id='NID32736-SID1024').update(jikkyo_force=None)
    assert await DumpPrograms() == expected_programs
