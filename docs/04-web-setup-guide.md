# Web サイト 公開準備ガイド

**作成日**: 2026-05-26
**対象**: TODO 2.1（Web サイト）のセットアップ・公開作業

---

## 1. ファイル構成

```
/
├── index.html             # トップページ（LP）
├── faq.html               # よくある質問
├── contact.html           # お問い合わせフォーム
├── thanks.html            # 送信完了ページ
├── sitemap.xml            # 検索エンジン用サイトマップ
├── robots.txt             # クローラ制御
└── assets/
    └── style.css          # 共通スタイルシート
```

---

## 2. 公開前に差し替えるべきプレースホルダ

ファイル全体に対して以下のキーワードで一括検索・置換してください。

| プレースホルダ | 差し替え内容 |
| --- | --- |
| `example.jp` | 実際のドメイン（例：`jinsei-timelapse.jp`） |
| `0120-XXX-XXX` | 実際の電話番号 |
| `info@example.jp` | 実際のメールアドレス |
| `G-XXXXXXXXXX` | Google Analytics 4 の測定 ID |
| `YOUR_FORM_ID` | Formspree のフォーム ID |
| `2026 Jinsei Timelapse Project` | 実際の事業者名 |

`sitemap.xml` / `robots.txt` 内のドメインも忘れずに更新してください。

---

## 3. お問い合わせフォームのセットアップ

### 推奨：Formspree

1. https://formspree.io にサインアップ（無料プランで月 50 件まで）
2. 新規フォーム作成、通知先メールアドレスを設定
3. 発行されたフォーム ID（`xyzabc123` のような文字列）をコピー
4. `contact.html` の以下を更新：
   ```html
   action="https://formspree.io/f/YOUR_FORM_ID"
   ```
   ↓
   ```html
   action="https://formspree.io/f/xyzabc123"
   ```
5. 送信完了後のリダイレクト先 `_next` も実ドメインに更新

### 代替案

- **Google Forms**：埋め込みコードを `contact.html` の `<form>` 部分と差し替え（集計は楽だが自由度低い）
- **Netlify Forms**：Netlify でホスティングするなら `<form>` に `netlify` 属性を追加するだけ
- **自前バックエンド**：Lambda + SES、Cloudflare Workers + Resend など

---

## 4. Google Analytics 4 の設定

1. https://analytics.google.com で新規プロパティを作成
2. ウェブストリームを追加し、測定 ID（`G-XXXXXXXXXX`）を取得
3. `index.html` の `<!-- Google Analytics 4 ... -->` のコメントを外し、ID を差し替え
4. `faq.html` / `contact.html` / `thanks.html` にも同じスニペットを追加
5. 設定後、リアルタイムレポートで自分のアクセスを確認

### コンバージョン設定（推奨）

GA4 のイベントとして以下を計測すると、施策効果を可視化できます。

| イベント名 | トリガー |
| --- | --- |
| `form_submit` | お問い合わせフォームの送信完了（thanks.html 到達） |
| `view_pricing` | 料金プランセクションのスクロール到達 |
| `click_cta` | CTA ボタンのクリック |

---

## 5. Search Console（検索エンジン登録）

1. https://search.google.com/search-console でプロパティ追加
2. HTML タグ方式 or DNS 方式で所有権を確認
3. サイトマップ送信：`https://example.jp/sitemap.xml`
4. 1〜2 週間後にインデックス状況を確認

---

## 6. 動作確認チェックリスト

公開前に以下を必ず確認してください。

### 機能
- [ ] すべてのナビゲーションリンクが正しく機能する
- [ ] お問い合わせフォームがテスト送信できる
- [ ] 送信後に thanks.html へ遷移する
- [ ] 通知メールが届く
- [ ] FAQ のアコーディオン（開閉）が動作する

### 表示
- [ ] PC（Chrome / Safari / Firefox / Edge）で崩れがない
- [ ] スマホ（iPhone Safari / Android Chrome）で崩れがない
- [ ] タブレット表示
- [ ] 文字サイズが十分に読みやすい（特にシニア層向け）

### SEO
- [ ] title・description・OG タグが各ページで適切に設定されている
- [ ] 構造化データ（Service / FAQPage）が有効（Google Rich Results Test で確認）
- [ ] sitemap.xml がアクセス可能
- [ ] robots.txt がアクセス可能

### セキュリティ・プライバシー
- [ ] HTTPS で配信されている
- [ ] プライバシーポリシーへのリンクが有効
- [ ] Cookie の使用について明示している（GA4 利用時）
- [ ] フォームのスパム対策（ハニーポット）が機能している

---

## 7. ホスティング選択肢

| サービス | 料金 | 特徴 |
| --- | --- | --- |
| **Netlify** | 無料〜 | フォーム連携・無料 SSL・GitHub 連携が容易 |
| **Vercel** | 無料〜 | 高速 CDN・Next.js への移行が容易 |
| **GitHub Pages** | 無料 | リポジトリそのまま公開・カスタムドメイン可 |
| **さくらのレンタルサーバ** | 月 500 円〜 | 日本国内サポート・電話相談あり |
| **エックスサーバー** | 月 990 円〜 | 国内大手・WordPress 移行も可能 |

**推奨**：事業初期は **Netlify**（フォーム機能内蔵で構築が早い）→ アクセス増えたら自社サーバへ移行

---

## 8. 公開後のメンテナンス

| 頻度 | 作業 |
| --- | --- |
| 週次 | お問い合わせ対応・GA4 レポート確認 |
| 月次 | FAQ の追加・更新／サイト読み込み速度チェック |
| 四半期 | コンテンツの大規模見直し／競合チェック |
| 年次 | デザインリニューアル検討／法務文書の更新 |

---

## 9. 次のアクション

- [ ] ホスティングサービスを選定
- [ ] 独自ドメインを取得（お名前.com / ムームードメイン等）
- [ ] SSL 証明書を設定（Let's Encrypt 等で無料化可能）
- [ ] Formspree（または代替）のアカウント作成
- [ ] GA4 / Search Console を設定
- [ ] プレースホルダ一括置換
- [ ] PC・スマホで動作確認
- [ ] 公開後、SNS で告知
