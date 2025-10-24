<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <div class="clip-videos-container-wrapper">
                <SPHeaderBar />
                <div class="clip-videos-container">
                    <Breadcrumbs :crumbs="[
                        { name: 'ホーム', path: '/' },
                        { name: 'ビデオをみる', path: '/videos/' },
                        { name: 'クリップ動画', path: '/clip-videos/', disabled: true },
                    ]" />
                    <ClipVideoList
                        title="クリップ動画"
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

import { onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import Breadcrumbs from '@/components/Breadcrumbs.vue';
import ClipVideoList from '@/components/ClipVideos/ClipVideoList.vue';
import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import ClipVideos, { IClipVideo } from '@/services/ClipVideos';
import useUserStore from '@/stores/UserStore';

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
const sort_order = ref<'desc' | 'asc'>('desc');

// クリップ動画を取得
const fetchClipVideos = async () => {
    const result = await ClipVideos.fetchClipVideos(sort_order.value, current_page.value);
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
    await router.replace({
        query: {
            ...route.query,
            page: page.toString(),
        },
    });
};

// 並び順を更新
const updateSortOrder = async (order: 'desc' | 'asc') => {
    sort_order.value = order;
    current_page.value = 1;  // ページを1に戻す
    is_loading.value = true;
    await router.replace({
        query: {
            ...route.query,
            order,
            page: '1',
        },
    });
};

// クリップ動画を削除
const handleDelete = async (clip_video_id: number) => {
    const success = await ClipVideos.deleteClipVideo(clip_video_id);
    if (success) {
        // 削除成功したら再取得
        await fetchClipVideos();
    }
};

// クリップ動画情報が更新された時にローカルのリストも差し替える
const handleClipVideoUpdated = (updatedClipVideo: IClipVideo) => {
    clip_videos.value = clip_videos.value.map(clipVideo =>
        clipVideo.id === updatedClipVideo.id ? updatedClipVideo : clipVideo,
    );
};

// クエリパラメータが変更されたらクリップ動画を再取得
watch(() => route.query, async (newQuery) => {
    // ページ番号を同期
    if (newQuery.page) {
        current_page.value = parseInt(newQuery.page as string);
    }
    // ソート順を同期
    if (newQuery.order) {
        sort_order.value = newQuery.order as 'desc' | 'asc';
    }
    await fetchClipVideos();
}, { deep: true });

// 開始時に実行
onMounted(async () => {
    // 事前にログイン状態を同期（トークンがあればユーザー情報を取得）
    const userStore = useUserStore();
    await userStore.fetchUser();

    // クエリパラメータから初期値を設定
    if (route.query.page) {
        current_page.value = parseInt(route.query.page as string);
    }
    if (route.query.order) {
        sort_order.value = route.query.order as 'desc' | 'asc';
    }

    // クリップ動画を取得
    await fetchClipVideos();
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
