
import DPlayer from 'dplayer';

import PlayerManager from '@/services/player/PlayerManager';
import usePlayerStore from '@/stores/PlayerStore';
import useSettingsStore from '@/stores/SettingsStore';


/**
 * 録画番組の CM 区間を自動でスキップする PlayerManager
 * ビデオ視聴時のみ動作し、CM 区間が分かっている録画番組で CM に入ると本編の続きまで自動でシークする
 */
class CMSkipManager implements PlayerManager {

    // ユーザー操作により DPlayer 側で画質が切り替わった際、この PlayerManager の再起動が必要かどうかを PlayerController に示す値
    // DPlayer は画質切り替え時に video 要素を作り直すため、再起動して新しい video 要素にイベントを登録し直す
    public readonly restart_required_when_quality_switched = true;

    // CM 区間の終了位置のこの秒数手前までに入った場合のみスキップする
    // 終了間際に入った場合はスキップするほどでもなく、シーク直後の再判定による不安定な動作も避けられる
    private static readonly SKIP_END_MARGIN = 0.3;

    // 「戻る」ボタンを含む通知を表示しておく秒数
    private static readonly NOTIFICATION_TIMEOUT = 6;

    // DPlayer のインスタンス
    // 設計上コンストラクタ以降で変更すべきでないため readonly にしている
    private readonly player: DPlayer;

    // 再生モード (Live: ライブ視聴, Video: ビデオ視聴)
    private readonly playback_mode: 'Live' | 'Video';

    // CM 区間のリスト (秒単位)
    private cm_sections: {start_time: number, end_time: number}[] = [];

    // 自動スキップの対象外にする CM 区間のインデックスの集合
    // ユーザーが CM 区間内にシークした場合や、スキップ直後に「戻る」を押した場合に追加される
    // 再生位置がその CM 区間から出たら削除される
    private ignored_sections = new Set<number>();

    // このマネージャーが開始したシークが完了 (seeked) するまでの間 true になる
    // この間は再入を避けるため、新たなスキップを保留する
    private programmatic_seeking = false;

    // programmatic_seeking が何らかの理由で解除されなくなった場合に備えた保険のタイマー
    private seek_guard_timer: ReturnType<typeof setTimeout> | null = null;

    // 「戻る」ボタンを含む通知の要素とその自動非表示タイマー
    private notification_element: HTMLElement | null = null;
    private notification_timer: ReturnType<typeof setTimeout> | null = null;

    // イベントハンドラーの参照 (destroy() で解除するために保持する)
    private readonly on_timeupdate = this.handleTimeUpdate.bind(this);
    private readonly on_seeking = this.handleSeeking.bind(this);
    private readonly on_seeked = this.endProgrammaticSeek.bind(this);

    // イベントを登録した video 要素 (DPlayer の on() は解除できないため、video 要素に直接登録している)
    private video: HTMLVideoElement | null = null;

    // 破棄済みかどうか
    private destroyed = false;

    /**
     * コンストラクタ
     * @param player DPlayer のインスタンス
     * @param playback_mode 再生モード (Live: ライブ視聴, Video: ビデオ視聴)
     */
    constructor(player: DPlayer, playback_mode: 'Live' | 'Video') {
        this.player = player;
        this.playback_mode = playback_mode;
    }


    /**
     * CM 区間を取得し、再生位置の監視を開始する
     */
    public async init(): Promise<void> {
        const player_store = usePlayerStore();

        // 破棄済みかどうかのフラグを下ろす
        this.destroyed = false;

        // CM 区間があるのは録画番組だけなので、ビデオ視聴時のみ動作する
        if (this.playback_mode !== 'Video') {
            return;
        }

        // CM 区間が1つもない録画番組では、再生位置を監視せずに初期化を終える
        const cm_sections = player_store.recorded_program?.recorded_video?.cm_sections ?? [];
        if (cm_sections.length === 0) {
            console.log('[CMSkipManager] Initialized. (No CM sections.)');
            return;
        }
        this.cm_sections = cm_sections;

        // 無視対象の CM 区間とシーク中のフラグを初期状態に戻す
        // 初期化時点ですでに CM 区間内にいる場合 (録画マージンの直後や、視聴履歴からの再開位置が CM だった場合など) も、最初の timeupdate でスキップする
        // ただし、再生開始位置へのシークや画質切り替え後の再生位置の復元で発生する seeking イベントがこの初期化より後に届くと、
        // 利用者のシークと同じ扱いになり、その CM 区間はそのまま再生される
        this.ignored_sections.clear();
        this.programmatic_seeking = false;

        // 再生位置の変化とシークを監視する
        this.video = this.player.video;
        this.video.addEventListener('seeking', this.on_seeking);
        this.video.addEventListener('seeked', this.on_seeked);
        this.video.addEventListener('timeupdate', this.on_timeupdate);

        console.log(`[CMSkipManager] Initialized. (${cm_sections.length} CM sections.)`);
    }


    /**
     * 再生位置が変わったときに、CM 区間に入っていればスキップする
     */
    private handleTimeUpdate(): void {
        if (this.destroyed || this.programmatic_seeking) {
            return;
        }

        // 設定がオンのときだけスキップする (毎回設定を参照するので、再生中に切り替えても即座に反映される)
        const settings_store = useSettingsStore();
        if (settings_store.settings.video_cm_auto_skip !== true) {
            return;
        }

        const current_time = this.player.video.currentTime;
        const duration = this.player.video.duration;

        // 再生位置が CM 区間から出ていれば、その区間の無視を解除する
        this.updateIgnoredSections(current_time, false);

        for (let index = 0; index < this.cm_sections.length; index++) {
            const section = this.cm_sections[index];

            // 動画の最後まで続く CM 区間は、終了位置へシークするとループ再生で先頭に戻ってしまうため、そのまま再生する
            if (Number.isFinite(duration) && section.end_time >= duration - 1.0) {
                continue;
            }
            // ユーザーが自分でシークした CM 区間や、「戻る」を押した CM 区間は、そのまま再生する
            if (this.ignored_sections.has(index)) {
                continue;
            }
            // 再生位置が CM 区間内 (終了間際を除く) にあれば、本編の続きまでスキップする
            const is_after_section_start = section.start_time <= current_time;
            const is_before_skip_end = current_time < section.end_time - CMSkipManager.SKIP_END_MARGIN;
            if (is_after_section_start && is_before_skip_end) {
                this.skip(index);
                return;
            }
        }
    }


    /**
     * シーク開始時に、ユーザー操作によるシークで CM 区間内に移動した場合はその区間を無視対象にする
     */
    private handleSeeking(): void {
        if (this.destroyed || this.programmatic_seeking) {
            return;
        }
        this.updateIgnoredSections(this.player.video.currentTime, true);
    }


    /**
     * 再生位置から外れた CM 区間の無視を解除し、必要であれば現在の区間を無視対象に追加する
     * @param current_time 現在の再生位置 (秒)
     * @param add_current 現在の再生位置を含む CM 区間を無視対象に追加するかどうか
     */
    private updateIgnoredSections(current_time: number, add_current: boolean): void {
        for (let index = 0; index < this.cm_sections.length; index++) {
            const section = this.cm_sections[index];
            const inside = section.start_time <= current_time && current_time < section.end_time;
            if (inside && add_current) {
                this.ignored_sections.add(index);
            } else if (!inside) {
                this.ignored_sections.delete(index);
            }
        }
    }


    /**
     * 指定した CM 区間の終了位置までシークし、「戻る」ボタン付きの通知を表示する
     * @param index スキップする CM 区間のインデックス
     */
    private skip(index: number): void {
        const section = this.cm_sections[index];
        console.log(`[CMSkipManager] Skipping CM section: ${section.start_time} - ${section.end_time}`);
        // スキップした区間を、再生位置がその区間から出るまで無視対象に加えておく
        // シーク先が何らかの理由で区間の終了位置よりわずかに手前 (CM 区間内) になった場合に、スキップを無限に繰り返すのを防ぐ
        // 正常に区間外へシークできた場合は、次の timeupdate で updateIgnoredSections() により無視対象から外れる
        this.ignored_sections.add(index);
        this.programmaticSeek(section.end_time);
        this.showNotification(Math.round(section.end_time - section.start_time), () => {
            // 「戻る」: CM の頭に戻り、この区間はそのまま再生する
            this.ignored_sections.add(index);
            this.programmaticSeek(section.start_time);
            this.hideNotification();
        });
    }


    /**
     * このマネージャーからのシークを実行する
     * seeked イベントが発生するまでは新たなスキップを行わない
     * @param seconds シーク先の再生位置 (秒)
     */
    private programmaticSeek(seconds: number): void {
        this.programmatic_seeking = true;
        // seeked が発生しなかった場合に備え、5秒後にはフラグを下ろす
        if (this.seek_guard_timer !== null) {
            clearTimeout(this.seek_guard_timer);
        }
        this.seek_guard_timer = setTimeout(() => this.endProgrammaticSeek(), 5000);
        this.player.seek(seconds);
    }


    /**
     * このマネージャーが開始したシークの実行中フラグを下ろす
     * seeked イベントのハンドラーと、保険のタイマーから呼ばれる
     */
    private endProgrammaticSeek(): void {
        this.programmatic_seeking = false;
        if (this.seek_guard_timer !== null) {
            clearTimeout(this.seek_guard_timer);
            this.seek_guard_timer = null;
        }
    }


    /**
     * プレイヤー内に「戻る」ボタン付きの通知を表示する
     * 既存の Snackbar や DPlayer の notice にはボタンを置けないため、プレイヤーのコンテナ内に簡易的なオーバーレイを置いている
     * @param skipped_seconds スキップした秒数
     * @param on_back 「戻る」が押されたときに実行する関数
     */
    private showNotification(skipped_seconds: number, on_back: () => void): void {
        this.hideNotification();

        const element = document.createElement('div');
        element.style.cssText = [
            'position: absolute',
            'right: 20px',
            'bottom: 80px',
            'z-index: 10',
            'display: flex',
            'align-items: center',
            'gap: 12px',
            'padding: 8px 8px 8px 16px',
            'border-radius: 6px',
            'background: rgba(0, 0, 0, 0.75)',
            'color: #fff',
            'font-size: 14px',
            'pointer-events: auto',
        ].join(';');

        const text = document.createElement('span');
        text.textContent = `CM をスキップしました（${skipped_seconds} 秒）`;
        element.appendChild(text);

        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = '戻る';
        button.style.cssText = [
            'padding: 4px 12px',
            'border-radius: 4px',
            'background: #E64F97',
            'color: #fff',
            'font-size: 14px',
            'font-weight: bold',
            'cursor: pointer',
        ].join(';');
        button.addEventListener('click', (event) => {
            event.stopPropagation();
            on_back();
        });
        // 通知内のクリックは、プレイヤー側のクリック (再生/一時停止の切り替えなど) に伝わる前に止める
        element.addEventListener('click', (event) => event.stopPropagation());
        element.appendChild(button);

        this.player.container.appendChild(element);
        this.notification_element = element;
        this.notification_timer = setTimeout(() => this.hideNotification(), CMSkipManager.NOTIFICATION_TIMEOUT * 1000);
    }


    /**
     * 「戻る」ボタン付きの通知を消す
     */
    private hideNotification(): void {
        if (this.notification_timer !== null) {
            clearTimeout(this.notification_timer);
            this.notification_timer = null;
        }
        if (this.notification_element !== null) {
            this.notification_element.remove();
            this.notification_element = null;
        }
    }


    /**
     * イベントハンドラー・タイマー・通知をすべて破棄する
     */
    public async destroy(): Promise<void> {
        this.destroyed = true;
        this.video?.removeEventListener('seeking', this.on_seeking);
        this.video?.removeEventListener('seeked', this.on_seeked);
        this.video?.removeEventListener('timeupdate', this.on_timeupdate);
        this.endProgrammaticSeek();
        this.hideNotification();
        this.video = null;
        this.cm_sections = [];
        this.ignored_sections.clear();
    }
}

export default CMSkipManager;
