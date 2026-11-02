<template>
    <v-snackbar :model-value="pending !== null" :timeout="-1" location="bottom" color="background-lighten-2" multi-line>
        <div v-if="pending" class="auto-switch-notice">
            <div>{{secondsRemaining}} 秒後にチャンネルを切り替えます</div>
            <strong v-html="ProgramUtils.decorateProgramInfo(pending.program, 'title')"></strong>
            <div>{{pending.channel.name}} / {{dayjs(pending.program.start_time).format('HH:mm')}}～</div>
        </div>
        <template #actions>
            <v-btn variant="text" color="secondary" @click="pending = null">今回は切り替えない</v-btn>
        </template>
    </v-snackbar>
    <v-snackbar v-model="showConflict" :timeout="10000" location="bottom" color="background-lighten-2" multi-line>
        同時刻に見たい番組が {{conflictCount}} 件あります。見る番組を選んでください。
        <template #actions>
            <v-btn variant="text" color="secondary" to="/reminders/?view=Scheduled&notify=Scheduled" @click="showConflict = false">番組を選ぶ</v-btn>
            <v-btn variant="text" aria-label="番組選択のお知らせを閉じる" @click="showConflict = false">
                <Icon icon="fluent:dismiss-16-filled" width="18px" />
            </v-btn>
        </template>
    </v-snackbar>
</template>
<script lang="ts" setup>

import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import type { IProgramReminder } from '@/services/ProgramReminders';

import useProgramRemindersStore from '@/stores/ProgramRemindersStore';
import useSettingsStore from '@/stores/SettingsStore';
import { dayjs } from '@/utils';
import { getProgramAutoSwitchCandidates, getProgramAutoSwitchID } from '@/utils/ProgramReminderUtils';
import { ProgramUtils } from '@/utils/ProgramUtils';

const router = useRouter();
const route = useRoute();
const reminderStore = useProgramRemindersStore();
const settingsStore = useSettingsStore();
const pending = ref<IProgramReminder | null>(null);
const secondsRemaining = ref(10);
const showConflict = ref(false);
const conflictCount = ref(0);
let deadline = 0;
let lastTickAt = 0;
let isTicking = false;
let timer: ReturnType<typeof setInterval> | undefined;

/** 画面を離れた場合は、この放送の自動切り替えを取り消す。 */
function cancelWhenInactive(): void {
    if (document.visibilityState !== 'visible' || !document.hasFocus()) {
        pending.value = null;
    }
}

/** 予告を表示した画面だけで、10秒間取り消せる時間を確保して切り替える。 */
async function tick(): Promise<void> {
    const now = dayjs().valueOf();
    const tickGap = now - lastTickAt;
    lastTickAt = now;
    const canSwitch = settingsStore.settings.program_reminder_auto_switch_enabled &&
        document.visibilityState === 'visible' && document.hasFocus() && route.name !== 'Videos Watch';
    const hasFreshPrograms = reminderStore.lastCheckedAt !== null && reminderStore.error === null &&
        now - reminderStore.lastCheckedAt < 15 * 60_000;
    if (!canSwitch || !hasFreshPrograms) {
        pending.value = null;
        return;
    }

    if (pending.value !== null) {
        const target = pending.value;
        const latest = reminderStore.reminders.find(item => item.key === target.key);
        const validTarget = latest?.status === 'Scheduled' && reminderStore.verifiedKeys.includes(target.key) &&
            latest.program.start_time === target.program.start_time && dayjs(latest.program.end_time).valueOf() > now;
        // スリープ復帰や手動の通知変更は、予告を取り消す理由として扱う。
        if (!validTarget || tickGap > 2500 || tickGap < 0) {
            pending.value = null;
            return;
        }
        const overlapping = reminderStore.scheduledReminders.filter(item =>
            item.program.start_time === target.program.start_time && reminderStore.verifiedKeys.includes(item.key));
        if (overlapping.length > 1) {
            pending.value = null;
            conflictCount.value = overlapping.length;
            showConflict.value = true;
            return;
        }
        secondsRemaining.value = Math.max(0, Math.ceil((deadline - now) / 1000));
        if (now >= deadline) {
            pending.value = null;
            await router.push(`/tv/watch/${target.channel.display_channel_id}`);
        }
        return;
    }

    if (isTicking) {
        return;
    }
    isTicking = true;
    try {
        const claim = async () => {
            reminderStore.syncLocalSettings();
            if (!settingsStore.settings.program_reminder_auto_switch_enabled ||
                document.visibilityState !== 'visible' || !document.hasFocus() || route.name === 'Videos Watch') {
                return;
            }
            const settings = settingsStore.settings;
            const originalPath = route.fullPath;
            const retained = settings.program_reminder_auto_switch_handled.filter(item =>
                dayjs(item.end_time).valueOf() > now - 86400_000);
            const candidates = getProgramAutoSwitchCandidates(
                reminderStore.reminders, reminderStore.verifiedKeys, retained.map(item => item.id), now,
            );
            if (candidates.length === 0) {
                return;
            }
            // 予告した放送を保存し、取り消し・再読み込み・複数タブでも一度だけ扱う。
            settings.program_reminder_auto_switch_handled = [...retained, ...candidates.map(item => ({
                id: getProgramAutoSwitchID(item), end_time: item.program.end_time,
            }))];
            await nextTick();
            if (!settings.program_reminder_auto_switch_enabled || route.fullPath !== originalPath ||
                document.visibilityState !== 'visible' || !document.hasFocus()) {
                return;
            }
            if (candidates.length > 1) {
                conflictCount.value = candidates.length;
                showConflict.value = true;
                return;
            }
            const target = candidates[0];
            if (route.name === 'TV Watch' && route.params.display_channel_id === target.channel.display_channel_id) {
                return;
            }
            pending.value = JSON.parse(JSON.stringify(target));
            deadline = dayjs().valueOf() + 10_000;
            secondsRemaining.value = 10;
        };
        if (navigator.locks !== undefined) {
            await navigator.locks.request('KonomiTV-ProgramReminders', { ifAvailable: true }, async lock => {
                if (lock !== null) {
                    await claim();
                }
            });
        } else {
            await claim();
        }
    } finally {
        isTicking = false;
    }
}

watch(() => route.fullPath, () => { pending.value = null; });
watch(() => settingsStore.settings.program_reminder_auto_switch_enabled, enabled => {
    if (!enabled) {
        pending.value = null;
    }
});

onMounted(() => {
    void tick();
    timer = setInterval(() => void tick(), 1000);
    document.addEventListener('visibilitychange', cancelWhenInactive);
    window.addEventListener('blur', cancelWhenInactive);
});
onBeforeUnmount(() => {
    clearInterval(timer);
    document.removeEventListener('visibilitychange', cancelWhenInactive);
    window.removeEventListener('blur', cancelWhenInactive);
});

</script>
<style lang="scss" scoped>

.auto-switch-notice {
    min-width: 0; overflow-wrap: anywhere; line-height: 1.7;
    strong { display: block; }
}

</style>
