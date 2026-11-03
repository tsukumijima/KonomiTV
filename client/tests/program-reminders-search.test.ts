import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createApp, nextTick, type App } from 'vue';
import { createMemoryHistory, createRouter } from 'vue-router';

import Programs from '@/services/Programs';
import Reservations from '@/services/Reservations';
import Settings, { IServerSettingsDefault } from '@/services/Settings';
import useChannelsStore from '@/stores/ChannelsStore';
import useUserStore from '@/stores/UserStore';
import Search from '@/views/TV/Search.vue';

vi.mock('@/components/Breadcrumbs.vue', () => ({ default: { render: () => null } }));
vi.mock('@/components/Navigation.vue', () => ({ default: { render: () => null } }));
vi.mock('@/components/SPHeaderBar.vue', () => ({ default: { render: () => null } }));
vi.mock('@/components/HeaderBar.vue', () => ({ default: {
    emits: ['search'], template: '<button @click="$emit(\'search\', \'ニュース\')">検索</button>',
} }));
vi.mock('@/components/Programs/ProgramSearchFilters.vue', () => ({ default: { render: () => null } }));
vi.mock('@/components/Reservations/ReservationList.vue', () => ({ default: {
    props: ['emptyMessage', 'emptySubMessage'], template: '<p>{{emptyMessage}} {{emptySubMessage}}</p>',
} }));

describe('検索ページのバックエンド判定', () => {
    let app: App;
    let container: HTMLElement;
    let router: ReturnType<typeof createRouter>;

    async function settle(): Promise<void> {
        for (let index = 0; index < 10; index += 1) {
            await Promise.resolve();
            await nextTick();
        }
    }

    async function mount(backend: 'EDCB' | 'Mirakurun', query: boolean): Promise<void> {
        vi.spyOn(Settings, 'fetchServerSettings').mockResolvedValue({ ...IServerSettingsDefault,
            general: { ...IServerSettingsDefault.general, backend } });
        router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/tv/search', component: Search }] });
        await router.push(query ? '/tv/search?query=ニュース' : '/tv/search');
        await router.isReady();
        container = document.createElement('div');
        document.body.append(container);
        app = createApp(Search);
        app.use(router);
        app.mount(container);
        await settle();
    }

    beforeEach(() => {
        localStorage.clear();
        vi.stubGlobal('matchMedia', () => ({ matches: false }));
        setActivePinia(createPinia());
        vi.spyOn(useChannelsStore(), 'update').mockResolvedValue(undefined);
        vi.spyOn(useUserStore(), 'fetchUser').mockResolvedValue(undefined);
        vi.spyOn(Programs, 'searchPrograms').mockResolvedValue({ programs: [], total: 0 });
        vi.spyOn(Reservations, 'fetchReservations').mockResolvedValue({ reservations: [], total: 0 });
        vi.spyOn(Reservations, 'fetchDefaultRecordSettings').mockResolvedValue(null);
    });
    afterEach(() => {
        app?.unmount();
        container?.remove();
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
    });

    it.each([false, true])('Mirakurunではquery=%sで開いても、再検索してもEDCB専用APIを呼ばない', async query => {
        await mount('Mirakurun', query);
        expect(container.textContent).toContain('番組検索は EDCB');
        expect(container.textContent).toContain('番組表から番組を選んで');
        await router.replace('/tv/search?query=ドラマ');
        await settle();
        container.querySelector('button')!.click();
        await settle();
        expect(Programs.searchPrograms).not.toHaveBeenCalled();
        expect(Reservations.fetchReservations).not.toHaveBeenCalled();
        expect(Reservations.fetchDefaultRecordSettings).not.toHaveBeenCalled();
    });

    it('EDCBでは条件なしの初期表示と再検索を行い、録画設定も取得する', async () => {
        await mount('EDCB', false);
        expect(Programs.searchPrograms).toHaveBeenCalledOnce();
        expect(Programs.searchPrograms).toHaveBeenLastCalledWith(expect.objectContaining({ keyword: '' }));
        expect(Reservations.fetchReservations).toHaveBeenCalledOnce();
        expect(Reservations.fetchDefaultRecordSettings).toHaveBeenCalledOnce();
        container.querySelector('button')!.click();
        await vi.waitFor(() => expect(Programs.searchPrograms).toHaveBeenCalledTimes(2));
        expect(Programs.searchPrograms).toHaveBeenLastCalledWith(expect.objectContaining({ keyword: 'ニュース' }));
    });
});
