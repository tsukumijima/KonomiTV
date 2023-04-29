<template>
    <div class="comment-container">
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
                <v-list style="background: var(--v-background-lighten1)">
                    <v-list-item dense style="min-height: 30px" @click="addMutedKeywords()">
                        <v-list-item-title class="d-flex align-center">
                            <Icon icon="fluent:comment-dismiss-20-filled" width="20px" />
                            <span class="ml-2">このコメントをミュート</span>
                        </v-list-item-title>
                    </v-list-item>
                    <v-list-item dense style="min-height: 30px" @click="addMutedNiconicoUserIds()">
                        <v-list-item-title class="d-flex align-center" >
                            <Icon icon="fluent:person-prohibited-20-filled" width="20px" />
                            <span class="ml-2">このコメントの投稿者をミュート</span>
                        </v-list-item-title>
                    </v-list-item>
                </v-list>
            </div>
            <div class="comment-list-cover" :class="{'comment-list-cover--display': is_comment_list_dropdown_display}"
                @click="hideCommentListDropdown()"></div>
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
                            <Icon icon="fluent:more-vertical-20-filled" width="20px" />
                        </div>
                    </div>
                </DynamicScrollerItem>
                </template>
            </DynamicScroller>
            <div class="comment-announce" v-if="initialize_failed_message === null && comment_list.length === 0">
                <div class="comment-announce__heading">まだコメントがありません。</div>
                <div class="comment-announce__text">
                    <p class="mt-0 mb-0">このチャンネルに対応するニコニコ実況のコメントが、リアルタイムで表示されます。</p>
                </div>
            </div>
            <div class="comment-announce" v-if="initialize_failed_message !== null && comment_list.length === 0">
                <div class="comment-announce__heading">コメントがありません。</div>
                <div class="comment-announce__text">
                    <p class="mt-0 mb-0">{{initialize_failed_message}}</p>
                </div>
            </div>
        </section>
        <div v-ripple class="comment-scroll-button elevation-5" @click="is_manual_scroll = false; scrollCommentList(true);"
             :class="{'comment-scroll-button--display': is_manual_scroll}">
            <Icon icon="fluent:arrow-down-12-filled" height="29px" />
        </div>
        <CommentMuteSettings v-model="comment_mute_settings_modal" />
    </div>
</template>
<script lang="ts">

import DPlayer from 'dplayer';
import * as DPlayerType from 'dplayer/dist/d.ts/types/DPlayer';
import { mapStores } from 'pinia';
import Vue from 'vue';

import CommentMuteSettings from '@/components/Settings/CommentMuteSettings.vue';
import LiveCommentManager, { ICommentData } from '@/services/player/LiveCommentManager';
import useUserStore from '@/store/UserStore';
import Utils, { CommentUtils } from '@/utils';

export default Vue.extend({
    name: 'Panel-CommentTab',
    components: {
        CommentMuteSettings,
    },
    data() {
        return {

            // ユーティリティをテンプレートで使えるように
            Utils: Utils,

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

            // LiveCommentManager のインスタンス
            live_comment_manager: null as LiveCommentManager | null,

            // ニコニコ実況セッションの初期化に失敗した際のエラーメッセージ
            // 視聴中チャンネルのニコニコ実況がないときなどに発生する
            initialize_failed_message: null as string | null,

            // visibilitychange イベントのリスナー
            visibilitychange_listener: null as (() => void) | null,

            // ResizeObserver のインスタンス
            resize_observer: null as ResizeObserver | null,

            // ResizeObserver の監視対象の要素
            resize_observer_element: null as HTMLElement | null,

            // コメントのミュート設定のモーダルを表示するか
            comment_mute_settings_modal: false,
        };
    },
    computed: {
        // UserStore に this.userStore でアクセスできるようにする
        // ref: https://pinia.vuejs.org/cookbook/options-api.html
        ...mapStores(useUserStore),
    },
    created() {

        // アカウント情報を更新
        this.userStore.fetchUser();
    },
    mounted() {

        // コメントリストの要素を取得
        if (this.comment_list_element === null) {
            this.comment_list_element = this.$el.querySelector('.comment-list');
        }

        // 現在コメントリストがユーザーイベントでスクロールされているかどうか
        let is_user_scrolling = false;

        // mousedown → mouseup 中: スクロールバーをマウスでドラッグ
        // 残念ながらスクロールバーのドラッグ中は mousemove のイベントが発火しないため、直接 is_user_scrolling を設定する
        this.comment_list_element.onmousedown = (event: MouseEvent) => {
            // コメントリストの要素の左上を起点としたカーソルのX座標を求める
            const x = event.clientX - this.comment_list_element.getBoundingClientRect().left;
            // 座標が clientWidth 以上であれば、スクロールバー上で mousedown されたものとする
            if (x > this.comment_list_element.clientWidth) is_user_scrolling = true;
        };
        this.comment_list_element.onmouseup = (event: MouseEvent) => {
            // コメントリストの要素の左上を起点としたカーソルのX座標を求める
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
        this.comment_list_element.ontouchstart = () => is_dragging = true;
        this.comment_list_element.ontouchend = () => is_dragging = false;
        // touchmove + is_dragging 中: コメントリストをタップでドラッグしてスクロール
        this.comment_list_element.ontouchmove = () => is_dragging === true ? on_user_scrolling(): '';

        // wheel 中: マウスホイールの回転
        this.comment_list_element.onwheel = on_user_scrolling;

        // コメントリストがスクロールされた際、自動スクロール中でない&ユーザーイベントで操作されていれば、手動スクロールモードに設定
        // 手動スクロールモードでは自動スクロールを行わず、ユーザーがコメントリストをスクロールできるようにする
        this.comment_list_element.onscroll = async () => {

            // scroll イベントは自動スクロールでも発火してしまうので、ユーザーイベントによるスクロールかを確認しないといけない
            // 自動スクロール中かどうかは is_auto_scrolling が true のときで判定できるはずだが、
            // コメントが多くなると is_auto_scrolling が false なのに scroll イベントが遅れて発火してしまうことがある
            if (this.is_auto_scrolling === false && is_user_scrolling === true) {

                // 手動スクロールを有効化
                this.is_manual_scroll = true;

                // イベント発火時点では scrollTop の値が完全に下にスクロールされていない場合があるため、0.1秒だけ待つ
                await Utils.sleep(0.1);

                // 一番下までスクロールされていたら自動スクロールに戻す
                if ((this.comment_list_element.scrollTop + this.comment_list_element.offsetHeight) >
                    (this.comment_list_element.scrollHeight - 10)) {  // 一番下から 10px 以内
                    this.is_manual_scroll = false;  // 手動スクロールを無効化
                }
            }
        };
    },
    // 終了前に実行
    beforeDestroy() {

        // ニコニコ実況セッションを破棄
        this.destroy();

        // ResizeObserver を終了
        if (this.resize_observer !== null) {
            this.resize_observer.unobserve(this.resize_observer_element);
        }
    },
    methods: {

        // ドロップダウンメニューを表示する
        showCommentListDropdown(event: Event, comment: ICommentData) {
            const comment_list_wrapper_rect = (this.$refs.comment_list_wrapper as HTMLDivElement).getBoundingClientRect();
            const comment_list_dropdown_height = 76;  // 76px はドロップダウンメニューの高さ
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

        // ミュートするキーワードを追加する
        addMutedKeywords() {
            CommentUtils.addMutedKeywords(this.comment_list_dropdown_comment.text);
            this.hideCommentListDropdown();
        },

        // ミュートするニコニコユーザー ID を追加する
        addMutedNiconicoUserIds() {
            CommentUtils.addMutedNiconicoUserIDs(this.comment_list_dropdown_comment.user_id);
            this.hideCommentListDropdown();
        },

        // コメントリストを一番下までスクロールする
        async scrollCommentList(smooth: boolean = false) {

            // ドロップダウンメニュー表示中なら手動スクロールモードに設定
            if (this.is_comment_list_dropdown_display === true) {
                this.is_manual_scroll = true;
            }

            // 手動スクロールモードの時は実行しない
            if (this.is_manual_scroll === true) return;

            // 自動スクロール中のフラグを立てる
            this.is_auto_scrolling = true;

            // 0.01 秒待って実行し、念押しで2回実行しないと完全に最下部までスクロールされない…（ブラウザの描画バグ？）
            // this.$nextTick() は効かなかった
            for (let index = 0; index < 3; index++) {
                await Utils.sleep(0.01);
                if (smooth === true) {  // スムーズスクロール
                    this.comment_list_element.scrollTo({top: this.comment_list_element.scrollHeight, left: 0, behavior: 'smooth'});
                } else {
                    this.comment_list_element.scrollTo(0, this.comment_list_element.scrollHeight);
                }
            }

            // 0.1 秒待つ（重要）
            await Utils.sleep(0.1);

            // 自動スクロール中のフラグを降ろす
            this.is_auto_scrolling = false;
        },

        // リサイズ時のイベントを初期化
        // プレイヤーが初期化される毎に実行する必要がある
        initReserveObserver() {

            // 以前に初期化された ResizeObserver を終了
            if (this.resize_observer !== null) {
                this.resize_observer.unobserve(this.resize_observer_element);
            }

            // 監視対象の要素
            this.resize_observer_element = document.querySelector('.watch-player');

            // タイムアウト ID
            // 一時的に無効にした transition を有効化する際に利用する
            let animation_timeout_id = null;

            // プレイヤーの要素がリサイズされた際に発火するイベント
            const on_resize = () => {

                // 映像の要素
                const video_element = document.querySelector('.dplayer-video-wrap-aspect');

                // コメント描画領域の要素
                const comment_area_element = document.querySelector<HTMLElement>('.dplayer-danmaku');

                // プレイヤー全体と映像の高さの差（レターボックス）から、コメント描画領域の高さを狭める必要があるかを判定する
                // 2で割っているのは単体の差を測るため
                if (this.resize_observer_element === null || this.resize_observer_element.clientHeight === null) return;
                if (video_element === null || video_element.clientHeight === null) return;
                const letter_box_height = (this.resize_observer_element.clientHeight - video_element.clientHeight) / 2;

                const threshold = Utils.isSmartphoneVertical() ? 0 : window.matchMedia('(max-height: 450px)').matches ? 50 : 66;
                if (letter_box_height < threshold) {

                    // コメント描画領域に必要な上下マージン
                    const comment_area_vertical_margin = (threshold - letter_box_height) * 2;

                    // 狭めるコメント描画領域の幅
                    // 映像の要素の幅をそのまま利用する
                    const comment_area_width = video_element.clientWidth;

                    // 狭めるコメント描画領域の高さ
                    const comment_area_height = video_element.clientHeight - comment_area_vertical_margin;

                    // 狭めるコメント描画領域のアスペクト比を求める
                    // https://tech.arc-one.jp/asepct-ratio/
                    const gcd = (x: number, y: number) => {  // 最大公約数を求める関数
                        if (y === 0) return x;
                        return gcd(y, x % y);
                    };
                    // 幅と高さの最大公約数を求める
                    const gcd_result = gcd(comment_area_width, comment_area_height);
                    // 幅と高さをそれぞれ最大公約数で割ってアスペクト比を算出
                    const comment_area_height_aspect = `${comment_area_width / gcd_result} / ${comment_area_height / gcd_result}`;

                    // 一時的に transition を無効化する
                    // アスペクト比の設定は連続して行われるが、その際に transition が適用されるとワンテンポ遅れたアニメーションになってしまう
                    comment_area_element.style.transition = 'none';

                    // コメント描画領域に算出したアスペクト比を設定する
                    comment_area_element.style.setProperty('--comment-area-aspect-ratio', comment_area_height_aspect);

                    // コメント描画領域に必要な上下マージンを設定する
                    comment_area_element.style.setProperty('--comment-area-vertical-margin', `${comment_area_vertical_margin}px`);

                    // 以前セットされた setTimeout() を止める
                    window.clearTimeout(animation_timeout_id);

                    // 0.2秒後に実行する
                    // 0.2秒より前にもう一度リサイズイベントが来た場合はタイマーがクリアされるため実行されない
                    window.setTimeout(() => {

                        // 再び transition を有効化する
                        comment_area_element.style.transition = '';

                    }, 0.2 * 1000);

                } else {

                    // コメント描画領域に設定したアスペクト比・上下マージンを削除する
                    comment_area_element.style.removeProperty('--comment-area-aspect-ratio');
                    comment_area_element.style.removeProperty('--comment-area-vertical-margin');
                }
            };

            // 要素の監視を開始
            this.resize_observer = new ResizeObserver(on_resize);
            this.resize_observer.observe(this.resize_observer_element);

            // 0.6 秒待ってから初回実行
            // チャンネル切り替え後、再初期化されたプレイヤーに適用するため（早いと再初期化前のプレイヤーに適用されてしまう）
            window.setTimeout(on_resize, 0.6 * 1000);
        },

        // ニコニコ実況に接続し、セッションを初期化する
        async initSession(player: DPlayer, channel_id: string) {

            // リサイズ時のイベントを初期化
            // イベントはプレイヤーの DOM に紐づいているため、プレイヤーが破棄→再初期化される毎に実行する必要がある
            this.initReserveObserver();

            // タブが非表示状態のときにコメントを格納する配列
            // タブが表示状態になったらコメントリストにのみ表示する（遅れているのでプレイヤーには表示しない）
            const comment_list_buffer: ICommentData[] = [];

            // コメントの最大保持数
            const max_comment_count = 500;

            // LiveCommentManager を初期化
            this.live_comment_manager = new LiveCommentManager(
                // DPlayer のインスタンス
                player,
                // チャンネル ID
                channel_id,

                // 初回の過去コメント (最大50件) を受信したときのコールバック
                async (initial_comments) => {

                    // コメントリストに一括で追加
                    this.comment_list.push(...initial_comments);

                    // コメントリストを一番下までスクロール
                    this.scrollCommentList();
                },

                // コメントを受信したときのコールバック
                // プレイヤーへの描画は LiveCommentManager が行う
                async (comment) => {

                    // タブが非表示状態のときは、バッファにコメントを追加するだけで終了する
                    // ここで追加すると、タブが表示状態になったときに一斉に描画されて大変なことになる
                    if (document.visibilityState === 'hidden') {
                        comment_list_buffer.push(comment);
                        return;
                    }

                    // コメントリストのコメント数が max_comment_count 件を超えたら、古いものから順に削除する
                    // 仮想スクロールとはいえ、さすがに max_comment_count 件を超えると重くなりそう
                    // 手動スクロール時は実行しない
                    if (this.comment_list.length >= max_comment_count && this.is_manual_scroll === false) {
                        this.comment_list.splice(0, Math.max(0, this.comment_list.length - max_comment_count));
                    }

                    // コメントリストに追加
                    this.comment_list.push(comment);

                    // コメントリストを一番下までスクロール
                    this.scrollCommentList();
                },
            );

            // タブが表示状態になったときのイベント
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
                    this.scrollCommentList();
                }
            };
            document.addEventListener('visibilitychange', this.visibilitychange_listener);

            // ニコニコ実況セッションを初期化する
            const result = await this.live_comment_manager.initSession();

            // ニコニコ実況セッションの初期化に失敗した
            // 初期化に失敗した際のエラーメッセージを保存しておく (エラー表示などで利用する)
            // プレイヤーへのエラー表示はすでに LiveCommentManager の方で行われているので、ここでは何もしない
            if (result.is_success === false) {
                this.initialize_failed_message = result.detail;
            }
        },

        // コメントを送信する
        sendComment(options: DPlayerType.APIBackendSendOptions) {

            // 初期化に失敗しているときは実行せず、保存しておいたエラーメッセージを表示する
            if (this.initialize_failed_message !== null) {
                options.error(this.initialize_failed_message);
                return;
            }

            // バリデーション
            if (this.userStore.user === null) {
                options.error('コメントするには、KonomiTV アカウントにログインしてください。');
                return;
            }
            if (this.userStore.user.niconico_user_id === null) {
                options.error('コメントするには、ニコニコアカウントと連携してください。');
                return;
            }
            if (this.userStore.user.niconico_user_premium === false && (options.data.type === 'top' || options.data.type === 'bottom')) {
                options.error('コメントを上下に固定するには、ニコニコアカウントのプレミアム会員登録が必要です。');
                return;
            }
            if (this.userStore.user.niconico_user_premium === false && options.data.size === 'big') {
                options.error('コメントサイズを大きめに設定するには、ニコニコアカウントのプレミアム会員登録が必要です。');
                return;
            }

            // ニコニコ実況のコメントサーバーにコメントを送信
            this.live_comment_manager.sendComment(options);
        },

        // ニコニコ実況セッションを破棄する
        destroy() {

            // タブの表示/非表示の状態が切り替わったときのイベントを削除
            if (this.visibilitychange_listener !== null) {
                document.removeEventListener('visibilitychange', this.visibilitychange_listener);
                this.visibilitychange_listener = null;
            }

            // LiveCommentManager を破棄
            if (this.live_comment_manager !== null) {
                this.live_comment_manager.destroy();
                this.live_comment_manager = null;
            }

            this.initialize_failed_message = null;
            this.comment_list = [];
        }
    }
});

</script>
<style lang="scss" scoped>

.comment-container {
    display: flex;
    flex-direction: column;

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
            background: var(--v-background-lighten3);
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
            padding-right: 10px;
            padding-bottom: 12px;
            overflow-y: scroll !important;
            @include tablet-vertical {
                padding-left: 24px;
                padding-right: 18px;
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
                word-break: break-all;
                &--my-post {
                    color: var(--v-secondary-lighten2);
                }

                &__text {
                    font-size: 13px;
                }

                &__time {
                    flex-shrink: 0;
                    margin-left: auto;
                    padding-left: 8px;
                    color: var(--v-text-darken1);
                    font-size: 13px;
                }

                &__icon {
                    width: 20px;
                    height: 20px;
                    margin-left: 8px;
                    border-radius: 5px;
                    color: var(--v-text-base);
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
                color: var(--v-text-darken1);
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
        background: var(--v-primary-base);
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