import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createApp, defineComponent, h, nextTick, type App } from 'vue';
import { createMemoryHistory, createRouter, RouterView } from 'vue-router';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';

import type { IProgramRecommendationRule } from '@/services/ProgramReminders';

import { IProgramDefault } from '@/services/Programs';
import useProgramRemindersStore from '@/stores/ProgramRemindersStore';
import useSettingsStore from '@/stores/SettingsStore';
import { dayjs } from '@/utils';
import ProgramReminders from '@/views/ProgramReminders.vue';

// 共通ヘッダーなどはこの検証の対象外。設定画面・入力欄・タブ・ルーターは実物を使う。
vi.mock('@/components/Breadcrumbs.vue', () => ({ default: { render: () => null } }));
vi.mock('@/components/HeaderBar.vue', () => ({ default: { render: () => null } }));
vi.mock('@/components/Navigation.vue', () => ({ default: { render: () => null } }));
vi.mock('@/components/SPHeaderBar.vue', () => ({ default: { render: () => null } }));

const comedyRule: IProgramRecommendationRule = {
    id: 'comedy', name: 'お笑い', keyword: 'お笑い', exclude_keyword: '', genre: null,
    is_title_only: true, is_free_only: true, is_enabled: true,
};

describe('通知設定の操作と編集中の画面移動', () => {
    let app: App;
    let container: HTMLElement;
    let settings: ReturnType<typeof useSettingsStore>;
    let router: ReturnType<typeof createRouter>;

    async function settle(): Promise<void> {
        await nextTick();
        await Promise.resolve();
        await nextTick();
    }

    function button(label: string): HTMLButtonElement {
        return [...document.querySelectorAll('button')].find(item => item.textContent?.trim() === label)!;
    }

    async function seedLists(): Promise<void> {
        const program = { ...IProgramDefault, id: 'test-program', title: 'お笑い番組',
            start_time: dayjs().add(1, 'hour').format(), end_time: dayjs().add(2, 'hour').format() };
        const scheduled = {
            key: 'comedy-on', program, channel: { id: 'test-channel', name: 'テスト放送', display_channel_id: 'gr011' },
            source: 'Recommended' as const, status: 'Scheduled' as const, reasons: ['以前の表示名：「お笑い」に一致'],
            keyword_matches: [{ id: comedyRule.id, name: comedyRule.name }], created_at: dayjs().valueOf(),
        };
        settings.settings.program_recommendation_rules = [{ ...comedyRule }];
        settings.settings.program_reminders = [scheduled, {
            ...scheduled, key: 'comedy-off', status: 'Dismissed', program: { ...program, title: 'お笑い候補' },
        }, { ...scheduled, key: 'manual', source: 'Manual', keyword_matches: [], reasons: ['自分で選んだ番組'],
            program: { ...program, title: '手動選択の音楽' } }];
        settings.settings.program_reminder_notices = [{
            id: 'history', reminder_key: scheduled.key, title: '以前のお知らせ', channel_name: 'テスト放送',
            start_time: program.start_time, end_time: program.end_time, display_channel_id: 'gr011',
            message: '5分前', created_at: dayjs().valueOf(), is_read: false,
        }];
        await settle();
    }

    function visibleTitles(): (string | null)[] {
        return [...container.querySelectorAll('article h3')].map(item => item.textContent);
    }

    function ruleInput(labelText: string): HTMLInputElement {
        const label = [...document.querySelectorAll<HTMLLabelElement>('.v-dialog label')]
            .find(item => item.textContent?.trim() === labelText && item.htmlFor)!;
        return document.getElementById(label.htmlFor) as HTMLInputElement;
    }

    async function fillRuleInput(label: string, value: string): Promise<void> {
        const input = ruleInput(label);
        input.value = value;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        await settle();
    }

    async function editTime(): Promise<void> {
        button('通知設定').click();
        await settle();
        const label = [...container.querySelectorAll('label')].find(item => item.textContent?.trim() === 'カスタム')!;
        container.querySelector<HTMLInputElement>(`#${label.htmlFor}`)!.click();
        await settle();
        const input = container.querySelector<HTMLInputElement>('input[type="number"]')!;
        input.value = '9';
        input.dispatchEvent(new Event('input', { bubbles: true }));
        await settle();
    }

    beforeEach(async () => {
        localStorage.clear();
        vi.stubGlobal('ResizeObserver', class {
            observe(): void {}
            unobserve(): void {}
            disconnect(): void {}
        });
        vi.stubGlobal('matchMedia', (media: string) => ({
            media, matches: false, onchange: null,
            addEventListener(): void {}, removeEventListener(): void {},
            addListener(): void {}, removeListener(): void {},
            dispatchEvent: () => true,
        }));
        const pinia = createPinia();
        setActivePinia(pinia);
        settings = useSettingsStore();
        settings.settings.program_reminder_lead_times = [5];
        vi.spyOn(useProgramRemindersStore(), 'refresh').mockResolvedValue(undefined);
        router = createRouter({ history: createMemoryHistory(), routes: [
            { path: '/reminders/', component: ProgramReminders },
            { path: '/elsewhere/', component: { render: () => h('p', '移動先') } },
            { path: '/tv/search', component: { render: () => null } },
            { path: '/tv/watch/:channel', component: { render: () => null } },
        ] });
        await router.push('/reminders/');
        await router.isReady();
        container = document.createElement('div');
        document.body.append(container);
        app = createApp({ render: () => h(components.VApp, {}, { default: () => h(RouterView) }) });
        app.use(pinia);
        app.use(router);
        app.use(createVuetify({ components }));
        app.component('Icon', defineComponent({ render: () => h('span') }));
        app.mount(container);
        await settle();
    });

    afterEach(() => {
        app?.unmount();
        container?.remove();
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
        localStorage.clear();
    });

    it('重複の追加は画面内の一文だけで止め、入力を保持し、表示名を変えた後に保存できる', async () => {
        settings.settings.program_recommendation_rules = [{ ...comedyRule, is_title_only: false, is_enabled: false }];
        button('通知設定').click();
        await settle();
        button('キーワードを追加').click();
        await settle();
        await fillRuleInput('番組名・出演者・キーワード', 'お笑い');
        button('キーワードを保存').click();
        await settle();
        expect(document.querySelector('.v-dialog p[role="alert"]')?.textContent).toBe('同じ条件がすでに追加されております。');
        expect(document.querySelectorAll('.v-dialog.v-overlay--active')).toHaveLength(1);
        expect(settings.settings.program_recommendation_rules).toHaveLength(1);
        expect(ruleInput('番組名・出演者・キーワード').value).toBe('お笑い');
        expect(ruleInput('表示名（任意）').value).toBe('');
        await fillRuleInput('表示名（任意）', '別の表示名');
        button('キーワードを保存').click();
        await settle();
        expect(settings.settings.program_recommendation_rules.map(item => item.name)).toEqual(['お笑い', '別の表示名']);
        expect(settings.settings.program_recommendation_rules[0].is_enabled).toBe(false);
        expect(document.querySelectorAll('.v-dialog.v-overlay--active')).toHaveLength(0);
    });

    it('編集して同じ条件になる場合も保存を止め、元の条件を変更せずに入力を残す', async () => {
        settings.settings.program_recommendation_rules = [
            { ...comedyRule, is_title_only: false }, { ...comedyRule, id: 'second', name: '別名', is_title_only: false },
        ];
        button('通知設定').click();
        await settle();
        container.querySelector<HTMLButtonElement>('button[aria-label="別名を編集"]')!.click();
        await settle();
        await fillRuleInput('表示名（任意）', 'お笑い');
        button('キーワードを保存').click();
        await settle();
        expect(document.querySelector('.v-dialog p[role="alert"]')?.textContent).toBe('同じ条件がすでに追加されております。');
        expect(settings.settings.program_recommendation_rules.map(item => item.name)).toEqual(['お笑い', '別名']);
        expect(ruleInput('表示名（任意）').value).toBe('お笑い');
    });

    it('編集対象自身は重複から外し、表示名が同じでも除外語が異なる追加は保存できる', async () => {
        settings.settings.program_recommendation_rules = [{ ...comedyRule, is_title_only: false }];
        button('通知設定').click();
        await settle();
        container.querySelector<HTMLButtonElement>('button[aria-label="お笑いを編集"]')!.click();
        await settle();
        button('キーワードを保存').click();
        await settle();
        expect(document.querySelectorAll('.v-dialog.v-overlay--active')).toHaveLength(0);
        expect(settings.settings.program_recommendation_rules).toHaveLength(1);
        button('キーワードを追加').click();
        await settle();
        await fillRuleInput('番組名・出演者・キーワード', 'お笑い');
        await fillRuleInput('含めないキーワード（任意）', '再放送');
        button('キーワードを保存').click();
        await settle();
        expect(settings.settings.program_recommendation_rules).toHaveLength(2);
        expect(settings.settings.program_recommendation_rules.map(item => item.exclude_keyword)).toEqual(['', '再放送']);
    });

    it('保存済みの重複条件は1行に整理し、削除後に同じ条件を登録できる', async () => {
        await seedLists();
        settings.settings.program_recommendation_rules = [{ ...comedyRule }, { ...comedyRule, id: 'duplicate' }];
        button('通知設定').click();
        await settle();
        expect(settings.settings.program_recommendation_rules).toHaveLength(1);
        expect(container.querySelectorAll('.rule-row')).toHaveLength(1);
        container.querySelector<HTMLButtonElement>('button[aria-label="お笑いを削除"]')!.click();
        await settle();
        button('キーワードを削除').click();
        await settle();
        button('キーワードを追加').click();
        await settle();
        await fillRuleInput('番組名・出演者・キーワード', 'お笑い');
        ruleInput('キーワードは番組名だけから探す').click();
        await settle();
        button('キーワードを保存').click();
        await settle();
        expect(settings.settings.program_recommendation_rules).toHaveLength(1);
        expect(document.querySelectorAll('.v-dialog.v-overlay--active')).toHaveLength(0);
        expect(useProgramRemindersStore().scheduledReminders).toHaveLength(2);
        expect(settings.settings.program_reminder_notices).toHaveLength(1);
    });

    it('4タブを指定順に表示し、通知予定には登録済みの番組だけを表示する', async () => {
        await seedLists();
        expect([...container.querySelectorAll('[role="tab"]')].map(item => item.textContent?.trim())).toEqual([
            '通知予定（2）', '番組候補（2）', 'お知らせ(1)', '通知設定',
        ]);
        expect(visibleTitles()).toEqual(['お笑い番組', '手動選択の音楽']);
        button('番組候補（2）').click();
        await settle();
        expect(visibleTitles()).toEqual(['お笑い候補', 'お笑い番組']);
        const cards = [...container.querySelectorAll('article')];
        expect(cards.find(item => item.querySelector('h3')?.textContent === 'お笑い番組')?.textContent).toContain('通知設定済み');
        expect(cards.find(item => item.querySelector('h3')?.textContent === 'お笑い候補')?.textContent).toContain('通知未設定');
        expect(container.querySelector('.reminder-card__reasons')?.textContent).toContain('お笑い：「お笑い」に一致');
        expect(container.querySelector('.reminder-card__reasons')?.textContent).not.toContain('以前の表示名');
    });

    it('候補の通知を登録・停止すると、通知予定の所属と候補の状態表示が切り替わる', async () => {
        await seedLists();
        button('番組候補（2）').click();
        await settle();
        button('通知する').click();
        await settle();
        expect(useProgramRemindersStore().scheduledReminders).toHaveLength(3);
        expect(visibleTitles()).toHaveLength(2);
        button('通知予定（3）').click();
        await settle();
        const card = [...container.querySelectorAll('article')].find(item => item.querySelector('h3')?.textContent === 'お笑い候補')!;
        [...card.querySelectorAll('button')].find(item => item.textContent?.trim() === '通知しない')!.click();
        await settle();
        expect(visibleTitles()).toEqual(['お笑い番組', '手動選択の音楽']);
        button('番組候補（2）').click();
        await settle();
        expect(visibleTitles()).toHaveLength(2);
        expect([...container.querySelectorAll('article')].find(item => item.querySelector('h3')?.textContent === 'お笑い候補')?.textContent)
            .toContain('通知未設定');
    });

    it('キーワード削除後も通知予定とお知らせが残り、削除済みキーワードで絞り込める', async () => {
        await seedLists();
        button('通知設定').click();
        await settle();
        container.querySelector<HTMLButtonElement>('button[aria-label="お笑いを削除"]')!.click();
        await settle();
        expect(document.body.textContent).toContain('登録済みの通知予定とお知らせは残ります');
        button('キーワードを削除').click();
        await settle();
        expect(settings.settings.program_recommendation_rules).toEqual([]);
        expect(settings.settings.program_reminder_notices).toHaveLength(1);
        button('通知予定（2）').click();
        await settle();
        expect(visibleTitles()).toEqual(['お笑い番組', '手動選択の音楽']);
        button('並べ替えと絞り込み').click();
        await settle();
        expect(document.body.textContent).toContain('（＊）削除済みキーワード');
        const label = [...document.querySelectorAll('label')].find(item => item.textContent === 'キーワード（いずれかに一致）')!;
        label.closest('.v-input')!.querySelector<HTMLInputElement>('input')!
            .dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
        await settle();
        const option = [...document.querySelectorAll<HTMLElement>('.v-list-item')].find(item => item.textContent?.includes('お笑い＊（1）'))!;
        expect(option).toBeDefined();
        option.click();
        await settle();
        button('閉じる').click();
        await settle();
        expect(visibleTitles()).toEqual(['お笑い番組']);
        button('番組候補（0）').click();
        await settle();
        expect(visibleTitles()).toEqual([]);
        expect(container.textContent).toContain('キーワードを登録しましょう');
        button('通知予定（2）').click();
        await settle();
        expect(visibleTitles()).toEqual(['お笑い番組']);
        button('お知らせ(1)').click();
        await settle();
        expect(container.querySelector('article h2')?.textContent).toBe('以前のお知らせ');
    });

    it('現在のキーワードの変更と停止に候補が追従し、通知予定は保持する', async () => {
        await seedLists();
        button('番組候補（2）').click();
        await settle();
        useProgramRemindersStore().updateRecommendationRules([{ ...comedyRule, name: '音楽', keyword: '音楽' }]);
        await settle();
        expect(visibleTitles()).toEqual(['手動選択の音楽']);
        expect(container.querySelector('.reminder-card__reasons')?.textContent).toContain('音楽：「音楽」に一致');
        settings.settings.program_recommendation_rules[0].is_enabled = false;
        await settle();
        expect(visibleTitles()).toEqual([]);
        button('通知予定（2）').click();
        await settle();
        expect(visibleTitles()).toEqual(['お笑い番組', '手動選択の音楽']);
    });

    it('今後の通知をオフにしても既存は維持し、一括オフの後は番組ごとに選び直せる', async () => {
        const program = {
            ...IProgramDefault, id: 'test-program', title: '手動で選んだ番組',
            start_time: dayjs().add(1, 'hour').format(), end_time: dayjs().add(2, 'hour').format(),
        };
        const manual = {
            key: 'manual', program, channel: { id: 'test-channel', name: 'テスト放送', display_channel_id: 'gr011' },
            source: 'Manual' as const, status: 'Scheduled' as const, reasons: ['自分で選んだ番組'], created_at: dayjs().valueOf(),
        };
        settings.settings.program_reminders = [manual, {
            ...manual, key: 'recommended', source: 'Recommended', program: { ...program, title: 'おすすめ番組' },
        }, { ...manual, key: 'muted', status: 'Dismissed', program: { ...program, title: '通知を止めた番組' } }];
        settings.settings.program_recommendation_rules = [{ ...comedyRule, keyword: '番組' }];
        await settle();
        button('通知設定').click();
        await settle();
        const offLabel = [...container.querySelectorAll('label')].find(item =>
            item.textContent?.trim() === '通知オフで追加し、見たい番組だけ自分で選ぶ')!;
        container.querySelector<HTMLInputElement>(`#${offLabel.htmlFor}`)!.click();
        await settle();
        expect(settings.settings.program_recommendation_notify_by_default).toBe(false);
        expect(useProgramRemindersStore().scheduledReminders).toHaveLength(2);

        button('登録済み番組の通知をすべてオフ').click();
        await settle();
        expect(settings.settings.program_reminders).toHaveLength(3);
        expect(settings.settings.program_reminders.every(item => item.status === 'Dismissed')).toBe(true);
        expect(settings.settings.program_recommendation_notify_by_default).toBe(false);
        expect(settings.settings.program_reminder_notifications_enabled).toBe(true);
        expect(button('登録済み番組の通知をすべてオフ').disabled).toBe(true);

        button('番組候補（3）').click();
        await settle();
        const manualCard = [...container.querySelectorAll('article')].find(item =>
            item.querySelector('h3')?.textContent === '手動で選んだ番組')!;
        [...manualCard.querySelectorAll('button')].find(item => item.textContent?.trim() === '通知する')!.click();
        await settle();
        expect(useProgramRemindersStore().scheduledReminders.map(item => item.key)).toEqual(['manual']);
        expect(settings.settings.program_reminders).toHaveLength(3);
    });

    it('通知予定・番組候補・お知らせを往復しても、カスタムの未保存入力を保持する', async () => {
        await editTime();
        for (const tab of ['通知予定（0）', '番組候補（0）', 'お知らせ']) {
            button(tab).click();
            await settle();
            button('通知設定').click();
            await settle();
            expect(container.querySelector<HTMLInputElement>('input[type="number"]')?.value).toBe('9');
            expect(settings.settings.program_reminder_lead_times).toEqual([5]);
        }
    });

    it('別ページへの移動を取り消すと入力が残り、破棄を選んだときだけ移動する', async () => {
        await editTime();
        let navigation = router.push('/elsewhere/');
        await settle();
        expect(document.body.textContent).toContain('変更を破棄しますか？');
        button('編集に戻る').click();
        await navigation;
        await settle();
        expect(router.currentRoute.value.path).toBe('/reminders/');
        expect(container.querySelector<HTMLInputElement>('input[type="number"]')!.value).toBe('9');
        navigation = router.push('/elsewhere/');
        await settle();
        button('変更を破棄').click();
        await navigation;
        await settle();
        expect(router.currentRoute.value.path).toBe('/elsewhere/');
        expect(settings.settings.program_reminder_lead_times).toEqual([5]);
    });

    it('再読み込みの確認は未保存の間だけ有効で、保存後と画面の終了後に解除する', async () => {
        await editTime();
        const unsaved = new Event('beforeunload', { cancelable: true });
        window.dispatchEvent(unsaved);
        expect(unsaved.defaultPrevented).toBe(true);
        button('通知時刻を保存').click();
        await settle();
        expect(settings.settings.program_reminder_lead_times).toEqual([9]);
        const saved = new Event('beforeunload', { cancelable: true });
        window.dispatchEvent(saved);
        expect(saved.defaultPrevented).toBe(false);
        await router.push('/elsewhere/');
        await settle();
        expect(router.currentRoute.value.path).toBe('/elsewhere/');
        const left = new Event('beforeunload', { cancelable: true });
        window.dispatchEvent(left);
        expect(left.defaultPrevented).toBe(false);
    });
});
