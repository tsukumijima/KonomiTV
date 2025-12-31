<template>
    <div class="panel-content clip-export-panel">
        <div class="panel-content-header">
            <Icon icon="material-symbols:content-cut" width="23px" />
            <span class="ml-2">クリップ書き出し</span>
        </div>
        <div class="clip-export-container" v-if="export_status === 'idle'">
            <!-- コマ送りボタン -->
            <div class="controls-section">
                <div class="text-subtitle-2 mb-2">
                    プレイヤーでコマ送りして正確な位置を確認
                </div>
                <div class="controls-buttons mb-2">
                    <v-btn size="small" variant="text" @click="seekBackwardFrame" title="1フレーム戻る" class="control-btn">
                        <Icon icon="ic:round-skip-previous" width="22px" />
                    </v-btn>
                    <v-btn size="small" variant="text" @click="seekBackward" title="1秒戻る" class="control-btn">
                        <Icon icon="ic:round-fast-rewind" width="22px" />
                    </v-btn>
                    <v-btn size="small" variant="text" @click="seekForward" title="1秒進む" class="control-btn">
                        <Icon icon="ic:round-fast-forward" width="22px" />
                    </v-btn>
                    <v-btn size="small" variant="text" @click="seekForwardFrame" title="1フレーム進む" class="control-btn">
                        <Icon icon="ic:round-skip-next" width="22px" />
                    </v-btn>
                </div>
                <div class="text-center text-body-2 current-position">
                    現在位置: {{ currentFrame }}F ({{ formatTime(current_playback_time) }})
                </div>
            </div>

            <!-- 範囲選択シークバー -->
            <div class="range-selector">
                <div class="range-slider-container">
                    <input
                        type="range"
                        class="range-slider range-slider-start"
                        :min="0"
                        :max="totalFrames"
                        :step="1"
                        v-model.number="start_frame"
                        :disabled="currentSegment === null"
                        @input="onStartFrameSliderChange"
                    />
                    <input
                        type="range"
                        class="range-slider range-slider-end"
                        :min="0"
                        :max="totalFrames"
                        :step="1"
                        v-model.number="end_frame"
                        :disabled="currentSegment === null"
                        @input="onEndFrameSliderChange"
                    />
                    <div class="range-track">
                        <div class="range-track-selected" :style="selectedRangeStyle"></div>
                    </div>
                </div>
            </div>

            <div class="segments-list mb-3">
                <div class="segments-list__header">
                    <span class="segments-list__title">クリップに含める範囲</span>
                    <v-btn size="small" variant="text" color="primary" @click="addSegment">
                        <Icon icon="fluent:add-20-regular" width="18px" height="18px" class="mr-1" />
                        範囲を追加
                    </v-btn>
                </div>
                <div v-if="segments.length === 0" class="segments-list__empty text-body-2">
                    範囲を追加してクリップの区間を指定してください。
                </div>
                <v-list
                    v-else
                    density="compact"
                    class="segments-list__items"
                >
                    <v-list-item
                        v-for="(segment, index) in segments"
                        :key="segment.id"
                        @click="selectSegment(segment.id)"
                        :class="['segments-list__item', { 'segments-list__item--active': segment.id === selected_segment_id }]"
                    >
                        <v-list-item-title class="segments-list__item-main">
                            <div class="segments-list__item-header">
                                <span class="segments-list__item-label">第{{ index + 1 }}範囲</span>
                                <span class="segments-list__item-duration">
                                    ({{ segment.end_frame - segment.start_frame }}F)
                                </span>
                            </div>
                            <div class="segments-list__item-range">
                                {{ segment.start_frame }}F ({{ formatTime(frameToTime(segment.start_frame)) }})
                                <br />
                                〜 {{ segment.end_frame }}F ({{ formatTime(frameToTime(segment.end_frame)) }})
                            </div>
                        </v-list-item-title>
                        <template #append>
                            <v-btn
                                icon
                                variant="text"
                                size="small"
                                color="text-darken-1"
                                @click.stop="removeSegment(segment.id)"
                            >
                                <Icon icon="fluent:delete-20-regular" width="18px" height="18px" />
                            </v-btn>
                        </template>
                    </v-list-item>
                </v-list>
            </div>

            <!-- フレーム入力 -->
            <div class="time-inputs mb-3">
                <div class="time-input-group mb-2">
                    <div class="time-input-row">
                        <span class="time-label">開始</span>
                        <v-text-field
                            v-model.number="start_frame"
                            density="compact"
                            variant="outlined"
                            hide-details
                            type="number"
                            :min="0"
                            :max="totalFrames"
                            placeholder="0"
                            :disabled="currentSegment === null"
                            @input="onStartFrameInput"
                            class="time-field"
                        ></v-text-field>
                        <span class="frame-unit">F</span>
                        <v-btn size="small" variant="text" color="primary" @click="setStartFrameFromPlayer" class="time-btn">
                            現在位置
                        </v-btn>
                    </div>
                    <div class="time-display">
                        {{ formatTime(frameToTime(start_frame)) }}
                    </div>
                </div>
                <div class="time-input-group mb-3">
                    <div class="time-input-row">
                        <span class="time-label">終了</span>
                        <v-text-field
                            v-model.number="end_frame"
                            density="compact"
                            variant="outlined"
                            hide-details
                            type="number"
                            :min="0"
                            :max="totalFrames"
                            placeholder="0"
                            :disabled="currentSegment === null"
                            @input="onEndFrameInput"
                            class="time-field"
                        ></v-text-field>
                        <span class="frame-unit">F</span>
                        <v-btn size="small" variant="text" color="primary" @click="setEndFrameFromPlayer" class="time-btn">
                            現在位置
                        </v-btn>
                    </div>
                    <div class="time-display">
                        {{ formatTime(frameToTime(end_frame)) }}
                    </div>
                </div>
            </div>

            <v-alert v-if="error_message" type="error" density="compact" class="mb-3">
                {{ error_message }}
            </v-alert>

            <div class="text-body-2 mb-3">
                クリップ長: {{ totalClipFrames }}F ({{ formatTime(totalClipDuration) }})
            </div>

            <v-btn color="primary" variant="flat" block @click="startExport" :disabled="!hasValidSegments">
                <Icon icon="material-symbols:content-cut" width="20px" class="mr-2" />
                書き出し開始
            </v-btn>
        </div>

        <!-- 処理中 -->
        <div class="clip-export-container" v-else-if="export_status === 'processing'">
            <v-progress-linear
                :model-value="progress"
                color="primary"
                height="25"
                class="mb-4"
            >
                <template v-slot:default="{ value }">
                    <strong>{{ Math.ceil(value) }}%</strong>
                </template>
            </v-progress-linear>
            <div class="text-center text-subtitle-1">
                {{ status_detail }}
            </div>
        </div>

        <!-- 完了 -->
        <div class="clip-export-container" v-else-if="export_status === 'completed'">
            <v-alert type="success" density="compact" class="mb-4">
                クリップの書き出しが完了しました！
            </v-alert>
            <div class="text-body-2 mb-4">
                <strong>ファイルサイズ:</strong> {{ formatFileSize(output_file_size) }}
            </div>
            
            <!-- プレビューと保存ボタン -->
            <v-btn color="primary" variant="outlined" block @click="previewClip" class="mb-2">
                <Icon icon="fluent:play-20-filled" width="20px" class="mr-2" />
                プレビュー
            </v-btn>
            <v-btn color="success" variant="flat" block @click="saveClip" class="mb-2" :loading="is_saving">
                <Icon icon="fluent:save-20-filled" width="20px" class="mr-2" />
                保存してクリップ一覧に追加
            </v-btn>
            <v-btn color="text-darken-1" variant="outlined" block @click="downloadClip" class="mb-2" :loading="is_downloading">
                <Icon icon="fluent:arrow-download-20-filled" width="20px" class="mr-2" />
                ダウンロード
            </v-btn>
            <v-btn color="text-darken-1" variant="text" block @click="resetExport">
                新しいクリップを作成
            </v-btn>
        </div>

        <!-- 失敗 -->
        <div class="clip-export-container" v-else-if="export_status === 'failed'">
            <v-alert type="error" density="compact" class="mb-4">
                書き出しに失敗しました: {{ status_detail }}
            </v-alert>
            <v-btn color="text-darken-1" variant="text" block @click="resetExport">
                やり直す
            </v-btn>
        </div>
    </div>
</template>

<script lang="ts">
import { mapStores } from 'pinia';
import { defineComponent } from 'vue';

import { IClipSegment } from '@/services/ClipVideos';
import Videos from '@/services/Videos';
import usePlayerStore from '@/stores/PlayerStore';
import { useSnackbarsStore } from '@/stores/SnackbarsStore';

export default defineComponent({
    name: 'ClipExport',
    data() {
        return {
            segments: [] as { id: number; start_frame: number; end_frame: number; }[],
            selected_segment_id: null as number | null,
            segment_id_counter: 0,
            start_frame: 0,
            end_frame: 0,
            error_message: '',
            export_status: 'idle' as 'idle' | 'processing' | 'completed' | 'failed',
            progress: 0,
            status_detail: '',
            task_id: null as string | null,
            output_file_size: null as number | null,
            polling_interval: null as number | null,
            main_player: null as any,
            current_playback_time: 0,
            playback_time_interval: null as number | null,
            is_saving: false,
            is_downloading: false,
        };
    },
    computed: {
        ...mapStores(usePlayerStore, useSnackbarsStore),
        frameRate(): number {
            return this.playerStore.recorded_program?.recorded_video?.video_frame_rate || 29.97;
        },
        totalFrames(): number {
            const duration = this.playerStore.recorded_program?.recorded_video?.duration || 0;
            return Math.floor(duration * this.frameRate);
        },
        currentFrame(): number {
            return Math.floor(this.current_playback_time * this.frameRate);
        },
        currentSegment(): { id: number; start_frame: number; end_frame: number; } | null {
            if (this.selected_segment_id === null) {
                return null;
            }
            return this.segments.find(segment => segment.id === this.selected_segment_id) ?? null;
        },
        currentSegmentIndex(): number {
            if (this.currentSegment === null) {
                return -1;
            }
            return this.segments.findIndex(segment => segment.id === this.currentSegment?.id);
        },
        totalClipFrames(): number {
            return this.segments.reduce((sum, segment) => sum + Math.max(segment.end_frame - segment.start_frame, 0), 0);
        },
        totalClipDuration(): number {
            return this.totalClipFrames / this.frameRate;
        },
        hasValidSegments(): boolean {
            return this.error_message === '' && this.segments.length > 0;
        },
        selectedRangeStyle(): any {
            if (this.currentSegment === null) {
                return { left: '0%', width: '0%' };
            }
            const total = this.totalFrames;
            if (total === 0) return { left: '0%', width: '0%' };
            const left = (this.start_frame / total) * 100;
            const width = ((this.end_frame - this.start_frame) / total) * 100;
            return {
                left: `${left}%`,
                width: `${width}%`,
            };
        },
    },
    watch: {
        'playerStore.video_panel_active_tab'(newTab) {
            if (newTab === 'ClipExport' && !this.playback_time_interval) {
                this.initializeClipExport();
            } else if (newTab !== 'ClipExport' && this.playback_time_interval) {
                this.cleanupIntervals();
            }
        },
    },
    methods: {
        generateSegmentId(): number {
            this.segment_id_counter += 1;
            return this.segment_id_counter;
        },
        getVideoDuration(): number {
            return this.playerStore.recorded_program?.recorded_video?.duration || 0;
        },
        frameToTime(frame: number): number {
            return frame / this.frameRate;
        },
        timeToFrame(time: number): number {
            return Math.floor(time * this.frameRate);
        },
        selectSegment(segmentId: number): void {
            const segment = this.segments.find(entry => entry.id === segmentId);
            if (!segment) {
                return;
            }
            this.selected_segment_id = segmentId;
            this.start_frame = segment.start_frame;
            this.end_frame = segment.end_frame;
            this.validateSegments();
        },
        applySegmentUpdate(segmentId: number, startFrame: number, endFrame: number): void {
            const total = this.totalFrames;
            if (total <= 0) {
                return;
            }

            let normalizedStart = Math.max(0, Math.min(startFrame, total));
            let normalizedEnd = Math.max(0, Math.min(endFrame, total));

            if (normalizedEnd <= normalizedStart) {
                const minimumGap = Math.min(Math.floor(this.frameRate), total);
                normalizedEnd = Math.min(normalizedStart + minimumGap, total);
                if (normalizedEnd <= normalizedStart) {
                    normalizedStart = Math.max(normalizedEnd - minimumGap, 0);
                }
            }

            const updatedSegment = { id: segmentId, start_frame: normalizedStart, end_frame: normalizedEnd };
            const nextSegments = this.segments.map(segment => segment.id === segmentId ? updatedSegment : segment);
            nextSegments.sort((a, b) => a.start_frame - b.start_frame);
            this.segments = nextSegments;

            const refreshed = this.segments.find(segment => segment.id === segmentId);
            if (refreshed) {
                this.selected_segment_id = refreshed.id;
                this.start_frame = refreshed.start_frame;
                this.end_frame = refreshed.end_frame;
            }

            this.validateSegments();
        },
        addSegment(): void {
            const total = this.totalFrames;
            if (total <= 0) {
                this.snackbarsStore.show('error', '録画番組の長さを取得できませんでした', 5);
                return;
            }

            const baseFrame = this.main_player ? this.timeToFrame(this.main_player.video.currentTime) : this.currentFrame;
            const windowFrames = Math.min(Math.floor(30 * this.frameRate), total);
            let startFrame = Math.max(Math.min(baseFrame, total), 0);
            if (startFrame + windowFrames > total) {
                startFrame = Math.max(total - windowFrames, 0);
            }

            const segmentId = this.generateSegmentId();
            this.segments = [...this.segments, { id: segmentId, start_frame: startFrame, end_frame: startFrame + windowFrames }]
                .sort((a, b) => a.start_frame - b.start_frame);
            this.applySegmentUpdate(segmentId, startFrame, startFrame + windowFrames);
        },
        removeSegment(segmentId: number): void {
            const previousIndex = this.segments.findIndex(segment => segment.id === this.selected_segment_id);
            this.segments = this.segments.filter(segment => segment.id !== segmentId);

            if (this.segments.length === 0) {
                this.selected_segment_id = null;
                this.start_frame = 0;
                this.end_frame = 0;
            } else {
                const targetIndex = Math.min(Math.max(previousIndex, 0), this.segments.length - 1);
                const nextSegment = this.segments[targetIndex];
                this.selectSegment(nextSegment.id);
            }

            this.validateSegments();
        },
        updateCurrentSegment(): void {
            const current = this.currentSegment;
            if (!current) {
                return;
            }
            this.applySegmentUpdate(current.id, this.start_frame, this.end_frame);
        },
        getSegmentsForExport(): IClipSegment[] {
            return this.segments
                .slice()
                .sort((a, b) => a.start_frame - b.start_frame)
                .map(segment => ({ start_frame: segment.start_frame, end_frame: segment.end_frame }));
        },
        validateSegments(): void {
            this.error_message = '';
            const total = this.totalFrames;

            if (this.segments.length === 0) {
                this.error_message = 'クリップ範囲を少なくとも1つ追加してください';
                return;
            }

            for (let index = 0; index < this.segments.length; index++) {
                const segment = this.segments[index];
                if (segment.start_frame < 0) {
                    this.error_message = `第${index + 1}範囲の開始フレームは0以上にしてください`;
                    return;
                }
                if (segment.end_frame <= segment.start_frame) {
                    this.error_message = `第${index + 1}範囲の終了フレームは開始フレームより後にしてください`;
                    return;
                }
                if (total > 0 && segment.end_frame > total) {
                    this.error_message = `第${index + 1}範囲の終了フレームは動画の長さ（${total}F）以下にしてください`;
                    return;
                }
            }
        },
        initializeClipExport() {
            const handlePanelOpened = (payload: any) => {
                this.main_player = payload.player;

                if (this.main_player && !this.main_player.video.paused) {
                    this.main_player.pause();
                }

                this.current_playback_time = this.main_player?.video.currentTime || 0;
                const total = this.totalFrames;
                this.segment_id_counter = 0;
                const currentFrame = this.timeToFrame(this.current_playback_time);
                const defaultStart = Math.min(currentFrame, Math.max(total - 1, 0));
                const windowFrames = Math.floor(30 * this.frameRate);
                const defaultEndCandidate = total > 0 ? Math.min(defaultStart + windowFrames, total) : defaultStart + windowFrames;
                const segmentId = this.generateSegmentId();
                this.segments = [{ id: segmentId, start_frame: defaultStart, end_frame: defaultEndCandidate }];
                this.applySegmentUpdate(segmentId, defaultStart, defaultEndCandidate);
                this.validateSegments();

                if (this.playback_time_interval) {
                    clearInterval(this.playback_time_interval);
                }
                this.playback_time_interval = window.setInterval(() => {
                    if (this.main_player) {
                        this.current_playback_time = this.main_player.video.currentTime;
                    }
                }, 100);
            };

            this.playerStore.event_emitter.on('ClipExportPanelOpened', handlePanelOpened);
            this.playerStore.event_emitter.emit('RequestPlayerInstance', {});
        },
        cleanupIntervals() {
            if (this.polling_interval) {
                clearInterval(this.polling_interval);
                this.polling_interval = null;
            }
            if (this.playback_time_interval) {
                clearInterval(this.playback_time_interval);
                this.playback_time_interval = null;
            }
        },
        seekForward() {
            if (this.main_player) {
                this.main_player.video.currentTime = Math.min(
                    this.main_player.video.currentTime + 1,
                    this.playerStore.recorded_program?.recorded_video?.duration || 0
                );
            }
        },
        seekBackward() {
            if (this.main_player) {
                this.main_player.video.currentTime = Math.max(
                    this.main_player.video.currentTime - 1,
                    0
                );
            }
        },
        seekForwardFrame() {
            if (this.main_player) {
                const frameDuration = 1 / this.frameRate;
                this.main_player.video.currentTime = Math.min(
                    this.main_player.video.currentTime + frameDuration,
                    this.playerStore.recorded_program?.recorded_video?.duration || 0
                );
            }
        },
        seekBackwardFrame() {
            if (this.main_player) {
                const frameDuration = 1 / this.frameRate;
                this.main_player.video.currentTime = Math.max(
                    this.main_player.video.currentTime - frameDuration,
                    0
                );
            }
        },
        setStartFrameFromPlayer() {
            if (!this.main_player) {
                return;
            }
            this.start_frame = this.timeToFrame(this.main_player.video.currentTime);
            if (this.start_frame >= this.end_frame) {
                this.end_frame = Math.min(this.start_frame + Math.floor(this.frameRate), this.totalFrames);
            }
            this.updateCurrentSegment();
        },
        setEndFrameFromPlayer() {
            if (!this.main_player) {
                return;
            }
            this.end_frame = this.timeToFrame(this.main_player.video.currentTime);
            this.updateCurrentSegment();
        },
        onStartFrameSliderChange() {
            this.updateCurrentSegment();
            if (this.main_player) {
                this.main_player.seek(this.frameToTime(this.start_frame));
            }
        },
        onEndFrameSliderChange() {
            this.updateCurrentSegment();
        },
        onStartFrameInput() {
            this.updateCurrentSegment();
        },
        onEndFrameInput() {
            this.updateCurrentSegment();
        },
        formatTime(seconds: number): string {
            const h = Math.floor(seconds / 3600);
            const m = Math.floor((seconds % 3600) / 60);
            const s = Math.floor(seconds % 60);
            return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
        },
        async startExport() {
            if (!this.hasValidSegments) return;

            const video_id = this.playerStore.recorded_program?.id;
            if (!video_id) {
                this.snackbarsStore.show('error', '録画番組情報の取得に失敗しました', 5);
                return;
            }

            if (this.main_player && !this.main_player.video.paused) {
                this.main_player.pause();
            }

            this.export_status = 'processing';
            this.progress = 0;
            this.status_detail = 'クリップ書き出しを開始しています...';

            const exportSegments = this.getSegmentsForExport();
            const task_id = await Videos.exportVideoClip(video_id, exportSegments);
            if (!task_id) {
                this.export_status = 'failed';
                this.status_detail = '書き出しの開始に失敗しました';
                return;
            }

            this.task_id = task_id;

            // ポーリング失敗回数をカウント
            let polling_error_count = 0;
            const max_polling_errors = 5;

            this.polling_interval = window.setInterval(async () => {
                if (!this.task_id) return;
                
                const status = await Videos.fetchVideoClipExportStatus(video_id, this.task_id);
                if (status) {
                    // 成功したらエラーカウントをリセット
                    polling_error_count = 0;
                    this.progress = status.progress;
                    this.status_detail = status.detail;

                    if (status.status === 'Completed') {
                        this.export_status = 'completed';
                        this.output_file_size = status.output_file_size;
                        if (this.polling_interval) {
                            clearInterval(this.polling_interval);
                            this.polling_interval = null;
                        }
                    } else if (status.status === 'Failed') {
                        this.export_status = 'failed';
                        if (this.polling_interval) {
                            clearInterval(this.polling_interval);
                            this.polling_interval = null;
                        }
                        this.snackbarsStore.show('error', 'クリップの書き出しに失敗しました', 5);
                    }
                } else {
                    // ステータス取得に失敗した場合
                    polling_error_count++;
                    if (polling_error_count >= max_polling_errors) {
                        // 連続して失敗した場合は失敗として扱う
                        this.export_status = 'failed';
                        this.status_detail = '進捗状況の取得に失敗しました。ネットワーク接続を確認してください。';
                        if (this.polling_interval) {
                            clearInterval(this.polling_interval);
                            this.polling_interval = null;
                        }
                        this.snackbarsStore.show('error', '進捗状況の取得に失敗しました', 5);
                    }
                }
            }, 2000);
        },
        async downloadClip() {
            if (!this.task_id) return;
            
            const video_id = this.playerStore.recorded_program?.id;
            if (!video_id) return;

            this.is_downloading = true;
            const success = await Videos.downloadVideoClip(video_id, this.task_id);
            this.is_downloading = false;

            if (success) {
                this.snackbarsStore.show('success', 'ダウンロードを開始しました', 5);
            } else {
                this.snackbarsStore.show('error', 'ダウンロードに失敗しました', 5);
            }
        },
        async previewClip() {
            if (!this.task_id) return;
            
            const video_id = this.playerStore.recorded_program?.id;
            if (!video_id) return;

            // プレビュー用URLを開く
            // PWA モードでも動作するよう、ポップアップブロック時のフォールバックを用意
            const preview_url = `/api/streams/video/${video_id}/clip-export/${this.task_id}/preview`;
            
            // 新しいタブで開くことを試みる（通常ブラウザ向け）
            // PWA モードの場合はフォールバックとして同じウィンドウで開く
            const newWindow = window.open(preview_url, '_blank', 'noopener,noreferrer');
            if (!newWindow || newWindow.closed || typeof newWindow.closed === 'undefined') {
                // ポップアップがブロックされた場合や PWA モードの場合
                // 同じウィンドウで開く
                window.location.href = preview_url;
            }
        },
        async saveClip() {
            if (!this.task_id) return;
            
            const video_id = this.playerStore.recorded_program?.id;
            if (!video_id) return;

            this.is_saving = true;

            const success = await Videos.saveVideoClip(video_id, this.task_id);
            
            this.is_saving = false;

            if (success) {
                this.snackbarsStore.show('success', 'クリップを保存しました。クリップ動画一覧で確認できます。', 5);
                // 保存後も画面はそのまま維持（ダウンロードする可能性もあるため）
            } else {
                this.snackbarsStore.show('error', 'クリップの保存に失敗しました', 5);
            }
        },
        resetExport() {
            this.export_status = 'idle';
            this.progress = 0;
            this.status_detail = '';
            this.task_id = null;
            this.output_file_size = null;
            this.error_message = '';
            this.is_saving = false;
            this.is_downloading = false;
            this.validateSegments();
        },
        formatFileSize(bytes: number | null): string {
            if (bytes === null) return '不明';
            const units = ['B', 'KB', 'MB', 'GB'];
            let size = bytes;
            let unitIndex = 0;
            while (size >= 1024 && unitIndex < units.length - 1) {
                size /= 1024;
                unitIndex++;
            }
            return `${size.toFixed(2)} ${units[unitIndex]}`;
        },
    },
    mounted() {
        if (this.playerStore.video_panel_active_tab === 'ClipExport') {
            this.initializeClipExport();
        }
    },
    beforeUnmount() {
        this.cleanupIntervals();
    },
});
</script>

<style lang="scss" scoped>

.clip-export-panel {
    padding: 20px 16px;
    height: 100%;
    display: flex;
    flex-direction: column;

    @include smartphone-horizontal {
        padding: 12px 10px;
    }

    @include smartphone-vertical {
        padding: 12px 10px;
    }
}

.clip-export-container {
    max-width: 100%;
    overflow-y: auto;
    overflow-x: hidden;
    flex: 1;
    padding-right: 4px;

    @include smartphone-horizontal {
        padding-right: 2px;
    }

    @include smartphone-vertical {
        padding-right: 2px;
    }
}

.controls-section {
    background: rgba(0, 0, 0, 0.03);
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 16px;

    @include smartphone-horizontal {
        padding: 10px 8px;
        margin-bottom: 12px;
    }

    @include smartphone-vertical {
        padding: 10px 8px;
        margin-bottom: 12px;
    }
}

.controls-buttons {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;

    .control-btn {
        min-width: 40px;
        padding: 0 8px;
    }

    @include smartphone-horizontal {
        gap: 2px;
        
        .control-btn {
            min-width: 36px;
            padding: 0 6px;
        }
    }

    @include smartphone-vertical {
        gap: 2px;
        
        .control-btn {
            min-width: 36px;
            padding: 0 6px;
        }
    }
}

.current-position {
    @include smartphone-horizontal {
        font-size: 0.875rem;
    }

    @include smartphone-vertical {
        font-size: 0.875rem;
    }
}

.range-selector {
    position: relative;
    padding: 16px 0 12px;
    margin-bottom: 16px;

    @include smartphone-horizontal {
        padding: 12px 0 10px;
        margin-bottom: 12px;
    }

    @include smartphone-vertical {
        padding: 12px 0 10px;
        margin-bottom: 12px;
    }
}

.segments-list {
    background: rgba(0, 0, 0, 0.03);
    border-radius: 8px;
    padding: 12px;

    @include smartphone-horizontal {
        padding: 10px;
    }

    @include smartphone-vertical {
        padding: 10px;
    }
}

.segments-list__header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.segments-list__title {
    font-weight: 600;
    font-size: 0.95rem;
}

.segments-list__empty {
    padding: 8px 0;
    color: rgb(var(--v-theme-text-darken-1));
}

.segments-list__items {
    padding: 0;
    background: transparent;
}

.segments-list__item {
    border-radius: 6px;
    transition: background-color 0.15s;
}

.segments-list__item--active {
    background: rgba(var(--v-theme-primary), 0.12);
}

.segments-list__item-main {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
}

.segments-list__item-header {
    display: flex;
    align-items: center;
    gap: 8px;
}

.segments-list__item-label {
    font-weight: 600;
    color: rgb(var(--v-theme-text));
}

.segments-list__item-range {
    font-feature-settings: "palt" 1;
    font-size: 0.85rem;
    line-height: 1.4;
    color: rgb(var(--v-theme-text-darken-1));
}

.segments-list__item-duration {
    color: rgb(var(--v-theme-text-darken-1));
    font-size: 0.85rem;
}

.range-slider-container {
    position: relative;
    height: 50px;
    width: 100%;

    @include smartphone-horizontal {
        height: 45px;
    }

    @include smartphone-vertical {
        height: 45px;
    }
}

.range-slider {
    position: absolute;
    width: 100%;
    height: 8px;
    -webkit-appearance: none;
    appearance: none;
    background: transparent;
    outline: none;
    pointer-events: none;
    margin: 0;
    padding: 0;
    top: 50%;
    transform: translateY(-50%);
}

.range-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: rgb(var(--v-theme-primary));
    cursor: pointer;
    pointer-events: all;
    border: 2px solid #fff;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
    z-index: 3;
    position: relative;

    @include smartphone-horizontal {
        width: 24px;
        height: 24px;
    }

    @include smartphone-vertical {
        width: 24px;
        height: 24px;
    }
}

.range-slider::-moz-range-thumb {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: rgb(var(--v-theme-primary));
    cursor: pointer;
    pointer-events: all;
    border: 2px solid #fff;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
    z-index: 3;
    position: relative;

    @include smartphone-horizontal {
        width: 24px;
        height: 24px;
    }

    @include smartphone-vertical {
        width: 24px;
        height: 24px;
    }
}

.range-slider-start {
    z-index: 2;
}

.range-slider-end {
    z-index: 2;
}

.range-track {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    width: 100%;
    height: 8px;
    background: #ddd;
    border-radius: 4px;
    z-index: 1;
}

.range-track-selected {
    position: absolute;
    height: 100%;
    background: rgb(var(--v-theme-primary));
    border-radius: 4px;
    opacity: 0.6;
}

.time-inputs {
    .time-input-group {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .time-input-row {
        display: flex;
        align-items: center;
        gap: 6px;

        @include smartphone-horizontal {
            gap: 4px;
        }

        @include smartphone-vertical {
            gap: 4px;
        }
    }

    .time-label {
        min-width: 45px;
        flex-shrink: 0;
        font-size: 0.9rem;

        @include smartphone-horizontal {
            min-width: 38px;
            font-size: 0.875rem;
        }

        @include smartphone-vertical {
            min-width: 38px;
            font-size: 0.875rem;
        }
    }

    .time-field {
        flex: 1;
        min-width: 0;
    }

    .frame-unit {
        flex-shrink: 0;
        font-size: 0.9rem;
        color: rgb(var(--v-theme-text-darken-1));
        min-width: 20px;

        @include smartphone-horizontal {
            font-size: 0.875rem;
            min-width: 16px;
        }

        @include smartphone-vertical {
            font-size: 0.875rem;
            min-width: 16px;
        }
    }

    .time-btn {
        flex-shrink: 0;
        padding: 0 8px;
        min-width: auto;
        font-size: 0.875rem;

        @include smartphone-horizontal {
            padding: 0 6px;
            font-size: 0.75rem;
        }

        @include smartphone-vertical {
            padding: 0 6px;
            font-size: 0.75rem;
        }
    }

    .time-display {
        margin-left: 45px;
        font-size: 0.85rem;
        color: rgb(var(--v-theme-text-darken-1));

        @include smartphone-horizontal {
            margin-left: 38px;
            font-size: 0.8rem;
        }

        @include smartphone-vertical {
            margin-left: 38px;
            font-size: 0.8rem;
        }
    }
}
</style>
