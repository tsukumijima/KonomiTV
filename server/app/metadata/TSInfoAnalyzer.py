
import ariblib
import asyncio
import concurrent.futures
from ariblib.aribstr import AribString
from ariblib.descriptors import ServiceDescriptor
from ariblib.descriptors import TSInformationDescriptor
from ariblib.sections import ActualStreamServiceDescriptionSection
from ariblib.sections import ProgramAssociationSection
from ariblib.sections import NetworkInformationSection
from pathlib import Path
from typing import Literal

from app.models import Channel
from app.models import RecordedProgram
from app.models import RecordedVideo


class ActualStreamNetworkInformationSection(NetworkInformationSection):
    """ 自ストリームSDT """
    _table_ids = [0x40]  # 自ネットワークのみ


class TSInfoAnalyzer:
    """ 録画 TS ファイル内に含まれる番組情報を解析するクラス """

    # formatString() で使用する変換マップ
    __format_string_translation_map = None


    def __init__(self, recorded_ts_path: Path) -> None:
        """
        録画 TS ファイル内に含まれる番組情報を解析するクラスを初期化する

        Args:
            recorded_ts_path (Path): 録画 TS ファイルのパス
        """

        # TS ファイルを開く
        # チャンクは 1000（だいたい 0.1 ～ 0.2 秒間隔）に設定
        self.ts = ariblib.tsopen(recorded_ts_path, chunk=1000)


    def analyze(self, recorded_video: RecordedVideo) -> tuple[RecordedProgram, Channel]:
        """
        録画 TS ファイル内に含まれる番組情報を解析し、データベースに格納するモデルを作成する

        Args:
            recorded_video (RecordedVideo): 録画ファイル情報を表すモデル

        Returns:
            tuple[RecordedProgram, Channel]: 録画番組情報とチャンネル情報を表すモデルのタプル
        """

        # TODO!!!!!

        # サービス (チャンネル) 情報を取得
        channel = self.__analyzeSDTInformation()

        # 録画番組情報のモデルを作成
        recorded_program = RecordedProgram()

        return recorded_program, channel


    @staticmethod
    def __getFormatStringTranslationTable() -> dict[str, str]:
        """
        formatString() で使用する変換テーブルを取得する

        Returns:
            dict[str, str]: 変換テーブル
        """

        # 全角英数を半角英数に置換
        # ref: https://github.com/ikegami-yukino/jaconv/blob/master/jaconv/conv_table.py
        zenkaku_table = '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ'
        hankaku_table = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        merged_table = dict(zip(list(zenkaku_table), list(hankaku_table)))

        # 全角記号を半角記号に置換
        synbol_zenkaku_table = '＂＃＄％＆＇（）＋，－．／：；＜＝＞［＼］＾＿｀｛｜｝　'
        synbol_hankaku_table = '"#$%&\'()+,-./:;<=>[\\]^_`{|} '
        merged_table.update(zip(list(synbol_zenkaku_table), list(synbol_hankaku_table)))
        merged_table.update({
            # 一部の半角記号を全角に置換
            # 主に見栄え的な問題（全角の方が字面が良い）
            '!': '！',
            '?': '？',
            '*': '＊',
            '~': '～',
            '@': '＠',
            # シャープ → ハッシュ
            '♯': '#',
            # 波ダッシュ → 全角チルダ
            ## EDCB は ～ を全角チルダとして扱っているため、KonomiTV でもそのように統一する
            ## TODO: 番組検索を実装する際は検索文字列の波ダッシュを全角チルダに置換する下処理が必要
            ## ref: https://qiita.com/kasei-san/items/3ce2249f0a1c1af1cbd2
            '〜': '～',
        })

        # 番組表で使用される囲み文字の置換テーブル
        # ref: https://note.nkmk.me/python-chr-ord-unicode-code-point/
        # ref: https://github.com/l3tnun/EPGStation/blob/v2.6.17/src/util/StrUtil.ts#L7-L46
        enclosed_characters_table = {
            '\U0001f14a': '[HV]',
            '\U0001f13f': '[P]',
            '\U0001f14c': '[SD]',
            '\U0001f146': '[W]',
            '\U0001f14b': '[MV]',
            '\U0001f210': '[手]',
            '\U0001f211': '[字]',
            '\U0001f212': '[双]',
            '\U0001f213': '[デ]',
            '\U0001f142': '[S]',
            '\U0001f214': '[二]',
            '\U0001f215': '[多]',
            '\U0001f216': '[解]',
            '\U0001f14d': '[SS]',
            '\U0001f131': '[B]',
            '\U0001f13d': '[N]',
            '\U0001f217': '[天]',
            '\U0001f218': '[交]',
            '\U0001f219': '[映]',
            '\U0001f21a': '[無]',
            '\U0001f21b': '[料]',
            '\U0001f21c': '[前]',
            '\U0001f21d': '[後]',
            '\U0001f21e': '[再]',
            '\U0001f21f': '[新]',
            '\U0001f220': '[初]',
            '\U0001f221': '[終]',
            '\U0001f222': '[生]',
            '\U0001f223': '[販]',
            '\U0001f224': '[声]',
            '\U0001f225': '[吹]',
            '\U0001f14e': '[PPV]',
            '\U0001f200': '[ほか]',
        }

        # Unicode の囲み文字を大かっこで囲った文字に置換する
        # EDCB で EpgDataCap3_Unicode.dll を利用している場合や、Mirakurun 3.9.0-beta.24 以降など、
        # 番組情報取得元から Unicode の囲み文字が送られてくる場合に対応するためのもの
        # Unicode の囲み文字はサロゲートペアなどで扱いが難しい上に KonomiTV では囲み文字を CSS でハイライトしているため、Unicode にするメリットがない
        # ref: https://note.nkmk.me/python-str-replace-translate-re-sub/
        merged_table.update(enclosed_characters_table)

        return merged_table


    @classmethod
    def formatString(cls, string: str | AribString) -> str:
        """
        文字列に含まれる英数や記号を半角に置換し、一律な表現に整える

        Args:
            string (str | AribString): str あるいは AribString の文字列

        Returns:
            str: 置換した文字列
        """

        # AribString になっている事があるので明示的に str 型にキャストする
        result = str(string)

        # 変換マップを構築
        if cls.__format_string_translation_map is None:
            cls.__format_string_translation_map = str.maketrans(cls.__getFormatStringTranslationTable())

        result = result.translate(cls.__format_string_translation_map)

        # 置換した文字列を返す
        return result


    @staticmethod
    def getNetworkType(network_id: int) -> Literal['GR', 'BS', 'CS', 'CATV', 'SKY', 'STARDIGIO', 'OTHER']:
        """
        ネットワーク ID からネットワークの種別を取得する
        種別は GR (地デジ)・BS・CS・CATV・SKY (SPHD)・STARDIGIO (スターデジオ)・OTHER (不明なネットワーク ID のチャンネル) のいずれか

        Args:
            network_id (int): ネットワーク ID

        Returns:
            str: GR・BS・CS・CATV・SKY・STARDIGIO・OTHER のいずれか
        """

        # 以下は ARIB STD-B10 第2部 付録N より抜粋
        # https://web.archive.org/web/2if_/http://www.arib.or.jp/english/html/overview/doc/2-STD-B10v5_3.pdf#page=256

        # 地上デジタルテレビジョン放送 (network_id: 30848 ~ 32744)
        if network_id >= 0x7880 and network_id <= 0x7FE8:
            return 'GR'

        # BSデジタル放送
        if network_id == 0x0004:
            return 'BS'

        # 110度CSデジタル放送
        # CS1: 0x0006 (旧プラット・ワン系)
        # CS2: 0x0007 (旧スカイパーフェクTV!2系)
        if network_id == 0x0006 or network_id == 0x0007:
            return 'CS'

        # ケーブルテレビ (リマックス方式・トランスモジュレーション方式)
        # ケーブルテレビ独自のチャンネルのみで、地上波・BS の再送信は含まない
        # デジタル放送リマックス: 0xFFFE (HD・SD チャンネル (MPEG-2))
        # デジタル放送高度リマックス: 0xFFFA (ケーブル4Kチャンネル (H.264, H.265))
        # JC-HITSトランスモジュレーション: 0xFFFD (HD・SD チャンネル (MPEG-2))
        # 高度JC-HITSトランスモジュレーション: 0xFFF9 (ケーブル4Kチャンネル (H.264, H.265))
        if network_id == 0xFFFE or network_id == 0xFFFA or network_id == 0xFFFD or network_id == 0xFFF9:
            return 'CATV'

        # 124/128度CSデジタル放送
        # SPHD: 0x000A (スカパー！プレミアムサービス)
        # SPSD-SKY: 0x0003 (運用終了)
        if network_id == 0x000A or network_id == 0x0003:
            return 'SKY'

        # 124/128度CSデジタル放送
        # SPSD-PerfecTV: 0x0001 (スターデジオ)
        if network_id == 1:
            return 'STARDIGIO'

        # 不明なネットワーク ID のチャンネル
        return 'OTHER'


    def __analyzeSDTInformation(self) -> Channel:
        """
        TS 内の SDT (Service Description Table) からサービス（チャンネル）情報を解析する
        PAT (Program Association Table) と NIT (Network Information Table) からも補助的に情報を取得する

        Returns:
            Channel: サービス（チャンネル）情報を表すモデル
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
        assert channel.service_id is not None, 'service_id not found.'

        # TS から SDT (Service Description Table) を抽出
        for sdt in self.ts.sections(ActualStreamServiceDescriptionSection):

            # ネットワーク ID とサービス種別 (=チャンネルタイプ) を取得
            channel.network_id = int(sdt.original_network_id)
            channel_type = self.getNetworkType(channel.network_id)
            assert channel_type != 'OTHER', f'Unknown network_id: {channel.network_id}'
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
                        channel.name = self.formatString(sd.service_name)
                        break
                    else:
                        continue
                    break
            else:
                continue
            break
        assert channel.network_id is not None, 'network_id not found.'
        assert channel.name is not None, 'channel name not found.'

        # リモコン番号を取得
        ## 地デジ: TS から NIT (Network Information Table) を抽出
        if channel.type == 'GR':
            for nit in self.ts.sections(ActualStreamNetworkInformationSection):

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
                channel.remocon_id = -1
        ## それ以外: 共通のリモコン番号取得処理を実行
        else:
            channel.remocon_id = channel.calculateRemoconID()

        # チャンネル番号を算出
        ## ThreadPoolExecutor 上で実行し、イベントループ周りの謎エラーを回避する
        with concurrent.futures.ThreadPoolExecutor(1) as executor:
            channel.channel_number = executor.submit(asyncio.run, channel.calculateChannelNumber()).result()

        # チャンネル ID を生成
        channel.id = f'NID{channel.network_id}-SID{channel.service_id:03d}'

        # 表示用チャンネルID = チャンネルタイプ(小文字)+チャンネル番号
        channel.display_channel_id = channel.type.lower() + channel.channel_number

        # サブチャンネルかどうかを算出
        channel.is_subchannel = channel.calculateIsSubchannel()

        # ラジオチャンネルにはなり得ない (録画ファイルのバリデーションの時点で映像と音声があることを確認している)
        channel.is_radiochannel = False

        # 録画ファイルから取得したチャンネルなので、is_watchable を False に設定
        channel.is_watchable = False

        return channel
