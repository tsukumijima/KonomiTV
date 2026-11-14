<template>
    <ReservationList
        class="toru-ranking"
        :class="{'toru-ranking--loading': isLoading && displayReservations.length === 0}"
        :style="{'--toru-ranking-loading-count': Math.min(limit, 20)}"
        title="予約数ランキング"
        :reservations="displayReservations"
        :total="rankingTotal"
        :page="page"
        :items-per-page="20"
        :is-loading="isLoading"
        :hide-sort="true"
        :hide-pagination="!showPagination"
        :hide-count="true"
        :show-more-button="showMoreButton"
        :show-back-button="showBackButton"
        :show-rank="true"
        :show-empty-message="!isLoading"
        :filter-select-items="showFilter ? filterItems : undefined"
        :filter-select-value="filter"
        empty-icon="fluent:trophy-20-regular"
        :empty-message="emptyMessage"
        :empty-sub-message="emptySubMessage"
        keep-deleted-items
        is-program-search-result
        :add-availability="addAvailability"
        @update:page="$emit('update:page', $event)"
        @update:filter-select-value="handleFilterChanged"
        @more="$emit('more')"
        @added="handleReservationChanged"
        @delete="handleReservationChanged" />
</template>
<script lang="ts" setup>

import { computed, onMounted, ref, watch } from 'vue';

import ReservationList from '@/components/Reservations/ReservationList.vue';
import { ILiveChannel } from '@/services/Channels';
import Programs, { IProgram } from '@/services/Programs';
import Reservations, { IRecordSettings, IReservation } from '@/services/Reservations';
import useChannelsStore from '@/stores/ChannelsStore';
import useServerSettingsStore from '@/stores/ServerSettingsStore';
import { TORU_RANKING_GENRES, ToruRankingChannelType, ToruRankingFilter } from '@/stores/ToruCountStore';
import { ReservationAddAvailability, ReservationUtils } from '@/utils';

// Props
const props = withDefaults(defineProps<{
    // 表示する番組数の上限
    limit: number;
    // 表示するページ番号 (ランキングは1ページあたり 20 件で、100 位まで取得できる)
    page?: number;
    // ランキングの絞り込み (チャンネルタイプかジャンルのどちらか一方)
    filter?: ToruRankingFilter;
    // ページネーションを表示するかどうか
    showPagination?: boolean;
    // 「もっと見る」ボタンを表示するかどうか
    showMoreButton?: boolean;
    // 戻るボタンを表示するかどうか
    showBackButton?: boolean;
    // 絞り込みの選択欄を表示するかどうか
    showFilter?: boolean;
}>(), {
    page: 1,
    filter: 'All',
    showPagination: false,
    showMoreButton: false,
    showBackButton: false,
    showFilter: false,
});

// Emits
const emit = defineEmits<{
    (e: 'more'): void;
    (e: 'update:page', page: number): void;
    (e: 'update:filter', filter: ToruRankingFilter): void;
    (e: 'changed'): void;
}>();

const channelsStore = useChannelsStore();
const serverSettingsStore = useServerSettingsStore();

// EDCB バックエンドかどうか
// サーバー設定がまだ取得されていない場合は EDCB と判定しない (デフォルト値が 'EDCB' のため)
const isEDCBBackend = computed(() => serverSettingsStore.is_loaded === true && serverSettingsStore.server_settings.general.backend === 'EDCB');

// 予約数の多い順に並んだ番組のリスト (取得に失敗した場合は null)
const rankingPrograms = ref<IProgram[] | null>([]);
// ランキング全体の件数 (ページ数の計算に使う)
const rankingTotal = ref(0);
// 読み込み中かどうか
const isLoading = ref(true);
// 録画予約済みの番組を実際の録画予約として表示するための、番組 ID をキーにした録画予約のマップ
const reservationMap = ref<Map<string, IReservation>>(new Map());
// 録画予約の一覧を1回でも取得できたかどうか
const isReservationsLoaded = ref(false);
// 録画予約を追加するときに使う録画設定の既定値
const defaultRecordSettings = ref<IRecordSettings | null>(null);

// 録画予約のない番組に、録画予約を追加できる状態かどうか
// 既存の録画予約と録画設定の既定値を取得できるまでは、予約済みの番組への重複した予約や、
// EDCB の既定値とは異なる設定での予約を防ぐため、追加できない状態にする
const addAvailability = computed<ReservationAddAvailability>(() => {
    if (serverSettingsStore.is_loaded === false) {
        return 'Preparing';
    }
    if (isEDCBBackend.value === false) {
        return 'EDCBOnly';
    }
    return isReservationsLoaded.value === true && defaultRecordSettings.value !== null ? 'Available' : 'Preparing';
});

const allChannels = computed<ILiveChannel[]>(() => {
    // チャンネルタイプごとの配列を1本の配列に変換する
    return Object.values(channelsStore.channels_list).flat();
});

const channelMap = computed(() => {
    // ランキングの番組は channel_id だけを持つため、予約カードへ渡すチャンネルを先に引ける形にする
    return new Map(allChannels.value.map((channel) => [channel.id, channel]));
});

// 絞り込みの選択欄の項目
// チャンネルタイプとジャンルを掛け合わせると 100 位までのランキングの件数が少なくなるため、
// どちらか一方だけを1つの選択欄から選ぶ形にし、チャンネルタイプとジャンルの間を区切り線で分ける
const filterItems = computed(() => {
    const items: { title: string; value: ToruRankingFilter; hasDividerAbove?: boolean; }[] = [{ title: '総合', value: 'All' }];
    // 受信できるチャンネルがある放送波だけを、絞り込みの選択肢に加える
    const candidates: { title: string; value: ToruRankingChannelType; }[] = [
        { title: '地デジ', value: 'GR' },
        { title: 'BS', value: 'BS' },
        { title: 'CS', value: 'CS' },
    ];
    for (const candidate of candidates) {
        if (allChannels.value.some((channel) => channel.type === candidate.value)) {
            items.push(candidate);
        }
    }
    TORU_RANKING_GENRES.forEach((genre, index) => {
        items.push({ title: genre.title, value: genre.value, hasDividerAbove: index === 0 });
    });
    return items;
});

const displayReservations = computed<IReservation[]>(() => {
    const programs = (rankingPrograms.value ?? []).slice(0, props.limit);
    return programs.map((program) => {
        // 録画予約済みの番組は実際の録画予約を、それ以外の番組は仮の録画予約データを予約カードへ渡す
        const reservation = reservationMap.value.get(program.id);
        if (reservation !== undefined) {
            return reservation;
        }
        return ReservationUtils.createUnreservedReservation(
            program,
            channelMap.value.get(program.channel_id) ?? null,
            defaultRecordSettings.value,
        );
    });
});

// ランキングに表示する番組がないときのメッセージは、読み込みの失敗・絞り込みの結果・予約数が未取得の場合で変える
// スマートフォンの縦画面でも1行に収まるよう、メッセージは短い文にしている
const emptyMessage = computed(() => {
    if (rankingPrograms.value === null) {
        return '読み込みに失敗しました。';
    }
    if (props.filter !== 'All') {
        return '該当する番組がありません。';
    }
    return 'まだ予約数がありません。';
});
const emptySubMessage = computed(() => {
    if (rankingPrograms.value === null) {
        return 'ページを再読み込みしてください。';
    }
    if (props.filter !== 'All') {
        return '絞り込みを「総合」に戻してください。';
    }
    return 'サーバーの起動直後は、しばらくお待ちください。';
});

/**
 * 予約数ランキングを取得する
 */
const fetchRanking = async () => {
    // レスポンスを待つ間に絞り込みやページが変更された場合に備えて、リクエストした時点の絞り込みとページ番号を保持しておく
    const requestedFilter = props.filter;
    const requestedPage = props.page;
    // 絞り込みは、チャンネルタイプかジャンルのどちらか一方として API に渡す
    let channelType: 'GR' | 'BS' | 'CS' | undefined = undefined;
    let genre: string | undefined = undefined;
    if (requestedFilter === 'GR' || requestedFilter === 'BS' || requestedFilter === 'CS') {
        channelType = requestedFilter;
    } else if (requestedFilter !== 'All') {
        genre = requestedFilter;
    }
    const result = await Programs.fetchToruRanking(channelType, genre, requestedPage);
    // 現在も同じ絞り込みとページを表示している場合だけ、結果を画面に反映する
    if (requestedFilter !== props.filter || requestedPage !== props.page) {
        return;
    }
    rankingPrograms.value = result === null ? null : result.programs;
    rankingTotal.value = result === null ? 0 : result.total;
    isLoading.value = false;
};

/**
 * 録画予約の一覧を取得し、録画予約済みの番組の表示を更新する
 */
const updateReservations = async () => {
    // 録画予約の一覧は EDCB の録画予約 API から取得するため、EDCB バックエンドの場合のみ取得する
    if (isEDCBBackend.value === false) {
        return;
    }
    const reservations = await Reservations.fetchReservations();
    if (reservations !== null) {
        reservationMap.value = new Map(reservations.reservations.map((reservation) => [reservation.program.id, reservation]));
        isReservationsLoaded.value = true;
    }
};

// 絞り込みの選択欄で絞り込みが変更された時の処理
const handleFilterChanged = (filter: string) => {
    emit('update:filter', filter as ToruRankingFilter);
};

// ランキングの番組に録画予約が追加・削除された時の処理
const handleReservationChanged = async () => {
    // 録画予約済みの表示を更新してから、親コンポーネントに録画予約の変更を通知する
    await updateReservations();
    emit('changed');
};

// 絞り込みかページが変更されたら、ランキングを取得し直す
watch(() => [props.filter, props.page], () => {
    isLoading.value = true;
    void fetchRanking();
});

onMounted(() => {
    // チャンネル一覧・既存の録画予約・録画設定の既定値は、予約カードのロゴ表示と予約操作に使う
    // ランキングの取得はこれらを使わず、取得が完了した時点で予約カードの表示も更新されるため、取得を待たずにランキングを取得する
    void Promise.all([
        channelsStore.update(),
        // 既存の録画予約と録画設定の既定値は EDCB の録画予約 API から取得するため、EDCB バックエンドの場合のみ取得する
        serverSettingsStore.fetchServerSettingsOnce().then(async () => {
            if (isEDCBBackend.value === false) {
                return;
            }
            await Promise.all([
                updateReservations(),
                Reservations.fetchDefaultRecordSettings().then((recordSettings) => {
                    defaultRecordSettings.value = recordSettings;
                }),
            ]);
        }),
    ]);
    void fetchRanking();
});

// ランキングの外で録画予約が追加・削除されたときに、親コンポーネントから録画予約済みの表示を更新できるようにする
defineExpose({ updateReservations });

</script>
<style lang="scss" scoped>

.toru-ranking--loading {
    // 初回のローディング中にちらつかないよう、表示する件数分 (1ページあたり最大 20 件) の高さを確保する
    // 予約カード 1 件の高さは、Reservation.vue の contain-intrinsic-height に合わせている
    :deep(.reservation-list__grid) {
        min-height: calc(90px * var(--toru-ranking-loading-count));
        @include smartphone-horizontal {
            min-height: calc(85px * var(--toru-ranking-loading-count));
        }
        @include smartphone-vertical {
            min-height: calc(105px * var(--toru-ranking-loading-count));
        }
    }
}

</style>
