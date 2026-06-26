# WordPress SEO エージェント

狙うキーワードを 1 つ与えると、**[分析] → [構成] → [作成] → [校正] → [監査]** を
自律実行し、合格した記事を WordPress に **下書き（draft）** として自動投稿する
Python スクリプトです。LLM は Anthropic Claude（公式 SDK）を使用します。

## 3 つの特徴

- **自己修正ループ**：監査が不合格なら、フィードバックを保持したまま分析に戻り最大 3 回リライト（無限ループ防止つき）。
- **JSON 監査**：監査は Structured Outputs（`messages.parse` + Pydantic）で `{"pass":..., "score":..., "reason":..., "improvements":[...]}` を必ずパース可能な形で返す。
- **設定はすべて `.env`**：API キー・WP 認証情報をコードに直書きしない。

## セットアップ

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 値を埋める
```

`.env` の主な項目:

| 変数 | 説明 |
| --- | --- |
| `ANTHROPIC_API_KEY` | Claude の API キー |
| `SEO_AGENT_MODEL` | 使用モデル（既定 `claude-opus-4-8`） |
| `SEO_AGENT_PASS_SCORE` | 合格スコア（既定 80） |
| `SEO_AGENT_MAX_LOOPS` | 最大リライト回数（既定 3） |
| `WORDPRESS_URL` / `WORDPRESS_USERNAME` / `WORDPRESS_APP_PASSWORD` | REST API + アプリケーションパスワード |
| `WORDPRESS_DEFAULT_CATEGORIES` / `WORDPRESS_DEFAULT_TAGS` | 既定カテゴリ・タグ（任意・自動作成） |

> WordPress 側は「ユーザー → プロフィール → アプリケーションパスワード」で発行した値を使います。

## 使い方

```bash
# 生成 → 監査合格で下書き投稿
python main.py "ふるさと納税 おすすめ 食品"

# WordPress に投稿せず原稿だけ確認（認証情報なしでも可）
python main.py "ふるさと納税 おすすめ 食品" --dry-run
```

終了コード: `0`=合格して投稿 / `2`=規定回数で不合格 / `1`=実行エラー。

## 拡張ポイント

`fetch_competitor_insights()` は競合（上位ページ）分析の差し込み口です。
Google Custom Search / SerpAPI 等を実装すれば、上位記事の構成を踏まえた
より精度の高い構成設計に拡張できます（現状は未連携で LLM 内部知識のみ）。
