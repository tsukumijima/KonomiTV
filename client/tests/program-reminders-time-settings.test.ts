import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createApp, defineComponent, h, nextTick, ref, type App, type Ref } from 'vue';
import { createVuetify } from 'vuetify';
import { VAlert, VApp, VBtn, VCheckbox, VSelect, VTextField } from 'vuetify/components';

import ProgramReminderTimeSettings from '@/components/Programs/ProgramReminderTimeSettings.vue';

describe('通知時刻の入力・保存', () => {
    let app: App;
    let container: HTMLElement;
    let times: Ref<number[]>;
    let updates: number[][];

    async function settle(): Promise<void> {
        await nextTick();
        await Promise.resolve();
        await nextTick();
    }

    async function mount(initial: number[] = [1440, 180, 5, 0]): Promise<void> {
        times = ref([...initial]);
        updates = [];
        container = document.createElement('div');
        document.body.append(container);
        app = createApp(defineComponent({
            setup() {
                return () => h(VApp, {}, { default: () => h(ProgramReminderTimeSettings, {
                    modelValue: times.value,
                    'onUpdate:modelValue': value => {
                        updates.push([...value]);
                        times.value = value;
                    },
                }) });
            },
        }));
        app.use(createVuetify({ components: { VAlert, VApp, VBtn, VCheckbox, VSelect, VTextField } }));
        app.component('Icon', defineComponent({ render: () => h('span') }));
        app.mount(container);
        await settle();
    }

    function checkbox(label: string): HTMLInputElement {
        const target = [...container.querySelectorAll('label')].find(item => item.textContent?.trim() === label)!;
        return container.querySelector(`#${target.htmlFor}`)!;
    }

    function button(label: string): HTMLButtonElement {
        return [...container.querySelectorAll('button')].find(item => item.textContent?.trim() === label)!;
    }

    function inputs(): HTMLInputElement[] {
        return [...container.querySelectorAll<HTMLInputElement>('input[type="number"]')];
    }

    async function openCustom(): Promise<void> {
        checkbox('カスタム').click();
        await settle();
    }

    async function enter(index: number, value: string): Promise<void> {
        const input = inputs()[index];
        input.value = value;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        await settle();
    }

    async function chooseUnit(index: number, label: string): Promise<void> {
        const field = container.querySelectorAll('.v-select .v-field')[index];
        field.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
        await settle();
        const option = [...document.querySelectorAll<HTMLElement>('[role="option"]')]
            .find(item => item.textContent?.trim() === label)!;
        expect(option).toBeDefined();
        option.click();
        await settle();
    }

    beforeEach(() => {
        // JSDOM が実装しない配置監視だけを補い、入力部品は実際の Vuetify を使う。
        vi.stubGlobal('ResizeObserver', class {
            observe(): void {}
            unobserve(): void {}
            disconnect(): void {}
        });
    });

    afterEach(() => {
        app?.unmount();
        container?.remove();
        vi.unstubAllGlobals();
    });

    it('選択式からカスタムへ開くだけでは保存せず、選択した4時刻を引き継ぐ', async () => {
        await mount();
        expect(inputs()).toHaveLength(0);
        expect(checkbox('5分前').checked).toBe(true);
        await openCustom();
        expect(inputs().map(input => input.value)).toEqual(['1', '3', '5', '0']);
        expect(updates).toEqual([]);
        expect(button('通知時刻を保存').disabled).toBe(true);
    });

    it.each([
        ['空欄', ''],
        ['負数', '-1'],
        ['小数', '1.5'],
        ['扱える範囲を超える整数', '999999999999999999'],
    ])('%s は保存できず、保存済みの値を保持する', async (_name, value) => {
        await mount([1440]);
        await openCustom();
        await enter(0, value);
        expect(button('通知時刻を保存').disabled).toBe(true);
        button('通知時刻を保存').click();
        await settle();
        expect(times.value).toEqual([1440]);
        expect(updates).toEqual([]);
    });

    it('単位の変更は保存時に換算し、編集中は通知予定を維持する', async () => {
        await mount([1440]);
        await openCustom();
        await chooseUnit(0, '時間前');
        expect(times.value).toEqual([1440]);
        button('通知時刻を保存').click();
        await settle();
        expect(times.value).toEqual([60]);
    });

    it('1分前と60秒前は保存時に1件へまとめる', async () => {
        await mount([1]);
        await openCustom();
        button('通知時刻を追加').click();
        await settle();
        await enter(1, '60');
        expect(inputs()).toHaveLength(2);
        button('通知時刻を保存').click();
        await settle();
        expect(times.value).toEqual([1]);
        expect(inputs()).toHaveLength(1);
    });

    it('1秒前と0秒を区別して保存し、選択式へ戻しても保持する', async () => {
        await mount([0]);
        await openCustom();
        button('通知時刻を追加').click();
        await settle();
        button('通知時刻を保存').click();
        await settle();
        expect(times.value).toEqual([1 / 60, 0]);
        checkbox('カスタム').click();
        await settle();
        expect(checkbox('1秒前（カスタム）').checked).toBe(true);
        expect(checkbox('放送開始時').checked).toBe(true);
    });

    it('すべての行を削除して保存すると、放送前の通知時刻だけが空になる', async () => {
        await mount([5, 0]);
        await openCustom();
        for (const remove of container.querySelectorAll<HTMLButtonElement>('button[aria-label$="を削除"]')) {
            remove.click();
            await settle();
        }
        expect(inputs()).toHaveLength(0);
        expect(times.value).toEqual([5, 0]);
        button('通知時刻を保存').click();
        await settle();
        expect(times.value).toEqual([]);
    });

    it('未保存の編集を戻すと、元の時刻で選択式に戻れる', async () => {
        await mount([5]);
        await openCustom();
        await enter(0, '9');
        expect(checkbox('カスタム').disabled).toBe(true);
        button('変更を戻す').click();
        await settle();
        expect(inputs()[0].value).toBe('5');
        expect(checkbox('カスタム').disabled).toBe(false);
        expect(updates).toEqual([]);
    });

    it('編集中の外部更新を上書きせず、再読み込みで最新の設定へ戻す', async () => {
        await mount([5]);
        await openCustom();
        await enter(0, '9');
        times.value = [60];
        await settle();
        expect(inputs()[0].value).toBe('9');
        expect(container.textContent).toContain('別の操作で通知時刻が更新されました');
        expect(button('通知時刻を保存').disabled).toBe(true);
        button('最新の設定を読み直す').click();
        await settle();
        expect(inputs()[0].value).toBe('1');
        expect(times.value).toEqual([60]);
        expect(updates).toEqual([]);
    });

    it('単位を変えた直後に、範囲エラーの表示と保存可否を一緒に更新する', async () => {
        await mount([1440]);
        await openCustom();
        await enter(0, '200000000');
        expect(container.textContent).toContain('扱える数値の範囲を超えています');
        await chooseUnit(0, '秒前');
        expect(button('通知時刻を保存').disabled).toBe(false);
        expect(container.textContent).not.toContain('扱える数値の範囲を超えています');
        await chooseUnit(0, '日前');
        expect(button('通知時刻を保存').disabled).toBe(true);
        expect(container.textContent).toContain('扱える数値の範囲を超えています');
    });

    it('途中の行を削除して追加し直しても、別の行の値や単位が入れ替わらない', async () => {
        await mount();
        await openCustom();
        container.querySelector<HTMLButtonElement>('button[aria-label="通知時刻 2 を削除"]')!.click();
        await settle();
        expect(inputs().map(input => input.value)).toEqual(['1', '5', '0']);
        button('通知時刻を追加').click();
        await settle();
        await enter(3, '7');
        button('通知時刻を保存').click();
        await settle();
        expect(times.value).toEqual([1440, 5, 7 / 60, 0]);
    });

    it.each([
        ['日前', 86400], ['時間前', 3600], ['分前', 60], ['秒前', 1],
    ] as const)('%s では安全に扱える整数の境界まで保存でき、次の整数は拒否する', async (unit, seconds) => {
        await mount([0]);
        await openCustom();
        await chooseUnit(0, unit);
        const maximum = Math.floor(Number.MAX_SAFE_INTEGER / (seconds * 1000));
        await enter(0, String(maximum + 1));
        expect(button('通知時刻を保存').disabled).toBe(true);
        await enter(0, String(maximum));
        expect(button('通知時刻を保存').disabled).toBe(false);
        button('通知時刻を保存').click();
        await settle();
        expect(Math.round(times.value[0] * 60)).toBe(maximum * seconds);
    });

    it('空の設定から追加して削除すると、未保存扱いを解除する', async () => {
        await mount([]);
        await openCustom();
        button('通知時刻を追加').click();
        await settle();
        expect(checkbox('カスタム').disabled).toBe(true);
        container.querySelector<HTMLButtonElement>('button[aria-label="通知時刻 1 を削除"]')!.click();
        await settle();
        expect(checkbox('カスタム').disabled).toBe(false);
        expect(button('通知時刻を保存').disabled).toBe(true);
        expect(times.value).toEqual([]);
    });
});
