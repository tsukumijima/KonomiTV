<template>
    <div class="comment-container" :class="{'comment-container--video': playback_mode === 'Video'}">
        <section class="comment-header">
            <h2 class="comment-header__title">
                <Icon class="comment-header__title-icon" icon="bi:chat-left-text-fill" height="18.5px" />
                <span class="comment-header__title-text">コメント</span>
            </h2>
            <button v-ripple class="comment-header__button ml-auto" @click="comment_mute_settings_modal = !comment_mute_settings_modal">
                <Icon icon="heroicons-solid:filter" height="11px" />
                <span class="ml-1">ミュート設定</span>
            </button>
        </section>
        <section class="comment-list-wrapper" ref="comment_list_wrapper">
            <div class="comment-list-dropdown" :class="{'comment-list-dropdown--display': is_comment_list_dropdown_display}"
                :style="{'--comment-list-dropdown-top': `${comment_list_dropdown_top}px`}">
                <v-list style="background: rgb(var(--v-theme-background-lighten-1))">
                    <v-list-item density="compact" style="min-height: 30px" @click="copyTextToClipboard()">
                        <v-list-item-title class="d-flex align-center">
                            <Icon icon="fluent:clipboard-paste-20-filled" width="20px" />
                            <span class="ml-2">クリップボードにコピー</span>
                        </v-list-item-title>
                    </v-list-item>
                    <v-list-item density="compact" style="min-height: 30px" @click="addMutedKeywords()">
                        <v-list-item-title class="d-flex align-center">
                            <Icon icon="fluent:comment-dismiss-20-filled" width="20px" />
                            <span class="ml-2">このコメントをミュート</span>
                        </v-list-item-title>
                    </v-list-item>
                    <v-list-item density="compact" style="min-height: 30px" @click="addMutedNiconicoUserIds()">
                        <v-list-item-title class="d-flex align-center" >
                            <Icon icon="fluent:person-prohibited-20-filled" width="20px" />
                            <span class="ml-2">このコメントの投稿者をミュート</span>
                        </v-list-item-title>
                    </v-list-item>
                </v-list>
            </div>
            <div class="comment-list-cover" :class="{'comment-list-cover--display': is_comment_list_dropdown_display}"
                @click="hideCommentListDropdown()"></div>
            <template v-if="playback_mode === 'Live'">
                <DynamicScroller class="comment-list" :direction="'vertical'" :items="comment_list" :min-item-size="34">
                    <template v-slot="{item, active}">
                    <DynamicScrollerItem :item="item" :active="active" :size-dependencies="[item.text]">
                        <div class="comment" :class="{'comment--my-post': item.my_post}">
                            <span class="comment__text">{{item.text}}</span>
                            <span class="comment__time">{{item.time}}</span>
                            <!-- なぜか @click だとスマホで発火しないので @touchend にしている -->
                            <div class="comment__icon" v-ripple="!Utils.isTouchDevice()"
                                @mouseup="showCommentListDropdown($event, item)"
                                @touchend="showCommentListDropdown($event, item)">
                                <!-- Icon コンポーネントを使うと個数が多いときに高負荷になるため、意図的に SVG を直書きしている -->
                                <svg class="iconify iconify--fluent" width="20px" height="20px" viewBox="0 0 20 20">
                                    <path fill="currentColor" d="M10 6.5A1.75 1.75 0 1 1 10 3a1.75 1.75 0 0 1 0 3.5ZM10 17a1.75 1.75 0 1 1 0-3.5a1.75 1.75 0 0 1 0 3.5Zm-1.75-7a1.75 1.75 0 1 0 3.5 0a1.75 1.75 0 0 0-3.5 0Z"></path>
                                </svg>
                            </div>
                        </div>
                    </DynamicScrollerItem>
                    </template>
                </DynamicScroller>
            </template>
            <template v-else>
                <VirtuaList ref="virtua_scroller" class="comment-list" :data="comment_list" #default="{ item }">
                    <div class="comment" :class="{'comment--my-post': item.my_post}">
                        <span class="comment__text">{{item.text}}</span>
                        <span class="comment__time">{{item.time}}</span>
                        <!-- なぜか @click だとスマホで発火しないので @touchend にしている -->
                        <div class="comment__icon" v-ripple="!Utils.isTouchDevice()"
                            @mouseup="showCommentListDropdown($event, item)"
                            @touchend="showCommentListDropdown($event, item)">
                            <!-- Icon コンポーネントを使うと個数が多いときに高負荷になるため、意図的に SVG を直書きしている -->
                            <svg class="iconify iconify--fluent" width="20px" height="20px" viewBox="0 0 20 20">
                                <path fill="currentColor" d="M10 6.5A1.75 1.75 0 1 1 10 3a1.75 1.75 0 0 1 0 3.5ZM10 17a1.75 1.75 0 1 1 0-3.5a1.75 1.75 0 0 1 0 3.5Zm-1.75-7a1.75 1.75 0 1 0 3.5 0a1.75 1.75 0 0 0-3.5 0Z"></path>
                            </svg>
                        </div>
                    </div>
                </VirtuaList>
            </template>
            <div class="comment-announce"
                v-if="playback_mode === 'Live' && playerStore.live_comment_init_failed_message === null && comment_list.length === 0">
                <div class="comment-announce__heading">まだコメントがありません。</div>
                <div class="comment-announce__text">
                    <p class="mt-0 mb-0">このチャンネルに対応するニコニコ実況のコメントが、リアルタイムで表示されます。</p>
                </div>
            </div>
            <div class="comment-announce"
                v-if="playback_mode === 'Live' && playerStore.live_comment_init_failed_message !== null && comment_list.length === 0">
                <div class="comment-announce__heading">コメントがありません。</div>
                <div class="comment-announce__text">
                    <p class="mt-0 mb-0">{{playerStore.live_comment_init_failed_message}}</p>
                </div>
            </div>
            <div class="comment-announce"
                v-if="playback_mode === 'Video' && playerStore.video_comment_init_failed_message === null && comment_list.length === 0">
                <div class="comment-announce__heading">まだコメントがありません。</div>
                <div class="comment-announce__text">
                    <p class="mt-0 mb-0">この録画番組に対応する、ニコニコ実況の過去ログコメントを取得しています...</p>
                </div>
            </div>
            <div class="comment-announce"
                v-if="playback_mode === 'Video' && playerStore.video_comment_init_failed_message !== null && comment_list.length === 0">
                <div class="comment-announce__heading">コメントがありません。</div>
                <div class="comment-announce__text">
                    <p class="mt-0 mb-0">{{playerStore.video_comment_init_failed_message}}</p>
                </div>
            </div>
        </section>
        <div v-ripple class="comment-scroll-button elevation-5" @click="handleAutoScrollButtonClick"
             :class="{'comment-scroll-button--display': is_manual_scroll}">
            <Icon icon="fluent:arrow-down-12-filled" height="29px" />
        </div>
        <CommentMuteSettings :modelValue="comment_mute_settings_modal" @update:modelValue="comment_mute_settings_modal = $event" />
    </div>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { VList as VirtuaList } from 'virtua/vue';
import { defineComponent, PropType } from 'vue';

import CommentMuteSettings from '@/components/Settings/CommentMuteSettings.vue';
import { ICommentData } from '@/services/player/managers/LiveCommentManager';
import useChannelsStore from '@/stores/ChannelsStore';
import usePlayerStore from '@/stores/PlayerStore';
import Utils, { CommentUtils } from '@/utils';

export default defineComponent({
    name: 'Panel-CommentTab',
    components: {
        CommentMuteSettings,
        VirtuaList,
    },
    props: {
        playback_mode: {
            type: String as PropType<'Live' | 'Video'>,
            required: true,
        },
    },
    data() {
        return {

            // ユーティリティをテンプレートで使えるように
            Utils: Object.freeze(Utils),

            // 手動スクロール状態かどうか
            is_manual_scroll: false,

            // 自動スクロール中かどうか
            // 自動スクロール中の場合、scroll イベントが発火しても無視する
            is_auto_scrolling: false,

            // コメントリストの配列
            comment_list: [] as ICommentData[],

            // コメントリストの要素
            comment_list_element: null as HTMLElement | null,

            // コメントリストのドロップダウン関連
            is_comment_list_dropdown_display: false as boolean,
            comment_list_dropdown_top: 0 as number,
            comment_list_dropdown_comment: null as ICommentData | null,

            // コメントのミュート設定のモーダルを表示するか
            comment_mute_settings_modal: false,

            // visibilitychange イベントのリスナー
            visibilitychange_listener: null as (() => void) | null,

            // 録画再生時の現在の再生位置（秒）とスクロール対象のコメントのインデックス
            current_playback_position: 0,
            target_comment_index: 0,

            // VirtuaList の参照
            virtua_scroller: null as {
                scrollToIndex: (index: number, opts?: {
                    align?: 'start' | 'center' | 'end' | 'nearest';
                    smooth?: boolean;
                    offset?: number;
                }) => void;
            } | null,
        };
    },
    computed: {
        ...mapStores(useChannelsStore, usePlayerStore),
    },
    watch: {

        // ライブ視聴のみ: ChannelsStore の channel.current.id の変更を監視する
        // 現在視聴中のチャンネルが変更されたときにコメントリストをクリアする
        'channelsStore.channel.current.id': {
            handler() {
                if (this.playback_mode === 'Live') {
                    // 明示的に空の配列を入れてクリアしないと、コメントリストが残ったままになる
                    this.comment_list = [];
                }
            }
        }
    },
    mounted() {

        // コメントリストの要素を取得
        if (this.comment_list_element === null) {
            this.comment_list_element = document.querySelector('.comment-list')!;
        }

        // VirtuaList の参照を取得（録画再生時のみ）
        if (this.playback_mode === 'Video') {
            this.virtua_scroller = this.$refs.virtua_scroller as any;
        }

        // 現在コメントリストがユーザーイベントでスクロールされているかどうか
        let is_user_scrolling = false;

        // mousedown → mouseup 中: スクロールバーをマウスでドラッグ
        // 残念ながらスクロールバーのドラッグ中は mousemove のイベントが発火しないため、直接 is_user_scrolling を設定する
        this.comment_list_element!.onmousedown = (event: MouseEvent) => {
            // コメントリストの要素の左上を起点としたカーソルのX座標を求める
            if (this.comment_list_element === null) return;
            const x = event.clientX - this.comment_list_element.getBoundingClientRect().left;
            // 座標が clientWidth 以上であれば、スクロールバー上で mousedown されたものとする
            if (x > this.comment_list_element.clientWidth) is_user_scrolling = true;
        };
        this.comment_list_element!.onmouseup = (event: MouseEvent) => {
            // コメントリストの要素の左上を起点としたカーソルのX座標を求める
            if (this.comment_list_element === null) return;
            const x = event.clientX - this.comment_list_element.getBoundingClientRect().left;
            // 座標が clientWidth 以上であれば、スクロールバー上で mouseup されたものとする
            if (x > this.comment_list_element.clientWidth) is_user_scrolling = false;
        };

        // ユーザーによるスクロールイベントで is_user_scrolling を true にする
        // 0.1 秒後に false にする（継続してイベントが発火すれば再び true になる）
        const on_user_scrolling = () => {
            is_user_scrolling = true;
            window.setTimeout(() => is_user_scrolling = false, 100);
        };

        // 現在コメントリストがドラッグされているかどうか
        let is_dragging = false;
        // touchstart → touchend 中: スクロールバーをタップでドラッグ
        this.comment_list_element!.ontouchstart = () => is_dragging = true;
        this.comment_list_element!.ontouchend = () => is_dragging = false;
        // touchmove + is_dragging 中: コメントリストをタップでドラッグしてスクロール
        this.comment_list_element!.ontouchmove = () => is_dragging === true ? on_user_scrolling(): '';

        // wheel 中: マウスホイールの回転
        this.comment_list_element!.onwheel = on_user_scrolling;

        // コメントリストがスクロールされた際、自動スクロール中でない&ユーザーイベントで操作されていれば、手動スクロールモードに設定
        // 手動スクロールモードでは自動スクロールを行わず、ユーザーがコメントリストをスクロールできるようにする
        this.comment_list_element!.onscroll = async () => {
            if (this.comment_list_element === null) return;

            // scroll イベントは自動スクロールでも発火してしまうので、ユーザーイベントによるスクロールかを確認しないといけない
            // 自動スクロール中かどうかは is_auto_scrolling が true のときで判定できるはずだが、
            // コメントが多くなると is_auto_scrolling が false なのに scroll イベントが遅れて発火してしまうことがある
            if (this.is_auto_scrolling === false && is_user_scrolling === true) {

                // 手動スクロールを有効化
                this.is_manual_scroll = true;
                console.log('[Comment.vue] Manual scroll is enabled.');

                // イベント発火時点では scrollTop の値が完全に下にスクロールされていない場合があるため、0.1秒だけ待つ
                await Utils.sleep(0.1);

                // ライブ視聴のみ: 一番下までスクロールされていたら自動スクロールに戻す
                // ビデオ視聴時は明示的に自動スクロールボタンを押した時のみ手動スクロールを無効化する
                if ((this.playback_mode === 'Live') &&
                    (this.comment_list_element.scrollTop + this.comment_list_element.offsetHeight) >
                    (this.comment_list_element.scrollHeight - 10)) {  // 一番下から 10px 以内
                    this.is_manual_scroll = false;  // 手動スクロールを無効化
                    console.log('[Comment.vue] Manual scroll is disabled because bottom of comment list is reached.');
                }
            }
        };

        // ***** イベントリスナーの登録 *****

        // タブが非表示状態のときにコメントを格納する配列
        // タブが表示状態になったらコメントリストにのみ表示する（遅れているのでプレイヤーには表示しない）
        const comment_list_buffer: ICommentData[] = [];

        // コメントの最大保持数
        const max_comment_count = 500;

        // LiveCommentManager からコメントを受信したときのイベントハンドラーを登録
        // 非同期関数で登録することで、気持ち高速化を図る
        // ビデオ視聴での過去ログコメントは PlayerController から直接このイベントに送信される
        this.playerStore.event_emitter.on('CommentReceived', async (event) => {

            // 初回の過去コメント (最大50件) を受信したとき or 録画再生時の番組に対応するすべての過去ログコメントを受信したとき
            if (event.is_initial_comments === true) {

                // チャンネル or 録画番組が切り替わった可能性があるので、既存のコメントリストをクリア
                this.comment_list = [];

                // コメントリストに一括で追加
                this.comment_list.push(...event.comments);
                console.log(`[Comment.vue] Comment list updated. ${this.comment_list.length} comments.`);

                // ライブ視聴のみ: コメントリストを一番下までスクロール
                if (this.playback_mode === 'Live') {
                    this.scrollCommentList(false);  // スムーズスクロールは遅いので行わない
                }

            // 通常のコメントを受信したとき
            } else {

                // タブが非表示状態のときは、バッファにコメントを追加するだけで終了する
                // ここで追加すると、タブが表示状態になったときに一斉に描画されて大変なことになる
                if (document.visibilityState === 'hidden') {
                    comment_list_buffer.push(...event.comments);
                    return;
                }

                // コメントリストのコメント数が max_comment_count 件を超えたら、古いものから順に削除する
                // 仮想スクロールとはいえ、さすがに max_comment_count 件を超えると重くなりそう
                // 手動スクロール時は実行しない
                if (this.comment_list.length >= max_comment_count && this.is_manual_scroll === false) {
                    this.comment_list.splice(0, Math.max(0, this.comment_list.length - max_comment_count));
                }

                // コメントリストに追加
                // 通常コメントは1つだが、コメントが殺到した場合は DOM 描画負荷軽減のため一括で送信されてくる
                this.comment_list.push(...event.comments);

                // コメントリストを一番下までスクロール
                // ビデオ視聴では is_initial_comments が true のイベントしか送られてこないので、そもそも実行されない
                this.scrollCommentList(false);  // スムーズスクロールは遅いので行わない
            }
        });

        // ライブ視聴のみ登録されるイベントリスナー
        if (this.playback_mode === 'Live') {

            // LiveCommentManager からコメントの送信完了イベントを受信したときのイベントハンドラーを登録
            this.playerStore.event_emitter.on('CommentSendCompleted', async (event) => {

                // 送信した自分のコメントをコメントリストに追加
                this.comment_list.push(event.comment);

                // コメントリストを一番下までスクロール
                // ビデオ視聴ではコメントを送信できないので、そもそも実行されない
                this.scrollCommentList(false);  // スムーズスクロールは遅いので行わない
            });

            // タブが表示状態になったときのイベントハンドラーを登録
            this.visibilitychange_listener = () => {
                if (document.visibilityState === 'visible') {

                    // コメントリスト + バッファの合計コメント数が max_comment_count 件を超えたら、
                    // コメントリスト内のコメントを古いものから順に削除し、max_comment_count 件になるようにする
                    const comment_list_and_buffer_length = this.comment_list.length + comment_list_buffer.length;
                    if (comment_list_and_buffer_length >= max_comment_count && this.is_manual_scroll === false) {
                        this.comment_list.splice(0, Math.max(0, comment_list_and_buffer_length - max_comment_count));
                    }

                    // バッファ内のコメントをコメントリストに一括で追加する
                    this.comment_list.push(...comment_list_buffer);
                    comment_list_buffer.length = 0;  // バッファを空にする

                    // コメントリストを一番下までスクロール
                    this.scrollCommentList(false);  // スムーズスクロールは遅いので行わない
                }
            };
            document.addEventListener('visibilitychange', this.visibilitychange_listener);
        }

        // 録画再生時のみ登録されるイベントリスナー
        if (this.playback_mode === 'Video') {

            // PlaybackPositionChanged イベントに応答する
            console.log('[Comment.vue] Setting up PlaybackPositionChanged event listener.');
            this.playerStore.event_emitter.on('PlaybackPositionChanged', (payload) => {
                // 現在再生位置を更新
                this.current_playback_position = payload.playback_position;
                // 手動スクロールが行われていなければ自動スクロール実行
                if (this.is_manual_scroll === false) {
                    this.scrollPlaybackComment(false);  // スムーズスクロールは遅いので行わない
                }
            });
        }
    },
    // 終了前に実行
    beforeUnmount() {

        // ***** イベントリスナーの登録解除 *****

        // タブの表示/非表示の状態が切り替わったときのイベントを削除
        if (this.playback_mode === 'Live' && this.visibilitychange_listener !== null) {
            document.removeEventListener('visibilitychange', this.visibilitychange_listener);
            this.visibilitychange_listener = null;
        }

        // LiveCommentManager / PlayerController からのイベントハンドラーを削除
        this.playerStore.event_emitter.off('CommentReceived');  // CommentReceived イベントの全てのイベントハンドラーを削除
        if (this.playback_mode === 'Live') {
            this.playerStore.event_emitter.off('CommentSendCompleted');  // CommentSendCompleted イベントの全てのイベントハンドラーを削除
        }
        if (this.playback_mode === 'Video') {
            this.playerStore.event_emitter.off('PlaybackPositionChanged');
        }

        // コメントリストをクリア
        this.comment_list = [];
    },
    methods: {

        // ドロップダウンメニューを表示する
        showCommentListDropdown(event: Event, comment: ICommentData) {
            const comment_list_wrapper_rect = (this.$refs.comment_list_wrapper as HTMLDivElement).getBoundingClientRect();
            const comment_list_dropdown_height = 106;  // 106px はドロップダウンメニューの高さ
            const comment_button_rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
            // メニューの表示位置をクリックされたコメントに合わせる
            this.comment_list_dropdown_top = comment_button_rect.top - comment_list_wrapper_rect.top;
            // メニューがコメントリストからはみ出るときだけ、表示位置を上側に調整
            if ((this.comment_list_dropdown_top + comment_list_dropdown_height) > comment_list_wrapper_rect.height) {
                this.comment_list_dropdown_top = this.comment_list_dropdown_top - comment_list_dropdown_height + comment_button_rect.height;
            }
            // 表示位置を調整できたので、メニューを表示
            this.comment_list_dropdown_comment = comment;
            this.is_comment_list_dropdown_display = true;
        },

        // ドロップダウンメニューを非表示にする
        hideCommentListDropdown() {
            this.is_comment_list_dropdown_display = false;
            this.comment_list = this.comment_list.filter((comment) => {
                return CommentUtils.isMutedComment(comment.text, comment.user_id) === false;
            });
        },

        // コメントのテキストをクリップボードにコピーする
        copyTextToClipboard() {
            if (this.comment_list_dropdown_comment === null) return;
            navigator.clipboard.writeText(this.comment_list_dropdown_comment.text);
            this.hideCommentListDropdown();
        },

        // ミュートするキーワードを追加する
        addMutedKeywords() {
            if (this.comment_list_dropdown_comment === null) return;
            CommentUtils.addMutedKeywords(this.comment_list_dropdown_comment.text);
            this.hideCommentListDropdown();
        },

        // ミュートするニコニコユーザー ID を追加する
        addMutedNiconicoUserIds() {
            if (this.comment_list_dropdown_comment === null) return;
            CommentUtils.addMutedNiconicoUserIDs(this.comment_list_dropdown_comment.user_id);
            this.hideCommentListDropdown();
        },

        // コメントリストを一番下までスクロールする
        async scrollCommentList(smooth: boolean = false) {
            if (this.comment_list_element === null) return;

            // ドロップダウンメニュー表示中なら手動スクロールモードに設定
            if (this.is_comment_list_dropdown_display === true) {
                this.is_manual_scroll = true;
                console.log('[Comment.vue] Manual scroll is enabled because dropdown menu is displayed.');
            }

            // ユーザーによる手動操作中の場合は何もしない
            if (this.is_manual_scroll === true) {
                return;
            }

            // 自動スクロール中のフラグを立てる
            this.is_auto_scrolling = true;

            // window.requestAnimationFrame() でアニメーション更新を待ってからスクロールする (重要)
            // すぐに scrollTo() を実行すると、DOM 描画のタイミングの関係なのか、なぜか最後までスクロールされないことがある
            // 念のため 3 回実行する
            const scroll_to_bottom = (count = 3) => {
                if (count <= 0) return;
                window.requestAnimationFrame(() => {
                    if (smooth === true) {  // スムーズスクロール
                        this.comment_list_element?.scrollTo({top: this.comment_list_element.scrollHeight, left: 0, behavior: 'smooth'});
                    } else {
                        this.comment_list_element?.scrollTo(0, this.comment_list_element.scrollHeight);
                    }
                    scroll_to_bottom(count - 1);
                });
            };
            scroll_to_bottom();

            // 0.1 秒待つ（重要）
            await Utils.sleep(0.1);

            // 自動スクロール中のフラグを降ろす
            this.is_auto_scrolling = false;
        },

        /**
         * 録画再生時、現在の再生位置に対応するコメントまでスクロールする
         * @param smooth スムーズスクロールを有効にするか
         */
        async scrollPlaybackComment(smooth: boolean = false): Promise<void> {
            if (!this.virtua_scroller) {
                console.log('[Comment.vue] VirtuaList reference is not available.');
                return;
            }

            // ドロップダウンメニュー表示中なら手動スクロールモードに設定
            if (this.is_comment_list_dropdown_display === true) {
                this.is_manual_scroll = true;
                console.log('[Comment.vue] Manual scroll is enabled because dropdown menu is displayed.');
            }

            // ユーザーによる手動操作中の場合は何もしない
            if (this.is_manual_scroll === true) {
                return;
            }

            // コメントリストが現在表示されていない時は何もしない
            if (this.playerStore.video_panel_active_tab !== 'Comment') {
                return;
            }

            // 再生位置に対応するコメントのインデックスを算出する
            let target_index = -1;
            for (let i = 0; i < this.comment_list.length; i++) {
                const comment = this.comment_list[i];
                // 各コメントの playback_position はコメント投稿時の再生位置（秒）である前提
                if (comment.playback_position <= this.current_playback_position) {
                    target_index = i;
                } else {
                    break;
                }
            }

            // ターゲットのコメントのインデックスが変更されていない時は実行しない (smooth: false のみ)
            if (target_index === this.target_comment_index && smooth === false) {
                return;
            }

            // 自動スクロール中のフラグを立てる
            this.is_auto_scrolling = true;

            // VirtuaList の scrollToIndex API を呼び出し、指定インデックスへスクロール
            if (target_index !== -1) {
                this.virtua_scroller.scrollToIndex(target_index, {
                    align: 'end',  // スクロール位置をコメントの下部に合わせる
                    smooth: smooth,
                    offset: -3,  // コメントの下部に合わせるため、-3px だけ上にずらす
                });
                // ターゲットのコメントのインデックスを更新
                this.target_comment_index = target_index;
            }

            // 0.1 秒待つ（重要）
            await Utils.sleep(0.1);

            // 自動スクロール中のフラグを降ろす
            this.is_auto_scrolling = false;
        },

        /**
         * 自動スクロールボタンがクリックされたときの処理
         */
        handleAutoScrollButtonClick(): void {

            // ユーザーによる手動スクロール状態をリセットし、自動スクロールを有効化
            this.is_manual_scroll = false;
            console.log('[Comment.vue] Manual scroll is disabled because Auto-scroll button clicked.');

            // playback_mode に応じたスクロール処理の呼び出し
            // 明示的に自動スクロールボタンが押されたときはスムーズスクロールを行う
            if (this.playback_mode === 'Live') {
                this.scrollCommentList(true);
            } else if (this.playback_mode === 'Video') {
                this.scrollPlaybackComment(true);
            }
        },
    }
});

</script>
<style lang="scss" scoped>

.comment-container {
    display: flex;
    flex-direction: column;
    &--video {
        // 録画再生時は Virtua の仮想スクローラーと content-visibility の相性が悪いっぽいので、
        // 一律で content-visibility: visible を設定
        content-visibility: visible !important;
    }

    .comment-header {
        display: flex;
        align-items: center;
        flex-shrink: 0;
        width: 100%;
        height: 26px;
        padding-left: 16px;
        padding-right: 16px;
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

        &__title {
            display: flex;
            align-items: center;
            font-size: 18.5px;
            font-weight: bold;
            line-height: 145%;
            @include tablet-vertical {
                font-size: 19px;
            }
            @include smartphone-horizontal {
                font-size: 16.5px;
            }
            @include smartphone-vertical {
                font-size: 17px;
            }

            &-icon {
                margin-bottom: -3px;  // 高さ調整
                @include tablet-vertical {
                    width: 24px;
                    height: 24px;
                }
                @include smartphone-horizontal {
                    height: 17.5px;
                }
                @include smartphone-vertical {
                    height: 18px;
                }
            }
            &-text {
                margin-left: 12px;
                @include tablet-vertical {
                    margin-left: 16px;
                }
            }
        }

        &__button {
            display: flex;
            align-items: center;
            height: 26px;
            padding: 0 9px;
            border-radius: 4px;
            background: rgb(var(--v-theme-background-lighten-3));
            font-size: 11px;
            line-height: 1.8;
            letter-spacing: 0;
        }
    }

    .comment-list-wrapper {
        position: relative;
        width: 100%;
        height: 100%;
        min-height: 0;
        margin-top: 16px;
        @include tablet-vertical {
            margin-top: 20px;
        }
        @include smartphone-horizontal {
            margin-top: 12px;
        }
        @include smartphone-vertical {
            margin-top: 14px;
        }

        .comment-list-dropdown {
            display: inline-block;
            position: absolute;
            top: var(--comment-list-dropdown-top, 0px);
            right: 16px;
            border-radius: 4px;
            overflow-x: hidden;
            overflow-y: auto;
            box-shadow: 0px 5px 5px -3px rgb(0 0 0 / 20%),
                        0px 8px 10px 1px rgb(0 0 0 / 14%),
                        0px 3px 14px 2px rgb(0 0 0 / 12%);
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.15s ease, visibility 0.15s ease;
            z-index: 8;
            &--display {
                opacity: 1;
                visibility: visible;
            }

            .v-list-item-title {
                font-size: 13px;
                font-weight: 500;
            }
        }

        .comment-list-cover {
            display: none;
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 7;
            &--display {
                display: block;
            }
        }

        .comment-list {
            width: 100%;
            height: 100%;
            padding-left: 16px;
            padding-right: 4px;
            padding-bottom: 12px;
            overflow-y: scroll !important;
            @include tablet-vertical {
                padding-left: 24px;
                padding-right: 10px;
                padding-bottom: 0px;
            }
            @include smartphone-vertical {
                padding-bottom: 0px;
            }

            .comment {
                display: flex;
                position: relative;
                align-items: center;
                min-height: 28px;
                padding-top: 6px;
                word-break: break-word;
                &--my-post {
                    color: rgb(var(--v-theme-secondary-lighten-2));
                }

                &__text {
                    font-size: 13px;
                }

                &__time {
                    flex-shrink: 0;
                    margin-left: auto;
                    padding-left: 8px;
                    color: rgb(var(--v-theme-text-darken-1));
                    font-size: 13px;
                }

                &__icon {
                    width: 20px;
                    height: 20px;
                    margin-left: 2px;
                    border-radius: 5px;
                    color: rgb(var(--v-theme-text));
                    cursor: pointer;
                }
            }
        }

        .comment-announce {
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            padding-left: 12px;
            padding-right: 12px;

            &__heading {
                font-size: 20px;
                font-weight: bold;
                @include smartphone-horizontal {
                    font-size: 16px;
                }
            }
            &__text {
                margin-top: 12px;
                color: rgb(var(--v-theme-text-darken-1));
                font-size: 13.5px;
                text-align: center;
                @include smartphone-horizontal {
                    font-size: 12px;
                }
            }
        }
    }

    .comment-scroll-button {
        display: flex;
        align-items: center;
        justify-content: center;
        position: absolute;
        left: 0px;
        right: 0px;
        bottom: 22px;
        width: 42px;
        height: 42px;
        margin: 0 auto;
        border-radius: 50%;
        background: rgb(var(--v-theme-primary));
        transition: background-color 0.15s, opacity 0.3s, visibility 0.3s;
        visibility: hidden;
        opacity: 0;
        user-select: none;
        cursor: pointer;

        &--display {
            opacity: 1;
            visibility: visible;
        }
    }
}

</style>