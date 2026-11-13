
import { defineStore } from 'pinia';
import { ref } from 'vue';

import Programs, { IProgram, IToruCount } from '@/services/Programs';
import { dayjs } from '@/utils';


/**
 * 番組リストの並び順 (放送時間順 / 予約数順)
 */
export type ProgramSortOrder = 'asc' | 'toru';

/**
 * 予約数ランキングを絞り込むチャンネルタイプ ('All' は、すべての放送波の番組を合わせた総合ランキング)
 */
export type ToruRankingChannelType = 'All' | 'GR' | 'BS' | 'CS';

/**
 * 予約数ランキングを絞り込めるジャンル (番組情報のジャンルの大分類) と、絞り込みの選択欄での表示名
 * 録画予約の多いジャンルだけを、予約数の多い順に並べている
 * 並び順は、2026/11 時点の関東の1週間分の番組について、ジャンルごとに上位 20 番組のトル数の平均を比べて決めた
 */
export const TORU_RANKING_GENRES = [
    { title: 'アニメ', value: 'アニメ・特撮' },
    { title: 'バラエティ', value: 'バラエティ' },
    { title: 'ドラマ', value: 'ドラマ' },
    { title: 'ドキュメンタリー', value: 'ドキュメンタリー・教養' },
    { title: 'スポーツ', value: 'スポーツ' },
    { title: '音楽', value: '音楽' },
    { title: '映画', value: '映画' },
] as const;
export type ToruRankingGenre = typeof TORU_RANKING_GENRES[number]['value'];

/**
 * 予約数ランキングの絞り込み (チャンネルタイプとジャンルのどちらか一方で絞り込む)
 */
export type ToruRankingFilter = ToruRankingChannelType | ToruRankingGenre;


/**
 * 番組ごとのトル数 (torne の利用者がその番組を録画予約している数) を管理するストア
 * 画面上では「予約数」として、番組表・番組リスト・録画予約などの番組情報に添えて表示する
 */
const useToruCountStore = defineStore('toruCount', () => {

    // 番組 ID をキーにした、番組ごとのトル数
    const toruCounts = ref<Record<string, IToruCount>>({});

    /**
     * サーバーから番組ごとのトル数を取得し、保持しているトル数を更新する
     */
    const update = async (): Promise<void> => {
        const result = await Programs.fetchToruCounts();
        // 取得に失敗した場合は、前回取得したトル数を引き続き表示する
        if (result !== null) {
            toruCounts.value = result;
        }
    };

    /**
     * 番組のトル数を取得する
     * @param program_id 番組 ID (放送休止中などで番組がない場合は null)
     * @returns トル数 (番組がない場合や、トル数を取得できていない番組の場合は null)
     */
    const getToruCount = (program_id: string | null): IToruCount | null => {
        if (program_id === null) {
            return null;
        }
        return toruCounts.value[program_id] ?? null;
    };

    /**
     * 番組のトル数の多さを、実況勢いと同じ名前の段階で取得する (トル数を表示するときの色分けに使う)
     * @param program_id 番組 ID (放送休止中などで番組がない場合は null)
     * @returns トル数の多さの段階
     */
    const getToruCountLevel = (program_id: string | null): 'normal' | 'many' | 'so-many' | 'festival' => {
        const toruCount = getToruCount(program_id);
        if (toruCount === null || toruCount.highlight_base === null) {
            return 'normal';
        }

        // トル数が基準値の何倍かで段階を決める
        // 色が濃い段階ほど珍しくなるよう、基準値の3倍・6倍・12倍を境目にしている
        // 関東の地デジ (基準値は 850 前後) では、およそ 2,500・5,000・10,000 トルが境目になり、1週間の番組のうち 40・3・1 件ほどが該当する
        // トル数は地域によって桁が異なる (地デジで最も多い番組が、関東では1万を超え、数十にとどまる地域もある) ため、
        // 境目は固定のトル数ではなく、サーバーが放送波ごとの分布から算出した基準値の倍率で決める
        const ratio = toruCount.count / toruCount.highlight_base;
        if (ratio >= 12) {
            return 'festival';
        } else if (ratio >= 6) {
            return 'so-many';
        } else if (ratio >= 3) {
            return 'many';
        }
        return 'normal';
    };

    /**
     * 番組を含む項目のリストを、指定された並び順に並べ替えた新しいリストを返す
     * @param items 並べ替える項目のリスト
     * @param getProgram 項目から番組情報を取り出す関数
     * @param order 並び順
     * @returns 並べ替えた項目のリスト
     */
    const sortPrograms = <T>(
        items: readonly T[],
        getProgram: (item: T) => Pick<IProgram, 'id' | 'start_time'>,
        order: ProgramSortOrder,
    ): T[] => {
        return items.map((item) => {
            const program = getProgram(item);
            // 予約数順では、トル数を取得できていない番組を 0 トルの番組より後ろに並べる
            let ratio = -1;
            let count = -1;
            if (order === 'toru') {
                const toruCount = toruCounts.value[program.id];
                if (toruCount !== undefined) {
                    // 地デジのトル数はその地域の利用者だけの数で、BS・CS のトル数は全国の合計とみられるため、トル数そのものは放送波をまたいで比較できない
                    // 予約数ランキングと同じく、放送波ごとの基準値に対する倍率で並べる (色分けも同じ倍率で決まるため、並び順と色が食い違わない)
                    ratio = toruCount.highlight_base !== null ? toruCount.count / toruCount.highlight_base : 0;
                    count = toruCount.count;
                }
            }
            return { item, ratio, count, startTime: dayjs(program.start_time).valueOf() };
        }).sort((first, second) => {
            // 倍率の大きい順に並べ、倍率が同じ場合はトル数の多い順に、トル数も同じ場合 (放送時間順ではすべての項目が該当する) は放送開始時刻の早い順に並べる
            return second.ratio - first.ratio || second.count - first.count || first.startTime - second.startTime;
        }).map(({ item }) => item);
    };

    return { toruCounts, update, getToruCount, getToruCountLevel, sortPrograms };
});

export default useToruCountStore;
