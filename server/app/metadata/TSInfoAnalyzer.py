
import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from io import BufferedReader, BytesIO
from pathlib import Path
from typing import Any, Literal, cast

import ariblib
import ariblib.event
from ariblib.descriptors import (
    AudioComponentDescriptor,
    ServiceDescriptor,
    TSInformationDescriptor,
)
from ariblib.packet import payload, payload_unit_start_indicator, pid
from ariblib.sections import (
    ActualNetworkNetworkInformationSection,
    ActualStreamPresentFollowingEventInformationSection,
    ActualStreamServiceDescriptionSection,
    ProgramAssociationSection,
    ProgramMapSection,
    TimeOffsetSection,
)
from biim.mpeg2ts import ts

from app import logging, schemas
from app.constants import JST
from app.utils import ClosestMultiple, NormalizeToJSTDatetime
from app.utils.TSInformation import TSInformation


class TSInfoAnalyzer:
    """
    録画 TS ファイルや録画データ関連ファイルに含まれる番組情報を解析するクラス
    ariblib の開発者の youzaka 氏に感謝します
    """

    def __init__(
        self,
        recorded_video: schemas.RecordedVideo,
        end_ts_offset: int | None = None,
        preferred_service_id: int | None = None,
    ) -> None:
        """
        録画 TS ファイルや録画データ関連ファイルに含まれる番組情報を解析するクラスを初期化する

        Args:
            recorded_video (schemas.RecordedVideo): 録画ファイル情報を表すモデル
            end_ts_offset (int | None): 有効な TS データの終了位置 (バイト単位、ファイル後半がゼロ埋めされている場合に指定する)
            preferred_service_id (int | None): 優先的に使用する service_id (FFprobe などの外部解析結果から得られた値)
        """

        # 有効な TS データの終了位置 (EIT 解析時に必要)
        # 未指定時はファイルサイズをそのまま利用する
        if end_ts_offset is not None:
            self.end_ts_offset = end_ts_offset
        else:
            self.end_ts_offset = recorded_video.file_size

        self.recorded_video = recorded_video
        self.first_tot_timedelta = timedelta()
        self.last_tot_timedelta = timedelta()

        # 優先的に使用する service_id (外部から指定された場合)
        self.preferred_service_id = preferred_service_id

        # 録画ファイルが MPEG-TS 形式の場合
        if self.recorded_video.container_format == 'MPEG-TS':
            # TS ファイルを開く
            ## 188 * 10000 バイト (≒ 1.88MB) ごとに分割して読み込む
            ## 現状 ariblib は先頭が sync_byte でない or 途中で同期が壊れる (破損した TS パケットが存在する) TS ファイルを想定していないため、
            ## ariblib に入力する録画ファイルは必ず正常な TS ファイルである必要がある
            self.ts = ariblib.tsopen(self.recorded_video.file_path, chunk=10000)

        # それ以外の場合、存在すれば PSI/SI 書庫 (.psc) を読み込んで仮想 TS ファイルを作成する
        else:
            packets = bytearray()
            try:
                # 書庫があれば必要な PSI/SI セクションを取り出してインメモリの TS ファイルとして ariblib に入力する
                psc_path = Path(self.recorded_video.file_path).with_suffix('.psc')
                with open(psc_path, 'rb') as f:
                    # PID ごとの連続性指標
                    counters: dict[int, int] = {}
                    last_time_sec = 0.0
                    last_tot_time_sec: float | None = None

                    def callback(time_sec: float, pid: int, section: bytes):
                        nonlocal last_time_sec, last_tot_time_sec
                        last_time_sec = time_sec
                        if pid in (0x12, 0x26, 0x27):
                            # EIT は 20% の位置から 60 秒間だけ
                            if time_sec < self.recorded_video.duration * 0.2 or time_sec > self.recorded_video.duration * 0.2 + 60:
                                return True
                        elif pid == 0x14:
                            # 録画時刻の解析の精度を上げるため
                            if last_tot_time_sec is None:
                                self.first_tot_timedelta = timedelta(seconds = time_sec)
                            last_tot_time_sec = time_sec
                        else:
                            # TOT 以外は 60 秒間だけ
                            if time_sec > 60:
                                return True

                        i = 0
                        while i < len(section):
                            # TS パケットに変換
                            packets.append(0x47)
                            packets.append((0x40 if i == 0 else 0) | pid >> 8)
                            packets.append(pid & 0xff)
                            counters[pid] = (counters[pid] + 1) & 0x0f if pid in counters else 0
                            packets.append(0x10 | counters[pid])
                            if i == 0:
                                packets.append(0)
                            while len(packets) % 188 != 0 and i < len(section):
                                packets.append(section[i])
                                i += 1
                            while len(packets) % 188 != 0:
                                packets.append(0xff)
                        return True

                    # PAT, NIT, SDT, TOT, EIT を取り出す
                    if not self.__readPSIData(f, [0x00, 0x10, 0x11, 0x14, 0x12, 0x26, 0x27], callback):
                        logging.warning(f'{psc_path}: File contents may be invalid.')
                    if last_tot_time_sec is not None:
                        self.last_tot_timedelta = timedelta(seconds = last_time_sec - last_tot_time_sec)
            except Exception:
                pass

            # TODO: 物理ファイル以外を受け取れるよう ariblib を変更すべき
            # このやり方は ariblib の内部実装を仮定しているのでよくない
            class TransportStreamFileWorkaround(ariblib.TransportStreamFile):
                def __init__(self, stream: Any):
                    BufferedReader.__init__(self, stream)
                    self.chunk_size = 1
                    self._callbacks = dict()

            # コンストラクタは失敗しない設計なので packets が空でも入力する
            # ここで self.end_ts_offset に 0 がセットされた時、TSInfoAnalyzer.analyze() は常に None を返す
            self.ts = TransportStreamFileWorkaround(BytesIO(packets))
            self.end_ts_offset = len(packets)


    def analyze(self) -> schemas.RecordedProgram | None:
        """
        録画 TS ファイルや録画データ関連ファイルに含まれる番組情報を解析する

        Returns:
            schemas.RecordedProgram:  録画番組情報（中に録画ファイル情報・チャンネル情報が含まれる）を表すモデル
                (サービスまたは番組情報が取得できなかった場合は None)
        """

        # 録画ファイルが MPEG-TS 形式ではなく、かつ PSI/SI の書庫がなかった場合
        # 録画番組情報の取得は不可能なため None を返す
        if self.recorded_video.container_format != 'MPEG-TS' and self.end_ts_offset == 0:
            return None

        # サービス (チャンネル) 情報を取得
        channel = self.__analyzeSDTInformation()
        if channel is None:
            logging.warning(f'{self.recorded_video.file_path}: Channel information not found.')
            return None

        # 録画番組情報のモデルを作成
        ## EIT[p/f] のうち、現在と次の番組情報を両方取得した上で、録画マージンを考慮してどちらの番組を録画したかを判定する
        recorded_program_present = self.__analyzeEITInformation(channel, is_following=False)
        recorded_program_following = self.__analyzeEITInformation(channel, is_following=True)
        ## 通常まず発生し得ないが、どちらかの番組情報が取得できなかった場合は正常に判定できないため None を返す
        if recorded_program_present is None or recorded_program_following is None:
            return None

        # 録画開始時刻と次の番組の開始時刻を比較して、もし差が0〜1分以内なら次の番組情報を利用する
        ## 録画ファイルのサイズ全体の 20% の位置にシークしてから番組情報を取得しているため、基本的には現在の番組情報を使うことになるはず
        ## シークした位置が録画開始マージン範囲（=録画対象の番組の前番組）だった場合のみ、次の番組情報が利用される
        ## 録画開始マージンは通常 5~10 秒程度で、長くても1分以内に収まるはず
        if (self.recorded_video.recording_start_time is not None and
            timedelta(minutes=0) <= (recorded_program_following.start_time - self.recorded_video.recording_start_time) <= timedelta(minutes=1)):
            recorded_program = recorded_program_following
        else:
            recorded_program = recorded_program_present

        # 選択された番組情報の duration が 0 の場合は現在/次の両方とも正しい番組情報を取得できなかったことを意味するので、None を返す
        # このとき番組開始時刻・番組終了時刻は 1970-01-01 09:00:00 になっているはず
        if recorded_program.duration == 0.0:
            logging.warning(f'{self.recorded_video.file_path}: Program information not found.')
            return None

        # 録画ファイル情報・チャンネル情報を紐付け
        recorded_program.recorded_video = self.recorded_video
        recorded_program.channel = channel

        return recorded_program


    def analyzeRecordingTime(self) -> tuple[datetime, datetime] | None:
        """
        TOT (Time Offset Table) から録画開始時刻と録画終了時刻を解析する
        このメソッドは MPEG-TS / PSI/SI 書庫 (.psc) の両方に対応する

        Returns:
            tuple[datetime, datetime]: 録画開始時刻と録画終了時刻 (取得できなかった場合は None)
        """

        # MPEG-TS の場合: ariblib.packet のユーティリティと TimeOffsetSection を使って単一パスで解析する
        if self.recorded_video.container_format == 'MPEG-TS':
            try:
                # 誤動作防止のため必ず最初にシークを戻す
                self.ts.seek(0)

                buffer = bytearray()
                first_pcr_sec: float | None = None
                current_pcr_sec: float | None = None
                # PSI セクション開始時点 (PUSI) の PCR 値を保持し、そのセクションに対する経過時間算出に用いる
                pcr_at_section_start_sec: float | None = None

                # end_ts_offset 以降はゼロ埋めである可能性が高いため、読み取りを制限する
                read_bytes = 0
                while True:
                    packet = self.ts.read(ts.PACKET_SIZE)
                    if packet is None or len(packet) < ts.PACKET_SIZE:
                        break
                    read_bytes += ts.PACKET_SIZE
                    if read_bytes > self.end_ts_offset:
                        break

                    # PCR を追跡
                    pcr_val = ts.pcr(packet)
                    if pcr_val is not None:
                        current_pcr_sec = pcr_val / ts.HZ
                        if first_pcr_sec is None:
                            first_pcr_sec = current_pcr_sec

                    # TOT (PID 0x14) のセクション組み立て
                    if pid(packet) != 0x14:
                        continue

                    prev, current = payload(packet)
                    if payload_unit_start_indicator(packet):
                        # まず、直前まで構築していたセクションを prev で完結させる
                        if buffer:
                            buffer.extend(prev)
                        # セクション長に従い切り出して TimeOffsetSection として解釈
                        while buffer and buffer[0] != 0xFF:
                            try:
                                if buffer[0] == 0x73:  # TimeOffsetSection の table_id
                                    section = TimeOffsetSection(buffer[:])
                                    if section.isfull():
                                        # 経過時間は「当該セクションの開始時 PCR - 最初の PCR」で算出する
                                        if (first_pcr_sec is not None) and (pcr_at_section_start_sec is not None):
                                            elapsed = max(float(pcr_at_section_start_sec) - float(first_pcr_sec), 0.0)
                                            assert section.JST_time is not None
                                            jst_time = NormalizeToJSTDatetime(section.JST_time)
                                            recording_start_time = jst_time - timedelta(seconds=elapsed)
                                            recording_end_time = recording_start_time + timedelta(seconds=self.recorded_video.duration)
                                            return (recording_start_time, recording_end_time)
                                # 次セクションへ
                                next_start = ((buffer[1] & 0x0F) << 8 | buffer[2]) + 3
                                buffer[:] = buffer[next_start:]
                            except Exception:
                                break
                        # 新しいセクション (current) を開始する。開始時点の PCR を保存する
                        buffer[:] = current
                        pcr_at_section_start_sec = current_pcr_sec
                    elif not buffer:
                        continue
                    else:
                        buffer.extend(current)

                # 残ったバッファを片付ける
                if buffer and buffer[0] == 0x73:
                    try:
                        section = TimeOffsetSection(buffer[:])
                        if section.isfull():
                            # ファイル末尾でセクションが完結した場合も、当該セクション開始時の PCR を使う
                            if (first_pcr_sec is None) or (pcr_at_section_start_sec is None):
                                pass
                            else:
                                elapsed = max(float(pcr_at_section_start_sec) - float(first_pcr_sec), 0.0)
                                assert section.JST_time is not None
                                jst_time = NormalizeToJSTDatetime(section.JST_time)
                                recording_start_time = jst_time - timedelta(seconds=elapsed)
                                recording_end_time = recording_start_time + timedelta(seconds=self.recorded_video.duration)
                                return (recording_start_time, recording_end_time)
                    except Exception:
                        pass

            except Exception as ex:
                logging.warning(f'{self.recorded_video.file_path}: Failed to analyze TOT from TS:', exc_info=ex)
                return None

            return None

        # それ以外の場合、存在すれば PSI/SI 書庫 (.psc) から作成された仮想 TS ファイルを使って録画開始時刻と録画終了時刻を解析する
        else:
            # 誤動作防止のため必ず最初にシークを戻す
            self.ts.seek(0)

            # TOT (Time Offset Table) を抽出
            first_tot_time: datetime | None = None
            last_tot_time: datetime | None = None
            for tot in self.ts.sections(TimeOffsetSection):
                if first_tot_time is None:
                    first_tot_time = NormalizeToJSTDatetime(tot.JST_time)
                last_tot_time = NormalizeToJSTDatetime(tot.JST_time)

            if first_tot_time is None or last_tot_time is None:
                return None

            return (first_tot_time - self.first_tot_timedelta, last_tot_time + self.last_tot_timedelta)


    def __analyzeSDTInformation(self) -> schemas.Channel | None:
        """
        TS 内の SDT (Service Description Table) からサービス（チャンネル）情報を解析する
        PAT (Program Association Table) と NIT (Network Information Table) からも補助的に情報を取得する

        Returns:
            schemas.Channel: サービス（チャンネル）情報を表すモデル (サービス情報が取得できなかった場合は None)
        """

        # 誤動作防止のため必ず最初にシークを戻す
        self.ts.seek(0)

        # 必要な情報を一旦変数として保持
        transport_stream_id: int | None = None
        service_id: int | None = None
        network_id: int | None = None
        channel_type: Literal['GR', 'BS', 'CS', 'CATV', 'SKY', 'BS4K'] | None = None
        channel_name: str | None = None
        remocon_id: int | None = None

        # PAT (Program Association Table) からサービス ID が取得できるまで繰り返し処理
        service_id_order: list[int] = []
        service_pmt_pid_map: dict[int, int] = {}
        for pat in self.ts.sections(ProgramAssociationSection):
            # トランスポートストリーム ID (TSID) を取得
            transport_stream_id = int(pat.transport_stream_id)

            # サービス ID と PMT PID を取得
            ## program_number は service_id と等しい
            for pat_pid in pat.pids:
                if pat_pid.program_number:
                    service_id = int(pat_pid.program_number)
                    service_id_order.append(service_id)
                    service_pmt_pid_map[service_id] = int(pat_pid.program_map_PID)

            # 最初に見つかった PAT を使う
            if len(service_id_order) > 0:
                break

        if len(service_id_order) == 0:
            logging.warning(f'{self.recorded_video.file_path}: service_id not found.')
            return None

        # 外部から preferred_service_id が指定されていて、PAT に含まれている場合はそれを優先的に使用
        ## FFprobe などで実際にストリームが存在する service_id が事前に判明している場合に使用される
        if self.preferred_service_id is not None and self.preferred_service_id in service_id_order:
            service_id = self.preferred_service_id
            logging.debug(
                f'{self.recorded_video.file_path}: Using preferred service_id {service_id} from external analysis.'
            )
        # 複数サービスが存在する場合は、映像・音声 PID の出現頻度から正しい service_id を推定する
        elif len(service_id_order) > 1:
            selected_service_id = self.__selectServiceIdByPidFrequency(
                service_id_order = service_id_order,
                service_pmt_pid_map = service_pmt_pid_map,
            )
            if selected_service_id is not None:
                service_id = selected_service_id
            else:
                # 推定できなかった場合は、PAT に最初に出現した service_id を採用する
                service_id = service_id_order[0]
        else:
            service_id = service_id_order[0]

        # TS から SDT (Service Description Table) を抽出
        for sdt in self.ts.sections(ActualStreamServiceDescriptionSection):
            # ネットワーク ID とサービス種別 (=チャンネルタイプ) を取得
            network_id = int(sdt.original_network_id)
            network_type = TSInformation.getNetworkType(network_id)
            if network_type == 'OTHER':
                logging.warning(f'{self.recorded_video.file_path}: Unknown network_id: {network_id}')
                return None
            channel_type = network_type  # ここで型が Literal['GR', 'BS', 'CS', 'CATV', 'SKY', 'BS4K'] に絞り込まれる
            # SDT に含まれるサービスごとの情報を取得
            for service in sdt.services:
                # service_id が PAT から抽出したものと一致した場合のみ
                # CS の場合同じ TS の中に複数のチャンネルが含まれている事があり、録画する場合は基本的に他のチャンネルは削除される
                # そうすると ffprobe で確認できるがサービス情報や番組情報だけ残ってしまい、別のチャンネルの番組情報になるケースがある
                # PAT にはそうした削除済みのチャンネルは含まれていないので、正しいチャンネルの service_id を抽出できる
                if service.service_id == service_id:
                    # SDT から得られる ServiceDescriptor 内の情報からチャンネル名を取得
                    for sd in service.descriptors[ServiceDescriptor]:
                        channel_name = TSInformation.formatString(sd.service_name)
                        break
                    else:
                        continue
                    break
            else:
                continue
            break
        if network_id is None:
            logging.warning(f'{self.recorded_video.file_path}: network_id not found.')
            return None
        if channel_type is None:
            logging.warning(f'{self.recorded_video.file_path}: channel_type not found.')
            return None
        if channel_name is None:
            logging.warning(f'{self.recorded_video.file_path}: channel_name not found.')
            return None

        # リモコン番号を取得
        if channel_type == 'GR':
            ## 地デジ: TS から NIT (Network Information Table) を抽出
            for nit in self.ts.sections(ActualNetworkNetworkInformationSection):
                # NIT に含まれるトランスポートストリームごとの情報を取得
                for transport_stream in nit.transport_streams:
                    # NIT から得られる TSInformationDescriptor 内の情報からリモコンキー ID を取得
                    # 地デジのみで、BS には TSInformationDescriptor 自体が存在しない
                    for ts_information in transport_stream.descriptors.get(TSInformationDescriptor, []):
                        remocon_id = int(ts_information.remote_control_key_id)
                        break
                    break
                else:
                    continue
                break
            if remocon_id is None:
                remocon_id = 0  # リモコン番号を取得できなかった際は 0 が自動設定される
        else:
            ## それ以外: 共通のリモコン番号取得処理を実行
            remocon_id = TSInformation.calculateRemoconID(channel_type, service_id)

        # チャンネル番号を算出
        channel_number = asyncio.run(TSInformation.calculateChannelNumber(
            channel_type,
            network_id,
            service_id,
            remocon_id,
        ))

        # チャンネル ID を生成
        channel_id = f'NID{network_id}-SID{service_id:03d}'

        # 表示用チャンネルID = チャンネルタイプ(小文字)+チャンネル番号
        display_channel_id = channel_type.lower() + channel_number

        # チャンネル情報を表すモデルを作成
        channel = schemas.Channel(
            id = channel_id,
            display_channel_id = display_channel_id,
            network_id = network_id,
            service_id = service_id,
            transport_stream_id = transport_stream_id,
            remocon_id = remocon_id,
            channel_number = channel_number,
            type = channel_type,
            name = channel_name,
        )

        # サブチャンネルかどうかを算出
        channel.is_subchannel = TSInformation.calculateIsSubchannel(channel.type, channel.service_id)

        # ラジオチャンネルにはなり得ない (録画ファイルのバリデーションの時点で映像と音声があることを確認している)
        channel.is_radiochannel = False

        # 録画ファイル内の情報として含まれているだけのチャンネルなので（現在視聴できるとは限らない）、is_watchable を False に設定
        ## もし視聴可能な場合はすでに channels テーブルにそのチャンネルのレコードが存在しているはずなので、そちらが優先される
        channel.is_watchable = False

        return channel


    def __analyzeEITInformation(self, channel: schemas.Channel, is_following: bool = False) -> schemas.RecordedProgram | None:
        """
        TS 内の EIT (Event Information Table) から番組情報を取得する
        チャンネル情報（サービス ID も含まれる）が必須な理由は、CS など複数サービスを持つ TS で
        意図しないチャンネルの番組情報が取得される問題を防ぐため

        Args:
            channel (schemas.Channel): チャンネル情報を表すモデル
            is_following (bool): 次の番組情報を取得するかどうか (デフォルト: 現在の番組情報)

        Returns:
            schemas.RecordedProgram | None: 録画番組情報を表すモデル、または取得に失敗した場合は None
        """

        if is_following is True:
            eit_section_number = 1
        else:
            eit_section_number = 0

        # 誤動作防止のため必ず最初にシークを戻す
        if self.recorded_video.container_format == 'MPEG-TS':
            # MPEG-TS 形式の場合、有効な TS データの終了位置から換算して 20% の位置にシークする
            # (正確には TS パケットサイズに合わせて 188 の倍数になるように調整している)
            # 先頭にシークすると録画開始マージン分のデータを含んでしまうため、大体録画開始マージン分を除いた位置から始める
            # 極端に録画開始マージンが大きいか番組長が短い録画でない限り、録画対象の番組が放送されているタイミングにシークできるはず
            # 例えば30分10秒の録画 (前後5秒が録画マージン) の場合、全体の 20% の位置にシークすると大体6分2秒の位置になる
            # 生の録画データはビットレートが一定のため、シーンによって大きくデータサイズが変動することはない
            # 録画中はファイルアロケーションの関係でファイル後半がゼロ埋めされている場合があるため、ファイルサイズではなく end_ts_offset を使う必要がある
            self.ts.seek(ClosestMultiple(int(self.end_ts_offset * 0.2), ts.PACKET_SIZE))
        else:
            # MPEG-TS 形式ではない場合、PSI/SI 書庫から生成した仮想 TS ファイルの先頭にシークする
            self.ts.seek(0)

        # 必要な情報を一旦変数として保持
        event_id: int | None = None
        title: str | None = None
        description: str | None = None
        detail: dict[str, str] | None = None
        start_time: datetime | None = None
        end_time: datetime | None = None
        duration: float | None = None
        is_free: bool | None = None
        genres: list[schemas.Genre] | None = None
        primary_audio_type: str | None = None
        primary_audio_language: str | None = None
        secondary_audio_type: str | None = None
        secondary_audio_language: str | None = None

        # TS から EIT (Event Information Table) を抽出
        count: int = 0
        corrupted_events: int = 0  # 破損したイベント数をカウント
        for eit in self.ts.sections(ActualStreamPresentFollowingEventInformationSection):

            # section_number と service_id が一致したときだけ
            # サービス ID が必要な理由は、CS などで同じトランスポートストリームに含まれる別チャンネルの番組情報になることを防ぐため
            if eit.section_number == eit_section_number and eit.service_id == channel.service_id:
                # TSID / ONID も一致する場合のみ採用する
                ## EIT は service_id だけでなく TSID / ONID も持つため、誤検出を避けるため一致条件に含める
                if channel.transport_stream_id is not None and eit.transport_stream_id != channel.transport_stream_id:
                    continue
                if channel.network_id is not None and eit.original_network_id != channel.network_id:
                    continue

                # EIT から得られる各種 Descriptor 内の情報を取得
                # ariblib.event が各種 Descriptor のラッパーになっていたのでそれを利用
                for event_data in eit.events:
                    try:
                        # EIT 内のイベントを取得
                        event: Any = ariblib.event.Event(eit, event_data)
                    except (IndexError, ValueError, TypeError, AttributeError) as ex:
                        # 破損したイベントをスキップ
                        corrupted_events += 1
                        if corrupted_events <= 20:  # 20個までは許容
                            logging.debug(f'{self.recorded_video.file_path}: Skipped corrupted event #{corrupted_events}:', exc_info=ex)
                            continue
                        else:
                            # 破損イベントが多すぎる場合は諦める
                            logging.warning(f'{self.recorded_video.file_path}: Too many corrupted events ({corrupted_events}), abandoning this position.')
                            return None

                    # デフォルトで毎回設定されている情報
                    ## イベント ID
                    event_id = int(event.event_id)
                    ## 番組開始時刻 (タイムゾーンを日本時間 (+9:00) に設定)
                    ## 注意: present の duration が None (終了時間未定) の場合のみ、following の start_time が None になることがある
                    if event.start_time is not None:
                        start_time = NormalizeToJSTDatetime(cast(datetime, event.start_time))
                    ## 番組長 (秒)
                    ## 注意: 臨時ニュースなどで放送時間未定の場合は None になる
                    if event.duration is not None:
                        duration = cast(timedelta, event.duration).total_seconds()
                    ## 番組終了時刻を start_time と duration から算出
                    if start_time is not None and duration is not None:
                        end_time = start_time + timedelta(seconds=duration)
                    ## ARIB TR-B15 第三分冊 (https://vs1p.manualzilla.com/store/data/006629648.pdf)
                    ## free_CA_mode が 1 のとき有料番組、0 のとき無料番組だそう
                    ## bool に変換した後、真偽を反転させる
                    is_free = not bool(event.free_CA_mode)

                    # 番組名, 番組概要 (ShortEventDescriptor)
                    if hasattr(event, 'title') and hasattr(event, 'desc'):
                        ## 番組名
                        title = TSInformation.formatString(event.title)
                        ## 番組概要
                        description = TSInformation.formatString(event.desc)

                    # 番組詳細情報 (ExtendedEventDescriptor)
                    if hasattr(event, 'detail'):
                        detail = {}
                        # 番組詳細テキストから取得した、見出しと本文の辞書ごとに
                        for head, text in cast(dict[str, str], event.detail).items():
                            # 見出しと本文
                            ## 見出しのみ ariblib 側で意図的に重複防止のためのタブ文字付加が行われる場合があるため、
                            ## strip() では明示的に半角スペースと改行のみを指定している
                            head_hankaku = TSInformation.formatString(head).replace('◇', '').strip(' \r\n')  # ◇ を取り除く
                            ## ないとは思うが、万が一この状態で見出しが衝突しうる場合は、見出しの後ろにタブ文字を付加する
                            while head_hankaku in detail.keys():
                                head_hankaku += '\t'
                            ## 見出しが空の場合、固定で「番組内容」としておく
                            if head_hankaku == '':
                                head_hankaku = '番組内容'
                            text_hankaku = TSInformation.formatString(text).strip()
                            detail[head_hankaku] = text_hankaku
                            # 番組概要が空の場合、番組詳細の最初の本文を概要として使う
                            # 空でまったく情報がないよりかは良いはず
                            if description is not None and description.strip() == '':
                                description = text_hankaku

                    ## ジャンル情報 (ContentDescriptor)
                    if hasattr(event, 'genre') and hasattr(event, 'subgenre') and hasattr(event, 'user_genre'):
                        genres = []
                        for index, _ in enumerate(event.genre):  # ジャンルごとに
                            # major … 大分類
                            # middle … 中分類
                            genre_dict: schemas.Genre = {
                                'major': event.genre[index].replace('／', '・'),
                                'middle': event.subgenre[index].replace('／', '・'),
                            }
                            # BS/地上デジタル放送用番組付属情報がジャンルに含まれている場合、user_genre から拡張情報を取得する
                            # たとえば「中止の可能性あり」や「延長の可能性あり」といった情報が取れる
                            if genre_dict['major'] == '拡張':
                                if genre_dict['middle'] == 'BS/地上デジタル放送用番組付属情報':
                                    genre_dict['middle'] = event.user_genre[index]
                                # 「拡張」はあるがBS/地上デジタル放送用番組付属情報でない場合はなんの値なのかわからないのでパス
                                else:
                                    continue
                            # ジャンルを追加
                            genres.append(genre_dict)

                    # 音声情報 (AudioComponentDescriptor)
                    ## 主音声情報
                    if hasattr(event, 'audio'):
                        ## 主音声の種別
                        primary_audio_type = str(event.audio)
                    ## 副音声情報
                    if hasattr(event, 'second_audio'):
                        ## 副音声の種別
                        secondary_audio_type = str(event.second_audio)
                    ## 主音声・副音声の言語
                    ## event クラスには用意されていないので自前で取得する
                    for acd in event_data.descriptors.get(AudioComponentDescriptor, []):
                        if bool(acd.main_component_flag) is True:
                            ## 主音声の言語
                            primary_audio_language = TSInformation.getISO639LanguageCodeName(acd.ISO_639_language_code)
                            ## デュアルモノのみ
                            if primary_audio_type == '1/0+1/0モード(デュアルモノ)':
                                if bool(acd.ES_multi_lingual_flag) is True:
                                    primary_audio_language += '+' + \
                                        TSInformation.getISO639LanguageCodeName(acd.ISO_639_language_code_2)
                                else:
                                    primary_audio_language += '+副音声'  # 副音声で固定
                        else:
                            ## 副音声の言語
                            secondary_audio_language = TSInformation.getISO639LanguageCodeName(acd.ISO_639_language_code)
                            ## デュアルモノのみ
                            if secondary_audio_type == '1/0+1/0モード(デュアルモノ)':
                                if bool(acd.ES_multi_lingual_flag) is True:
                                    secondary_audio_language += '+' + \
                                        TSInformation.getISO639LanguageCodeName(acd.ISO_639_language_code_2)
                                else:
                                    secondary_audio_language += '+副音声'  # 副音声で固定

                    # EIT から取得できるすべての情報を取得できたら抜ける
                    ## 一回の EIT ですべての情報 (Descriptor) が降ってくるとは限らない
                    ## 副音声情報は副音声がない番組では当然取得できないので、除外している
                    if all([
                        event_id is not None,
                        title is not None,
                        description is not None,
                        detail is not None,
                        start_time is not None,
                        end_time is not None,
                        duration is not None,
                        is_free is not None,
                        genres is not None,
                        primary_audio_type is not None,
                        primary_audio_language is not None,
                    ]):
                        break

                else: # 多重ループを抜けるトリック
                    continue
                break

            # カウントを追加
            count += 1

            # ループが 100 回を超えたら、番組詳細とジャンルの初期値を設定する
            # 稀に番組詳細やジャンルが全く設定されていない番組があり、存在しない情報を探して延々とループするのを避けるため
            if count > 100:
                if detail is None:
                    detail = {}
                if genres is None:
                    genres = []

            # ループが 2000 回を超えたら (≒20回シークしても放送時間が確定しなかったら) 、タイムアウトでループを抜ける
            if count > 2000:
                p_or_f = 'following' if is_following is True else 'present'
                logging.warning(f'{self.recorded_video.file_path}: Analyzing EIT information ({p_or_f}) timed out.')
                break

            # MPEG-TS 形式の場合、ループが 100 で割り切れるたびに現在の位置から 188MB シークする
            ## ループが 100 以上に到達しているときはおそらく放送時間が未定の番組なので、放送時間が確定するまでシークする
            ## PSI/SI 書庫から生成した仮想 TS ファイルには映像/音声が含まれていないため、それ以外の形式の場合はシークしない
            if self.recorded_video.container_format == 'MPEG-TS' and count % 100 == 0:
                self.ts.seek(ts.PACKET_SIZE * 1000000, 1)  # 188MB (188 * 1000000 バイト) 進める

        # この時点でタイトルを取得できていない場合（タイムアウト発生時）、フォールバックとして拡張子を除いたファイル名をフォーマットした上でタイトルとして使用する
        if title is None:
            title = TSInformation.formatString(Path(self.recorded_video.file_path).stem)

        # この時点で番組開始時刻・番組終了時刻を取得できていない場合、適当なダミー値を設定する
        ## start_time が None になる組み合わせは「現在の番組の終了時間が未定」かつ「次の番組情報を取得しようとした」ときか、
        ## 録画ファイルが短すぎて EIT のパースに失敗した場合のみ
        ## 番組情報としては全く使い物にならないし、基本現在の番組情報を使わせるようにしたいので、後続の処理で使われないような値を設定する
        if start_time is None and end_time is None:
            start_time = datetime(1970, 1, 1, 9, tzinfo=JST)
            end_time = datetime(1970, 1, 1, 9, tzinfo=JST)
            duration = 0.0

        # 番組開始時刻が取得できないが番組終了時刻のみ取得できる状況は仕様上発生し得ない
        assert start_time is not None

        # この時点で番組終了時刻のみを取得できていない場合、フォールバックとして録画終了時刻を利用する
        ## さらにまずあり得ないとは思うが、もし録画終了時刻が取得できていない場合は、番組開始時刻 + 動画長を利用する
        if end_time is None:
            if self.recorded_video.recording_end_time is not None:
                end_time = self.recorded_video.recording_end_time
                duration = (end_time - start_time).total_seconds()
            else:
                end_time = start_time + timedelta(seconds=self.recorded_video.duration)
                duration = self.recorded_video.duration
        assert duration is not None

        # 録画番組情報を表すモデルを作成 (ここでは確実に値を設定できるフィールドのみ設定)
        recorded_program = schemas.RecordedProgram(
            recorded_video = self.recorded_video,
            channel = channel,
            network_id = channel.network_id,
            service_id = channel.service_id,
            event_id = event_id,
            title = title,
            start_time = start_time,
            end_time = end_time,
            duration = duration,
            # 必須フィールドのため作成日時・更新日時は適当に現在時刻を入れている
            # この値は参照されず、DB の値は別途自動生成される
            created_at = datetime.now(tz=JST),
            updated_at = datetime.now(tz=JST),
        )

        # 以下のフィールドは、対応するデータを取得できなかった場合に Pydantic モデルに設定されているデフォルト値が使われる
        ## データが取得できなかったとしたら、そのデータが EIT に含まれていないが、タイムアウトした場合に限られるはず
        if description is not None:
            recorded_program.description = description
        if detail is not None:
            recorded_program.detail = detail
        if is_free is not None:
            recorded_program.is_free = is_free
        if genres is not None:
            recorded_program.genres = genres
        if primary_audio_type is not None:
            recorded_program.primary_audio_type = primary_audio_type
        if primary_audio_language is not None:
            recorded_program.primary_audio_language = primary_audio_language
        if secondary_audio_type is not None:  # 音声多重放送のみ存在
            recorded_program.secondary_audio_type = secondary_audio_type
        if secondary_audio_language is not None:  # 音声多重放送のみ存在
            recorded_program.secondary_audio_language = secondary_audio_language

        return recorded_program


    def __selectServiceIdByPidFrequency(
        self,
        service_id_order: list[int],
        service_pmt_pid_map: dict[int, int],
    ) -> int | None:
        """
        PAT と PMT から得られる PID 情報と TS 内の PID 出現頻度を突き合わせて、
        映像・音声 PID が実在する service_id を推定する

        Args:
            service_id_order (list[int]): PAT に登場した順序で並んだ service_id のリスト
            service_pmt_pid_map (dict[int, int]): service_id と PMT PID の対応表

        Returns:
            int | None: 推定された service_id（推定できない場合は None）
        """

        # MPEG-TS 以外では実データを確認できないため推定しない
        if self.recorded_video.container_format != 'MPEG-TS':
            return None

        # PMT から映像・音声 PID を取得
        ## ariblib の ProgramMapSection は _pids クラス属性がデフォルトで定義されていないため、
        ## 動的に追加してから sections() メソッドを使用する
        service_pid_map: dict[int, dict[str, set[int]]] = {}

        # ファイルの 20% 位置にシークしてから PMT を解析する
        ## Mirakurun/mirakc では録画開始直後はサービス分離が完了しておらず、古い PMT 情報が含まれている場合がある
        ## ファイルの 20% 位置であれば、サービス分離が完了した後の正しい PMT を取得できる可能性が高い
        ## ariblib の sections() メソッドは内部キャッシュを持っておりシーク位置を尊重しないため、
        ## 新しいファイルハンドルを開いて 20% 位置から読み込む必要がある
        effective_size = min(self.end_ts_offset, self.recorded_video.file_size)
        pmt_seek_offset = ClosestMultiple(int(effective_size * 0.2), ts.PACKET_SIZE)

        # ProgramMapSection._pids が存在しない場合は空リストで初期化
        if not hasattr(ProgramMapSection, '_pids'):
            ProgramMapSection._pids = []  # type: ignore[attr-defined]
        original_pmt_pids = ProgramMapSection._pids  # type: ignore[attr-defined]
        pmt_pids_to_use = list(service_pmt_pid_map.values())
        ProgramMapSection._pids = pmt_pids_to_use  # type: ignore[attr-defined]
        try:
            # 20% 位置から始まる新しいファイルハンドルを開いて PMT を解析
            ## サービス分離済みのファイルでは特定のサービスの PMT しか存在しないため、
            ## 一定回数 PMT を確認したら終了する
            with ariblib.tsopen(self.recorded_video.file_path, chunk=1000) as pmt_ts:
                pmt_ts.seek(pmt_seek_offset)
                pmt_check_count = 0
                max_pmt_checks = len(service_pmt_pid_map) * 3  # 各サービスにつき最大3回のチェック
                for pmt in pmt_ts.sections(ProgramMapSection):
                    pmt_check_count += 1
                    service_id = int(pmt.program_number)
                    if service_id not in service_pmt_pid_map:
                        continue
                    # 既にこのサービスの PMT を取得済みならスキップ
                    if service_id in service_pid_map:
                        # すべてのサービスを確認済みか、一定回数チェックしたら終了
                        if len(service_pid_map) == len(service_pmt_pid_map) or pmt_check_count >= max_pmt_checks:
                            break
                        continue
                    video_pids = {int(p) for p in pmt.video_pids()}
                    audio_pids = {int(p) for p in pmt.audio_pids()}
                    if len(video_pids) == 0 and len(audio_pids) == 0:
                        continue
                    service_pid_map[service_id] = {
                        'video_pids': video_pids,
                        'audio_pids': audio_pids,
                    }
                    # すべてのサービスを確認済みか、一定回数チェックしたら終了
                    if len(service_pid_map) == len(service_pmt_pid_map) or pmt_check_count >= max_pmt_checks:
                        break
        finally:
            ProgramMapSection._pids = original_pmt_pids  # type: ignore[attr-defined]

        if len(service_pid_map) == 0:
            return None

        # TS 内の PID 出現頻度を取得
        try:
            file_path = Path(self.recorded_video.file_path)
            effective_size = min(self.end_ts_offset, self.recorded_video.file_size)
            if effective_size < ts.PACKET_SIZE * 100:
                return None
            sample_offset = ClosestMultiple(int(effective_size * 0.2), ts.PACKET_SIZE)
            if sample_offset > effective_size - ts.PACKET_SIZE:
                sample_offset = max(effective_size - ts.PACKET_SIZE, 0)
            sample_size = ClosestMultiple(6 * 1024 * 1024, ts.PACKET_SIZE)
            sample_size = min(sample_size, effective_size - sample_offset)
            if sample_size < ts.PACKET_SIZE * 100:
                return None
            with file_path.open('rb') as f:
                f.seek(sample_offset)
                sample_data = f.read(sample_size)
        except Exception as ex:
            logging.warning(f'{self.recorded_video.file_path}: Failed to read TS sample for PID analysis:', exc_info=ex)
            return None

        pid_counts: dict[int, int] = {}
        offset = 0
        while offset + ts.PACKET_SIZE <= len(sample_data):
            if sample_data[offset] != ts.SYNC_BYTE[0]:
                offset += 1
                continue
            packet = sample_data[offset:offset + ts.PACKET_SIZE]
            packet_pid = pid(packet)
            pid_counts[packet_pid] = pid_counts.get(packet_pid, 0) + 1
            offset += ts.PACKET_SIZE

        if len(pid_counts) == 0:
            return None

        # 映像 PID と音声 PID の出現回数を評価して service_id を選定
        best_service_id: int | None = None
        best_score = -1
        best_video_count = -1
        best_audio_count = -1
        for service_id in service_id_order:
            if service_id not in service_pid_map:
                continue
            video_pids = service_pid_map[service_id]['video_pids']
            audio_pids = service_pid_map[service_id]['audio_pids']
            video_count = sum(pid_counts.get(p, 0) for p in video_pids)
            audio_count = sum(pid_counts.get(p, 0) for p in audio_pids)
            # 映像を優先してスコア化する
            score = video_count * 2 + audio_count
            if score > best_score:
                best_score = score
                best_video_count = video_count
                best_audio_count = audio_count
                best_service_id = service_id
            elif score == best_score and best_service_id is not None:
                # スコアが同じ場合は映像 PID が多い方を優先する
                if video_count > best_video_count:
                    best_video_count = video_count
                    best_audio_count = audio_count
                    best_service_id = service_id
                elif video_count == best_video_count and audio_count > best_audio_count:
                    best_audio_count = audio_count
                    best_service_id = service_id

        if best_service_id is not None and best_score > 0:
            logging.debug(
                f'{self.recorded_video.file_path}: Selected service_id {best_service_id} by PID frequency '
                f'(score: {best_score}, video: {best_video_count}, audio: {best_audio_count}).'
            )
            return best_service_id

        return None


    @classmethod
    def __readPSIData(cls, reader: BufferedReader, target_pids: list[int], callback: Callable[[float, int, bytes], bool]) -> bool:
        """
        書庫から PSI/SI セクションを取り出す

        Args:
            reader (BufferedReader): 書庫データ
            target_pids (list[int]): 取り出すセクションの PID のリスト
            callback (Callable[[float, int, bytes], bool]): セクションを1つ取り出すごとに呼び出される関数

        Returns:
            bool: フォーマットエラーか callback から False が返ったとき False を返す
        """

        def GetUint16(buf: bytes, pos: int):
            return buf[pos] | buf[pos + 1] << 8

        def GetUint32(buf: bytes, pos: int):
            return GetUint16(buf, pos) | GetUint16(buf, pos + 2) << 16

        last_pids: list[int] = []
        last_dict: list[int | bytes | None] = []
        init_time = -1

        while True:
            buf = reader.read(32)
            if len(buf) != 32 or buf[0:8] != b'Pssc\x0d\x0a\x9a\x0a':
                # 完了
                break

            time_list_len = GetUint16(buf, 10)
            dictionary_len = GetUint16(buf, 12)
            dictionary_window_len = GetUint16(buf, 14)
            dictionary_data_size = GetUint32(buf, 16)
            dictionary_buff_size = GetUint32(buf, 20)
            code_list_len = GetUint32(buf, 24)
            if (dictionary_window_len < dictionary_len or
                dictionary_buff_size < dictionary_data_size or
                dictionary_window_len > 65536 - 4096):
                return False

            time_buf = reader.read(time_list_len * 4 + dictionary_len * 2)
            if len(time_buf) != time_list_len * 4 + dictionary_len * 2:
                return False

            pos = time_list_len * 4
            remain = dictionary_data_size
            pids: list[int] = []
            dict: list[int | bytes | None] = []
            for _ in range(dictionary_len):
                code_or_size = GetUint16(time_buf, pos) - 4096
                if code_or_size >= 0:
                    # 前回辞書 ID の参照
                    if code_or_size >= len(last_pids) or last_pids[code_or_size] < 0:
                        return False
                    pids.append(last_pids[code_or_size])
                    dict.append(last_dict[code_or_size])
                    last_pids[code_or_size] = -1
                else:
                    # セクションサイズ
                    remain -= 2
                    buf = reader.read(2)
                    if len(buf) != 2 or remain < 0:
                        return False
                    pids.append(GetUint16(buf, 0) % 0x2000)
                    # このあとセクションデータに置き換える
                    dict.append(code_or_size)
                pos += 2

            for i in range(dictionary_len):
                if type(dict[i]) is int:
                    # 新規なのでセクションデータを読む
                    size = cast(int, dict[i]) + 4097
                    remain -= size
                    buf = reader.read(size)
                    if len(buf) != size or remain < 0:
                        return False
                    # 対象 PID 以外のセクションデータは無視
                    dict[i] = buf if pids[i] in target_pids else None

            for i in range(dictionary_window_len - dictionary_len):
                if i >= len(last_pids):
                    return False
                # 前回辞書のうち未参照のものを引き継ぐ
                if last_pids[i] >= 0:
                    pids.append(last_pids[i])
                    dict.append(last_dict[i])
            last_pids = pids
            last_dict = dict
            # 残りは読み飛ばす
            remain += dictionary_data_size % 2
            if remain > 0 and len(reader.read(remain)) != remain:
                return False

            curr_time = -1
            for time_list_pos in range(0, time_list_len * 4, 4):
                abs_time = GetUint32(time_buf, time_list_pos)
                if abs_time == 0xffffffff:
                    curr_time = -1
                elif abs_time >= 0x80000000:
                    curr_time = abs_time % 0x40000000
                    if init_time < 0:
                        init_time = curr_time
                else:
                    if curr_time >= 0:
                        curr_time += GetUint16(time_buf, time_list_pos)
                    n = GetUint16(time_buf, time_list_pos + 2) + 1
                    buf = reader.read(n * 2)
                    if len(buf) != n * 2:
                        return False
                    time_sec = (curr_time + 0x40000000 - init_time) % 0x40000000 / 11250
                    for i in range(n):
                        code = GetUint16(buf, i * 2) - 4096
                        if code < 0 or code >= len(pids):
                            return False
                        if dict[code] is not None and not callback(time_sec, pids[code], cast(bytes, dict[code])):
                            return False

            trailer_size = 4 - (dictionary_len * 2 + (dictionary_data_size + 1) // 2 * 2 + code_list_len * 2) % 4
            buf = reader.read(trailer_size)
            if len(buf) != trailer_size:
                return False

        return True
