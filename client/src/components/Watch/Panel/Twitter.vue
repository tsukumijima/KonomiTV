<template>
    <div class="twitter-container">
        <div class="tab-container">
            <TwitterSearch :class="{'tab-content--active': playerStore.twitter_active_tab === 'Search'}" />
            <TwitterTimeline :class="{'tab-content--active': playerStore.twitter_active_tab === 'Timeline'}"
                :is-twitter-panel-visible="isTwitterPanelVisible" :is-timeline-tab-active="playerStore.twitter_active_tab === 'Timeline'" />
            <TwitterCaptures :class="{'tab-content--active': playerStore.twitter_active_tab === 'Capture'}" />
        </div>
        <div class="tab-button-container">
            <div v-ripple class="tab-button" :class="{'tab-button--active': playerStore.twitter_active_tab === 'Search'}"
                @click="playerStore.twitter_active_tab = 'Search'">
                <Icon icon="fluent:search-16-filled" height="18px" />
                <span class="tab-button__text">ツイート検索</span>
            </div>
            <div v-ripple class="tab-button" :class="{'tab-button--active': playerStore.twitter_active_tab === 'Timeline'}"
                @click="playerStore.twitter_active_tab = 'Timeline'">
                <Icon icon="fluent:home-16-regular" height="18px" />
                <span class="tab-button__text">タイムライン</span>
            </div>
            <div v-ripple class="tab-button" :class="{'tab-button--active': playerStore.twitter_active_tab === 'Capture'}"
                @click="playerStore.twitter_active_tab = 'Capture'">
                <Icon icon="fluent:image-copy-20-regular" height="18px" />
                <span class="tab-button__text">キャプチャ</span>
            </div>
        </div>
        <div class="tweet-form" :class="{
            'tweet-form--focused': is_tweet_hashtag_form_focused || is_tweet_text_form_focused,
            'tweet-form--virtual-keyboard-display': playerStore.is_virtual_keyboard_display &&
                (Utils.hasActiveElementClass('tweet-form__hashtag-form') || Utils.hasActiveElementClass('tweet-form__textarea')) &&
                (() => {is_hashtag_list_display = false; return true;})(),
        }">
            <div class="tweet-form__hashtag">
                <!-- input[type=search] を使っているのは autocomplete 避け目的のはず -->
                <input class="tweet-form__hashtag-form" type="search" enterkeyhint="done" placeholder="#ハッシュタグ" spellcheck="false"
                    v-model="tweet_hashtag" @input="updateTweetLetterCount()"
                    @focus="is_tweet_hashtag_form_focused = true" @blur="is_tweet_hashtag_form_focused = false"
                    @change="tweet_hashtag = formatHashtag(tweet_hashtag); updateTweetLetterCount()">
                <div v-ripple class="tweet-form__hashtag-list-button" @click="clickHashtagListButton()">
                    <Icon icon="fluent:clipboard-text-ltr-32-regular" height="22px" />
                </div>
            </div>
            <textarea class="tweet-form__textarea" enterkeyhint="enter" placeholder="ツイート" spellcheck="false" v-model="tweet_text" ref="tweet_text"
                @input="updateTweetLetterCount()"
                @paste="pasteClipboardData($event)"
                @focus="is_tweet_text_form_focused = true"
                @blur="is_tweet_text_form_focused = false">
            </textarea>
            <div class="tweet-form__control">
                <div v-ripple class="account-button" :class="{'account-button--no-login': !twitterStore.is_logged_in_twitter}"
                    @click="clickAccountButton()">
                    <img class="account-button__icon"
                        :src="twitterStore.is_logged_in_twitter ? twitterStore.selected_twitter_account?.icon_url : '/assets/images/account-icon-default.png'">
                    <span class="account-button__screen-name">
                        {{twitterStore.is_logged_in_twitter ? `@${twitterStore.selected_twitter_account?.screen_name}` : '連携されていません'}}
                    </span>
                    <Icon class="account-button__menu" icon="fluent:more-circle-20-regular" width="22px" />
                </div>
                <div class="limit-meter">
                    <div class="limit-meter__content" :class="{
                        'limit-meter__content--yellow': tweet_letter_remain_count <= 20,
                        'limit-meter__content--red': tweet_letter_remain_count <= 0,
                    }">
                        <Icon icon="fa-brands:twitter" width="12px" style="margin-right: -2px;" />
                        <span>{{tweet_letter_remain_count}}</span>
                    </div>
                    <div class="limit-meter__content">
                        <Icon icon="fluent:image-16-filled" width="14px" />
                        <span>{{playerStore.twitter_selected_capture_blobs.length}}/4</span>
                    </div>
                </div>
                <button class="tweet-button" v-ripple="Utils.isTouchDevice() === false" :disabled="is_tweet_button_disabled"
                    @click="sendTweet()" @touchstart="sendTweet()">
                    <Icon icon="fa-brands:twitter" height="16px" />
                    <span class="ml-1">ツイート</span>
                </button>
            </div>
        </div>
        <div class="hashtag-list" :class="{
            'hashtag-list--display': is_hashtag_list_display,
            'hashtag-list--virtual-keyboard-display': playerStore.is_virtual_keyboard_display && Utils.hasActiveElementClass('hashtag__input'),
        }">
            <div class="hashtag-heading">
                <div class="hashtag-heading__text">
                    <Icon icon="charm:hash" width="17px" />
                    <span class="ml-1">ハッシュタグリスト</span>
                </div>
                <button v-ripple class="hashtag-heading__add-button"
                    @click="saved_twitter_hashtags.push({id: Utils.time(), text: '#ここにハッシュタグを入力', editing: false})">
                    <Icon icon="fluent:add-12-filled" width="17px" />
                    <span class="ml-1">追加</span>
                </button>
            </div>
            <draggable class="hashtag-container" handle=".hashtag__sort-handle" item-key="id"
                v-model="saved_twitter_hashtags">
                <!-- スロットの仕様上、名前は element 固定なので注意 -->
                <template #item="{ element }: { element: IHashtag }">
                    <div v-ripple="!element.editing" class="hashtag" :class="{'hashtag--editing': element.editing}"
                        @click="clickHashtag(element)">
                        <!-- 以下では Icon コンポーネントを使うと個数が多いときに高負荷になるため、意図的に SVG を直書きしている -->
                        <!-- input[type=search] を使っているのは autocomplete 避け目的のはず -->
                        <input type="search" enterkeyhint="done" class="hashtag__input" spellcheck="false" v-model="element.text"
                            :disabled="!element.editing" @click.stop="">
                        <button v-ripple class="hashtag__edit-button"
                            @click.prevent.stop="element.editing = !element.editing;
                                element.text = formatHashtag(element.text, true); updateTweetLetterCount()">
                            <svg class="iconify iconify--fluent" width="17px" height="17px" viewBox="0 0 16 16"
                                v-if="element.editing === false">
                                <path fill="currentColor" d="M10.529 1.764a2.621 2.621 0 1 1 3.707 3.707l-.779.779L9.75 2.543l.779-.779ZM9.043 3.25L2.657 9.636a2.955 2.955 0 0 0-.772 1.354l-.87 3.386a.5.5 0 0 0 .61.608l3.385-.869a2.95 2.95 0 0 0 1.354-.772l6.386-6.386L9.043 3.25Z"></path>
                            </svg>
                            <svg class="iconify iconify--fluent" width="17px" height="17px" viewBox="0 0 16 16"
                                v-if="element.editing === true">
                                <path fill="currentColor" d="M14.046 3.486a.75.75 0 0 1-.032 1.06l-7.93 7.474a.85.85 0 0 1-1.188-.022l-2.68-2.72a.75.75 0 1 1 1.068-1.053l2.234 2.267l7.468-7.038a.75.75 0 0 1 1.06.032Z"></path>
                            </svg>
                        </button>
                        <button v-ripple class="hashtag__delete-button"
                            @click.prevent.stop="saved_twitter_hashtags.splice(saved_twitter_hashtags.indexOf(element), 1)">
                            <svg class="iconify iconify--fluent" width="17px" height="17px" viewBox="0 0 16 16">
                                <path fill="currentColor" d="M7 3h2a1 1 0 0 0-2 0ZM6 3a2 2 0 1 1 4 0h4a.5.5 0 0 1 0 1h-.564l-1.205 8.838A2.5 2.5 0 0 1 9.754 15H6.246a2.5 2.5 0 0 1-2.477-2.162L2.564 4H2a.5.5 0 0 1 0-1h4Zm1 3.5a.5.5 0 0 0-1 0v5a.5.5 0 0 0 1 0v-5ZM9.5 6a.5.5 0 0 0-.5.5v5a.5.5 0 0 0 1 0v-5a.5.5 0 0 0-.5-.5Z"></path>
                            </svg>
                        </button>
                        <div class="hashtag__sort-handle">
                            <svg class="iconify iconify--material-symbols" width="17px" height="17px" viewBox="0 0 24 24">
                                <path fill="currentColor" d="M5 15q-.425 0-.713-.288T4 14q0-.425.288-.713T5 13h14q.425 0 .713.288T20 14q0 .425-.288.713T19 15H5Zm0-4q-.425 0-.713-.288T4 10q0-.425.288-.713T5 9h14q.425 0 .713.288T20 10q0 .425-.288.713T19 11H5Z"></path>
                            </svg>
                        </div>
                    </div>
                </template>
            </draggable>
        </div>
        <div class="twitter-account-list" :class="{'twitter-account-list--display': is_twitter_account_list_display}">
            <div v-ripple class="twitter-account" v-for="twitter_account in userStore.user ? userStore.user.twitter_accounts : []"
                :key="twitter_account.id" @click="updateSelectedTwitterAccount(twitter_account)">
                <!-- 以下では Icon コンポーネントを使うと個数が多いときに高負荷になるため、意図的に SVG を直書きしている -->
                <img class="twitter-account__icon" :src="twitter_account.icon_url">
                <div class="twitter-account__info">
                    <div class="twitter-account__name">{{twitter_account.name}}</div>
                    <div class="twitter-account__screen-name">@{{twitter_account.screen_name}}</div>
                </div>
                <svg class="twitter-account__check iconify iconify--fluent" width="24px" height="24px" viewBox="0 0 16 16"
                    v-show="twitter_account.id === settingsStore.settings.selected_twitter_account_id">
                    <path fill="currentColor" d="M14.046 3.486a.75.75 0 0 1-.032 1.06l-7.93 7.474a.85.85 0 0 1-1.188-.022l-2.68-2.72a.75.75 0 1 1 1.068-1.053l2.234 2.267l7.468-7.038a.75.75 0 0 1 1.06.032Z"></path>
                </svg>
            </div>
        </div>
    </div>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent, PropType } from 'vue';
import draggable from 'vuedraggable';

import TwitterCaptures from '@/components/Watch/Panel/Twitter/Captures.vue';
import TwitterSearch from '@/components/Watch/Panel/Twitter/Search.vue';
import TwitterTimeline from '@/components/Watch/Panel/Twitter/Timeline.vue';
import { IProgram } from '@/services/Programs';
import Twitter from '@/services/Twitter';
import { ITwitterAccount } from '@/services/Users';
import useChannelsStore from '@/stores/ChannelsStore';
import usePlayerStore from '@/stores/PlayerStore';
import useSettingsStore from '@/stores/SettingsStore';
import useTwitterStore from '@/stores/TwitterStore';
import useUserStore from '@/stores/UserStore';
import Utils, { ChannelUtils } from '@/utils';

// このコンポーネント内でのキャプチャのインターフェイス
export interface ITweetCapture {
    blob: Blob;
    filename: string;
    image_url: string;
    selected: boolean;
    focused: boolean;
}

// このコンポーネント内でのハッシュタグのインターフェイス
interface IHashtag {
    id: number;
    text: string;
    editing: boolean;
}

export default defineComponent({
    name: 'Panel-TwitterTab',
    components: {
        draggable,
        TwitterCaptures,
        TwitterSearch,
        TwitterTimeline,
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

            // 連携している Twitter アカウントリストを表示しているか
            is_twitter_account_list_display: false,

            // 保存している Twitter のハッシュタグが入るリスト
            saved_twitter_hashtags: useSettingsStore().settings.saved_twitter_hashtags.map((hashtag, index) => {
                // id プロパティは :key="" に指定するためにつける ID (ミリ秒単位のタイムスタンプ + index で適当に一意になるように)
                return {id: Utils.time() + index, text: hashtag, editing: false} as IHashtag;
            }),

            // ハッシュタグリストを表示しているか
            is_hashtag_list_display: false,

            // キャプチャリストの要素
            captures_element: null as HTMLDivElement | null,

            // ツイートハッシュタグフォームにフォーカスしているか
            is_tweet_hashtag_form_focused: false,

            // ツイート本文フォームにフォーカスしているか
            is_tweet_text_form_focused: false,

            // ツイートのハッシュタグ
            tweet_hashtag: '',

            // ツイート本文
            tweet_text: '',

            // 140 文字から引いた残りの文字数カウント
            tweet_letter_remain_count: 140,

            // ツイートを送信中か (API リクエストを実行するまで)
            is_tweet_sending: false,

            // Twitter パネル表示中に Keep-Alive API を叩くための interval ID
            twitter_keep_alive_interval_id: null as number | null,
        };
    },
    computed: {
        ...mapStores(useChannelsStore, usePlayerStore, useSettingsStore, useUserStore, useTwitterStore),

        // ツイートボタンが無効かどうか
        is_tweet_button_disabled(): boolean {
            return this.twitterStore.is_logged_in_twitter === false || this.tweet_letter_remain_count < 0 ||
                ((this.tweet_text.trim() === '' || this.tweet_letter_remain_count === 140) && this.playerStore.twitter_selected_capture_blobs.length === 0);
        },

        // パネルで Twitter タブが表示されているかどうか
        isTwitterPanelVisible(): boolean {
            if (this.playback_mode === 'Live') {
                return this.playerStore.tv_panel_active_tab === 'Twitter';
            } else {
                return this.playerStore.video_panel_active_tab === 'Twitter';
            }
        },

        // Keep-Alive API を送るべき状態かどうか
        shouldTwitterKeepAlive(): boolean {
            // 選択されている Twitter アカウントが存在しない場合は Keep-Alive を送らない
            if (this.twitterStore.selected_twitter_account === null) {
                return false;
            }
            // パネルが表示されていない場合は Keep-Alive を送らない
            if (this.isTwitterPanelVisible === false) {
                return false;
            }
            // 選択されている Twitter アカウントで一度でも API 呼び出しが行われている場合には Keep-Alive を送る
            const screen_name = this.twitterStore.selected_twitter_account.screen_name;
            return this.twitterStore.account_api_activity[screen_name] === true;
        },
    },
    watch: {

        // ライブ視聴のみ: ChannelsStore の channel.current.name の変更を監視する
        // 現在視聴中のチャンネルが変更されたときに局タグを自動で更新する
        'channelsStore.channel.current.name': {
            handler(new_channel_name: string, old_channel_name: string) {
                if (this.playback_mode === 'Live') {
                    const old_channel_hashtag = ChannelUtils.getChannelHashtag(old_channel_name) ?? '';
                    this.tweet_hashtag = this.formatHashtag(this.tweet_hashtag.replaceAll(old_channel_hashtag, ''));
                    this.updateTweetLetterCount();
                    // 「番組が切り替わったときにハッシュタグフォームをリセットする」がオンなら、ハッシュタグフォームを空にする
                    if (this.settingsStore.settings.reset_hashtag_when_program_switches === true) {
                        this.tweet_hashtag = this.formatHashtag('');
                        this.updateTweetLetterCount();
                    }
                }
            }
        },

        // ライブ視聴のみ: ChannelsStore の channel.current.program_present の変更を監視する
        // 現在視聴中の番組が変更されたときに局タグを自動で更新する
        'channelsStore.channel.current.program_present': {
            deep: true,  // ネストされたプロパティの変更も監視する
            handler(new_program: IProgram | null, old_program: IProgram | null) {
                if (this.playback_mode === 'Live') {
                    // NID-SID-EID の組が変わったときのみ更新する
                    if (new_program?.id !== old_program?.id) {
                        // 「番組が切り替わったときにハッシュタグフォームをリセットする」がオンなら、ハッシュタグフォームを空にする
                        if (this.settingsStore.settings.reset_hashtag_when_program_switches === true) {
                            this.tweet_hashtag = this.formatHashtag('');
                            this.updateTweetLetterCount();
                        }
                    }
                }
            }
        },

        // 保存しているハッシュタグが変更されたら随時 LocalStorage に保存する
        saved_twitter_hashtags: {
            deep: true,
            handler() {
                this.settingsStore.settings.saved_twitter_hashtags = this.saved_twitter_hashtags.map(hashtag => hashtag.text);
            }
        },

        // Keep-Alive の対象状態が変化したらタイマーを制御する
        shouldTwitterKeepAlive: {
            immediate: true,
            handler(is_active: boolean) {
                if (is_active === true) {
                    this.startTwitterKeepAliveTimer();
                } else {
                    this.stopTwitterKeepAliveTimer();
                }
            },
        },
    },
    async created() {

        // アカウント情報を更新
        await this.userStore.fetchUser();

        // Twitter 関連の状態を一括更新
        await this.twitterStore.update();

        // 局タグ追加処理を走らせる (ハッシュタグフォームのフォーマット処理も同時に行われるが、元々空なので無意味)
        this.tweet_hashtag = this.formatHashtag(this.tweet_hashtag);
        this.updateTweetLetterCount();

        // CaptureManager からキャプチャを受け取るイベントハンドラーを登録
        // 非同期関数で登録することで、CaptureManager でキャプチャの登録完了を待たずに処理を続行できるはず
        this.playerStore.event_emitter.on('CaptureCompleted', async (event) => {
            this.addCaptureList(event.capture, event.filename);
        });
    },
    beforeUnmount() {

        // 終了前にすべてのキャプチャの Blob URL を revoke してリソースを解放する
        for (const capture of this.playerStore.twitter_captures) {
            URL.revokeObjectURL(capture.image_url);
        }

        // CaptureManager からキャプチャを受け取るイベントハンドラーを削除
        this.playerStore.event_emitter.off('CaptureCompleted');  // CaptureCompleted イベントの全てのイベントハンドラーを削除

        // Keep-Alive API を叩くタイマーを停止する
        this.stopTwitterKeepAliveTimer();
    },
    methods: {

        // 文字数カウントを変更するイベント
        updateTweetLetterCount() {

            // サロゲートペアを考慮し、スプレッド演算子で一度配列化してから数えている
            // ref: https://qiita.com/suin/items/3da4fb016728c024eaca
            this.tweet_letter_remain_count = 140 - [...this.tweet_hashtag].length - [...this.tweet_text].length;
        },

        // クリップボード内のデータがペーストされたときのイベント
        pasteClipboardData(event: ClipboardEvent) {
            if (event.clipboardData === null) return;

            // 一応配列になっているので回しているが、基本1回のペーストにつき DataTransferItem は1個しか入らない
            for (const clipboard_item of event.clipboardData.items) {

                // 画像のみを対象にする (DataTransferItem.type には MIME タイプが入る)
                if (clipboard_item.type.startsWith('image/')) {

                    // クリップボード内の画像データを File オブジェクトとして取得し、キャプチャリストに追加
                    const file = clipboard_item.getAsFile();
                    if (file) {
                        this.addCaptureList(file, file.name);
                    }
                }
            }
        },

        // ハッシュタグリストボタンが押されたときのイベント
        clickHashtagListButton() {
            this.is_hashtag_list_display = !this.is_hashtag_list_display;
            // すべてのハッシュタグの編集状態を解除する
            for (const hashtag of this.saved_twitter_hashtags) {
                hashtag.editing = false;
            }
        },

        // ハッシュタグがクリックされたときのイベント
        clickHashtag(hashtag: IHashtag) {
            this.tweet_hashtag = hashtag.text;
            this.tweet_hashtag = this.formatHashtag(this.tweet_hashtag);
            this.updateTweetLetterCount();
            window.setTimeout(() => this.is_hashtag_list_display = false, 150);
        },

        // アカウントボタンが押されたときのイベント
        clickAccountButton() {

            // Twitter アカウントが連携されていない場合は Twitter 設定画面に飛ばす
            if (!this.twitterStore.is_logged_in_twitter) {

                // 視聴画面以外に遷移するため、フルスクリーンを解除しないと画面が崩れる
                if (document.fullscreenElement) {
                    document.exitFullscreen();
                }

                this.$router.push({path: '/settings/twitter'});
                return;
            }

            // アカウントリストの表示/非表示を切り替え
            this.is_twitter_account_list_display = !this.is_twitter_account_list_display;

            // アカウントリストが表示されているなら、ハッシュタグリストを非表示にする
            if (this.is_twitter_account_list_display === true) {
                this.is_hashtag_list_display = false;
            }
        },

        // 選択されている Twitter アカウントを更新する
        updateSelectedTwitterAccount(twitter_account: ITwitterAccount) {
            this.settingsStore.settings.selected_twitter_account_id = twitter_account.id;
            this.twitterStore.selected_twitter_account = twitter_account;
            // アカウント切り替え時は API アクティビティをリセットして、不要な Keep-Alive を抑止する
            this.twitterStore.resetAccountAPIActivity(twitter_account.screen_name);

            // Twitter アカウントリストのオーバーレイを閉じる (少し待ってから閉じたほうが体感が良い)
            window.setTimeout(() => this.is_twitter_account_list_display = false, 150);
        },

        // Twitter パネルが表示されている間は一定間隔で Keep-Alive API を叩く
        startTwitterKeepAliveTimer() {
            if (this.twitter_keep_alive_interval_id !== null) {
                return;
            }
            void this.pingTwitterKeepAlive();
            this.twitter_keep_alive_interval_id = window.setInterval(() => {
                void this.pingTwitterKeepAlive();
            }, 10 * 1000);
        },

        // Twitter パネルの Keep-Alive タイマーを停止する
        stopTwitterKeepAliveTimer() {
            if (this.twitter_keep_alive_interval_id !== null) {
                window.clearInterval(this.twitter_keep_alive_interval_id);
                this.twitter_keep_alive_interval_id = null;
            }
        },

        // TwitterScrapeBrowser の Keep-Alive API を呼び出す
        async pingTwitterKeepAlive() {
            if (this.twitterStore.selected_twitter_account === null) return;
            await Twitter.keepAlive(this.twitterStore.selected_twitter_account.screen_name);
        },

        // 撮ったキャプチャをキャプチャタブのキャプチャリストに追加する
        addCaptureList(blob: Blob, filename: string) {

            if (this.captures_element === null) {
                this.captures_element = document.querySelector('.tab-content--capture')!;
            }

            // 撮ったキャプチャが 100 枚を超えていたら、重くなるので古いものから削除する
            // 削除する前に Blob URL を revoke してリソースを解放するのがポイント
            if (this.playerStore.twitter_captures.length > 100) {
                URL.revokeObjectURL(this.playerStore.twitter_captures[0].image_url);
                this.playerStore.twitter_selected_capture_blobs = this.playerStore.twitter_selected_capture_blobs.filter(blob => {
                    return blob !== this.playerStore.twitter_captures[0].blob;
                });
                this.playerStore.twitter_captures.shift();
            }

            // キャプチャリストにキャプチャを追加
            const blob_url = URL.createObjectURL(blob);
            this.playerStore.twitter_captures.push({
                blob: blob,
                filename: filename,
                image_url: blob_url,
                selected: false,
                focused: false,
            });

            // キャプチャリストを下にスクロール
            // this.$nextTick() のコールバックで DOM の更新を待つ
            this.$nextTick(() => {
                if (this.captures_element === null) return;
                this.captures_element.scrollTo({
                    top: this.captures_element.scrollHeight,
                    behavior: 'smooth',
                });
            });
        },

        // 撮ったキャプチャに番組タイトルの透かしを描画する
        async drawProgramTitleOnCapture(capture: Blob): Promise<Blob> {

            // キャプチャの Blob を createImageBitmap() で Canvas に描ける ImageBitmap に変換
            const image_bitmap = await createImageBitmap(capture);

            // OffscreenCanvas が使えるなら使う (OffscreenCanvas の方がパフォーマンスが良い)
            const canvas = ('OffscreenCanvas' in window) ?
                new OffscreenCanvas(image_bitmap.width, image_bitmap.height) : document.createElement('canvas');

            // Canvas にキャプチャを描画
            const context = canvas.getContext('2d', {
                alpha: false,
                desynchronized: true,
                willReadFrequently: false,
            }) as OffscreenCanvasRenderingContext2D | CanvasRenderingContext2D;
            context.drawImage(image_bitmap, 0, 0);
            image_bitmap.close();

            // 描画設定
            context.font = 'bold 22px "Open Sans", "YakuHanJPs", "Twemoji", "Hiragino Sans", "Noto Sans JP", sans-serif'; // フォント
            context.fillStyle = 'rgba(255, 255, 255, 70%)';  // 半透明の白
            context.shadowColor = 'rgba(0, 0, 0, 100%)';  // 影の色
            context.shadowBlur = 4;  // 影をぼかすしきい値
            context.shadowOffsetX = 0;  // 影のX座標
            context.shadowOffsetY = 0;  // 影のY座標

            // 現在視聴中の番組タイトルを取得
            let title;
            if (this.playback_mode === 'Live') {
                title = this.channelsStore.channel.current.program_present?.title ?? '放送休止';
            } else {
                title = this.playerStore.recorded_program.title;
            }

            // 番組タイトルの透かしを描画
            switch (this.settingsStore.settings.tweet_capture_watermark_position) {
                case 'TopLeft': {
                    context.textAlign = 'left'; // 左寄せ
                    context.textBaseline = 'top'; // ベースラインを上寄せ
                    context.fillText(title, 16, 12);
                    break;
                }
                case 'TopRight': {
                    context.textAlign = 'right'; // 右寄せ
                    context.textBaseline = 'top'; // ベースラインを上寄せ
                    context.fillText(title, canvas.width - 16, 12);
                    break;
                }
                case 'BottomLeft': {
                    context.textAlign = 'left'; // 左寄せ
                    context.textBaseline = 'bottom'; // ベースラインを下寄せ
                    context.fillText(title, 16, canvas.height - 12);
                    break;
                }
                case 'BottomRight': {
                    context.textAlign = 'right'; // 右寄せ
                    context.textBaseline = 'bottom'; // ベースラインを下寄せ
                    context.fillText(title, canvas.width - 16, canvas.height - 12);
                    break;
                }
            }

            // Blob にして返す
            if (canvas instanceof OffscreenCanvas) {
                return await canvas.convertToBlob({type: 'image/jpeg', quality: 1});
            } else {
                return new Promise((resolve, reject) => canvas.toBlob(blob => {
                    if (blob === null) {
                        reject();
                    } else {
                        resolve(blob);
                    }
                }, 'image/jpeg', 1));
            }
        },

        // ハッシュタグを整形（余計なスペースなどを削り、全角ハッシュを半角ハッシュへ、全角スペースを半角スペースに置換）
        formatHashtag(tweet_hashtag: string, from_hashtag_list: boolean = false): string {

            // ハッシュとスペースの表記ゆれを統一し、連続するハッシュやスペースを1つにする
            const tweet_hashtag_array = tweet_hashtag.trim()
                .replaceAll('♯', '#').replaceAll('＃', '#').replace(/#{2,}/g, '#').replaceAll('　', ' ').replaceAll(/ +/g,' ').split(' ')
                .filter(hashtag => hashtag !== '');

            // ハッシュタグがついてない場合にハッシュタグを付与
            for (let index in tweet_hashtag_array) {
                if (!tweet_hashtag_array[index].startsWith('#')) {
                    tweet_hashtag_array[index] = `#${tweet_hashtag_array[index]}`;
                }
            }

            // ライブ視聴: 設定でオンになっている場合のみ、視聴中チャンネルの局タグを自動で追加する (ハッシュタグリスト内のハッシュタグは除外)
            // ビデオ視聴ではリアルタイム実況ではないので追加しない
            if (this.playback_mode === 'Live') {
                if (this.settingsStore.settings.auto_add_watching_channel_hashtag === true && from_hashtag_list === false) {
                    const channel_hashtag = ChannelUtils.getChannelHashtag(this.channelsStore.channel.current.name);
                    if (channel_hashtag !== null) {
                        if (tweet_hashtag_array.includes(channel_hashtag) === false) {
                            tweet_hashtag_array.push(channel_hashtag);
                        }
                    }
                }
            }

            return tweet_hashtag_array.join(' ');
        },

        // ツイートを送信する
        async sendTweet() {

            // ツイートボタンが無効なら何もしない
            if (this.is_tweet_button_disabled === true) return;

            // Twitter アカウントが連携されていない場合は何もしない
            if (this.twitterStore.selected_twitter_account === null) return;

            // 送信中フラグを立てる (重複送信防止)
            if (this.is_tweet_sending === true) return;
            this.is_tweet_sending = true;

            // ハッシュタグを整形
            this.tweet_hashtag = this.formatHashtag(this.tweet_hashtag);
            const tweet_hashtag = this.tweet_hashtag;
            this.updateTweetLetterCount();

            // 実際に送るツイート本文を作成
            let tweet_text = this.tweet_text;
            if (tweet_hashtag !== '') {  // ハッシュタグが入力されているときのみ
                switch (this.settingsStore.settings.tweet_hashtag_position) {
                    // ツイート本文の前に追加する
                    case 'Prepend': {
                        tweet_text = `${tweet_hashtag} ${this.tweet_text}`;
                        break;
                    }
                    // ツイート本文の後に追加する
                    case 'Append': {
                        tweet_text = `${this.tweet_text} ${tweet_hashtag}`;
                        break;
                    }
                    // ツイート本文の前に追加してから改行する
                    case 'PrependWithLineBreak': {
                        tweet_text = `${tweet_hashtag}\n${this.tweet_text}`;
                        break;
                    }
                    // ツイート本文の後に改行してから追加する
                    case 'AppendWithLineBreak': {
                        tweet_text = `${this.tweet_text}\n${tweet_hashtag}`;
                        break;
                    }
                }
            }

            // キャプチャへの透かしの描画がオンの場合、キャプチャの Blob を透かし付きのものに差し替える
            const tweet_capture_blobs: Blob[] = [];
            for (let tweet_capture_blob of this.playerStore.twitter_selected_capture_blobs) {
                if (this.settingsStore.settings.tweet_capture_watermark_position !== 'None') {
                    tweet_capture_blob = await this.drawProgramTitleOnCapture(tweet_capture_blob);
                }
                tweet_capture_blobs.push(tweet_capture_blob);
            }

            // 連投防止のため、フォーム上のツイート本文・キャプチャの選択・キャプチャのフォーカスを消去
            // 送信した感を出す意味合いもある
            this.tweet_text = '';
            this.updateTweetLetterCount();
            for (const capture of this.playerStore.twitter_captures) {
                capture.selected = false;
                capture.focused = false;
            }
            this.playerStore.twitter_selected_capture_blobs = [];

            // ツイート送信 API にリクエスト
            // レスポンスは待たない
            Twitter.sendTweet(this.twitterStore.selected_twitter_account.screen_name, tweet_text, tweet_capture_blobs).then((result) => {
                this.playerStore.event_emitter.emit('SendNotification', {
                    message: result.message,
                    color: result.is_error ? '#FF6F6A' : undefined,
                });
            });

            // 送信中フラグを下ろす
            this.is_tweet_sending = false;

            // パネルを閉じる
            if (this.settingsStore.settings.fold_panel_after_sending_tweet === true) {
                this.playerStore.is_panel_display = false;
                (this.$refs.tweet_text as HTMLTextAreaElement).blur();  // フォーカスを外す
            }
        },
    }
});

</script>
<style lang="scss" scoped>

.twitter-container {
    display: flex;
    flex-direction: column;
    position: relative;
    padding-bottom: 8px;
    @include tablet-vertical {
        padding-bottom: 0px;
    }
    @include smartphone-vertical {
        padding-bottom: 0px;
    }
    &.watch-panel__content--active {
        content-visibility: visible !important;
    }
    &.watch-panel__content--active .tab-container .tab-content--active {
        opacity: 1;
        visibility: visible;
        z-index: 10;
        @media (hover: none) {
            content-visibility: auto;
        }
    }

    .tab-container {
        position: relative;
        flex-grow: 1;
        min-height: 0;  // magic!

        .tab-content {
            position: absolute;
            width: 100%;
            height: 100%;
            transition: opacity 0.2s, visibility 0.2s;
            opacity: 0;
            visibility: hidden;
            overflow-y: scroll;
            outline: none;
            &::-webkit-scrollbar {
                width: 6px;
            }

            // スマホ・タブレット (タッチデバイス) ではアニメーションが重めなので、アニメーションを無効化
            // アクティブなタブ以外は明示的に描画しない
            @media (hover: none) {
                transition: none;
                content-visibility: hidden;
            }
        }
    }

    .tab-button-container {
        display: flex;
        flex-shrink: 0;
        column-gap: 7px;
        height: 40px;
        margin-left: 12px;
        margin-right: 12px;
        padding-top: 8px;
        padding-bottom: 6px;
        @include tablet-vertical {
            height: 40px;
            margin-left: 24px;
            margin-right: 24px;
        }
        @include smartphone-horizontal {
            height: 38px;
            margin-left: 8px;
            margin-right: 8px;
        }
        @include smartphone-vertical {
            height: 38px;
        }

        .tab-button {
            display: flex;
            align-items: center;
            justify-content: center;
            flex: 1;
            background: rgb(var(--v-theme-background-lighten-2));
            border-radius: 7px;
            font-size: 11px;
            transition: background-color 0.15s ease;
            user-select: none;
            cursor: pointer;
            @include tablet-vertical {
                font-size: 11.5px;
                border-radius: 7px;
            }
            @include smartphone-horizontal {
                font-size: 10.5px;
                border-radius: 6px;
            }
            @include smartphone-vertical {
                font-size: 10.5px;
                border-radius: 6px;
            }
            &--active {
                background: rgb(var(--v-theme-twitter));
            }

            &__text {
                margin-left: 4px;
                margin-right: 2px;
                line-height: 2;
            }
        }
    }

    .tweet-form {
        display: flex;
        position: relative;
        flex-direction: column;
        flex-shrink: 0;
        height: 136px;
        margin-left: 12px;
        margin-right: 12px;
        border-radius: 12px;
        border-bottom-left-radius: 7px;
        border-bottom-right-radius: 7px;
        background: rgb(var(--v-theme-background-lighten-1));
        transition: box-shadow 0.09s ease;
        @include tablet-vertical {
            margin-left: 24px;
            margin-right: 24px;
        }
        @include smartphone-horizontal {
            height: 96px;
            margin-left: 8px;
            margin-right: 8px;
            border-radius: 6px;
            border-bottom-left-radius: 5px;
            border-bottom-right-radius: 5px;
        }
        @include smartphone-vertical {
            height: 96px;
            border-radius: 6px;
            border-bottom-left-radius: 5px;
            border-bottom-right-radius: 5px;
        }

        &--focused {
            box-shadow: rgba(79, 130, 230, 60%) 0 0 0 3.5px;
        }

        &--virtual-keyboard-display {
            position: relative;
            bottom: calc(env(keyboard-inset-height, 0px) - 77px);
            z-index: 20;
            @include tablet-vertical {
                bottom: calc(env(keyboard-inset-height, 0px) - 40px) !important;
            }
            @include smartphone-horizontal {
                bottom: calc(env(keyboard-inset-height, 0px) - 34px);
            }
            @include smartphone-vertical {
                bottom: calc(env(keyboard-inset-height, 0px) - 40px) !important;
            }
        }

        &__hashtag {
            display: block;
            position: relative;
            height: 19px;
            margin-top: 12px;
            margin-left: 12px;
            margin-right: 12px;
            @include smartphone-horizontal {
                height: 16px;
                margin-top: 8px;
            }
            @include smartphone-vertical {
                height: 16px;
                margin-top: 8px;
            }

            &-form {
                display: block;
                width: calc(100% - 24px);
                height: 100%;
                flex-grow: 1;
                font-size: 12.5px;
                color: rgb(var(--v-theme-twitter-lighten-2));
                outline: none;
                @include smartphone-horizontal {
                    width: calc(100% - 22px);
                    font-size: 12px;
                }
                @include smartphone-vertical {
                    width: calc(100% - 22px);
                    font-size: 12px;
                }
                // iOS Safari でフォーカス時にズームされる問題への対処
                @supports (-webkit-touch-callout: none) {
                    @include smartphone-horizontal {
                        width: calc(100% * 1.333 - 32px);
                        height: calc(16px * 1.333 + 4px);
                        font-size: 16px;
                        transform: scale(0.75);
                        transform-origin: 0 0;
                    }
                    @include smartphone-vertical {
                        width: calc(100% * 1.333 - 32px);
                        height: calc(16px * 1.333 + 4px);
                        font-size: 16px;
                        transform: scale(0.75);
                        transform-origin: 0 0;
                    }
                }
                &::placeholder {
                    color: rgba(65, 165, 241, 60%);
                }
            }
            &-list-button {
                display: flex;
                position: absolute;
                align-items: center;
                justify-content: center;
                top: -8px;
                right: -8px;
                width: 34px;
                height: 34px;
                padding: 6px;
                border-radius: 50%;
                color: rgb(var(--v-theme-twitter-lighten-2));
                cursor: pointer;
                @include smartphone-horizontal {
                    right: -11px;
                }
                @include smartphone-vertical {
                    right: -11px;
                }
            }
        }

        &__textarea {
            display: block;
            flex-grow: 1;
            margin-top: 8px;
            margin-left: 12px;
            margin-right: 12px;
            font-size: 12.5px;
            color: rgb(var(--v-theme-text));
            word-break: break-word;
            resize: none;
            outline: none;
            @include smartphone-horizontal {
                margin-top: 6px;
                font-size: 12px;
            }
            @include smartphone-vertical {
                margin-top: 6px;
                font-size: 12px;
            }
            // iOS Safari でフォーカス時にズームされる問題への対処
            @supports (-webkit-touch-callout: none) {
                @include smartphone-horizontal {
                    position: absolute;
                    top: 24px;
                    left: -2px;
                    min-width: calc(100% * 1.28 - 25px);
                    min-height: 34px;
                    font-size: 16px;
                    transform: scale(0.78125);
                    transform-origin: 0 0;
                }
                @include smartphone-vertical {
                    position: absolute;
                    top: 24px;
                    left: -2px;
                    min-width: calc(100% * 1.28 - 25px);
                    min-height: 34px;
                    font-size: 16px;
                    transform: scale(0.78125);
                    transform-origin: 0 0;
                }
            }
            &::placeholder {
                color: rgb(var(--v-theme-text-darken-2));
            }
        }

        &__control {
            display: flex;
            align-items: center;
            height: 32px;
            margin-top: 6px;
            @include smartphone-horizontal {
                height: 26px;
            }
            @include smartphone-vertical {
                height: 26px;
            }
            // iOS Safari でフォーカス時にズームされる問題への対処…の副作用の対処
            @supports (-webkit-touch-callout: none) {
                @include smartphone-horizontal {
                    margin-top: auto;
                }
                @include smartphone-vertical {
                    margin-top: auto;
                }
            }

            .account-button {
                display: flex;
                align-items: center;
                width: 183px;
                height: 100%;
                border-radius: 7px;
                font-size: 13px;
                color: rgb(var(--v-theme-text));
                background: rgb(var(--v-theme-background-lighten-2));
                user-select: none;
                cursor: pointer;
                @include tablet-vertical {
                    width: 200px;
                    border-radius: 5px;
                    font-size: 11.5px;
                }
                @include smartphone-horizontal {
                    width: 156px;
                    border-radius: 5px;
                    font-size: 11px;
                }
                @include smartphone-vertical {
                    width: auto;
                    flex-grow: 1;
                    border-radius: 5px;
                    font-size: 11.5px;
                }
                &--no-login {
                    .account-button__screen-name {
                        font-weight: 500;
                    }
                    .account-button__menu {
                        display: none;
                    }
                }

                &__icon {
                    display: block;
                    width: 32px;
                    height: 100%;
                    border-radius: 7px;
                    // 読み込まれるまでのアイコンの背景
                    background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
                    @include smartphone-horizontal {
                        width: 26px;
                    }
                    @include smartphone-vertical {
                        width: 26px;
                    }
                }
                &__screen-name {
                    flex-grow: 1;
                    line-height: 2;
                    text-align: center;
                    font-weight: bold;
                }
                &__menu {
                    margin-right: 4px;
                }
            }

            .limit-meter {
                display: flex;
                align-items: center;
                justify-content: center;
                flex-direction: column;
                flex-grow: 1;
                row-gap: 0.5px;
                font-size: 10px;
                color: rgb(var(--v-theme-text-darken-1));
                user-select: none;
                @include tablet-vertical {
                    flex-grow: 1;
                    flex-direction: row;
                    width: auto;
                }
                @include smartphone-horizontal {
                    font-size: 9px;
                }
                @include smartphone-vertical {
                    flex-grow: unset;
                    flex-direction: row;
                    width: 88px;
                }

                &__content {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    &:nth-child(2) {
                        @include tablet-vertical {
                            margin-left: 28px;
                            padding-right: 3px;
                        }
                        @include smartphone-horizontal {
                            margin-top: -2.5px;
                        }
                        @include smartphone-vertical {
                            margin-left: 6px;
                        }
                    }
                    svg {
                        width: 14px;
                        @include tablet-vertical {
                            width: 16px;
                            height: 16px;
                        }
                    }
                    span {
                        width: 16px;
                        margin-left: 5px;
                        text-align: center;
                        font-weight: bold;
                        @include tablet-vertical {
                            width: 25px;
                            margin-left: 8px;
                            font-size: 15px;
                        }
                    }
                    &--yellow {
                        color: rgb(var(--v-theme-warning));
                    }
                    &--red {
                        color: rgb(var(--v-theme-error));
                    }
                }
            }

            .tweet-button {
                display: flex;
                align-items: center;
                justify-content: center;
                width: 94px;
                height: 100%;
                border-radius: 7px;
                font-size: 12.5px;
                line-height: 2;
                color: rgb(var(--v-theme-text));
                background: rgb(var(--v-theme-twitter));
                user-select: none;
                outline: none;
                cursor: pointer;
                @include tablet-vertical {
                    width: 200px;
                    border-radius: 5px;
                    font-size: 11.8px;
                }
                @include smartphone-horizontal {
                    width: 86px;
                    border-radius: 5px;
                    font-size: 11.8px;
                }
                @include smartphone-vertical {
                    width: 100px;
                    border-radius: 5px;
                    font-size: 11.8px;
                }

                &[disabled] {
                    opacity: 0.6;
                    cursor: auto;
                    // スマホでクリック時の波紋が発動しないようにする
                    pointer-events: none;
                }
            }
        }
    }

    .hashtag-list {
        position: absolute;
        left: 12px;
        right: 12px;
        bottom: 149px;
        max-height: calc(100vh - 239px);
        max-height: calc(100dvh - 239px);
        padding: 12px 4px;
        padding-bottom: 10px;
        border-radius: 7px;
        // スクロールバーが表示されると角が丸くなくなる問題への対処
        clip-path: inset(0% 0% 0% 0% round 7px);
        background: rgb(var(--v-theme-background-lighten-2));
        box-shadow: 0px 3px 4px rgba(0, 0, 0, 53%);
        transition: opacity 0.15s ease, visibility 0.15s ease;
        opacity: 0;
        visibility: hidden;
        overflow-y: auto;
        z-index: 20;
        @include tablet-vertical {
            left: 24px;
            right: 24px;
            bottom: 142px;
            max-height: calc(100% - 158px);
        }
        @include smartphone-horizontal {
            left: 8px;
            right: 8px;
            bottom: 110px;
            max-height: calc(100vh - 152px);
            max-height: calc(100dvh - 152px);
            padding: 6px 4px;
            border-radius: 6px;
            clip-path: inset(0% 0% 0% 0% round 6px);
        }
        @include smartphone-vertical {
            bottom: 102px;
            max-height: calc(100% - 110px);
            padding: 8px 4px;
            border-radius: 6px;
            clip-path: inset(0% 0% 0% 0% round 6px);
        }
        &--display {
            opacity: 1;
            visibility: visible;
        }
        &--virtual-keyboard-display {
            bottom: calc(env(keyboard-inset-height, 0px) - 74px) !important;
            max-height: calc(100vh - calc(env(keyboard-inset-height, 0px) + 16px)) !important;
            max-height: calc(100dvh - calc(env(keyboard-inset-height, 0px) + 16px)) !important;
            @include smartphone-horizontal {
                bottom: calc(env(keyboard-inset-height, 0px) - 26px) !important;
            }
            @include smartphone-vertical {
                bottom: calc(env(keyboard-inset-height, 0px) - 44px) !important;
                max-height: calc(100% - env(keyboard-inset-height, 0px) + 36px) !important;
            }
        }
        @include smartphone-horizontal {
            &::-webkit-scrollbar {
                width: 4px;
            }
        }
        &::-webkit-scrollbar-track {
            background: rgb(var(--v-theme-background-lighten-2));
        }
        &::-webkit-scrollbar-thumb {
                background: rgb(var(--v-theme-gray));
            &:hover {
                background: rgb(var(--v-theme-gray));
            }
        }
        // iOS Safari 向け
        @supports (-webkit-touch-callout: none) {
            @include smartphone-horizontal {
                &::-webkit-scrollbar {
                    width: 0.1px;
                    -webkit-appearance: none;
                }
            }
            @include smartphone-vertical {
                &::-webkit-scrollbar {
                    width: 0.1px;
                    -webkit-appearance: none;
                }
            }
        }

        .hashtag-heading {
            display: flex;
            align-items: center;
            font-weight: bold;
            padding-left: 8px;
            padding-right: 4px;
            @include smartphone-horizontal {
                padding-left: 4px;
                padding-right: 2px;
            }

            &__text {
                display: flex;
                align-items: center;
                flex-grow: 1;
                font-size: 14px;
            }

            &__add-button {
                display: flex;
                align-items: center;
                font-size: 13px;
                padding: 4px 8px;
                border-radius: 5px;
                outline: none;
                cursor: pointer;
            }
        }

        .hashtag-container {
            display: flex;
            flex-direction: column;

            .hashtag {
                display: flex;
                position: relative !important;
                align-items: center;
                padding-top: 1.5px;
                padding-bottom: 1.5px;
                padding-left: 8px;
                padding-right: 4px;
                border-radius: 7px;
                transition: background-color 0.15s ease;
                cursor: pointer;
                @include smartphone-horizontal {
                    padding-top: 0px;
                    padding-bottom: 0px;
                    padding-left: 4px;
                    padding-right: 2px;
                }
                @include smartphone-vertical {
                    padding-top: 0px;
                    padding-bottom: 0px;
                }
                &:first-of-type {
                    margin-top: 6px;
                    @include smartphone-vertical {
                        margin-top: 0px;
                    }
                }
                &:hover {
                    background: rgba(255, 255, 255, 10%);
                }
                // タッチデバイスで hover を無効にする
                @media (hover: none) {
                    &:hover {
                        background: transparent;
                    }
                }

                &--editing {
                    &:hover {
                        background: transparent;
                    }
                    .hashtag__input {
                        box-shadow: rgba(79, 130, 230, 60%) 0 0 0 3.5px;
                        cursor: text;
                        pointer-events: auto;
                    }
                }

                &__input {
                    display: block;
                    flex-grow: 1;
                    border-radius: 2px;
                    color: rgb(var(--v-theme-twitter-lighten-2));
                    opacity: 1;
                    outline: none;
                    cursor: pointer;
                    transition: box-shadow 0.09s ease;
                    margin-right: 4px;
                    font-size: 12.5px;
                    pointer-events: none;
                    // iOS Safari でフォーカス時にズームされる問題への対処
                    @supports (-webkit-touch-callout: none) {
                        @include smartphone-horizontal {
                            position: absolute !important;
                            left: -26px !important;
                            width: calc(100% - 6px);
                            margin-right: 0px;
                            font-size: 16px;
                            transform: scale(0.78125);
                        }
                        @include smartphone-vertical {
                            position: absolute !important;
                            left: -26px !important;
                            width: calc(100% - 21px);
                            margin-right: 0px;
                            font-size: 16px;
                            transform: scale(0.78125);
                        }
                    }
                }

                &__edit-button {
                    margin-left: auto;
                }
                &__edit-button, &__delete-button, &__sort-handle {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    width: 19px;
                    height: 27px;
                    border-radius: 5px;
                    outline: none;
                    cursor: pointer;
                    @include smartphone-vertical {
                        width: 25px;
                    }
                }
                &__sort-handle {
                    cursor: grab;
                }
            }
        }
    }

    .twitter-account-list {
        position: absolute;
        left: 12px;
        right: 12px;
        bottom: 48px;
        max-height: calc(100vh - 137px);
        max-height: calc(100dvh - 137px);
        border-radius: 7px;
        // スクロールバーが表示されると角が丸くなくなる問題への対処
        clip-path: inset(0% 0% 0% 0% round 7px);
        background: rgb(var(--v-theme-background-lighten-2));
        box-shadow: 0px 3px 4px rgba(0, 0, 0, 53%);
        transition: opacity 0.15s ease, visibility 0.15s ease;
        opacity: 0;
        visibility: hidden;
        overflow-y: auto;
        z-index: 20;
        @include tablet-vertical {
            left: 24px;
            right: 24px;
        }
        @include smartphone-horizontal {
            left: 8px;
            right: 8px;
            bottom: 40px;
            max-height: calc(100vh - 82px);
            max-height: calc(100dvh - 82px);
            border-radius: 6px;
            clip-path: inset(0% 0% 0% 0% round 6px);
        }
        @include smartphone-vertical {
            bottom: 32px;
            max-height: calc(100% - 40px);
            border-radius: 6px;
            clip-path: inset(0% 0% 0% 0% round 6px);
        }
        &--display {
            opacity: 1;
            visibility: visible;
        }
        &::-webkit-scrollbar-track {
            background: rgb(var(--v-theme-background-lighten-2));
        }
        &::-webkit-scrollbar-thumb {
                background: rgb(var(--v-theme-gray));
            &:hover {
                background: rgb(var(--v-theme-gray));
            }
        }

        .twitter-account {
            display: flex;
            align-items: center;
            padding: 12px 12px;
            border-radius: 7px;
            user-select: none;
            cursor: pointer;
            @include smartphone-horizontal {
                padding: 8px 12px;
            }
            @include smartphone-vertical {
                padding: 8px 12px;
            }

            &__icon {
                display: block;
                width: 50px;
                height: 50px;
                border-radius: 50%;
                @include smartphone-horizontal {
                    width: 36px;
                    height: 36px;
                }
                @include smartphone-vertical {
                    width: 36px;
                    height: 36px;
                }
            }
            &__info {
                display: flex;
                flex-direction: column;
                flex-grow: 1;
                min-width: 0;
                margin-left: 12px;
            }
            &__name {
                font-size: 17px;
                font-weight: bold;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                @include smartphone-horizontal {
                    font-size: 14px;
                    line-height: 1.3;
                }
                @include smartphone-vertical {
                    font-size: 14px;
                    line-height: 1.3;
                }
            }
            &__screen-name {
                color: rgb(var(--v-theme-text-darken-1));
                font-size: 14px;
                @include smartphone-horizontal {
                    font-size: 13px;
                }
                @include smartphone-vertical {
                    font-size: 13px;
                }
            }
            &__check {
                flex-shrink: 0;
                color: rgb(var(--v-theme-twitter-lighten-1));
            }
        }
    }
}

</style>
