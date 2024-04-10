
from fastapi.responses import HTMLResponse
from typing import Any


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
                            'KonomiTV-OAuthPopup': {
                                'status': $status$,
                                'detail': '$detail$',
                            }
                        }, '*');
                    // (スマホ・タブレット) リダイレクト経由で OAuth 連携を行った場合
                    } else {
                        location.href = `$redirect_to$#status=$status$&detail=${encodeURIComponent('$detail$')}`;
                    }
                };
            </script>
        </head>
        <body style="background: #1E1310; color: #FFEAEA;">
        </body>
        </html>
        """

        # ステータスコードと詳細メッセージを置換して入れる
        ## f-string も format() も中括弧のエスケープが必要で面倒なので、自前でやる
        html = html.replace('$status$', str(self.status_code))
        html = html.replace('$detail$', self.detail)
        html = html.replace('$redirect_to$', self.redirect_to)

        # バイト列で返す必要があるらしい
        return html.encode('utf-8')
