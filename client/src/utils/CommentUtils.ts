
import { Buffer } from 'buffer';

import useSettingsStore from '@/store/SettingsStore';
import Utils from '@/utils';

/**
 * コメント周りのユーティリティ
 */
export class CommentUtils {

    // 「露骨な表現を含むコメントをミュートする」のフィルタ正規表現
    static readonly mute_vulgar_comments_pattern = new RegExp(Buffer.from('cHJwcnzvvZDvvZLvvZDvvZJ8U0VYfFPjgIdYfFPil69YfFPil4tYfFPil49YfO+8s++8pe+8uHzvvLPjgIfvvLh877yz4pev77y4fO+8s+KXi++8uHzvvLPil4/vvLh844Ki44OA44Or44OIfOOCouODiuOCpXzjgqLjg4rjg6t844Kk44Kr6IetfOOCpOOBj3zjgYbjgpPjgZN844Km44Oz44KzfOOBhuOCk+OBoXzjgqbjg7Pjg4F844Ko44Kt44ObfOOBiOOBoeOBiOOBoXzjgYjjgaPjgaF844Ko44OD44OBfOOBiOOBo+OCjXzjgqjjg4Pjg61844GI44KNfOOCqOODrXzlt6Xlj6N844GK44GV44KP44KK44G+44KTfOOBiuOBl+OBo+OBk3zjgqrjgrfjg4PjgrN844Kq44OD44K144OzfOOBiuOBo+OBseOBhHzjgqrjg4Pjg5HjgqR844Kq44OK44OL44O8fOOBiuOBquOBu3zjgqrjg4rjg5t844GK44Gx44GEfOOCquODkeOCpHzjgYpwfOOBiu+9kHzjgqrjg5Xjg5HjgrN844Ks44Kk44K444OzfOOCreODs+OCv+ODnnzjgY/jgbHjgYJ844GP44Gx44GBfOOCr+ODquODiOODquOCuXzjgq/jg7Pjg4t844GU44GP44GU44GP44GU44GP44GU44GPfOOCs+ODs+ODieODvOODoHzjgrbjg7zjg6Hjg7N844K344KzfOOBl+OBk+OBl+OBk3zjgrfjgrPjgrfjgrN844GZ44GR44GZ44GRfOOBm+OBhOOBiOOBjXzjgZnjgYXjgYXjgYXjgYXjgYV844GZ44GG44GG44GG44GG44GGfOOCu+OCr+ODreOCuXzjgrvjg4Pjgq/jgrl844K744OV44OsfOOBoeOBo+OBseOBhHzjgaHjgaPjg5HjgqR844OB44OD44OR44KkfOOBoeOCk+OBk3zjgaHjgIfjgZN844Gh4pev44GTfOOBoeKXi+OBk3zjgaHil4/jgZN844OB44Oz44KzfOODgeOAh+OCs3zjg4Hil6/jgrN844OB4peL44KzfOODgeKXj+OCs3zjgaHjgpPjgb1844Gh44CH44G9fOOBoeKXr+OBvXzjgaHil4vjgb1844Gh4peP44G9fOODgeODs+ODnXzjg4HjgIfjg51844OB4pev44OdfOODgeKXi+ODnXzjg4Hil4/jg51844Gh44KT44Gh44KTfOODgeODs+ODgeODs3zjgabjgYPjgpPjgabjgYPjgpN844OG44Kj44Oz44OG44Kj44OzfOODhuOCo+ODs+ODnXzjg4fjgqvjgYR844OH44Oq44OY44OrfOiEseOBknzjgbHjgYTjgoLjgb9844OR44OR5rS7fOOBteOBhuODu3zjgbXjgYbigKZ844G144GFfO++jO+9qXzjgbXjgY/jgonjgb/jgYvjgZF844G144GP44KJ44KT44GnfOOBuuOBo+OBn3zjgbrjgo3jgbrjgo1844Oa44Ot44Oa44OtfO++je++n+++m+++je++n+++m3zjg5Xjgqfjg6l844G844Gj44GNfOODneODq+ODjnzjgbzjgo3jgpN844Oc44Ot44OzfO++ju++nu++m+++nXzjgb3jgo3jgop844Od44Ot44OqfO++ju++n+++m+++mHzjg57jg7PjgY3jgaR844Oe44Oz44Kt44OEfOOBvuOCk+OBk3zjgb7jgIfjgZN844G+4pev44GTfOOBvuKXi+OBk3zjgb7il4/jgZN844Oe44Oz44KzfOODnuOAh+OCs3zjg57il6/jgrN844Oe4peL44KzfOODnuKXj+OCs3zjgb7jgpPjgZXjgpN844KC44Gj44GT44KKfOODouODg+OCs+ODqnzjgoLjgb/jgoLjgb9844Oi44Of44Oi44OffOODpOOBo+OBn3zjg6TjgaPjgaZ844Ok44KJfOOChOOCieOBm+OCjXzjg6Tjgop844Ok44KLfOODpOOCjHzjg6Tjgo1844Op44OW44ObfOODr+ODrOODoXzllph86Zmw5qC4fOmZsOiMjnzpmbDllId85rer5aSifOmZsOavm3znlKPjgoHjgot85aWz44Gu5a2Q44Gu5pelfOaxmuOBo+OBleOCk3zlp6Z86aiO5LmX5L2NfOmHkeeOiXzmnIjntYx85b6M6IOM5L2NfOWtkOS9nOOCinzlsITnsr585L+h6ICFfOeyvua2snzpgI/jgZF85oCn5LqkfOeyvuWtkHzmraPluLjkvY185oCn5b60fOaAp+eahHznlJ/nkIZ85a+45q2i44KBfOe0oOadkHzmirHjgYR85oqx44GLfOaKseOBjXzmirHjgY985oqx44GRfOaKseOBk3zkubPpppZ85oGl5Z6ifOS4reOBoOOBl3zkuK3lh7rjgZd85bC/fOaKnOOBhHzmipzjgZHjgarjgYR85oqc44GR44KLfOaKnOOBkeOCjHzohqjjgol85YuD6LW3fOaPieOBvnzmj4njgb985o+J44KAfOaPieOCgXzmvKvmuZZ844CH772efOKXr++9nnzil4vvvZ584peP772efOOAh+ODg+OCr+OCuXzil6/jg4Pjgq/jgrl84peL44OD44Kv44K5fOKXj+ODg+OCr+OCuQ==', 'base64').toString());

    // 「罵倒や差別的な表現を含むコメントをミュートする」のフィルタ正規表現
    static readonly mute_abusive_discriminatory_prejudiced_comments_pattern = new RegExp(Buffer.from('44CCfOOCouOCueODmnzjgqTjgqvjgox844Kk44Op44Gk44GPfOOCpuOCuHzjgqbjg7zjg6h844Km44OofOOCpuODqOOCr3zjgqbjg7J844GN44KC44GEfOOCreODouOCpHzjgq3jg6LjgYR844KtL+ODoC/jg4F844Ks44Kk44K4fO+9tu++nu+9su+9vO++nnzjgqzjgq1844Kr44K5fOOCreODg+OCunzjgY3jgaHjgYzjgYR844Kt44OB44Ks44KkfOOCreODoOODgXzjg4Hjg6fjg7N85Y2D44On44OzfOOBpOOCk+OBvHzjg4Tjg7Pjg5x844ON44OI44Km44OofOOBq+OBoOOBguOBgnzjg4vjg4B8776G776A776efOODkeODvOODqHzjg5Hjg6h844OR44Oo44KvfOOBtuOBo+OBlXzjg5bjg4PjgrV844G244GV44GEfOODluOCteOCpHzjgb7jgazjgZF844Oh44Kv44OpfOODkOOCq3zjg6DjgqvjgaTjgY986bq755Sf44K744Oh44Oz44OIfOaFsOWuieWppnzlrrPlhZB85aSW5a2XfOWnpuWbvXzpn5Plm7186Z+T5LitfOmfk+aXpXzln7rlnLDlpJZ85rCX5oyB44Gh5oKqfOWbveS6pOaWree1tnzmrrp86aCD44GZfOWcqOaXpXzlj4LmlL/mqKl85q2744GtfOawj+OBrXzvvoDvvot85q255YyVfOatueODknzpmpzlrrN85pat5LqkfOS4remfk3zmnJ3prq585b6055So5belfOWjunzml6Xpn5N85pel5bidfOeymOedgHzlj43ml6V86aas6bm/fOeZuumBlHzmnLR85aOy5Zu9fOS4jeW/q3zplpPmipzjgZF86Z2W5Zu9', 'base64').toString());

    /**
     * ニコニコの色指定を 16 進数カラーコードに置換する
     * @param color ニコニコの色指定
     * @return 16 進数カラーコード
     */
    static getCommentColor(color: string): string {
        const color_table = {
            'white': '#FFEAEA',
            'red': '#F02840',
            'pink': '#FD7E80',
            'orange': '#FDA708',
            'yellow': '#FFE133',
            'green': '#64DD17',
            'cyan': '#00D4F5',
            'blue': '#4763FF',
            'purple': '#D500F9',
            'black': '#1E1310',
            'white2': '#CCCC99',
            'niconicowhite': '#CCCC99',
            'red2': '#CC0033',
            'truered': '#CC0033',
            'pink2': '#FF33CC',
            'orange2': '#FF6600',
            'passionorange': '#FF6600',
            'yellow2': '#999900',
            'madyellow': '#999900',
            'green2': '#00CC66',
            'elementalgreen': '#00CC66',
            'cyan2': '#00CCCC',
            'blue2': '#3399FF',
            'marineblue': '#3399FF',
            'purple2': '#6633CC',
            'nobleviolet': '#6633CC',
            'black2': '#666666',
        };
        if (color_table[color] !== undefined) {
            return color_table[color];
        } else {
            return null;
        }
    }

    /**
     * ニコニコの位置指定を DPlayer の位置指定に置換する
     * @param position ニコニコの位置指定
     * @return DPlayer の位置指定
     */
    static getCommentPosition(position: string): 'top' | 'right' | 'bottom' {
        switch (position) {
            case 'ue':
                return 'top';
            case 'naka':
                return 'right';
            case 'shita':
                return 'bottom';
            default:
                return null;
        }
    }

    /**
     * ミュート対象のコメントかどうかを判断する
     * @param comment コメント
     * @param user_id コメントを投稿したユーザーの ID
     * @return ミュート対象のコメントなら true を返す
     */
    static isMutedComment(comment: string, user_id: string): boolean {

        const settings_store = useSettingsStore();

        // キーワードミュート処理
        for (const muted_comment_keyword of settings_store.settings.muted_comment_keywords) {
            if (muted_comment_keyword.pattern === '') continue;  // キーワードが空文字のときは無視
            switch (muted_comment_keyword.match) {
                // 部分一致
                case 'partial':
                    if (comment.includes(muted_comment_keyword.pattern)) return true;
                    break;
                // 前方一致
                case 'forward':
                    if (comment.startsWith(muted_comment_keyword.pattern)) return true;
                    break;
                // 後方一致
                case 'backward':
                    if (comment.endsWith(muted_comment_keyword.pattern)) return true;
                    break;
                // 完全一致
                case 'exact':
                    if (comment === muted_comment_keyword.pattern) return true;
                    break;
                // 正規表現
                case 'regex':
                    if (new RegExp(muted_comment_keyword.pattern).test(comment)) return true;
                    break;
            }
        }

        // 「露骨な表現を含むコメントをミュートする」がオンの場合
        if (settings_store.settings.mute_vulgar_comments === true) {
            if (CommentUtils.mute_vulgar_comments_pattern.test(comment)) return true;
        }

        // 「罵倒や差別的な表現を含むコメントをミュートする」がオンの場合
        if (settings_store.settings.mute_abusive_discriminatory_prejudiced_comments === true) {
            if (CommentUtils.mute_abusive_discriminatory_prejudiced_comments_pattern.test(comment)) return true;
        }

        // 「8文字以上同じ文字が連続しているコメントをミュートする」がオンの場合
        if (settings_store.settings.mute_consecutive_same_characters_comments === true) {
            if (/(.)\1{7,}/.test(comment)) return true;
        }

        // 「ＮHK→計1447ＩＤ／内プレ425ＩＤ／総33372米 ◆ Ｅﾃﾚ → 計73ＩＤ／内プレ19ＩＤ／総941米」のような
        // 迷惑コメントを一括で弾く (あえてミュートしたくないユースケースが思い浮かばないのでデフォルトで弾く)
        if (/最高\d+米\/|計\d+ＩＤ|総\d+米/.test(comment)) return true;

        // ユーザー ID ミュート処理
        if (settings_store.settings.muted_niconico_user_ids.includes(user_id)) return true;

        // いずれのミュート処理にも引っかからなかった (ミュート対象ではない)
        return false;
    }

    // ミュート済みキーワードリストに追加する (完全一致)
    static addMutedKeywords(comment: string): void {
        // すでにまったく同じミュート済みキーワードが追加済みの場合は何もしない
        const settings_store = useSettingsStore();
        for (const muted_comment_keyword of settings_store.settings.muted_comment_keywords) {
            if (muted_comment_keyword.match === 'exact' && muted_comment_keyword.pattern === comment) {
                return;
            }
        }
        // ミュート済みキーワードリストに追加
        settings_store.settings.muted_comment_keywords.push({
            match: 'exact',
            pattern: comment,
        });
    }

    // ミュート済みニコニコユーザー ID リストに追加する
    static addMutedNiconicoUserIDs(user_id: string): void {
        // すでに追加済みの場合は何もしない
        const settings_store = useSettingsStore();
        if (settings_store.settings.muted_niconico_user_ids.includes(user_id)) {
            return;
        }
        // ミュート済みニコニコユーザー ID リストに追加
        settings_store.settings.muted_niconico_user_ids.push(user_id);
    }
}
