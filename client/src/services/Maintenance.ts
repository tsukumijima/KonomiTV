
import { fetchEventSource } from '@microsoft/fetch-event-source';

import Message from '@/message';
import APIClient from '@/services/APIClient';
import Utils from '@/utils';


class Maintenance {

    /**
     * サーバーログまたはアクセスログをリアルタイムに取得する
     * @param log_type ログの種類 ('server' または 'access')
     * @param initial_callback 初回接続時にログ行を受け取るコールバック関数
     * @param callback ログ行を受け取るコールバック関数
     * @returns リクエストを中止するための AbortController
     */
    static streamLogs(
        log_type: 'server' | 'access',
        initial_callback: (log_lines: string[]) => void,
        callback: (log_line: string) => void,
    ): AbortController | null {

        // リクエストを中止するための AbortController
        const abort_controller = new AbortController();

        // アクセストークンを取得
        const access_token = Utils.getAccessToken();
        if (access_token === null) {
            Message.error('サーバーログの表示には管理者権限が必要です。\n管理者アカウントでログインし直してください。');
            return null;
        }

        // EventStream の受信を開始する
        fetchEventSource(`${Utils.api_base_url}/maintenance/logs/${log_type}`, {
            method: 'GET',
            signal: abort_controller.signal,
            // 認証ヘッダーを設定
            headers: {
                'Authorization': `Bearer ${access_token}`,
                'X-KonomiTV-Version': Utils.version,
            },
            // ブラウザタブが非アクティブな時も接続を維持する
            openWhenHidden: true,
            // EventStream からメッセージを受け取った時のイベント
            onmessage: (event) => {
                if (event.event === 'initial_log_update') {
                    initial_callback(JSON.parse(event.data));
                } else if (event.event === 'log_update') {
                    callback(JSON.parse(event.data));
                }
            },
            // エラー発生時の処理
            onerror: (error) => {
                console.error('Log stream error:', error);
                // 認証エラーなどの場合は再接続を試みない
                if (error instanceof Response && (error.status === 401 || error.status === 403)) {
                    Message.error('サーバーログの表示には管理者権限が必要です。\n管理者アカウントでログインし直してください。');
                    abort_controller.abort();
                    return;
                }
                // その他のエラーは再接続を試みる
                return;
            }
        });

        return abort_controller;
    }


    /**
     * データベースを更新する
     */
    static async updateDatabase(): Promise<void> {

        // API リクエストを実行
        const response = await APIClient.post('/maintenance/update-database');

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                default:
                    APIClient.showGenericError(response, 'データベースを更新できませんでした。');
                    break;
            }
        }
    }


    /**
     * 録画フォルダの一括スキャンを開始する
     * @returns タスクの実行に成功した場合は true、失敗した場合は false
     */
    static async runBatchScan(): Promise<boolean> {

        // API リクエストを実行
        const response = await APIClient.post('/maintenance/run-batch-scan', undefined, {
            // 最大1日以上かかるのでタイムアウトを1日に設定
            timeout: 24 * 60 * 60 * 1000,
        });

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                case 'Batch scan of recording folders is already running':
                    APIClient.showGenericError(response, '録画フォルダの一括スキャンは既に実行中です。');
                    break;
                default:
                    APIClient.showGenericError(response, '録画フォルダの一括スキャンを開始できませんでした。');
                    break;
            }
            return false;
        }

        return true;
    }


    /**
     * バックグラウンド解析タスクを開始する
     * @returns タスクの実行に成功した場合は true、失敗した場合は false
     */
    static async startBackgroundAnalysis(): Promise<boolean> {

        // API リクエストを実行
        const response = await APIClient.post('/maintenance/run-background-analysis', undefined, {
            // 最大1日以上かかるのでタイムアウトを1日に設定
            timeout: 24 * 60 * 60 * 1000,
        });

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                case 'Background analysis task is already running':
                    APIClient.showGenericError(response, 'バックグラウンド解析タスクは既に実行中です。');
                    break;
                default:
                    APIClient.showGenericError(response, 'バックグラウンド解析タスクを開始できませんでした。');
                    break;
            }
            return false;
        }

        return true;
    }


    /**
     * サーバーを再起動する
     */
    static async restartServer(): Promise<boolean> {

        // API リクエストを実行
        const response = await APIClient.post('/maintenance/restart');

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                default:
                    APIClient.showGenericError(response, 'サーバーを再起動できませんでした。');
                    break;
            }
            return false;
        }

        return true;
    }


    /**
     * サーバーをシャットダウンする
     */
    static async shutdownServer(): Promise<boolean> {

        // API リクエストを実行
        const response = await APIClient.post('/maintenance/shutdown');

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                default:
                    APIClient.showGenericError(response, 'サーバーをシャットダウンできませんでした。');
                    break;
            }
            return false;
        }

        return true;
    }
}

export default Maintenance;
