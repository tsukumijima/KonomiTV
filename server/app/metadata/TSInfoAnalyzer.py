
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
from typing import Any, cast
from zoneinfo import ZoneInfo

from app import logging
from app.models.Channel import Channel
from app.models.RecordedProgram import RecordedProgram
from app.models.RecordedVideo import RecordedVideo
from app.schemas import Genre
from app.utils import ClosestMultiple
from app.utils.TSInformation import TSInformation


class TSInfoAnalyzer:
    """
    録画 TS ファイル内に含まれる番組情報を解析するクラス
    ariblib の開発者の youzaka 氏に感謝します
    """

    def __init__(self, recorded_video: RecordedVideo) -> None:
        """
        録画 TS ファイル内に含まれる番組情報を解析するクラスを初期化する

        Args:
            recorded_video (RecordedVideo): 録画ファイル情報を表すモデル
        """

        # TS ファイルを開く
        ## 188 * 10000 バイト (≒ 1.88MB) ごとに分割して読み込む
        ## 現状 ariblib は先頭が sync_byte でない or 途中で同期が壊れる (破損した TS パケットが存在する) TS ファイルを想定していないため、
        ## ariblib に入力する録画ファイルは必ず正常な TS ファイルである必要がある
        self.recorded_video = recorded_video
        self.ts = ariblib.tsopen(self.recorded_video.file_path, chunk=10000)


    def analyze(self) -> tuple[RecordedProgram, Channel] | None:
        """
        録画 TS ファイル内に含まれる番組情報を解析し、データベースに格納するモデルを作成する
        各モデルの紐付けは行われていないので、子レコード作成後に別途紐付ける必要がある

        Returns:
            tuple[RecordedProgram, Channel]: 録画番組情報とチャンネル情報を表すモデルのタプル (サービス情報が取得できなかった場合は None)
        """

        # サービス (チャンネル) 情報を取得
        channel = self.__analyzeSDTInformation()
        if channel is None:
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

        return recorded_program, channel


    def __analyzeSDTInformation(self) -> Channel | None:
        """
        TS 内の SDT (Service Description Table) からサービス（チャンネル）情報を解析する
        PAT (Program Association Table) と NIT (Network Information Table) からも補助的に情報を取得する

        Returns:
            Channel: サービス（チャンネル）情報を表すモデル (サービス情報が取得できなかった場合は None)
        """

        # 誤動作防止のため必ず最初にシークを戻す
        self.ts.seek(0)

        # サービス (チャンネル) 情報を表すモデルを作成
        channel = Channel()

        # TS から PAT (Program Association Table) を抽出
        pat = next(self.ts.sections(ProgramAssociationSection))

        # トランスポートストリーム ID (TSID) を取得
        channel.transport_stream_id = int(pat.transport_stream_id)

        # サービス ID を取得
        for pid in pat.pids:
            if pid.program_number:
                # program_number は service_id と等しい
                # PAT から抽出した service_id を使えば、映像や音声が存在するストリームの番組情報を的確に抽出できる
                channel.service_id = int(pid.program_number)
                # 他にも pid があるかもしれないが（複数のチャンネルが同じストリームに含まれている場合など）、最初の pid のみを取得する
                break
        if channel.service_id is None:
            logging.warning(f'{self.recorded_video.file_path}: service_id not found.')
            return None

        # TS から SDT (Service Description Table) を抽出
        for sdt in self.ts.sections(ActualStreamServiceDescriptionSection):
            # ネットワーク ID とサービス種別 (=チャンネルタイプ) を取得
            channel.network_id = int(sdt.original_network_id)
            channel_type = TSInformation.getNetworkType(channel.network_id)
            if channel_type == 'OTHER':
                logging.warning(f'{self.recorded_video.file_path}: Unknown network_id: {channel.network_id}')
                return None
            channel.type = channel_type
            # SDT に含まれるサービスごとの情報を取得
            for service in sdt.services:
                # service_id が PAT から抽出したものと一致した場合のみ
                # CS の場合同じ TS の中に複数のチャンネルが含まれている事があり、録画する場合は基本的に他のチャンネルは削除される
                # そうすると ffprobe で確認できるがサービス情報や番組情報だけ残ってしまい、別のチャンネルの番組情報になるケースがある
                # PAT にはそうした削除済みのチャンネルは含まれていないので、正しいチャンネルの service_id を抽出できる
                if service.service_id == channel.service_id:
                    # SDT から得られる ServiceDescriptor 内の情報からチャンネル名を取得
                    for sd in service.descriptors[ServiceDescriptor]:
                        channel.name = TSInformation.formatString(sd.service_name)
                        break
                    else:
                        continue
                    break
            else:
                continue
            break
        if channel.network_id is None or channel.name is None:
            logging.warning(f'{self.recorded_video.file_path}: network_id or channel name not found.')
            return None

        # リモコン番号を取得
        if channel.type == 'GR':
            ## 地デジ: TS から NIT (Network Information Table) を抽出
            for nit in self.ts.sections(ActualNetworkNetworkInformationSection):
                # NIT に含まれるトランスポートストリームごとの情報を取得
                for transport_stream in nit.transport_streams:
                    # NIT から得られる TSInformationDescriptor 内の情報からリモコンキー ID を取得
                    # 地デジのみで、BS には TSInformationDescriptor 自体が存在しない
                    for ts_information in transport_stream.descriptors.get(TSInformationDescriptor, []):
                        channel.remocon_id = int(ts_information.remote_control_key_id)
                        break
                    break
                else:
                    continue
                break
            if channel.remocon_id is None:
                channel.remocon_id = 0  # リモコン番号を取得できなかった際は 0 が自動設定される
        else:
            ## それ以外: 共通のリモコン番号取得処理を実行
            channel.remocon_id = channel.calculateRemoconID()

        # チャンネル ID を生成
        channel.id = f'NID{channel.network_id}-SID{channel.service_id:03d}'

        # チャンネル番号を算出
        channel.channel_number = asyncio.run(channel.calculateChannelNumber())

        # 表示用チャンネルID = チャンネルタイプ(小文字)+チャンネル番号
        channel.display_channel_id = channel.type.lower() + channel.channel_number

        # サブチャンネルかどうかを算出
        channel.is_subchannel = channel.calculateIsSubchannel()

        # ラジオチャンネルにはなり得ない (録画ファイルのバリデーションの時点で映像と音声があることを確認している)
        channel.is_radiochannel = False

        # 録画ファイル内の情報として含まれているだけのチャンネルなので（視聴できるとは限らない）、is_watchable を False に設定
        ## もし視聴可能な場合はすでに channels テーブルにそのチャンネルのレコードが存在しているはずなので、そちらが優先される
        channel.is_watchable = False

        return channel


    def __analyzeEITInformation(self, channel: Channel, is_following: bool = False) -> RecordedProgram:
        """
        TS 内の EIT (Event Information Table) から番組情報を取得する
        サービス ID が必要な理由は、CS などで別のチャンネルの番組情報が取得されるのを防ぐため
        このため、事前に __analyzeSDTInformation() でサービス ID を含めたチャンネル情報を取得しておく必要がある

        Args:
            channel (Channel): チャンネル情報を表すモデル
            is_following (bool): 次の番組情報を取得するかどうか (デフォルト: 現在の番組情報)

        Returns:
            RecordedProgram: 録画番組情報を表すモデル
        """

        if is_following is True:
            eit_section_number = 1
        else:
            eit_section_number = 0

        # 誤動作防止のため必ず最初にシークを戻す
        ## 録画ファイルのサイズ全体の 20% の位置にシークする (正確にはシーク単位は 188 バイトずつでなければならないので 188 の倍数になるように調整する)
        ## 先頭にシークすると録画開始マージン分のデータを含んでしまうため、大体録画開始マージン分を除いた位置から始める
        ## 極端に録画開始マージンが大きいか番組長が短い録画でない限り、録画対象の番組が放送されているタイミングにシークできるはず
        ## 例えば30分10秒の録画 (前後5秒が録画マージン) の場合、全体の 20% の位置にシークすると大体6分2秒の位置になる
        ## 生の録画データはビットレートが一定のため、シーンによって大きくデータサイズが変動することはない
        self.ts.seek(ClosestMultiple(int(self.recorded_video.file_size * 0.2), ts.PACKET_SIZE))

        # 録画番組情報を表すモデルを作成
        recorded_program = RecordedProgram()
        recorded_program.network_id = channel.network_id
        recorded_program.service_id = channel.service_id

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
                    recorded_program.event_id = int(event.event_id)
                    ## 番組開始時刻 (タイムゾーンを日本時間 (+9:00) に設定)
                    ## 注意: present の duration が None (終了時間未定) の場合のみ、following の start_time が None になることがある
                    if event.start_time is not None:
                        recorded_program.start_time = cast(datetime, event.start_time).astimezone(ZoneInfo('Asia/Tokyo'))
                    ## 番組長 (秒)
                    ## 注意: 臨時ニュースなどで放送時間未定の場合は None になる
                    if event.duration is not None:
                        recorded_program.duration = cast(timedelta, event.duration).total_seconds()
                    ## 番組終了時刻を start_time と duration から算出
                    if recorded_program.start_time is not None and recorded_program.duration is not None:
                        recorded_program.end_time = recorded_program.start_time + cast(timedelta, event.duration)
                    ## ARIB TR-B15 第三分冊 (https://vs1p.manualzilla.com/store/data/006629648.pdf)
                    ## free_CA_mode が 1 のとき有料番組、0 のとき無料番組だそう
                    ## bool に変換した後、真偽を反転させる
                    recorded_program.is_free = not bool(event.free_CA_mode)

                    # 番組名, 番組概要 (ShortEventDescriptor)
                    if hasattr(event, 'title') and hasattr(event, 'desc'):
                        ## 番組名
                        recorded_program.title = TSInformation.formatString(event.title)
                        ## 番組概要
                        recorded_program.description = TSInformation.formatString(event.desc)

                    # 番組詳細情報 (ExtendedEventDescriptor)
                    if hasattr(event, 'detail'):
                        recorded_program.detail = {}
                        # 番組詳細テキストから取得した、見出しと本文の辞書ごとに
                        for head, text in cast(dict[str, str], event.detail).items():
                            # 見出しと本文
                            ## 見出しのみ ariblib 側で意図的に重複防止のためのタブ文字付加が行われる場合があるため、
                            ## strip() では明示的に半角スペースと改行のみを指定している
                            head_hankaku = TSInformation.formatString(head).replace('◇', '').strip(' \r\n')  # ◇ を取り除く
                            ## ないとは思うが、万が一この状態で見出しが衝突しうる場合は、見出しの後ろにタブ文字を付加する
                            while head_hankaku in recorded_program.detail.keys():
                                head_hankaku += '\t'
                            ## 見出しが空の場合、固定で「番組内容」としておく
                            if head_hankaku == '':
                                head_hankaku = '番組内容'
                            text_hankaku = TSInformation.formatString(text).strip()
                            recorded_program.detail[head_hankaku] = text_hankaku
                            # 番組概要が空の場合、番組詳細の最初の本文を概要として使う
                            # 空でまったく情報がないよりかは良いはず
                            if recorded_program.description.strip() == '':
                                recorded_program.description = text_hankaku

                    ## ジャンル情報 (ContentDescriptor)
                    if hasattr(event, 'genre') and hasattr(event, 'subgenre') and hasattr(event, 'user_genre'):
                        recorded_program.genres = []
                        for index, _ in enumerate(event.genre):  # ジャンルごとに
                            # major … 大分類
                            # middle … 中分類
                            genre_dict: Genre = {
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
                            recorded_program.genres.append(genre_dict)

                    # 音声情報 (AudioComponentDescriptor)
                    ## 主音声情報
                    if hasattr(event, 'audio'):
                        ## 主音声の種別
                        recorded_program.primary_audio_type = str(event.audio)
                    ## 副音声情報
                    if hasattr(event, 'second_audio'):
                        ## 副音声の種別
                        recorded_program.secondary_audio_type = str(event.second_audio)
                    ## 主音声・副音声の言語
                    ## event クラスには用意されていないので自前で取得する
                    for acd in event_data.descriptors.get(AudioComponentDescriptor, []):
                        if bool(acd.main_component_flag) is True:
                            ## 主音声の言語
                            recorded_program.primary_audio_language = \
                                TSInformation.getISO639LanguageCodeName(acd.ISO_639_language_code)
                            ## デュアルモノのみ
                            if recorded_program.primary_audio_type == '1/0+1/0モード(デュアルモノ)':
                                if bool(acd.ES_multi_lingual_flag) is True:
                                    recorded_program.primary_audio_language += '+' + \
                                        TSInformation.getISO639LanguageCodeName(acd.ISO_639_language_code_2)
                                else:
                                    recorded_program.primary_audio_language += '+副音声'  # 副音声で固定
                        else:
                            ## 副音声の言語
                            recorded_program.secondary_audio_language = \
                                TSInformation.getISO639LanguageCodeName(acd.ISO_639_language_code)
                            ## デュアルモノのみ
                            if recorded_program.secondary_audio_type == '1/0+1/0モード(デュアルモノ)':
                                if bool(acd.ES_multi_lingual_flag) is True:
                                    recorded_program.secondary_audio_language += '+' + \
                                        TSInformation.getISO639LanguageCodeName(acd.ISO_639_language_code_2)
                                else:
                                    recorded_program.secondary_audio_language += '+副音声'  # 副音声で固定

                    # EIT から取得できるすべての情報を取得できたら抜ける
                    ## 一回の EIT ですべての情報 (Descriptor) が降ってくるとは限らない
                    ## 副音声情報は副音声がない番組では当然取得できないので、除外している
                    attributes: list[str] = [
                        'event_id',
                        'title',
                        'description',
                        'detail',
                        'start_time',
                        'end_time',
                        'duration',
                        'is_free',
                        'genres',
                        'primary_audio_type',
                        'primary_audio_language',
                    ]
                    if all([
                        hasattr(recorded_program, attribute) and getattr(recorded_program, attribute) is not None
                        for attribute in attributes
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
                if recorded_program.detail is None:
                    recorded_program.detail = {}
                if recorded_program.genres is None:
                    recorded_program.genres = []

            # ループが 2000 回を超えたら (≒20回シークしても放送時間が確定しなかったら) 、タイムアウトでループを抜ける
            if count > 2000:
                p_or_f = 'following' if is_following is True else 'present'
                logging.warning(f'{self.recorded_video.file_path}: Analyzing EIT information ({p_or_f}) timed out.')
                break

            # ループが 100 で割り切れるたびに現在の位置から 188MB シークする
            ## ループが 100 以上に到達しているときはおそらく放送時間が未定の番組なので、放送時間が確定するまでシークする
            if count % 100 == 0:
                self.ts.seek(ts.PACKET_SIZE * 1000000, 1)  # 188MB (188 * 1000000 バイト) 進める

        # この時点でタイトルを取得できていない場合、拡張子を除いたファイル名をフォーマットした上でタイトルとして使用する
        ## 他の値は RecordedProgram モデルで設定されたデフォルト値が自動的に入るので、タイトルだけここで設定する
        if recorded_program.title is None:
            recorded_program.title = TSInformation.formatString(Path(self.recorded_video.file_path).stem)

        # この時点で番組開始時刻・番組終了時刻を取得できていない場合、適当なダミー値を設定する
        ## start_time が None になる組み合わせは「現在の番組の終了時間が未定」かつ「次の番組情報を取得しようとした」ときのみ
        ## 番組情報としては全く使い物にならないし、基本現在の番組情報を使わせるようにしたいので、後続の処理で使われないような値を設定する
        if recorded_program.start_time is None and recorded_program.end_time is None:
            recorded_program.start_time = datetime(1970, 1, 1, 9, tzinfo=ZoneInfo('Asia/Tokyo'))
            recorded_program.end_time = datetime(1970, 1, 1, 9, tzinfo=ZoneInfo('Asia/Tokyo'))
            recorded_program.duration = 0

        # この時点で番組終了時刻のみを取得できていない場合、フォールバックとして録画終了時刻を利用する
        ## さらにまずあり得ないとは思うが、もし録画終了時刻が取得できていない場合は、番組開始時刻 + 動画長を利用する
        if recorded_program.end_time is None:
            if self.recorded_video.recording_end_time is not None:
                recorded_program.end_time = self.recorded_video.recording_end_time
                recorded_program.duration = (recorded_program.end_time - recorded_program.start_time).total_seconds()
            else:
                recorded_program.end_time = recorded_program.start_time + timedelta(seconds=self.recorded_video.duration)
                recorded_program.duration = self.recorded_video.duration

        assert recorded_program.start_time is not None, 'start_time not found.'
        assert recorded_program.end_time is not None, 'end_time not found.'
        assert recorded_program.duration is not None, 'duration not found.'

        # 録画開始時刻・録画終了時刻が取得できている場合
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
