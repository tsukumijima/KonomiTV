<template>
    <div class="reminder-times">
        <div v-if="!isCustomMode" class="reminder-times__presets">
            <v-checkbox v-for="option in timeOptions" :key="option.value"
                :model-value="normalizedTimes.includes(option.value)"
                :label="option.title" color="secondary" density="compact" hide-details
                @update:model-value="togglePreset(option.value, $event)" />
        </div>
        <v-checkbox v-model="isCustomMode" label="カスタム" color="secondary" density="compact" hide-details
            :disabled="isDirty || hasExternalChange" />
        <template v-if="isCustomMode">
            <p class="reminder-times__help">放送開始からどれだけ前に知らせるかを、秒単位で追加できます。0 は放送開始時です。</p>
            <div v-for="(row, index) in rows" :key="row.id" class="reminder-times__row">
                <v-text-field v-model="row.value" type="number" min="0" step="1" variant="outlined" density="compact"
                    :label="`通知時刻 ${index + 1}`" :error-messages="rowErrors[index]" hide-details="auto" />
                <v-select v-model="row.unit" :items="PROGRAM_REMINDER_TIME_UNITS" label="単位"
                    variant="outlined" density="compact" hide-details />
                <v-btn icon variant="text" size="36" :aria-label="`通知時刻 ${index + 1} を削除`"
                    @click="rows.splice(index, 1)">
                    <Icon icon="fluent:delete-20-regular" width="20px" />
                </v-btn>
            </div>
            <p v-if="rows.length === 0" class="reminder-times__help mt-3">放送前のお知らせ時刻はありません。番組を見つけたときのお知らせは別の設定です。</p>
            <v-btn variant="tonal" color="secondary" class="mt-3" @click="addTime">
                <Icon icon="fluent:add-20-regular" width="18px" class="mr-1" />通知時刻を追加
            </v-btn>
            <p class="reminder-times__help mt-3">
                行数の上限はありません。同じ時刻は保存時に1件にまとめます。設定した時刻は、通知オンのすべての番組に適用します。
            </p>
            <v-alert v-if="hasExternalChange" type="info" variant="tonal" class="mt-3">
                別の操作で通知時刻が更新されました。「最新の設定を読み直す」で確認してから編集してください。
            </v-alert>
            <div class="reminder-times__actions">
                <v-btn variant="flat" color="secondary" :disabled="!isDirty || !isValid || hasExternalChange" @click="saveTimes">
                    <Icon icon="fluent:save-20-regular" width="18px" class="mr-1" />通知時刻を保存
                </v-btn>
                <v-btn variant="text" :disabled="!isDirty && !hasExternalChange" @click="loadTimes(props.modelValue)">
                    <Icon icon="fluent:arrow-undo-20-regular" width="18px" class="mr-1" />
                    {{hasExternalChange ? '最新の設定を読み直す' : '変更を戻す'}}
                </v-btn>
                <span class="reminder-times__help" role="status">{{isDirty ? '未保存の変更があります' : `保存済み：${normalizedTimes.length} 回`}}</span>
            </div>
            <p v-if="isDirty || hasExternalChange" class="reminder-times__help mt-2">
                選択式に戻すには、変更を保存するか元に戻してください。
            </p>
        </template>
    </div>
</template>
<script lang="ts" setup>

import { computed, ref, watch } from 'vue';

import { PROGRAM_REMINDER_LEAD_TIMES, PROGRAM_REMINDER_TIME_UNITS, type ProgramReminderTimeUnit } from '@/services/ProgramReminders';
import { formatProgramReminderLeadTime, getProgramReminderLeadTimeInput, normalizeProgramReminderLeadTimes } from '@/utils/ProgramReminderUtils';

const props = defineProps<{ modelValue: number[] }>();
const emit = defineEmits<{ 'update:modelValue': [value: number[]]; 'dirty-change': [value: boolean] }>();

// 通常は選択式を表示し、カスタムを開いたときも同じ保存済み時刻を編集する。
const isCustomMode = ref(false);
// 入力中は保存済みの通知予定を維持し、保存ボタンで有効な時刻だけを確定する。
const rows = ref<{ id: number; value: string; unit: ProgramReminderTimeUnit }[]>([]);
let nextID = 0;
const loadedRows = ref('[]');
const loadedTimes = ref('');
const hasExternalChange = ref(false);
const serializedRows = computed(() => JSON.stringify(rows.value.map(({ value, unit }) => ({ value, unit }))));
const isDirty = computed(() => serializedRows.value !== loadedRows.value);
// 数値と単位の両方からエラーを計算し、表示と保存判定に同じ結果を使う。
const rowErrors = computed(() => rows.value.map(row => {
    const result = validateValue(row.value, row.unit);
    return result === true ? [] : [result];
}));
const isValid = computed(() => rowErrors.value.every(errors => errors.length === 0));
const normalizedTimes = computed(() => normalizeProgramReminderLeadTimes(props.modelValue));

// 保存済みのカスタム時刻も選択肢に含め、選択式で通知予定を確認・解除できるようにする。
const timeOptions = computed(() => {
    const options = [...PROGRAM_REMINDER_LEAD_TIMES];
    for (const minutes of normalizedTimes.value) {
        if (!options.some(option => option.value === minutes)) {
            options.push({ title: `${formatProgramReminderLeadTime(minutes)}（カスタム）`, value: minutes });
        }
    }
    return options;
});

/** 選択した時刻だけを切り替え、ほかの保存済み時刻を引き継ぐ。 */
function togglePreset(minutes: number, enabled: boolean | null): void {
    const times = normalizedTimes.value.filter(value => value !== minutes);
    if (enabled) {
        times.push(minutes);
    }
    emit('update:modelValue', normalizeProgramReminderLeadTimes(times));
}

/** 入力できる範囲を、整数秒として正確に扱える値にそろえる。 */
function validateValue(value: unknown, unit: ProgramReminderTimeUnit): true | string {
    if (value === null || value === undefined || String(value).trim() === '') {
        return '数値を入力してください';
    }
    const amount = Number(value);
    const secondsPerUnit = PROGRAM_REMINDER_TIME_UNITS.find(item => item.value === unit)!.seconds;
    if (!Number.isInteger(amount) || amount < 0) {
        return '0 以上の整数を入力してください';
    }
    if (!Number.isSafeInteger(amount * secondsPerUnit * 1000)) {
        return '扱える数値の範囲を超えています';
    }
    return true;
}

/** 保存済みの時刻を、日・時間・分・秒の入力行に展開する。 */
function loadTimes(times: number[]): void {
    const normalized = normalizeProgramReminderLeadTimes(times);
    rows.value = normalized.map(minutes => {
        const input = getProgramReminderLeadTimeInput(minutes);
        return { id: nextID++, value: String(input.value), unit: input.unit };
    });
    loadedTimes.value = JSON.stringify(normalized);
    loadedRows.value = serializedRows.value;
    hasExternalChange.value = false;
}

function addTime(): void {
    rows.value.push({ id: nextID++, value: '1', unit: 'Second' });
}

function saveTimes(): void {
    if (!isValid.value || hasExternalChange.value) return;
    const times = rows.value.map(row => {
        const secondsPerUnit = PROGRAM_REMINDER_TIME_UNITS.find(item => item.value === row.unit)!.seconds;
        return Number(row.value) * secondsPerUnit / 60;
    });
    const normalized = normalizeProgramReminderLeadTimes(times);
    emit('update:modelValue', normalized);
    loadTimes(normalized);
}

// 同期などで設定が更新されたときは、編集中の入力を保持したまま再読み込みを案内する。
watch(() => JSON.stringify(normalizedTimes.value), current => {
    if (current === loadedTimes.value) {
        hasExternalChange.value = false;
    } else if (isDirty.value) {
        hasExternalChange.value = true;
    } else {
        loadTimes(props.modelValue);
    }
}, { immediate: true });

// タブやページの移動時にも、親画面が未保存の入力を保護できるよう伝える。
watch(isDirty, dirty => emit('dirty-change', dirty), { flush: 'sync' });

</script>
<style lang="scss" scoped>

.reminder-times {
    &__presets {
        display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
        @include smartphone-vertical { grid-template-columns: repeat(2, 1fr); }
    }
    &__help { color: rgb(var(--v-theme-text-darken-1)); font-size: 13px; line-height: 1.8; }
    &__row {
        display: grid; grid-template-columns: minmax(0, 1fr) 130px 36px; gap: 10px;
        align-items: start; max-width: 510px; margin-top: 16px;
        @include smartphone-vertical { grid-template-columns: minmax(0, 1fr) 108px 36px; gap: 6px; }
    }
    &__actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 16px; }
}

</style>
