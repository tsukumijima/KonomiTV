import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { IProgramRecommendationRule, IProgramReminder, IProgramReminderCandidate } from '@/services/ProgramReminders';

import Programs, { IProgramDefault, type ITimeTable } from '@/services/Programs';
import useProgramRemindersStore from '@/stores/ProgramRemindersStore';
import useSettingsStore from '@/stores/SettingsStore';
import { dayjs } from '@/utils';
import {
    collectProgramReminderNotices, deduplicateProgramRecommendationRules, getProgramRecommendationReasons,
    getProgramRecommendationRuleKey, getProgramReminderKey, getProgramReminderKeywords,
    groupProgramRemindersByRule, groupScheduledProgramRemindersByKeyword, isSameReminderBroadcast,
    normalizeProgramReminderLeadTimes, reconcileProgramReminders,
} from '@/utils/ProgramReminderUtils';

const start = dayjs('2026-11-10T20:00:00+09:00').valueOf();
const candidate: IProgramReminderCandidate = {
    program: {
        ...IProgramDefault, id: 'NID4-SID101-EID100', channel_id: 'NID4-SID101',
        network_id: 4, service_id: 101, event_id: 100,
        title: 'Ｍ－１ お笑い特番', description: '新しい芸人が登場', detail: { 出演者: '山田太郎' },
        start_time: dayjs(start).format(), end_time: dayjs(start).add(1, 'hour').format(),
        genres: [{ major: 'バラエティ', middle: 'お笑い・コメディ' }],
    },
    channel: { id: 'NID4-SID101', name: 'テスト放送', display_channel_id: 'bs101' },
};
const rule: IProgramRecommendationRule = {
    id: 'rule-1', name: 'お笑い', keyword: 'm-1 特番', exclude_keyword: '', genre: null,
    is_title_only: false, is_free_only: true, is_enabled: true,
};
const reminder: IProgramReminder = {
    ...candidate, key: getProgramReminderKey(candidate.program), source: 'Recommended', status: 'Scheduled',
    reasons: ['お笑いに一致'], created_at: start - 8 * 86400_000,
};

describe('番組の推薦条件', () => {
    it('文字幅・大小文字を正規化し、空白区切りを AND で照合する', () => {
        expect(getProgramRecommendationReasons(candidate.program, [rule])).toEqual(['お笑い：「m-1」・「特番」に一致']);
        expect(getProgramRecommendationReasons(candidate.program, [{ ...rule, keyword: 'M-1 ドラマ' }])).toEqual([]);
    });
    it('番組詳細の出演者も探し、番組名だけの条件では対象を限定する', () => {
        expect(getProgramRecommendationReasons(candidate.program, [{ ...rule, keyword: '山田太郎' }])).toHaveLength(1);
        expect(getProgramRecommendationReasons(candidate.program, [{ ...rule, keyword: '山田太郎', is_title_only: true }])).toEqual([]);
    });
    it('ジャンルだけから未知の番組も探し、空の条件・停止中の条件を除外する', () => {
        expect(getProgramRecommendationReasons(candidate.program, [{ ...rule, keyword: '', genre: 'バラエティ' }])).toHaveLength(1);
        expect(getProgramRecommendationReasons(candidate.program, [{ ...rule, keyword: '' }])).toEqual([]);
        expect(getProgramRecommendationReasons(candidate.program, [{ ...rule, is_enabled: false }])).toEqual([]);
    });
    it('除外語は OR で照合し、無料放送の条件を適用する', () => {
        expect(getProgramRecommendationReasons(candidate.program, [{ ...rule, exclude_keyword: '再放送 芸人' }])).toEqual([]);
        expect(getProgramRecommendationReasons({ ...candidate.program, is_free: false }, [rule])).toEqual([]);
    });
});

describe('登録した条件ごとの分類', () => {
    it('現在の条件名・登録順で分類し、停止中の条件でも保存した候補を探せる', () => {
        const rules = [
            { ...rule, id: 'performer', name: '出演者', keyword: '山田太郎', is_enabled: false },
            { ...rule, name: '名前を変更した条件' },
        ];
        const before = JSON.stringify({ reminder, rules });
        const groups = groupProgramRemindersByRule([reminder], rules);
        expect(groups.map(group => group.name)).toEqual(['出演者', '名前を変更した条件', '現在の条件に一致しない番組']);
        expect(groups[0].key).toBe('Rule:performer');
        expect(groups[0].reminders).toEqual([reminder]);
        expect(groups[1].reminders).toEqual([reminder]);
        expect(JSON.stringify({ reminder, rules })).toBe(before);
    });
    it('各条件内を放送順にそろえ、編集後の条件に合わない候補も別のグループに残す', () => {
        const earlier = { ...reminder, key: 'earlier', program: { ...reminder.program,
            start_time: dayjs(start).subtract(1, 'hour').format() } };
        const unmatched = { ...reminder, key: 'unmatched', program: { ...reminder.program, title: 'ニュース' } };
        const groups = groupProgramRemindersByRule([reminder, unmatched, earlier], [rule]);
        expect(groups[0].reminders.map(item => item.key)).toEqual(['earlier', reminder.key]);
        expect(groups[1].reminders).toEqual([unmatched]);
        expect(groupProgramRemindersByRule([reminder], [])[0].reminders).toEqual([reminder]);
    });
});

describe('放送予定の更新', () => {
    it('複数の条件・同じ番組の重複応答を1件にまとめる', () => {
        const result = reconcileProgramReminders([], [candidate, candidate], [rule, { ...rule, id: 'rule-2' }], true, start - 1000);
        expect(result.reminders).toHaveLength(1);
        expect(result.reminders[0].reasons).toHaveLength(2);
    });
    it('放送時刻の変更を同じ予定に反映し、発見時刻と除外状態を維持する', () => {
        const delayed = { ...candidate, program: { ...candidate.program, start_time: dayjs(start).add(30, 'minute').format() } };
        const result = reconcileProgramReminders([{ ...reminder, status: 'Dismissed' }], [delayed], [rule], true, start - 1000);
        expect(result.reminders).toHaveLength(1);
        expect(result.reminders[0]).toMatchObject({ key: reminder.key, created_at: reminder.created_at, status: 'Dismissed' });
        expect(result.reminders[0].program.start_time).toBe(delayed.program.start_time);
        expect(result.changedKeys).toEqual([reminder.key]);
    });
    it('同じイベント ID でも翌日の放送は別の予定として扱う', () => {
        const nextDay = { ...candidate, program: { ...candidate.program,
            start_time: dayjs(start).add(1, 'day').format(), end_time: dayjs(start).add(25, 'hour').format() } };
        expect(isSameReminderBroadcast(candidate.program, nextDay.program)).toBe(false);
        const result = reconcileProgramReminders([reminder], [candidate, nextDay], [rule], true, start - 1000);
        expect(result.reminders).toHaveLength(2);
    });
    it('番組表から消えた予定を保持し、お知らせ対象から外す', () => {
        const result = reconcileProgramReminders([reminder], [], [rule], true, start - 1000);
        expect(result.reminders).toEqual([{ ...reminder, keyword_matches: [{
            id: rule.id, name: rule.name, condition_key: getProgramRecommendationRuleKey(rule),
        }] }]);
        expect(result.verifiedKeys).toEqual([]);
    });
    it('自動追加の停止中も手動の予定を更新し、新しいおすすめは追加しない', () => {
        expect(reconcileProgramReminders([], [candidate], [rule], false, start - 1000).reminders).toEqual([]);
        const manual = { ...reminder, source: 'Manual' as const };
        expect(reconcileProgramReminders([manual], [candidate], [], false, start - 1000).verifiedKeys).toEqual([manual.key]);
    });
    it('通知オフを既定にしてもおすすめを保存し、通知は生成しない', () => {
        const result = reconcileProgramReminders([], [candidate], [rule], true, start - 300_000, false);
        expect(result.reminders).toHaveLength(1);
        expect(result.reminders[0].status).toBe('Dismissed');
        expect(collectProgramReminderNotices(result.reminders, [], result.verifiedKeys, [], [5], true, start - 300_000)).toEqual([]);
    });
    it('通知の既定を変更しても、既存のオン・オフと手動登録を維持する', () => {
        expect(reconcileProgramReminders([reminder], [candidate], [rule], true, start - 1000, false)
            .reminders[0].status).toBe('Scheduled');
        const muted = { ...reminder, source: 'Manual' as const, status: 'Dismissed' as const };
        expect(reconcileProgramReminders([muted], [candidate], [rule], true, start - 1000, true)
            .reminders[0]).toMatchObject({ source: 'Manual', status: 'Dismissed' });
    });
    it('100件を超える一致番組をすべて追加し、既存候補の通知状態を保持する', () => {
        const candidates = Array.from({ length: 110 }, (_, index) => ({ ...candidate, program: { ...candidate.program,
            id: `${candidate.program.id}-${index}`, start_time: dayjs(start).add(index, 'minute').format() } }));
        const result = reconcileProgramReminders([reminder], candidates, [rule], true, start - 1000);
        // 番組表に含まれない既存1件も保持するため、新規110件と合わせて111件になる。
        expect(result.reminders.filter(item => item.status === 'Scheduled')).toHaveLength(111);
        expect(result.matchingCount).toBe(110);
        expect(result.reminders.some(item => item.key === reminder.key)).toBe(true);
        const muted = reconcileProgramReminders([], candidates, [rule], true, start - 1000, false);
        expect(muted.reminders).toHaveLength(110);
        expect(muted.reminders.every(item => item.status === 'Dismissed')).toBe(true);
        const refreshed = reconcileProgramReminders(muted.reminders, candidates, [rule], true, start - 500, true);
        expect(refreshed.reminders).toHaveLength(110);
        expect(refreshed.reminders.every(item => item.status === 'Dismissed')).toBe(true);
    });
});

describe('通知予定に残すキーワード', () => {
    it('名前を変更しても登録時の ID で追跡し、削除後は最後の名前に印を付ける', () => {
        const stored = { ...reminder, keyword_matches: [{ id: rule.id, name: rule.name }] };
        const renamed = { ...rule, name: 'コメディ', keyword: '別の内容' };
        const keywords = getProgramReminderKeywords(stored, [renamed]);
        expect(keywords).toEqual([{ id: rule.id, name: 'コメディ', condition_key: getProgramRecommendationRuleKey(renamed) }]);
        const saved = { ...stored, keyword_matches: keywords };
        expect(groupScheduledProgramRemindersByKeyword([saved], []).filter(group => group.reminders.length > 0))
            .toEqual([{ key: `Condition:${getProgramRecommendationRuleKey(renamed)}`, name: 'コメディ＊', reminders: [saved] }]);
    });
    it('削除後に同名でも検索条件が異なるキーワードを作った場合は、分類を分ける', () => {
        const stored = { ...reminder, keyword_matches: [{ id: rule.id, name: rule.name, condition_key: getProgramRecommendationRuleKey(rule) }] };
        const recreated = { ...rule, id: 'new-rule', keyword: 'm-1' };
        const groups = groupScheduledProgramRemindersByKeyword([stored], [recreated]);
        expect(groups.map(group => [group.key, group.name, group.reminders.length])).toEqual([
            [`Condition:${getProgramRecommendationRuleKey(recreated)}`, 'お笑い', 1],
            [`Condition:${getProgramRecommendationRuleKey(rule)}`, 'お笑い＊', 1], ['Unmatched', 'キーワード未指定', 0],
        ]);
    });
    it('旧形式の名前に全角コロンが含まれていても、削除済みの名前を引き継ぐ', () => {
        const legacy = { ...reminder, reasons: ['出演者：お笑い：「m-1」・「特番」に一致'] };
        expect(getProgramReminderKeywords(legacy, [])).toEqual([{ id: 'Legacy:出演者：お笑い', name: '出演者：お笑い' }]);
    });
    it('旧理由に検索語が残っていても、全条件が不明なものは現在の条件と同一と推測しない', () => {
        const legacy = { ...reminder, reasons: ['旧名称：「m-1」・「特番」に一致'] };
        expect(getProgramReminderKeywords(legacy, [rule])).toEqual([
            { id: 'Legacy:旧名称', name: '旧名称' },
            { id: rule.id, name: rule.name, condition_key: getProgramRecommendationRuleKey(rule) },
        ]);
        const second = { ...rule, id: 'second', name: '別名' };
        expect(getProgramReminderKeywords(legacy, [rule, second])).toEqual([
            { id: 'Legacy:旧名称', name: '旧名称' },
            { id: rule.id, name: rule.name, condition_key: getProgramRecommendationRuleKey(rule) },
            { id: 'second', name: '別名', condition_key: getProgramRecommendationRuleKey(second) },
        ]);
    });
    it('保存と番組表更新を経ても、削除済みキーワードと通知の状態を保持する', () => {
        const stored: IProgramReminder = JSON.parse(JSON.stringify({
            ...reminder, status: 'Dismissed', keyword_matches: [{ id: 'deleted', name: '削除した名前' }],
        }));
        const result = reconcileProgramReminders([stored], [candidate], [], true, start - 1000);
        expect(result.reminders).toEqual([stored]);
        expect(result.verifiedKeys).toEqual([stored.key]);
        expect(result.matchingCount).toBe(0);
    });
});

describe('キーワードの完全一致による重複判定', () => {
    it('表示名と全検索条件を厳密に比較し、文字幅・大小文字・空白・語順も区別する', () => {
        const key = getProgramRecommendationRuleKey(rule);
        expect(getProgramRecommendationRuleKey({ ...rule, id: 'another', is_enabled: false })).toBe(key);
        const different: Partial<IProgramRecommendationRule>[] = [
            { name: '別表示名' }, { keyword: '別の検索語' }, { exclude_keyword: '再放送' }, { genre: 'バラエティ' },
            { is_title_only: true }, { is_free_only: false }, { keyword: 'M-1 特番' },
            { keyword: 'ｍ－１ 特番' }, { keyword: 'm-1  特番' }, { keyword: '特番 m-1' },
        ];
        for (const change of different) expect(getProgramRecommendationRuleKey({ ...rule, ...change })).not.toBe(key);
    });
    it('登録済みの完全一致する条件だけをまとめ、表示名の異なる条件と有効状態を保持する', () => {
        const named = { ...rule, id: 'named', name: '表示名違い' };
        expect(deduplicateProgramRecommendationRules([
            { ...rule, is_enabled: false }, { ...rule, id: 'duplicate' }, named,
        ])).toEqual([rule, named]);
    });
    it('同じ条件の削除・再追加・再削除を繰り返しても、分類と番組件数を1つに保つ', () => {
        let stored = { ...reminder, keyword_matches: getProgramReminderKeywords({ ...reminder, keyword_matches: [] }, [rule]) };
        const originalKey = groupScheduledProgramRemindersByKeyword([stored], [rule])[0].key;
        for (let index = 0; index < 3; index += 1) {
            stored = JSON.parse(JSON.stringify({ ...stored, keyword_matches: getProgramReminderKeywords(stored, []) }));
            const recreated = { ...rule, id: `recreated-${index}` };
            stored = { ...stored, keyword_matches: getProgramReminderKeywords(stored, [recreated]) };
            expect(stored.keyword_matches).toHaveLength(1);
            expect(groupScheduledProgramRemindersByKeyword([stored], [recreated])[0])
                .toMatchObject({ key: originalKey, name: 'お笑い', reminders: [stored] });
            const deletedGroups = groupScheduledProgramRemindersByKeyword([stored], []).filter(group => group.reminders.length > 0);
            expect(deletedGroups).toEqual([{ key: originalKey, name: 'お笑い＊', reminders: [stored] }]);
            expect(stored.status).toBe('Scheduled');
        }
    });
    it('別IDの同一条件に関連付いた番組をまとめ、両方に該当する番組を二重に数えない', () => {
        const first = { id: 'old-1', name: rule.name, condition_key: getProgramRecommendationRuleKey(rule) };
        const second = { ...first, id: 'old-2' };
        const programs = [
            { ...reminder, key: 'first', keyword_matches: [first, second] },
            { ...reminder, key: 'second', keyword_matches: [second] },
        ];
        const groups = groupScheduledProgramRemindersByKeyword(programs, []).filter(group => group.reminders.length > 0);
        expect(groups).toHaveLength(1);
        expect(groups[0].reminders.map(item => item.key)).toEqual(['first', 'second']);
        expect(getProgramReminderKeywords(programs[0], [])).toEqual([first]);
    });
    it('旧データの名前が同じでも、検索条件が未保存なら別IDのまま保持する', () => {
        const stored = { ...reminder, keyword_matches: [
            { id: 'unknown-1', name: '同じ名前' }, { id: 'unknown-2', name: '同じ名前' },
        ] };
        expect(getProgramReminderKeywords(stored, [])).toEqual(stored.keyword_matches);
        expect(groupScheduledProgramRemindersByKeyword([stored], []).filter(group => group.reminders.length > 0)).toHaveLength(2);
    });
});

describe('放送前のお知らせ', () => {
    it('任意の時刻を整数秒で整理し、重複と無効な値を除く', () => {
        expect(normalizeProgramReminderLeadTimes([5, 300 / 60, 0, 3 / 60, 2 / 60, 1 / 60,
            -1, NaN, Infinity, Number.MAX_VALUE])).toEqual([5, 3 / 60, 2 / 60, 1 / 60, 0]);
    });
    it('3秒前から開始時まで1秒ずつ通知し、早期通知とリロード後の重複を防ぐ', () => {
        const times = [3 / 60, 2 / 60, 1 / 60, 0];
        let notices = collectProgramReminderNotices([reminder], [], [reminder.key], [], times, false, start - 3001);
        expect(notices).toEqual([]);
        for (let seconds = 3; seconds >= 0; seconds -= 1) {
            const next = collectProgramReminderNotices([reminder], notices, [reminder.key], [], times, false, start - seconds * 1000);
            expect(next.map(item => item.message)).toEqual([seconds === 0 ? '放送開始時' : `${seconds}秒前`]);
            notices = JSON.parse(JSON.stringify([...notices, ...next]));
        }
        expect(collectProgramReminderNotices([reminder], notices, [reminder.key], [], times, false, start + 1000)).toEqual([]);
    });
    it('以前の分単位の通知記録を引き継ぎ、同じ時刻の別表現を再通知しない', () => {
        const first = collectProgramReminderNotices([reminder], [], [reminder.key], [], [5], false, start - 300_000);
        expect(first[0].id).toBe(`${reminder.key}:${reminder.program.start_time}:5`);
        expect(collectProgramReminderNotices([reminder], first, [reminder.key], [], [300 / 60, 5], false, start - 300_000)).toEqual([]);
    });
    it('指定した時刻に1度だけ通知し、リロード後の記録でも重複しない', () => {
        const current = start - 180 * 60_000;
        const first = collectProgramReminderNotices([reminder], [], [reminder.key], [], [1440, 180, 5], false, current);
        expect(first.map(notice => notice.message)).toEqual(['3時間前']);
        expect(collectProgramReminderNotices([reminder], first, [reminder.key], [], [1440, 180, 5], false, current + 15000)).toEqual([]);
    });
    it('遅れて見つかった番組の過去の時刻をまとめて通知しない', () => {
        const late = { ...reminder, created_at: start - 60_000 };
        const notices = collectProgramReminderNotices([late], [], [late.key], [], [10080, 1440, 180, 5], true, start - 60_000);
        expect(notices.map(notice => notice.message)).toEqual(['好みに合う放送予定が見つかりました']);
    });
    it('再開時に2分以上経過した通知、除外済み・終了済み・未確認の番組を通知しない', () => {
        expect(collectProgramReminderNotices([reminder], [], [reminder.key], [], [5], false, start - 60_000)).toEqual([]);
        expect(collectProgramReminderNotices([{ ...reminder, status: 'Dismissed' }], [], [reminder.key], [], [5], true, start - 300_000)).toEqual([]);
        expect(collectProgramReminderNotices([reminder], [], [], [], [5], true, start - 300_000)).toEqual([]);
        expect(collectProgramReminderNotices([reminder], [], [reminder.key], [], [0], true, start + 3600_000)).toEqual([]);
    });
    it('予定変更を通知し、変更後の放送時刻を使う', () => {
        const discovery = collectProgramReminderNotices([reminder], [], [reminder.key], [], [], true, start - 400_000);
        const delayed = { ...reminder, program: { ...reminder.program, start_time: dayjs(start).add(30, 'minute').format() } };
        const notices = collectProgramReminderNotices([delayed], discovery, [delayed.key], [delayed.key], [5], true, start - 300_000);
        expect(notices.map(notice => notice.message)).toEqual(['放送予定の時刻が変更されました']);
        expect(notices[0].start_time).toBe(delayed.program.start_time);
    });
});

describe('番組表の通信と設定の競合', () => {
    beforeEach(() => {
        localStorage.clear();
        setActivePinia(createPinia());
        vi.useFakeTimers();
        vi.setSystemTime(start - 3600_000);
    });
    afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

    it('既存の重複条件と参照を整理しても、番組・通知状態・お知らせ・通知設定を保持する', () => {
        const settings = useSettingsStore();
        settings.settings.program_recommendation_rules = [structuredClone(rule), { ...rule, id: 'duplicate' }];
        settings.settings.program_reminders = [{ ...reminder, keyword_matches: [
            { id: rule.id, name: rule.name }, { id: 'duplicate', name: rule.name },
        ] }];
        const notices = collectProgramReminderNotices([reminder], [], [reminder.key], [], [60], true, start - 3600_000);
        settings.settings.program_reminder_notices = notices;
        settings.settings.program_recommendation_notify_by_default = false;
        settings.settings.program_reminder_lead_times = [1440, 5, 0];
        const store = useProgramRemindersStore();
        expect(settings.settings.program_recommendation_rules).toEqual([rule]);
        expect(store.scheduledReminders).toHaveLength(1);
        expect(store.reminders[0]).toEqual({ ...reminder, keyword_matches: [{
            id: rule.id, name: rule.name, condition_key: getProgramRecommendationRuleKey(rule),
        }] });
        expect(settings.settings.program_reminder_notices).toEqual(notices);
        expect(settings.settings.program_reminder_lead_times).toEqual([1440, 5, 0]);
        expect(settings.settings.program_recommendation_notify_by_default).toBe(false);
    });

    it('キーワードの編集・無効化・削除は候補だけに反映し、通知予定とお知らせを保持する', () => {
        const settings = useSettingsStore();
        const other = { ...reminder, key: 'other', status: 'Dismissed' as const, program: {
            ...reminder.program, title: '歴史ドラマ', description: '', detail: {},
        } };
        const manual = { ...reminder, key: 'manual', source: 'Manual' as const, program: {
            ...reminder.program, title: '天気予報', description: '', detail: {},
        } };
        settings.settings.program_reminders = [structuredClone(reminder), other, manual];
        settings.settings.program_recommendation_rules = [structuredClone(rule)];
        const notices = collectProgramReminderNotices([reminder], [], [reminder.key], [], [60], true, start - 3600_000);
        settings.settings.program_reminder_notices = notices;
        const store = useProgramRemindersStore();
        expect(store.candidateReminders.map(item => item.key)).toEqual([reminder.key]);
        store.updateRecommendationRules([{ ...rule, name: 'ドラマ', keyword: '歴史' }]);
        expect(store.candidateReminders.map(item => item.key)).toEqual(['other']);
        expect(store.scheduledReminders.map(item => item.key)).toEqual([reminder.key, 'manual']);
        store.updateRecommendationRules([{ ...rule, name: 'ドラマ', keyword: '歴史', is_enabled: false }]);
        expect(store.candidateReminders).toEqual([]);
        store.updateRecommendationRules([]);
        expect(store.candidateReminders).toEqual([]);
        expect(store.reminders.map(item => item.status)).toEqual(['Scheduled', 'Dismissed', 'Scheduled']);
        expect(store.scheduledReminders.map(item => item.key)).toEqual([reminder.key, 'manual']);
        expect(settings.settings.program_reminder_notices).toEqual(notices);
        expect(store.reminders[0].keyword_matches).toEqual([{
            id: rule.id, name: 'ドラマ', condition_key: getProgramRecommendationRuleKey({ ...rule, name: 'ドラマ', keyword: '歴史' }),
        }]);
    });
    it('キーワードを削除した後の再取得でも、登録済みの通知と停止済みの番組を保持する', async () => {
        const settings = useSettingsStore();
        const muted = { ...reminder, key: 'muted', status: 'Dismissed' as const, program: {
            ...reminder.program, id: 'muted-program',
        } };
        settings.settings.program_reminders = [structuredClone(reminder), muted];
        settings.settings.program_recommendation_rules = [structuredClone(rule)];
        settings.settings.program_recommendation_enabled = true;
        const store = useProgramRemindersStore();
        store.updateRecommendationRules([]);
        vi.spyOn(Programs, 'fetchTimeTable').mockResolvedValue({
            channels: [{ channel: candidate.channel as ITimeTable['channels'][number]['channel'],
                programs: [reminder, muted].map(item => ({ ...item.program, reservation: null })), subchannels: null }],
            date_range: { earliest: candidate.program.start_time, latest: candidate.program.end_time },
        });
        await store.refresh(true);
        expect(store.candidateReminders).toEqual([]);
        expect(store.scheduledReminders.map(item => item.key)).toEqual([reminder.key]);
        expect(store.reminders.map(item => item.status)).toEqual(['Scheduled', 'Dismissed']);
        expect(store.reminders.every(item => item.keyword_matches?.[0].id === rule.id)).toBe(true);
        expect(store.verifiedKeys).toEqual([reminder.key, 'muted']);
    });
    it('通知を停止しても候補に残り、その場で通知を再開できる', () => {
        const settings = useSettingsStore();
        settings.settings.program_reminders = [{ ...reminder }];
        const store = useProgramRemindersStore();
        store.dismiss(reminder.key);
        expect(store.upcomingReminders).toHaveLength(1);
        expect(store.scheduledReminders).toHaveLength(0);
        store.restore(reminder.key);
        expect(store.upcomingReminders).toHaveLength(1);
        expect(store.scheduledReminders).toHaveLength(1);
    });
    it('登録済みの通知をまとめて停止しても、候補・履歴・条件と今後の通知設定を保持する', () => {
        const settings = useSettingsStore();
        const manual = { ...reminder, key: 'manual', source: 'Manual' as const };
        const muted = { ...reminder, key: 'muted', status: 'Dismissed' as const };
        const ended = { ...reminder, key: 'ended', program: {
            ...reminder.program, end_time: dayjs(start).subtract(2, 'hour').format(),
        } };
        settings.settings.program_reminders = [structuredClone(reminder), manual, muted, ended];
        settings.settings.program_recommendation_rules = [structuredClone(rule)];
        settings.settings.program_recommendation_enabled = true;
        settings.settings.program_recommendation_notify_by_default = true;
        settings.settings.program_reminder_notices = collectProgramReminderNotices(
            [reminder], [], [reminder.key], [], [60], true, start - 3600_000,
        );
        const store = useProgramRemindersStore();
        const before = JSON.parse(JSON.stringify(settings.settings)) as typeof settings.settings;

        expect(store.dismissAll()).toBe(2);
        expect(store.reminders.map(item => item.key)).toEqual([reminder.key, 'manual', 'muted', 'ended']);
        expect(store.upcomingReminders).toHaveLength(3);
        expect(store.scheduledReminders).toHaveLength(0);
        expect(store.reminders.map(item => item.status)).toEqual(['Dismissed', 'Dismissed', 'Dismissed', 'Scheduled']);
        expect(store.reminders.map(({ status: _status, ...item }) => item)).toEqual(
            before.program_reminders.map(({ status: _status, ...item }) => item),
        );
        const { program_reminders: _reminders, ...remainingSettings } = settings.settings;
        const { program_reminders: _beforeReminders, ...beforeSettings } = before;
        expect(remainingSettings).toEqual(beforeSettings);
        expect(store.dismissAll()).toBe(0);

        store.restore('manual');
        expect(store.scheduledReminders.map(item => item.key)).toEqual(['manual']);
        expect(store.upcomingReminders).toHaveLength(3);
    });
    it('取得失敗を0件と区別し、保存した予定を保持する', async () => {
        const settings = useSettingsStore();
        settings.settings.program_reminders = [{ ...reminder }];
        vi.spyOn(Programs, 'fetchTimeTable').mockResolvedValue(null);
        const store = useProgramRemindersStore();
        await store.refresh(true);
        expect(store.error).toContain('更新できません');
        expect(settings.settings.program_reminders).toHaveLength(1);
        store.checkNotices();
        expect(settings.settings.program_reminder_notices).toEqual([]);
    });
    it('通信中に変更した除外状態を、遅れて届いた応答で上書きしない', async () => {
        const settings = useSettingsStore();
        settings.settings.program_reminders = [{ ...reminder }];
        let resolveFetch: (value: ITimeTable) => void = () => {};
        vi.spyOn(Programs, 'fetchTimeTable').mockReturnValue(new Promise(resolve => { resolveFetch = resolve; }));
        const store = useProgramRemindersStore();
        const request = store.refresh(true);
        store.dismiss(reminder.key);
        resolveFetch({ channels: [{ channel: candidate.channel as ITimeTable['channels'][number]['channel'],
            programs: [{ ...candidate.program, reservation: null }], subchannels: null }],
        date_range: { earliest: candidate.program.start_time, latest: candidate.program.end_time } });
        await request;
        expect(settings.settings.program_reminders[0].status).toBe('Dismissed');
    });
});
