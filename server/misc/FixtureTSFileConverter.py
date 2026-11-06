#!/usr/bin/env python3

"""
Usage: uv run python -m misc.FixtureTSFileConverter /path/to/input.ts tests/fixtures/recorded/output.ts --start 0 --length 127000000 --replace-video

実際の録画ファイルからテスト fixture 用 TS ファイル (tests/fixtures/recorded/) に変換するスクリプト。
録画の指定した範囲を TS パケット単位で切り出し、必要なら映像だけを低いビットレートの H.264 に差し替える。
番組情報 (PSI/SI)・音声・字幕は録画のまま残すので、解析のテストでは実際の放送の癖をそのまま確認できる。
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

import typer
from biim.mpeg2ts import ts

from app.constants import LIBRARY_PATH


app = typer.Typer(add_completion=False)


@app.command()
def main(
    input_path: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True, help='Input recorded TS file.'),
    output_path: Path = typer.Argument(..., dir_okay=False, resolve_path=True, help='Output TS file.'),
    start: int = typer.Option(0, '--start', min=0, help='Start byte offset in the input file (rounded down to a TS packet boundary).'),
    length: int = typer.Option(..., '--length', min=ts.PACKET_SIZE, help='Length in bytes to cut out (rounded down to a TS packet boundary).'),
    replace_video: bool = typer.Option(False, '--replace-video', help='Replace the video stream with a low bitrate H.264 stream using tsreplace.'),
    video_bitrate: str = typer.Option('120k', '--video-bitrate', help='Target bitrate of the replaced video stream.'),
):
    # 切り出す範囲を TS パケットの境界にそろえる
    start = start // ts.PACKET_SIZE * ts.PACKET_SIZE
    length = length // ts.PACKET_SIZE * ts.PACKET_SIZE

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        # 録画の指定した範囲を切り出す
        cut_path = temp_dir_path / 'cut.ts'
        with open(input_path, 'rb') as input_file, open(cut_path, 'wb') as cut_file:
            input_file.seek(start)
            cut_file.write(input_file.read(length))
        typer.echo(f'Cut {cut_path.stat().st_size} bytes from offset {start}.')

        # 映像を差し替えない場合は、切り出したファイルをそのまま出力する
        if replace_video is False:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cut_path, output_path)
            typer.echo(f'Wrote {output_path} ({output_path.stat().st_size} bytes).')
            return

        # 映像だけを非常に低いビットレートの H.264 にエンコードする
        ## 録画は 60i なので、yadif でフィールドごとでなくフレームごとにインターレースを解除する
        ## tsreplace が元の映像と同じ時刻に差し込めるよう、-copyts で元のタイムスタンプを保ったまま MPEG-TS に書き出す
        ## tsreplace の -e で FFmpeg をパイプでつなぐと FFmpeg のフィルターが失敗するため、いったんファイルに書き出す
        video_path = temp_dir_path / 'video.ts'
        subprocess.run(
            [
                LIBRARY_PATH['FFmpeg'],
                '-hide_banner',
                '-loglevel', 'error',
                '-copyts',
                '-i', str(cut_path),
                '-map', '0:v:0',
                '-an', '-sn', '-dn',
                '-vf', 'yadif=0',
                '-c:v', 'libx264',
                '-preset', 'veryfast',
                '-b:v', video_bitrate,
                '-g', '30',
                '-f', 'mpegts',
                '-y', str(video_path),
            ],
            check = True,
        )

        # tsreplace で映像のストリームを差し替える (番組情報・音声・字幕はそのまま残る)
        tsreplace_path = shutil.which('tsreplace')
        if tsreplace_path is None:
            typer.echo('tsreplace is not found in PATH.', err=True)
            raise typer.Exit(code=1)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                tsreplace_path,
                '-i', str(cut_path),
                '-r', str(video_path),
                '-o', str(output_path),
            ],
            check = True,
        )
        typer.echo(f'Wrote {output_path} ({output_path.stat().st_size} bytes).')


if __name__ == '__main__':
    app()
