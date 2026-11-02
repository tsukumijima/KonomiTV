import { defineStore } from 'pinia';
import { computed, ref, watch } from 'vue';

import type { IChannel } from '@/services/Channels';
import type { IProgramRecommendationRule, IProgramReminder, IProgramReminderCandidate, IProgramReminderNotice } from '@/services/ProgramReminders';

import Programs, { type IProgram } from '@/services/Programs';
import useSettingsStore, { getLocalStorageSettings, getNormalizedLocalClientSettings } from '@/stores/SettingsStore';
import { dayjs } from '@/utils';
import {
    collectProgramReminderNotices, deduplicateProgramRecommendationRules, getProgramRecommendationReasons,
    getProgramReminderKey, getProgramReminderKeywords,
    isSameReminderBroadcast, reconcileProgramReminders,
} from '@/utils/ProgramReminderUtils';


/** 放送予定の自動抽出・更新と、アプリ内のお知らせを管理する。永続化は SettingsStore が担当する。 */
const useProgramRemindersStore = defineStore('program-reminders', () => {
    const settingsStore = useSettingsStore();
    const isLoading = ref(false);
    const hasLoaded = ref(false);
    const error = ref<string | null>(null);
    const lastCheckedAt = ref<number | null>(null);
    const matchingCount = ref(0);
    const verifiedKeys = ref<string[]>([]);
    const now = ref(dayjs().valueOf());
    const latestNotices = ref<IProgramReminderNotice[]>([]);
    let lastAttemptAt = 0;
    let changedKeys: string[] = [];

    const reminders = computed(() => settingsStore.settings.program_reminders);
    // 通知の状態にかかわらず、保存済みの番組から未終了の放送を取り出す。
    const upcomingReminders = computed(() => reminders.value.filter(reminder =>
        dayjs(reminder.program.end_time).valueOf() > now.value));
    const scheduledReminders = computed(() => reminders.value.filter(reminder =>
        reminder.status === 'Scheduled' && dayjs(reminder.program.end_time).valueOf() > now.value));
    const dismissedReminders = computed(() => reminders.value.filter(reminder =>
        reminder.status === 'Dismissed' && dayjs(reminder.program.end_time).valueOf() > now.value));
    // 候補は現在有効なキーワードで毎回絞り込む。通知予定・過去の候補の保存状態とは独立している。
    const candidateReminders = computed(() => upcomingReminders.value.filter(reminder =>
        getProgramRecommendationReasons(reminder.program, settingsStore.settings.program_recommendation_rules).length > 0));
    const unreadCount = computed(() => settingsStore.settings.program_reminder_notices.filter(notice => !notice.is_read).length);

    // 保存済み・同期で受け取った重複条件を整理し、削除前の条件も通知予定へ保存する。
    watch(() => settingsStore.settings.program_recommendation_rules, rules => {
        const uniqueRules = deduplicateProgramRecommendationRules(rules);
        const updated = reminders.value.map(reminder => ({
            ...reminder, keyword_matches: getProgramReminderKeywords(reminder, rules),
        }));
        const rulesChanged = JSON.stringify(rules) !== JSON.stringify(uniqueRules);
        const remindersChanged = JSON.stringify(reminders.value) !== JSON.stringify(updated);
        if (rulesChanged || remindersChanged) {
            settingsStore.$patch({ settings: { program_recommendation_rules: uniqueRules, program_reminders: updated } });
        }
    }, { deep: true, immediate: true });

    /** 同じブラウザのほかのタブで変更した、通知と視聴の状態を読み取る。 */
    function syncLocalSettings(): void {
        const saved = getNormalizedLocalClientSettings(getLocalStorageSettings());
        const reminderSettings = {
            program_reminders: saved.program_reminders,
            program_recommendation_rules: saved.program_recommendation_rules,
            program_recommendation_enabled: saved.program_recommendation_enabled,
            program_recommendation_notify_by_default: saved.program_recommendation_notify_by_default,
            program_reminder_notifications_enabled: saved.program_reminder_notifications_enabled,
            program_reminder_notify_on_discovery: saved.program_reminder_notify_on_discovery,
            program_reminder_lead_times: saved.program_reminder_lead_times,
            program_reminder_notices: saved.program_reminder_notices,
            program_reminder_auto_switch_enabled: saved.program_reminder_auto_switch_enabled,
            program_reminder_auto_switch_handled: saved.program_reminder_auto_switch_handled,
        };
        const hasChanges = Object.entries(reminderSettings).some(([key, value]) =>
            JSON.stringify(settingsStore.settings[key]) !== JSON.stringify(value));
        if (hasChanges) {
            settingsStore.$patch({ settings: reminderSettings });
        }
    }

    /** アプリを開いている間に、最大10分間隔で番組表を更新する。 */
    async function refresh(force = false): Promise<void> {
        now.value = dayjs().valueOf();
        const settings = settingsStore.settings;
        const hasActiveRules = settings.program_recommendation_enabled && settings.program_recommendation_rules.some(rule => rule.is_enabled);
        if (isLoading.value || (!force && !hasActiveRules && scheduledReminders.value.length === 0)) {
            return;
        }
        if (!force && now.value - lastAttemptAt < 10 * 60_000) {
            return;
        }
        lastAttemptAt = now.value;
        isLoading.value = true;
        try {
            // 番組表 API は EDCB / Mirakurun 共通。配信対象局と番組を同時に取得する。
            const result = await Programs.fetchTimeTable(dayjs().startOf('day'), dayjs().add(8, 'day'));
            if (result === null) {
                error.value = '番組表を更新できませんでした。保存済みの予定を表示しています。「更新」から再試行できます。';
                verifiedKeys.value = [];
                return;
            }
            const candidates: IProgramReminderCandidate[] = [];
            for (const group of result.channels) {
                const groups = [group, ...(group.subchannels ?? [])];
                for (const channelGroup of groups) {
                    const channel = channelGroup.channel;
                    for (const timetableProgram of channelGroup.programs) {
                        const { reservation: _reservation, ...program } = timetableProgram;
                        candidates.push({
                            program,
                            channel: { id: channel.id, name: channel.name, display_channel_id: channel.display_channel_id },
                        });
                    }
                }
            }

            // 取得中に本人が変更した条件・除外状態を、応答時点の最新設定から読み取る。
            const currentSettings = settingsStore.settings;
            const reconciled = reconcileProgramReminders(
                currentSettings.program_reminders, candidates, currentSettings.program_recommendation_rules,
                currentSettings.program_recommendation_enabled, dayjs().valueOf(),
                currentSettings.program_recommendation_notify_by_default,
            );
            if (JSON.stringify(currentSettings.program_reminders) !== JSON.stringify(reconciled.reminders)) {
                currentSettings.program_reminders = reconciled.reminders;
            }
            verifiedKeys.value = reconciled.verifiedKeys;
            changedKeys = reconciled.changedKeys;
            matchingCount.value = reconciled.matchingCount;
            lastCheckedAt.value = dayjs().valueOf();
            hasLoaded.value = true;
            error.value = null;
        } finally {
            isLoading.value = false;
        }
    }

    /** 番組表・検索結果で選んだ放送を、録画予約とは独立して保存する。 */
    function addManual(program: IProgram, channel: Pick<IChannel, 'id' | 'name' | 'display_channel_id'>): void {
        const currentTime = dayjs().valueOf();
        if (dayjs(program.end_time).valueOf() <= currentTime) {
            return;
        }
        const existing = reminders.value.find(reminder => isSameReminderBroadcast(reminder.program, program));
        const reminder: IProgramReminder = {
            key: existing?.key ?? getProgramReminderKey(program),
            program: JSON.parse(JSON.stringify(program)),
            channel: { id: channel.id, name: channel.name, display_channel_id: channel.display_channel_id },
            source: 'Manual', status: 'Scheduled', reasons: ['自分で選んだ番組'],
            created_at: existing?.created_at ?? currentTime,
        };
        reminder.keyword_matches = getProgramReminderKeywords(existing ?? reminder, settingsStore.settings.program_recommendation_rules);
        settingsStore.settings.program_reminders = [
            ...reminders.value.filter(item => item.key !== reminder.key), reminder,
        ].sort((a, b) => dayjs(a.program.start_time).valueOf() - dayjs(b.program.start_time).valueOf());
        void refresh(true);
    }

    /** 放送回の通知を停止する。保存済みの Dismissed 状態も通知停止として扱う。 */
    function dismiss(key: string): void {
        settingsStore.settings.program_reminders = reminders.value.map(reminder =>
            reminder.key === key ? { ...reminder, status: 'Dismissed' } : reminder);
    }

    /** 保存済みの番組を保持し、登録済みの未終了番組の通知をまとめて停止する。 */
    function dismissAll(): number {
        now.value = dayjs().valueOf();
        const keys = new Set(scheduledReminders.value.map(reminder => reminder.key));
        if (keys.size === 0) {
            return 0;
        }
        settingsStore.settings.program_reminders = reminders.value.map(reminder =>
            keys.has(reminder.key) ? { ...reminder, status: 'Dismissed' } : reminder);
        return keys.size;
    }

    /** 通知を停止した放送回を、再びお知らせの対象にする。 */
    function restore(key: string): void {
        settingsStore.settings.program_reminders = reminders.value.map(reminder =>
            reminder.key === key ? {
                ...reminder, status: 'Scheduled',
                keyword_matches: getProgramReminderKeywords(reminder, settingsStore.settings.program_recommendation_rules),
            } : reminder);
    }

    /** 編集・削除の前に登録時のキーワードを保存し、通知予定と履歴を維持する。 */
    function updateRecommendationRules(rules: IProgramRecommendationRule[]): void {
        const previousRules = settingsStore.settings.program_recommendation_rules;
        const uniqueRules = deduplicateProgramRecommendationRules(rules);
        settingsStore.$patch(state => {
            state.settings.program_reminders = state.settings.program_reminders.map(reminder => {
                const remembered = { ...reminder, keyword_matches: getProgramReminderKeywords(reminder, previousRules) };
                return { ...remembered, keyword_matches: getProgramReminderKeywords(remembered, uniqueRules) };
            });
            state.settings.program_recommendation_rules = uniqueRules;
        });
    }

    /** 確認できた最新の放送予定に基づいて、この端末のお知らせを追加する。 */
    function checkNotices(): void {
        now.value = dayjs().valueOf();
        const settings = settingsStore.settings;
        if (!settings.program_reminder_notifications_enabled || lastCheckedAt.value === null ||
            error.value !== null || now.value - lastCheckedAt.value > 15 * 60_000) {
            return;
        }
        const retainedNotices = settings.program_reminder_notices.filter(notice =>
            dayjs(notice.end_time).valueOf() > now.value - 7 * 86400_000);
        const newNotices = collectProgramReminderNotices(
            reminders.value, retainedNotices, verifiedKeys.value, changedKeys,
            settings.program_reminder_lead_times, settings.program_reminder_notify_on_discovery, now.value,
        );
        changedKeys = [];
        if (newNotices.length > 0 || retainedNotices.length !== settings.program_reminder_notices.length) {
            settings.program_reminder_notices = [...retainedNotices, ...newNotices];
        }
        latestNotices.value = newNotices;
    }

    function markAllRead(): void {
        settingsStore.settings.program_reminder_notices = settingsStore.settings.program_reminder_notices.map(notice =>
            ({ ...notice, is_read: true }));
    }

    return {
        isLoading, hasLoaded, error, lastCheckedAt, matchingCount, verifiedKeys, now, latestNotices,
        reminders, upcomingReminders, candidateReminders, scheduledReminders, dismissedReminders, unreadCount,
        syncLocalSettings, refresh, addManual, dismiss, dismissAll, restore, updateRecommendationRules, checkNotices, markAllRead,
    };
});

export default useProgramRemindersStore;
