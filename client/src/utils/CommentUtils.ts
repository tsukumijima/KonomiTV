
import { Buffer } from 'buffer';

import useSettingsStore from '@/stores/SettingsStore';


/**
 * コメント周りのユーティリティ
 */
export class CommentUtils {

    // 「露骨な表現を含むコメントをミュートする」のフィルタ正規表現
    private static readonly mute_vulgar_comments_pattern = new RegExp(Buffer.from('XChpXCl8XChVXCl8cHJwcnzvvZDvvZLvvZDvvZJ8U0VYfFPjgIdYfFPil69YfFPil4tYfFPil49YfO+8s++8pe+8uHzvvLPjgIfvvLh877yz4pev77y4fO+8s+KXi++8uHzvvLPil4/vvLh844Ki44OA44Or44OIfOOCouOCveOCs3zjgqLjg4rjgqV844Ki44OK44OrfOOCpOOCq+iHrXzjgqTjgY9844Kk44Oz44OdfOOBhuOCk+OBk3zjgqbjg7PjgrN844GG44KT44GhfOOCpuODs+ODgXzjgqjjgq3jg5t844GI44Gh44GI44GhfOOBiOOBo+OBoXzjgqjjg4Pjg4F844GI44Gj44KNfOOCqOODg+ODrXxe44GI44KNfOOCqOODrXzlt6Xlj6N844Kq44Kr44K6fOOBiuOBleOCj+OCiuOBvuOCk3zjgYrjgZfjgaPjgZN844Kq44K344OD44KzfOOCquODg+OCteODs3zjgYrjgaPjgbHjgYR844Kq44OD44OR44KkfOOCquODiuODi+ODvHzjgYrjgarjgbt844Kq44OK44ObfOOBiuOBseOBhHzjgqrjg5HjgqR844GK44KB44GTfOOCquODoeOCs3zjgYpwfOOBiu+9kHzjgqrjg5Xjg5HjgrN844Ks44OB44Og44OBfOOCreODoeOCu+OCr3zjgq3jg7Pjgr/jg55844GP44Gx44GCfOOBj+OBseOBgXzjgq/jg6rjg4jjg6rjgrl844Kv44Oz44OLfOOBlOOBj+OBlOOBj+OBlOOBj+OBlOOBj3zjgrPjg7Pjg4njg7zjg6B844GR44Gk44GC44GqfOOCseODhOOCouODinzjgrHjg4TnqbR844K244O844Oh44OzfOOCt+OCs3zjgZfjgZPjgZfjgZN844K344Kz44K344KzfOOBmeOBkeOBmeOBkXzjgZvjgYTjgYjjgY1844Gb44GE44KKfOOBm+ODvOOCinzjgZnjgYXjgYXjgYV844GZ44GG44GG44GGfOOCu+OCr+ODreOCuXzjgrvjg4Pjgq/jgrl844K744OV44OsfOOBoeOBo+OBseOBhHzjgaHjgaPjg5HjgqR844OB44OD44OR44KkfOOBoeOCk+OBk3zjgaHjgIfjgZN844Gh4pev44GTfOOBoeKXi+OBk3zjgaHil4/jgZN844OB44Oz44KzfOODgeOAh+OCs3zjg4Hil6/jgrN844OB4peL44KzfOODgeKXj+OCs3zjgaHjgpPjgb1844Gh44CH44G9fOOBoeKXr+OBvXzjgaHil4vjgb1844Gh4peP44G9fOODgeODs+ODnXzjg4HjgIfjg51844OB4pev44OdfOODgeKXi+ODnXzjg4Hil4/jg51844Gh44KT44Gh44KTfOODgeODs+ODgeODs3zjgabjgYPjgpPjgabjgYPjgpN844OG44Kj44Oz44OG44Kj44OzfOOBpuOBg+OCk+OBvXzjg4bjgqPjg7Pjg51844OH44Kr44GEfOODh+OCq+ODgeODs3zjg4fjg6rjg5jjg6t844Gq44GL44Gg44GXfOOBquOBi+OAh+OBl3zjgarjgYvil6/jgZd844Gq44GL4peL44GXfOOBquOBi+KXj+OBl3zohLHjgZJ844OM44GEfOODjOOBi3zjg4zjgqt844OM44GNfOODjOOCrXzjg4zjgY9844OM44KvfOODjOOBkXzjg4zjgrF844OM44GTfOODjOOCs3zjgbHjgYTjgoLjgb9844Gx44GE44Ga44KKfOODkeODs+ODhuOCo3zjg5HjgqTjgrrjg6p844OR44Kk44OR44OzfOODkOOCpOODlnzjg5Hjg5HmtLt844OP44OhfOODlOOCueODiOODs3zjg5Pjg4Pjg4F844G144GG44O7fOOBteOBhuKApnzjgbXjgYV8776M772pfOOBteOBj+OCieOBv3zjgbXjgY/jgonjgpPjgad844G644Gj44GffOOBuuOCjeOBuuOCjXzjg5rjg63jg5rjg618776N776f776b776N776f776bfOODleOCp+ODqXzjgbvjgYbjgZHjgYR844G844Gj44GNfOODneODq+ODjnzjgbzjgo3jgpN844Oc44Ot44OzfO++ju++nu++m+++nXzjgb3jgo3jgop844Od44Ot44OqfO++ju++n+++m+++mHzjg57jg7PjgY3jgaR844Oe44Oz44Kt44OEfOOBvuOCk+OBk3zjgb7jgIfjgZN844G+4pev44GTfOOBvuKXi+OBk3zjgb7il4/jgZN844Oe44Oz44KzfOODnuOAh+OCs3zjg57il6/jgrN844Oe4peL44KzfOODnuKXj+OCs3zjgb7jgpPjgZXjgpN844KC44Gj44GT44KKfOODouODg+OCs+ODqnzjgoLjgb/jgoLjgb9844Oi44Of44Oi44OffOODpOOBo+OBn3zjg6TjgaPjgaZ844Ok44KJfOOChOOCieOBm+OCjXzjg6Tjgop844Ok44OqfOODpOOCi3zjg6Tjgox844Ok44KNfOODqeODluODm3zjg6/jg6zjg6F85oSb5rayfOWSpXzllph86Zmw5qC4fOmZsOiMjnzpmbDllId85rerfOmaoOavm3zpmbDmr5t855Sj44KB44KLfOWls+OBruWtkOOBruaXpXzmsZrjgaPjgZXjgpN85aemfOmojuS5l+S9jXzlt6jkubN85beo5qC5fOW3qOWwu3zlt6jjg4Hjg7N85beo54+NfOmHkeeOiXzmnIjntYx85b6M6IOM5L2NfOWtkOeornzlrZDkvZzjgop85bCE57K+fOa9ruWQuXzkv6HogIV857K+5rayfOmAj+OBkXzmgKfkuqR857K+5a2QfOato+W4uOS9jXzmgKflvrR85oCn55qEfOeUn+eQhnzntbblgKt85a+45q2i44KBfOe0oOadkHzmirHjgYR85oqx44GLfOaKseOBjXzmirHjgY985oqx44GRfOaKseOBk3zkvZPmtrJ85Lmz6aaWfOaBpeWeonznj43mo5J85Lit44Gg44GXfOS4reWHuuOBl3zlsL985oqc44GEfOaKnOOBkeOBquOBhHzmipzjgZHjgot85oqc44GR44KMfOaOkuS+v3zniq/nj4186Iao44KJfOWMheiMjnzli4Potbd86IacfOaRqee+hXzprZTnvoV85o+J44G+fOaPieOBv3zmj4njgoB85o+J44KBfOa8q+a5lnzjgIfvvZ584pev772efOKXi++9nnzil4/vvZ5844CHfnzil69+fOKXi3584pePfnzjgIfjg4Pjgq/jgrl84pev44OD44Kv44K5fOKXi+ODg+OCr+OCuXzil4/jg4Pjgq/jgrk=', 'base64').toString());

    // 「ネガティブな表現、差別的な表現、政治的に偏った表現を含むコメントをミュートする」のフィルタ正規表現
    private static readonly mute_abusive_discriminatory_prejudiced_comments_pattern = new RegExp(Buffer.from('44CCfOOCouODi+ODl+ODrOOBj+OCk3zjgqLjg4vjg5fjg6zlkJt844Ki44K544OafOOBguOBu3zjgqLjg5t86Zi/5ZGGfOOCpOOCq+OCjHzjgYTjgb7jgYTjgaF844Kk44Oe44Kk44OBfOOCpOODqeOBpOOBj3zjgqbjgrh844Km44O844OofOOCpuODqHzjgqbjg6jjgq9844Km44OyfOOBjeOCguOBhHzjgq3jg6LjgqR844Kt44Oi44GEfOOCrS/jg6Av44OBfOOCrOOCpOOCuHzvvbbvvp7vvbLvvbzvvp5844Ks44Kk44K444OzfOOCrOOCrXzjgqvjgrl844Kt44OD44K6fOOBjeOBoeOBjOOBhHzjgq3jg4HjgqzjgqR844Kt44Og44OBfOOBjeOCieOBhHzjgq3jg6njgqR85auM44GEfOOCr+OCvXzns55844K344OKfOOCueODhuODnnzjgaTjgb7jgonjgap844Gk44G+44KJ44KTfOODgeODp+ODg+ODkeODqnzjg4Hjg6fjg7N85Y2D44On44OzfOOBpOOCk+OBvHzjg4Tjg7Pjg5x844ON44OI44Km44OofOOBq+OBoOOBguOBgnzjg4vjg4B85LqM44OAfO++hu++gO++nnzjg5Hjg7zjg6h844OR44OofOODkeODqOOCr3xe44G044O8JHxe44OU44O8JHzjgbbjgaPjgZV844OW44OD44K1fOOBtuOBleOBhHzjg5bjgrXjgqR844OY44Kk44OI44K544OU44O844OBfOODm+ODonzjgb7jgazjgZF844Oh44Kv44OpfOODkOOCq3zjg6DjgqvjgaTjgY986I2S44KJ44GXfOm6u+eUn+OCu+ODoeODs+ODiHzlj7Pnv7x85rGa54mpfOaFsOWuieWppnzlrrPlhZB85aSW5a2XfOWnpuWbvXzpn5Plm7186Z+T5LitfOmfk+aXpXzln7rlnLDlpJZ85rCX54uC44GEfOawl+mBleOBhHzliIfjgaPjgZ985YiH44Gj44GmfOawl+aMgeOBoeaCqnzoh6185bGRfOWbveS6pOaWree1tnzlm73nsY185Zu944Gr5biw44KMfOWbveOBuOW4sOOCjHzlt6bnv7x85q66fOmgg3zpoIPjgZd86aCD44GZfOmgg+OBm3xe5ZyofOWcqOaXpXzlnKjml6XnibnmqKl85Zyo54m55LyafOWPguaUv+aoqXznsr7npZ7nlbDluLjogIV85q2744GtfOawj+OBrXzvvoDvvot85q255YyVfOatueODknzmrbvliJF844K344Kx44KkfOOBl+OBkeOBhHzlpLHpgJ986Zqc5a6zfOWkp+adseS6nHzmlq3kuqR86YCa5ZCNfOS4remfk3zmnJ3prq585b6055So5belfOWjunzlo7d85aO8fOaXpemfk3zml6XluJ1857KY552AfOWNiuWztnzlj43ml6V85Y+N5rCR5pePfOmmrOm5v3znmbrni4J855m66YGUfOactHzlo7Llm7185LiN5b+rfOS9teWQiHzplpPmipzjgZF854Sh6IO9fOaWh+WPpXzpnZblm7186YeO6YOO', 'base64').toString());

    // 「8文字以上同じ文字が連続しているコメントをミュートする」のフィルタ正規表現
    private static readonly mute_consecutive_same_characters_comments_pattern = /(.)\1{7,}/;

    // ニコ生の特殊コマンド付きコメントのフィルタ正規表現
    private static readonly special_command_comments_pattern = /\/[a-z]+ /;

    // 迷惑な統計コメントのフィルタ正規表現
    private static readonly annoying_statistical_comments_pattern = /最高\d+米\/|計\d+ＩＤ|総\d+米/;

    // ニコニコの色指定を 16 進数カラーコードに置換するテーブル
    private static readonly color_table: {[key: string]: string} = {
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


    /**
     * ニコニコの色指定を 16 進数カラーコードに置換する
     * @param color ニコニコの色指定
     * @return 16 進数カラーコード
     */
    static getCommentColor(color: string): string | null {
        return this.color_table[color] || null;
    }


    /**
     * ニコニコの位置指定を DPlayer の位置指定に置換する
     * @param position ニコニコの位置指定
     * @return DPlayer の位置指定
     */
    static getCommentPosition(position: string): 'top' | 'right' | 'bottom' | null {
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
     * ニコニコのサイズ指定を DPlayer のサイズ指定に置換する
     * @param size ニコニコのサイズ指定
     * @returns DPlayer のサイズ指定
     */
    static getCommentSize(size: string): 'big' | 'medium' | 'small' | null {
        switch (size) {
            case 'big':
            case 'medium':
            case 'small':
                return size;
            default:
                return null;
        }
    }


    /**
     * ニコニコのコメントコマンドを解析する
     * @param comment_mail ニコニコのコメントコマンド
     * @returns コメントの色、位置、サイズ
     */
    static parseCommentCommand(comment_mail: string): {
        color: string;
        position: 'top' | 'right' | 'bottom';
        size: 'big' | 'medium' | 'small';
    } {
        let color = '#FFEAEA';
        let position: 'top' | 'right' | 'bottom' = 'right';
        let size: 'big' | 'medium' | 'small' = 'medium';

        if (comment_mail !== undefined && comment_mail !== null) {
            const commands = comment_mail.replace('184', '').split(' ');

            for (const command of commands) {
                const parsed_color = CommentUtils.getCommentColor(command);
                const parsed_position = CommentUtils.getCommentPosition(command);
                const parsed_size = CommentUtils.getCommentSize(command);
                if (parsed_color !== null) {
                    color = parsed_color;
                }
                if (parsed_position !== null) {
                    position = parsed_position;
                }
                if (parsed_size !== null) {
                    size = parsed_size;
                }
            }
        }

        return {color, position, size};
    }


    /**
     * ミュート対象のコメントかどうかを判断する
     * @param comment コメント
     * @param user_id コメントを投稿したユーザーの ID
     * @param color コメントの色
     * @param position コメントの位置
     * @param size コメントのサイズ
     * @return ミュート対象のコメントなら true を返す
     */
    static isMutedComment(
        comment: string,
        user_id: string,
        color?: string,
        position?: 'top' | 'right' | 'bottom',
        size?: 'big' | 'medium' | 'small',
    ): boolean {

        const settings_store = useSettingsStore();

        // ユーザー ID ミュート処理
        if (settings_store.settings.muted_niconico_user_ids.includes(user_id)) {
            return true;
        }

        // ニコ生の特殊コマンド付きコメント (/nicoad, /emotion など) を一括で弾く
        if (CommentUtils.special_command_comments_pattern.test(comment)) {
            return true;
        }

        // 「映像の上下に固定表示されるコメントをミュートする」がオンの場合
        // コメントの位置が top (上固定) もしくは bottom (下固定) のときは弾く
        if (settings_store.settings.mute_fixed_comments === true && (position === 'top' || position === 'bottom')) {
            console.log('[CommentUtils] Muted comment (fixed_comments): ' + comment);
            return true;
        }

        // 「色付きのコメントをミュートする」がオンの場合
        // コメントの色が #FFEAEA (デフォルト) 以外のときは弾く
        if (settings_store.settings.mute_colored_comments === true && color !== '#FFEAEA') {
            console.log('[CommentUtils] Muted comment (colored_comments): ' + comment);
            return true;
        }

        // 「文字サイズが大きいコメントをミュートする」がオンの場合
        // コメントのサイズが big のときは弾く
        if (settings_store.settings.mute_big_size_comments === true && size === 'big') {
            console.log('[CommentUtils] Muted comment (big_size_comments): ' + comment);
            return true;
        }

        // 「露骨な表現を含むコメントをミュートする」がオンの場合
        if ((settings_store.settings.mute_vulgar_comments === true) &&
            (CommentUtils.mute_vulgar_comments_pattern.test(comment))) {
            console.log('[CommentUtils] Muted comment (vulgar_comments): ' + comment);
            return true;
        }

        // 「ネガティブな表現、差別的な表現、政治的に偏った表現を含むコメントをミュートする」がオンの場合
        if ((settings_store.settings.mute_abusive_discriminatory_prejudiced_comments === true) &&
            (CommentUtils.mute_abusive_discriminatory_prejudiced_comments_pattern.test(comment))) {
            console.log('[CommentUtils] Muted comment (abusive_discriminatory_prejudiced_comments): ' + comment);
            return true;
        }

        // 「8文字以上同じ文字が連続しているコメントをミュートする」がオンの場合
        if ((settings_store.settings.mute_consecutive_same_characters_comments === true &&
            (CommentUtils.mute_consecutive_same_characters_comments_pattern.test(comment)))) {
            console.log('[CommentUtils] Muted comment (consecutive_same_characters_comments): ' + comment);
            return true;
        }

        // キーワードミュート処理
        for (const muted_comment_keyword of settings_store.settings.muted_comment_keywords) {
            if (muted_comment_keyword.pattern === '') continue;  // キーワードが空文字のときは無視
            switch (muted_comment_keyword.match) {
                // 部分一致
                case 'partial':
                    if (comment.includes(muted_comment_keyword.pattern)) {
                        console.log('[CommentUtils] Muted comment (partial): ' + comment);
                        return true;
                    }
                    break;
                // 前方一致
                case 'forward':
                    if (comment.startsWith(muted_comment_keyword.pattern)) {
                        console.log('[CommentUtils] Muted comment (forward): ' + comment);
                        return true;
                    }
                    break;
                // 後方一致
                case 'backward':
                    if (comment.endsWith(muted_comment_keyword.pattern)) {
                        console.log('[CommentUtils] Muted comment (backward): ' + comment);
                        return true;
                    }
                    break;
                // 完全一致
                case 'exact':
                    if (comment === muted_comment_keyword.pattern) {
                        console.log('[CommentUtils] Muted comment (exact): ' + comment);
                        return true;
                    }
                    break;
                // 正規表現
                case 'regex':
                    if (new RegExp(muted_comment_keyword.pattern).test(comment)) {
                        console.log('[CommentUtils] Muted comment (regex): ' + comment);
                        return true;
                    }
                    break;
            }
        }

        // 「ＮHK→計1447ＩＤ／内プレ425ＩＤ／総33372米 ◆ Ｅﾃﾚ → 計73ＩＤ／内プレ19ＩＤ／総941米」のような
        // 迷惑コメントを一括で弾く (あえてミュートしたくないユースケースが思い浮かばないのでデフォルトで弾く)
        // 一番最後なのは、この迷惑コメント自体の頻度が低いため
        if (CommentUtils.annoying_statistical_comments_pattern.test(comment)) {
            return true;
        }

        // いずれのミュート処理にも引っかからなかった (ミュート対象ではない)
        return false;
    }


    /**
     * ミュート済みキーワードリストに追加する (完全一致)
     * @param comment コメント文字列
     */
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


    /**
     * ミュート済みニコニコユーザー ID リストに追加する
     * @param user_id ニコニコユーザー ID
     */
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
