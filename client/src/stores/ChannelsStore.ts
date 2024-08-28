
import { defineStore } from 'pinia';

import Channels, { ChannelType, ChannelTypePretty, ILiveChannelsList, ILiveChannel, ILiveChannelDefault } from '@/services/Channels';
import { IProgram, IProgramDefault } from '@/services/Programs';
import useSettingsStore from '@/stores/SettingsStore';
import Utils, { ChannelUtils } from '@/utils';


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
        } as ILiveChannelsList,

        // 初回のチャンネル情報更新が実行された後かどうか
        is_channels_list_initial_updated: false,

        // 最終更新日時 (UNIX タイムスタンプ、秒単位)
        last_updated_at: 0,

        // 現在視聴中のチャンネルの ID (ex: gr011)
        // 視聴画面のみ有効で、ホーム画面では利用されない
        // 視聴画面から離れる際は、必ず gr000 (現在視聴画面ではないことを示す特別な値) に戻さなければならない
        // 本来は null あたりにすべきだが、null を入れると UI 側でのエラー処理が大変なので、やむを得ず形式上有効だが絶対にあり得ない値を入れている
        display_channel_id: 'gr000' as string,

        // 現在視聴中のチャンネルの視聴者数 (LiveEventManager でリアルタイムに更新される)
        // チャンネル切り替え後、LiveEventManager で Server-Sent Events から取得されるまでは null になる
        // 視聴画面のみ有効で、ホーム画面では利用されない
        viewer_count: null as number | null,

        // 現在視聴中のチャンネルの現在放送中の番組情報 (EPG (EIT[p/f]) からリアルタイムに更新される)
        // チャンネル切り替え後、LiveDataBroadcastingManager で EIT[p/f] から取得されるまでは null になる
        // 視聴画面のみ有効で、ホーム画面では利用されない
        current_program_present: null as IProgram | null,

        // 現在視聴中のチャンネルの次に放送される番組情報 (EPG (EIT[p/f]) からリアルタイムに更新される)
        // チャンネル切り替え後、LiveDataBroadcastingManager で EIT[p/f] から取得されるまでは null になる
        // 視聴画面のみ有効で、ホーム画面では利用されない
        current_program_following: null as IProgram | null,
    }),
    getters: {

        /**
         * 前・現在・次のチャンネルの情報 (視聴画面用)
         * チャンネル情報はデータ量がかなり多いので、個別に取得するより一気に取得したほうがループ回数が少なくなりパフォーマンスが良い
         */
        channel(): { previous: ILiveChannel; current: ILiveChannel; next: ILiveChannel; } {

            // 初回のチャンネル情報更新がまだ実行されていない or 実行中のときは、情報取得中であることを示すダミーのチャンネル情報を返す
            if (this.is_channels_list_initial_updated === false) {
                return {
                    previous: ILiveChannelDefault,
                    current: ILiveChannelDefault,
                    next: ILiveChannelDefault,
                };
            }

            // エラー発生時用のダミーのチャンネル情報
            const IProgramError: IProgram = {
                ...IProgramDefault,
                title: 'チャンネル情報取得エラー',
                description: 'このチャンネル ID のチャンネル情報は存在しません。',
            };
            const ILiveChannelError: ILiveChannel = {
                ...ILiveChannelDefault,
                name: 'チャンネル情報取得エラー',
                program_present: IProgramError,
                program_following: IProgramError,
            };

            // display_channel_id に一致するチャンネルタイプを取得する
            // 取得できなかった場合、display_channel_id 自体が不正なため、エラー発生時用のダミーのチャンネル情報を返す
            // このチャンネル情報が返されたとき、視聴画面側では 404 ページへのリダイレクトが行われる
            const channel_type = ChannelUtils.getChannelType(this.display_channel_id);
            if (channel_type === null) {
                return {
                    previous: ILiveChannelError,
                    current: ILiveChannelError,
                    next: ILiveChannelError,
                };
            }

            // チャンネルタイプごとのチャンネル情報リストを取得する (すべてのチャンネルリストから探索するより効率的)
            const channels: ILiveChannel[] = this.channels_list[channel_type];

            // 起点にするチャンネル情報があるインデックスを取得
            // 取得できなかった場合、display_channel_id に一致するチャンネル情報は存在しないため、エラー発生時用のダミーのチャンネル情報を返す
            // このチャンネル情報が返されたとき、視聴画面側では 404 ページへのリダイレクトが行われる
            const current_channel_index = channels.findIndex((channel) => channel.display_channel_id === this.display_channel_id);
            if (current_channel_index === -1) {
                return {
                    previous: ILiveChannelError,
                    current: ILiveChannelError,
                    next: ILiveChannelError,
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

            // structuredClone() でディープコピーを行い、プロパティの変更が channels_list 内のオブジェクトに反映されないようにする
            // チャンネルリストに反映するとその時点で全チャンネルの再レンダリングが走ってしまい (?) 負荷が高まる
            const current_channel = structuredClone(channels[current_channel_index]);

            // 現在のチャンネル情報のみ、EPG から取得した現在/次の番組情報があればそちらを優先して上書き表示する
            if (this.current_program_present !== null) {
                current_channel.program_present = this.current_program_present;
            }
            if (this.current_program_following !== null) {
                current_channel.program_following = this.current_program_following;
            }

            // 現在のチャンネル情報のみ、LiveEventManager から取得したリアルタイム視聴者数があればそちらを優先して上書き表示する
            if (this.viewer_count !== null) {
                current_channel.viewer_count = this.viewer_count;
            }

            // 前・現在・次のチャンネル情報を返す
            return {
                previous: channels[previous_channel_index],
                current: current_channel,
                next: channels[next_channel_index],
            };
        },

        /**
         * 実際に表示されるチャンネルリストを表すデータ
         * ピン留めチャンネルのタブを追加するほか、放送していないサブチャンネルはピン留めタブを含めて表示から除外される
         * また、チャンネルが1つもないチャンネルタイプのタブも表示から除外される
         * (たとえば SKY (スカパー！プレミアムサービス) のタブは、SKY に属すチャンネルが1つもない（=受信できない）なら表示されない)
         */
        channels_list_with_pinned(): Map<ChannelTypePretty, ILiveChannel[]> {
            const settings_store = useSettingsStore();

            // 事前に Map を定義しておく
            // Map にしていたのは、確か連想配列の順序を保証してくれるからだったはず
            const channels_list_with_pinned = new Map<ChannelTypePretty, ILiveChannel[]>();
            channels_list_with_pinned.set('ピン留め', []);
            channels_list_with_pinned.set('地デジ', []);

            // 初回のチャンネル情報更新がまだ実行されていない or 実行中のときは最低限の上記2つだけで返す
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
            const pinned_channels: ILiveChannel[] = [];
            for (const [channel_type, channels] of Object.entries(this.channels_list)) {
                for (const channel of channels) {

                    // ピン留め中チャンネルの ID (ex: NID32736-SID1024) が入るリストに含まれているチャンネルなら、ピン留めタブに追加
                    // 一旦 pinned_channels に追加した後、pinned_channel_ids の順に並び替える
                    // ピン留めされているなら放送していないサブチャンネルも含める
                    if (settings_store.settings.pinned_channel_ids.includes(channel.id)) {
                        pinned_channels.push(channel);
                    }

                    // 放送していないサブチャンネルは除外
                    if (channel.is_display === false) {
                        continue;
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

            // この時点で pinned_channels に存在していないピン留め中チャンネルの ID を pinned_channel_ids から削除する
            // 受信環境の変化などでピン留め中チャンネルのチャンネル情報が取得できなくなった場合に備える
            // Vue.js 3.4.13 以降で発生する Maximum recursive updates exceeded in component エラーを回避するには、async/await を使い
            // 副作用を持ってはならない getter 関数が完了してから SettingsStore の更新処理を実行する必要がある
            (async () => {
                await Utils.sleep(100);  // 少し待つのが重要
                settings_store.settings.pinned_channel_ids = settings_store.settings.pinned_channel_ids.filter((channel_id) => {
                    return pinned_channels.some((channel) => channel.id === channel_id);
                });
            })();

            // ピン留め中チャンネルを pinned_channel_ids の順に並び替える
            channels_list_with_pinned.get('ピン留め')?.push(...pinned_channels.sort((a, b) => {
                const index_a = settings_store.settings.pinned_channel_ids.indexOf(a.id);
                const index_b = settings_store.settings.pinned_channel_ids.indexOf(b.id);
                return index_a - index_b;
            }));

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
         * 視聴画面ではピン留め中チャンネルが1つもないときは、ピン留めタブを表示する必要性がないため削除される
         */
        channels_list_with_pinned_for_watch(): Map<ChannelTypePretty, ILiveChannel[]> {

            // 意図せぬ副作用が発生しないように、channels_list_with_pinned が返す Map をコピーする
            const channels_list_with_pinned = new Map([...this.channels_list_with_pinned]);

            // 初回のチャンネル情報更新がまだ実行されていない or 実行中のときのみ、表示タイミングの問題で例外的に常にピン留めタブを削除せずに返す
            // こうしないと視聴画面に直接アクセスした際に、ピン留めタブではなく地デジタブがデフォルトで表示されてしまう
            if (this.is_channels_list_initial_updated === false) {
                return channels_list_with_pinned;
            }

            // ピン留め中チャンネルが1つもない場合は、ピン留めタブを削除する
            if (channels_list_with_pinned.get('ピン留め')?.length === 0) {
                channels_list_with_pinned.delete('ピン留め');
            }

            return channels_list_with_pinned;
        }
    },
    actions: {

        /**
         * チャンネルタイプとリモコン番号からチャンネル情報を取得する
         * @param channel_type チャンネルタイプ
         * @param remocon_id リモコン番号
         * @returns チャンネル情報 (見つからなかった場合は null)
         */
        getChannelByRemoconID(channel_type: ChannelType, remocon_id: number): ILiveChannel | null {

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

                // 再帰的に Object.freeze() を適用し、Vue 側で再帰的にリアクティブ化されないようにする
                // channels_list 内の大量のチャンネル/番組情報オブジェクトはここ以外から更新されることはない
                // さらに更新周期自体も基本 30 秒以上な上、毎回一括更新で一部だけが更新されることもないため、リアクティブである必要がない
                // 大きなオブジェクトを扱う際は、細部のリアクティブを捨てることでパフォーマンスが向上する (下記記事が大変参考になりました)
                // ref: https://speakerdeck.com/tbashiyy/shi-shu-mo-rekodoninai-euruvue-dot-jspuroziekutowoshi-xian-surutamenopahuomansutiyuningu
                // ref: https://unyacat.net/2021/01/20/vue-freeze-faster/
                this.channels_list = Utils.deepObjectFreeze(channels_list);

                // チャンネルリストの更新日時を更新
                if (this.is_channels_list_initial_updated === false) {
                    this.is_channels_list_initial_updated = true;
                }
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
