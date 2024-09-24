
import re
from ariblib.aribstr import AribString
from typing import cast, Literal


class TSInformation:
    """ 録画 TS ファイル内に含まれる番組情報のユーティリティ """

    # 映像のコーデック
    # ref: https://github.com/Chinachu/Mirakurun/blob/master/src/Mirakurun/EPG.ts#L23-L27
    STREAM_CONTENT = {
        0x01: 'MPEG-2',
        0x05: 'H.264',
        0x09: 'H.265',
    }

    # 映像の解像度
    # ref: https://github.com/Chinachu/Mirakurun/blob/master/src/Mirakurun/EPG.ts#L29-L63
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
