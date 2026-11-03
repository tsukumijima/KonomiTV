
import asyncio
import ipaddress
import re
import socket
import time
from typing import Annotated

import httpx2 as httpx
from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from fastapi.responses import Response
from ping3 import ping

from app import logging, schemas
from app.constants import API_REQUEST_HEADERS


# ルーター
router = APIRouter(
    tags = ['Data Broadcasting'],
    prefix = '/api/data-broadcasting',
)

# 以下の API 実装は web-bml での実装を Python に移植したもの (with GPT-4)
# ref: https://github.com/tsukumijima/web-bml/blob/master/server/index.ts#L195-L296


async def ResolveHost(host: str, family: socket.AddressFamily = socket.AF_UNSPEC) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """
    ホスト名を名前解決し、得られたすべての IP アドレスを返す。
    IP アドレスが指定された場合は、その IP アドレスをそのまま返す。

    Args:
        host (str): ホスト名または IP アドレス
        family (socket.AddressFamily): 取得するアドレスファミリー (既定ではすべて)

    Returns:
        list[ipaddress.IPv4Address | ipaddress.IPv6Address]: 名前解決で得られた IP アドレスのリスト

    Raises:
        socket.gaierror: 名前解決に失敗した場合
    """

    # イベントループをブロックしないよう、イベントループの getaddrinfo() で名前解決する
    address_infos = await asyncio.get_running_loop().getaddrinfo(host, None, family=family, type=socket.SOCK_STREAM)
    return [ipaddress.ip_address(address_info[4][0]) for address_info in address_infos]


async def RejectNonGlobalDestination(request: httpx.Request) -> None:
    """
    データ放送ブラウザ向けのプロキシが送信するリクエストの送信先を検証する、httpx のリクエストのイベントフック。
    データ放送の双方向コンテンツの送信先は放送局のインターネット上のサーバーであるため、
    ループバック・プライベート・リンクローカルなど、インターネット上にないアドレスへのリクエストを拒否する。
    イベントフックはリダイレクト先へのリクエストでも呼び出されるため、リダイレクト先も同様に検証される。

    Args:
        request (httpx.Request): 送信するリクエスト

    Raises:
        HTTPException: 送信先がインターネット上にないアドレスに解決された場合
    """

    try:
        addresses = await ResolveHost(request.url.host)
    except socket.gaierror:
        # 名前解決に失敗した場合は、httpx の接続処理で発生する接続エラーとして扱う
        return

    # 名前解決で得られたアドレスが1つでもインターネット上にないアドレスであれば、リクエストを拒否する
    for address in addresses:
        if address.is_global is False:
            logging.error(f'[DataBroadcastingRouter][RejectNonGlobalDestination] Request URL must not point to a non-global address: {request.url} ({address})')
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail = 'Request URL must not point to a non-global address',
            )


@router.get(
    '/request/{request_url:path}',
    summary = 'データ放送ブラウザ HTTP (GET) リクエストプロキシ API',
    response_description = 'リクエスト URL に対する GET リクエストのレスポンス。',
)
async def BMLBrowserRequestGETProxyAPI(
    request_url: Annotated[str, Path(description='リクエスト URL 。')],
    request: Request,
):
    """
    データ放送ブラウザ (web-bml) のネット接続機能から利用される、HTTP (GET) プロキシ。<br>
    Web ブラウザからの HTTP リクエストには CORS の制限があるため、この API を経由してリクエストを送信する。<br>
    web-bml のネット接続機能専用の API で、web-bml 以外からは利用されない。
    """

    # URLが HTTP または HTTPS URL かのバリデーション
    if not (request_url.startswith("http://") or request_url.startswith("https://")):
        logging.error(f'[DataBroadcastingRouter][BMLBrowserRequestGETProxyAPI] Request URL must be http or https URL: {request_url}')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail = 'Request URL must be http or https URL',
        )

    # パスパラメータにはクエリ文字列が含まれないため、リクエスト URL のクエリ文字列を付け直す
    if request.url.query:
        request_url = f'{request_url}?{request.url.query}'

    logging.debug(f'Request URL: {request_url}')

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'ja',
        'Pragma': 'no-cache',
    }
    allowed_request_headers = ['if-modified-since', 'cache-control']
    for key, value in request.headers.items():
        if key.lower() in allowed_request_headers:
            headers[key] = value

    # タイムアウトはデータ放送の動作を壊さないようにあえて設定しない
    # さらにデータ放送からアクセスされるサイトは HTTPS の場合でも証明書が切れていることが日常茶飯事なので、証明書の検証を行わない
    ## 正確には放送波経由で古い規格の HTTPS 証明書が降ってきているらしいが、どのみち実装困難なので証明書の状態は無視する
    # 送信先 (リダイレクト先を含む) がインターネット上にないアドレスであれば、イベントフックでリクエストを拒否する
    async with httpx.AsyncClient(
        headers = {**API_REQUEST_HEADERS, **headers},
        follow_redirects = True,
        verify = False,
        event_hooks = {'request': [RejectNonGlobalDestination]},
    ) as client:
        try:
            response = await client.get(request_url)
        except HTTPException:
            # イベントフックで送信先が拒否された場合は、そのままエラーを返す
            raise
        except Exception as ex:
            # リクエスト中に例外が発生した場合は、エラーメッセージをログに出力して 500 エラーを返す
            ## HTTP リクエスト自体が DNS 名前解決エラーや接続エラーで失敗した場合に発生する
            logging.error('[DataBroadcastingRouter][BMLBrowserRequestGETProxyAPI] Failed to request:', exc_info=ex)
            raise HTTPException(
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail = f'Failed to request: {ex}',
            )

    allowed_response_headers = [
        'accept-ranges',
        'authentication-info',
        'last-modified',
        'pragma',
        'date',
        'cache-control',
        'age',
        'expire',
        'content-language',
        'content-location',
        'content-type',
    ]
    response_headers = {key: value for key, value in response.headers.items() if key.lower() in allowed_response_headers}

    # レスポンスボディは読み込み済みなので、ステータスコードとともにそのまま返す
    ## データ放送ブラウザはステータスコードを見てコンテンツの動作を分岐するため、送信先のステータスコードを維持する
    return Response(content=response.content, status_code=response.status_code, headers=response_headers)


@router.post(
    '/request/{request_url:path}',
    summary = 'データ放送ブラウザ HTTP (POST) リクエストプロキシ API',
    response_description = 'リクエスト URL に対する POST リクエストのレスポンス。',
    # リクエストボディはデコードせずにそのまま転送するため、FastAPI の Form() ではなく、API ドキュメント向けにスキーマだけを定義する
    openapi_extra = {
        'requestBody': {
            'content': {
                'application/x-www-form-urlencoded': {
                    'schema': {
                        'type': 'object',
                        'properties': {
                            'Denbun': {
                                'type': 'string',
                                'maxLength': 4096,
                                'description': 'データ放送ブラウザからのリクエストボディ (Denbun) 。パーセントエンコードされた状態で 4096 バイトまで。',
                            },
                        },
                    },
                },
            },
        },
    },
)
async def BMLBrowserRequestPOSTProxyAPI(
    request_url: Annotated[str, Path(description='リクエスト URL 。')],
    request: Request,
):
    """
    データ放送ブラウザ (web-bml) のネット接続機能から利用される、HTTP (POST) プロキシ。<br>
    Web ブラウザからの HTTP リクエストには CORS の制限があるため、この API を経由してリクエストを送信する。<br>
    web-bml のネット接続機能専用の API で、web-bml 以外からは利用されない。<br>
    Denbun は仕様書いわく「電文」のことらしく、データ放送ブラウザからの x-www-form-urlencoded 形式の値のキー名は Denbun で固定されている。<br>
    ARIB TR-B14 の規定により、リクエストボディは「Denbun=」と、EUC-JP (C プロファイルでは Shift_JIS) の文字列をパーセントエンコードした値だけで構成される。
    """

    # URLが HTTP または HTTPS URL かのバリデーション
    if not (request_url.startswith("http://") or request_url.startswith("https://")):
        logging.error(f'[DataBroadcastingRouter][BMLBrowserRequestPOSTProxyAPI] Request URL must be http or https URL: {request_url}')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail = 'Request URL must be http or https URL',
        )

    # リクエストボディが ARIB TR-B14 で規定された形式かのバリデーション
    ## Denbun の値の文字コードは送信元のコンテンツによって EUC-JP と Shift_JIS のどちらかになり、サーバー側では判別できない
    ## 値をデコードすると文字コードの解釈を誤って内容が壊れるため、リクエストボディはデコードせずにそのまま転送する
    ## 規定どおりにエンコードされたリクエストボディには、Denbun 以外のパラメータや、エンコードされていない & や = は含まれない
    body = await request.body()
    is_too_long = len(body) > len(b'Denbun=') + 4096
    is_denbun_format = re.fullmatch(rb"Denbun=(?:[A-Za-z0-9\-_.!~*'()+]|%[0-9A-Fa-f]{2})*", body) is not None
    if is_too_long is True or is_denbun_format is False:
        logging.error(f'[DataBroadcastingRouter][BMLBrowserRequestPOSTProxyAPI] Request body must be a percent-encoded Denbun parameter: {body!r}')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail = 'Request body must be a percent-encoded Denbun parameter',
        )

    # パスパラメータにはクエリ文字列が含まれないため、リクエスト URL のクエリ文字列を付け直す
    if request.url.query:
        request_url = f'{request_url}?{request.url.query}'

    logging.debug(f'Request URL: {request_url}')
    logging.debug(f'Request body: {body!r}')

    headers = {
        'Accept': '*/*',
        'Pragma': 'no-cache',
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    # タイムアウトはデータ放送の動作を壊さないようにあえて設定しない
    # さらにデータ放送からアクセスされるサイトは HTTPS の場合でも証明書が切れていることが日常茶飯事なので、証明書の検証を行わない
    ## 正確には放送波経由で古い規格の HTTPS 証明書が降ってきているらしいが、どのみち実装困難なので証明書の状態は無視する
    # 送信先 (リダイレクト先を含む) がインターネット上にないアドレスであれば、イベントフックでリクエストを拒否する
    async with httpx.AsyncClient(
        headers = {**API_REQUEST_HEADERS, **headers},
        follow_redirects = True,
        verify = False,
        event_hooks = {'request': [RejectNonGlobalDestination]},
    ) as client:
        try:
            response = await client.post(request_url, content=body)
        except HTTPException:
            # イベントフックで送信先が拒否された場合は、そのままエラーを返す
            raise
        except Exception as ex:
            # リクエスト中に例外が発生した場合は、エラーメッセージをログに出力して 500 エラーを返す
            ## HTTP リクエスト自体が DNS 名前解決エラーや接続エラーで失敗した場合に発生する
            logging.error('[DataBroadcastingRouter][BMLBrowserRequestPOSTProxyAPI] Failed to request:', exc_info=ex)
            raise HTTPException(
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail = f'Failed to request: {ex}',
            )

    allowed_response_headers = [
        'accept-ranges',
        'authentication-info',
        'last-modified',
        'pragma',
        'date',
        'cache-control',
        'age',
        'expire',
        'content-language',
        'content-location',
        'content-type',
    ]
    response_headers = {key: value for key, value in response.headers.items() if key.lower() in allowed_response_headers}

    # レスポンスボディは読み込み済みなので、ステータスコードとともにそのまま返す
    ## データ放送ブラウザはステータスコードを見てコンテンツの動作を分岐するため、送信先のステータスコードを維持する
    return Response(content=response.content, status_code=response.status_code, headers=response_headers)


@router.get(
    '/internet-status',
    summary = 'データ放送ブラウザネット接続状態確認 API',
    response_description = 'データ放送ブラウザ向けのネット接続状態。',
    response_model = schemas.DataBroadcastingInternetStatus,
)
async def BMLBrowserInternetStatusAPI(
    destination: Annotated[str, Query(description='接続先のホスト名または IP アドレス。')],
    is_icmp: Annotated[bool, Query(description='名前解決の代わりに ICMP (Ping) を使用するかどうか。')] = False,
    timeout_milliseconds: Annotated[int, Query(description='タイムアウト時間 (ミリ秒) 。')] = 3000,
):
    """
    データ放送ブラウザ (web-bml) のネット接続機能から利用される、ネット接続状態確認 API。<br>
    Web ブラウザからの HTTP リクエストには CORS の制限があるため、この API により KonomiTV サーバー側がネットに接続できるかが確認される。<br>
    web-bml のネット接続機能専用の API で、web-bml 以外からは利用されない。
    """

    # 接続先を IPv4 アドレスに名前解決し、名前解決にかかった時間を計測する
    ## ARIB STD-B24 第二編の confirmIPNetwork() では、ICMP を使用しない場合 (confirmType が 0) は、
    ## 名前解決を試行し、その成否で IP ネットワークへの接続の状態を確認すると規定されている
    start = time.time()
    try:
        addresses = await asyncio.wait_for(ResolveHost(destination, family=socket.AF_INET), timeout=timeout_milliseconds / 1000)
    except (socket.gaierror, TimeoutError):
        addresses = []
    resolve_time = time.time() - start

    # 名前解決に失敗した場合や、ループバック・プライベートなどインターネット上にないアドレスに解決された場合は、接続されていないとして返す
    ## データ放送の双方向コンテンツの接続先は放送局のインターネット上のサーバーであるため、LAN 内のアドレスへの接続状態は確認しない
    is_global_destination = len(addresses) > 0
    for address in addresses:
        if address.is_global is False:
            is_global_destination = False
    if is_global_destination is False:
        return schemas.DataBroadcastingInternetStatus(
            success = False,
            ip_address = None,
            response_time_milliseconds = None,
        )
    ip_address = str(addresses[0])

    # ICMP を使用する場合は ping3 ライブラリで ICMP パケットのレスポンス時間を取得
    ## ping3 の ping() は応答かタイムアウトまで処理をブロックするため、イベントループを止めないよう別スレッドで実行する
    if is_icmp is True:
        response_time = await asyncio.to_thread(ping, ip_address, timeout=int(timeout_milliseconds / 1000))
        success = response_time is not None

    # ICMP を使用しない場合は名前解決にかかった時間をレスポンス時間とする
    else:
        response_time = resolve_time
        success = True

    # ミリ秒単位のレスポンス時間
    response_time_milliseconds = int(response_time * 1000) if response_time is not None else None

    return schemas.DataBroadcastingInternetStatus(
        success = success,
        ip_address = ip_address if success else None,
        response_time_milliseconds = response_time_milliseconds,
    )
