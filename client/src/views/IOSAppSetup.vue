<template>
    <div class="ios-app-setup-container">
        <v-container class="d-flex align-center justify-center" style="min-height: 100vh;">
            <v-card class="setup-card" max-width="600" elevation="8">
                <v-card-title class="text-h5 pa-6">
                    <v-icon class="mr-2">mdi-server-network</v-icon>
                    サーバー URL の設定
                </v-card-title>
                <v-card-text class="pa-6">
                    <p class="text-body-1 mb-6">
                        KonomiTV サーバーの URL を入力してください。<br>
                        Tailscale VPN 経由での接続もサポートしています。
                    </p>

                    <!-- URL 入力フォーム -->
                    <v-text-field v-model="server_url" label="サーバー URL" placeholder="https://192-168-1-100.local.konomi.tv:7000" variant="outlined" :error-messages="validation_error" :disabled="is_testing" @input="validation_error = null" class="mb-4" prepend-inner-icon="mdi-link-variant"/>

                    <!-- 入力例の表示 -->
                    <div class="mb-6">
                        <p class="text-caption mb-2">入力例:</p>
                        <div class="d-flex flex-wrap ga-2">
                            <v-chip size="small" color="primary" variant="outlined" @click="server_url = 'https://192-168-1-100.local.konomi.tv:7000'">
                                ローカル IP (Wi-Fi)
                            </v-chip>
                            <v-chip size="small" color="primary" variant="outlined" @click="server_url = 'https://100-125-18-21.local.konomi.tv:7000'">
                                Tailscale VPN
                            </v-chip>
                        </div>
                    </div>

                    <!-- 接続テスト結果 -->
                    <v-alert v-if="connection_test_result" :type="connection_test_result.success ? 'success' : 'error'" :icon="connection_test_result.success ? 'mdi-check-circle' : 'mdi-alert-circle'" class="mb-4">
                        <div v-if="connection_test_result.success">
                            <div class="text-body-1 font-weight-bold mb-1">接続成功！</div>
                            <div class="text-body-2">サーバーバージョン: {{ connection_test_result.version }}</div>
                            <div class="text-body-2">応答時間: {{ connection_test_result.latency }}ms</div>
                        </div>
                        <div v-else>
                            <div class="text-body-1 font-weight-bold mb-1">接続失敗</div>
                            <div class="text-body-2">{{ connection_test_result.message }}</div>
                        </div>
                    </v-alert>

                    <!-- Tailscale ガイドへのリンク -->
                    <v-expansion-panels class="mb-4">
                        <v-expansion-panel>
                            <v-expansion-panel-title>
                                <v-icon class="mr-2">mdi-help-circle-outline</v-icon>
                                Tailscale VPN 経由で接続する方法
                            </v-expansion-panel-title>
                            <v-expansion-panel-text>
                                <ol class="text-body-2">
                                    <li class="mb-2">iOS デバイスと KonomiTV サーバーの両方で Tailscale アプリをインストールし、同じアカウントでログインします。</li>
                                    <li class="mb-2">KonomiTV サーバーの Tailscale IP アドレス (100.x.y.z 形式) を確認します。</li>
                                    <li class="mb-2">URL を <code>https://100-x-y-z.local.konomi.tv:7000</code> の形式で入力します（ピリオドをハイフンに置き換えます）。</li>
                                </ol>
                            </v-expansion-panel-text>
                        </v-expansion-panel>
                    </v-expansion-panels>
                </v-card-text>

                <v-card-actions class="pa-6 pt-0">
                    <v-spacer/>
                    <v-btn color="primary" size="large" :loading="is_testing" :disabled="!server_url || server_url.trim() === ''" @click="testAndSave" prepend-icon="mdi-connection">
                        接続テスト & 保存
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-container>
    </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

import Message from '@/message';
import URLValidator from '@/services/URLValidator';
import useSettingsStore from '@/stores/SettingsStore';
import router from '@/router';

// サーバー URL
const server_url = ref('');
// バリデーションエラーメッセージ
const validation_error = ref<string | null>(null);
// 接続テスト中フラグ
const is_testing = ref(false);
// 接続テスト結果
const connection_test_result = ref<{success: boolean; message: string; version?: string; latency?: number} | null>(null);

/**
 * サーバー URL の接続テストを実行し、成功時に設定を保存する
 */
async function testAndSave() {
    // URL バリデーション
    const validation = URLValidator.validateServerURL(server_url.value);
    if (!validation.valid) {
        validation_error.value = validation.error!;
        return;
    }

    // 接続テスト
    is_testing.value = true;
    connection_test_result.value = null;

    const test_result = await URLValidator.testConnection(server_url.value);

    if (test_result.success) {
        // 接続成功 - URL を保存
        const settings_store = useSettingsStore();
        settings_store.settings.ios_app_server_url = server_url.value;
        settings_store.settings.ios_app_initial_setup_completed = true;

        connection_test_result.value = {
            success: true,
            message: '接続に成功しました！',
            version: test_result.version,
            latency: test_result.latency,
        };

        Message.success('サーバー URL を保存しました。3秒後にメインページへ遷移します。');

        // 3秒後にメインページへ遷移
        setTimeout(() => {
            router.push('/');
        }, 3000);
    } else {
        // 接続失敗
        connection_test_result.value = {
            success: false,
            message: test_result.error!,
        };
    }

    is_testing.value = false;
}
</script>

<style lang="scss" scoped>
.ios-app-setup-container {
    background: linear-gradient(135deg, rgb(var(--v-theme-background)) 0%, rgba(var(--v-theme-background-lighten-1), 0.8) 100%);
    min-height: 100vh;
}

.setup-card {
    backdrop-filter: blur(10px);
}

code {
    background-color: rgba(var(--v-theme-on-surface), 0.1);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 0.9em;
}
</style>
