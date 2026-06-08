---
name: release-checklist
description: "KonomiTV のリリース前チェックリストと手順ガイド。リリースを打つ前にユーザーと一緒に確認事項を順番に潰していくためのスキル。リリース前の準備やリリース手順を確認したいときに使う"
---

KonomiTV の新バージョンをリリースする前に、ユーザーと一緒に確認事項を潰していくためのチェックリスト。
リリース頻度が数ヶ月おきのため手順を忘れがちなので、このスキルで毎回漏れなく進められるようにする。

## リリースフローの全体像

```
[手動] リリース前の確認・準備 (このスキルのスコープ)
  ↓
[手動] Dockerfile のリリース準備コミット
  ↓
[手動] GitHub Actions「Create Release Commit」を workflow_dispatch で実行
  ↓ (以降は自動)
[自動] バージョン番号の一括更新・クライアントビルド・Release コミット作成
[自動] release ブランチ更新 → インストーラー & サードパーティビルド
[自動] タグ作成 → GitHub Release 作成 (generateReleaseNotes: true)
[自動] Docker イメージのビルド & 公開
  ↓
[手動] GitHub Release のリリースノートを編集 (generate-release-notes スキルの出力をマージ)
```

## チェックリスト

以下のチェック項目を上から順にユーザーと確認していく。
エージェントが自動で確認できる項目はエージェントが実行し、ユーザーへの確認が必要な項目はユーザーに質問する。

### Phase 1: コードの最終確認

- [ ] **master ブランチが最新か**
  - `git status` と `git log --oneline -5` で確認する
  - 未 push のコミットがないか、意図しない変更が残っていないか
- [ ] **クライアントの lint / 型チェックが通るか**
  - `client/` で `yarn lint` と `yarn typecheck` を実行する
  - クライアントのビルド自体は Create Release Commit ワークフロー内で自動実行されるため、手元での `yarn build` は不要
- [ ] **サーバー側の lint / 型チェックが通るか**
  - `server/` で `poetry run task lint` を実行する

### Phase 2: サードパーティライブラリの確認

- [ ] **サードパーティライブラリのバージョンが最新か**
  - `.github/workflows/build_thirdparty.yaml` に定義されている各ライブラリのバージョンを確認する
  - 特に QSVEncC / NVEncC / VCEEncC / FFmpeg / rkmppenc は頻繁に更新されるので、`gh release list` で各リポジトリの最新リリースを取得し、現在のバージョンと比較する
    - `gh release list --repo rigaya/QSVEnc --limit 1`
    - `gh release list --repo rigaya/NVEnc --limit 1`
    - `gh release list --repo rigaya/VCEEnc --limit 1`
    - `gh release list --repo rigaya/rkmppenc --limit 1`
    - FFmpeg は BtbN/FFmpeg-Builds のリリースを確認する
  - 差分がある場合は「現在 X.XX、最新 X.XX」のように比較結果をユーザーに報告し、更新するか判断を仰ぐ
  - 更新が必要な場合は、ユーザーが `build_thirdparty.yaml` のバージョンを更新してコミットする
- [ ] **開発版 Dockerfile の thirdparty URL が最新の CI ランの成果物を指しているか**
  - `Dockerfile` 内の `nightly.link` URL の `actions/runs/XXXXXXX` が、最新の build_thirdparty ワークフロー実行の run ID と一致しているか確認する
  - サードパーティライブラリのバージョンを更新した場合、CI が完了した後にこの URL も更新する必要がある

### Phase 3: Dockerfile のリリース準備

- [ ] **Dockerfile を「リリース版用」に切り替える**
  - 以下の変更を行い、`Update: [Dockerfile] リリース準備` としてコミットする
  - **ただし、この時点ではまだ push しない。** リリース版 URL のバージョン番号は Create Release Commit ワークフローが自動で更新するため、前回リリースのバージョン番号のままで構わない

  変更内容:
  ```
  # 「リリース版用」の行のコメントを外す
  RUN aria2c -x10 https://github.com/tsukumijima/KonomiTV/releases/download/v(前回バージョン)/thirdparty-linux.tar.xz
  RUN tar xvf thirdparty-linux.tar.xz

  # 「開発版用」の行をコメントアウトする
  # RUN aria2c -x10 https://nightly.link/tsukumijima/KonomiTV/actions/runs/XXXXXXX/thirdparty-linux.tar.xz.zip
  # RUN unzip thirdparty-linux.tar.xz.zip && tar xvf thirdparty-linux.tar.xz
  ```

### Phase 4: リリースノートの下書き生成

- [ ] **generate-release-notes スキルを実行して下書きを生成する**
  - `/tmp/konomi-tv-release-notes-draft.md` に出力される
  - ユーザーがこの下書きをベースに加筆修正し、最終版を用意する
  - リリースノートの最終版は GitHub Release 作成後に編集画面で反映する

### Phase 5: リリースの実行

- [ ] **Dockerfile のリリース準備コミットを push する**
  - Phase 3 で作成したコミットを `git push` する
- [ ] **GitHub Actions「Create Release Commit」を実行する**
  - ユーザーに依頼: GitHub の Actions タブから `Create Release Commit` ワークフローを手動実行してもらう
  - バージョン番号を入力する (例: `0.14.0`、`v` は付けない)
  - このワークフローが以下を自動で行う:
    - 各ファイルのバージョン番号を一括更新
    - クライアントのビルド
    - `Release: version X.X.X` コミットの作成と push
    - `release` ブランチの更新
- [ ] **Publish Release ワークフローの完了を待つ**
  - release ブランチの更新をトリガーに、インストーラー・サードパーティライブラリのビルドとリリース作成が自動実行される
  - 完了まで30分〜1時間程度かかる

### Phase 6: リリース後の作業

- [ ] **GitHub Release のリリースノートを編集する**
  - GitHub が `generateReleaseNotes: true` で自動生成した内容 (Dependabot PR 一覧・外部 PR 一覧・New Contributors) に、Phase 4 で準備した下書きをマージする
  - スクリーンショットや動画の追加、文面の最終調整を行う
- [ ] **Docker イメージが正常に公開されたか確認する**
  - `Publish Docker Image` ワークフローの実行結果を確認する
- [ ] **Dockerfile を「開発版用」に戻す**
  - Phase 3 の逆の変更を行う
  - thirdparty の nightly.link URL は最新リリースの build_thirdparty ワークフローの run ID に更新する
  - `Update: [Dockerfile] 開発版用サードパーティーライブラリを更新` としてコミット & push する
- [ ] **リリースの告知**
  - ユーザーに確認:「Twitter (X) での告知は行いますか？」

## エージェントが自動実行できる項目

以下はエージェントが自律的に実行してよい項目:

- `git status` / `git log` による状態確認
- `yarn lint` / `yarn typecheck` によるクライアント側 lint / 型チェック確認
- `poetry run task lint` によるサーバー側 lint 確認
- Dockerfile の diff 確認
- `.github/workflows/build_thirdparty.yaml` のバージョン確認
- `gh release list` で各サードパーティライブラリの最新バージョンとの比較

## エージェントがユーザーに確認すべき項目

以下は必ずユーザーの判断・操作が必要:

- サードパーティライブラリの更新判断
- GitHub Actions ワークフローの手動実行
- リリースノートの最終承認
- リリース告知の判断
