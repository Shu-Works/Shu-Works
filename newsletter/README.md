# メルマガ自動下書きツール（MailerLite × Python）

海外向けデジタル塗り絵（Shopify 販売）のマーケティング用。
指定テーマから **英語のメルマガ（件名・本文・画像・CTA・フッター）** を生成し、
MailerLite に **「下書き（Draft）」キャンペーン** として保存する。

> あなたの作業は、スマホで MailerLite を開いて **最終確認 → 配信ボタンを押すだけ**。

---

## Three Things（このツールがやること）

1. **テーマから英語の物語を書く** — 日本文化／四季／レトロ風景。Claude API があれば毎回オリジナル、無ければ定番文面。
2. **完成した HTML メールを組む** — ヘッダー画像・本文・Shopify への CTA ボタン・配信解除リンク付きフッターまで。
3. **MailerLite に下書きとして保存する** — 配信はしない。人間が最終確認して送る。

---

## セットアップ（初回のみ）

```bash
cd newsletter

# 1. 依存ライブラリのインストール
pip3 install -r requirements.txt

# 2. 設定ファイルを作成して値を埋める
cp .env.example .env
nano .env        # MAILERLITE_API_KEY / FROM_EMAIL / SHOP_URL などを記入
```

`.env` に入れる項目は `.env.example` にすべてコメント付きで書いてある。
**最低限必要なのは** `MAILERLITE_API_KEY` / `FROM_NAME` / `FROM_EMAIL` / `SHOP_URL` の4つ。

- **`ANTHROPIC_API_KEY`** を入れると Claude が毎回オリジナル文面を生成する（任意）。無くてもテンプレで動く。
- **`PEXELS_API_KEY`** を入れるとテーマに合った著作権フリー画像を自動選定する（任意）。無ければプレースホルダ画像。

---

## 使い方

```bash
# まず見た目だけ確認（MailerLite には投稿しない）。output/ に HTML が出る
python3 create_draft.py --dry-run

# テーマ一覧
python3 create_draft.py --list

# 本番：ランダムなテーマで下書きを作成
python3 create_draft.py

# テーマを指定して作成
python3 create_draft.py --theme four_seasons
```

利用可能なテーマ（`themes.json` で追加・編集できる）:

| キー | 内容 |
| --- | --- |
| `japanese_culture` | 日本の日常文化・職人の手仕事 |
| `four_seasons` | 日本の四季・七十二候 |
| `retro_landscapes` | 昭和レトロな街並み |

---

## 定期実行（毎週1回 自動で下書きを作る）

`run_weekly.sh` を cron に登録する。

```bash
# 実行権限を付与（初回のみ）
chmod +x newsletter/run_weekly.sh

# cron を編集
crontab -e
```

エディタが開いたら、次の1行を追記して保存（**毎週月曜の朝9時**に実行する例）:

```cron
0 9 * * 1 /home/user/Shu-Works/newsletter/run_weekly.sh
```

cron の時刻フォーマット = `分 時 日 月 曜日`（曜日: 0=日曜, 1=月曜 … 6=土曜）。
他の例:

```cron
0 9 * * 5    # 毎週金曜 9:00
0 8 1 * *    # 毎月1日 8:00
```

登録できたか確認:

```bash
crontab -l
```

実行ログは `newsletter/weekly.log` に追記される（成功・失敗とも）。

> 補足: 上のパス `/home/user/Shu-Works/...` は現在の作業環境のもの。
> 別マシンに置く場合は実際の絶対パスに置き換えること。

---

## 仕組み（ファイル構成）

| ファイル | 役割 |
| --- | --- |
| `create_draft.py` | 本体。生成 → HTML 組み立て → MailerLite 投稿 |
| `themes.json` | テーマ定義・画像キーワード・フォールバック文面 |
| `email_template.html` | メールの HTML 雛形（table レイアウト・レスポンシブ） |
| `.env` | API キー等の秘密情報（Git 管理外） |
| `run_weekly.sh` | cron 用ラッパー |
| `output/` | `--dry-run` の HTML 出力先（Git 管理外） |

---

## よくあるエラー

- **`MailerLite API エラー (HTTP 401)`** … `MAILERLITE_API_KEY` が間違っている。
- **`HTTP 422` / from に関するエラー** … `FROM_EMAIL` が MailerLite で未認証。管理画面でドメイン/送信元を認証する。
- **画像がプレースホルダのまま** … `PEXELS_API_KEY` 未設定（任意なので問題なし。固定画像にしたいなら `HEADER_IMAGE_URL` を指定）。
- **文面がいつも同じ** … `ANTHROPIC_API_KEY` 未設定でテンプレ動作中。Claude を使うならキーを設定する。

---

## 設計メモ

- **API キーは絶対にコードに書かない** … すべて `.env`。`.gitignore` 済み。
- **配信は絶対に自動化しない** … 作るのは Draft だけ。最後の判断は人間（社長）が下す。
- **依存は最小** … `requests` と `python-dotenv` のみ。Claude も Pexels も requests 経由。
