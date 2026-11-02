"""リマインドの設定を、実際の認証・保存・取得 API を経由して往復させる。"""

import httpx2 as httpx


async def test_reminder_settings_roundtrip(client: httpx.AsyncClient, admin_headers: dict[str, str]) -> None:
    """
    放送予定と好みの条件が設定同期で保持され、端末のお知らせは同期対象から外れることを確認する。

    Args:
        client (httpx.AsyncClient): テスト用の API クライアント
        admin_headers (dict[str, str]): テストアカウントの認証情報
    """

    # 新しい設定キーが未保存のアカウントにも、クライアントと同じ既定値を返す。
    response = await client.get('/api/settings/client', headers=admin_headers)
    assert response.status_code == 200
    settings = response.json()
    assert settings['program_reminders'] == []
    assert settings['program_recommendation_enabled'] is False
    assert settings['program_recommendation_notify_by_default'] is True
    assert settings['program_reminder_lead_times'] == [1440, 180, 5]

    # 配列の内容と停止状態を保存し、取得時にも同じ内容が返ることを確認する。
    settings.update({
        'last_synced_at': 1.0,
        'program_reminders': [{
            'key': 'NID4-SID101-EID100@1794308400000',
            'status': 'Dismissed',
            'keyword_matches': [{
                'id': 'deleted-rule', 'name': '削除済みのお笑い',
                'condition_key': '["削除済みのお笑い","お笑い 特番","",null,false,true]',
            }],
        }],
        'program_recommendation_rules': [{'id': 'test-rule', 'keyword': 'お笑い 特番', 'is_enabled': True}],
        'program_recommendation_enabled': True,
        'program_recommendation_notify_by_default': False,
        'program_reminder_notifications_enabled': False,
        'program_reminder_notify_on_discovery': False,
        'program_reminder_lead_times': [180, 5, 1 / 60, 0],
    })
    response = await client.put('/api/settings/client', headers=admin_headers,
        json={**settings, 'program_reminder_notices': [{'id': 'local-only'}]})
    assert response.status_code == 204, response.text
    response = await client.get('/api/settings/client', headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == settings
    assert 'program_reminder_notices' not in response.json()

    # 現在のキーワードをすべて削除しても、通知予定の検索に使う登録時の情報は保持する。
    settings['program_recommendation_rules'] = []
    response = await client.put('/api/settings/client', headers=admin_headers, json=settings)
    assert response.status_code == 204, response.text
    response = await client.get('/api/settings/client', headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == settings

    # 秒単位の小数を保持し、負の通知時刻は保存前に拒否する。
    response = await client.put('/api/settings/client', headers=admin_headers,
        json={**settings, 'program_reminder_lead_times': [-1]})
    assert response.status_code == 422
    response = await client.get('/api/settings/client', headers=admin_headers)
    assert response.json()['program_reminder_lead_times'] == [180, 5, 1 / 60, 0]

    # ログインしていないリクエストには、個人の放送予定を返さない。
    response = await client.get('/api/settings/client')
    assert response.status_code == 401
