
import { ChannelType } from '@/services/Channels';


/**
 * チャンネル周りのユーティリティ
 */
export class ChannelUtils {

    /**
     * display_channel_id からチャンネルタイプを取得する
     * @param display_channel_id display_channel_id
     * @returns チャンネルタイプ (不正な display_channel_id の場合は null)
     */
    static getChannelType(display_channel_id: string): ChannelType | null {
        try {
            const result = display_channel_id.match('(?<channel_type>[a-z]+(?:4k)?)\\d+')?.groups?.channel_type.toUpperCase();
            if (!result) return null;
            switch (result) {
                case 'GR': return 'GR';
                case 'BS': return 'BS';
                case 'CS': return 'CS';
                case 'CATV': return 'CATV';
                case 'SKY': return 'SKY';
                case 'BS4K': return 'BS4K';
                // ChannelType のいずれにもマッチしない場合
                default: return null;
            }
        } catch (e) {
            // 何かしらエラーが発生したということは display_channel_id が不正
            return null;
        }
    }


    /**
     * チャンネルの実況勢いから「多」「激多」「祭」を取得する
     * ref: https://ja.wikipedia.org/wiki/%E3%83%8B%E3%82%B3%E3%83%8B%E3%82%B3%E5%AE%9F%E6%B3%81
     * @param jikkyo_force チャンネルの実況勢い
     * @returns normal（普通）or many（多）or so-many（激多）or festival（祭）
     */
    static getChannelForceType(jikkyo_force: number | null): 'normal' | 'many' | 'so-many' | 'festival' {

        // 実況勢いが null（=対応する実況チャンネルがない）
        if (jikkyo_force === null) return 'normal';

        // 実況勢いが 500 コメント以上（祭）
        if (jikkyo_force >= 500) return 'festival';
        // 実況勢いが 200 コメント以上（激多）
        if (jikkyo_force >= 200) return 'so-many';
        // 実況勢いが 100 コメント以上（多）
        if (jikkyo_force >= 100) return 'many';

        // それ以外
        return 'normal';
    }


    /**
     * チャンネル名から対応する局タグを取得する
     * @param channel_name チャンネル名
     * @returns 局タグ (一致するものがない場合は null)
     */
    static getChannelHashtag(channel_name: string): string | null {

        const channel_list = {
            // NHK
            'NHK総合': '#nhk',
            'NHKEテレ': '#etv',
            // 民放
            // 北海道
            'HBC': '#hbc',
            '札幌テレビ': '#stv',
            'HTB': '#htb',
            'TVh': '#tvh',
            '北海道文化放送': '#uhb',
            // 青森
            'RAB青森放送': '#rab',
            '青森朝日放送': '#aba',
            'ATV青森テレビ': '#atv',
            // 岩手
            'テレビ岩手': '#tvi',
            '岩手朝日テレビ': '#iat',
            'IBCテレビ': '#ibc',
            'めんこいテレビ': '#mit',
            // 宮城
            'TBCテレビ': '#tbc',
            'ミヤギテレビ': '#mmt',
            '東日本放送': '#khb',
            '仙台放送': '#oxtv',
            // 秋田
            'ABS秋田放送': '#abs',
            '秋田朝日放送': '#aab',
            'AKT秋田テレビ': '#akt',
            // 山形
            '山形放送': '#ybc',
            '山形テレビ': '#yts',
            'TUY': '#tuy',
            'さくらんぼテレビ': '#say',
            // 福島
            '福島中央テレビ': '#fct',
            'KFB福島放送': '#kfb',
            'テレビユー福島': '#tuf',
            'FTV福島テレビ': '#ftv',
            // 新潟
            'TeNY': '#TeNY',
            '新潟テレビ21': '#uxtv',
            'BSN': '#bsn',
            'NST': '#nst',
            // 富山
            'KNBテレビ': '#knb',
            'チューリップテレビ': '#tut',
            '富山テレビ放送': '#toyamatv',
            // 石川
            'テレビ金沢': '#tv_kanazawa',
            'HAB': '#hab',
            'MRO': '#mro',
            '石川テレビ': '#ishikawatv',
            // 福井
            '福井放送': '#fbc',
            '福井テレビ': '#fukuitv',
            // 山梨
            '山梨放送': '#ybs',
            'UTYテレビ山梨': '#uty',
            // 長野
            'テレビ信州': '#tsb',
            '長野朝日放送': '#abn',
            'SBC信越放送': '#sbc',
            '長野放送': '#nbs',
            // 静岡
            'Daiichi-TV': '#sdt',
            '静岡朝日テレビ': '#satv',
            'SBS': '#sbs',
            'テレビ静岡': '#sut',
            // 三重
            '三重テレビ': '#mietv',
            // 岐阜
            'ぎふチャン': '#gifuchan',
            // 滋賀
            'BBCびわ湖放送': '#BBC_biwako',
            // 奈良
            '奈良テレビ': '#tvn',
            // 和歌山
            'WTV': '#telewaka',
            // 岡山香川
            'RNC西日本テレビ': '#rnc',
            '瀬戸内海放送': '#ksb',
            'RSKテレビ': '#rsk',
            'TSCテレビせとうち': '#tvsetouchi',
            'OHK': '#ohk',
            // 広島
            'RCCテレビ': '#rcc',
            '広島テレビ': '#htv',
            '広島ホームテレビ': '#hometv',
            'テレビ新広島': '#tss',
            // 鳥取島根
            '日本海テレビ': '#nkt',
            'BSSテレビ': '#bss',
            'さんいん中央テレビ': '#tsk',
            // 山口
            'tysテレビ山口': '#tys',
            '山口放送': '#kry',
            'yab山口朝日': '#yab',
            // 徳島
            '四国放送': '#jrt',
            // 高知
            '高知放送': '#rkc',
            'テレビ高知': '#kutv',
            '高知さんさんテレビ': '#kss',
            // 愛媛
            '南海放送': '#rnb',
            '愛媛朝日テレビ': '#eat',
            'あいテレビ': '#itv',
            'テレビ愛媛': '#ebc',
            // 福岡
            'KBCテレビ': '#kbc',
            'RKB毎日放送': '#rkb',
            'FBS福岡放送': '#fbs',
            'TVQ九州放送': '#tvq',
            'テレビ西日本': '#tnc',
            // 佐賀
            'STSサガテレビ': '#sagatv',
            // 長崎
            'NBC長崎放送': '#nbc',
            '長崎国際テレビ': '#nib',
            'NCC長崎文化放送': '#ncc',
            'テレビ長崎': '#ktn',
            // 熊本
            'RKK熊本放送': '#rkk',
            'くまもと県民': '#kkt',
            'KAB熊本朝日放送': '#kab',
            'テレビ熊本': '#tku',
            // 大分
            'OBS大分放送': '#obs',
            'TOSテレビ大分': '#tos',
            'OAB大分朝日放送': '#oab',
            // 宮崎
            'MRT宮崎放送': '#mrt',
            'テレビ宮崎': '#umk',
            // 鹿児島
            'MBC南日本放送': '#mbc',
            '鹿児島讀賣テレビ': '#kyt',
            'KKB鹿児島放送': '#kkb',
            '鹿児島テレビ放送': '#kts',
            // 沖縄
            'RBCテレビ': '#rbc',
            '琉球朝日放送': '#qab',
            '沖縄テレビ': '#otv',
            // 三大首都圏
            '日テレ': '#ntv',
            '読売テレビ': '#ytv',
            '中京テレビ': '#chukyotv',
            'テレビ朝日': '#tvasahi',
            'ABCテレビ': '#abc',
            'メ~テレ': '#nagoyatv', 'メ〜テレ': '#nagoyatv',
            'TBSチャンネル': null, 'TBS': '#tbs',
            'MBS': '#mbs',
            'CBC': '#cbc',
            'テレビ東京': '#tvtokyo', 'テレ東': '#tvtokyo',
            'テレビ大阪': '#tvo',
            'テレビ愛知': '#tva',
            'フジテレビ': '#fujitv',
            '関西テレビ': '#kantele',
            '東海テレビ': '#tokaitv',
            // 独立局
            'TOKYO MX': '#tokyomx',
            'tvk': '#tvk',
            'チバテレ': '#chibatv',
            'テレ玉': '#teletama',
            '群馬テレビ': '#gtv',
            'とちぎテレビ': '#tochitere', 'とちテレ': '#tochitere',
            'サンテレビ': '#suntv',
            'KBS京都': '#kbs',
            // BS・CS
            'NHKBS1': '#nhkbs1',
            'NHKBSプレミアム': '#nhkbsp',
            'NHKBS': '#nhkbs',
            'BS日テレ': '#bsntv',
            'BS朝日': '#bsasahi',
            'BS-TBS': '#bstbs',
            'BSテレ東': '#bstvtokyo',
            'BSフジ': '#bsfuji',
            'BS10スターチャンネル': '#bs10スターチャンネル',
            'BS10': '#bs10',
            'BS11': '#bs11',
            'BS12': '#bs12',
            'BS松竹東急': '#bs260ch',
            'BSJapanext': '#bsjapanext',
            'BSよしもと': '#bsyoshimoto',
            'AT-X': '#at_x',
        };

        // 前方一致でチャンネルを検出する
        const result = Object.keys(channel_list).find(key => channel_name.startsWith(key));
        return result ? channel_list[result] : null;
    }
}
