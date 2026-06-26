"""
WordPress SEO エージェント — 自律記事生成パイプライン
=====================================================

狙うキーワードを 1 つ受け取り、次のサイクルを最大 3 回まで自律実行する。

    [分析] → [構成] → [作成] → [校正] → [監査]

監査が合格（pass=True かつ score >= しきい値）すれば WordPress に
「下書き（draft）」として自動投稿して終了する。不合格なら監査フィードバックを
保持したまま [分析] に戻り、リライトループを回す。3 回回しても不合格なら、
エラー内容とそこまでの原稿を出力して停止する（無限ループ防止）。

LLM は Anthropic の Claude（公式 SDK）を使用する。監査フェーズは
Structured Outputs（messages.parse + Pydantic）で必ずパース可能な JSON を返す。

使い方:
    python main.py "ふるさと納税 おすすめ 食品"
    python main.py "ふるさと納税 おすすめ 食品" --dry-run   # WordPress 投稿せず原稿だけ確認

設計の前提:
- API キー・WP 認証情報はコードに直書きせず .env から読み込む（python-dotenv）。
- 競合分析は将来 API 連携できるよう独立関数として分離している。
- 各関数に型ヒントとログ出力を付与している。
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

import anthropic
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# ログ設定
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("seo_agent")


# -----------------------------------------------------------------------------
# 設定（.env から読み込み）
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class Settings:
    """環境変数から組み立てる実行設定。"""

    anthropic_api_key: str
    model: str
    pass_score: int
    max_loops: int

    wordpress_url: str
    wordpress_username: str
    wordpress_app_password: str
    default_categories: list[str] = field(default_factory=list)
    default_tags: list[str] = field(default_factory=list)

    # 競合分析（検索プロバイダ）。キー未設定なら自動的に無効化される。
    search_provider: str = "auto"  # auto | serpapi | google_cse | none
    serpapi_api_key: str = ""
    google_cse_api_key: str = ""
    google_cse_id: str = ""
    competitor_top_n: int = 5

    @classmethod
    def from_env(cls) -> "Settings":
        """`.env` を読み込み、必須項目を検証して Settings を返す。"""
        load_dotenv()

        def _split(name: str) -> list[str]:
            raw = os.getenv(name, "") or ""
            return [item.strip() for item in raw.split(",") if item.strip()]

        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY が .env に設定されていません。")

        wp_url = os.getenv("WORDPRESS_URL", "").strip().rstrip("/")
        wp_user = os.getenv("WORDPRESS_USERNAME", "").strip()
        # アプリケーションパスワードは表示時の空白をそのまま貼ってよいよう除去する。
        wp_pass = (os.getenv("WORDPRESS_APP_PASSWORD", "") or "").replace(" ", "").strip()

        settings = cls(
            anthropic_api_key=api_key,
            model=os.getenv("SEO_AGENT_MODEL", "claude-opus-4-8").strip() or "claude-opus-4-8",
            pass_score=int(os.getenv("SEO_AGENT_PASS_SCORE", "80") or "80"),
            max_loops=int(os.getenv("SEO_AGENT_MAX_LOOPS", "3") or "3"),
            wordpress_url=wp_url,
            wordpress_username=wp_user,
            wordpress_app_password=wp_pass,
            default_categories=_split("WORDPRESS_DEFAULT_CATEGORIES"),
            default_tags=_split("WORDPRESS_DEFAULT_TAGS"),
            search_provider=(os.getenv("SEO_SEARCH_PROVIDER", "auto").strip() or "auto"),
            serpapi_api_key=os.getenv("SERPAPI_API_KEY", "").strip(),
            google_cse_api_key=os.getenv("GOOGLE_CSE_API_KEY", "").strip(),
            google_cse_id=os.getenv("GOOGLE_CSE_ID", "").strip(),
            competitor_top_n=int(os.getenv("SEO_COMPETITOR_TOP_N", "5") or "5"),
        )
        logger.info(
            "設定読み込み完了 model=%s pass_score=%s max_loops=%s wp=%s",
            settings.model,
            settings.pass_score,
            settings.max_loops,
            settings.wordpress_url or "(未設定)",
        )
        return settings

    def require_wordpress(self) -> None:
        """WordPress 投稿に必要な設定が揃っているか検証する。"""
        missing = [
            name
            for name, value in (
                ("WORDPRESS_URL", self.wordpress_url),
                ("WORDPRESS_USERNAME", self.wordpress_username),
                ("WORDPRESS_APP_PASSWORD", self.wordpress_app_password),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "WordPress 投稿に必要な設定が不足しています: " + ", ".join(missing)
            )


# -----------------------------------------------------------------------------
# 構造化データモデル
# -----------------------------------------------------------------------------
class AuditResult(BaseModel):
    """監査フェーズが返す Structured Output。"""

    pass_: bool = Field(
        ...,
        alias="pass",
        description="合格なら true、不合格なら false",
    )
    score: int = Field(..., ge=0, le=100, description="SEO 総合スコア（0-100）")
    reason: str = Field(..., description="判定理由の要約")
    improvements: list[str] = Field(
        default_factory=list,
        description="不合格時の具体的な改善点（合格時は空でよい）",
    )

    model_config = {"populate_by_name": True}


class ThemeReport(BaseModel):
    """競合 H2 見出しを意味クラスタリングした網羅性レポート（Structured Output）。"""

    must_cover: list[str] = Field(
        default_factory=list,
        description="上位の大半が扱う必須テーマ（網羅性のために外せない）",
    )
    underserved: list[str] = Field(
        default_factory=list,
        description="一部しか扱わない／手薄なテーマ（独自性・差別化の好機）",
    )
    notes: str = Field(default="", description="網羅性・差別化に関する短い所見")


@dataclass
class Draft:
    """パイプライン内で受け渡す記事の状態。"""

    keyword: str
    title: str = ""
    body_html: str = ""
    tags: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    analysis: str = ""
    outline: str = ""
    # 競合分析の結果テキスト（ループ間で再取得しないようキャッシュ）
    competitor: str = ""
    # 直近の監査フィードバック（リライト時に各フェーズへ渡す）
    feedback: Optional[AuditResult] = None


# -----------------------------------------------------------------------------
# 競合分析（検索上位ページの構成を要約）
# -----------------------------------------------------------------------------
class CompetitorAnalyzer:
    """
    検索上位ページの構成（タイトル・H2/H3・概算文字量）を要約して返す。

    検索プロバイダは SerpAPI または Google Custom Search を、設定済みの方を
    自動採用する。どちらのキーも無ければ無効化され、空文字を返す
    （この場合パイプラインは LLM の内部知識のみで構成を設計する）。

    HTML の取得・解析は best-effort で、個々のページで失敗しても全体は止めない。
    過度な負荷をかけないため取得は上位 N 件のみ・タイムアウト付きで行う。
    """

    _UA = (
        "Mozilla/5.0 (compatible; SEOAgentBot/1.0; +https://example.com/bot)"
    )

    def __init__(self, settings: Settings, timeout: int = 15) -> None:
        self.settings = settings
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self._UA})

    def _provider(self) -> str:
        """有効な検索プロバイダ名を決定する（auto は設定済みキーから判定）。"""
        provider = self.settings.search_provider
        if provider == "serpapi":
            return "serpapi" if self.settings.serpapi_api_key else "none"
        if provider == "google_cse":
            return "google_cse" if (
                self.settings.google_cse_api_key and self.settings.google_cse_id
            ) else "none"
        if provider == "none":
            return "none"
        # auto: 使えるものを優先採用
        if self.settings.serpapi_api_key:
            return "serpapi"
        if self.settings.google_cse_api_key and self.settings.google_cse_id:
            return "google_cse"
        return "none"

    def _search_urls(self, keyword: str) -> list[str]:
        """検索プロバイダ経由で上位の自然検索 URL を取得する。"""
        provider = self._provider()
        try:
            if provider == "serpapi":
                resp = self.session.get(
                    "https://serpapi.com/search.json",
                    params={
                        "engine": "google",
                        "q": keyword,
                        "hl": "ja",
                        "gl": "jp",
                        "num": 10,
                        "api_key": self.settings.serpapi_api_key,
                    },
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                items = resp.json().get("organic_results", [])
                return [it["link"] for it in items if it.get("link")]
            if provider == "google_cse":
                resp = self.session.get(
                    "https://www.googleapis.com/customsearch/v1",
                    params={
                        "key": self.settings.google_cse_api_key,
                        "cx": self.settings.google_cse_id,
                        "q": keyword,
                        "hl": "ja",
                        "gl": "jp",
                        "num": 10,
                    },
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                items = resp.json().get("items", [])
                return [it["link"] for it in items if it.get("link")]
        except requests.RequestException as exc:
            logger.warning("検索プロバイダ呼び出しに失敗: %s", exc)
        return []

    def _page_structure(self, url: str) -> Optional[dict]:
        """1 ページの構成（title / H2 / H3数 / 概算文字量）を抽出する。"""
        from bs4 import BeautifulSoup  # 遅延 import（未インストールでも無効化で済む）

        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.debug("ページ取得失敗 %s: %s", url, exc)
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        title = soup.title.get_text(strip=True) if soup.title else url
        h2 = [h.get_text(strip=True) for h in soup.find_all("h2") if h.get_text(strip=True)]
        h3_count = len(soup.find_all("h3"))
        text_len = len(soup.get_text(separator=" ", strip=True))
        return {
            "url": url,
            "title": title,
            "h2": h2[:8],
            "h3_count": h3_count,
            "text_len": text_len,
        }

    def gather(self, keyword: str) -> list[dict]:
        """
        上位ページの構成（title / H2 / H3数 / 概算文字量）を収集して返す。

        Returns:
            ページ構成 dict のリスト（無効・取得失敗時は空リスト）。
        """
        provider = self._provider()
        if provider == "none":
            logger.info("競合分析: 検索プロバイダ未設定のためスキップ（内部知識で代替）")
            return []

        urls = self._search_urls(keyword)[: self.settings.competitor_top_n]
        if not urls:
            logger.info("競合分析: 上位 URL を取得できませんでした")
            return []

        logger.info("競合分析: %s 経由で上位 %d 件を解析", provider, len(urls))
        pages: list[dict] = []
        for url in urls:
            info = self._page_structure(url)
            if info:
                pages.append(info)
        return pages

    @staticmethod
    def format_pages(pages: list[dict]) -> str:
        """収集したページ構成を、人間/LLM が読める一覧テキストに整形する。"""
        if not pages:
            return ""
        lines = ["上位検索結果の構成（参考。模倣ではなく差別化の材料）:"]
        for i, info in enumerate(pages, 1):
            h2_sample = " ｜ ".join(info["h2"][:5]) or "（H2なし）"
            lines.append(
                f"{i}. {info['title']}\n"
                f"   H2例: {h2_sample}\n"
                f"   H3数: {info['h3_count']} / 概算本文量: 約{info['text_len']}文字"
            )
        return "\n".join(lines)


def gather_competitor_pages(keyword: str, settings: Settings) -> list[dict]:
    """
    競合（検索上位ページ）の構成を収集する（SEOAgent から呼ばれる薄いラッパ）。

    競合分析の失敗で本処理を止めないよう、例外は握りつぶして空リストを返す。
    """
    try:
        return CompetitorAnalyzer(settings).gather(keyword)
    except Exception as exc:
        logger.warning("競合分析でエラー（無視して続行）: %s", exc)
        return []


# -----------------------------------------------------------------------------
# WordPress クライアント（REST API）
# -----------------------------------------------------------------------------
class WordPressClient:
    """WordPress REST API へ下書き投稿するための薄いクライアント。"""

    def __init__(self, settings: Settings, timeout: int = 30) -> None:
        self.base_url = settings.wordpress_url
        self.timeout = timeout
        self.session = requests.Session()
        self.session.auth = (settings.wordpress_username, settings.wordpress_app_password)
        self.session.headers.update({"Accept": "application/json"})

    def _api(self, path: str) -> str:
        return f"{self.base_url}/wp-json/wp/v2/{path.lstrip('/')}"

    def _resolve_term_ids(self, taxonomy: str, names: list[str]) -> list[int]:
        """
        タグ/カテゴリ名を ID に解決する。存在しなければ作成する。

        Args:
            taxonomy: "tags" または "categories"。
            names: 用語名のリスト。

        Returns:
            解決された用語 ID のリスト。
        """
        ids: list[int] = []
        for name in names:
            # 既存検索
            resp = self.session.get(
                self._api(taxonomy),
                params={"search": name, "per_page": 100},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            found = next(
                (t for t in resp.json() if t.get("name", "").lower() == name.lower()),
                None,
            )
            if found:
                ids.append(int(found["id"]))
                logger.debug("%s 既存: %s -> %s", taxonomy, name, found["id"])
                continue
            # 無ければ作成
            create = self.session.post(
                self._api(taxonomy), json={"name": name}, timeout=self.timeout
            )
            create.raise_for_status()
            new_id = int(create.json()["id"])
            ids.append(new_id)
            logger.info("%s 作成: %s -> %s", taxonomy, name, new_id)
        return ids

    def create_draft(
        self,
        title: str,
        content_html: str,
        categories: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
    ) -> dict:
        """
        記事を下書き（status=draft）として投稿する。

        Args:
            title: 記事タイトル。
            content_html: 本文（HTML）。
            categories: カテゴリ名のリスト（任意）。
            tags: タグ名のリスト（任意）。

        Returns:
            作成された投稿の JSON。
        """
        payload: dict = {
            "title": title,
            "content": content_html,
            "status": "draft",
        }
        if categories:
            payload["categories"] = self._resolve_term_ids("categories", categories)
        if tags:
            payload["tags"] = self._resolve_term_ids("tags", tags)

        logger.info("WordPress へ下書き投稿します: %s", title)
        resp = self.session.post(self._api("posts"), json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        logger.info(
            "下書き投稿完了: id=%s edit=%s",
            data.get("id"),
            f"{self.base_url}/wp-admin/post.php?post={data.get('id')}&action=edit",
        )
        return data


# -----------------------------------------------------------------------------
# SEO エージェント本体
# -----------------------------------------------------------------------------
class SEOAgent:
    """分析 → 構成 → 作成 → 校正 → 監査 のパイプラインを駆動する。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # --- LLM 呼び出しの共通ヘルパ -------------------------------------------
    def _complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 8000,
        effort: str = "high",
        stream: bool = False,
    ) -> str:
        """
        システム/ユーザープロンプトを分離して Claude を呼び出し、本文テキストを返す。

        長文出力（記事本文など）では stream=True を指定して
        HTTP タイムアウトを避ける。
        """
        kwargs: dict = {
            "model": self.settings.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": effort},
        }
        if stream:
            with self.client.messages.stream(**kwargs) as s:
                message = s.get_final_message()
        else:
            message = self.client.messages.create(**kwargs)
        return "".join(b.text for b in message.content if b.type == "text").strip()

    # --- 競合分析（H2 集計 → 必須/手薄テーマ抽出） --------------------------
    def _cluster_themes(self, keyword: str, headings: list[str], page_count: int) -> Optional[ThemeReport]:
        """
        収集した競合 H2 見出しを意味でクラスタリングし、必須/手薄テーマを抽出する。

        表記揺れのある日本語見出しを束ねるため、単純な文字列一致ではなく LLM の
        Structured Outputs を使う。
        """
        system = (
            "あなたは SEO の競合分析アナリストです。検索上位記事の見出し（H2）一覧を受け取り、"
            "意味の近いものをテーマに束ねて分類します。表記の揺れは同一テーマとして扱います。"
            "- must_cover: 上位の大半が扱う＝網羅性のために外せない必須テーマ\n"
            "- underserved: 一部しか扱わない／手薄＝独自性を出せる差別化テーマ\n"
            "キーワードの検索意図に無関係な見出し（運営者情報・関連記事リンク等）は除外すること。"
        )
        user = (
            f"狙うキーワード: 「{keyword}」\n"
            f"分析対象: 上位 {page_count} 記事の H2 見出し（計 {len(headings)} 件）\n\n"
            "=== H2 見出し一覧 ===\n"
            + "\n".join(f"- {h}" for h in headings)
            + "\n\nこれらを must_cover / underserved / notes に分類してください。"
        )
        try:
            message = self.client.messages.parse(
                model=self.settings.model,
                max_tokens=2000,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=ThemeReport,
            )
            return message.parsed_output
        except Exception as exc:
            logger.warning("テーマ集計に失敗（per-page 情報のみ使用）: %s", exc)
            return None

    def _competitor_report(self, keyword: str) -> str:
        """競合ページを収集し、per-page 概要 + 必須/手薄テーマ集計をテキスト化する。"""
        pages = gather_competitor_pages(keyword, self.settings)
        if not pages:
            return ""

        report = CompetitorAnalyzer.format_pages(pages)

        headings = [h for p in pages for h in p.get("h2", [])]
        # 集計はある程度の見出し数があるときのみ意味を持つ。
        if len(headings) >= 5:
            themes = self._cluster_themes(keyword, headings, len(pages))
            if themes:
                report += "\n\n=== 競合 H2 集計 ===\n"
                report += "■ 必須テーマ（網羅性のため外せない）:\n"
                report += "\n".join(f"- {t}" for t in themes.must_cover) or "- （特になし）"
                report += "\n■ 手薄テーマ（独自性の好機。差別化材料に）:\n"
                report += "\n".join(f"- {t}" for t in themes.underserved) or "- （特になし）"
                if themes.notes:
                    report += f"\n■ 所見: {themes.notes}"
        return report

    # --- 各フェーズ ----------------------------------------------------------
    def analyze(self, draft: Draft) -> None:
        """[分析] 検索意図（潜在・顕在ニーズ）と E-E-A-T 方針を分析する。"""
        logger.info("[分析] keyword=%s", draft.keyword)

        # 競合分析はループ間で不変なので初回のみ取得してキャッシュ。
        if not draft.competitor:
            draft.competitor = self._competitor_report(draft.keyword)

        system = (
            "あなたは E-E-A-T を重視する日本語 SEO のシニアストラテジストです。"
            "検索ユーザーの顕在ニーズ（明示的に知りたいこと）と潜在ニーズ"
            "（言語化されていない本当の目的）を切り分け、網羅性と独自性の観点から"
            "記事が満たすべき要件を簡潔に整理します。装飾や前置きは不要です。"
        )
        user = (
            f"狙うキーワード: 「{draft.keyword}」\n\n"
            "次を日本語で出力してください:\n"
            "1. 想定読者像（誰が・どんな状況で検索するか）\n"
            "2. 顕在ニーズ（箇条書き）\n"
            "3. 潜在ニーズ（箇条書き）\n"
            "4. E-E-A-T を担保するために本文へ盛り込むべき要素\n"
            "5. 網羅すべきテーマ（競合の必須テーマは必ずカバーする）\n"
            "6. 競合に対する独自性の打ち出し方（手薄テーマを差別化に活かす）\n"
        )
        if draft.competitor:
            user += (
                f"\n=== 競合分析（参考。模倣ではなく差別化の材料）===\n{draft.competitor}\n"
                "\n必須テーマは漏らさず網羅し、手薄テーマや独自の切り口で差別化してください。\n"
            )
        if draft.feedback:
            user += (
                "\n前回の監査で不合格でした。次の改善点を踏まえ、分析を更新してください:\n"
                + self._format_feedback(draft.feedback)
            )

        draft.analysis = self._complete(system, user, max_tokens=4000)
        logger.info("[分析] 完了（%d 文字）", len(draft.analysis))

    def build_outline(self, draft: Draft) -> None:
        """[構成] 分析を踏まえ H2/H3 構成案とタイトル・タグを設計する。"""
        logger.info("[構成] keyword=%s", draft.keyword)
        system = (
            "あなたは検索意図を構造化に落とし込む SEO 編集者です。"
            "網羅性と読了率の両立を意識し、論理的な H2/H3 構成を設計します。"
            "出力は必ず指定の JSON 形式のみ（前後に説明文を付けない）。"
        )
        user = (
            f"狙うキーワード: 「{draft.keyword}」\n\n"
            f"=== 分析結果 ===\n{draft.analysis}\n\n"
            "この分析に基づき、以下のキーのみを持つ JSON を 1 つ出力してください:\n"
            "{\n"
            '  "title": "32文字前後のSEOタイトル（キーワードを自然に含む）",\n'
            '  "outline": "H2/H3 を字下げで表現した構成案（テキスト）",\n'
            '  "categories": ["カテゴリ名"],\n'
            '  "tags": ["タグ", "タグ"]\n'
            "}\n"
        )
        if draft.feedback:
            user += (
                "\n前回の監査の改善点を構成に反映してください:\n"
                + self._format_feedback(draft.feedback)
            )

        raw = self._complete(system, user, max_tokens=4000)
        data = self._loads_json(raw)
        draft.title = data.get("title", draft.title) or draft.title
        draft.outline = data.get("outline", "")
        # 既定値があれば優先しつつ、LLM 提案を補完する。
        draft.categories = self.settings.default_categories or data.get("categories", []) or []
        draft.tags = self.settings.default_tags or data.get("tags", []) or []
        logger.info("[構成] 完了 title=%s tags=%s", draft.title, draft.tags)

    def write(self, draft: Draft) -> None:
        """[作成] 構成に沿って HTML 本文を生成する。"""
        logger.info("[作成] title=%s", draft.title)
        system = (
            "あなたは読みやすさを最優先する日本語 Web ライターです。"
            "スマホ閲覧を意識し、1 段落を短く保ち、箇条書き（<ul>/<ol>）や"
            "比較表（<table>）を適切に使って情報を整理します。"
            "出力は記事本文の HTML 断片のみ。<h2>/<h3>/<p>/<ul>/<ol>/<table> 等を用い、"
            "<html> や <body>、Markdown コードフェンス（```）は使わないこと。"
            "アフィリエイトリンクを自然に挿入できる文脈（おすすめ提示・比較・CTA）を"
            "意識的に作りつつ、実在しない事実は書かないこと。"
        )
        user = (
            f"狙うキーワード: 「{draft.keyword}」\n"
            f"タイトル: {draft.title}\n\n"
            f"=== 構成案 ===\n{draft.outline}\n\n"
            f"=== 分析（検索意図）===\n{draft.analysis}\n\n"
            "上記に忠実に、本文 HTML を出力してください。導入文・各 H2 セクション・"
            "まとめ（CTA を含む）まで一気通貫で書いてください。"
        )
        if draft.feedback:
            user += (
                "\n前回の監査の改善点を本文へ反映してください:\n"
                + self._format_feedback(draft.feedback)
            )

        # 本文は長くなり得るためストリーミングで取得する。
        draft.body_html = self._strip_code_fence(
            self._complete(system, user, max_tokens=16000, stream=True)
        )
        logger.info("[作成] 完了（%d 文字）", len(draft.body_html))

    def proofread(self, draft: Draft) -> None:
        """[校正] 誤字脱字・冗長表現・トーンを整える（HTML 構造は維持）。"""
        logger.info("[校正] title=%s", draft.title)
        system = (
            "あなたは日本語のプロ校正者です。意味を変えずに、誤字脱字・二重表現・"
            "冗長な言い回し・不自然な敬語を修正し、読みやすさを高めます。"
            "HTML タグ構造は維持し、本文 HTML 断片のみを返してください。"
            "Markdown コードフェンス（```）は使わないこと。"
        )
        user = (
            "次の HTML を校正して、修正後の HTML 断片だけを返してください。\n\n"
            f"{draft.body_html}"
        )
        draft.body_html = self._strip_code_fence(
            self._complete(system, user, max_tokens=16000, stream=True)
        )
        logger.info("[校正] 完了（%d 文字）", len(draft.body_html))

    def audit(self, draft: Draft) -> AuditResult:
        """[監査] Structured Outputs で SEO 品質を厳格採点する。"""
        logger.info("[監査] title=%s", draft.title)
        system = (
            "あなたは妥協を許さない SEO 監査責任者です。次の観点で記事を厳格に採点します:\n"
            "- 検索キーワードがタイトル・見出し・本文に自然かつ適切に含まれているか\n"
            "- 検索意図（顕在・潜在ニーズ）への網羅性\n"
            "- 独自性・E-E-A-T の担保\n"
            "- 日本語の自然さ・読みやすさ（スマホ前提）\n"
            "- HTML 構造（見出し・箇条書き・表）の適切さ\n"
            "甘い評価は禁止。基準を満たさなければ容赦なく不合格にし、"
            "改善点を具体的に列挙すること。"
        )
        user = (
            f"狙うキーワード: 「{draft.keyword}」\n"
            f"タイトル: {draft.title}\n"
            f"合格ライン: score >= {self.settings.pass_score} かつ 重大な欠陥なし\n\n"
            "=== 本文 HTML ===\n"
            f"{draft.body_html}\n\n"
            "上記を採点し、pass / score / reason / improvements を返してください。"
        )

        message = self.client.messages.parse(
            model=self.settings.model,
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=AuditResult,
        )
        result = message.parsed_output
        if result is None:
            raise RuntimeError("監査結果のパースに失敗しました。")
        logger.info("[監査] pass=%s score=%s", result.pass_, result.score)
        return result

    # --- ユーティリティ ------------------------------------------------------
    @staticmethod
    def _format_feedback(feedback: AuditResult) -> str:
        lines = [f"- 総評: {feedback.reason} (score={feedback.score})"]
        lines += [f"- 改善: {imp}" for imp in feedback.improvements]
        return "\n".join(lines)

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        """LLM が誤って付けた ```html ... ``` フェンスを除去する。"""
        t = text.strip()
        if t.startswith("```"):
            t = t.split("\n", 1)[-1] if "\n" in t else t
            if t.endswith("```"):
                t = t[: t.rfind("```")]
        return t.strip()

    @staticmethod
    def _loads_json(raw: str) -> dict:
        """LLM 応答から JSON を抽出してパースする（軽い防御）。"""
        text = raw.strip()
        if text.startswith("```"):
            text = SEOAgent._strip_code_fence(text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start : end + 1])
            raise

    # --- パイプライン制御 ----------------------------------------------------
    def run(self, keyword: str, dry_run: bool = False) -> dict:
        """
        キーワードに対しパイプラインを最大 max_loops 回まで実行する。

        Args:
            keyword: 狙う検索キーワード。
            dry_run: True なら WordPress 投稿せず原稿を返すのみ。

        Returns:
            実行結果の dict（合否・原稿・投稿先など）。

        Raises:
            RuntimeError: 規定回数で合格しなかった場合。
        """
        draft = Draft(keyword=keyword)

        for attempt in range(1, self.settings.max_loops + 1):
            logger.info("===== ループ %d / %d =====", attempt, self.settings.max_loops)
            self.analyze(draft)
            self.build_outline(draft)
            self.write(draft)
            self.proofread(draft)
            result = self.audit(draft)

            if result.pass_ and result.score >= self.settings.pass_score:
                logger.info("監査合格（attempt=%d, score=%d）", attempt, result.score)
                post = None
                if dry_run:
                    logger.info("dry-run のため WordPress 投稿はスキップします。")
                else:
                    self.settings.require_wordpress()
                    wp = WordPressClient(self.settings)
                    post = wp.create_draft(
                        title=draft.title,
                        content_html=draft.body_html,
                        categories=draft.categories,
                        tags=draft.tags,
                    )
                return {
                    "status": "passed",
                    "attempts": attempt,
                    "audit": result.model_dump(by_alias=True),
                    "title": draft.title,
                    "body_html": draft.body_html,
                    "wordpress_post": post,
                }

            logger.warning(
                "監査不合格（attempt=%d, score=%d）。フィードバックを保持してリライトします。",
                attempt,
                result.score,
            )
            draft.feedback = result

        # 規定回数で合格しなかった場合（無限ループ防止）
        logger.error("最大ループ回数 %d 回でも合格しませんでした。", self.settings.max_loops)
        return {
            "status": "failed",
            "attempts": self.settings.max_loops,
            "audit": draft.feedback.model_dump(by_alias=True) if draft.feedback else None,
            "title": draft.title,
            "body_html": draft.body_html,
            "wordpress_post": None,
        }


# -----------------------------------------------------------------------------
# CLI エントリポイント
# -----------------------------------------------------------------------------
def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="WordPress SEO エージェント: キーワードから記事を自律生成し下書き投稿する。",
    )
    parser.add_argument("keyword", help="狙う検索キーワード（例: 'ふるさと納税 おすすめ 食品'）")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="WordPress へ投稿せず、生成した原稿だけを出力する。",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    try:
        settings = Settings.from_env()
        agent = SEOAgent(settings)
        result = agent.run(args.keyword, dry_run=args.dry_run)
    except Exception as exc:  # CLI なので最終的にここで握る
        logger.exception("実行中にエラーが発生しました: %s", exc)
        return 1

    print("\n" + "=" * 70)
    print(f"結果: {result['status']}  / 試行回数: {result['attempts']}")
    print(f"タイトル: {result['title']}")
    if result.get("audit"):
        print("監査:", json.dumps(result["audit"], ensure_ascii=False))
    if result.get("wordpress_post"):
        print(f"投稿 ID: {result['wordpress_post'].get('id')}")
    print("=" * 70)

    if args.dry_run or result["status"] == "failed":
        print("\n--- 本文 HTML ---\n")
        print(result["body_html"])

    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    sys.exit(main())
