
import concurrent.futures
from typing import Any

from syrupy.assertion import SnapshotAssertion

from app.metadata.MetadataAnalyzer import MetadataAnalyzer
from tests.conftest import FIXTURES_DIR


def AnalyzeRecording(file_name: str) -> dict[str, Any]:
    """
    テスト用の録画ファイルを解析し、スナップショットと比べられる形の辞書を返す

    Args:
        file_name (str): tests/fixtures/recorded/ 以下のファイル名

    Returns:
        dict[str, Any]: 解析結果 (テスト用のファイルを置いた場所や、チェックアウトした日時で変わる値を除いたもの)
    """

    # 本番の RecordedScanTask と同じく、別のプロセスで解析する
    ## 地デジのチャンネル番号の計算では、解析するプロセスが自分で DB に接続して閉じる
    analyzer = MetadataAnalyzer(FIXTURES_DIR / 'recorded' / file_name)
    with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
        recorded_program = executor.submit(analyzer.analyze).result()
    assert recorded_program is not None
    return recorded_program.model_dump(
        mode = 'json',
        exclude = {
            'created_at': True,
            'updated_at': True,
            'recorded_video': {'file_path', 'file_created_at', 'file_modified_at', 'created_at', 'updated_at'},
        },
    )


def test_analyze_terrestrial_recording(snapshot_json: SnapshotAssertion) -> None:
    """
    地上波の録画データを用いて、正常に番組情報と映像・音声の情報を解析できることを確認する
    """

    assert AnalyzeRecording('terrestrial-tsreplace-h264.ts') == snapshot_json


def test_analyze_recording_with_aac_frames_misaligned_to_pes(snapshot_json: SnapshotAssertion) -> None:
    """
    AAC のフレームと PES の区切りがそろっていない放送局の録画データでも、音声のチャンネル数とサンプルレートを正しく取得できる
    このファイルは、MetadataAnalyzer が部分解析する際の開始位置 (ファイル全体の 25%) の音声 PES がフレームの途中から始まるため、
    そのまま FFprobe に渡すと 39ch・7350Hz と誤って判定されてしまう位置で敢えて切り出してある
    """

    result = AnalyzeRecording('bs-aac-misaligned-pes.ts')
    assert result['recorded_video']['primary_audio_channel'] == 'Stereo'
    assert result['recorded_video']['primary_audio_sampling_rate'] == 48000
    assert result == snapshot_json


def test_analyze_recording_read_within_recording_start_margin() -> None:
    """
    番組情報を読む位置 (ファイル全体の 20%) が録画開始マージン (前の番組の終わり) に入る録画データでも、
    前の番組ではなく、録画開始から1分以内に始まる録画対象の番組を選ぶ
    このファイルは、番組の開始の約10秒前から録画を始めた録画の先頭の約4秒だけを切り出してあり、全体が前の番組の時間に入る
    """

    result = AnalyzeRecording('terrestrial-recording-start-margin.ts')
    assert result['title'] == 'あおほし'
    assert result['start_time'] == '2025-06-10T02:00:00+09:00'
