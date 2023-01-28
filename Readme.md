
# <img width="350" src="https://user-images.githubusercontent.com/39271166/134050201-8110f076-a939-4b62-8c86-7beaa3d4728c.png" alt="KonomiTV">

<img width="100%" src="https://user-images.githubusercontent.com/39271166/153729504-2c047f35-c788-49d2-a088-cc1c3bab3fd0.png"><br>

いろいろな場所とデバイスでテレビと録画を快適に見れる、モダンな Web ベースのソフトウェアです。

ユーザーのさまざまな好みがつまった、温かみのある居心地の良い場を作ってみたいという想いから、KonomiTV と名付けました。  
手元の PC・タブレット・スマホをテレビにすることを考えたときに、まったく新しく、使いやすくて快適な視聴体験を創出したいという想いから開発しています。

計画はかなり壮大ですが、現時点ではテレビをリアルタイムで視聴できる「テレビをみる」と、設定画面のみが実装されています。  
将来的には、録画した番組を Netflix をはじめとした配信サイトのような UX で快適に視聴できる「ビデオをみる」など、多くの機能を追加予定です。

## 設計思想

いわゆる TS 抜きでテレビを見ている人の多くが、TVTest でテレビを見て、録画をファイルベースで管理して、録画ファイルをメディアプレイヤーで開いて…といった、ファイルやアーキテクチャベースの視聴の仕方をされているかと思います。  
ですが、その中で必ず出てくる BonDriver を選択したり、ファイルをフォルダの中から探しだして選択したり、1話を見終わったから2話を開き直したりといった手間は、本来その番組を視聴し、心いくまで楽しむにあたって、不要な工程ではないかと考えます。雑念、といったほうが分かりやすいでしょうか。  

一方世間のトレンドに目を向けてみると、Netflix や Amazon Prime Video のような配信サイトが幅を利かせています。  
これらのサイトが流行っているのは、（良い意味で）何も考えなくても、いつでもどこでも気軽に快適に映像コンテンツを見まくれる、そんなユーザー体験が実現されているからです。  
配信サイトとテレビ・録画は「リアルタイムで配信されている」「事前に選んだコンテンツしか視聴できない」など大きな差異もありますが、映像コンテンツを視聴するインターフェイスという点では共通しています。  
そこで、テレビと録画の視聴といういまだレガシーな視聴体験が残っている分野に、優れた UX を実現している配信サイトでの概念を取り入れ、まるで自分だけの Netflix のような視聴体験を演出できれば面白いのではないか？と考えました。その仮説と理想を実現すべく、鋭意開発を続けています。

こうした考えから、設計思想として「映像コンテンツを視聴し楽しむ」ために不要な概念や操作を可能なかぎり表層から排除・隠蔽し、ユーザーが本当の目的以外の雑念に気を取られないようなシステムを目指しています。

たとえば TVRemotePlus であった「ストリーム」の概念を KonomiTV では排しています。チャンネルをクリックするだけですぐに視聴できるほか、裏側ではチューナーの共有、同じチャンネルを複数のデバイスで見ているなら自動的に共聴するといった高度な仕組みも備え、ユーザーがストレスなく視聴できるように設計されています。  
画質の切り替えの UI も、KonomiTV では多くの動画サイトと同じようにプレイヤー内に統合されています。裏側では毎回エンコーダーを再起動しているのですが、表層からはあたかも事前に複数の画質が用意されているかのように見えるはずです。  
一般的な PC で動かす以上使えるリソースには限界がありますし、全てにおいて Netflix のような機能を実装できるわけではありません。それでも使えるリソースの範囲で最大限使いやすいソフトウェアにしていければと、細部に様々な工夫を取り入れています。

当然ながら表に泥臭い処理を見せないようにしている分、裏側の実装がそれなりに大変です。細かいところまで調整しているとかなりの手間がかかります。  
それでも私が頑張れば私を含めたユーザーの視聴体験が向上するわけで、必要な犠牲かなと思っています。

## 動作環境

<img width="100%" src="https://user-images.githubusercontent.com/39271166/153731898-c9743df8-794b-4498-ac25-017662f38759.png"><br>

### サーバー

- **Windows 10/11 PC または Linux (Ubuntu) PC**
  - **Windows 10 Pro と Ubuntu 20.04 LTS の PC でのみ動作確認を行っています。**
    - Windows 11 でも動作するとは思いますが、手元に環境がないため、検証はできていません。
    - 32bit 版の Windows 10 には対応していません。
  - **Linux PC は Ubuntu (20.04 LTS 以降) のみサポートしています。**
    - Linux PC では、Docker で動かすこともできます（後述）。
    - Debian・RedHat 系 OS・Arch Linux でも動作するかもしれませんが、開発/検証リソースが大幅に不足しているため、サポートは行いません。
      - できるだけ Ubuntu の利用を推奨しますが、もし Ubuntu 以外の OS にインストールする際は、Docker でのインストールを推奨します。
      - ビルド済みのサードパーティーライブラリは glibc 2.31 以上に依存しています。Docker を使わずにインストールする場合、[glibc 2.30 以下を採用する OS](https://repology.org/project/glibc/versions) では動作しません。
    - ARM 向けのサードパーティーライブラリの実行ファイルを用意できていないため、今のところラズパイなどの ARM の Linux PC では動作しません。
      - KonomiTV はその性質上ハードウェアエンコーダーに強く依存していますが、ARM SoC のハードウェアエンコーダーは SoC メーカーごとにまちまちで、サポート状況もかなり厳しいと言わざるを得ません…。
      - 将来的には、メジャーで比較的サポート状況の良い、ラズパイ4 (Broadcom BCM2711) と Rockchip RK3568 / RK3588 SoC のハードウェアエンコーダーにのみ対応する予定です。
- **EDCB または Mirakurun**
  - KonomiTV のバックエンドには、EDCB または Mirakurun のいずれかを選択できます。
  - **EDCB は、220122 以降のバージョンの [xtne6f 版 EDCB](https://github.com/xtne6f/EDCB) / [tkntrec 版 EDCB](https://github.com/tkntrec/EDCB) にのみ対応しています。**
    - **220122 以前のバージョンの EDCB では正常に動作しません。<ins>「人柱版10.66」などの古いバージョンをお使いの場合は、EDCB のアップグレードが必要です。</ins>**
    - **最新の EDCB のビルド済みアーカイブは [tsukumijima/DTV-Builds](https://github.com/tsukumijima/DTV-Builds) にて配布しています。** こだわりがなければ、DTV-Builds で配布しているアーカイブの利用を強くおすすめします (動作確認も DTV-Builds で配布しているアーカイブで行っています)。
    - **KonomiTV と連携するには、さらに EDCB に事前の設定が必要になります（後述）。**
  - **Mirakurun は 3.9.0 以降を推奨します。**
    - 3.8.0 以下のバージョンでも動作しますが、諸問題で推奨しません。
    - リバースプロキシなどで Mirakurun に Basic 認証が掛かっていると正常に動作しません。

### クライアント

- **PC: Microsoft Edge または Google Chrome**
  - Firefox でも動作するはずですが、コメント描画が重く、コメント表示をオンにするとライブストリーミングが時折止まることが確認されています。動作確認もあまりできていないため、Chrome か Edge を使うことをおすすめします。
  - Mac の Safari はサポートしていません。Mac でも Chrome か Edge を使ってください。
- **Android: Google Chrome**
  - 現時点では横画面表示のみの対応です。縦画面表示ではレイアウトが崩れます。
  - Android の Firefox はサポートしていません。
- **iPadOS: Safari（暫定対応）**
  - 現時点では横画面表示のみの対応です。縦画面表示ではレイアウトが崩れます。
  - あまり動作確認を行っていないため、修正できていない不具合があるかもしれません。
  - 技術的な問題により、iOS Safari への対応は当面の間行いません（後述）。

## 備考・注意事項

- **現在 β 版で、まだ実験的なプロダクトです。当初よりかなり安定してきましたが、まだ完璧に保証ができる状態ではありません。**
  - 完成予想はおろか、TVRemotePlus で実装していた機能に関してもまだ完全にカバーできていないため、現時点で TVRemotePlus を代替できるレベルには達していません。
- **TVRemotePlus の後継という位置づけのソフトですが、それはあくまで精神的なものであり、実際の技術スタックや UI/UX はゼロから設計されています。**
  - 確かに TVRemotePlus の開発で得られた知見を数多く活用していますし開発者も同じではありますが、ユーザービリティや操作感は大きく異なるはずです。
  - TVRemotePlus の技術スタックでは解決不可能なボトルネックを根本的に解消した上で、「同じものを作り直す」のではなく、ゼロから新しいテレビ視聴・録画視聴のユーザー体験を作り上げ、追求したいという想いから開発しています。
  - どちらかというと録画視聴機能の方がメインの予定でいますが、前述のとおり、現時点ではテレビのライブ視聴機能のみの実装です。構想は壮大ですが、全て実装し終えるには数年単位で時間がかかるでしょう。
- **今のところ、スマートフォン・タブレットでは横画面表示のみ対応しています。将来的には縦画面でも崩れずに表示できるようにする予定です。**
  - **スマートフォンでは、最低限 iPhone SE2 (4.7インチ) 以上の画面サイズが必要です。**
    - 快適に利用するには、画面サイズが 6.1 インチ以上の端末をおすすめします。
    - iPhone 5s (4インチ) サイズには対応しておらず、画面が大幅に崩れます。
  - **Fire タブレット (Fire HD 10 (2021) / Fire HD 8 (2022)) でも動作します。**
    - Fire HD 10 (2021) では Google Play を導入した上で、Google Play 経由で Chrome をインストールしてください。
    - Fire HD 8 (2022) では現状 Google Play が導入できないため、適宜 Chrome の APK を入手してインストールしてください。Chrome は、(Google アカウントとの同期機能以外は) GMS がインストールされていなくても動作します。
  - **iPhone の Safari はライブストリーミングに必要な Media Source Extensions API がサポートされていないため、現時点では動作しません。**
    - 今後 iPhone の Safari に対応した再生モードを実装する予定ですが、かなり実装が大変なこと、私が iPhone を常用していないこともあり、実装時期は未定です。
    - Safari 側のバグが原因で、iPad でホーム画面に追加したアイコンから単独アプリのように起動した場合も (PWA)、iPhone の Safari 同様に動作しません。
- **今後、開発の過程で設定や構成が互換性なく大幅に変更される可能性があります。**
- **ユーザービリティなどのフィードバック・不具合報告・Pull Requests (PR) などは歓迎します。**
  - 技術スタックはサーバー側が Python 3.10 + [FastAPI](https://github.com/tiangolo/fastapi) + [Tortoise ORM](https://github.com/tortoise/tortoise-orm) + [Uvicorn](https://github.com/encode/uvicorn) 、クライアント側が Vue.js 2.x + [Vuetify](https://github.com/vuetifyjs/vuetify) 2.x の SPA です。
    - Vuetify は補助的に利用しているだけで、大部分は独自で書いた SCSS スタイルを適用しています。
  - コメントを多めに書いたりそれなりにきれいにコーディングしているつもりなので、少なくとも TVRemotePlus なんかよりかは読みやすいコードになっている…はず。
  - 他人が見るために書いたものではないのであれですが、一応自分用の [開発資料](https://mango-garlic-eff.notion.site/KonomiTV-90f4b25555c14b9ba0cf5498e6feb1c3) と [DB設計](https://mango-garlic-eff.notion.site/KonomiTV-544e02334c89420fa24804ec70f46b6d) 的なメモを公開しておきます。もし PR される場合などの参考になれば。

## 事前準備

<img width="100%" src="https://user-images.githubusercontent.com/39271166/153729029-bbcd6c16-9661-4f61-b7a9-64df8c1e4586.png"><br>

### チューナーのドライバーを px4_drv に変更する

必須ではありませんが、**Windows で PLEX 製チューナーを利用している場合は、事前にドライバーを [px4_drv for WinUSB](https://github.com/tsukumijima/px4_drv) に変更しておくことを強く推奨します。**  
px4_drv では、公式ドライバーとの比較で、チューナーの起動時間が大幅に短縮されています。  
その分 KonomiTV での視聴までにかかる待機時間も速くなるため（5秒以上速くなる）、より快適に使えます。  

**px4_drv を導入すると、ほかにもドロップが大幅に減って安定するなど、たくさんのメリットがあります！**  
内蔵カードリーダーが使えないこと、BonDriver の差し替えが必要になることだけ注意してください。

> px4_drv for WinUSB のビルド済みアーカイブは [tsukumijima/DTV-Builds](https://github.com/tsukumijima/DTV-Builds) にて配布しています。

### EDCB の事前設定

<img width="613" src="https://user-images.githubusercontent.com/39271166/201383288-7bcda592-bffd-4a15-b975-ced2b66e4289.png"><br>

**EDCB バックエンドでは、いくつか EDCB に事前の設定が必要です。**  
**<ins>この事前設定を行わないと KonomiTV は正常に動作しません。</ins> 必ず下記のとおりに設定してください。**

**また、必ず 220122 以降のバージョンの [xtne6f 版 EDCB](https://github.com/xtne6f/EDCB) / [tkntrec 版 EDCB](https://github.com/tkntrec/EDCB) を利用していることを確認してください。**  
現在利用している EDCB のバージョンは、EpgTimer の設定ウインドウの下に表示されています。**KonomiTV でサポートしていない古い EDCB では、このバージョン表示自体がありません。**

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

>SrvPipe とは、EpgDataCap_Bon で受信した放送波を EpgTimerSrv (EpgTimer Service) に渡すための、EDCB 固有の特殊な名前付きパイプのことです。  
> KonomiTV は SrvPipe を経由して EDCB から放送波を受信しているため、この設定を忘れると、テレビのライブストリーミングができません。

このほか、**リモート PC の KonomiTV から EDCB にアクセスする場合は、EpgTimerSrv.exe にファイアウォールが掛かっていると接続に失敗します。**  
適宜ファイアウォールの設定を変更し、EDCB に接続できるようにしておいてください。

### QSVEncC・NVEncC・VCEEncC に対応した GPU ドライバーのインストール

KonomiTV は、[QSVEncC](https://github.com/rigaya/QSVEnc) (Intel QSV)・[NVEncC](https://github.com/rigaya/NVEnc) (NVIDIA NVENC)・[VCEEncC](https://github.com/rigaya/VCEEnc)・(AMD VCE) の3つのハードウェアエンコーダーに標準で対応しています。

> FFmpeg (ソフトウェアエンコーダー) は遅い上に CPU 負荷がかなり高くなるため、ハードウェアエンコーダーの利用を強くおすすめします。

#### Windows

- QSVEncC：[Intel Graphics Driver](https://downloadcenter.intel.com/ja/product/80939/Graphics-Drivers)
- NVEncC：[NVIDIA Graphics Driver](https://www.nvidia.co.jp/Download/index.aspx)
- VCEEncC：[AMD Graphics Driver](https://www.amd.com/ja/support)

それぞれのハードウェアエンコーダーを使用するには、対応した GPU ドライバーのインストールが必要です。  
基本的にすでにインストールされていると思います。

> 古いドライバーを使用している場合は、この機会に最新のドライバーにアップデートしておくことをおすすめします。ドライバーが古すぎると、ハードウェアエンコードに失敗する場合があります。

#### Linux

QSVEncC では、別途 Intel Media Driver のインストールが必要です。

> Linux 版の Intel QSV は、Broadwell (第5世代) 以上の Intel CPU でのみ利用できます。そのため、Haswell (第4世代) 以下の CPU では、Intel Media Driver のインストール有無にかかわらず、QSVEncC を利用できません。  
> なお、Windows 版の Intel QSV は、Haswell (第4世代) 以下の CPU でも利用できます。

```bash
curl -fsSL https://repositories.intel.com/graphics/intel-graphics.key | sudo gpg --dearmor --yes -o /usr/share/keyrings/intel-graphics-keyring.gpg
echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics-keyring.gpg] https://repositories.intel.com/graphics/ubuntu focal main' | sudo tee /etc/apt/sources.list.d/intel-graphics.list > /dev/null
sudo apt update && sudo apt install -y intel-media-va-driver-non-free intel-opencl-icd
```

以上のコマンドを実行して、Intel Media Driver をインストールしてください (Ubuntu 20.04 LTS 以降向け) 。  

> Docker を使ってインストールする場合は、Intel Media Driver をインストールしなくても動作します（未検証）。  
> [KonomiTV の Docker イメージ](https://github.com/tsukumijima/KonomiTV/blob/master/Dockerfile) には Intel Media Driver が標準でインストールされているほか、Intel Graphics 本体のドライバは Linux カーネルに取り込まれているためです。

> Alder Lake (第12世代) 以降の Intel CPU では、追加で `sudo apt install -y libmfx-gen1.2` を実行してください。  
> なお、`libmfx-gen1.2` パッケージは Ubuntu 22.04 LTS にしか存在しないため、Ubuntu 20.04 LTS では、Alder Lake 以降の CPU の Intel QSV を利用できません。

-----

NVEncC では、[NVIDIA Graphics Driver](https://www.nvidia.co.jp/Download/index.aspx) のインストールが必要です。  
基本的にはすでにインストールされていると思います。個人的には `ubuntu-drivers` コマンドを使って apt でインストールするのがおすすめです。

**Docker を使って KonomiTV をインストールする場合は (後述) 、さらに NVIDIA Container Toolkit のインストールが必要です。**

```bash
# Ubuntu では nvidia-docker2 パッケージをインストールするだけ
sudo apt install -y nvidia-docker2
```

-----

VCEEncC では、[AMDGPU-PRO Driver](https://www.amd.com/ja/support/linux-drivers) のインストールが必要です。  
古いドライバーがインストールされていると、VCEEncC を利用できないことがあります。最新のドライバーをインストールしてください。

```bash
# Ubuntu 20.04 LTS (2022/11時点で最新の amdgpu-install パッケージの URL)
curl -LO https://repo.radeon.com/amdgpu-install/22.20/ubuntu/focal/amdgpu-install_22.20.50200-1_all.deb
# Ubuntu 22.04 LTS (2022/11時点で最新の amdgpu-install パッケージの URL)
curl -LO https://repo.radeon.com/amdgpu-install/22.20/ubuntu/jammy/amdgpu-install_22.20.50200-1_all.deb

# AMDGPU-PRO Driver のインストール
sudo apt install -y ./amdgpu-install_22.20.50200-1_all.deb
sudo apt update && sudo amdgpu-install -y --accept-eula --usecase=graphics,amf,opencl --opencl=rocr,legacy --no-32

# 再起動
sudo reboot
```

以上のコマンドを実行して、AMDGPU-PRO Driver をインストールしてください (Ubuntu 20.04 LTS 以降向け) 。

### Tailscale の導入

<img width="100%" src="https://user-images.githubusercontent.com/39271166/201439632-d78b8401-ef70-4955-98e8-b317ecf3e278.png"><br>

**KonomiTV で外出先からリモート視聴するには、Tailscale というメッシュ VPN ソフトを、サーバー PC とクライアントデバイス双方にインストールしておく必要があります。**  

> KonomiTV を家の中だけで使う分には必須ではありませんが、セットアップがとっても簡単で時間もそこまでかからないので、この機会にインストールしておくことをおすすめします。

> 厳密にはほかの方法 (OpenVPN・SoftEther・リバースプロキシなど) でもリモート視聴は可能ですが、技術的に難易度がかなり高くネットワークエンジニア以外には難しいこと、Tailscale を使った方法が一番手軽でセキュアなことから、**<ins>KonomiTV では Tailscale を使ったリモート視聴方法のみ公式にサポートしています。</ins>**  
> **特にリバースプロキシ経由でのアクセスでは<ins>一部機能が正常に動作しなくなる</ins>ほか、セキュリティ上の問題もあるため、非推奨です。**

Tailscale は、デバイスが接続されているネットワークや物理的距離に関係なく、**同じアカウントにログインしている Tailscale クライアント (デバイス) 同士で直接通信できる、次世代型のメッシュ VPN です。**

VPN サーバーを介さず Tailscale クライアント同士で直接通信するため、通常の VPN よりも高速です。さらに通信は暗号化されるため、セキュアに外出先から自宅のデバイスへアクセスできます。

**さらに、デバイスをほかの Tailscale ユーザーとシェアすることもできます。**  
Google ドライブでファイルへの招待リンクを作って共同編集したい人に送るのと同じ要領で、Tailscale クライアントをインストールしたデバイスをほかのユーザーとシェアできます。  
KonomiTV を共有したい家族や親戚に Tailscale アカウントを作成してもらえば、Tailscale ログイン用の Google / Microsoft / GitHub アカウントを家族間で共有することなく、セキュアに KonomiTV をシェアできます。

**Tailscale の詳細や導入方法は、以前私が執筆した **[こちら](https://blog.tsukumijima.net/article/tailscale-vpn/)** の記事をご覧ください。**  
この記事のとおりにセットアップすれば、あとは各デバイスで Tailscale での VPN 接続をオンにしておくだけです。

**KonomiTV での利用以外にも、EDCB Material WebUI や EPGStation などの、プライベートネットワーク上の Web サーバーに家の外からアクセスするときにとても便利なサービスです。**  
20台までは無料ですし (逸般の誤家庭でなければ十分すぎる)、この機会に導入しておくことをおすすめします。

## サーバーのインストール

<img width="100%" src="https://user-images.githubusercontent.com/39271166/201460497-7f0b951a-5495-40cd-95af-32cc2146d991.png"><br>

### KonomiTV (β) 0.5.2 以前からのアップグレード

KonomiTV 0.5.2 以前のバージョンをすでにインストールしている場合、**直接 0.5.2 から 0.6.0 以降にアップグレードすることはできません。** 各種構成に破壊的な変更を多数行ったため、KonomiTV 0.5.2 と 0.6.0 以降には互換性がないためです。

お手数ですが、**一度 0.5.2 をインストールしているフォルダを丸ごと削除した上で、新しく 0.6.0 以降をインストールし直してください。**  

また、KonomiTV 0.6.0-dev 以降のバージョンでは、ポータブル版の Python をサードパーティーライブラリに組み込んでいます。そのため、Python 3.9 / 3.10 を別途インストールする必要はなくなりました。  
不要であれば適宜アンインストールしてください（残しておいても動作に支障はありません）。

### KonomiTV (β) 0.6.0-dev (開発版) からのアップグレード

**0.6.0 の正式リリース前に公開していた [ベータ版インストーラー](https://github.com/tsukumijima/Storehouse/releases/tag/KonomiTV-Installer-Prerelease) で KonomiTV 0.6.0-dev (master ブランチの開発版) をインストールしている場合は、0.6.0 以降の正式版のインストーラーを使って、0.6.0 以降にアップグレードできます。**

ただし、ベータ版インストーラーの初期リビジョンでインストールした場合は構成に不備があるほか、100% アップグレードが成功する保証もありません。  
心配な方は、**一度インストーラーでアンインストールしてから、新しく 0.6.0 以降をインストールし直すことをおすすめします。**

> KonomiTV 0.6.0-dev 以降のバージョンでは、Windows サービスや PM2 / Docker サービスのインストール処理が追加されています。そのため、単にフォルダを削除するだけではアンインストールできません。

### Windows

[動作環境] に記載のとおり、Windows 10 以降の 64bit OS にのみ対応しています。  
Windows 8 以前と、32bit OS には対応していません。

**[Releases](https://github.com/tsukumijima/KonomiTV/releases) ページから、最新の KonomiTV のインストーラーをダウンロードします。**  
Assets の下にある `KonomiTV-Installer.exe` をダウンロードしてください。

> **`KonomiTV-Installer.exe` がウイルス対策ソフトにウイルスと扱われてしまうことがありますが、誤検知です。一般に Python 製ソフトを exe 化すると問答無用でウイルスだと扱われてしまうことが多く、頭を抱えています…。**  
> 適宜お使いのウイルス対策ソフトで、`KonomiTV-Installer.exe` を許可してください。KonomiTV のインストーラーのソースコードは [こちら](https://github.com/tsukumijima/KonomiTV/tree/master/installer) で公開しています。

<img width="100%" src="https://user-images.githubusercontent.com/39271166/201462168-f898fe8f-ac1f-4942-908f-de6263389a97.png"><br>

**ダウンロードが終わったら、`KonomiTV-Installer.exe` をダブルクリックで実行します。**  
インストールには管理者権限が必要です。

**あとは、インストーラーの通りに必要事項を入力していけば、インストールがはじまります！**  
スペックにもよりますが、インストールには少し時間がかかります。気長に待ちましょう。

> インストールが完了すると、ログオン中のユーザーのパスワードの入力を求められます。  
> これはKonomiTV の Windows サービスを一般ユーザーの権限で起動するために利用するもので、入力されたパスワードがそれ以外の用途に利用されることはありません。

> ログオン中のユーザーにパスワードを設定していない場合は、簡単なものでいいので何かパスワードを設定してから、その設定したパスワードを入力してください (なお、パスワードの設定後にインストーラーを起動し直す必要はありません。)。

### Linux

[動作環境] に記載のとおり、Ubuntu 20.04 LTS 以降の OS にのみ対応しています。  
それ以外のディストリビューションでも動くかもしれませんが、動作は保証しませんし、今後のサポート予定もありません（Docker ならどの OS でもそれなりに動くような気はします）。

> できるだけ Ubuntu の利用を推奨しますが、もし Ubuntu 以外の OS にインストールする際は、Docker でのインストールをおすすめします。

**Linux 向けの KonomiTV には、通常のインストール方法と、Docker を使ったインストール方法の 2 通りがあります。**  

**通常のインストール方法では、事前に [PM2](https://pm2.keymetrics.io/docs/usage/quick-start/) と [Node.js](https://github.com/nodesource/distributions) (PM2 の動作に必要) のインストールが必要です。**  
[Mirakurun](https://github.com/Chinachu/Mirakurun) や [EPGStation](https://github.com/l3tnun/EPGStation) を Docker を使わずにインストールしているなら、すでにインストールされているはずです。

**Docker を使ったインストール方法では、事前に [Docker](https://docs.docker.com/engine/install/) と [Docker Compose](https://docs.docker.com/compose/install/) のインストールが必要です。**  
Docker Compose は V1 と V2 の両方に対応していますが、できれば V2 (ハイフンなしの `docker compose` コマンド) が使えるようにしておくことをおすすめします。

> **Docker Compose V1 は最終版の 1.29.2 でのみ動作を確認しています。古いバージョンでは正常に動作しない可能性が高いです。**  
> もし Docker Compose V1 が 1.29.2 よりも古い場合は、この機会に V2 への更新をおすすめします。以前よりもグラフィカルに進捗が表示されたりなどのメリットもあります。

> [QSVEncC・NVEncC・VCEEncC に対応した GPU ドライバーのインストール] に記載のとおり、**NVIDIA GPU が搭載されている PC に Docker を使ってインストールする場合は、必ず事前に NVIDIA Container Toolkit をインストールしておいてください。**  
> NVIDIA Container Toolkit がインストールされていない場合、KonomiTV のインストールにも失敗する可能性が高いです。

> Docker を使ってインストールする場合、動作環境によっては `getaddrinfo EAI_AGAIN registry.yarnpkg.com` といったエラーで Docker イメージのビルドに失敗することがあります。  
> Docker の DNS 設定がおかしかったり、Docker が書き換える iptables の定義が壊れてしまっていることが原因のようで、解決方法は千差万別です。  
> KonomiTV は通常のインストール方法でも極力環境を汚さないように開発されています。Docker を使わずに通常通りインストールしたほうが早いかもしれません。

<img width="100%" src="https://user-images.githubusercontent.com/39271166/201463450-96bb686e-c5bb-493d-b907-57b5f51ac986.png"><br>

```bash
curl -LO https://github.com/tsukumijima/KonomiTV/releases/download/v0.6.2/KonomiTV-Installer.elf
chmod a+x KonomiTV-Installer.elf
./KonomiTV-Installer.elf
```

以上のコマンドを実行して `KonomiTV-Installer.elf` を実行し、インストーラーの通りに進めてください。  
インストールには root 権限が必要です。`KonomiTV-Installer.elf` の実行時に自動的にパスワードを求められます。

### KonomiTV にアクセスする

<img width="100%" src="https://user-images.githubusercontent.com/39271166/201465324-fdae7d03-ba1f-4aa4-9d48-7e04f2290bc7.png"><br>

**「インストールが完了しました！ すぐに使いはじめられます！」と表示されたら、KonomiTV サーバーのインストールは完了です！おつかれさまでした！！🎉🎊**  
インストーラーに記載されている URL から、KonomiTV の Web UI にアクセスしてみましょう！  

**通常、`(イーサネット)` または `(Wi-Fi)` の URL が家の中からアクセスするときの URL 、`(Tailscale)` の URL が外出先（家の外）から Tailscale 経由でアクセスするときの URL になります。**  

> `https://my.local.konomi.tv:7000/` の URL は、KonomiTV サーバーをインストールした PC 自身を指す URL ([ループバックアドレス](https://wa3.i-3-i.info/word1101.html)) です。基本的に使うことはないと思います。

> `(Tailscale)` の URL は、事前に Tailscale を導入していない場合は表示されません（外出先からのアクセス自体は、Tailscale をいつ導入したかに関わらず、Tailscale が起動していれば問題なく行えます）。

KonomiTV サーバーは Windows サービス (Windows) / PM2 サービス (Linux) /  Docker サービス (Linux-Docker) としてインストールされているので、サーバー PC を再起動したあとも自動的に起動します。  
もし再起動後に KonomiTV にアクセスできない場合は、`server/logs/KonomiTV-Server.log` に出力されているエラーメッセージを確認してください。

-----

<img width="100%" src="https://user-images.githubusercontent.com/39271166/201473243-e246802f-0100-4e6a-bb0e-4247f784bb3b.png"><br>

**PC 版 Chrome や Edge では、URL バー右のアイコン → [アプリをインストール] から、KonomiTV をブラウザバーのないデスクトップアプリとしてインストールできます！**  
ブラウザバーが表示されない分、より映像に没頭できますし、画面も広く使えます。私も KonomiTV をデスクトップアプリとして使っています。  
タスクバーや Dock に登録しておけば、起動するのも簡単です。ぜひお試しください。

<img width="100%" src="https://user-images.githubusercontent.com/39271166/201473798-97aa818a-0474-46bc-b56a-0c49f281e92a.jpg"><br>

**Android 版 Chrome では、下に表示される [ホーム画面に追加] またはメニューの [アプリをインストール] から、KonomiTV をブラウザバーのないスマホアプリとしてインストールできます！**  
特にスマホは画面が小さいので、アプリとしてインストールした方が画面が広くなって使いやすいです。私も KonomiTV をスマホアプリとして使っています。こちらもぜひお試しください。

> [PWA (Progressive Web Apps)](https://developer.mozilla.org/ja/docs/Web/Progressive_web_apps) という、Web アプリを通常のネイティブアプリのように使えるようにする技術を利用しています。将来的には、PWA だけでなく、より快適に利用できるようにした iOS 向けアプリと Android 向けアプリ (いわゆるガワアプリ) をリリースする予定です。

## 付録

<img width="100%" src="https://user-images.githubusercontent.com/39271166/153728655-afe25279-2d42-4150-bfdf-71de62dde44d.jpg"><br>

### `https://aa-bb-cc-dd.local.konomi.tv:7000/` の URL について

**この `https://aa-bb-cc-dd.local.konomi.tv:7000/` のフォーマットの URL は、KonomiTV の WebUI に HTTPS でアクセスするための特殊な URL です。**  

aa-bb-cc-dd の部分には、ローカル IP アドレスのうち、. (ドット) を - (ハイフン) に置き換えた値が入ります。  
つまり、サーバー PC のローカル IP アドレスが `192.168.1.11` だったとしたら、`https://192-168-1-11.local.konomi.tv:7000/` という URL になります。

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

> `https://(IPアドレス(.を-にしたもの)).local.konomi.tv:7000/` はすべてのプライベート IP アドレスに対応していますが、セキュリティ上の兼ね合いでグローバル IP アドレスには対応していません。  
> なお、Tailscale の [100.x.y.z アドレス](https://tailscale.com/kb/1015/100.x-addresses/) には対応しています。

> どうしてもほかの URL でアクセスしたい方向けに、一応環境設定 (config.yaml) にカスタム HTTPS 証明書を指定する機能を用意しています。サポートは一切しませんので、すべて理解している方のみ行ってください。

### 設定ファイルの編集

**KonomiTV の環境設定は、KonomiTV をインストールしたフォルダにある config.yaml に保存されています。**  

> config.example.yaml は、config.yaml のデフォルトの設定を記載した、config.yaml のひな形となるファイルです。アップデート時に上書きされるため、config.example.yaml は編集しないでください。  

> 設定ファイルは YAML 形式ですが、JSON のようなスタイルで書いています。括弧がないとわかりにくいと思うので… (JSON は YAML のサブセットなので、実は JSON は YAML として解釈可能です)

**config.yaml は、インストーラーでインストールした際に自動的に生成されます。**  
環境設定を変更するときは、config.yaml 内の設定を手動で編集する必要があります。将来的には GUI から環境設定を変更できるようにする予定です。

以下は主要な設定項目の説明です。  
ほかにも設定項目はありますが、基本的に変更の必要はありません。

#### バックエンドの設定

KonomiTV のバックエンドには、EDCB または Mirakurun のいずれかを選択できます。  
`general.backend` に `EDCB` または `Mirakurun` を指定してください。

-----

EDCB をバックエンドとして利用する場合は、EDCB (EpgTimerNW) の TCP API の URL (`general.edcb_url`) をお使いの録画環境に合わせて編集してください。

通常、TCP API の URL は `tcp://(EDCBのあるPCのIPアドレス):4510/` になります。接続できない際は、ファイアウォールの設定や EpgTimer Service が起動しているかを確認してみてください。  
前述のとおり、あらかじめ EDCB の事前設定を済ませておく必要があります。

> TCP API の URL として `tcp://edcb-namedpipe/` と指定すると、TCP API の代わりに名前付きパイプで通信を行います（KonomiTV と EDCB が同じ PC で起動している場合のみ）。

-----

Mirakurun をバックエンドとして利用する場合は、Mirakurun の HTTP API の URL (`general.mirakurun_url`) をお使いの録画環境に合わせて編集してください。

通常、HTTP API の URL は `http://(MirakurunのあるPCのIPアドレス):40772/` になります。接続できない際は、Mirakurun が起動しているかを確認してみてください。

#### エンコーダーの設定

エンコーダーには、ソフトウェアエンコーダーの FFmpeg のほか、ハードウェアエンコーダーの QSVEncC・NVEncC・VCEEncC を選択できます。  
`general.encoder` に `FFmpeg` / `QSVEncC` / `NVEncC` / `VCEEncC` のいずれかを指定してください。

**ハードウェアエンコーダーを選択すると、エンコードに GPU アクセラレーションを利用するため、CPU 使用率を大幅に下げる事ができます。**  
エンコード速度も高速になるため、お使いの PC で利用可能であれば、できるだけハードウェアエンコーダーを選択することを推奨します。

> お使いの PC で選択したハードウェアエンコーダーが利用できない場合、ライブストリーミング時にその旨を伝えるエラーメッセージが表示されます。まずはお使いの PC でハードウェアエンコーダーが使えるかどうか、一度試してみてください（設定ファイルの変更後はサーバーの再起動が必要です）。

> 前述のとおり、Linux 環境で QSVEncC・NVEncC・VCEEncC を利用する場合は、別途 GPU ドライバーのインストールが必要です。

**QSVEncC は、Intel 製 CPU の内蔵 GPU に搭載されているハードウェアエンコード機能 (Intel QSV) を利用するエンコーダーです。**  
ここ数年に発売された Intel Graphics 搭載の Intel 製 CPU であれば基本的に搭載されているため、一般的な PC の大半で利用できます。内蔵 GPU なのにもかかわらず高速で、画質も良好です。  

> Linux 版の Intel QSV は、Broadwell (第5世代) 以上の Intel CPU でのみ利用できます。そのため、Haswell (第4世代) 以下の CPU では、QSVEncC を利用できません。  
> なお、Windows 版の Intel QSV は、Haswell (第4世代) 以下の CPU でも利用できます。

**NVEncC は、Geforce などの NVIDIA 製 GPU に搭載されているハードウェアエンコード機能 (NVENC) を利用するエンコーダーです。**  
高速で画質も QSV より若干良いのですが、Geforce シリーズでは同時にエンコードが可能なセッション数が 3 に限定されているため、同時に 3 チャンネル以上視聴することはできません。  
同時に 4 チャンネル以上視聴しようとした場合、KonomiTV では「NVENC のエンコードセッションが不足しているため、ライブストリームを開始できません。」というエラーメッセージが表示されます。

**VCEEncC は、Radeon などの AMD 製 GPU に搭載されているハードウェアエンコード機能 (AMD VCE) を利用するエンコーダーです。**  
QSVEncC・NVEncC に比べると安定しない上に、画質や性能もあまり良くありません。もし QSVEncC・NVEncC が使えるならそちらを使うことをおすすめします。

#### リッスンポートの設定

`server.port` に、KonomiTV サーバーのリッスンポートを指定してください。  
デフォルトのリッスンポートは `7000` です。  

> インストーラーでのインストール時にポート 7000 がほかのサーバーソフトと重複している場合は、代わりのポートとして 7100 (7100 も利用できない場合は、さらに +100 される) が自動的にデフォルトのリッスンポートに設定されます。

基本的に変更の必要はありません。変更したい方のみ変更してください。

#### アップロードしたキャプチャ画像の保存先フォルダの設定

`capture.upload_folder` に、アップロードしたキャプチャ画像の保存先フォルダを指定してください。

クライアントの [キャプチャの保存先] 設定で [KonomiTV サーバーにアップロード] または [ブラウザでのダウンロードと、KonomiTV サーバーへのアップロードを両方行う] を選択したときに利用されます。

デフォルトの保存先フォルダは、インストーラーで入力したフォルダが自動的に設定されています。  
保存先フォルダを変更したくなったときは、この設定を変更してください。

-----

<img width="100%" src="https://user-images.githubusercontent.com/39271166/201438534-10a19a9e-56ef-4c9e-88c2-2198de76979d.png"><br>

**環境設定の変更を反映するには、KonomiTV サーバー (KonomiTV Service) の再起動が必要です。**

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

> 放送波から取得できる局ロゴは最高でも 64x36 で、現代的なデバイスで見るにはあまりにも解像度が低すぎます。とはいえ、局ロゴがなければぱっとチャンネルを判別できなくなり、ユーザー体験が悪化してしまいます。  
> さらに、局ロゴは何らかの事情で取得できていないことも考えられます。こういった事情もあり、高画質な局ロゴを同梱しています。

チャンネルに対応する局ロゴが同梱されていない場合は、Mirakurun・EDCB のいずれかから局ロゴの取得を試みます。Mirakurun または EDCB から局ロゴを取得できなかった場合は、デフォルトの局ロゴが利用されます。    

- Mirakurun:
  - Mirakurun の API から局ロゴの取得を試みます。  
  - 基本的には何もしなくても局ロゴが収集されているはずです。
- EDCB:
  - EDCB のロゴデータ保存機能で収集された局ロゴの取得を試みます。
    - ロゴデータ保存機能は [2020年10月に追加された](https://github.com/xtne6f/EDCB/commit/0457241ccdd83ae9847ab15a16157d04927b72ce) もので、KonomiTV が動作する 220122 以降のバージョンの EDCB なら問題なく利用できます。
  - EpgDataCap_Bon の設定 → [EPG取得設定] → [ロゴデータを保存する] にチェックが入っていて、なおかつ `EDCB/Settings/LogoData/` にロゴデータ (PNG) が保存されていることが条件です。

> 同梱されているロゴは `server/static/logos/` に `NID(ネットワークID)-SID(サービスID).png` (解像度: 256×256) のフォーマットで保存されています。  
> チャンネルのネットワーク ID とサービス ID がわかっていれば、自分で局ロゴ画像を作ることも可能です。

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

> 上記のフォーマット以外の URL (例: `https://localhost:7000/`・`https://192.168.1.11:7000/`) では証明書や HTTPS の通信エラーが発生し、Web UI にアクセスできない仕様になっています。  
> 当然ですが、プライベート IP アドレス単体では正式な証明書を取得できないためです。  

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
  - 低遅延ストリーミングがオンのときは、放送波との遅延を最短 1.5 秒にまで抑えて視聴できます。ただし、回線速度が遅かったり不安定な通信環境だと、ストリーミングが安定しないことがあります。
  - 低遅延ストリーミングをオフにすると、遅延が 5 秒以上になりますが、不安定な通信環境でも安定して視聴できます。
  - 低遅延ストリーミングのオン/オフは [設定] → [全般] から変更できます。
- **ストリーミング画質を下げてみてください。**
  - デフォルトのストリーミング画質の 1080p では、平均約 5.1Mbps のデータ量を消費します。データ量はシーン次第で上下しますが、一般的に動きの激しいシーンや実写ではデータ量が多くなります。
  - 画質を下げることで、回線速度が遅くても安定して視聴できるようになります。
  - スペックの低いデバイスでは、画質を下げるとストリーミングが安定することがあります。
  - デフォルトのストリーミング画質は [設定] → [全般] から変更できます。

#### 外出先 (自宅以外) から Tailscale 経由で視聴しているとき
 
- **低遅延ストリーミングをオフにしてみてください。**
  - 低遅延ストリーミングがオンのときは、放送波との遅延を最短 1.5 秒にまで抑えて視聴できます。ただし、**モバイルデータ通信 (4G) やフリー Wi-Fi などのネットワーク遅延の大きい不安定な通信環境では、ストリーミングが安定しないことが多いです。**
    - 海外や他の都道府県など地理的に離れた場所から視聴するときは、ネットワーク遅延が特に大きくなります。
  - **低遅延ストリーミングをオフにすると、遅延が 5 秒以上になりますが、不安定な通信環境でも比較的安定して視聴できます。**
  - 低遅延ストリーミングのオン/オフは [設定] → [全般] から変更できます。
- **ストリーミング画質を下げてみてください。**
  - デフォルトのストリーミング画質の 1080p では、平均約 5.1Mbps のデータ量を消費します。データ量はシーン次第で上下しますが、一般的に動きの激しいシーンや実写ではデータ量が多くなります。
  - 場所にもよりますが、モバイルデータ通信 (4G) やフリー Wi-Fi では通信速度があまり出ないことが多いです。**画質を下げることで、回線速度が遅くても安定して視聴できるようになります。**
    - スマホの小さな画面では画質を 720p や 540p まで下げても見た目ほとんど変わらないので、そのあたりまで画質を下げるのがおすすめです。
  - **画質を下げることで、モバイルデータ通信 (4G/5G) で視聴するときのデータ通信量 (いわゆるギガ、パケ代) も抑えられます。** 360p や 240p まで下げれば、データ通信量をかなり削減できます。
    - PC サイズの画面で 360p はさすがに厳しいですが、スマホサイズの画面なら 360p でもそれなりに視聴に耐える印象です。
  - スペックの低いデバイスでは、画質を下げるとストリーミングが安定することがあります。
  - デフォルトのストリーミング画質は [設定] → [全般] から変更できます。
- **通信節約モードを有効にしてみてください。**
  - 通信節約モードでは、H.265 / HEVC という圧縮率の高いコーデックを使い、画質はほぼそのまま、通信量を**通常の 2/3 程度**に抑えながら視聴できます。
  - **外出先からモバイルデータ通信 (4G/5G) で視聴するときは常に通信節約モードをオンにしておくことをおすすめします。** 画質を保ったまま、データ通信量 (いわゆるギガ、パケ代) をかなり削減できます。
  - ただし、サーバー PC の GPU が H.265 / HEVC でのハードウェアエンコードに対応している必要があります。視聴開始時に「H.265/HEVC でのエンコードに対応していません」というエラーメッセージが表示された場合は、通信節約モードは使えません。
  - 通信節約モードのオン/オフは [設定] → [全般] から変更できます。

## 開発者向け情報

<img width="100%" src="https://user-images.githubusercontent.com/39271166/201457873-dab7a1cb-667f-4bcd-8843-231850d05689.png"><br>

### サーバー

Uvicorn は ASGI サーバーで、FastAPI で書かれた KonomiTV のアプリケーションサーバーを実行します。  
また、KonomiTV の場合は静的ファイルを配信する Web サーバーの役割も兼ねています。

開発時などでサーバーをリロードモード（コードを変更すると自動でサーバーが再起動される）で起動したいときは、`pipenv run dev` を実行してください。  
コードを変更すると強制的にサーバーが再起動されるため、サーバーを終了するタイミングによっては EDCB のチューナーが終了されないままになることがあります。

API ドキュメント (Swagger) は https://my.local.konomi.tv:7000/api/docs にあります。  
API ドキュメントは FastAPI によって自動生成されたものです。  
その場で API リクエストを試せたり、グラフィカルに API ドキュメントを参照できたりととても便利です。ぜひご活用ください。

### クライアント

クライアントは Vue.js 2.x の SPA (Single Page Application) で構築されており、コーディングとビルドには少なくとも Node.js が必要です。  
Node.js v16, npm v8, yarn v1 で開発しています。

クライアントのデバッグは `client/` フォルダにて `yarn dev` または `npm run dev` を実行し、https://my.local.konomi.tv:7001/ にてリッスンされる開発用サーバーにて行っています。  

> 事前に `yarn install` を実行し、依存するパッケージをインストールしておいてください。  

> 以前は npm を使っていたのですが、GitHub からのパッケージの更新がなぜかかなり重いため、yarn に変更しました。パッケージのインストールは遅いですが、npm を使ってビルドすることもできます。

`yarn dev` でリッスンされる開発サーバーでは、コードすると自動的に差分が再ビルドされます。  
API サーバーは別のポート (7000) でリッスンされているので、開発サーバーでのみ API のアクセス先を `http://(サーバーと同じホスト名):7000/` に固定しています。

クライアントの静的ファイルは、`client/dist/` に配置されているビルド済みのものをサーバー側で配信するように設定されています。  
そのため、`yarn build` でクライアントのビルドを更新したのなら、サーバー側で配信されるファイルも同時に更新されることになります。

## 寄付・支援について

<img width="100%" src="https://user-images.githubusercontent.com/39271166/201461029-2f75a38f-928c-4f23-8552-e2d845d67365.jpg"><br>

とてもありがたいことに私に寄付したいという方が複数いらっしゃったので、**今のところ [アマギフ (Amazon ギフト券)](https://www.amazon.co.jp/b?node=3131877051&tag=tsukumijima-22) だけ受けつけています。**  

特典などは今のところありませんが、それでも寄付していただけるのであれば、アマギフの URL を [Twitter の DM (クリックすると DM が開きます)](https://twitter.com/messages/compose?recipient_id=1194724304585248769) か `tvremoteplusあっとgmail.com` まで送っていただけると、大変開発の励みになります…🙏🙏🙏

> アマギフを送っていただく際に KonomiTV に実装してほしい機能を添えていただければ、もしかするとその機能を優先して実装することがある…かもしれません。  
> ただし、私個人のプライベートやモチベーション、技術的な難易度などの兼ね合いもあるため、『必ず実装する』とお約束することはできません。あくまで私からのちょっとしたお礼レベルなので、基本期待しないでいただけると…。

また、一応 **[Amazon のほしい物リスト](https://www.amazon.co.jp/hz/wishlist/ls/3AZ4RI13SW2PV) もあります。** どのようなものでも贈っていただけると泣いて喜びます…。

このほか、**[こちら](https://www.amazon.co.jp/?tag=tsukumijima-22) のリンクをクリックしてから Amazon で何かお買い物していただくことでも支援できます (Amazon アソシエイト)。**  
買う商品はどのようなものでも OK ですが、より [紹介料率 (商品価格のうち、何%がアソシエイト参加者に入るかの割合)](https://affiliate.amazon.co.jp/help/node/topic/GRXPHT8U84RAYDXZ) が高く、価格が高い商品の方が、私に入る報酬は高くなります。Kindle の電子書籍や食べ物・飲み物は紹介料率が高めに設定されているみたいです。  

> もしかすると GitHub から Amazon に飛ぶと[リファラ](https://wa3.i-3-i.info/word129.html)チェックで弾かれてしまうかもしれないので、リンクをコピペして新しく開いたタブに貼り付ける方が良いかもしれません。

## Special Thanks

- [xtne6f](https://github.com/xtne6f) さん： KonomiTV と EDCB を連携させるための実装や、[tsreadex](https://github.com/xtne6f/tsreadex) の実装の依頼・開発などで多大なご協力をいただきました。
- [rigaya](https://github.com/rigaya) さん： QSVEncC・NVEncC・VCEEncC での動作オプションや不具合の対応、エンコードパラメーターのアドバイスなどを支援していただきました。
- [xqq](https://github.com/xqq) さん： [mpegts.js](https://github.com/xqq/mpegts.js) で MPEG-TS をダイレクトストリーミングできるようになり、わずか最短 1.5 秒の低遅延でテレビを視聴することができるようになりました。mpegts.js のヘルプやプレイヤーへの導入のサポートなども支援していただきました。
- [monyone](https://github.com/monyone) さん：[aribb24.js](https://github.com/monyone/aribb24.js) のおかげで、ARIB 字幕や文字スーパーを完璧に表示できるようになりました。また、字幕関連のほか、iPhone 向けの [LL-HLS ライブストリーミングの実装](https://github.com/monyone/biim) やトラブルシューティング、導入のサポートなどで多大なご協力をいただきました。

KonomiTV の開発にあたり、ほかにも沢山の方からサポートやフィードバックをいただきました。  
この場をお借りして厚く感謝を申し上げます。 本当にありがとうございました！

## License

[MIT License](License.txt)
