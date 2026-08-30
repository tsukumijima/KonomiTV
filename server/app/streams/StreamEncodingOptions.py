from __future__ import annotations

from dataclasses import dataclass

from app.config import Config
from app.constants import LIVE_STREAMING_QUALITY_TYPES, QUALITY, QUALITY_TYPES


@dataclass(frozen=True)
class StreamEncodingOptions:
    """
    ライブ/録画ストリームでベース画質に追加するエンコードオプションを表す

    Args:
        is_hevc_10bit_enabled (bool): HEVC 10bit を要求するクライアント向けのストリームかどうか
        is_24fps_mode_enabled (bool): 24fps モードを適用するストリームかどうか
        audio_track_index (int): 選択する音声トラックの 0 スタートのインデックス (録画のみ、ライブでは常に 0)
    """

    # HEVC 10bit を要求するクライアント向けのストリームかどうか
    ## --fallback-bitdepth により、GPU 側が HEVC 10bit 非対応の場合でも 8bit へフォールバックされるため、
    ## 値の意味は「HEVC 10bit を要求」であり「HEVC 10bit 出力の保証」ではない
    is_hevc_10bit_enabled: bool = False

    # 24fps モードを適用するストリームかどうか
    ## 1080p-60fps では 60fps 化を優先し、24fps モードの要求があってもここでは無効にする
    is_24fps_mode_enabled: bool = False

    # 選択する音声トラックの 0 スタートのインデックス (録画のみ、ライブでは常に 0)
    ## 0: 主音声 (デフォルト), 1: 副音声。指定したインデックスの音声トラックが録画データに存在しない場合
    ## (録画マージン内でまだ副音声が始まっていない場合など)、セグメント単位で主音声にフォールバックする
    ## — VideoEncodingTask.run() 側の処理であり、ここでは指定値を保持するだけ
    audio_track_index: int = 0

    @classmethod
    def fromRequest(
        cls,
        quality: QUALITY_TYPES,
        is_hevc_10bit_requested: bool,
        is_24fps_mode_requested: bool,
        audio_track_index_requested: int = 0,
    ) -> StreamEncodingOptions:
        """
        API で指定されたオプションから、実際に使うストリームオプションを作る

        Args:
            quality (QUALITY_TYPES): ベース画質
            is_hevc_10bit_requested (bool): クライアントが HEVC 10bit を要求しているかどうか
            is_24fps_mode_requested (bool): クライアントが 24fps モードを要求しているかどうか
            audio_track_index_requested (int): クライアントが要求する音声トラックインデックス (0: 主音声, 1: 副音声)

        Returns:
            StreamEncodingOptions: 実際のストリーム生成に使うエンコードオプション
        """

        # HEVC 10bit は通信節約モードで使う HEVC 画質かつ QSVEncC / NVEncC の場合だけ有効化する
        ## VCEEncC は HEVC 10bit 対応の機種かを判定できず、rkmppenc は HEVC 10bit エンコード自体に非対応のため設定しない
        is_hevc_10bit_enabled = (
            is_hevc_10bit_requested is True and
            QUALITY[quality].is_hevc is True and
            Config().general.encoder in ['QSVEncC', 'NVEncC']
        )

        # 24fps モードは 60fps 画質以外で有効化する
        ## 1080p-60fps では 60i を 60p 化するユーザー意図が明確なので、24fps モードより 60fps 化を優先する
        is_24fps_mode_enabled = (
            is_24fps_mode_requested is True and
            QUALITY[quality].is_60fps is False
        )

        # 現状 ARIB 放送で意味を持つのは主音声 (0) と副音声 (1) のみ
        ## 不正な値が渡された場合は安全側に倒して主音声にする
        audio_track_index = audio_track_index_requested if audio_track_index_requested in (0, 1) else 0

        return cls(
            is_hevc_10bit_enabled = is_hevc_10bit_enabled,
            is_24fps_mode_enabled = is_24fps_mode_enabled,
            audio_track_index = audio_track_index,
        )

    def buildSuffix(self) -> str:
        """
        ライブストリーム ID の末尾に付ける文字列を組み立てる

        Returns:
            str: ライブストリーム ID の末尾に付ける文字列
        """

        suffix = ''

        # -10bit は -24fps より先に付け、ビット深度からフレームレートの順で並べる
        if self.is_hevc_10bit_enabled is True:
            suffix += '-10bit'

        # 24fps モードが有効なストリームだけ -24fps を付ける
        if self.is_24fps_mode_enabled is True:
            suffix += '-24fps'

        # 音声トラック指定は他のオプションと独立した概念のため、既存の並び (10bit → 24fps) の
        # 一番最後に付ける。主音声 (index 0) の場合は既存の URL 形式を一切変えないよう、
        # 接尾辞自体を付けない
        if self.audio_track_index != 0:
            suffix += f'-audio{self.audio_track_index + 1}'

        return suffix


@dataclass(frozen=True)
class StreamQualityWithOptions:
    """
   ストリーミング配信 API の品質指定を、ベース画質と追加エンコードオプションへ分解した結果を表す

    Args:
        quality (LIVE_STREAMING_QUALITY_TYPES): ベース画質
        encoding_options (StreamEncodingOptions): ベース画質に追加するエンコードオプション
    """

    # QUALITY に定義されているベース画質
    ## API パスには 720p-hevc-10bit-24fps のようにオプション付きの品質が渡されるが、エンコード処理にはこの値だけを渡す
    ## ライブ時のみ "original" を受け付ける (録画再生時は VideoEncodingTask 自体を迂回するので設定できないが、型を分けるのが面倒なのでこれで)
    quality: LIVE_STREAMING_QUALITY_TYPES

    # ベース画質に追加するエンコードオプション
    ## HEVC 10bit や 24fps モードは、ベース画質から分けてストリーム ID やエンコード引数へ渡す
    encoding_options: StreamEncodingOptions


def SplitQualityAndEncodingOptions(quality: str) -> StreamQualityWithOptions | None:
    """
    API パスの品質指定 (例: 720p-hevc-10bit-24fps) を、ベース画質 (720p-hevc) と追加オプション (-10bit / -24fps) に分解する

    Args:
        quality (str): API パスで指定された品質

    Returns:
        StreamQualityWithOptions | None: 分解結果 (不正な品質指定の場合は None)
    """

    # オリジナル画質が指定された場合は確実にライブ配信からなので特別扱い
    if quality == 'original':
        return StreamQualityWithOptions(
            quality = 'original',
            # エンコーダーを通さないためエンコードオプションは空
            encoding_options = StreamEncodingOptions(),
        )

    # -10bit / -24fps / -audio2 は buildSuffix() と同じ順序でのみ受け付ける
    ## 末尾から剥がすことで、1080p-60fps-hevc のようにベース画質自体が -hevc を含むケースを安全に扱う
    base_quality = quality

    # -audio2 は buildSuffix() で一番最後に付けているため、剥がすのも一番最初に行う
    audio_track_index_requested = 0
    if base_quality.endswith('-audio2') is True:
        base_quality = base_quality[:-len('-audio2')]
        audio_track_index_requested = 1

    is_24fps_mode_requested = False
    if base_quality.endswith('-24fps') is True:
        base_quality = base_quality[:-len('-24fps')]
        is_24fps_mode_requested = True

    is_hevc_10bit_requested = False
    if base_quality.endswith('-10bit') is True:
        base_quality = base_quality[:-len('-10bit')]
        is_hevc_10bit_requested = True

    # ベース画質が QUALITY に存在しない場合は、ルーター側で従来通り 422 を返す
    if base_quality not in QUALITY:
        return None

    # 画質とサーバー側の対応状況を見て、実際に使えるオプションだけを残す
    ## HEVC 10bit 非対応エンコーダーや 1080p-60fps の 24fps モード要求はここで無効化される
    encoding_options = StreamEncodingOptions.fromRequest(
        base_quality,
        is_hevc_10bit_requested,
        is_24fps_mode_requested,
        audio_track_index_requested,
    )
    return StreamQualityWithOptions(
        quality = base_quality,
        encoding_options = encoding_options,
    )
