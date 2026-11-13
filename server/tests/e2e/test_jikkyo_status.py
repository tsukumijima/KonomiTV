"""ニコニコ実況のステータスの取得の E2E テスト。"""

import httpx2 as httpx

from app.models.Channel import Channel


# =====================================================================================
# 複合フロー E2E テスト
# =====================================================================================

# -------------------------------------------------------------------------------------
# 実際の NX-Jikkyo のチャンネル情報 API から実況勢いを取得し、チャンネル情報に反映するフロー
# (Channel.updateJikkyoStatus() → GET /api/channels) - 正常系
# -------------------------------------------------------------------------------------


async def test_update_jikkyo_status__sets_jikkyo_force_of_channels(client: httpx.AsyncClient) -> None:
    """
    実際の NX-Jikkyo のチャンネル情報 API から取得した実況勢いを、実況チャンネルがあるチャンネルの情報として取得できる
    """

    # NX-Jikkyo 側のレスポンス形式が変更された場合に検出できるよう、モックに差し替えずに実際の API を呼び出す
    await Channel.updateJikkyoStatus()
    response = await client.get('/api/channels')
    assert response.status_code == 200, response.text
    channels = response.json()

    # 実況チャンネルがある NHK総合 (jk1) と NHK BS (jk101) には、0 以上の実況勢いが設定される
    jikkyo_forces = {channel['id']: channel['jikkyo_force'] for channel in channels['GR'] + channels['BS']}
    assert isinstance(jikkyo_forces['NID32736-SID1024'], int) and jikkyo_forces['NID32736-SID1024'] >= 0
    assert isinstance(jikkyo_forces['NID4-SID101'], int) and jikkyo_forces['NID4-SID101'] >= 0
