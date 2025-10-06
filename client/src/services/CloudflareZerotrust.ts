
import APIClient from '@/services/APIClient';

interface CloudflareZerotrustIdentity {
    id: string;
    name: string;
    email: string;
    groups: string[];
    idp: {
        id: string;
        type: string;
    };
    geo: {
        country: string;
    };
    user_uuid: string;
    account_id: string;
    iat: number;
    ip: string;
    auth_status: string;
    common_name: string;
    service_token_id: string;
    service_token_status: boolean;
    is_warp: boolean;
    is_gateway: boolean;
    version: number;
}


// interface ErrorCloudflareZerotrustIdentity {
//     err: string;
// }

export type ICloudflareZerotrustIdentity = CloudflareZerotrustIdentity | boolean | null ; 


class CloudflareZerotrust {

    /**
     * Cloudflare Zerotrust ユーザー情報を取得する
     * @param suppress_error エラーメッセージを表示しない場合は true
     * @returns バージョン情報 or バージョン情報の取得に失敗した場合は null
     */
    static async fetchCloudflareZerotrustIdentity(): Promise<ICloudflareZerotrustIdentity> {
        if (location.hostname.endsWith('local.konomi.tv')){
            return null;
        }
        // API リクエストを実行
        const response = await APIClient.get('/cdn-cgi/access/get-identity', {
            baseURL: ''
        });

        // not cf
        if (typeof response.data === 'string' && response.data?.includes('<!DOCTYPE html>')) {
            return null;
        // not login
        // "err": "no app token set"
        } else if ('err' in response.data) {
            return false;
        }
        return response.data;
    }
}

export default CloudflareZerotrust;
