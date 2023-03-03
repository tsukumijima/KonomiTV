
import { defineStore } from 'pinia';

import Channels, { ChannelType, ChannelTypePretty, IChannelsList, IChannel, IChannelDefault } from '@/services/Channels';
import useSettingsStore from '@/store/SettingsStore';


/**
 * TV ホーム画面と TV 視聴画面の両方のページでチャンネル情報を共有するためのストア
 * チャンネル情報の API からの取得はかなり重めなので、ページ遷移時に毎回 API リクエストを行うのはパフォーマンスが悪い
 * チャンネル情報をストアに格納しておくことで、TV ホーム画面から TV 視聴画面に遷移したときのパフォーマンスが向上する
 */
const useChannelsStore = defineStore('channels', {
    state: () => ({

        // すべてのチャンネルタイプのチャンネルリスト
        channels_list: {
            GR: [],
            BS: [],
            CS: [],
            CATV: [],
            SKY: [],
            STARDIGIO: [],
        } as IChannelsList,

        // 初回のチャンネル情報更新が実行された後かどうか
        is_channels_list_initial_updated: false,

        // 最終更新日時 (UNIX タイムスタンプ、秒単位)
        last_updated_at: 0,
    }),
    getters: {

        /**
         * 実際に表示されるチャンネルリストを表すデータ
         * ピン留め済みのチャンネルのタブを追加するほか、放送していないサブチャンネルはピン留めタブを含めて表示から除外される
         * また、チャンネルが1つもないチャンネルタイプのタブも表示から除外される
         * (たとえば SKY (スカパー！プレミアムサービス) のタブは、SKY に属すチャンネルが1つもない（=受信できない）なら表示されない)
         */
        channels_list_with_pinned(): Map<ChannelTypePretty, IChannel[]> {

            const settings_store = useSettingsStore();

            // 事前に Map を定義しておく
            // Map にしていたのは、確か連想配列の順序を保証してくれるからだったはず
            const channels_list_with_pinned = new Map<ChannelTypePretty, IChannel[]>();
            channels_list_with_pinned.set('ピン留め', []);
            channels_list_with_pinned.set('地デジ', []);

            // 初回のチャンネル情報更新がまだ実行されていない or 実行中のときは最低限のこの2つだけで返す
            if (this.is_channels_list_initial_updated === false) {
                return channels_list_with_pinned;
            }

            channels_list_with_pinned.set('BS', []);
            channels_list_with_pinned.set('CS', []);
            channels_list_with_pinned.set('CATV', []);
            channels_list_with_pinned.set('SKY', []);
            channels_list_with_pinned.set('StarDigio', []);

            // channels_list に格納されているすべてのチャンネルに対しループを回し、
            // 順次 channels_list_with_pinned に追加していく
            // 1つのチャンネルに対するループ回数が少なくなる分、毎回 filter() や find() するよりも高速になるはず
            for (const [channel_type, channels] of Object.entries(this.channels_list)) {
                for (const channel of channels) {

                    // 放送していないサブチャンネルは除外
                    if (channel.is_display === false) {
                        continue;
                    }

                    // ピン留めしているチャンネルの ID (ex: gr011) が入るリストに含まれていたら、ピン留めタブに追加
                    if (settings_store.settings.pinned_channel_ids.includes(channel.channel_id)) {
                        channels_list_with_pinned.get('ピン留め')?.push(channel);
                    }

                    // チャンネルタイプごとに分類
                    switch (channel.channel_type) {
                        case 'GR': {
                            channels_list_with_pinned.get('地デジ')?.push(channel);
                            break;
                        }
                        case 'BS': {
                            channels_list_with_pinned.get('BS')?.push(channel);
                            break;
                        }
                        case 'CS': {
                            channels_list_with_pinned.get('CS')?.push(channel);
                            break;
                        }
                        case 'CATV': {
                            channels_list_with_pinned.get('CATV')?.push(channel);
                            break;
                        }
                        case 'SKY': {
                            channels_list_with_pinned.get('SKY')?.push(channel);
                            break;
                        }
                        case 'STARDIGIO': {
                            channels_list_with_pinned.get('StarDigio')?.push(channel);
                            break;
                        }
                    }
                }
            }

            // 最後に、チャンネルが1つもないチャンネルタイプのタブを除外する (ピン留めタブを除く)
            for (const [channel_type, channels] of channels_list_with_pinned) {
                if (channel_type === 'ピン留め') {
                    continue;
                }
                if (channels.length === 0) {
                    channels_list_with_pinned.delete(channel_type);
                }
            }

            // ただし、this.channels_list_with_pinned 全体が空でもうピン留めタブしか残っていない場合は、ピン留めタブも削除する
            if (channels_list_with_pinned.size === 1 && channels_list_with_pinned.has('ピン留め')) {
                channels_list_with_pinned.delete('ピン留め');
            }

            return channels_list_with_pinned;
        },

        /**
         * 視聴ページ向け版の channels_list_with_pinned
         * 視聴ページではピン留めされているチャンネルが1つもないときにピン留めタブを表示する必要性がないので、削除される
         */
        channels_list_with_pinned_for_watch(): Map<ChannelTypePretty, IChannel[]> {
            const channels_list_with_pinned = this.channels_list_with_pinned;
            if (channels_list_with_pinned.get('ピン留め')?.length === 0) {
                channels_list_with_pinned.delete('ピン留め');
            }
            return channels_list_with_pinned;
        }
    },
    actions: {

        /**
         * 前・現在・次のチャンネル情報を取得する
         * チャンネル情報はデータ量がかなり多いので、一気に取得したほうがループ回数が少なくなるためパフォーマンスが良い
         * @param channel_id 起点にするチャンネル ID (ex: gr011)
         * @returns チャンネル情報
         */
        getPreviousAndCurrentAndNextChannel(channel_id: string): {
            previous_channel: IChannel,
            current_channel: IChannel,
            next_channel: IChannel,
        } {
            for (const [channel_type, channels] of Object.entries(this.channels_list)) {

                // 起点にするチャンネル情報があるインデックスを取得
                const current_channel_index = channels.findIndex((channel) => channel.channel_id === channel_id);

                // 前・次のインデックスが最初か最後の時はそれぞれ最後と最初にインデックスを一周させる
                let previous_channel_index = current_channel_index - 1;
                if (previous_channel_index === -1) {
                    previous_channel_index = channels.length - 1;  // 最後のインデックス
                }
                let next_channel_index = current_channel_index + 1;
                if (next_channel_index === channels.length) {
                    next_channel_index = 0;  // 最初のインデックス
                }

                // 前・現在・次のチャンネル情報を返す
                return {
                    previous_channel: channels[previous_channel_index],
                    current_channel: channels[current_channel_index],
                    next_channel: channels[next_channel_index],
                };
            }

            // まだチャンネルリストの更新が終わっていないなどの場合で取得できなかった場合、
            // null を返すと UI 側でのエラー処理が大変なので、暫定的なダミーのチャンネル情報を返す
            return {
                previous_channel: IChannelDefault,
                current_channel: IChannelDefault,
                next_channel: IChannelDefault,
            };
        },

        /**
         * チャンネルタイプとリモコン番号からチャンネル情報を取得する
         * @param channel_type チャンネルタイプ
         * @param remocon_id リモコン番号
         * @returns チャンネル情報 (見つからなかった場合は null)
         */
        getChannelByRemoconID(channel_type: ChannelType, remocon_id: number): IChannel | null {

            // 指定されたチャンネルタイプのチャンネルを取得
            const channels = this.channels_list[channel_type];

            // リモコン番号が一致するチャンネルを取得
            const channel = channels.find((channel) => channel.remocon_id === remocon_id);

            // リモコン番号が一致するチャンネルを見つけられなかった場合は null を返す
            return channel ?? null;
        },

        /**
         * チャンネルリストを更新する
         * @param force 強制的に更新するかどうか
         */
        async update(force: boolean = false): Promise<void> {

            const update = async () => {

                // 最新のすべてのチャンネルの情報を取得
                const channels_list = await Channels.fetchAll();
                if (channels_list === null) {
                    return;
                }

                this.channels_list = channels_list;
                this.is_channels_list_initial_updated = true;
                this.last_updated_at = Date.now() / 1000;
            };

            // すでに取得されている場合は更新しない
            if (this.is_channels_list_initial_updated === true && force === false) {

                // ただし、最終更新日時が1分以上前の場合は非同期で更新する
                if (Date.now() / 1000 - this.last_updated_at > 60) {
                    update();
                }

                return;
            }

            // チャンネルリストの更新を行う
            await update();
        }
    }
});

export default useChannelsStore;
