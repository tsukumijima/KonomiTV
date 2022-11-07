
from fastapi.responses import HTMLResponse
from typing import Any, Dict


class OAuthCallbackResponse(HTMLResponse):
    """ OAuth 連携のコールバック時のレスポンス """

    def __init__(
        self,
        detail: str,
        status_code: int = 200,
        headers: Dict[str, Any] = {},
    ) -> None:
        """
        OAuth 連携のコールバック時のレスポンスを返す
        実際に出力されるのは HTML で、OAuth 連携が完了または失敗したことを KonomiTV クライアントに送信するための JavaScript が記述される

        Args:
            detail (str): KonomiTV クライアントに送信する詳細メッセージ
            status_code (int, optional): HTTP ステータスコード. Defaults to 200.
            headers (dict, optional): カスタムのヘッダー. Defaults to None.
        """
        self.status_code = status_code
        self.detail = detail
        self.background = None
        self.body = self.render()
        self.init_headers(headers)


    def render(self) -> bytes:

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
                    if (window.opener) {
                        window.opener.postMessage({
                            'KonomiTV-OAuthPopup': {
                                'status': $status$,
                                'detail': '$detail$',
                            }
                        }, '*');
                    }
                    // Android Chrome の PWA でリダイレクトが PWA アプリ (WebAPK) 側の Intent Filter に取られてしまい、
                    // postMessage() で送っても親ウインドウ側で受け取れない問題があるため、正しく送信できたかに関わらずポップアップを閉じる
                    // OAuth の連携結果を伝えることはできないが、サーバーでの連携処理はこのページが表示された時点で終わっているため問題ない
                    // ref: https://github.com/w3c/manifest/issues/989
                    setTimeout(() => window.close(), 100);  // postMessage() を確実に送信できるように少し遅らせてから実行
                };
            </script>
        </head>
        <body style="background:#1E1310;color:#FFEAEA;">
        </body>
        </html>
        """

        # ステータスコードと詳細メッセージを置換して入れる
        ## f-string も format() も中括弧のエスケープが必要で面倒なので、自前でやる
        html = html.replace('$status$', str(self.status_code))
        html = html.replace('$detail$', self.detail)

        # バイト列で返す必要があるらしい
        return html.encode('utf-8')
