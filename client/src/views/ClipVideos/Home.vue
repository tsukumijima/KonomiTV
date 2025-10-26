<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <div class="clip-videos-container-wrapper">
                <SPHeaderBar />
                <div class="clip-videos-container">
                    <Breadcrumbs :crumbs="breadcrumbs" />
                    <ClipVideoList
                        :title="listTitle"
                        :clipVideos="clip_videos"
                        :total="total_clip_videos"
                        :page="current_page"
                        :sortOrder="sort_order"
                        :isLoading="is_loading"
                        :showBackButton="true"
                        :showEmptyMessage="!is_loading"
                        @update:page="updatePage"
                        @update:sortOrder="updateSortOrder($event as SortOrder)"
                        @delete="handleDelete"
                        @clipVideoUpdated="handleClipVideoUpdated" />
                </div>
            </div>
        </main>
    </div>
</template>
<script lang="ts" setup>

import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { NavigationFailureType, isNavigationFailure, useRoute, useRouter } from 'vue-router';

import Breadcrumbs from '@/components/Breadcrumbs.vue';
import ClipVideoList from '@/components/ClipVideos/ClipVideoList.vue';
import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import ClipVideos, { IClipVideo } from '@/services/ClipVideos';
import useUserStore from '@/stores/UserStore';
import Utils from '@/utils';

type SortOrder = 'desc' | 'asc';

// ルーター
const route = useRoute();
const router = useRouter();

// クリップ動画のリスト
const clip_videos = ref<IClipVideo[]>([]);
const total_clip_videos = ref(0);
const is_loading = ref(true);

// 現在のページ番号
const current_page = ref(1);

// 並び順
const sort_order = ref<SortOrder>('desc');

// 検索キーワード
const search_keyword = ref('');

const normalizedKeyword = computed(() => search_keyword.value.trim());

const listTitle = computed(() => {
    if (normalizedKeyword.value !== '') {
        return Utils.isSmartphoneVertical() ? '検索結果' : `「${normalizedKeyword.value}」の検索結果`;
    }
    return 'クリップ動画';
});

const breadcrumbs = computed(() => {
    const items = [
        { name: 'ホーム', path: '/' },
        { name: 'ビデオをみる', path: '/videos/' },
    ];

    if (normalizedKeyword.value !== '') {
        items.push({ name: 'クリップ動画', path: '/clip-videos/' });
        const params = new URLSearchParams({
            keyword: normalizedKeyword.value,
            order: sort_order.value,
            page: current_page.value.toString(),
        });
        items.push({
            name: '検索結果',
            path: `/clip-videos/?${params.toString()}`,
            disabled: true,
        });
        return items;
    }

    items.push({ name: 'クリップ動画', path: '/clip-videos/', disabled: true });
    return items;
});

// クエリパラメータの値を解決
const resolveQueryValue = (value: unknown): string | undefined => {
    if (Array.isArray(value)) {
        return value[0];
    }
    if (typeof value === 'string') {
        return value;
    }
    return undefined;
};

// クエリを安全に置換
const replaceQuerySafely = async (query: Record<string, string>): Promise<boolean> => {
    try {
        await router.replace({ query });
        return true;
    } catch (error) {
        if (isNavigationFailure(error, NavigationFailureType.duplicated)) {
            return false;
        }
        throw error;
    }
};

// クリップ動画を取得
const fetchClipVideos = async () => {
    const result = await ClipVideos.fetchClipVideos(sort_order.value, current_page.value, normalizedKeyword.value);
    if (result) {
        clip_videos.value = result.clip_videos;
        total_clip_videos.value = result.total;
    }
    is_loading.value = false;
};

// ページを更新
const updatePage = async (page: number) => {
    current_page.value = page;
    is_loading.value = true;

    const trimmedKeyword = normalizedKeyword.value;
    const query: Record<string, string> = {
        order: sort_order.value,
        page: page.toString(),
    };
    if (trimmedKeyword !== '') {
        query.keyword = trimmedKeyword;
    }

    const navigated = await replaceQuerySafely(query);
    if (!navigated) {
        await fetchClipVideos();
    }
};

// 並び順を更新
const updateSortOrder = async (order: SortOrder) => {
    sort_order.value = order;
    current_page.value = 1;  // ページを1に戻す
    is_loading.value = true;

    const trimmedKeyword = normalizedKeyword.value;
    const query: Record<string, string> = {
        order,
        page: '1',
    };
    if (trimmedKeyword !== '') {
        query.keyword = trimmedKeyword;
    }

    const navigated = await replaceQuerySafely(query);
    if (!navigated) {
        await fetchClipVideos();
    }
};

// クリップ動画を削除
const handleDelete = async (clip_video_id: number) => {
    const success = await ClipVideos.deleteClipVideo(clip_video_id);
    if (success) {
        // 削除成功したら再取得
        is_loading.value = true;
        await fetchClipVideos();
    }
};

// クリップ動画情報が更新された時にローカルのリストも差し替える
const handleClipVideoUpdated = (updatedClipVideo: IClipVideo) => {
    clip_videos.value = clip_videos.value.map(clipVideo =>
        clipVideo.id === updatedClipVideo.id ? updatedClipVideo : clipVideo,
    );
};

// ヘッダーからの検索操作（ルート未変更時）を補助
const handleHeaderSearchReload = async (event: Event) => {
    const detail = (event as CustomEvent<string>).detail;
    const keyword = typeof detail === 'string' ? detail.trim() : '';
    search_keyword.value = keyword;
    current_page.value = 1;
    is_loading.value = true;
    await fetchClipVideos();
};

// クエリパラメータが変更されたらクリップ動画を再取得
watch(() => route.query, async (newQuery) => {
    const pageParam = resolveQueryValue(newQuery.page);
    const parsedPage = pageParam ? Number.parseInt(pageParam, 10) : NaN;
    current_page.value = Number.isNaN(parsedPage) || parsedPage < 1 ? 1 : parsedPage;

    const orderParam = resolveQueryValue(newQuery.order);
    sort_order.value = orderParam === 'asc' ? 'asc' : 'desc';

    const keywordParam = resolveQueryValue(newQuery.keyword);
    search_keyword.value = (keywordParam ?? '').trim();

    is_loading.value = true;
    await fetchClipVideos();
}, { deep: true });

// 開始時に実行
onMounted(async () => {
    // 事前にログイン状態を同期（トークンがあればユーザー情報を取得）
    const userStore = useUserStore();
    await userStore.fetchUser();

    window.addEventListener('clip-videos-search', handleHeaderSearchReload);

    // クエリパラメータから初期値を設定
    const initialPageParam = resolveQueryValue(route.query.page);
    const parsedInitialPage = initialPageParam ? Number.parseInt(initialPageParam, 10) : NaN;
    current_page.value = Number.isNaN(parsedInitialPage) || parsedInitialPage < 1 ? 1 : parsedInitialPage;

    const initialOrderParam = resolveQueryValue(route.query.order);
    sort_order.value = initialOrderParam === 'asc' ? 'asc' : 'desc';

    const initialKeyword = resolveQueryValue(route.query.keyword);
    search_keyword.value = (initialKeyword ?? '').trim();

    // クリップ動画を取得
    await fetchClipVideos();
});

onUnmounted(() => {
    window.removeEventListener('clip-videos-search', handleHeaderSearchReload);
});

</script>
<style lang="scss" scoped>

.clip-videos-container-wrapper {
    display: flex;
    flex-direction: column;
    width: 100%;
}

.clip-videos-container {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
    padding: 20px;
    margin: 0 auto;
    min-width: 0;
    max-width: 1000px;
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
}

</style>
