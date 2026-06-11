
from __future__ import annotations

import asyncio
import io
import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, ClassVar, Final, TypeVar, cast, get_args

from atproto import (
    AsyncClient,
    AsyncRequest,
    Session,
    SessionEvent,
    client_utils,
    models,
)
from atproto_client.exceptions import (
    InvokeTimeoutError,
    NetworkError,
    UnauthorizedError,
)
from atproto_client.namespaces import async_ns
from atproto_client.request import Response
from fastapi import HTTPException, UploadFile
from httpx import Timeout
from PIL import Image
from pydantic import BaseModel
from typing_extensions import TypedDict

from app import logging, schemas
from app.constants import JST
from app.models.BlueskyAccount import BlueskyAccount


_RetriableResultT = TypeVar('_RetriableResultT')


def _CollectSDKUnionTypeTags(annotation: Any) -> set[str]:
    """
    atproto SDK の Pydantic Union 型から discriminator 用の $type を収集する

    Args:
        annotation (Any): Pydantic モデルフィールドの型注釈

    Returns:
        set[str]: SDK が現在受け入れられる $type の集合
    """

    supported_type_tags: set[str] = set()

    # atproto SDK は Lexicon の $type を py_type フィールドの default として保持している
    ## 依存バージョンは固定しているため、この構造を SDK 側の信頼できる型定義として扱う
    if isinstance(annotation, type) is True and issubclass(annotation, BaseModel) is True:
        py_type_field = annotation.model_fields.get('py_type')
        if py_type_field is not None and isinstance(py_type_field.default, str) is True:
            supported_type_tags.add(py_type_field.default)
        return supported_type_tags

    # Optional / Annotated / Union の入れ子を再帰的に辿り、実際の Pydantic モデルだけを拾う
    for child_annotation in get_args(annotation):
        supported_type_tags.update(_CollectSDKUnionTypeTags(child_annotation))

    return supported_type_tags


def _CollectRequiredSDKUnionTypeTags(field_name: str, annotation: Any) -> set[str]:
    """
    固定した atproto SDK から必須 Union タグを収集する

    Args:
        field_name (str): 起動時エラーに含める SDK フィールド名
        annotation (Any): Pydantic モデルフィールドの型注釈

    Returns:
        set[str]: SDK が現在受け入れられる $type の集合
    """

    supported_type_tags = _CollectSDKUnionTypeTags(annotation)

    # 依存バージョンを固定しているため、ここで空になる場合は SDK の型構造を読めていない
    ## そのまま起動すると既知 embed まで未知扱いになるため、原因が分かる形で起動時に止める
    if len(supported_type_tags) == 0:
        raise RuntimeError(f'Failed to collect atproto SDK union type tags. field: {field_name}')

    return supported_type_tags


_ATPROTO_SUPPORTED_MAIN_EMBED_TYPES: Final[set[str]] = _CollectRequiredSDKUnionTypeTags(
    'AppBskyFeedPost.Record.embed',
    models.AppBskyFeedPost.Record.model_fields['embed'].annotation,
)
_ATPROTO_SUPPORTED_VIEW_EMBED_TYPES: Final[set[str]] = _CollectRequiredSDKUnionTypeTags(
    'AppBskyFeedDefs.PostView.embed',
    models.AppBskyFeedDefs.PostView.model_fields['embed'].annotation,
)
_ATPROTO_SUPPORTED_FEED_REASON_TYPES: Final[set[str]] = _CollectRequiredSDKUnionTypeTags(
    'AppBskyFeedDefs.FeedViewPost.reason',
    models.AppBskyFeedDefs.FeedViewPost.model_fields['reason'].annotation,
)


def _NormalizeUnknownEmbedForSDK(embed: dict[str, Any], *, is_view_embed: bool | None = None) -> None:
    """
    SDK 未対応の Bluesky embed だけをメディアなし embed へ正規化する

    Args:
        embed (dict[str, Any]): raw レスポンス上の embed オブジェクト
        is_view_embed (bool | None): view 側 embed として扱うかどうか (None なら $type から推定)
    """

    embed_type = embed.get('$type')
    if isinstance(embed_type, str) is False:
        return

    # recordWithMedia は media 内に別の embed Union を持つため、外側を保ったまま内側だけを処理する
    if embed_type in ('app.bsky.embed.recordWithMedia', 'app.bsky.embed.recordWithMedia#view'):
        media = embed.get('media')
        if isinstance(media, dict) is True:
            _NormalizeUnknownEmbedForSDK(
                cast(dict[str, Any], media),
                is_view_embed = embed_type.endswith('#view'),
            )
        return

    # SDK がすでに知っている型は、将来の追加フィールドを含んでいてもそのまま SDK に渡す
    if embed_type in _ATPROTO_SUPPORTED_MAIN_EMBED_TYPES or embed_type in _ATPROTO_SUPPORTED_VIEW_EMBED_TYPES:
        return

    unsupported_embed_type = cast(str, embed_type)
    should_treat_as_view_embed = is_view_embed if is_view_embed is not None else unsupported_embed_type.endswith('#view')

    # 未知 embed は投稿本文まで巻き込んで落ちるため、既知の空画像 embed として扱う
    ## 本文・投稿者・リアクション数は残し、KonomiTV が解釈できないメディアだけを捨てる
    embed.clear()
    if should_treat_as_view_embed is True:
        embed.update({'$type': 'app.bsky.embed.images#view', 'images': []})
    else:
        embed.update({'$type': 'app.bsky.embed.images', 'images': []})


def _NormalizeUnknownSchemaForSDK(value: Any) -> None:
    """
    API レスポンス内の SDK 未対応 Union 要素を再帰的に正規化する

    Args:
        value (Any): API レスポンス内の任意の値
    """

    # SDK が closed union で落ちる既知フィールドだけを触り、通常の拡張フィールドはそのまま残す
    if isinstance(value, dict) is True:
        value_dict = cast(dict[str, Any], value)

        embed = value_dict.get('embed')
        if isinstance(embed, dict) is True:
            _NormalizeUnknownEmbedForSDK(
                cast(dict[str, Any], embed),
                is_view_embed = value_dict.get('$type') != 'app.bsky.feed.post',
            )

        # quoted post の ViewRecord.embeds は view 側 embed の配列なので、未知要素だけをメディアなしにする
        embeds = value_dict.get('embeds')
        if isinstance(embeds, list) is True:
            for embed_value in cast(list[Any], embeds):
                if isinstance(embed_value, dict) is True:
                    _NormalizeUnknownEmbedForSDK(cast(dict[str, Any], embed_value), is_view_embed = True)

        # 未知の reason は表示理由が分からないだけなので、投稿自体を残すために理由なしとして扱う
        reason = value_dict.get('reason')
        if isinstance(reason, dict) is True:
            reason_type = cast(dict[str, Any], reason).get('$type')
            if isinstance(reason_type, str) is True and reason_type not in _ATPROTO_SUPPORTED_FEED_REASON_TYPES:
                value_dict.pop('reason')

        for child_value in value_dict.values():
            _NormalizeUnknownSchemaForSDK(child_value)
        return

    if isinstance(value, list) is True:
        for child_value in cast(list[Any], value):
            _NormalizeUnknownSchemaForSDK(child_value)


def _PatchAtprotoUnknownSchemaResponseModel() -> None:
    """
    atproto SDK のレスポンスモデル化直前に未対応 Union 要素だけを読み飛ばす
    """

    original_get_response_model = async_ns.get_response_model
    if getattr(original_get_response_model, '_konomitv_unknown_schema_patch', False) is True:
        return

    def GetResponseModelWithUnknownSchemaPatch(response: Response, model: type[Any]) -> Any:
        """
        未対応 Union 要素をメディアなし・理由なしへ変換してからレスポンスモデルへ変換する

        Args:
            response (Response): atproto SDK の raw レスポンス
            model (type[Any]): 変換先の SDK レスポンスモデル

        Returns:
            Any: SDK が返すレスポンスモデル
        """

        _NormalizeUnknownSchemaForSDK(response.content)
        return original_get_response_model(response, model)

    setattr(GetResponseModelWithUnknownSchemaPatch, '_konomitv_unknown_schema_patch', True)
    async_ns.get_response_model = GetResponseModelWithUnknownSchemaPatch


class BlueskyReplyReference(TypedDict):
    """Bluesky のリプライ先参照情報"""

    root_uri: str
    root_cid: str
    parent_uri: str
    parent_cid: str


class BlueskyAPI:
    """
    Bluesky の AT Protocol API を扱うクライアント
    """

    # Bluesky の画像 embed で許可される画像枚数
    MAX_IMAGE_COUNT: Final[int] = 4
    # app.bsky.embed.images の blob 上限
    MAX_IMAGE_BYTES: Final[int] = 2_000_000
    # atproto SDK の既定タイムアウトは短めなので、画像アップロードや混雑時の PDS 応答を待てる値に広げる
    REQUEST_TIMEOUT: ClassVar[Timeout] = Timeout(timeout=30.0, connect=10.0)
    # Bluesky 側の一時的な遅延を吸収するため、読み書きタイムアウトと 502 応答だけを短く再試行する
    API_RETRY_ATTEMPTS: Final[int] = 3
    API_RETRY_BASE_DELAY_SECONDS: Final[float] = 0.8
    # Bluesky アカウント ID ごとのシングルトンインスタンスを管理する辞書
    ## 同じセッション情報を複数の SDK クライアントへ復元すると、更新トークンの更新処理がクライアントごとに独立してしまう
    ## SDK クライアントを共有し、SDK 内部の更新ロックと HTTP 接続プールをアカウント単位で使い回す
    __instances: ClassVar[dict[int, BlueskyAPI]] = {}


    def __new__(cls, bluesky_account: BlueskyAccount) -> BlueskyAPI:
        """
        Bluesky アカウント ID ごとのシングルトンインスタンスを取得する

        Args:
            bluesky_account (BlueskyAccount): API 操作に利用する Bluesky アカウント

        Returns:
            BlueskyAPI: 対象アカウントの共有 API クライアント
        """

        # インスタンス生成中に await しないため、同一イベントループ上では辞書操作だけで重複生成を避けられる
        instance = cls.__instances.get(bluesky_account.id)
        if instance is None:
            instance = super().__new__(cls)

            # セッション更新時に session_string を保存し直すため、ORM インスタンス自体を保持する
            instance.bluesky_account = bluesky_account
            # SDK クライアントをアカウント単位で使い回し、HTTP 接続プールと SDK 内部の更新ロックを共有する
            instance.client = AsyncClient(request=AsyncRequest(timeout=cls.REQUEST_TIMEOUT))
            # セッション更新通知の登録状態
            ## `_login()` はセッションの初回復元時だけ呼ばれるが、再試行時にも同じコールバックを重複登録しないよう保持する
            instance.is_session_change_handler_registered = False
            # 保存済みのセッション情報を SDK クライアントへ復元済みかどうか
            instance.is_session_restored = False
            # 同じアカウントへの初回リクエストが重なった場合も、セッション復元は 1 回だけ実行する
            instance._session_initialization_lock = asyncio.Lock()

            cls.__instances[bluesky_account.id] = instance
        else:
            # DB から取得した新しい ORM インスタンスへ差し替え、セッション更新時の保存先を最新状態にする
            instance.bluesky_account = bluesky_account

        return instance

    def __init__(self, bluesky_account: BlueskyAccount) -> None:
        """
        Bluesky API クライアントのインスタンス変数に型ヒントを付与する

        Args:
            bluesky_account (BlueskyAccount): API 操作に利用する Bluesky アカウント
        """

        # シングルトンの実体は __new__() で初期化する
        ## __init__() は取得のたびに呼ばれるため、ここで値を再代入すると共有中の SDK クライアントが失われる
        self.bluesky_account: BlueskyAccount
        self.client: AsyncClient
        self.is_session_change_handler_registered: bool
        self.is_session_restored: bool
        self._session_initialization_lock: asyncio.Lock


    @property
    def log_prefix(self) -> str:
        """
        ログ出力時にアカウントを識別する接頭辞を返す

        Returns:
            str: ログ出力用の接頭辞
        """

        return f'[BlueskyAPI][{self.bluesky_account.handle}]'


    @classmethod
    async def removeInstance(cls, bluesky_account_id: int) -> None:
        """
        指定された Bluesky アカウント ID の共有 API クライアントを破棄する

        Args:
            bluesky_account_id (int): 破棄する Bluesky アカウントの ID
        """

        # 辞書から先に取り除き、再連携直後のリクエストでは新しいセッション情報からクライアントを作り直す
        ## HTTP クライアントの終了中に新しいリクエストが来ても、破棄対象のクライアントを再利用させない
        instance = cls.__instances.pop(bluesky_account_id, None)
        if instance is None:
            return

        try:
            await instance.client.request.close()
        except Exception as ex:
            # クライアントの破棄に失敗しても、再連携や連携解除は継続する
            logging.error(f'[BlueskyAPI] Failed to close client. [account_id: {bluesky_account_id}]', exc_info=ex)

    @staticmethod
    async def authenticate(handle: str, app_password: str) -> BlueskyAccount:
        """
        App Password で Bluesky にログインし、BlueskyAccount ORM インスタンスを返す

        Args:
            handle (str): Bluesky の handle
            app_password (str): Bluesky の App Password

        Returns:
            BlueskyAccount: ログイン結果から作成した未保存の BlueskyAccount ORM インスタンス
        """

        normalized_handle = BlueskyAPI.normalizeBlueskyHandle(handle)
        client = AsyncClient(request=AsyncRequest(timeout=BlueskyAPI.REQUEST_TIMEOUT))
        # App Password は保存せず、ログイン成功後に SDK の session_string だけを暗号化して保持する
        try:
            profile = await client.login(normalized_handle, app_password)
            session_string = client.export_session_string()
        finally:
            # 認証画面用のクライアントは共有しないため、利用後に HTTP 接続プールを閉じる
            await client.request.close()

        # profile.handle は DID 解決後の正規 handle なので、ユーザー入力ではなく API 応答値を DB に保存する
        account = BlueskyAccount(
            did=profile.did,
            handle=profile.handle,
            name=profile.display_name or profile.handle,
            icon_url=profile.avatar or '',
            session_string='',
        )
        account.session_string = account.encryptSessionString(session_string)
        return account


    def _isRetriableBlueskyError(self, ex: Exception) -> bool:
        """
        Bluesky API 呼び出しを再試行してよい一時的な例外かを判定する

        Args:
            ex (Exception): 判定する例外

        Returns:
            bool: 一時的な通信失敗として再試行してよい場合は True
        """

        # HTTPX の読み書きタイムアウトは atproto SDK で InvokeTimeoutError に丸められるため、操作単位で短く再試行する
        if isinstance(ex, InvokeTimeoutError) is True:
            return True

        if isinstance(ex, NetworkError) is False:
            return False

        network_error = cast(NetworkError, ex)

        # SDK は 413 も NetworkError として扱うが、blob サイズ超過は再試行しても解消しない
        # レスポンス情報がない NetworkError は接続断などの通信失敗なので、タイムアウトと同じ一時失敗として扱う
        if network_error.response is None:
            return True

        return network_error.response.status_code in {502}


    async def _invokeWithRetry(
        self,
        operation_name: str,
        operation: Callable[[], Awaitable[_RetriableResultT]],
    ) -> _RetriableResultT:
        """
        Bluesky API 呼び出しを一時的な通信失敗に限って再試行する

        Args:
            operation_name (str): ログに出力する操作名
            operation (Callable[[], Awaitable[_RetriableResultT]]): 実行する非同期 API 呼び出し

        Returns:
            _RetriableResultT: API 呼び出しの戻り値
        """

        for attempt_number in range(1, self.API_RETRY_ATTEMPTS + 1):
            try:
                return await operation()
            except Exception as ex:
                is_retriable_error = self._isRetriableBlueskyError(ex)
                is_last_attempt = attempt_number >= self.API_RETRY_ATTEMPTS

                # 投稿作成そのもののような重複実行の実害がある呼び出しでは使わず、再試行しても状態が壊れにくい操作だけを渡す
                if is_retriable_error is False or is_last_attempt is True:
                    raise

                retry_delay_seconds = self.API_RETRY_BASE_DELAY_SECONDS * attempt_number
                logging.warning(
                    f'{self.log_prefix} Retrying Bluesky API operation after transient error. '
                    f'[operation: {operation_name}, attempt: {attempt_number}/{self.API_RETRY_ATTEMPTS}, '
                    f'retry_delay: {retry_delay_seconds:.1f}s]',
                    exc_info=ex,
                )
                await asyncio.sleep(retry_delay_seconds)

        # for ループ内で必ず return か raise されるが、型チェッカーに制御フローを明示する
        raise RuntimeError(f'Bluesky API retry loop unexpectedly finished. [operation: {operation_name}]')


    async def _login(self) -> None:
        """
        暗号化保存されている session_string から atproto SDK のセッションを復元する
        """

        async def on_session_change(event: SessionEvent, session: Session) -> None:
            # refresh 後の session_string は古い refresh token を置き換えるため、DB に保存し直す必要がある
            if event not in (SessionEvent.CREATE, SessionEvent.REFRESH):
                return
            # SDK から通知された時点のセッション情報を保存し、共有クライアントの後続処理による状態変化を持ち込まない
            session_string = session.export()
            self.bluesky_account.session_string = self.bluesky_account.encryptSessionString(session_string)
            await self.bluesky_account.save()
            logging.info(f'{self.log_prefix} Bluesky session string updated.')

        # atproto SDK のセッション更新通知は追加登録型なので、再試行時に登録すると保存処理が重複する
        ## 通知ハンドラーは共有 SDK クライアントに 1 回だけ紐づける
        if self.is_session_change_handler_registered is False:
            self.client.on_session_change(on_session_change)
            self.is_session_change_handler_registered = True

        # 保存済みの session_string を共有 SDK クライアントへ復元し、以降のアクセストークン更新を SDK 側に任せる
        await self._invokeWithRetry(
            'restore_session',
            lambda: self.client.login(session_string=self.bluesky_account.decryptSessionString()),
        )


    async def _restoreSession(self) -> schemas.TwitterAPIResult | None:
        """
        API 操作前に Bluesky セッションを復元する

        Returns:
            schemas.TwitterAPIResult | None: 復元失敗時の API 結果 (成功時は None)
        """

        # 共有 SDK クライアントへセッションを復元済みなら、各 API 操作をそのまま並行実行する
        ## アクセストークン更新の競合は SDK 内部の更新ロックで処理される
        if self.is_session_restored is True:
            return None

        # 同じアカウントへの初回リクエストが重なった場合も、セッション復元とプロフィール取得は 1 回だけ実行する
        async with self._session_initialization_lock:
            # ロック待機中に別のリクエストが復元を完了していた場合は、その共有クライアントを利用する
            if self.is_session_restored is True:
                return None

            try:
                await self._login()
            except (HTTPException, UnauthorizedError) as ex:
                # 復号不能な session_string と PDS 側の認証拒否は、どちらもユーザーの再連携で解消する状態
                ## 通信障害や SDK 側の不具合まで再連携扱いにすると、実際には不要なアカウント再設定を促してしまう
                logging.error(f'{self.log_prefix} Failed to restore Bluesky session due to authorization error:', exc_info=ex)
                return schemas.TwitterAPIResult(
                    is_success=False,
                    detail='Bluesky のセッションが期限切れです。設定画面から再連携してください。',
                )
            except Exception as ex:
                logging.error(f'{self.log_prefix} Failed to restore Bluesky session:', exc_info=ex)
                return schemas.TwitterAPIResult(
                    is_success=False,
                    detail='Bluesky との通信エラーまたは内部エラーが発生しました。後でもう一度お試しください。',
                )

            self.is_session_restored = True
        return None


    async def _fetchPostByURI(self, post_uri: str) -> models.AppBskyFeedDefs.PostView | None:
        """
        AT URI から Bluesky 投稿情報を取得する

        Args:
            post_uri (str): 対象投稿の AT URI

        Returns:
            models.AppBskyFeedDefs.PostView | None: 取得できた投稿情報
        """

        # API パスから受け取る ID は AT URI そのものなので、不正な文字列は Bluesky API に渡す前に弾く
        if post_uri.startswith('at://') is False:
            return None

        # リポスト / いいね作成には CID が必要で、取り消しには viewer.repost / viewer.like が必要になる
        post_response = await self._invokeWithRetry(
            'get_posts',
            lambda: self.client.app.bsky.feed.get_posts(
                models.AppBskyFeedGetPosts.Params(uris=[post_uri]),
            ),
        )
        if len(post_response.posts) == 0:
            return None
        return post_response.posts[0]


    async def _prepareAndUploadImage(self, image: UploadFile) -> models.AppBskyEmbedImages.Image:
        """
        アップロードされた 1 枚の画像を Bluesky の画像 embed 要素へ変換する

        Args:
            image (UploadFile): 添付画像

        Returns:
            models.AppBskyEmbedImages.Image: Bluesky の画像 embed 要素
        """

        def ConvertLargeImageToWebP(image_bytes: bytes) -> bytes:
            """
            2MB を超える画像を WebP に変換し、必要に応じて長辺を縮小する

            Args:
                image_bytes (bytes): 変換前の画像データ

            Returns:
                bytes: Bluesky にアップロード可能な WebP 画像データ
            """

            with Image.open(io.BytesIO(image_bytes)) as image:
                # アルファチャンネル付き画像も WebP に保存できるよう RGBA に寄せる
                if image.mode not in ('RGB', 'RGBA'):
                    image = image.convert('RGBA')

                # 1 ループ目は元解像度のまま quality だけ 85 → 50 と段階的に下げて 2MB 以下を狙う
                # それでも収まらない場合は長辺を 1920 → 1600 → 1280 → 1024 → 800 と段階的に縮めて再試行する
                # 画質より解像度の維持を優先するための順序
                original_image = image.copy()
                original_long_edge = max(original_image.width, original_image.height)
                for max_long_edge in [original_long_edge, 1920, 1600, 1280, 1024, 800]:
                    working_image = original_image
                    current_long_edge = max(working_image.width, working_image.height)
                    # 現在の試行サイズより大きい画像だけを縮小し、小さい画像を拡大して画質を落とさない
                    if current_long_edge > max_long_edge:
                        resize_ratio = max_long_edge / current_long_edge
                        resized_width = max(1, int(working_image.width * resize_ratio))
                        resized_height = max(1, int(working_image.height * resize_ratio))
                        working_image = working_image.resize((resized_width, resized_height), Image.Resampling.LANCZOS)

                    for quality in [85, 80, 70, 60, 50]:
                        output_buffer = io.BytesIO()
                        working_image.save(output_buffer, format='WEBP', quality=quality, method=6)
                        converted_bytes = output_buffer.getvalue()
                        # 2MB 以下になった最初の組み合わせを採用し、必要以上の画質低下や縮小を避ける
                        if len(converted_bytes) <= self.MAX_IMAGE_BYTES:
                            return converted_bytes

            raise ValueError('Image size exceeds the Bluesky limit after WebP conversion.')

        def GetImageSize(image_bytes: bytes) -> tuple[int, int]:
            """
            画像データから Bluesky の表示比率に使う幅と高さを取得する

            Args:
                image_bytes (bytes): Bluesky にアップロードする最終的な画像データ

            Returns:
                tuple[int, int]: 画像の幅と高さ
            """

            with Image.open(io.BytesIO(image_bytes)) as image:
                return image.width, image.height

        # UploadFile は非同期に読み出し、サイズだけで分かる変換要否は Pillow を呼ぶ前に判定する
        image_bytes = await image.read()
        # Bluesky の blob 上限を超える場合だけ WebP 変換を試し、通常のキャプチャは元の JPEG をそのままアップロードする
        if len(image_bytes) > self.MAX_IMAGE_BYTES:
            image_bytes = await asyncio.to_thread(ConvertLargeImageToWebP, image_bytes)

        if len(image_bytes) > self.MAX_IMAGE_BYTES:
            raise ValueError('Image size exceeds the Bluesky limit.')

        # Bluesky クライアントは投稿レコード上の aspectRatio を表示枠のヒントとして使うため、
        # blob 参照だけでなく最終的な画像データの縦横比も明示する
        image_width, image_height = await asyncio.to_thread(GetImageSize, image_bytes)

        # atproto の画像 embed には先に blob をアップロードし、その参照を Image として詰める
        upload_response = await self._invokeWithRetry(
            'upload_blob',
            lambda: self.client.upload_blob(image_bytes),
        )
        return models.AppBskyEmbedImages.Image(
            alt='',
            image=upload_response.blob,
            aspect_ratio=models.AppBskyEmbedDefs.AspectRatio(
                width=image_width,
                height=image_height,
            ),
        )


    def _formatPostView(self, post: models.AppBskyFeedDefs.PostView, reason: Any | None = None) -> schemas.Tweet:
        """
        Bluesky の PostView を KonomiTV 共通の Tweet スキーマへ変換する

        Args:
            post (models.AppBskyFeedDefs.PostView): Bluesky の投稿情報
            reason (Any | None, optional): リポストなどの表示理由

        Returns:
            schemas.Tweet: KonomiTV 共通の Tweet スキーマ
        """

        # post.record は atproto SDK 上は複数 lexicon のレコードを取りうる Union 型のため、
        # isinstance でナローイングしてから本文と投稿日時にアクセスする
        # Bluesky のフィード投稿は実態として常に app.bsky.feed.post レコードのはずだが、SDK の型上は保証されない
        record = post.record
        if isinstance(record, models.AppBskyFeedPost.Record):
            text = self._expandFacetLinksInText(record.text, record.facets)
            created_at_text = record.created_at
        else:
            text = ''
            created_at_text = post.indexed_at

        # KonomiTV の Tweet スキーマでは画像 URL はサムネイル URL の配列として扱う
        # Bluesky の画像以外の embed は現時点では共通 UI に載せない
        image_urls: list[str] = []
        embed = post.embed
        if isinstance(embed, models.AppBskyEmbedImages.View):
            image_urls = [image.thumb for image in embed.images]
        elif isinstance(embed, models.AppBskyEmbedGallery.View):
            # gallery embed は現行 Lexicon 上すべて画像項目なので、表示用サムネイル URL をそのまま拾う
            image_urls = [item.thumbnail for item in embed.items]

        # 以降の UI は Twitter と同じ TweetUser を参照するため、DID と handle を共通フィールドへ詰め替える
        tweet_user = schemas.TweetUser(
            source='Bluesky',
            id=post.author.did,
            name=post.author.display_name or post.author.handle,
            screen_name=post.author.handle,
            icon_url=post.author.avatar or '',
        )

        tweet = schemas.Tweet(
            source='Bluesky',
            id=post.uri,
            created_at=self._parseDateTime(created_at_text),
            user=tweet_user,
            text=text,
            lang='',
            via='',
            image_urls=image_urls if len(image_urls) > 0 else None,
            movie_url=None,
            retweet_count=post.repost_count or 0,
            favorite_count=post.like_count or 0,
            retweeted=post.viewer is not None and post.viewer.repost is not None,
            favorited=post.viewer is not None and post.viewer.like is not None,
            retweeted_tweet=None,
            quoted_tweet=None,
        )

        # Bluesky のリポストは Twitter の RT セマンティクスに合わせて、
        # リポストした人を投稿者として表示しつつ元の投稿を retweeted_tweet にネストする
        # reason は app.bsky.feed.defs#feedViewPost の reason フィールドで、リポスト経由のフィード項目に ReasonRepost が入る
        if isinstance(reason, models.AppBskyFeedDefs.ReasonRepost):
            repost_user = reason.by
            repost_tweet_user = schemas.TweetUser(
                source='Bluesky',
                id=repost_user.did,
                name=repost_user.display_name or repost_user.handle,
                screen_name=repost_user.handle,
                icon_url=repost_user.avatar or '',
            )
            tweet = tweet.model_copy(update={
                'user': repost_tweet_user,
                'retweeted_tweet': tweet.model_copy(),
            })

        return tweet


    async def createPost(
        self,
        text: str,
        images: list[UploadFile],
        reply_to: BlueskyReplyReference | None = None,
    ) -> schemas.PostTweetResult | schemas.TwitterAPIResult:
        """
        Bluesky にポストを送信する

        Args:
            text (str): 投稿本文
            images (list[UploadFile]): 添付画像
            reply_to (BlueskyReplyReference | None): リプライ先情報 (None の場合は単独ポスト)

        Returns:
            schemas.PostTweetResult | schemas.TwitterAPIResult: 投稿結果
        """

        # Bluesky の画像 embed は最大 4 枚なので、アップロード処理に入る前に KonomiTV 側で明示的に拒否する
        if len(images) > self.MAX_IMAGE_COUNT:
            return schemas.TwitterAPIResult(
                is_success=False,
                detail='Bluesky では画像は 4 枚まで添付できます。',
            )

        session_error = await self._restoreSession()
        if session_error is not None:
            return session_error

        try:
            # 画像 embed と facets 付き本文を組み立ててから投稿し、Bluesky 上で URL / ハッシュタグがリンク化されるようにする
            embed: models.AppBskyEmbedImages.Main | None = None
            if len(images) > 0:
                # 画像ごとの読み込み・必要時の再エンコード・blob アップロードは互いに独立しているため、
                # 投稿前に同時に進めて 4 枚添付時の待ち時間が単純加算されないようにする
                embed_images = await asyncio.gather(*[
                    self._prepareAndUploadImage(image)
                    for image in images
                ])
                embed = models.AppBskyEmbedImages.Main(images=embed_images)

            reply_ref: models.AppBskyFeedPost.ReplyRef | None = None
            if reply_to is not None:
                # Bluesky のリプライはツリー全体のルートと直前の親ポストの両方を要求する
                # フロント側の状態は送信成功レスポンスの uri / cid だけで更新し、削除済み親への失敗時は状態を触らない
                reply_ref = models.AppBskyFeedPost.ReplyRef(
                    root=models.ComAtprotoRepoStrongRef.Main(
                        uri=reply_to['root_uri'],
                        cid=reply_to['root_cid'],
                    ),
                    parent=models.ComAtprotoRepoStrongRef.Main(
                        uri=reply_to['parent_uri'],
                        cid=reply_to['parent_cid'],
                    ),
                )

            post_response = await self.client.send_post(
                text=self._buildTextBuilder(text),
                embed=embed,
                langs=['ja'],
                reply_to=reply_ref,
            )
        except Exception as ex:
            logging.error(f'{self.log_prefix} Failed to create post:', exc_info=ex)
            return schemas.TwitterAPIResult(
                is_success=False,
                detail='Bluesky へのポストに失敗しました。',
            )

        # 投稿完了通知から直接開けるよう、AT URI の record key を bsky.app の URL へ変換する
        post_url = f'https://bsky.app/profile/{self.bluesky_account.handle}/post/{self._extractRecordKey(post_response.uri)}'
        return schemas.PostTweetResult(
            is_success=True,
            detail='Bluesky にポストしました。',
            tweet_url=post_url,
            post_uri=post_response.uri,
            post_cid=post_response.cid,
        )


    async def createRepost(self, post_id: str) -> schemas.TwitterAPIResult:
        """
        Bluesky の投稿をリポストする

        Args:
            post_id (str): 対象投稿の AT URI

        Returns:
            schemas.TwitterAPIResult: リポスト結果
        """

        session_error = await self._restoreSession()
        if session_error is not None:
            return session_error

        try:
            # リポスト作成には StrongRef (URI + CID) が必要なので、AT URI から現在の CID を取得してから SDK に渡す
            post = await self._fetchPostByURI(post_id)
            if post is None:
                return schemas.TwitterAPIResult(is_success=False, detail='Bluesky 投稿情報を取得できませんでした。')
            await self.client.repost(post.uri, post.cid)
        except Exception as ex:
            logging.error(f'{self.log_prefix} Failed to repost:', exc_info=ex)
            return schemas.TwitterAPIResult(is_success=False, detail='Bluesky のリポストに失敗しました。')

        return schemas.TwitterAPIResult(is_success=True, detail='Bluesky の投稿をリポストしました。')


    async def deleteRepost(self, post_id: str) -> schemas.TwitterAPIResult:
        """
        Bluesky のリポストを取り消す

        Args:
            post_id (str): 対象投稿の AT URI

        Returns:
            schemas.TwitterAPIResult: リポスト取消結果
        """

        session_error = await self._restoreSession()
        if session_error is not None:
            return session_error

        try:
            # delete_repost にはリポスト自体の URI が必要なので、対象投稿を取得して viewer.repost を引き直す
            post = await self._fetchPostByURI(post_id)
            if post is None or post.viewer is None or post.viewer.repost is None:
                return schemas.TwitterAPIResult(is_success=False, detail='Bluesky のリポスト情報を取得できませんでした。')
            await self.client.delete_repost(post.viewer.repost)
        except Exception as ex:
            logging.error(f'{self.log_prefix} Failed to delete repost:', exc_info=ex)
            return schemas.TwitterAPIResult(is_success=False, detail='Bluesky のリポスト取り消しに失敗しました。')

        return schemas.TwitterAPIResult(is_success=True, detail='Bluesky のリポストを取り消しました。')


    async def favoritePost(self, post_id: str) -> schemas.TwitterAPIResult:
        """
        Bluesky の投稿をいいねする

        Args:
            post_id (str): 対象投稿の AT URI

        Returns:
            schemas.TwitterAPIResult: いいね結果
        """

        session_error = await self._restoreSession()
        if session_error is not None:
            return session_error

        try:
            # いいね作成も StrongRef が必要なので、AT URI から現在の CID を取得してから SDK に渡す
            post = await self._fetchPostByURI(post_id)
            if post is None:
                return schemas.TwitterAPIResult(is_success=False, detail='Bluesky 投稿情報を取得できませんでした。')
            await self.client.like(post.uri, post.cid)
        except Exception as ex:
            logging.error(f'{self.log_prefix} Failed to like post:', exc_info=ex)
            return schemas.TwitterAPIResult(is_success=False, detail='Bluesky のいいねに失敗しました。')

        return schemas.TwitterAPIResult(is_success=True, detail='Bluesky の投稿をいいねしました。')


    async def unfavoritePost(self, post_id: str) -> schemas.TwitterAPIResult:
        """
        Bluesky のいいねを取り消す

        Args:
            post_id (str): 対象投稿の AT URI

        Returns:
            schemas.TwitterAPIResult: いいね取消結果
        """

        session_error = await self._restoreSession()
        if session_error is not None:
            return session_error

        try:
            # delete_like にはいいねレコードの URI が必要なので、対象投稿の viewer.like を取得してから削除する
            post = await self._fetchPostByURI(post_id)
            if post is None or post.viewer is None or post.viewer.like is None:
                return schemas.TwitterAPIResult(is_success=False, detail='Bluesky のいいね情報を取得できませんでした。')
            await self.client.delete_like(post.viewer.like)
        except Exception as ex:
            logging.error(f'{self.log_prefix} Failed to delete like:', exc_info=ex)
            return schemas.TwitterAPIResult(is_success=False, detail='Bluesky のいいね取り消しに失敗しました。')

        return schemas.TwitterAPIResult(is_success=True, detail='Bluesky のいいねを取り消しました。')


    async def homeLatestTimeline(self, cursor_id: str | None = None) -> schemas.TimelineTweetsResult | schemas.TwitterAPIResult:
        """
        Bluesky のホームタイムラインを取得する

        Args:
            cursor_id (str | None, optional): 前回レスポンスのカーソル

        Returns:
            schemas.TimelineTweetsResult | schemas.TwitterAPIResult: タイムライン取得結果
        """

        session_error = await self._restoreSession()
        if session_error is not None:
            return session_error

        try:
            # Bluesky のホームタイムラインはカーソル 1 本でページングするため、Twitter の Top / Bottom 区別は持ち込まない
            response = await self._invokeWithRetry(
                'get_timeline',
                lambda: self.client.get_timeline(limit=30, cursor=cursor_id),
            )
        except Exception as ex:
            logging.error(f'{self.log_prefix} Failed to fetch home timeline:', exc_info=ex)
            return schemas.TwitterAPIResult(is_success=False, detail='Bluesky のタイムライン取得に失敗しました。')

        # KonomiTV クライアントは Twitter と同じ TimelineTweetsResult を期待するため、PostView を Tweet に正規化する
        tweets = [self._formatPostView(feed_view.post, feed_view.reason) for feed_view in response.feed]
        cursor = response.cursor or None
        return schemas.TimelineTweetsResult(
            is_success=True,
            detail='Bluesky のタイムラインを取得しました。',
            tweets=tweets,
            newer_cursor_id=None,
            load_more_cursors=[
                schemas.TimelineLoadMoreCursor(
                    cursor_type='Older',
                    cursor_id=cursor,
                    entry_id=None,
                    upper_created_at=tweets[-1].created_at if len(tweets) > 0 else None,
                    lower_created_at=None,
                )
            ] if cursor is not None else [],
            is_cursor_consumed=True,
        )


    async def searchTimeline(self, query: str, cursor_id: str | None = None) -> schemas.TimelineTweetsResult | schemas.TwitterAPIResult:
        """
        Bluesky の投稿を検索する

        Args:
            query (str): 検索クエリ
            cursor_id (str | None, optional): 前回レスポンスのカーソル

        Returns:
            schemas.TimelineTweetsResult | schemas.TwitterAPIResult: 検索結果
        """

        session_error = await self._restoreSession()
        if session_error is not None:
            return session_error

        try:
            # 検索結果もホームタイムラインと同じ Tweet 配列へ変換できるよう、最新順で一定件数だけ取得する
            response = await self._invokeWithRetry(
                'search_posts',
                lambda: self.client.app.bsky.feed.search_posts(
                    models.AppBskyFeedSearchPosts.Params(
                        q=query,
                        cursor=cursor_id,
                        limit=30,
                        sort='latest',
                    ),
                ),
            )
        except Exception as ex:
            logging.error(f'{self.log_prefix} Failed to search posts:', exc_info=ex)
            return schemas.TwitterAPIResult(is_success=False, detail='Bluesky の検索に失敗しました。')

        # search_posts は reason を持たない PostView 配列なので、リポスト表示用の変換は通さない
        tweets = [self._formatPostView(post) for post in response.posts]
        cursor = response.cursor or None
        return schemas.TimelineTweetsResult(
            is_success=True,
            detail='Bluesky の検索結果を取得しました。',
            tweets=tweets,
            newer_cursor_id=None,
            load_more_cursors=[
                schemas.TimelineLoadMoreCursor(
                    cursor_type='Older',
                    cursor_id=cursor,
                    entry_id=None,
                    upper_created_at=tweets[-1].created_at if len(tweets) > 0 else None,
                    lower_created_at=None,
                )
            ] if cursor is not None else [],
            is_cursor_consumed=True,
        )


    @staticmethod
    def normalizeBlueskyHandle(handle: str) -> str:
        """
        ユーザー入力の Bluesky handle を atproto SDK が扱う形式に正規化する

        Args:
            handle (str): ユーザーが入力した handle

        Returns:
            str: 前後の空白と先頭の @ を除去し、小文字化した handle
        """

        normalized_handle = handle.strip()

        # bsky.app のプロフィール URL をそのまま貼り付けた場合も handle 部分だけを取り出す
        for profile_url_prefix in ('https://bsky.app/profile/', 'http://bsky.app/profile/'):
            if normalized_handle.startswith(profile_url_prefix) is True:
                normalized_handle = normalized_handle.removeprefix(profile_url_prefix).split('/')[0].split('?')[0]
                break

        # UI 表示用の @ 付き表記 (@user.bsky.social) で入力された場合も受け付ける
        if normalized_handle.startswith('@') is True:
            normalized_handle = normalized_handle.removeprefix('@').strip()

        # ログイン成功後に DB へ保存される handle (profile.handle) と同じく小文字に揃える
        return normalized_handle.lower()


    @staticmethod
    def _extractRecordKey(uri: str) -> str:
        """
        AT URI から record key を取り出す

        Args:
            uri (str): AT URI

        Returns:
            str: record key
        """

        return uri.rsplit('/', 1)[-1]


    @staticmethod
    def _parseDateTime(datetime_text: str) -> datetime:
        """
        Bluesky API の日時文字列を JST の datetime に変換する

        Args:
            datetime_text (str): ISO 8601 形式の日時文字列

        Returns:
            datetime: JST に変換済みの日時
        """

        return datetime.fromisoformat(datetime_text.replace('Z', '+00:00')).astimezone(JST)


    @classmethod
    def _buildTextBuilder(cls, text: str) -> client_utils.TextBuilder:
        """
        URL とハッシュタグだけを facets 化した TextBuilder を作成する

        Args:
            text (str): 投稿本文

        Returns:
            client_utils.TextBuilder: facets 情報を含む TextBuilder
        """

        # URL の末尾に張り付きがちな句読点・閉じ括弧の集合
        # 例えば「サイト https://example.com,いいね！」のような本文では、URL に , が含まれないよう
        # この集合に含まれる文字を URL の末尾から本文側に押し戻して facets を構築する
        URL_TRAILING_PUNCTUATIONS = '。、,.;:!?！？)）」』]>'

        text_builder = client_utils.TextBuilder()
        token_pattern = re.compile(r'(https?://[^\s]+)|([#＃]([^\s#＃]+))')

        cursor = 0
        for match in token_pattern.finditer(text):
            # マッチしていない通常本文を先に追加し、元本文の順序を保ったまま facets を挿入する
            if match.start() > cursor:
                text_builder.text(text[cursor:match.start()])
            token_text = match.group(0)
            if match.group(1) is not None:
                # URL の末尾に張り付いた句読点・閉じ括弧は本文側に戻す
                # こうしないと facets の URL に余計な記号が含まれリンク先がエラーになる
                trailing_chars = ''
                while len(token_text) > 0 and token_text[-1] in URL_TRAILING_PUNCTUATIONS:
                    trailing_chars = token_text[-1] + trailing_chars
                    token_text = token_text[:-1]
                if len(token_text) > 0:
                    text_builder.link(token_text, token_text)
                if trailing_chars != '':
                    text_builder.text(trailing_chars)
            else:
                # Bluesky の tag facet には # を含まないタグ名を渡す必要がある
                # URL と同じく末尾記号を facet に含めると、タグ名に句読点が混ざって検索性が落ちる
                trailing_chars = ''
                while len(token_text) > 0 and token_text[-1] in URL_TRAILING_PUNCTUATIONS:
                    trailing_chars = token_text[-1] + trailing_chars
                    token_text = token_text[:-1]
                if len(token_text) > 0:
                    tag_text = token_text.lstrip('#＃')
                    # 記号だけのハッシュタグは Bluesky 側の facet として意味を持たない
                    ## 空タグ名を渡すと不正な facet になるため、本文として残して投稿内容を壊さない
                    if tag_text != '':
                        text_builder.tag(token_text, tag_text)
                    else:
                        text_builder.text(token_text)
                if trailing_chars != '':
                    text_builder.text(trailing_chars)
            cursor = match.end()

        # 最後の URL / ハッシュタグ以降に残った通常本文を追加する
        if cursor < len(text):
            text_builder.text(text[cursor:])

        return text_builder


    @classmethod
    def _expandFacetLinksInText(
        cls,
        text: str,
        facets: list[models.AppBskyRichtextFacet.Main] | None,
    ) -> str:
        """
        Bluesky の link facet が持つ実 URL を表示用テキストへ反映する

        Args:
            text (str): Bluesky レコード上の本文
            facets (list[models.AppBskyRichtextFacet.Main] | None): 本文上の装飾情報

        Returns:
            str: link facet の表示範囲を実 URL に置換した本文
        """

        if facets is None or len(facets) == 0:
            return text

        text_bytes = text.encode('utf-8')
        replacements: list[tuple[int, int, str]] = []
        for facet in facets:
            link_uri: str | None = None
            for feature in facet.features:
                # Bluesky 公式 Web は短縮表示された URL でも link facet の uri に実 URL を保持している
                # KonomiTV 側では本文へ実 URL を戻し、既存のフロント側リンク化処理に乗せる
                if isinstance(feature, models.AppBskyRichtextFacet.Link):
                    link_uri = feature.uri
                    break

            if link_uri is None:
                continue

            byte_start = facet.index.byte_start
            byte_end = facet.index.byte_end
            # PDS 由来の byte slice が壊れている場合は表示本文を壊さず、その facet だけを無視する
            if byte_start < 0 or byte_end <= byte_start or byte_end > len(text_bytes):
                logging.warning(
                    f'{cls.__name__} Ignored invalid Bluesky link facet range. '
                    f'[byte_start: {byte_start}, byte_end: {byte_end}, text_bytes: {len(text_bytes)}]',
                )
                continue

            replacements.append((byte_start, byte_end, link_uri))

        if len(replacements) == 0:
            return text

        # byte slice の後ろから置換すると、前方 facet の byte offset を維持したまま安全に差し替えられる
        expanded_text_bytes = bytearray(text_bytes)
        for byte_start, byte_end, link_uri in sorted(replacements, key=lambda replacement: replacement[0], reverse=True):
            expanded_text_bytes[byte_start:byte_end] = link_uri.encode('utf-8')

        return expanded_text_bytes.decode('utf-8')


# atproto SDK が将来の表示系 Union 追加で落ちる場合も、投稿本文だけは残せるようにする
_PatchAtprotoUnknownSchemaResponseModel()
