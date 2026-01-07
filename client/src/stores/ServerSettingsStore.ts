
import { defineStore } from 'pinia';
import { ref } from 'vue';

import Settings, { type IServerSettings, IServerSettingsDefault } from '@/services/Settings';


/**
 * サーバー設定を共有・キャッシュするストア
 */
const useServerSettingsStore = defineStore('serverSettings', () => {

    // サーバー設定のキャッシュ
    const server_settings = ref<IServerSettings>(structuredClone(IServerSettingsDefault));

    // 読み込み状態
    const is_loaded = ref(false);
    const is_loading = ref(false);

    // 進行中の取得 Promise を保持
    let fetch_promise: Promise<IServerSettings | null> | null = null;


    /**
     * サーバー設定を一度だけ取得する
     * @returns 取得結果のサーバー設定、取得失敗時は null
     */
    async function fetchServerSettingsOnce(): Promise<IServerSettings | null> {
        if (is_loaded.value) {
            return server_settings.value;
        }

        if (fetch_promise !== null) {
            return await fetch_promise;
        }

        is_loading.value = true;
        fetch_promise = Settings.fetchServerSettings()
            .then((settings) => {
                if (settings !== null) {
                    server_settings.value = settings;
                    is_loaded.value = true;
                }
                return settings;
            })
            .finally(() => {
                is_loading.value = false;
                fetch_promise = null;
            });

        return await fetch_promise;
    }


    return {
        server_settings,
        is_loaded,
        is_loading,
        fetchServerSettingsOnce,
    };
});

export default useServerSettingsStore;
