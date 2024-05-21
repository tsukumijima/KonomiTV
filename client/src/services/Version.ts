
import APIClient from '@/services/APIClient';


/** バージョン情報を表すインターフェイス */
export interface IVersionInformation {
    version: string;
    latest_version: string;
    environment: 'Windows' | 'Linux' | 'Linux-Docker' | 'Linux-ARM';
    backend: 'EDCB' | 'Mirakurun';
    encoder: 'FFmpeg' | 'QSVEncC' | 'NVEncC' | 'VCEEncC' | 'rkmppenc';
}


class Version {

    /**
     * バージョン情報を取得する
     * @param suppress_error エラーメッセージを表示しない場合は true
     * @returns バージョン情報 or バージョン情報の取得に失敗した場合は null
     */
    static async fetchServerVersion(suppress_error: boolean = false): Promise<IVersionInformation | null> {

        // API リクエストを実行
        const response = await APIClient.get<IVersionInformation>('/version');

        // エラー処理
        if (response.type === 'error') {
            if (suppress_error === false) {
                APIClient.showGenericError(response, 'バージョン情報を取得できませんでした。');
            }
            return null;
        }

        return response.data;
    }
}

export default Version;
