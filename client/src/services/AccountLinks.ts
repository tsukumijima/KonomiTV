
import APIClient from '@/services/APIClient';
import { IAccountLink } from '@/services/Users';


/** Twitter アカウントと Bluesky アカウントの紐付け作成リクエスト */
export interface IAccountLinkCreateRequest {
    twitter_account_id: number;
    bluesky_account_id: number;
}

class AccountLinks {

    /**
     * Twitter アカウントと Bluesky アカウントの紐付けを作成する
     * @param request 紐付け作成リクエスト
     * @returns 作成した紐付け情報
     */
    static async create(request: IAccountLinkCreateRequest): Promise<IAccountLink | null> {
        // 紐付け作成後は返却された Twitter / Bluesky の子レコードをそのまま画面の選択候補に反映する
        const response = await APIClient.post<IAccountLink>('/users/me/account-links', request);
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'アカウントの紐付けを作成できませんでした。');
            return null;
        }
        return response.data;
    }


    /**
     * Twitter アカウントと Bluesky アカウントの紐付けを解除する
     * @param link_id 紐付け ID
     * @returns 解除に成功した場合は true
     */
    static async delete(link_id: number): Promise<boolean> {
        // 紐付け解除はリンクレコードだけを削除し、個別の Twitter / Bluesky 連携は維持する
        const response = await APIClient.delete(`/users/me/account-links/${link_id}`);
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'アカウントの紐付けを解除できませんでした。');
            return false;
        }
        return true;
    }
}

export default AccountLinks;
