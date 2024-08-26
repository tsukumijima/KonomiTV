<template>
    <header class="header">
        <router-link v-ripple class="konomitv-logo ml-3 ml-md-6" to="/tv/">
            <img class="konomitv-logo__image" src="/assets/images/logo.svg" height="21">
        </router-link>
        <v-spacer></v-spacer>
        <div v-if="showSearchInput" class="search-box">
            <input class="search-input" type="text" :placeholder="search_placeholder"
                v-model="search_query" @keydown="handleKeyDown">
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
import { useRouter, useRoute } from 'vue-router';

const isButtonDisplay = ref(false);
const search_query = ref('');
const router = useRouter();
const route = useRoute();

// 検索クエリの初期化関数
const initialize_search_query = () => {
    if (route.path.endsWith('/search') && route.query.query) {
        search_query.value = decodeURIComponent(route.query.query as string);
    }
};

onMounted(() => {
    pwaInstallHandler.addListener((canInstall) => {
        isButtonDisplay.value = canInstall;
    });
    initialize_search_query();
});

// ルートの変更を監視して検索クエリを更新
watch(() => route.fullPath, initialize_search_query);

const search_placeholder = computed(() => {
    return route.path.startsWith('/videos') || route.path.startsWith('/mylist') || route.path.startsWith('/viewing-history')
        ? '録画番組を検索...'
        : '放送予定の番組を検索...';
});

const getSearchPath = () => {
    return route.path.startsWith('/videos') || route.path.startsWith('/mylist') || route.path.startsWith('/viewing-history')
        ? '/videos/search'
        : '/tv/search';
};

const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Enter' && !event.isComposing) {
        doSearch();
    }
};

const doSearch = () => {
    if (search_query.value.trim()) {
        const search_path = getSearchPath();
        router.push(`${search_path}?query=${encodeURIComponent(search_query.value.trim())}`);
    }
};

const showSearchInput = computed(() => {
    const path = route.path;
    return !path.startsWith('/captures') && !path.startsWith('/settings');
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

</style>