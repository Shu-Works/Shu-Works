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

## 競合分析（任意）

`CompetitorAnalyzer` が検索上位ページの構成（タイトル・H2見出し・H3数・概算文字量）を
要約し、[分析]フェーズに取り込みます。検索プロバイダは **SerpAPI** または
**Google Custom Search** を、`.env` にキーがある方を自動採用します。

- `SEO_SEARCH_PROVIDER`（`auto`/`serpapi`/`google_cse`/`none`）
- `SERPAPI_API_KEY` または `GOOGLE_CSE_API_KEY` + `GOOGLE_CSE_ID`
- `SEO_COMPETITOR_TOP_N`（解析する上位件数、既定 5）

さらに、収集した競合の **H2 見出しを意味でクラスタリング**（`messages.parse` で構造化）し、
次の2軸に集計して分析に注入します:

- **必須テーマ**（上位の大半が扱う＝網羅性のために外せない）
- **手薄テーマ**（一部しか扱わない＝独自性・差別化の好機）

これにより「カバーすべきだが上位が手薄なテーマ」を炙り出し、**網羅性と独自性を同時に**
引き上げます。表記揺れのある日本語見出しも LLM が同一テーマとして束ねます。

さらに **必須テーマは[監査]フェーズにも渡され**、本文での網羅を突合します。取りこぼしは
重大な欠陥として減点され、不足テーマ名が改善点に明記されてリライトへ戻るため、
ループが速く確実に収束します（分析→監査の閉ループ）。

**どちらのキーも未設定なら競合分析は自動でスキップ**され、LLM の内部知識のみで
構成を設計します（従来動作）。個々のページ取得に失敗してもパイプラインは止まりません。
競合データはリライトループ間で**キャッシュ**し再取得しません。取得結果は「模倣」ではなく
**差別化の材料**として分析に渡しています。
