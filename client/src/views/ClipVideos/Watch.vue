<template>
	<Watch :playback_mode="'Video'" />
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent } from 'vue';

import Watch from '@/components/Watch/Watch.vue';
import ClipVideos from '@/services/ClipVideos';
import PlayerController from '@/services/player/PlayerController';
import Videos from '@/services/Videos';
import usePlayerStore from '@/stores/PlayerStore';
import useSettingsStore from '@/stores/SettingsStore';

// PlayerController のインスタンス
let player_controller: PlayerController | null = null;

export default defineComponent({
	name: 'Clip-Videos-Watch',
	components: {
		Watch,
	},
	computed: {
		...mapStores(usePlayerStore, useSettingsStore),
	},
	created() {
		this.init();
	},
	beforeRouteUpdate(to, from, next) {
		const destroy_promise = this.destroy();
		destroy_promise.then(() => this.init());
		next();
	},
	beforeUnmount() {
		this.destroy();
	},
	methods: {

		// 再生セッションを初期化する
		async init() {

			// URL 上のクリップ動画 ID が未定義なら実行しない
			if (this.$route.params.clip_video_id === undefined) {
				this.$router.push({ path: '/not-found/' });
				return;
			}

			const clip_video_id = parseInt(this.$route.params.clip_video_id as string, 10);
			if (Number.isNaN(clip_video_id) === true) {
				this.$router.push({ path: '/not-found/' });
				return;
			}

			// クリップ動画情報を取得
			const clip_video = await ClipVideos.fetchClipVideo(clip_video_id);
			if (clip_video === null) {
				this.$router.push({ path: '/not-found/' });
				return;
			}

			// クリップに紐づく録画番組情報を取得
			const recorded_program = await Videos.fetchVideo(clip_video.recorded_program.id);
			if (recorded_program === null) {
				this.$router.push({ path: '/not-found/' });
				return;
			}

			// PlayerStore を更新
			this.playerStore.recorded_program = recorded_program;
			this.playerStore.clip_video = clip_video;

			// PlayerController を初期化
			player_controller = new PlayerController('Video');
			await player_controller.init({
				default_quality: null,
				playback_rate: null,
				seek_seconds: clip_video.start_time,
			});
		},

		// 再生セッションを破棄する
		async destroy() {
			if (player_controller !== null) {
				await player_controller.destroy();
				player_controller = null;
			}
			this.playerStore.clip_video = null;
		},
	},
});

</script>
