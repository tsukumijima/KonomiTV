
import { AxiosError } from 'axios';

import Message from '@/message';
import APIClient from '@/services/APIClient';
import Utils, { Semaphore } from '@/utils';


class Captures {

    // 同時アップロード数の上限 & セマフォインスタンス
    private static readonly MAX_CONCURRENT_UPLOADS = 5;
    private static readonly semaphore = new Semaphore(Captures.MAX_CONCURRENT_UPLOADS);

    /**
     * キャプチャをサーバーにアップロードし保存する
     * @param blob キャプチャ画像の Blob
     * @param filename サーバーに保存するときのファイル名
     */
    static async uploadCapture(blob: Blob, filename: string): Promise<void> {

        // リトライループ
        // 成功するか、リトライ不可なエラーが発生するまで継続
        // eslint-disable-next-line no-constant-condition
        while (true) {

            // キャプチャ画像の File オブジェクト (= Blob) を FormData に入れる
            // multipart/form-data で送るために必要
            // ref: https://r17n.page/2020/02/04/nodejs-axios-file-upload-api/
            const form_data = new FormData();
            form_data.append('image', blob, filename);

            // セマフォを取得し、アップロードを同時 5 件までに制限する
            await this.semaphore.acquire();
            let response: Awaited<ReturnType<typeof APIClient.post>>;
            try {
                // API リクエストを実行
                response = await APIClient.post('/captures', form_data, {
                    headers: {'Content-Type': 'multipart/form-data'},
                    // 回線状況によってはアップロードに時間がかかることがあるので、
                    // タイムアウトを 60 秒に伸ばす
                    timeout: 60 * 1000,
                });
            } finally {
                // セマフォを必ず解放する (アップロード試行 1 回分のみを占有)
                this.semaphore.release();
            }

            // 成功
            if (response.type !== 'error') {
                return;
            }

            // エラー処理
            switch (response.data.detail) {
                case 'Permission denied to save the file': {
                    Message.error('キャプチャのアップロードに失敗しました。保存先フォルダに書き込み権限がありません。');
                    return;
                }
                case 'No space left on the device': {
                    Message.error('キャプチャのアップロードに失敗しました。保存先フォルダに空き容量がありません。');
                    return;
                }
                case 'Unexpected error occurred while saving the file': {
                    Message.error('キャプチャのアップロードに失敗しました。保存中に予期しないエラーが発生しました。');
                    return;
                }
                default: {
                    if (Number.isNaN(response.status)) {
                        // HTTP リクエスト自体が失敗した場合はネットワークエラーの可能性が高い & 基本アップロードに失敗してはならないので、リトライする
                        // リトライする前に 1 ~ 15 秒程度ランダムに待機することで、
                        // リトライリクエストが同じタイミングで殺到するのを回避する
                        const sleep_time_seconds = 1 + Math.random() * 15;
                        if (response.error.code === AxiosError.ECONNABORTED) {
                            // ネットワーク接続エラーの場合
                            Message.warning(`キャプチャのアップロード中にサーバーへの接続が切断されました。${sleep_time_seconds.toFixed(2)} 秒後にリトライします。`);
                        } else if (response.error.code === AxiosError.ETIMEDOUT) {
                            // タイムアウトの場合
                            Message.warning(`キャプチャのアップロード中にサーバーへの接続がタイムアウトしました。${sleep_time_seconds.toFixed(2)} 秒後にリトライします。`);
                        } else if (response.error.code === AxiosError.ERR_NETWORK) {
                            // 予期しないネットワークエラーの場合
                            Message.warning(`キャプチャのアップロード中に予期しないネットワークエラーが発生しました。${sleep_time_seconds.toFixed(2)} 秒後にリトライします。`);
                        } else {
                            // それ以外のエラーの場合
                            Message.warning(`キャプチャのアップロードに失敗しました。${sleep_time_seconds.toFixed(2)} 秒後にリトライします。`);
                        }
                        await Utils.sleep(sleep_time_seconds);  // 秒単位で指定
                        // ループ先頭に戻ってリトライ
                        continue;
                    } else {
                        APIClient.showGenericError(response, 'キャプチャのアップロードに失敗しました。');
                        return;
                    }
                }
            }
        }
    }

    // TODO: キャプチャ管理機能の実装時に API を追加する
}

export default Captures;
