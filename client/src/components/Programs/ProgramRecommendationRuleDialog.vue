<template>
    <v-dialog :model-value="modelValue" max-width="580" @update:model-value="$emit('update:modelValue', $event)">
        <v-card>
            <v-card-title class="d-flex justify-center pt-6 font-weight-bold">
                {{rule ? 'キーワードを編集' : 'キーワードを追加'}}
            </v-card-title>
            <v-card-text class="pt-2 pb-0">
                <p class="mb-5 text-text-darken-1">好きな番組名や出演者、気になる話題から、放送予定を探します。</p>
                <v-text-field v-model="draft.name" label="表示名（任意）" variant="outlined"
                    placeholder="例：好きなお笑い番組" maxlength="80" />
                <v-text-field v-model="draft.keyword" label="番組名・出演者・キーワード" variant="outlined"
                    placeholder="例：お笑い 特番" maxlength="200"
                    hint="空白で区切ると、すべての語を含む番組が対象になります。" persistent-hint />
                <v-select v-model="draft.genre" :items="genres" label="ジャンル（任意）" variant="outlined"
                    clearable class="mt-4" hint="キーワードを空にして、ジャンルだけでも探せます。" persistent-hint />
                <v-text-field v-model="draft.exclude_keyword" label="含めないキーワード（任意）" variant="outlined"
                    class="mt-4" maxlength="200" hint="空白で区切った語のどれかを含む番組を除外します。" persistent-hint />
                <v-checkbox v-model="draft.is_title_only" label="キーワードは番組名だけから探す"
                    color="secondary" density="compact" hide-details class="mt-3" />
                <v-checkbox v-model="draft.is_free_only" label="無料放送だけを対象にする"
                    color="secondary" density="compact" hide-details />
                <p v-if="validationError" class="text-error mt-2" role="alert">{{validationError}}</p>
            </v-card-text>
            <v-card-actions class="pt-4 px-6 pb-6">
                <v-spacer />
                <v-btn color="text" variant="text" @click="$emit('update:modelValue', false)">
                    <Icon icon="fluent:dismiss-16-filled" width="18px" height="18px" /><span class="ml-1">キャンセル</span>
                </v-btn>
                <v-btn color="secondary" variant="flat" height="40" class="px-3" @click="save">
                    <Icon icon="fluent:save-16-regular" width="18px" height="18px" /><span class="ml-1">キーワードを保存</span>
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>
<script lang="ts" setup>

import { nanoid } from 'nanoid';
import { ref, watch } from 'vue';

import type { IProgramRecommendationRule } from '@/services/ProgramReminders';

import { ILocalClientSettingsDefault } from '@/stores/SettingsStore';
import { getProgramRecommendationRuleKey } from '@/utils/ProgramReminderUtils';

const props = defineProps<{ modelValue: boolean; rule: IProgramRecommendationRule | null; rules: IProgramRecommendationRule[] }>();
const emit = defineEmits<{
    (event: 'update:modelValue', value: boolean): void;
    (event: 'save', rule: IProgramRecommendationRule): void;
}>();
const genres = Object.keys(ILocalClientSettingsDefault.timetable_genre_colors);
const draft = ref<IProgramRecommendationRule>({
    id: '', name: '', keyword: '', exclude_keyword: '', genre: null,
    is_title_only: false, is_free_only: true, is_enabled: true,
});
const validationError = ref('');

watch(() => props.modelValue, open => {
    if (open) {
        draft.value = props.rule ? { ...props.rule } : {
            id: nanoid(), name: '', keyword: '', exclude_keyword: '', genre: null,
            is_title_only: false, is_free_only: true, is_enabled: true,
        };
        validationError.value = '';
    }
});

function save(): void {
    if (draft.value.keyword.trim() === '' && draft.value.genre === null) {
        validationError.value = 'キーワードかジャンルを指定してください。';
        return;
    }
    const rule = { ...draft.value };
    rule.keyword = rule.keyword.trim();
    rule.exclude_keyword = rule.exclude_keyword.trim();
    rule.name = rule.name.trim() || rule.keyword || rule.genre || '';
    if (props.rules.some(existing => existing.id !== rule.id &&
        getProgramRecommendationRuleKey(existing) === getProgramRecommendationRuleKey(rule))) {
        validationError.value = '同じ条件がすでに追加されております。';
        return;
    }
    emit('save', rule);
    emit('update:modelValue', false);
}

</script>
