<template>
    <v-dialog max-width="570" transition="slide-y-transition" v-model="account_manage_settings_modal">
        <v-card class="user-manage-settings">
            <v-card-title class="px-5 pt-6 pb-3 d-flex align-center font-weight-bold" style="height: 60px;">
                <Icon icon="fluent:person-board-20-filled" height="26px" />
                <span class="ml-3">アカウントの管理</span>
                <v-spacer></v-spacer>
                <div v-ripple class="d-flex align-center rounded-circle cursor-pointer px-2 py-2" @click="account_manage_settings_modal = false">
                    <Icon icon="fluent:dismiss-12-filled" width="23px" height="23px" />
                </div>
            </v-card-title>
            <div class="px-5 pb-6">
                <div class="user-manage-settings__label">
                    管理者ユーザーには、サーバー設定やアカウントの管理権限が与えられます。<br>
                    変更内容はすぐに反映されます。<br>
                </div>
                <div class="user-manage-settings__label text-error-lighten-1">
                    <strong>アカウントを削除すると、そのアカウントに紐づくすべてのユーザーデータが削除されます。元に戻すことはできません。</strong>
                </div>
                <div class="user-manage-settings__label"
                    v-if="user_accounts.length === 0">
                    <div><b>まだ KonomiTV アカウントが一つも作成されていません。</b></div>
                    <div class="mt-1">KonomiTV アカウントを作成すると、より便利な機能が使えます！ぜひログインしての利用をおすすめします。</div>
                </div>
                <div class="user-accounts" v-if="user_accounts.length > 0">
                    <div v-for="user_account in user_accounts" :key="user_account.id" class="user-account">
                        <img class="user-account__icon" :src="user_accounts_blob_urls[user_account.id]">
                        <div class="user-account__info">
                            <span class="user-account__name">{{user_account.name}}</span>
                            <span class="user-account__id">User ID: {{user_account.id}}</span>
                        </div>
                        <v-select class="user-account__role" color="primary"
                            density="compact" variant="outlined" hide-details
                            :items="['一般', '管理者']"
                            v-model="user_roles[user_account.id]"
                        />
                        <button v-ripple class="user-account__delete-button"
                            :disabled="user_account.name === user_store.user?.name"
                            @click="confirmDeleteUser(user_account.name)">
                            <svg class="iconify iconify--fluent" width="20px" height="20px" viewBox="0 0 16 16">
                                <path fill="currentColor" d="M7 3h2a1 1 0 0 0-2 0ZM6 3a2 2 0 1 1 4 0h4a.5.5 0 0 1 0 1h-.564l-1.205 8.838A2.5 2.5 0 0 1 9.754 15H6.246a2.5 2.5 0 0 1-2.477-2.162L2.564 4H2a.5.5 0 0 1 0-1h4Zm1 3.5a.5.5 0 0 0-1 0v5a.5.5 0 0 0 1 0v-5ZM9.5 6a.5.5 0 0 0-.5.5v5a.5.5 0 0 0 1 0v-5a.5.5 0 0 0-.5-.5Z"></path>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        </v-card>
        <v-dialog max-width="385" v-model="account_delete_confirm_dialog">
            <v-card>
                <v-card-title class="d-flex justify-center pt-6 font-weight-bold">本当にアカウントを削除しますか？</v-card-title>
                <v-card-text class="pt-2 pb-0">
                    アカウントに紐づくすべてのユーザーデータが削除されます。元に戻すことはできません。<br>
                    本当にアカウントを削除しますか？
                </v-card-text>
                <v-card-actions class="pt-4 px-6 pb-6">
                    <v-spacer></v-spacer>
                    <v-btn color="text" variant="text" @click="account_delete_confirm_dialog = false">キャンセル</v-btn>
                    <v-btn color="error" variant="flat" @click="deleteAccount()">削除</v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
    </v-dialog>
</template>
<script lang='ts' setup>

import { PropType, ref, watch } from 'vue';

import Message from '@/message';
import Users, { IUser } from '@/services/Users';
import useUserStore from '@/stores/UserStore';
import Utils from '@/utils';

// 親コンポーネントと子コンポーネントでモーダルの表示状態を同期する
const props = defineProps({
    modelValue: {
        type: Boolean as PropType<boolean>,
        required: true,
    }
});
const emit = defineEmits(['update:modelValue']);
const account_manage_settings_modal = ref(false);
watch(() => props.modelValue, (newValue) => {
    account_manage_settings_modal.value = newValue;
});
watch(account_manage_settings_modal, (newValue) => {
    emit('update:modelValue', newValue);
});

// 自分のユーザー情報を取得
const user_store = useUserStore();

// ユーザー情報リスト
const user_accounts = ref<IUser[]>([]);

// ユーザーごとのアイコンの Blob URL を ID: Blob URL の形で保持
const user_accounts_blob_urls = ref<{ [key: number]: string }>({});

// ユーザーごとのロールを ID: ロール の形で保持
// 変更されたら API に反映
const user_roles = ref<{ [key: number]: string }>({});
watch(user_roles, (new_value) => {
    for (const [id, role] of Object.entries(new_value)) {
        const user = user_accounts.value.find(user => user.id === Number(id));
        if (user) {
            const is_admin = role === '管理者';
            if (user.is_admin !== is_admin) {
                Users.updateSpecifiedUser(user.name, is_admin).then((result) => {
                    if (result) {
                        Message.success(`ユーザー ${user.name} の権限を ${role} に変更しました。`);
                        // ユーザー情報を再取得
                        fetchAllUsers();
                    } else {
                        user_roles.value[user.id] = user.is_admin ? '管理者' : '一般';
                    }
                }).catch(() => {
                    user_roles.value[user.id] = user.is_admin ? '管理者' : '一般';
                });
            }
        }
    }
}, { deep: true });

// ユーザー情報を取得 (管理者ユーザー時のみ)
function fetchAllUsers() {
    Users.fetchAllUsers().then(async (response) => {
        // ユーザー情報が取得できた場合
        if (response !== null) {
            user_accounts.value = response;
            for (const user_account of user_accounts.value) {
                // ユーザーごとのアイコンの Blob URL を取得
                Users.fetchSpecifiedUserIcon(user_account.name).then((response) => {
                    user_accounts_blob_urls.value[user_account.id] = response ?? '';
                });
                // ユーザーごとのロールを取得
                // is_admin が true なら管理者、false なら一般
                user_roles.value[user_account.id] = user_account.is_admin ? '管理者' : '一般';
            }
        // 何らかの理由でユーザー情報が取得できなかった場合
        } else {
            // 強制的に再度ユーザー情報を取得
            const user_account = await user_store.fetchUser(true);
            // ユーザー情報を取得した結果自分のユーザーが管理者権限でなくなった場合、メッセージを出して3秒後にリロード
            if (user_account !== null && user_account.name === user_store.user?.name && !user_account.is_admin) {
                Message.warning('ログイン中ユーザーの管理者権限が剥奪されました。3秒後にリロードします。');
                await Utils.sleep(3);
                location.reload();
            }
        }
    });
}
user_store.fetchUser().then((user) => {
    // 管理者ユーザーの場合のみユーザー情報を取得
    // こうしないとコンポーネントが読み込まれた時、管理者ユーザーでないのに取得しようとしてエラーが表示されてしまう
    if (user?.is_admin) {
        fetchAllUsers();
    }
});

// 指定したユーザーを削除する
const account_delete_confirm_dialog = ref(false);
const user_to_delete = ref<string | null>(null);
function confirmDeleteUser(username: string) {
    user_to_delete.value = username;
    account_delete_confirm_dialog.value = true;
}
function deleteAccount() {
    if (user_to_delete.value) {
        Users.deleteSpecifiedUser(user_to_delete.value).then((result) => {
            if (result) {
                user_accounts.value = user_accounts.value.filter(user => user.name !== user_to_delete.value);
                Message.success(`ユーザー ${user_to_delete.value} を削除しました。`);
                // ユーザー情報を再取得
                fetchAllUsers();
            }
            account_delete_confirm_dialog.value = false;
        });
    }
}

</script>
<style lang="scss" scoped>

.user-manage-settings {
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

.user-manage-settings__label {
    margin-top: 8px;
    color: rgb(var(--v-theme-text-darken-1));
    font-size: 13.5px;
    line-height: 1.6;
    @include smartphone-horizontal {
        font-size: 11px;
        line-height: 1.7;
    }
}

.user-accounts {
    display: flex;
    flex-direction: column;
    margin-top: 12px;

    .user-account {
        display: flex;
        align-items: center;
        padding: 12px 0px;
        border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
        transition: background-color 0.15s ease;

        &:last-of-type {
            border-bottom: none;
        }

        &__icon {
            display: inline-block;
            flex-shrink: 0;
            width: 64px;
            height: 64px;
            border-radius: 50%;
            // 読み込まれるまでのアイコンの背景
            background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
            object-fit: cover;
            @include smartphone-vertical {
                width: 50px;
                height: 50px;
            }
        }

        &__info {
            display: flex;
            flex-direction: column;
            margin-left: 16px;
            margin-right: 4px;
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
            @include smartphone-vertical {
                margin-left: 12px;
            }
        }

        &__name {
            font-size: 18px;
            font-weight: bold;
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
            @include smartphone-vertical {
                font-size: 16px;
            }
        }

        &__id {
            margin-top: 2px;
            font-size: 14px;
            color: rgb(var(--v-theme-text-darken-1));
            @include smartphone-vertical {
                font-size: 13px;
            }
        }

        &__role {
            width: 110px;
            max-width: 110px;
            margin-left: auto;
            flex-shrink: 0;
        }

        &__delete-button {
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            width: 40px;
            height: 40px;
            background-color: rgb(var(--v-theme-error));
            margin-left: 16px;
            border-radius: 5px;
            outline: none;
            cursor: pointer;
            @include smartphone-vertical {
                margin-left: 8px;
            }

            &:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
        }
    }
}

</style>