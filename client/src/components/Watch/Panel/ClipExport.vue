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
                    現在位置: {{ formatTime(current_playback_time) }}
                </div>
            </div>

            <!-- 範囲選択シークバー -->
            <div class="range-selector">
                <div class="range-slider-container">
                    <input
                        type="range"
                        class="range-slider range-slider-start"
                        :min="0"
                        :max="playerStore.recorded_program?.recorded_video?.duration || 0"
                        :step="0.1"
                        v-model.number="start_time_seconds"
                        @input="onStartTimeSliderChange"
                    />
                    <input
                        type="range"
                        class="range-slider range-slider-end"
                        :min="0"
                        :max="playerStore.recorded_program?.recorded_video?.duration || 0"
                        :step="0.1"
                        v-model.number="end_time_seconds"
                        @input="onEndTimeSliderChange"
                    />
                    <div class="range-track">
                        <div class="range-track-selected" :style="selectedRangeStyle"></div>
                    </div>
                </div>
            </div>

            <!-- 時刻入力 -->
            <div class="time-inputs mb-3">
                <div class="time-input-row mb-2">
                    <span class="time-label">開始</span>
                    <v-text-field
                        v-model="start_time_display"
                        density="compact"
                        variant="outlined"
                        hide-details
                        placeholder="00:00:00"
                        @input="onStartTimeInput"
                        class="time-field"
                    ></v-text-field>
                    <v-btn size="small" variant="text" color="primary" @click="setStartTimeFromPlayer" class="time-btn">
                        現在位置
                    </v-btn>
                </div>
                <div class="time-input-row mb-3">
                    <span class="time-label">終了</span>
                    <v-text-field
                        v-model="end_time_display"
                        density="compact"
                        variant="outlined"
                        hide-details
                        placeholder="00:00:00"
                        @input="onEndTimeInput"
                        class="time-field"
                    ></v-text-field>
                    <v-btn size="small" variant="text" color="primary" @click="setEndTimeFromPlayer" class="time-btn">
                        現在位置
                    </v-btn>
                </div>
            </div>

            <v-alert v-if="error_message" type="error" density="compact" class="mb-3">
                {{ error_message }}
            </v-alert>

            <div class="text-body-2 mb-3">
                クリップ時間: {{ formatTime(end_time_seconds - start_time_seconds) }}
            </div>

            <v-btn color="primary" variant="flat" block @click="startExport" :disabled="!isValidTimeRange">
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
            <v-btn color="text-darken-1" variant="outlined" block @click="downloadClip" class="mb-2">
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

import Videos from '@/services/Videos';
import usePlayerStore from '@/stores/PlayerStore';
import { useSnackbarsStore } from '@/stores/SnackbarsStore';

export default defineComponent({
    name: 'ClipExport',
    data() {
        return {
            start_time_display: '00:00:00',
            end_time_display: '00:00:00',
            start_time_seconds: 0,
            end_time_seconds: 0,
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
        };
    },
    computed: {
        ...mapStores(usePlayerStore, useSnackbarsStore),
        isValidTimeRange(): boolean {
            return this.start_time_seconds >= 0 && 
                   this.end_time_seconds > this.start_time_seconds &&
                   this.end_time_seconds <= (this.playerStore.recorded_program?.recorded_video?.duration || 0);
        },
        selectedRangeStyle(): any {
            const duration = this.playerStore.recorded_program?.recorded_video?.duration || 0;
            if (duration === 0) return { left: '0%', width: '0%' };
            const left = (this.start_time_seconds / duration) * 100;
            const width = ((this.end_time_seconds - this.start_time_seconds) / duration) * 100;
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
        initializeClipExport() {
            // DPlayer インスタンスを取得
            this.playerStore.event_emitter.on('ClipExportPanelOpened', (payload: any) => {
                this.main_player = payload.player;
                
                // メインプレイヤーが再生中の場合は一時停止
                if (this.main_player && !this.main_player.video.paused) {
                    this.main_player.pause();
                }

                // 現在の再生位置を取得
                this.current_playback_time = this.main_player?.video.currentTime || 0;

                // デフォルトで現在位置から30秒後までを設定
                this.start_time_seconds = Math.floor(this.current_playback_time);
                this.end_time_seconds = Math.min(
                    this.start_time_seconds + 30,
                    this.playerStore.recorded_program?.recorded_video?.duration || 0
                );
                this.start_time_display = this.formatTime(this.start_time_seconds);
                this.end_time_display = this.formatTime(this.end_time_seconds);

                // メインプレイヤーの再生位置を定期的に更新
                this.playback_time_interval = window.setInterval(() => {
                    if (this.main_player) {
                        this.current_playback_time = this.main_player.video.currentTime;
                    }
                }, 100);
            });
            
            // イベントを発火してプレイヤーインスタンスを要求
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
                const frameDuration = 1 / 29.97;
                this.main_player.video.currentTime = Math.min(
                    this.main_player.video.currentTime + frameDuration,
                    this.playerStore.recorded_program?.recorded_video?.duration || 0
                );
            }
        },
        seekBackwardFrame() {
            if (this.main_player) {
                const frameDuration = 1 / 29.97;
                this.main_player.video.currentTime = Math.max(
                    this.main_player.video.currentTime - frameDuration,
                    0
                );
            }
        },
        setStartTimeFromPlayer() {
            if (this.main_player) {
                this.start_time_seconds = this.main_player.video.currentTime;
                this.start_time_display = this.formatTime(this.start_time_seconds);
                this.validateTimeRange();
            }
        },
        setEndTimeFromPlayer() {
            if (this.main_player) {
                this.end_time_seconds = this.main_player.video.currentTime;
                this.end_time_display = this.formatTime(this.end_time_seconds);
                this.validateTimeRange();
            }
        },
        onStartTimeSliderChange() {
            this.start_time_display = this.formatTime(this.start_time_seconds);
            this.validateTimeRange();
            
            const duration = this.playerStore.recorded_program?.recorded_video?.duration || 0;
            
            if (this.start_time_seconds >= this.end_time_seconds) {
                this.end_time_seconds = Math.min(this.start_time_seconds + 1, duration);
                this.end_time_display = this.formatTime(this.end_time_seconds);
            }

            if (this.main_player) {
                this.main_player.seek(this.start_time_seconds);
            }
        },
        onEndTimeSliderChange() {
            this.end_time_display = this.formatTime(this.end_time_seconds);
            this.validateTimeRange();
            
            if (this.end_time_seconds <= this.start_time_seconds) {
                this.start_time_seconds = Math.max(this.end_time_seconds - 1, 0);
                this.start_time_display = this.formatTime(this.start_time_seconds);
            }
        },
        formatTime(seconds: number): string {
            const h = Math.floor(seconds / 3600);
            const m = Math.floor((seconds % 3600) / 60);
            const s = Math.floor(seconds % 60);
            return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
        },
        parseTime(timeStr: string): number {
            const parts = timeStr.split(':').map(p => parseInt(p) || 0);
            if (parts.length === 3) {
                return parts[0] * 3600 + parts[1] * 60 + parts[2];
            }
            return 0;
        },
        onStartTimeInput(event: Event) {
            this.start_time_seconds = this.parseTime((event.target as HTMLInputElement).value);
            this.validateTimeRange();
        },
        onEndTimeInput(event: Event) {
            this.end_time_seconds = this.parseTime((event.target as HTMLInputElement).value);
            this.validateTimeRange();
        },
        validateTimeRange() {
            this.error_message = '';
            const duration = this.playerStore.recorded_program?.recorded_video?.duration || 0;
            
            if (this.start_time_seconds < 0) {
                this.error_message = '開始時刻は0秒以上である必要があります';
            } else if (this.end_time_seconds <= this.start_time_seconds) {
                this.error_message = '終了時刻は開始時刻より後である必要があります';
            } else if (this.end_time_seconds > duration) {
                this.error_message = `終了時刻は動画の長さ（${this.formatTime(duration)}）以下である必要があります`;
            }
        },
        async startExport() {
            if (!this.isValidTimeRange) return;

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

            const task_id = await Videos.exportVideoClip(video_id, this.start_time_seconds, this.end_time_seconds);
            if (!task_id) {
                this.export_status = 'failed';
                this.status_detail = '書き出しの開始に失敗しました';
                return;
            }

            this.task_id = task_id;

            this.polling_interval = window.setInterval(async () => {
                if (!this.task_id) return;
                
                const status = await Videos.fetchVideoClipExportStatus(video_id, this.task_id);
                if (status) {
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
                }
            }, 2000);
        },
        async downloadClip() {
            if (!this.task_id) return;
            
            const video_id = this.playerStore.recorded_program?.id;
            if (!video_id) return;

            const success = await Videos.downloadVideoClip(video_id, this.task_id);
            if (success) {
                this.snackbarsStore.show('success', 'ダウンロードを開始しました', 5);
            }
        },
        async previewClip() {
            if (!this.task_id) return;
            
            const video_id = this.playerStore.recorded_program?.id;
            if (!video_id) return;

            // プレビュー用URLを開いてブラウザでプレビュー
            const preview_url = `/api/streams/video/${video_id}/clip-export/${this.task_id}/preview`;
            window.open(preview_url, '_blank');
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
}
</style>
