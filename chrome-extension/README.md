# KonomiTV Twitter Embed PoC

KonomiTV のページ内に公式 x.com Web App を iframe 表示できるか確認するための最小拡張です。

KonomiTV を最上位ページに保ったまま、Twitter が `SameSite=Lax` で保存する認証 Cookie を iframe 内の Twitter API へ補完します。

## 読み込み手順

1. Chrome で `chrome://extensions/` を開きます
2. 右上の「デベロッパーモード」を有効にします
3. 「パッケージ化されていない拡張機能を読み込む」を押します
4. `/Develop/KonomiTV/chrome-extension` を選択します
5. 通常ウィンドウで KonomiTV の `https://*.local.konomi.tv:*` ページを開きます

## 確認項目

- 画面右下に x.com のパネルが表示されます
- x.com のホームタイムラインがログイン済み状態で表示されます
- タイムライン、通知、プロフィールなどの API リクエストが認証済み状態で完了します

## 実装メモ

- `background.js` は x.com / twitter.com の `sub_frame` 応答から `Content-Security-Policy` と `X-Frame-Options` を削除します
- DNR の `initiatorDomains` は `local.konomi.tv` に絞っています
- `background.js` はホスト・Path・分割キーが適合する Twitter の Cookie を Chrome から取得し、Twitter の Service Worker が発行する要求にも補完します
- Cookie はブラウザ終了時に破棄される DNR セッション規則へ保持し、KonomiTV タブが1つもない間は規則自体を削除します
- `konomitv-panel.js` は iframe のリファラーを送信せず、ローカルの KonomiTV オリジンが Twitter の onboarding API へ渡らないようにします
- `konomitv-panel.js` は KonomiTV 側へ検証用 iframe パネルを追加します
- `x-frame.js` は KonomiTV 内の x.com iframe だけへ表示調整用 CSS を注入します
