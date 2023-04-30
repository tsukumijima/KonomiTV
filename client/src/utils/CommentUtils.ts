
import { Buffer } from 'buffer';

import useSettingsStore from '@/store/SettingsStore';


/**
 * コメント周りのユーティリティ
 */
export class CommentUtils {

    // 「露骨な表現を含むコメントをミュートする」のフィルタ正規表現
    static readonly mute_vulgar_comments_pattern = new RegExp(Buffer.from('KGkpfChVKXxwcnByfO+9kO+9ku+9kO+9knxTRVh8U+OAh1h8U+KXr1h8U+KXi1h8U+KXj1h877yz77yl77y4fO+8s+OAh++8uHzvvLPil6/vvLh877yz4peL77y4fO+8s+KXj++8uHzjgqLjg4Djg6vjg4h844Ki44OK44KlfOOCouODiuODq3zjgqTjgqvoh61844Kk44GPfOOBhuOCk+OBk3zjgqbjg7PjgrN844GG44KT44GhfOOCpuODs+ODgXzjgqjjgq3jg5t844GI44Gh44GI44GhfOOBiOOBo+OBoXzjgqjjg4Pjg4F844GI44Gj44KNfOOCqOODg+ODrXzjgYjjgo1844Ko44OtfOW3peWPo3zjgYrjgZXjgo/jgorjgb7jgpN844GK44GX44Gj44GTfOOCquOCt+ODg+OCs3zjgqrjg4PjgrXjg7N844GK44Gj44Gx44GEfOOCquODg+ODkeOCpHzjgqrjg4rjg4vjg7x844GK44Gq44G7fOOCquODiuODm3zjgYrjgbHjgYR844Kq44OR44KkfOOBinB844GK772QfOOCquODleODkeOCs3zjgqzjgqTjgrjjg7N844Kt44Oz44K/44OefOOBj+OBseOBgnzjgY/jgbHjgYF844Kv44Oq44OI44Oq44K5fOOCr+ODs+ODi3zjgZTjgY/jgZTjgY/jgZTjgY/jgZTjgY9844Kz44Oz44OJ44O844OgfOOBkeOBpOOBguOBqnzjgrHjg4TjgqLjg4p844K244O844Oh44OzfOOCt+OCs3zjgZfjgZPjgZfjgZN844K344Kz44K344KzfOOBmeOBkeOBmeOBkXzjgZvjgYTjgYjjgY1844Gb44GE44KKfOOBm+ODvOOCinzjgZnjgYXjgYXjgYXjgYXjgYV844GZ44GG44GG44GG44GG44GGfOOCu+OCr+ODreOCuXzjgrvjg4Pjgq/jgrl844K744OV44OsfOOBoeOBo+OBseOBhHzjgaHjgaPjg5HjgqR844OB44OD44OR44KkfOOBoeOCk+OBk3zjgaHjgIfjgZN844Gh4pev44GTfOOBoeKXi+OBk3zjgaHil4/jgZN844OB44Oz44KzfOODgeOAh+OCs3zjg4Hil6/jgrN844OB4peL44KzfOODgeKXj+OCs3zjgaHjgpPjgb1844Gh44CH44G9fOOBoeKXr+OBvXzjgaHil4vjgb1844Gh4peP44G9fOODgeODs+ODnXzjg4HjgIfjg51844OB4pev44OdfOODgeKXi+ODnXzjg4Hil4/jg51844Gh44KT44Gh44KTfOODgeODs+ODgeODs3zjgabjgYPjgpPjgabjgYPjgpN844OG44Kj44Oz44OG44Kj44OzfOODhuOCo+ODs+ODnXzjg4fjgqvjgYR844OH44Oq44OY44OrfOOBquOBi+OBoOOBl3zjgarjgYvjgIfjgZd844Gq44GL4pev44GXfOOBquOBi+KXi+OBl3zjgarjgYvil4/jgZd86ISx44GSfOODjOOBhHzjg4zjgYt844OM44KrfOODjOOBjXzjg4zjgq1844OM44GPfOODjOOCr3zjg4zjgZF844OM44KxfOODjOOBk3zjg4zjgrN844Gx44GE44KC44G/fOODkeODkea0u3zjgbXjgYbjg7t844G144GG4oCmfOOBteOBhXzvvozvval844G144GP44KJ44G/fOOBteOBj+OCieOCk+OBp3zjgbrjgaPjgZ9844G644KN44G644KNfOODmuODreODmuODrXzvvo3vvp/vvpvvvo3vvp/vvpt844OV44Kn44OpfOOBu+OBhuOBkeOBhHzjgbzjgaPjgY1844Od44Or44OOfOOBvOOCjeOCk3zjg5zjg63jg7N8776O776e776b776dfOOBveOCjeOCinzjg53jg63jg6p8776O776f776b776YfOODnuODs+OBjeOBpHzjg57jg7Pjgq3jg4R844G+44KT44GTfOOBvuOAh+OBk3zjgb7il6/jgZN844G+4peL44GTfOOBvuKXj+OBk3zjg57jg7PjgrN844Oe44CH44KzfOODnuKXr+OCs3zjg57il4vjgrN844Oe4peP44KzfOOBvuOCk+OBleOCk3zjgoLjgaPjgZPjgop844Oi44OD44Kz44OqfOOCguOBv+OCguOBv3zjg6Ljg5/jg6Ljg59844Ok44Gj44GffOODpOOBo+OBpnzjg6Tjgol844KE44KJ44Gb44KNfOODpOOCinzjg6Tjgot844Ok44KMfOODpOOCjXzjg6njg5bjg5t844Ov44Os44OhfOaEm+a2snzllph86Zmw5qC4fOmZsOiMjnzpmbDllId85rer5aSifOmaoOavm3zpmbDmr5t855Sj44KB44KLfOWls+OBruWtkOOBruaXpXzmsZrjgaPjgZXjgpN85aemfOmojuS5l+S9jXzlt6jmoLl85beo44OB44OzfOW3qOePjXzph5Hnjol85pyI57WMfOW+jOiDjOS9jXzlrZDnqK585a2Q5L2c44KKfOWwhOeyvnzkv6HogIV857K+5rayfOmAj+OBkXzmgKfkuqR857K+5a2QfOato+W4uOS9jXzmgKflvrR85oCn55qEfOeUn+eQhnzlr7jmraLjgoF857Sg5p2QfOaKseOBhHzmirHjgYt85oqx44GNfOaKseOBj3zmirHjgZF85oqx44GTfOS9k+a2snzkubPpppZ85oGl5Z6ifOePjeajknzkuK3jgaDjgZd85Lit5Ye644GXfOWwv3zmipzjgYR85oqc44GR44Gq44GEfOaKnOOBkeOCi3zmipzjgZHjgox854qv54+NfOiGqOOCiXzljIXojI585YuD6LW3fOaRqee+hXzprZTnvoV85o+J44G+fOaPieOBv3zmj4njgoB85o+J44KBfOa8q+a5lnzjgIfvvZ584pev772efOKXi++9nnzil4/vvZ5844CH44OD44Kv44K5fOKXr+ODg+OCr+OCuXzil4vjg4Pjgq/jgrl84peP44OD44Kv44K5', 'base64').toString());

    // 「罵倒や差別的な表現を含むコメントをミュートする」のフィルタ正規表現
    static readonly mute_abusive_discriminatory_prejudiced_comments_pattern = new RegExp(Buffer.from('44CCfOOCouODi+ODl+ODrOOBj+OCk3zjgqLjg4vjg5fjg6zlkJt844Ki44K544OafOOCpOOCq+OCjHzjgYTjgb7jgYTjgaF844Kk44Oe44Kk44OBfOOCpOODqeOBpOOBj3zjgqbjgrh844Km44O844OofOOCpuODqHzjgqbjg6jjgq9844Km44OyfOOBjeOCguOBhHzjgq3jg6LjgqR844Kt44Oi44GEfOOCrS/jg6Av44OBfOOCrOOCpOOCuHzvvbbvvp7vvbLvvbzvvp5844Ks44KtfOOCq+OCuXzjgq3jg4Pjgrp844GN44Gh44GM44GEfOOCreODgeOCrOOCpHzjgq3jg6Djg4F844K344OKfOOCueODhuODnnzjgaTjgb7jgonjgap844Gk44G+44KJ44KTfOODgeODp+ODg+ODkeODqnzjg4Hjg6fjg7N85Y2D44On44OzfOOBpOOCk+OBvHzjg4Tjg7Pjg5x844ON44OI44Km44OofOOBq+OBoOOBguOBgnzjg4vjg4B85LqM44OAfO++hu++gO++nnzjg5Hjg7zjg6h844OR44OofOODkeODqOOCr3zjgbbjgaPjgZV844OW44OD44K1fOOBtuOBleOBhHzjg5bjgrXjgqR844G+44Gs44GRfOODoeOCr+ODqXzjg5Djgqt844Og44Kr44Gk44GPfOiNkuOCieOBl3zpurvnlJ/jgrvjg6Hjg7Pjg4h85oWw5a6J5ammfOWus+WFkHzlpJblrZd85aem5Zu9fOmfk+WbvXzpn5PkuK186Z+T5pelfOWfuuWcsOWklnzmsJfni4LjgYR85rCX6YGV44GEfOWIh+OBo+OBn3zliIfjgaPjgaZ85rCX5oyB44Gh5oKqfOWbveS6pOaWree1tnzmrrp86aCDfOmgg+OBl3zpoIPjgZl86aCD44GbfOWcqOaXpXzlj4LmlL/mqKl85q2744GtfOawj+OBrXzvvoDvvot85q255YyVfOatueODknzlpLHpgJ986Zqc5a6zfOaWreS6pHzkuK3pn5N85pyd6a6ufOW+tOeUqOW3pXzlo7p85aO3fOWjvHzml6Xpn5N85pel5bidfOeymOedgHzlj43ml6V86aas6bm/fOeZuueLgnznmbrpgZR85py0fOWjsuWbvXzkuI3lv6t85L215ZCIfOmWk+aKnOOBkXzmloflj6V86Z2W5Zu9', 'base64').toString());

    // 「8文字以上同じ文字が連続しているコメントをミュートする」のフィルタ正規表現
    static readonly mute_consecutive_same_characters_comments_pattern = /(.)\1{7,}/;

    // ニコ生の特殊コマンド付きコメントのフィルタ正規表現
    static readonly special_command_comments_pattern = /\/[a-z]+ /;

    // 迷惑な統計コメントのフィルタ正規表現
    static readonly annoying_statistical_comments_pattern = /最高\d+米\/|計\d+ＩＤ|総\d+米/;

    // ニコニコの色指定を 16 進数カラーコードに置換するテーブル
    static readonly color_table: {[key: string]: string} = {
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

        // 「罵倒や差別的な表現を含むコメントをミュートする」がオンの場合
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
