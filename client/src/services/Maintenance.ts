
import APIClient from '@/services/APIClient';


class Maintenance {


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
