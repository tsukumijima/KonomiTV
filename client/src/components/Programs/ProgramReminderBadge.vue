<template>
    <v-btn variant="text" icon size="36" to="/reminders/" aria-label="見たい番組とお知らせ">
        <v-badge :model-value="reminderStore.unreadCount > 0" :content="reminderStore.unreadCount" color="secondary">
            <Icon icon="fluent:alert-20-regular" width="24px" />
        </v-badge>
    </v-btn>
</template>
<script lang="ts" setup>

import useProgramRemindersStore from '@/stores/ProgramRemindersStore';

const reminderStore = useProgramRemindersStore();

</script>
