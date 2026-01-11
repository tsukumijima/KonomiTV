<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <SettingsBase>
        <h2 class="settings__heading">
            <a v-ripple class="settings__back-button" @click="$router.back()">
                <Icon icon="fluent:chevron-left-12-filled" width="27px" />
            </a>
            <Icon icon="fluent:server-surface-16-filled" width="22px" />
            <span class="ml-2">サーバー設定</span>
        </h2>
        <div class="settings__description">
            サーバー設定を変更するには、管理者アカウントでログインしている必要があります。<br>
        </div>
        <div class="settings__description mt-1">
            [サーバー設定を更新] ボタンを押さずにこのページから離れると、変更内容は破棄されます。<br>
            変更を反映するには KonomiTV サーバーの再起動が必要です。<br>
        </div>
        <div class="settings__content" :class="{'settings__content--disabled': is_disabled}">
            <div class="settings__content-heading">
                <Icon icon="fa-solid:sliders-h" width="22px" style="padding: 0 3px;" />
                <span class="ml-2">全般</span>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">利用するバックエンド</div>
                <div class="settings__item-label">
                    EDCB・Mirakurun のいずれかを選択してください。<br>
                    バックエンドに Mirakurun が選択されているときは、録画予約機能は利用できません。<br>
                </div>
                <v-select class="settings__item-form" color="primary" variant="outlined" hide-details
                    :density="is_form_dense ? 'compact' : 'default'"
                    :items="['EDCB', 'Mirakurun']" v-model="server_settings.general.backend">
                </v-select>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">EDCB (EpgTimerNW) の TCP API の URL</div>
                <div class="settings__item-label">
                    バックエンドに EDCB が選択されているときに利用されます。<br>
                    tcp://edcb-namedpipe/ と指定すると、TCP API の代わりに名前付きパイプを使って通信します (ローカルのみ)。<br>
                </div>
                <div class="settings__item-label mt-1">
                    一部 Windows 環境では localhost の名前解決が遅いため、ストリーミング開始までの待機時間が長くなる場合があります。
                    EDCB と同じ PC に KonomiTV をインストールしている場合、localhost ではなく 127.0.0.1 の利用を推奨します。<br>
                </div>
                <v-text-field class="settings__item-form" color="primary" variant="outlined" hide-details
                    :density="is_form_dense ? 'compact' : 'default'"
                    v-model="server_settings.general.edcb_url">
                </v-text-field>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">Mirakurun / mirakc の HTTP API の URL</div>
                <div class="settings__item-label">
                    バックエンドに Mirakurun が選択されているときに利用されます。<br>
                </div>
                <div class="settings__item-label mt-1">
                    一部 Windows 環境では localhost の名前解決が遅いため、ストリーミング開始までの待機時間が長くなる場合があります。
                    Mirakurun / mirakc と同じ PC に KonomiTV をインストールしている場合、localhost ではなく 127.0.0.1 の利用を推奨します。<br>
                </div>
                <v-text-field class="settings__item-form" color="primary" variant="outlined" hide-details
                    :density="is_form_dense ? 'compact' : 'default'"
                    v-model="server_settings.general.mirakurun_url">
                </v-text-field>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">利用するエンコーダー</div>
                <div class="settings__item-label">
                    FFmpeg はソフトウェアエンコーダーです。<br>
                    すべての PC で利用できますが、CPU に多大な負荷がかかり、パフォーマンスが悪いです。<br>
                </div>
                <div class="settings__item-label mt-1">
                    QSVEncC・NVEncC・VCEEncC・rkmppenc はハードウェアエンコーダーです。<br>
                    CPU 負荷が低く、パフォーマンスがとても高いです（おすすめ）。<br>
                </div>
                <v-select class="settings__item-form" color="primary" variant="outlined" hide-details
                    :density="is_form_dense ? 'compact' : 'default'"
                    :items="[
                        {title: 'FFmpeg : ソフトウェアエンコーダー', value: 'FFmpeg'},
                        {title: 'QSVEncC : Intel Graphics 搭載 CPU / Intel Arc GPU で利用可能', value: 'QSVEncC'},
                        {title: 'NVEncC : NVIDIA GPU で利用可能', value: 'NVEncC'},
                        {title: 'VCEEncC : AMD GPU で利用可能', value: 'VCEEncC'},
                        {title: 'rkmppenc : Rockchip RK3588 系 SoC 搭載 SBC で利用可能', value: 'rkmppenc'}
                    ]"
                    v-model="server_settings.general.encoder">
                </v-select>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">番組情報の更新間隔 (分)</div>
                <div class="settings__item-label">
                    番組情報を EDCB または Mirakurun / mirakc から取得する間隔を設定します。デフォルトは 5 (分) です。<br>
                </div>
                <v-slider class="settings__item-form" color="primary" show-ticks="always" thumb-label hide-details
                    :min="0.5" :max="60" :step="0.5"
                    :density="is_form_dense ? 'compact' : 'default'"
                    v-model="server_settings.general.program_update_interval">
                </v-slider>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="debug">デバッグモードを有効にする</label>
                <label class="settings__item-label" for="debug">
                    有効にすると、デバッグログも出力されるようになります。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="debug" hide-details
                    v-model="server_settings.general.debug">
                </v-switch>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="debug_encoder">エンコーダーのログを有効にする</label>
                <label class="settings__item-label" for="debug_encoder">
                    有効にすると、ライブ視聴時のエンコーダーのログが KonomiTV/server/logs/ 以下に保存されます。<br>
                    さらにデバッグモード有効時は、サーバーログにエンコーダーのログがリアルタイム出力されます。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="debug_encoder" hide-details
                    v-model="server_settings.general.debug_encoder">
                </v-switch>
            </div>
            <div class="settings__content-heading mt-6">
                <Icon icon="fluent:server-surface-16-filled" width="22px" />
                <span class="ml-2">サーバー</span>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">KonomiTV サーバーのリッスンポート</div>
                <div class="settings__item-label">
                    デフォルトのリッスンポートは 7000 です。<br>
                </div>
                <v-text-field class="settings__item-form" color="primary" variant="outlined" hide-details
                    :density="is_form_dense ? 'compact' : 'default'"
                    v-model="server_settings.server.port">
                </v-text-field>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">HTTPS リバースプロキシのカスタム HTTPS 証明書/秘密鍵ファイルへの絶対パス</div>
                <div class="settings__item-label">
                    設定すると、カスタム HTTPS 証明書を使って HTTPS リバースプロキシを開始します。<br>
                    カスタム HTTPS 証明書を有効化すると、https://192-168-x-xx.local.konomi.tv:7000/ の URL では KonomiTV にアクセスできなくなります。<br>
                    基本空欄のままで問題ありません。HTTPS 証明書について詳細に理解している方のみ設定してください。<br>
                </div>
                <v-text-field class="settings__item-form" color="primary" variant="outlined" hide-details
                    label="例: C:\path\to\cert.pem"
                    :density="is_form_dense ? 'compact' : 'default'"
                    v-model="server_settings.server.custom_https_certificate">
                </v-text-field>
                <v-text-field class="settings__item-form" color="primary" variant="outlined" hide-details
                    label="例: C:\path\to\key.pem"
                    :density="is_form_dense ? 'compact' : 'default'"
                    v-model="server_settings.server.custom_https_private_key">
                </v-text-field>
            </div>
            <div class="settings__content-heading mt-6">
                <Icon icon="fluent:tv-20-filled" width="22px" />
                <span class="ml-2">テレビのライブストリーミング</span>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="always_receive_tv_from_mirakurun">常に Mirakurun / mirakc から放送波を受信する</label>
                <label class="settings__item-label" for="always_receive_tv_from_mirakurun">
                    利用するバックエンドが EDCB のとき、常に Mirakurun / mirakc から放送波を受信するかを設定します。
                    バックエンドに Mirakurun が選択されているときは効果がありません。<br>
                </label>
                <label class="settings__item-label mt-1" for="always_receive_tv_from_mirakurun">
                    KonomiTV から EDCB と Mirakurun / mirakc 両方にアクセスできる必要があります。<br>
                    EDCB はチューナー起動やチャンネル切り替えに時間がかかるため、Mirakurun / mirakc が利用できる環境であれば、この設定を有効にするとより快適に使えます。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="always_receive_tv_from_mirakurun" hide-details
                    v-model="server_settings.general.always_receive_tv_from_mirakurun">
                </v-switch>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">チャンネル表示・選局で優先するエリア (地デジ)</div>
                <div class="settings__item-label">
                    複数の地域の放送波が受信できる環境で、リモコン番号が同じチャンネルが複数ある場合に、どのエリアのチャンネルを優先して表示・選局するかを設定します。デフォルトは未設定です。<br>
                </div>
                <div class="settings__item-label mt-1">
                    優先エリアのチャンネルは枝番なし (例: Ch:011) で、それ以外のチャンネルは枝番付き (例: Ch:011-1) で表示されます。キーボードショートカットやリモコンボタンでの選局時も、優先エリアのチャンネルが選局されます。<br>
                </div>
                <div class="settings__item-label mt-1">
                    設定しない場合は、(ネットワークID)-(サービスID) の数値順で優先順位が決まります。<br>
                </div>
                <v-select class="settings__item-form" color="primary" variant="outlined" hide-details
                    :density="is_form_dense ? 'compact' : 'default'"
                    :items="preferred_terrestrial_region_options"
                    v-model="server_settings.tv.preferred_terrestrial_region">
                </v-select>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">誰も見ていないチャンネルのエンコードタスクを維持する秒数</div>
                <div class="settings__item-label">
                    10 秒に設定したなら、10 秒間誰も見ていない状態が継続したらエンコードタスク（エンコーダー）を終了します。<br>
                </div>
                <div class="settings__item-label mt-1">
                    0 秒に設定すると、ネット回線が瞬断したりリロードしただけでチューナーとエンコーダーの再起動が必要になり、再生復帰までに時間がかかります。余裕をもたせておく事をおすすめします。<br>
                </div>
                <v-slider class="settings__item-form" color="primary" show-ticks="always" thumb-label hide-details
                    :min="0" :max="60" :step="1"
                    :density="is_form_dense ? 'compact' : 'default'"
                    v-model="server_settings.tv.max_alive_time">
                </v-slider>
            </div>
            <div class="settings__content-heading mt-6">
                <Icon icon="fluent:movies-and-tv-20-filled" width="22px" />
                <span class="ml-2">ビデオのオンデマンドストリーミング</span>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">録画済み番組の保存先フォルダの絶対パス</div>
                <div class="settings__item-label" style="padding-bottom: 2px;">
                    指定フォルダ以下に保存されている MPEG-TS 形式の録画ファイルを KonomiTV サーバーが自動的に見つけ出し、メタデータの解析とサムネイルの作成を行います。<br>
                    解析が完了すると、録画番組一覧から再生できるようになります。<br>
                </div>
                <div class="settings__item-label mt-1" style="padding-bottom: 2px;">
                    複数の保存先フォルダを指定できます。フォルダやファイルのシンボリックリンクにも対応しています。<br>
                    シンボリックリンクは実体のパスに変換されるため、同じ録画ファイルが重複スキャンされることはありません。<br>
                </div>
                <div v-for="(folder, index) in server_settings.video.recorded_folders" :key="'recorded-folder-' + index">
                    <div class="d-flex align-center mt-3">
                        <v-text-field class="settings__item-form mt-0" color="primary" variant="outlined" hide-details
                            placeholder="例: E:\TV-Record"
                            :density="is_form_dense ? 'compact' : 'default'"
                            v-model="server_settings.video.recorded_folders[index]">
                        </v-text-field>
                        <button v-ripple class="settings__item-delete-button"
                            @click="server_settings.video.recorded_folders.splice(index, 1)">
                            <svg class="iconify iconify--fluent" width="20px" height="20px" viewBox="0 0 16 16">
                                <path fill="currentColor" d="M7 3h2a1 1 0 0 0-2 0ZM6 3a2 2 0 1 1 4 0h4a.5.5 0 0 1 0 1h-.564l-1.205 8.838A2.5 2.5 0 0 1 9.754 15H6.246a2.5 2.5 0 0 1-2.477-2.162L2.564 4H2a.5.5 0 0 1 0-1h4Zm1 3.5a.5.5 0 0 0-1 0v5a.5.5 0 0 0 1 0v-5ZM9.5 6a.5.5 0 0 0-.5.5v5a.5.5 0 0 0 1 0v-5a.5.5 0 0 0-.5-.5Z"></path>
                            </svg>
                        </button>
                    </div>
                </div>
                <v-btn class="mt-3" color="background-lighten-2" variant="flat" height="40px"
                    @click="server_settings.video.recorded_folders.push('')">
                    <Icon icon="fluent:add-12-filled" height="17px" />
                    <span class="ml-1">保存先フォルダを追加</span>
                </v-btn>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">録画フォルダのスキャン対象から除外するフォルダの絶対パス</div>
                <div class="settings__item-label" style="padding-bottom: 2px;">
                    録画フォルダ以下にある一時フォルダなど、スキャン対象から除外したいサブフォルダを指定できます。<br>
                </div>
                <div class="settings__item-label mt-1" style="padding-bottom: 2px;">
                    シンボリックリンク解決前のパスと、解決後の実体パスの両方で前方一致判定を行います。<br>
                    例えば、<code>E:\TV-Record\Temp</code> を指定すると、そのサブフォルダ以下の録画ファイルはスキャン対象から除外されます。<br>
                </div>
                <div v-for="(pattern, index) in server_settings.video.exclude_scan_paths" :key="'exclude-pattern-' + index">
                    <div class="d-flex align-center mt-3">
                        <v-text-field class="settings__item-form mt-0" color="primary" variant="outlined" hide-details
                            placeholder="例: E:\TV-Record\Trash"
                            :density="is_form_dense ? 'compact' : 'default'"
                            v-model="server_settings.video.exclude_scan_paths[index]">
                        </v-text-field>
                        <button v-ripple class="settings__item-delete-button"
                            @click="server_settings.video.exclude_scan_paths.splice(index, 1)">
                            <svg class="iconify iconify--fluent" width="20px" height="20px" viewBox="0 0 16 16">
                                <path fill="currentColor" d="M7 3h2a1 1 0 0 0-2 0ZM6 3a2 2 0 1 1 4 0h4a.5.5 0 0 1 0 1h-.564l-1.205 8.838A2.5 2.5 0 0 1 9.754 15H6.246a2.5 2.5 0 0 1-2.477-2.162L2.564 4H2a.5.5 0 0 1 0-1h4Zm1 3.5a.5.5 0 0 0-1 0v5a.5.5 0 0 0 1 0v-5ZM9.5 6a.5.5 0 0 0-.5.5v5a.5.5 0 0 0 1 0v-5a.5.5 0 0 0-.5-.5Z"></path>
                            </svg>
                        </button>
                    </div>
                </div>
                <v-btn class="mt-3" color="background-lighten-2" variant="flat" height="40px"
                    @click="server_settings.video.exclude_scan_paths.push('')">
                    <Icon icon="fluent:add-12-filled" height="17px" />
                    <span class="ml-1">除外フォルダを追加</span>
                </v-btn>
            </div>
            <div class="settings__content-heading mt-6">
                <Icon icon="fluent:image-multiple-16-filled" width="22px" />
                <span class="ml-2">キャプチャ</span>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">アップロードしたキャプチャ画像の保存先フォルダの絶対パス</div>
                <div class="settings__item-label">
                    <router-link class="link" to="/settings/capture">[キャプチャ]</router-link> → [キャプチャの保存先] で [KonomiTV サーバーにアップロード] または
                    [ブラウザでのダウンロードと、KonomiTV サーバーへのアップロードを両方行う] が選択されているときに利用されます。<br>
                </div>
                <div class="settings__item-label mt-1" style="padding-bottom: 2px;">
                    複数の保存先フォルダを指定できます。<br>
                    先頭から順に利用され、保存先フォルダがいっぱいになったら次の保存先フォルダに保存されます。<br>
                </div>
                <div v-for="(folder, index) in server_settings.capture.upload_folders" :key="'upload-folder-' + index">
                    <div class="d-flex align-center mt-3">
                        <v-text-field class="settings__item-form mt-0" color="primary" variant="outlined" hide-details
                            placeholder="例: E:\TV-Capture"
                            :density="is_form_dense ? 'compact' : 'default'"
                            v-model="server_settings.capture.upload_folders[index]">
                        </v-text-field>
                        <button v-ripple class="settings__item-delete-button"
                            @click="server_settings.capture.upload_folders.splice(index, 1)">
                            <svg class="iconify iconify--fluent" width="20px" height="20px" viewBox="0 0 16 16">
                                <path fill="currentColor" d="M7 3h2a1 1 0 0 0-2 0ZM6 3a2 2 0 1 1 4 0h4a.5.5 0 0 1 0 1h-.564l-1.205 8.838A2.5 2.5 0 0 1 9.754 15H6.246a2.5 2.5 0 0 1-2.477-2.162L2.564 4H2a.5.5 0 0 1 0-1h4Zm1 3.5a.5.5 0 0 0-1 0v5a.5.5 0 0 0 1 0v-5ZM9.5 6a.5.5 0 0 0-.5.5v5a.5.5 0 0 0 1 0v-5a.5.5 0 0 0-.5-.5Z"></path>
                            </svg>
                        </button>
                    </div>
                </div>
                <v-btn class="mt-3" color="background-lighten-2" variant="flat" height="40px"
                    @click="server_settings.capture.upload_folders.push('')">
                    <Icon icon="fluent:add-12-filled" height="17px" />
                    <span class="ml-1">保存先フォルダを追加</span>
                </v-btn>
            </div>
            <v-btn class="settings__save-button bg-secondary mt-6" variant="flat" @click="updateServerSettings()">
                <Icon icon="fluent:save-16-filled" class="mr-2" height="23px" />サーバー設定を更新
            </v-btn>
            <div class="settings__content-heading mt-8">
                <Icon icon="fluent:person-board-20-filled" width="22px" />
                <span class="ml-2">アカウント</span>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">アカウントの管理</div>
                <div class="settings__item-label">
                    現在 KonomiTV に登録されているすべてのアカウントの一覧の確認、管理者権限の付与/剥奪、アカウントの削除ができます。<br>
                </div>
                <div class="settings__item-label mt-1">
                    ログイン中ユーザーの設定変更は、別途 <router-link class="link" to="/settings/account">アカウント設定画面</router-link> から行ってください。<br>
                </div>
            </div>
            <v-btn class="settings__save-button mt-4" variant="flat" @click="account_manage_settings_modal = !account_manage_settings_modal">
                <Icon icon="fluent:person-board-20-filled" height="20px" />
                <span class="ml-1">アカウントの管理設定を開く</span>
            </v-btn>
        </div>
        <div class="settings__content">
            <div class="settings__content-heading mt-8">
                <Icon icon="fluent:wrench-settings-20-filled" width="22px" />
                <span class="ml-2">メンテナンス</span>
            </div>
        </div>
        <div class="settings__content" :class="{'settings__content--disabled': is_disabled}">
            <div class="settings__item">
                <div class="settings__item-heading">サーバーログの表示</div>
                <div class="settings__item-label">
                    KonomiTV サーバーの動作ログとアクセスログをリアルタイムで表示します。<br>
                    サーバーの動作状況の確認やトラブルシューティングに役立ちます。<br>
                </div>
            </div>
            <v-btn class="settings__save-button mt-5" color="background-lighten-2" variant="flat"
                @click="server_log_dialog = !server_log_dialog">
                <Icon icon="fluent:document-text-16-regular" height="20px" />
                <span class="ml-2">サーバーログを表示</span>
            </v-btn>
        </div>
        <div class="settings__content">
            <div class="settings__item">
                <div class="settings__item-heading">KonomiTV のデータベースを更新</div>
                <div class="settings__item-label">
                    KonomiTV のデータベースに保存されている、チャンネル情報・番組情報・Twitter アカウント情報などの外部 API に依存するデータをすべて更新します。<br>
                    即座に外部 API からのデータ更新を反映させたいときに利用してください。<br>
                </div>
            </div>
            <v-btn class="settings__save-button mt-5" color="background-lighten-2" variant="flat"
                @click="updateDatabase()">
                <Icon icon="iconoir:database-backup" height="20px" />
                <span class="ml-2">データベースを更新</span>
            </v-btn>
            <div class="settings__item">
                <div class="settings__item-heading">録画フォルダの一括スキャンを手動実行</div>
                <div class="settings__item-label">
                    録画フォルダ内のファイルは、通常 KonomiTV サーバーの起動時に自動的にスキャンされます。<br>
                    録画ファイルが KonomiTV に正しく反映されていない場合にのみ実行してみてください。<br>
                </div>
                <div class="settings__item-label mt-1">
                    <strong>大量の録画ファイルが保存されている環境では、処理完了まで数時間〜数日以上かかることがあります。</strong><br>
                </div>
            </div>
            <v-btn class="settings__save-button mt-5" color="background-lighten-2" variant="flat"
                @click="runBatchScan()">
                <Icon icon="fluent:folder-sync-20-regular" height="20px" />
                <span class="ml-2">録画フォルダの一括スキャンを手動実行</span>
            </v-btn>
            <div class="settings__item">
                <div class="settings__item-heading">録画ファイルのバックグラウンド解析タスクを再実行</div>
                <div class="settings__item-label">
                    録画ファイルのメタデータ解析やサムネイル作成が完了していない場合に、これらの処理を再度実行します。<br>
                    PC のシャットダウンなどで途中で中断してしまった場合は、このボタンから処理を再開できます。<br>
                </div>
                <div class="settings__item-label mt-1">
                    <strong>大量の録画ファイルが保存されている環境では、処理完了まで数時間〜数日以上かかることがあります。</strong><br>
                </div>
            </div>
            <v-btn class="settings__save-button mt-5" color="background-lighten-2" variant="flat"
                @click="startBackgroundAnalysis()">
                <Icon icon="fluent:book-arrow-clockwise-20-regular" height="20px" />
                <span class="ml-2">バックグラウンド解析タスクを再実行</span>
            </v-btn>
        </div>
        <div class="settings__content" :class="{'settings__content--disabled': is_disabled}">
            <div class="settings__item">
                <div class="settings__item-heading text-error-lighten-1">KonomiTV サーバーを再起動</div>
                <div class="settings__item-label">
                    KonomiTV サーバーを再起動します。サーバー設定の変更を反映するには再起動が必要です。<br>
                    <strong>再起動を実行すると、すべての視聴中セッションが切断されます。</strong>十分注意してください。<br>
                </div>
            </div>
            <v-btn class="settings__save-button bg-error mt-5" variant="flat"
                @click="restartServer()">
                <Icon icon="fluent:arrow-counterclockwise-20-filled" height="20px" />
                <span class="ml-2">KonomiTV サーバーを再起動</span>
            </v-btn>
            <div class="settings__item">
                <div class="settings__item-heading text-error-lighten-1">KonomiTV サーバーをシャットダウン</div>
                <div class="settings__item-label">
                    KonomiTV サーバーをシャットダウンします。<br>
                    <strong>シャットダウンを実行すると、再度手動で KonomiTV サーバーを起動するまで KonomiTV にアクセスできなくなります。</strong>十分注意してください。<br>
                </div>
                <div class="settings__item-label mt-1">
                    なお、Linux 版 KonomiTV サーバーはプロセス管理を PM2 / Docker に委譲しているため、シャットダウン後は自動で再起動されます。完全にシャットダウンするには、PM2 / Docker 側でサービスを停止してください。<br>
                </div>
            </div>
            <v-btn class="settings__save-button bg-error mt-5" variant="flat"
                @click="shutdownServer()">
                <Icon icon="fluent:power-20-filled" height="20px" />
                <span class="ml-2">KonomiTV サーバーをシャットダウン</span>
            </v-btn>
        </div>
        <AccountManageSettings :modelValue="account_manage_settings_modal" @update:modelValue="account_manage_settings_modal = $event" />
        <ServerLogDialog :modelValue="server_log_dialog" @update:modelValue="server_log_dialog = $event" />
    </SettingsBase>
</template>
<script lang="ts" setup>

import { ref } from 'vue';

import AccountManageSettings from '@/components/Settings/AccountManageSettings.vue';
import ServerLogDialog from '@/components/Settings/ServerLogDialog.vue';
import Message from '@/message';
import Maintenance from '@/services/Maintenance';
import Settings, { IServerSettings, IServerSettingsDefault } from '@/services/Settings';
import Version from '@/services/Version';
import useUserStore from '@/stores/UserStore';
import Utils from '@/utils';
import SettingsBase from '@/views/Settings/Base.vue';

// フォームを小さくするかどうか
const is_form_dense = Utils.isSmartphoneHorizontal();

// 優先する地デジのエリアの選択肢
const preferred_terrestrial_region_options = [
    { title: '未設定', value: null },
    { title: '北海道（札幌）', value: '北海道（札幌）' },
    { title: '北海道（函館）', value: '北海道（函館）' },
    { title: '北海道（旭川）', value: '北海道（旭川）' },
    { title: '北海道（帯広）', value: '北海道（帯広）' },
    { title: '北海道（釧路）', value: '北海道（釧路）' },
    { title: '北海道（北見）', value: '北海道（北見）' },
    { title: '北海道（室蘭）', value: '北海道（室蘭）' },
    { title: '青森県', value: '青森県' },
    { title: '岩手県', value: '岩手県' },
    { title: '宮城県', value: '宮城県' },
    { title: '秋田県', value: '秋田県' },
    { title: '山形県', value: '山形県' },
    { title: '福島県', value: '福島県' },
    { title: '茨城県', value: '茨城県' },
    { title: '栃木県', value: '栃木県' },
    { title: '群馬県', value: '群馬県' },
    { title: '埼玉県', value: '埼玉県' },
    { title: '千葉県', value: '千葉県' },
    { title: '東京都', value: '東京都' },
    { title: '神奈川県', value: '神奈川県' },
    { title: '新潟県', value: '新潟県' },
    { title: '富山県', value: '富山県' },
    { title: '石川県', value: '石川県' },
    { title: '福井県', value: '福井県' },
    { title: '山梨県', value: '山梨県' },
    { title: '長野県', value: '長野県' },
    { title: '岐阜県', value: '岐阜県' },
    { title: '静岡県', value: '静岡県' },
    { title: '愛知県', value: '愛知県' },
    { title: '三重県', value: '三重県' },
    { title: '滋賀県', value: '滋賀県' },
    { title: '京都府', value: '京都府' },
    { title: '大阪府', value: '大阪府' },
    { title: '兵庫県', value: '兵庫県' },
    { title: '奈良県', value: '奈良県' },
    { title: '和歌山県', value: '和歌山県' },
    { title: '鳥取県', value: '鳥取県' },
    { title: '島根県', value: '島根県' },
    { title: '岡山県', value: '岡山県' },
    { title: '広島県', value: '広島県' },
    { title: '山口県', value: '山口県' },
    { title: '徳島県', value: '徳島県' },
    { title: '香川県', value: '香川県' },
    { title: '愛媛県', value: '愛媛県' },
    { title: '高知県', value: '高知県' },
    { title: '福岡県', value: '福岡県' },
    { title: '佐賀県', value: '佐賀県' },
    { title: '長崎県', value: '長崎県' },
    { title: '熊本県', value: '熊本県' },
    { title: '大分県', value: '大分県' },
    { title: '宮崎県', value: '宮崎県' },
    { title: '鹿児島県', value: '鹿児島県' },
    { title: '沖縄県', value: '沖縄県' },
];

// ユーザー情報を取得し、もし管理者権限であれば無効化を解除
const is_disabled = ref(true);
const user_store = useUserStore();
user_store.fetchUser().then((user) => {
    if (user && user.is_admin) {
        is_disabled.value = false;
    }
});

// サーバー設定を取得
const server_settings = ref<IServerSettings>(structuredClone(IServerSettingsDefault));
Settings.fetchServerSettings().then((settings) => {
    if (settings) {
        server_settings.value = settings;
    }
});

// サーバー設定を更新する関数
async function updateServerSettings() {

    // custom_https_certificate と custom_https_private_key が空文字列の場合は null に変換
    if (server_settings.value.server.custom_https_certificate === '') {
        server_settings.value.server.custom_https_certificate = null;
    }
    if (server_settings.value.server.custom_https_private_key === '') {
        server_settings.value.server.custom_https_private_key = null;
    }

    // サーバー設定を更新
    const result = await Settings.updateServerSettings(server_settings.value);

    // 成功した場合のみメッセージを表示
    // エラー処理は Services 層で行われるため、ここではエラー処理は不要
    // 再起動するまでは設定データは反映されないため、再起動せずにページをリロードすると反映されてないように見える点に注意
    if (result === true) {
        Message.success('サーバー設定を更新しました。\n変更を反映するためには、KonomiTV サーバーを再起動してください。');
    }
}

// ユーザー管理モーダルの表示状態
const account_manage_settings_modal = ref(false);
// サーバーログダイアログの表示状態
const server_log_dialog = ref(false);

// データベースを更新する関数
async function updateDatabase() {
    Message.show('データベースを更新しています...');
    await Maintenance.updateDatabase();
    Message.success('データベースを更新しました。');
}

// 録画フォルダの一括スキャンを実行する関数
async function runBatchScan() {
    Message.info(
        '録画フォルダの一括スキャンを開始しています...\n' +
        '大量の録画ファイルが保存されている環境では、処理完了まで数時間〜数日以上かかることがあります。'
    );
    const result = await Maintenance.runBatchScan();
    if (result === true) {
        Message.success(
            '録画フォルダの一括スキャンが完了しました。\n' +
            'すべての録画ファイルがデータベースに同期されているはずです。'
        );
    }
}

// バックグラウンド解析タスクを開始する関数
async function startBackgroundAnalysis() {
    Message.info(
        'バックグラウンド解析タスクを開始しています...\n' +
        '大量の録画ファイルが保存されている環境では、処理完了まで数時間〜数日以上かかることがあります。'
    );
    const result = await Maintenance.startBackgroundAnalysis();
    if (result === true) {
        Message.success(
            'バックグラウンド解析タスクの実行が完了しました。\n' +
            'すべての録画番組のメタデータ解析/サムネイル生成が完了しているはずです。'
        );
    }
}

// KonomiTV サーバーの再起動を行う関数
async function restartServer() {
    const result = await Maintenance.restartServer();
    if (result === true) {
        Message.show('KonomiTV サーバーを再起動しています...');
        // バージョン情報が取得できるようになるまで待つ
        await Utils.sleep(1.0);
        while (await Version.fetchServerVersion(true) === null) {
            await Utils.sleep(1.0);
        }
        Message.success('KonomiTV サーバーを再起動しました。');
    }
}

// KonomiTV サーバーのシャットダウンを行う関数
async function shutdownServer() {
    const result = await Maintenance.shutdownServer();
    if (result === true) {
        Message.success('KonomiTV サーバーをシャットダウンしました。');
    }
}

</script>

