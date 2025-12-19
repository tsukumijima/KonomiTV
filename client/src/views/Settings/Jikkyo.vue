<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <SettingsBase>
        <h2 class="settings__heading">
            <a v-ripple class="settings__back-button" @click="$router.back()">
                <Icon icon="fluent:chevron-left-12-filled" width="27px" />
            </a>
            <Icon icon="bi:chat-left-text-fill" width="19px" />
            <span class="ml-3">ニコニコ実況</span>
        </h2>
        <div class="settings__content" :class="{'settings__content--loading': is_loading}">
            <div class="niconico-account niconico-account--anonymous" v-if="userStore.user === null || userStore.user.niconico_user_id === null">
                <div class="niconico-account-wrapper">
                    <Icon class="flex-shrink-0" icon="bi:chat-left-text-fill" width="45px" />
                    <div class="niconico-account__info ml-4">
                        <div class="niconico-account__info-name">
                            <span class="niconico-account__info-name-text">ニコニコアカウントと連携していません</span>
                        </div>
                        <span class="niconico-account__info-description">
                            ニコニコアカウントと連携すると、テレビを見ながらニコニコ実況にコメントできるようになります。
                        </span>
                    </div>
                </div>
                <v-btn class="niconico-account__login ml-auto" color="secondary" width="130" height="56" variant="flat"
                    @click="loginNiconicoAccount()">
                    <Icon icon="fluent:plug-connected-20-filled" class="mr-2" height="26" />連携する
                </v-btn>
            </div>
            <div class="niconico-account" v-if="userStore.user !== null && userStore.user.niconico_user_id !== null">
                <div class="niconico-account-wrapper">
                    <img class="niconico-account__icon" :src="userStore.user_niconico_icon_url ?? ''" @error="setDefaultIcon">
                    <div class="niconico-account__info">
                        <div class="niconico-account__info-name">
                            <span class="niconico-account__info-name-text">{{userStore.user.niconico_user_name}} と連携しています</span>
                        </div>
                        <span class="niconico-account__info-description">
                            <span class="mr-2" style="white-space: nowrap;">Niconico User ID:</span>
                            <a class="link mr-2" :href="`https://www.nicovideo.jp/user/${userStore.user.niconico_user_id}`"
                                target="_blank">{{userStore.user.niconico_user_id}}</a>
                            <span class="text-secondary" v-if="userStore.user.niconico_user_premium === true">(Premium)</span>
                        </span>
                    </div>
                </div>
                <v-btn class="niconico-account__login ml-auto" color="secondary" width="130" height="56" variant="flat"
                    @click="logoutNiconicoAccount()">
                    <Icon icon="fluent:plug-disconnected-20-filled" class="mr-2" height="26" />連携解除
                </v-btn>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="prefer_posting_to_nicolive">可能であればニコニコ実況にコメントする</label>
                <label class="settings__item-label" for="prefer_posting_to_nicolive">
                    <ul class="ml-4 mb-2 font-weight-bold">
                        <li>オン：<a class="link" href="https://jk.nicovideo.jp" target="_blank">ニコニコ実況</a> に優先的にコメントを送信</li>
                        <li>オフ：<a class="link" href="https://nx-jikkyo.tsukumijima.net" target="_blank">NX-Jikkyo</a> にコメントを送信</li>
                    </ul>
                    ニコニコ実況が利用できない場合（BS 民放など公式では廃止された実況チャンネル・ニコニコ生放送のメンテナンス中など）は、常に NX-Jikkyo にコメントします。
                </label>
                <label class="settings__item-label mt-2" for="prefer_posting_to_nicolive">
                    ニコニコ実況にコメントするには、ニコニコアカウントとの連携が必要です。<br>
                    NX-Jikkyo は「ニコニコ実況の Web 版非公式コメントビューア」＋「ニコニコ実況公式にない実況チャンネルを補完する互換コメントサーバー」で、アカウント不要でコメントできます。<br>
                </label>
                <label class="settings__item-label mt-2" for="prefer_posting_to_nicolive">
                    ニコニコアカウント未連携でのコメント送信時に「代わりに NX-Jikkyo にコメントします」という通知を表示しないようにするには、この設定をオフにしてください。
                </label>
                <v-switch class="settings__item-switch" color="primary" id="prefer_posting_to_nicolive" hide-details
                    v-model="settingsStore.settings.prefer_posting_to_nicolive">
                </v-switch>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">コメントのミュート設定</div>
                <div class="settings__item-label">
                    表示したくないコメントを、映像上やコメントリストに表示しないようにミュートできます。<br>
                </div>
                <div class="settings__item-label mt-2">
                    デフォルトでは、下記のミュート設定がオンになっています。<br>
                    これらのコメントも表示したい方は、適宜オフに設定してください。<br>
                    <ul class="ml-5 mt-2">
                        <li>露骨な表現を含むコメントをミュートする</li>
                        <li>ネガティブな表現、差別的な表現、政治的に偏った表現を含むコメントをミュートする</li>
                        <li>文字サイズが大きいコメントをミュートする</li>
                    </ul>
                </div>
            </div>
            <v-btn class="settings__save-button mt-4" variant="flat" @click="comment_mute_settings_modal = !comment_mute_settings_modal">
                <Icon icon="heroicons-solid:filter" height="19px" />
                <span class="ml-1">コメントのミュート設定を開く</span>
            </v-btn>
            <v-divider class="mt-6"></v-divider>
            <div class="settings__quote mt-7">
                「コメントを表示」「コメントを無制限に表示」「コメントの不透明度」の各設定は、<br>プレイヤー下にある設定アイコン ⚙️ からも随時変更できます。<br>
            </div>
            <div class="settings__item settings__item--switch settings__item--sync-disabled">
                <label class="settings__item-heading" for="show_comment">コメントを表示</label>
                <label class="settings__item-label" for="show_comment">
                    プレイヤーにニコニコ実況 / NX-Jikkyo のコメントを流すかどうかを設定します。<br>
                    コメントを非表示にしても、画面右側にあるパネルのコメントリストには表示されます。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="show_comment" hide-details
                    v-model="show_comment">
                </v-switch>
            </div>
            <div class="settings__item settings__item--switch settings__item--sync-disabled">
                <label class="settings__item-heading" for="show_comment_unlimited">コメントを無制限に表示</label>
                <label class="settings__item-label" for="show_comment_unlimited">
                    オンにすると、コメントの重なりを許容し、可能な限り多くのコメントを表示します。<br>
                    コメントが多い番組でオンにすると、映像が見づらくなる可能性があります。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="show_comment_unlimited" hide-details
                    v-model="show_comment_unlimited">
                </v-switch>
            </div>
            <div class="settings__item settings__item--sync-disabled">
                <div class="settings__item-heading">コメントの不透明度</div>
                <div class="settings__item-label">
                    プレイヤーに流れるコメントの不透明度を設定します。<br>
                    0% に設定するとコメントが完全に透明になり、100% に設定すると完全に不透明になります。<br>
                </div>
                <v-slider class="settings__item-form" color="primary" show-ticks="always" thumb-label hide-details
                    :step="0.05" :min="0" :max="1" v-model="comment_opacity">
                    <template #thumb-label="{ modelValue }">
                        {{ Math.round(modelValue * 100) }}%
                    </template>
                </v-slider>
            </div>
            <v-divider class="mt-6"></v-divider>
            <div class="settings__item">
                <div class="settings__item-heading">コメントの速さ</div>
                <div class="settings__item-label">
                    プレイヤーに流れるコメントの速さを設定します。<br>
                    たとえば 1.2 に設定すると、コメントが 1.2 倍速く流れます。<br>
                </div>
                <v-slider class="settings__item-form" color="primary" show-ticks="always" thumb-label hide-details
                    :step="0.1" :min="0.5" :max="2" v-model="settingsStore.settings.comment_speed_rate">
                </v-slider>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">コメントの文字サイズ</div>
                <div class="settings__item-label">
                    プレイヤーに流れるコメントの文字サイズの基準値を設定します。<br>
                    実際の文字サイズは画面サイズに合わせて調整されます。デフォルトの文字サイズは 34px です。<br>
                </div>
                <v-slider class="settings__item-form" color="primary" show-ticks="always" thumb-label hide-details
                    :step="1" :min="20" :max="60" v-model="settingsStore.settings.comment_font_size">
                </v-slider>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="close_comment_form_after_sending">コメント送信後にコメント入力フォームを閉じる</label>
                <label class="settings__item-label" for="close_comment_form_after_sending">
                    オンにすると、コメント送信後に、コメント入力フォームが自動で閉じるようになります。<br>
                    コメント入力フォームが表示されたままだと、大半のショートカットキーが文字入力と競合して使えなくなります。とくに理由がなければ、オンにしておくのがおすすめです。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="close_comment_form_after_sending" hide-details
                    v-model="settingsStore.settings.close_comment_form_after_sending">
                </v-switch>
            </div>
        </div>
        <CommentMuteSettings :modelValue="comment_mute_settings_modal" @update:modelValue="comment_mute_settings_modal = $event" />
    </SettingsBase>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent } from 'vue';

import CommentMuteSettings from '@/components/Settings/CommentMuteSettings.vue';
import Message from '@/message';
import Niconico from '@/services/Niconico';
import useSettingsStore from '@/stores/SettingsStore';
import useUserStore from '@/stores/UserStore';
import Utils from '@/utils';
import SettingsBase from '@/views/Settings/Base.vue';

export default defineComponent({
    name: 'Settings-Jikkyo',
    components: {
        SettingsBase,
        CommentMuteSettings,
    },
    data() {
        return {

            // コメントのミュート設定のモーダルを表示するか
            comment_mute_settings_modal: false,

            // ローディング中かどうか
            is_loading: true,

            // コメントを表示するか (LocalStorage: dplayer-danmaku-show)
            show_comment: true,

            // コメントを無制限に表示するか (LocalStorage: dplayer-danmaku-unlimited)
            show_comment_unlimited: false,

            // コメントの不透明度 (LocalStorage: dplayer-danmaku-opacity)
            comment_opacity: 0.5,
        };
    },
    watch: {
        show_comment(new_value: boolean) {
            // コメント表示設定を LocalStorage に保存する
            localStorage.setItem('dplayer-danmaku-show', new_value ? '1' : '0');
        },
        show_comment_unlimited(new_value: boolean) {
            // コメント無制限表示設定を LocalStorage に保存する
            localStorage.setItem('dplayer-danmaku-unlimited', new_value ? '1' : '0');
        },
        comment_opacity(new_value: number) {
            // コメント不透明度設定を LocalStorage に保存する
            localStorage.setItem('dplayer-danmaku-opacity', new_value.toString());
        },
    },
    computed: {
        ...mapStores(useSettingsStore, useUserStore),
    },
    async created() {

        // LocalStorage からコメント表示設定を読み込む
        const show_comment_raw = localStorage.getItem('dplayer-danmaku-show');
        if (show_comment_raw !== null) {
            this.show_comment = show_comment_raw === '1';
        }

        // LocalStorage からコメント無制限表示設定を読み込む
        const show_comment_unlimited_raw = localStorage.getItem('dplayer-danmaku-unlimited');
        if (show_comment_unlimited_raw !== null) {
            this.show_comment_unlimited = show_comment_unlimited_raw === '1';
        }

        // LocalStorage からコメント透明度設定を読み込む
        const comment_opacity_raw = localStorage.getItem('dplayer-danmaku-opacity');
        if (comment_opacity_raw !== null) {
            this.comment_opacity = parseFloat(comment_opacity_raw);
        }

        // アカウント情報を更新
        await this.userStore.fetchUser();

        // ローディング状態を解除
        this.is_loading = false;

        // もしハッシュ (# から始まるフラグメント) に何か指定されていたら、
        // OAuth 連携のコールバックの結果が入っている可能性が高いので、パースを試みる
        // アカウント情報更新より後にしないと Snackbar がうまく表示されない
        if (location.hash !== '') {
            const params = new URLSearchParams(location.hash.replace('#', ''));
            if (params.get('status') !== null && params.get('detail') !== null) {
                // コールバックの結果を取得できたので、OAuth 連携の結果を画面に通知する
                const authorization_status = parseInt(params.get('status')!);
                const authorization_detail = params.get('detail')!;
                this.onOAuthCallbackReceived(authorization_status, authorization_detail);
                // URL からフラグメントを削除
                // ref: https://stackoverflow.com/a/49373716/17124142
                history.replaceState(null, '', ' ');
            }
        }
    },
    methods: {
        setDefaultIcon(event: Event) {
            (event.target as HTMLImageElement).src = '/assets/images/account-icon-default.png';
        },

        async loginNiconicoAccount() {

            // ログインしていない場合はエラーにする
            if (this.userStore.is_logged_in === false) {
                Message.warning('連携をはじめるには、KonomiTV アカウントにログインしてください。');
                return;
            }

            // ニコニコアカウントと連携するための認証 URL を取得
            const authorization_url = await Niconico.fetchAuthorizationURL();
            if (authorization_url === null) {
                return;
            }

            // モバイルデバイスではポップアップが事実上使えない (特に Safari ではブロックされてしまう) ので、素直にリダイレクトで実装する
            if (Utils.isMobileDevice() === true) {
                location.href = authorization_url;
                return;
            }

            // OAuth 連携のため、認証 URL をポップアップウインドウで開く
            // window.open() の第2引数はユニークなものにしておくと良いらしい
            // ref: https://qiita.com/catatsuy/items/babce8726ea78f5d25b1 (大変参考になりました)
            const popup_window = window.open(authorization_url, 'KonomiTV-OAuthPopup', Utils.getWindowFeatures());
            if (popup_window === null) {
                Message.error('ポップアップウインドウを開けませんでした。');
                return;
            }

            // 認証完了 or 失敗後、ポップアップウインドウから送信される文字列を受信
            const onMessage = async (event) => {

                // すでにウインドウが閉じている場合は実行しない
                if (popup_window.closed) return;

                // 受け取ったオブジェクトに KonomiTV-OAuthPopup キーがない or そもそもオブジェクトではない際は実行しない
                // ブラウザの拡張機能から結構余計な message が飛んでくるっぽい…。
                if (Utils.typeof(event.data) !== 'object') return;
                if (('KonomiTV-OAuthPopup' in event.data) === false) return;

                // 認証は完了したので、ポップアップウインドウを閉じ、リスナーを解除する
                if (popup_window) popup_window.close();
                window.removeEventListener('message', onMessage);

                // ステータスコードと詳細メッセージを取得
                const authorization_status = event.data['KonomiTV-OAuthPopup']['status'] as number;
                const authorization_detail = event.data['KonomiTV-OAuthPopup']['detail'] as string;
                this.onOAuthCallbackReceived(authorization_status, authorization_detail);
            };

            // postMessage() を受信するリスナーを登録
            window.addEventListener('message', onMessage);
        },

        async onOAuthCallbackReceived(authorization_status: number, authorization_detail: string) {
            console.log(`NiconicoAuthCallbackAPI: Status: ${authorization_status} / Detail: ${authorization_detail}`);

            // OAuth 連携に失敗した
            if (authorization_status !== 200) {
                if (authorization_detail.startsWith('Authorization was denied (access_denied)')) {
                    Message.error('ニコニコアカウントとの連携がキャンセルされました。');
                } else if (authorization_detail.startsWith('Failed to get access token (HTTP Error ')) {
                    const error = authorization_detail.replace('Failed to get access token ', '');
                    Message.error(`アクセストークンの取得に失敗しました。${error}`);
                } else if (authorization_detail.startsWith('Failed to get access token (Connection Timeout)')) {
                    Message.error('アクセストークンの取得に失敗しました。ニコニコで障害が発生している可能性があります。');
                } else if (authorization_detail.startsWith('Failed to get user information (HTTP Error ')) {
                    const error = authorization_detail.replace('Failed to get user information ', '');
                    Message.error(`ニコニコアカウントのユーザー情報の取得に失敗しました。${error}`);
                } else if (authorization_detail.startsWith('Failed to get user information (Connection Timeout)')) {
                    Message.error('ニコニコアカウントのユーザー情報の取得に失敗しました。ニコニコで障害が発生している可能性があります。');
                } else {
                    Message.error(`ニコニコアカウントとの連携に失敗しました。(${authorization_detail})`);
                }
                return;
            }

            // アカウント情報を強制的に更新
            await this.userStore.fetchUser(true);

            Message.success('ニコニコアカウントと連携しました。');
        },

        async logoutNiconicoAccount() {

            // ニコニコアカウント連携解除 API にリクエスト
            const result = await Niconico.logoutAccount();
            if (result === false) {
                return;
            }

            // アカウント情報を強制的に更新
            await this.userStore.fetchUser(true);

            Message.success('ニコニコアカウントとの連携を解除しました。');
        },
    }
});

</script>
<style lang="scss" scoped>

.settings__content {
    opacity: 1;
    transition: opacity 0.4s;

    &--loading {
        opacity: 0;
    }
}

.niconico-account {
    display: flex;
    align-items: center;
    height: 120px;
    padding: 20px;
    border-radius: 15px;
    background: rgb(var(--v-theme-background-lighten-2));
    @include tablet-horizontal {
        align-items: normal;
        flex-direction: column;
        height: auto;
        padding: 16px;
    }
    @include tablet-vertical {
        align-items: normal;
        flex-direction: column;
        height: auto;
        padding: 16px;
        .niconico-account-wrapper {
            .niconico-account__info {
                margin-left: 16px !important;
                margin-right: 0 !important;
                &-name-text {
                    font-size: 18.5px;
                }
                &-description {
                    font-size: 13.5px;
                }
            }
        }
    }
    @include smartphone-horizontal {
        align-items: normal;
        flex-direction: column;
        height: auto;
        padding: 16px;
        border-radius: 10px;
        .niconico-account-wrapper {
            .niconico-account__info {
                margin-right: 0 !important;
            }
        }
    }
    @include smartphone-horizontal-short {
        .niconico-account-wrapper {
            .niconico-account__info {
                margin-left: 16px !important;
                &-name-text {
                    font-size: 18px;
                }
                &-description {
                    font-size: 13px;
                }
            }
        }
    }
    @include smartphone-vertical {
        align-items: normal;
        flex-direction: column;
        height: auto;
        padding: 16px 12px;
        border-radius: 10px;
        .niconico-account-wrapper {
            .niconico-account__info {
                margin-left: 12px !important;
                margin-right: 0px !important;
                &-name-text {
                    font-size: 17px;
                }
                &-description {
                    font-size: 13px;
                }
            }
        }
    }

    &--anonymous {
        @include tablet-vertical {
            .niconico-account__login {
                margin-top: 12px;
            }
        }
        @include smartphone-horizontal {
            .niconico-account__login {
                margin-top: 12px;
            }
        }
        @include smartphone-horizontal-short {
            .niconico-account-wrapper {
                svg {
                    display: none;
                }
                .niconico-account__info {
                    margin-left: 0 !important;
                }
            }
        }
        @include smartphone-vertical {
            padding-top: 20px;
            .niconico-account__login {
                margin-top: 16px;
            }
            .niconico-account-wrapper {
                svg {
                    display: none;
                }
                .niconico-account__info {
                    margin-left: 0 !important;
                    margin-right: 0 !important;
                }
            }
        }
    }

    &-wrapper {
        display: flex;
        align-items: center;
        min-width: 0;
        height: 80px;
        @include smartphone-vertical {
            height: 60px;
        }
    }

    &__icon {
        flex-shrink: 0;
        min-width: 80px;
        height: 100%;
        border-radius: 50%;
        object-fit: cover;
        // 読み込まれるまでのアイコンの背景
        background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
        // 低解像度で表示する画像がぼやけないようにする
        // ref: https://sho-log.com/chrome-image-blurred/
        image-rendering: -webkit-optimize-contrast;
        @include smartphone-vertical {
            width: 60px;
            min-width: 60px;
            height: 60px;
        }
    }

    &__info {
        display: flex;
        flex-direction: column;
        min-width: 0;
        margin-left: 20px;
        margin-right: 16px;

        &-name {
            display: inline-flex;
            align-items: center;
            height: 33px;
            @include smartphone-vertical {
                height: auto;
            }

            &-text {
                display: inline-block;
                font-size: 20px;
                color: rgb(var(--v-theme-text));
                font-weight: bold;
                overflow: hidden;
                white-space: nowrap;
                text-overflow: ellipsis;  // はみ出た部分を … で省略
            }
        }

        &-description {
            display: inline-block;
            margin-top: 4px;
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 14px;
        }
    }

    &__login {
        border-radius: 7px;
        font-size: 16px;
        letter-spacing: 0;
        @include tablet-horizontal {
            height: 50px !important;
            margin-top: 12px;
            margin-right: auto;
        }
        @include tablet-vertical {
            height: 42px !important;
            margin-top: 8px;
            margin-right: auto;
            font-size: 14.5px;
        }
        @include smartphone-horizontal {
            height: 42px !important;
            margin-top: 8px;
            margin-right: auto;
            font-size: 14.5px;
        }
        @include smartphone-vertical {
            height: 42px !important;
            margin-top: 16px;
            margin-right: auto;
            font-size: 14.5px;
        }
    }
}

</style>