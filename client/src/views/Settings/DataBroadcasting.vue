<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <SettingsBase>
        <h2 class="settings__heading">
            <a v-ripple class="settings__back-button" @click="$router.back()">
                <Icon icon="fluent:chevron-left-12-filled" width="27px" />
            </a>
            <svg width="27px" height="27px" viewBox="0 0 512 512">
                <path fill="currentColor" d="M248.039 381.326L355.039 67.8258C367.539 28.3257 395.039 34.3258 406.539 34.3258C431.039 34.3258 453.376 61.3258 441.039 96.8258C362.639 322.426 343.539 375.326 340.539 384.826C338.486 391.326 342.039 391.326 345.539 391.326C377.039 391.326 386.539 418.326 386.539 435.326C386.539 458.826 371.539 477.326 350.039 477.326H214.539C179.039 477.326 85.8269 431.3 88.0387 335.826C91.0387 206.326 192.039 183.326 243.539 183.326H296.539L265.539 272.326H243.539C185.539 272.326 174.113 314.826 176.039 334.326C180.039 374.826 215.039 389.814 237.039 390.326C244.539 390.5 246.039 386.826 248.039 381.326Z" />
            </svg>
            <span class="ml-2">データ放送</span>
        </h2>
        <div class="settings__content">
            <div class="settings__item settings__item--switch settings__item--sync-disabled">
                <label class="settings__item-heading" for="tv_show_data_broadcasting">テレビをみるときにデータ放送機能を利用する</label>
                <label class="settings__item-label" for="tv_show_data_broadcasting">
                    データ放送画面自体のオン/オフは、視聴画面右側のパネルからリモコンを表示した上で、リモコンの d ボタンから切り替えられます。<br>
                </label>
                <label class="settings__item-label" for="tv_show_data_broadcasting">
                    データ放送機能をオンにすると、視聴時の負荷が若干高くなります。データ放送を利用しない場合や、スペックの低い Android デバイスで動作が重い場合は、オフに設定してみてください。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="tv_show_data_broadcasting" hide-details
                    v-model="settingsStore.settings.tv_show_data_broadcasting">
                </v-switch>
            </div>
            <div class="settings__item settings__item--switch settings__item--sync-disabled">
                <label class="settings__item-heading" for="enable_internet_access_from_data_broadcasting">データ放送からのインターネットアクセスを有効にする</label>
                <label class="settings__item-label" for="enable_internet_access_from_data_broadcasting">
                    オンにすると、データ放送機能を利用する際に、データ放送からインターネットにアクセスできるようになります。<br>
                    たとえば紅白歌合戦の視聴者投票をはじめとした双方向番組に参加したり、ネット接続時限定のミニゲームが遊べるようになります。<br>
                </label>
                <label class="settings__item-label" for="enable_internet_access_from_data_broadcasting">
                    その一方で、<b>データ放送からのインターネットアクセスが有効な場合、あなたの視聴データがテレビ局に送信されることがあります。</b><br>
                    大半のチャンネルでは個別に視聴データの送信を無効化できますが、依然プライバシー上の問題が残ります。
                    通常はオフにしておき、双方向コンテンツを使うときだけオンにすることをおすすめします。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="enable_internet_access_from_data_broadcasting" hide-details
                    v-model="settingsStore.settings.enable_internet_access_from_data_broadcasting">
                </v-switch>
            </div>
            <v-divider class="mt-6"></v-divider>
            <div class="settings__item settings__item--sync-disabled" @submit.prevent>
                <label class="settings__item-heading">お住まいの郵便番号</label>
                <label class="settings__item-label">
                    ここで設定した郵便番号をもとに、データ放送の地域情報（ニュース・天気予報など）が表示されます。<br>
                    設定しない場合、データ放送の一部のコンテンツが利用できないことがあります。<br>
                </label>
                <v-text-field class="settings__item-form" color="primary" variant="outlined"
                    placeholder="郵便番号" :density="is_form_dense ? 'compact' : 'default'"
                    :rules="[data_broadcasting_zip_code_validation]" v-model="data_broadcasting_zip_code">
                </v-text-field>
            </div>
            <div class="settings__item settings__item--sync-disabled mt-2">
                <label class="settings__item-heading">お住まいの都道府県</label>
                <label class="settings__item-label">
                    ここで設定した都道府県をもとに、データ放送の地域情報（ニュース・天気予報など）が表示されます。<br>
                    設定しない場合、データ放送の一部のコンテンツが利用できないことがあります。<br>
                </label>
                <v-select class="settings__item-form" color="primary" variant="outlined" hide-details
                    :density="is_form_dense ? 'compact' : 'default'"
                    :items="data_broadcasting_prefectures" v-model="data_broadcasting_prefecture">
                </v-select>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading text-error-lighten-1">データ放送の保存データをリセット</div>
                <div class="settings__item-label">
                    このデバイス（ブラウザ）に保存されているデータ放送の保存データを、初期状態にリセット (消去) できます。<br>
                    保存データには、データ放送内のミニゲームの得点、プレゼント企画のスタンプ個数、設定などが含まれます。<br>
                    <strong class="text-error-lighten-1">保存データをリセットすると、元に戻すことはできません。十分ご注意ください。</strong><br>
                </div>
            </div>
            <v-btn class="settings__save-button bg-error mt-5" variant="flat" @click="resetNVRAMSettings()">
                <Icon icon="material-symbols:device-reset-rounded" class="mr-2" height="23px" />保存データをリセット
            </v-btn>
        </div>
    </SettingsBase>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent } from 'vue';

import Message from '@/message';
import useSettingsStore from '@/stores/SettingsStore';
import Utils from '@/utils';
import SettingsBase from '@/views/Settings/Base.vue';

// データ放送の NVRAM のうち、郵便番号/都道府県設定の保存に使う LocalStorage キーのプレフィックス
const NVRAM_LOCAL_STORAGE_PREFIX = 'KonomiTV-BMLBrowser_nvram_prefix=receiverinfo%2F';

export default defineComponent({
    name: 'Settings-DataBroadcasting',
    components: {
        SettingsBase,
    },
    data() {
        return {

            // フォームを小さくするかどうか
            is_form_dense: Utils.isSmartphoneHorizontal(),

            // データ放送向け郵便番号設定
            data_broadcasting_zip_code: '' as string,

            // データ放送向け郵便番号（日本）のバリデーション関数
            data_broadcasting_zip_code_validation: (value: string) => {
                if (value === '') {
                    return true;
                }
                if (value.match(/^[0-9]{3}-[0-9]{4}$/) === null) {
                    return '郵便番号は「000-0000」の形式で入力してください。';
                }
                return true;
            },

            // データ放送向け都道府県設定
            data_broadcasting_prefecture: '255-0b0' as string,
            data_broadcasting_prefectures: [
                {title: '未設定', value: '255-0b0'},
                {title: '西北海道', value: '2-0b000101101011'},
                {title: '東北海道', value: '1-0b000101101011'},
                {title: '青森県', value: '3-0b010001100111'},
                {title: '岩手県', value: '4-0b010111010100'},
                {title: '宮城県', value: '5-0b011101011000'},
                {title: '秋田県', value: '6-0b101011000110'},
                {title: '山形県', value: '7-0b111001001100'},
                {title: '福島県', value: '8-0b000110101110'},
                {title: '茨城県', value: '9-0b110001101001'},
                {title: '栃木県', value: '10-0b111000111000'},
                {title: '群馬県', value: '11-0b100110001011'},
                {title: '埼玉県', value: '12-0b011001001011'},
                {title: '千葉県', value: '13-0b000111000111'},
                {title: '東京都 (島部を除く)', value: '14-0b101010101100'},
                {title: '東京都島部 (伊豆・小笠原諸島)', value: '49-0b101010101100'},
                {title: '神奈川県', value: '15-0b010101101100'},
                {title: '新潟県', value: '16-0b010011001110'},
                {title: '富山県', value: '17-0b010100111001'},
                {title: '石川県', value: '18-0b011010100110'},
                {title: '福井県', value: '19-0b100100101101'},
                {title: '山梨県', value: '20-0b110101001010'},
                {title: '長野県', value: '21-0b100111010010'},
                {title: '岐阜県', value: '22-0b101001100101'},
                {title: '静岡県', value: '23-0b101001011010'},
                {title: '愛知県', value: '24-0b100101100110'},
                {title: '三重県', value: '25-0b001011011100'},
                {title: '滋賀県', value: '26-0b110011100100'},
                {title: '京都府', value: '27-0b010110011010'},
                {title: '大阪府', value: '28-0b110010110010'},
                {title: '兵庫県', value: '29-0b011001110100'},
                {title: '奈良県', value: '30-0b101010010011'},
                {title: '和歌山県', value: '31-0b001110010110'},
                {title: '鳥取県', value: '32-0b110100100011'},
                {title: '島根県', value: '33-0b001100011011'},
                {title: '岡山県', value: '34-0b001010110101'},
                {title: '広島県', value: '35-0b101100110001'},
                {title: '山口県', value: '36-0b101110011000'},
                {title: '徳島県', value: '37-0b111001100010'},
                {title: '香川県', value: '38-0b100110110100'},
                {title: '愛媛県', value: '39-0b000110011101'},
                {title: '高知県', value: '40-0b001011100011'},
                {title: '福岡県', value: '41-0b011000101101'},
                {title: '佐賀県', value: '42-0b100101011001'},
                {title: '長崎県', value: '43-0b101000101011'},
                {title: '熊本県', value: '44-0b100010100111'},
                {title: '大分県', value: '45-0b110010001101'},
                {title: '宮崎県', value: '46-0b110100011100'},
                {title: '鹿児島県 (南西諸島を除く)', value: '47-0b110101000101'},
                {title: '鹿児島県島部 (南西諸島の鹿児島県域)', value: '50-0b110101000101'},
                {title: '沖縄県', value: '48-0b001101110010'},
            ],
        };
    },
    computed: {
        ...mapStores(useSettingsStore),
    },
    watch: {
        async data_broadcasting_zip_code(new_value: string) {
            // バリデーションチェック
            // なぜか Vuetify のバリデーション機能を使うと一つ前の入力値のバリデーション結果が返ってきてしまう (?) ので、自前でチェックする
            if (this.data_broadcasting_zip_code_validation(new_value) !== true) {
                return;
            }
            // 郵便番号設定を LocalStorage に保存する
            if (new_value !== '') {
                // - を除去してから Base64 エンコードする
                const zip_code_raw = window.btoa(new_value.replace('-', ''));
                localStorage.setItem(`${NVRAM_LOCAL_STORAGE_PREFIX}zipcode`, zip_code_raw);
            } else {
                // 未設定の場合は LocalStorage から削除する
                localStorage.removeItem(`${NVRAM_LOCAL_STORAGE_PREFIX}zipcode`);
            }
        },
        data_broadcasting_prefecture(new_value: string) {
            // 都道府県設定を LocalStorage に保存する
            if (new_value !== '255-0b0') {
                const value = new_value.split('-0b');
                const prefecture_number = parseInt(value[0]);
                const prefecture_raw = window.btoa(String.fromCharCode(prefecture_number));
                localStorage.setItem(`${NVRAM_LOCAL_STORAGE_PREFIX}prefecture`, prefecture_raw);
                const region_code_number = parseInt(value[1], 2);  // 2進数の文字列を10進数の数値に変換する
                const region_code_raw = window.btoa(String.fromCharCode(region_code_number >> 8, region_code_number & 0xff));
                localStorage.setItem(`${NVRAM_LOCAL_STORAGE_PREFIX}regioncode`, region_code_raw);
            } else {
                // 未設定の場合は LocalStorage から削除する
                localStorage.removeItem(`${NVRAM_LOCAL_STORAGE_PREFIX}prefecture`);
                localStorage.removeItem(`${NVRAM_LOCAL_STORAGE_PREFIX}regioncode`);
            }
        }
    },
    created() {
        // 郵便番号設定を LocalStorage から読み込む
        const zip_code_raw = localStorage.getItem(`${NVRAM_LOCAL_STORAGE_PREFIX}zipcode`);
        if (zip_code_raw) {
            try {
                // 3文字目と4文字目の間に - を挿入する
                this.data_broadcasting_zip_code = window.atob(zip_code_raw);
                this.data_broadcasting_zip_code = this.data_broadcasting_zip_code.slice(0, 3) + '-' + this.data_broadcasting_zip_code.slice(3);
            } catch (error) {
                // 何もしない
            }
        }
        // 都道府県設定を LocalStorage から読み込む
        // 現在設定されている都道府県を特定するだけなら regioncode は不要なので、省略している
        const prefecture_raw = localStorage.getItem(`${NVRAM_LOCAL_STORAGE_PREFIX}prefecture`);
        if (prefecture_raw) {
            try {
                const prefecture = window.atob(prefecture_raw).charCodeAt(0);
                for (const item of this.data_broadcasting_prefectures) {
                    if (item.value.startsWith(`${prefecture}-`)) {
                        this.data_broadcasting_prefecture = item.value;
                        break;
                    }
                }
            } catch (error) {
                // 何もしない
            }
        }
    },
    methods: {
        resetNVRAMSettings() {
            // KonomiTV-BMLBrowser_nvram_ から始まる LocalStorage の項目をすべて削除する
            for (const key in localStorage) {
                if (key.startsWith('KonomiTV-BMLBrowser_nvram_')) {
                    localStorage.removeItem(key);
                }
            }
            this.data_broadcasting_zip_code = '';
            this.data_broadcasting_prefecture = '255-0b0';
            Message.success('データ放送の保存データをリセットしました。');
        }
    }
});

</script>