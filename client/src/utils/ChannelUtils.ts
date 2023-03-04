
import { ChannelType } from '@/services/Channels';

/**
 * チャンネル周りのユーティリティ
 */
export class ChannelUtils {

    /**
     * チャンネル ID からチャンネルタイプを取得する
     * @param channel_id チャンネル ID
     * @returns チャンネルタイプ
     */
    static getChannelType(channel_id: string): ChannelType {
        const result = channel_id.match('(?<channel_type>[a-z]+)[0-9]+').groups.channel_type.toUpperCase();
        return result as ChannelType;
    }


    /**
     * チャンネルの実況勢いから「多」「激多」「祭」を取得する
     * ref: https://ja.wikipedia.org/wiki/%E3%83%8B%E3%82%B3%E3%83%8B%E3%82%B3%E5%AE%9F%E6%B3%81
     * @param channel_force チャンネルの実況勢い
     * @returns normal（普通）or many（多）or so-many（激多）or festival（祭）
     */
    static getChannelForceType(channel_force: number | null): 'normal' | 'many' | 'so-many' | 'festival' {

        // 実況勢いが null（=対応する実況チャンネルがない）
        if (channel_force === null) return 'normal';

        // 実況勢いが 500 コメント以上（祭）
        if (channel_force >= 500) return 'festival';
        // 実況勢いが 200 コメント以上（激多）
        if (channel_force >= 200) return 'so-many';
        // 実況勢いが 100 コメント以上（多）
        if (channel_force >= 100) return 'many';

        // それ以外
        return 'normal';
    }
}
