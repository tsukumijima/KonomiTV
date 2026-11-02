<template>
    <div class="route-container">
        <HeaderBar v-model:search-query="searchQuery" @search="searchPrograms" />
        <main>
            <Navigation />
            <div class="reminders-wrapper">
                <SPHeaderBar v-model:search-query="searchQuery" @search="searchPrograms" />
                <div class="reminders-container">
                    <Breadcrumbs :crumbs="[
                        { name: 'ホーム', path: '/' },
                        { name: '見たい番組', path: '/reminders/', disabled: true },
                    ]" />
                    <div class="reminders-header">
                        <h1><Icon icon="fluent:alert-20-regular" width="26px" />見たい番組</h1>
                        <v-btn variant="tonal" :loading="reminderStore.isLoading" @click="reminderStore.refresh(true)">
                            <Icon icon="fluent:arrow-sync-20-regular" width="18px" class="mr-1" />更新
                        </v-btn>
                    </div>
                    <p class="reminders-intro">好みに合う番組を自動で見つけて、放送前にお知らせします。</p>
                    <p class="reminders-help">
                        お知らせは KonomiTV の画面を表示している間に届きます。録画は別途予約してください。
                    </p>
                    <v-alert v-if="reminderStore.error" type="warning" variant="tonal" class="mt-4">
                        {{reminderStore.error}}
                    </v-alert>
                    <v-alert v-if="settingsStore.local_save_error" type="error" variant="tonal" class="mt-4">
                        {{settingsStore.local_save_error}}
                    </v-alert>
                    <v-tabs v-model="activeView" color="secondary" class="reminders-tabs mt-4">
                        <v-tab value="Scheduled"><span>通知予定</span><span class="reminders-tab-count">（{{reminderStore.scheduledReminders.length}}）</span></v-tab>
                        <v-tab value="Candidates"><span>番組候補</span><span class="reminders-tab-count">（{{reminderStore.candidateReminders.length}}）</span></v-tab>
                        <v-tab value="Notices"><span>お知らせ</span><span v-if="reminderStore.unreadCount" class="reminders-tab-count ml-1">({{reminderStore.unreadCount}})</span></v-tab>
                        <v-tab value="Preferences">通知設定</v-tab>
                    </v-tabs>

                    <section v-if="activeView === 'Scheduled' || activeView === 'Candidates'" class="reminders-section">
                        <div class="reminders-toolbar">
                            <strong>{{visibleReminders.length}} 件を表示</strong>
                            <v-menu v-model="isFilterMenuOpen" location="bottom end" :close-on-content-click="false">
                                <template #activator="{ props: menuProps }">
                                    <v-btn variant="flat" color="background-lighten-1" v-bind="menuProps">
                                        <Icon icon="fluent:filter-20-regular" width="18px" class="mr-1" />並べ替えと絞り込み
                                        <span v-if="activeFilterCount" class="text-secondary ml-2">{{activeFilterCount}}</span>
                                    </v-btn>
                                </template>
                                <v-card class="reminders-filter-menu" color="background-lighten-1">
                                    <v-select v-model="sortOrder" label="並べ替え" :items="sortOptions"
                                        variant="outlined" density="compact" hide-details />
                                    <v-select v-model="selectedRuleKeys" :items="ruleOptions" label="キーワード（いずれかに一致）"
                                        variant="outlined" density="compact" multiple chips closable-chips hide-details
                                        placeholder="すべてのキーワード" class="mt-5" />
                                    <p v-if="activeView === 'Scheduled'" class="reminders-help mt-2">（＊）削除済みキーワード</p>
                                    <p v-if="activeView === 'Scheduled'" class="reminders-help mt-4">登録方法</p>
                                    <v-chip-group v-if="activeView === 'Scheduled'" v-model="sourceFilter" color="secondary" mandatory column>
                                        <v-chip value="All" filter>すべて</v-chip>
                                        <v-chip value="Recommended" filter>おすすめ</v-chip>
                                        <v-chip value="Manual" filter>自分で選んだ番組</v-chip>
                                    </v-chip-group>
                                    <p v-if="activeView === 'Candidates'" class="reminders-help mt-3">通知の状態</p>
                                    <v-chip-group v-if="activeView === 'Candidates'" v-model="notificationFilter" color="secondary" mandatory column>
                                        <v-chip value="All" filter>すべて（{{sourceReminders.length}}）</v-chip>
                                        <v-chip value="Scheduled" filter>通知設定済み（{{sourceReminders.filter(item => item.status === 'Scheduled').length}}）</v-chip>
                                        <v-chip value="Dismissed" filter>未設定（{{sourceReminders.filter(item => item.status === 'Dismissed').length}}）</v-chip>
                                    </v-chip-group>
                                    <div class="d-flex flex-wrap justify-end mt-3">
                                        <v-btn variant="text" :disabled="activeFilterCount === 0" @click="clearFilters">
                                            <Icon icon="fluent:filter-dismiss-20-regular" width="18px" class="mr-1" />絞り込みを解除
                                        </v-btn>
                                        <v-btn variant="text" @click="isFilterMenuOpen = false">
                                            <Icon icon="fluent:dismiss-16-filled" width="18px" class="mr-1" />閉じる
                                        </v-btn>
                                    </div>
                                </v-card>
                            </v-menu>
                            <v-btn variant="text" color="secondary" to="/tv/search">
                                <Icon icon="fluent:search-20-regular" width="18px" class="mr-1" />番組を探して追加
                            </v-btn>
                        </div>
                        <div class="reminders-filter-summary">
                            <span class="reminders-help">{{sortOptions.find(option => option.value === sortOrder)?.title}}</span>
                            <v-chip v-if="activeView === 'Scheduled' && sourceFilter !== 'All'" closable size="small" @click:close="sourceFilter = 'All'">
                                {{sourceFilter === 'Manual' ? '自分で選んだ番組' : 'おすすめ'}}
                            </v-chip>
                            <v-chip v-if="activeView === 'Candidates' && notificationFilter !== 'All'" closable size="small" @click:close="notificationFilter = 'All'">
                                {{notificationFilter === 'Scheduled' ? '通知設定済み' : '未設定'}}
                            </v-chip>
                            <v-chip v-for="key in selectedRuleKeys" :key="key" closable size="small"
                                @click:close="selectedRuleKeys = selectedRuleKeys.filter(item => item !== key)">
                                {{ruleGroups.find(group => group.key === key)?.name}}
                            </v-chip>
                        </div>
                        <p v-if="sortOrder === 'Rule'" class="reminders-help mb-4">各キーワード内は放送が近い順です。複数に該当する番組は、それぞれに表示します。通知は重複しません。</p>
                        <div v-if="reminderStore.isLoading && !reminderStore.hasLoaded && visibleReminders.length === 0" class="reminders-empty">
                            <v-progress-circular indeterminate color="secondary" class="mb-4" />
                            <p>放送予定を確認しています...</p>
                        </div>
                        <div v-else-if="visibleReminders.length === 0" class="reminders-empty">
                            <Icon icon="fluent:calendar-search-20-regular" width="52px" class="mb-4" />
                            <h2>{{emptyTitle}}</h2>
                            <p>{{emptyDescription}}</p>
                            <v-btn v-if="activeFilterCount > 0 && listReminders.length > 0"
                                variant="flat" color="secondary" class="mt-5" @click="clearFilters">
                                <Icon icon="fluent:filter-dismiss-20-regular" width="18px" class="mr-1" />絞り込みを解除
                            </v-btn>
                            <v-btn v-else-if="activeView === 'Scheduled'" variant="flat" color="secondary" class="mt-5" @click="activeView = 'Candidates'">
                                <Icon icon="fluent:calendar-search-20-regular" width="18px" class="mr-1" />番組候補から選ぶ
                            </v-btn>
                            <v-btn v-else variant="flat" color="secondary" class="mt-5" @click="activeView = 'Preferences'">
                                <Icon icon="fluent:options-20-regular" width="18px" class="mr-1" />キーワードを設定
                            </v-btn>
                        </div>
                        <section v-for="group in visibleGroups" :key="group.key" class="reminder-group">
                            <h2 v-if="sortOrder === 'Rule'" class="reminder-group__title">{{group.name}}<span>{{group.reminders.length}} 件</span></h2>
                            <article v-for="reminder in group.reminders" :key="reminder.key" class="reminder-card">
                                <div class="reminder-card__source">
                                    <Icon :icon="reminder.source === 'Recommended' ? 'fluent:sparkle-20-regular' : 'fluent:bookmark-20-regular'" width="16px" />
                                    {{reminder.source === 'Recommended' ? 'おすすめ' : '自分で選んだ番組'}}
                                    <span v-if="isOnAir(reminder.program.start_time, reminder.program.end_time)" class="text-secondary ml-2">放送中</span>
                                </div>
                                <h3 v-html="ProgramUtils.decorateProgramInfo(reminder.program, 'title')"></h3>
                                <div class="reminder-card__broadcast">
                                    <img :src="`${Utils.api_base_url}/channels/${reminder.channel.id}/logo`" alt="" />
                                    <span>{{reminder.channel.name}}<br>{{formatTime(reminder.program.start_time, reminder.program.end_time)}}</span>
                                </div>
                                <p class="reminder-card__description" v-html="ProgramUtils.decorateProgramInfo(reminder.program, 'description')"></p>
                                <div class="reminder-card__reasons">
                                    <div v-for="reason in activeView === 'Candidates' ? getProgramRecommendationReasons(reminder.program,
                                        settings.program_recommendation_rules) : reminder.reasons" :key="reason">{{reason}}</div>
                                </div>
                                <p v-if="!reminderStore.isLoading && !reminderStore.verifiedKeys.includes(reminder.key)" class="text-warning mt-3">
                                    最新の番組表で確認できていません。確認できるまでお知らせを保留します。
                                </p>
                                <div class="reminder-card__actions">
                                    <span class="reminders-help d-flex align-center">
                                        <Icon :icon="reminder.status === 'Scheduled' ? 'fluent:alert-on-20-regular' : 'fluent:alert-off-20-regular'"
                                            width="18px" class="mr-1" />
                                        {{reminder.status === 'Scheduled' ? '通知設定済み' : '通知未設定'}}
                                    </span>
                                    <v-btn variant="flat" color="secondary" :to="`/tv/watch/${reminder.channel.display_channel_id}`">
                                        <Icon icon="fluent:play-20-filled" width="18px" class="mr-1" />
                                        {{isOnAir(reminder.program.start_time, reminder.program.end_time) ? '今すぐ見る' : 'チャンネルを開く'}}
                                    </v-btn>
                                    <v-spacer />
                                    <v-btn v-if="reminder.status === 'Scheduled'" variant="text" @click="reminderStore.dismiss(reminder.key)">
                                        <Icon icon="fluent:alert-off-20-regular" width="18px" class="mr-1" />通知しない
                                    </v-btn>
                                    <v-btn v-else variant="tonal" color="secondary" @click="reminderStore.restore(reminder.key)">
                                        <Icon icon="fluent:alert-on-20-regular" width="18px" class="mr-1" />通知する
                                    </v-btn>
                                </div>
                            </article>
                        </section>
                    </section>

                    <section v-else-if="activeView === 'Notices'" class="reminders-section">
                        <div class="reminders-toolbar">
                            <p class="reminders-help">この端末のお知らせを、放送終了後7日間表示します。</p>
                            <v-btn variant="text" color="secondary" :disabled="reminderStore.unreadCount === 0" @click="reminderStore.markAllRead()">
                                <Icon icon="fluent:checkmark-20-regular" width="18px" class="mr-1" />すべて既読にする
                            </v-btn>
                        </div>
                        <div v-if="notices.length === 0" class="reminders-empty">
                            <Icon icon="fluent:alert-20-regular" width="52px" class="mb-4" />
                            <h2>お知らせはまだありません</h2>
                            <p>番組を見つけたときと、設定した放送前の時刻に表示します。</p>
                        </div>
                        <article v-for="notice in notices" :key="notice.id" class="reminder-card"
                            :class="{'reminder-card--unread': !notice.is_read}">
                            <div class="reminder-card__source">{{notice.message}}<span v-if="!notice.is_read">・未読</span></div>
                            <h2 v-html="ProgramUtils.decorateProgramInfo({...IProgramDefault, title: notice.title}, 'title')"></h2>
                            <p class="mt-2">{{notice.channel_name}} / {{formatTime(notice.start_time, notice.end_time)}}</p>
                            <div class="reminder-card__actions">
                                <span class="reminders-help">{{dayjs(notice.created_at).format('M/D HH:mm')}}</span>
                                <v-spacer />
                                <v-btn v-if="!notice.is_read" variant="text" @click="notice.is_read = true">既読にする</v-btn>
                                <v-btn v-if="dayjs(notice.end_time).valueOf() > reminderStore.now" color="secondary" variant="flat"
                                    :to="`/tv/watch/${notice.display_channel_id}`">
                                    {{isOnAir(notice.start_time, notice.end_time) ? '今すぐ見る' : 'チャンネルを開く'}}
                                </v-btn>
                            </div>
                        </article>
                    </section>

                    <!-- 設定タブの入力を保持し、ほかのタブを見た後も編集を続けられるようにする。 -->
                    <section v-show="activeView === 'Preferences'" class="reminders-section">
                        <div class="preferences-card">
                            <h2>好みに合う番組を自動で探す</h2>
                            <p class="reminders-help mt-2">番組名・出演者・ジャンルなどをキーワードとして登録すると、合う番組を自動で探します。</p>
                            <v-switch v-model="settings.program_recommendation_enabled" color="secondary"
                                label="キーワードに合う番組を自動で探す" hide-details @update:model-value="reminderStore.refresh(true)" />
                            <p v-if="!settings.program_recommendation_enabled" class="reminders-help">自動検索は停止中です。登録済みの通知予定は継続します。</p>
                            <p class="mt-4 font-weight-bold">新しいおすすめの通知</p>
                            <v-radio-group v-model="settings.program_recommendation_notify_by_default" color="secondary" hide-details>
                                <v-radio label="通知オンで追加する" :value="true" />
                                <v-radio label="通知オフで追加し、見たい番組だけ自分で選ぶ" :value="false" />
                            </v-radio-group>
                            <p class="reminders-help">これから見つかるおすすめに適用します。すでに候補にある番組の通知状態は変わりません。</p>
                            <v-btn variant="tonal" color="secondary" class="mt-4"
                                :disabled="reminderStore.scheduledReminders.length === 0" @click="dismissAllReminders">
                                <Icon icon="fluent:alert-off-20-regular" width="18px" class="mr-1" />登録済み番組の通知をすべてオフ
                            </v-btn>
                            <div v-for="rule in settings.program_recommendation_rules" :key="rule.id" class="rule-row">
                                <div class="rule-row__body">
                                    <strong>{{rule.name}}</strong>
                                    <p class="reminders-help">{{rule.keyword || 'キーワード指定なし'}}{{rule.genre ? ` / ${rule.genre}` : ''}}</p>
                                    <p v-if="rule.exclude_keyword" class="reminders-help">除外：{{rule.exclude_keyword}}</p>
                                    <v-switch v-model="rule.is_enabled" color="secondary" density="compact" label="このキーワードを使う"
                                        hide-details @update:model-value="reminderStore.refresh(true)" />
                                </div>
                                <v-btn icon variant="text" size="36" :aria-label="`${rule.name}を編集`" @click="editRule(rule)">
                                    <Icon icon="fluent:edit-20-regular" width="20px" />
                                </v-btn>
                                <v-btn icon variant="text" color="error" size="36" :aria-label="`${rule.name}を削除`" @click="ruleToDelete = rule">
                                    <Icon icon="fluent:delete-20-regular" width="20px" />
                                </v-btn>
                            </div>
                            <v-btn variant="flat" color="secondary" class="mt-4" @click="editRule(null)">
                                <Icon icon="fluent:add-20-regular" width="18px" class="mr-1" />キーワードを追加
                            </v-btn>
                        </div>
                        <div class="preferences-card mt-4">
                            <h2>アプリ内のお知らせ</h2>
                            <v-switch v-model="settings.program_reminder_notifications_enabled" color="secondary"
                                label="このアプリでお知らせを表示" hide-details />
                            <v-checkbox v-model="settings.program_reminder_notify_on_discovery" color="secondary"
                                label="おすすめ番組を見つけたとき" hide-details />
                            <p class="mt-4 mb-2 font-weight-bold">放送前のお知らせ時刻</p>
                            <ProgramReminderTimeSettings v-model="settings.program_reminder_lead_times"
                                @dirty-change="hasUnsavedTimeChanges = $event" />
                            <p class="reminders-help mt-4">画面を閉じている間や端末のスリープ中には届きません。開き直したとき、2分を超えて過ぎた放送前のお知らせは省略し、放送予定を確認します。</p>
                            <v-btn variant="tonal" class="mt-4" @click="previewNotice">
                                <Icon icon="fluent:alert-20-regular" width="18px" class="mr-1" />お知らせの表示を試す
                            </v-btn>
                        </div>
                        <v-expansion-panels variant="accordion" class="mt-4">
                            <v-expansion-panel bg-color="background-lighten-1">
                                <v-expansion-panel-title>
                                    視聴の詳細設定（自動切り替え：{{settings.program_reminder_auto_switch_enabled ? 'オン' : 'オフ'}}）
                                </v-expansion-panel-title>
                                <v-expansion-panel-text>
                                    <v-switch v-model="settings.program_reminder_auto_switch_enabled" color="secondary" hide-details
                                        label="放送開始時に自動でチャンネルを切り替える" />
                                    <p class="reminders-help mt-2">
                                        この端末だけの設定です。「通知する」にした番組が対象です。
                                        KonomiTV の画面を操作中に、開始直前から10秒間の予告を表示して切り替えます。
                                        予告の「今回は切り替えない」で取り消せます。
                                    </p>
                                    <p class="reminders-help mt-2">
                                        同時刻に複数の対象がある場合は、見る番組を選びます。
                                        録画の再生中、別のタブ・アプリを操作中、画面を閉じている間は自動で切り替えません。
                                    </p>
                                </v-expansion-panel-text>
                            </v-expansion-panel>
                        </v-expansion-panels>
                    </section>
                    <p v-if="reminderStore.lastCheckedAt" class="reminders-help mt-5">
                        番組表の最終確認：{{dayjs(reminderStore.lastCheckedAt).format('M/D HH:mm')}}（日本時間）
                    </p>
                </div>
            </div>
        </main>
        <ProgramRecommendationRuleDialog v-model="isRuleDialogOpen" :rule="editingRule"
            :rules="settings.program_recommendation_rules" @save="saveRule" />
        <v-dialog :model-value="ruleToDelete !== null" max-width="500" @update:model-value="ruleToDelete = null">
            <v-card>
                <v-card-title class="d-flex justify-center pt-6 font-weight-bold">キーワードを削除しますか？</v-card-title>
                <v-card-text class="pt-2 pb-0">
                    「{{ruleToDelete?.name}}」を削除します。登録済みの通知予定とお知らせは残ります。
                </v-card-text>
                <v-card-actions class="pt-4 px-6 pb-6">
                    <v-spacer />
                    <v-btn color="text" variant="text" @click="ruleToDelete = null">
                        <Icon icon="fluent:dismiss-16-filled" width="18px" height="18px" /><span class="ml-1">キャンセル</span>
                    </v-btn>
                    <v-btn color="error" variant="flat" height="40" class="px-3" @click="deleteRule">
                        <Icon icon="fluent:delete-16-regular" width="18px" height="18px" /><span class="ml-1">キーワードを削除</span>
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
        <v-dialog :model-value="showLeaveConfirm" max-width="500" @update:model-value="finishLeave(false)">
            <v-card>
                <v-card-title class="d-flex justify-center pt-6 font-weight-bold">変更を破棄しますか？</v-card-title>
                <v-card-text class="pt-2 pb-0">通知時刻の変更がまだ保存されていません。</v-card-text>
                <v-card-actions class="pt-4 px-6 pb-6">
                    <v-spacer />
                    <v-btn color="text" variant="text" @click="finishLeave(false)">
                        <Icon icon="fluent:arrow-left-16-regular" width="18px" height="18px" /><span class="ml-1">編集に戻る</span>
                    </v-btn>
                    <v-btn color="secondary" variant="flat" height="40" class="px-3" @click="finishLeave(true)">
                        <Icon icon="fluent:dismiss-16-regular" width="18px" height="18px" /><span class="ml-1">変更を破棄</span>
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
        <v-snackbar v-model="showPreview" :timeout="8000" location="top" color="background-lighten-2">
            <div class="d-flex align-center"><Icon icon="fluent:alert-20-regular" width="24px" class="mr-3" />お知らせの表示テストです。</div>
            <template #actions><v-btn variant="text" @click="showPreview = false">閉じる</v-btn></template>
        </v-snackbar>
    </div>
</template>
<script lang="ts" setup>

import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router';

import type { IProgramRecommendationRule } from '@/services/ProgramReminders';

import Breadcrumbs from '@/components/Breadcrumbs.vue';
import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import ProgramRecommendationRuleDialog from '@/components/Programs/ProgramRecommendationRuleDialog.vue';
import ProgramReminderTimeSettings from '@/components/Programs/ProgramReminderTimeSettings.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import Message from '@/message';
import { IProgramDefault } from '@/services/Programs';
import useProgramRemindersStore from '@/stores/ProgramRemindersStore';
import useSettingsStore from '@/stores/SettingsStore';
import Utils, { dayjs, ProgramUtils } from '@/utils';
import {
    getProgramRecommendationReasons, getProgramRecommendationRuleKey, groupProgramRemindersByRule,
    groupScheduledProgramRemindersByKeyword,
} from '@/utils/ProgramReminderUtils';

const router = useRouter();
const route = useRoute();
const reminderStore = useProgramRemindersStore();
const settingsStore = useSettingsStore();
const settings = computed(() => settingsStore.settings);
const activeView = ref(['Candidates', 'Notices', 'Preferences'].includes(String(route.query.view)) ? String(route.query.view) : 'Scheduled');
// 削除済みキーワードの選択や通知状態の絞り込みを、もう一方の一覧へ持ち込まない。
const listFilters = reactive({
    Scheduled: { source: 'All', notification: 'All', keywords: [] as string[], sort: 'StartTime' },
    Candidates: { source: 'All', notification: 'All', keywords: [] as string[], sort: 'StartTime' },
});
const currentFilters = computed(() => listFilters[activeView.value === 'Candidates' ? 'Candidates' : 'Scheduled']);
const sourceFilter = computed({ get: () => currentFilters.value.source, set: value => currentFilters.value.source = value });
const notificationFilter = computed({ get: () => currentFilters.value.notification, set: value => currentFilters.value.notification = value });
const selectedRuleKeys = computed({ get: () => currentFilters.value.keywords, set: value => currentFilters.value.keywords = value });
const sortOrder = computed({ get: () => currentFilters.value.sort, set: value => currentFilters.value.sort = value });
const sortOptions = [
    { title: '放送が近い順', value: 'StartTime' },
    { title: 'キーワードごと（登録順）', value: 'Rule' },
];
const isFilterMenuOpen = ref(false);
const searchQuery = ref('');
const isRuleDialogOpen = ref(false);
const editingRule = ref<IProgramRecommendationRule | null>(null);
const ruleToDelete = ref<IProgramRecommendationRule | null>(null);
const showPreview = ref(false);
const hasUnsavedTimeChanges = ref(false);
const showLeaveConfirm = ref(false);
let resolveLeave: ((allow: boolean) => void) | null = null;
const listReminders = computed(() => activeView.value === 'Candidates' ?
    reminderStore.candidateReminders : reminderStore.scheduledReminders);
const sourceReminders = computed(() => listReminders.value.filter(reminder =>
    activeView.value === 'Candidates' || sourceFilter.value === 'All' || reminder.source === sourceFilter.value));
const notificationReminders = computed(() => sourceReminders.value.filter(reminder =>
    activeView.value === 'Scheduled' || notificationFilter.value === 'All' || reminder.status === notificationFilter.value));
const ruleGroups = computed(() => activeView.value === 'Candidates' ? groupProgramRemindersByRule(
    notificationReminders.value, settings.value.program_recommendation_rules.filter(rule => rule.is_enabled)) :
    groupScheduledProgramRemindersByKeyword(notificationReminders.value, settings.value.program_recommendation_rules));
const ruleOptions = computed(() => ruleGroups.value
    .filter(group => group.key !== 'Unmatched')
    .map(group => ({ title: `${group.name}（${group.reminders.length}）`, value: group.key })));
// 複数の条件は OR で絞り込み、放送順の一覧では同じ番組を1件にまとめる。
const selectedGroups = computed(() => ruleGroups.value.filter(group =>
    selectedRuleKeys.value.length === 0 || selectedRuleKeys.value.includes(group.key)));
const visibleReminders = computed(() => {
    const keys = new Set(selectedGroups.value.flatMap(group => group.reminders.map(reminder => reminder.key)));
    return notificationReminders.value.filter(reminder => keys.has(reminder.key)).sort((a, b) =>
        dayjs(a.program.start_time).valueOf() - dayjs(b.program.start_time).valueOf() || a.key.localeCompare(b.key));
});
const visibleGroups = computed(() => {
    if (sortOrder.value === 'Rule') return selectedGroups.value.filter(group => group.reminders.length > 0);
    return [{ key: 'All', name: '', reminders: visibleReminders.value }];
});
const activeFilterCount = computed(() => Number(sourceFilter.value !== 'All') +
    Number(notificationFilter.value !== 'All') + selectedRuleKeys.value.length);
const notices = computed(() => [...settings.value.program_reminder_notices].sort((a, b) => b.created_at - a.created_at));
const emptyTitle = computed(() => {
    if (reminderStore.error) return '番組表を取得できませんでした';
    if (activeFilterCount.value > 0 && listReminders.value.length > 0) return '絞り込みに合う番組はありません';
    if (activeView.value === 'Scheduled') return '通知予定はありません';
    if (settings.value.program_recommendation_rules.some(rule => rule.is_enabled)) return 'キーワードに合う番組候補はありません';
    return 'キーワードを登録しましょう';
});
const emptyDescription = computed(() => {
    if (reminderStore.error) return '接続を確認して、右上の「更新」からもう一度お試しください。';
    if (activeFilterCount.value > 0 && listReminders.value.length > 0) return 'キーワードなどの選択を変更するか、絞り込みを解除してください。';
    if (activeView.value === 'Scheduled') return '番組候補の「通知する」、番組表や検索結果のベルから登録できます。';
    if (!settings.value.program_recommendation_enabled) return '「通知設定」でキーワードの自動検索をオンにしてください。';
    if (settings.value.program_recommendation_rules.some(rule => rule.is_enabled)) return 'キーワードを調整するか、番組表が更新されるのをお待ちください。';
    return '「通知設定」でキーワードを追加し、使うものをオンにしてください。';
});

// 候補側だけを現在有効なキーワードに合わせる。通知予定側は削除済みの選択も保持する。
watch(() => settings.value.program_recommendation_rules.map(rule => ({
    id: rule.id, enabled: rule.is_enabled, key: `Condition:${getProgramRecommendationRuleKey(rule)}`,
})), (rules, previousRules) => {
    const currentIDs = rules.filter(rule => rule.enabled).map(rule => `Rule:${rule.id}`);
    listFilters.Candidates.keywords = listFilters.Candidates.keywords.filter(key => currentIDs.includes(key));
    // 編集では同じ ID の新しい条件を選び、削除・再追加では保存した条件キーを引き継ぐ。
    listFilters.Scheduled.keywords = listFilters.Scheduled.keywords.map(key => {
        const previous = previousRules.find(rule => rule.key === key);
        return rules.find(rule => rule.id === previous?.id)?.key ?? key;
    });
});

function clearFilters(): void {
    sourceFilter.value = 'All';
    notificationFilter.value = 'All';
    selectedRuleKeys.value = [];
}

// 同じ画面を表示中でも、通知から押した行き先に対応するタブを開く。
watch(() => [route.query.view, route.query.notify], () => {
    if (['Scheduled', 'Candidates', 'Notices', 'Preferences'].includes(String(route.query.view))) {
        activeView.value = String(route.query.view);
    }
    if (route.query.notify === 'Scheduled') {
        activeView.value = 'Scheduled';
        clearFilters();
    }
});

/** 保存済みの番組を使って、実際のお知らせと同じ表示・視聴導線を試す。 */
function previewNotice(): void {
    const target = reminderStore.scheduledReminders[0] ?? reminderStore.upcomingReminders[0];
    if (target === undefined) {
        showPreview.value = true;
        return;
    }
    reminderStore.latestNotices = [{
        id: 'Preview', reminder_key: target.key, title: target.program.title,
        channel_name: target.channel.name, start_time: target.program.start_time, end_time: target.program.end_time,
        display_channel_id: target.channel.display_channel_id, message: 'お知らせの表示テストです',
        created_at: dayjs().valueOf(), is_read: false,
    }];
}

function searchPrograms(query: string): void {
    void router.push({ path: '/tv/search', query: { query } });
}
function formatTime(start: string, end: string): string {
    return `${dayjs(start).format('M/D (ddd) HH:mm')} ～ ${dayjs(end).format('HH:mm')}`;
}
function isOnAir(start: string, end: string): boolean {
    return dayjs(start).valueOf() <= reminderStore.now && reminderStore.now < dayjs(end).valueOf();
}
function dismissAllReminders(): void {
    const count = reminderStore.dismissAll();
    if (count > 0) {
        Message.show(`${count} 件の通知をオフにしました。`);
    }
}
function editRule(rule: IProgramRecommendationRule | null): void {
    editingRule.value = rule;
    isRuleDialogOpen.value = true;
}
function saveRule(rule: IProgramRecommendationRule): void {
    const rules = settings.value.program_recommendation_rules;
    const index = rules.findIndex(item => item.id === rule.id);
    if (index === -1) {
        reminderStore.updateRecommendationRules([...rules, rule]);
    } else {
        reminderStore.updateRecommendationRules(rules.map(item => item.id === rule.id ? rule : item));
    }
    void reminderStore.refresh(true);
}
function deleteRule(): void {
    const targetID = ruleToDelete.value?.id;
    reminderStore.updateRecommendationRules(settings.value.program_recommendation_rules.filter(rule => rule.id !== targetID));
    ruleToDelete.value = null;
    void reminderStore.refresh(true);
}

/** ページを離れる操作は、未保存の入力をどう扱うか決まってから続ける。 */
function finishLeave(allow: boolean): void {
    showLeaveConfirm.value = false;
    if (!allow) {
        activeView.value = 'Preferences';
    }
    resolveLeave?.(allow);
    resolveLeave = null;
}

// アプリ内の移動では既存画面と同じ確認ダイアログを使う。
onBeforeRouteLeave(() => {
    if (!hasUnsavedTimeChanges.value) return true;
    resolveLeave?.(false);
    showLeaveConfirm.value = true;
    return new Promise<boolean>(resolve => { resolveLeave = resolve; });
});

/** 再読み込みやタブを閉じる操作では、ブラウザの離脱確認を有効化する。 */
function confirmReload(event: BeforeUnloadEvent): void {
    event.preventDefault();
    event.returnValue = '';
}
watch(hasUnsavedTimeChanges, dirty => {
    if (dirty) {
        window.addEventListener('beforeunload', confirmReload);
    } else {
        window.removeEventListener('beforeunload', confirmReload);
    }
}, { flush: 'sync' });
onBeforeUnmount(() => {
    window.removeEventListener('beforeunload', confirmReload);
    resolveLeave?.(false);
});
onMounted(() => void reminderStore.refresh(true));

</script>
<style lang="scss" scoped>

.reminders-wrapper { width: 100%; min-width: 0; }
.reminders-container {
    width: 100%; max-width: 1000px; padding: 20px; margin: 0 auto;
    @include smartphone-vertical { padding: 16px 12px; }
}
.reminders-header {
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    h1 { display: flex; align-items: center; gap: 10px; font-size: 24px; }
}
.reminders-intro { margin-top: 16px; line-height: 1.8; }
.reminders-help { color: rgb(var(--v-theme-text-darken-1)); font-size: 13px; line-height: 1.8; }
.reminders-tabs {
    @include smartphone-vertical {
        :deep(.v-slide-group__content) { width: 100%; }
        :deep(.v-tab) { flex: 1 1 0; min-width: 0; padding: 0 4px; font-size: 12px; }
        :deep(.v-btn__content) { flex-direction: column; line-height: 1.4; }
        .reminders-tab-count { margin-left: 0 !important; }
    }
}
.reminders-section { margin-top: 20px; }
.reminders-toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 16px; }
.reminders-filter-menu { width: min(440px, calc(100vw - 24px)); padding: 20px; }
.reminders-filter-summary { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 16px; }
.reminder-group__title {
    display: flex; align-items: baseline; gap: 12px; font-size: 18px; margin: 24px 0 12px;
    span { color: rgb(var(--v-theme-text-darken-1)); font-size: 13px; font-weight: normal; }
}
.reminders-empty {
    display: flex; flex-direction: column; align-items: center; padding: 48px 16px; text-align: center;
    color: rgb(var(--v-theme-text-darken-1));
    h2 { font-size: 19px; color: rgb(var(--v-theme-text)); margin-bottom: 12px; }
    p { max-width: 540px; line-height: 1.8; }
}
.reminder-card, .preferences-card {
    padding: 20px; border-radius: 8px; background: rgb(var(--v-theme-background-lighten-1));
    h2, h3 { font-size: 18px; line-height: 1.6; overflow-wrap: anywhere; }
    @include smartphone-vertical { padding: 16px; }
}
.reminder-card {
    margin-bottom: 14px; border: 1px solid transparent;
    &--unread { border-color: rgb(var(--v-theme-secondary)); }
    &__source { display: flex; align-items: center; gap: 6px; color: rgb(var(--v-theme-text-darken-1)); font-size: 12px; margin-bottom: 8px; }
    &__broadcast {
        display: flex; align-items: center; gap: 12px; margin-top: 12px; font-size: 13px; line-height: 1.8;
        img { width: 64px; height: 36px; object-fit: contain; }
    }
    &__description { margin-top: 14px; line-height: 1.8; font-size: 14px; overflow-wrap: anywhere; }
    &__reasons { margin-top: 14px; font-size: 12px; color: rgb(var(--v-theme-secondary-lighten-1)); line-height: 1.8; }
    &__actions { display: flex; flex-wrap: wrap; align-items: center; margin-top: 12px; gap: 8px; }
}
.rule-row, .dismissed-row {
    display: flex; align-items: center; gap: 8px; padding: 16px 0;
    border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
    &__body { flex: 1; min-width: 0; overflow-wrap: anywhere; }
}
.dismissed-row > div { flex: 1; min-width: 0; }

</style>
