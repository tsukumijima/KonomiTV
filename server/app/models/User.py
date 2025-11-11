
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import httpx
from tortoise import fields
from tortoise.fields import Field as TortoiseField
from tortoise.models import Model as TortoiseModel

from app.constants import API_REQUEST_HEADERS, HTTPX_CLIENT, NICONICO_OAUTH_CLIENT_ID
from app.utils import Interlaced


if TYPE_CHECKING:
    from app.models.TwitterAccount import TwitterAccount


class User(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'users'

    id = fields.IntField(pk=True)
    name = fields.TextField()
    password = fields.TextField()
    is_admin = fields.BooleanField()
    client_settings = cast(TortoiseField[dict[str, Any]], fields.JSONField(default={}, encoder=lambda x: json.dumps(x, ensure_ascii=False)))  # type: ignore
    niconico_user_id = cast(TortoiseField[int | None], fields.IntField(null=True))
    niconico_user_name = cast(TortoiseField[str | None], fields.TextField(null=True))
    niconico_user_premium = cast(TortoiseField[bool | None], fields.BooleanField(null=True))
    niconico_access_token = cast(TortoiseField[str | None], fields.TextField(null=True))
    niconico_refresh_token = cast(TortoiseField[str | None], fields.TextField(null=True))
    twitter_accounts: fields.ReverseRelation[TwitterAccount]
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)


    async def refreshNiconicoAccessToken(self) -> None:
        """
        このユーザーに紐づくニコニコアカウントのアクセストークンを、リフレッシュトークンで更新する
        更新されたアクセストークンはこのメソッド内でデータベースに永続化される

        Raises:
            Exception: アクセストークンの更新に失敗した場合 (例外に含まれるエラーメッセージを API レスポンスで返す想定)
        """

        try:

            # リフレッシュトークンを使い、ニコニコ OAuth のアクセストークンとリフレッシュトークンを更新
            token_api_url = 'https://oauth.nicovideo.jp/oauth2/token'
            async with HTTPX_CLIENT() as client:
                token_api_response = await client.post(
                    url = token_api_url,
                    headers = {**API_REQUEST_HEADERS, 'Content-Type': 'application/x-www-form-urlencoded'},
                    data = {
                        'grant_type': 'refresh_token',
                        'client_id': NICONICO_OAUTH_CLIENT_ID,
                        'client_secret': Interlaced(3),
                        'refresh_token': self.niconico_refresh_token,
                    },
                )

            # ステータスコードが 200 以外
            if token_api_response.status_code != 200:
                error_code = ''
                try:
                    error_code = f' ({token_api_response.json()["error"]})'
                except Exception:
                    pass
                raise Exception(f'アクセストークンの更新に失敗しました。(HTTP Error {token_api_response.status_code}{error_code})')

            token_api_response_json = token_api_response.json()

        # 接続エラー（サーバーメンテナンスやタイムアウトなど）
        except (httpx.NetworkError, httpx.TimeoutException):
            raise Exception('アクセストークンの更新リクエストがタイムアウトしました。')

        # 取得したアクセストークンとリフレッシュトークンをユーザーアカウントに設定
        ## 仕様上リフレッシュトークンに有効期限はないが、一応このタイミングでリフレッシュトークンも更新することが推奨されている
        self.niconico_access_token = str(token_api_response_json['access_token'])
        self.niconico_refresh_token = str(token_api_response_json['refresh_token'])

        try:
            # ついでなので、このタイミングでユーザー情報を取得し直す
            ## 頻繁に変わるものでもないとは思うけど、一応再ログインせずとも同期されるようにしておきたい
            ## 3秒応答がなかったらタイムアウト
            user_api_url = f'https://nvapi.nicovideo.jp/v1/users/{self.niconico_user_id}'
            async with HTTPX_CLIENT() as client:
                # X-Frontend-Id がないと INVALID_PARAMETER になる
                user_api_response = await client.get(user_api_url, headers={**API_REQUEST_HEADERS, 'X-Frontend-Id': '6'})

            if user_api_response.status_code == 200:
                # ユーザー名
                self.niconico_user_name = str(user_api_response.json()['data']['user']['nickname'])
                # プレミアム会員かどうか
                self.niconico_user_premium = bool(user_api_response.json()['data']['user']['isPremium'])

        # 接続エラー（サーバー再起動やタイムアウトなど）
        except (httpx.NetworkError, httpx.TimeoutException):
            pass  # 取れなくてもセッション取得に支障はないのでパス

        # 変更をデータベースに保存
        await self.save()
