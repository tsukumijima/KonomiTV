
import { defineStore } from 'pinia';
import Vue from 'vue';

import Channels, { ChannelType, ChannelTypePretty, IChannelsList, IChannel, IChannelDefault } from '@/services/Channels';
import useSettingsStore from '@/store/SettingsStore';
import Utils, { ChannelUtils } from '@/utils';


/**
 * TV ホーム画面と TV 視聴画面の両方のページでチャンネル情報を共有するためのストア
 * チャンネル情報の API からの取得はかなり重めなので、ページ遷移時に毎回 API リクエストを行うのはパフォーマンスが悪い
 * チャンネル情報をストアに格納しておくことで、TV ホーム画面から TV 視聴画面に遷移したときのパフォーマンスが向上する
 */
const useChannelsStore = defineStore('channels', {
    state: () => ({

        // 現在視聴中のチャンネルの ID (ex: gr011)
        // 視聴画面のみ有効で、ホーム画面では利用されない
        channel_id: 'gr000' as string,

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
         * ライブ視聴画面を表示中かどうか
         * チャンネル情報がセットされているかどうかで判定できる
         */
        is_showing_live(): boolean {
            return this.channel_id !== 'gr000';
        },

        /**
         * 前・現在・次のチャンネル情報 (視聴画面用)
         * チャンネル情報はデータ量がかなり多いので、個別に取得するより一気に取得したほうがループ回数が少なくなりパフォーマンスが良い
         */
        channel(): {previous: IChannel; current: IChannel; next: IChannel;} {

            // チャンネルタイプごとのチャンネル情報リストを取得する (すべてのチャンネルリストから探索するより効率的)
            const channels: IChannel[] | undefined = this.channels_list[ChannelUtils.getChannelType(this.channel_id)];

            // まだチャンネルリストの更新が終わっていないなどの場合で取得できなかった場合、
            // null を返すと UI 側でのエラー処理が大変なので、暫定的なダミーのチャンネル情報を返す
            if (channels === undefined || channels.length === 0) {
                return {
                    previous: IChannelDefault,
                    current: IChannelDefault,
                    next: IChannelDefault,
                };
            }

            // 起点にするチャンネル情報があるインデックスを取得
            const current_channel_index = channels.findIndex((channel) => channel.channel_id === this.channel_id);

            // インデックスが取得できなかった場合も同様に、暫定的なダミーのチャンネル情報を返す
            if (current_channel_index === -1) {
                const IProgramError = {
                    ...IChannelDefault.program_present,
                    channel_id: 'gr999',
                    title: 'チャンネル情報取得エラー',
                    description: 'このチャンネル ID のチャンネル情報は存在しません。',
                };
                const IChannelError = {
                    ...IChannelDefault,
                    channel_id: 'gr999',  // チャンネル情報が存在しないことを示す特殊なチャンネル ID
                    name: 'ERROR',
                    program_present: IProgramError,
                    program_following: IProgramError,
                };
                return {
                    previous: IChannelError,
                    current: IChannelError,
                    next: IChannelError,
                };
            }

            // 前のインデックスを取得する
            // インデックスがマイナスになった時は、最後のインデックスに巻き戻す
            // channel.is_display が true のチャンネルに到達するまで続ける
            const previous_channel_index = ((): number => {
                let index = current_channel_index - 1;
                while (channels.length) {
                    if (index <= -1) {
                        index = channels.length - 1;  // 最後のインデックス
                    }
                    if (channels[index].is_display) {
                        return index;
                    }
                    index--;
                }
                return 0;
            })();

            // 次のインデックスを取得する
            // インデックスが配列の長さを超えた時は、最初のインデックスに巻き戻す
            // channel.is_display が true のチャンネルに到達するまで続ける
            const next_channel_index = ((): number => {
                let index = current_channel_index + 1;
                while (channels.length) {
                    if (index >= channels.length) {
                        index = 0;  // 最初のインデックス
                    }
                    if (channels[index].is_display) {
                        return index;
                    }
                    index++;
                }
                return 0;
            })();

            // 前・現在・次のチャンネル情報を返す
            return {
                previous: channels[previous_channel_index],
                current: channels[current_channel_index],
                next: channels[next_channel_index],
            };
        },

        /**
         * 実際に表示されるチャンネルリストを表すデータ
         * ピン留めチャンネルのタブを追加するほか、放送していないサブチャンネルはピン留めタブを含めて表示から除外される
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
                    switch (channel.type) {
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

            // ピン留めチャンネルを追加順に並び替える
            for (const channel of [...channels_list_with_pinned.get('ピン留め')!]) {
                const index = settings_store.settings.pinned_channel_ids.indexOf(channel.channel_id);
                channels_list_with_pinned.get('ピン留め')![index] = channel;
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
         * 視聴画面向けの channels_list_with_pinned
         * 視聴画面ではピン留めされているチャンネルが1つもないときは、ピン留めタブを表示する必要性がないため削除される
         */
        channels_list_with_pinned_for_watch(): Map<ChannelTypePretty, IChannel[]> {
            const channels_list_with_pinned = new Map([...this.channels_list_with_pinned]);
            if (channels_list_with_pinned.get('ピン留め')?.length === 0) {
                channels_list_with_pinned.delete('ピン留め');
            }
            return channels_list_with_pinned;
        }
    },
    actions: {

        /**
         * 指定されたチャンネル ID のチャンネル情報を取得する
         * @param channel_id 取得するチャンネル ID (ex: gr011)
         * @returns チャンネル情報
         */
        getChannel(channel_id: string): IChannel | null {

            // チャンネルタイプごとのチャンネル情報リストを取得する (すべてのチャンネルリストから探索するより効率的)
            const channels = this.channels_list[ChannelUtils.getChannelType(channel_id)];
            if (channels === undefined) {
                return null;
            }

            // チャンネル ID が一致するチャンネル情報を返す
            return channels.find(channel => channel.channel_id === channel_id) ?? null;
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
         * 指定されたチャンネル ID のチャンネル情報を更新する
         * 今のところ viewer_count (視聴者数) を更新する目的でしか使っていない
         * @param channel_id 更新するチャンネル ID (ex: gr011)
         * @param channel 更新後のチャンネル情報
         */
        updateChannel(channel_id: string, channel: IChannel): void {

            // チャンネルタイプごとのチャンネル情報リストを取得する (すべてのチャンネルリストから探索するより効率的)
            const channel_type = ChannelUtils.getChannelType(channel_id);
            if (this.channels_list[channel_type] === undefined) {
                return null;
            }

            // チャンネル ID が一致するチャンネル情報を更新する
            const index = this.channels_list[channel_type].findIndex(channel => channel.channel_id === channel_id);
            if (index === -1) {
                return;
            }
            // リアクティブにするために Vue.set を使う
            Vue.set(this.channels_list[channel_type], index, channel);
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
                this.last_updated_at = Utils.time();
            };

            // すでに取得されている場合は更新しない
            if (this.is_channels_list_initial_updated === true && force === false) {

                // ただし、最終更新日時が1分以上前の場合は非同期で更新する
                if (Utils.time() - this.last_updated_at > 60) {
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
