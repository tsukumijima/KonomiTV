
from starlette._utils import create_collapsing_task_group
from starlette.responses import FileResponse
from starlette.types import Message, Receive, Scope, Send


class DisconnectAwareFileResponse(FileResponse):
    """
    mpeg2toh264 を利用したオリジナル画質での録画再生時にシークを繰り返すと、
    切断済みのリクエストによる読み出しが残り、シークが遅くなる問題への対策

    Starlette 1.6.0 の FileResponse は http.disconnect を監視せず、Uvicorn 0.52.4 は切断後の send() を正常終了させるため、
    ブラウザが取得を中止しても指定範囲の末尾までファイルを読み続けてしまう
    Range の解析や配信処理は Starlette に任せ、切断を検出した後の送信時に例外で読み出しを終了させる
    通常の例外でファイルのコンテキストを抜けるため、キャンセルによって非同期のクローズまで中断される問題も回避できる
    Starlette の更新時には上流の対応状況を確認し、切断時の読み出し停止が実装されたら標準の FileResponse へ戻す

    ref: https://github.com/tsukumijima/KonomiTV/issues/279
    ref: https://github.com/Kludex/starlette/pull/3390
    ref: https://github.com/libratechw/starlette/commit/17e3955f997c2f271a08057fe649abadcc482f77
    """

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        ファイルを配信し、接続が切れた場合は次の送信時に読み出しを終了する。

        Args:
            scope (Scope): ASGI リクエストの情報
            receive (Receive): リクエストや切断通知を受け取る関数
            send (Send): レスポンスを送信する関数

        Returns:
            None: 配信または切断後の後処理が完了した時点で終了
        """

        # ASGI 2.4 以降ではサーバーが切断後の送信を例外にするため、標準の処理を利用する
        # HEAD とサーバーへファイル送信を委譲する経路、および HTTP 以外の応答も標準の処理に任せる
        spec_version = tuple(map(int, scope.get('asgi', {}).get('spec_version', '2.0').split('.')))
        if (scope['type'] != 'http' or scope['method'].upper() == 'HEAD' or spec_version >= (2, 4)
            or ('http.response.pathsend' in scope.get('extensions', {}) and b'range' not in dict(scope['headers']))):
            await super().__call__(scope, receive, send)
            return

        class ClientDisconnected(Exception):
            """ ファイルのクローズを実行しながら配信処理を抜けるための内部例外。 """

        is_disconnected = False
        is_interrupted = False

        async def ListenForDisconnect() -> None:
            """
            接続の切断通知を受け取り、送信処理へ通知する。

            Returns:
                None: 切断通知を受け取った時点で終了
            """

            nonlocal is_disconnected
            # リクエスト本文の通知を読み進め、接続が切れた時点で監視を終了する
            while True:
                if (await receive())['type'] == 'http.disconnect':
                    is_disconnected = True
                    return

        async def SendWithDisconnectCheck(message: Message) -> None:
            """
            切断済みなら配信を終了し、接続中ならレスポンスを送信する。

            Args:
                message (Message): Starlette が生成したレスポンスメッセージ

            Returns:
                None: メッセージの送信が完了した時点で終了
            """

            # 読み出しタスク自体はキャンセルせず、Starlette の async with にファイルを閉じさせる
            if is_disconnected is True:
                raise ClientDisconnected
            await send(message)

        # 監視と配信を並行させ、配信終了時には待機中の監視も終了する
        # タスクグループによる例外の包装を解き、標準の FileResponse と同じ例外を呼び出し元へ返す
        async with create_collapsing_task_group() as task_group:
            task_group.start_soon(ListenForDisconnect)
            try:
                await super().__call__(scope, receive, SendWithDisconnectCheck)
            except ClientDisconnected:
                is_interrupted = True
            finally:
                task_group.cancel_scope.cancel()

        # 切断で中断した場合も、ファイルのクローズが終わってからバックグラウンド処理を実行する
        # 正常終了時は親クラスが実行済みなので、ここでは切断による中断時だけ補う
        if is_interrupted is True and self.background is not None:
            await self.background()
