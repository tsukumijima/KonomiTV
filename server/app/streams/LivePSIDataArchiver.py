
import asyncio
import time
from typing import AsyncGenerator, cast

from app.constants import LIBRARY_PATH


class LivePSIDataArchiver:


    def __init__(self, service_id: int) -> None:
        """
        ライブストリーミング (データ放送) 用 PSI/SI データアーカイバーを初期化する

        Args:
            service_id (int): 視聴対象のチャンネルのサービス ID
        """

        # 視聴対象のチャンネルのサービス ID
        self.service_id = service_id

        # psisiarc のプロセス
        self.psisiarc_process: asyncio.subprocess.Process | None = None

        # PSI/SI データのアーカイブデータを貯めるリスト
        self.psi_archive_list: list[bytes] = []

        # PSI/SI データのアーカイブデータの状態を管理する Condition
        self.psi_archive_list_condition = asyncio.Condition()

        # psisiarc のプロセスを再起動中かどうか
        self.is_restarting: bool = False


    @property
    def is_running(self) -> bool:
        """
        PSI/SI データアーカイバーが起動中かどうかを返す
        """

        return self.psisiarc_process is not None and self.psisiarc_process.returncode is None


    async def run(self) -> None:
        """
        PSI/SI データアーカイバーを起動する
        """

        # すでにリストにデータがある場合は、クリアしておく
        async with self.psi_archive_list_condition:
            if len(self.psi_archive_list) > 0:
                self.psi_archive_list.clear()
                self.psi_archive_list_condition.notify_all()  # 全ての待機中のタスクに通知

        # psisiarc のオプション
        # ref: https://github.com/xtne6f/psisiarc
        psisiarc_options = [
            # 事前定義されたオプションを追加する
            # 番組情報とデータ放送を抽出する
            '-r', 'arib-data',
            # 特定サービスのみを選択して出力するフィルタを有効にする
            ## 有効にすると、特定のストリームのみ PID を固定して出力される
            ## 視聴対象のチャンネルのサービス ID を指定する
            '-n ', str(self.service_id),
            # PCR (Program Clock Reference) を基準に一定間隔でアーカイブデータを出力する
            # 3秒間隔でアーカイブデータを出力する
            '-i', '3',
            # 標準入力から放送波を入力する
            '-',
            # 標準出力にアーカイブデータを出力する
            '-',
        ]

        # psisiarc を起動する
        self.psisiarc_process = await asyncio.subprocess.create_subprocess_exec(
            *[LIBRARY_PATH['psisiarc'], *psisiarc_options],
            stdin = asyncio.subprocess.PIPE,  # 放送波を入力
            stdout = asyncio.subprocess.PIPE,  # ストリーム出力
            stderr = asyncio.subprocess.STDOUT,  # ログ出力
        )

        # psisiarc のプロセスを再起動中でないことを示す
        if self.is_restarting is True:
            self.is_restarting = False

        # 起動時間のタイムスタンプ
        start_at = time.time()

        # 受信した PSI/SI アーカイブデータを Queue に貯める
        trailer_size: int = 0
        trailer_remain_size: int = 0
        while True:

            # psisiarc が終了している場合は終了する
            if self.psisiarc_process is None or self.psisiarc_process.returncode is not None:
                return

            # PSI/SI アーカイブデータを psisiarc から読み取る
            result = await self.__readPSIArchivedDataChunk(trailer_size, trailer_remain_size)
            if result is None:
                return
            psi_archive, trailer_size, trailer_remain_size = result

            # PSI/SI アーカイブデータをリストに追加する
            async with self.psi_archive_list_condition:
                self.psi_archive_list.append(psi_archive)
                self.psi_archive_list_condition.notify_all()  # 全ての待機中のタスクに通知

            # もし起動から15分以上経過している場合は、psisiarc を一旦終了して再起動する
            ## 再起動するタイミングでデータをリセットし、データが無尽蔵に増えていくのを防ぐ
            if time.time() - start_at > 60 * 15:
                await self.restart()
                return


    async def pushTSPacketData(self, packet: bytes) -> None:
        """
        LiveEncodingTask から生の放送波の MPEG2-TS パケットを受け取り、PSI/SI データアーカイバーに送信する
        LiveHLSSegmenter とは異なり、188 bytes ぴったりで送信する必要はない

        Args:
            packet (bytes): MPEG2-TS パケット
        """

        # psisiarc が起動していない・既に終了している場合は何もしない
        if self.psisiarc_process is None or cast(asyncio.StreamWriter, self.psisiarc_process.stdin).is_closing():
            return

        # psisiarc に TS パケットを送信する
        cast(asyncio.StreamWriter, self.psisiarc_process.stdin).write(packet)
        await cast(asyncio.StreamWriter, self.psisiarc_process.stdin).drain()


    async def getPSIArchivedData(self) -> AsyncGenerator[bytes, None]:
        """
        PSI/SI アーカイブデータをジェネレーターとして返す
        このメソッドは複数の非同期タスクから呼び出される可能性がある

        Yields:
            AsyncGenerator[bytes, None]: PSI/SI アーカイブデータ
        """

        # 既にリストにデータがある場合は、すべてのデータを返してから、最新のチャンクを待機する
        async with self.psi_archive_list_condition:
            if len(self.psi_archive_list) > 0:
                for psi_archive in self.psi_archive_list:
                    yield psi_archive

        while True:

            # psisiarc が終了している場合は終了する
            ## ただし、再起動中の場合は終了しない
            if (self.psisiarc_process is None or self.psisiarc_process.returncode is not None) and self.is_restarting is False:
                break

            # データの利用可能性を待つ
            async with self.psi_archive_list_condition:
                await self.psi_archive_list_condition.wait()

                # PSI/SI アーカイブデータが更新されたら、最新のチャンクを返す
                # 複数の非同期タスクすべてが同じデータを随時取得できるようにするため、
                # getPSIArchivedData() 内では PSI/SI アーカイブデータは常に読み取り専用である必要がある
                if len(self.psi_archive_list) > 0:
                    yield self.psi_archive_list[-1]


    async def destroy(self) -> None:
        """
        PSI/SI データアーカイバーを破棄する
        """

        # psisiarc を終了する
        if self.psisiarc_process is not None:
            try:
                self.psisiarc_process.kill()
            except Exception:
                pass

        # データをクリアする
        async with self.psi_archive_list_condition:
            self.psi_archive_list.clear()
            self.psi_archive_list_condition.notify_all()  # 全ての待機中のタスクに通知


    async def restart(self) -> None:
        """
        PSI/SI データアーカイバーを再起動する
        このメソッドは run() が終了するまで戻らないので注意
        """

        # 破棄してから再起動する
        self.is_restarting = True
        await self.destroy()
        await self.run()


    async def __readPSIArchivedDataChunk(self, trailer_size: int, trailer_remain_size: int) -> tuple[bytes, int, int] | None:
        """
        psisiarc からの出力ストリームから PSI/SI アーカイブデータ (.psc) を適切に読み取る
        EDCB Legacy WebUI の実装をそのまま Python に移植したもの (完全な形で移植してくれた ChatGPT (GPT-4) 先生に感謝！)
        ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-230212/ini/HttpPublic/legacy/view.lua#L128-L160

        Args:
            trailer_size (int): trailer のサイズ
            trailer_remain_size (int): trailer までの余りのサイズ

        Returns:
            tuple[bytes, int, int] | None: アーカイブデータ、次の trailer のサイズ、次の trailer までの余りのサイズ
        """

        def get_le_number(buffer: bytes, pos: int, len: int) -> int:
            return int.from_bytes(buffer[pos:pos+len], byteorder='little')

        if self.psisiarc_process is None:
            return None

        try:
            if trailer_size > 0:
                buffer = await cast(asyncio.StreamReader, self.psisiarc_process.stdout).readexactly(trailer_size)
                if len(buffer) != trailer_size:
                    return None

            buffer = await cast(asyncio.StreamReader, self.psisiarc_process.stdout).readexactly(32)
            if len(buffer) != 32:
                return None

            time_list_len = get_le_number(buffer, 10, 2)
            dictionary_len = get_le_number(buffer, 12, 2)
            dictionary_data_size = get_le_number(buffer, 16, 4)
            code_list_len = get_le_number(buffer, 24, 4)
            payload = b''
            payload_size = time_list_len * 4 + dictionary_len * 2 + ((dictionary_data_size + 1) // 2) * 2 + code_list_len * 2

            if payload_size > 0:
                payload = await cast(asyncio.StreamReader, self.psisiarc_process.stdout).readexactly(payload_size)
                if len(payload) != payload_size:
                    return None

            # Base64 のパディングを避けるため、トレーラを利用して buffer のサイズを 3 の倍数にする
            trailer_consume_size = (3 - (trailer_remain_size + len(buffer) + len(payload) + 2) % 3) % 3
            buffer = b'=' * trailer_remain_size + buffer + payload + b'=' * trailer_consume_size
            return buffer, 2 + (2 + len(payload)) % 4, 2 + (2 + len(payload)) % 4 - trailer_consume_size

        except asyncio.IncompleteReadError:
            return None
