#!/usr/bin/env python3

# Usage: poetry run python -m misc.TSReplaceEncodeMatrixTest /path/to/input.ts

"""
tsreplace + QSVEncC/NVEncC のエンコードパターン横断検証スクリプト

指定された生 TS (60i 地デジ前提) を入力として、以下の 12 パターンで tsreplace を使って
映像のみを再エンコードし、KonomiTV での再生・キーフレーム解析が問題なく動くかを検証する。

パターン:
  {H.264, H.265} × {QSVEncC, NVEncC} × {30p normal deinterlace, 24p VFR afs, 60p bob deinterlace}

フェーズ 1 で H.264 系の 6 パターンを並行実行し、終わったらフェーズ 2 で H.265 系を並行実行する
(GPU とハードウェアエンコーダーの同時利用耐性を加味して、コーデックごとに分けている)。
メモリ使用量を抑えたい場合は `--concurrency` でコーデックごとの同時実行数を絞れる。

フェーズ 3 では出力された各 TS に対して ffprobe ベースのキーフレーム解析と PCR 二分探索
ベンチマークを実行し、KonomiTV のキーフレーム抽出経路と on-demand 探索経路の両方が期待通り
に動作するかを検証する。

設計メモ:
- エンコードパラメータは rigaya 氏からご提案いただいた KonomiTV 向け録画後再エンコード
  用設定をベースにしている (HEVC 10bit / --icq 21 / --qvbr 30 / --gop-len 75 など)。
- tsreplace の -e モードを使い、tsreplace が encoder を直接起動する形にしている。
  これにより encoder と tsreplace の接続は tsreplace 側に任せられる。
- subprocess の stdout/stderr は親プロセスから継承しているため、複数プロセス分のログが
  そのまま端末に混在する形で流れる (デバッグ目的なので分離は行わない)。
- 既存の .avc.*.ts / .hevc.*.ts は上書きされる (失敗したら単にもう一度実行すればよい)。
"""

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import typer

from app.constants import LIBRARY_PATH


# ***** 型エイリアス *****

# 出力コーデック (h264 or hevc)
Codec = Literal['h264', 'hevc']
# 使用エンコーダー (qsv or nvenc)
Encoder = Literal['qsv', 'nvenc']
# フレームレートモード (30p normal / 24p afs VFR / 60p bob)
FpsMode = Literal['30p', '24p', '60p']


# ***** 定数 *****

# ログ出力時の区切り線
SEPARATOR = '=' * 80


@dataclass
class EncodePattern:
    """エンコードパターンを表すデータクラス"""

    # 出力コーデック (h264 or hevc)
    codec: Codec
    # 使用エンコーダー (qsv or nvenc)
    encoder: Encoder
    # フレームレートモード (30p / 24p afs / 60p bob)
    fps_mode: FpsMode

    @property
    def suffix(self) -> str:
        """
        出力ファイル名に付加するサフィックス

        例: codec=h264, encoder=qsv, fps_mode=30p -> "avc.qsv30p"
        """

        codec_part = 'avc' if self.codec == 'h264' else 'hevc'
        return f'{codec_part}.{self.encoder}{self.fps_mode}'


@dataclass
class EncodeResult:
    """エンコード結果を表すデータクラス"""

    # 対応するエンコードパターン
    pattern: EncodePattern
    # 出力ファイルのパス
    output_path: Path
    # tsreplace プロセスの終了コード
    returncode: int
    # エンコードにかかった秒数
    elapsed_seconds: float
    # 出力ファイルのサイズ (バイト、失敗時は 0)
    output_size: int


@dataclass
class AnalysisResult:
    """エンコード後の解析結果を表すデータクラス"""

    # ffprobe で取得できた総パケット数
    total_packets: int = 0
    # ffprobe で取得できたキーフレーム数
    keyframes: int = 0
    # 最初のパケットの PTS (秒)
    first_pts: float = 0.0
    # 最後のパケットの PTS (秒)
    last_pts: float = 0.0
    # PCR_PID (biim の PMT から取得)
    pcr_pid: int | None = None
    # PCR 二分探索 (cold cache) の実測時間 (ミリ秒)
    binary_search_ms: float = 0.0
    # 二分探索の反復回数
    binary_search_iters: int = 0
    # PCR 間隔の最大値 (バイト)
    pcr_max_gap_bytes: int = 0
    # PCR 間隔の最大値 (ミリ秒)
    pcr_max_gap_ms: float = 0.0
    # 先頭から 4 MB 以内で見つかった PCR の個数
    pcr_count_in_head: int = 0
    # 解析時にエラーが起きた場合のメッセージ
    error: str | None = None


@dataclass
class PCRInfo:
    """analyze_pcr() が返す内部の PCR 解析結果"""

    # PCR_PID (PMT から取得)
    pcr_pid: int
    # PCR 二分探索 (cold cache) の実測時間 (ミリ秒)
    binary_search_ms: float
    # 二分探索の反復回数
    binary_search_iters: int
    # PCR 間隔の最大値 (バイト)
    pcr_max_gap_bytes: int
    # PCR 間隔の最大値 (ミリ秒)
    pcr_max_gap_ms: float
    # 先頭から 4 MB 以内で見つかった PCR の個数
    pcr_count_in_head: int


@dataclass
class LaunchedProcess:
    """起動済みの subprocess とそのメタ情報を保持する"""

    # 対応するエンコードパターン
    pattern: EncodePattern
    # tsreplace subprocess.Popen ハンドル
    process: 'subprocess.Popen[bytes]'
    # 起動開始時刻 (perf_counter)
    start_time: float
    # 出力ファイルパス
    output_path: Path


# ***** エンコーダー引数の組み立て *****

def build_common_encoder_args(codec: Codec) -> list[str]:
    """
    コーデックによらず両エンコーダーで共通の引数を組み立てる

    Args:
        codec (Codec): 出力コーデック

    Returns:
        list[str]: 共通引数のリスト
    """

    args: list[str] = []

    # 入力は標準入力 (tsreplace -e モードで tsreplace から pipe 経由で渡される)
    args += ['-i', '-']
    # 入力は MPEG-TS コンテナ
    args += ['--input-format', 'mpegts']
    # 出力は標準出力 (tsreplace が受け取る)
    args += ['-o', '-']
    # 出力は raw elementary stream (h264/hevc ES)
    ## VFR (afs drop=on) でもタイミング情報は tsreplace が元 TS の PCR/PTS から復元するので、
    ## 出力側はタイミング情報なしの raw ES で問題ない
    args += ['--output-format', 'raw']

    # 出力コーデック
    args += ['-c', codec]

    # HEVC は 10bit + fallback モード
    ## rigaya 氏の推奨設定
    ## --fallback-bitdepth は 10bit 非対応環境で 8bit にフォールバックする
    if codec == 'hevc':
        args += ['--output-depth', '10', '--fallback-bitdepth']

    # GOP 長 (rigaya 氏推奨値)
    args += ['--gop-len', '75']

    # バンディング対策 (--vpp-deband)
    ## 一部の GPU 世代では若干遅くなるが、品質重視のため有効化する
    args += ['--vpp-deband']

    return args


def build_deinterlace_args(encoder: Encoder, fps_mode: FpsMode) -> list[str]:
    """
    デインタレース/フレームレート変換の引数を組み立てる

    Args:
        encoder (Encoder): 使用エンコーダー
        fps_mode (FpsMode): フレームレートモード

    Returns:
        list[str]: デインタレース関連引数
    """

    if fps_mode == '30p':
        # 60i -> 30p single-field deinterlace
        if encoder == 'qsv':
            # QSVEncC: VEBOX デインタレース (normal モード)
            ## Arrow Lake + intel-media-driver の古いバージョンでは crash する問題があったが、
            ## パッチ適用済みの環境なら動作する
            return ['--vpp-deinterlace', 'normal']
        # NVEncC: CUDA による yadif デインタレース (default mode=0, single rate)
        ## --vpp-afs や --vpp-nnedi に比べて速度と品質のバランスが良い
        return ['--vpp-yadif']

    if fps_mode == '24p':
        # 60i -> 24/30p VFR (自動フィールドシフト)
        ## QSVEncC / NVEncC 共通で --vpp-afs が使える
        ## drop=on: 重複フレームを落として 24p または 30p にする (通常は混合 VFR になる)
        ## smooth=on: シフト境界でフレーム補間を行う (フィルタのちらつき低減)
        return ['--vpp-afs', 'drop=on,smooth=on']

    # fps_mode == '60p'
    ## 60i -> 60p bob deinterlace
    if encoder == 'qsv':
        # QSVEncC: VEBOX デインタレース (bob モード)
        return ['--vpp-deinterlace', 'bob']
    # NVEncC: CUDA yadif の bob モード (フィールドごとに 1 フレーム出力)
    return ['--vpp-yadif', 'mode=bob']


def build_qsv_quality_args() -> list[str]:
    """
    QSVEncC の品質関連引数を組み立てる (rigaya 氏推奨設定)

    Returns:
        list[str]: QSVEncC 品質関連引数
    """

    return [
        # ICQ (Intelligent Constant Quality) モード
        ## 21 は「MPEG-2 からの画質劣化をほぼ知覚できない」塩梅の目安
        '--icq', '21',
        # B フレームの数 (8 フレーム)
        '-b', '8',
        # Extended BRC (ビットレートコントロールの品質向上)
        '--extbrc',
        # マクロブロック単位の BRC
        '--mbbrc',
        # エンコードシナリオ (game_streaming は低遅延寄りだが高画質)
        '--scenario-info', 'game_streaming',
        # 人間の知覚特性に最適化したチューニング
        '--tune', 'perceptual',
        # I フレーム / B フレームの適応的配置
        '--i-adapt',
        '--b-adapt',
        # B-pyramid 有効化 (B フレームの階層参照)
        '--b-pyramid',
        # 重み付き P/B 予測
        '--weightp',
        '--weightb',
        # 参照フレーム数の適応制御
        '--adapt-ref',
        # 長期参照フレームの適応制御
        '--adapt-ltr',
        # 量子化行列の適応制御
        '--adapt-cqm',
        # look-ahead 品質制御
        '--la-depth', '60',
        '--la-quality', 'slow',
    ]


def build_nvenc_quality_args() -> list[str]:
    """
    NVEncC の品質関連引数を組み立てる (rigaya 氏推奨設定)

    Returns:
        list[str]: NVEncC 品質関連引数
    """

    return [
        # QVBR (Quality-Controlled Variable Bitrate) モード
        ## 30 は HEVC 10bit + tune uhq 環境で「画質劣化をほぼ知覚できない」目安
        '--qvbr', '30',
        # エンコードプリセット (quality が最も品質寄り)
        '--preset', 'quality',
        # 最高品質チューニング
        '--tune', 'uhq',
        # 2-pass full マルチパス
        '--multipass', '2pass-full',
        # 重み付き P 予測
        '--weightp',
        # B フレーム参照モード (each = すべての B フレームを参照可能に)
        '--bref-mode', 'each',
    ]


def build_encoder_args(pattern: EncodePattern) -> list[str]:
    """
    指定パターンに対応する encoder コマンドライン引数一式を組み立てる

    Args:
        pattern (EncodePattern): エンコードパターン

    Returns:
        list[str]: encoder に渡す引数のリスト (encoder バイナリパスは含まない)
    """

    args: list[str] = []

    # 共通引数
    args += build_common_encoder_args(pattern.codec)

    # デインタレース/フレームレート変換
    args += build_deinterlace_args(pattern.encoder, pattern.fps_mode)

    # 品質関連引数 (エンコーダーごとに異なる)
    if pattern.encoder == 'qsv':
        args += build_qsv_quality_args()
    else:
        args += build_nvenc_quality_args()

    return args


def build_tsreplace_command(
    tsreplace_binary: str,
    input_path: Path,
    output_path: Path,
    pattern: EncodePattern,
) -> list[str]:
    """
    tsreplace -e モードのコマンドを組み立てる

    Args:
        tsreplace_binary (str): tsreplace バイナリの絶対パス (shutil.which() 経由で解決する)
        input_path (Path): 入力 TS ファイル
        output_path (Path): 出力 TS ファイル
        pattern (EncodePattern): エンコードパターン

    Returns:
        list[str]: tsreplace のコマンドライン全体
    """

    # encoder バイナリを KonomiTV の LIBRARY_PATH から取得
    ## この環境の絶対パスに依存しないように、必ず LIBRARY_PATH 経由で解決する
    encoder_binary = LIBRARY_PATH['QSVEncC'] if pattern.encoder == 'qsv' else LIBRARY_PATH['NVEncC']

    # encoder 引数を組み立てる
    encoder_args = build_encoder_args(pattern)

    # tsreplace のコマンド
    return [
        tsreplace_binary,
        '-i', str(input_path),
        '-o', str(output_path),
        '-e', encoder_binary,
        *encoder_args,
    ]


# ***** エンコード実行 *****

def run_patterns_in_batches(
    tsreplace_binary: str,
    input_path: Path,
    patterns: list[EncodePattern],
    concurrency: int,
) -> list[EncodeResult]:
    """
    複数のエンコードパターンを指定された並行数で逐次 batch 実行する
    batch 内の各パターンごとに tsreplace サブプロセスを起動し、batch 内の全プロセスの完了を待つ
    サブプロセスの stdout/stderr は親プロセスから継承しているため、進捗ログはそのまま
    端末に流れる

    Args:
        tsreplace_binary (str): tsreplace バイナリの絶対パス
        input_path (Path): 入力 TS ファイル
        patterns (list[EncodePattern]): 実行するエンコードパターンのリスト
        concurrency (int): 1 バッチあたりの同時実行数 (1 以上)

    Returns:
        list[EncodeResult]: 各パターンのエンコード結果 (入力 patterns と同じ順)
    """

    results: list[EncodeResult] = []
    for batch_start in range(0, len(patterns), concurrency):
        batch = patterns[batch_start:batch_start + concurrency]
        if not batch:
            continue

        # batch 内のプロセスを一斉に起動する
        launched: list[LaunchedProcess] = []
        for pattern in batch:
            # 出力ファイルパスを組み立てる
            ## 例: .../foo.ts -> .../foo.avc.qsv30p.ts
            output_path = input_path.with_suffix(f'.{pattern.suffix}.ts')

            # tsreplace コマンドを組み立てる
            cmd = build_tsreplace_command(tsreplace_binary, input_path, output_path, pattern)

            # ログ出力 (起動するコマンドを明示する)
            print(f'[{pattern.suffix}] Launching tsreplace...', flush=True)
            print(f'[{pattern.suffix}] {" ".join(cmd)}', flush=True)

            # subprocess を起動 (stdout/stderr は親プロセスから継承)
            ## これにより encoder と tsreplace の進捗ログがそのまま端末に流れる
            start_time = time.perf_counter()
            process: subprocess.Popen[bytes] = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,  # tsreplace は -i で入力を指定するので stdin は不要
                stdout=None,  # 親から継承
                stderr=None,  # 親から継承
            )
            launched.append(LaunchedProcess(
                pattern=pattern,
                process=process,
                start_time=start_time,
                output_path=output_path,
            ))

        # batch 内の全プロセスの完了を待つ
        for launched_process in launched:
            returncode = launched_process.process.wait()
            elapsed_seconds = time.perf_counter() - launched_process.start_time
            output_size = launched_process.output_path.stat().st_size \
                if launched_process.output_path.exists() else 0
            results.append(EncodeResult(
                pattern=launched_process.pattern,
                output_path=launched_process.output_path,
                returncode=returncode,
                elapsed_seconds=elapsed_seconds,
                output_size=output_size,
            ))
            print(
                f'[{launched_process.pattern.suffix}] Finished: '
                f'rc={returncode}, elapsed={elapsed_seconds:.1f}s, '
                f'size={output_size / 1024 / 1024:.1f} MB',
                flush=True,
            )

    return results


# ***** 出力ファイルの解析 *****

def analyze_pcr(path: Path) -> PCRInfo:
    """
    PCR の存在・密度・二分探索の性能を計測する
    biim の TS ライブラリを直接使って PCR を読み取る
    biim / ctypes を使うため、この関数は関数内で遅延インポートする

    Args:
        path (Path): 解析対象の TS ファイル

    Returns:
        PcrInfo: PCR 解析結果

    Raises:
        RuntimeError: PCR が見つからないか、PMT から PCR_PID を取得できなかった場合
    """

    # biim / ctypes を関数内で遅延インポートする
    ## (スクリプト冒頭でインポートすると biim 未インストール環境で全体が壊れるため)
    import ctypes

    from biim.mpeg2ts import ts
    from biim.mpeg2ts.parser import SectionParser
    from biim.mpeg2ts.pat import PATSection
    from biim.mpeg2ts.pmt import PMTSection

    libc = ctypes.CDLL('libc.so.6', use_errno=True)
    POSIX_FADV_DONTNEED = 4

    file_size = path.stat().st_size

    # 先頭 4 MB を読み込み、PMT から PCR_PID を取得する
    with open(path, 'rb') as f:
        head_data = f.read(4 * 1024 * 1024)

    pat_parser: SectionParser[PATSection] = SectionParser(PATSection)
    pmt_parser: SectionParser[PMTSection] = SectionParser(PMTSection)
    pmt_pid: int | None = None
    pcr_pid: int | None = None

    offset = 0
    while offset + 188 <= len(head_data):
        if head_data[offset] != 0x47:
            offset += 1
            continue
        packet = head_data[offset:offset + 188]
        pid = ts.pid(packet)
        if pid == 0:
            pat_parser.push(packet)
            for pat in pat_parser:
                if pat.CRC32() != 0:
                    continue
                for program_number, program_map_pid in pat:
                    if program_number != 0 and pmt_pid is None:
                        pmt_pid = program_map_pid
        elif pmt_pid is not None and pid == pmt_pid:
            pmt_parser.push(packet)
            for pmt in pmt_parser:
                if pmt.CRC32() != 0:
                    continue
                pcr_pid = pmt.PCR_PID
                break
        if pcr_pid is not None:
            break
        offset += 188

    if pcr_pid is None:
        raise RuntimeError('PCR_PID not found in PMT')

    # 先頭 4 MB 内の PCR を全て列挙して、最大ギャップ (バイト / ミリ秒) を計測する
    pcrs_in_head: list[tuple[int, int]] = []  # (offset_in_data, pcr_base)
    offset = 0
    while offset + 188 <= len(head_data):
        if head_data[offset] != 0x47:
            offset += 1
            continue
        packet = head_data[offset:offset + 188]
        if ts.pid(packet) == pcr_pid:
            pcr_value = ts.pcr(packet)
            if pcr_value is not None:
                pcrs_in_head.append((offset, pcr_value))
        offset += 188

    pcr_max_gap_bytes = 0
    pcr_max_gap_ms = 0.0
    if len(pcrs_in_head) >= 2:
        for i in range(1, len(pcrs_in_head)):
            gap_bytes = pcrs_in_head[i][0] - pcrs_in_head[i - 1][0]
            gap_ticks = pcrs_in_head[i][1] - pcrs_in_head[i - 1][1]
            # 33bit のラップアラウンドを考慮する
            if gap_ticks < 0:
                gap_ticks += (1 << 33)
            gap_ms = gap_ticks / 90  # pcr_base は 90kHz 単位
            if gap_bytes > pcr_max_gap_bytes:
                pcr_max_gap_bytes = gap_bytes
            if gap_ms > pcr_max_gap_ms:
                pcr_max_gap_ms = gap_ms

    # 末尾付近 4 MB を読み、最後の PCR を取得する (二分探索のターゲット計算用)
    tail_scan_window = 4 * 1024 * 1024
    tail_start = max(0, file_size - tail_scan_window)
    with open(path, 'rb') as f:
        f.seek(tail_start)
        tail_data = f.read(file_size - tail_start)

    tail_pcrs: list[tuple[int, int]] = []
    offset = 0
    while offset + 188 <= len(tail_data):
        if tail_data[offset] != 0x47:
            offset += 1
            continue
        packet = tail_data[offset:offset + 188]
        if ts.pid(packet) == pcr_pid:
            pcr_value = ts.pcr(packet)
            if pcr_value is not None:
                tail_pcrs.append((offset, pcr_value))
        offset += 188

    if not pcrs_in_head or not tail_pcrs:
        raise RuntimeError('no PCR at head or tail')

    first_pcr = pcrs_in_head[0][1]
    last_pcr = tail_pcrs[-1][1]
    total_ticks = last_pcr - first_pcr
    if total_ticks < 0:
        total_ticks += (1 << 33)

    # 50% 地点の PCR を目標値として二分探索する
    target_pcr = (first_pcr + total_ticks // 2) & ((1 << 33) - 1)

    # cold cache にしてから二分探索を実行 (posix_fadvise DONTNEED は hint なので完全には効かない)
    fd = os.open(str(path), os.O_RDONLY)
    try:
        libc.posix_fadvise(fd, 0, 0, POSIX_FADV_DONTNEED)
    finally:
        os.close(fd)

    # 二分探索の実行
    lo = 0
    hi = file_size
    iterations = 0
    start = time.perf_counter()
    while hi - lo > 1_000_000:
        mid = (lo + hi) // 2
        iterations += 1

        # mid 位置から窓を拡大しながら PCR を探す
        found_pcr: int | None = None
        window = 64 * 1024
        while window <= 4 * 1024 * 1024 and found_pcr is None:
            read_size = min(window, file_size - mid)
            if read_size <= 188:
                break
            with open(path, 'rb') as f:
                f.seek(mid)
                data = f.read(read_size)

            # 188 バイト境界を再同期する
            sync_offset = -1
            for i in range(min(len(data) - 188, 4096)):
                if data[i] == 0x47 and data[i + 188] == 0x47:
                    sync_offset = i
                    break
            if sync_offset < 0:
                window *= 2
                continue

            scan_offset = sync_offset
            while scan_offset + 188 <= len(data):
                if data[scan_offset] != 0x47:
                    scan_offset += 1
                    continue
                packet = data[scan_offset:scan_offset + 188]
                if ts.pid(packet) == pcr_pid:
                    pcr_value = ts.pcr(packet)
                    if pcr_value is not None:
                        found_pcr = pcr_value
                        break
                scan_offset += 188

            if found_pcr is None:
                window *= 2

        if found_pcr is None:
            # この区間には PCR がない想定。前進する
            lo = mid
            continue

        if found_pcr < target_pcr:
            lo = mid
        else:
            hi = mid

    binary_search_ms = (time.perf_counter() - start) * 1000

    return PCRInfo(
        pcr_pid=pcr_pid,
        binary_search_ms=binary_search_ms,
        binary_search_iters=iterations,
        pcr_max_gap_bytes=pcr_max_gap_bytes,
        pcr_max_gap_ms=pcr_max_gap_ms,
        pcr_count_in_head=len(pcrs_in_head),
    )


def analyze_output(result: EncodeResult, ffprobe_binary: str) -> AnalysisResult:
    """
    エンコード結果に対してキーフレーム/PCR 解析を実行する

    以下を実施:
      - ffprobe で映像パケットとキーフレームをカウント
      - PMT から PCR_PID を取得
      - PCR 密度 (先頭 4 MB) を計測
      - PCR 二分探索 (cold cache) のベンチマーク

    Args:
        result (EncodeResult): 対象のエンコード結果
        ffprobe_binary (str): ffprobe バイナリの絶対パス (LIBRARY_PATH 経由)

    Returns:
        AnalysisResult: 解析結果
    """

    # 失敗した結果は解析しない
    if result.returncode != 0 or result.output_size == 0:
        return AnalysisResult(error='encoding failed')

    path = result.output_path

    # ffprobe で映像パケット一覧を取得 (キーフレームをカウントするため)
    try:
        ffprobe_result = subprocess.run(
            [
                ffprobe_binary, '-v', 'error',
                '-select_streams', 'v:0',
                '-show_packets',
                '-show_entries', 'packet=pts_time,flags',
                '-of', 'json',
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return AnalysisResult(error='ffprobe timeout')

    if ffprobe_result.returncode != 0:
        return AnalysisResult(
            error=f'ffprobe rc={ffprobe_result.returncode}: {ffprobe_result.stderr[:200]}',
        )

    try:
        ffprobe_json = json.loads(ffprobe_result.stdout)
        packets = ffprobe_json.get('packets', [])
    except json.JSONDecodeError as ex:
        return AnalysisResult(error=f'ffprobe json parse failed: {ex}')

    total_packets = len(packets)
    keyframes = sum(1 for p in packets if 'K' in p.get('flags', ''))
    first_pts = float(packets[0].get('pts_time', 0)) if packets else 0.0
    last_pts = float(packets[-1].get('pts_time', 0)) if packets else 0.0

    # PCR 解析 (biim を使う)
    try:
        pcr_info = analyze_pcr(path)
    except Exception as ex:
        return AnalysisResult(
            total_packets=total_packets,
            keyframes=keyframes,
            first_pts=first_pts,
            last_pts=last_pts,
            error=f'PCR analysis failed: {ex}',
        )

    return AnalysisResult(
        total_packets=total_packets,
        keyframes=keyframes,
        first_pts=first_pts,
        last_pts=last_pts,
        pcr_pid=pcr_info.pcr_pid,
        binary_search_ms=pcr_info.binary_search_ms,
        binary_search_iters=pcr_info.binary_search_iters,
        pcr_max_gap_bytes=pcr_info.pcr_max_gap_bytes,
        pcr_max_gap_ms=pcr_info.pcr_max_gap_ms,
        pcr_count_in_head=pcr_info.pcr_count_in_head,
    )


# ***** メイン *****

app = typer.Typer(add_completion=False)


@app.command(help='tsreplace + QSVEncC/NVEncC の複数パターン横断検証を実行する')
def main(
    input_path: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True, help='Input TS file (60i source).'),
    concurrency: int = typer.Option(3, '--concurrency', '-c', min=1, max=6, help='Number of concurrent encodes per codec group.'),
    only_codec: str | None = typer.Option(None, '--only-codec', help='Run only the specified codec (h264 or hevc).'),
    only_encoder: str | None = typer.Option(None, '--only-encoder', help='Run only the specified encoder (qsv or nvenc).'),
    only_fps: str | None = typer.Option(None, '--only-fps', help='Run only the specified fps mode (30p, 24p, or 60p).'),
) -> None:
    """エントリーポイント"""

    # tsreplace バイナリを PATH から解決する (環境依存の絶対パスを使わない)
    tsreplace_binary = shutil.which('tsreplace')
    if tsreplace_binary is None:
        typer.echo('ERROR: tsreplace not found in PATH. Install tsreplace first.', err=True)
        raise typer.Exit(code=1)

    # ffprobe は KonomiTV のサードパーティとして LIBRARY_PATH から取得する
    ffprobe_binary = LIBRARY_PATH['FFprobe']

    # 事前チェック: 各バイナリが存在するか
    qsvencc_binary = LIBRARY_PATH['QSVEncC']
    nvencc_binary = LIBRARY_PATH['NVEncC']
    for name, binary in [
        ('QSVEncC', qsvencc_binary),
        ('NVEncC', nvencc_binary),
        ('FFprobe', ffprobe_binary),
    ]:
        if not Path(binary).exists():
            typer.echo(f'ERROR: {name} binary not found: {binary}', err=True)
            raise typer.Exit(code=1)

    typer.echo(SEPARATOR)
    typer.echo(f'Input:       {input_path}')
    typer.echo(f'Size:        {input_path.stat().st_size / 1024 / 1024 / 1024:.2f} GB')
    typer.echo(f'Concurrency: {concurrency} per codec group')
    typer.echo(f'tsreplace:   {tsreplace_binary}')
    typer.echo(f'QSVEncC:     {qsvencc_binary}')
    typer.echo(f'NVEncC:      {nvencc_binary}')
    typer.echo(SEPARATOR)

    # 全 12 パターンを定義
    all_patterns: list[EncodePattern] = [
        EncodePattern(codec='h264', encoder='qsv', fps_mode='30p'),
        EncodePattern(codec='h264', encoder='qsv', fps_mode='24p'),
        EncodePattern(codec='h264', encoder='qsv', fps_mode='60p'),
        EncodePattern(codec='h264', encoder='nvenc', fps_mode='30p'),
        EncodePattern(codec='h264', encoder='nvenc', fps_mode='24p'),
        EncodePattern(codec='h264', encoder='nvenc', fps_mode='60p'),
        EncodePattern(codec='hevc', encoder='qsv', fps_mode='30p'),
        EncodePattern(codec='hevc', encoder='qsv', fps_mode='24p'),
        EncodePattern(codec='hevc', encoder='qsv', fps_mode='60p'),
        EncodePattern(codec='hevc', encoder='nvenc', fps_mode='30p'),
        EncodePattern(codec='hevc', encoder='nvenc', fps_mode='24p'),
        EncodePattern(codec='hevc', encoder='nvenc', fps_mode='60p'),
    ]

    # フィルタ (--only-codec / --only-encoder / --only-fps が指定されている場合)
    def _pattern_matches(pattern: EncodePattern) -> bool:
        if only_codec is not None and pattern.codec != only_codec:
            return False
        if only_encoder is not None and pattern.encoder != only_encoder:
            return False
        if only_fps is not None and pattern.fps_mode != only_fps:
            return False
        return True

    filtered_patterns = [p for p in all_patterns if _pattern_matches(p)]
    if not filtered_patterns:
        typer.echo('ERROR: no patterns match the given filters.', err=True)
        raise typer.Exit(code=1)

    # コーデックごとにグループ分け
    h264_patterns = [p for p in filtered_patterns if p.codec == 'h264']
    h265_patterns = [p for p in filtered_patterns if p.codec == 'hevc']

    all_results: list[EncodeResult] = []

    # フェーズ 1: H.264 系を並行実行
    if h264_patterns:
        typer.echo(f'\n{SEPARATOR}')
        typer.echo(f'PHASE 1: H.264 group ({len(h264_patterns)} patterns, concurrency={concurrency})')
        typer.echo(SEPARATOR)
        phase1_start = time.perf_counter()
        h264_results = run_patterns_in_batches(
            tsreplace_binary, input_path, h264_patterns, concurrency,
        )
        phase1_elapsed = time.perf_counter() - phase1_start
        typer.echo(f'\nPhase 1 complete in {phase1_elapsed:.1f} sec')
        all_results.extend(h264_results)

    # フェーズ 2: H.265 系を並行実行
    if h265_patterns:
        typer.echo(f'\n{SEPARATOR}')
        typer.echo(f'PHASE 2: H.265 group ({len(h265_patterns)} patterns, concurrency={concurrency})')
        typer.echo(SEPARATOR)
        phase2_start = time.perf_counter()
        h265_results = run_patterns_in_batches(
            tsreplace_binary, input_path, h265_patterns, concurrency,
        )
        phase2_elapsed = time.perf_counter() - phase2_start
        typer.echo(f'\nPhase 2 complete in {phase2_elapsed:.1f} sec')
        all_results.extend(h265_results)

    # フェーズ 3: 出力ファイルを解析 (ffprobe + PCR 二分探索)
    typer.echo(f'\n{SEPARATOR}')
    typer.echo('PHASE 3: Analyzing output files')
    typer.echo(SEPARATOR)
    analysis_map: dict[str, AnalysisResult] = {}
    for result in all_results:
        typer.echo(f'[{result.pattern.suffix}] Analyzing...')
        analysis = analyze_output(result, ffprobe_binary)
        analysis_map[result.pattern.suffix] = analysis
        if analysis.error is not None:
            typer.echo(f'[{result.pattern.suffix}]   ERROR: {analysis.error}')
        else:
            pcr_pid_str = hex(analysis.pcr_pid) if analysis.pcr_pid is not None else 'None'
            typer.echo(
                f'[{result.pattern.suffix}]   '
                f'packets={analysis.total_packets}, '
                f'keyframes={analysis.keyframes}, '
                f'duration={analysis.last_pts - analysis.first_pts:.1f}s, '
                f'pcr_pid={pcr_pid_str}, '
                f'pcr_gap_max={analysis.pcr_max_gap_bytes}B/{analysis.pcr_max_gap_ms:.1f}ms, '
                f'binsearch={analysis.binary_search_ms:.1f}ms ({analysis.binary_search_iters} iters)'
            )

    # サマリー出力
    typer.echo(f'\n{SEPARATOR}')
    typer.echo('SUMMARY')
    typer.echo(SEPARATOR)
    header = (
        f'{"Pattern":<20} {"Status":<10} {"EncTime":<10} {"Size(MB)":<10} '
        f'{"KFs":<6} {"PCR gap":<14} {"BinSearch":<14}'
    )
    typer.echo(header)
    typer.echo('-' * 90)
    for result in all_results:
        status = 'OK' if result.returncode == 0 else f'FAIL({result.returncode})'
        size_mb = result.output_size / 1024 / 1024
        analysis = analysis_map.get(result.pattern.suffix)
        if analysis is not None and analysis.error is None:
            kfs_str = str(analysis.keyframes)
            pcr_gap_str = f'{analysis.pcr_max_gap_bytes}B'
            bin_search_str = f'{analysis.binary_search_ms:.1f}ms/{analysis.binary_search_iters}it'
        else:
            kfs_str = '-'
            pcr_gap_str = '-'
            bin_search_str = '-'
        typer.echo(
            f'{result.pattern.suffix:<20} {status:<10} '
            f'{result.elapsed_seconds:<10.1f} {size_mb:<10.1f} '
            f'{kfs_str:<6} {pcr_gap_str:<14} {bin_search_str:<14}'
        )

    success_count = sum(1 for r in all_results if r.returncode == 0)
    typer.echo(f'\nEncoding success: {success_count}/{len(all_results)} patterns')

    full_success_count = sum(
        1 for r in all_results
        if r.returncode == 0
        and analysis_map.get(r.pattern.suffix) is not None
        and (analysis_map[r.pattern.suffix].error is None)
    )
    typer.echo(f'Full success (encode + PCR analysis): {full_success_count}/{len(all_results)}')

    if success_count != len(all_results):
        raise typer.Exit(code=1)


if __name__ == '__main__':
    app()
