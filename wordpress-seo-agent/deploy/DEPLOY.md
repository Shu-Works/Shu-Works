# サーバー常時稼働ガイド（Xserver クラウド / Linux）

WordPress SEO エージェントを **cron で定時実行**し、毎晩キーワードから記事を
生成 → **下書き（draft）投稿**まで自動化する手順です。

> 設計思想: このエージェントは「常駐プロセス」ではなく**バッチ処理**です。
> サーバーが24時間起動していて、cron が決めた時刻にジョブを発火させます。
> 「1回の発火 = 1記事」。発火回数で1日の本数とAPIコストをコントロールします。
> 投稿は下書きなので、**朝に人間が確認して公開**する運用と相性が良いです。

---

## 0. 前提
- Xserver クラウド（または VPS）に SSH でログインできること
- `git` / `python3`（3.10+ 推奨）/ `python3-venv` が使えること
  - 無ければ: `sudo apt update && sudo apt install -y git python3 python3-venv`

## 1. コードを配置（Publicリポジトリなので認証不要）
```bash
cd ~
git clone --branch claude/wordpress-seo-agent-python-gxeelp --single-branch \
  https://github.com/Shu-Works/Shu-Works.git
cd Shu-Works/wordpress-seo-agent
pwd   # ← この絶対パスを後で cron に使います
```

## 2. Python 環境を作る
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 3. 認証情報を設定（.env）
`.env` はあなた自身で作成・編集します（Git管理外。鍵は私には渡さないでください）。
```bash
cp .env.example .env
nano .env      # 値を埋める
chmod 600 .env # 自分だけ読める権限に
```
最低限うめる項目:
| 変数 | 内容 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude の API キー |
| `WORDPRESS_URL` | 例 `https://example.com`（末尾スラッシュ不要） |
| `WORDPRESS_USERNAME` | WordPress のユーザー名 |
| `WORDPRESS_APP_PASSWORD` | 「ユーザー → プロフィール → アプリケーションパスワード」で発行した値 |

任意（競合分析を使う場合のみ。無ければ自動スキップ）:
`SEO_SEARCH_PROVIDER` / `SERPAPI_API_KEY` または `GOOGLE_CSE_API_KEY`+`GOOGLE_CSE_ID`

## 4. まず投稿せずに動作確認（dry-run）
WordPress には投稿せず、原稿だけ生成して確認します。
```bash
source .venv/bin/activate
python main.py "ふるさと納税 おすすめ 食品" --dry-run
```
原稿HTMLが出力されればOK。APIキーが正しいか・課金が動くかをここで確認します。

## 5. 本番を1回だけ手動実行（下書き投稿テスト）
```bash
python main.py "ふるさと納税 おすすめ 食品"
```
WordPress 管理画面の「投稿 → 下書き」に記事が増えていれば成功です。

## 6. キーワードを登録
`deploy/keywords.csv` に狙うキーワードを1行ずつ書きます（上の行から処理されます）。
```bash
nano deploy/keywords.csv
```

## 7. ランナーを実行可能にして手動テスト
```bash
chmod +x deploy/run_queue.sh
deploy/run_queue.sh
cat deploy/logs/run-$(date +%Y%m%d).log     # 実行ログを確認
cat deploy/keywords.done.csv                # 処理済みの記録
```
`run_queue.sh` はキューの先頭1件を処理し、終わった行を `keywords.done.csv` に移します。

## 8. cron に登録（自動化）
```bash
crontab -e
```
`deploy/crontab.example` の行を**実パスに置き換えて**貼り付け、保存。
```bash
crontab -l   # 登録確認
```
> タイムゾーン確認: `date`。UTCなら `sudo timedatectl set-timezone Asia/Tokyo` でJSTに。

---

## 運用のポイント
- **本数の調整** = cron の発火回数。最初は「1日1本」で様子を見るのが安全。
- **コスト**: モデルは既定 `claude-opus-4-8` + `effort:high` + 競合解析を毎回行うため、
  1記事あたりのAPIコストが乗ります。高ければ `.env` で
  `SEO_AGENT_PASS_SCORE` を下げる / 競合分析をオフにする等で調整。
- **承認フロー**: 投稿は下書き。朝に WordPress で確認 → 手動公開、を推奨。
- **ログ**: `deploy/logs/run-YYYYMMDD.log`（実行）/ `deploy/logs/cron.log`（cron）。
- **失敗時の挙動**:
  - exit 2（3回でも不合格）→ そのKWは `keywords.done.csv` に `failed` で記録し、キューから外す。
  - exit 1（APIエラー等）→ キューに残し、次回の発火でリトライ。
- **多重起動防止**: `flock` で前回がまだ実行中なら今回はスキップします。

## トラブルシュート
- `venv の python が見つかりません` → 手順2をやり直す（`.venv` がagent直下にあるか確認）。
- `ANTHROPIC_API_KEY が .env に設定されていません` → `.env` の場所（agent直下）と中身を確認。
- cron で動かない → パスは**絶対パス**か、`crontab.example` のリダイレクト先 `logs/cron.log` を確認。
