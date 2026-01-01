<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <SettingsBase>
        <h2 class="settings__heading">
            <a v-ripple class="settings__back-button" @click="$router.back()">
                <Icon icon="fluent:chevron-left-12-filled" width="27px" />
            </a>
            <Icon icon="fa-brands:discord" width="19px" style="margin: 0 4px;" />
            <span class="ml-3">Discord連携</span>
        </h2>
        <div class="settings__content">
            <!-- Discord連携のON/OFF -->
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="discord_enabled">Discord連携機能を有効にする</label>
                <label class="settings__item-label" for="discord_enabled">
                    KonomiTVとDiscordを連携すると、各種通知をDiscordに送信できるようになります。<br>
                    使用するにはDiscord Botのトークンの設定が必要です。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="discord_enabled" hide-details
                    :disabled="!is_admin"
                    v-model="server_settings.discord.enabled">
                </v-switch>
            </div>

            <!-- Discord連携機能がOFFでも設定項目は表示する -->
            <!-- Discord接続状態 -->
            <div class="settings__item">
                <div class="settings__item-heading">Discord接続状態</div>
                <div class="settings__item-label">
                    <div v-if="discord_connected" class="d-flex align-center">
                        <v-icon color="success" class="mr-2">mdi-check-circle</v-icon>
                        <span>Botが正常に接続されています</span>
                    </div>
                    <div v-else class="d-flex align-center">
                        <v-icon color="error" class="mr-2">mdi-alert-circle</v-icon>
                        <span>Botが接続されていません。Bot Tokenを確認してください。</span>
                    </div>
                </div>
            </div>

            <!-- Bot Token設定 (管理者のみ変更可能) -->
            <div class="settings__item" :class="{'settings__content--disabled': !is_admin || !server_settings.discord.enabled}">
                <div class="settings__item-heading">Discord Bot Token</div>
                <div class="settings__item-label">
                    Discord Botのトークンを入力してください。<br>
                    トークンはDiscordの開発者ポータルで取得できます。<br>
                </div>
                <v-text-field class="settings__item-form" color="primary" variant="outlined" hide-details
                    v-model="server_settings.discord.token"
                    :disabled="!is_admin || !server_settings.discord.enabled"
                    :append-icon="show_token ? 'mdi-eye' : 'mdi-eye-off'"
                    :type="show_token ? 'text' : 'password'"
                    placeholder="Discord Bot Token"
                    @click:append="show_token = !show_token">
                </v-text-field>
            </div>

            <!-- 通知チャンネルの設定 -->
            <div class="settings__item" :class="{'settings__content--disabled': !is_admin || !server_settings.discord.enabled}">
                <div class="settings__item-heading">通知チャンネルID</div>
                <div class="settings__item-label">
                    通知を送信するDiscordチャンネルのIDを入力してください。<br>
                    チャンネルIDはDiscordのチャンネルを右クリック→IDをコピーで取得できます。<br>
                </div>
                <v-text-field class="settings__item-form" color="primary" variant="outlined"
                    v-model="server_settings.discord.channel_id"
                    :disabled="!is_admin || !server_settings.discord.enabled"
                    placeholder="例: 123456789012345678"
                    type="text"
                    :rules="channelIdRules"
                    hide-details="auto">
                </v-text-field>
            </div>

            <!-- サーバー起動/終了通知の設定 -->
            <div class="settings__item settings__item--switch" :class="{'settings__content--disabled': !server_settings.discord.enabled}">
                <label class="settings__item-heading" for="discord_notify_server">起動/終了の通知</label>
                <label class="settings__item-label" for="discord_notify_server">
                    サーバーの起動時と終了時に通知を送信します。<br>
                    通知が不要な場合は、この設定をオフにできます。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="discord_notify_server" hide-details
                    :disabled="!server_settings.discord.enabled"
                    v-model="server_settings.discord.notify_server">
                </v-switch>
            </div>

            <!-- 録画予約通知の設定 -->
            <div class="settings__item settings__item--switch" :class="{'settings__content--disabled': !server_settings.discord.enabled}">
                <label class="settings__item-heading" for="discord_notify_recording">録画予約/完了の通知</label>
                <label class="settings__item-label" for="discord_notify_recording">
                    録画予約の開始時と完了時に通知を送信します。<br>
                    通知が不要な場合は、この設定をオフにできます。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="discord_notify_recording" hide-details
                    :disabled="!server_settings.discord.enabled"
                    v-model="server_settings.discord.notify_recording">
                </v-switch>
            </div>
            <div class="settings__description mt-3">
                設定を変更した場合は、[Discord設定を更新] ボタンを押して保存してください。<br>
                変更を反映するには KonomiTV サーバーの再起動が必要です。<br>
            </div>
            <v-btn class="settings__save-button bg-secondary mt-6" variant="flat" @click="updateDiscordSettings()">
                <Icon icon="fluent:save-16-filled" class="mr-2" height="23px" />Discord設定を更新
            </v-btn>
        </div>
    </SettingsBase>
</template>

<script lang="ts">
// 忘れがちなので無駄にコメントが多め
import { defineComponent } from 'vue';
import Message from '@/message';
import Settings, { IServerSettingsDefault } from '@/services/Settings';
import useSettingsStore from '@/stores/SettingsStore';
import useUserStore from '@/stores/UserStore';
import SettingsBase from '@/views/Settings/Base.vue';
export default defineComponent({
    name: 'Settings-Discord',
    components: {
        SettingsBase,
    },
    setup() {
        const settingsStore = useSettingsStore();
        return { settingsStore };
    },
    data() {
        return {
            // Discord接続状態
            discord_connected: false,
            // トークンを表示するか
            show_token: false,
            // サーバー設定
            server_settings: JSON.parse(JSON.stringify(IServerSettingsDefault)),
            // 設定変更前の状態を保持
            original_server_settings: JSON.parse(JSON.stringify(IServerSettingsDefault)),
            // 管理者権限による無効化状態（初期値は非管理者として設定）
            is_admin: false,
            // 保存中かどうか
            saving: false,
        };
    },
    computed: {
        // 設定が変更されているかどうかを判定
        hasChanges() {
            return JSON.stringify(this.server_settings) !== JSON.stringify(this.original_server_settings);
        },
        // チャンネルIDのバリデーションルール
        channelIdRules() {
            return [
                (v: string) => {
                    if (!v || v === '') return true; // 空の場合は許可
                    if (!/^\d+$/.test(v)) return 'チャンネルIDは数字のみで入力してください';
                    if (v.length < 17 || v.length > 19) return 'チャンネルIDは17～19桁で入力してください';
                    // 精度が保てる範囲かチェック
                    try {
                        const num = BigInt(v);
                        if (num < 0) return 'チャンネルIDは正の数値である必要があります';
                    } catch (e) {
                        return '無効なチャンネルIDです';
                    }
                    return true;
                }
            ];
        }
    },
    async mounted() {
        await this.loadSettings();
    },
    async activated() {
        // ページが再度アクティブになった時にも設定を更新
        await this.loadSettings();
    },
    methods: {
        // 設定を読み込む
        async loadSettings() {
            // 管理者権限チェック
            const user_store = useUserStore();
            const user = await user_store.fetchUser();
            this.is_admin = user?.is_admin || false;
            // サーバー設定を取得
            const settings = await Settings.fetchServerSettings();
            if (settings) {
                // channel_id を確実に文字列として扱う
                if (settings.discord.channel_id !== null) {
                    settings.discord.channel_id = String(settings.discord.channel_id);
                }
                this.server_settings = settings;
                this.original_server_settings = JSON.parse(JSON.stringify(settings));
                // サーバー設定に基づいてクライアント設定を同期
                this.settingsStore.settings.discord.enabled = settings.discord.enabled;
                this.settingsStore.settings.discord.notify_server = settings.discord.notify_server;
                this.settingsStore.settings.discord.notify_recording = settings.discord.notify_recording;
            } else {
                Message.error('サーバー設定を取得できませんでした。');
            }
            // 接続状態を確認
            await this.checkConnection();
        },
        // Discord接続状態を確認
        async checkConnection() {
            try {
                const status = await Settings.fetchDiscordStatus();
                this.discord_connected = status.connected;
            } catch (error) {
                this.discord_connected = false;
            }
        },
        // Discord設定を更新する
        async updateDiscordSettings() {
            this.saving = true;
            try {
                // channel_id を確実に文字列として扱う（保存前）
                // JavaScriptでは数値が大きくなると Number.MAX_SAFE_INTEGER を超えてしまい、精度が落ちてしまうので、基本的にクライアント側ではString型として扱う
                // Pythonではint型における最大値は基本的に存在しないため、クライアント(String型)↔サーバー(int型)という形でやり取りする。
                if (this.server_settings.discord.channel_id !== null && this.server_settings.discord.channel_id !== '') {
                    this.server_settings.discord.channel_id = String(this.server_settings.discord.channel_id);
                }
                // サーバー設定を更新
                const serverResult = await Settings.updateServerSettings(this.server_settings);
                if (serverResult === true) {
                    // 設定保存後に最新の設定を再取得
                    await this.loadSettings();
                    Message.success('Discord設定を更新しました。\n変更を反映するためには、KonomiTV サーバーを再起動してください。');
                } else {
                    Message.error('Discord設定の更新に失敗しました。');
                }
            } catch (error) {
                console.error('Discord settings update failed:', error);
                Message.error('Discord設定の更新に失敗しました。');
            } finally {
                this.saving = false;
            }
        },
    }
});
</script>