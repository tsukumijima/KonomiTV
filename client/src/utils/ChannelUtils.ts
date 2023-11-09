
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
            const result = display_channel_id.match('(?<channel_type>[a-z]+)[0-9]+')!.groups!.channel_type.toUpperCase();
            switch (result) {
                case 'GR': return 'GR';
                case 'BS': return 'BS';
                case 'CS': return 'CS';
                case 'CATV': return 'CATV';
                case 'SKY': return 'SKY';
                case 'STARDIGIO': return 'STARDIGIO';
                // 正規表現ではエラーになっていないが、ChannelType のいずれにもマッチしない
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
     * とりあえず三大首都圏 + BS のみ対応
     * @param channel_name チャンネル名
     * @returns 局タグ (一致するものがない場合は null)
     */
    static getChannelHashtag(channel_name: string): string | null {
        // NHK
        if (channel_name.startsWith('NHK総合')) {
            return '#nhk';
        } else if (channel_name.startsWith('NHKEテレ')) {
            return '#etv';
        // 民放
        } else if (channel_name.startsWith('日テレ')) {
            return '#ntv';
        } else if (channel_name.startsWith('読売テレビ')) {
            return '#ytv';
        } else if (channel_name.startsWith('中京テレビ')) {
            return '#chukyotv';
        } else if (channel_name.startsWith('テレビ朝日')) {
            return '#tvasahi';
        } else if (channel_name.startsWith('ABCテレビ')) {
            return '#abc';
        } else if (channel_name.startsWith('メ~テレ') || channel_name.startsWith('メ〜テレ')) {
            return '#nagoyatv';
        } else if (channel_name.startsWith('TBS') && !channel_name.includes('TBSチャンネル')) {
            return '#tbs';
        } else if (channel_name.startsWith('MBS')) {
            return '#mbs';
        } else if (channel_name.startsWith('CBC')) {
            return '#cbc';
        } else if (channel_name.startsWith('テレビ東京')) {
            return '#tvtokyo';
        } else if (channel_name.startsWith('テレビ大阪')) {
            return '#tvo';
        } else if (channel_name.startsWith('テレビ愛知')) {
            return '#tva';
        } else if (channel_name.startsWith('フジテレビ')) {
            return '#fujitv';
        } else if (channel_name.startsWith('関西テレビ')) {
            return '#kantele';
        } else if (channel_name.startsWith('東海テレビ')) {
            return '#tokaitv';
        // 独立局
        } else if (channel_name.startsWith('TOKYO MX')) {
            return '#tokyomx';
        } else if (channel_name.startsWith('tvk')) {
            return '#tvk';
        } else if (channel_name.startsWith('チバテレ')) {
            return '#chibatv';
        } else if (channel_name.startsWith('テレ玉')) {
            return '#teletama';
        } else if (channel_name.startsWith('サンテレビ')) {
            return '#suntv';
        } else if (channel_name.startsWith('KBS京都')) {
            return '#kbs';
        // BS・CS
        } else if (channel_name.startsWith('NHKBS1')) {
            return '#nhkbs1';
        } else if (channel_name.startsWith('NHKBSプレミアム')) {
            return '#nhkbsp';
        } else if (channel_name.startsWith('BS日テレ')) {
            return '#bsntv';
        } else if (channel_name.startsWith('BS朝日')) {
            return '#bsasahi';
        } else if (channel_name.startsWith('BS-TBS')) {
            return '#bstbs';
        } else if (channel_name.startsWith('BSテレ東')) {
            return '#bstvtokyo';
        } else if (channel_name.startsWith('BSフジ')) {
            return '#bsfuji';
        } else if (channel_name.startsWith('BS11イレブン')) {
            return '#bs11';
        } else if (channel_name.startsWith('BS12トゥエルビ')) {
            return '#bs12';
        } else if (channel_name.startsWith('AT-X')) {
            return '#at_x';
        }

        return null;
    }
}
