<template>
    <v-dialog max-width="900" transition="slide-y-transition" v-model="server_log_dialog_modal">
        <v-card class="server-log-dialog">
            <v-card-title class="px-5 pt-6 pb-0 d-flex align-center font-weight-bold" style="height: 60px;">
                <Icon icon="fluent:document-text-16-regular" height="26px" />
                <span class="ml-3">サーバーログ</span>
                <v-spacer></v-spacer>
                <div v-ripple class="d-flex align-center rounded-circle cursor-pointer px-2 py-2" @click="server_log_dialog_modal = false">
                    <Icon icon="fluent:dismiss-12-filled" width="23px" height="23px" />
                </div>
            </v-card-title>
            <v-tabs class="server-log-dialog__tabs" color="primary" bg-color="transparent" align-tabs="center" v-model="active_tab">
                <v-tab style="text-transform: none !important;" value="server">サーバーログ</v-tab>
                <v-tab style="text-transform: none !important;" value="access">アクセスログ</v-tab>
            </v-tabs>
            <div class="px-5 pb-6">
                <div class="server-log-dialog__label-container">
                    <div class="server-log-dialog__label">
                        リアルタイムでログを表示しています。最新のログが下部に表示されます。
                    </div>
                    <div class="server-log-dialog__auto-scroll-control">
                        <label for="auto_scroll_enabled" class="server-log-dialog__auto-scroll-label">自動スクロール</label>
                        <v-switch
                            id="auto_scroll_enabled"
                            v-model="auto_scroll_enabled"
                            class="server-log-dialog__auto-scroll-switch"
                            color="primary"
                            density="compact"
                            hide-details
                        ></v-switch>
                    </div>
                </div>
                <div class="server-log-dialog__console-container">
                    <!-- サーバーログ表示エリア -->
                    <VirtuaList
                        ref="server_scroller"
                        class="server-log-dialog__console"
                        :class="{ 'hidden': active_tab !== 'server' }"
                        :data="server_log_lines"
                        #default="{ item }">
                        <div class="server-log-dialog__line" v-html="formatLogLine(item)"></div>
                    </VirtuaList>

                    <!-- アクセスログ表示エリア -->
                    <VirtuaList
                        ref="access_scroller"
                        class="server-log-dialog__console"
                        :class="{ 'hidden': active_tab !== 'access' }"
                        :data="access_log_lines"
                        #default="{ item }">
                        <div class="server-log-dialog__line" v-html="formatLogLine(item)"></div>
                    </VirtuaList>
                </div>
            </div>
        </v-card>
    </v-dialog>
</template>
<script lang='ts' setup>

import { VList as VirtuaList } from 'virtua/vue';
import { PropType, ref, watch, onMounted, onBeforeUnmount, useTemplateRef, nextTick } from 'vue';

import Maintenance from '@/services/Maintenance';

// 親コンポーネントと子コンポーネントでモーダルの表示状態を同期する
const props = defineProps({
    modelValue: {
        type: Boolean as PropType<boolean>,
        required: true,
    }
});
const emit = defineEmits(['update:modelValue']);
const server_log_dialog_modal = ref(false);
watch(() => props.modelValue, (newValue) => {
    server_log_dialog_modal.value = newValue;
    if (newValue) {
        // ダイアログが開かれたらログの取得を開始
        startAllLogStreaming();
    } else {
        // ダイアログが閉じられたらログの取得を停止
        stopAllLogStreaming();
    }
});
watch(server_log_dialog_modal, (newValue) => {
    emit('update:modelValue', newValue);
});

// 最大表示行数
const MAX_LINES = 10000;

// ログ表示用の変数
const server_log_lines = ref<string[]>([]);
const access_log_lines = ref<string[]>([]);
const server_scroller = useTemplateRef('server_scroller');
const access_scroller = useTemplateRef('access_scroller');
const active_tab = ref<string>('server');
// 自動スクロールの状態管理
const auto_scroll_enabled = ref<boolean>(true);
let server_abort_controller: AbortController | null = null;
let access_abort_controller: AbortController | null = null;

// ログレベルに応じた色付けを行う関数
function formatLogLine(line: string): string {
    // ログレベルのパターン
    const logLevelPattern = /(DEBUG|INFO|WARNING|ERROR|CRITICAL):/;
    const match = line.match(logLevelPattern);

    if (match) {
        const logLevel = match[1];
        let color = '';

        // ログレベルに応じた色を設定
        switch (logLevel) {
            case 'DEBUG':
                color = '#7cbfcb';
                break;
            case 'INFO':
                color = '#aeca91';
                break;
            case 'WARNING':
                color = '#e5cb95';
                break;
            case 'ERROR':
                color = '#da8789';
                break;
        }

        // ログレベル部分のみ色付け
        return line.replace(logLevelPattern, `<span style="color: ${color};">${logLevel}</span>:`);
    }

    return line;
}

// すべてのログストリーミングを開始する関数
function startAllLogStreaming() {
    // サーバーログのストリーミングを開始
    startLogStreaming('server');
    // アクセスログのストリーミングを開始
    startLogStreaming('access');
}

// ログストリーミングを開始する関数
function startLogStreaming(log_type: 'server' | 'access') {
    // すでに接続中なら一度切断
    if (log_type === 'server' && server_abort_controller !== null) {
        stopLogStreaming('server');
    } else if (log_type === 'access' && access_abort_controller !== null) {
        stopLogStreaming('access');
    }

    // ログの取得を開始
    const abort_controller = Maintenance.streamLogs(
        log_type,
        (lines: string[]) => {
            // ログタイプに応じたログ行配列を更新
            const log_lines = log_type === 'server' ? server_log_lines : access_log_lines;
            // ログ行を一括追加
            log_lines.value = lines;
            // 最大表示行数を制限（パフォーマンス対策）
            if (log_lines.value.length > MAX_LINES) {
                log_lines.value = log_lines.value.slice(-MAX_LINES);
            }
            // 自動スクロールが有効な場合のみ対応するスクローラーを最下部に移動
            if (auto_scroll_enabled.value) {
                scrollToBottom(log_type);
            }
        },
        (line: string) => {
            // ログタイプに応じたログ行配列を更新
            const log_lines = log_type === 'server' ? server_log_lines : access_log_lines;
            // ログ行を追加
            log_lines.value.push(line);
            // 最大表示行数を制限（パフォーマンス対策）
            if (log_lines.value.length > MAX_LINES) {
                log_lines.value = log_lines.value.slice(-MAX_LINES);
            }
            // 自動スクロールが有効な場合のみ対応するスクローラーを最下部に移動
            if (auto_scroll_enabled.value) {
                scrollToBottom(log_type);
            }
        }
    );

    // 接続に失敗した場合
    if (abort_controller === null) {
        const error_message = 'サーバーログの表示には管理者権限が必要です。\n管理者アカウントでログインし直してください。';
        if (log_type === 'server') {
            server_log_lines.value = [error_message];
        } else {
            access_log_lines.value = [error_message];
        }
        return;
    }

    // AbortController を保存
    if (log_type === 'server') {
        server_abort_controller = abort_controller;
    } else {
        access_abort_controller = abort_controller;
    }
}

// 特定のログストリーミングを停止する関数
function stopLogStreaming(log_type: 'server' | 'access') {
    if (log_type === 'server' && server_abort_controller !== null) {
        server_abort_controller.abort();
        server_abort_controller = null;
    } else if (log_type === 'access' && access_abort_controller !== null) {
        access_abort_controller.abort();
        access_abort_controller = null;
    }
}

// すべてのログストリーミングを停止する関数
function stopAllLogStreaming() {
    stopLogStreaming('server');
    stopLogStreaming('access');
}

// 指定されたログタイプのスクローラーを最下部に移動する関数
function scrollToBottom(log_type: 'server' | 'access') {
    nextTick(() => {
        if (log_type === 'server' && server_scroller.value) {
            server_scroller.value.scrollToIndex(server_log_lines.value.length - 1, {
                align: 'end',
            });
        } else if (log_type === 'access' && access_scroller.value) {
            access_scroller.value.scrollToIndex(access_log_lines.value.length - 1, {
                align: 'end',
            });
        }
    });
}

// コンポーネントがマウントされたときにログの取得を開始（すでにダイアログが開いている場合）
onMounted(() => {
    if (server_log_dialog_modal.value) {
        startAllLogStreaming();
    }
});

// コンポーネントが破棄される前にログの取得を停止
onBeforeUnmount(() => {
    stopAllLogStreaming();
});

</script>
<style lang="scss" scoped>

.server-log-dialog {
    .v-card-title, & > div {
        @include smartphone-vertical {
            padding-left: 12px !important;
            padding-right: 12px !important;
        }
    }
    .v-card-title span {
        font-size: 20px;
        @include smartphone-vertical {
            font-size: 19px;
        }
    }
}

.server-log-dialog__tabs {
    border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

.server-log-dialog__label-container {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 16px;
}

.server-log-dialog__label {
    color: rgb(var(--v-theme-text-darken-1));
    font-size: 13.5px;
    line-height: 1.6;
    @include smartphone-horizontal {
        font-size: 11px;
        line-height: 1.7;
    }
}

.server-log-dialog__console-container {
    position: relative;
    margin-top: 16px;
    height: 60vh !important;
    height: 60dvh !important;
}

.server-log-dialog__console {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    overflow-y: auto;
    color: rgb(var(--v-theme-text));
    background-color: #101010;
    border-radius: 6px;
    padding: 12px;
    font-family: 'SF Mono', 'Consolas', 'Hiragino Sans', 'Noto Sans JP', monospace;
    font-size: 13px;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-all;
    transition: opacity 0.2s ease;

    &::-webkit-scrollbar-track {
        background: #101010;
    }

    @include smartphone-vertical {
        font-size: 11px;
    }

    &.hidden {
        opacity: 0;
        pointer-events: none;
    }
}

.server-log-dialog__line {
    margin: 0;
    padding: 0;
}

.server-log-dialog__auto-scroll-control {
    display: flex;
    align-items: center;
}

.server-log-dialog__auto-scroll-label {
    color: rgb(var(--v-theme-text-darken-1));
    font-size: 13.5px;
    line-height: 1.6;
    @include smartphone-horizontal {
        font-size: 11px;
        line-height: 1.7;
    }
}

.server-log-dialog__auto-scroll-switch {
    flex-shrink: 0;
    width: 35px;
    margin-left: 12px;
}

</style>