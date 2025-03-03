
import ariblib
import ariblib.event
import asyncio
from ariblib.descriptors import AudioComponentDescriptor
from ariblib.descriptors import ServiceDescriptor
from ariblib.descriptors import TSInformationDescriptor
from ariblib.sections import ActualNetworkNetworkInformationSection
from ariblib.sections import ActualStreamPresentFollowingEventInformationSection
from ariblib.sections import ActualStreamServiceDescriptionSection
from ariblib.sections import ProgramAssociationSection
from biim.mpeg2ts import ts
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any, cast, Literal
from zoneinfo import ZoneInfo

from app import logging
from app import schemas
from app.utils import ClosestMultiple
from app.utils.TSInformation import TSInformation


class TSInfoAnalyzer:
    """
    録画 TS ファイル内に含まれる番組情報を解析するクラス
    ariblib の開発者の youzaka 氏に感謝します
    """

    def __init__(self, recorded_video: schemas.RecordedVideo, end_ts_offset: int | None = None) -> None:
        """
        録画 TS ファイル内に含まれる番組情報を解析するクラスを初期化する

        Args:
            recorded_video (schemas.RecordedVideo): 録画ファイル情報を表すモデル
            end_ts_offset (int | None): 有効な TS データの終了位置 (バイト単位、ファイル後半がゼロ埋めされている場合に指定する)
        """

        # 有効な TS データの終了位置 (EIT 解析時に必要)
        # 未指定時はファイルサイズをそのまま利用する
        if end_ts_offset is not None:
            self.end_ts_offset = end_ts_offset
        else:
            self.end_ts_offset = recorded_video.file_size

        # TS ファイルを開く
        ## 188 * 10000 バイト (≒ 1.88MB) ごとに分割して読み込む
        ## 現状 ariblib は先頭が sync_byte でない or 途中で同期が壊れる (破損した TS パケットが存在する) TS ファイルを想定していないため、
        ## ariblib に入力する録画ファイルは必ず正常な TS ファイルである必要がある
        self.recorded_video = recorded_video
        self.ts = ariblib.tsopen(self.recorded_video.file_path, chunk=10000)


    def analyze(self) -> schemas.RecordedProgram | None:
        """
        録画 TS ファイル内に含まれる番組情報を解析する

        Returns:
            schemas.RecordedProgram:  録画番組情報（中に録画ファイル情報・チャンネル情報が含まれる）を表すモデル
                (サービスまたは番組情報が取得できなかった場合は None)
        """

        # サービス (チャンネル) 情報を取得
        channel = self.__analyzeSDTInformation()
        if channel is None:
            logging.warning(f'{self.recorded_video.file_path}: Channel information not found.')
            return None

        # 録画番組情報のモデルを作成
        ## EIT[p/f] のうち、現在と次の番組情報を両方取得した上で、録画マージンを考慮してどちらの番組を録画したかを判定する
        recorded_program_present = self.__analyzeEITInformation(channel, is_following=False)
        recorded_program_following = self.__analyzeEITInformation(channel, is_following=True)

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
        for pat in self.ts.sections(ProgramAssociationSection):
            # トランスポートストリーム ID (TSID) を取得
            transport_stream_id = int(pat.transport_stream_id)

            # サービス ID を取得
            for pid in pat.pids:
                if pid.program_number:
                    # program_number は service_id と等しい
                    # PAT から抽出した service_id を使えば、映像や音声が存在するストリームの番組情報を的確に抽出できる
                    service_id = int(pid.program_number)
                    # 他にも pid があるかもしれないが（複数のチャンネルが同じストリームに含まれている場合など）、最初の pid のみを取得する
                    break

            # service_id が見つかったらループを抜ける
            if service_id is not None:
                break

        if service_id is None:
            logging.warning(f'{self.recorded_video.file_path}: service_id not found.')
            return None

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


    def __analyzeEITInformation(self, channel: schemas.Channel, is_following: bool = False) -> schemas.RecordedProgram:
        """
        TS 内の EIT (Event Information Table) から番組情報を取得する
        チャンネル情報（サービス ID も含まれる）が必須な理由は、CS など複数サービスを持つ TS で
        意図しないチャンネルの番組情報が取得される問題を防ぐため

        Args:
            channel (schemas.Channel): チャンネル情報を表すモデル
            is_following (bool): 次の番組情報を取得するかどうか (デフォルト: 現在の番組情報)

        Returns:
            schemas.RecordedProgram: 録画番組情報を表すモデル
        """

        if is_following is True:
            eit_section_number = 1
        else:
            eit_section_number = 0

        # 誤動作防止のため必ず最初にシークを戻す
        ## 有効な TS データの終了位置から換算して 20% の位置にシークする (正確には TS パケットサイズに合わせて 188 の倍数になるように調整している)
        ## 先頭にシークすると録画開始マージン分のデータを含んでしまうため、大体録画開始マージン分を除いた位置から始める
        ## 極端に録画開始マージンが大きいか番組長が短い録画でない限り、録画対象の番組が放送されているタイミングにシークできるはず
        ## 例えば30分10秒の録画 (前後5秒が録画マージン) の場合、全体の 20% の位置にシークすると大体6分2秒の位置になる
        ## 生の録画データはビットレートが一定のため、シーンによって大きくデータサイズが変動することはない
        ## 録画中はファイルアロケーションの関係でファイル後半がゼロ埋めされている場合があるため、ファイルサイズではなく end_ts_offset を使う必要がある
        self.ts.seek(ClosestMultiple(int(self.end_ts_offset * 0.2), ts.PACKET_SIZE))

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
        for eit in self.ts.sections(ActualStreamPresentFollowingEventInformationSection):

            # section_number と service_id が一致したときだけ
            # サービス ID が必要な理由は、CS などで同じトランスポートストリームに含まれる別チャンネルの番組情報になることを防ぐため
            if eit.section_number == eit_section_number and eit.service_id == channel.service_id:

                # EIT から得られる各種 Descriptor 内の情報を取得
                # ariblib.event が各種 Descriptor のラッパーになっていたのでそれを利用
                for event_data in eit.events:

                    # EIT 内のイベントを取得
                    event: Any = ariblib.event.Event(eit, event_data)

                    # デフォルトで毎回設定されている情報
                    ## イベント ID
                    event_id = int(event.event_id)
                    ## 番組開始時刻 (タイムゾーンを日本時間 (+9:00) に設定)
                    ## 注意: present の duration が None (終了時間未定) の場合のみ、following の start_time が None になることがある
                    if event.start_time is not None:
                        start_time = cast(datetime, event.start_time).astimezone(ZoneInfo('Asia/Tokyo'))
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

            # ループが 100 で割り切れるたびに現在の位置から 188MB シークする
            ## ループが 100 以上に到達しているときはおそらく放送時間が未定の番組なので、放送時間が確定するまでシークする
            if count % 100 == 0:
                self.ts.seek(ts.PACKET_SIZE * 1000000, 1)  # 188MB (188 * 1000000 バイト) 進める

        # この時点でタイトルを取得できていない場合（タイムアウト発生時）、フォールバックとして拡張子を除いたファイル名をフォーマットした上でタイトルとして使用する
        if title is None:
            title = TSInformation.formatString(Path(self.recorded_video.file_path).stem)

        # この時点で番組開始時刻・番組終了時刻を取得できていない場合、適当なダミー値を設定する
        ## start_time が None になる組み合わせは「現在の番組の終了時間が未定」かつ「次の番組情報を取得しようとした」ときか、
        ## 録画ファイルが短すぎて EIT のパースに失敗した場合のみ
        ## 番組情報としては全く使い物にならないし、基本現在の番組情報を使わせるようにしたいので、後続の処理で使われないような値を設定する
        if start_time is None and end_time is None:
            start_time = datetime(1970, 1, 1, 9, tzinfo=ZoneInfo('Asia/Tokyo'))
            end_time = datetime(1970, 1, 1, 9, tzinfo=ZoneInfo('Asia/Tokyo'))
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
            created_at = datetime.now(tz=ZoneInfo('Asia/Tokyo')),
            updated_at = datetime.now(tz=ZoneInfo('Asia/Tokyo')),
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

        # 録画開始時刻・録画終了時刻の両方が取得できている場合
        if (self.recorded_video.recording_start_time is not None and
            self.recorded_video.recording_end_time is not None):

            # 録画マージン (開始/終了) を算出
            ## 取得できなかった場合はデフォルト値として 0 が自動設定される
            ## 番組の途中から録画した/番組終了前に録画を中断したなどで録画マージンがマイナスになる場合も 0 が設定される
            recorded_program.recording_start_margin = \
                max((recorded_program.start_time - self.recorded_video.recording_start_time).total_seconds(), 0.0)
            recorded_program.recording_end_margin = \
                max((self.recorded_video.recording_end_time - recorded_program.end_time).total_seconds(), 0.0)

            # 番組開始時刻 < 録画開始時刻 or 録画終了時刻 < 番組終了時刻 の場合、部分的に録画されていることを示すフラグを立てる
            ## 番組全編を録画するには、録画開始時刻が番組開始時刻よりも前で、録画終了時刻が番組終了時刻よりも後である必要がある
            if (recorded_program.start_time < self.recorded_video.recording_start_time or
                self.recorded_video.recording_end_time < recorded_program.end_time):
                recorded_program.is_partially_recorded = True
            else:
                recorded_program.is_partially_recorded = False

        return recorded_program
