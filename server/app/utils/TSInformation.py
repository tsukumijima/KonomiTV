
import multiprocessing
import re
from typing import ClassVar, Literal, cast

from ariblib.aribstr import AribString
from tortoise import Tortoise, connections
from tortoise.exceptions import ConfigurationError
from tortoise.expressions import Q


# 地デジ放送エリアの Literal 型（北海道は7分割、計53選択肢）
TerrestrialRegion = Literal[
    '北海道（札幌）', '北海道（函館）', '北海道（旭川）', '北海道（帯広）',
    '北海道（釧路）', '北海道（北見）', '北海道（室蘭）',
    '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
    '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
    '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県',
    '岐阜県', '静岡県', '愛知県', '三重県',
    '滋賀県', '京都府', '大阪府', '兵庫県', '奈良県', '和歌山県',
    '鳥取県', '島根県', '岡山県', '広島県', '山口県',
    '徳島県', '香川県', '愛媛県', '高知県',
    '福岡県', '佐賀県', '長崎県', '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県',
]


class TSInformation:
    """ 日本の放送波の MPEG-TS PSI/SI の解析時に役立つ雑多なユーティリティ """

    # 映像のコーデック
    # ref: https://github.com/Chinachu/Mirakurun/blob/master/src/Mirakurun/EPG.ts#L23-L27
    STREAM_CONTENT: ClassVar[dict[int, str]] = {
        0x01: 'MPEG-2',
        0x05: 'H.264',
        0x09: 'H.265',
    }

    # 映像の解像度
    # ref: https://github.com/Chinachu/Mirakurun/blob/master/src/Mirakurun/EPG.ts#L29-L63
    COMPONENT_TYPE: ClassVar[dict[int, str]] = {
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

    # 地域名 → 対応する地域識別のリスト（県域 + 広域）
    # 北海道は放送エリアごとに地域識別が異なるため、個別に分割
    # ARIB TR-B14 第五分冊 第七編 9.1「各種数値割り当て一覧」に基づく
    TERRESTRIAL_REGION_TO_REGION_IDS: ClassVar[dict[TerrestrialRegion, list[int]]] = {
        # 北海道（地域識別が異なる7つの放送エリア + 北海道域）
        '北海道（札幌）': [10, 4],   # 札幌 + 北海道域
        '北海道（函館）': [11, 4],   # 函館 + 北海道域
        '北海道（旭川）': [12, 4],   # 旭川 + 北海道域
        '北海道（帯広）': [13, 4],   # 帯広 + 北海道域
        '北海道（釧路）': [14, 4],   # 釧路 + 北海道域
        '北海道（北見）': [15, 4],   # 北見 + 北海道域
        '北海道（室蘭）': [16, 4],   # 室蘭 + 北海道域
        # 東北
        '青森県': [22],
        '岩手県': [20],
        '宮城県': [17],
        '秋田県': [18],
        '山形県': [19],
        '福島県': [21],
        # 関東（関東広域を含む）
        '茨城県': [26, 1],
        '栃木県': [28, 1],
        '群馬県': [25, 1],
        '埼玉県': [29, 1],
        '千葉県': [27, 1],
        '東京都': [23, 1],
        '神奈川県': [24, 1],
        # 甲信越・北陸
        '新潟県': [31],
        '富山県': [37],
        '石川県': [34],
        '福井県': [36],
        '山梨県': [32],
        '長野県': [30],
        # 東海（中京広域を含む）
        '静岡県': [35],
        '愛知県': [33, 3],
        '岐阜県': [39, 3],
        '三重県': [38, 3],
        # 近畿（近畿広域を含む）
        '滋賀県': [45, 2],
        '京都府': [41, 2],
        '大阪府': [40, 2],
        '兵庫県': [42, 2],
        '奈良県': [44, 2],
        '和歌山県': [43, 2],
        # 中国（岡山香川・島根鳥取を含む）
        '鳥取県': [49, 6],
        '島根県': [48, 6],
        '岡山県': [47, 5],
        '広島県': [46],
        '山口県': [50],
        # 四国（岡山香川を含む）
        '徳島県': [53],
        '香川県': [52, 5],
        '愛媛県': [51],
        '高知県': [54],
        # 九州・沖縄
        '福岡県': [55],
        '佐賀県': [61],
        '長崎県': [57],
        '熊本県': [56],
        '大分県': [60],
        '宮崎県': [59],
        '鹿児島県': [58],
        '沖縄県': [62],
    }

    # 地域識別 → 対応する地域名のリスト（逆引きマッピング）
    # TERRESTRIAL_REGION_TO_REGION_IDS から事前に構築して高速な逆引きを実現する
    # region_id をキーとし、その region_id を持つすべての地域名をリストで保持する
    REGION_ID_TO_REGION_NAMES: ClassVar[dict[int, list[TerrestrialRegion]]] = {}

    # formatString() で使用する変換マップ
    __format_string_translation_map: dict[int, str] | None = None
    __format_string_regex: re.Pattern[str] | None = None
    __format_string_regex_table: dict[str, str] | None = None


    @classmethod
    def __buildFormatStringTranslationMap(cls) -> None:
        """
        formatString() で使用する変換マップや正規表現を構築する
        一度のみ実行され、以降はキャッシュされる
        """

        # すでに構築済みの場合は何もしない
        if cls.__format_string_translation_map is not None and cls.__format_string_regex is not None:
            return

        # 全角英数を半角英数に置換
        # ref: https://github.com/ikegami-yukino/jaconv/blob/master/jaconv/conv_table.py
        zenkaku_table = '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ'
        hankaku_table = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        merged_table = dict(zip(list(zenkaku_table), list(hankaku_table)))

        # 全角記号を半角記号に置換
        symbol_zenkaku_table = '＂＃＄％＆＇（）＋，－．／：；＜＝＞［＼］＾＿｀｛｜｝　'
        symbol_hankaku_table = '"#$%&\'()+,-./:;<=>[\\]^_`{|} '
        merged_table.update(zip(list(symbol_zenkaku_table), list(symbol_hankaku_table)))
        merged_table.update({
            # 一部の半角記号を全角に置換
            # 主に見栄え的な問題（全角の方が字面が良い）
            '!': '！',
            '?': '？',
            '*': '＊',
            '~': '～',
            # シャープ → ハッシュ
            '♯': '#',
            # 波ダッシュ → 全角チルダ
            ## EDCB は ～ を全角チルダとして扱っているため、KonomiTV でもそのように統一する
            ## TODO: 番組検索を実装する際は検索文字列の波ダッシュを全角チルダに置換する下処理が必要
            ## ref: https://qiita.com/kasei-san/items/3ce2249f0a1c1af1cbd2
            '〜': '～',
        })

        # 番組表で使用される囲み文字の置換テーブル
        ## ref: https://note.nkmk.me/python-chr-ord-unicode-code-point/
        ## ref: https://github.com/l3tnun/EPGStation/blob/v2.6.17/src/util/StrUtil.ts#L7-L46
        ## ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-230526/EpgDataCap3/EpgDataCap3/ARIB8CharDecode.cpp#L1324-L1614
        enclosed_characters_table = {
            '\U0001f14a': '[HV]',
            '\U0001f14c': '[SD]',
            '\U0001f13f': '[P]',
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
            '\U0001f19b': '[3D]',
            '\U0001f19c': '[2ndScr]',
            '\U0001f19d': '[2K]',
            '\U0001f19e': '[4K]',
            '\U0001f19f': '[8K]',
            '\U0001f1a0': '[5.1]',
            '\U0001f1a1': '[7.1]',
            '\U0001f1a2': '[22.2]',
            '\U0001f1a3': '[60P]',
            '\U0001f1a4': '[120P]',
            '\U0001f1a5': '[d]',
            '\U0001f1a6': '[HC]',
            '\U0001f1a7': '[HDR]',
            '\U0001f1a8': '[Hi-Res]',
            '\U0001f1a9': '[Lossless]',
            '\U0001f1aa': '[SHV]',
            '\U0001f1ab': '[UHD]',
            '\U0001f1ac': '[VOD]',
            '\U0001f23b': '[配]',
        }

        # Unicode の囲み文字を大かっこで囲った文字に置換する
        ## EDCB で EpgDataCap3_Unicode.dll を利用している場合や、Mirakurun 3.9.0-beta.24 以降など、
        ## 番組情報取得元から Unicode の囲み文字が送られてくる場合に対応するためのもの
        ## Unicode の囲み文字はサロゲートペアなどで扱いが難しい上に KonomiTV では囲み文字を CSS でハイライトしているため、Unicode にするメリットがない
        ## ref: https://note.nkmk.me/python-str-replace-translate-re-sub/
        merged_table.update(enclosed_characters_table)

        # 変換マップを構築し、クラス変数に格納
        cls.__format_string_translation_map = str.maketrans(merged_table)

        # 逆に代替の文字表現に置換された ARIB 外字を Unicode に置換するテーブル
        ## 主に EDCB (EpgDataCap3_Unicode.dll 不使用) 環境向けの処理
        ## EDCB は通常 Shift-JIS で表現できない文字をサロゲートペア範囲外の文字も含めてすべて代替の文字表現に変換するが、これはこれで見栄えが悪い
        ## そこで、サロゲートペアなしで表現できて、一般的な日本語フォントでグリフが用意されていて、
        ## かつ他の文字表現から明確に判別可能でそのままでは分かりづらい文字表現だけ Unicode に置換する
        ## ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-230526/EpgDataCap3/EpgDataCap3/ARIB8CharDecode.cpp#L1324-L1614
        cls.__format_string_regex_table = {
            # '[・]': '⚿',  # グリフが用意されていないことが多い
            '(秘)': '㊙',
            'm^2': 'm²',
            'm^3': 'm³',
            'cm^2': 'cm²',
            'cm^3': 'cm³',
            'km^2': 'km²',
            '[社]': '㈳',
            '[財]': '㈶',
            '[有]': '㈲',
            '[株]': '㈱',
            '[代]': '㈹',
            # '(問)': '㉄',  # グリフが用意されていないことが多い
            '^2': '²',
            '^3': '³',
            # '(箏): '㉇',  # グリフが用意されていないことが多い
            '(〒)': '〶',
            '()()': '⚾',
        }

        # 正規表現を構築し、クラス変数に格納
        cls.__format_string_regex = re.compile("|".join(map(re.escape, cls.__format_string_regex_table.keys())))


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

        # 変換マップを構築 (初回以降はキャッシュされる)
        cls.__buildFormatStringTranslationMap()
        assert cls.__format_string_translation_map is not None
        assert cls.__format_string_regex is not None
        assert cls.__format_string_regex_table is not None

        # 置換を実行
        result = result.translate(cls.__format_string_translation_map)
        result = cls.__format_string_regex.sub(lambda match: cast(dict[str, str], cls.__format_string_regex_table)[match.group(0)], result)

        # 置換した文字列を返す
        return result


    @staticmethod
    def getNetworkType(network_id: int) -> Literal['GR', 'BS', 'CS', 'CATV', 'SKY', 'BS4K', 'OTHER']:
        """
        ネットワーク ID からネットワークの種別を取得する
        種別は GR (地デジ)・BS・CS・CATV・SKY (SPHD)・BS4K・OTHER (不明なネットワーク ID のチャンネル) のいずれか

        Args:
            network_id (int): ネットワーク ID

        Returns:
            str: GR・BS・CS・CATV・SKY・BS4K・OTHER のいずれか
        """

        # 以下は ARIB STD-B10 第2部 付録N より抜粋
        # ref: https://web.archive.org/web/2if_/http://www.arib.or.jp/english/html/overview/doc/2-STD-B10v5_3.pdf#page=256
        # ref: https://www.arib.or.jp/english/html/overview/doc/6-STD-B10v5_13-E1.pdf#page=273
        # ref: https://www.arib.or.jp/english/html/overview/doc/6-STD-B10v5_13-E1.pdf#page=274

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
        # 高度ケーブル自主放送: 0xFFF7 (ケーブル4Kチャンネル (H.264, H.265))
        if network_id == 0xFFFE or network_id == 0xFFFA or network_id == 0xFFFD or network_id == 0xFFF9 or network_id == 0xFFF7:
            return 'CATV'

        # 124/128度CSデジタル放送
        # SPHD: 0x000A (スカパー！プレミアムサービス)
        # SPSD-PerfecTV: 0x0001 (スターデジオ: 運用終了)
        # SPSD-SKY: 0x0003 (運用終了)
        if network_id == 0x000A or network_id == 0x0001 or network_id == 0x0003:
            return 'SKY'

        # 高度BSデジタル放送: 0x000B (BS4K)
        # 高度110度CSデジタル放送: 0x000C (CS4K: 運用終了)
        if network_id == 0x000B or network_id == 0x000C:
            return 'BS4K'

        # 不明なネットワーク ID のチャンネル
        return 'OTHER'


    @staticmethod
    def getRegionIDFromNetworkID(network_id: int) -> int | None:
        """
        地デジのネットワーク ID から地域識別を取得する

        ARIB TR-B14 第五分冊 第七編 9.1 より:
        network_id = 0x7FF0 - 0x0010 × 地域識別 + 地域事業者識別 - 0x0400 × 県複フラグ

        Args:
            network_id (int): ネットワーク ID

        Returns:
            int | None: 地域識別 (1-62) (地デジ以外の場合は None)
        """

        # 地デジの NID 範囲チェック
        # 県複フラグ=0: 0x7C10 ~ 0x7FEF
        # 県複フラグ=1: 0x7810 ~ 0x7BEF
        if not (0x7800 <= network_id <= 0x7FF0):
            return None

        # 県複フラグの判定と補正
        # NID < 0x7C00 なら県複フラグ=1 と判断し、0x0400 を加算して正規化
        if network_id < 0x7C00:
            network_id += 0x0400

        # 地域識別の計算
        # network_id = 0x7FF0 - 0x0010 × 地域識別 + 地域事業者識別
        # 地域事業者識別は 0〜15 なので、0x0010 で割る場合は切り捨てではなく切り上げが必要
        # (region_broadcaster_id が 0 以外だと、切り捨てでは地域識別が 1 ずれる)
        region_id = (0x7FF0 - network_id + 0x000F) // 0x0010
        return region_id if 1 <= region_id <= 62 else None


    @staticmethod
    def getRegionNamesFromNetworkID(network_id: int) -> list[TerrestrialRegion] | None:
        """
        地デジのネットワーク ID から該当するすべての地域名を取得する

        事前に構築した REGION_ID_TO_REGION_NAMES を使用して高速に逆引きを行う
        広域放送局 (region_id: 1-6) の場合、その広域に含まれるすべての都道府県名をリストで返す

        Args:
            network_id (int): ネットワーク ID

        Returns:
            list[TerrestrialRegion] | None: 地域名のリスト (地デジ以外または不明な場合は None)
        """

        # ネットワーク ID から地域識別を取得
        region_id = TSInformation.getRegionIDFromNetworkID(network_id)
        if region_id is None:
            return None

        # 事前に構築した逆引きマッピングから地域名リストを取得
        region_names = TSInformation.REGION_ID_TO_REGION_NAMES.get(region_id)
        if region_names is None:
            return None

        # リストのコピーを返す（呼び出し元での変更を防ぐ）
        return list(region_names)


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


    @staticmethod
    def calculateRemoconID(type: Literal['BS', 'CS', 'CATV', 'SKY', 'BS4K'], service_id: int) -> int:
        """
        サービス ID からチャンネルのリモコン番号を算出する (地デジ以外向け)

        Args:
            type (Literal['BS', 'CS', 'CATV', 'SKY', 'BS4K']): チャンネル種別 (地デジ以外)
            service_id (int): サービス ID

        Returns:
            int: 算出されたリモコン番号
        """

        assert type != 'GR', 'GR type channel is not supported.'

        # 基本的にはサービス ID をリモコン番号とする
        remocon_id = service_id

        # BS: 一部のチャンネルに決め打ちでチャンネル番号を割り当てる
        if type == 'BS':
            if 101 <= service_id <= 102:
                remocon_id = 1
            elif 103 <= service_id <= 104:
                remocon_id = 3
            elif 141 <= service_id <= 149:
                remocon_id = 4
            elif 151 <= service_id <= 159:
                remocon_id = 5
            elif 161 <= service_id <= 169:
                remocon_id = 6
            elif 171 <= service_id <= 179:
                remocon_id = 7
            elif 181 <= service_id <= 189:
                remocon_id = 8
            elif 191 <= service_id <= 193:
                remocon_id = 9
            elif 200 <= service_id <= 202:
                remocon_id = 10
            elif service_id == 211:
                remocon_id = 11
            elif service_id == 222:
                remocon_id = 12

        # SKY: サービス ID を 1024 で割った余りをリモコン番号 (=チャンネル番号) とする
        ## SPHD (network_id=10) のチャンネル番号は service_id - 32768 、
        ## SPSD (SKYサービス系: network_id=3) のチャンネル番号は service_id - 16384 で求められる
        ## 両者とも 1024 の倍数なので、1024 で割った余りからチャンネル番号が算出できる
        elif type == 'SKY':
            remocon_id = service_id % 1024

        return remocon_id


    @staticmethod
    async def calculateChannelNumber(
        type: Literal['GR', 'BS', 'CS', 'CATV', 'SKY', 'BS4K'],
        network_id: int,
        service_id: int,
        remocon_id: int,
        same_network_id_counts: dict[int, int] | None = None,
        same_remocon_id_counts: dict[int, int] | None = None,
    ) -> str:
        """
        チャンネルの3桁チャンネル番号を算出する (ex: 011, 031-1, 211)

        Args:
            type (Literal['GR', 'BS', 'CS', 'CATV', 'SKY', 'BS4K']): チャンネル種別
            network_id (int): ネットワーク ID
            service_id (int): サービス ID
            remocon_id (int): リモコン番号
            same_network_id_counts (dict[int, int] | None): 同じネットワーク ID のサービスのカウント
            same_remocon_id_counts (dict[int, int] | None): 同じリモコン番号のサービスのカウント

        Returns:
            str: 算出されたチャンネル番号
        """

        # 循環インポート回避のためここでインポート
        from app.constants import DATABASE_CONFIG

        # 基本的にはサービス ID をチャンネル番号とする
        channel_number = str(service_id).zfill(3)

        # 地デジ: リモコン番号からチャンネル番号を算出する (枝番処理も行う)
        if type == 'GR' and same_remocon_id_counts is not None and same_network_id_counts is not None:

            # 同じリモコン番号のサービスのカウントを定義
            if remocon_id not in same_remocon_id_counts:  # まだキーが存在しないとき
                # 011(-0), 011-1, 011-2 のように枝番をつけるため、ネットワーク ID とは異なり -1 を基点とする
                same_remocon_id_counts[remocon_id] = -1

            # 同じネットワーク内にある最初のサービスのときだけ、同じリモコン番号のサービスのカウントを追加
            # これをやらないと、サブチャンネルまで枝番処理の対象になってしまう
            if same_network_id_counts[network_id] == 1:
                same_remocon_id_counts[remocon_id] += 1

            # 上2桁はリモコン番号から、下1桁は同じネットワーク内にあるサービスのカウント
            channel_number = str(remocon_id).zfill(2) + str(same_network_id_counts[network_id])

            # 同じリモコン番号のサービスが複数ある場合、枝番をつける
            if same_remocon_id_counts[remocon_id] > 0:
                channel_number += '-' + str(same_remocon_id_counts[remocon_id])

        # 地デジ (録画番組向け): リモコン番号からチャンネル番号を算出する (枝番処理も行うが、DB アクセスが発生する)
        elif type == 'GR':
            from app.models.Channel import Channel

            # 同じネットワーク内にあるサービスのカウントを取得
            ## 地デジのサービス ID は、ARIB TR-B14 第五分冊 第七編 9.1 によると
            ## (地域識別:6bit)(県複フラグ:1bit)(サービス種別:2bit)(地域事業者識別:4bit)(サービス番号:3bit) の 16bit で構成されている
            ## 0x0007 はビット単位に直すと 0b0000000110000111 になるので、AND 演算でビットマスク（1以外のビットを強制的に0に設定）すると、
            ## サービス番号 (0~7) のみを取得できる (1~8 に直すために +1 する)
            same_network_id_count = (service_id & 0x0007) + 1

            # 上2桁はリモコン番号から、下1桁は同じネットワーク内にあるサービスのカウント
            channel_number = str(remocon_id).zfill(2) + str(same_network_id_count)

            # Tortoise ORM のコネクションを初期化する
            ## MetadataAnalyzer はマルチプロセスまたは単独で実行されるため、通常メインプロセスのコネクションは使用できず、独自に初期化する必要がある
            cleanup_required = False
            if multiprocessing.current_process().name != 'MainProcess':
                # マルチプロセス時は問答無用でデータベース接続を初期化する
                ## Windows だと既存のコネクションを破棄せずとも接続を初期化すれば良いが、Linux では必ず破棄してから初期化する必要があったはず
                ## おそらくマルチプロセス時に変数の状態こそ fork 先に引き継がれるが、コネクション自体は正しく引き継がれない (?) のが原因
                connections.discard('default')
                await Tortoise.init(config=DATABASE_CONFIG)
                cleanup_required = True
            else:
                # シングルプロセス時はコネクションが取得できない場合のみ初期化
                try:
                    conn = Tortoise.get_connection('default')
                    # コネクションが取得できても実際は使えない可能性があるのでテスト
                    await conn.execute_query('SELECT 1')
                except (ConfigurationError, Exception):
                    connections.discard('default')
                    await Tortoise.init(config=DATABASE_CONFIG)
                    cleanup_required = True

            # 同じチャンネル番号のサービスのカウントを DB から取得
            ## network_id と service_id の組み合わせは (CATV を除き日本全国で一意) なので、
            ## これらが異なる場合は同じリモコン番号/チャンネル番号でも別チャンネルになる
            ## ex: tvk1 (gr031) / NHK総合1・福岡 (gr031)
            same_channel_number_count = await Channel.filter(
                ~(Q(network_id=network_id) & Q(service_id=service_id)),  # network_id と service_id の組み合わせが異なる
                channel_number=channel_number,  # チャンネル番号が同じ
                type='GR',  # 地デジのみ
            ).count()

            # Tortoise ORM を独自に初期化した場合は、開いた Tortoise ORM のコネクションを明示的に閉じる
            # コネクションを閉じないと Ctrl+C を押下しても終了できない
            if cleanup_required is True:
                await Tortoise.close_connections()

            # 異なる NID-SID で同じチャンネル番号のサービスが複数ある場合、枝番をつける
            ## same_channel_number_count は自身を含まないため、1 以上の場合は枝番をつける
            if same_channel_number_count >= 1:
                channel_number += '-' + str(same_channel_number_count)

        # SKY: サービス ID を 1024 で割った余りをチャンネル番号とする
        ## SPHD (network_id=10) のチャンネル番号は service_id - 32768 、
        ## SPSD (SKYサービス系: network_id=3) のチャンネル番号は service_id - 16384 で求められる
        ## 両者とも 1024 の倍数なので、1024 で割った余りからチャンネル番号が
        ## 両者とも 1024 の倍数なので、1024 で割った余りからチャンネル番号が算出できる
        elif type == 'SKY':
            channel_number = str(service_id % 1024).zfill(3)

        return channel_number


    @staticmethod
    def calculateIsSubchannel(type: Literal['GR', 'BS', 'CS', 'CATV', 'SKY', 'BS4K'], service_id: int) -> bool:
        """ チャンネルがサブチャンネルかどうかを算出する """

        # 地デジ: サービス ID に 0x0187 を AND 演算（ビットマスク）した時に 0 でない場合
        ## 地デジのサービス ID は、ARIB TR-B14 第五分冊 第七編 9.1 によると
        ## (地域識別:6bit)(県複フラグ:1bit)(サービス種別:2bit)(地域事業者識別:4bit)(サービス番号:3bit) の 16bit で構成されている
        ## 0x0187 はビット単位に直すと 0b0000000110000111 になるので、AND 演算でビットマスク（1以外のビットを強制的に0に設定）すると、
        ## サービス種別とサービス番号のみを取得できる  ビットマスクした値のサービス種別が 0（テレビ型）でサービス番号が 0（プライマリサービス）であれば
        ## メインチャンネルと判定できるし、そうでなければサブチャンネルだと言える
        if type == 'GR':
            is_subchannel = (service_id & 0x0187) != 0

        # BS: EDCB / Mirakurun から得られる情報からはサブチャンネルかを判定できないため、決め打ちで設定
        elif type == 'BS':
            # サービス ID が以下のリストに含まれるかどうか
            if ((service_id in [102, 104]) or
                (142 <= service_id <= 149) or
                (152 <= service_id <= 159) or
                (162 <= service_id <= 169) or
                (172 <= service_id <= 179) or
                (182 <= service_id <= 189) or
                (service_id in [232, 233])):
                is_subchannel = True
            else:
                is_subchannel = False

        # それ以外: サブチャンネルという概念自体がないため一律で False に設定
        else:
            is_subchannel = False

        return is_subchannel


# REGION_ID_TO_REGION_NAMES の初期化
# TERRESTRIAL_REGION_TO_REGION_IDS から逆引きマッピングを構築する
# モジュールのインポート時に一度だけ実行される
for _region_name, _region_ids in TSInformation.TERRESTRIAL_REGION_TO_REGION_IDS.items():
    for _region_id in _region_ids:
        if _region_id not in TSInformation.REGION_ID_TO_REGION_NAMES:
            TSInformation.REGION_ID_TO_REGION_NAMES[_region_id] = []
        TSInformation.REGION_ID_TO_REGION_NAMES[_region_id].append(_region_name)
