
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
     * バックグラウンド解析タスクを開始する
     * @returns タスクの実行に成功した場合は true、失敗した場合は false
     */
    static async startBackgroundAnalysis(): Promise<boolean> {

        // API リクエストを実行
        const response = await APIClient.post('/maintenance/background-analysis', undefined, {
            // 最大1日以上かかるのでタイムアウトを1日に設定
            timeout: 24 * 60 * 60 * 1000,
        });

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
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
    static async restartServer(): Promise<void> {

        // API リクエストを実行
        const response = await APIClient.post('/maintenance/restart');

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                default:
                    APIClient.showGenericError(response, 'サーバーを再起動できませんでした。');
                    break;
            }
        }
    }


    /**
     * サーバーをシャットダウンする
     */
    static async shutdownServer(): Promise<void> {

        // API リクエストを実行
        const response = await APIClient.post('/maintenance/shutdown');

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                default:
                    APIClient.showGenericError(response, 'サーバーをシャットダウンできませんでした。');
                    break;
            }
        }
    }
}

export default Maintenance;
