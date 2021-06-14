
from copy import copy
from datetime import date, datetime, timedelta, timezone
import json
import sys

import ariblib
import ariblib.event
from ariblib.descriptors import (
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
    TimeOffsetSection,
)


class TSInformation:

    def __init__(self, ts:TransportStreamFile):

        # tsopen() で取得した TS データ
        self.ts = ts

    def extract(self) -> str:
        """TS 内から得られる各種番組情報などを抽出して辞書にまとめる

        Returns:
            str: TS の各種情報をまとめた辞書
        """

        # TOT (Time Offset Table) からおおよその録画開始時刻・録画終了時刻を取得
        # TOT だけだと正確でないので、PCR (Packet Clock Reference) の値で補完する
        record_start_time = tsinfo.getRecordStartTime()
        record_end_time = tsinfo.getRecordEndTime()

        # 録画時間を算出
        record_duration = record_end_time - record_start_time

        # SDT (Service Description Table) からチャンネル情報を取得
        sdt = tsinfo.getSDTInformation()

        # EIT (Event Information Table) から現在と次の番組情報を取得
        # 「現在」は録画開始時点のものなので、録画マージンがある場合基本的には eit_current には前の番組の情報が入る
        eit_current = tsinfo.getEITInformation(0)
        eit_following = tsinfo.getEITInformation(1)

        # 録画開始時刻と次の番組の開始時刻を比較して、差が1分以内（録画マージン）なら次の番組情報を利用する
        # 基本的に録画マージンがあるはずなので、番組途中から録画したとかでなければ次の番組情報を使う事になるはず
        if eit_following['start_time'] - record_start_time <= timedelta(minutes=1):
            eit = copy(eit_following)
        else:
            eit = copy(eit_current)

        return {
            'record': {
                'start_time': record_start_time,
                'end_time': record_end_time,
                'duration': record_duration,
            },
            'service': sdt,
            'program': eit,
        }

    def getSDTInformation(self) -> dict:

        """TS 内の SDT (Service Descrition Table) からサービス（チャンネル）情報を取得する
        地上波のみ、リモコンキー ID を取得するため NIT (Network Information Table) からも情報を取得する

        Returns:
            dict: サービス（チャンネル）情報が入った辞書
        """

        # サービスタイプ
        # 参考: https://github.com/youzaka/ariblib/blob/master/ariblib/constants.py#L276
        SERVICE_TYPE = {
            0x00: '未定義',
            0x01: 'デジタルTVサービス',
            0x02: 'デジタル音声サービス',
            0xA1: '臨時映像サービス',
            0xA2: '臨時音声サービス',
            0xA3: '臨時データサービス',
            0xA4: 'エンジニアリングサービス',
            0xA5: 'プロモーション映像サービス',
            0xA6: 'プロモーション音声サービス',
            0xA7: 'プロモーションデータサービス',
            0xA8: '事前蓄積用データサービス',
            0xA9: '蓄積専用データサービス',
            0xAA: 'ブックマーク一覧データサービス',
            0xAB: 'サーバー型サイマルサービス',
            0xAC: '独立ファイルサービス',
            0xC0: 'データサービス',
            0xC1: 'TLVを用いた蓄積型サービス',
            0xC2: 'マルチメディアサービス',
        }

        # 雛形
        result = {
            'service_id': None,
            'network_id': None,
            'remote_control_key_id': None,
            'service_type': None,
            'service_name': None,
            'transport_stream_name': None,
        }

        # 誤動作防止のため必ず最初にシークを戻す
        self.ts.seek(0)

        # TS から SDT (Service Description Table) を抽出
        for sdt in self.ts.sections(ActualStreamServiceDescriptionSection):

            # NetworkID を取得
            result['network_id'] = sdt.original_network_id

            # SDT から得られる ServiceDescriptor 内の情報（サービスタイプ・サービス名）を取得
            for service in sdt.services:

                print(service.service_id)

                # ServiceID を取得
                result['service_id'] = service.service_id

                for sd in service.descriptors[ServiceDescriptor]:
                    result['service_type'] = SERVICE_TYPE[int(hex(sd.service_type), 16)]
                    result['service_name'] = str(sd.service_name)
                    break
                else:
                    continue
                break
            else:
                continue
            break

        # 地デジのみ（ network_id が 30000 ～ 40000 ）
        # BS はどうやら取得できないらしい（形式が違うので当然か？）
        if result['network_id'] > 30000 and result['network_id'] < 40000:

            # TS から NIT (Network Information Table) を抽出
            for nit in self.ts.sections(NetworkInformationSection):

                # SDT から得られる TSInformationDescriptor 内の情報（リモコンキー ID）を取得
                for transport_stream in nit.transport_streams:
                    for tsinformation in transport_stream.descriptors[TSInformationDescriptor]:
                        result['remote_control_key_id'] = tsinformation.remote_control_key_id
                        result['transport_stream_name'] = str(tsinformation.ts_name_char)
                        break
                    else:
                        continue
                    break
                else:
                    continue
                break

        return result

    def getEITInformation(self, eit_section_number:int) -> dict:

        """TS内の EIT (Event Information Table) から番組情報を取得する

        Args:
            eit_section_number (int): 取得したい EIT セクション（ 0 なら現在の番組、1 なら次の番組）

        Returns:
            dict: 番組情報が入った辞書
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

        # 雛形
        result = {
            'title': None,
            'description': None,
            'detail': None,
            'start_time': None,
            'end_time': None,
            'duration': None,
            'is_free': None,
            'genres': None,
            'video': {
                'type': None,
                'codec': None,
                'resolution': None,
            },
            'audio': {
                'type': None,
                'sampling_rate': None,
            },
        }

        # 誤動作防止のため必ず最初にシークを戻す
        self.ts.seek(0)

        # TS から EIT (Event Information Table) を抽出
        for eit in self.ts.sections(ActualStreamPresentFollowingEventInformationSection):

            # section_number が一致したときだけ
            if eit.section_number == eit_section_number:

                # EIT から得られる各種 Descriptor 内の情報を取得
                # ariblib.event が各種 Descriptor のラッパーになっていたのでそれを利用
                for event_data in eit.events:

                    # EIT 内のイベントを取得
                    event = ariblib.event.Event(eit, event_data)

                    # 存在するなら順に追加していく
                    # 直接取得した文字列は AribSting になっているので、str に明示的に変換する

                    ## 番組名
                    if hasattr(event, 'title'):
                        result['title'] = str(event.title)
                    ## 番組概要
                    if hasattr(event, 'desc'):
                        result['description'] = str(event.desc)
                    ## 番組詳細
                    if hasattr(event, 'detail'):
                        result['detail'] = {}
                        # 見出し, 本文
                        for heading, text in event.detail.items():
                            result['detail'][heading] = str(text)
                    ## 番組長
                    if hasattr(event, 'duration'):
                        result['duration'] = event.duration
                    ## 番組開始時刻・番組終了時刻
                    if hasattr(event, 'start_time'):
                        # タイムゾーンを日本時間 (+9:00) に設定
                        result['start_time'] = event.start_time.astimezone(timezone(timedelta(hours=9)))
                        # 番組終了時刻を start_time と duration から算出
                        result['end_time'] = result['start_time'] + result['duration']
                    ## 無料放送かどうか
                    if hasattr(event, 'free_CA_mode'):
                        # ARIB TR-B15 第三分冊 (https://vs1p.manualzilla.com/store/data/006629648.pdf)
                        # free_CA_mode が 1 のとき有料番組、0 のとき無料番組だそう
                        # bool に変換した後、真偽を反転させる
                        result['is_free'] = not bool(event.free_CA_mode)
                    ## ジャンル
                    if hasattr(event, 'genre'):
                        result['genres'] = []
                        for index, _ in enumerate(event.genre):
                            result['genres'].append({
                                'major': event.genre[index],
                                'middle': event.subgenre[index],
                            })
                    ## 映像種別
                    if hasattr(event, 'video'):
                        result['video']['type'] = event.video
                    ## 映像コーデック
                    if hasattr(event, 'video_content'):
                        result['video']['codec'] = STREAM_CONTENT[int(hex(event.video_content), 16)]
                    ## 解像度
                    if hasattr(event, 'video_component'):
                        result['video']['resolution'] = COMPONENT_TYPE[int(hex(event.video_component), 16)]
                    ## 音声種別
                    if hasattr(event, 'audio'):
                        result['audio']['type'] = event.audio
                    ## サンプルレート
                    if hasattr(event, 'sampling_rate'):
                        result['audio']['sampling_rate'] = event.sampling_rate_string

                    def all_not_none(iterable):
                        """リスト内の要素が全て None でないなら True を返す"""
                        for element in iterable:
                            if element is None:
                                return False
                        return True

                    # 全て取得できたら抜ける
                    if (all_not_none(result.values()) and \
                        all_not_none(result['video'].values()) and \
                        all_not_none(result['audio'].values())):
                        break

                else: # 多重ループを抜けるトリック
                    continue
                break

        return result

    def getRecordStartTime(self) -> datetime:

        """TS 内の TOT (Time Offset Table) と PCR (Program Clock Reference) の差分から、おおよその録画開始時刻を算出する

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

        # なぜかここで取得した推定録画開始時刻は実際の時刻より3～5秒早くなっている
        # （おおよその実測値で、録画時間や録画マージン→切り替わりと比較するとよくわかる）
        # 仕方がないので（どうにかできそうだけど）、間を取って一律で3.5秒足す
        first_tot = first_tot + timedelta(seconds=3.5)

        # タイムゾーンを日本時間 (+9:00) に設定
        return first_tot.astimezone(timezone(timedelta(hours=9)))

    def getRecordEndTime(self) -> datetime:

        """TS 内の TOT (Time Offset Table) と PCR (Program Clock Reference) の差分から、おおよその録画終了時刻を算出する

        Returns:
            datetime: 録画終了時刻の datetime
        """

        # ファイルの末尾から 188000 (188KB) まで遡ってシーク
        # だいたい PCR は 9 つ取得できる
        # 注意!!! シークする際は必ず 188（ TS パケット長）の倍数にすること
        # そうしないと PCR が狂った値になる（ PCR 存在フラグは TS パケットに必ずあるので、188 の倍数でないとおかしくなるのは当たり前）
        self.ts.seek(-1880000, 2)

        # PCR を取得して配列に格納
        pcrs = []
        for _ in self.ts:
            pcr = self.getPCRTimeDelta()
            if pcr is not None:
               pcrs.append(pcr)

        # TS 内最後の PCR (Packet Clock Reference)
        last_pcr:timedelta = pcrs[-1]  # 配列の最後の要素

        # ファイルの末尾から 1880000 (1880KB) まで遡ってシーク
        self.ts.seek(-18800000, 2)

        # TOT を取得して配列に格納
        tots = []
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

        # なぜかここで取得した推定録画終了時刻は実際の時刻より1～2秒ほど遅くなっている
        # 仕方がないので（どうにかできそうだけど）、間を取って一律で1.5秒引く
        last_tot = last_tot - timedelta(seconds=1.5)

        # タイムゾーンを日本時間 (+9:00) に設定
        return last_tot.astimezone(timezone(timedelta(hours=9)))

    def getPCRTimeDelta(self) -> timedelta:

        """現在の TS のシーク位置の PCR (Program Clock Reference) を取得する

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

    # 引数の TS ファイルを開く
    # チャンクは 1000（だいたい 0.1 ～ 0.2 秒間隔）に設定
    with ariblib.tsopen(sys.argv[1], chunk=1000) as ts:

        # TSInformation を初期化
        tsinfo = TSInformation(ts)

        # TS 内の各種情報を抽出
        extract = tsinfo.extract()

        # 参考: https://www.yoheim.net/blog.php?q=20170703
        def json_serial(obj:object):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if isinstance(obj, (timedelta)):
                return obj.seconds
            raise TypeError('Type %s not serializable' % type(obj))

        # JSON 化して出力
        print(json.dumps(extract, default=json_serial, ensure_ascii=False, indent=4))
