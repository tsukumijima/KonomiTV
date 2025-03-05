<template>
    <v-dialog max-width="800" transition="slide-y-transition" v-model="server_log_dialog_modal">
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
                <div class="server-log-dialog__label">
                    リアルタイムでログを表示しています。最新のログが下部に表示されます。
                </div>
                <div class="server-log-dialog__console" ref="logConsole">
                    <div v-for="(line, index) in log_lines" :key="index" class="server-log-dialog__line">
                        {{ line }}
                    </div>
                    <div v-if="log_lines.length === 0" class="server-log-dialog__empty">
                        ログを取得中...
                    </div>
                </div>
            </div>
        </v-card>
    </v-dialog>
</template>
<script lang='ts' setup>

import { PropType, ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';

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
        startLogStreaming();
    } else {
        // ダイアログが閉じられたらログの取得を停止
        stopLogStreaming();
    }
});
watch(server_log_dialog_modal, (newValue) => {
    emit('update:modelValue', newValue);
});

// 最大表示行数
const MAX_LINES = 5000;

// ログ表示用の変数
const log_lines = ref<string[]>([]);
const logConsole = ref<HTMLElement | null>(null);
const active_tab = ref<string>('server');
let abort_controller: AbortController | null = null;

// タブが切り替わったらログをクリアして新しいログの取得を開始
watch(active_tab, () => {
    stopLogStreaming();
    log_lines.value = [];
    startLogStreaming();
});

// ログストリーミングを開始する関数
function startLogStreaming() {
    // すでに接続中なら一度切断
    if (abort_controller !== null) {
        stopLogStreaming();
    }

    // 現在のタブに応じたログタイプを取得
    const log_type = active_tab.value === 'server' ? 'server' : 'access';

    // ログの取得を開始
    abort_controller = Maintenance.streamLogs(log_type, (log_line: string) => {
        // ログ行を追加
        log_lines.value.push(log_line);

        // 最大表示行数を制限（パフォーマンス対策）
        if (log_lines.value.length > MAX_LINES) {
            log_lines.value = log_lines.value.slice(-MAX_LINES);
        }

        // 次のティックでスクロールを最下部に移動
        nextTick(() => {
            if (logConsole.value) {
                logConsole.value.scrollTop = logConsole.value.scrollHeight;
            }
        });
    });

    // 接続に失敗した場合
    if (abort_controller === null) {
        log_lines.value = ['サーバーログの表示には管理者権限が必要です。\n管理者アカウントでログインし直してください。'];
    }
}

// ログストリーミングを停止する関数
function stopLogStreaming() {
    if (abort_controller !== null) {
        abort_controller.abort();
        abort_controller = null;
    }
}

// コンポーネントがマウントされたときにログの取得を開始（すでにダイアログが開いている場合）
onMounted(() => {
    if (server_log_dialog_modal.value) {
        startLogStreaming();
    }
});

// コンポーネントが破棄される前にログの取得を停止
onBeforeUnmount(() => {
    stopLogStreaming();
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
            font-size: 15.5px;
        }
    }
}

.server-log-dialog__tabs {
    border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

.server-log-dialog__label {
    margin-top: 16px;
    color: rgb(var(--v-theme-text-darken-1));
    font-size: 13.5px;
    line-height: 1.6;
    @include smartphone-horizontal {
        font-size: 11px;
        line-height: 1.7;
    }
}

.server-log-dialog__console {
    margin-top: 16px;
    height: 60vh;
    height: 60dvh;
    overflow-y: auto;
    color: rgb(var(--v-theme-text));
    background-color: #101010;
    border-radius: 6px;
    padding: 12px;
    font-family: 'Consolas', 'Monaco', 'Courier New', 'Hiragino Sans', 'Noto Sans JP', monospace;
    font-size: 13px;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-all;

    &::-webkit-scrollbar-track {
        background: #101010;
    }

    @include smartphone-vertical {
        font-size: 11px;
    }
}

.server-log-dialog__line {
    margin: 0;
    padding: 0;
}

.server-log-dialog__empty {
    color: rgb(var(--v-theme-text-darken-1));
    text-align: center;
    padding: 20px 0;
}

</style>