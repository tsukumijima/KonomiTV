
import { IChannel } from '@/interface';

/**
 * チャンネル周りのユーティリティ
 */
export class ChannelUtils {

    /**
     * チャンネル ID からチャンネルタイプを取得する
     * @param channel_id チャンネル ID
     * @param is_chideji GR を「地デジ」と表記するかどうか
     * @returns チャンネルタイプ
     */
    static getChannelType(channel_id: string, is_chideji: boolean = false): string {
        const result = channel_id.match('(?<channel_type>[a-z]+)[0-9]+').groups.channel_type.toUpperCase();
        if (result === 'GR' && is_chideji) {
            return '地デジ';
        } else {
            return result;
        }
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

        // 実況勢いが 1000 コメント以上（祭）
        if (channel_force >= 1000) return 'festival';
        // 実況勢いが 200 コメント以上（激多）
        if (channel_force >= 200) return 'so-many';
        // 実況勢いが 100 コメント以上（多）
        if (channel_force >= 100) return 'many';

        // それ以外
        return 'normal';
    }


    /**
     * チャンネルタイプとリモコン番号からチャンネル情報を取得する
     * @param channels_list チャンネルリスト
     * @param channel_type チャンネルタイプ
     * @param remocon_id リモコン番号
     * @returns チャンネル情報
     */
    static getChannelFromRemoconID(channels_list: Map<string, IChannel[]>, channel_type: string, remocon_id: number): IChannel | null {

        // 指定されたチャンネルタイプのチャンネルを取得
        channel_type = channel_type.replace('GR', '地デジ');  //「GR」は「地デジ」に置換しておく
        const channels = channels_list.get(channel_type);

        // リモコン番号が一致するチャンネルを見つけ、一番最初に見つかったものを返す
        for (let index = 0; index < channels.length; index++) {
            const channel = channels[index];
            if (channel.remocon_id === remocon_id) {
                return channel;
            }
        }

        // リモコン番号が一致するチャンネルを見つけられなかった
        return null;
    }


    /**
     * 前・現在・次のチャンネル情報を取得する
     * @param channels_list チャンネルリスト
     * @param channel_id 起点にする現在のチャンネル ID
     * @returns 前・現在・次のチャンネル情報
     */
    static getPreviousAndCurrentAndNextChannel(channels_list: Map<string, IChannel[]>, channel_id: string): IChannel[] {

        // 前後のチャンネルを取得
        const channels = channels_list.get(this.getChannelType(channel_id, true));
        for (let index = 0; index < channels.length; index++) {
            const element = channels[index];

            // チャンネル ID が一致したときだけ
            if (element.channel_id === channel_id) {

                // インデックスが最初か最後の時はそれぞれ最後と最初にインデックスを一周させる
                let previous_index = index - 1;
                if (previous_index === -1) previous_index = channels.length - 1;
                let next_index = index + 1;
                if (next_index === channels.length) next_index = 0;

                // 前・現在・次のチャンネル情報を返す
                return [channels[previous_index], channels[index], channels[next_index]];
            }
        }
    }
}
