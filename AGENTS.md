# AGENTS.md

## プロジェクト固有の注意事項

- yarn や poetry はそれぞれ `client/` と `server/` のディレクトリに移動した状態で実行してください。ルートディレクトリにはパッケージ管理系のファイルは一切配置していません。
- サーバー側では poetry を使っているので、python コマンドは必ず全て poetry run 経由で実行します。python を直接実行すると .venv/ 以下のライブラリがインストールされていないために失敗します。
- 開発サーバーは `yarn dev` で起動します。
- クライアントの開発サーバーは `https://my.local.konomi.tv:7001` でリッスンされるので (Akebi HTTPS Server による HTTPS リバースプロキシが同時に起動されるため) 、Chrome DevTools MCP では `https://my.local.konomi.tv:7001` を使ってアクセスしてください。

## 技術スタック

KonomiTV は、クライアント・サーバーアーキテクチャに基づく Web アプリケーション (PWA) です。
以下の2つの主要部分で構成されています。

KonomiTV が一般的な Web サービスと異なる点は、フロントエンドと API サーバーの両方が各ユーザーの PC 環境で動作する点です。
したがって、Windows と Linux の両方で動作するように開発する必要があります。
Windows では Windows サービス、Linux では pm2 サービスとして動作するよう設計しています。

- `client/`: KonomiTV のフロントエンドアプリケーション (PWA)
  - TypeScript
  - yarn v1
  - Vite
  - Vue.js 3.x
    - Vuetify 3.x
    - Pinia
- `server/`: KonomiTV のバックエンド API サーバー
  - Python 3.11
  - Poetry
  - Uvicorn
  - FastAPI
    - Pydantic v2
  - Tortoise ORM
    - SQLite (ローカル動作が必要なため MySQL や PostgreSQL は採用できなかった)
    - Aerich

## ディレクトリ構成

### クライアント (`client/`)

- `public/`: 直接提供される静的ファイル
- `src/`: ソースコード
  - `views/`: Vue ルートコンポーネント/ページ
    - `TV/`: テレビ視聴関連ページ
    - `Videos/`: 動画関連ページ
    - `Reservations/`: 予約関連ページ
    - `Settings/`: アプリケーション設定ページ
    - `Login.vue`: ログインページ
    - `Register.vue`: アカウント登録ページ
    - `MyList.vue`: マイリストページ
    - `WatchedHistory.vue`: 視聴履歴ページ
    - `MyPage.vue`: マイページ
    - `NotFound.vue`: 404 エラーページ
  - `components/`: Vue コンポーネント
    - `Watch/`: テレビ・録画番組視聴画面向けコンポーネント群
      - `Panel/`: 視聴画面右側のパネル内表示用コンポーネント群
        - `Twitter/`: ツイート検索/タイムライン表示/キャプチャ管理/ツイート表示用コンポーネント群
    - `Settings/`: 設定ページから呼び出されるダイアログコンポーネント群
    - `HeaderBar.vue`: ヘッダーバー
    - `SPHeaderBar.vue`: スマートフォン用ヘッダーバー
    - `Navigation.vue`: ナビゲーション
    - `BottomNavigation.vue`: スマートフォン用下部ナビゲーション
    - `Snackbars.vue`: 通知メッセージ表示コンポーネント
    - `Breadcrumbs.vue`: パンくずリスト表示コンポーネント
  - `stores/`: 状態管理 (Pinia ストア)
  - `services/`: サーバー API へのサービスクライアント
    - `player/`: KonomiTV の視聴画面で用いられるライブ/ビデオプレイヤーのロジック (重要)
      - `managers/`: PlayerController に紐づく様々な機能のロジックを提供し、各機能に責任を持つ PlayerManager 群
      - `PlayerController.ts`: 動画プレイヤーである DPlayer に関連するロジックを丸ごとラップするクラスで、KonomiTV の再生系ロジックの中核を担う
  - `utils/`: ユーティリティ関数とヘルパー
  - `workers/`: 重い処理をバックグラウンドで実行するための Web Workers コード (with Comlink)
  - `styles/`: グローバル CSS の定義 (グローバル CSS は `App.vue` の方がメイン)
  - `router/`: Vue Router 設定
  - `plugins/`: Vue プラグインの初期化定義
  - `App.vue`: アプリケーションのルートコンポーネント (グローバル CSS 定義もここに含まれる)
  - `main.ts`: アプリケーションのエントリーポイント・初期化処理
- `package.json`: Node.js プロジェクト設定と依存関係 (yarn)
- `vite.config.mts`: Vite ビルド設定
- `tsconfig.json`: TypeScript 設定
- `.eslintrc.json`: ESLint コードスタイル設定

### サーバー (`server/`)

- `app/`: FastAPI アプリケーションコード
  - `routers/`: API ルートハンドラー
    - `ChannelsRouter.py`: チャンネル関連メタデータ取得 API
    - `ProgramsRouter.py`: 番組関連メタデータ取得 API
    - `VideosRouter.py`: 録画番組メタデータ取得 API
    - `SeriesRouter.py`: 番組シリーズ関連 API
    - `LiveStreamsRouter.py`: 放送中テレビ放送のライブストリーミング配信関連 API
    - `VideoStreamsRouter.py`: 録画番組のストリーミング配信関連 API
    - `ReservationsRouter.py`: EDCB と連携したテレビ番組の録画予約関連 API
    - `ReservationConditionsRouter.py`: EDCB と連携したテレビ番組の自動録画予約条件 (EPG 自動予約) 関連 API
    - `DataBroadcastingRouter.py`: データ放送のインターネット接続機能向け API
    - `CapturesRouter.py`: キャプチャ画像管理 API
    - `TwitterRouter.py`: Twitter 連携 API
    - `NiconicoRouter.py`: ニコニコ実況連携 API
    - `UsersRouter.py`: ユーザーアカウント管理 API
    - `SettingsRouter.py`: クライアント・サーバー設定管理 API
    - `MaintenanceRouter.py`: サーバーメンテナンス用 API
    - `VersionRouter.py`: バージョン情報 API
  - `models/`: データベースモデルとスキーマ
    - `Channel.py`: チャンネル情報を管理するモデル（放送局情報、チャンネル番号、ロゴ、ストリーム設定など）
    - `Program.py`: 放送番組情報を管理するモデル（番組メタデータ、EPG 番組情報、タイトル、番組詳細、ジャンルなど）
    - `RecordedProgram.py`: 録画済み番組のメタデータを管理するモデル（EPG 録画番組情報、録画開始/終了時刻など）
    - `RecordedVideo.py`: 録画済み番組の動画ファイル情報を管理するモデル（ファイルパス、映像/音声コーデック、ファイルサイズなど）
    - `Series.py`: 番組シリーズ情報を管理するモデル（シリーズ名、シリーズ ID など）
    - `SeriesBroadcastPeriod.py`: 番組シリーズの放送期間情報を管理するモデル
    - `TwitterAccount.py`: Twitter アカウント連携情報を管理するモデル（トークン、認証情報など）
    - `User.py`: ユーザーアカウント情報を管理するモデル（認証情報、権限など）
  - `migrations/`: Tortoise ORM のマイグレーションツール: Aerich 向けの DB マイグレーション定義 (Aerich で自動生成されたコードを修正したもの)
  - `streams/`: テレビ放送のライブストリーミング・録画番組のオンデマンドストリーミング関連の実装
    - `LiveEncodingTask.py`: ライブストリーミング用のエンコード・ストリーミングタスクを管理
    - `VideoEncodingTask.py`: 録画番組用のエンコード・ストリーミングタスクを管理
    - `LiveStream.py`: 放送波のライブストリーミングの状態管理
    - `VideoStream.py`: 録画番組のオンデマンドストリーミングの状態管理
    - `LivePSIDataArchiver.py`: 放送波から PSI/SI データを抽出・アーカイブする機能の実装
  - `metadata/`: 録画番組データから番組情報などのメタデータを抽出・保存するための実装
    - `RecordedScanTask.py`: 録画フォルダの監視とメタデータの DB への同期を行うタスク
    - `MetadataAnalyzer.py`: 録画ファイルのメタデータを解析するクラス
    - `TSInfoAnalyzer.py`: 録画 TS ファイルや録画データ関連ファイルに含まれる番組情報を解析するクラス
    - `ThumbnailGenerator.py`: プレイヤーのシークバー用タイル画像と、候補区間内で最も良い1枚の代表サムネイルを生成するクラス
    - `KeyFrameAnalyzer.py`: 録画ファイルのキーフレーム情報を解析するクラス
    - `CMSectionsDetector.py`: 録画 TS ファイルに含まれる CM 区間を検出するクラス
  - `utils/`: ユーティリティ関数とヘルパー
    - `edcb/`: EDCB 連携用の API クライアント実装
    - `JikkyoClient.py`: ニコニコ実況・NX-Jikkyo 連携用の API クライアント実装
    - `TwitterGraphQLAPI.py`: Twitter API 連携用にリバースエンジニアリングして開発した API クライアント実装
    - `TSInformation.py`: 日本のテレビ放送で用いられている MPEG2-TS から情報を取得する際に役立つユーティリティ群
    - `OAuthCallbackResponse.py`: OAuth 認証のコールバック時にブラウザに情報を渡すために返す特殊なレスポンス
    - `DriveIOLimiter.py`: ドライブごとの同時実行数を制限するためのユーティリティクラス
    - `ProcessLimiter.py`: プロセスごとの同時実行数を制限するためのユーティリティクラス
  - `app.py`: FastAPI アプリケーションやルーターの初期化・バックグラウンドタスクの定義
  - `config.py`: サーバー設定 (`config.yaml`) のロードとバリデーション
  - `constants.py`: サーバー全体で用いられるグローバル定数
  - `logging.py`: ロギング設定
  - `schemas.py`: API リクエスト/レスポンス型に用いる Pydantic スキーマ
- `data/`: アプリケーションデータ用ディレクトリ
  - `database.sqlite`: SQLite データベースファイル
- `logs/`: アプリケーションログ用ディレクトリ
- `misc/`: メンテナンス・デバッグ用 Pythonスクリプト群
- `static/`: サーバー API によって提供される静的ファイル (Git 管理下にあり、放送局ロゴなどが含まれる)
- `thirdparty/`: FFmpeg や QSVEncC などのエンコーダーをはじめとした、ビルド済みのサードパーティー実行ファイル (Git 管理外で、`poetry run task update-thirdparty` で更新する)
- `pyproject.toml`: Python プロジェクト設定と依存関係 (Poetry)
- `KonomiTV.py`: KonomiTV サーバーのエントリーポイント
- `KonomiTV-Service.py`: Windows サービス管理スクリプト & Windows サービスのエントリーポイント

## コーディング規約

### 全般
- コードをざっくり斜め読みした際の可読性を高めるため、日本語のコメントを多めに記述する
- コードを変更する際、既存のコメントは、変更によりコメント内容がコードの記述と合わなくなった場合を除き、コメント量に関わらずそのまま保持する
- ログメッセージに関しては文字化けを避けるため、必ず英語で記述する
- それ以外のコーディングスタイルは、原則変更箇所周辺のコードスタイルに合わせる
- 不要な薄いラッパーや別名関数は作らず、責務のあるコンポーネントだけを追加する。
- コメントは冗長なくらいでちょうどよい。条件分岐・ループ・例外処理の直前にはその意図を書き、Python では `__init__()` で代入するインスタンス変数には「保持する情報」「参照されるメソッド」「前提条件」を必ずコメントとして記す。クラス Docstring には責務のみを記載し、引数説明は `__init__()` の Docstring に集約する
- Enum・Literal・Union 型の文字列表現は `tweet_capture_watermark_position: 'None' | 'TopLeft' | 'TopRight' | 'BottomLeft' | 'BottomRight';` のように基本的に UpperCamelCase で命名する必要がある
- 通常の Web サービスではないかなり特殊なソフトウェアなので、コンテキストとして分からないことがあれば別途 Readme.md を読むか、私に質問すること
- DB レコードの Pydantic / TypeScript 定義では、親となるレコード本体のスキーマを最上位に配置し、その下に子スキーマをフィールドの定義順に従って並べる
- JSON フィールドの値を生成する際は、辞書リテラル (`{}`) を直接書くのではなく、TypedDict のコンストラクタを使用して型構造を明示的に示す
- 画像の幅・高さ・総数・間隔など、視覚的に重要な情報を持つフィールドは定義の上部に集約し、重要度の高い順に配置することで一目で把握できるようにする
- 親スキーマから子スキーマへの並び順を徹底し、関連する子スキーマは親となる DB レコードスキーマの直下にまとめて配置する。可読性を損なうような配置変更は行わない
- TypeScript 側のスキーマ定義も Python 側と同じ順序を維持する。もし差分が発生する場合は、その理由をコメントで明記する

### Python コード
- **コードの編集後には、必ず `poetry run task lint` コマンドで、Ruff によるコードリンターと Pyright による型チェッカーを実行すること**
- 文字列にはシングルクォートを用いる (Docstring を除く)
- Python 3.11 の機能を使う (3.10 以下での動作は考慮不要)
- ビルトイン型を使用した Type Hint で実装する (from typing import List, Dict などは避ける)
- Pydantic モデル定義では必ず Annotated 記法を使う。`= Field()` 型の定義は行わずに全て Annotated 記法で定義すること
- 変数・インスタンス変数は snake_case で命名する
- 関数・クラス名は UpperCamelCase で命名する (例: `class VideoEncodingTask:`, `def GetClientURL():`)
  - FastAPI で定義するエンドポイントの関数名も UpperCamelCase で命名する必要がある
  - FastAPI で定義するエンドポイント名は、文法的に比較的正しくなるようパス名や操作を並び替えた上で、「〇〇API」の形で命名すること
    - 例: GET `/streams/live/{display_channel_id}/{quality}/mpegts` -> `LiveMPEGTSStreamAPI`
    - 例: PUT `/users/me` -> `UserUpdateAPI`
- クラスに生えたメソッド名は lowerCamelCase で命名する (例: `LiveStream.getONAirLiveStreams()`)
- 複数行のコレクションには末尾カンマを含める
- `getattr()` で型チェッカーを黙らせるのは禁止。参照する属性は型ヒントやプロパティできちんと公開し、どうしても `getattr()` が必要な場合は「その属性が必ず存在する根拠」を詳細にコメントする
- すべての Docstring には Args / Returns を明記し、コメントは処理のまとまりごとに必ず加えて「なぜそうするのか」「何を意図した値なのか」を丁寧に説明する。コードを読まなくてもコメントから処理の流れを追えるようにする
- このプロジェクトでは必ずロギングモジュールとして `import logging` の代わりに `from app import logging` を使うべき

### Vue / TypeScript コード

- **コードの編集後には、必ず `yarn lint; yarn typecheck` コマンドで、ESLint によるコードリンターと TypeScript による型チェッカーを実行すること**
- 文字列にはシングルクォートを用いる
- 新規で実装する箇所に関しては Vue 3 Composition API パターンに従う
  - Vue.js 2 から移行した関係で Options API で書かれているコンポーネントがあるが、それらは Options API のまま維持する
- 新規で実装する Vue 3 Composition API のコンポーネントでは、原則として変数を lowerCamelCase で命名する
  - FastAPI サーバーでは snake_case で命名している関係で外部 API のフィールドは全てスネークケースになっているが、これはそのまま参照して良い
- TypeScript による型安全性を確保する
- コンポーネント属性は可能な限り1行に記述 (約100文字まで)
- 必ず day.js を utils/index.ts からインポートして使うこと！！！new Date() を絶対に使うな！！！

### CSS / SCSS スタイリング
- このプロジェクトで使用している色 (CSS 変数) などは `client/src/App.vue` や `client/src/plugins/vuetify.ts` に定義しているので、それを参照すること
- 新規に UI を実装する際は、すでに実装されている他のコンポーネントやページの大まかなデザインの方向性を踏襲すること
