import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createApp, defineComponent, h, nextTick, type App, type Component } from 'vue';
import { createMemoryHistory, createRouter } from 'vue-router';

import type { IProgramReminder } from '@/services/ProgramReminders';

import ProgramReminderAutoSwitch from '@/components/Programs/ProgramReminderAutoSwitch.vue';
import ProgramReminderNotifications from '@/components/Programs/ProgramReminderNotifications.vue';
import { IProgramDefault } from '@/services/Programs';
import useProgramRemindersStore from '@/stores/ProgramRemindersStore';
import useSettingsStore, { getSyncableClientSettings, setLocalStorageSettings } from '@/stores/SettingsStore';
import { dayjs } from '@/utils';
import { getProgramAutoSwitchCandidates, getProgramAutoSwitchID } from '@/utils/ProgramReminderUtils';

const start = dayjs('2026-11-10T20:00:00+09:00').valueOf();
const reminder: IProgramReminder = {
    key: 'test-program', source: 'Manual', status: 'Scheduled', reasons: ['自分で選んだ番組'], created_at: start - 86400_000,
    channel: { id: 'NID4-SID101', display_channel_id: 'bs101', name: 'テスト放送' },
    program: { ...IProgramDefault, id: 'NID4-SID101-EID100', title: '視聴テスト番組',
        start_time: dayjs(start).format(), end_time: dayjs(start).add(1, 'hour').format() },
};
const second: IProgramReminder = { ...reminder, key: 'second-program',
    channel: { id: 'NID4-SID102', display_channel_id: 'bs102', name: '別の放送局' } };

describe('自動切り替えの候補', () => {
    it('直前の通知オン・確認済みの放送だけを対象にし、開始後は追いかけない', () => {
        expect(getProgramAutoSwitchCandidates([reminder], [reminder.key], [], start - 10001)).toEqual([]);
        expect(getProgramAutoSwitchCandidates([reminder], [reminder.key], [], start - 10000)).toEqual([reminder]);
        expect(getProgramAutoSwitchCandidates([reminder], [reminder.key], [], start + 1)).toEqual([]);
        expect(getProgramAutoSwitchCandidates([{ ...reminder, status: 'Dismissed' }], [reminder.key], [], start - 1000)).toEqual([]);
        expect(getProgramAutoSwitchCandidates([reminder], [], [], start - 1000)).toEqual([]);
    });
    it('同時刻の候補をまとめ、一度扱った放送は再予告せず、時刻変更は別に判定する', () => {
        expect(getProgramAutoSwitchCandidates([reminder, second], [reminder.key, second.key], [], start - 10000)).toHaveLength(2);
        expect(getProgramAutoSwitchCandidates([reminder], [reminder.key], [getProgramAutoSwitchID(reminder)], start - 1000)).toEqual([]);
        const changed = { ...reminder, program: { ...reminder.program, start_time: dayjs(start).add(5, 'second').format() } };
        expect(getProgramAutoSwitchCandidates([changed], [reminder.key], [getProgramAutoSwitchID(reminder)], start - 1000)).toEqual([changed]);
    });
});

describe('自動切り替えの画面と操作', () => {
    let apps: App[];
    let containers: HTMLElement[];
    let settings: ReturnType<typeof useSettingsStore>;
    let store: ReturnType<typeof useProgramRemindersStore>;
    let router: ReturnType<typeof createRouter>;
    let stopSaving: () => void;

    async function mount(component: Component = ProgramReminderAutoSwitch): Promise<HTMLElement> {
        const container = document.createElement('div');
        document.body.append(container);
        containers.push(container);
        const app = createApp(component);
        app.use(router);
        app.component('Icon', defineComponent({ render: () => h('span') }));
        app.component('VSnackbar', defineComponent({
            props: ['modelValue'],
            setup(props, { slots }) {
                return () => props.modelValue ? h('section', [slots.default?.(), slots.actions?.()]) : null;
            },
        }));
        app.component('VBtn', defineComponent({
            props: ['to'],
            setup(props, { slots, attrs }) {
                return () => h(props.to ? 'a' : 'button', { ...attrs, href: props.to }, slots.default?.());
            },
        }));
        app.mount(container);
        apps.push(app);
        await nextTick();
        await nextTick();
        return container;
    }

    beforeEach(async () => {
        apps = [];
        containers = [];
        localStorage.clear();
        vi.useFakeTimers({ now: start - 10000 });
        vi.spyOn(document, 'hasFocus').mockReturnValue(true);
        vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible');
        setActivePinia(createPinia());
        settings = useSettingsStore();
        settings.settings.program_reminders = [structuredClone(reminder)];
        setLocalStorageSettings(settings.settings);
        stopSaving = settings.$subscribe((_mutation, state) => setLocalStorageSettings(state.settings));
        store = useProgramRemindersStore();
        store.lastCheckedAt = start - 10000;
        store.verifiedKeys = [reminder.key];
        router = createRouter({ history: createMemoryHistory(), routes: [
            { path: '/reminders/', name: 'Program Reminders', component: {} },
            { path: '/tv/watch/:display_channel_id', name: 'TV Watch', component: {} },
            { path: '/videos/watch/:video_id', name: 'Videos Watch', component: {} },
        ] });
        await router.push('/reminders/');
        await router.isReady();
    });
    afterEach(() => {
        for (const app of apps) app.unmount();
        for (const container of containers) container.remove();
        stopSaving();
        vi.restoreAllMocks();
        vi.useRealTimers();
        localStorage.clear();
    });

    it('初期値はオフで、端末の有効設定や処理済み状態をサーバー同期に含めない', async () => {
        expect(settings.settings.program_reminder_auto_switch_enabled).toBe(false);
        await mount();
        await vi.advanceTimersByTimeAsync(12000);
        expect(router.currentRoute.value.path).toBe('/reminders/');
        const syncable = getSyncableClientSettings(settings.settings);
        expect(syncable).not.toHaveProperty('program_reminder_auto_switch_enabled');
        expect(syncable).not.toHaveProperty('program_reminder_auto_switch_handled');
    });
    it('10秒の予告を表示してから、対象チャンネルへ1回だけ遷移する', async () => {
        settings.settings.program_reminder_auto_switch_enabled = true;
        await nextTick();
        const container = await mount();
        expect(container.textContent).toContain('10 秒後');
        expect(container.textContent).toContain('視聴テスト番組');
        await vi.advanceTimersByTimeAsync(9000);
        expect(router.currentRoute.value.path).toBe('/reminders/');
        expect(container.textContent).toContain('1 秒後');
        await vi.advanceTimersByTimeAsync(1000);
        expect(router.currentRoute.value.path).toBe('/tv/watch/bs101');
        expect(settings.settings.program_reminder_auto_switch_handled).toHaveLength(1);
    });
    it('開始直前に開いた場合も、予告を10秒表示して取り消す時間を確保する', async () => {
        vi.setSystemTime(start - 1000);
        settings.settings.program_reminder_auto_switch_enabled = true;
        await nextTick();
        await mount();
        await vi.advanceTimersByTimeAsync(1000);
        expect(router.currentRoute.value.path).toBe('/reminders/');
        await vi.advanceTimersByTimeAsync(9000);
        expect(router.currentRoute.value.path).toBe('/tv/watch/bs101');
    });
    it('取り消した放送を、再表示しても自動で切り替えない', async () => {
        settings.settings.program_reminder_auto_switch_enabled = true;
        await nextTick();
        const container = await mount();
        container.querySelector('button')!.click();
        await nextTick();
        const otherView = await mount();
        expect(otherView.textContent).not.toContain('秒後');
        await vi.advanceTimersByTimeAsync(11000);
        expect(router.currentRoute.value.path).toBe('/reminders/');
    });
    it('同時刻に複数ある場合は手動選択へ案内する', async () => {
        settings.settings.program_reminder_auto_switch_enabled = true;
        settings.settings.program_reminders.push(structuredClone(second));
        store.verifiedKeys.push(second.key);
        await nextTick();
        const container = await mount();
        expect(container.textContent).toContain('見る番組を選んでください');
        expect(container.querySelector('a')?.getAttribute('href')).toBe('/reminders/?view=Scheduled&notify=Scheduled');
        await vi.advanceTimersByTimeAsync(11000);
        expect(router.currentRoute.value.path).toBe('/reminders/');
    });
    it.each(['Recorded', 'CurrentChannel', 'Stale', 'Failed', 'Hidden', 'Unfocused', 'AlreadyStarted'])(
        '再生中・確認不能・非表示・開始済みの状態では自動切り替えを始めない: %s', async situation => {
            settings.settings.program_reminder_auto_switch_enabled = true;
            if (situation === 'Recorded') await router.push('/videos/watch/1');
            if (situation === 'CurrentChannel') await router.push('/tv/watch/bs101');
            if (situation === 'Stale') store.lastCheckedAt = start - 16 * 60_000;
            if (situation === 'Failed') store.error = '更新できません';
            if (situation === 'Hidden') vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden');
            if (situation === 'Unfocused') vi.mocked(document.hasFocus).mockReturnValue(false);
            if (situation === 'AlreadyStarted') vi.setSystemTime(start + 1);
            const originalPath = router.currentRoute.value.path;
            await nextTick();
            const container = await mount();
            expect(container.textContent).not.toContain('秒後');
            await vi.advanceTimersByTimeAsync(11000);
            expect(router.currentRoute.value.path).toBe(originalPath);
        },
    );
    it.each(['Disabled', 'Muted', 'Missing', 'Moved', 'Blurred', 'Slept', 'Navigated', 'Conflict'])(
        '予告中に条件が変わった場合は中止する: %s', async situation => {
            settings.settings.program_reminder_auto_switch_enabled = true;
            await nextTick();
            const container = await mount();
            expect(container.textContent).toContain('秒後');
            if (situation === 'Disabled') settings.settings.program_reminder_auto_switch_enabled = false;
            if (situation === 'Muted') store.dismiss(reminder.key);
            if (situation === 'Missing') store.verifiedKeys = [];
            if (situation === 'Moved') settings.settings.program_reminders[0].program.start_time = dayjs(start).add(1, 'hour').format();
            if (situation === 'Blurred') {
                vi.mocked(document.hasFocus).mockReturnValue(false);
                window.dispatchEvent(new Event('blur'));
            }
            if (situation === 'Slept') vi.setSystemTime(start + 60_000);
            if (situation === 'Navigated') await router.push('/reminders/?view=Notices');
            if (situation === 'Conflict') {
                settings.settings.program_reminders.push(structuredClone(second));
                store.verifiedKeys.push(second.key);
            }
            await vi.advanceTimersByTimeAsync(12000);
            expect(container.textContent).not.toContain('秒後');
            expect(router.currentRoute.value.path).toBe('/reminders/');
        },
    );
    it('単発の通知には番組情報と直接視聴、複数件にはお知らせ一覧の導線を表示する', async () => {
        vi.spyOn(store, 'refresh').mockResolvedValue();
        vi.spyOn(store, 'checkNotices').mockImplementation(() => {});
        const container = await mount(ProgramReminderNotifications);
        const notice = { id: 'test-notice', reminder_key: reminder.key, title: reminder.program.title,
            channel_name: reminder.channel.name, start_time: reminder.program.start_time, end_time: reminder.program.end_time,
            display_channel_id: reminder.channel.display_channel_id, message: '放送開始前です', created_at: start - 10000, is_read: false };
        store.latestNotices = [notice];
        await nextTick();
        expect(container.textContent).toContain('チャンネルを開く');
        expect(container.textContent).toContain('視聴テスト番組');
        expect(container.querySelector('a')?.getAttribute('href')).toBe('/tv/watch/bs101');
        store.now = start;
        await nextTick();
        expect(container.textContent).toContain('今すぐ見る');
        store.latestNotices = [notice, { ...notice, id: 'another-notice' }];
        await nextTick();
        expect(container.textContent).toContain('お知らせを見る');
        expect(container.querySelector('a')?.getAttribute('href')).toBe('/reminders/?view=Notices');
    });
});
