
import { defineStore } from 'pinia';

import CloudflareZerotrust, { ICloudflareZerotrustIdentity } from '@/services/CloudflareZerotrust';
import useSettingsStore from '@/stores/SettingsStore';


/**
 * CFZTを共有するストア
 */
const useCFZTStore = defineStore('CFZT', {
    state: () => ({

        identity_info: null as ICloudflareZerotrustIdentity | boolean | null,

        // 最終更新日時 (UNIX タイムスタンプ、秒単位)
        last_updated_at: 0,
    }),
    getters: {
        // null
        is_CFZT(): boolean {
            const settings_store = useSettingsStore();
            return !!settings_store.settings.is_cloudflare_zerotrust;
        },
        // null false
        is_login(): boolean {
            return !!this.identity_info;
        }
    },
    actions: {

        /**
         * Cloudflare Zerotrust(CFZT) ユーザー情報を取得する
         * すでに取得済みの情報がある場合は API リクエストを行わずにそれを返す
         * @param force 強制的に API リクエストを行う場合は true
         * @returns CFZT でない場合は null、ログインしていない場合は false
         */
        async fetchCFZTIdentity(force: boolean = false): Promise<ICloudflareZerotrustIdentity | null> {
            const settings_store = useSettingsStore();
            // hidden setting = is_cloudflare_zerotrust
            // if(settings_store.settings.is_cloudflare_zerotrust === false && force === false){
            //     return null;
            // }
            // if (this.identity_info !== null && force === false) {
            //     // ただし、最終更新日時が5秒以上前の場合は非同期で更新する
            //     if (Utils.time() - this.last_updated_at > 5) {
            //         this.fetchCFZTIdentity(true);
            //     }
            //     return this.identity_info;
            // }

            const identity_info = await CloudflareZerotrust.fetchCloudflareZerotrustIdentity();
            // console.log('identity_info',!!identity_info,!identity_info,identity_info);
            settings_store.settings.is_cloudflare_zerotrust = (identity_info !== null);
            
            this.identity_info = identity_info;

            return this.identity_info;
        },
    }
});

export default useCFZTStore;
