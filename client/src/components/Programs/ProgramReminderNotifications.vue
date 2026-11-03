<template>
    <v-snackbar v-model="isVisible" :timeout="10000" location="top" color="background-lighten-2" multi-line>
        <div class="d-flex align-center">
            <Icon icon="fluent:alert-20-regular" width="24px" class="mr-3" />
            <div v-if="singleNotice" class="reminder-notification__body">
                <div>{{singleNotice.message}}</div>
                <strong v-html="ProgramUtils.decorateProgramInfo({...IProgramDefault, title: singleNotice.title}, 'title')"></strong>
                <div>{{singleNotice.channel_name}} / {{dayjs(singleNotice.start_time).format('M/D HH:mm')}}～</div>
            </div>
            <span v-else>見たい番組のお知らせが {{displayedNotices.length}} 件あります。</span>
        </div>
        <template #actions>
            <v-btn v-if="singleNotice && singleNotice.display_channel_id && dayjs(singleNotice.end_time).valueOf() > reminderStore.now"
                variant="text" color="secondary" :to="`/tv/watch/${singleNotice.display_channel_id}`" @click="isVisible = false">
                {{dayjs(singleNotice.start_time).valueOf() <= reminderStore.now ? '今すぐ見る' : 'チャンネルを開く'}}
            </v-btn>
            <v-btn v-else variant="text" color="secondary" to="/reminders/?view=Notices" @click="isVisible = false">お知らせを見る</v-btn>
            <v-btn variant="text" aria-label="お知らせを閉じる" @click="isVisible = false">
                <Icon icon="fluent:dismiss-16-filled" width="18px" />
            </v-btn>
        </template>
    </v-snackbar>
</template>
<script lang="ts" setup>

import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import type { IProgramReminderNotice } from '@/services/ProgramReminders';

import { IProgramDefault } from '@/services/Programs';
import useProgramRemindersStore from '@/stores/ProgramRemindersStore';
import { dayjs } from '@/utils';
import { ProgramUtils } from '@/utils/ProgramUtils';

const reminderStore = useProgramRemindersStore();
const isVisible = ref(false);
const displayedNotices = ref<IProgramReminderNotice[]>([]);
const singleNotice = computed(() => displayedNotices.value.length === 1 ? displayedNotices.value[0] : null);
let timer: ReturnType<typeof setInterval> | undefined;
let isTicking = false;

/** 同一オリジンのタブ間で処理を直列化し、お知らせの記録後にロックを解放する。 */
async function tick(): Promise<void> {
    if (isTicking || document.visibilityState !== 'visible') {
        return;
    }
    isTicking = true;
    try {
        const update = async () => {
            reminderStore.syncLocalSettings();
            await reminderStore.refresh();
            reminderStore.checkNotices();
            // SettingsStore の保存が完了してから、ほかのタブが次の処理へ進めるようにする。
            await nextTick();
        };
        if (navigator.locks !== undefined) {
            await navigator.locks.request('KonomiTV-ProgramReminders', { ifAvailable: true }, async lock => {
                if (lock !== null) {
                    await update();
                }
            });
        } else if (document.hasFocus()) {
            await update();
        }
    } finally {
        isTicking = false;
    }
}

function onStorage(event: StorageEvent): void {
    if (event.key === 'KonomiTV-Settings') {
        reminderStore.syncLocalSettings();
    }
}

watch(() => reminderStore.latestNotices, notices => {
    if (notices.length > 0) {
        displayedNotices.value = notices;
        isVisible.value = true;
    }
});

onMounted(() => {
    void tick();
    // 秒単位の通知時刻を扱う。ブラウザ休止時の遅延は、時刻判定側の期限で調整する。
    timer = setInterval(() => void tick(), 1000);
    document.addEventListener('visibilitychange', tick);
    window.addEventListener('focus', tick);
    window.addEventListener('storage', onStorage);
});
onBeforeUnmount(() => {
    clearInterval(timer);
    document.removeEventListener('visibilitychange', tick);
    window.removeEventListener('focus', tick);
    window.removeEventListener('storage', onStorage);
});

</script>
<style lang="scss" scoped>

.reminder-notification__body {
    min-width: 0; overflow-wrap: anywhere; line-height: 1.7;
    strong { display: block; }
}

</style>
