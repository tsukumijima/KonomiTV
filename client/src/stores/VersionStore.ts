
import { defineStore } from 'pinia';

import Version, { IVersionInformation } from '@/services/Version';
import Utils from '@/utils';


/**
 * 現在ログイン中のユーザーアカウントの情報を共有するストア
 */
const useVersionStore = defineStore('version', {
    state: () => ({

        // サーバーのバージョン情報
        server_version_info: null as IVersionInformation | null,

        // 最終更新日時 (UNIX タイムスタンプ、秒単位)
        last_updated_at: 0,
    }),
    getters: {
        client_version(): string {
            return Utils.version;
        },
        server_version(): string | null {
            return this.server_version_info?.version ?? null;
        },
        latest_version(): string | null {
            return this.server_version_info?.latest_version ?? null;
        },
        is_client_develop_version(): boolean {
            return this.client_version.includes('-dev');
        },
        is_server_develop_version(): boolean {
            return this.server_version?.includes('-dev') ?? false;
        },
        is_update_available(): boolean {
            // もし現在のサーバーバージョンと最新のバージョンが異なるなら、アップデートが利用できると判断する
            // 現在のサーバーバージョンが開発版 (-dev あり) で、かつ最新のバージョンがリリース版 (-dev なし) の場合も同様に表示する
            // つまり開発版だと同じバージョンのリリース版がリリースされたときにしかアップデート通知が表示されない事になるが、ひとまずこれで…
            if (this.server_version === null || this.latest_version === null) return false;
            if ((this.is_server_develop_version === false && this.server_version !== this.latest_version) ||
                (this.is_server_develop_version === true && this.server_version.replace('-dev', '') === this.latest_version)) {
                return true;
            }
            return false;
        },
        is_version_mismatch(): boolean {
            if (this.server_version === null) return false;
            return this.client_version !== this.server_version;
        }
    },
    actions: {

        /**
         * バージョン情報を取得する
         * すでに取得済みの情報がある場合は API リクエストを行わずにそれを返す
         * @param force 強制的に API リクエストを行う場合は true
         * @returns バージョン情報 or バージョン情報の取得に失敗した場合は null
         */
        async fetchServerVersion(force: boolean = false): Promise<IVersionInformation | null> {

            // バージョン情報がある場合はそれを返す
            // force が true の場合は無視される
            if (this.server_version_info !== null && force === false) {
                // ただし、最終更新日時が1分以上前の場合は非同期で更新する
                if (Utils.time() - this.last_updated_at > 60) {
                    this.fetchServerVersion(true);
                }
                return this.server_version_info;
            }

            // サーバーのバージョン情報を取得する
            const version_info = await Version.fetchServerVersion();
            if (version_info === null) {
                return null;
            }
            this.server_version_info = version_info;
            this.last_updated_at = Utils.time();

            return this.server_version_info;
        },
    }
});

export default useVersionStore;
