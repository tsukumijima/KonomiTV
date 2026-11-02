<template>
    <v-btn v-if="program && channel && isUpcoming" class="px-3" variant="tonal" color="secondary"
        :aria-pressed="isAdded" @click.stop="toggle">
        <Icon :icon="isAdded ? 'fluent:alert-on-20-filled' : 'fluent:alert-20-regular'" width="20px" />
        <span class="ml-1">{{buttonLabel}}</span>
    </v-btn>
</template>
<script lang="ts" setup>

import { computed } from 'vue';

import type { IChannel } from '@/services/Channels';
import type { IProgram } from '@/services/Programs';

import Message from '@/message';
import useProgramRemindersStore from '@/stores/ProgramRemindersStore';
import { dayjs } from '@/utils';
import { isSameReminderBroadcast } from '@/utils/ProgramReminderUtils';

const props = defineProps<{ program: IProgram | null | undefined; channel: IChannel | null | undefined }>();
const reminderStore = useProgramRemindersStore();
const reminder = computed(() => reminderStore.reminders.find(item =>
    props.program && isSameReminderBroadcast(item.program, props.program)));
const isAdded = computed(() => reminder.value?.status === 'Scheduled');
const buttonLabel = computed(() => {
    if (isAdded.value) return '通知しない';
    if (reminder.value) return '通知する';
    return 'リマインドに追加';
});
const isUpcoming = computed(() => props.program && dayjs(props.program.end_time).valueOf() > reminderStore.now);

function toggle(): void {
    if (!props.program || !props.channel) {
        return;
    }
    if (isAdded.value && reminder.value) {
        reminderStore.dismiss(reminder.value.key);
        Message.show('この放送の通知を停止しました。');
    } else if (reminder.value) {
        reminderStore.restore(reminder.value.key);
        Message.show('この放送の通知を再開しました。');
    } else {
        reminderStore.addManual(props.program, props.channel);
        Message.show('リマインドに追加しました。お知らせ時刻は「見たい番組」で変更できます。');
    }
}

</script>
