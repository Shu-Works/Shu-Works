# サイトデプロイ手順（Cloudflare Pages）

> 2サイトを **完全無料・10分** で公開する手順。

---

## 前提

- ドメイン2本取得済：`sakusaku-kun.com` / `shu-works.co.jp`
- 本リポジトリ `sites/sakusaku-kun/` と `sites/shu-works/` にHTMLファイル一式
- Cloudflare アカウントを持っている（または無料で作成）
- GitHub アカウント

---

## 1. ドメインを Cloudflare に移管（既に終わってる前提）

CEOがドメインDNSを設定済みであれば、すでに完了している。
Cloudflare DNS で管理されていることを確認：

1. Cloudflare ダッシュボード → ドメイン一覧に `sakusaku-kun.com` と `shu-works.co.jp` が表示される
2. それぞれ「Active」ステータスになっている

---

## 2. sakusaku-kun.com を Cloudflare Pages にデプロイ

### Step 1：プロジェクト作成
1. Cloudflare ダッシュボード → 左メニュー「Workers & Pages」→「Create」
2. 「Pages」タブ →「Connect to Git」を選択
3. GitHub と連携（初回は認証が必要）
4. リポジトリ `Shu-Works/Shu-Works` を選択
5. ブランチ：`claude/line-estimate-service-plan-G1ED5`（または `main` にマージ後 `main`）

### Step 2：ビルド設定
- **Project name**: `sakusaku-kun`
- **Production branch**: 上記ブランチ
- **Framework preset**: `None`（静的HTML）
- **Build command**: 空欄
- **Build output directory**: `sites/sakusaku-kun`
- **Root directory**: 空欄（デフォルト）

### Step 3：デプロイ
- 「Save and Deploy」をクリック
- 1〜2分でデプロイ完了
- 自動的に `xxxxxx.pages.dev` というURLが発行される
- そのURLでサイトが表示されることを確認

### Step 4：カスタムドメイン設定
1. デプロイされたプロジェクト → 「Custom domains」タブ
2. 「Set up a custom domain」→ `sakusaku-kun.com` を入力
3. 「Add Custom Domain」
4. Cloudflare が自動的に DNS レコード（CNAME）を追加
5. 「www.sakusaku-kun.com」も同様に追加（推奨）
6. 数分後、`https://sakusaku-kun.com` でアクセス可能になる

→ SSL証明書は自動発行・更新（融資審査要件をクリア）

---

## 3. shu-works.co.jp を Cloudflare Pages にデプロイ

### Step 1：プロジェクト作成（2つ目）
1. 「Workers & Pages」→「Create」→「Pages」
2. 同じリポジトリを選択
3. 同じブランチを選択

### Step 2：ビルド設定
- **Project name**: `shu-works`
- **Production branch**: 同じブランチ
- **Framework preset**: `None`
- **Build command**: 空欄
- **Build output directory**: `sites/shu-works`

### Step 3：デプロイ → カスタムドメイン
- デプロイ完了 → Custom domains で `shu-works.co.jp` を追加
- `www.shu-works.co.jp` も追加

---

## 4. 確認

ブラウザで以下にアクセス：

| URL | 期待される結果 |
| --- | --- |
| https://sakusaku-kun.com | サク索くん TOP |
| https://sakusaku-kun.com/features.html | 機能ページ |
| https://sakusaku-kun.com/pricing.html | 料金プラン |
| https://shu-works.co.jp | Shu Works コーポレート TOP |
| https://shu-works.co.jp/company.html | 会社概要 |
| https://shu-works.co.jp/tokutei.html | 特定商取引法表記 |

---

## 5. SSL証明書の確認

ブラウザのアドレスバーで鍵マークを確認 → 「Connection is secure」と表示されれば OK。
SSL証明書は Let's Encrypt で自動発行・3ヶ月ごとに自動更新。

---

## 6. 今後の更新方法

サイトの内容を更新したい場合：

### CEO の操作はゼロ
- 俺（イーロン）にチャットで「○○を追加して」と指示
- 俺がリポジトリで該当ファイルを編集 → push
- Cloudflare Pages が自動的に検知してデプロイ（30秒〜2分）
- 公開サイトに反映

### CEO が直接編集する場合（推奨しない）
- GitHub の Web UI で該当ファイルを編集
- Commit → 自動デプロイ

---

## 7. トラブルシューティング

### "Custom domain not working"
- DNS が Cloudflare 管理になっているか確認
- カスタムドメイン追加から数分は反映に時間がかかる

### "SSL certificate pending"
- 通常5〜15分で発行完了
- 24時間経っても発行されない場合は Cloudflare サポートに連絡

### "404 Not Found" がページに出る
- ビルド出力ディレクトリが `sites/sakusaku-kun` / `sites/shu-works` になっているか確認
- index.html が直下に存在するか確認

### "ページが古い情報のまま"
- ブラウザのキャッシュをクリア
- Cloudflare のキャッシュをクリア（ダッシュボード → Caching → Purge Everything）

---

## 8. アクセス解析を入れる（オプション）

無料の解析ツール：
- **Cloudflare Web Analytics**（無料・プライバシー重視・Cookie不要）
  - Cloudflare ダッシュボード → Analytics → Web Analytics
  - 自動的に有効化される
- **Google Analytics 4**（必要なら別途設置）

---

## 9. 完了チェックリスト

- [ ] sakusaku-kun.com が公開され https でアクセスできる
- [ ] shu-works.co.jp が公開され https でアクセスできる
- [ ] 全ページがリンクで遷移できる
- [ ] フォームが送信できる（メーラーが起動）
- [ ] スマホ表示が崩れていない
- [ ] OGP 画像が表示される（SNS シェア時）

完了したら、Instagram Bio / LINE 自動応答 / 営業 DM の URL を本物に差し替え。
