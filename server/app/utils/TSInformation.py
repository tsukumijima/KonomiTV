
import json
import sys
from copy import copy
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Union

import ariblib
import ariblib.constants
import ariblib.event
from ariblib.aribstr import AribString
from ariblib.descriptors import (
    AudioComponentDescriptor,
    ServiceDescriptor,
    TSInformationDescriptor,
)
from ariblib.packet import (
    adaptation_field,
    TransportStreamFile,
)
from ariblib.sections import (
    ActualStreamPresentFollowingEventInformationSection,
    ActualStreamServiceDescriptionSection,
    NetworkInformationSection,
    ProgramAssociationSection,
    TimeOffsetSection,
)


class TSInformation:
    """
    TS ファイルから各種情報を取得するクラス
    ariblib の開発者の youzaka 氏に感謝します
    """

    # 映像のコーデック
    # 参考: https://github.com/Chinachu/Mirakurun/blob/master/src/Mirakurun/epg.ts#L27
    STREAM_CONTENT = {
        0x01: 'mpeg2',
        0x05: 'h.264',
        0x09: 'h.265',
    }

    # 映像の解像度
    # 参考: https://github.com/Chinachu/Mirakurun/blob/master/src/Mirakurun/epg.ts#L33
    COMPONENT_TYPE = {
        0x01: '480i',
        0x02: '480i',
        0x03: '480i',
        0x04: '480i',
        0x83: '4320p',
        0x91: '2160p',
        0x92: '2160p',
        0x93: '2160p',
        0x94: '2160p',
        0xA1: '480p',
        0xA2: '480p',
        0xA3: '480p',
        0xA4: '480p',
        0xB1: '1080i',
        0xB2: '1080i',
        0xB3: '1080i',
        0xB4: '1080i',
        0xC1: '720p',
        0xC2: '720p',
        0xC3: '720p',
        0xC4: '720p',
        0xD1: '240p',
        0xD2: '240p',
        0xD3: '240p',
        0xD4: '240p',
        0xE1: '1080p',
        0xE2: '1080p',
        0xE3: '1080p',
        0xE4: '1080p',
        0xF1: '180p',
        0xF2: '180p',
        0xF3: '180p',
        0xF4: '180p',
    }

    # formatString() で使用する変換マップ
    __format_string_translation_map = None


    def __init__(self, tspath:str):
        """
        TS ファイルから各種情報を取得する

        Args:
            tspath (str): TS ファイルのパス
        """

        # TS ファイルを開く
        # チャンクは 1000（だいたい 0.1 ～ 0.2 秒間隔）に設定
        self.ts:TransportStreamFile = ariblib.tsopen(tspath, chunk=1000)


    def extract(self) -> str:
        """
        TS 内から得られる各種番組情報などを抽出して辞書にまとめる

        Returns:
            str: TS の各種情報をまとめた辞書
        """

        # SDT (Service Description Table) からチャンネル情報を取得
        sdt = self.getSDTInformation()

        # EIT (Event Information Table) から現在と次の番組情報を取得
        # 「現在」は録画開始時点のものなので、録画マージンがある場合基本的には eit_present には前の番組の情報が入る
        eit_present = self.getEITInformation(sdt['service_id'], 0)
        eit_following = self.getEITInformation(sdt['service_id'], 1)

        # TOT (Time Offset Table) からおおよその録画開始時刻・録画終了時刻を取得
        # TOT だけだと正確でないので、PCR (Packet Clock Reference) の値で補完する
        record_start_time = self.getRecordStartTime()
        record_end_time = self.getRecordEndTime()

        # 録画時間を算出
        record_duration = record_end_time - record_start_time

        # 録画開始時刻と次の番組の開始時刻を比較して、差が1分以内（＝録画マージン）なら次の番組情報を利用する
        # 録画マージン分おおまかにシークしてから番組情報を取得しているため、基本的には現在の番組情報を使うことになるはず
        if eit_following['start_time'] is not None and eit_following['start_time'] - record_start_time <= timedelta(minutes=1):
            eit = copy(eit_following)
        else:
            eit = copy(eit_present)

        return {
            'record': {
                'start_time': record_start_time,
                'start_margin': (eit['start_time'] or record_start_time) - record_start_time,
                'end_time': record_end_time,
                'end_margin': record_end_time - (eit['end_time'] or record_end_time),
                'duration': record_duration,
            },
            'channel': sdt,
            'program': eit,
        }


    @staticmethod
    def __getFormatStringTranslationTable() -> dict:
        """
        formatString() で使用する変換テーブルを取得する

        Returns:
            dict: 変換テーブル
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
    def formatString(cls, string:Union[str, AribString]) -> str:
        """
        文字列に含まれる英数や記号を半角に置換し、一律な表現に整える

        Args:
            string (Union[str, AribString]): str あるいは AribString の文字列

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
    def getNetworkType(network_id:int) -> str:
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


    @staticmethod
    def getISO639LanguageCodeName(iso639_language_code: str) -> str:
        """
        ISO639 形式の言語コードが示す言語の名称を取得する

        Args:
            iso639_code (str): ISO639 形式の言語コード

        Returns:
            str: ISO639 形式の言語コードが示す言語の名称
        """

        if iso639_language_code == 'jpn':
            return '日本語'
        elif iso639_language_code == 'eng':
            return '英語'
        elif iso639_language_code == 'deu':
            return 'ドイツ語'
        elif iso639_language_code == 'fra':
            return 'フランス語'
        elif iso639_language_code == 'ita':
            return 'イタリア語'
        elif iso639_language_code == 'rus':
            return 'ロシア語'
        elif iso639_language_code == 'zho':
            return '中国語'
        elif iso639_language_code == 'kor':
            return '韓国語'
        elif iso639_language_code == 'spa':
            return 'スペイン語'
        else:
            return 'その他の言語'


    def getSDTInformation(self) -> dict:
        """
        TS 内の SDT (Service Descrition Table) からサービス（チャンネル）情報を取得する
        PAT (Program Association Table) と NIT (Network Information Table) からも補助的に情報を取得する

        Returns:
            dict: サービス（チャンネル）情報が入った辞書
        """

        # 雛形
        result = {
            'id': None,
            'network_id': None,
            'service_id': None,
            'transport_stream_id': None,
            'remocon_id': None,
            'channel_name': None,
            'channel_ts_name': None,
            'channel_type': None,
            'channel_service_type': None,
        }

        # 誤動作防止のため必ず最初にシークを戻す
        self.ts.seek(0)

        # TS から PAT (Program Association Table) を抽出
        pat = next(self.ts.sections(ProgramAssociationSection))

        # トランスポートストリーム ID を取得
        result['transport_stream_id'] = pat.transport_stream_id

        # ネットワーク ID を取得
        for pid in pat.pids:
            if pid.program_number:
                # だいぶ罠だったのだが、program_number は service_id と等しい
                # つまり、PAT から抽出した service_id を使えば映像や音声が存在するストリームの番組情報を的確に抽出できる
                result['service_id'] = pid.program_number
                # 他にも pid があるかもしれないが（複数のチャンネルが同じストリームに含まれている場合など）、最初の pid のみを使うので break
                break

        # TS から SDT (Service Description Table) を抽出
        for sdt in self.ts.sections(ActualStreamServiceDescriptionSection):

            # ネットワーク ID を取得
            result['network_id'] = sdt.original_network_id

            # ネットワーク種別を取得
            result['channel_type'] = self.getNetworkType(result['network_id'])

            # サービスごとに
            for service in sdt.services:

                # service_id が PAT から抽出したものと一致した場合のみ
                # CS の場合同じ TS の中に複数のチャンネルが含まれている事があり、録画する場合は基本的に他のチャンネルは削除される
                # そうすると ffprobe で確認できるがサービス情報や番組情報だけ残ってしまい、別のチャンネルの番組情報になるケースがある
                # PAT にはそうした削除済みのチャンネルは含まれていないので、正しいチャンネルの service_id を抽出できる
                if service.service_id == result['service_id']:

                    # SDT から得られる ServiceDescriptor 内の情報（サービスタイプ・サービス名）を取得
                    for sd in service.descriptors[ServiceDescriptor]:
                        result['channel_service_type'] = ariblib.constants.SERVICE_TYPE[int(hex(sd.service_type), 16)]
                        result['channel_name'] = self.formatString(sd.service_name)
                        break
                    else:
                        continue
                    break
            else:
                continue
            break

        # TS から NIT (Network Information Table) を抽出
        NetworkInformationSection._table_ids = [0x40]  # 自ネットワークのみ
        for nit in self.ts.sections(NetworkInformationSection):

            for transport_stream in nit.transport_streams:

                # NIT から得られる TSInformationDescriptor 内の情報（リモコンキー ID）を取得
                # 地デジのみで、BS には ServiceDescriptor 自体が存在しない
                for ts_information in transport_stream.descriptors.get(TSInformationDescriptor, []):
                    result['remocon_id'] = ts_information.remote_control_key_id
                    result['channel_ts_name'] = self.formatString(ts_information.ts_name_char)
                    break
                break
            else:
                continue
            break

        # ID を設定
        result['id'] = f'NID{result["network_id"]}-SID{result["service_id"]:03d}'

        return result


    def getEITInformation(self, service_id:int, eit_section_number:int) -> dict:
        """
        TS内の EIT (Event Information Table) から番組情報を取得する
        サービス ID が必要な理由は、CS などで別のチャンネルの番組情報が取得されるのを防ぐため
        このため、事前に getSDTInformation() で service_id を取得しておく必要がある

        Args:
            service_id (int): 取得したいチャンネルのサービス ID
            eit_section_number (int): 取得したい EIT セクション（ 0 なら現在の番組、1 なら次の番組）

        Returns:
            dict: 番組情報が入った辞書
        """

        # 雛形
        result = {
            'id': None,
            'network_id': None,
            'service_id': None,
            'event_id': None,
            'title': None,
            'description': None,
            'detail': None,
            'start_time': None,
            'end_time': None,
            'duration': None,
            'is_free': None,
            'genre': None,
            'video': {
                'type': None,
                'codec': None,
                'resolution': None,
            },
            'primary_audio': {
                'type': None,
                'language': None,
                'sampling_rate': None,
            },
            'secondary_audio': {
                'type': None,
                'language': None,
                'sampling_rate': None,
            },
        }

        # 誤動作防止のため必ず最初にシークを戻す
        # 録画マージンを考慮して、少し後から始める
        self.ts.seek(18800000)  # 18MB

        # TS から EIT (Event Information Table) を抽出
        count = 0
        for eit in self.ts.sections(ActualStreamPresentFollowingEventInformationSection):

            # section_number と service_id が一致したときだけ
            # サービス ID が必要な理由は、CS などで同じトランスポートストリームに含まれる別チャンネルの番組情報になることを防ぐため
            if eit.section_number == eit_section_number and eit.service_id == service_id:

                # EIT から得られる各種 Descriptor 内の情報を取得
                # ariblib.event が各種 Descriptor のラッパーになっていたのでそれを利用
                for event_data in eit.events:

                    # EIT 内のイベントを取得
                    event = ariblib.event.Event(eit, event_data)

                    # 存在するなら順に追加していく
                    # 直接取得した文字列は AribSting になっているので、明示的に str 型にキャストする

                    ## ネットワーク ID・サービス ID・イベント ID
                    if hasattr(event, 'event_id'):
                        result['id'] = f'NID{event.original_network_id}-SID{event.service_id}-EID{event.event_id}'
                        result['network_id'] = event.original_network_id
                        result['service_id'] = event.service_id
                        result['event_id'] = event.event_id

                    ## 番組名
                    if hasattr(event, 'title'):
                        result['title'] = self.formatString(event.title)

                    ## 番組概要
                    if hasattr(event, 'desc'):
                        result['description'] = self.formatString(event.desc)

                    ## 番組詳細
                    if hasattr(event, 'detail'):
                        result['detail'] = dict()

                        # 見出しと本文
                        for heading, text in event.detail.items():
                            result['detail'][heading.replace('◇', '')] = self.formatString(text)  # ◇ を取り除く

                            # 番組概要が空の場合、番組詳細の最初の本文を概要として使う
                            # 空でまったく情報がないよりかは良いはず
                            if result['description'].strip() == '':
                                result['description'] = self.formatString(text)

                    ## 番組長
                    if hasattr(event, 'duration'):
                        result['duration'] = event.duration

                    ## 番組開始時刻・番組終了時刻
                    if hasattr(event, 'start_time') and event.start_time is not None:
                        # タイムゾーンを日本時間 (+9:00) に設定
                        result['start_time'] = event.start_time.astimezone(timezone(timedelta(hours=9)))
                        # 番組終了時刻を start_time と duration から算出
                        if result['duration'] is not None:
                            result['end_time'] = result['start_time'] + result['duration']
                        else:
                            result['end_time'] = None  # 放送時間未定

                    ## 無料放送かどうか
                    if hasattr(event, 'free_CA_mode'):
                        # ARIB TR-B15 第三分冊 (https://vs1p.manualzilla.com/store/data/006629648.pdf)
                        # free_CA_mode が 1 のとき有料番組、0 のとき無料番組だそう
                        # bool に変換した後、真偽を反転させる
                        result['is_free'] = not bool(event.free_CA_mode)

                    ## ジャンル
                    if hasattr(event, 'genre'):
                        result['genre'] = list()
                        for index, _ in enumerate(event.genre):  # ジャンルごとに

                            # major … 大分類
                            # middle … 中分類
                            genre_dict = {
                                'major': event.genre[index].replace('／', '・'),
                                'middle': event.subgenre[index].replace('／', '・'),
                            }

                            # BS/地上デジタル放送用番組付属情報がジャンルに含まれている場合、user_nibble から値を取得して書き換える
                            # たとえば「中止の可能性あり」や「延長の可能性あり」といった情報が取れる
                            if genre_dict['major'] == '拡張':
                                if genre_dict['middle'] == 'BS/地上デジタル放送用番組付属情報':
                                    genre_dict['middle'] = event.user_genre[index]
                                # 「拡張」はあるがBS/地上デジタル放送用番組付属情報でない場合はなんの値なのかわからないのでパス
                                else:
                                    continue

                            # ジャンルを追加
                            result['genre'].append(genre_dict)

                    ## 映像情報
                    if hasattr(event, 'video'):  ## 映像の種別
                        result['video']['type'] = event.video
                    if hasattr(event, 'video_content'):  ## 映像のコーデック
                        result['video']['codec'] = self.STREAM_CONTENT[int(hex(event.video_content), 16)]
                    if hasattr(event, 'video_component'):  ## 映像の解像度
                        result['video']['resolution'] = self.COMPONENT_TYPE[int(hex(event.video_component), 16)]

                    ## 主音声情報
                    if hasattr(event, 'audio'):  ## 主音声の種別
                        result['primary_audio']['type'] = event.audio
                    if hasattr(event, 'sampling_rate_string'):  ## 主音声のサンプルレート
                        result['primary_audio']['sampling_rate'] = event.sampling_rate_string

                    ## 副音声情報
                    if hasattr(event, 'second_audio'):  ## 副音声の種別
                        result['secondary_audio']['type'] = event.second_audio
                    if hasattr(event, 'second_sampling_rate_string'):  ## 副音声のサンプルレート
                        result['secondary_audio']['sampling_rate'] = event.second_sampling_rate_string

                    ## 主音声・副音声の言語
                    ## event クラスには用意されていないので自前で取得する
                    for acd in event_data.descriptors.get(AudioComponentDescriptor, []):
                        if bool(acd.main_component_flag) is True:
                            ## 主音声の言語
                            result['primary_audio']['language'] = self.getISO639LanguageCodeName(acd.ISO_639_language_code)
                            ## デュアルモノのみ
                            if result['primary_audio']['type'] == '1/0+1/0モード(デュアルモノ)':
                                if bool(acd.ES_multi_lingual_flag) is True:
                                    result['primary_audio']['language'] += '+' + self.getISO639LanguageCodeName(acd.ISO_639_language_code_2)
                                else:
                                    result['primary_audio']['language'] += '+副音声'  # 副音声で固定
                        else:
                            ## 副音声の言語
                            result['secondary_audio']['language'] = self.getISO639LanguageCodeName(acd.ISO_639_language_code)
                            ## デュアルモノのみ
                            if result['secondary_audio']['type'] == '1/0+1/0モード(デュアルモノ)':
                                if bool(acd.ES_multi_lingual_flag) is True:
                                    result['secondary_audio']['language'] += '+' + self.getISO639LanguageCodeName(acd.ISO_639_language_code_2)
                                else:
                                    result['secondary_audio']['language'] += '+副音声'  # 副音声で固定

                    def all_not_none(iterable):
                        """リスト内の要素が全て None でないなら True を返す"""
                        for element in iterable:
                            if element is None:
                                return False
                        return True

                    # 全て取得できたら抜ける
                    # 一つの EIT に全ての情報が含まれているとは限らないため
                    if (all_not_none(result.values()) and
                        all_not_none(result['video'].values()) and
                        all_not_none(result['primary_audio'].values())):
                        break

                else: # 多重ループを抜けるトリック
                    continue
                break

            # カウントを追加
            count += 1

            # ループが 100 回を超えたら、番組詳細とジャンルの初期値を設定する
            # 稀に番組詳細やジャンルが全く設定されていない番組があり、存在しない情報を探して延々とループするのを避けるため
            if count > 100:
                if result['detail'] is None:
                    result['detail'] = dict()
                if result['genre'] is None:
                    result['genre'] = list()

            # ループが 1000 回を超えたら（＝10回シークしても放送時間が確定しなかったら）、タイムアウトでループを抜ける
            if count > 1000:
                break

            # ループが 100 で割り切れるたびに現在の位置から 188MB シークする
            # ループが 100 以上に到達しているときはおそらく放送時間が未定の番組なので、放送時間が確定するまでシークする
            if count % 100 == 0:
                self.ts.seek(188000000, 1)  # 188MB

        return result


    def getRecordStartTime(self) -> datetime:
        """
        TS 内の TOT (Time Offset Table) と PCR (Program Clock Reference) の差分から、おおよその録画開始時刻を算出する

        Returns:
            datetime: 録画開始時刻の datetime
        """

        # 誤動作防止のため必ず最初にシークを戻す
        self.ts.seek(0)

        # TS 内最初の PCR (Packet Clock Reference)
        first_pcr:timedelta = self.getPCRTimeDelta()

        # TS 内最初の TOT (Time Offset Table)
        current_tot:datetime = next(self.ts.sections(TimeOffsetSection)).JST_time

        # TOT 取得直後の PCR (Packet Clock Reference)
        current_pcr:timedelta = self.getPCRTimeDelta()

        # TOT は 5 秒間隔で送出されているため、そのままでは誤差が生じる
        # current_pcr と first_pcr の差分で TOT を取得するまでの時間を推測し、それを current_tot から引くことで、推定録画開始時刻を算出する
        first_tot:datetime = current_tot - (current_pcr - first_pcr)

        # なぜかここで取得した推定録画開始時刻は実際の時刻より少し早くなっている
        # （おおよその実測値で、録画時間や録画マージン→切り替わりと比較するとよくわかる）
        # 仕方がないので（どうにかできそうだけど）、実測値から一律で5.15秒足す
        first_tot = first_tot + timedelta(seconds=5.15)

        # タイムゾーンを日本時間 (+9:00) に設定
        return first_tot.astimezone(timezone(timedelta(hours=9)))


    def getRecordEndTime(self) -> datetime:
        """
        TS 内の TOT (Time Offset Table) と PCR (Program Clock Reference) の差分から、おおよその録画終了時刻を算出する

        Returns:
            datetime: 録画終了時刻の datetime
        """

        # ファイルの末尾から 188000 (188KB) まで遡ってシーク
        # だいたい PCR は 9 つ取得できる
        # 注意!!! シークする際は必ず 188（ TS パケット長）の倍数にすること
        # そうしないと PCR が狂った値になる（ PCR は TS ヘッダの延長線上 (adaptation field) にあるので、188 の倍数でないとおかしくなるのは当たり前）
        self.ts.seek(-1880000, 2)

        # PCR を取得して配列に格納
        pcrs = list()
        for _ in self.ts:
            pcr = self.getPCRTimeDelta()
            if pcr is not None:
               pcrs.append(pcr)

        # TS 内最後の PCR (Packet Clock Reference)
        last_pcr:timedelta = pcrs[-1]  # 配列の最後の要素

        # ファイルの末尾から 1880000 (1880KB) まで遡ってシーク
        self.ts.seek(-18800000, 2)

        # TOT を取得して配列に格納
        tots = list()
        for tot in self.ts.sections(TimeOffsetSection):
            tots.append(tot.JST_time)
            pcr = self.getPCRTimeDelta()
            if pcr is not None:
                # 次の TOT 取得直前の PCR (Packet Clock Reference)
                current_pcr:timedelta = copy(pcr)

        # TS 内最後の TOT (Time Offset Table)
        current_tot:datetime = tots[-1]  # 配列の最後の要素

        # TOT は 5 秒間隔で送出されているため、そのままでは誤差が生じる
        # last_pcr と current_pcr の差分で TOT を取得した後 EOF までの時間を推測し、それを current_tot に足すことで、推定録画終了時刻を算出する
        last_tot:datetime = current_tot + (last_pcr - current_pcr)

        # なぜかここで取得した推定録画終了時刻は実際の時刻より少し速くなっている
        # 仕方がないので（どうにかできそうだけど）、実測値から一律で0.5秒足す
        last_tot = last_tot + timedelta(seconds=0.5)

        # タイムゾーンを日本時間 (+9:00) に設定
        return last_tot.astimezone(timezone(timedelta(hours=9)))


    def getPCRTimeDelta(self) -> timedelta:
        """
        現在の TS のシーク位置の PCR (Program Clock Reference) を取得する

        Returns:
            timedelta: PCR から算出した timedelta（時間差分）
        """

        try:
            for packet in self.ts:

                # packet から Adaptation Field を取得
                adaptation = adaptation_field(packet)
                if (adaptation == b''): continue

                # PCR が存在する場合のみ
                if adaptation.with_PCR is not None:

                    # 生の PCR
                    pcr_raw = adaptation.with_PCR.program_clock_reference_base

                    # 秒数で割って timedelta にする
                    # 参考: https://www.gcd.org/blog/2010/09/648/
                    pcr = timedelta(seconds=pcr_raw / 90000)
                    return pcr

            # PCR が存在しない
            return None

        # IndexError が発生したら None を返す
        except IndexError:
            return None


if __name__ == '__main__':

    # 引数が足りない
    if len(sys.argv) <= 1:
        print(f'{sys.argv[0]}: TS ファイルから各種情報を取得して JSON で出力するツール')
        print(f'usage: $ python {sys.argv[0]} TSFilePath [OutputPath]')
        sys.exit(0)

    # TSInformation を初期化
    tsinfo = TSInformation(sys.argv[1])

    # TS 内の各種情報を抽出
    extract = tsinfo.extract()

    # 参考: https://www.yoheim.net/blog.php?q=20170703
    def json_serial(obj:object):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, (timedelta)):
            return obj.total_seconds()
        raise TypeError('Type %s not serializable' % type(obj))

    # JSON 化して出力
    if len(sys.argv) == 3:
        with open(sys.argv[2], mode='wt', encoding='utf-8') as file:
            json.dump(extract, file, default=json_serial, ensure_ascii=False, indent=4)
    else:
        print(json.dumps(extract, default=json_serial, ensure_ascii=False, indent=4))
