#!/usr/bin/env python3

"""
Usage: uv run python -m misc.FixtureProgramsCapturer tests/fixtures/programs --service 32736-32736-1024 --service 4-18803-260

実際の Mirakurun と EDCB から、指定したチャンネルの番組情報をテスト用データ (tests/fixtures/programs/) として取得するスクリプト。
Mirakurun の /api/programs の応答と、EDCB (EpgTimerSrv) の番組情報一覧の応答を、同じ時刻にそれぞれ取得する。
どちらも指定したチャンネルと期間の番組を抽出するのみで、番組情報の内容は変更せずに保存する。
EDCB の応答は KonomiTV の CtrlCmdUtil が受け取るバイト列のまま保存し、テストでは偽の EDCB からそのまま返す。
"""

import json
import socket
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx2 as httpx
import typer

from app.constants import JST
from app.utils.edcb.EDCBUtil import EDCBUtil


app = typer.Typer(add_completion=False)

# EpgTimerSrv の CtrlCmd のコマンド番号と成功の応答コード (app/utils/edcb/CtrlCmdUtil.py と同じ値)
CMD_SUCCESS = 1
CMD_EPG_SRV_ENUM_PG_INFO_EX = 1029


@app.command()
def main(
    output_dir: Path = typer.Argument(..., file_okay=False, resolve_path=True, help='Output directory.'),
    services: list[str] = typer.Option(..., '--service', help='Service to capture, in the form of "ONID-TSID-SID". Can be specified multiple times.'),
    hours: float = typer.Option(24, '--hours', min=1, help='Capture programs that start within this many hours from now.'),
    mirakurun_url: str = typer.Option('http://127.0.0.1:40772/', '--mirakurun-url', help='Mirakurun URL.'),
    edcb_url: str = typer.Option('tcp://127.0.0.1:4510/', '--edcb-url', help='EDCB (EpgTimerSrv) URL.'),
):
    # 取得対象のチャンネルを (ONID, TSID, SID) のタプルに変換する
    service_ids: list[tuple[int, int, int]] = []
    for service in services:
        onid, tsid, sid = (int(value) for value in service.split('-'))
        service_ids.append((onid, tsid, sid))

    # 取得時刻と、取得対象の番組の開始時刻の上限
    ## テストではこの時刻を現在時刻として番組情報を更新するため、最後に出力する
    captured_at = datetime.now(JST).replace(microsecond=0)
    limit = captured_at + timedelta(hours=hours)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Mirakurun から全番組を取得し、指定したチャンネルで期間内に開始する番組のみを、応答の順序を保ったまま抽出する
    response = httpx.get(mirakurun_url.rstrip('/') + '/api/programs', timeout=60)
    response.raise_for_status()
    mirakurun_programs = []
    for program in response.json():
        if (program['networkId'], program['serviceId']) not in [(onid, sid) for onid, _, sid in service_ids]:
            continue
        if program['startAt'] >= limit.timestamp() * 1000:
            continue
        mirakurun_programs.append(program)
    mirakurun_path = output_dir / 'mirakurun-programs.json'
    mirakurun_path.write_text(json.dumps(mirakurun_programs, ensure_ascii=False, indent=4) + '\n', encoding='utf-8')
    typer.echo(f'Wrote {mirakurun_path} ({len(mirakurun_programs)} programs).')

    # EDCB に、指定したチャンネルで期間内に開始する番組の一覧を要求する
    ## 引数は KonomiTV の CtrlCmdUtil.sendEnumPgInfoEx() と同じく、(マスク, サービス ID) の組の列と、開始時刻の範囲 (始点と終点)
    ## マスクを 0 にすると、サービス ID が完全に一致する番組のみを返す
    ## EDCB の FILETIME は日本時間基準のため、UTC+9 の固定のオフセットで変換する
    service_time_list: list[int] = []
    for onid, tsid, sid in service_ids:
        service_time_list += [0, onid << 32 | tsid << 16 | sid]
    service_time_list += [1, EDCBUtil.datetimeToFileTime(limit, timezone(timedelta(hours=9)))]
    body = struct.pack('<ii', 8 + 8 * len(service_time_list), len(service_time_list))
    body += b''.join(struct.pack('<q', value) for value in service_time_list)
    request = struct.pack('<ii', CMD_EPG_SRV_ENUM_PG_INFO_EX, len(body)) + body

    # 応答の先頭8バイト (応答コードと本体のサイズ) を読み込んでから、本体をそのまま保存する
    parsed_edcb_url = urlparse(edcb_url)
    with socket.create_connection((parsed_edcb_url.hostname, parsed_edcb_url.port), timeout=60) as connection:
        connection.sendall(request)
        reader = connection.makefile('rb')
        ret, size = struct.unpack('<ii', reader.read(8))
        if ret != CMD_SUCCESS:
            raise typer.Exit(f'EDCB returned an error. (ret: {ret})')
        edcb_programs = reader.read(size)
    edcb_path = output_dir / 'edcb-programs.bin'
    edcb_path.write_bytes(edcb_programs)
    typer.echo(f'Wrote {edcb_path} ({len(edcb_programs)} bytes).')

    typer.echo(f'Captured at {captured_at.isoformat()}.')


if __name__ == '__main__':
    app()
