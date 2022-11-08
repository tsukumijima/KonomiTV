<template>
    <v-dialog max-width="700" transition="slide-y-transition" v-model="comment_mute_settings_modal">
        <v-card>
            <v-card-title class="px-5 pt-5 pb-3 d-flex align-center font-weight-bold" style="height: 60px;">
                <Icon icon="heroicons-solid:filter" height="26px" />
                <span class="ml-3">コメントのミュート設定</span>
                <v-spacer></v-spacer>
                <div v-ripple class="d-flex align-center rounded-circle cursor-pointer px-2 py-2" @click="comment_mute_settings_modal = false">
                    <Icon icon="fluent:dismiss-12-filled" width="23px" height="23px" />
                </div>
            </v-card-title>
            <div class="px-5 pb-5">
                <!-- <div class="text-subtitle-1 d-flex align-center font-weight-bold mt-1">
                    <Icon icon="fa-solid:sliders-h" width="24px" height="20px" />
                    <span class="ml-2">クイック設定</span>
                </div>
                <div class="settings__item settings__item--switch">
                    <label class="settings__item-heading" for="mute_abusive_discriminatory_comments">
                        罵倒や差別的な表現を含むコメントをミュートする
                    </label>
                    <label class="settings__item-label" for="mute_abusive_discriminatory_comments">
                        『死ね』『殺す』などの罵倒や、特定の人々への差別的な表現を含むコメントを、一括でミュートするかを設定します。<br>
                    </label>
                    <v-switch class="settings__item-switch" id="mute_abusive_discriminatory_comments" inset hide-details>
                    </v-switch>
                </div>
                <div class="settings__item settings__item--switch">
                    <label class="settings__item-heading" for="mute_politically_biased_comments">
                        政治的に偏った表現を含むコメントをミュートする
                    </label>
                    <label class="settings__item-label" for="mute_politically_biased_comments">
                        『ネトウヨ』『パヨク』などの政治的に偏った表現を含むコメントを、一括でミュートするかを設定します。<br>
                    </label>
                    <v-switch class="settings__item-switch" id="mute_politically_biased_comments" inset hide-details>
                    </v-switch>
                </div>
                <div class="settings__item settings__item--switch">
                    <label class="settings__item-heading" for="mute_vulgar_comments">
                        露骨な表現を含むコメントをミュートする
                    </label>
                    <label class="settings__item-label" for="mute_vulgar_comments">
                        性的な単語などの露骨・下品な表現を含むコメントを、一括でミュートするかを設定します。<br>
                    </label>
                    <v-switch class="settings__item-switch" id="mute_vulgar_comments" inset hide-details>
                    </v-switch>
                </div>
                <div class="settings__item settings__item--switch">
                    <label class="settings__item-heading" for="mute_consecutive_characters_comments">
                        8文字以上文字が連続しているコメントをミュートする
                    </label>
                    <label class="settings__item-label" for="mute_consecutive_characters_comments">
                        『wwwwwwwwwww』など、8文字以上文字が連続しているコメントを、一括でミュートするかを設定します。<br>
                    </label>
                    <v-switch class="settings__item-switch" id="mute_consecutive_characters_comments" inset hide-details>
                    </v-switch>
                </div> -->
                <div class="text-subtitle-1 d-flex align-center font-weight-bold mt-4">
                    <Icon icon="fluent:comment-dismiss-20-filled" width="24px" />
                    <span class="ml-2">ミュート済みのキーワード</span>
                    <v-btn class="ml-auto" depressed
                        @click="muted_comment_keywords.push({id: Date.now(), match: 'partial', pattern: ''})">
                        <Icon icon="fluent:add-12-filled" height="17px" />
                        <span class="ml-1">追加</span>
                    </v-btn>
                </div>
                <div class="muted-comment-items">
                    <div class="muted-comment-item" v-for="muted_comment_keyword in muted_comment_keywords" :key="muted_comment_keyword.id">
                        <v-text-field type="search" class="muted-comment-item__input" dense outlined hide-details
                            placeholder="ミュートするキーワードを入力" v-model="muted_comment_keyword.pattern">
                        </v-text-field>
                        <v-select class="muted-comment-item__match-type" dense outlined hide-details
                            :items="muted_comment_keyword_match_type" v-model="muted_comment_keyword.match">
                        </v-select>
                        <button v-ripple class="muted-comment-item__delete-button"
                            @click="muted_comment_keywords.splice(muted_comment_keywords.indexOf(muted_comment_keyword), 1)">
                            <Icon icon="fluent:delete-16-filled" width="20px" />
                        </button>
                    </div>
                </div>
                <div class="text-subtitle-1 d-flex align-center font-weight-bold mt-4">
                    <Icon icon="fluent:person-prohibited-20-filled" width="24px" />
                    <span class="ml-2">ミュート済みのニコニコユーザー ID</span>
                    <v-btn class="ml-auto" depressed
                        @click="muted_niconico_user_ids.push({id: Date.now(), user_id: ''})">
                        <Icon icon="fluent:add-12-filled" height="17px" />
                        <span class="ml-1">追加</span>
                    </v-btn>
                </div>
                <div class="muted-comment-items">
                    <div class="muted-comment-item" v-for="muted_niconico_user_id in muted_niconico_user_ids" :key="muted_niconico_user_id.id">
                        <v-text-field type="search" class="muted-comment-item__input" dense outlined hide-details
                            placeholder="ミュートするニコニコユーザー ID を入力" v-model="muted_niconico_user_id.user_id">
                        </v-text-field>
                        <button v-ripple class="muted-comment-item__delete-button"
                            @click="muted_niconico_user_ids.splice(muted_niconico_user_ids.indexOf(muted_niconico_user_id), 1)">
                            <Icon icon="fluent:delete-16-filled" width="20px" />
                        </button>
                    </div>
                </div>
            </div>
        </v-card>
    </v-dialog>
</template>
<script lang="ts">

import Vue, { PropType } from 'vue';

import { IMutedCommentKeywords } from '@/interface';
import Utils from '@/utils';

export default Vue.extend({
    name: 'CommentMuteSettings',
    // カスタム v-model を実装する
    // ref: https://jp.vuejs.org/v2/guide/components-custom-events.html
    model: {
        prop: 'showing',  // v-model で渡された値が "showing" props に入る
        event: 'change'  // "change" イベントで親コンポーネントに反映
    },
    props: {
        // コメントのミュート設定のモーダルを表示するか
        showing: {
            type: Boolean as PropType<Boolean>,
            required: true,
        }
    },
    data() {
        return {

            // コメントのミュート設定のモーダルを表示するか
            comment_mute_settings_modal: false,

            // ミュート済みのキーワードが入るリスト
            muted_comment_keywords: (Utils.getSettingsItem('muted_comment_keywords') as IMutedCommentKeywords[]).map((keyword, index) => {
                // id プロパティは :key="" に指定するためにつける ID (ミリ秒単位のタイムスタンプ + index で適当に一意になるように)
                return {
                    id: Date.now() + index,
                    match: keyword.match as ('partial' | 'forward' | 'backward' | 'exact' | 'regex'),
                    pattern: keyword.pattern as string,
                };
            }),

            // ミュート済みのキーワードのマッチタイプ
            muted_comment_keyword_match_type: [
                {text: '部分一致', value: 'partial'},
                {text: '前方一致', value: 'forward'},
                {text: '後方一致', value: 'backward'},
                {text: '完全一致', value: 'exact'},
                {text: '正規表現', value: 'regex'},
            ],

            // ミュート済みのニコニコユーザー ID が入るリスト
            muted_niconico_user_ids: (Utils.getSettingsItem('muted_niconico_user_ids') as string[]).map((user_id, index) => {
                // id プロパティは :key="" に指定するためにつける ID (ミリ秒単位のタイムスタンプ + index で適当に一意になるように)
                return {
                    id: Date.now() + index,
                    user_id: user_id,
                };
            }),

            // 設定値が保存されるオブジェクト
            // ここの値とフォームを v-model で binding する
            settings: (() => {
                // 現在の設定値を取得する
                const settings = {}
                const setting_keys = [
                ];
                for (const setting_key of setting_keys) {
                    settings[setting_key] = Utils.getSettingsItem(setting_key);
                }
                return settings;
            })(),
        }
    },
    watch: {

        // settings 内の値の変更を監視する
        settings: {
            deep: true,
            handler() {
                // settings 内の値を順に LocalStorage に保存する
                for (const [setting_key, setting_value] of Object.entries(this.settings)) {
                    Utils.setSettingsItem(setting_key, setting_value);
                }
            }
        },

        // ミュート済みのキーワードが変更されたら随時 LocalStorage に保存する
        muted_comment_keywords: {
            deep: true,
            handler() {
                Utils.setSettingsItem('muted_comment_keywords', this.muted_comment_keywords.map((muted_comment_keyword) => {
                    delete muted_comment_keyword.id;
                    return muted_comment_keyword;
                }));
            }
        },

        // ミュート済みのニコニコユーザー ID が変更されたら随時 LocalStorage に保存する
        muted_niconico_user_ids: {
            deep: true,
            handler() {
                Utils.setSettingsItem('muted_niconico_user_ids', this.muted_niconico_user_ids.map((muted_niconico_user_id) => {
                    return muted_niconico_user_id.user_id;
                }));
            }
        },

        // showing (親コンポーネント側) の変更を監視し、変更されたら comment_mute_settings_modal に反映する
        showing() {
            this.comment_mute_settings_modal = this.showing as boolean;
        },

        // comment_mute_settings_modal (子コンポーネント側) の変更を監視し、変更されたら this.$emit() で親コンポーネントに伝える
        comment_mute_settings_modal() {
            this.$emit('change', this.comment_mute_settings_modal);
        }
    }
});

</script>
<style lang="scss" scoped>

// views/Settings/Base.vue から抜粋して一部編集
.settings__item {
    display: flex;
    position: relative;
    flex-direction: column;
    margin-top: 16px;

    &--switch {
        margin-right: 62px;
    }

    &-heading {
        color: var(--v-text-base);
        font-size: 16.5px;
    }
    &-label {
        margin-top: 8px;
        color: var(--v-text-darken1);
        font-size: 13.5px;
        line-height: 1.6;
    }
    &-switch {
        align-items: center;
        position: absolute;
        top: 0;
        right: -74px;
        bottom: 0;
        margin-top: 0;
    }

    p {
        margin-bottom: 8px;
        &:last-of-type {
            margin-bottom: 0px;
        }
    }
}
.muted-comment-items {
    display: flex;
    flex-direction: column;
    margin-top: 8px;

    .muted-comment-item {
        display: flex;
        align-items: center;
        padding: 6px 0px;
        border-bottom: 1px solid var(--v-background-lighten2);
        transition: background-color 0.15s ease;
        @include smartphone-horizontal {
            padding-top: 0px;
            padding-bottom: 0px;
        }
        // タッチデバイスで hover を無効にする
        @media (hover: none) {
            &:hover {
                background: transparent;
            }
        }

        &:last-of-type {
            border-bottom: none;
        }

        &__input {
            font-size: 14px;
        }

        &__match-type {
            max-width: 150px;
            margin-left: 12px;
            font-size: 14px;
        }

        &__delete-button {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 40px;
            height: 40px;
            margin-left: 6px;
            border-radius: 5px;
            outline: none;
            cursor: pointer;
        }
    }
}

</style>