
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
