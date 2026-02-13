import re
import sys
import tempfile
import time
import traceback
from contextlib import ExitStack
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Literal, TextIO

from tortoise import timezone

from app.constants import (
    KONOMITV_SERVER_LOG_PATH,
    LOGS_ARCHIVES_DIR,
    SERVER_LOG_ARCHIVE_RETENTION_DAYS,
)


# サーバーログの日付プレフィックスを抽出するための正規表現
# ログフォーマット例: [2025/12/17 16:33:58.880] INFO: Message
LOG_DATE_PATTERN = re.compile(r'^\[(\d{4}/\d{2}/\d{2}) \d{2}:\d{2}:\d{2}\.\d{3}\]')

# アーカイブファイル名から日付キー (YYYYMMDD) を抽出するための正規表現
ARCHIVE_FILE_PATTERN = re.compile(
    rf'^{re.escape(KONOMITV_SERVER_LOG_PATH.stem)}\.(\d{{8}}){re.escape(KONOMITV_SERVER_LOG_PATH.suffix)}$',
)


class DailyRotatingFileHandler(TimedRotatingFileHandler):
    """
    JST 基準で日次ローテーションを行うログハンドラー。
    """

    def __init__(
        self,
        filename: str | Path,
        encoding: str | None = None,
        retention_days: int | None = None,
    ) -> None:
        """
        ログハンドラーを初期化する。

        Args:
            filename (str | Path): ログファイルのパス
            encoding (str | None): ファイルエンコーディング
            retention_days (int | None): アーカイブ保持日数 (None の場合は無期限保持)
        """

        super().__init__(
            filename=filename,
            when='midnight',
            interval=1,
            backupCount=0,
            encoding=encoding,
            utc=False,
        )

        # 日次ローテーション用の命名規則を固定する
        ## TimedRotatingFileHandler の既定サフィックスではなく YYYYMMDD を使う
        self.suffix = '%Y%m%d'

        # ローテーション後の移動先を archives ディレクトリへ切り替える
        self.namer = self._namer

        # 後続の cleanup で使用する保持日数を保持しておく
        self.retention_days = retention_days

    @staticmethod
    def _namer(default_name: str) -> str:
        """
        ローテーション後のファイル名を archives ディレクトリ配下に変換する。

        Args:
            default_name (str): TimedRotatingFileHandler が生成するファイル名

        Returns:
            str: 変換後のアーカイブファイル名
        """

        date_suffix = default_name.rsplit('.', 1)[1]
        return str(GetArchiveFilePath(date_suffix))

    def doRollover(self) -> None:
        """
        日付変更時のローテーション処理を実行する。

        NOTE: doRollover は TimedRotatingFileHandler の既存メソッドのオーバーライドのため、
              あえて snake_case() ではなく camelCase() で命名されている。
        """

        # ローテーション対象時刻と現在時刻を決定する
        ## rollover_time は「前回の切り替え境界」を示す時刻
        current_time = int(time.time())
        rollover_time = self.rolloverAt - self.interval

        # ハンドラー設定に応じて、ローテーション対象日時の time tuple を取得する
        if self.utc is True:
            time_tuple = time.gmtime(rollover_time)
        else:
            time_tuple = time.localtime(rollover_time)
            dst_now = time.localtime(current_time)[-1]
            dst_then = time_tuple[-1]

            # DST（夏時間）境界を跨いだ場合の 1 時間ズレを補正する
            ## 日本は DST を採用していないため本来不要だが、標準実装と同じ補正ロジックを維持して安全性を確保する
            if dst_now != dst_then:
                dst_offset = 3600 if dst_now else -3600
                time_tuple = time.localtime(rollover_time + dst_offset)

        # ローテーション後に配置するアーカイブファイルパスを確定する
        archive_name = self.rotation_filename(self.baseFilename + '.' + time.strftime(self.suffix, time_tuple))
        archive_path = Path(archive_name)

        # 先に stream を閉じて、Windows を含む環境で rename が失敗しにくい状態にする
        if self.stream is not None:
            self.stream.close()
            # close() 後は stream を未オープン状態に戻しておく（標準実装の doRollover() と同等の挙動）
            # pyright の型定義では stream が TextIOWrapper 扱いのため、None 代入は reportAttributeAccessIssue になる
            self.stream = None  # type: ignore[reportAttributeAccessIssue]

        # ローテーション先ディレクトリを事前に用意する
        LOGS_ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)

        # 既に同名アーカイブがある場合は上書きせず、重複ローテーションを避ける
        if archive_path.exists() is False:
            try:
                self.rotate(self.baseFilename, archive_name)
            except OSError:
                # 同一ログファイルに複数ハンドラーが接続されている場合、Windows で共有違反が発生することがある
                ## 別ハンドラーが先にローテーションを完了したケースもあるため、例外時は警告を出さずに継続する
                pass

        # delay=False の場合は、次ログ書き込みに備えて stream を再オープンする
        if self.delay is False:
            self.stream = self._open()

        # 次回ローテーション時刻を再計算する
        self.rolloverAt = self.computeRollover(current_time)

        # ローカル操作性を優先し、アーカイブ側の権限を緩める
        ## pm2 などで root 実行されるケースでは、一般ユーザー権限でログの閲覧・削除ができない問題への対策
        for permission_target_path in (LOGS_ARCHIVES_DIR, archive_path):
            try:
                permission_target_path.chmod(0o777)
            # Windows を含む環境差異で権限変更に失敗しても、ローテーション成功自体は維持する
            except (NotImplementedError, OSError):
                continue

        # ローテーション完了後に期限切れアーカイブを整理する
        CleanupOldArchiveLogs(self.retention_days)


def GetArchiveFilePath(date_key: str) -> Path:
    """
    日付キー (YYYYMMDD) からアーカイブファイルのパスを生成する。

    Args:
        date_key (str): 日付キー（例: '20260212'）

    Returns:
        Path: アーカイブファイルのパス（例: logs/archives/KonomiTV-Server.20260212.log）
    """

    # アーカイブ命名規則を 1 箇所に集約して、生成と解析の不一致を防ぐ
    ## 例: KonomiTV-Server.log -> KonomiTV-Server.20260212.log
    return LOGS_ARCHIVES_DIR / f'{KONOMITV_SERVER_LOG_PATH.stem}.{date_key}{KONOMITV_SERVER_LOG_PATH.suffix}'


def CleanupOldArchiveLogs(retention_days: int | None) -> None:
    """
    保存期間を超えたアーカイブログを削除する。

    Args:
        retention_days (int | None): アーカイブ保持日数。None の場合は無期限保持。
    """

    # 保持日数が無効（未設定または 0 以下）の場合は、安全のため削除処理を行わない
    if retention_days is None or retention_days < 1:
        return

    # アーカイブディレクトリがまだ存在しない場合は、削除対象がないため即終了する
    if LOGS_ARCHIVES_DIR.exists() is False:
        return

    # JST 基準で削除閾値を算出する
    ## 例: retention_days=30 の場合、30 日より前の日付ファイルのみ削除する
    today_in_jst = timezone.now().date()
    delete_before_date = today_in_jst - timedelta(days=retention_days)

    # 命名規則に一致するアーカイブファイルのみを対象にクリーンアップする
    for archive_path in LOGS_ARCHIVES_DIR.glob(f'{KONOMITV_SERVER_LOG_PATH.stem}.*{KONOMITV_SERVER_LOG_PATH.suffix}'):
        match = ARCHIVE_FILE_PATTERN.match(archive_path.name)

        # 命名規則から外れるファイルは、他用途の可能性があるため触らない
        if match is None:
            continue

        try:
            archive_date = datetime.strptime(match.group(1), '%Y%m%d').date()
        except ValueError:
            # 日付として解釈できないファイル名は安全のためスキップする
            continue

        # 保存期間を超えたアーカイブのみ削除
        if archive_date < delete_before_date:
            try:
                archive_path.unlink()
            # パーミッション等で削除できない場合でも、他ファイルのクリーンアップは継続する
            except OSError:
                continue


def SplitServerLogByDate() -> None:
    """
    起動時にサーバーログを日付単位で分割する。

    サーバーログ内の各行を、行頭の日付プレフィックスに基づいて振り分ける。
    スタックトレースなど日付を持たない行は、直前に出現した日付と同じファイルへ書き出す。
    分割の成否にかかわらず、処理の最後に期限切れアーカイブのクリーンアップを実行する。
    """

    def PrintBootstrapLog(level: Literal['INFO', 'WARNING', 'ERROR'], message: str) -> None:
        """
        ロガー初期化前のフェーズで、Uvicorn 形式に寄せたログを標準エラー出力に出力する。

        Args:
            level (Literal['INFO', 'WARNING', 'ERROR']): ログレベル
            message (str): 出力するログメッセージ
        """

        # ロガー初期化前でも既存ログに近い見た目で観測できるよう、JST タイムスタンプ付きで出力する
        now_in_jst = timezone.now()
        date_time_str = now_in_jst.strftime('%Y/%m/%d %H:%M:%S')
        timestamp = f'{date_time_str}.{now_in_jst.microsecond // 1000:03d}'
        level_prefix = f'{level.upper()}:'.ljust(10)
        print(f'[{timestamp}] {level_prefix} {message}', file=sys.stderr)

    # 分割処理で使用する一時ファイルのパス
    ## 例外時のクリーンアップで参照するため、try ブロックの外で宣言する
    today_temp_path: Path | None = None

    try:
        # ======== Phase 1: 分割が必要かの事前判定 ========

        # ログファイルが存在しない場合は分割不要
        if KONOMITV_SERVER_LOG_PATH.exists() is False:
            return

        # ファイルサイズの取得を試みる
        ## サイズ取得に失敗する環境（権限不足・I/O エラー等）では分割処理を諦めて起動継続を優先する
        try:
            file_size = KONOMITV_SERVER_LOG_PATH.stat().st_size
        except OSError as ex:
            PrintBootstrapLog('ERROR', f'Failed to get server log file size: {ex}. Skip log split.')
            return

        # 空ファイルであれば分割対象は存在しない
        if file_size == 0:
            return

        # ======== Phase 2: 高速パス判定 ========

        # ログ本文に含まれる日付表記に合わせて、比較用の今日の日付文字列を JST で生成する
        today_str = timezone.now().date().strftime('%Y/%m/%d')

        # ログの先頭で最初に見つかる日付行が今日であれば、全行が今日のログとみなして分割をスキップする
        ## 通常の運用ではほとんどの起動がこのパスを通るため、全行パースのコストを回避できる
        try:
            with KONOMITV_SERVER_LOG_PATH.open(encoding='utf-8', errors='replace') as source_file:
                for source_line in source_file:
                    match = LOG_DATE_PATTERN.match(source_line)
                    # 最初に見つかった日付行のみで判定し、今日の日付であれば分割不要と判断する
                    if match is not None:
                        if match.group(1) == today_str:
                            return
                        break
        # 高速判定が失敗しても、分割本体を試せば復旧できるため WARNING のみに留める
        except OSError as ex:
            PrintBootstrapLog(
                'WARNING',
                f'Failed to pre-scan server log for fast path: {ex}. Continue full split.',
            )

        # ======== Phase 3: 日付別分割の実行 ========

        PrintBootstrapLog(
            'INFO',
            f'Splitting server log by date (file size: {file_size / 1024 / 1024:.1f} MB)...',
        )

        archive_entry_counts: dict[str, int] = {}
        archived_paths: set[Path] = set()

        try:
            # 複数ファイル（入力ログ・一時ファイル・複数アーカイブ）を安全に扱うため ExitStack を使う
            with ExitStack() as exit_stack:
                # 元のログファイルを読み取り用に開く
                source_file = exit_stack.enter_context(
                    KONOMITV_SERVER_LOG_PATH.open(encoding='utf-8', errors='replace'),
                )

                # 今日分のログを書き出す一時ファイルを作成する
                ## 分割完了後にアトミックに本体ログへ置換するため、同じディレクトリに一時ファイルを生成する
                today_temp_file = exit_stack.enter_context(
                    tempfile.NamedTemporaryFile(
                        mode='w',
                        encoding='utf-8',
                        dir=KONOMITV_SERVER_LOG_PATH.parent,
                        prefix='.KonomiTV-Server.today.',
                        suffix='.log.tmp',
                        delete=False,
                    ),
                )
                today_temp_path = Path(today_temp_file.name)

                # 日付ごとのアーカイブファイルハンドルを遅延生成するための辞書
                archive_files: dict[str, TextIO] = {}

                # current_date は「直近で観測した日付プレフィックス」を保持する
                ## スタックトレース行のような日付無し行も直前日付へ帰属できるようにする
                current_date: str | None = None

                # -------- ログ行の振り分けループ --------

                for source_line in source_file:
                    match = LOG_DATE_PATTERN.match(source_line)

                    # 日付プレフィックスを持つ行で帰属先日付を更新する
                    if match is not None:
                        current_date = match.group(1)

                    # 今日の日付の行、または日付が未確定の先頭行は今日分として扱う
                    if current_date is None or current_date == today_str:
                        today_temp_file.write(source_line)
                        continue

                    # 過去日付の行をアーカイブファイルに書き出す
                    date_key = current_date.replace('/', '')
                    archive_file = archive_files.get(date_key)

                    # 日付ごとのアーカイブファイルハンドルは初回アクセス時に遅延生成する
                    if archive_file is None:
                        archive_file_path = GetArchiveFilePath(date_key)
                        LOGS_ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)
                        archive_file = exit_stack.enter_context(archive_file_path.open('a', encoding='utf-8'))
                        archive_files[date_key] = archive_file
                        archived_paths.add(archive_file_path)

                    # アーカイブファイルに行を書き出す
                    archive_file.write(source_line)

                    # 日付プレフィックスを持つ行のみエントリとしてカウントする
                    ## スタックトレース等の継続行はカウントに含めない
                    if match is not None:
                        archive_entry_counts[date_key] = archive_entry_counts.get(date_key, 0) + 1

            # -------- ExitStack を抜けてすべてのファイルハンドルが閉じられた後の後処理 --------

            # 分割対象がなかった場合は一時ファイルを削除して終了
            if len(archived_paths) == 0:
                if today_temp_path is not None and today_temp_path.exists() is True:
                    today_temp_path.unlink()
                return

            # 今日分の一時ファイルを本体ログへアトミックに置換する
            if today_temp_path is not None:
                today_temp_path.replace(KONOMITV_SERVER_LOG_PATH)

            # 手作業でログ確認しやすいよう、生成したアーカイブに緩い権限を付与する
            ## pm2 などで root 実行されるケースでは、一般ユーザー権限でログの閲覧・削除ができない問題への対策
            for permission_target_path in [LOGS_ARCHIVES_DIR, *archived_paths]:
                try:
                    permission_target_path.chmod(0o777)
                # Windows を含む環境差異で権限変更に失敗しても、分割そのものは成功扱いとする
                except (NotImplementedError, OSError):
                    continue

            # 分割結果のサマリーをログ出力する
            archived_dates = sorted(archive_entry_counts.keys())
            if len(archived_dates) > 0:
                archived_summary = ', '.join(
                    f'{date_key} ({archive_entry_counts[date_key]} entries)' for date_key in archived_dates
                )
                PrintBootstrapLog(
                    'INFO',
                    f'Successfully split server log into {len(archived_dates)} archive(s): {archived_summary}',
                )

        # 分割全体で予期しない例外が起きた場合は、起動継続を優先してエラーのみ出力する
        ## 途中生成した一時ファイルが残ると次回処理のノイズになるため、可能な限り削除する
        except Exception as ex:
            PrintBootstrapLog('ERROR', f'Failed to split server log by date: {ex}')
            traceback.print_exc()
            if today_temp_path is not None and today_temp_path.exists() is True:
                try:
                    today_temp_path.unlink()
                except OSError:
                    pass

    # 分割の成否にかかわらず、期限切れアーカイブのクリーンアップを最後に実行する
    finally:
        CleanupOldArchiveLogs(SERVER_LOG_ARCHIVE_RETENTION_DAYS)
