<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <SettingsBase>
        <h2 class="settings__heading">
            <router-link v-ripple class="settings__back-button" to="/settings/">
                <Icon icon="fluent:arrow-left-12-filled" width="25px" />
            </router-link>
            <Icon icon="fluent:server-surface-16-filled" width="22px" />
            <span class="ml-2">サーバー設定</span>
        </h2>
        <div class="settings__content">
            <div class="settings__item">
                <div class="settings__item-heading">鋭意開発中…</div>
            </div>
        </div>
    </SettingsBase>
</template>
<script lang="ts">

import { defineComponent } from 'vue';

import SettingsBase from '@/views/Settings/Base.vue';

export default defineComponent({
    name: 'Settings-Server',
    components: {
        SettingsBase,
    }
});

</script>