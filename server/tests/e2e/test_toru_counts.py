"""torne のトル数の取得の E2E テスト。"""

import re

import httpx2 as httpx

from app.models.Channel import Channel
from app.utils.TorneClient import TorneClient


# =====================================================================================
# 複合フロー E2E テスト
# =====================================================================================

# -------------------------------------------------------------------------------------
# 実際の torne のトル数 API からトル数を取得し、API から番組ごとのトル数を取得するフロー
# (TorneClient.updateToruCounts() → GET /api/programs/toru-counts) - 正常系
# -------------------------------------------------------------------------------------


async def test_update_toru_counts__returns_counts_of_receivable_channels(client: httpx.AsyncClient) -> None:
    """
    実際の torne のトル数 API から取得したトル数を、受信できるチャンネルの番組 ID ごとに API から取得できる
    """

    # API 側のレスポンス形式や認証が変更された場合に検出できるよう、モックに差し替えずに実際の API を呼び出す
    await TorneClient.updateToruCounts()
    response = await client.get('/api/programs/toru-counts')
    assert response.status_code == 200, response.text
    toru_counts = response.json()

    # 地上波と BS の両方で、1週間先までの番組のトル数を取得できる
    ## 偽の Mirakurun は、地上波の NHK総合 (東京) と BS のチャンネルを返す
    channel_ids = {channel.id for channel in await Channel.filter(is_watchable=True)}
    counted_channel_ids: set[str] = set()
    for program_id, toru_count in toru_counts.items():

        # 番組 ID は、番組情報の ID と同じ「NID(ネットワーク ID)-SID(サービス ID)-EID(イベント ID)」の形式で、受信できるチャンネルの番組だけが含まれる
        match = re.fullmatch(r'(NID\d+-SID\d{3,})-EID\d+', program_id)
        assert match is not None, program_id
        assert match.group(1) in channel_ids, program_id
        counted_channel_ids.add(match.group(1))

        # トル数は 1 以上で、色を付け始める基準値は 2 以上になる
        assert toru_count['count'] >= 1, program_id
        assert toru_count['highlight_base'] is None or toru_count['highlight_base'] >= 2, program_id
    assert 'NID32736-SID1024' in counted_channel_ids
    assert 'NID4-SID101' in counted_channel_ids
    assert len(toru_counts) >= 100
