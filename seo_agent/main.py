"""
WordPress SEO Agent System
自動キーワード分析 → 記事構成 → 記事生成 → 校正 → 監査 → WordPress投稿
"""

import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import anthropic
import requests
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
# ロガー設定
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("seo_agent.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("seo_agent")

# ──────────────────────────────────────────────
# 定数
# ──────────────────────────────────────────────
MAX_LOOPS = 3
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

WP_URL = os.getenv("WP_URL", "")          # 例: https://example.com
WP_USER = os.getenv("WP_USER", "")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")

# API呼び出しのリトライ設定
API_MAX_RETRIES = 4
API_BACKOFF_BASE = 2.0            # 秒（2, 4, 8, 16... と指数的に増加）

# 合格ライン（監査LLMと共有する閾値）
AUDIT_PASS_SCORE = 75

# 記事品質の客観基準（決定論的チェック / 監査LLMにも実数として渡す）
MIN_WORD_COUNT = 2000            # 本文の最低文字数（タグ除く）
MAX_WORD_COUNT = 6000            # 冗長すぎる記事を防ぐ上限
KEYWORD_DENSITY_MIN = 0.005      # キーワード密度の下限（0.5%）
KEYWORD_DENSITY_MAX = 0.030      # キーワード密度の上限（3.0%／過剰最適化防止）
MIN_H2_COUNT = 3                 # 最低H2数

# ──────────────────────────────────────────────
# 共有採点基準（RUBRIC）
# 執筆フェーズと監査フェーズの両方に注入し、
# 「ライターが採点表を知った上で書く」状態を作る。
# ここを一元管理することで、両者の評価軸が永久にズレない。
# ──────────────────────────────────────────────
RUBRIC = """【SEO品質 採点基準（各20点 × 5項目 = 100点満点 / 75点で合格）】

1. 検索意図の充足度（20点）
   - 顕在ニーズに直接答えているか
   - 潜在ニーズ（読者が言語化できていない不安・疑問）まで先回りして解消しているか

2. コンテンツの網羅性（20点）
   - 競合上位が扱うトピックを漏れなくカバーしているか
   - かつ、競合にない独自の切り口・一次情報があるか

3. 日本語品質（20点）
   - 自然で読みやすい丁寧語。重複・冗長・助詞ミスがない
   - 1段落3〜5行、結論ファースト

4. E-E-A-T（20点）
   - Experience（実体験）・Expertise（専門性）が文章から伝わるか
   - 根拠・出典・具体例で信頼性（Trust）を担保しているか

5. HTML/技術的SEO（20点）
   - 見出し階層（H2/H3）が論理的
   - 箇条書き（ul/ol）・表（table）がスマホ可読性に貢献している
   - キーワード密度が適切（0.5〜3.0%）で過剰最適化がない"""

# ──────────────────────────────────────────────
# データクラス
# ──────────────────────────────────────────────

@dataclass
class AnalysisResult:
    """キーワード分析結果"""
    keyword: str
    search_intent: str                  # 検索意図の要約
    explicit_needs: list[str]           # 顕在ニーズ
    latent_needs: list[str]             # 潜在ニーズ
    eeat_angle: str                     # E-E-A-T上の差別化ポイント
    target_persona: str                 # ターゲット読者像
    competitor_insights: list[str] = field(default_factory=list)


@dataclass
class H2Section:
    h2: str
    h3s: list[str]
    purpose: str                        # このセクションが答える読者の問い


@dataclass
class StructureResult:
    """記事構成案"""
    title: str
    meta_description: str              # 120〜160字
    h2_sections: list[H2Section]
    affiliate_contexts: list[str]      # 自然なアフィリエイトリンク挿入箇所の説明
    tags: list[str]
    categories: list[str]


@dataclass
class ContentMetrics:
    """記事HTMLから決定論的に算出した客観指標（雰囲気でなく事実で採点するため）"""
    char_count: int                    # タグを除いた本文文字数
    keyword_count: int                 # キーワード出現回数
    keyword_density: float             # キーワード密度（0.0〜1.0）
    h2_count: int
    h3_count: int
    has_list: bool                     # ul/ol を含むか
    has_table: bool                    # table を含むか
    affiliate_marks: int               # アフィリエイトリンクマーカー数
    unbalanced_tags: list[str]         # 開閉が一致しないタグ（HTML健全性）

    def hard_failures(self, keyword: str) -> list[str]:
        """合否以前の客観的な不備（機械的に判定可能な致命傷）を列挙する"""
        problems: list[str] = []
        if self.char_count < MIN_WORD_COUNT:
            problems.append(
                f"本文が短すぎます（{self.char_count}字 < 最低{MIN_WORD_COUNT}字）")
        if self.char_count > MAX_WORD_COUNT:
            problems.append(
                f"本文が冗長です（{self.char_count}字 > 上限{MAX_WORD_COUNT}字）")
        if self.keyword_density < KEYWORD_DENSITY_MIN:
            problems.append(
                f"キーワード「{keyword}」の密度が低すぎます"
                f"（{self.keyword_density:.2%} < {KEYWORD_DENSITY_MIN:.1%}）")
        if self.keyword_density > KEYWORD_DENSITY_MAX:
            problems.append(
                f"キーワード「{keyword}」が過剰最適化です"
                f"（{self.keyword_density:.2%} > {KEYWORD_DENSITY_MAX:.1%}）")
        if self.h2_count < MIN_H2_COUNT:
            problems.append(f"H2見出しが不足（{self.h2_count}個 < 最低{MIN_H2_COUNT}個）")
        if not (self.has_list or self.has_table):
            problems.append("箇条書き(ul/ol)も表(table)も無く、スマホ可読性が低い")
        if self.unbalanced_tags:
            problems.append(
                f"HTMLタグの開閉不一致: {', '.join(self.unbalanced_tags)}")
        return problems


@dataclass
class AuditResult:
    """監査結果（Structured Output）"""
    pass_audit: bool
    reason: str
    score: int                         # 0〜100
    improvements: list[str]


@dataclass
class ArticleBundle:
    """記事一式"""
    structure: StructureResult
    html_content: str
    audit: Optional[AuditResult] = None


# ──────────────────────────────────────────────
# Anthropic クライアント
# ──────────────────────────────────────────────

def _get_client() -> anthropic.Anthropic:
    if not ANTHROPIC_API_KEY:
        raise EnvironmentError("ANTHROPIC_API_KEY が .env に設定されていません")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _messages_create_with_retry(client: anthropic.Anthropic, **kwargs):
    """
    client.messages.create を指数バックオフ付きでラップする。
    一時的な過負荷(529)・レート制限(429)・接続エラーを自動リトライし、
    自律ループ全体がワンショットのAPI失敗で停止しないようにする。
    """
    last_exc: Optional[Exception] = None
    for attempt in range(1, API_MAX_RETRIES + 1):
        try:
            return client.messages.create(**kwargs)
        except (anthropic.APIStatusError, anthropic.APIConnectionError, anthropic.RateLimitError) as e:
            last_exc = e
            # 4xx（リクエスト不正）はリトライしても無駄なので即時中断（429除く）
            status = getattr(e, "status_code", None)
            if status is not None and 400 <= status < 500 and status != 429:
                logger.error("API呼び出しエラー（リトライ不可 status=%s）: %s", status, e)
                raise
            if attempt == API_MAX_RETRIES:
                break
            wait = API_BACKOFF_BASE ** attempt
            logger.warning("API呼び出し失敗 (試行 %d/%d, status=%s) — %.0f秒後に再試行: %s",
                           attempt, API_MAX_RETRIES, status, wait, e)
            time.sleep(wait)
    logger.error("API呼び出しが %d 回のリトライ後も失敗しました", API_MAX_RETRIES)
    raise last_exc  # type: ignore[misc]


def call_claude(system: str, user: str, max_tokens: int = 4096) -> str:
    """通常のClaude呼び出し（テキスト返却）"""
    client = _get_client()
    logger.debug("Claude呼び出し開始 (model=%s, max_tokens=%d)", CLAUDE_MODEL, max_tokens)
    message = _messages_create_with_retry(
        client,
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = message.content[0].text
    logger.debug("Claude応答受信 (入力=%d, 出力=%d tokens)",
                 message.usage.input_tokens, message.usage.output_tokens)
    return text


def call_claude_json(system: str, user: str, schema: dict, max_tokens: int = 2048) -> dict:
    """
    tool_use を使い、スキーマ準拠のJSONをClaude から受け取る。
    Anthropicの tool_use = Structured Outputs 相当。
    """
    client = _get_client()
    tool = {
        "name": "structured_output",
        "description": "スキーマに従ったJSON出力",
        "input_schema": schema,
    }
    message = _messages_create_with_retry(
        client,
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        tools=[tool],
        tool_choice={"type": "tool", "name": "structured_output"},
        messages=[{"role": "user", "content": user}],
    )
    for block in message.content:
        if block.type == "tool_use":
            return block.input  # type: ignore[return-value]
    raise ValueError("tool_use ブロックが見つかりませんでした")


# ──────────────────────────────────────────────
# フェーズ 0: 競合分析（将来拡張用スタブ）
# ──────────────────────────────────────────────

def analyze_competitors(keyword: str) -> list[str]:
    """
    競合記事を分析してインサイトリストを返す。
    将来的にはSerpAPI / DataForSEO / Google Search API 等と連携する。
    現在はスタブとしてモック値を返す。
    """
    logger.info("[競合分析] キーワード: %s (現在はスタブ)", keyword)
    # TODO: 外部SEO APIを呼び出し、上位記事の見出し・文字数・被リンクを取得
    return [
        f"上位記事の平均文字数: 約3,000字（推定）",
        f"共通のH2トピック: {keyword}の基本・選び方・おすすめ比較",
        "差別化余地: 実体験ベースのE-E-Aコンテンツが少ない",
    ]


# ──────────────────────────────────────────────
# フェーズ 1: キーワード分析
# ──────────────────────────────────────────────

def analyze_keyword(keyword: str, feedback: Optional[str] = None) -> AnalysisResult:
    """
    検索意図・顕在/潜在ニーズ・E-E-A-T角度を分析する。
    feedback が与えられた場合は前回の監査フィードバックを考慮する。
    """
    logger.info("[分析] キーワード分析開始: %s", keyword)
    competitor_insights = analyze_competitors(keyword)

    feedback_section = (
        f"\n\n## 前回の監査フィードバック（必ず反映すること）\n{feedback}"
        if feedback else ""
    )

    system = """あなたは日本のSEOコンサルタントです。
与えられたキーワードに対して、Googleの検索意図を深く分析してください。
特に以下を意識してください：
- 顕在ニーズ（ユーザーが明示的に求めていること）
- 潜在ニーズ（ユーザーが気づいていないが満たされると満足するニーズ）
- E-E-A-T（Experience・Expertise・Authoritativeness・Trustworthiness）の観点での差別化
- スマホユーザーが多い日本市場への適応"""

    user = f"""## 分析対象キーワード
{keyword}

## 競合インサイト
{chr(10).join(f'- {i}' for i in competitor_insights)}{feedback_section}

## 出力形式
以下のフォーマットでJSON出力してください（tool_useを使用します）"""

    schema = {
        "type": "object",
        "required": ["search_intent", "explicit_needs", "latent_needs",
                     "eeat_angle", "target_persona"],
        "properties": {
            "search_intent": {"type": "string", "description": "検索意図の一文要約"},
            "explicit_needs": {
                "type": "array", "items": {"type": "string"},
                "description": "顕在ニーズ（3〜5個）"
            },
            "latent_needs": {
                "type": "array", "items": {"type": "string"},
                "description": "潜在ニーズ（3〜5個）"
            },
            "eeat_angle": {"type": "string", "description": "E-E-A-T上の差別化ポイント"},
            "target_persona": {"type": "string", "description": "ターゲット読者像（具体的に）"},
        },
    }

    raw = call_claude_json(system, user, schema)
    result = AnalysisResult(
        keyword=keyword,
        search_intent=raw["search_intent"],
        explicit_needs=raw["explicit_needs"],
        latent_needs=raw["latent_needs"],
        eeat_angle=raw["eeat_angle"],
        target_persona=raw["target_persona"],
        competitor_insights=competitor_insights,
    )
    logger.info("[分析] 完了 - 意図: %s", result.search_intent)
    return result


# ──────────────────────────────────────────────
# フェーズ 2: 記事構成設計
# ──────────────────────────────────────────────

def design_structure(analysis: AnalysisResult, feedback: Optional[str] = None) -> StructureResult:
    """
    分析結果を元に、H2/H3構成・タイトル・メタディスクリプションを設計する。
    feedback がある場合は前回構成の問題点を改善する。
    """
    logger.info("[構成] 記事構成設計開始")

    feedback_section = (
        f"\n\n## 改善必須事項\n{feedback}\n上記の問題点を必ず解決した構成にしてください。"
        if feedback else ""
    )

    system = """あなたは日本の一流SEOライターかつ編集長です。
検索意図を完全に網羅し、かつ読者が最後まで読み続けたくなる記事構成を設計します。
原則：
1. タイトルはキーワードを含み32字以内、クリック欲求を高めること
2. H2は5〜8個、各H2に1〜3個のH3を設ける
3. 「まとめ」セクションは必ず最後に配置
4. アフィリエイトリンクを不自然なく挿入できる文脈を3箇所以上設ける
5. meta_descriptionは120〜160字で検索意図を満たすことを示す"""

    user = f"""## キーワード
{analysis.keyword}

## 検索意図
{analysis.search_intent}

## 顕在ニーズ
{chr(10).join(f'- {n}' for n in analysis.explicit_needs)}

## 潜在ニーズ
{chr(10).join(f'- {n}' for n in analysis.latent_needs)}

## E-E-A-T差別化ポイント
{analysis.eeat_angle}

## ターゲット読者
{analysis.target_persona}

## 競合インサイト
{chr(10).join(f'- {i}' for i in analysis.competitor_insights)}{feedback_section}"""

    schema = {
        "type": "object",
        "required": ["title", "meta_description", "h2_sections",
                     "affiliate_contexts", "tags", "categories"],
        "properties": {
            "title": {"type": "string"},
            "meta_description": {"type": "string"},
            "h2_sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["h2", "h3s", "purpose"],
                    "properties": {
                        "h2": {"type": "string"},
                        "h3s": {"type": "array", "items": {"type": "string"}},
                        "purpose": {"type": "string"},
                    },
                },
            },
            "affiliate_contexts": {
                "type": "array", "items": {"type": "string"},
                "description": "アフィリエイトリンクを挿入するセクションと理由"
            },
            "tags": {"type": "array", "items": {"type": "string"}},
            "categories": {"type": "array", "items": {"type": "string"}},
        },
    }

    raw = call_claude_json(system, user, schema, max_tokens=3000)
    h2_sections = [
        H2Section(h2=s["h2"], h3s=s["h3s"], purpose=s["purpose"])
        for s in raw["h2_sections"]
    ]
    result = StructureResult(
        title=raw["title"],
        meta_description=raw["meta_description"],
        h2_sections=h2_sections,
        affiliate_contexts=raw["affiliate_contexts"],
        tags=raw["tags"],
        categories=raw["categories"],
    )
    logger.info("[構成] 完了 - タイトル: %s (%d H2)", result.title, len(result.h2_sections))
    return result


# ──────────────────────────────────────────────
# フェーズ 3: 記事本文生成
# ──────────────────────────────────────────────

def create_article(structure: StructureResult, analysis: AnalysisResult) -> str:
    """
    構成案を元にHTML形式の本文を生成する。
    スマホ閲読を意識し、ul/ol/tableを適切に使用する。
    """
    logger.info("[執筆] 記事本文生成開始 - タイトル: %s", structure.title)

    # H2/H3構成をプロンプト用テキストに変換
    outline_text = ""
    for i, section in enumerate(structure.h2_sections, 1):
        outline_text += f"\n### H2-{i}: {section.h2}\n目的: {section.purpose}\n"
        for j, h3 in enumerate(section.h3s, 1):
            outline_text += f"  - H3-{i}-{j}: {h3}\n"

    affiliate_hints = "\n".join(f"- {ctx}" for ctx in structure.affiliate_contexts)

    system = """あなたは日本のアフィリエイトSEOライターです。
以下のルールに従い、HTML形式で記事本文を執筆してください。

【HTML出力ルール】
- 本文全体をHTMLタグで記述する（<h2>, <h3>, <p>, <ul>, <ol>, <table>等）
- <html>, <head>, <body>タグは不要。本文コンテンツのみ
- スマホ画面（幅375px想定）での読みやすさを最優先
- 1段落は3〜5行を目安に短くまとめる
- 箇条書き（<ul><li>）はメリット・手順・比較に積極活用
- 表（<table>）は比較や仕様まとめに使用（headersにはscope属性を付与）
- アフィリエイトリンクは <!-- AFFILIATE_LINK: [商品名] --> というHTMLコメントで挿入位置をマークする
- キーワードは自然な密度（1〜2%）で本文に含める
- リード文（最初の段落）で読者の悩みに共感し、この記事で解決できると示す
- まとめセクションでキーワードを含む締めくくりを書く

【文章ルール】
- 日本語は丁寧語（〜です/〜ます）で統一
- 回りくどい表現を避け、結論ファースト
- 「〜してみてください」「〜でしょう」等のぼかし表現は最小限に

【重要】この記事は以下の基準で採点されます。最初から満点を狙って書いてください：
""" + RUBRIC

    user = f"""## 記事タイトル
{structure.title}

## ターゲットキーワード
{analysis.keyword}

## ターゲット読者
{analysis.target_persona}

## 記事の構成（この構成に完全に従って執筆してください）
{outline_text}

## アフィリエイトリンク挿入箇所のガイド
{affiliate_hints}

## 追加指示
- 全体の文字数は3,000〜4,000字程度を目標にする
- E-E-A-T観点: {analysis.eeat_angle}
- 記事の最後は「まとめ」H2で締める

それでは、上記構成に従ってHTML本文を執筆してください。"""

    html_content = call_claude(system, user, max_tokens=6000)

    # コードブロックのマークダウンが混入した場合は除去
    html_content = re.sub(r"^```html\s*", "", html_content.strip(), flags=re.IGNORECASE)
    html_content = re.sub(r"\s*```$", "", html_content.strip())

    logger.info("[執筆] 完了 - 文字数（概算）: %d字", len(html_content))
    return html_content


# ──────────────────────────────────────────────
# フェーズ 4: 校正
# ──────────────────────────────────────────────

def proofread_article(html_content: str, analysis: AnalysisResult) -> str:
    """
    生成された記事をSEO・日本語・HTMLの観点で校正し、改善版を返す。
    """
    logger.info("[校正] 記事校正開始")

    system = """あなたは日本語校正のプロフェッショナルかつSEOエキスパートです。
提供されたHTML記事を以下の観点で精密に校正し、修正済みHTMLを返してください。

【校正チェックリスト】
1. 日本語の自然さ: 不自然な表現・重複・助詞ミスの修正
2. キーワード密度: ターゲットキーワードが1〜2%の適切な密度か確認し調整
3. HTMLの正確さ: タグの閉じ忘れ・ネスト誤りの修正
4. 読みやすさ: 長すぎる文の分割、段落の調整
5. 見出しの改善: H2/H3がSEOと読者の興味を同時に満たしているか
6. CTAの自然さ: アフィリエイトリンクマーク付近の文脈が購買意欲を高めているか

【出力】修正済みのHTML本文のみ返してください（説明不要）"""

    user = f"""## ターゲットキーワード
{analysis.keyword}

## 校正対象HTML
{html_content}"""

    proofread = call_claude(system, user, max_tokens=6000)
    proofread = re.sub(r"^```html\s*", "", proofread.strip(), flags=re.IGNORECASE)
    proofread = re.sub(r"\s*```$", "", proofread.strip())

    logger.info("[校正] 完了")
    return proofread


# ──────────────────────────────────────────────
# 決定論的メトリクス算出（雰囲気採点の排除）
# ──────────────────────────────────────────────

def compute_content_metrics(html_content: str, keyword: str) -> ContentMetrics:
    """
    記事HTMLから機械的に算出できる客観指標を計算する。
    LLM監査の前にこれを通すことで、「実数」に基づいた採点が可能になる。
    """
    # タグを除いたプレーンテキスト（文字数・密度の算出用）
    plain = re.sub(r"<[^>]+>", "", html_content)
    plain = re.sub(r"<!--.*?-->", "", plain, flags=re.DOTALL)
    plain = re.sub(r"\s+", "", plain)               # 日本語は空白で単語分割できないため空白除去
    char_count = len(plain)

    keyword_count = plain.count(keyword.replace(" ", "")) if keyword else 0
    # キーワード密度 = (キーワード文字数 × 出現回数) / 全文字数
    kw_len = len(keyword.replace(" ", "")) or 1
    keyword_density = (keyword_count * kw_len / char_count) if char_count else 0.0

    h2_count = len(re.findall(r"<h2\b", html_content, re.IGNORECASE))
    h3_count = len(re.findall(r"<h3\b", html_content, re.IGNORECASE))
    has_list = bool(re.search(r"<(ul|ol)\b", html_content, re.IGNORECASE))
    has_table = bool(re.search(r"<table\b", html_content, re.IGNORECASE))
    affiliate_marks = len(re.findall(r"AFFILIATE_LINK", html_content))

    # 主要ブロックタグの開閉バランスをチェック（簡易HTML健全性）
    unbalanced: list[str] = []
    for tag in ("h2", "h3", "p", "ul", "ol", "li", "table", "tr", "td", "th"):
        opens = len(re.findall(rf"<{tag}\b", html_content, re.IGNORECASE))
        closes = len(re.findall(rf"</{tag}\s*>", html_content, re.IGNORECASE))
        if opens != closes:
            unbalanced.append(f"{tag}(開{opens}/閉{closes})")

    metrics = ContentMetrics(
        char_count=char_count,
        keyword_count=keyword_count,
        keyword_density=keyword_density,
        h2_count=h2_count,
        h3_count=h3_count,
        has_list=has_list,
        has_table=has_table,
        affiliate_marks=affiliate_marks,
        unbalanced_tags=unbalanced,
    )
    logger.info(
        "[メトリクス] %d字 / KW出現%d回(密度%.2f%%) / H2:%d H3:%d / list:%s table:%s / アフィリ:%d箇所",
        char_count, keyword_count, keyword_density * 100,
        h2_count, h3_count, has_list, has_table, affiliate_marks,
    )
    if metrics.unbalanced_tags:
        logger.warning("[メトリクス] HTMLタグ開閉不一致: %s", ", ".join(metrics.unbalanced_tags))
    return metrics


# ──────────────────────────────────────────────
# フェーズ 5: SEO監査（Structured Output）
# ──────────────────────────────────────────────

def audit_article(
    html_content: str,
    structure: StructureResult,
    analysis: AnalysisResult,
    metrics: ContentMetrics,
) -> AuditResult:
    """
    記事をSEO観点で監査し、合否・スコア・改善点をJSON形式で返す。
    tool_use を使用してパース可能なJSONを保証する。
    合格基準: 機械的な致命傷がなく、かつ score >= AUDIT_PASS_SCORE。

    決定論的メトリクス(metrics)で計測した「実数」を監査LLMに渡し、
    雰囲気でなく事実に基づいた採点をさせる。さらに hard_failures があれば
    LLMの判定に関わらず不合格に倒す（過大評価を機械でガードする）。
    """
    logger.info("[監査] SEO監査開始")

    hard_failures = metrics.hard_failures(analysis.keyword)

    system = f"""あなたは厳格なSEO監査エキスパートです。
記事をGoogleの品質ガイドラインに照らし、以下の採点基準で厳密に採点します。
{AUDIT_PASS_SCORE}点以上で合格（pass: true）、それ未満は不合格（pass: false）とします。
採点は甘くせず、日本のSEO競合環境を考慮した厳格な基準で行ってください。
提示される「客観メトリクス（実測値）」を必ず採点根拠に組み込んでください。

{RUBRIC}"""

    metrics_block = f"""## 客観メトリクス（機械計測した実測値・採点に必ず反映すること）
- 本文文字数: {metrics.char_count}字（推奨 {MIN_WORD_COUNT}〜{MAX_WORD_COUNT}字）
- キーワード出現: {metrics.keyword_count}回 / 密度 {metrics.keyword_density:.2%}（推奨 {KEYWORD_DENSITY_MIN:.1%}〜{KEYWORD_DENSITY_MAX:.1%}）
- 見出し: H2 {metrics.h2_count}個 / H3 {metrics.h3_count}個
- 箇条書き(ul/ol): {'あり' if metrics.has_list else 'なし'} / 表(table): {'あり' if metrics.has_table else 'なし'}
- アフィリエイトリンク挿入箇所: {metrics.affiliate_marks}箇所
- HTMLタグ開閉不一致: {', '.join(metrics.unbalanced_tags) if metrics.unbalanced_tags else 'なし（健全）'}"""

    hard_block = (
        "\n\n## 機械検出された致命的不備（これらは減点必須）\n"
        + "\n".join(f"- {p}" for p in hard_failures)
        if hard_failures else ""
    )

    user = f"""## 評価対象
- キーワード: {analysis.keyword}
- 記事タイトル: {structure.title}
- メタディスクリプション: {structure.meta_description}

{metrics_block}{hard_block}

## 評価対象HTML
{html_content[:8000]}{"...(以下省略)" if len(html_content) > 8000 else ""}"""

    schema = {
        "type": "object",
        "required": ["pass_audit", "reason", "score", "improvements"],
        "properties": {
            "pass_audit": {
                "type": "boolean",
                "description": "true=合格(75点以上), false=不合格"
            },
            "reason": {
                "type": "string",
                "description": "合否判定の主要な理由（1〜2文）"
            },
            "score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "SEOスコア（0〜100）"
            },
            "improvements": {
                "type": "array",
                "items": {"type": "string"},
                "description": "不合格の場合の具体的な改善指示（合格時は空配列）"
            },
        },
    }

    raw = call_claude_json(system, user, schema)
    llm_pass = bool(raw["pass_audit"])
    score = int(raw["score"])
    reason = raw["reason"]
    improvements = list(raw.get("improvements", []))

    # 機械ガード: 致命的不備があればLLMの判定に関わらず不合格に倒す。
    # スコアの整合性（pass=true なのに閾値未満）も機械側で正す。
    final_pass = llm_pass and not hard_failures and score >= AUDIT_PASS_SCORE
    if hard_failures:
        # LLMが見落とした客観的不備を改善指示の先頭に必ず含める
        improvements = hard_failures + [i for i in improvements if i not in hard_failures]
        if llm_pass:
            reason = f"機械検出の致命的不備により不合格に補正。{reason}"
            logger.warning("[監査] LLMは合格判定だが機械ガードで不合格に補正（致命的不備%d件）",
                           len(hard_failures))

    result = AuditResult(
        pass_audit=final_pass,
        reason=reason,
        score=score,
        improvements=improvements,
    )
    status = "合格 ✓" if result.pass_audit else "不合格 ✗"
    logger.info("[監査] %s - スコア: %d/100 - %s", status, result.score, result.reason)
    return result


# ──────────────────────────────────────────────
# WordPress 投稿
# ──────────────────────────────────────────────

def post_to_wordpress(
    title: str,
    html_content: str,
    tags: list[str],
    categories: list[str],
    status: str = "draft",
) -> dict:
    """
    WordPress REST API を使い記事を投稿する（デフォルト: 下書き）。
    認証にはアプリケーションパスワードを使用。

    Returns:
        {"success": bool, "post_id": int|None, "post_url": str|None, "error": str|None}
    """
    logger.info("[WP投稿] 開始 - タイトル: %s", title)

    if not all([WP_URL, WP_USER, WP_APP_PASSWORD]):
        logger.error("[WP投稿] WordPress接続情報が .env に設定されていません")
        return {"success": False, "post_id": None, "post_url": None,
                "error": "WordPress接続情報未設定"}

    # タグとカテゴリのIDを取得または作成
    tag_ids = _get_or_create_wp_terms(tags, "tags")
    category_ids = _get_or_create_wp_terms(categories, "categories")

    api_url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/posts"
    auth = (WP_USER, WP_APP_PASSWORD)
    payload = {
        "title": title,
        "content": html_content,
        "status": status,
        "tags": tag_ids,
        "categories": category_ids,
    }

    try:
        resp = requests.post(api_url, json=payload, auth=auth, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        post_id = data.get("id")
        post_url = data.get("link", "")
        logger.info("[WP投稿] 成功 - 投稿ID: %d URL: %s", post_id, post_url)
        return {"success": True, "post_id": post_id, "post_url": post_url, "error": None}
    except requests.HTTPError as e:
        error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        logger.error("[WP投稿] 失敗 - %s", error_msg)
        return {"success": False, "post_id": None, "post_url": None, "error": error_msg}
    except requests.RequestException as e:
        logger.error("[WP投稿] ネットワークエラー - %s", str(e))
        return {"success": False, "post_id": None, "post_url": None, "error": str(e)}


def _get_or_create_wp_terms(names: list[str], taxonomy: str) -> list[int]:
    """
    タグまたはカテゴリの名前リストからWordPress上のIDリストを返す。
    存在しない場合は新規作成する。
    taxonomy: "tags" または "categories"
    """
    if not names or not all([WP_URL, WP_USER, WP_APP_PASSWORD]):
        return []

    endpoint_map = {"tags": "tags", "categories": "categories"}
    base_url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/{endpoint_map[taxonomy]}"
    auth = (WP_USER, WP_APP_PASSWORD)
    ids = []

    for name in names:
        try:
            # 既存検索
            resp = requests.get(base_url, params={"search": name}, auth=auth, timeout=10)
            resp.raise_for_status()
            results = resp.json()
            existing = [r for r in results if r["name"].lower() == name.lower()]
            if existing:
                ids.append(existing[0]["id"])
            else:
                # 新規作成
                create_resp = requests.post(
                    base_url, json={"name": name}, auth=auth, timeout=10
                )
                create_resp.raise_for_status()
                ids.append(create_resp.json()["id"])
        except requests.RequestException as e:
            logger.warning("[WP] タームID取得失敗 (%s: %s) - スキップ", taxonomy, name)

    return ids


# ──────────────────────────────────────────────
# メインループ
# ──────────────────────────────────────────────

def run_seo_agent(keyword: str) -> None:
    """
    SEOエージェントのメインループ。
    最大 MAX_LOOPS 回、分析→構成→執筆→校正→監査を繰り返す。
    合格で WordPress 下書き投稿、3回不合格でエラー出力して終了。
    """
    logger.info("=" * 60)
    logger.info("SEOエージェント起動 - キーワード: 「%s」", keyword)
    logger.info("最大ループ回数: %d", MAX_LOOPS)
    logger.info("=" * 60)

    feedback: Optional[str] = None
    last_bundle: Optional[ArticleBundle] = None

    for attempt in range(1, MAX_LOOPS + 1):
        logger.info("")
        logger.info("━━━ ループ %d/%d ━━━", attempt, MAX_LOOPS)

        # ── フェーズ 1: 分析 ──
        analysis = analyze_keyword(keyword, feedback=feedback)

        # ── フェーズ 2: 構成 ──
        structure = design_structure(analysis, feedback=feedback)

        # ── フェーズ 3: 執筆 ──
        html_content = create_article(structure, analysis)

        # ── フェーズ 4: 校正 ──
        html_content = proofread_article(html_content, analysis)

        # ── フェーズ 5: 監査（決定論的メトリクス + LLM採点 + 機械ガード）──
        metrics = compute_content_metrics(html_content, analysis.keyword)
        audit = audit_article(html_content, structure, analysis, metrics)
        last_bundle = ArticleBundle(
            structure=structure,
            html_content=html_content,
            audit=audit,
        )

        if audit.pass_audit:
            logger.info("")
            logger.info("✅ 監査合格！(スコア: %d/100) WordPress へ投稿します", audit.score)

            wp_result = post_to_wordpress(
                title=structure.title,
                html_content=html_content,
                tags=structure.tags,
                categories=structure.categories,
                status="draft",
            )

            if wp_result["success"]:
                logger.info("")
                logger.info("🎉 投稿完了!")
                logger.info("  投稿ID  : %s", wp_result["post_id"])
                logger.info("  URL     : %s", wp_result["post_url"])
                logger.info("  タイトル: %s", structure.title)
                logger.info("  スコア  : %d/100", audit.score)
            else:
                logger.error("WordPress 投稿失敗: %s", wp_result["error"])
                logger.info("生成記事（手動投稿用）を seo_output.html に保存します")
                _save_output(structure.title, html_content)
            return

        # 不合格: フィードバックを次ループに渡す
        feedback_lines = [audit.reason] + audit.improvements
        feedback = "\n".join(f"- {line}" for line in feedback_lines)
        logger.info("")
        logger.info("❌ 監査不合格 (スコア: %d/100)", audit.score)
        logger.info("フィードバック:")
        for line in feedback_lines:
            logger.info("  • %s", line)

        if attempt < MAX_LOOPS:
            logger.info("フィードバックを反映して再挑戦します...")

    # 3回全て不合格
    logger.error("")
    logger.error("=" * 60)
    logger.error("⛔ %d回のループを経ても合格できませんでした", MAX_LOOPS)
    logger.error("最終スコア: %d/100", last_bundle.audit.score if last_bundle else 0)
    logger.error("最終フィードバック: %s", feedback)
    logger.error("=" * 60)

    if last_bundle:
        output_path = _save_output(last_bundle.structure.title, last_bundle.html_content)
        logger.error("最終稿を %s に保存しました（手動確認・修正後に投稿してください）", output_path)


def _save_output(title: str, html_content: str) -> str:
    """記事HTMLをファイルに保存し、パスを返す"""
    safe_title = re.sub(r'[\\/*?:"<>|]', "_", title)[:50]
    output_path = f"seo_output_{safe_title}.html"
    full_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
</head>
<body>
<h1>{title}</h1>
{html_content}
</body>
</html>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_html)
    return output_path


# ──────────────────────────────────────────────
# エントリーポイント
# ──────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使い方: python main.py \"ターゲットキーワード\"")
        print('例:     python main.py "ふるさと納税 おすすめ 2024"')
        sys.exit(1)

    target_keyword = " ".join(sys.argv[1:])
    run_seo_agent(target_keyword)
