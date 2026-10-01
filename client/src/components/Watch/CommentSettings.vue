<template>
    <v-dialog max-width="540" transition="slide-y-transition" v-model="playerStore.comment_settings_modal">
        <v-card class="comment-settings-modal">
            <v-card-title class="px-5 pt-3 pb-3 d-flex align-center font-weight-bold">
                <Icon icon="fluent:comment-multiple-20-filled" height="28px" />
                <span class="ml-3">実況チャンネル設定</span>
                <v-spacer></v-spacer>
                <div v-ripple class="d-flex align-center rounded-circle cursor-pointer px-2 py-2"
                    @click="playerStore.comment_settings_modal = false">
                    <Icon icon="fluent:dismiss-12-filled" width="23px" height="23px" />
                </div>
            </v-card-title>
            <div class="px-5 pb-6">
                <div>
                    <div class="font-weight-bold text-subtitle-1">実況コメントのチャンネル選択</div>
                    <div class="text-text-darken-1 mt-1" style="font-size: 13.5px;">
                        チェックを入れたチャンネルの実況コメントを取得・表示します (複数選択可)。
                    </div>
                </div>
                <div class="mt-4">
                    <div class="d-flex align-center justify-space-between mb-2">
                        <div class="font-weight-bold" style="font-size: 14px;">
                            表示するチャンネル
                        </div>
                        <div class="d-flex align-center">
                            <span class="text-text-darken-1 mr-2" style="font-size: 12.5px;">
                                選択中: {{ displaySelectedCount }}局
                            </span>
                            <v-btn
                                v-if="currentChannel && !isDefaultSelection"
                                variant="text"
                                density="compact"
                                color="primary"
                                class="px-1 mr-1"
                                style="font-size: 12px; height: 24px;"
                                @click="resetToDefault"
                            >
                                デフォルトに戻す
                            </v-btn>
                            <v-btn
                                v-if="displaySelectedCount > 0"
                                variant="text"
                                density="compact"
                                color="error"
                                class="px-1"
                                style="font-size: 12px; height: 24px;"
                                @click="clearAllChannels"
                            >
                                全解除
                            </v-btn>
                        </div>
                    </div>
                    <div class="sub-channel-list">
                        <div
                            v-for="item in channelItems"
                            :key="item.id"
                            class="sub-channel-item d-flex align-center px-3 py-2 rounded cursor-pointer"
                            :class="{
                                'sub-channel-item--selected': selectedChannelIds.includes(item.id),
                                'sub-channel-item--current': item.is_current,
                            }"
                            @click="toggleChannel(item.id)"
                        >
                            <v-checkbox-btn
                                :model-value="selectedChannelIds.includes(item.id)"
                                color="primary"
                                class="flex-shrink-0 mr-2"
                                @click.stop="toggleChannel(item.id)"
                            ></v-checkbox-btn>
                            <img
                                class="channel-logo mr-3 flex-shrink-0"
                                :src="getChannelLogoUrl(item)"
                                style="width: 36px; height: 24px; object-fit: contain; border-radius: 2px;"
                                @error="(e) => (e.target as HTMLElement).style.display = 'none'"
                            />
                            <div class="flex-grow-1 text-truncate font-weight-medium" style="font-size: 14px;">
                                <span class="text-text-darken-1 mr-2 font-weight-regular" style="font-size: 13px;">Ch.{{ item.channel_number }}</span>
                                <span>{{ item.name }}</span>
                            </div>
                            <div class="channel-force ml-3 flex-shrink-0"
                                :class="`channel-force--${ChannelUtils.getChannelForceType(item.jikkyo_force)}`">
                                <svg class="iconify iconify--fa-solid mr-1" width="10.5px" height="12px" viewBox="0 0 448 512">
                                    <path fill="currentColor" d="M323.56 51.2c-20.8 19.3-39.58 39.59-56.22 59.97C240.08 73.62 206.28 35.53 168 0C69.74 91.17 0 209.96 0 281.6C0 408.85 100.29 512 224 512s224-103.15 224-230.4c0-53.27-51.98-163.14-124.44-230.4zm-19.47 340.65C282.43 407.01 255.72 416 226.86 416C154.71 416 96 368.26 96 290.75c0-38.61 24.31-72.63 72.79-130.75c6.93 7.98 98.83 125.34 98.83 125.34l58.63-66.88c4.14 6.85 7.91 13.55 11.27 19.97c27.35 52.19 15.81 118.97-33.43 153.42z"></path>
                                </svg>
                                <span>{{ item.jikkyo_force !== null ? item.jikkyo_force : '--' }}</span>
                                <span class="channel-force-unit ml-1">コメ/分</span>
                            </div>
                            <v-chip v-if="item.is_current" size="x-small" label variant="flat" color="primary" class="ml-2 flex-shrink-0 font-weight-bold">
                                視聴中
                            </v-chip>
                            <v-chip size="x-small" label variant="tonal" class="ml-2 flex-shrink-0" :color="item.type === '地デジ' ? 'primary' : 'secondary'">
                                {{ item.type }}
                            </v-chip>
                        </div>
                    </div>
                </div>
            </div>
        </v-card>
    </v-dialog>
</template>
<script lang="ts" setup>

import { computed, ref, watch, type PropType } from 'vue';

import Niconico, { type IJikkyoStatus } from '@/services/Niconico';
import useChannelsStore from '@/stores/ChannelsStore';
import usePlayerStore from '@/stores/PlayerStore';
import Utils, { PRIMARY_JIKKYO_CHANNELS, CommentUtils, ChannelUtils, type IJikkyoOption } from '@/utils';

// Props
const props = defineProps({
    playback_mode: {
        type: String as PropType<'Live' | 'Video'>,
        default: 'Live',
    },
});

// ストア
const channelsStore = useChannelsStore();
const playerStore = usePlayerStore();

// 実況チャンネル全体の最新ステータス
const jikkyoStatuses = ref<{ [key: string]: IJikkyoStatus }>({});

// 実況ステータス一覧を取得
const updateJikkyoStatuses = async () => {
    const statuses = await Niconico.fetchJikkyoStatuses();
    if (statuses !== null) {
        jikkyoStatuses.value = statuses;
    }
};

// 初回およびチャンネルリスト更新
updateJikkyoStatuses();
channelsStore.update();

// 現在の再生対象チャンネル情報
const playbackChannel = computed(() => {
    return props.playback_mode === 'Live'
        ? channelsStore.channel.current
        : playerStore.recorded_program.channel;
});

// 自局判定
const isCurrentChannel = (channel: IJikkyoOption): boolean => {
    return CommentUtils.isCurrentJikkyoChannel(channel.id, playbackChannel.value);
};

// 現在視聴中の実況チャンネル
const currentChannel = computed<IJikkyoOption | null>(() => {
    return CommentUtils.findJikkyoOptionByChannel(playbackChannel.value);
});

// チャンネル選択肢一覧
const channelItems = computed(() => {
    // channels_list から全チャンネルを平坦化して jikkyo_id または logo_id / チャンネル番号 等から jikkyo_force のマップを作成
    const forceMap = new Map<string, number | null>();
    for (const channels of Object.values(channelsStore.channels_list)) {
        for (const ch of channels) {
            if (ch.jikkyo_id && ch.jikkyo_force !== null && !forceMap.has(ch.jikkyo_id)) {
                forceMap.set(ch.jikkyo_id, ch.jikkyo_force);
            }
            if (ch.id && ch.jikkyo_force !== null && !forceMap.has(ch.id)) {
                forceMap.set(ch.id, ch.jikkyo_force);
            }
        }
    }

    return PRIMARY_JIKKYO_CHANNELS.map(channel => {
        // Niconico.fetchJikkyoStatuses() の全体ステータスを優先し、なければ channelsStore から取得
        const statusForce = jikkyoStatuses.value[channel.id]?.force;
        const force = (statusForce !== undefined && statusForce !== -1)
            ? statusForce
            : (forceMap.get(channel.id) ?? forceMap.get(channel.logo_id) ?? null);

        return {
            ...channel,
            is_current: isCurrentChannel(channel),
            jikkyo_force: force,
        };
    });
});

// デフォルトの選択状態 (自局のみ)
const getDefaultChannelIds = (): string[] => {
    const current = currentChannel.value;
    return current ? [current.id] : [];
};

// 選択中のチャンネル ID リスト
const selectedChannelIds = ref<string[]>([...playerStore.sub_channel_ids]);

// 画面上で選択されている局数 (主要局一覧に実在する局のみ)
const displaySelectedCount = computed(() => {
    return selectedChannelIds.value.filter(id =>
        PRIMARY_JIKKYO_CHANNELS.some(item => item.id === id)
    ).length;
});

// 実況チャンネルのロゴ URL を取得 (ニコニコ実況は東京基準のため常に東京キー局のロゴを使用)
const getChannelLogoUrl = (item: IJikkyoOption): string => {
    return `${Utils.api_base_url}/channels/${item.logo_id}/logo`;
};

// デフォルト選択状態かどうか
const isDefaultSelection = computed(() => {
    const defaultIds = getDefaultChannelIds();
    if (selectedChannelIds.value.length !== defaultIds.length) return false;
    return defaultIds.every(id => selectedChannelIds.value.includes(id));
});

// 配列の一致判定
const areChannelIdsEqual = (a: string[], b: string[]): boolean => {
    if (a.length !== b.length) return false;
    return a.every((val, index) => val === b[index]);
};

// チャンネル選択状態を同期
const syncChannels = () => {
    playerStore.sub_channel_ids = [...selectedChannelIds.value];
    playerStore.sub_channel_id = selectedChannelIds.value[0] ?? null;
    if (selectedChannelIds.value.length > 0) {
        playerStore.last_selected_channel_ids = [...selectedChannelIds.value];
    }
    playerStore.event_emitter.emit('SubChannelChanged', {
        sub_channel_id: playerStore.sub_channel_id,
        sub_channel_ids: playerStore.sub_channel_ids,
    });
};

// チャンネルのチェック切り替え
const toggleChannel = (channelId: string) => {
    // 主要局リストにないフォールバック ID (自局 ID など) が含まれていれば除外する
    selectedChannelIds.value = selectedChannelIds.value.filter(id =>
        PRIMARY_JIKKYO_CHANNELS.some(item => item.id === id)
    );
    const index = selectedChannelIds.value.indexOf(channelId);
    if (index === -1) {
        selectedChannelIds.value.push(channelId);
    } else {
        selectedChannelIds.value.splice(index, 1);
    }
};

// デフォルトに戻す
const resetToDefault = () => {
    selectedChannelIds.value = getDefaultChannelIds();
};

// 全選択解除
const clearAllChannels = () => {
    selectedChannelIds.value = [];
};

// モーダルを閉じたタイミングで反映 (開いたタイミングで勢い情報を更新)
watch(() => playerStore.comment_settings_modal, (isOpen) => {
    if (isOpen) {
        selectedChannelIds.value = [...playerStore.sub_channel_ids];
        channelsStore.update();
        updateJikkyoStatuses();
    } else {
        if (!areChannelIdsEqual(selectedChannelIds.value, playerStore.sub_channel_ids)) {
            syncChannels();
        }
    }
});

// 外部変更を同期
watch(() => playerStore.sub_channel_ids, (newSubChannelIds) => {
    if (!playerStore.comment_settings_modal) {
        selectedChannelIds.value = [...newSubChannelIds];
    }
}, { deep: true });

// 視聴中チャンネルが変わった際にデフォルト選択を再初期化
watch(currentChannel, (newCurrent, oldCurrent) => {
    if (newCurrent && (!oldCurrent || newCurrent.id !== oldCurrent.id)) {
        // すでに同一のチャンネルのみが選択されている場合は二重同期・再取得をスキップ
        if (selectedChannelIds.value.length === 1 && selectedChannelIds.value[0] === newCurrent.id) {
            return;
        }
        selectedChannelIds.value = [newCurrent.id];
        syncChannels();
    }
});

</script>
<style lang="scss" scoped>

.comment-settings-modal {
    border-radius: 16px !important;
    background: rgb(var(--v-theme-background-lighten-1)) !important;

    .sub-channel-list {
        max-height: 380px;
        overflow-y: auto;
        border: 1px solid rgb(var(--v-theme-background-lighten-2));
        border-radius: 8px;
        background: rgb(var(--v-theme-background));
        padding: 4px;
    }

    .sub-channel-item {
        transition: background-color 0.15s ease;
        user-select: none;

        &:hover {
            background: rgb(var(--v-theme-background-lighten-1));
        }

        &--selected {
            background: rgba(var(--v-theme-primary), 0.08);

            &:hover {
                background: rgba(var(--v-theme-primary), 0.14);
            }
        }

        &--current {
            border-left: 3px solid rgb(var(--v-theme-primary));
        }
    }

    .channel-force {
        display: flex;
        align-items: center;
        font-size: 12.5px;
        color: rgb(var(--v-theme-text-darken-1));

        &--festival {
            color: #E7556E;
        }
        &--so-many {
            color: #E76B55;
        }
        &--many {
            color: #E7A355;
        }

        &-unit {
            font-size: 11px;
            color: rgb(var(--v-theme-text-darken-1));
        }
    }

    .channel-logo {
        background: rgb(var(--v-theme-background-lighten-2));
    }
}

</style>
