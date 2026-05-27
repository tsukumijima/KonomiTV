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
            <div class="tweet-form__control" :class="{
                'tweet-form__control--linked': twitterStore.selected_account?.kind === 'Linked',
            }">
                <div v-ripple class="account-button" :class="{'account-button--no-login': !twitterStore.has_twitter_panel_account}"
                    @click="clickAccountButton()">
                    <img class="account-button__icon"
                        :src="twitterStore.has_twitter_panel_account ? selectedAccountIconUrl : '/assets/images/account-icon-default.png'">
                    <span class="account-button__screen-name">
                        {{twitterStore.has_twitter_panel_account ? selectedAccountDisplayId : '連携されていません'}}
                    </span>
                    <Icon class="account-button__menu" icon="fluent:more-circle-20-regular" width="18px" />
                </div>
                <button v-if="twitterStore.selected_account?.kind === 'Linked'" v-ripple
                    class="post-target-button" @click="cycleLinkedPostTarget()">
                    <span v-if="isLinkedPostTargetBoth" class="dual-service-icon dual-service-icon--post-target">
                        <Icon icon="fa-brands:twitter" />
                        <Icon icon="simple-icons:bluesky" />
                    </span>
                    <Icon v-else-if="shouldPostToTwitter" icon="fa-brands:twitter" width="14px" />
                    <Icon v-else-if="shouldPostToBluesky" icon="simple-icons:bluesky" width="14px" />
                </button>
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
                <button class="tweet-button" :class="tweetButtonClass" v-ripple="Utils.isTouchDevice() === false" :disabled="is_tweet_button_disabled"
                    @click="sendTweet()" @touchstart="sendTweet()">
                    <span v-if="shouldPostToBothServices" class="dual-service-icon dual-service-icon--tweet-button">
                        <Icon icon="fa-brands:twitter" />
                        <Icon icon="simple-icons:bluesky" />
                    </span>
                    <Icon v-else-if="shouldPostToTwitter" icon="fa-brands:twitter" height="16px" />
                    <Icon v-else-if="shouldPostToBluesky" icon="simple-icons:bluesky" height="15px" />
                    <span class="ml-1">{{tweetButtonLabel}}</span>
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
            <div v-ripple class="twitter-account" v-for="account in twitterStore.selectable_accounts"
                :key="getSelectableAccountKey(account)" @click="updateSelectedAccount(account)">
                <!-- 単体アカウントは左下のサービスバッジ、紐付けアカウントは設定画面同様に Bluesky アバターを重ねる -->
                <div class="twitter-account__icon-wrapper">
                    <img class="twitter-account__icon" :src="getSelectableAccountIconUrl(account)">
                    <img v-if="account.kind === 'Linked'" class="twitter-account__icon-badge"
                        :src="account.account_link.bluesky_account.icon_url || '/assets/images/account-icon-default.png'">
                    <span v-if="account.kind === 'Twitter'" class="twitter-account__service-badge twitter-account__service-badge--twitter">
                        <Icon icon="fa-brands:twitter" />
                    </span>
                    <span v-if="account.kind === 'Bluesky'" class="twitter-account__service-badge twitter-account__service-badge--bluesky">
                        <Icon icon="simple-icons:bluesky" />
                    </span>
                    <span v-if="account.kind === 'Linked'" class="twitter-account__service-badge twitter-account__service-badge--linked">
                        <span class="twitter-account__service-badge-segment twitter-account__service-badge-segment--twitter">
                            <Icon icon="fa-brands:twitter" />
                        </span>
                        <span class="twitter-account__service-badge-segment twitter-account__service-badge-segment--bluesky">
                            <Icon icon="simple-icons:bluesky" />
                        </span>
                    </span>
                </div>
                <div class="twitter-account__info">
                    <div v-for="row in getSelectableAccountNameRows(account)" :key="row.id" class="twitter-account__name">
                        <Icon v-if="row.icon" class="twitter-account__name-service-icon" :icon="row.icon" />
                        <span class="twitter-account__text">{{row.text}}</span>
                    </div>
                    <span v-if="account.kind === 'Linked'" class="twitter-account__screen-name">
                        <span class="twitter-account__screen-name-handle">@{{account.account_link.twitter_account.screen_name}}</span>
                        <Icon class="twitter-account__screen-name-link-icon" icon="fluent:link-20-filled" />
                        <span class="twitter-account__screen-name-handle">@{{account.account_link.bluesky_account.handle}}</span>
                    </span>
                    <span v-else class="twitter-account__screen-name">
                        <span class="twitter-account__screen-name-handle">{{getSelectableAccountDisplayId(account)}}</span>
                    </span>
                </div>
                <svg class="twitter-account__check iconify iconify--fluent" width="24px" height="24px" viewBox="0 0 16 16"
                    v-show="isSelectableAccountSelected(account)">
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

import type { IPostTweetSendResult } from '@/services/Twitter';

import TwitterCaptures from '@/components/Watch/Panel/Twitter/Captures.vue';
import TwitterSearch from '@/components/Watch/Panel/Twitter/Search.vue';
import TwitterTimeline from '@/components/Watch/Panel/Twitter/Timeline.vue';
import Bluesky from '@/services/Bluesky';
import { IProgram } from '@/services/Programs';
import Twitter from '@/services/Twitter';
import { ISelectableAccount } from '@/services/Users';
import useChannelsStore from '@/stores/ChannelsStore';
import usePlayerStore from '@/stores/PlayerStore';
import useSettingsStore, { ITwitterPanelPostTarget } from '@/stores/SettingsStore';
import useTwitterStore from '@/stores/TwitterStore';
import useUserStore from '@/stores/UserStore';
import Utils, { ChannelUtils, dayjs } from '@/utils';
import { TweetUtils } from '@/utils/TweetUtils';


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

interface ISelectableAccountDisplayRow {
    id: string;
    icon?: string;
    text: string;
}

// 同時投稿時の通知文と待ち合わせ処理で扱う送信先サービス
// 実際の選択状態は送信開始時点で別途スナップショットし、通知処理は現在のトグル状態を参照しない
type TweetPostService = 'Twitter' | 'Bluesky';

// 投稿 API の戻り値を DPlayer notice 向けの通知単位へ正規化した結果
// settled_at は 2 サービスの完了時刻差を判定するための値で、通知文そのものには使わない
interface ITweetPostNotificationResult {
    service: TweetPostService;
    message: string;
    is_error: boolean;
    settled_at: number;
}

// Twitter / Bluesky 同時投稿時、両方の結果を一つの DPlayer notice にまとめる最大待ち時間 (ミリ秒)
// waitForRemainingTweetPostResult のタイムアウトと、完了時刻差の統合判定の両方で同じ値を使う
const SIMULTANEOUS_TWEET_POST_NOTIFICATION_MERGE_TIMEOUT_MS = 2000;

// 送信先サービスと、そのサービスへ投げた非同期処理を対応づける
// Promise だけではどのサービスの結果か後から安全に判定できないため、service を外側にも保持する
interface ITweetPostRequest {
    service: TweetPostService;
    promise: Promise<ITweetPostNotificationResult>;
}

// 実際に DPlayer notice へ流す通知内容
// 複数サービスの結果をまとめた場合も、最終的にはこの一つの型へ畳み込む
interface ITweetPostSettledResult {
    service: TweetPostService;
    message: string;
    is_error: boolean;
}

// 投稿ボタン押下時点の送信先を固定したスナップショット
// API 応答待ちの間にトグルが変わっても、送信処理と通知文が現在の UI 状態へ引っ張られないようにする
interface ITweetPostTargetSnapshot {
    twitter_screen_name: string | null;
    bluesky_handle: string | null;
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
            return this.twitterStore.selected_account === null || this.tweet_letter_remain_count < 0 ||
                ((this.tweet_text.trim() === '' || this.tweet_letter_remain_count === 140) && this.playerStore.twitter_selected_capture_blobs.length === 0);
        },

        selectedAccountIconUrl(): string {
            const account = this.twitterStore.selected_account;
            // 紐付けアカウントの代表表示は既存 Twitter タブの見え方を保つため Twitter 側へ寄せる
            // Bluesky 側の識別はアカウント選択リスト内のバッジと二段表示で補う
            if (account?.kind === 'Twitter') return account.twitter_account.icon_url;
            if (account?.kind === 'Bluesky') return account.bluesky_account.icon_url || '/assets/images/account-icon-default.png';
            if (account?.kind === 'Linked') return account.account_link.twitter_account.icon_url;
            return '/assets/images/account-icon-default.png';
        },

        selectedAccountDisplayId(): string {
            const account = this.twitterStore.selected_account;
            // 入力欄横の短い ID 表示は一行に収める必要があるため、紐付け時は代表として Twitter 側を出す
            // Bluesky 側の handle はドロップダウン内で省略表示込みの二段表示に任せる
            if (account?.kind === 'Twitter') return `@${account.twitter_account.screen_name}`;
            if (account?.kind === 'Bluesky') return `@${account.bluesky_account.handle}`;
            if (account?.kind === 'Linked') return `@${account.account_link.twitter_account.screen_name}`;
            return '連携されていません';
        },

        shouldPostToTwitter(): boolean {
            const account = this.twitterStore.selected_account;
            if (account?.kind === 'Twitter') return true;
            if (account?.kind === 'Linked') return this.linkedPostTarget.is_post_to_twitter;
            return false;
        },

        shouldPostToBluesky(): boolean {
            const account = this.twitterStore.selected_account;
            if (account?.kind === 'Bluesky') return true;
            if (account?.kind === 'Linked') return this.linkedPostTarget.is_post_to_bluesky;
            return false;
        },

        shouldPostToBothServices(): boolean {
            return this.shouldPostToTwitter === true && this.shouldPostToBluesky === true;
        },

        isLinkedPostTargetBoth(): boolean {
            const account = this.twitterStore.selected_account;
            if (account?.kind !== 'Linked') return false;
            return this.shouldPostToBothServices;
        },

        linkedPostTargetKey(): string | null {
            const account = this.twitterStore.selected_account;
            // 送信先の切替状態は視聴中に頻繁に変わる軽い UI 状態なので DB には置かない
            // 紐付け ID ごとの LocalStorage キーにして、リンク解除後の単独アカウントへ状態を漏らさない
            if (account?.kind !== 'Linked') return null;
            return `Linked-${account.account_link.id}`;
        },

        linkedPostTarget(): ITwitterPanelPostTarget {
            const linked_post_target_key = this.linkedPostTargetKey;
            if (linked_post_target_key === null) {
                return {
                    is_post_to_twitter: true,
                    is_post_to_bluesky: true,
                };
            }
            return this.settingsStore.settings.twitter_panel_post_targets[linked_post_target_key] ?? {
                is_post_to_twitter: true,
                is_post_to_bluesky: true,
            };
        },

        tweetButtonLabel(): string {
            // Bluesky 単独投稿では「ポスト」に変え、Twitter を含む場合は抗議的に残している「ツイート」を維持する
            if (this.shouldPostToTwitter === false && this.shouldPostToBluesky === true) {
                return 'ポスト';
            }
            return 'ツイート';
        },

        tweetButtonClass(): Record<string, boolean> {
            return {
                'tweet-button--twitter': this.shouldPostToTwitter === true && this.shouldPostToBluesky === false,
                'tweet-button--bluesky': this.shouldPostToTwitter === false && this.shouldPostToBluesky === true,
                'tweet-button--both': this.shouldPostToTwitter === true && this.shouldPostToBluesky === true,
            };
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

            // Twitter タブで利用できる連携アカウントがない場合は Twitter 設定画面に飛ばす
            if (!this.twitterStore.has_twitter_panel_account) {

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

        getSelectableAccountKey(account: ISelectableAccount): string {
            // DB 上の連番 ID はテーブルごとに重複しうるため、種別を含めたキーで選択状態を安定させる
            if (account.kind === 'Twitter') return `Twitter-${account.twitter_account.id}`;
            if (account.kind === 'Bluesky') return `Bluesky-${account.bluesky_account.id}`;
            return `Linked-${account.account_link.id}`;
        },

        getSelectableAccountIconUrl(account: ISelectableAccount): string {
            // 紐付け行は Twitter 側を主アイコン、Bluesky 側を重ねバッジにする
            // 丸アバター同士を合成せず、既存の Twitter アカウント選択体験を崩さない
            if (account.kind === 'Twitter') return account.twitter_account.icon_url;
            if (account.kind === 'Bluesky') return account.bluesky_account.icon_url || '/assets/images/account-icon-default.png';
            return account.account_link.twitter_account.icon_url;
        },

        getSelectableAccountNameRows(account: ISelectableAccount): ISelectableAccountDisplayRow[] {
            if (account.kind === 'Twitter') {
                return [{id: 'twitter-name', text: account.twitter_account.name}];
            }
            if (account.kind === 'Bluesky') {
                return [{id: 'bluesky-name', text: account.bluesky_account.name}];
            }

            const twitter_name = account.account_link.twitter_account.name;
            const bluesky_name = account.account_link.bluesky_account.name;

            // 表示名が完全一致する場合は重複表示せず、1行だけ出す
            if (twitter_name === bluesky_name) {
                return [{id: 'shared-name', text: twitter_name}];
            }

            // 表示名が異なる場合だけサービスアイコン付きで2段表示する
            return [
                {id: 'twitter-name', icon: 'fa-brands:twitter', text: twitter_name},
                {id: 'bluesky-name', icon: 'simple-icons:bluesky', text: bluesky_name},
            ];
        },

        getSelectableAccountDisplayId(account: ISelectableAccount): string {
            if (account.kind === 'Twitter') {
                return `@${account.twitter_account.screen_name}`;
            }
            if (account.kind === 'Bluesky') {
                return `@${account.bluesky_account.handle}`;
            }
            return `@${account.account_link.twitter_account.screen_name}`;
        },

        isSelectableAccountSelected(account: ISelectableAccount): boolean {
            // fetchUser() のたびに選択候補のオブジェクト参照が作り直されるため、種別付きキーで比較する
            return this.twitterStore.selected_account !== null &&
                this.getSelectableAccountKey(account) === this.getSelectableAccountKey(this.twitterStore.selected_account);
        },

        // 選択されている Twitter タブ用アカウントを更新する
        updateSelectedAccount(account: ISelectableAccount) {
            // selectAccount() 内で selected_twitter_panel_account への永続化と selected_twitter_account の導出を行うため、ここでの個別更新は不要
            this.twitterStore.selectAccount(account);
            // アカウント切り替え時は API アクティビティをリセットして、不要な Keep-Alive を抑止する
            if (this.twitterStore.selected_twitter_account !== null) {
                this.twitterStore.resetAccountAPIActivity(this.twitterStore.selected_twitter_account.screen_name);
            }

            // Twitter アカウントリストのオーバーレイを閉じる (少し待ってから閉じたほうが体感が良い)
            window.setTimeout(() => this.is_twitter_account_list_display = false, 150);
        },

        cycleLinkedPostTarget() {
            const linked_post_target_key = this.linkedPostTargetKey;
            if (linked_post_target_key === null) {
                return;
            }
            const current_twitter = this.linkedPostTarget.is_post_to_twitter;
            const current_bluesky = this.linkedPostTarget.is_post_to_bluesky;
            let is_post_to_twitter = true;
            let is_post_to_bluesky = true;
            // 両方 → Twitter のみ → Bluesky のみ → 両方 の順で循環させ、空送信先の状態は作らない
            if (current_twitter === true && current_bluesky === true) {
                is_post_to_twitter = true;
                is_post_to_bluesky = false;
            } else if (current_twitter === true && current_bluesky === false) {
                is_post_to_twitter = false;
                is_post_to_bluesky = true;
            }
            this.settingsStore.settings.twitter_panel_post_targets[linked_post_target_key] = {
                is_post_to_twitter,
                is_post_to_bluesky,
            };
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

            // Twitter タブ用アカウントが連携されていない場合は何もしない
            if (this.twitterStore.selected_account === null) return;

            // 送信中フラグを立てる (重複送信防止)
            if (this.is_tweet_sending === true) return;
            this.is_tweet_sending = true;

            // 送信先トグルは送信中でも操作できるため、以降の処理では現在値を見ない
            // ここで固定した送信先だけを使い、API 呼び出しと完了通知の整合性を保つ
            const post_target_snapshot = this.createTweetPostTargetSnapshot();
            if (post_target_snapshot.twitter_screen_name === null && post_target_snapshot.bluesky_handle === null) {
                this.is_tweet_sending = false;
                return;
            }

            // ハッシュタグを整形
            this.tweet_hashtag = this.formatHashtag(this.tweet_hashtag);
            const tweet_hashtag = this.tweet_hashtag;
            const tweet_hashtags = tweet_hashtag !== '' ? tweet_hashtag.split(' ') : [];
            // 局タグの自動追加も反映済みのハッシュタグセットで判定し、ユーザーが実際に投稿する文脈とツリーを一致させる
            const hashtag_key = TweetUtils.normalizeHashtagKey(tweet_hashtags);
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

            const send_results: ITweetPostRequest[] = [];
            // 紐付けアカウントでもサーバー側の統合投稿 API は作らず、フロントから各サービスへ独立して送る
            // 片方が凍結や API エラーで失敗しても、もう片方の投稿結果は通知として残す
            if (post_target_snapshot.twitter_screen_name !== null) {
                // Twitter 送信は押下時点の screen_name だけを参照する
                // 送信中にアカウント選択や送信先トグルが変わっても、この Promise の宛先は変えない
                send_results.push({
                    service: 'Twitter',
                    promise: this.sendTweetToService('Twitter',
                        this.sendTweetWithReplyThread(post_target_snapshot.twitter_screen_name, tweet_text, tweet_capture_blobs, hashtag_key)),
                });
            }
            if (post_target_snapshot.bluesky_handle !== null) {
                // Bluesky 送信も押下時点の handle へ固定する
                // 同時投稿から単独投稿へ即座に戻しても、完了通知はこの送信で実際に投げた対象だけを扱う
                send_results.push({
                    service: 'Bluesky',
                    promise: this.sendTweetToService('Bluesky',
                        this.sendBlueskyPostWithReplyThread(post_target_snapshot.bluesky_handle, tweet_text, tweet_capture_blobs, hashtag_key)),
                });
            }

            await this.notifyTweetPostResults(send_results);

            // 送信中フラグを下ろす
            this.is_tweet_sending = false;

            // パネルを閉じる
            if (this.settingsStore.settings.fold_panel_after_sending_tweet === true) {
                this.playerStore.is_panel_display = false;
                (this.$refs.tweet_text as HTMLTextAreaElement).blur();  // フォーカスを外す
            }
        },

        createTweetPostTargetSnapshot(): ITweetPostTargetSnapshot {

            const account = this.twitterStore.selected_account;
            // 単独 Twitter アカウントでは Twitter だけへ送る
            // 紐付けアカウントのトグル状態は存在しないため、現在の選択アカウントそのものが送信先になる
            if (account?.kind === 'Twitter') {
                return {
                    twitter_screen_name: account.twitter_account.screen_name,
                    bluesky_handle: null,
                };
            }
            // 単独 Bluesky アカウントでは Bluesky だけへ送る
            // 通知文もこのスナップショットに基づいて単体送信として扱う
            if (account?.kind === 'Bluesky') {
                return {
                    twitter_screen_name: null,
                    bluesky_handle: account.bluesky_account.handle,
                };
            }
            // 紐付けアカウントでは投稿ボタン押下時点のトグル状態を固定する
            // 画像処理や API 待ちの間にユーザーがトグルを変更しても、この送信の宛先と通知内容は変えない
            if (account?.kind === 'Linked') {
                // 投稿ボタンを押した瞬間のトグル状態を固定する
                // 送信中にユーザーが送信先を切り替えても、この送信と完了通知は押下時点の対象だけを参照する
                return {
                    twitter_screen_name: this.linkedPostTarget.is_post_to_twitter === true ? account.account_link.twitter_account.screen_name : null,
                    bluesky_handle: this.linkedPostTarget.is_post_to_bluesky === true ? account.account_link.bluesky_account.handle : null,
                };
            }
            return {
                twitter_screen_name: null,
                bluesky_handle: null,
            };
        },

        async sendTweetWithReplyThread(
            screen_name: string,
            tweet_text: string,
            tweet_capture_blobs: Blob[],
            hashtag_key: string,
        ): Promise<IPostTweetSendResult> {

            const settings = this.settingsStore.settings;
            const state = settings.twitter_reply_thread_states[screen_name];
            const now = dayjs();
            const decision = TweetUtils.decideReplyThread({
                mode: settings.twitter_reply_thread_mode,
                state,
                current_hashtag_key: hashtag_key,
                now,
            });

            // リプライ先は送信直前の状態から固定し、API 待ちの間に状態が変わってもこの投稿の宛先を変えない
            const in_reply_to_status_id = decision.send_as_reply === true && state !== undefined ? state.last_tweet_id : null;
            const result = await Twitter.sendTweet(screen_name, tweet_text, tweet_capture_blobs, in_reply_to_status_id);
            if (result.is_error === true || result.tweet_id === null) {
                return result;
            }

            // リプライツリー状態は送信成功時だけ更新し、失敗時は前回の親へ再試行できる余地を残す
            if (decision.send_as_reply === true && state !== undefined) {
                settings.twitter_reply_thread_states[screen_name] = {
                    ...state,
                    last_tweet_id: result.tweet_id,
                };
            } else if (decision.reset_state_after === true) {
                settings.twitter_reply_thread_states[screen_name] = {
                    last_tweet_id: result.tweet_id,
                    started_at: now.toISOString(),
                    hashtag_key,
                };
            } else if (decision.clear_state === true) {
                delete settings.twitter_reply_thread_states[screen_name];
            }

            return result;
        },

        async sendBlueskyPostWithReplyThread(
            handle: string,
            tweet_text: string,
            tweet_capture_blobs: Blob[],
            hashtag_key: string,
        ): Promise<IPostTweetSendResult> {

            const settings = this.settingsStore.settings;
            const state = settings.bluesky_reply_thread_states[handle];
            const now = dayjs();
            const decision = TweetUtils.decideReplyThread({
                mode: settings.bluesky_reply_thread_mode,
                state,
                current_hashtag_key: hashtag_key,
                now,
            });

            // Bluesky のリプライはルートと親ポストの StrongRef が必要なので、保存済み状態が揃う時だけ渡す
            const reply_to = decision.send_as_reply === true && state !== undefined ? {
                root_uri: state.root_uri,
                root_cid: state.root_cid,
                parent_uri: state.parent_uri,
                parent_cid: state.parent_cid,
            } : null;
            const result = await Bluesky.sendPost(handle, tweet_text, tweet_capture_blobs, reply_to);
            if (result.is_error === true || result.post_uri === null || result.post_cid === null) {
                return result;
            }

            // ルートはツリーの起点として固定し、返信が伸びた時は直前の親ポストだけを新しい投稿へ進める
            if (decision.send_as_reply === true && state !== undefined) {
                settings.bluesky_reply_thread_states[handle] = {
                    ...state,
                    parent_uri: result.post_uri,
                    parent_cid: result.post_cid,
                };
            } else if (decision.reset_state_after === true) {
                settings.bluesky_reply_thread_states[handle] = {
                    root_uri: result.post_uri,
                    root_cid: result.post_cid,
                    parent_uri: result.post_uri,
                    parent_cid: result.post_cid,
                    started_at: now.toISOString(),
                    hashtag_key,
                };
            } else if (decision.clear_state === true) {
                delete settings.bluesky_reply_thread_states[handle];
            }

            return result;
        },

        async sendTweetToService(
            service: TweetPostService,
            send_result: Promise<IPostTweetSendResult>,
        ): Promise<ITweetPostNotificationResult> {

            try {
                // 成功 / 失敗の詳細文は各サービスの送信関数に任せる
                // ここでは完了時刻とサービス名を付与し、後段で統合通知できる形へ揃える
                const result = await send_result;
                return {
                    service,
                    message: result.message,
                    is_error: result.is_error,
                    settled_at: performance.now(),
                };
            } catch (error) {
                // 各送信関数は通常 reject せずに {message, is_error: true} を返す設計だが、
                // APIClient 以前のネットワーク断などで reject が漏れる経路を想定して保険を入れる
                console.error('Tweet sending promise rejected unexpectedly.', error);
                return {
                    service,
                    message: service === 'Twitter' ? 'Twitter へのツイートに失敗しました。' : 'Bluesky へのポストに失敗しました。',
                    is_error: true,
                    settled_at: performance.now(),
                };
            }
        },

        async notifyTweetPostResults(send_results: ITweetPostRequest[]): Promise<void> {

            if (send_results.length === 0) {
                return;
            }

            if (send_results.length === 1) {
                // 単体投稿では待ち合わせせず、従来通りそのサービスの結果だけを即時通知する
                // 成功文はサービスごとに統一し、API 側 detail の揺れを画面へ出さない
                const result = await send_results[0].promise;
                this.emitTweetPostNotification(this.formatSingleTweetPostNotification(result));
                return;
            }

            // DPlayer の notice は同時に一つしか表示できないため、近いタイミングの二重投稿結果だけを短時間待ち合わせる
            // Twitter 側だけ大きく遅い場合は先に返ったサービスを従来通り個別通知し、待たされる体感を避ける
            const first_result = await Promise.race(send_results.map(send_result => send_result.promise));
            const second_result = await this.waitForRemainingTweetPostResult(
                send_results,
                first_result.service,
                SIMULTANEOUS_TWEET_POST_NOTIFICATION_MERGE_TIMEOUT_MS,
            );
            if (second_result !== null &&
                second_result.settled_at - first_result.settled_at <= SIMULTANEOUS_TWEET_POST_NOTIFICATION_MERGE_TIMEOUT_MS) {
                // 待ち合わせ時間以内に両方返った場合だけ一つの notice へまとめる
                // ここでまとめないと DPlayer 側で後勝ち上書きになり、片方の結果をユーザーが見落とす
                this.emitTweetPostNotification(this.formatMergedTweetPostNotification([first_result, second_result]));
                return;
            }

            // 片方だけ先に返り、もう片方が待ち合わせ時間以内に返らない場合は待たせず個別通知へ戻す
            // Twitter の投稿 UI 経路は遅くなることがあるため、同時投稿でも常に統合待ちにはしない
            this.emitTweetPostNotification(this.formatSingleTweetPostNotification(first_result));
            if (second_result !== null) {
                this.emitTweetPostNotification(this.formatSingleTweetPostNotification(second_result));
                return;
            }

            // タイムアウト後に遅れて返ったサービスは、その時点で単体結果として通知する
            // 先に表示した notice を無理に再統合すると、実際の完了順とユーザー体感がずれる
            const delayed_result = await send_results.find(send_result => send_result.service !== first_result.service)!.promise;
            this.emitTweetPostNotification(this.formatSingleTweetPostNotification(delayed_result));
        },

        async waitForRemainingTweetPostResult(
            send_results: ITweetPostRequest[],
            first_result_service: TweetPostService,
            timeout_milliseconds: number,
        ): Promise<ITweetPostNotificationResult | null> {

            const remaining_result = send_results.find(send_result => send_result.service !== first_result_service);
            if (remaining_result === undefined) {
                return null;
            }
            // もう片方の投稿結果が短時間で返るかだけを見る
            // タイムアウト時は null を返し、呼び出し側で個別通知へ切り替える
            const timeout_result = new Promise<null>(resolve => {
                window.setTimeout(() => resolve(null), timeout_milliseconds);
            });
            return await Promise.race([remaining_result.promise, timeout_result]);
        },

        formatSingleTweetPostNotification(result: ITweetPostNotificationResult): ITweetPostSettledResult {

            if (result.is_error === true) {
                // 失敗時は API 側やネットワーク層で作った詳細文をそのまま出す
                // 成功時だけ UI 文言をサービス名つきの統一文へ差し替える
                return {
                    service: result.service,
                    message: result.message,
                    is_error: true,
                };
            }

            return {
                service: result.service,
                message: result.service === 'Twitter' ? 'Twitter にツイートしました。' : 'Bluesky にポストしました。',
                is_error: false,
            };
        },

        formatMergedTweetPostNotification(results: ITweetPostNotificationResult[]): ITweetPostSettledResult {

            const twitter_result = results.find(result => result.service === 'Twitter');
            const bluesky_result = results.find(result => result.service === 'Bluesky');
            // 両方成功した場合は、DPlayer notice の一枠で同時送信成功を伝える
            // 送信先は押下時点のスナップショット由来なので、現在のトグル状態はここでも参照しない
            if (twitter_result?.is_error === false && bluesky_result?.is_error === false) {
                return {
                    service: 'Twitter',
                    message: 'Twitter と Bluesky に同時ツイートしました。',
                    is_error: false,
                };
            }

            // 片方だけ失敗した場合は、成功側と失敗側を一文にまとめる
            // notice が上書きされる制約下でも、どちらが成功したかを一目で分かるようにする
            if (twitter_result?.is_error === true && bluesky_result?.is_error === false) {
                return {
                    service: 'Twitter',
                    message: `Bluesky にポストしました。Twitter へのツイートは失敗しました。(${twitter_result.message})`,
                    is_error: true,
                };
            }

            // Twitter 成功 / Bluesky 失敗も同じく一つの notice に集約する
            // 失敗詳細は原因調査に使えるため、括弧内に元メッセージを残す
            if (twitter_result?.is_error === false && bluesky_result?.is_error === true) {
                return {
                    service: 'Bluesky',
                    message: `Twitter にツイートしました。Bluesky へのポストは失敗しました。(${bluesky_result.message})`,
                    is_error: true,
                };
            }

            // 両方失敗した場合は、各サービスの失敗理由を一つの notice に連結する
            // どちらか一方だけ失敗したように見えないよう、サービス横断の失敗として扱う
            return {
                service: 'Twitter',
                message: `Twitter と Bluesky へのツイートに失敗しました。(${results.map(result => result.message).join(' / ')})`,
                is_error: true,
            };
        },

        emitTweetPostNotification(result: ITweetPostSettledResult): void {

            // DPlayer 側の notice 表示は SendNotification イベントに集約されている
            // エラー時だけ赤系の色を指定し、成功時は既存 notice の既定色を使う
            this.playerStore.event_emitter.emit('SendNotification', {
                message: result.message,
                color: result.is_error ? '#FF6F6A' : undefined,
            });
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
            min-width: 0;
            height: 32px;
            margin-top: 6px;
            @include smartphone-horizontal {
                height: 26px;
                column-gap: 3px;
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
                    flex: 1 1 0;
                    min-width: 0;
                    width: auto;
                    border-radius: 5px;
                    font-size: 11px;
                }
                @include smartphone-vertical {
                    flex: 1 1 0;
                    min-width: 0;
                    width: auto;
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
                    min-width: 0;
                    padding-left: 3px;
                    padding-right: 3px;
                    line-height: 2;
                    text-align: center;
                    font-weight: bold;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }
                &__menu {
                    flex-shrink: 0;
                    margin-right: 4px;
                    @include smartphone-horizontal {
                        margin-right: 2px;

                        :deep(svg) {
                            width: 18px;
                            height: 18px;
                        }
                    }
                }
            }

            .limit-meter {
                display: flex;
                align-items: center;
                justify-content: center;
                flex-direction: column;
                flex-grow: 1;
                row-gap: 0.5px;
                min-width: 45px;
                font-size: 10px;
                color: rgb(var(--v-theme-text-darken-1));
                user-select: none;
                @include tablet-vertical {
                    flex-grow: 1;
                    flex-direction: row;
                    width: auto;
                }
                @include smartphone-horizontal {
                    flex-grow: 0;
                    flex-shrink: 0;
                    min-width: 34px;
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
                        margin-left: 4.5px;
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

            .dual-service-icon {
                display: inline-flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                flex-shrink: 0;
                line-height: 0;

                :deep(svg) {
                    display: block;
                }

                &--post-target :deep(svg) {
                    width: 12.5px;
                    height: 12.5px;
                    @include smartphone-horizontal {
                        width: 9px;
                        height: 9px;
                    }
                }

                &--tweet-button :deep(svg) {
                    width: 13.5px;
                    height: 13.5px;
                    @include smartphone-horizontal {
                        width: 10px;
                        height: 10px;
                    }
                }
            }

            .post-target-button {
                display: flex;
                align-items: center;
                justify-content: center;
                flex-shrink: 0;
                column-gap: 3px;
                width: 34px;
                height: 100%;
                border-radius: 7px;
                margin-left: 4px;
                color: rgb(var(--v-theme-text));
                background: rgb(var(--v-theme-background-lighten-2));
                cursor: pointer;
                @include smartphone-horizontal {
                    width: 24px;
                    margin-left: 0;
                    border-radius: 5px;
                }
                @include smartphone-vertical {
                    width: 30px;
                    border-radius: 5px;
                }
            }

            .tweet-button {
                display: flex;
                align-items: center;
                justify-content: center;
                flex-shrink: 0;
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
                    width: 80px;
                    padding-left: 4px;
                    padding-right: 4px;
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

                &--twitter {
                    background: rgb(var(--v-theme-twitter));
                }

                &--bluesky {
                    background: #0F73FF;
                }

                &--both {
                    background: linear-gradient(90deg, rgb(var(--v-theme-twitter)) 0%, #0F73FF 100%);
                }
            }

            &--linked {
                .account-button {
                    // Linked アカウントでは投稿ボタンの寸法を固定したまま、
                    // 送信先切り替えボタン・文字数表示を詰めて名前表示を広げる
                    min-width: 0;
                    @include tablet-vertical {
                        width: 200px;
                    }
                    @include tablet-horizontal {
                        width: 162px;
                        border-radius: 5px;
                    }
                    @include desktop {
                        width: 162px;
                    }

                    .account-button__menu {
                        width: 18px;
                        height: 18px;
                        margin-right: 2px;
                        @include smartphone-horizontal {
                            width: 16px;
                            height: 16px;
                        }
                        @include smartphone-vertical {
                            width: 16px;
                            height: 16px;
                        }
                    }
                }

                .post-target-button {
                    width: 26px;
                    column-gap: 2px;
                    margin-left: 3px;
                    @include smartphone-horizontal {
                        width: 20px;
                        margin-left: 0;
                    }
                    @include smartphone-vertical {
                        width: 24px;
                        margin-left: 3px;
                    }
                }

                .dual-service-icon--post-target :deep(svg) {
                    width: 10px;
                    height: 10px;
                    @include smartphone-horizontal {
                        width: 8px;
                        height: 8px;
                    }
                    @include smartphone-vertical {
                        width: 9px;
                        height: 9px;
                    }
                }

                .limit-meter {
                    min-width: 42px;
                    @include smartphone-horizontal {
                        min-width: 31px;
                    }
                    @include smartphone-vertical {
                        width: 80px;
                    }

                    .limit-meter__content {
                        svg {
                            @include smartphone-horizontal {
                                width: 12px;
                                height: 12px;
                            }
                        }

                        span {
                            @include smartphone-horizontal {
                                width: 14px;
                                margin-left: 3.5px;
                                font-size: 8.5px;
                            }
                        }
                    }
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

            &__icon-wrapper {
                position: relative;
                flex-shrink: 0;
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
            &__icon-badge {
                position: absolute;
                top: -6px;
                right: -6px;
                width: 26px;
                height: 26px;
                border: 2px solid rgb(var(--v-theme-background-lighten-2));
                border-radius: 50%;
                object-fit: cover;
                @include smartphone-horizontal {
                    width: 18px;
                    height: 18px;
                }
                @include smartphone-vertical {
                    width: 18px;
                    height: 18px;
                }
            }
            &__service-badge {
                position: absolute;
                left: 0px;
                bottom: 0px;
                color: #fff;
                line-height: 0;

                &--twitter,
                &--bluesky {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    width: 20px;
                    height: 20px;
                    border-radius: 5px;

                    :deep(svg) {
                        width: 11px;
                        height: 11px;
                    }
                }

                // 視聴パネルのツイートボタンと同じ Twitter ブランドカラー
                &--twitter {
                    background: rgb(var(--v-theme-twitter));
                }

                // 視聴パネルのポストボタンと同じ Bluesky ブランドカラー
                &--bluesky {
                    background: #0F73FF;
                }

                &--linked {
                    display: flex;
                    width: 40px;
                    height: 20px;
                }

                &-segment {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    flex: 1 1 50%;
                    height: 100%;

                    :deep(svg) {
                        width: 10px;
                        height: 10px;
                    }

                    &--twitter {
                        background: rgb(var(--v-theme-twitter));
                        border-radius: 5px 0 0 5px;
                    }

                    &--bluesky {
                        background: #0F73FF;
                        border-radius: 0 5px 5px 0;
                    }
                }

                @include smartphone-horizontal {
                    &--twitter,
                    &--bluesky {
                        width: 16px;
                        height: 16px;
                        border-radius: 4px;

                        :deep(svg) {
                            width: 9px;
                            height: 9px;
                        }
                    }

                    &--linked {
                        width: 32px;
                        height: 16px;
                    }

                    &-segment {
                        :deep(svg) {
                            width: 8px;
                            height: 8px;
                        }

                        &--twitter {
                            border-radius: 4px 0 0 4px;
                        }

                        &--bluesky {
                            border-radius: 0 4px 4px 0;
                        }
                    }
                }
                @include smartphone-vertical {
                    &--twitter,
                    &--bluesky {
                        width: 16px;
                        height: 16px;
                        border-radius: 4px;

                        :deep(svg) {
                            width: 9px;
                            height: 9px;
                        }
                    }

                    &--linked {
                        width: 32px;
                        height: 16px;
                    }

                    &-segment {
                        :deep(svg) {
                            width: 8px;
                            height: 8px;
                        }

                        &--twitter {
                            border-radius: 4px 0 0 4px;
                        }

                        &--bluesky {
                            border-radius: 0 4px 4px 0;
                        }
                    }
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
                display: flex;
                align-items: center;
                column-gap: 6px;
                min-width: 0;
                max-width: 100%;
                overflow: hidden;
                font-size: 17px;
                font-weight: bold;
                white-space: nowrap;
                color: rgb(var(--v-theme-text));
                @include smartphone-horizontal {
                    font-size: 14px;
                    line-height: 1.3;
                }
                @include smartphone-vertical {
                    font-size: 14px;
                    line-height: 1.3;
                }
            }
            &__name-service-icon {
                display: block;
                flex-shrink: 0;
                width: 13px;
                height: 13px;
                font-size: 13px;
                @include smartphone-horizontal {
                    width: 11px;
                    height: 11px;
                    font-size: 11px;
                }
                @include smartphone-vertical {
                    width: 11px;
                    height: 11px;
                    font-size: 11px;
                }
            }
            &__screen-name {
                min-width: 0;
                overflow: hidden;
                color: rgb(var(--v-theme-text-darken-1));
                font-size: 14px;
                line-height: 1.4;
                @include smartphone-horizontal {
                    font-size: 13px;
                }
                @include smartphone-vertical {
                    font-size: 13px;
                }

                &-handle {
                    display: inline-block;
                    max-width: 100%;
                    vertical-align: middle;
                    overflow: hidden;
                    white-space: nowrap;
                    text-overflow: ellipsis;

                    // 単体アカウント行は1行全体を使って ellipsis する
                    &:only-child {
                        display: block;
                    }
                }

                &-link-icon {
                    display: inline-flex;
                    align-items: center;
                    vertical-align: middle;
                    margin: 0 6px;
                    width: 14px;
                    height: 14px;
                    font-size: 14px;
                    @include smartphone-horizontal {
                        width: 12px;
                        height: 12px;
                        font-size: 12px;
                    }
                    @include smartphone-vertical {
                        width: 12px;
                        height: 12px;
                        font-size: 12px;
                    }
                }
            }
            &__text {
                min-width: 0;
                flex: 1 1 auto;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            &__check {
                flex-shrink: 0;
                color: rgb(var(--v-theme-twitter-lighten-1));
            }
        }
    }
}

</style>
