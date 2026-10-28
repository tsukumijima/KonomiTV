
import io
from datetime import datetime

from PIL import Image

from app.constants import JST
from app.metadata.CaptureScanTask import ReadCaptureImage
from tests.conftest import FIXTURES_DIR


# テスト用のキャプチャ (実際のキャプチャをそのまま置いたもの) があるディレクトリ
CAPTURES_DIR = FIXTURES_DIR / 'captures'


def test_read_capture_with_program_information() -> None:
    """
    EXIF の XPComment に書き込んだ番組情報を読み取る（撮影日時はファイルの更新日時より番組情報の値を優先する）
    """

    data = (CAPTURES_DIR / 'Capture_20260826-044039.jpg').read_bytes()
    info = ReadCaptureImage(data, 'Capture_20260826-044039.jpg', datetime(2030, 1, 1, tzinfo=JST))

    assert info.metadata_status == 'Parsed'
    assert (info.image_width, info.image_height) == (1440, 1080)
    assert info.captured_at == datetime(2026, 8, 26, 4, 40, 39, tzinfo=JST)
    assert info.metadata is not None
    assert (info.metadata.network_id, info.metadata.service_id, info.metadata.event_id) == (32738, 1040, 8571)
    assert info.metadata.title == 'Oha！4 ▽中野ブロードウェイ時計店で窃盗 被害総額2億円相当'
    assert info.metadata.start_time == datetime(2026, 8, 26, 4, 30, tzinfo=JST)
    assert info.metadata.captured_playback_position == 639.734
    # ファイルの中身の SHA-256 (sha256sum で計算した値)
    assert info.file_hash.hex() == 'a292a6e65340f11428dc56a62bf12ed1d4a4393063dd92ccd063527c38e149e8'


def test_read_capture_written_by_older_version() -> None:
    """
    2022年版の KonomiTV が書き込んだ番組情報 (字幕・コメントの合成の有無を含む形式) も読み取れる
    """

    data = (CAPTURES_DIR / 'Capture_20221219-001337.jpg').read_bytes()
    info = ReadCaptureImage(data, 'Capture_20221219-001337.jpg', datetime(2030, 1, 1, tzinfo=JST))

    assert info.metadata_status == 'Parsed'
    assert info.captured_at == datetime(2022, 12, 19, 0, 13, 37, tzinfo=JST)
    assert info.metadata is not None
    assert info.metadata.title == '宇崎ちゃんは遊びたい！ω #12「クリスマスイブも遊びたい！」'
    assert info.metadata.is_caption_composited is False
    assert info.metadata.is_comment_composited is False


def test_read_capture_without_playback_position_written_by_live_only_version() -> None:
    """
    2022年10月までの KonomiTV が書き込んだ、再生位置のない番組情報も読み取り、
    ライブ視聴のキャプチャとして、番組の開始時刻から撮影日時までの秒数を再生位置にする
    """

    data = (CAPTURES_DIR / 'Capture_20221003-224010.jpg').read_bytes()
    info = ReadCaptureImage(data, 'Capture_20221003-224010.jpg', datetime(2030, 1, 1, tzinfo=JST))

    assert info.metadata_status == 'Parsed'
    assert info.captured_at == datetime(2022, 10, 3, 22, 40, 10, tzinfo=JST)
    assert info.metadata is not None
    assert (info.metadata.network_id, info.metadata.service_id, info.metadata.event_id) == (32391, 23608, 43641)
    assert info.metadata.title == '[新]新米錬金術師の店舗経営 #1'
    assert info.metadata.start_time == datetime(2022, 10, 3, 22, 30, tzinfo=JST)
    # 22:30:00 に始まった番組を 22:40:10 に撮ったので、再生位置は10分10秒
    assert info.metadata.captured_playback_position == 610.0


def test_read_capture_of_program_with_undecided_duration() -> None:
    """
    放送時間未定の番組で撮ったキャプチャの番組情報も読み取り、終了時刻と番組長を不明 (None) として扱う
    """

    data = (CAPTURES_DIR / 'Capture_20251013-141201.jpg').read_bytes()
    info = ReadCaptureImage(data, 'Capture_20251013-141201.jpg', datetime(2030, 1, 1, tzinfo=JST))

    assert info.metadata_status == 'Parsed'
    assert info.metadata is not None
    assert info.metadata.title == 'ニュース'
    assert info.metadata.start_time == datetime(2025, 10, 13, 13, 55, tzinfo=JST)
    # 番組情報には終了時刻として開始時刻と同じ値が書き込まれているが、終了時刻としては使えないので None にする
    assert info.metadata.end_time is None
    assert info.metadata.duration is None
    assert info.metadata.captured_playback_position == 1021.285


def test_read_capture_without_metadata_uses_file_modified_time() -> None:
    """
    番組情報も EXIF もない PNG は、ファイル名の時刻と近ければ、ファイルの更新日時を撮影日時にする
    """

    data = (CAPTURES_DIR / 'Capture_20190629-092455.png').read_bytes()
    modified_at = datetime(2019, 6, 29, 9, 25, 30, tzinfo=JST)
    info = ReadCaptureImage(data, 'Capture_20190629-092455.png', modified_at)

    assert info.metadata_status == 'NoMetadata'
    assert info.metadata is None
    assert (info.image_width, info.image_height) == (1440, 810)
    assert info.captured_at == modified_at


def test_read_capture_without_metadata_prefers_file_name_time_after_copy() -> None:
    """
    番組情報も EXIF もない画像で、ファイルの更新日時がファイル名の時刻から10分以上離れているときは、
    コピーで更新日時が変わったとみなして、ファイル名の時刻を撮影日時にする
    """

    data = (CAPTURES_DIR / 'Capture_20190629-092455.png').read_bytes()
    info = ReadCaptureImage(data, 'Capture_20190629-092455.png', datetime(2024, 3, 1, 12, 0, tzinfo=JST))

    assert info.metadata_status == 'NoMetadata'
    assert info.captured_at == datetime(2019, 6, 29, 9, 24, 55, tzinfo=JST)


def test_read_capture_without_metadata_named_in_twelve_hour_notation() -> None:
    """
    番組情報も EXIF もない画像で、ファイルの更新日時がファイル名の時刻とちょうど12時間ずれているときは、
    時刻を12時間表記で名前に入れるソフトで撮ったとみなして、ファイルの更新日時を撮影日時にする
    """

    data = (CAPTURES_DIR / 'Capture_20190629-092455.png').read_bytes()
    modified_at = datetime(2019, 6, 29, 21, 24, 55, tzinfo=JST)
    info = ReadCaptureImage(data, 'Capture_20190629-092455.png', modified_at)

    assert info.metadata_status == 'NoMetadata'
    assert info.captured_at == modified_at


def test_read_capture_tiny_jpeg() -> None:
    """
    保存先に置かれたアイコンのような、縦か横が 8px 未満の JPEG も読める
    """

    # 縦横とも 8px 未満の JPEG と、横だけが 8px 未満の JPEG を作る
    for image_width, image_height in [(5, 5), (7, 100)]:
        buffer = io.BytesIO()
        Image.new('RGB', (image_width, image_height)).save(buffer, 'JPEG')
        modified_at = datetime(2024, 3, 1, 12, 0, tzinfo=JST)
        info = ReadCaptureImage(buffer.getvalue(), 'icon.jpg', modified_at)

        assert (info.image_width, info.image_height) == (image_width, image_height)
