
import { Buffer } from 'buffer';

import useSettingsStore from '@/stores/SettingsStore';


/**
 * コメント周りのユーティリティ
 */
export class CommentUtils {

    // 「露骨な表現を含むコメントをミュートする」のフィルタ正規表現
    private static readonly mute_vulgar_comments_pattern = new RegExp(Buffer.from('XChpXCl8XChVXCl8cHJwcnzvvZDvvZLvvZDvvZJ8U0VYfFPjgIdYfFPil69YfFPil4tYfFPil49YfO+8s++8pe+8uHzvvLPjgIfvvLh877yz4pev77y4fO+8s+KXi++8uHzvvLPil4/vvLh844Ki44OA44Or44OIfOOCouOCveOCs3zjgqLjg4rjgqV844Ki44OK44OrfOOCpOOCq+iHrXzjgqTjgY9844Kk44Oz44OdfOOBhuOCk+OBk3zjgqbjg7PjgrN844GG44KT44GhfOOCpuODs+ODgXzjgqjjgq3jg5t844GI44Gh44GI44GhfOOBiOOBo+OBoXzjgqjjg4Pjg4F844GI44Gj44KNfOOCqOODg+ODrXxe44GI44KNfOOBiOOCjeOBhHzjgqjjg6185bel5Y+jfOOCquOCq+OCunzjgYrjgZXjgo/jgorjgb7jgpN844GK44GX44Gj44GTfOOCquOCt+ODg+OCs3zjgqrjg4PjgrXjg7N844GK44Gj44Gx44GEfOOCquODg+ODkeOCpHzjgqrjg4rjg4vjg7x844GK44Gq44G7fOOCquODiuODm3zjgYrjgbHjgYR844Kq44OR44KkfO+9te++iu++n++9snzjgYrjgb7jgZ9844Kq44Oe44K/fO+9te++j+++gHzjgYrjgoHjgZN844Kq44Oh44KzfO+9te++ku+9unzjgYpwfOOBiu+9kHzjgqrjg5Xjg5HjgrN844Ks44OB44Og44OBfOOCreODoeOCu+OCr3zjgq3jg7Pjgr/jg55844GP44Gx44GCfOOBj+OBseOBgXzjgq/jg6rjg4jjg6rjgrl844Kv44Oz44OLfOOBlOOBj+OBlOOBj+OBlOOBj+OBlOOBj3zjgrPjg7Pjg4njg7zjg6B844GR44Gk44GC44GqfOOCseODhOOCouODinzjgrHjg4TnqbR844K244O844Oh44OzfOOCt+OCs3zjgZfjgZPjgZfjgZN844K344KzfOOBmeOBkeOBmeOBkXzjgZvjgYTjgYjjgY1844Gb44GE44KKfOOBm+ODvOOCinzjgZnjgYXjgYXjgYV844GZ44GG44GG44GGfOOCu+OCr+ODreOCuXzjgrvjg4Pjgq/jgrl844K744OV44OsfOOBoeOBo+OBseOBhHzjgaHjgaPjg5HjgqR844OB44OD44OR44KkfOOBoeOCk+OBk3zjgaHjgIfjgZN844Gh4pev44GTfOOBoeKXi+OBk3zjgaHil4/jgZN844OB44Oz44KzfOODgeOAh+OCs3zjg4Hil6/jgrN844OB4peL44KzfOODgeKXj+OCs3zjgaHjgpPjgb1844Gh44CH44G9fOOBoeKXr+OBvXzjgaHil4vjgb1844Gh4peP44G9fOODgeODs+ODnXzjg4HjgIfjg51844OB4pev44OdfOODgeKXi+ODnXzjg4Hil4/jg51844Gh44KT44Gh44KTfOODgeODs+ODgeODs3zjgaHjg7zjgpN844Gh44Cc44KTfOODgeOAnOODs3zjgabjgYPjgpPjgabjgYPjgpN844OG44Kj44Oz44OG44Kj44OzfOOBpuOBg+OCk+OBvXzjg4bjgqPjg7Pjg51844OH44Kr44GEfOODh+OCq+ODgeODs3zjg4fjg6rjg5jjg6t844Ga44KL44KA44GRfOOCuuODq+ODoOOCsXzjgarjgYvjgaDjgZd844Gq44GL44CH44GXfOOBquOBi+KXr+OBl3zjgarjgYvil4vjgZd844Gq44GL4peP44GXfOiEseOBknzjg4zjgYR844OM44GLfOODjOOCq3zjg4zjgY1844OM44KtfOODjOOBj3zjg4zjgq9844OM44GRfOODjOOCsXzjg4zjgZN844OM44KzfOOBseOBhOOCguOBv3zjgbHjgYTjgZrjgop844OR44Oz44OG44KjfOODkeOCpOOCuuODqnzjg5HjgqTjg5Hjg7N844OQ44Kk44OWfOODkeODkea0u3zjg4/jg6F844OU44K544OI44OzfOODk+ODg+ODgXzjgbXjgYbjg7t844G144GG4oCmfOOBteOBhXzvvozvval844G144GP44KJ44G/fOOBteOBj+OCieOCk+OBp3zjgbrjgaPjgZ9844G644KN44G644KNfOODmuODreODmuODrXzvvo3vvp/vvpvvvo3vvp/vvpt844OV44Kn44OpfOOBu+OBhuOBkeOBhHzjgbzjgaPjgY1844Od44Or44OOfOOBvOOCjeOCk3zjg5zjg63jg7N8776O776e776b776dfOOBveOCjeOCinzjg53jg63jg6p8776O776f776b776YfOOBvuODvOOCk3zjgb7jgJzjgpN844Oe44Cc44OzfOODnuODs+OBjeOBpHzjg57jg7Pjgq3jg4R844G+44KT44GTfOOBvuOAh+OBk3zjgb7il6/jgZN844G+4peL44GTfOOBvuKXj+OBk3zjg57jg7PjgrN844Oe44CH44KzfOODnuKXr+OCs3zjg57il4vjgrN844Oe4peP44KzfOOBvuOCk+OBleOCk3zjgoLjgaPjgZPjgop844Oi44OD44Kz44OqfOOCguOBv+OCguOBv3zjg6Ljg5/jg6Ljg59844Ok44Gj44GffOODpOOBo+OBpnzjg6Tjgol844KE44KJ44Gb44KNfOODpOOCinzjg6Tjg6p844Ok44Oq44OB44OzfOODpOODquODnuODs3zjg6Tjgot844Ok44KMfOODpOOCjXzjg6njg5bjg5t844Ov44Os44OhfOaEm+a2snzlkqV85ZaYfOmZsOaguHzpmbDojI586Zmw5ZSHfOa3q3zpmqDmr5t86Zmw5q+bfOeUo+OCgeOCi3zlpbPjga7lrZDjga7ml6V85rGa44Gj44GV44KTfOiyneWQiHzlp6Z86LKr6YCafOmojuS5l+S9jXzlt6jkubN85beo5qC5fOW3qOWwu3zlt6jjg4Hjg7N85beo54+NfOmHkeeOiXzmnIjntYx85b6M6IOM5L2NfOWtkOeornzlrZDkvZzjgop85bCE57K+fOa9ruWQuXzkv6HogIV857K+5rayfOmAj+OBkXzmgKfkuqR857K+5a2QfOato+W4uOS9jXzmgKflvrR85oCn55qEfOeUn+eQhnzntbblgKt85a+45q2i44KBfOe0oOadkHzmirHjgYR85oqx44GLfOaKseOBjXzmirHjgY985oqx44GRfOaKseOBk3zkvZPmtrJ85Lmz6aaWfOaBpeWeonznj43mo5J85Lit44Gg44GXfOS4reWHuuOBl3zlsL985oqc44GEfOaKnOOBkeOBquOBhHzmipzjgZHjgot85oqc44GR44KMfOaOkuS+v3zniq/nj4186Iao44KJfOWMheiMjnzli4Potbd86IacfOaRqee+hXzprZTnvoV85o+J44G+fOaPieOBv3zmj4njgoB85o+J44KBfOa8q+a5lnzjgIfvvZ584pev772efOKXi++9nnzil4/vvZ5844CHfnzil69+fOKXi3584pePfnzjgIfjg4Pjgq/jgrl84pev44OD44Kv44K5fOKXi+ODg+OCr+OCuXzil4/jg4Pjgq/jgrk=', 'base64').toString());

    // 「ネガティブな表現、差別的な表現、政治的に偏った表現を含むコメントをミュートする」のフィルタ正規表現
    private static readonly mute_abusive_discriminatory_prejudiced_comments_pattern = new RegExp(Buffer.from('44CCfOOCouODi+ODl+ODrHzjgqLjgrnjg5p844GC44G7fOOCouODm3zpmL/lkYZ844Kk44Kr44KMfOOBhOOBvuOBhOOBoXzjgqTjg57jgqTjg4F844Kk44Op44Gk44GPfOOCpuOCuHzjgqbjg7zjg6h844Km44OofOOCpuODqOOCr3zjgqbjg7J844GG44KL44Gb44GIfOOCruOCueOCruOCuXzvvbfvvp7vvb3vvbfvvp7vvb1844GN44Gj44Gf44Gt44GIfOOBjeOBo+OBn+OBreOBh3zjgY3jgZ/jga3jgYh844GN44Gf44Gt44GHfOaxmuOBreOBiHzmsZrjga3jgYd844GN44KC44GEfOOCreODouOCpHzjgq3jg6LjgYR844KtL+ODoC/jg4F844Ks44Kk44K4fO+9tu++nu+9su+9vO++nnzjgqzjgqTjgrjjg7N844Ks44KtfOOCq+OCuXzjgq3jg4Pjgrp844GN44Gh44GM44GEfOOCreODgeOCrOOCpHzjgq3jg6Djg4F844GN44KJ44GEfOOCreODqeOCpHzlq4zjgYR8XuiPjCR844Kv44K9fOeznnzjgrfjg4p844K544OG44OefOOBpOOBvuOCieOBqnzjgaTjgb7jgonjgpN844OB44On44OD44OR44OqfOODgeODp+ODs3zljYPjg6fjg7N844Gk44G+44KJ44GqfOOBpOOCk+OBvHzjg4Tjg7Pjg5x844ON44OI44Km44OofOOBq+OBoOOBguOBgnzjg4vjg4B85LqM44OAfO++hu++gO++nnzjg5Hjg7zjg6h844OR44OofOODkeODqOOCr3zjg5Ljg4njgYR844OS44OJ44KkfF7jgbTjg7wkfF7jg5Tjg7wkfOOBtuOBo+OBlXzjg5bjg4PjgrV844G244GV44GEfOODluOCteOCpHzjg5jjgqTjg4jjgrnjg5Tjg7zjg4F844Ob44OifOOBvuOBrOOBkXzjg6Hjgq/jg6l844OQ44KrfOODkeOCr3zjg6DjgqvjgaTjgY986I2S44KJ44GXfOm6u+eUn+OCu+ODoeODs+ODiHzlj7Pnv7x85rGa54mpfOmdoueZveOBj+OBqnzmhbDlronlqaZ85a6z5YWQfOWkluWtl3zlp6blm7186Z+T5Zu9fOmfk+S4rXzpn5Pml6V85Z+65Zyw5aSWfOawl+eLguOBhHzmsJfpgZXjgYR85YiH44Gj44GffOWIh+OBo+OBpnzmsJfmjIHjgaHmgqp86IetfOWxkXzlt6XkvZzlk6F85Zu95Lqk5pat57W2fOWbveexjXzlm73jgavluLDjgox85Zu944G45biw44KMfOW3pue/vHzmrrp86aCDfOmgg+OBl3zpoIPjgZl86aCD44GbfF7lnKh85Zyo5pelfOWcqOaXpeeJueaoqXzlnKjnibnkvJp85Y+C5pS/5qipfOeyvuelnueVsOW4uOiAhXzmrbvjga185rCP44GtfO++gO++i3zmrbnljJV85q2544OSfOatu+WIkXzjgrfjgrHjgqR844GX44GR44GEfOWksemAn3zpmpzlrrN844K544OG44OefOWkp+adseS6nHzmlq3kuqR86YCa5ZCNfOS4remfk3zmnJ3prq585b6055So5belfOWjunzlo7d85aO8fOaXpemfk3zml6XluJ1857KY552AfOWNiuWztnzlj43ml6V85Y+N5rCR5pePfOmmrOm5v3znmbrni4J855m66YGUfOactHzlo7Llm7185b6u5aaZfOS4jeW/q3zkvbXlkIh86ZaT5oqc44GRfO++ke+9uO++ke+9uHzjg6Djgq/jg6Djgq9854Sh6IO9fOa8j+OCiXzmvI/jgox85paH5Y+lfOmdluWbvXzph47pg44=', 'base64').toString());

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
    static parseCommentCommand(comment_mail: string | null | undefined): {
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
