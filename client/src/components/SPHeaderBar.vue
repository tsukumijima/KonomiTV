<template>
    <header class="header" :class="{ 'search-active': is_search_active }">
        <template v-if="!is_search_active">
            <router-link v-ripple class="konomitv-logo" to="/tv/">
                <img class="konomitv-logo__image" src="/assets/images/logo.svg" height="21">
            </router-link>
            <v-spacer></v-spacer>
            <div v-ripple class="search-button" @click="activateSearch">
                <Icon icon="fluent:search-20-filled" height="24px" />
            </div>
        </template>
        <template v-else>
            <div class="search-box">
                <input ref="search_input" type="text" :placeholder="search_placeholder"
                    v-model="search_query" @keydown="handleKeyDown">
                <div v-ripple class="search-box__close" @click="deactivateSearch">
                    <Icon icon="fluent:dismiss-20-filled" height="24px" />
                </div>
            </div>
        </template>
    </header>
</template>
<script lang="ts" setup>

import { ref, computed, watch, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';

const router = useRouter();
const route = useRoute();
const is_search_active = ref(false);
const search_query = ref('');
const search_input = ref<HTMLInputElement | null>(null);

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

const activateSearch = () => {
    is_search_active.value = true;
    // 次のティックで入力フォーカスを設定
    setTimeout(() => {
        search_input.value?.focus();
    }, 0);
};

const deactivateSearch = () => {
    is_search_active.value = false;
    search_query.value = '';
};

const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Enter' && !event.isComposing) {
        if (search_query.value.trim()) {
            const search_path = getSearchPath();
            router.push(`${search_path}?query=${encodeURIComponent(search_query.value.trim())}`);
        }
    } else if (event.key === 'Escape') {
        deactivateSearch();
    }
};

// 検索クエリの初期化関数
const initialize_search_query = () => {
    if (route.path.endsWith('/search') && route.query.query) {
        search_query.value = decodeURIComponent(route.query.query as string);
        is_search_active.value = true;
    }
};

// コンポーネントのマウント時に初期化
onMounted(() => {
    initialize_search_query();
});

// ルートの変更を監視して検索クエリを更新
watch(() => route.fullPath, initialize_search_query);

</script>
<style lang="scss" scoped>

.header {
    display: none;
    justify-content: center;
    align-items: center;
    flex-shrink: 0;
    padding: 0px 16px;
    padding-top: 14px;
    height: 48px;
    background: rgb(var(--v-theme-background));
    @include smartphone-vertical {
        display: flex;
    }

    &.search-active {
        padding: 0;
    }

    .konomitv-logo {
        display: block;
        padding: 12px 8px;
        border-radius: 8px;

        &__image {
            display: block;
        }
    }

    .search-button {
        display: flex;
        align-items: center;
        justify-content: center;
        position: relative;
        margin-right: -2px;
        padding: 2px;
        border-radius: 8px;
        cursor: pointer;
    }

    .search-box {
        display: flex;
        align-items: center;
        width: 100%;
        height: 100%;
        padding: 0 16px;
        padding-top: 14px;

        input {
            flex-grow: 1;
            height: 100%;
            border: none;
            background: transparent;
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 16px;

            &:focus {
                outline: none;
            }

            &::placeholder {
                color: rgb(var(--v-theme-text-darken-2));
            }
        }

        &__close {
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            margin-right: -2px;
            padding: 2px;
            border-radius: 8px;
            cursor: pointer;
        }
    }
}

</style>