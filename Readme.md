
# <img width="350" src="https://user-images.githubusercontent.com/39271166/134050201-8110f076-a939-4b62-8c86-7beaa3d4728c.png" alt="KonomiTV Logo">　<!-- omit in toc -->

<img width="100%" src="https://github.com/user-attachments/assets/6971f354-0418-4305-bf6d-b061142ffec6">
<video controls src="https://github.com/user-attachments/assets/ee0b6df0-3bb0-40da-99f4-798437aa2f9c"></video>

**いろいろな場所とデバイスでテレビと録画を快適に見れる、モダンな Web ベースのソフトウェアです。**

ユーザーのさまざまな好みがつまった、温かみのある居心地の良い場を作りたいという願いを込めて、KonomiTV と名付けました。  
手元の PC・タブレット・スマホをテレビにすることを考えたときに、まったく新しく、使いやすくて快適な視聴体験を創出したい一心で開発を進めています。

計画はかなり壮大ですが、2025年10月時点ではおもに以下の機能のみ実装されています。

- **「テレビをみる」**: 高画質/低遅延なリアルタイム視聴に対応し、ニコニコ実況や Twitter のコメントとともに番組を楽しめる、デバイスを選ばない快適な視聴体験
- **「ビデオをみる」**: 動画配信サービスのような洗練された UI と、当時の盛り上がりを追体験できるコメント再生機能を備えた、録画番組をゆったりと楽しめる視聴体験
- **「番組表」**: 読みやすく色分けされたデザインと軽快な動作で、気になる番組を見つけたら1クリックで録画予約できる **[🎉NEW!]**
- **「録画予約」**: 予約した番組の番組情報や放送時間を一目で把握でき、リアタイ視聴をサポート **[🎉NEW!]**
- **「マイリスト」**: 気になる録画番組をさっと登録して、ゆっくり観たいときに思い出せる、あなたのための視聴リスト
- **「視聴履歴」**: 録画番組の視聴状況を自動で追跡し、途中で中断した場合も前回の続きから再開して、あなたの番組鑑賞をサポート
- **「KonomiTV アカウント」**:  外出先のスマホでも自宅の PC でも、いつでもどこでも同じマイリスト・視聴履歴・設定を共有できる
- **「クライアント設定」**: KonomiTV のクライアントアプリ (PWA) の細かな設定が可能な設定画面
- **「サーバー設定」**: KonomiTV サーバーの動作環境や配信設定をカスタマイズできる設定画面

今後もより快適な視聴体験を実現すべく、「番組検索」「キーワード自動予約条件の管理」「録画番組の自動エンコード」「キャプチャ画像の管理」など、さらに便利で使いやすい機能を順次追加していく予定です。

## 目次 <!-- omit in toc -->
- [設計思想](#設計思想)
- [動作環境](#動作環境)
  - [サーバー](#サーバー)
  - [クライアント](#クライアント)
- [備考・注意事項](#備考注意事項)
- [事前準備](#事前準備)
  - [チューナーのドライバーを px4\_drv に変更する](#チューナーのドライバーを-px4_drv-に変更する)
  - [EDCB の事前設定](#edcb-の事前設定)
  - [QSVEncC・NVEncC・VCEEncC・rkmppenc に対応した GPU ドライバーのインストール](#qsvenccnvenccvceenccrkmppenc-に対応した-gpu-ドライバーのインストール)
    - [Windows](#windows)
    - [Linux - QSVEncC](#linux---qsvencc)
    - [Linux - NVEncC](#linux---nvencc)
    - [Linux - VCEEncC](#linux---vceencc)
    - [Linux - rkmppenc](#linux---rkmppenc)
  - [Tailscale の導入](#tailscale-の導入)
- [サーバーのインストール/アップデート](#サーバーのインストールアップデート)
  - [Windows](#windows-1)
  - [Linux](#linux)
  - [KonomiTV にアクセスする](#konomitv-にアクセスする)
  - [デスクトップアプリ・スマホアプリとして使う](#デスクトップアプリスマホアプリとして使う)
  - [フィードバックのお願い](#フィードバックのお願い)
- [付録](#付録)
  - [Twitter 実況機能について](#twitter-実況機能について)
    - [1. Chrome 拡張機能「GET cookies.txt LOCALLY」をインストールする](#1-chrome-拡張機能get-cookiestxt-locallyをインストールする)
    - [2. シークレットウインドウで Web 版 Twitter にログインする](#2-シークレットウインドウで-web-版-twitter-にログインする)
    - [3. Chrome 拡張機能を起動して Cookie データをエクスポートする](#3-chrome-拡張機能を起動して-cookie-データをエクスポートする)
    - [4. KonomiTV の設定画面で Cookie データを入力する](#4-konomitv-の設定画面で-cookie-データを入力する)
  - [`https://aa-bb-cc-dd.local.konomi.tv:7000/` の URL について](#httpsaa-bb-cc-ddlocalkonomitv7000-の-url-について)
  - [設定ファイルの編集](#設定ファイルの編集)
    - [バックエンドの設定](#バックエンドの設定)
    - [エンコーダーの設定](#エンコーダーの設定)
    - [リッスンポートの設定](#リッスンポートの設定)
    - [録画済み番組の保存先フォルダの設定](#録画済み番組の保存先フォルダの設定)
    - [アップロードしたキャプチャ画像の保存先フォルダの設定](#アップロードしたキャプチャ画像の保存先フォルダの設定)
  - [局ロゴ](#局ロゴ)
- [FAQ](#faq)
  - [Web UI にアクセスすると 502 Bad Gateway エラーが表示される](#web-ui-にアクセスすると-502-bad-gateway-エラーが表示される)
  - [Web UI にアクセスすると「Client sent an HTTP request to an HTTPS server.」と表示される](#web-ui-にアクセスするとclient-sent-an-http-request-to-an-https-serverと表示される)
  - [Web UI にアクセスすると「このサイトは安全に接続できません」「～から無効な応答が送信されました。」(ERR\_SSL\_PROTOCOL\_ERROR) と表示される](#web-ui-にアクセスするとこのサイトは安全に接続できませんから無効な応答が送信されましたerr_ssl_protocol_error-と表示される)
  - [Web UI にアクセスすると、DNS エラーが表示される](#web-ui-にアクセスするとdns-エラーが表示される)
  - [ライブストリーミングの視聴が安定しない・途切れ途切れになる](#ライブストリーミングの視聴が安定しない途切れ途切れになる)
    - [全般](#全般)
    - [KonomiTV サーバーのある自宅の Wi-Fi につないで視聴しているとき](#konomitv-サーバーのある自宅の-wi-fi-につないで視聴しているとき)
    - [外出先 (自宅以外) から Tailscale 経由で視聴しているとき](#外出先-自宅以外-から-tailscale-経由で視聴しているとき)
- [開発者向け情報](#開発者向け情報)
  - [開発版 KonomiTV のインストール (開発環境の構築)](#開発版-konomitv-のインストール-開発環境の構築)
  - [サーバーの起動](#サーバーの起動)
  - [Windows / PM2 サービスのインストールと起動](#windows--pm2-サービスのインストールと起動)
    - [Windows サービス](#windows-サービス)
    - [PM2 サービス](#pm2-サービス)
  - [クライアントの開発・ビルド](#クライアントの開発ビルド)
- [寄付・支援について](#寄付支援について)
- [Special Thanks](#special-thanks)
- [License](#license)

## 設計思想

<img width="100%" src="https://user-images.githubusercontent.com/39271166/153731898-c9743df8-794b-4498-ac25-017662f38759.png"><br>
<img width="100%" src="https://github.com/user-attachments/assets/e2a83d19-5716-4268-840d-cee4b985cb68"><br>

いわゆる TS 抜きでテレビを見ている人の多くが、TVTest でテレビを見て、録画をファイルベースで管理して、録画ファイルをメディアプレイヤーで開いて…といった、ファイルやアーキテクチャベースの視聴の仕方をされているかと思います。  
ですが、その中で必ず出てくる BonDriver を選択したり、ファイルをフォルダの中から探しだして選択したり、1話を見終わったから2話を開き直したりといった手間は、本来その番組を視聴し、心いくまで楽しむにあたって、不要な工程ではないかと考えます。雑念、といったほうが分かりやすいでしょうか。  

一方世間のトレンドに目を向けてみると、Netflix・Amazon Prime Video・AbemaTV のような配信サイトが幅を利かせています。  
これらのサイトが流行っているのは、（良い意味で）何も考えなくても、いつでもどこでも気軽に快適に映像コンテンツを見まくれる、そんなユーザー体験が実現されているからです。  
配信サイトとテレビ・録画は「リアルタイムで配信されている」「事前に選んだコンテンツしか視聴できない」など大きな差異もありますが、映像コンテンツを視聴するインターフェイスという点では共通しています。  
そこで、テレビと録画の視聴といういまだレガシーな視聴体験が残っている分野に、優れた UX を実現している配信サイトでの概念を取り入れ、まるで自分だけの Netflix のような視聴体験を演出できれば面白いのではないか？と考えました。その仮説と理想を実現すべく、鋭意開発を続けています。

こうした考えから、設計思想として「映像コンテンツを視聴し楽しむ」ために不要な概念や操作を可能なかぎり表層から排除・隠蔽し、ユーザーが本当の目的以外の雑念に気を取られないようなシステムを目指しています。

たとえば TVRemotePlus であった「ストリーム」の概念を KonomiTV では排しています。チャンネルをクリックするだけですぐに視聴できるほか、裏側ではチューナーの共有、同じチャンネルを複数のデバイスで見ているなら自動的に共聴するといった高度な仕組みも備え、ユーザーがストレスなく視聴できるように設計されています。  
画質の切り替えの UI も、KonomiTV では多くの動画サイトと同じようにプレイヤー内に統合されています。裏側では毎回エンコーダーを再起動しているのですが、表層からはあたかも事前に複数の画質が用意されているかのように見えるはずです。

一般的な PC で動かす以上使えるリソースには限界がありますし、全てにおいて Netflix のような機能を実装できるわけではありません。それでも使えるリソースの範囲で最大限使いやすいソフトウェアにしていければと、細部に様々な工夫を取り入れています。

当然ながら表に泥臭い処理を見せないようにしている分、裏側の実装がそれなりに大変です。細かいところまで調整しているとかなりの手間と時間がかかります。  
それでも私が頑張れば私を含めたユーザーの視聴体験が向上するわけで、必要な犠牲かなと思っています。

<img width="100%" src="https://github.com/user-attachments/assets/933956b2-acd5-45c5-8226-c857d12f2a2a"><br>
<img width="100%" src="https://github.com/user-attachments/assets/831cba8a-27e1-4f52-8856-0e0b8fef4ae1"><br>

## 動作環境

### サーバー

- **Windows 10/11 PC または Linux (Ubuntu) PC**
  - **Windows 10 Pro と Ubuntu 20.04 LTS の PC でのみ動作確認を行っています。**
    - Windows 11 でも動作するとは思いますが、手元に環境がないため、検証は行っていません（動作報告はいただいています）。
    - 32bit 版の Windows 10 には対応していません。
    - Windows サービスを特殊な方法で強引に動かしている関係で、Active Directory などの企業向けユーザー認証が必要な環境では動作しません。
  - **Linux PC は Ubuntu (20.04 LTS 以降) / Debian (11 Bullseye 以降) のみサポートしています。**
    - Linux PC では Docker 上にインストールすることもできます（後述）。
      - Ubuntu 24.04 LTS での動作は完全に未検証です。おそらく Docker でインストールした方がトラブルが少ないと思います。
    - Debian での動作確認はしていません。おそらく動くとは思いますが…
    - RedHat 系 OS・Arch Linux でも動作するかもしれませんが、開発/検証リソースが大幅に不足しているため、サポートは行いません。
      - できるだけ Ubuntu の利用を推奨しますが、もし Ubuntu 以外の OS にインストールする際は、Docker でのインストールを推奨します。
      - ビルド済みのサードパーティーライブラリは glibc 2.31 以上に依存しています。Docker を使わずにインストールする場合、[glibc 2.30 以下を採用する OS](https://repology.org/project/glibc/versions) では動作しません。
    - ARM 向けには、Rockchip RK3568 / RK3588 SoC のハードウェアエンコーダーに対応しています。
      - arm64 のみに対応しています。armhf などの 32bit ARM には対応していません。
      - ラズパイ4 / ラズパイ5はハードウェアエンコーダーが非力なのと入手性が微妙なため、サポート予定はありません。
        - ラズパイ5に至ってはハードウェアエンコーダー自体が搭載されていない…
      - ARM 向けのインストーラーも用意していますが、テスト不足のため、動作する保証はありません。
- **EDCB または Mirakurun / mirakc**
  - KonomiTV のバックエンドには、EDCB または Mirakurun / mirakc のいずれかを選択できます。
  - **EDCB は、220122 以降のバージョンの [xtne6f 版 EDCB](https://github.com/xtne6f/EDCB) / [tkntrec 版 EDCB](https://github.com/tkntrec/EDCB) にのみ対応しています。**
    - **220122 以前のバージョンの EDCB では正常に動作しません。<ins>「人柱版10.66」などの古いバージョンをお使いの場合は、EDCB のアップグレードが必要です。</ins>**
    - 230922 以降の xtne6f 版 / tkntrec 版 EDCB に更新すると EpgDataCap_Bon の起動が少し高速化され、KonomiTV でより快適にチャンネルを切り替えられるようになります。**  
    - **最新の EDCB のビルド済みアーカイブは [tsukumijima/DTV-Builds](https://github.com/tsukumijima/DTV-Builds) にて配布しています。** こだわりがなければ、DTV-Builds で配布しているアーカイブの利用を強くおすすめします (動作確認も DTV-Builds で配布しているアーカイブで行っています)。
    - **KonomiTV と連携するには、さらに EDCB に事前の設定が必要になります（後述）。**
    - [サーバー設定] → [常に Mirakurun / mirakc から放送波を受信する] をオンにすると、番組情報取得は EDCB から、放送波の受信は Mirakurun / mirakc から行えます。
      - Linux 環境ではチャンネル選局速度が向上するため、Mirakurun / mirakc サーバーが別途ある場合は強くおすすめします。
    - 240622 以降で実装された Linux 版 EDCB での動作確認は行っていません。私の開発環境では [EDCB-Wine](https://github.com/tsukumijima/EDCB-Wine) で安定稼働しています。
  - **Mirakurun は 3.9.0 以降を推奨します。**
    - 3.8.0 以下のバージョンでも動作しますが、諸問題で推奨しません。
    - **Mirakurun 4.0.0-beta.5 以下のバージョンでは、KonomiTV の起動時のバージョン情報取得によりドロップが発生する問題があります。**
      - この問題を回避するには、KonomiTV を 0.13.0 以降に更新するか、Mirakurun を 4.0.0-beta.6 以降に更新する必要があります。
      - 詳細は [こちらのツイートスレッド](https://x.com/TVRemotePlus/status/1982242605200011590) をご確認ください。
  - **Mirakurun 互換チューナーサーバーである [mirakc](https://github.com/mirakc/mirakc) も利用できます。**
    - 動作確認は最新版のみで行っています。
    - mirakc は局ロゴの収集に対応していないため、局ロゴが同梱されていないチャンネルでは、常にデフォルトの局ロゴが利用されます。
  - リバースプロキシなどで Mirakurun / mirakc に Basic 認証が掛かっていると正常に動作しません。

> [!IMPORTANT]
> **KonomiTV サーバー本体は Windows と Linux の両方で動作するように設計されていますが、メディア配信サーバーとして動作するために、多くの外部ソフトウェアを必要とします。**  
> 実行環境である CPython や、FFmpeg / QSVEncC などの動画エンコードやストリーミングに必要なツール類は、すべて [KonomiTV のサードパーティーライブラリ](https://github.com/tsukumijima/KonomiTV/blob/master/.github/workflows/build_thirdparty.yaml) に同梱されており、OS に依存せず単独で動作するよう細かく調整されています。  
> そのため、通常は Linux 環境であっても追加のパッケージインストールは必要ありませんが、検証できていない新しい OS ではうまく動作しない可能性もあります。

### クライアント

- **PC: Google Chrome**
  - **Windows 版 Microsoft Edge は https://github.com/tsukumijima/KonomiTV/issues/58 の問題 (Edge 側のバグ) があるため非推奨です。** 
    - 仮にこの問題がなかったとしても、Microsoft Edge では通信節約モード (HEVC) での視聴に有料の [HEVC ビデオ拡張機能](https://apps.microsoft.com/detail/9NMZLZ57R3T7) プラグインが別途必要になります。Chrome ではこのような制約はないため、Chrome の利用をおすすめします。 
  - Firefox でも動作するはずですが、コメント描画が重く、コメント表示をオンにするとライブストリーミングが時折止まることが確認されています。  
    - 動作確認も基本行っておらず、積極的なサポートはしていません。Chrome を使うことをおすすめします。
  - Mac Safari はサポートしていません。Mac でも Chrome を使ってください。
- **Android: Google Chrome**
  - Android の Firefox はサポートしていません。
- **iPhone (iOS) / iPad (iPadOS): Safari**
  - **iOS / iPadOS 17.1 以降のみに対応しています。17.0 以下の iOS / iPadOS バージョンのサポートは廃止されました。**
    - iOS 17.1 で ManagedMediaSource API がサポートされたため、KonomiTV 0.9.0 以降では iOS / iPadOS でも PC・Android と同じ再生方式 (mpegts.js) で再生します。
    - メンテナンスコストの観点から、以前の LL-HLS 再生方式は廃止されました。iPadOS では 17.0 以下でも一応動作しますが、iOS では 17.1 以降でないと視聴開始に失敗します。
  - 動作確認は iOS / iPadOS 17.1 以降で行っています。
  - **iOS / iPadOS の Chrome (WKWebView) はサポートしていません。**
  - iOS Safari (iPadOS を除く) では Fullscreen API がサポートされていないため、フルスクリーンボタンは動作しません。
  - PWA でも動作しますが、長年修正されていない Safari のバグの影響で、PWA モードでは Picture-in-Picture ボタンが動作しません。
  - Safari は全体的にバグが多く開発が大変なため、全体的にあまり動作確認を行えていません。修正できていない不具合があるかもしれません。

## 備考・注意事項

- **まだ開発中の β 版です。当初よりかなり安定してきましたが、まだ完璧に動作保証ができる状態ではありません。**
  - **KonomiTV 0.12.0 以降では、構想から4年の歳月を経て録画番組の再生機能が実装されました！🎉🎊**  
    - **ライブ視聴・録画再生の両方で TVRemotePlus の完全上位互換となっています。** TVRemotePlus はすでに開発を終了しているため、移行をお勧めします。
  - L字画面のクロップなどの細かな設定も含め、TVRemotePlus よりも大幅に改善されているはずです。
- **録画予約機能・番組検索機能は EDCB バックエンドを前提に設計されています。Mirakurun バックエンドや EPGStation には対応していません。**
  - 詳細は [こちらのツイート](https://x.com/TVRemotePlus/status/2006499142198243457) にて説明しています。
- **スマートフォンでは、最低限 iPhone SE2 (4.7インチ) 以上の画面サイズが必要です。**
  - 快適に利用するには、画面サイズが 6.1 インチ以上の端末をおすすめします。
  - iPhone 5s (4インチ) サイズの端末には原則対応しておらず、画面が大幅に崩れます。
- **Fire タブレット (Fire HD 10 (2021) / Fire HD 8 (2022)) でも動作します。**
  - Fire HD 10 (2021) では Google Play を導入した上で、Google Play 経由で Chrome をインストールしてください。
  - Fire HD 8 (2022) では現状 Google Play が導入できないため、適宜 Chrome の APK を入手してインストールしてください。Chrome は、(Google アカウントとの同期機能以外は) GMS がインストールされていなくても動作します。
  - **Fire HD 10 (2021) などの一部のローエンド Android (特に MediaTek SoC 搭載) デバイスでは、1080p 以上の映像描画が不安定なことが確認されています。** その場合は 720p 以下の画質での視聴をおすすめします。
- **今後、開発の過程で設定や構成が互換性なく大幅に変更される可能性があります。**
- **ユーザービリティなどのフィードバック・不具合報告・Pull Requests (PR) などは歓迎します。**
  - 技術スタックはサーバー側が Python 3.11 + [FastAPI](https://github.com/tiangolo/fastapi) + [Tortoise ORM](https://github.com/tortoise/tortoise-orm) + [Uvicorn](https://github.com/encode/uvicorn) 、クライアント側が Vue.js 3.x + [Vuetify](https://github.com/vuetifyjs/vuetify) 3.x の SPA です。
    - Vuetify は補助的に利用しているだけで、大部分は独自で書いた SCSS スタイルを適用しています。
  - コメントを多めに書いたりそれなりにきれいにコーディングしているつもりです。少なくとも TVRemotePlus なんかよりかは読みやすいコードになっている…はず。
  - 他人が見るために書いたものではないのであれですが、一応自分用の [開発資料](https://mango-garlic-eff.notion.site/KonomiTV-90f4b25555c14b9ba0cf5498e6feb1c3) と [DB設計](https://mango-garlic-eff.notion.site/KonomiTV-544e02334c89420fa24804ec70f46b6d) 的なメモを公開しておきます。もし PR される場合などの参考になれば。
    - 2025年2月時点では両方のドキュメントとも3年以上全く更新できていないため、あくまで参考程度にご覧ください。

<img width="100%" src="https://github.com/user-attachments/assets/29ca62cb-056d-4d50-af59-bf031199355b"><br>
<img width="100%" src="https://github.com/user-attachments/assets/bb4d681e-91ba-410a-95a3-c77bdcaec073"><br>

## 事前準備

### チューナーのドライバーを px4_drv に変更する

必須ではありませんが、**Windows で PLEX 製チューナーをお使いの方は、事前にドライバーを [px4_drv for WinUSB](https://github.com/tsukumijima/px4_drv) に変更しておくことを強く推奨します。**  
px4_drv では、公式ドライバーとの比較で、チューナーの起動時間が大幅に短縮されています。  
その分 KonomiTV での視聴までにかかる待機時間も速くなるため（5秒以上速くなる）、より快適に使えます。一部の新しいチューナーへの対応も追加されています。  

**px4_drv を導入すると、ほかにもドロップが大幅に減って安定するなど、たくさんのメリットがあります！**  
内蔵カードリーダーが使えないこと、BonDriver の差し替えが必要になることだけ注意してください。

> [!NOTE]  
> px4_drv for WinUSB のビルド済みアーカイブは [tsukumijima/DTV-Builds](https://github.com/tsukumijima/DTV-Builds) にて配布しています。

### EDCB の事前設定

<img width="613" src="https://user-images.githubusercontent.com/39271166/201383288-7bcda592-bffd-4a15-b975-ced2b66e4289.png"><br>

**EDCB バックエンドでは、いくつか EDCB に事前の設定が必要です。**  
**<ins>この事前設定を行わないと KonomiTV は正常に動作しません。</ins> 必ず下記のとおりに設定してください。**

**また、必ず 220122 以降のバージョンの [xtne6f 版 EDCB](https://github.com/xtne6f/EDCB) / [tkntrec 版 EDCB](https://github.com/tkntrec/EDCB) を利用していることを確認してください。**  
現在利用している EDCB のバージョンは、EpgTimer の設定ウインドウの下に表示されています。**KonomiTV でサポートしていない古い EDCB では、このバージョン表示自体がありません。**

> [!NOTE]  
> **230922 以降の xtne6f 版 / tkntrec 版 EDCB に更新すると EpgDataCap_Bon の起動が少し高速化され、KonomiTV でより快適にチャンネルを切り替えられるようになります。**

**[動作環境] に記載のとおり、<ins>220122 以前や「人柱版10.66」などの古いバージョンをお使いの場合は、EDCB のアップグレードが必要になります。</ins>**  
**最新版の EDCB のビルド済みアーカイブは [tsukumijima/DTV-Builds](https://github.com/tsukumijima/DTV-Builds) にて配布しています。**  
特にこだわりがなければ、このビルド済みアーカイブで事前に EDCB を最新版にアップグレードしておいてください。

-----

<img width="664" src="https://user-images.githubusercontent.com/39271166/201383475-7d5f6077-fb9a-452d-87a0-38c448a5e744.png"><br>

**EpgTimer を開き、[設定] → [動作設定] → [全般] から、[EpgTimerSrv の設定画面を開く] をクリックして、EpgTimerSrv の設定画面を開きます。**  
さらに [その他] タブに切り替え、以下のとおりに設定してください。

- **[視聴に使用する BonDriver] に BonDriver を追加する**
  - **EDCB に登録している BonDriver のうち、ここで設定した BonDriver だけが KonomiTV での視聴に利用されます。**
  - [視聴に使用する BonDriver] に追加した BonDriver がすべて録画に使われているときは、KonomiTV からは視聴できません（チューナー不足と表示されます）。
  - また、KonomiTV での視聴中に録画が開始されたとき、その時点でチューナーが足りない場合は録画予約が優先され、KonomiTV 向けのストリーム配信は停止されます。
- **[ネットワーク接続を許可する (EpgTimerNW 用)] にチェックを入れる**
  - この設定にチェックを入れることで、KonomiTV が TCP API 経由で EDCB と通信できるようになります。
- **[ネットワーク接続を許可する (EpgTimerNW 用)] → [アクセス制御] に、`+127.0.0.0/8,+10.0.0.0/8,+172.16.0.0/12,+192.168.0.0/16,+169.254.0.0/16,+100.64.0.0/10` と入力する**
  - [プライベート IP アドレス](https://wa3.i-3-i.info/word11977.html) と [Tailscale](https://tailscale.com/) の [100.x.y.z](https://tailscale.com/kb/1015/100.x-addresses/) アドレスからのアクセスを許可する設定です。
  - この数字の羅列の意味を理解している方以外は、そのままコピペして貼り付けることを強くおすすめします。
- **[ネットワーク接続を許可する (EpgTimerNW 用)] → [IPv6] のチェックを外す**
  - この設定にチェックを入れると、**IPv6 アドレスでアクセスできるようになる代わりに、IPv4 アドレスでのアクセスが一切できなくなります (落とし穴…)。**
  - [IPv4/IPv6 両対応にする設定ではない](https://github.com/xtne6f/EDCB/blob/work-plus-s-220921/Document/Readme_Mod.txt#L256) ため、チェックを外すことを強くおすすめします。
- **xtne6f 版 EDCB の場合、[EpgTimerSrv の応答を tkntrec 版互換にする (要再起動)] にチェックを入れる**
  - EDCB から局ロゴを取得する際に必要です。変更を適用するには、EpgTimerSrv (EpgTimer Service) を再起動してください。
  - tkntrec 版 EDCB では既定で有効になっています（設定項目自体がありません）。

-----

<img width="570" src="https://user-images.githubusercontent.com/39271166/201386157-451f84cb-38a2-44dd-b8e7-4c2b461c90ed.png"><br>

**また、EpgDataCap_Bon にも設定が必要です。**  
**EpgDataCap_Bon を開き、[設定] → [ネットワーク設定] → [TCP送信] から、[SrvPipe] を選択して [追加] ボタンをクリックしてください。**
送信先一覧に `0.0.0.1:0-29 (SrvPipe)` と表示されていれば OK です。

> [!NOTE]  
> SrvPipe とは、EpgDataCap_Bon で受信した放送波を EpgTimerSrv (EpgTimer Service) に渡すための、EDCB 固有の特殊な名前付きパイプのことです。  
> KonomiTV は SrvPipe を経由して EDCB から放送波を受信しているため、この設定を忘れると、テレビのライブストリーミングができません。

> [!WARNING]
> **[設定] → [動作設定] → [スクランブル解除処理を行う\*] にも必ずチェックを入れておいてください！**  
> [スクランブル解除処理を行う*]  がオフの場合、KonomiTV に EpgDataCap_Bon.exe → EpgTimerSrv.exe 経由でスクランブル未解除の TS が送り込まれ、結果としてエンコーダーの初期化に失敗します。
> 
> また必須ではありませんが、この機会に [設定] → [動作設定] → [全サービスを処理対象とする*] のチェックを外しておくことを推奨します。

このほか、**リモート PC の KonomiTV から EDCB にアクセスする場合は、EpgTimerSrv.exe にファイアウォールが掛かっていると接続に失敗します。**  
適宜ファイアウォールの設定を変更し、EDCB に接続できるようにしておいてください。

### QSVEncC・NVEncC・VCEEncC・rkmppenc に対応した GPU ドライバーのインストール

KonomiTV は、[QSVEncC](https://github.com/rigaya/QSVEnc) (Intel QSV)・[NVEncC](https://github.com/rigaya/NVEnc) (NVIDIA NVENC)・[VCEEncC](https://github.com/rigaya/VCEEnc) (AMD VCE)・[rkmppenc](https://github.com/rigaya/rkmppenc) (Rockchip ARM SoC) の4つのハードウェアエンコーダーに標準で対応しています。

> [!IMPORTANT]  
> **FFmpeg (ソフトウェアエンコーダー) は遅い上に CPU 負荷がかなり高くなるため、ハードウェアエンコーダーの利用を強くおすすめします。**  
> FFmpeg での積極的な動作確認は行っていません。

> [!WARNING]
> **RDNA 世代以前 (Vega 世代) の AMD GPU / APU では、ハードウェアエンコーダーやドライバの作りが悪く極めて不安定で、VCEEncC がクラッシュしやすいことが報告されています。**  
> 一般的に QSVEncC / NVEncC の方が明確に安定しており画質も良いため、**外付け GPU の有無に関わらず、可能な限り QSVEncC / NVEncC の利用を推奨します。**

#### Windows

- QSVEncC：[Intel Graphics Driver](https://www.intel.co.jp/content/www/jp/ja/support/articles/000005629/graphics/processor-graphics.html)
- NVEncC：[NVIDIA Graphics Driver](https://www.nvidia.co.jp/Download/index.aspx)
- VCEEncC：[AMD Graphics Driver](https://www.amd.com/ja/support/download/drivers.html)

それぞれのハードウェアエンコーダーを使用するには、対応した GPU ドライバーのインストールが必要です。  
Windows の場合、基本的にすでにインストール済みのはずです。

> [!NOTE]  
> **古いドライバーを使用している場合は、この機会に最新のドライバーにアップデートしておくことをおすすめします。**  
> ドライバーが古すぎると、ハードウェアエンコードに失敗する場合があります。  
> KonomiTV をアップデートした後は、ドライバーも最新のドライバーにアップデートしておくことをおすすめします。

#### Linux - QSVEncC

**QSVEncC では、別途 Intel Media Driver のインストールが必要です。**

> [!WARNING]  
> **Linux 版の Intel QSV は、Broadwell (第5世代) 以上の Intel CPU でのみ利用できます。**  
> そのため、Haswell (第4世代) 以下の CPU では、Intel Media Driver のインストール有無にかかわらず、QSVEncC を利用できません。  
> なお、Windows 版の Intel QSV は、Haswell (第4世代) 以下の CPU でも利用できます。

```bash
# Ubuntu 24.04 LTS
curl -fsSL https://repositories.intel.com/gpu/intel-graphics.key | sudo gpg --yes --dearmor --output /usr/share/keyrings/intel-graphics-keyring.gpg
echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics-keyring.gpg] https://repositories.intel.com/gpu/ubuntu noble unified' | sudo tee /etc/apt/sources.list.d/intel-gpu-noble.list > /dev/null

# Ubuntu 22.04 LTS
curl -fsSL https://repositories.intel.com/gpu/intel-graphics.key | sudo gpg --yes --dearmor --output /usr/share/keyrings/intel-graphics-keyring.gpg
echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics-keyring.gpg] https://repositories.intel.com/gpu/ubuntu jammy unified' | sudo tee /etc/apt/sources.list.d/intel-gpu-jammy.list > /dev/null

# Ubuntu 20.04 LTS
curl -fsSL https://repositories.intel.com/gpu/intel-graphics.key | sudo gpg --yes --dearmor --output /usr/share/keyrings/intel-graphics-keyring.gpg
echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics-keyring.gpg] https://repositories.intel.com/gpu/ubuntu focal client' | sudo tee /etc/apt/sources.list.d/intel-graphics.list > /dev/null

sudo apt update && sudo apt install -y intel-media-va-driver-non-free intel-opencl-icd libigfxcmrt7 libmfx1 libmfxgen1 libva-drm2 libva-x11-2
```

上記のコマンドを実行して、Intel Media Driver をインストールしてください (Ubuntu 20.04 LTS 以降向け) 。  
最新のインストール手順は [QSVEncC の公式ドキュメント](https://github.com/rigaya/QSVEnc/blob/master/Install.ja.md) もあわせてご確認ください。

> [!NOTE]  
> **Docker でインストールする際は、ホストマシンに Intel Media Driver をインストールしなくても動作します。**  
> [KonomiTV の Docker イメージ](https://github.com/tsukumijima/KonomiTV/blob/master/Dockerfile) には Intel Media Driver が標準でインストールされているほか、Intel Graphics 自体のドライバは Linux カーネルに取り込まれているためです。

> [!NOTE]  
> 以前 Alder Lake (第12世代) 以降の Intel CPU で必要だった `libmfx-gen1.2` は、[QSVEncC 7.38](https://github.com/rigaya/QSVEnc/releases/tag/7.38) 以降で `libmfxgen1` に置き換えられました。  
> `libmfxgen1` は、Ubuntu 20.04 LTS 以降で利用できます。

> [!WARNING]  
> **Jasper Lake 世代などの一部 CPU や Arc GPU では、別途 HuC ファームウェアのロードを有効にする必要があります。**  
> HuC ファームウェアのロードを有効にするには、`/etc/modprobe.d/i915.conf` にカーネルパラメーターとして `options i915 enable_guc=2` を追記し、システムを再起動してください。  
> 詳細は [QSVEncC のドキュメント](https://github.com/rigaya/QSVEnc/blob/master/Install.ja.md) をご確認ください。

#### Linux - NVEncC

**NVEncC では、[NVIDIA Graphics Driver](https://www.nvidia.co.jp/Download/index.aspx) のインストールが必要です。**  
基本的にはすでにインストールされていると思います。個人的には `ubuntu-drivers` コマンドを使って apt でインストールするのがおすすめです。  
[NVEncC の公式ドキュメント](https://github.com/rigaya/NVEnc/blob/master/Install.ja.md) もあわせてご確認ください。

**Docker で KonomiTV をインストールする際は、さらに NVIDIA Container Toolkit のインストールが必要です。**  
インストール手順は [NVIDIA の公式ドキュメント](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) をご確認ください。

#### Linux - VCEEncC

**VCEEncC では、[AMDGPU-PRO Driver](https://www.amd.com/ja/support/download/linux-drivers.html) のインストールが必要です。**  

> [!WARNING]  
> **古いドライバーがインストールされている場合、VCEEncC が動作しない可能性があります。**  
> KonomiTV をアップデートした後は、AMDGPU-PRO Driver も最新のドライバーにアップデートしてください。

> [!WARNING]  
> **VCEEncC を使うには AMDGPU-PRO ドライバーが必要です。**  
> オープンソース版の AMDGPU ドライバーには AMD AMF (Advanced Media Framework) が含まれていないため、VCEEncC を利用できません。

```bash
# Ubuntu 24.04 LTS (2025年11月時点で最新の amdgpu-install パッケージの URL)
curl -LO https://repo.radeon.com/amdgpu-install/6.4.4/ubuntu/noble/amdgpu-install_6.4.60404-1_all.deb
# Ubuntu 22.04 LTS (2025年11月時点で最新の amdgpu-install パッケージの URL)
curl -LO https://repo.radeon.com/amdgpu-install/6.4.4/ubuntu/jammy/amdgpu-install_6.4.60404-1_all.deb

# AMDGPU-PRO Driver のインストール
sudo apt install -y ./amdgpu-install_6.4.60404-1_all.deb
sudo apt update && sudo amdgpu-install -y --accept-eula --usecase=graphics,amf,opencl --opencl=rocr --vulkan=amdvlk --no-32

# 再起動
sudo reboot
```

上記のコマンドを実行して、AMDGPU-PRO Driver をインストールしてください (Ubuntu 22.04 LTS 以降向け) 。

#### Linux - rkmppenc

**rkmppenc のサポートは実験的です。Rockchip 製 ARM SoC (RK3588/RK3588S など) 搭載デバイスでのみ利用できます。**

```bash
# Mali GPU Driver のインストール (RK3588/RK3588S 向け)
## --vpp-yadif などの OpenCL フィルタの利用に必要
## Debian 11 Bullseye Core イメージにはデフォルトではインストールされていない
## 他の Rockchip SoC の Mali GPU Driver は https://github.com/tsukumijima/libmali-rockchip/releases から入手できる
## RK3588/RK3588S の場合、g610-g6p0 より g610-g13p0 の方が高速に動作する
## 2026年1月追記: v1.9-1-3238416 よりも後のバージョンは glibc 2.34 でビルドされているため、
## glibc 2.31 を持つ Debian 11 Bullseye では v1.9-1-3238416 までしかインストールできない (!!!)
wget https://github.com/tsukumijima/libmali-rockchip/releases/download/v1.9-1-3238416/libmali-valhall-g610-g13p0-wayland-gbm_1.9-1_arm64.deb
sudo apt install -y --allow-downgrades ./libmali-valhall-g610-g13p0-wayland-gbm_1.9-1_arm64.deb
rm libmali-valhall-g610-g13p0-wayland-gbm_1.9-1_arm64.deb

# rockchip-multimedia-config のインストール
## Rockchip のハードウェアエンコーダーを有効化するための設定パッケージ
wget https://github.com/tsukumijima/rockchip-multimedia-config/releases/download/v1.0.2-1/rockchip-multimedia-config_1.0.2-1_all.deb
sudo apt install -y ./rockchip-multimedia-config_1.0.2-1_all.deb
rm rockchip-multimedia-config_1.0.2-1_all.deb

# 念のため再起動
sudo reboot
```

上記のコマンドを実行して、Mali GPU Driver と、Rockchip のハードウェアエンコーダーを有効化するための設定パッケージをインストールしてください (Ubuntu 20.04 LTS 以降向け) 。  
[rkmppenc の公式ドキュメント](https://github.com/tsukumijima/rkmppenc/blob/master/Install.ja.md) もあわせてご確認ください。

### Tailscale の導入

<img width="100%" src="https://user-images.githubusercontent.com/39271166/201439632-d78b8401-ef70-4955-98e8-b317ecf3e278.png"><br>

**KonomiTV で外出先からリモート視聴するには、[Tailscale](https://tailscale.com/) というメッシュ VPN ソフトを、サーバー PC とクライアントデバイス双方にインストールしておく必要があります。**  

> [!NOTE]  
> KonomiTV を家の中だけで使う分には必須ではありませんが、セットアップがとっても簡単で時間もそこまでかからないので、この機会にインストールしておくことをおすすめします。

> [!NOTE]  
> 厳密にはほかの方法 (OpenVPN・SoftEther・リバースプロキシなど) でもリモート視聴は可能ですが、技術的に難易度がかなり高くネットワークエンジニア以外には難しいこと、Tailscale を使った方法が一番手軽でセキュアなことから、**KonomiTV では Tailscale を使ったリモート視聴方法のみ公式にサポートしています。**  
> **特にリバースプロキシや BASIC 認証経由でのアクセスでは一部機能が正常に動作しなくなるほか、セキュリティ上の問題もあるため、公式にはサポートしていません。**

Tailscale は、デバイスが接続されているネットワークや物理的距離に関係なく、**同じアカウントにログインしている Tailscale クライアント (デバイス) 同士で直接通信できる、次世代型のメッシュ VPN です。**

VPN サーバーを介さず Tailscale クライアント同士で直接通信するため、通常の VPN よりも高速です。さらに通信は暗号化されるため、セキュアに外出先から自宅のデバイスへアクセスできます。

**さらに、デバイスをほかの Tailscale ユーザーとシェアすることもできます。**  
Google ドライブでファイルへの招待リンクを作って共同編集したい人に送るのと同じ要領で、Tailscale クライアントをインストールしたデバイスをほかのユーザーとシェアできます。  
KonomiTV を共有したい家族や親戚に Tailscale アカウントを作成してもらえば、Tailscale ログイン用の Google / Microsoft / GitHub アカウントを家族間で共有することなく、セキュアに KonomiTV をシェアできます。

**Tailscale の詳細や導入方法は、以前私が執筆した **[こちら](https://blog.tsukumijima.net/article/tailscale-vpn/)** の記事をご覧ください。**  
この記事のとおりにセットアップすれば、あとは各デバイスで Tailscale での VPN 接続をオンにしておくだけです。

**KonomiTV での利用以外にも、EDCB Material WebUI や EPGStation などの、プライベートネットワーク上の Web サーバーに家の外からアクセスするときにとても便利なサービスです。**  
100台までは無料ですし (逸般の誤家庭でなければ十分すぎる)、この機会にぜひ導入をおすすめします。

<img width="100%" src="https://github.com/user-attachments/assets/8e91d6db-1988-4da1-bd10-3c11870fa3c8"><br>

## サーバーのインストール/アップデート

**KonomiTV には、インストーラー/アップデーター/アンインストーラーの3つのモードを内包した、CLI ベースのインストーラーがあります。**  
このインストーラーを使えば、とてもかんたんに KonomiTV をインストール/アップデートできます！

**インストール時は、KonomiTV のインストーラーを起動したあと、最初の質問で `1` を入力します。**  
あとは、インストーラーの通りに進めていくだけで、自動的にインストールが開始されます！詳しくは下記のインストール手順をご覧ください。

**アップデート/アンインストール時は、KonomiTV のインストーラーを起動したあと、最初の質問でアップデートでは `2` 、アンインストールでは `3` を入力します。**  
**その後、KonomiTV がインストールされているフォルダを入力すると、自動的にアップデート/アンインストールが開始されます！**

> [!NOTE]  
> インストール/アップデートにはインターネット接続が必要です。オフラインインストーラーではないため注意してください。

> [!WARNING]  
> **KonomiTV サーバーは特殊な仕組みで動作しているため、通常のアプリと異なり Windows の「設定」や「プログラムと機能」からアンインストールすることはできません。**  
> アンインストールする際は、**必ず KonomiTV のインストーラー (アンインストーラーモード) を使ってアンインストールしてください。**  
> インストーラーには後方互換性があるため、インストールされているバージョンより新しいバージョンのインストーラーを使ってアンインストールすることもできます。

**以下はインストール時の手順になります。**  
アップデート/アンインストールする際は適宜読み替えてください。

> [!WARNING]  
> KonomiTV は鋭意開発中のため、現在破壊的な構成変更が頻繁に行われています。   
> 破壊的変更が続く中アップデーターの機能を維持することは難しいため、**安定版リリースまでの当面の間、アップデーターは最低限のメンテナンスのみ行っています。**

> [!NOTE]  
> **インストーラーを実行する前に、当該バージョンの [リリースノート](https://github.com/tsukumijima/KonomiTV/releases) を一読しておくことを強く推奨します。**  
> 各バージョンごとのインストール時の注意点なども、すべてリリースノートに記載されています。

### Windows

[動作環境](#動作環境) に記載のとおり、Windows 10 以降の 64bit OS にのみ対応しています。  
Windows 8.1 以下と、32bit OS には対応していません。

**[Releases](https://github.com/tsukumijima/KonomiTV/releases) ページから、最新の KonomiTV のインストーラーをダウンロードします。**  
Assets の下にある `KonomiTV-Installer.exe` をダウンロードしてください。

> [!NOTE]  
> **`KonomiTV-Installer.exe` がウイルス対策ソフトにウイルスと扱われてしまうことがありますが、誤検知です。一般に Python 製ソフトを exe 化すると問答無用でウイルスだと扱われてしまうことが多く、頭を抱えています…。**  
> 適宜お使いのウイルス対策ソフトで、`KonomiTV-Installer.exe` の実行を許可してください。KonomiTV のインストーラーのソースコードは [こちら](https://github.com/tsukumijima/KonomiTV/tree/master/installer) で公開しています。

<img width="100%" src="https://user-images.githubusercontent.com/39271166/201462168-f898fe8f-ac1f-4942-908f-de6263389a97.png"><br>

**ダウンロードが終わったら、`KonomiTV-Installer.exe` をダブルクリックで実行します。**  
インストールには管理者権限が必要です。

**あとは、インストーラーの通りに必要事項を入力していけば、インストールがはじまります！**  
スペックにもよりますが、インストールには少し時間がかかります。気長に待ちましょう。

**インストール処理の終盤で、KonomiTV の実行ユーザー名と、パスワードの入力を求められます。**

> [!NOTE]  
> ユーザー名とパスワードは、KonomiTV を一般ユーザーの権限で動作させるために必要です。  
> Windows サービスは通常、ネットワークドライブにアクセスする際に認証情報が必要ですが、**一般ユーザーの権限で動作させることで、そのユーザーのネットワークドライブに自由にアクセスできるようになります。**  
> なお、入力されたユーザー名とパスワードは、この目的以外には一切使用されません。

実行ユーザー名を入力せずに Enter キーを押すと、デフォルトで現在ログオン中のユーザーが利用されます。

> [!IMPORTANT]  
> **セキュリティソフトの誤作動により、インストール途中にエラーが発生し、インストールに失敗することがあります。**  
> その場合は一時的にセキュリティソフトのリアルタイムスキャンをオフにしたり、インストール先のフォルダをスキャン対象から除外してから、再度インストーラーを実行してみてください。

> [!WARNING]  
> - **PIN などのほかの認証方法には対応していません。必ず通常のパスワードを入力してください。**
> - **指定したユーザーにパスワードを設定していない場合は、簡単なものでいいので何かパスワードを設定してから、その設定したパスワードを入力してください。**
>   - なお、パスワードの設定後にインストーラーを起動し直す必要はありません。
> - **Microsoft アカウントでユーザーアカウントを作成した場合もログオンできない場合があります。**
>   - 一度ローカルアカウントに切り替え、通常のパスワードを設定してから、再度インストーラーを実行してみてください。
> - **ごく稀に、正しいパスワードを指定したにも関わらず、ログオンできない場合があります。**
>   - その場合は、インストーラーを Ctrl+C で中断した後、インストーラーの実行ファイル (`KonomiTV-Installer.exe`) を Shift + 右クリック → [[別のユーザーとして実行]](https://faq.nec-lavie.jp/qasearch/1007/app/servlet/relatedqa?QID=020525) をクリックします。  
>     表示された画面でログオン中のユーザー名とパスワードを指定してから、再度インストーラーを実行してみてください。
> - **検証環境がないため、Windows Server / Active Directory / ドメインアカウントなどの特殊な環境はサポートしていません。**
>   - 当該環境ではインストーラー/アップデーターが正常に動作しないことが報告されています。
>   - インストーラー/アップデーターのソースコードを読み、手動でインストールを行ってください。

> [!WARNING]  
> **KonomiTV の Windows サービスは、PC の起動後数分遅れてから起動します。**  
> PC の起動直後は EDCB や Mirakurun の Windows サービスがまだ起動していないためです。

### Linux

[動作環境](#動作環境) に記載のとおり、Ubuntu 20.04 LTS / Debian 11 Bullseye 以降の OS にのみ対応しています。  
それ以外のディストリビューションでも動くかもしれませんが、動作は保証しませんし、今後のサポート予定もありません (Docker ならどの OS でもそれなりに動くような気はします) 。

> [!NOTE]  
> できるだけ Ubuntu の利用を推奨しますが、もし Ubuntu 以外の OS にインストールする際は、Docker でのインストールをおすすめします。

> [!WARNING]  
> **NVIDIA が KonomiTV で利用していたバージョンの CUDA Docker イメージを削除した影響で 、0.12.0 以下では Docker を使ったインストール方法が動作しなくなりました。**  
> 0.13.0 以降のバージョンでは、RTX 5090 などの Blackwell 世代 GPU の対応も兼ね、CUDA Docker イメージを `nvidia/cuda:12.8.0-base-ubuntu22.04` に変更しています。0.13.0 以降へのアップデートをお願いします。  
> なお、CUDA 12.8 の動作には  nvidia-driver-570 以上のドライバーがインストールされている必要があります。

> [!WARNING]  
> **AMD が Docker イメージ内で利用している AMDGPU-PRO ドライバーの旧バージョンの APT リポジトリをサイレントに削除した影響で ([#118](https://github.com/tsukumijima/KonomiTV/issues/118) / [#130](https://github.com/tsukumijima/KonomiTV/issues/130) を参照) 、0.11.0 以下では Docker を使ったインストール方法が動作しなくなりました。**  
> 0.12.0 以降のバージョンでは AMDGPU-PRO ドライバーの APT リポジトリの URL を更新しています。0.12.0 以降へのアップデートをお願いします。

**Linux 向けの KonomiTV には、通常のインストール方法と、Docker を使ったインストール方法の 2 通りがあります。**  

**通常のインストール方法では、事前に [PM2](https://PM2.keymetrics.io/docs/usage/quick-start/) と [Node.js](https://github.com/nodesource/distributions) (PM2 の動作に必要) のインストールが必要です。**  
[Mirakurun](https://github.com/Chinachu/Mirakurun) や [EPGStation](https://github.com/l3tnun/EPGStation) を Docker を使わずにインストールしているなら、すでにインストールされているはずです。  
また、インストーラーの実行時に `lshw` コマンドが必要です。`lshw` がインストールされていない場合は、適宜インストールしてください。

**Docker を使ったインストール方法では、事前に [Docker](https://docs.docker.com/engine/install/) と [Docker Compose](https://docs.docker.com/compose/install/) のインストールが必要です。**  
Docker Compose は V1 と V2 の両方に対応していますが、できれば V2 (ハイフンなしの `docker compose` コマンド) が使えるようにしておくことをおすすめします。

**なお、Ubuntu 公式 apt リポジトリの Docker / Docker Compose は古いバージョンで固定されているため、必ず Docker 公式 apt リポジトリからインストール・アップデートを行うようにしてください。**  
古い Docker / Docker Compose では正常に動作しません。

> [!WARNING]  
> **ARM デバイスでは、対応コストの観点から Docker を使ったインストール方法はサポートされていません。**

> [!WARNING]  
> **Docker Compose V1 は最終版の 1.29.2 でのみ動作を確認しています。古いバージョンでは正常に動作しない可能性が高いです。**  
> もし Docker Compose V1 が 1.29.2 よりも古い場合は、この機会に V2 への更新をおすすめします。以前よりもグラフィカルに進捗が表示されたりなどのメリットもあります。  

> [!WARNING]  
> [QSVEncC・NVEncC・VCEEncC・rkmppenc に対応した GPU ドライバーのインストール](#qsvenccnvenccvceenccrkmppenc-に対応した-gpu-ドライバーのインストール) に記載のとおり、**NVIDIA GPU が搭載されている PC に Docker を使ってインストールする場合は、必ず事前に NVIDIA Container Toolkit をインストールしておいてください。**  
> NVIDIA Container Toolkit がインストールされていない場合、KonomiTV のインストールにも失敗する可能性が高いです。

> [!NOTE]  
> Docker を使ってインストールする場合、動作環境によっては `getaddrinfo EAI_AGAIN registry.yarnpkg.com` といったエラーで Docker イメージのビルドに失敗することがあります。  
> Docker の DNS 設定がおかしかったり、Docker が書き換える iptables の定義が壊れてしまっていることが原因のようで、解決方法は千差万別です。  
> また、KonomiTV の Docker Compose 構成では都合上 `network_mode: host` を使っていますが、これによりほかの環境と衝突している可能性もあります。  
> KonomiTV は通常のインストール方法でも極力環境を汚さないように開発されています。Docker を使わずに通常通りインストールしたほうが手っ取り早いかもしれません。  
> 参考: https://e-tipsmemo.hatenablog.com/entry/2024/04/07/000000

<img width="100%" src="https://user-images.githubusercontent.com/39271166/201463450-96bb686e-c5bb-493d-b907-57b5f51ac986.png"><br>

```bash
curl -LO https://github.com/tsukumijima/KonomiTV/releases/download/v0.13.0/KonomiTV-Installer.elf
chmod a+x KonomiTV-Installer.elf
./KonomiTV-Installer.elf
```

以上のコマンドを実行して `KonomiTV-Installer.elf` を実行し、インストーラーの通りに進めてください。  
インストールには root 権限が必要です。`KonomiTV-Installer.elf` の実行時に自動的にパスワードを求められます。

> [!NOTE]  
> ARM デバイスでは、`KonomiTV-Installer.elf` の代わりに `KonomiTV-Installer-ARM.elf` をダウンロードしてください。

### KonomiTV にアクセスする

<img width="100%" src="https://user-images.githubusercontent.com/39271166/201465324-fdae7d03-ba1f-4aa4-9d48-7e04f2290bc7.png"><br>

**「インストールが完了しました！ すぐに使いはじめられます！」と表示されたら、KonomiTV サーバーのインストールは完了です！おつかれさまでした！！🎉🎊**  
インストーラーに記載されている URL から、KonomiTV の Web UI にアクセスしてみましょう！  

**通常、`(イーサネット)` または `(Wi-Fi)` の URL が家の中からアクセスするときの URL 、`(Tailscale)` の URL が外出先（家の外）から Tailscale 経由でアクセスするときの URL になります。**  

> [!NOTE]  
> `https://my.local.konomi.tv:7000/` の URL は、KonomiTV サーバーをインストールした PC 自身を指す URL ([ループバックアドレス](https://wa3.i-3-i.info/word1101.html)) です。  
> `(Tailscale)` とつく URL は、事前に Tailscale を導入していない場合は表示されません。  
> 外出先からのアクセス自体は、Tailscale をいつ導入したかに関わらず、Tailscale が起動していれば問題なく行えます。

KonomiTV サーバーは Windows サービス (Windows) / PM2 サービス (Linux) / Docker サービス (Linux-Docker) としてインストールされているので、サーバー PC を再起動したあとも自動的に起動します。

もし再起動後に KonomiTV にアクセスできない場合は、`server/logs/KonomiTV-Server.log` に出力されているエラーメッセージを確認してください。

> [!TIP]  
> **ぜひこの機会に KonomiTV の公式 Twitter をフォローしていただけると嬉しいです！**  
> KonomiTV の開発進捗やユーザーのみなさんへのお知らせなどを随時ツイートしています。  
> 各種 Tips も発信していますので、もし導入時にわからない箇所があれば、一度ツイートを検索してみると解決策が見つかるかもしれません。
> 
> [![Twitter](https://img.shields.io/twitter/follow/KonomiTV?style=social)](https://twitter.com/TVRemotePlus)

### デスクトップアプリ・スマホアプリとして使う

<img width="100%" src="https://user-images.githubusercontent.com/39271166/201473243-e246802f-0100-4e6a-bb0e-4247f784bb3b.png"><br>

**PC 版 Chrome や Edge では、URL バー右のアイコン → [アプリをインストール] から、KonomiTV をブラウザバーのないデスクトップアプリとしてインストールできます！**  
ブラウザバーが表示されない分、より映像に没頭できますし、画面も広く使えます。私も KonomiTV をデスクトップアプリとして使っています。  
タスクバーや Dock に登録しておけば、起動するのも簡単です。ぜひお試しください。

> [!NOTE]  
> デスクトップアプリとしてインストールしない場合は、[サイトの設定] から自動再生を [許可する] にしておくと、テレビをスムーズに視聴できます。

<img width="100%" src="https://user-images.githubusercontent.com/39271166/201473798-97aa818a-0474-46bc-b56a-0c49f281e92a.jpg"><br>

**Android Chrome では下に表示される [ホーム画面に追加] またはメニューの [アプリをインストール] から、iPhone / iPad Safari では共有メニュー → [ホーム画面に追加] から、それぞれ KonomiTV をブラウザバーのないスマホアプリとしてインストールできます！**

スマホは画面が小さいので、アプリとしてインストールした方が画面が広くなって使いやすいです。私も KonomiTV をスマホアプリとして使っています。こちらもぜひお試しください。

> [!WARNING]  
> 現状、iPhone / iPad Safari で KonomiTV をスマホアプリとしてインストールすると、Safari のバグの影響で Picture-in-Picture ボタンが利用できなくなります。  
> とはいえ Picture-in-Picture が不要であれば、アプリとしてインストールした方が圧倒的に快適です。

> [!NOTE]  
> [PWA (Progressive Web Apps)](https://developer.mozilla.org/ja/docs/Web/Progressive_web_apps) という、Web アプリを通常のネイティブアプリのように使えるようにする技術を利用しています。  
> 将来的には PWA だけでなく、より快適に利用できるようにした iOS 向けアプリと Android 向けアプリ (いわゆるガワアプリ) をリリースする予定です。

### フィードバックのお願い

**KonomiTV はまだまだ開発中のソフトウェアです。**

機能が多岐に渡ることと、もとよりテレビのストリーミングという特殊で複雑な技術を扱っていることから、テストが追いつかず慢性的な検証不足に陥っています。  
できるだけ手元の環境で検証やテストを行うようにはしていますが、すべての環境や条件を網羅できているわけではありませんし、不具合や問題が残っている可能性は十分にあります。

**もし KonomiTV を使っていて、何か不具合や問題が発生した場合は、ぜひ [Google フォーム](https://docs.google.com/forms/d/e/1FAIpQLScWKzmfCat4w9n9Jp4_P1dIFzewzV4qO-7_BJOcs5Zdvt6yPA/viewform) からフィードバックをお願いします…！！**  
**フィードバックしていただけると、KonomiTV の品質改善に大いに役立ちます！**

> [!NOTE]  
> できればマイナーな条件や機能の組み合わせで問題が出ないか、各自でテストしていただけるととても助かります…！  
> その際、フィードバックフォームには試した環境や条件などを詳細に記載していただけると、問題の再現性が高まります。
>
> KonomiTV ではユーザビリティ (使いやすさ) を第一に考えて UI や細部の機能を緻密に設計しています。  
> 「〇〇の機能/画面が使いづらい」といったフィードバックや、新しい機能のリクエストも大歓迎です。

みなさんからのフィードバックにすべて応えることはできませんが、いただいたフィードバックは KonomiTV の機能向上や改善に役立てさせていただきます！

<img width="100%" src="https://github.com/user-attachments/assets/b262e652-bffc-4466-b5bb-005a3ec6db10"><br>

## 付録

### Twitter 実況機能について

2023年7月以降、[Twitter のサードパーティー API の有料化（個人向け API の事実上廃止）](https://www.watch.impress.co.jp/docs/news/1475575.html) により、従来の連携方法では KonomiTV から Twitter にアクセスできなくなりました。

そこで KonomiTV では、**[Chrome 拡張機能「GET cookies.txt LOCALLY」](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) を使い、ブラウザから Netscape 形式でエクスポートした、[Web 版 Twitter](https://x.com/) の Cookie データによる Twitter 連携に対応しています。**

**ここで入力した Cookie データは、ローカルの KonomiTV サーバーにのみ、暗号化の上で保存されます。**  
Cookie データが Twitter API 以外の外部サービスに送信されることは一切ありません。

> [!WARNING]
> 不審判定されないよう様々な技術的対策を施してはいますが、**非公式な方法で無理やり実装しているため、今後の Twitter の仕様変更や不審判定基準の変更により、アカウントがロック・凍結される可能性も否定できません。**  
> 自己の責任のもとでご利用ください。
>
> **📢 念のため、なるべく [X Premium](https://x.com/i/premium_sign_up) に加入している Twitter アカウントでの利用をおすすめします。**  
> Basic プランでは [X Pro (新 TweetDeck)](https://pro.x.com/) が使えないため、凍結避け効果は薄いと思われます。  
> また、万が一の凍結リスクに備え、**実況専用に作成したサブアカウントでの連携をおすすめします。**

> [!NOTE]
> 📢 v0.13.0 以降では、**[ヘッドレスブラウザ（ウインドウが表示されないブラウザ）を使って](https://github.com/tsukumijima/KonomiTV/blob/master/server/app/utils/TwitterScrapeBrowser.py) 、[Web 版 Twitter からの API コールと全く同じ方法で API リクエストを送る](https://github.com/tsukumijima/KonomiTV/blob/master/server/static/zendriver_setup.js) ように改良しました！**
>
> これまで不審判定されないよう [様々な技術的対策](https://github.com/tsukumijima/tweepy-authlib) を施してきましたが、2025年11月に KonomiTV と同様の方法で Twitter API にアクセスしていた [OldTweetDeck のユーザーが一時的に大量凍結される騒動](https://arkxv.com/blog/x-suspended/) ([詳細](https://github.com/dimdenGD/OldTweetDeck/issues/459#issuecomment-3499066798)) が起きたことを踏まえ、より堅牢で安全なアプローチに切り替えました。
>
> **この関係で、Twitter 実況機能を使うには、KonomiTV サーバー側に [Google Chrome](https://www.google.com/chrome/) または [Brave](https://brave.com/ja/) がインストールされている必要があります。**  
> なお、Linux (Docker) 環境では既に Docker イメージに含まれているため不要です。  
> また、Twitter 実況機能を使わないならインストールする必要はありません。
>
> ヘッドレスブラウザは、視聴画面で Twitter パネル内の各機能を使うときにバックグラウンドで自動的に起動し、使わなくなったら自動終了します。  
> Twitter 実況機能が使われない場合には起動しません。

KonomiTV で Twitter アカウントを連携するには、以下の手順に従ってください。

#### 1. Chrome 拡張機能「GET cookies.txt LOCALLY」をインストールする

<img width="70%" src="https://github.com/user-attachments/assets/6ed63df2-c007-4f5f-a3b5-54b3d2225afd"><br>

まず、**PC 版 Chrome に [Chrome 拡張機能「GET cookies.txt LOCALLY」](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) をインストールします。**

<img width="30%" src="https://github.com/user-attachments/assets/fa20a726-b85d-4960-bac6-8614e98e6c35"><br>

次に、**拡張機能アイコンを押し、その後 [GET cookies.txt LOCALLY] の右にある `︙` → [拡張機能を管理] を押します。**

<img width="70%" src="https://github.com/user-attachments/assets/90416512-4798-495c-9eee-5488b077251d"><br>

すると Chrome 拡張機能「GET cookies.txt LOCALLY」の設定ページが開くので、**下の方にある [シークレット モードでの実行を許可] をオンにします。**  
これにより、後述するシークレットウインドウでも、この拡張機能を実行できるようになります。

#### 2. シークレットウインドウで Web 版 Twitter にログインする

<img width="50%" src="https://github.com/user-attachments/assets/1346c834-60ac-4f32-816e-27bb601f336c"><br>

[新しいシークレットウインドウを開く」をクリックし、シークレットウインドウを開きます。  
次に、**そのシークレットウインドウで [Web 版 Twitter](https://x.com/) にアクセスし、連携したいアカウントにログインします。**

> [!IMPORTANT]
> **万が一の意図しないアカウントが不審判定される事態を避けるため、必ず連携したいアカウントにのみログインしてください。**  
> わざわざシークレットウインドウで実行しているのは、複数アカウントでログインしている場合に、同時ログイン中の他アカウントと関連付けが可能な情報を Cookie に含めないようにするためです。

#### 3. Chrome 拡張機能を起動して Cookie データをエクスポートする

<img width="70%" src="https://github.com/user-attachments/assets/a90b8675-e233-454e-8eea-b3f8e1211502"><br>

Web 版 Twitter を開いているタブで、**「GET cookies.txt LOCALLY」のアイコンをクリックし、UI 画面を開きます。**  
その後、[Export Format:] が [Netscape] になっていることを確認してから [Copy] ボタンを押し、x.com の Cookie データをクリップボードにコピーします。

#### 4. KonomiTV の設定画面で Cookie データを入力する

<img width="70%" src="https://github.com/user-attachments/assets/6edb2afd-002f-47fa-814c-ce5616532eb1"><br>

KonomiTV の [設定] → [Twitter] に移動し、**「連携する Twitter アカウントを追加」ボタンをクリックします。**  
**表示されたダイアログの Cookie 入力フォームに、先ほどコピーした Cookie データを貼り付けてください。**

入力が完了したら [ログイン] ボタンを押すと、Cookie データが正しい場合は Twitter アカウントとの連携が完了します。  

> [!TIP]
> **Cookie が正しいのにログインに失敗するときは、何回か再度 [ログイン] ボタンを押してリトライするとうまく行くことがあります。**  
> [ログイン] ボタンを押すと、前述のヘッドレスブラウザが起動します。  
> 内部では、指定された Cookie データでログイン中アカウントの情報をヘッドレスブラウザで経由で取得できるかがチェックします。  
> これらの処理が正常に完了すれば、指定された Cookie データを暗号化の上でデータベースに保存して、ログイン完了となります。

### `https://aa-bb-cc-dd.local.konomi.tv:7000/` の URL について

**この `https://aa-bb-cc-dd.local.konomi.tv:7000/` のフォーマットの URL は、KonomiTV の WebUI に HTTPS でアクセスするための特殊な URL です。**  

aa-bb-cc-dd の部分には、ローカル IP アドレスのうち、. (ドット) を - (ハイフン) に置き換えた値が入ります。  
つまり、サーバー PC のローカル IP アドレスが `192.168.1.11` だったとしたら、`https://192-168-1-11.local.konomi.tv:7000/` という URL になります。

> [!TIP]
> [ループバックアドレス](https://wa3.i-3-i.info/word1101.html) のみ、`https://127-0-0-1.local.konomi.tv:7000/` の代わりに、  
> ・`https://my.local.konomi.tv:7000/`  
> ・`https://local.local.konomi.tv:7000/`  
> ・`https://localhost.local.konomi.tv:7000/`  
> のシンプルな URL でアクセスできます。

通常、自宅のローカル LAN 上の Web サイトには、`http://192.168.1.11:8000/` のような IP アドレス直打ちでの HTTP アクセスがほとんどです。EDCB Material WebUI・TVRemotePlus・Mirakurun・EPGStation などの DTV 関連のソフトでも、同様のアクセス方法が取られてきました。

…ところが、最近のブラウザはインターネット上に公開されている Web サイトのみならず、盗聴のリスクが著しく低いローカル LAN 上の Web サイトにも、HTTPS を要求するようになってきました。  
すでに PWA の主要機能である [Service Worker](https://developer.mozilla.org/ja/docs/Web/API/Service_Worker_API) などをはじめ、近年追加された多くの Web API の利用に HTTPS が必須になってしまっています。こうした強力な API が HTTP アクセスでは使えないことが、KonomiTV を開発する上で大きな制約になっていました。

**そこで KonomiTV では、過去に例のない非常に特殊な仕組みを使い、プライベートネットワーク上の Web サービスにも関わらず [自己署名証明書](https://wa3.i-3-i.info/word18213.html) のインストールなしで HTTPS でアクセスできるようにしました。**  
具体的には、Let's Encrypt の DNS 認証 / ワイルドカード証明書・ワイルドカード DNS・Keyless SSL の3つの技術を組み合わせています。**[tsukumijima/Akebi](https://github.com/tsukumijima/Akebi)** に技術解説とソースコードを載せていますので、よろしければご覧ください。

**この仕組み (Akebi) を使うには、`https://192-168-1-11.local.konomi.tv:7000/` のような HTTPS URL でアクセスする必要があります。** 当然ですが、プライベート IP アドレス単体では正式な証明書を取得できないためです。

> [!NOTE]
> `https://(IPアドレス(.を-にしたもの)).local.konomi.tv:7000/` はすべてのプライベート IP アドレスに対応していますが、セキュリティ上の兼ね合いでグローバル IP アドレスには対応していません。  
> なお、Tailscale の [100.x.y.z アドレス](https://tailscale.com/kb/1015/100.x-addresses/) には対応しています。

> [!NOTE]
> Akebi HTTPS Server の起動時に DNS & Keyless サーバーとの通信が必要な関係で、KonomiTV サーバーはインターネットから隔離されている環境では正常に動作しません。

> [!TIP]
> どうしてもほかの URL でアクセスしたい方向けに、一応サーバー設定 (config.yaml) にカスタム HTTPS 証明書を指定する機能を用意しています。  
> サポートは一切しませんので、すべて理解している方のみ行ってください。

### 設定ファイルの編集

**KonomiTV のサーバー設定は、KonomiTV をインストールしたフォルダにある config.yaml に保存されています。**  

> [!IMPORTANT]  
> **KonomiTV 0.10.0 以降では、サーバー設定を KonomiTV の UI 上で変更できるようになりました！**  
> サーバー設定を変更するには、管理者権限を持つ KonomiTV アカウントでログインし、[設定] → [サーバー設定] に移動してください。  
> KonomiTV サーバー内で一番最初に作成された KonomiTV アカウントには、既定で管理者権限が付与されています。

> [!WARNING]  
> 0.7.1 以下に利用されていた config.yaml と 0.8.0 以降で利用されている config.yaml は、フォーマットの互換性がありません。  
> KonomiTV は開発中のため、今後も設定ファイルの破壊的変更が発生する可能性があります。

> [!WARNING]  
> config.example.yaml は、config.yaml のデフォルトの設定を記載した、config.yaml のひな形となるファイルです。  
> アップデート時に上書きされるため、config.example.yaml は編集しないでください。  

**config.yaml は、インストーラーでインストールした際に自動的に生成されます。**  

以下は主要な設定項目の説明です。  
ほかにも設定項目はありますが、基本的に変更の必要はありません。

#### バックエンドの設定

KonomiTV のバックエンドには、EDCB または Mirakurun / mirakc のいずれかを選択できます。  
`general.backend` に `EDCB` または `Mirakurun` を指定してください。

> [!WARNING]  
> 一部 Windows 環境では localhost の名前解決が遅いため、チューナーが数秒遅れて起動し、ストリーミング開始までの待機時間が長くなる場合があります。    
> **EDCB / Mirakurun と同じ PC に KonomiTV をインストールしている場合、localhost ではなく 127.0.0.1 の利用を推奨します。**

-----

EDCB をバックエンドとして利用する場合は、EDCB (EpgTimerNW) の TCP API の URL (`general.edcb_url`) をお使いの録画環境に合わせて編集してください。

通常、TCP API の URL は `tcp://(EDCBのあるPCのIPアドレス):4510/` になります。接続できない際は、ファイアウォールの設定や EpgTimer Service が起動しているかを確認してみてください。  
前述のとおり、あらかじめ EDCB の事前設定を済ませておく必要があります。

> [!NOTE]  
> TCP API の URL として `tcp://edcb-namedpipe/` と指定すると、TCP API の代わりに名前付きパイプで通信を行います（KonomiTV と EDCB が同じ PC で起動している場合のみ）。

-----

Mirakurun / mirakc をバックエンドとして利用する場合は、Mirakurun / mirakc の HTTP API の URL (`general.mirakurun_url`) をお使いの録画環境に合わせて編集してください。

通常、HTTP API の URL は `http://(Mirakurun/mirakcのあるPCのIPアドレス):40772/` になります。接続できない際は、Mirakurun / mirakc が起動しているかを確認してみてください。

#### エンコーダーの設定

エンコーダーには、ソフトウェアエンコーダーの FFmpeg のほか、ハードウェアエンコーダーの QSVEncC・NVEncC・VCEEncC・rkmppenc を選択できます。  
`general.encoder` に `FFmpeg` / `QSVEncC` / `NVEncC` / `VCEEncC` / `rkmppenc` のいずれかを指定してください。

**ハードウェアエンコーダーを選択すると、エンコードに GPU アクセラレーションを利用するため、CPU 使用率を大幅に下げる事ができます。**  
エンコード速度も高速になるため、お使いの PC で利用可能であれば、できるだけハードウェアエンコーダーを選択することを推奨します。

> [!NOTE]  
> お使いの PC で選択したハードウェアエンコーダーが利用できない場合、ライブストリーミング時にその旨を伝えるエラーメッセージが表示されます。まずはお使いの PC でハードウェアエンコーダーが使えるかどうか、一度試してみてください（設定ファイルの変更後はサーバーの再起動が必要です）。

> [!NOTE]  
> 前述のとおり、Linux 環境で QSVEncC・NVEncC・VCEEncC・rkmppenc を利用する場合は、別途 GPU ドライバーのインストールが必要です。

**QSVEncC は、Intel 製 CPU の内蔵 GPU に搭載されているハードウェアエンコード機能 (Intel QSV) を利用するエンコーダーです。**  
ここ数年に発売された Intel Graphics 搭載の Intel 製 CPU であれば基本的に搭載されているため、一般的な PC の大半で利用できます。内蔵 GPU なのにもかかわらず高速で、画質も良好です。  

> [!WARNING]  
> Linux 版の Intel QSV は、Broadwell (第5世代) 以上の Intel CPU でのみ利用できます。そのため、Haswell (第4世代) 以下の CPU では、QSVEncC を利用できません。  
> なお、Windows 版の Intel QSV は、Haswell (第4世代) 以下の CPU でも利用できます。

**NVEncC は、Geforce などの NVIDIA 製 GPU に搭載されているハードウェアエンコード機能 (NVENC) を利用するエンコーダーです。**  
高速で画質も QSV より若干良いのですが、Geforce シリーズでは同時にエンコードが可能なセッション数が 3 に限定されているため、同時に 3 チャンネル以上視聴することはできません。  
同時に 4 チャンネル以上視聴しようとした場合、KonomiTV では「NVENC のエンコードセッションが不足しているため、ライブストリームを開始できません。」というエラーメッセージが表示されます。

**VCEEncC は、Radeon などの AMD 製 GPU に搭載されているハードウェアエンコード機能 (AMD VCE) を利用するエンコーダーです。**  
QSVEncC・NVEncC に比べると安定しない上に、画質や性能もあまり良くありません。もし QSVEncC・NVEncC が使えるならそちらを使うことをおすすめします。

**rkmppenc は、RK3588 などの Rockchip 製 ARM SoC に搭載されているハードウェアエンコード機能 (mpp) を利用するエンコーダーです。**  
画質は VCEEncC と同等くらいですが、ARM デバイスで利用できるハードウェアエンコーダーとしては最高レベルの性能を誇ります。

#### リッスンポートの設定

`server.port` に、KonomiTV サーバーのリッスンポートを指定してください。  
デフォルトのリッスンポートは `7000` です。  

> [!NOTE]  
> インストーラーでのインストール時にポート 7000 がほかのサーバーソフトと重複している場合は、代わりのポートとして 7100 (7100 も利用できない場合は、さらに +100 される) が自動的にデフォルトのリッスンポートに設定されます。

基本的に変更の必要はありません。変更したい方のみ変更してください。

#### 録画済み番組の保存先フォルダの設定

`video.recorded_folders` に、録画済み番組の保存先フォルダを指定してください。

デフォルトの録画済み番組の保存先フォルダは、インストーラーで入力したフォルダが自動的に設定されています。  
録画済み番組の保存先フォルダを変更したくなったときは、この設定を変更してください。

#### アップロードしたキャプチャ画像の保存先フォルダの設定

`capture.upload_folders` に、アップロードしたキャプチャ画像の保存先フォルダを指定してください。

クライアントの [キャプチャの保存先] 設定で [KonomiTV サーバーにアップロード] または [ブラウザでのダウンロードと、KonomiTV サーバーへのアップロードを両方行う] を選択したときに利用されます。

デフォルトの保存先フォルダは、インストーラーで入力したフォルダが自動的に設定されています。  
保存先フォルダを変更したくなったときは、この設定を変更してください。

-----

<img width="100%" src="https://github.com/user-attachments/assets/5576f7eb-71d3-4a56-8104-22ad4c949818"><br>

<img width="100%" src="https://user-images.githubusercontent.com/39271166/201438534-10a19a9e-56ef-4c9e-88c2-2198de76979d.png"><br>

**サーバー設定の変更を反映するには、KonomiTV サーバー (KonomiTV Service) の再起動が必要です。**

> [!IMPORTANT]  
> **KonomiTV 0.10.0 以降では、KonomiTV の UI から KonomiTV サーバーを再起動できるようになりました！**  
> KonomiTV サーバーを再起動するには、管理者権限を持つ KonomiTV アカウントでログインし、[設定] → [サーバー設定] → [メンテナンス] に移動してください。  
> KonomiTV サーバー内で一番最初に作成された KonomiTV アカウントには、既定で管理者権限が付与されています。

- Windows:「サービス」アプリを開いた後、サービス一覧の中から KonomiTV Service を探して、右クリックメニューから [再起動] をクリックしてください。   
  - または、管理者権限のコマンドラインから `sc stop "KonomiTV Service"; sc start "KonomiTV Service"` を実行してください。
- Linux: `sudo pm2 restart KonomiTV` を実行してください。
  - `sudo` をつけないと正しく実行できません (KonomiTV は root ユーザーの PM2 プロファイルに登録されているため) 。
- Linux (Docker): KonomiTV をインストールしたフォルダで `docker compose restart` を実行してください。

なお、config.yaml が存在しなかったり、設定項目が誤っているとサーバーの起動の時点でエラーが発生します。  
その際は `server/logs/KonomiTV-Server.log` に出力されているエラーメッセージに従い、config.yaml の内容を確認してみてください。

### 局ロゴ

KonomiTV には、放送波から取得できるものよりも遥かに高画質な局ロゴが同梱されています。  
ほとんどの地上波チャンネル・BS/CS の全チャンネル・一部の CATV のコミュニティチャンネルをカバーしており、受信できるチャンネルに対応する局ロゴが同梱されていれば、それが利用されます。

> [!NOTE]  
> 放送波から取得できる局ロゴは最高でも 64x36 で、現代的なデバイスで見るにはあまりにも解像度が低すぎます。とはいえ、局ロゴがなければぱっとチャンネルを判別できなくなり、ユーザー体験が悪化してしまいます。  
> さらに、局ロゴは何らかの事情で取得できていないことも考えられます。こういった事情もあり、高画質な局ロゴを同梱しています。

チャンネルに対応する局ロゴが同梱されていない場合は、Mirakurun・EDCB のいずれかから局ロゴの取得を試みます。Mirakurun または EDCB から局ロゴを取得できなかった場合は、デフォルトの局ロゴが利用されます。    

- Mirakurun:
  - Mirakurun の API から局ロゴの取得を試みます。  
  - 基本的には何もしなくても局ロゴが収集されているはずです。
  - mirakc は局ロゴの収集に対応していないため、局ロゴが同梱されていないチャンネルでは、常にデフォルトの局ロゴが利用されます。
- EDCB:
  - EDCB のロゴデータ保存機能で収集された局ロゴの取得を試みます。
    - ロゴデータ保存機能は [2020年10月に追加された](https://github.com/xtne6f/EDCB/commit/0457241ccdd83ae9847ab15a16157d04927b72ce) もので、KonomiTV が動作する 220122 以降のバージョンの EDCB なら問題なく利用できます。
  - EpgDataCap_Bon → [設定] → [EPG取得設定] → [ロゴデータを保存する] にチェックが入っていて、なおかつ `EDCB/Settings/LogoData/` にロゴデータ (PNG) がすでに保存されていることが条件です。

> [!NOTE]  
> 同梱されているロゴは `server/static/logos/` に `NID(ネットワークID)-SID(サービスID).png` (解像度: 256×256) のフォーマットで保存されています。  
> チャンネルのネットワーク ID とサービス ID がわかっていれば、自分で局ロゴ画像を作ることも可能です。

<img width="100%" src="https://github.com/user-attachments/assets/4e5e173e-e89a-4e17-8266-1155e8ee2f6a"><br>

## FAQ

### Web UI にアクセスすると 502 Bad Gateway エラーが表示される

KonomiTV サーバーの起動中と考えられます。しばらく待ってから再度アクセスしてみてください。

数分待ってもアクセスできない場合は、KonomiTV サーバーがエラー終了している可能性があります。`server/logs/KonomiTV-Server.log` に出力されているエラーログを確認してみてください。

### Web UI にアクセスすると「Client sent an HTTP request to an HTTPS server.」と表示される

エラーメッセージの通り、`http://` でアクセスしてしまっているときに表示されます。  
KonomiTV サーバーは HTTPS で起動しているため、Web UI には `https://` で始まる URL でアクセスする必要があります。

### Web UI にアクセスすると「このサイトは安全に接続できません」「～から無効な応答が送信されました。」(ERR_SSL_PROTOCOL_ERROR) と表示される

[`https://aa-bb-cc-dd.local.konomi.tv:7000/` の URL について](#httpsaa-bb-cc-ddlocalkonomitv7000-の-url-について) の項目で説明した通り、KonomiTV では過去に例のない非常に特殊な仕組みを使い、[自己署名証明書](https://wa3.i-3-i.info/word18213.html) のインストールなしで HTTPS でアクセスできるようにしています。

Web UI には `https://(IPアドレス(.を-にしたもの)).local.konomi.tv:7000/` のフォーマットの HTTPS URL (例: `https://192-168-1-11.local.konomi.tv:7000/`) でアクセスしてください。  
URL が少し長いので、適宜ブックマークやホーム画面に追加しておくと便利です。

> [!IMPORTANT]  
> 上記のフォーマット以外の URL (例: `https://localhost:7000/`・`https://192.168.1.11:7000/`) では証明書や HTTPS の通信エラーが発生し、Web UI にアクセスできない仕様になっています。  
> 当然ですが、プライベート IP アドレス単体では正式な証明書を取得できないためです。 

### Web UI にアクセスすると、DNS エラーが表示される

**お使いのルーターで DNS Rebinding Protection が有効になっている可能性があります。**  
KonomiTV は Akebi (前述) に依存しているため、DNS Rebinding Protection を無効にしなければアクセスできません。

適宜ルーターの設定を変更するか、お使いのデバイスの DNS を 1.1.1.1 や 8.8.8.8 などの公開 DNS サーバーに変更してください。

> [!TIP]  
> OpenWRT では、Rebind Protection のチェックボックスを外すと無効化できるようです。

### ライブストリーミングの視聴が安定しない・途切れ途切れになる

原因はいくつか考えられますが、回線速度が遅かったり、不安定な通信環境であることが考えられます。  

#### 全般

- **KonomiTV サーバーをインストールした PC が有線 LAN に接続されていない可能性があります。**
  - **KonomiTV サーバーをインストールした PC はできるだけ有線 LAN に接続してください。** Wi-Fi 接続だけでも動作しますが、Wi-Fi 環境次第では通信が不安定になることがあります。
  - LAN 端子がないなどやむを得ず Wi-Fi 接続だけで使う場合は、PC をできるだけ Wi-Fi ルーターに近い場所に配置するなど、安定して通信できることを確認してください。
- **デバイスのスペック不足の可能性があります。**
  - KonomiTV はブラウザでリッチな視聴体験を実現していますが、その反面どうしてもネイティブアプリに比べると動作が重いです。特に **Android のローエンドや数年前の古いスマホでは、スペック不足でストリーミングが安定しないことがあります。**
  - 根本的には新しいデバイスに買い替える以外の方法はありませんが、**描画処理が重たいニコニコ実況のコメント表示や低遅延ストリーミングをオフにすると、以前より安定して再生できることが多いです。**
  - また、画質を 720p 以下に下げて視聴するのも有効です。古いスマホでは液晶の解像度が低めことも多いので、720p 以下に下げても十分視聴に耐えると思います。

#### KonomiTV サーバーのある自宅の Wi-Fi につないで視聴しているとき

- **遅い Wi-Fi アクセスポイントに接続されている可能性があります。**
  - 5GHz 帯の Wi-Fi アクセスポイント (SSID に `5G`・`A` と入っていることが多い) に接続し直してみてください。
  - 5GHz 帯の Wi-Fi アクセスポイントに対応していない古いデバイスをお持ちの方は、この機会に買い替えや 5GHz 対応の USB Wi-Fi ドングルの購入をおすすめします…。
- **Wi-Fi ルーターとの距離が離れている可能性があります。Wi-Fi ルーターに近い場所に移動するか、より近い Wi-Fi アクセスポイントに接続し直してください。**
  - Wi-Fi ルーターとの距離が離れていると、遮蔽物や減衰の影響で通信が不安定になることがあります。
  - デバイスを Wi-Fi ルーターにできるだけ近づけた状態でストリーミングが安定するなら、Wi-Fi 環境自体に問題がある可能性が高いです（電波干渉が発生している、など）。との距離が離れておらず、通信速度が十分に出ていることを確認してください。
- **低遅延ストリーミングをオフにしてみてください。**
  - 低遅延ストリーミングがオンのときは、放送波との遅延を最短 0.9 秒にまで抑えて視聴できます。ただし、回線速度が遅かったり不安定な通信環境だと、ストリーミングが安定しないことがあります。
  - 低遅延ストリーミングをオフにすると、遅延が 5 秒以上になりますが、不安定な通信環境でも安定して視聴できます。
  - 低遅延ストリーミングのオン/オフは [設定] → [全般] から変更できます。
- **ストリーミング画質を下げてみてください。**
  - デフォルトのストリーミング画質の 1080p では、平均約 10Mbps のデータ量を消費します (通信節約モードがオンなら約 3Mbps に減少する) 。データ量はシーン次第で上下しますが、一般的に動きの激しいシーンや実写ではデータ量が多くなります。
  - 画質を下げることで、回線速度が遅くても安定して視聴できるようになります。
  - スペックの低いデバイスでは、画質を下げるとストリーミングが安定することがあります。
  - デフォルトのストリーミング画質は [設定] → [全般] から変更できます。

#### 外出先 (自宅以外) から Tailscale 経由で視聴しているとき
 
- **低遅延ストリーミングをオフにしてみてください。**
  - 低遅延ストリーミングがオンのときは、放送波との遅延を最短 0.9 秒にまで抑えて視聴できます。ただし、**モバイルデータ通信 (4G) やフリー Wi-Fi などのネットワーク遅延の大きい不安定な通信環境では、ストリーミングが安定しないことが多いです。**
    - 海外や他の都道府県など地理的に離れた場所から視聴するときは、ネットワーク遅延が特に大きくなります。
  - **低遅延ストリーミングをオフにすると、遅延が 5 秒以上になりますが、不安定な通信環境でも比較的安定して視聴できます。**
  - 低遅延ストリーミングのオン/オフは [設定] → [全般] から変更できます。
- **ストリーミング画質を下げてみてください。**
  - デフォルトのストリーミング画質の 1080p では、平均約 10Mbps のデータ量を消費します (通信節約モードがオンなら約 3Mbps まで減る)  。データ量はシーン次第で上下しますが、一般的に動きの激しいシーンや実写ではデータ量が多くなります。
  - 場所にもよりますが、モバイルデータ通信 (4G) やフリー Wi-Fi では通信速度があまり出ないことが多いです。**画質を下げることで、回線速度が遅くても安定して視聴できるようになります。**
    - スマホの小さな画面では画質を 720p や 540p まで下げても見た目ほとんど変わらないので、そのあたりまで画質を下げるのがおすすめです。
  - **画質を下げることで、モバイルデータ通信 (4G/5G) で視聴するときのデータ通信量 (いわゆるギガ、パケ代) も抑えられます。** 360p や 240p まで下げれば、データ通信量をかなり削減できます。
    - PC サイズの画面で 360p はさすがに厳しいですが、スマホサイズの画面なら 360p でもそれなりに視聴に耐える印象です。
  - スペックの低いデバイスでは、画質を下げるとストリーミングが安定することがあります。
  - デフォルトのストリーミング画質は [設定] → [全般] から変更できます。
- **通信節約モードを有効にしてみてください。**
  - 通信節約モードでは、H.265 / HEVC という圧縮率の高いコーデックを使い、画質はほぼそのまま、通信量を**通常の 1/2 程度**に抑えながら視聴できます。
  - **外出先からモバイルデータ通信 (4G/5G) で視聴するときは常に通信節約モードをオンにしておくことをおすすめします。** 画質を保ったまま、データ通信量 (いわゆるギガ、パケ代) をかなり削減できます。
  - ただし、サーバー PC の GPU が H.265 / HEVC でのハードウェアエンコードに対応している必要があります。視聴開始時に「H.265/HEVC でのエンコードに対応していません」というエラーメッセージが表示された場合は、通信節約モードは使えません。
  - 通信節約モードのオン/オフは [設定] → [全般] から変更できます。

<img width="100%" src="https://github.com/user-attachments/assets/0b034bfa-6021-442b-a81e-046722ff3469"><br>

## 開発者向け情報

VS Code を開発に利用しています。  
開発時に推奨する VS Code 拡張機能は [.vscode/extensions.json](.vscode/extensions.json) に記述されています。

### 開発版 KonomiTV のインストール (開発環境の構築)

ここでは、master ブランチにある最新の開発版 KonomiTV を手動でインストールする方法を説明します。  
サポートは行えませんので、技術的な知識がある方のみお試しください。

- Python 3.11.x
- Poetry (最新版)
- Node.js 20.16.0 (クライアントの開発やビルドを行う場合のみ)
- yarn 1.x (クライアントの開発やビルドを行う場合のみ)

事前に、上記ソフトウェアをインストールしている必要があります。

開発環境は Windows 10 (x64) と Ubuntu 20.04 LTS (x64) で動作を確認しています。  
なお、開発環境の Docker での動作は想定していません。サードパーティーライブラリなどの兼ね合いで、Docker では開発時の柔軟性が低くなってしまうためです。

```bash
# Windows は PowerShell 7 で、Ubuntu は bash での実行を想定

# リポジトリの clone
## /Develop の部分は適宜変更すること
cd /Develop
git clone https://github.com/tsukumijima/KonomiTV.git

# 設定ファイルのコピーと編集
## config.yaml は適切に構成されている必要がある (さもなければサーバーが起動しない)
cd KonomiTV/
# Windows
Copy-Item -Force config.example.yaml config.yaml
# Linux:
cp -a config.example.yaml config.yaml
nano config.yaml

# 一時的な Poetry 仮想環境の構築 (poetry run task update-thirdparty の実行に必要)
cd server/
poetry env use 3.11
poetry install --no-root --with dev

# 最新のサードパーティーライブラリを GitHub Actions からダウンロード
## 本番環境用のスタンドアローン版 Python もサードパーティーライブラリに含まれている
poetry run task update-thirdparty

# サードパーティーライブラリ内のスタンドアローン版 Python を明示的に指定して Poetry 仮想環境を再構築
## ローカル環境の Python 3.11 を使うと、組み込みの SQLite バージョンが古いことによる問題が発生する可能性がある
## サードパーティーライブラリ内の Python には最新の SQLite が組み込まれているため、そちらを明示的に利用すべき
# Windows:
Remove-Item -Recurse -Force .venv/
poetry env use /Develop/KonomiTV/server/thirdparty/Python/python.exe
# Linux
rm -rf .venv/
poetry env use /Develop/KonomiTV/server/thirdparty/Python/bin/python

# 依存パッケージのインストール
poetry install --no-root --with dev
```

### サーバーの起動

KonomiTV サーバー (KonomiTV.py) を起動すると、内部で [Uvicorn](https://github.com/encode/uvicorn) と [Akebi HTTPS Server](https://github.com/tsukumijima/Akebi) が起動されます。

Uvicorn は ASGI サーバーで、FastAPI で記述された KonomiTV のアプリケーションサーバーを実行します。  
また、KonomiTV の場合は `client/dist/` 以下の静的ファイル (クライアント) を配信する Web サーバーの役割も兼ねています。  
Akebi HTTPS Server は、自己署名証明書なしでプライベートネットワーク上の HTTP サーバーに HTTPS 化するためのリバースプロキシサーバーです。

実際にユーザーがアクセスするのは Uvicorn の HTTP (HTTP/1.1) サーバーのリバースプロキシである、Akebi HTTPS Server による HTTPS (HTTP/2) サーバーになります。  
Uvicorn も Akebi HTTPS Server も KonomiTV.py の起動時に透過的に同時起動されるため、一般のユーザーが意識する必要はありません。

```bash
cd /Develop/KonomiTV/server/

# リロードモードで起動する
poetry run task dev

# 通常モードで起動する
poetry run task serve
```

サーバーの起動方法には、リロードモードと通常モードの2つがあります。

通常モードは、本番環境 (リリース版) での Windows サービスや PM2 サービスで起動されるサーバーと同じモードになります。  
より厳密にサービス起動時の環境を再現したい際は、sudo などで root 権限/管理者権限で実行してください。

リロードモードでは、`server/` 以下のコードを変更すると自動でサーバーが再起動されます。  
コードが変更されると今まで起動していたサーバープロセスは強制終了され、新しいサーバープロセスが起動されます。

> [!WARNING]  
> リロードモードかつ EDCB バックエンド利用時、サーバーを終了するタイミング次第では、EDCB のチューナープロセス (EpgDataCap_Bon) が終了されないままになることがあります。  
> 必ずログでエンコードタスクが終了 (Offline) になったことを確認してから、サーバーを終了してください。

> [!WARNING]  
> Python の asyncio の制限により、リロードモードは事実上 Windows 環境では利用できません。  
> 正確には外部プロセス実行を伴うストリーミング視聴を行わなければ一応動作しますが、予期せぬ問題が発生する可能性があります。  
> この関係もあり、現在の開発は Linux (Ubuntu 20.04 LTS) をメインに行っています。

起動したサーバーは、`https://my.local.konomi.tv:7000/` でリッスンされます。
特にリッスン範囲の制限はしていないので、プライベートネットワーク上の他の PC やスマホからもアクセスできます。  
サーバーを終了するときは、Ctrl+C を押してください。

起動中のサーバーのログは、`server/logs/KonomiTV-Server.log` に保存されます。  
同時起動される Akebi HTTPS Server のログは `server/logs/Akebi-HTTPS-Server.log` に保存されます。

> [!NOTE]  
> サーバー設定でデバッグモード (general -> debug) を有効にすると、デバッグログも出力されるようになります。開発環境では常にデバッグモードにしておくことをおすすめします。  
> さらにエンコーダーのログ (general -> debug_encoder) を有効にすると、ライブ視聴時のエンコーダーのログが `server/logs/KonomiTV-Encoder-(ストリームID).log` に保存されます。

API ドキュメント (Swagger) は https://my.local.konomi.tv:7000/api/docs にあります。  
API ドキュメントは FastAPI によって自動生成されたものです。  
その場で API リクエストを試せたり、グラフィカルに API ドキュメントを参照できたりととても便利です。ぜひご活用ください。

### Windows / PM2 サービスのインストールと起動

ここでは、上記手順で構築した開発環境を Windows / PM2 サービスとして起動する方法を説明します。

#### Windows サービス

事前に PowerShell 7 を管理者権限で起動しておいてください。  
管理者権限でない場合、Windows サービスのインストールに失敗します。

> [!WARNING]  
> KonomiTV の Windows サービスは相当強引な手法で実装しているため (そうせざるを得なかった…) 、開発状況次第では Windows サービスでのみ動作しなくなっている可能性があります。  
> 動作不良時は、一度 `poetry run task serve` で起動できるかや、`server/logs/KonomiTV-Server.log` 内のログを確認してみてください。

> [!NOTE]  
> KonomiTV-Service.py は、KonomiTV の Windows サービスの管理を行うユーティリティスクリプトです。  
> `poetry run python KonomiTV-Service.py --help` と実行すると、利用できるコマンドの一覧が表示されます。

```powershell
cd /Develop/KonomiTV/server/

# Windows サービスのインストール
## インストールと同時に自動起動 (OS 起動後数分遅延してから) も設定される
poetry run python KonomiTV-Service.py install --username (ログオン中のユーザー名) --password (ログオン中ユーザーのパスワード)

# Windows サービスの起動
## sc start "KonomiTV Service" でも起動できる
poetry run python KonomiTV-Service.py start

# Windows サービスの停止
## sc stop "KonomiTV Service" でも停止できる
poetry run python KonomiTV-Service.py stop

# Windows サービスのアンインストール
## アンインストールと同時に自動起動の設定も解除される
poetry run python KonomiTV-Service.py stop  # サービスを停止してからアンインストールすること
poetry run python KonomiTV-Service.py uninstall
```

#### PM2 サービス

事前に root 権限で PM2 がインストールされている必要があります。

```bash
cd /Develop/KonomiTV/server/

# PM2 サービスのインストール
sudo pm2 start .venv/bin/python --name KonomiTV -- KonomiTV.py

# PM2 のスタートアップ設定
sudo pm2 startup

# PM2 への変更の保存
sudo pm2 save

# PM2 サービスの起動
sudo pm2 start KonomiTV

# PM2 サービスの停止
sudo pm2 stop KonomiTV

# PM2 サービスのアンインストール
sudo pm2 stop KonomiTV  # サービスを停止してからアンインストールすること
sudo pm2 delete KonomiTV
sudo pm2 save
```

### クライアントの開発・ビルド

クライアント (フロントエンド) は Vue.js 3.x の SPA (Single Page Application) で開発されており、コーディングとビルドには少なくとも Node.js が必要です。  
Node.js 20.16.0 / yarn 1.x で開発しています。

```bash
cd /Develop/KonomiTV/client/

# 依存パッケージのインストール
yarn install

# クライアントの開発サーバーの起動
yarn dev

# クライアントのビルド
## ビルド成果物は client/dist/ に出力され、サーバー側の HTTP サーバーによって配信される
yarn build
```

起動したクライアントの開発サーバーは、`https://my.local.konomi.tv:7001/` でリッスンされます。  
`client/` 以下のコードを変更すると、自動で差分が再ビルドされます。  
特にリッスン範囲の制限はしていないので、プライベートネットワーク上の他の PC やスマホからもアクセスできます。  
サーバーを終了するときは、Ctrl+C を押してください。

> [!WARNING]  
> `yarn dev` でクライアントの開発サーバーを起動する際は、必ず `poetry run task dev` でサーバー側の開発サーバーも起動してください。  
> クライアントの開発サーバーはフロントエンド側の静的ファイルのみをホスティングしますが、サーバー側の開発サーバーは静的ファイルの配信だけでなく、API サーバーとしての役割も兼ねています。  
> このため、クライアントの開発サーバーのみ、クライアントからのサーバー API のアクセス先を `https://(サーバーと同じIPアドレス).local.konomi.tv:7000/` に固定しています。

クライアントの静的ファイルは、`client/dist/` に配置されているビルド済みの成果物を、サーバー側で配信するように構成されています。  
そのため、`yarn build` でクライアントのビルドを更新したのなら、サーバー側で配信される静的ファイルも同時に更新されることになります。

## 寄付・支援について

とてもありがたいことに寄付したいという方が複数いらっしゃったので、**今のところ [アマギフ (Amazon ギフト券)](https://www.amazon.co.jp/b?node=3131877051&tag=tsukumijima-22)・PayPay のみ受けつけています。**  

特典などは今のところありませんが、それでも寄付していただけるのであれば、アマギフの URL か PayPay の QR コードを [Twitter の DM (クリックすると DM が開きます)](https://twitter.com/messages/compose?recipient_id=1194724304585248769) か `tvremoteplus[at]gmail.com` まで送っていただけますと、大変開発の励みになります…🙏🙏

**一応 [Amazon のほしい物リスト](https://www.amazon.co.jp/hz/wishlist/ls/3AZ4RI13SW2PV) もあります。** どのようなものでも贈っていただけると泣いて喜びます…🙇

> [!NOTE]  
> アマギフを送っていただく際に KonomiTV に実装してほしい機能を添えていただければ、もしかするとその機能を優先して実装することがある…かもしれません。  
> ただし、私個人のプライベートやモチベーション、技術的な難易度などの兼ね合いもあるため、『必ず実装する』とお約束することはできません。あくまで私からのちょっとしたお礼レベルなので、基本期待しないでいただけると…。

このほか、**[こちら](https://www.amazon.co.jp/?tag=tsukumijima-22) のリンクをクリックしてから Amazon で何かお買い物していただくことでも支援できます (Amazon アソシエイト)。**  
買う商品はどのようなものでも OK ですが、より [紹介料率 (商品価格のうち、何%がアソシエイト参加者に入るかの割合)](https://affiliate.amazon.co.jp/help/node/topic/GRXPHT8U84RAYDXZ) が高く、価格が高い商品の方が、私に入る報酬は高くなります。Kindle の電子書籍や食べ物・飲み物は紹介料率が高めに設定されているみたいです。  

> [!NOTE]  
> もしかすると GitHub から Amazon に飛ぶと[リファラ](https://wa3.i-3-i.info/word129.html)チェックで弾かれてしまうかもしれないので、リンクをコピペして新しく開いたタブに貼り付ける方が良いかもしれません。

## Special Thanks

- [xtne6f](https://github.com/xtne6f) さん： KonomiTV と EDCB を連携させるための実装や、[tsreadex](https://github.com/xtne6f/tsreadex) の実装の依頼・開発などで多大なご協力をいただきました。
- [rigaya](https://github.com/rigaya) さん： [QSVEncC](https://github.com/rigaya/QSVEnc)・[NVEncC](https://github.com/rigaya/NVEnc)・[VCEEncC](https://github.com/rigaya/VCEEnc) での動作オプションや不具合の対応、低遅延化改良、エンコードパラメーターのアドバイスなどを支援していただきました。また、[rkmppenc](https://github.com/rigaya/rkmppenc) の開発では多岐に渡り多大なご協力をいただきました。
- [xqq](https://github.com/xqq) さん： [mpegts.js](https://github.com/xqq/mpegts.js) で MPEG-TS をダイレクトストリーミングできるようになり、わずか最短 0.9 秒の低遅延でテレビを視聴することができるようになりました。mpegts.js のヘルプやプレイヤーへの導入のサポートなども支援していただきました。
- [monyone](https://github.com/monyone) さん：[aribb24.js](https://github.com/monyone/aribb24.js) のおかげで、ARIB 字幕や文字スーパーを完璧に表示できるようになりました。また、字幕関連のほか、[MPEG-TS 録画ファイルのインメモリでのリアルタイム HLS ストリーミングの実装](https://github.com/monyone/biim) とそのトラブルシューティング、導入のサポートなどで多大なご協力をいただきました。
- [otya](https://github.com/otya128) さん：ストリーミング関連で発生した各種課題の解決や、データ放送ブラウザ ([web-bml](https://github.com/otya128/web-bml)) の組み込みなどで広くご協力をいただきました。

KonomiTV の開発にあたり、ほかにも沢山の方からサポートやフィードバック、ご支援をいただきました。  
この場をお借りして厚く感謝を申し上げます。 本当にありがとうございました！

## License

[MIT License](License.txt)
