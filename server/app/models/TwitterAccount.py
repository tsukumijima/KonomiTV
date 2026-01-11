
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import atexit
import shutil
from typing import TYPE_CHECKING

import js2py_.node_import
import tweepy
from cryptography.fernet import InvalidToken
from fastapi import HTTPException, status
from requests.cookies import RequestsCookieJar
from tortoise import fields
from tortoise.models import Model as TortoiseModel
from tweepy_authlib import CookieSessionUserHandler

from app import logging
from app.constants import (
    TWITTER_ACCOUNT_COOKIE_ENCRYPTION_PREFIX,
    TWITTER_ACCOUNT_COOKIE_FERNET,
)


if TYPE_CHECKING:
    from app.models.User import User


# js2py_ ライブラリの node_import.py は、モジュールのトップレベルで tempfile.mkdtemp() を呼び出し
# 一時ディレクトリを作成するが、クリーンアップ処理が実装されていないため、一時ディレクトリが残り続けてしまう問題がある
# tweepy_authlib が js2py_ をインポートしているため、tweepy_authlib のインポート後に
# atexit でクリーンアップを登録することで、プロセス終了時に一時ディレクトリを削除する
# ref: https://github.com/nicholaskajoh/js2py_/blob/master/js2py_/node_import.py
def _cleanup_js2py_temp_dir() -> None:
    try:
        shutil.rmtree(js2py_.node_import.DIRNAME, ignore_errors=True)
    except Exception:
        pass

atexit.register(_cleanup_js2py_temp_dir)


class TwitterAccount(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'twitter_accounts'

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


    def encryptAccessTokenSecret(self, plain_text: str) -> str:
        """
        Netscape 形式の Cookie データを暗号化する

        Returns:
            str: 暗号化済みのテキスト
        """

        # 空文字は暗号化不要なのでそのまま返し、無駄な処理を避ける
        if plain_text == '':
            return ''

        # Fernet で暗号化し、接頭辞を付けて暗号化済みであることを明示する
        encrypted_text = TWITTER_ACCOUNT_COOKIE_FERNET.encrypt(plain_text.encode('utf-8')).decode('utf-8')
        return f'{TWITTER_ACCOUNT_COOKIE_ENCRYPTION_PREFIX}{encrypted_text}'


    def decryptAccessTokenSecret(self) -> str:
        """
        データベースに保存されている Cookie データを復号する

        Returns:
            str: 復号済みのテキスト
        """

        # 暗号化された Cookie の接頭辞がない場合はそのまま返す
        encrypted_text = self.access_token_secret or ''
        if encrypted_text == '':
            return ''
        # 接頭辞が無い (= 従来形式) 場合は平文として扱う
        if encrypted_text.startswith(TWITTER_ACCOUNT_COOKIE_ENCRYPTION_PREFIX) is False:
            return encrypted_text

        # 暗号化された Cookie の接頭辞を除去して復号する
        token = encrypted_text[len(TWITTER_ACCOUNT_COOKIE_ENCRYPTION_PREFIX):].encode('utf-8')
        try:
            decrypted_text = TWITTER_ACCOUNT_COOKIE_FERNET.decrypt(token).decode('utf-8')
        except InvalidToken as ex:
            logging.error('[TwitterAccount][decryptAccessTokenSecret] Failed to decrypt cookie:', exc_info=ex)
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail = 'Failed to decrypt Twitter cookies. Please re-link your Twitter account.',
            ) from ex

        return decrypted_text


    def getTweepyAuthHandler(self) -> CookieSessionUserHandler:
        """
        tweepy の認証ハンドラーを取得する
        access_token_secret には Netscape 形式の Cookie ファイルの内容が格納されている想定

        Returns:
            CookieSessionUserHandler: tweepy の認証ハンドラー (Cookie セッション)
        """

        # 循環インポート防止のためここでインポート
        from app.utils.TwitterScrapeBrowser import TwitterScrapeBrowser

        # Netscape Cookie ファイル形式の場合
        ## access_token フィールドが "NETSCAPE_COOKIE_FILE" の固定値になっている
        if self.access_token == 'NETSCAPE_COOKIE_FILE':

            # access_token_secret から Netscape 形式の Cookie をパースし、RequestCookieJar オブジェクトを作成
            cookies = RequestsCookieJar()
            cookies_txt_content = self.decryptAccessTokenSecret()
            # TwitterScrapeBrowser の parseNetscapeCookieFile を使って Cookie をパース
            cookie_params = TwitterScrapeBrowser.parseNetscapeCookieFile(cookies_txt_content)
            # CookieParam から RequestsCookieJar に変換
            for param in cookie_params:
                # ドメインが .x.com の場合のみ処理
                if param.domain is not None and 'x.com' in param.domain:
                    cookies.set(param.name, param.value, domain=param.domain)

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
        auth_handler = self.getTweepyAuthHandler()
        return tweepy.API(auth=auth_handler)
