
import type { IJikkyoWebSocketInfo } from '@/services/Channels';

import APIClient from '@/services/APIClient';


/** ニコニコアカウントと連携するための認証 URL を表すインターフェイス */
export interface INiconicoAuthURL {
    authorization_url: string;
}

/** ニコニコ実況のステータス情報を表すインターフェイス */
export interface IJikkyoStatus {
    force: number;
    viewers: number;
    comments: number;
}

/** 実況チャンネル設定モーダルに表示する主要局を表すインターフェイス */
export interface IJikkyoPrimaryChannel {
    id: string;              // 実況 ID
    name: string;            // 代表局名
    type: '地デジ' | 'BS';   // 放送種別
    channel_number: string;  // チャンネル番号
    logo_id: string;         // ロゴ取得用チャンネル ID
}


class Niconico {

    /**
     * ニコニコアカウントと連携するための認証 URL を取得する
     * @returns 認証 URL or 認証 URL の取得に失敗した場合は null
     */
    static async fetchAuthorizationURL(): Promise<string | null> {

        // API リクエストを実行
        const response = await APIClient.get<INiconicoAuthURL>('/niconico/auth');

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'ニコニコアカウントとの連携用の認証 URL を取得できませんでした。');
            return null;
        }

        return response.data.authorization_url;
    }


    /**
     * 現在ログイン中のユーザーアカウントに紐づくニコニコアカウントとの連携を解除する
     * @returns 連携解除に成功した場合は true, 失敗した場合は false
     */
    static async logoutAccount(): Promise<boolean> {

        // API リクエストを実行
        const response = await APIClient.delete('/niconico/logout');

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'ニコニコアカウントとの連携を解除できませんでした。');
            return false;
        }

        return true;
    }


    /**
     * 全ての実況チャンネルの最新ステータス情報を取得する
     * @returns 実況チャンネル ID をキーとしたステータス情報の辞書 or 取得に失敗した場合は null
     */
    static async fetchJikkyoStatuses(): Promise<{ [key: string]: IJikkyoStatus } | null> {

        // API リクエストを実行
        const response = await APIClient.get<{ [key: string]: IJikkyoStatus }>('/niconico/jikkyo/statuses');

        // エラー処理
        if (response.type === 'error') {
            console.error('[Niconico.fetchJikkyoStatuses] Failed to fetch jikkyo statuses:', response);
            return null;
        }

        return response.data;
    }


    /**
     * 実況チャンネル設定モーダルに表示する主要局のリストを取得する
     * @returns 主要局リスト or 取得に失敗した場合は null
     */
    static async fetchPrimaryJikkyoChannels(): Promise<IJikkyoPrimaryChannel[] | null> {

        // API リクエストを実行
        const response = await APIClient.get<IJikkyoPrimaryChannel[]>('/niconico/jikkyo/channels');

        // エラー処理
        if (response.type === 'error') {
            console.error('[Niconico.fetchPrimaryJikkyoChannels] Failed to fetch primary jikkyo channels:', response);
            return null;
        }

        return response.data;
    }


    /**
     * 実況チャンネル ID に対応する WebSocket 接続情報を取得する
     * @param jikkyo_id 実況チャンネル ID。jk1, jk9 など
     * @returns WebSocket 接続情報 or 取得に失敗した場合は null
     */
    static async fetchJikkyoWebSocketInfo(jikkyo_id: string): Promise<IJikkyoWebSocketInfo | null> {

        // API リクエストを実行
        const response = await APIClient.get<IJikkyoWebSocketInfo>(`/niconico/jikkyo/${jikkyo_id}/session`);

        // エラー処理
        if (response.type === 'error') {
            console.error(`[Niconico.fetchJikkyoWebSocketInfo] Failed to fetch websocket info for ${jikkyo_id}:`, response);
            return null;
        }

        return response.data;
    }
}

export default Niconico;
