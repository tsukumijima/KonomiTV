<template>
    <div class="series-container">
        <!-- フィルターコントロール -->
        <div class="series-controls">
            <v-btn-toggle v-model="filter_mode" mandatory density="compact" color="primary" class="series-controls__toggle">
                <v-btn value="strict" size="small">
                    <Icon icon="fluent:target-20-regular" width="16px" class="mr-1" />
                    厳格
                </v-btn>
                <v-btn value="relaxed" size="small">
                    <Icon icon="fluent:grid-dots-20-regular" width="16px" class="mr-1" />
                    緩和
                </v-btn>
            </v-btn-toggle>

            <v-checkbox
                v-model="show_other_channels"
                label="他CH含む"
                density="compact"
                hide-details
                color="primary"
                class="series-controls__checkbox"
            ></v-checkbox>
        </div>

        <!-- 現在表示中の情報 -->
        <div class="series-info" v-if="!is_loading && filtered_series.length > 0">
            <span class="series-info__count">
                {{ filtered_series.length }}件のシリーズ番組
            </span>
            <span class="series-info__threshold text-text-darken-1">
                ({{ score_threshold }}点以上)
            </span>
        </div>

        <!-- ローディング -->
        <div v-if="is_loading" class="series-loading">
            <Icon icon="line-md:loading-twotone-loop" width="32px" class="series-loading__icon" />
            <p>シリーズ番組を検索中...</p>
        </div>

        <!-- シリーズ番組リスト -->
        <div v-else-if="filtered_series.length > 0" class="series-list">
            <router-link
                v-for="match in filtered_series"
                :key="match.program.id"
                :to="`/videos/watch/${match.program.id}`"
                class="series-item"
                :class="{
                    'series-item--current': match.program.id === playerStore.recorded_program?.id,
                    'series-item--high-score': match.score >= 90,
                }">

                <!-- サムネイル -->
                <div class="series-item__thumbnail">
                    <img class="series-item__thumbnail-image" loading="lazy" decoding="async"
                        :src="`${Utils.api_base_url}/videos/${match.program.id}/thumbnail`"
                        :alt="match.program.title">
                    <div class="series-item__thumbnail-duration">
                        {{ ProgramUtils.getProgramDuration(match.program) }}
                    </div>
                    <!-- スコアバッジ（デバッグ用） -->
                    <div v-if="show_debug_scores" class="series-item__score-badge"
                         v-ftooltip="`タイトル: ${match.breakdown.title}, 時間: ${match.breakdown.time}, CH: ${match.breakdown.channel}, Meta: ${match.breakdown.metadata}`">
                        {{ match.score }}
                    </div>
                    <!-- 録画状態インジケーター -->
                    <div v-if="match.program.recorded_video.status === 'Recording'"
                         class="series-item__thumbnail-status series-item__thumbnail-status--recording">
                        <div class="series-item__thumbnail-status-dot"></div>
                        録画中
                    </div>
                </div>

                <!-- 情報 -->
                <div class="series-item__info">
                    <div class="series-item__title" v-html="ProgramUtils.decorateProgramInfo(match.program, 'title')"></div>
                    <div class="series-item__meta">
                        <div class="series-item__meta-date">
                            {{ formatDate(match.program.start_time) }}
                        </div>
                        <div class="series-item__meta-channel" v-if="match.program.channel">
                            <div class="series-item__meta-channel-icon">
                                <div class="ch-sprite" :chid="match.program.channel.id">
                                    <img loading="lazy" :src="`${Utils.api_base_url}/channels/${match.program.channel.id}/logo`">
                                </div>
                            </div>
                            <span class="series-item__meta-channel-name">{{ match.program.channel.name }}</span>
                        </div>
                    </div>
                </div>
            </router-link>
        </div>

        <!-- 結果なし -->
        <div v-else class="series-empty">
            <Icon icon="fluent:tv-20-regular" width="48px" class="series-empty__icon" />
            <p class="series-empty__text">シリーズ番組が見つかりません</p>
            <small v-if="filter_mode === 'strict'" class="series-empty__hint">
                「緩和」モードで再度お試しください
            </small>
        </div>

        <!-- APIから追加読み込みボタン -->
        <div v-if="!is_loading && has_more_api_data" class="series-load-more-container">
            <v-btn
                @click="loadMoreFromAPI"
                :loading="is_loading_more"
                variant="text"
                color="primary"
                class="series-load-more">
                <Icon v-if="!is_loading_more" icon="fluent:arrow-download-20-regular" width="18px" class="mr-1" />
                さらに読み込む
            </v-btn>
        </div>
    </div>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent } from 'vue';

import { IRecordedProgram } from '@/services/Videos';
import Videos from '@/services/Videos';
import usePlayerStore from '@/stores/PlayerStore';
import Utils, { dayjs } from '@/utils';
import { ProgramUtils } from '@/utils/ProgramUtils';

/** シリーズマッチング結果 */
interface SeriesMatch {
    program: IRecordedProgram;
    score: number;
    breakdown: {
        title: number;
        time: number;
        channel: number;
        metadata: number;
    };
}

export default defineComponent({
    name: 'Panel-SeriesTab',
    data() {
        return {
            // ユーティリティをテンプレートで使えるように
            Utils: Object.freeze(Utils),
            ProgramUtils: Object.freeze(ProgramUtils),

            // フィルターモード
            filter_mode: 'strict' as 'strict' | 'relaxed',

            // 他チャンネル表示フラグ
            show_other_channels: false,

            // ローディング状態
            is_loading: false,

            // 取得した全番組リスト
            all_programs: [] as IRecordedProgram[],

            // シリーズマッチング結果
            series_matches: [] as SeriesMatch[],

            // API から取得済みのページ数
            fetched_api_pages: 0,

            // API にまだデータがあるか
            has_more_api_data: true,

            // 追加読み込み中
            is_loading_more: false,

            // デバッグ用スコア表示
            show_debug_scores: false,
        };
    },
    computed: {
        ...mapStores(usePlayerStore),

        // スコア閾値
        score_threshold(): number {
            return this.filter_mode === 'strict' ? 70 : 50;
        },

        // フィルタリング済みシリーズ番組
        filtered_series(): SeriesMatch[] {
            const current_program = this.playerStore.recorded_program;
            if (!current_program) return [];

            return this.series_matches
                .filter(match => match.score >= this.score_threshold)
                // 自分自身は除外しない（吉祥物として表示）
                .filter(match => {
                    if (this.show_other_channels) return true;
                    return match.program.channel?.id === current_program.channel?.id;
                })
                .sort((a, b) => {
                    // 放送日時で降順ソート（新しい順）
                    return dayjs(b.program.start_time).unix() - dayjs(a.program.start_time).unix();
                });
        },

    },
    watch: {
        // 番組が変わったら再検索
        'playerStore.recorded_program': {
            handler() {
                this.searchSeriesPrograms();
            },
            immediate: true,
        },
    },
    methods: {

        // シリーズ番組を検索
        async searchSeriesPrograms() {
            let current_program = this.playerStore.recorded_program;

            // playerStore に録画番組情報がない場合は URL から取得
            if (!current_program) {
                const video_id = this.$route.params.video_id;
                if (!video_id) return;

                const fetched_program = await Videos.fetchVideo(parseFloat(video_id as string));
                if (!fetched_program) return;

                // playerStore に保存
                this.playerStore.recorded_program = fetched_program;
                current_program = fetched_program;
            }

            this.is_loading = true;
            this.series_matches = []; // 前回の結果をクリア
            this.all_programs = [];
            this.fetched_api_pages = 0;
            this.has_more_api_data = true;

            try {
                // 最初の2ページ（60件）を取得して評価
                const initial_pages = 2;

                for (let page = 1; page <= initial_pages; page++) {
                    const result = await Videos.fetchVideos('desc', page);
                    if (result && result.recorded_programs.length > 0) {
                        this.all_programs.push(...result.recorded_programs);
                        this.fetched_api_pages = page;
                    } else {
                        this.has_more_api_data = false;
                        break;
                    }
                }

                console.log(`[Series] 現在の番組: ${current_program.title}`);
                console.log(`[Series] 取得した番組数: ${this.all_programs.length}件`);

                // 各番組をスコアリング
                this.series_matches = this.all_programs
                    .map(program => this.calculateSeriesMatch(current_program, program))
                    .filter(match => match.score > 0); // スコア0は除外

                console.log(`[Series] マッチング結果: ${this.series_matches.length}件`);

                // デバッグ: トップ10のスコアを表示
                const top_matches = this.series_matches
                    .sort((a, b) => b.score - a.score)
                    .slice(0, 10);

                console.log('[Series] Top 10 matches:');
                top_matches.forEach((match, index) => {
                    console.log(`${index + 1}. [${match.score}点] ${match.program.title}`);
                    console.log(`   タイトル: ${match.breakdown.title}, 時間: ${match.breakdown.time}, CH: ${match.breakdown.channel}, Meta: ${match.breakdown.metadata}`);
                });

            } catch (error) {
                console.error('Failed to search series programs:', error);
            } finally {
                this.is_loading = false;
            }
        },

        // API からさらに番組を読み込む（一度に5ページ）
        async loadMoreFromAPI() {
            if (!this.has_more_api_data || this.is_loading_more) return;

            const current_program = this.playerStore.recorded_program;
            if (!current_program) return;

            this.is_loading_more = true;

            try {
                const start_page = this.fetched_api_pages + 1;
                const pages_to_load = 5;
                let loaded_count = 0;

                for (let i = 0; i < pages_to_load; i++) {
                    const page = start_page + i;
                    const result = await Videos.fetchVideos('desc', page);

                    if (result && result.recorded_programs.length > 0) {
                        this.all_programs.push(...result.recorded_programs);
                        this.fetched_api_pages = page;
                        loaded_count += result.recorded_programs.length;

                        // 新しい番組をスコアリングして追加
                        const new_matches = result.recorded_programs
                            .map(program => this.calculateSeriesMatch(current_program, program))
                            .filter(match => match.score > 0);

                        this.series_matches.push(...new_matches);
                    } else {
                        // データがなくなったら終了
                        this.has_more_api_data = false;
                        break;
                    }
                }

                console.log(`[Series] ページ${start_page}～${this.fetched_api_pages}を読み込み: +${loaded_count}件`);

                if (!this.has_more_api_data) {
                    console.log('[Series] これ以上のデータはありません');
                }

            } catch (error) {
                console.error('Failed to load more programs:', error);
            } finally {
                this.is_loading_more = false;
            }
        },

        // シリーズマッチングのスコアを計算
        calculateSeriesMatch(current: IRecordedProgram, target: IRecordedProgram): SeriesMatch {
            const title_score = this.calculateTitleScore(current.title, target.title);
            const time_score = this.calculateTimeScore(current, target);
            const channel_score = this.calculateChannelScore(current, target);
            const metadata_score = this.calculateMetadataScore(current, target);

            return {
                program: target,
                score: title_score + time_score + channel_score + metadata_score,
                breakdown: {
                    title: title_score,
                    time: time_score,
                    channel: channel_score,
                    metadata: metadata_score,
                },
            };
        },

        // タイトルマッチングスコア（最大60点）
        calculateTitleScore(current_title: string, target_title: string): number {
            // enclosed_characters を除去
            const clean_current = this.removeEnclosedCharacters(current_title);
            const clean_target = this.removeEnclosedCharacters(target_title);

            // エピソード番号前のベースタイトルを抽出
            const current_base = this.extractBaseTitle(clean_current);
            const target_base = this.extractBaseTitle(clean_target);

            // 完全一致
            if (current_base === target_base && current_base.length > 0) {
                return 60;
            }

            // 文字列類似度計算
            const similarity = this.calculateStringSimilarity(current_base, target_base);
            if (similarity >= 0.9) return 55;
            if (similarity >= 0.8) return 50;
            if (similarity >= 0.7) return 40;

            // キーワードマッチング
            const keywords = this.extractKeywords(current_base);
            if (keywords.length === 0) return 0;

            const match_rate = this.calculateKeywordMatchRate(keywords, target_base);
            if (match_rate >= 0.8) return 35;
            if (match_rate >= 0.6) return 25;
            if (match_rate >= 0.4) return 15;
            if (match_rate >= 0.2) return 8;

            return 0;
        },

        // 時間帯マッチングスコア（最大20点）
        calculateTimeScore(current: IRecordedProgram, target: IRecordedProgram): number {
            const current_time = dayjs(current.start_time);
            const target_time = dayjs(target.start_time);

            // 日付の差分（絶対値）
            const date_diff_days = Math.abs(current_time.diff(target_time, 'day'));

            // 曜日の差分（0-6）
            const day_diff = Math.abs((current_time.day() - target_time.day() + 7) % 7);

            // 時間の差分（分単位）
            const hour_diff = Math.abs(current_time.hour() - target_time.hour());
            const minute_diff = Math.abs(current_time.minute() - target_time.minute());
            const total_minute_diff = hour_diff * 60 + minute_diff;

            // 連続放送パターン（毎日放送、例：朝ドラ、帯番組）
            // 日付差が1-7日以内で時間がほぼ同じ
            if (date_diff_days >= 1 && date_diff_days <= 7) {
                if (total_minute_diff <= 5) return 20;   // ほぼ同時刻
                if (total_minute_diff <= 15) return 18;  // 15分以内
                if (total_minute_diff <= 30) return 16;  // 30分以内
            }

            // 週間番組パターン（同じ曜日・時間、7日間隔の可能性高い）
            if (day_diff === 0) {
                if (total_minute_diff <= 5) return 20;
                if (total_minute_diff <= 15) return 18;
                if (total_minute_diff <= 30) return 15;
                if (total_minute_diff <= 60) return 10;
            }

            // それ以外で時間が近い場合（日間番組の可能性）
            if (total_minute_diff <= 15) return 12;
            if (total_minute_diff <= 30) return 8;
            if (total_minute_diff <= 60) return 5;

            return 0;
        },

        // チャンネルマッチングスコア（最大10点）
        calculateChannelScore(current: IRecordedProgram, target: IRecordedProgram): number {
            if (!current.channel || !target.channel) return 0;

            // 同一チャンネル
            if (current.channel.id === target.channel.id) {
                return 10;
            }

            // 同一ネットワーク系列
            if (current.channel.network_id && target.channel.network_id &&
                current.channel.network_id === target.channel.network_id) {
                return 6;
            }

            // チャンネルタイプが同じ（地上波同士、BS同士など）
            const current_type = this.getChannelType(current.channel.channel_number);
            const target_type = this.getChannelType(target.channel.channel_number);
            if (current_type === target_type) {
                return 3;
            }

            return 0;
        },

        // メタデータマッチングスコア（最大10点）
        calculateMetadataScore(current: IRecordedProgram, target: IRecordedProgram): number {
            let score = 0;

            // EPGのシリーズID一致（最重要）
            if (current.series_id && current.series_id === target.series_id) {
                return 10;
            }

            // ジャンル一致
            if (current.genres.length > 0 && target.genres.length > 0) {
                // major と middle が完全一致
                const exact_match = current.genres.some(g1 =>
                    target.genres.some(g2 => g1.major === g2.major && g1.middle === g2.middle)
                );

                if (exact_match) {
                    // 連続物ジャンル（アニメ、ドラマ等）は高配点
                    const series_genres = ['アニメ・特撮', 'ドラマ', '情報・ワイドショー'];
                    const is_series_genre = current.genres.some(g => series_genres.includes(g.major));
                    score += is_series_genre ? 5 : 4;
                } else {
                    // major のみ一致
                    const major_match = current.genres.some(g1 =>
                        target.genres.some(g2 => g1.major === g2.major)
                    );
                    if (major_match) {
                        score += 2;
                    }
                }
            }

            // 番組の長さが近い（±5分）
            const duration_diff = Math.abs(current.duration - target.duration);
            if (duration_diff <= 300) {
                score += 3;
            } else if (duration_diff <= 600) {
                score += 2;
            } else if (duration_diff <= 900) {
                score += 1;
            }

            return Math.min(score, 10);
        },

        // enclosed_characters を除去
        removeEnclosedCharacters(title: string): string {
            const patterns = ProgramUtils.getEnclosedCharactersRemovalPatterns();
            let result = title;
            for (const pattern of patterns) {
                result = result.replace(pattern, '');
            }
            return result.trim();
        },

        // エピソード番号前のベースタイトルを抽出
        extractBaseTitle(title: string): string {
            let base = title;

            // まず副標題を除去（「」『』の中身を削除）
            base = base.replace(/[「『].*?[」』]/g, '').trim();

            // エピソード番号パターンを除去
            const patterns = [
                /\(\d+\)/,       // xxx(1)
                /#\d+/,          // xxx#1
                /第\d+話/,       // xxx第1話
                /第\d+回/,       // xxx第1回
                /【\d+】/,       // xxx【1】
                /\s+\d+\s*$/,    // xxx 1 (末尾の数字)
            ];

            for (const pattern of patterns) {
                const match = base.match(pattern);
                if (match) {
                    base = base.substring(0, match.index).trim();
                    break;
                }
            }

            return base;
        },

        // エピソード番号を抽出
        extractEpisodeNumber(title: string): number | null {
            const patterns = [
                /#(\d+)/,
                /\((\d+)\)/,
                /第(\d+)話/,
                /第(\d+)回/,
                /【(\d+)】/,
            ];

            for (const pattern of patterns) {
                const match = title.match(pattern);
                if (match && match[1]) {
                    return parseInt(match[1], 10);
                }
            }

            return null;
        },

        // キーワードを抽出（2文字以上の単語）
        extractKeywords(title: string): string[] {
            // スペースで分割
            const words = title.split(/[\s\u3000]+/).filter(w => w.length >= 2);
            return words;
        },

        // キーワードマッチ率を計算
        calculateKeywordMatchRate(keywords: string[], target: string): number {
            if (keywords.length === 0) return 0;

            const matched = keywords.filter(keyword => target.includes(keyword)).length;
            return matched / keywords.length;
        },

        // 文字列類似度を計算（簡易版）
        calculateStringSimilarity(str1: string, str2: string): number {
            if (str1 === str2) return 1;
            if (str1.length === 0 || str2.length === 0) return 0;

            // 共通部分の長さ / 長い方の長さ
            const longer = str1.length > str2.length ? str1 : str2;
            const shorter = str1.length > str2.length ? str2 : str1;

            if (longer.includes(shorter)) {
                return shorter.length / longer.length;
            }

            // 共通文字数をカウント
            const chars1 = new Set(str1);
            const chars2 = new Set(str2);
            const common = [...chars1].filter(c => chars2.has(c)).length;
            const total = Math.max(chars1.size, chars2.size);

            return common / total;
        },

        // チャンネルタイプを取得
        getChannelType(channel_number: string): string {
            const num = parseInt(channel_number);
            if (num >= 1 && num <= 12) return 'terrestrial'; // 地上波
            if (num >= 101 && num <= 999) return 'bs'; // BS
            if (num >= 1000) return 'cs'; // CS
            return 'other';
        },

        // 日付をフォーマット
        formatDate(date_string: string): string {
            const date = dayjs(date_string);
            const now = dayjs();

            // 今日
            if (date.isSame(now, 'day')) {
                return `今日 ${date.format('HH:mm')}`;
            }

            // 昨日
            if (date.isSame(now.subtract(1, 'day'), 'day')) {
                return `昨日 ${date.format('HH:mm')}`;
            }

            // 今週
            if (date.isSame(now, 'week')) {
                const day_names = ['日', '月', '火', '水', '木', '金', '土'];
                return `${day_names[date.day()]}曜 ${date.format('HH:mm')}`;
            }

            // それ以前
            return date.format('M/D HH:mm');
        },
    }
});

</script>
<style lang="scss" scoped>

.series-container {
    display: flex;
    flex-direction: column;
    padding-left: 16px;
    padding-right: 16px;
    overflow-y: auto;
    @include tablet-vertical {
        margin-top: 20px;
        padding-left: 24px;
        padding-right: 24px;
    }
    @include smartphone-horizontal {
        margin-top: 12px;
    }
    @include smartphone-vertical {
        margin-top: 14px;
    }
}

.series-controls {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    @include smartphone-vertical {
        flex-direction: column;
        align-items: stretch;
        gap: 8px;
    }

    &__toggle {
        flex-shrink: 0;
    }

    &__checkbox {
        margin-left: auto;
        flex-shrink: 0;
        @include smartphone-vertical {
            margin-left: 0;
        }
    }
}

.series-info {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    font-size: 13px;
    color: rgb(var(--v-theme-text-darken-1));

    &__count {
        font-weight: 600;
        color: rgb(var(--v-theme-text));
    }

    &__threshold {
        font-size: 12px;
    }
}

.series-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 48px 24px;
    color: rgb(var(--v-theme-text-darken-1));

    &__icon {
        margin-bottom: 12px;
        color: rgb(var(--v-theme-primary));
    }

    p {
        margin: 0;
        font-size: 14px;
    }
}

.series-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.series-item {
    display: flex;
    gap: 12px;
    padding: 10px;
    border-radius: 6px;
    background: rgb(var(--v-theme-background-lighten-1));
    transition: background-color 0.15s, transform 0.15s;
    text-decoration: none;
    color: rgb(var(--v-theme-text));
    cursor: pointer;
    user-select: none;

    &:hover {
        background: rgb(var(--v-theme-background-lighten-2));
        transform: translateX(2px);
    }

    &--current {
        background: rgba(var(--v-theme-primary), 0.12);
        border-left: 3px solid rgb(var(--v-theme-primary));
        padding-left: 7px;

        &:hover {
            background: rgba(var(--v-theme-primary), 0.18);
        }
    }

    &--high-score {
        border-left: 3px solid rgb(var(--v-theme-primary));
        padding-left: 7px;
    }

    &__thumbnail {
        position: relative;
        width: 120px;
        aspect-ratio: 16 / 9;
        flex-shrink: 0;
        border-radius: 4px;
        overflow: hidden;
        background: rgb(var(--v-theme-background));
        @include smartphone-vertical {
            width: 100px;
        }

        &-image {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        &-duration {
            position: absolute;
            right: 4px;
            bottom: 4px;
            padding: 2px 4px;
            border-radius: 2px;
            background: rgba(0, 0, 0, 0.75);
            color: #fff;
            font-size: 10px;
            line-height: 1.2;
        }

        &-status {
            position: absolute;
            top: 4px;
            left: 4px;
            display: flex;
            align-items: center;
            gap: 3px;
            padding: 3px 6px;
            border-radius: 3px;
            font-size: 10px;
            line-height: 1;
            font-weight: 600;

            &--recording {
                background: rgba(244, 67, 54, 0.9);
                color: #fff;
            }

            &-dot {
                width: 6px;
                height: 6px;
                border-radius: 50%;
                background: #fff;
                animation: recording-pulse 1.5s ease-in-out infinite;
            }
        }
    }

    &__score-badge {
        position: absolute;
        top: 4px;
        right: 4px;
        padding: 3px 6px;
        border-radius: 3px;
        background: rgba(0, 0, 0, 0.8);
        color: #4caf50;
        font-size: 11px;
        font-weight: 700;
        line-height: 1;
    }

    &__info {
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 6px;
        flex: 1;
        min-width: 0;
    }

    &__title {
        font-size: 13.5px;
        font-weight: 600;
        line-height: 1.4;
        overflow: hidden;
        display: -webkit-box;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
        line-clamp: 2;
        @include smartphone-vertical {
            font-size: 13px;
        }
    }

    &__meta {
        display: flex;
        flex-direction: column;
        gap: 4px;
        font-size: 11.5px;
        color: rgb(var(--v-theme-text-darken-1));

        &-date {
            font-weight: 500;
        }

        &-channel {
            display: flex;
            align-items: center;
            gap: 6px;

            &-icon {
                display: inline-block;
                flex-shrink: 0;
                --ch-sprite-width: 32;
                --ch-sprite-height: 18;
                --ch-sprite-border-radius: 2;
                width: calc(var(--ch-sprite-width) * 1px);
                height: calc(var(--ch-sprite-height) * 1px);
                border-radius: calc(var(--ch-sprite-border-radius) * 1px);
                background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
                overflow: hidden;

                .ch-sprite {
                    width: 100%;
                    height: 100%;

                    img {
                        width: 100%;
                        height: 100%;
                        object-fit: cover;
                    }
                }
            }

            &-name {
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
        }
    }
}

.series-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 48px 24px;
    color: rgb(var(--v-theme-text-darken-1));
    text-align: center;

    &__icon {
        margin-bottom: 16px;
        opacity: 0.5;
    }

    &__text {
        margin: 0 0 8px 0;
        font-size: 14px;
        font-weight: 600;
    }

    &__hint {
        font-size: 12px;
        opacity: 0.8;
    }
}

.series-load-more-container {
    display: flex;
    justify-content: center;
    margin-top: 16px;
    padding-bottom: 8px;
}

@keyframes recording-pulse {
    0%, 100% {
        opacity: 1;
    }
    50% {
        opacity: 0.3;
    }
}

</style>
