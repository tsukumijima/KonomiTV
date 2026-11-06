
import json
from typing import Any
from urllib.parse import urlsplit

from fastapi.responses import HTMLResponse


class OAuthCallbackResponse(HTMLResponse):
    """ OAuth 連携のコールバック時のレスポンス """

    def __init__(
        self,
        detail: str,
        redirect_to: str,
        status_code: int = 200,
        headers: dict[str, Any] = {},
    ) -> None:
        """
        OAuth 連携のコールバック時のレスポンスを返す
        実際に出力されるのは HTML で、OAuth 連携が完了または失敗したことを KonomiTV クライアントに送信するための JavaScript が記述される

        Args:
            detail (str): KonomiTV クライアントに送信する詳細メッセージ
            redirect_to (str): リダイレクト先の KonomiTV クライアントの URL (モバイルデバイスのみ利用)
            status_code (int, optional): HTTP ステータスコード. Defaults to 200.
            headers (dict, optional): カスタムのヘッダー. Defaults to None.
        """
        self.status_code = status_code
        self.detail = detail
        self.redirect_to = redirect_to
        self.background = None
        self.body = self.render()
        self.init_headers(headers)


    def render(self, content: Any = None) -> bytes:

        # JavaScript へ渡す値は全体を JSON 化し、文字列置換によるスクリプト注入を防ぐ
        ## 以前は '$detail$' のように生の値を <script> 内へ直接埋め込んでいたため、detail や redirect_to に
        ## 引用符やバッククオートを含めるとスクリプトを注入できる状態だった
        ## JSON 文字列内でも </script> は HTML パーサーに終了タグとして扱われるため、山括弧も Unicode エスケープする
        callback_data_json = (
            json.dumps(
                {
                    'status': self.status_code,
                    'detail': self.detail,
                },
                ensure_ascii=False,
                separators=(',', ':'),
            )
            .replace('<', '\\u003C')
            .replace('>', '\\u003E')
            .replace('&', '\\u0026')
        )
        redirect_to_json = (
            json.dumps(self.redirect_to, ensure_ascii=False).replace('<', '\\u003C').replace('>', '\\u003E')
        )

        # ポップアップへ postMessage する際の送信先オリジンをリダイレクト先 URL から導出する
        ## 以前は '*' を指定しており、任意のオリジンへコールバック情報を渡しうる状態だった
        redirect_url = urlsplit(self.redirect_to)
        target_origin = f'{redirect_url.scheme}://{redirect_url.netloc}'
        target_origin_json = json.dumps(target_origin)

        # ブラウザに返す HTML のテンプレート
        html = """
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="utf-8">
            <meta http-equiv="X-UA-Compatible" content="IE=edge">
            <meta name="viewport" content="width=device-width,initial-scale=1.0">
            <script>
                window.onload = () => {
                    // (PC) ポップアップ経由で OAuth 連携を行った場合
                    if (window.opener) {
                        window.opener.postMessage({
                            'KonomiTV-OAuthPopup': $callback_data$
                        }, $target_origin$);
                    // (スマホ・タブレット) リダイレクト経由で OAuth 連携を行った場合
                    } else {
                        const callbackData = $callback_data$;
                        const redirectURL = new URL($redirect_to$);
                        redirectURL.hash = new URLSearchParams(callbackData).toString();
                        location.href = redirectURL.toString();
                    }
                };
            </script>
        </head>
        <body style="background: #1E1310; color: #FFEAEA;">
        </body>
        </html>
        """

        # JSON 化したコールバック情報と送信先をテンプレートへ埋め込む
        html = html.replace('$callback_data$', callback_data_json)
        html = html.replace('$target_origin$', target_origin_json)
        html = html.replace('$redirect_to$', redirect_to_json)

        # バイト列で返す必要があるらしい
        return html.encode('utf-8')
