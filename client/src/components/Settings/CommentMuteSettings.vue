<template>
    <v-dialog max-width="700" transition="slide-y-transition" v-model="comment_mute_settings_modal">
        <v-card>
            <v-card-title class="px-5 pt-5 pb-3 d-flex align-center font-weight-bold">
                <Icon icon="heroicons-solid:filter" height="26px" />
                <span class="ml-3">コメントのミュート設定</span>
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
                    <label class="settings__item-heading" for="Mute_consecutive_characters_comments">
                        8文字以上文字が連続しているコメントをミュートする
                    </label>
                    <label class="settings__item-label" for="Mute_consecutive_characters_comments">
                        『wwwwwwwwwww』など、8文字以上文字が連続しているコメントを、一括でミュートするかを設定します。<br>
                    </label>
                    <v-switch class="settings__item-switch" id="Mute_consecutive_characters_comments" inset hide-details>
                    </v-switch>
                </div> -->
                <div class="text-subtitle-1 d-flex align-center font-weight-bold mt-4">
                    <Icon icon="fluent:comment-dismiss-20-filled" width="24px" />
                    <span class="ml-2">ミュート済みのキーワード</span>
                    <v-btn class="ml-auto" depressed>
                        <Icon icon="fluent:add-12-filled" height="17px" />
                        <span class="ml-1">追加</span>
                    </v-btn>
                </div>
                <div class="text-subtitle-1 d-flex align-center font-weight-bold mt-4">
                    <Icon icon="fluent:comment-dismiss-20-filled" width="24px" />
                    <span class="ml-2">ミュート済みのコマンド（色・位置・大きさ）</span>
                    <v-btn class="ml-auto" depressed>
                        <Icon icon="fluent:add-12-filled" height="17px" />
                        <span class="ml-1">追加</span>
                    </v-btn>
                </div>
                <div class="text-subtitle-1 d-flex align-center font-weight-bold mt-4">
                    <Icon icon="fluent:person-prohibited-20-filled" width="24px" />
                    <span class="ml-2">ミュート済みのアカウント</span>
                    <v-btn class="ml-auto" depressed>
                        <Icon icon="fluent:add-12-filled" height="17px" />
                        <span class="ml-1">追加</span>
                    </v-btn>
                </div>
            </div>
            <v-divider></v-divider>
            <v-card-actions class="px-5 py-3">
                <v-spacer></v-spacer>
                <v-btn color="background lighten-2 px-3" elevation="0" @click="comment_mute_settings_modal = false">閉じる</v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>
<script lang="ts">

import Vue, { PropType } from 'vue';

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
        }
    },
    watch: {

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

</style>