<template>
    <div class="route-container">
        <HeaderBar v-model:search-query="searchCondition.keyword" @search="executeSearch" />
        <main>
            <Navigation />
            <div class="program-search-container-wrapper">
                <SPHeaderBar v-model:search-query="searchCondition.keyword" @search="executeSearch" />
                <div class="program-search-container">
                    <Breadcrumbs :crumbs="[
                        { name: 'ホーム', path: '/' },
                        { name: 'テレビをみる', path: '/tv/' },
                        { name: '検索結果', path: `/tv/search?query=${encodeURIComponent(searchCondition.keyword)}`, disabled: true },
                    ]" />
                    <div class="program-search-container__body">
                        <div class="program-search-container__filters">
                            <ProgramSearchFilters
                                v-model:condition="searchCondition"
                                :channels="allChannels"
                                :is-searching="isSearching"
                                @search="executeSearch" />
                        </div>
                        <ReservationList
                            :title="resultTitle"
                            :reservations="displayReservations"
                            :total="totalPrograms"
                            :page="currentPage"
                            hide-sort
                            :is-loading="isLoading"
                            :show-empty-message="hasSearched"
                            :filter-button-label="shouldShowFilterDrawerButton ? '絞り込み' : undefined"
                            empty-icon="fluent:search-20-regular"
                            :empty-message="emptyMessage"
                            :empty-sub-message="'別のキーワードや絞り込み条件で検索をお試しください。'"
                            keep-deleted-items
                            compact-reservations-on-tablet-horizontal
                            @filter="isFilterDrawerOpen = true"
                            @added="updateReservedProgramIds"
                            @delete="updateReservedProgramIds"
                            @update:page="updatePage" />
                    </div>
                </div>
            </div>
        </main>
        <div class="program-search-filter-drawer__scrim"
            :class="{ 'program-search-filter-drawer__scrim--visible': isFilterDrawerOpen }"
            @click="isFilterDrawerOpen = false"></div>
        <aside class="program-search-filter-drawer"
            :class="{ 'program-search-filter-drawer--visible': isFilterDrawerOpen }">
            <ProgramSearchFilters
                v-model:condition="searchCondition"
                :channels="allChannels"
                :is-searching="isSearching"
                @search="executeSearchFromDrawer" />
        </aside>
    </div>
</template>
<script lang="ts" setup>

import { computed, onBeforeUnmount, onMounted, ref, toRaw, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import Breadcrumbs from '@/components/Breadcrumbs.vue';
import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import ProgramSearchFilters from '@/components/Programs/ProgramSearchFilters.vue';
import ReservationList from '@/components/Reservations/ReservationList.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import { IChannel, ILiveChannel } from '@/services/Channels';
import Programs, { IProgram, IProgramSearchCondition } from '@/services/Programs';
import Reservations, { IRecordSettings, IRecordSettingsDefault, IReservation } from '@/services/Reservations';
import useChannelsStore from '@/stores/ChannelsStore';
import useUserStore from '@/stores/UserStore';
import Utils, { dayjs } from '@/utils';

const route = useRoute();
const router = useRouter();
const channelsStore = useChannelsStore();

const createDefaultSearchCondition = (): IProgramSearchCondition => {
    return {
        is_enabled: true,
        keyword: '',
        exclude_keyword: '',
        note: '',
        is_title_only: false,
        is_case_sensitive: false,
        is_fuzzy_search_enabled: false,
        is_regex_search_enabled: false,
        service_ranges: null,
        genre_ranges: null,
        is_exclude_genre_ranges: false,
        date_ranges: null,
        is_exclude_date_ranges: false,
        duration_range_min: null,
        duration_range_max: null,
        broadcast_type: 'All',
        duplicate_title_check_scope: 'None',
        duplicate_title_check_period_days: 6,
    };
};

// 検索条件はフォームと検索 API の両方で共有し、URL にはキーワードとページだけを残す
const searchCondition = ref<IProgramSearchCondition>(createDefaultSearchCondition());

// API 結果は全件保持し、一覧コンポーネント側で30件ずつ表示する
const programs = ref<IProgram[]>([]);
const totalPrograms = ref(0);
const currentPage = ref(1);
const isLoading = ref(false);
const isSearching = ref(false);
const hasSearched = ref(false);
const isFilterDrawerOpen = ref(false);
const defaultRecordSettings = ref<IRecordSettings | null>(null);
const reservationMap = ref<Map<string, IReservation>>(new Map());
const searchedKeyword = ref('');
const viewportRevision = ref(0);

// フォーム検索で URL を更新した直後の watch 再実行を抑え、同じ検索 API が二重に走るのを避ける
let isRouteUpdatingFromSearch = false;

const allChannels = computed<ILiveChannel[]>(() => {
    // チャンネル種別ごとの配列を検索結果用の1本の配列に変換する
    return Object.values(channelsStore.channels_list).flat();
});

const channelMap = computed(() => {
    // 検索結果は channel_id だけを持つため、予約カードへ渡すチャンネルを先に引ける形にする
    return new Map(allChannels.value.map((channel) => [channel.id, channel]));
});

const sortedPrograms = computed(() => {
    // 検索結果画面では、サーバーからの返却順に依存せず、常に放送時刻が近い順に並び替える
    // サーバーからの返却結果も基本的には時刻順になっているはずだが、念のため
    return [...programs.value].sort((firstProgram, secondProgram) => {
        return dayjs(firstProgram.start_time).valueOf() - dayjs(secondProgram.start_time).valueOf();
    });
});

const displayReservations = computed<IReservation[]>(() => {
    const startIndex = (currentPage.value - 1) * 30;
    const displayPrograms = sortedPrograms.value.slice(startIndex, startIndex + 30);

    // 検索結果から得た番組情報をモック予約データへ変換
    return displayPrograms.map((program) => createMockReservation(program));
});

const resultTitle = computed(() => {
    if (Utils.isSmartphoneVertical() === true) {
        return '検索結果';
    }
    return searchedKeyword.value.trim() !== ''
        ? `「${searchedKeyword.value}」の検索結果`
        : '検索結果';
});

const emptyMessage = computed(() => {
    return searchedKeyword.value.trim() !== ''
        ? `「${Utils.escapeHTML(searchedKeyword.value)}」に一致する番組は<br class='d-sm-none'>見つかりませんでした。`
        : '条件に一致する番組は<br class="d-sm-none">見つかりませんでした。';
});

const shouldShowFilterDrawerButton = computed(() => {
    viewportRevision.value;
    // タブレット縦画面以下は左サイドバーを置く幅が足りないため、検索条件はドロワーで開く
    return Utils.isTabletVertical() === true ||
        Utils.isSmartphoneHorizontal() === true ||
        Utils.isSmartphoneVertical() === true;
});

const syncConditionFromRoute = () => {
    // ヘッダー検索から渡されたキーワードを、絞り込みフォームの初期値として取り込む
    searchCondition.value.keyword = typeof route.query.query === 'string' ? route.query.query : '';

    // ページ番号は不正値を1ページ目へ寄せ、ページネーションの表示崩れを避ける
    const page = Number.parseInt(route.query.page as string, 10);
    currentPage.value = Number.isFinite(page) && page > 0 ? page : 1;
};

const searchPrograms = async () => {
    isLoading.value = true;
    isSearching.value = true;
    hasSearched.value = true;
    searchCondition.value.keyword = searchCondition.value.keyword ?? '';
    searchCondition.value.exclude_keyword = searchCondition.value.exclude_keyword ?? '';
    searchedKeyword.value = searchCondition.value.keyword;

    const result = await Programs.searchPrograms(searchCondition.value);
    if (result !== null) {
        programs.value = result.programs;
        totalPrograms.value = result.total;
    } else {
        programs.value = [];
        totalPrograms.value = 0;
    }

    isLoading.value = false;
    isSearching.value = false;
};

const executeSearch = async (searchKeyword?: string) => {
    if (typeof searchKeyword === 'string') {
        // ヘッダーの Enter 直後は v-model の親反映を待たず、確定済みキーワードを先に検索条件へ入れる
        searchCondition.value.keyword = searchKeyword;
    }
    currentPage.value = 1;

    try {
        isRouteUpdatingFromSearch = true;

        // 検索条件を URL にも反映し、リロードや共有時に最低限キーワード検索へ復元できるようにする
        await router.replace({
            query: {
                query: searchCondition.value.keyword,
                page: '1',
            },
        });
    } finally {
        isRouteUpdatingFromSearch = false;
    }

    await searchPrograms();
};

const executeSearchFromDrawer = async () => {
    // スマホでは検索実行後に結果へ視線を戻せるよう、ドロワーを閉じてから検索する
    isFilterDrawerOpen.value = false;
    await executeSearch();
};

const updatePage = async (page: number) => {
    currentPage.value = page;

    // 全件取得済みの結果をページ内で切るだけなので、ページ移動では API を呼び直さない
    await router.replace({
        query: {
            ...route.query,
            page: page.toString(),
        },
    });
};

watch(() => route.query.query, async (query) => {
    if (isRouteUpdatingFromSearch === true) {
        return;
    }

    // ヘッダー検索で同じページへ再遷移した場合も、URL のキーワードを検索条件へ同期して再検索する
    searchCondition.value.keyword = typeof query === 'string' ? query : '';
    currentPage.value = 1;
    await searchPrograms();
});

watch(() => route.query.page, (pageQuery) => {
    // ブラウザの戻る・進むで page だけが変わった場合も、一覧のページ番号を URL に合わせる
    const page = Number.parseInt(pageQuery as string, 10);
    currentPage.value = Number.isFinite(page) && page > 0 ? page : 1;
});

watch(isFilterDrawerOpen, (isOpen) => {
    if (isOpen === true) {
        // 独自ドロワー表示中は詳細ドロワーと同じく背面スクロールを止める
        document.documentElement.classList.add('v-overlay-scroll-blocked');
    } else {
        document.documentElement.classList.remove('v-overlay-scroll-blocked');
    }
});

const handleViewportResize = () => {
    // 画面回転や DevTools のサイズ変更後も、ドロワー表示へ切り替える判定を再評価する
    viewportRevision.value += 1;
};

const createFallbackChannel = (program: IProgram): IChannel => {
    return {
        id: program.channel_id,
        display_channel_id: program.channel_id,
        network_id: program.network_id,
        service_id: program.service_id,
        transport_stream_id: null,
        remocon_id: 0,
        channel_number: '---',
        type: 'GR',
        name: program.channel_id,
        terrestrial_regions: null,
        jikkyo_force: null,
        is_subchannel: false,
        is_radiochannel: false,
        is_watchable: true,
    };
};

const createMockReservation = (program: IProgram): IReservation => {
    const reservation = reservationMap.value.get(program.id);
    if (reservation !== undefined) {
        return reservation;
    }

    const recordSettings = defaultRecordSettings.value !== null
        ? structuredClone(toRaw(defaultRecordSettings.value))
        : null;

    return {
        id: -1,
        channel: channelMap.value.get(program.channel_id) ?? createFallbackChannel(program),
        program,
        is_recording_in_progress: false,
        recording_availability: 'Full',
        comment: '',
        scheduled_recording_file_name: '',
        estimated_recording_file_size: 0,
        record_settings: recordSettings ?? structuredClone(toRaw(IRecordSettingsDefault)),
    };
};

const updateReservedProgramIds = async () => {
    // 既存予約を取得し、検索結果上でも予約済み番組の丸ボタンを押せない状態にする
    const reservations = await Reservations.fetchReservations();
    if (reservations !== null) {
        reservationMap.value = new Map(reservations.reservations.map((reservation) => [reservation.program.id, reservation]));
    }
};

onMounted(async () => {
    // ユーザー情報とチャンネル一覧を先に取得し、検索結果カードが予約操作とロゴ表示を行える状態にする
    const userStore = useUserStore();
    await Promise.all([
        userStore.fetchUser(),
        channelsStore.update(),
        updateReservedProgramIds(),
        Reservations.fetchDefaultRecordSettings().then((recordSettings) => {
            defaultRecordSettings.value = recordSettings;
        }),
    ]);

    syncConditionFromRoute();

    // query パラメータがある検索結果 URL は、空文字でも全件検索として扱う
    if (typeof route.query.query === 'string') {
        await searchPrograms();
    }

    window.addEventListener('resize', handleViewportResize);
});

onBeforeUnmount(() => {
    // ドロワーを開いたままページ遷移した場合でも、背面スクロール禁止だけが残らないよう戻す
    document.documentElement.classList.remove('v-overlay-scroll-blocked');
    window.removeEventListener('resize', handleViewportResize);
});

</script>
<style lang="scss" scoped>

.program-search-container-wrapper {
    display: flex;
    flex-direction: column;
    width: 100%;
    min-width: 0;
}

.program-search-container {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
    min-width: 0;
    max-width: 1280px;
    padding: 20px;
    margin: 0 auto;
    @include smartphone-horizontal {
        padding: 16px 20px !important;
    }
    @include smartphone-horizontal-short {
        padding: 16px 16px !important;
    }
    @include smartphone-vertical {
        padding: 16px 8px !important;
        padding-top: 8px !important;
    }

    &__body {
        display: flex;
        align-items: flex-start;
        column-gap: 32px;
        width: 100%;
        height: 100%;
        min-width: 0;
        @include tablet-horizontal {
            column-gap: 20px;
            :deep(.reservation) {
                padding: 0px 12px;
            }
            :deep(.reservation__controls) {
                margin-right: 12px;
            }
        }
        @include tablet-vertical {
            display: block;
        }
        @include smartphone-horizontal {
            display: block;
        }
        @include smartphone-vertical {
            display: block;
        }
    }

    &__filters {
        position: sticky;
        top: 80px;
        padding-top: 10px;
        @include tablet-vertical {
            display: none;
        }
        @include smartphone-horizontal {
            display: none;
        }
        @include smartphone-vertical {
            display: none;
        }
    }
}

.program-search-filter-drawer {
    display: flex;
    position: fixed;
    top: 0;
    bottom: 0;
    left: 0;
    width: 370px;
    max-width: calc(100vw - 32px);
    flex-direction: column;
    background: rgb(var(--v-theme-background));
    border-top-right-radius: 16px;
    border-bottom-right-radius: 16px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.16);
    overflow-y: auto;
    z-index: 1010;
    transform: translateX(-100%);
    transition: transform 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);

    &--visible {
        transform: translateX(0);
    }

    &__scrim {
        position: fixed;
        top: 0;
        right: 0;
        bottom: 0;
        left: 0;
        background: rgba(0, 0, 0, 0.5);
        visibility: hidden;
        opacity: 0;
        z-index: 1009;
        transition: opacity 0.25s ease, visibility 0.25s ease;
        pointer-events: none;

        &--visible {
            visibility: visible;
            opacity: 1;
            pointer-events: auto;
        }
    }

    @include smartphone-vertical {
        width: calc(100vw - 32px);
    }

    :deep(.program-search-filters) {
        width: 100%;
        min-height: 100%;
    }
}

</style>
