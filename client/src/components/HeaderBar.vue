<template>
    <header class="header">
        <router-link v-ripple class="konomitv-logo ml-3 ml-md-6" to="/tv/">
            <img class="konomitv-logo__image" src="/assets/images/logo.svg" height="21">
        </router-link>
        <v-spacer></v-spacer>
        <!-- 番組表コントロール用スロット -->
        <slot name="timetable-controls"></slot>
        <div v-if="showSearchInput" class="search-box">
            <input class="search-input" type="search" name="header-search" enterkeyhint="search" :placeholder="searchPlaceholder"
                v-model="searchQuery" @keydown="handleKeyDown">
            <Icon class="search-input__icon" icon="fluent:search-20-filled" height="24px" @click="doSearch" />
        </div>
        <v-btn v-show="isButtonDisplay && !isTimeTablePage" variant="flat" class="pwa-install-button"
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

const props = defineProps<{
    searchQuery?: string;
}>();

const emit = defineEmits<{
    (e: 'update:searchQuery', searchQuery: string): void;
    (e: 'search', searchQuery: string): void;
}>();

const isButtonDisplay = ref(false);
const internalSearchQuery = ref('');
const router = useRouter();
const route = useRoute();

const searchQuery = computed({
    get: () => props.searchQuery ?? internalSearchQuery.value,
    set: (value: string) => {
        // 検索ページでは親がキーワードを持ち、通常ページではヘッダー内だけで保持する
        if (props.searchQuery !== undefined) {
            emit('update:searchQuery', value);
        } else {
            internalSearchQuery.value = value;
        }
    },
});

// 検索クエリの初期化関数
const initializeSearchQuery = () => {
    // 親から検索キーワードを受けているページでは、URL からの復元を親側に任せる
    if (props.searchQuery !== undefined) {
        return;
    }
    if (route.path.endsWith('/search') && route.query.query) {
        internalSearchQuery.value = decodeURIComponent(route.query.query as string);
    } else {
        internalSearchQuery.value = '';
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
    return route.path.startsWith('/videos') || route.path.startsWith('/mylist') || route.path.startsWith('/watched-history')
        ? '録画番組を検索...'
        : '放送予定の番組を検索...';
});

const getSearchPath = () => {
    return route.path.startsWith('/videos') || route.path.startsWith('/mylist') || route.path.startsWith('/watched-history')
        ? '/videos/search'
        : '/tv/search';
};

const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Enter' && !event.isComposing) {
        doSearch();
    }
};

const doSearch = () => {
    // 番組検索ページでは空欄キーワードでも絞り込み検索できるため、空文字のままページ側へ渡す
    if (props.searchQuery !== undefined) {
        const trimmedSearchQuery = searchQuery.value.trim();
        emit('update:searchQuery', trimmedSearchQuery);
        emit('search', trimmedSearchQuery);
        return;
    }

    if (searchQuery.value.trim()) {
        const searchPath = getSearchPath();
        router.push(`${searchPath}?query=${encodeURIComponent(searchQuery.value.trim())}`);
    }
};

const showSearchInput = computed(() => {
    const path = route.path;
    return !path.startsWith('/captures') && !path.startsWith('/settings') && !path.startsWith('/login') && !path.startsWith('/register');
});

// 番組表ページかどうか（ヘッダーにコントロールが多くスペースに余裕がないため、PWA インストールボタンを非表示にする）
const isTimeTablePage = computed(() => route.path.startsWith('/timetable'));

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
    z-index: 40;

    // スマホ横・縦画面では SPHeaderBar を使用するため非表示
    @include smartphone-horizontal {
        display: none;
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
