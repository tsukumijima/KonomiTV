<template>
    <header class="header">
        <router-link v-ripple class="konomitv-logo ml-3 ml-md-6" to="/tv/">
            <img class="konomitv-logo__image" src="/assets/images/logo.svg" height="21">
        </router-link>
        <v-spacer></v-spacer>
        <!-- 番組表コントロール用スロット -->
        <slot name="timetable-controls"></slot>
        <div v-if="showSearchInput" class="search-box">
            <input class="search-input" type="search" enterkeyhint="search" :placeholder="searchPlaceholder"
                v-model="searchQuery" @keydown="handleKeyDown">
            <Icon class="search-input__icon" icon="fluent:search-20-filled" height="24px" @click="doSearch" />
        </div>
        <v-btn v-show="isButtonDisplay" variant="flat" class="pwa-install-button"
            @click="pwaInstallHandler.install()">
            <Icon icon="material-symbols:install-desktop-rounded" height="20px" class="mr-1" />
            アプリとしてインストール
        </v-btn>
        <div class="mr-3 mr-md-6"></div>
    </header>
</template>
<script lang="ts" setup>

import { pwaInstallHandler } from 'pwa-install-handler';
import { onMounted, ref, computed, watch } from 'vue';
import { NavigationFailureType, isNavigationFailure, useRouter, useRoute } from 'vue-router';

const isButtonDisplay = ref(false);
const searchQuery = ref('');
const router = useRouter();
const route = useRoute();

// 検索クエリの初期化関数
const resolveQueryValue = (value: unknown): string | undefined => {
    if (Array.isArray(value)) {
        const first = value[0];
        return typeof first === 'string' ? first : undefined;
    }
    if (typeof value === 'string') {
        return value;
    }
    return undefined;
};

const initializeSearchQuery = () => {
    if (route.path.startsWith('/clip-videos')) {
        searchQuery.value = resolveQueryValue(route.query.keyword) ?? '';
        return;
    }
    if (route.path.endsWith('/search') && route.query.query) {
        searchQuery.value = decodeURIComponent(route.query.query as string);
        return;
    }
};

onMounted(() => {
    pwaInstallHandler.addListener((canInstall) => {
        isButtonDisplay.value = canInstall;
    });
    initializeSearchQuery();
});

// ルートの変更を監視して検索クエリを更新
watch(() => route.fullPath, initializeSearchQuery);

const searchPlaceholder = computed(() => {
    const path = route.path;
    if (path.startsWith('/clip-videos')) {
        return 'クリップ動画を検索...';
    }
    if (path.startsWith('/videos') || path.startsWith('/mylist') || path.startsWith('/watched-history')) {
        return '録画番組を検索...';
    }
    return '放送予定の番組を検索...';
});

const getSearchPath = () => {
    if (route.path.startsWith('/clip-videos')) {
        return '/clip-videos/';
    }
    if (route.path.startsWith('/videos') || route.path.startsWith('/mylist') || route.path.startsWith('/watched-history')) {
        return '/videos/search';
    }
    return '/tv/search';
};

const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Enter' && !event.isComposing) {
        void doSearch();
    }
};

const doSearch = async () => {
    const trimmed = searchQuery.value.trim();
    const path = route.path;

    if (path.startsWith('/clip-videos')) {
        const orderParam = resolveQueryValue(route.query.order);
        const order = orderParam === 'asc' ? 'asc' : 'desc';

        const query: Record<string, string> = {
            order,
            page: '1',
        };
        if (trimmed !== '') {
            query.keyword = trimmed;
        }

        try {
            await router.push({
                path: '/clip-videos/',
                query,
            });
        } catch (error) {
            if (isNavigationFailure(error, NavigationFailureType.duplicated)) {
                window.dispatchEvent(new CustomEvent('clip-videos-search', { detail: trimmed }));
                return;
            }
            throw error;
        }
        return;
    }

    if (trimmed === '') {
        return;
    }

    const search_path = getSearchPath();
    router.push(`${search_path}?query=${encodeURIComponent(trimmed)}`);
};

const showSearchInput = computed(() => {
    const path = route.path;
    return !path.startsWith('/captures') && !path.startsWith('/settings') && !path.startsWith('/login') && !path.startsWith('/register');
});

</script>
<style lang="scss" scoped>

.header {
    position: fixed;
    display: flex;
    align-items: center;
    width: 100%;
    height: 65px;
    padding: 4px 16px;
    background: rgb(var(--v-theme-background));
    box-shadow: 0px 5px 5px -3px rgb(0 0 0 / 20%),
                0px 8px 10px 1px rgb(0 0 0 / 14%),
                0px 3px 14px 2px rgb(0 0 0 / 12%);
    z-index: 10;

    @include smartphone-horizontal {
        width: 210px;
        height: 48px;
        justify-content: center;
        .v-spacer {
            display: none;
        }
    }
    @include smartphone-horizontal-short {
        width: 190px;
    }
    @include smartphone-vertical {
        display: none;
    }

    .spacer {
        @include smartphone-horizontal {
            display: none;
        }
    }

    .konomitv-logo {
        display: block;
        padding: 12px 8px;
        border-radius: 8px;
        @include smartphone-horizontal {
            margin: 0 !important;
        }

        &__image {
            display: block;
            @include smartphone-horizontal {
                height: 19.5px;
            }
        }
    }

    .pwa-install-button {
        height: 46px;
        margin-left: 12px;
        background: rgb(var(--v-theme-background-lighten-1));
        color: rgb(var(--v-theme-text));

        @include smartphone-horizontal {
            display: none !important;
        }
        @media (display-mode: standalone) {
            display: none !important;
        }
    }
}

.search-box {
    position: relative;
    @include smartphone-horizontal {
        display: none;
    }

    .search-input {
        width: 230px;
        height: 46px;
        padding: 0 12px;
        border-radius: 6px;
        border: 1.5px solid rgb(var(--v-theme-background-lighten-2));
        background: rgb(var(--v-theme-background-lighten-1));
        color: rgb(var(--v-theme-text-darken-1));
        font-size: 15px;
        transition: box-shadow 0.09s ease;

        &:focus {
            box-shadow: rgb(var(--v-theme-primary), 50%) 0 0 0 3.5px;
            outline: none;
        }

        &::placeholder {
            color: rgb(var(--v-theme-text-darken-2));
        }
    }

    .search-input__icon {
        position: absolute;
        top: 50%;
        right: 8px;
        transform: translateY(-50%);
        padding-left: 4px;
        color: rgb(var(--v-theme-text-darken-2));
        background: rgb(var(--v-theme-background-lighten-1));
        cursor: pointer;
    }
}

// iOS アプリ（Capacitor）でセーフエリアの左右パディングを追加
body.capacitor-ios .header {
    padding-left: max(16px, env(safe-area-inset-left));
    padding-right: max(16px, env(safe-area-inset-right));
}

</style>