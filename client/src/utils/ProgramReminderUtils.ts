import type {
    IProgramRecommendationRule,
    IProgramReminder,
    IProgramReminderCandidate,
    IProgramReminderGroup,
    IProgramReminderKeyword,
    IProgramReminderNotice,
    ProgramReminderTimeUnit,
} from '@/services/ProgramReminders';
import type { IProgram } from '@/services/Programs';

import { PROGRAM_REMINDER_TIME_UNITS } from '@/services/ProgramReminders';
import { dayjs } from '@/utils';


/** 番組表の文字幅・英字の大小・空白の差を吸収して検索する。 */
export function normalizeReminderText(text: string): string {
    return text.normalize('NFKC').toLocaleLowerCase('ja-JP').replace(/\s+/g, ' ').trim();
}

/** EIT のイベント ID は再利用されるため、初回に見つけた開始時刻を識別子に含める。 */
export function getProgramReminderKey(program: IProgram): string {
    return `${program.id}@${dayjs(program.start_time).valueOf()}`;
}

/** 時刻変更後は、新しい開始時刻に対して視聴の予告を行う。 */
export function getProgramAutoSwitchID(reminder: IProgramReminder): string {
    return `${reminder.key}:AutoSwitch:${reminder.program.start_time}`;
}

/**
 * これから10秒以内に始まる、最新の番組表で確認できた通知オンの放送を返す。
 * 開始済みの番組は手動視聴に任せ、再開時の突然の切り替えを防ぐ。
 */
export function getProgramAutoSwitchCandidates(
    reminders: IProgramReminder[], verifiedKeys: string[], handledIDs: string[], now: number,
): IProgramReminder[] {
    const verified = new Set(verifiedKeys);
    const handled = new Set(handledIDs);
    const candidates = reminders.filter(reminder => {
        const startTime = dayjs(reminder.program.start_time).valueOf();
        return reminder.status === 'Scheduled' && verified.has(reminder.key) &&
            startTime >= now && startTime <= now + 10_000 &&
            dayjs(reminder.program.end_time).valueOf() > now;
    }).sort((a, b) => dayjs(a.program.start_time).valueOf() - dayjs(b.program.start_time).valueOf());
    const first = candidates[0];
    if (first === undefined) {
        return [];
    }
    // 同時刻の候補はひとまとめに扱い、一度取り消した組み合わせを再度予告することを防ぐ。
    const sameStart = candidates.filter(candidate => candidate.program.start_time === first.program.start_time);
    if (sameStart.some(candidate => handled.has(getProgramAutoSwitchID(candidate)))) {
        return [];
    }
    return sameStart;
}

/**
 * 時刻変更は同じイベント ID と番組名で追跡する。
 * 12時間以上離れた放送は ID が再利用された別の放送回として扱う。
 */
export function isSameReminderBroadcast(first: IProgram, second: IProgram): boolean {
    if (first.id !== second.id) {
        return false;
    }
    if (dayjs(first.start_time).valueOf() === dayjs(second.start_time).valueOf()) {
        return true;
    }
    const timeDifference = Math.abs(dayjs(first.start_time).diff(dayjs(second.start_time), 'minute'));
    return timeDifference < 12 * 60 && normalizeReminderText(first.title) === normalizeReminderText(second.title);
}

/** 実際の番組情報に一致した条件だけを、推薦理由として返す。 */
export function getProgramRecommendationReasons(program: IProgram, rules: IProgramRecommendationRule[]): string[] {
    const reasons: string[] = [];
    const title = normalizeReminderText(program.title);
    const fullText = normalizeReminderText([program.title, program.description, ...Object.values(program.detail)].join(' '));

    for (const rule of rules) {
        const words = normalizeReminderText(rule.keyword).split(' ').filter(Boolean);
        const excludedWords = normalizeReminderText(rule.exclude_keyword).split(' ').filter(Boolean);
        // 空の条件は全番組に一致するため、番組名・出演者・ジャンルのいずれかを必須にする。
        if (!rule.is_enabled || (words.length === 0 && rule.genre === null)) {
            continue;
        }
        const text = rule.is_title_only ? title : fullText;
        if (!words.every(word => text.includes(word))) {
            continue;
        }
        if (excludedWords.some(word => fullText.includes(word))) {
            continue;
        }
        if (rule.genre !== null && !program.genres.some(genre => genre.major === rule.genre)) {
            continue;
        }
        if (rule.is_free_only && !program.is_free) {
            continue;
        }
        const matchedItems = [...words.map(word => `「${word}」`), ...(rule.genre ? [rule.genre] : [])];
        reasons.push(`${rule.name}：${matchedItems.join('・')}に一致`);
    }
    return reasons;
}

/**
 * 表示名とすべての検索条件を、文字列もそのまま比較できるキーにする。
 * ID と有効・停止は管理状態として扱い、検索条件の同一性は切り替え後も維持する。
 */
export function getProgramRecommendationRuleKey(rule: IProgramRecommendationRule): string {
    return JSON.stringify([
        rule.name, rule.keyword, rule.exclude_keyword, rule.genre, rule.is_title_only, rule.is_free_only,
    ]);
}

/** 完全一致する既存の条件を登録順にまとめ、有効だった検索を引き継ぐ。 */
export function deduplicateProgramRecommendationRules(rules: IProgramRecommendationRule[]): IProgramRecommendationRule[] {
    const unique = new Map<string, IProgramRecommendationRule>();
    for (const rule of rules) {
        const key = getProgramRecommendationRuleKey(rule);
        const existing = unique.get(key);
        if (existing === undefined) {
            unique.set(key, rule);
        } else if (!existing.is_enabled && rule.is_enabled) {
            unique.set(key, { ...existing, is_enabled: true });
        }
    }
    return [...unique.values()];
}

/**
 * 現在の登録条件で候補を分類する。停止中の条件も、保存済み候補の整理に使用する。
 * 条件の名前や推薦理由の文字列ではなく、各条件の照合結果と ID でグループを作る。
 */
export function groupProgramRemindersByRule(
    reminders: IProgramReminder[], rules: IProgramRecommendationRule[],
): IProgramReminderGroup[] {
    const sorted = [...reminders].sort((a, b) =>
        dayjs(a.program.start_time).valueOf() - dayjs(b.program.start_time).valueOf() || a.key.localeCompare(b.key));
    const matched = new Set<string>();
    const groups = deduplicateProgramRecommendationRules(rules).map(rule => {
        const matching = sorted.filter(reminder =>
            getProgramRecommendationReasons(reminder.program, [{ ...rule, is_enabled: true }]).length > 0);
        for (const reminder of matching) {
            matched.add(reminder.key);
        }
        return { key: `Rule:${rule.id}`, name: rule.name, reminders: matching };
    });
    groups.push({
        key: 'Unmatched', name: '現在の条件に一致しない番組',
        reminders: sorted.filter(reminder => !matched.has(reminder.key)),
    });
    return groups;
}

/**
 * 通知予定の検索に使うキーワードを、名前と検索条件を含めて保持する。
 * 削除・再追加によって ID が変わった場合も、条件の完全一致でまとめる。
 * 検索条件を保持していない旧データは名前を引き継ぎ、元の ID ごとに保持する。
 */
export function getProgramReminderKeywords(
    reminder: IProgramReminder, rules: IProgramRecommendationRule[],
): IProgramReminderKeyword[] {
    const currentMatches = rules.filter(rule =>
        getProgramRecommendationReasons(reminder.program, [{ ...rule, is_enabled: true }]).length > 0);
    const references: IProgramReminderKeyword[] = [];
    const currentByID = new Map(rules.map(rule => [rule.id, rule]));
    const currentByCondition = new Map(deduplicateProgramRecommendationRules(rules)
        .map(rule => [getProgramRecommendationRuleKey(rule), rule]));
    if (reminder.keyword_matches !== undefined) {
        for (const keyword of reminder.keyword_matches) {
            references.push({ ...keyword });
        }
    } else if (reminder.source === 'Recommended') {
        for (const reason of reminder.reasons) {
            const separator = reason.lastIndexOf('：');
            if (separator < 1 || !reason.endsWith('に一致')) continue;
            const name = reason.slice(0, separator);
            // 推薦理由には除外語や対象範囲が含まれないため、旧条件として保存する。
            references.push({ id: `Legacy:${name}`, name });
        }
    }
    for (const rule of currentMatches) {
        references.push({ id: rule.id, name: rule.name, condition_key: getProgramRecommendationRuleKey(rule) });
    }
    const keywords = new Map<string, IProgramReminderKeyword>();
    for (const reference of references) {
        let keyword = reference;
        // 同じ ID の編集は現在の名前・条件へ更新し、再追加は保存した条件と厳密に照合する。
        const current = currentByID.get(keyword.id);
        if (current !== undefined) {
            keyword = { id: current.id, name: current.name, condition_key: getProgramRecommendationRuleKey(current) };
        }
        const canonical = currentByCondition.get(keyword.condition_key ?? '');
        if (canonical !== undefined) {
            keyword = { ...keyword, id: canonical.id, name: canonical.name };
        }
        const key = keyword.condition_key === undefined ? `ID:${keyword.id}` : `Condition:${keyword.condition_key}`;
        if (!keywords.has(key)) keywords.set(key, keyword);
    }
    return [...keywords.values()];
}

/** 登録済みの通知は、現在の一致条件に関係なく、保存したキーワードで分類する。 */
export function groupScheduledProgramRemindersByKeyword(
    reminders: IProgramReminder[], rules: IProgramRecommendationRule[],
): IProgramReminderGroup[] {
    const keywordGroups = new Map<string, IProgramReminderGroup>(deduplicateProgramRecommendationRules(rules).map(rule =>
        [`Condition:${getProgramRecommendationRuleKey(rule)}`, {
            key: `Condition:${getProgramRecommendationRuleKey(rule)}`, name: rule.name, reminders: [],
        }]));
    const unmatched: IProgramReminder[] = [];
    const sorted = [...reminders].sort((a, b) =>
        dayjs(a.program.start_time).valueOf() - dayjs(b.program.start_time).valueOf() || a.key.localeCompare(b.key));
    for (const reminder of sorted) {
        const keywords = getProgramReminderKeywords(reminder, rules);
        if (keywords.length === 0) unmatched.push(reminder);
        for (const keyword of keywords) {
            const key = keyword.condition_key === undefined ? `ID:${keyword.id}` : `Condition:${keyword.condition_key}`;
            if (!keywordGroups.has(key)) {
                keywordGroups.set(key, { key, name: `${keyword.name}＊`, reminders: [] });
            }
            const group = keywordGroups.get(key)!;
            if (!group.reminders.some(item => item.key === reminder.key)) group.reminders.push(reminder);
        }
    }
    return [...keywordGroups.values(), { key: 'Unmatched', name: 'キーワード未指定', reminders: unmatched }];
}

/** 分単位の保存値を整数秒に丸め、同じ通知時刻をまとめて放送より遠い順にそろえる。 */
export function normalizeProgramReminderLeadTimes(leadTimes: number[]): number[] {
    const seconds = new Set<number>();
    for (const minutes of leadTimes) {
        const value = Math.round(minutes * 60);
        if (Number.isFinite(minutes) && minutes >= 0 && Number.isSafeInteger(value * 1000)) {
            seconds.add(value);
        }
    }
    return [...seconds].sort((a, b) => b - a).map(value => value / 60);
}

/** 保存済みの通知時刻を、整数で入力できる最も大きい単位に換算する。 */
export function getProgramReminderLeadTimeInput(minutes: number): { value: number; unit: ProgramReminderTimeUnit } {
    const seconds = Math.round(minutes * 60);
    const unit = PROGRAM_REMINDER_TIME_UNITS.find(item => seconds > 0 && seconds % item.seconds === 0) ??
        PROGRAM_REMINDER_TIME_UNITS[3];
    return { value: seconds / unit.seconds, unit: unit.value };
}

/** 任意の通知時刻を、お知らせと設定画面で共通の文言にする。 */
export function formatProgramReminderLeadTime(minutes: number): string {
    if (Math.round(minutes * 60) === 0) {
        return '放送開始時';
    }
    const input = getProgramReminderLeadTimeInput(minutes);
    const unit = PROGRAM_REMINDER_TIME_UNITS.find(item => item.value === input.unit)!;
    return `${input.value}${unit.title}`;
}

/**
 * 最新の番組表と保存済みの放送予定を照合する。
 * 取得失敗時は呼び出し側で保存済みの予定を維持し、成功した取得結果だけを渡す。
 */
export function reconcileProgramReminders(
    reminders: IProgramReminder[], candidates: IProgramReminderCandidate[],
    rules: IProgramRecommendationRule[], automaticEnabled: boolean, now: number,
    notifyByDefault = true,
): { reminders: IProgramReminder[]; verifiedKeys: string[]; changedKeys: string[]; matchingCount: number } {
    const retained = reminders.filter(reminder => dayjs(reminder.program.end_time).valueOf() > now - 7 * 86400_000)
        .map(reminder => ({ ...reminder, keyword_matches: getProgramReminderKeywords(reminder, rules) }));
    const result: IProgramReminder[] = [];
    const verifiedKeys: string[] = [];
    const changedKeys: string[] = [];
    const remaining = new Set(retained);
    let matchingCount = 0;

    // 放送が近い順に選び、同じ API 応答に含まれる重複もイベント単位でまとめる。
    const uniqueCandidates = new Map(candidates.map(candidate => [getProgramReminderKey(candidate.program), candidate]));
    const sortedCandidates = [...uniqueCandidates.values()].sort((a, b) =>
        dayjs(a.program.start_time).valueOf() - dayjs(b.program.start_time).valueOf());
    for (const candidate of sortedCandidates) {
        const { program, channel } = candidate;
        if (dayjs(program.end_time).valueOf() <= now) {
            continue;
        }
        const reasons = getProgramRecommendationReasons(program, rules);
        if (reasons.length > 0 && dayjs(program.start_time).valueOf() > now) {
            matchingCount += 1;
        }
        const existing = retained.find(reminder => remaining.has(reminder) && isSameReminderBroadcast(reminder.program, program));
        if (existing !== undefined) {
            remaining.delete(existing);
            if (existing.program.start_time !== program.start_time || existing.program.end_time !== program.end_time) {
                changedKeys.push(existing.key);
            }
            const updated = { ...existing, program, channel };
            result.push({ ...updated, keyword_matches: getProgramReminderKeywords(updated, rules) });
            verifiedKeys.push(existing.key);
            continue;
        }

        // 既存の候補の通知状態は上の分岐で保持し、初回追加だけ既定の通知設定を適用する。
        if (!automaticEnabled || reasons.length === 0 ||
            dayjs(program.start_time).valueOf() <= now) {
            continue;
        }
        const reminder: IProgramReminder = {
            key: getProgramReminderKey(program), program, channel, source: 'Recommended',
            status: notifyByDefault ? 'Scheduled' : 'Dismissed', reasons, created_at: now, keyword_matches: [],
        };
        reminder.keyword_matches = getProgramReminderKeywords(reminder, rules);
        result.push(reminder);
        verifiedKeys.push(reminder.key);
    }

    // 番組表から消えた予定も一覧に残し、未確認であることを画面に表示する。
    // お知らせには verifiedKeys にある、今回取得できた放送だけを使用する。
    result.push(...remaining);
    result.sort((a, b) => dayjs(a.program.start_time).valueOf() - dayjs(b.program.start_time).valueOf());
    return { reminders: result, verifiedKeys, changedKeys, matchingCount };
}

/**
 * 放送前のお知らせを生成する。端末を閉じていた間の古い時刻は飛ばす。
 * 同じ放送の発見通知は1度だけ、放送時刻が変わった後の通知は新しい時刻を基準にする。
 */
export function collectProgramReminderNotices(
    reminders: IProgramReminder[], previousNotices: IProgramReminderNotice[], verifiedKeys: string[],
    changedKeys: string[], leadTimes: number[], notifyOnDiscovery: boolean, now: number,
): IProgramReminderNotice[] {
    const notices: IProgramReminderNotice[] = [];
    const existingIDs = new Set(previousNotices.map(notice => notice.id));
    const verified = new Set(verifiedKeys);

    for (const reminder of reminders) {
        const program = reminder.program;
        if (reminder.status !== 'Scheduled' || !verified.has(reminder.key) || dayjs(program.end_time).valueOf() <= now) {
            continue;
        }
        const stages: {id: string; message: string}[] = [];
        if (notifyOnDiscovery && reminder.source === 'Recommended') {
            stages.push({ id: `${reminder.key}:Discovery`, message: '好みに合う放送予定が見つかりました' });
        }
        if (changedKeys.includes(reminder.key)) {
            stages.push({ id: `${reminder.key}:Changed:${program.start_time}:${program.end_time}`, message: '放送予定の時刻が変更されました' });
        }
        for (const minutes of normalizeProgramReminderLeadTimes(leadTimes)) {
            // 小数の分を整数秒へ換算してから計算し、1秒前などの丸め誤差をそろえる。
            const dueAt = dayjs(program.start_time).valueOf() - Math.round(minutes * 60) * 1000;
            // 初回発見前の時刻と、2分以上前に過ぎた時刻は通知対象外にする。
            if (dueAt < reminder.created_at || now < dueAt || now - dueAt > 120_000) {
                continue;
            }
            stages.push({ id: `${reminder.key}:${program.start_time}:${minutes}`, message: formatProgramReminderLeadTime(minutes) });
        }
        for (const stage of stages) {
            if (existingIDs.has(stage.id)) {
                continue;
            }
            existingIDs.add(stage.id);
            notices.push({
                id: stage.id, reminder_key: reminder.key, title: program.title,
                channel_name: reminder.channel.name, start_time: program.start_time, end_time: program.end_time,
                display_channel_id: reminder.channel.display_channel_id, message: stage.message,
                created_at: now, is_read: false,
            });
        }
    }
    return notices;
}
