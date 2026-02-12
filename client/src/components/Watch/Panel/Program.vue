<template>
    <div class="program-container">
        <section class="program-broadcaster">
            <img class="program-broadcaster__icon" :src="`${Utils.api_base_url}/channels/${channelsStore.channel.current.id}/logo`">
            <div class="program-broadcaster__number">Ch: {{channelsStore.channel.current.channel_number}}</div>
            <div class="program-broadcaster__name">{{channelsStore.channel.current.name}}</div>
        </section>
        <section class="program-info">
            <h1 class="program-info__title"
                v-html="ProgramUtils.decorateProgramInfo(channelsStore.channel.current.program_present, 'title')">
            </h1>
            <div class="program-info__time">
                {{ProgramUtils.getProgramTime(channelsStore.channel.current.program_present)}}
            </div>
            <div class="program-info__description"
                v-html="ProgramUtils.decorateProgramInfo(channelsStore.channel.current.program_present, 'description')">
            </div>
            <div class="program-info__genre-container" v-if="channelsStore.channel.current.program_present?.genres && channelsStore.channel.current.program_present.genres.length > 0">
                <div class="program-info__genre" :key="genre_index"
                    v-for="(genre, genre_index) in channelsStore.channel.current.program_present.genres">
                    {{genre.major}} / {{genre.middle}}
                </div>
            </div>
            <div class="program-info__next">
                <span class="program-info__next-decorate">NEXT</span>
                <Icon class="program-info__next-icon" icon="fluent:fast-forward-20-filled" width="16px" />
            </div>
            <span class="program-info__next-title"
                v-html="ProgramUtils.decorateProgramInfo(channelsStore.channel.current.program_following, 'title')">
            </span>
            <div class="program-info__next-time">
                {{ProgramUtils.getProgramTime(channelsStore.channel.current.program_following)}}
            </div>
            <div class="program-info__status">
                <div class="program-info__status-force"
                    :class="`program-info__status-force--${ChannelUtils.getChannelForceType(channelsStore.channel.current.jikkyo_force)}`">
                    <Icon icon="fa-solid:fire-alt" height="14px" />
                    <span class="ml-2">勢い:</span>
                    <span class="ml-2">{{channelsStore.channel.current.jikkyo_force ?? '--'}} コメ/分</span>
                </div>
                <div class="program-info__status-viewers ml-5">
                    <Icon icon="fa-solid:eye" height="14px" />
                    <span class="ml-2">視聴数:</span>
                    <span class="ml-1">{{channelsStore.channel.current.viewer_count}}</span>
                </div>
            </div>
            <!-- 録画開始ボタン / 録画状態表示 -->
            <div v-ripple="isRecordButtonClickable"
                class="program-info__record-button"
                :class="{
                    'program-info__record-button--disabled': !isEDCBBackend,
                    'program-info__record-button--preparing': isPreparing,
                }"
                @click="handleRecordButtonClick">
                <!-- 録画中: 静止した赤いドット + テキスト (クリックで停止ダイアログを表示) -->
                <template v-if="isRecording">
                    <div class="program-info__recording-dot"></div>
                    <span style="margin-left: 6px;">録画中</span>
                </template>
                <!-- 録画開始中: 予約投入済みだが録画がまだ開始されていない -->
                <template v-else-if="isPreparing">
                    <Icon icon="fluent:record-16-regular" width="17px" height="17px"
                        style="color: #EF5350; margin-bottom: -1px" />
                    <span style="margin-left: 5px;">録画開始中...</span>
                </template>
                <!-- 未予約 (EDCB バックエンド): クリックで録画開始 -->
                <template v-else-if="isEDCBBackend">
                    <Icon icon="fluent:record-16-regular" width="17px" height="17px"
                        style="color: #EF5350; margin-bottom: -1px" />
                    <span style="margin-left: 5px;">録画開始</span>
                </template>
                <!-- Mirakurun バックエンド: グレーアウト表示 -->
                <template v-else>
                    <Icon icon="fluent:record-16-regular" width="17px" height="17px" style="margin-bottom: -1px" />
                    <span style="margin-left: 5px;">録画開始 (EDCB 専用)</span>
                </template>
            </div>
        </section>
        <!-- 録画停止確認ダイアログ -->
        <v-dialog v-model="show_stop_recording_dialog" max-width="715">
            <v-card>
                <v-card-title class="d-flex justify-center pt-6 font-weight-bold">
                    録画を停止しますか？
                </v-card-title>
                <v-card-text class="pt-2 pb-0">
                    <!-- 予約の基本情報 -->
                    <div v-if="reservation" class="mb-4">
                        <div class="text-h6 text-text mb-2"
                            v-html="ProgramUtils.decorateProgramInfo(reservation.program, 'title')"></div>
                        <div class="text-body-2 text-text-darken-1">
                            {{ProgramUtils.getProgramTime(reservation.program)}}
                        </div>
                    </div>
                    <!-- 録画中の警告バナー -->
                    <div class="warning-banner warning-banner--recording">
                        <Icon icon="fluent:warning-16-filled" class="warning-banner__icon" />
                        <span class="warning-banner__text">
                            この番組は現在録画中です。<br>
                            録画を停止すると、現在までの録画ファイルは残りますが、残りの期間の録画は中断されます。
                        </span>
                    </div>
                </v-card-text>
                <v-card-actions class="pt-4 px-6 pb-6">
                    <v-spacer></v-spacer>
                    <v-btn color="text" variant="text" @click="show_stop_recording_dialog = false">
                        <Icon icon="fluent:dismiss-20-regular" width="18px" height="18px" />
                        <span class="ml-1">キャンセル</span>
                    </v-btn>
                    <v-btn class="px-3" color="error" variant="flat" @click="confirmStopRecording">
                        <Icon icon="fluent:delete-20-regular" width="18px" height="18px" />
                        <span class="ml-1">録画を停止</span>
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
        <section class="program-detail-container">
            <div class="program-detail" :key="detail_heading"
                v-for="(detail_text, detail_heading) in channelsStore.channel.current.program_present?.detail ?? {}">
                <h2 class="program-detail__heading">{{detail_heading}}</h2>
                <div class="program-detail__text" v-html="Utils.URLtoLink(detail_text)"></div>
            </div>
        </section>
    </div>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent } from 'vue';

import Message from '@/message';
import Reservations, { IRecordSettingsDefault, IReservation } from '@/services/Reservations';
import useChannelsStore from '@/stores/ChannelsStore';
import useServerSettingsStore from '@/stores/ServerSettingsStore';
import Utils, { ChannelUtils, ProgramUtils } from '@/utils';

export default defineComponent({
    name: 'Panel-ProgramTab',
    data() {
        return {
            // ユーティリティをテンプレートで使えるように
            Utils: Object.freeze(Utils),
            ChannelUtils: Object.freeze(ChannelUtils),
            ProgramUtils: Object.freeze(ProgramUtils),

            // 現在の番組に対する録画予約情報
            reservation: null as IReservation | null,
            // 録画開始ボタンの処理中かどうか
            is_starting_recording: false,
            // 録画停止確認ダイアログの表示状態
            show_stop_recording_dialog: false,
            // 録画開始中 → 録画中の遷移を検知するためのポーリングタイマー ID (3秒間隔)
            polling_timer_id: null as ReturnType<typeof setInterval> | null,
            // 外部からの予約追加や番組変更を検知するためのバックグラウンドポーリングタイマー ID (60秒間隔)
            background_polling_timer_id: null as ReturnType<typeof setInterval> | null,
            // バックグラウンドポーリングの実行中かどうか
            // API 応答遅延時にポーリング処理が多重実行されるのを防ぐ
            is_background_polling_in_progress: false,
            // 録画予約状態取得の最新リクエストを識別するトークン
            // 非同期通信の完了順が前後しても、最新の番組状態だけを反映するために使う
            reservation_status_request_token: 0,
        };
    },
    computed: {
        ...mapStores(useChannelsStore, useServerSettingsStore),

        // EDCB バックエンドかどうか
        isEDCBBackend(): boolean {
            return this.serverSettingsStore.server_settings.general.backend === 'EDCB';
        },

        // 現在の番組が録画中かどうか
        isRecording(): boolean {
            return this.reservation?.is_recording_in_progress === true;
        },

        // 現在の番組に録画予約があるかどうか（録画中を含む）
        hasReservation(): boolean {
            return this.reservation !== null;
        },

        // 録画開始中かどうか（予約投入済み + まだ録画が開始されていない）
        isPreparing(): boolean {
            return this.hasReservation === true && this.isRecording === false;
        },

        // 録画ボタンがクリック可能かどうか（v-ripple エフェクトの表示判定に使用）
        // 録画中（停止ダイアログを開く）または未予約 (EDCB バックエンド) の場合のみクリック可能
        isRecordButtonClickable(): boolean {
            return this.isRecording || (this.isEDCBBackend && !this.hasReservation && !this.is_starting_recording);
        },

        // 録画予約状態チェック用の現在番組 ID
        // program オブジェクト全体を監視すると同一番組内の微小更新でも watch が発火し API が過剰呼び出しされるため、
        // 予約照合に必要な最小単位である番組 ID のみに絞って監視する
        currentProgramPresentIdForReservationCheck(): string | null {
            return this.channelsStore.current_program_present?.id ?? null;
        },
    },
    watch: {
        // PSI/SI デコード結果のうち、番組 ID が変化した場合のみ監視する
        // 同一番組内での更新で毎秒 API が発火しないようにしつつ、番組切り替わり時の再チェックは維持する
        currentProgramPresentIdForReservationCheck() {
            this.invalidateReservationStatusRequest();
            this.stopPolling();
            // PSI/SI デコード結果が更新されたので、より正確な番組 ID で予約状態を再チェック
            this.checkReservationStatus();
        },
        // チャンネル切替時にポーリング停止・予約情報リセット後、新チャンネルの状態を即座にチェック
        'channelsStore.channel.current.id'() {
            this.invalidateReservationStatusRequest();
            this.stopPolling();
            this.reservation = null;
            // 新しいチャンネルの録画予約状態を channels API のデータで即座にチェック
            this.checkReservationStatus();
            // バックグラウンドポーリングをリスタート
            this.startBackgroundPolling();
        },
    },
    methods: {
        /**
         * 現在の番組の録画予約状態をチェックする
         * 全予約を取得し、現在放送中の番組と一致する予約を探す
         */
        async checkReservationStatus(): Promise<boolean> {
            // channelsStore.channel.current.program_present は PSI/SI 取得済みならリアルタイムの event_id を含み、
            // 未取得なら channels API のデータ (DB スナップショット) が使用される
            const programPresent = this.channelsStore.channel.current.program_present;
            if (this.isEDCBBackend !== true || programPresent === null) {
                this.reservation = null;
                return false;
            }
            const requestToken = ++this.reservation_status_request_token;
            try {
                const result = await Reservations.fetchReservations();

                // 自分より新しいリクエストが既に開始されている場合は、古い結果を破棄する
                if (requestToken !== this.reservation_status_request_token) {
                    return false;
                }

                // 通信待ちの間に番組が切り替わった場合は、古い番組に対する結果を破棄する
                const latestProgramPresent = this.channelsStore.channel.current.program_present;
                if (latestProgramPresent === null || latestProgramPresent.id !== programPresent.id) {
                    return false;
                }

                // 通信待ちの間に EDCB 以外へ切り替わった場合も結果を破棄する
                if (this.isEDCBBackend !== true) {
                    this.reservation = null;
                    return false;
                }

                if (result === null) {
                    return false;
                }
                // 現在の番組 ID (PSI/SI 由来のリアルタイム event_id を含む) と一致する予約を探す
                const matchingReservation = result.reservations.find(
                    (reservation) => reservation.program.id === programPresent.id
                );
                this.reservation = matchingReservation ?? null;
                return true;
            } catch {
                return false;
            }
        },

        /**
         * 録画ボタンクリック時のハンドラー
         * 状態に応じて録画開始・録画停止確認ダイアログ表示を振り分ける
         */
        handleRecordButtonClick(): void {
            // 録画中の場合は停止確認ダイアログを表示
            if (this.isRecording === true) {
                this.show_stop_recording_dialog = true;
                return;
            }
            // 録画開始中の場合は何もしない（ポーリング中のため操作不可）
            if (this.isPreparing === true) {
                return;
            }
            // Mirakurun バックエンドの場合は警告を表示
            if (this.isEDCBBackend !== true) {
                Message.warning('録画予約機能は EDCB バックエンド選択時のみ利用できます。');
                return;
            }
            // 未予約の場合は録画を開始
            this.startRecording();
        },

        /**
         * 現在の番組の録画を開始する（録画予約を追加する）
         * 予約追加後、録画が実際に開始されるまでポーリングで監視する
         */
        async startRecording(): Promise<void> {
            // 処理中の場合は何もしない
            if (this.is_starting_recording === true) {
                return;
            }
            // channels API のデータ、または PSI/SI デコード結果が反映された番組情報を使用
            const programPresent = this.channelsStore.channel.current.program_present;
            if (programPresent === null) {
                return;
            }
            this.is_starting_recording = true;
            try {
                const result = await Reservations.addReservation(programPresent.id, IRecordSettingsDefault);
                // 予約状態を再チェックして UI を更新
                // 予約追加に失敗した場合も、外部で既に予約済みの可能性があるため状態を再取得する
                await this.checkReservationStatus();
                if (result === true) {
                    Message.show('録画予約を追加しました。録画を開始しています...');
                    // まだ録画が開始されていない場合はポーリングを開始し、録画開始を待機する
                    if (this.isRecording !== true) {
                        this.startPolling();
                    }
                }
            } finally {
                this.is_starting_recording = false;
            }
        },

        /**
         * 録画停止確認ダイアログで「録画を停止」を押した際の処理
         * 予約を削除して録画を中断する
         */
        async confirmStopRecording(): Promise<void> {
            this.show_stop_recording_dialog = false;
            if (this.reservation === null) {
                return;
            }
            const result = await Reservations.deleteReservation(this.reservation.id);
            if (result === true) {
                Message.show('録画を停止しました。');
                this.stopPolling();
                // 予約状態を再チェックして UI を更新
                await this.checkReservationStatus();
            }
        },

        /**
         * 録画開始中 → 録画中の遷移を検知するためのポーリングを開始する
         * 3秒間隔で録画予約状態をチェックし、録画が開始されたらポーリングを自動停止する
         */
        startPolling(): void {
            this.stopPolling();
            this.polling_timer_id = setInterval(async () => {
                const isReservationStatusChecked = await this.checkReservationStatus();
                // 通信エラー時は一時的な失敗の可能性があるため、ポーリングを継続して再試行する
                if (isReservationStatusChecked !== true) {
                    return;
                }
                // 録画が開始された場合はポーリングを停止
                if (this.isRecording === true) {
                    // 視聴中なので success などの色のついたメッセージは使わず、あえて控えめに表示する
                    Message.show('録画を開始しました。');
                    this.stopPolling();
                    return;
                }
                // 予約が見つからなくなった場合は、成功扱いせずにポーリングのみ停止する
                if (this.hasReservation === false) {
                    this.stopPolling();
                }
            }, 3000);
        },

        /**
         * 録画予約状態のポーリングを停止する
         */
        stopPolling(): void {
            if (this.polling_timer_id !== null) {
                clearInterval(this.polling_timer_id);
                this.polling_timer_id = null;
            }
        },

        /**
         * 外部からの予約追加や番組変更を検知するためのバックグラウンドポーリングを開始する
         * 60秒間隔で録画予約状態をチェックし、外部から追加された予約や録画状態の変化を反映する
         */
        startBackgroundPolling(): void {
            // Mirakurun バックエンドの場合は録画予約 API が使えないためポーリング不要
            if (this.isEDCBBackend !== true) {
                return;
            }
            this.stopBackgroundPolling();
            this.background_polling_timer_id = setInterval(async () => {
                // 録画開始待ちの短周期ポーリング中は、重複して全予約取得を行わない
                if (this.polling_timer_id !== null || this.is_starting_recording === true) {
                    return;
                }
                // API 応答が遅い環境では次周期が先に到来して多重実行されるため、実行中はスキップする
                if (this.is_background_polling_in_progress === true) {
                    return;
                }

                this.is_background_polling_in_progress = true;
                try {
                    await this.checkReservationStatus();
                } finally {
                    this.is_background_polling_in_progress = false;
                }
            }, 60000);
        },

        /**
         * バックグラウンドポーリングを停止する
         */
        stopBackgroundPolling(): void {
            if (this.background_polling_timer_id !== null) {
                clearInterval(this.background_polling_timer_id);
                this.background_polling_timer_id = null;
            }
            this.is_background_polling_in_progress = false;
        },

        /**
         * 録画予約状態取得リクエストを無効化する
         * チャンネル切替・番組切替などで進行中リクエストの結果を破棄したいときに使う
         */
        invalidateReservationStatusRequest(): void {
            this.reservation_status_request_token++;
        },
    },
    mounted() {
        // 初期状態の録画予約状態をチェックしバックグラウンドポーリングを開始
        // PSI/SI デコード結果が未取得でも channels API のデータで仮チェックを行い、
        // 既に録画中の番組であれば初回表示時から「録画中」と表示する
        this.checkReservationStatus();
        this.startBackgroundPolling();
    },
    beforeUnmount() {
        // コンポーネント破棄時にポーリングを停止
        this.invalidateReservationStatusRequest();
        this.stopPolling();
        this.stopBackgroundPolling();
    },
});

</script>
<style lang="scss" scoped>

.program-container {
    padding-left: 16px;
    padding-right: 16px;
    overflow-y: auto;
    @include tablet-vertical {
        padding-left: 24px;
        padding-right: 24px;
    }

    .program-broadcaster {
        display: none;
        align-items: center;
        min-width: 0;
        @include tablet-vertical {
            display: flex;
            margin-top: 20px;
        }
        @include smartphone-horizontal {
            display: flex;
            margin-top: 16px;
        }
        @include smartphone-vertical {
            display: flex;
            margin-top: 16px;
        }

        &__icon {
            display: inline-block;
            flex-shrink: 0;
            width: 43px;
            height: 24px;
            border-radius: 3px;
            background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
            object-fit: cover;
            user-select: none;
            @include tablet-vertical {
                width: 58px;
                height: 32px;
            }
            @include smartphone-horizontal {
                width: 42px;
                height: 23.5px;
            }
            @include smartphone-vertical {
                width: 58px;
                height: 32px;
            }
        }

        &__number {
            flex-shrink: 0;
            margin-left: 12px;
            font-size: 16.5px;
            @include tablet-vertical {
                margin-left: 16px;
                font-size: 19px;
            }
        }

        &__name {
            margin-left: 5px;
            font-size: 16.5px;
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
            @include tablet-vertical {
                margin-left: 8px;
                font-size: 19px;
            }
            @include smartphone-vertical {
                font-size: 18px;
            }
        }
    }

    .program-info {
        .program-info__title {
            font-size: 22px;
            font-weight: bold;
            line-height: 145%;
            font-feature-settings: "palt" 1;  // 文字詰め
            letter-spacing: 0.05em;  // 字間を少し空ける
            @include tablet-vertical {
                margin-top: 16px;
            }
            @include smartphone-horizontal {
                margin-top: 10px;
                font-size: 18px;
            }
            @include smartphone-vertical {
                margin-top: 16px;
                font-size: 19px;
            }
        }
        .program-info__time {
            margin-top: 8px;
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 14px;
            @include smartphone-horizontal {
                font-size: 13px;
            }
        }
        .program-info__description {
            margin-top: 12px;
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 12px;
            line-height: 168%;
            overflow-wrap: break-word;
            font-feature-settings: "palt" 1;  // 文字詰め
            letter-spacing: 0.08em;  // 字間を少し空ける
            @include smartphone-horizontal {
                margin-top: 8px;
                font-size: 11px;
            }
        }
        .program-info__genre-container {
            display: flex;
            flex-wrap: wrap;
            margin-top: 10px;

            .program-info__genre {
                display: inline-block;
                font-size: 10.5px;
                padding: 3px;
                margin-top: 4px;
                margin-right: 4px;
                border-radius: 4px;
                background: rgb(var(--v-theme-background-lighten-2));
                @include smartphone-horizontal {
                    font-size: 9px;
                }
            }
        }
        // 録画開始ボタン / 録画状態表示
        .program-info__record-button {
            display: inline-flex;
            align-items: center;
            padding: 5px 8px;
            margin-top: 12px;
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 12.7px;
            line-height: 170%;
            background: rgb(var(--v-theme-background-lighten-1));
            border-radius: 4px;
            user-select: none;
            transition: color 0.15s ease;
            cursor: pointer;
            @include smartphone-horizontal {
                font-size: 11.5px;
            }

            &:hover {
                color: rgb(var(--v-theme-text));
            }

            // Mirakurun バックエンド時: グレーアウト
            &--disabled {
                opacity: 0.5;
                cursor: default;
                &:hover {
                    color: rgb(var(--v-theme-text-darken-1));
                }
            }

            // 録画開始中: クリック不可
            &--preparing {
                cursor: default;
            }

            // 録画中の赤い丸ドット (静止版、番組表の recording-icon のアニメなし版)
            .program-info__recording-dot {
                display: block;
                width: 10px;
                height: 10px;
                border-radius: 50%;
                background-color: #EF5350;
                box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.25);
            }
        }
        .program-info__next {
            display: flex;
            align-items: center;
            margin-top: 18px;
            color: rgb(var(--v-theme-text));
            font-size: 14px;
            font-weight: bold;
            user-select: none;
            @include smartphone-horizontal {
                margin-top: 14px;
                font-size: 13px;
            }
            &-decorate {
                flex-shrink: 0;
            }
            &-icon {
                flex-shrink: 0;
                margin-left: 3px;
                font-size: 15px;
            }
        }
        .program-info__next-title {
            display: -webkit-box;
            margin-top: 2px;
            color: rgb(var(--v-theme-text));
            font-size: 14px;
            font-weight: bold;
            overflow: hidden;
            -webkit-line-clamp: 2;  // 2行までに制限
            -webkit-box-orient: vertical;
            @include smartphone-horizontal {
                font-size: 13px;
            }
        }
        .program-info__next-time {
            margin-top: 3px;
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 13.5px;
        }

        .program-info__status {
            display: flex;
            align-items: center;
            margin-top: 16px;
            font-size: 14px;
            color: rgb(var(--v-theme-text-darken-1));
            @include smartphone-horizontal {
                margin-top: 10px;
                font-size: 12px;
            }

            &-force, &-viewers {
                display: flex;
                align-items: center;
            }

            &-force--festival {
                color: #E7556E;
            }
            &-force--so-many {
                color: #E76B55;
            }
            &-force--many {
                color: #E7A355;
            }
        }
    }

    .program-detail-container {
        margin-top: 24px;
        margin-bottom: 24px;
        @include tablet-vertical {
            margin-top: 20px;
            margin-bottom: 20px;
        }
        @include smartphone-horizontal {
            margin-top: 20px;
            margin-bottom: 16px;
        }

        .program-detail {
            margin-top: 16px;

            .program-detail__heading {
                font-size: 18px;
                @include smartphone-horizontal {
                    font-size: 16px;
                }
            }
            .program-detail__text {
                margin-top: 8px;
                color: rgb(var(--v-theme-text-darken-1));
                font-size: 12px;
                line-height: 168%;
                overflow-wrap: break-word;
                white-space: pre-wrap;  // \n で改行する
                font-feature-settings: "palt" 1;  // 文字詰め
                letter-spacing: 0.08em;  // 字間を少し空ける
                @include smartphone-horizontal {
                    font-size: 11px;
                }

                // リンクの色
                :deep(a:link), :deep(a:visited) {
                    color: rgb(var(--v-theme-primary-lighten-1));
                    text-decoration: underline;
                    text-underline-offset: 3px;  // 下線と字の間隔を空ける
                }
            }
        }
    }
}

// 録画停止確認ダイアログ内の警告バナー (ReservationDetailDrawer.vue と同じスタイル)
// v-dialog はテレポートされるため、.program-container の外にスタイルを定義する必要がある
.warning-banner {
    display: flex;
    align-items: center;
    padding: 12px 16px;
    border-radius: 6px;

    &__icon {
        width: 22px;
        height: 22px;
        margin-right: 8px;
        flex-shrink: 0;
    }

    &__text {
        font-size: 13px;
        font-weight: 500;
        line-height: 1.55;
    }

    // 録画中の警告 (エラー色)
    &--recording {
        background-color: rgba(var(--v-theme-error-darken-3), 0.5);
        .warning-banner__icon {
            color: rgb(var(--v-theme-error));
        }
        .warning-banner__text {
            color: rgb(var(--v-theme-error-lighten-1));
        }
    }
}

</style>