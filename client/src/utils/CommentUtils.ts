
import { Buffer } from 'buffer';

import useSettingsStore from '@/stores/SettingsStore';


/**
 * コメント周りのユーティリティ
 */
export class CommentUtils {

    // 「露骨な表現を含むコメントをミュートする」のフィルタ正規表現
    private static readonly mute_vulgar_comments_pattern = new RegExp(Buffer.from('XChpXCl8XChVXCl8cHJwcnzvvZDvvZLvvZDvvZJ8U0VYfFPjgIdYfFPil69YfFPil4tYfFPil49YfO+8s++8pe+8uHzvvLPjgIfvvLh877yz4pev77y4fO+8s+KXi++8uHzvvLPil4/vvLh844Ki44OA44Or44OIfOOCouOCveOCs3zjgqLjg4rjgqV844Ki44OK44OrfOOCpOOCq+iHrXzjgqTjgY9844Kk44Oz44OdfOOBhuOCk+OBk3zjgqbjg7PjgrN844GG44KT44GhfOOCpuODs+ODgXzjgqjjgq3jg5t844GI44Gh44GI44GhfOOBiOOBo+OBoXzjgqjjg4Pjg4F844GI44Gj44KNfOOCqOODg+ODrXzjgYjjgo1844Ko44OtfOW3peWPo3zjgqrjgqvjgrp844GK44GV44KP44KK44G+44KTfOOBiuOBl+OBo+OBk3zjgqrjgrfjg4PjgrN844Kq44OD44K144OzfOOBiuOBo+OBseOBhHzjgqrjg4Pjg5HjgqR844Kq44OK44OL44O8fOOBiuOBquOBu3zjgqrjg4rjg5t844GK44Gx44GEfOOCquODkeOCpHzjgYrjgoHjgZN844Kq44Oh44KzfOOBinB844GK772QfOOCquODleODkeOCs3zjgqzjgqTjgrjjg7N844Ks44OB44Og44OBfOOCreODoeOCu+OCr3zjgq3jg7Pjgr/jg55844GP44Gx44GCfOOBj+OBseOBgXzjgq/jg6rjg4jjg6rjgrl844Kv44Oz44OLfOOBlOOBj+OBlOOBj+OBlOOBj+OBlOOBj3zjgrPjg7Pjg4njg7zjg6B844GR44Gk44GC44GqfOOCseODhOOCouODinzjgrHjg4TnqbR844K244O844Oh44OzfOOCt+OCs3zjgZfjgZPjgZfjgZN844K344Kz44K344KzfOOBmeOBkeOBmeOBkXzjgZvjgYTjgYjjgY1844Gb44GE44KKfOOBm+ODvOOCinzjgZnjgYXjgYXjgYXjgYXjgYV844GZ44GG44GG44GG44GG44GGfOOCu+OCr+ODreOCuXzjgrvjg4Pjgq/jgrl844K744OV44OsfOOBoeOBo+OBseOBhHzjgaHjgaPjg5HjgqR844OB44OD44OR44KkfOOBoeOCk+OBk3zjgaHjgIfjgZN844Gh4pev44GTfOOBoeKXi+OBk3zjgaHil4/jgZN844OB44Oz44KzfOODgeOAh+OCs3zjg4Hil6/jgrN844OB4peL44KzfOODgeKXj+OCs3zjgaHjgpPjgb1844Gh44CH44G9fOOBoeKXr+OBvXzjgaHil4vjgb1844Gh4peP44G9fOODgeODs+ODnXzjg4HjgIfjg51844OB4pev44OdfOODgeKXi+ODnXzjg4Hil4/jg51844Gh44KT44Gh44KTfOODgeODs+ODgeODs3zjgabjgYPjgpPjgabjgYPjgpN844OG44Kj44Oz44OG44Kj44OzfOOBpuOBg+OCk+OBvXzjg4bjgqPjg7Pjg51844OH44Kr44GEfOODh+OCq+ODgeODs3zjg4fjg6rjg5jjg6t844Gq44GL44Gg44GXfOOBquOBi+OAh+OBl3zjgarjgYvil6/jgZd844Gq44GL4peL44GXfOOBquOBi+KXj+OBl3zohLHjgZJ844OM44GEfOODjOOBi3zjg4zjgqt844OM44GNfOODjOOCrXzjg4zjgY9844OM44KvfOODjOOBkXzjg4zjgrF844OM44GTfOODjOOCs3zjgbHjgYTjgoLjgb9844Gx44GE44Ga44KKfOODkeODs+ODhuOCo3zjg5HjgqTjgrrjg6p844OR44Kk44OR44OzfOODkOOCpOODlnzjg5Hjg5HmtLt844OP44OhfOODlOOCueODiOODs3zjg5Pjg4Pjg4F844G144GG44O7fOOBteOBhuKApnzjgbXjgYV8776M772pfOOBteOBj+OCieOBv3zjgbXjgY/jgonjgpPjgad844G644Gj44GffOOBuuOCjeOBuuOCjXzjg5rjg63jg5rjg618776N776f776b776N776f776bfOODleOCp+ODqXzjgbvjgYbjgZHjgYR844G844Gj44GNfOODneODq+ODjnzjgbzjgo3jgpN844Oc44Ot44OzfO++ju++nu++m+++nXzjgb3jgo3jgop844Od44Ot44OqfO++ju++n+++m+++mHzjg57jg7PjgY3jgaR844Oe44Oz44Kt44OEfOOBvuOCk+OBk3zjgb7jgIfjgZN844G+4pev44GTfOOBvuKXi+OBk3zjgb7il4/jgZN844Oe44Oz44KzfOODnuOAh+OCs3zjg57il6/jgrN844Oe4peL44KzfOODnuKXj+OCs3zjgb7jgpPjgZXjgpN844KC44Gj44GT44KKfOODouODg+OCs+ODqnzjgoLjgb/jgoLjgb9844Oi44Of44Oi44OffOODpOOBo+OBn3zjg6TjgaPjgaZ844Ok44KJfOOChOOCieOBm+OCjXzjg6Tjgop844Ok44OqfOODpOOCi3zjg6Tjgox844Ok44KNfOODqeODluODm3zjg6/jg6zjg6F85oSb5rayfOWWmHzpmbDmoLh86Zmw6IyOfOmZsOWUh3zmt6t86Zqg5q+bfOmZsOavm3znlKPjgoHjgot85aWz44Gu5a2Q44Gu5pelfOaxmuOBo+OBleOCk3zlp6Z86aiO5LmX5L2NfOW3qOS5s3zlt6jmoLl85beo5bC7fOW3qOODgeODs3zlt6jnj4186YeR546JfOaciOe1jHzlvozog4zkvY185a2Q56iufOWtkOS9nOOCinzlsITnsr585r2u5ZC5fOS/oeiAhXznsr7mtrJ86YCP44GRfOaAp+S6pHznsr7lrZB85q2j5bi45L2NfOaAp+W+tHzmgKfnmoR855Sf55CGfOe1tuWAq3zlr7jmraLjgoF857Sg5p2QfOaKseOBhHzmirHjgYt85oqx44GNfOaKseOBj3zmirHjgZF85oqx44GTfOS9k+a2snzkubPpppZ85oGl5Z6ifOePjeajknzkuK3jgaDjgZd85Lit5Ye644GXfOWwv3zmipzjgYR85oqc44GR44Gq44GEfOaKnOOBkeOCi3zmipzjgZHjgox85o6S5L6/fOeKr+ePjXzohqjjgol85YyF6IyOfOWLg+i1t3zohpx85pGp576FfOmtlOe+hXzmj4njgb585o+J44G/fOaPieOCgHzmj4njgoF85ryr5rmWfOOAh++9nnzil6/vvZ584peL772efOKXj++9nnzjgId+fOKXr3584peLfnzil49+fOOAh+ODg+OCr+OCuXzil6/jg4Pjgq/jgrl84peL44OD44Kv44K5fOKXj+ODg+OCr+OCuQ==', 'base64').toString());

    // 「ネガティブな表現、差別的な表現、政治的に偏った表現を含むコメントをミュートする」のフィルタ正規表現
    private static readonly mute_abusive_discriminatory_prejudiced_comments_pattern = new RegExp(Buffer.from('44CCfOOCouODi+ODl+ODrOOBj+OCk3zjgqLjg4vjg5fjg6zlkJt844Ki44K544OafOOBguOBu3zjgqLjg5t86Zi/5ZGGfOOCpOOCq+OCjHzjgYTjgb7jgYTjgaF844Kk44Oe44Kk44OBfOOCpOODqeOBpOOBj3zjgqbjgrh844Km44O844OofOOCpuODqHzjgqbjg6jjgq9844Km44OyfOOBjeOCguOBhHzjgq3jg6LjgqR844Kt44Oi44GEfOOCrS/jg6Av44OBfOOCrOOCpOOCuHzvvbbvvp7vvbLvvbzvvp5844Ks44KtfOOCq+OCuXzjgq3jg4Pjgrp844GN44Gh44GM44GEfOOCreODgeOCrOOCpHzjgq3jg6Djg4F844GN44KJ44GEfOOCreODqeOCpHzlq4zjgYR844Kv44K9fOeznnzjgrfjg4p844K544OG44OefOOBpOOBvuOCieOBqnzjgaTjgb7jgonjgpN844OB44On44OD44OR44OqfOODgeODp+ODs3zljYPjg6fjg7N844Gk44KT44G8fOODhOODs+ODnHzjg43jg4jjgqbjg6h844Gr44Gg44GC44GCfOODi+ODgHzkuozjg4B8776G776A776efOODkeODvOODqHzjg5Hjg6h844OR44Oo44KvfF7jgbTjg7wkfF7jg5Tjg7wkfOOBtuOBo+OBlXzjg5bjg4PjgrV844G244GV44GEfOODluOCteOCpHzjg5jjgqTjg4jjgrnjg5Tjg7zjg4F844Ob44OifOOBvuOBrOOBkXzjg6Hjgq/jg6l844OQ44KrfOODoOOCq+OBpOOBj3zojZLjgonjgZd86bq755Sf44K744Oh44Oz44OIfOWPs+e/vHzmsZrnial85oWw5a6J5ammfOWus+WFkHzlpJblrZd85aem5Zu9fOmfk+WbvXzpn5PkuK186Z+T5pelfOWfuuWcsOWklnzmsJfni4LjgYR85rCX6YGV44GEfOWIh+OBo+OBn3zliIfjgaPjgaZ85rCX5oyB44Gh5oKqfOiHrXzlsZF85Zu95Lqk5pat57W2fOW3pue/vHzmrrp86aCDfOmgg+OBl3zpoIPjgZl86aCD44GbfOWcqOaXpXzlnKjml6XnibnmqKl85Zyo54m55LyafOWPguaUv+aoqXznsr7npZ7nlbDluLjogIV85q2744GtfOawj+OBrXzvvoDvvot85q255YyVfOatueODknzlpLHpgJ986Zqc5a6zfOWkp+adseS6nHzmlq3kuqR85Lit6Z+TfOacnemurnzlvrTnlKjlt6V85aO6fOWjt3zlo7x85pel6Z+TfOaXpeW4nXznspjnnYB85Y+N5pelfOWPjeawkeaXj3zppqzpub9855m654uCfOeZuumBlHzmnLR85aOy5Zu9fOS4jeW/q3zkvbXlkIh86ZaT5oqc44GRfOeEoeiDvXzmloflj6V86Z2W5Zu9fOmHjumDjg==', 'base64').toString());

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
