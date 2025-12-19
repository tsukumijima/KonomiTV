<template>
    <v-dialog max-width="770" transition="slide-y-transition" v-model="comment_mute_settings_modal">
        <v-card class="comment-mute-settings">
            <v-card-title class="px-5 pt-6 pb-3 d-flex align-center font-weight-bold" style="height: 60px;">
                <Icon icon="heroicons-solid:filter" height="26px" />
                <span class="ml-3">コメントのミュート設定</span>
                <v-spacer></v-spacer>
                <div v-ripple class="d-flex align-center rounded-circle cursor-pointer px-2 py-2" @click="comment_mute_settings_modal = false">
                    <Icon icon="fluent:dismiss-12-filled" width="23px" height="23px" />
                </div>
            </v-card-title>
            <div class="px-5 pb-6">
                <div class="text-subtitle-1 d-flex align-center font-weight-bold mt-4">
                    <Icon icon="fa-solid:sliders-h" width="24px" height="20px" />
                    <span class="ml-2">クイック設定</span>
                </div>
                <div class="settings__item settings__item--switch">
                    <label class="settings__item-heading" for="mute_vulgar_comments">
                        露骨な表現を含むコメントをミュートする
                    </label>
                    <label class="settings__item-label" for="mute_vulgar_comments">
                        性的な単語などの露骨・下品な表現を含むコメントを、一括でミュートするかを設定します。<br>
                    </label>
                    <v-switch class="settings__item-switch" color="primary" id="mute_vulgar_comments" hide-details
                        v-model="settingsStore.settings.mute_vulgar_comments">
                    </v-switch>
                </div>
                <div class="settings__item settings__item--switch">
                    <label class="settings__item-heading" for="mute_abusive_discriminatory_prejudiced_comments">
                        ネガティブな表現、差別的な表現、政治的に偏った表現を含むコメントをミュートする
                    </label>
                    <label class="settings__item-label" for="mute_abusive_discriminatory_prejudiced_comments">
                        『死ね』『殺す』などのネガティブな表現、特定の国や人々への差別的な表現、政治的に偏った表現を含むコメントを、一括でミュートするかを設定します。<br>
                    </label>
                    <v-switch class="settings__item-switch" color="primary" id="mute_abusive_discriminatory_prejudiced_comments" hide-details
                        v-model="settingsStore.settings.mute_abusive_discriminatory_prejudiced_comments">
                    </v-switch>
                </div>
                <div class="settings__item settings__item--switch">
                    <label class="settings__item-heading" for="mute_big_size_comments">
                        文字サイズが大きいコメントをミュートする
                    </label>
                    <label class="settings__item-label" for="mute_big_size_comments">
                        通常より大きい文字サイズで表示されるコメントを、一括でミュートするかを設定します。<br>
                        文字サイズが大きいコメントには迷惑なコメントが多いです。基本的にはオンにしておくのがおすすめです。<br>
                    </label>
                    <v-switch class="settings__item-switch" color="primary" id="mute_big_size_comments" hide-details
                        v-model="settingsStore.settings.mute_big_size_comments">
                    </v-switch>
                </div>
                <div class="settings__item settings__item--switch">
                    <label class="settings__item-heading" for="mute_fixed_comments">
                        映像の上下に固定表示されるコメントをミュートする
                    </label>
                    <label class="settings__item-label" for="mute_fixed_comments">
                        映像の上下に固定された状態で表示されるコメントを、一括でミュートするかを設定します。<br>
                        固定表示されるコメントが煩わしい方におすすめです。<br>
                    </label>
                    <v-switch class="settings__item-switch" color="primary" id="mute_fixed_comments" hide-details
                        v-model="settingsStore.settings.mute_fixed_comments">
                    </v-switch>
                </div>
                <div class="settings__item settings__item--switch">
                    <label class="settings__item-heading" for="mute_colored_comments">
                       色付きのコメントをミュートする
                    </label>
                    <label class="settings__item-label" for="mute_colored_comments">
                        白以外の色で表示される色付きのコメントを、一括でミュートするかを設定します。<br>
                        オンにしておくと、目立つ色のコメントを一掃できます。<br>
                    </label>
                    <v-switch class="settings__item-switch" color="primary" id="mute_colored_comments" hide-details
                        v-model="settingsStore.settings.mute_colored_comments">
                    </v-switch>
                </div>
                <div class="settings__item settings__item--switch">
                    <label class="settings__item-heading" for="mute_consecutive_same_characters_comments">
                        8文字以上同じ文字が連続しているコメントをミュートする
                    </label>
                    <label class="settings__item-label" for="mute_consecutive_same_characters_comments">
                        『wwwwwwwwwww』『あばばばばばばばばば』など、8文字以上同じ文字が連続しているコメントを、一括でミュートするかを設定します。<br>
                        しばしばあるテンプレコメントが煩わしい方におすすめです。<br>
                    </label>
                    <v-switch class="settings__item-switch" color="primary" id="mute_consecutive_same_characters_comments" hide-details
                        v-model="settingsStore.settings.mute_consecutive_same_characters_comments">
                    </v-switch>
                </div>
                <div class="text-subtitle-1 d-flex align-center font-weight-bold mt-4">
                    <Icon icon="fluent:comment-dismiss-20-filled" width="24px" />
                    <span class="ml-2 mr-2">ミュート済みのキーワード</span>
                    <v-btn class="ml-auto" color="background-lighten-1" variant="flat"
                        @click="settingsStore.settings.muted_comment_keywords.unshift({match: 'partial', pattern: ''})">
                        <Icon icon="fluent:add-12-filled" height="17px" />
                        <span class="ml-1">追加</span>
                    </v-btn>
                </div>
                <div class="muted-comment-items">
                    <div class="muted-comment-item"
                        v-for="(muted_comment_keyword, index) in settingsStore.settings.muted_comment_keywords" :key="index">
                        <!-- 以下では Icon コンポーネントを使うと個数が多いときに高負荷になるため、意図的に SVG を直書きしている -->
                        <v-text-field type="search" class="muted-comment-item__input" color="primary"
                            density="compact" variant="outlined" hide-details
                            placeholder="ミュートするキーワードを入力"
                            v-model="settingsStore.settings.muted_comment_keywords[index].pattern">
                        </v-text-field>
                        <v-select class="muted-comment-item__match-type" color="primary"
                            density="compact" variant="outlined" hide-details
                            :items="muted_comment_keyword_match_type"
                            v-model="settingsStore.settings.muted_comment_keywords[index].match">
                        </v-select>
                        <button v-ripple class="muted-comment-item__delete-button"
                            @click="settingsStore.settings.muted_comment_keywords
                                .splice(settingsStore.settings.muted_comment_keywords.indexOf(muted_comment_keyword), 1)">
                            <svg class="iconify iconify--fluent" width="20px" height="20px" viewBox="0 0 16 16">
                                <path fill="currentColor" d="M7 3h2a1 1 0 0 0-2 0ZM6 3a2 2 0 1 1 4 0h4a.5.5 0 0 1 0 1h-.564l-1.205 8.838A2.5 2.5 0 0 1 9.754 15H6.246a2.5 2.5 0 0 1-2.477-2.162L2.564 4H2a.5.5 0 0 1 0-1h4Zm1 3.5a.5.5 0 0 0-1 0v5a.5.5 0 0 0 1 0v-5ZM9.5 6a.5.5 0 0 0-.5.5v5a.5.5 0 0 0 1 0v-5a.5.5 0 0 0-.5-.5Z"></path>
                            </svg>
                        </button>
                    </div>
                </div>
                <div class="text-subtitle-1 d-flex align-center font-weight-bold mt-4">
                    <Icon icon="fluent:person-prohibited-20-filled" width="24px" />
                    <span class="ml-2 mr-2">ミュート済みのニコニコユーザー ID</span>
                    <v-btn class="ml-auto" color="background-lighten-1" variant="flat"
                        @click="settingsStore.settings.muted_niconico_user_ids.unshift('')">
                        <Icon icon="fluent:add-12-filled" height="17px" />
                        <span class="ml-1">追加</span>
                    </v-btn>
                </div>
                <div class="muted-comment-items">
                    <div class="muted-comment-item"
                        v-for="(muted_niconico_user_id, index) in settingsStore.settings.muted_niconico_user_ids" :key="index">
                        <!-- 以下では Icon コンポーネントを使うと個数が多いときに高負荷になるため、意図的に SVG を直書きしている -->
                        <v-text-field type="search" class="muted-comment-item__input" color="primary"
                            density="compact" variant="outlined" hide-details
                            placeholder="ミュートするニコニコユーザー ID を入力" v-model="settingsStore.settings.muted_niconico_user_ids[index]">
                        </v-text-field>
                        <button v-ripple class="muted-comment-item__delete-button"
                            @click="settingsStore.settings.muted_niconico_user_ids
                                .splice(settingsStore.settings.muted_niconico_user_ids.indexOf(muted_niconico_user_id), 1)">
                            <svg class="iconify iconify--fluent" width="20px" height="20px" viewBox="0 0 16 16">
                                <path fill="currentColor" d="M7 3h2a1 1 0 0 0-2 0ZM6 3a2 2 0 1 1 4 0h4a.5.5 0 0 1 0 1h-.564l-1.205 8.838A2.5 2.5 0 0 1 9.754 15H6.246a2.5 2.5 0 0 1-2.477-2.162L2.564 4H2a.5.5 0 0 1 0-1h4Zm1 3.5a.5.5 0 0 0-1 0v5a.5.5 0 0 0 1 0v-5ZM9.5 6a.5.5 0 0 0-.5.5v5a.5.5 0 0 0 1 0v-5a.5.5 0 0 0-.5-.5Z"></path>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        </v-card>
    </v-dialog>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent, PropType } from 'vue';

import useSettingsStore from '@/stores/SettingsStore';

export default defineComponent({
    name: 'CommentMuteSettings',
    props: {
        modelValue: {
            type: Boolean as PropType<boolean>,
            required: true,
        }
    },
    emits: {
        'update:modelValue': (value: boolean) => true,
    },
    data() {
        return {

            // コメントのミュート設定のモーダルを表示するか
            comment_mute_settings_modal: false,

            // ミュート済みのキーワードのマッチタイプ
            muted_comment_keyword_match_type: [
                {title: '部分一致', value: 'partial'},
                {title: '前方一致', value: 'forward'},
                {title: '後方一致', value: 'backward'},
                {title: '完全一致', value: 'exact'},
                {title: '正規表現', value: 'regex'},
            ],
        };
    },
    computed: {
        ...mapStores(useSettingsStore),
    },
    watch: {

        // modelValue (親コンポーネント側: Props) の変更を監視し、変更されたら comment_mute_settings_modal に反映する
        modelValue() {
            this.comment_mute_settings_modal = this.modelValue;
        },

        // comment_mute_settings_modal (子コンポーネント側) の変更を監視し、変更されたら this.$emit() で親コンポーネントに伝える
        comment_mute_settings_modal() {
            this.$emit('update:modelValue', this.comment_mute_settings_modal);
        }
    }
});

</script>
<style lang="scss" scoped>

.comment-mute-settings {
    .v-card-title, & > div {
        @include smartphone-vertical {
            padding-left: 12px !important;
            padding-right: 12px !important;
        }
    }
    .v-card-title span {
        font-size: 20px;
        @include smartphone-vertical {
            font-size: 19px;
        }
    }
}

// views/Settings/Base.vue から抜粋して一部編集
.settings__item {
    display: flex;
    position: relative;
    flex-direction: column;
    margin-top: 24px;
    @include smartphone-horizontal {
        margin-top: 16px;
    }

    &--switch {
        margin-right: 62px;
    }

    &-heading {
        display: flex;
        align-items: center;
        color: rgb(var(--v-theme-text));
        font-size: 16.5px;
        @include smartphone-horizontal {
            font-size: 15px;
        }
    }
    &-label {
        margin-top: 8px;
        color: rgb(var(--v-theme-text-darken-1));
        font-size: 13.5px;
        line-height: 1.6;
        @include smartphone-horizontal {
            font-size: 11px;
            line-height: 1.7;
        }
    }
    &-form {
        margin-top: 14px;
        @include smartphone-horizontal {
            font-size: 13.5px;
        }
    }
    &-switch {
        display: flex !important;
        align-items: center;
        position: absolute;
        top: 0;
        right: -60px;
        bottom: 0px;
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
        border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
        transition: background-color 0.15s ease;

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
            @include smartphone-vertical {
                max-width: 117px;
            }
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