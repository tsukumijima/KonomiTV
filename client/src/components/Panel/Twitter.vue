<template>
    <div class="twitter-container">
        <v-dialog content-class="zoom-capture-modal-container" max-width="980" transition="slide-y-transition" v-model="zoom_capture_modal">
            <div class="zoom-capture-modal">
                <img class="zoom-capture-modal__image" :src="zoom_capture ? zoom_capture.image_url: ''">
                <a v-ripple class="zoom-capture-modal__download"
                    :href="zoom_capture ? zoom_capture.image_url : ''" :download="zoom_capture ? zoom_capture.filename : ''">
                    <Icon icon="fa6-solid:download" width="45px" />
                </a>
            </div>
        </v-dialog>
        <div class="tab-container">
            <div class="tab-content" :class="{'tab-content--active': twitter_active_tab === 'Capture'}">
                <div class="captures">
                    <div class="capture" :class="{
                            'capture--selected': capture.selected,
                            'capture--focused': capture.focused,
                            'capture--disabled': !capture.selected && tweet_captures.length >= 4,
                        }"
                        v-for="capture in captures" :key="capture.image_url"
                        @click="clickCapture(capture)">
                        <img class="capture__image" :src="capture.image_url">
                        <div class="capture__disabled-cover"></div>
                        <div class="capture__selected-number">{{tweet_captures.findIndex(blob => blob === capture.blob) + 1}}</div>
                        <Icon class="capture__selected-checkmark" icon="fluent:checkmark-circle-16-filled" />
                        <div class="capture__selected-border"></div>
                        <div class="capture__focused-border"></div>
                        <div v-ripple class="capture__zoom"
                            @click.prevent.stop="zoom_capture_modal = true; zoom_capture = capture"
                            @mousedown.prevent.stop="/* 親要素の波紋が広がらないように */">
                            <Icon icon="fluent:zoom-in-16-regular" width="32px" />
                        </div>
                    </div>
                </div>
                <div class="capture-announce" v-show="captures.length === 0">
                    <div class="capture-announce__heading">まだキャプチャがありません。</div>
                    <div class="capture-announce__text">
                        <p class="mt-0 mb-0">プレイヤーのキャプチャボタンやショートカットキーでキャプチャを撮ると、ここに表示されます。</p>
                        <p class="mt-2 mb-0">表示されたキャプチャを選択してからツイートすると、キャプチャを付けてツイートできます。</p>
                    </div>
                </div>
            </div>
        </div>
        <div class="tab-button-container">
            <div v-ripple class="tab-button" :class="{'tab-button--active': twitter_active_tab === 'Search'}"
                @click="twitter_active_tab = 'Search'">
                <Icon icon="fluent:search-16-filled" height="18px" />
                <span class="tab-button__text">ツイート検索</span>
            </div>
            <div v-ripple class="tab-button" :class="{'tab-button--active': twitter_active_tab === 'Timeline'}"
                @click="twitter_active_tab = 'Timeline'">
                <Icon icon="fluent:home-16-regular" height="18px" />
                <span class="tab-button__text">タイムライン</span>
            </div>
            <div v-ripple class="tab-button" :class="{'tab-button--active': twitter_active_tab === 'Capture'}"
                @click="twitter_active_tab = 'Capture'">
                <Icon icon="fluent:image-copy-20-regular" height="18px" />
                <span class="tab-button__text">キャプチャ</span>
            </div>
        </div>
        <div class="tweet-form" :class="{
            'tweet-form--focused': is_tweet_hashtag_form_focused || is_tweet_text_form_focused,
            'tweet-form--virtual-keyboard-display': is_virtual_keyboard_display &&
                (Utils.hasActiveElementClass('tweet-form__hashtag-form') || Utils.hasActiveElementClass('tweet-form__textarea')) &&
                (() => {is_hashtag_list_display = false; return true;})(),
        }">
            <div class="tweet-form__hashtag">
                <input class="tweet-form__hashtag-form" type="search" placeholder="#ハッシュタグ" spellcheck="false"
                    v-model="tweet_hashtag" @input="updateTweetLetterCount()"
                    @focus="is_tweet_hashtag_form_focused = true" @blur="is_tweet_hashtag_form_focused = false"
                    @change="tweet_hashtag = formatHashtag(tweet_hashtag)">
                <div v-ripple class="tweet-form__hashtag-list-button" @click="is_hashtag_list_display = !is_hashtag_list_display">
                    <Icon icon="fluent:clipboard-text-ltr-32-regular" height="22px" />
                </div>
            </div>
            <textarea class="tweet-form__textarea" placeholder="ツイート" spellcheck="false" v-model="tweet_text" ref="tweet_text"
                @input="updateTweetLetterCount()"
                @paste="pasteClipboardData($event)"
                @focus="is_tweet_text_form_focused = true"
                @blur="is_tweet_text_form_focused = false">
            </textarea>
            <div class="tweet-form__control">
                <div v-ripple class="account-button" :class="{'account-button--no-login': !is_logged_in_twitter}"
                    @click="clickAccountButton()">
                    <img class="account-button__icon"
                        :src="is_logged_in_twitter ? selected_twitter_account.icon_url : '/assets/images/account-icon-default.png'">
                    <span class="account-button__screen-name">
                        {{is_logged_in_twitter ? `@${selected_twitter_account.screen_name}` : '連携されていません'}}
                    </span>
                    <Icon class="account-button__menu" icon="fluent:more-circle-20-regular" width="22px" />
                </div>
                <div class="limit-meter">
                    <div class="limit-meter__content" :class="{
                        'limit-meter__content--yellow': tweet_letter_count <= 20,
                        'limit-meter__content--red': tweet_letter_count <= 0,
                    }">
                        <Icon icon="fa-brands:twitter" width="12px" style="margin-right: -2px;" />
                        <span>{{tweet_letter_count}}</span>
                    </div>
                    <div class="limit-meter__content">
                        <Icon icon="fluent:image-16-filled" width="14px" />
                        <span>{{tweet_captures.length}}/4</span>
                    </div>
                </div>
                <button v-ripple class="tweet-button"
                    :disabled="!is_logged_in_twitter || tweet_letter_count < 0 ||
                        (tweet_letter_count === 140 && tweet_captures.length === 0)"
                    @click="sendTweet()">
                    <Icon icon="fa-brands:twitter" height="16px" />
                    <span class="ml-1">ツイート</span>
                </button>
            </div>
        </div>
        <div class="twitter-account-list" :class="{'twitter-account-list--display': is_twitter_account_list_display}">
            <div v-ripple class="twitter-account" v-for="twitter_account in user.twitter_accounts" :key="twitter_account.id"
                @click="updateSelectedTwitterAccount(twitter_account)">
                <img class="twitter-account__icon" :src="twitter_account.icon_url">
                <div class="twitter-account__info">
                    <div class="twitter-account__name">{{twitter_account.name}}</div>
                    <div class="twitter-account__screen-name">@{{twitter_account.screen_name}}</div>
                </div>
                <Icon class="twitter-account__check" icon="fluent:checkmark-16-filled" width="24px"
                    v-show="twitter_account.id === selected_twitter_account_id" />
            </div>
        </div>
        <div class="hashtag-list" :class="{
            'hashtag-list--display': is_hashtag_list_display,
            'hashtag-list--virtual-keyboard-display': is_virtual_keyboard_display && Utils.hasActiveElementClass('hashtag__input'),
        }">
            <div class="hashtag-heading">
                <div class="hashtag-heading__text">
                    <Icon icon="charm:hash" width="17px" />
                    <span class="ml-1">ハッシュタグリスト</span>
                </div>
                <button v-ripple class="hashtag-heading__add-button"
                    @click="saved_twitter_hashtags.push({id: Date.now(), text: '#ここにハッシュタグを入力', editing: false})">
                    <Icon icon="fluent:add-12-filled" width="17px" />
                    <span class="ml-1">追加</span>
                </button>
            </div>
            <draggable class="hashtag-container" v-model="saved_twitter_hashtags" handle=".hashtag__sort-handle">
                <div v-ripple="!hashtag.editing" class="hashtag" :class="{'hashtag--editing': hashtag.editing}"
                    v-for="hashtag in saved_twitter_hashtags" :key="hashtag.id"
                    @click="clickHashtag(hashtag)">
                    <input type="search" class="hashtag__input" spellcheck="false" v-model="hashtag.text" :disabled="!hashtag.editing" @click.stop="">
                    <button v-ripple class="hashtag__edit-button"
                        @click.prevent.stop="hashtag.editing = !hashtag.editing; hashtag.text = formatHashtag(hashtag.text, true)">
                        <Icon :icon="hashtag.editing ? 'fluent:checkmark-16-filled': 'fluent:edit-16-filled'" width="17px" />
                    </button>
                    <button v-ripple class="hashtag__delete-button"
                        @click.prevent.stop="saved_twitter_hashtags.splice(saved_twitter_hashtags.indexOf(hashtag), 1)">
                        <Icon  icon="fluent:delete-16-filled" width="17px" />
                    </button>
                    <div class="hashtag__sort-handle">
                        <Icon icon="material-symbols:drag-handle-rounded" width="17px" />
                    </div>
                </div>
            </draggable>
        </div>
    </div>
</template>
<script lang="ts">

import axios from 'axios';
import Vue, { PropType } from 'vue';
import draggable from 'vuedraggable'

import { IChannel, ITwitterAccount, IUser } from '@/interface';
import Utils from '@/utils';

// このコンポーネント内でのキャプチャのインターフェイス
interface ITweetCapture {
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

export default Vue.extend({
    name: 'Panel-TwitterTab',
    components: {
        draggable,
    },
    props: {
        // チャンネル情報
        channel: {
            type: Object as PropType<IChannel>,
            required: true,
        },
        // プレイヤーのインスタンス
        player: {
            type: null as PropType<any>,  // 代入当初は null になるため苦肉の策
            required: true,
        },
        // 仮想キーボードが表示されているかどうか
        is_virtual_keyboard_display: {
            type: Boolean as PropType<boolean>,
            required: true,
        },
    },
    data() {
        return {

            // ユーティリティをテンプレートで使えるように
            Utils: Utils,

            // window.setTimeout() にアクセスできるように
            window: window,

            // ログイン中かどうか
            is_logged_in: Utils.getAccessToken() !== null,

            // Twitter アカウントを1つでも連携しているかどうか
            is_logged_in_twitter: false,

            // ユーザーアカウントの情報
            // ログインしていない場合は null になる
            user: null as IUser | null,

            // 現在ツイート対象として選択されている Twitter アカウント
            selected_twitter_account: null as ITwitterAccount | null,

            // 現在ツイート対象として選択されている Twitter アカウントの ID
            selected_twitter_account_id: Utils.getSettingsItem('selected_twitter_account_id') as number | null,

            // 連携している Twitter アカウントリストを表示しているか
            is_twitter_account_list_display: false,

            // 保存している Twitter のハッシュタグが入るリスト
            saved_twitter_hashtags: (Utils.getSettingsItem('saved_twitter_hashtags') as string[]).map((hashtag, index) => {
                // id プロパティは :key="" に指定するためにつける ID (ミリ秒単位のタイムスタンプ + index で適当に一意になるように)
                return {id: Date.now() + index, text: hashtag, editing: false} as IHashtag;
            }),

            // ハッシュタグリストを表示しているか
            is_hashtag_list_display: false,

            // 既定で表示される Twitter タブ内のタブ
            twitter_active_tab: Utils.getSettingsItem('twitter_active_tab') as ('Search' | 'Timeline' | 'Capture'),

            // キャプチャを拡大表示するモーダルの表示状態
            zoom_capture_modal: false,

            // 現在モーダルで拡大表示中のキャプチャのオブジェクト
            zoom_capture: null as ITweetCapture | null,

            // キャプチャリスト
            captures: [] as ITweetCapture[],

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

            // ツイートに添付するキャプチャの Blob のリスト
            tweet_captures: [] as Blob[],

            // 文字数カウント
            tweet_letter_count: 140,
        }
    },
    async created() {

        // ユーザーモデルの初期値
        this.user = {
            id: 0,
            name: '',
            is_admin: true,
            niconico_user_id: null,
            niconico_user_name: null,
            niconico_user_premium: null,
            twitter_accounts: [],
            created_at: '',
            updated_at: '',
        }

        // 表示されているアカウント情報を更新 (ログイン時のみ)
        if (this.is_logged_in === true) {
            await this.syncAccountInfo();

            // 連携している Twitter アカウントがあれば true に設定
            if (this.user.twitter_accounts.length > 0) {
                this.is_logged_in_twitter = true;

                // 現在ツイート対象として選択されている Twitter アカウントの ID が設定されていない or ID に紐づく Twitter アカウントがない
                // 連携している Twitter アカウントのうち、一番最初のものを自動選択する
                // ここで言う Twitter アカウントの ID は DB 上で連番で振られるもので、Twitter アカウントそのものの固有 ID ではない
                if (this.selected_twitter_account_id === null ||
                    !this.user.twitter_accounts.some((twitter_account) => twitter_account.id === this.selected_twitter_account_id)) {
                    this.selected_twitter_account_id = this.user.twitter_accounts[0].id;
                    Utils.setSettingsItem('selected_twitter_account_id', this.selected_twitter_account_id);
                }

                // 現在ツイート対象として選択されている Twitter アカウントを取得・設定
                const twitter_account_index = this.user.twitter_accounts.findIndex((twitter_account) => {
                    return twitter_account.id === this.selected_twitter_account_id;  // Twitter アカウントの ID が選択されているものと一致する
                });
                this.selected_twitter_account = this.user.twitter_accounts[twitter_account_index];
            }
        }

        // 局タグ追加処理を走らせる (ハッシュタグフォームのフォーマット処理も同時に行われるが、元々空なので無意味)
        this.tweet_hashtag = this.formatHashtag(this.tweet_hashtag);
    },
    beforeDestroy() {
        // 終了前にすべてのキャプチャの Blob URL を revoke してリソースを解放する
        for (const capture of this.captures) {
            URL.revokeObjectURL(capture.image_url);
        }
    },
    watch: {

        // チャンネル情報が変更されたとき
        // 前のチャンネル情報と次のチャンネル情報で channel_id が変わってたら局タグ追加処理を走らせる
        async channel(new_channel: IChannel, old_channel: IChannel) {
            if (new_channel.channel_id !== old_channel.channel_id) {
                const old_channel_hashtag = this.getChannelHashtag(old_channel.channel_name) ?? '';
                this.tweet_hashtag = this.formatHashtag(this.tweet_hashtag.replaceAll(old_channel_hashtag, ''));
            }
        },

        // 保存しているハッシュタグが変更されたら随時 LocalStorage に保存する
        saved_twitter_hashtags: {
            deep: true,
            handler() {
                Utils.setSettingsItem('saved_twitter_hashtags', this.saved_twitter_hashtags.map(hashtag => hashtag.text));
            }
        }
    },
    methods: {

        // ユーザーアカウントの情報を取得する
        async syncAccountInfo() {
            try {
                this.user = (await Vue.axios.get('/users/me')).data;
            } catch (error) {
                // ログインされていないので未ログイン状態に設定
                if (axios.isAxiosError(error) && error.response && error.response.status === 401) {
                    this.is_logged_in = false;
                    this.user = null;
                }
            }
        },

        // 文字数カウントを変更するイベント
        updateTweetLetterCount() {

            // サロゲートペアを考慮し、スプレッド演算子で一度配列化してから数えている
            // ref: https://qiita.com/suin/items/3da4fb016728c024eaca
            this.tweet_letter_count = 140 - [...this.tweet_hashtag].length - [...this.tweet_text].length;
        },

        // アカウントボタンが押されたときのイベント
        clickAccountButton() {

            // Twitter アカウントが連携されていない場合は Twitter 設定画面に飛ばす
            if (!this.is_logged_in_twitter) {

                // 視聴ページ以外に遷移するため、フルスクリーンを解除しないと画面が崩れる
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

        // クリップボード内のデータがペーストされたときのイベント
        pasteClipboardData(event: ClipboardEvent) {

            // 一応配列になっているので回しているが、基本1回のペーストにつき DataTransferItem は1個しか入らない
            for (const clipboard_item of event.clipboardData.items) {

                // 画像のみを対象にする (DataTransferItem.type には MIME タイプが入る)
                if (clipboard_item.type.startsWith('image/')) {

                    // クリップボード内の画像データを File オブジェクトとして取得し、キャプチャリストに追加
                    const file = clipboard_item.getAsFile();
                    this.addCaptureList(file, file.name);
                }
            }
        },

        // 選択されている Twitter アカウントを更新する
        updateSelectedTwitterAccount(twitter_account: ITwitterAccount) {
            this.selected_twitter_account_id = twitter_account.id;
            Utils.setSettingsItem('selected_twitter_account_id', this.selected_twitter_account_id);
            this.selected_twitter_account = twitter_account;

            // Twitter アカウントリストのオーバーレイを閉じる (少し待ってから閉じたほうが体感が良い)
            window.setTimeout(() => this.is_twitter_account_list_display = false, 150);
        },

        // キャプチャリスト内のキャプチャがクリックされたときのイベント
        clickCapture(capture: ITweetCapture) {

            // 選択されたキャプチャが3枚まで & まだ選択されていないならキャプチャをツイート対象に追加する
            if (this.tweet_captures.length < 4 && capture.selected === false) {
                capture.selected = true;
                this.tweet_captures.push(capture.blob);
            } else {
                // ツイート対象のキャプチャになっていたら取り除く
                const index = this.tweet_captures.findIndex(blob => blob === capture.blob);
                if (index > -1) {
                    this.tweet_captures.splice(index, 1);
                }
                // キャプチャの選択を解除
                capture.selected = false;
            }
        },

        // 撮ったキャプチャを親コンポーネントから受け取り、キャプチャリストに追加する
        async addCaptureList(blob: Blob, filename: string) {

            if (this.captures_element === null) {
                this.captures_element = this.$el.querySelector('.tab-content');
            }

            // 撮ったキャプチャが50件を超えていたら、重くなるので古いものから削除する
            // 削除する前に Blob URL を revoke してリソースを解放するのがポイント
            if (this.captures.length > 50) {
                URL.revokeObjectURL(this.captures[0].image_url);
                this.captures.shift();
            }

            // キャプチャリストにキャプチャを追加
            const blob_url = URL.createObjectURL(blob);
            this.captures.push({
                blob: blob,
                filename: filename,
                image_url: blob_url,
                selected: false,
                focused: false,
            });

            // キャプチャリストを下にスクロール
            // this.$nextTick() のコールバックで DOM の更新を待つ
            this.$nextTick(() => {
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
            context.font = `bold 22px 'YakuHanJPs', 'Open Sans', 'Hiragino Sans', 'Noto Sans JP', sans-serif`; // フォント
            context.fillStyle = 'rgba(255, 255, 255, 70%)';  // 半透明の白
            context.shadowColor = 'rgba(0, 0, 0, 100%)'  // 影の色
            context.shadowBlur = 4;  // 影をぼかすしきい値
            context.shadowOffsetX = 0;  // 影のX座標
            context.shadowOffsetY = 0;  // 影のY座標

            // 番組タイトルの透かしを描画
            switch (Utils.getSettingsItem('tweet_capture_watermark_position')) {
                case 'TopLeft': {
                    context.textAlign = 'left'; // 左寄せ
                    context.textBaseline = 'top'; // ベースラインを上寄せ
                    context.fillText(this.channel.program_present.title, 16, 12);
                    break;
                }
                case 'TopRight': {
                    context.textAlign = 'right'; // 右寄せ
                    context.textBaseline = 'top'; // ベースラインを上寄せ
                    context.fillText(this.channel.program_present.title, canvas.width - 16, 12);
                    break;
                }
                case 'BottomLeft': {
                    context.textAlign = 'left'; // 左寄せ
                    context.textBaseline = 'bottom'; // ベースラインを下寄せ
                    context.fillText(this.channel.program_present.title, 16, canvas.height - 12);
                    break;
                }
                case 'BottomRight': {
                    context.textAlign = 'right'; // 右寄せ
                    context.textBaseline = 'bottom'; // ベースラインを下寄せ
                    context.fillText(this.channel.program_present.title, canvas.width - 16, canvas.height - 12);
                    break;
                }
            }

            // Blob にして返す
            if ('OffscreenCanvas' in window) {
                return await (canvas as OffscreenCanvas).convertToBlob({type: 'image/jpeg', quality: 1});
            } else {
                return new Promise(resolve => (canvas as HTMLCanvasElement).toBlob(blob => resolve(blob), 'image/jpeg', 1));
            }
        },

        // チャンネル名から対応する局タグを取得する
        // とりあえず三大首都圏 + BS のみ対応
        getChannelHashtag(channel_name: string): string | null {
            // NHK
            if (channel_name.startsWith('NHK総合')) {
                return '#nhk';
            } else if (channel_name.startsWith('NHKEテレ')) {
                return '#etv';
            // 民放
            } else if (channel_name.startsWith('日テレ')) {
                return '#ntv';
            } else if (channel_name.startsWith('読売テレビ')) {
                return '#ytv';
            } else if (channel_name.startsWith('中京テレビ')) {
                return '#chukyotv';
            } else if (channel_name.startsWith('テレビ朝日')) {
                return '#tvasahi';
            } else if (channel_name.startsWith('ABCテレビ')) {
                return '#abc';
            } else if (channel_name.startsWith('メ~テレ')) {
                return '#nagoyatv';
            } else if (channel_name.startsWith('TBS') && !channel_name.includes('TBSチャンネル')) {
                return '#tbs';
            } else if (channel_name.startsWith('MBS')) {
                return '#mbs';
            } else if (channel_name.startsWith('CBC')) {
                return '#cbc';
            } else if (channel_name.startsWith('テレビ東京')) {
                return '#tvtokyo';
            } else if (channel_name.startsWith('テレビ大阪')) {
                return '#tvo';
            } else if (channel_name.startsWith('テレビ愛知')) {
                return '#tva';
            } else if (channel_name.startsWith('フジテレビ')) {
                return '#fujitv';
            } else if (channel_name.startsWith('関西テレビ')) {
                return '#kantele';
            } else if (channel_name.startsWith('東海テレビ')) {
                return '#tokaitv';
            // 独立局
            } else if (channel_name.startsWith('TOKYO MX')) {
                return '#tokyomx';
            } else if (channel_name.startsWith('tvk')) {
                return '#tvk';
            } else if (channel_name.startsWith('チバテレ')) {
                return '#chibatv';
            } else if (channel_name.startsWith('テレ玉')) {
                return '#teletama';
            } else if (channel_name.startsWith('サンテレビ')) {
                return '#suntv';
            } else if (channel_name.startsWith('KBS京都')) {
                return '#kbs';
            // BS・CS
            } else if (channel_name.startsWith('NHKBS1')) {
                return '#nhkbs1';
            } else if (channel_name.startsWith('NHKBSプレミアム')) {
                return '#nhkbsp';
            } else if (channel_name.startsWith('BS日テレ')) {
                return '#bsntv';
            } else if (channel_name.startsWith('BS朝日')) {
                return '#bsasahi';
            } else if (channel_name.startsWith('BS-TBS')) {
                return '#bstbs';
            } else if (channel_name.startsWith('BSテレ東')) {
                return '#bstvtokyo';
            } else if (channel_name.startsWith('BSフジ')) {
                return '#bsfuji';
            } else if (channel_name.startsWith('BS11イレブン')) {
                return '#bs11';
            } else if (channel_name.startsWith('BS12トゥエルビ')) {
                return '#bs12';
            } else if (channel_name.startsWith('AT-X')) {
                return '#at_x';
            }

            return null;
        },

        // ハッシュタグがクリックされたときのイベント
        clickHashtag(hashtag: IHashtag) {
            this.tweet_hashtag = hashtag.text;
            this.tweet_hashtag = this.formatHashtag(this.tweet_hashtag);
            this.updateTweetLetterCount();
            window.setTimeout(() => this.is_hashtag_list_display = false, 150);
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

            // 設定でオンになっている場合のみ、視聴中チャンネルの局タグを自動的に追加する (ハッシュタグリスト内のハッシュタグは除外)
            if (Utils.getSettingsItem('auto_add_watching_channel_hashtag') === true && from_hashtag_list === false) {
                const channel_hashtag = this.getChannelHashtag(this.channel.channel_name);
                if (channel_hashtag !== null) {
                    if (tweet_hashtag_array.includes(channel_hashtag) === false) {
                        tweet_hashtag_array.push(channel_hashtag);
                    }
                }
            }

            return tweet_hashtag_array.join(' ');
        },

        // ツイートを送信する
        async sendTweet() {

            // ハッシュタグを整形
            this.tweet_hashtag = this.formatHashtag(this.tweet_hashtag);
            const tweet_hashtag = this.tweet_hashtag;

            // 実際に送るツイート本文を作成
            let tweet_text = this.tweet_text;
            if (tweet_hashtag !== '') {  // ハッシュタグが入力されているときのみ
                switch (Utils.getSettingsItem('tweet_hashtag_position')) {
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

            // multipart/form-data でツイート本文と画像（選択されている場合）を送る
            const form_data = new FormData();
            form_data.append('tweet', tweet_text);
            for (let tweet_capture of this.tweet_captures) {
                // キャプチャへの透かしの描画がオンの場合、キャプチャの Blob を透かし付きのものに差し替える
                if (Utils.getSettingsItem('tweet_capture_watermark_position') !== 'None') {
                    tweet_capture = await this.drawProgramTitleOnCapture(tweet_capture);
                }
                form_data.append('images', tweet_capture);
            }

            // 連投防止のため、フォーム上のツイート本文・キャプチャの選択・キャプチャのフォーカスを消去
            // 送信した感を出す意味合いもある
            for (const capture of this.captures) {
                capture.selected = false;
                capture.focused = false;
            }
            this.tweet_captures = [];
            this.tweet_text = '';

            // パネルを閉じるように親コンポーネントに伝える
            if (Utils.getSettingsItem('fold_panel_after_sending_tweet') === true) {
                this.$emit('panel_folding_requested');
                (this.$refs.tweet_text as HTMLTextAreaElement).blur();  // フォーカスを外す
            }

            try {

                // ツイート送信 API にリクエスト
                const result = await Vue.axios.post(`/twitter/accounts/${this.selected_twitter_account.screen_name}/tweets`, form_data, {
                    headers: {'Content-Type': 'multipart/form-data'},
                });

                // 成功 or 失敗に関わらず detail の内容をそのまま通知する
                if (result.data.is_success === true) {
                    this.player.notice(result.data.detail);
                } else {
                    this.player.notice('エラー: ' + result.data.detail);
                }

            } catch (error) {
                console.error(error);
                this.player.notice('エラー: ツイートの送信に失敗しました。');
            }
        },
    }
});

</script>
<style lang="scss">

@include smartphone-horizontal {
    .zoom-capture-modal-container.v-dialog {
        width: auto !important;
        max-width: auto !important;
        aspect-ratio: 16 / 9;
    }
}

</style>
<style lang="scss" scoped>

.zoom-capture-modal {
    position: relative;

    &__image {
        display: block;
        width: 100%;
        border-radius: 11px;
    }

    &__download {
        display: flex;
        position: absolute;
        align-items: center;
        justify-content: center;
        right: 22px;
        bottom: 20px;
        width: 80px;
        height: 80px;
        border-radius: 50%;
        color: var(--v-text-base);
        filter: drop-shadow(0px 0px 4.5px rgba(0, 0, 0, 90%));
    }
}

.twitter-container {
    display: flex;
    flex-direction: column;
    position: relative;
    padding-bottom: 8px;

    &.watch-panel__content--active .tab-container .tab-content--active {
        opacity: 1;
        visibility: visible;
        @media (hover: none) {
            content-visibility: auto;
        }
    }

    .tab-container {
        flex-grow: 1;
        min-height: 0;  // magic!

        .tab-content {
            position: relative;
            height: 100%;
            transition: opacity 0.2s, visibility 0.2s;
            opacity: 0;
            visibility: hidden;
            overflow-y: scroll;
            @include smartphone-horizontal {
                padding-top: 8px;
            }

            // スマホ・タブレット (タッチデバイス) ではアニメーションが重めなので、アニメーションを無効化
            // アクティブなタブ以外は明示的に描画しない
            @media (hover: none) {
                transition: none;
                content-visibility: hidden;
            }

            .captures {
                display: grid;
                grid-template-columns: 1fr 1fr;
                grid-row-gap: 12px;
                grid-column-gap: 12px;
                padding-left: 12px;
                padding-right: 5px;
                max-height: 100%;
                @include smartphone-horizontal {
                    grid-row-gap: 8px;
                    grid-column-gap: 8px;
                }

                .capture {
                    position: relative;
                    height: 82px;
                    border-radius: 11px;
                    // 読み込まれるまでのキャプチャの背景
                    background: linear-gradient(150deg, var(--v-gray-base), var(--v-background-lighten2));
                    overflow: hidden;
                    user-select: none;
                    cursor: pointer;
                    content-visibility: auto;
                    @include smartphone-horizontal {
                        height: 74px;
                    }

                    &__image {
                        display: block;
                        width: 100%;
                        height: 100%;
                    }

                    &__zoom {
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        position: absolute;
                        top: 1px;
                        right: 3px;
                        width: 38px;
                        height: 38px;
                        border-radius: 50%;
                        filter: drop-shadow(0px 0px 2.5px rgba(0, 0, 0, 90%));
                        cursor: pointer;
                    }

                    &__disabled-cover {
                        display: none;
                        align-items: center;
                        justify-content: center;
                        position: absolute;
                        top: 0;
                        left: 0;
                        right: 0;
                        bottom: 0;
                        background: rgba(30, 19, 16, 50%);
                    }

                    &__selected-number {
                        display: none;
                        align-items: center;
                        justify-content: center;
                        position: absolute;
                        top: 0;
                        left: 0;
                        right: 0;
                        bottom: 0;
                        background: rgba(30, 19, 16, 50%);
                        font-size: 38px;
                        text-shadow: 0px 0px 2.5px rgba(0, 0, 0, 90%)
                    }

                    &__selected-checkmark {
                        display: none;
                        position: absolute;
                        top: 6px;
                        left: 7px;
                        width: 20px;
                        height: 20px;
                        color: var(--v-primary-base);
                    }

                    &__selected-border {
                        display: none;
                        position: absolute;
                        top: 0;
                        left: 0;
                        right: 0;
                        bottom: 0;
                        border-radius: 11px;
                        border: 4px solid var(--v-primary-base);
                    }

                    &__focused-border {
                        display: none;
                        position: absolute;
                        top: 0;
                        left: 0;
                        right: 0;
                        bottom: 0;
                        border-radius: 11px;
                        border: 4px solid var(--v-secondary-base);
                    }

                    &--selected {
                        .capture__selected-number, .capture__selected-checkmark, .capture__selected-border {
                            display: flex;
                        }
                    }
                    &--focused {
                        .capture__focused-border {
                            display: block;
                        }
                    }
                    &--disabled {
                        cursor: auto;
                        .capture__disabled-cover {
                            display: block;
                        }
                    }
                }
            }

            .capture-announce {
                display: flex;
                align-items: center;
                justify-content: center;
                flex-direction: column;
                height: 100%;
                padding-left: 12px;
                padding-right: 5px;

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
        @include smartphone-horizontal {
            height: 38px;
            margin-left: 8px;
            margin-right: 8px;
        }

        .tab-button {
            display: flex;
            align-items: center;
            justify-content: center;
            flex: 1;
            background: var(--v-background-lighten2);
            border-radius: 7px;
            font-size: 11px;
            transition: background-color 0.15s ease;
            user-select: none;
            cursor: pointer;
            @include smartphone-horizontal {
                font-size: 10.5px;
            }
            &--active {
                background: var(--v-twitter-base);
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
        flex-direction: column;
        flex-shrink: 0;
        height: 136px;
        margin-left: 12px;
        margin-right: 12px;
        border-radius: 12px;
        border-bottom-left-radius: 7px;
        border-bottom-right-radius: 7px;
        background: var(--v-background-lighten1);
        transition: box-shadow 0.09s ease;
        @include smartphone-horizontal {
            height: 96px;
            margin-left: 8px;
            margin-right: 8px;
            border-bottom-left-radius: 5px;
            border-bottom-right-radius: 5px;
        }

        &--focused {
            box-shadow: rgba(79, 130, 230, 60%) 0 0 0 3.5px;
        }

        &--virtual-keyboard-display {
            position: relative;
            bottom: calc(env(keyboard-inset-height, 0px) - 77px);
            @include smartphone-horizontal {
                bottom: calc(env(keyboard-inset-height, 0px) - 56px);
            }
        }

        &__hashtag {
            display: flex;
            align-items: center;
            height: 19px;
            margin-top: 12px;
            margin-left: 12px;
            margin-right: 12px;
            @include smartphone-horizontal {
                height: 16px;
                margin-top: 8px;
            }

            &-form {
                display: block;
                height: 100%;
                flex-grow: 1;
                font-size: 12.5px;
                color: var(--v-twitter-lighten2);
                outline: none;
                @include smartphone-horizontal {
                    font-size: 12px;
                }
                &::placeholder {
                    color: rgba(65, 165, 241, 60%);
                }
            }
            &-list-button {
                display: flex;
                position: relative;
                align-items: center;
                justify-content: center;
                right: -8px;
                width: 34px;
                height: 34px;
                padding: 6px;
                border-radius: 50%;
                color: var(--v-twitter-lighten2);
                cursor: pointer;
            }
        }

        &__textarea {
            display: block;
            flex-grow: 1;
            margin-top: 8px;
            margin-left: 12px;
            margin-right: 12px;
            font-size: 12.5px;
            color: var(--v-text-base);
            word-break: break-all;
            resize: none;
            outline: none;
            @include smartphone-horizontal {
                margin-top: 6px;
                font-size: 12px;
            }
            &::placeholder {
                color: var(--v-text-darken2);
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

            .account-button {
                display: flex;
                align-items: center;
                width: 183px;
                height: 100%;
                border-radius: 7px;
                font-size: 13px;
                color: var(--v-text-base);
                background: var(--v-background-lighten2);
                user-select: none;
                cursor: pointer;
                @include smartphone-horizontal {
                    width: 156px;
                    border-radius: 5px;
                    font-size: 11px;
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
                    background: linear-gradient(150deg, var(--v-gray-base), var(--v-background-lighten2));
                    @include smartphone-horizontal {
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
                color: var(--v-text-darken1);
                user-select: none;
                @include smartphone-horizontal {
                    font-size: 9px;
                }

                &__content {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    &:nth-child(2) {
                        @include smartphone-horizontal {
                            margin-top: -2.5px;
                        }
                    }
                    svg {
                        width: 14px;
                    }
                    span {
                        width: 16px;
                        margin-left: 5px;
                        text-align: center;
                        font-weight: bold;
                    }
                    &--yellow {
                        color: var(--v-warning-base);
                    }
                    &--red {
                        color: var(--v-error-base);
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
                color: var(--v-text-base);
                background: var(--v-twitter-base);
                user-select: none;
                outline: none;
                cursor: pointer;
                @include smartphone-horizontal {
                    width: 86px;
                    border-radius: 5px;
                    font-size: 11.8px;
                }

                &[disabled] {
                    opacity: 0.7;
                    cursor: auto;
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
        background: var(--v-background-lighten2);
        box-shadow: 0px 3px 4px rgba(0, 0, 0, 53%);
        transition: opacity 0.2s ease, visibility 0.2s ease;
        opacity: 0;
        visibility: hidden;
        overflow-y: auto;
        z-index: 3;
        @include smartphone-horizontal {
            left: 8px;
            right: 8px;
            bottom: 40px;
            max-height: calc(100vh - 104px);
            max-height: calc(100dvh - 104px);
        }
        &--display {
            opacity: 1;
            visibility: visible;
        }
        &::-webkit-scrollbar-track {
            background: var(--v-background-lighten2);
        }
        &::-webkit-scrollbar-thumb {
                background: var(--v-gray-base);
            &:hover {
                background: var(--v-gray-base);
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

            &__icon {
                display: block;
                width: 50px;
                height: 50px;
                border-radius: 50%;
                @include smartphone-horizontal {
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
            }
            &__screen-name {
                color: var(--v-text-darken1);
                font-size: 14px;
                @include smartphone-horizontal {
                    font-size: 13px;
                }
            }
            &__check {
                flex-shrink: 0;
                color: var(--v-twitter-lighten1);
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
        border-radius: 7px;
        // スクロールバーが表示されると角が丸くなくなる問題への対処
        clip-path: inset(0% 0% 0% 0% round 7px);
        background: var(--v-background-lighten2);
        box-shadow: 0px 3px 4px rgba(0, 0, 0, 53%);
        transition: opacity 0.2s ease, visibility 0.2s ease;
        opacity: 0;
        visibility: hidden;
        overflow-y: auto;
        z-index: 2;
        @include smartphone-horizontal {
            left: 8px;
            right: 8px;
            bottom: 110px;
            max-height: calc(100vh - 174px);
            max-height: calc(100dvh - 174px);
            padding: 8px 4px;
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
                bottom: calc(env(keyboard-inset-height, 0px) - 48px) !important;
            }
        }
        &::-webkit-scrollbar-track {
            background: var(--v-background-lighten2);
        }
        &::-webkit-scrollbar-thumb {
                background: var(--v-gray-base);
            &:hover {
                background: var(--v-gray-base);
            }
        }

        .hashtag-heading {
            display: flex;
            align-items: center;
            font-weight: bold;
            padding-left: 8px;
            padding-right: 4px;

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
                }
                &:first-of-type {
                    margin-top: 6px;
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
                    }
                }

                &__input {
                    display: block;
                    flex-grow: 1;
                    border-radius: 2px;
                    color: var(--v-twitter-lighten2);
                    font-size: 12.5px;
                    opacity: 1;
                    outline: none;
                    cursor: pointer;
                    transition: box-shadow 0.09s ease;
                }

                &__edit-button {
                    margin-left: 4px;
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
                }
                &__sort-handle {
                    cursor: move;
                }
            }
        }
    }
}

</style>