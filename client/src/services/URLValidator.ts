
import APIClient from '@/services/APIClient';


/**
 * サーバー URL のバリデーションと接続テスト機能を提供するユーティリティクラス
 */
class URLValidator {

    /**
     * サーバー URL の形式を検証する
     * @param url 検証対象の URL
     * @returns バリデーション結果
     */
    static validateServerURL(url: string): {valid: boolean; error?: string} {
        try {
            const parsed = new URL(url);

            // プロトコル検証: HTTP または HTTPS のみサポート
            if (!['http:', 'https:'].includes(parsed.protocol)) {
                return {valid: false, error: 'HTTP または HTTPS のみサポートしています。'};
            }

            // ポート番号検証
            const port = parsed.port ? parseInt(parsed.port) : (parsed.protocol === 'https:' ? 443 : 80);
            if (port < 1 || port > 65535) {
                return {valid: false, error: 'ポート番号が不正です (1-65535)。'};
            }

            // ホスト名検証（localhost/IP アドレス/ドメイン名）
            const hostname = parsed.hostname;
            if (!hostname || hostname.length === 0) {
                return {valid: false, error: 'ホスト名が指定されていません。'};
            }

            return {valid: true};
        } catch (error) {
            return {valid: false, error: 'URL の形式が不正です。'};
        }
    }


    /**
     * サーバーへの接続テストを実行する
     * /api/version エンドポイントにアクセスして、サーバーが正常に応答するかを確認する
     * @param url テスト対象のサーバー URL (例: https://192-168-1-100.local.konomi.tv:7000)
     * @returns 接続テスト結果
     */
    static async testConnection(url: string): Promise<{success: boolean; error?: string; version?: string; latency?: number}> {
        const start_time = performance.now();
        try {
            const response = await APIClient.get('/version', {
                baseURL: `${url}/api`,
                timeout: 5000,  // 5秒でタイムアウト
            });

            const latency = Math.round(performance.now() - start_time);

            if (response.type === 'success') {
                return {
                    success: true,
                    version: response.data.version,
                    latency: latency,
                };
            } else {
                return {
                    success: false,
                    error: `接続に失敗しました (HTTP ${response.status})`,
                };
            }
        } catch (error: any) {
            // エラーメッセージをユーザーフレンドリーに変換
            let error_message = 'サーバーに接続できませんでした。';

            // axios のエラーコードに応じた詳細メッセージ
            if (error.code === 'ECONNABORTED' || error.code === 'ERR_NETWORK') {
                error_message = 'サーバーへの接続が切断されました。URL とネットワーク接続を確認してください。';
            } else if (error.code === 'ETIMEDOUT') {
                error_message = 'サーバーへの接続がタイムアウトしました。ネットワーク接続を確認してください。';
            } else if (error.response) {
                // サーバーからエラーレスポンスが返された場合
                error_message = `サーバーエラーが発生しました (HTTP ${error.response.status})`;
            }

            return {
                success: false,
                error: error_message,
            };
        }
    }
}

export default URLValidator;
