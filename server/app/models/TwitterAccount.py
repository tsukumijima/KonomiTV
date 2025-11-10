
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

from typing import TYPE_CHECKING

import tweepy
from fastapi import HTTPException, status
from requests.cookies import RequestsCookieJar
from tortoise import fields
from tortoise.models import Model as TortoiseModel
from tweepy_authlib import CookieSessionUserHandler

from app import logging


if TYPE_CHECKING:
    from app.models.User import User


class TwitterAccount(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'twitter_accounts'

    # テーブル設計は Notion を参照のこと
    id = fields.IntField(pk=True)
    user: fields.ForeignKeyRelation[User] = \
        fields.ForeignKeyField('models.User', related_name='twitter_accounts', on_delete=fields.CASCADE)
    user_id: int
    name = fields.TextField()
    screen_name = fields.TextField()
    icon_url = fields.TextField()
    access_token = fields.TextField()
    access_token_secret = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)


    def getTweepyAuthHandler(self) -> CookieSessionUserHandler:
        """
        tweepy の認証ハンドラーを取得する
        access_token_secret には Netscape 形式の Cookie ファイルの内容が格納されている想定

        Returns:
            CookieSessionUserHandler: tweepy の認証ハンドラー (Cookie セッション)
        """

        # Netscape Cookie ファイル形式の場合
        ## access_token フィールドが "NETSCAPE_COOKIE_FILE" の固定値になっている
        if self.access_token == 'NETSCAPE_COOKIE_FILE':

            # access_token_secret から Netscape 形式の Cookie をパースし、RequestCookieJar オブジェクトを作成
            cookies = RequestsCookieJar()
            cookies_txt_content = self.access_token_secret
            # cookies.txt の内容を行ごとに分割
            cookies_lines = cookies_txt_content.strip().split('\n')
            for line in cookies_lines:
                # コメント行やヘッダー行をスキップ
                if line.startswith('#') or line.startswith('# ') or not line.strip():
                    continue
                # タブで分割し、必要な情報を取得
                parts = line.split('\t')
                if len(parts) >= 7:
                    domain, _, _, _, _, name, value = parts[:7]
                    # ドメインが .twitter.com または .x.com の場合のみ処理
                    if domain in ['.twitter.com', 'twitter.com', '.x.com', 'x.com']:
                        cookies.set(name, value, domain=domain)

            # 読み込んだ RequestCookieJar オブジェクトを CookieSessionUserHandler に渡す
            ## Cookie を指定する際はコンストラクタ内部で API リクエストは行われないため、ログイン時のように await する必要性はない
            auth_handler = CookieSessionUserHandler(cookies=cookies)

        # 古い形式のレコード (OAuth 認証や旧 Cookie 形式) の場合
        else:
            logging.error(f'[TwitterAccount][getTweepyAuthHandler] OAuth session or old cookie format is no longer available. [screen_name: {self.screen_name}]')
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='OAuth session or old cookie format is no longer available.',
            )

        return auth_handler


    def getTweepyAPI(self) -> tweepy.API:
        """
        tweepy の API インスタンスを取得する

        Returns:
            tweepy.API: tweepy の API インスタンス
        """

        # auth_handler で初期化した tweepy.API インスタンスを返す
        return tweepy.API(auth=self.getTweepyAuthHandler())
