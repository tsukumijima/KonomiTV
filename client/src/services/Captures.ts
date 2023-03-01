
import APIClient from '@/services/APIClient';


class Captures {

    /**
     * キャプチャをサーバーにアップロードし保存する
     * @param blob キャプチャ画像の Blob
     * @param filename サーバーに保存するときのファイル名
     */
    static async uploadCapture(blob: Blob, filename: string): Promise<void> {

        // キャプチャ画像の File オブジェクト (= Blob) を FormData に入れる
        // multipart/form-data で送るために必要
        // ref: https://r17n.page/2020/02/04/nodejs-axios-file-upload-api/
        const form_data = new FormData();
        form_data.append('image', blob, filename);

        // API リクエストを実行
        const response = await APIClient.post('/captures', form_data, {headers: {'Content-Type': 'multipart/form-data'}});

        // エラー処理
        if ('is_error' in response) {
            APIClient.showGenericError(response, 'キャプチャのアップロードに失敗しました。');
            return;
        }
    }

    // TODO: キャプチャリスト機能の実装時にいろいろ追加する
}

export default Captures;
