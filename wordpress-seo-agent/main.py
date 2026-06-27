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
import base64
import html
import json
import logging
import os
import re
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

    # アフィリエイト案件（提携クリニック）。ファイルが無ければ空＝機能オフ。
    clinics: list[dict] = field(default_factory=list)
    clinics_per_article: int = 5

    # 画像生成（OpenAI）。キーが無ければ無効＝文字記事のまま（安全縮退）。
    openai_api_key: str = ""
    image_enabled: bool = True
    image_model: str = "gpt-image-2"
    image_quality: str = "medium"
    image_section_max: int = 3
    # 出力フォーマット（サイト軽量化のため既定 webp）と圧縮率（0-100, webp/jpeg のみ）
    image_format: str = "webp"
    image_compression: int = 80
    # イラスト監査（Claude vision で文字化け・内容・コンプラを検査して再生成）
    image_audit_enabled: bool = True
    image_audit_retries: int = 2

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
            clinics=load_clinics(os.getenv("CLINICS_FILE", "clinics.json").strip() or "clinics.json"),
            clinics_per_article=int(os.getenv("CLINICS_PER_ARTICLE", "5") or "5"),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            image_enabled=(os.getenv("IMAGE_GEN", "true").strip().lower() not in ("0", "false", "no", "off")),
            image_model=os.getenv("IMAGE_MODEL", "gpt-image-2").strip() or "gpt-image-2",
            image_quality=os.getenv("IMAGE_QUALITY", "medium").strip() or "medium",
            image_section_max=int(os.getenv("IMAGE_SECTION_MAX", "3") or "3"),
            image_format=os.getenv("IMAGE_FORMAT", "webp").strip().lower() or "webp",
            image_compression=int(os.getenv("IMAGE_COMPRESSION", "80") or "80"),
            image_audit_enabled=(os.getenv("IMAGE_AUDIT", "true").strip().lower() not in ("0", "false", "no", "off")),
            image_audit_retries=int(os.getenv("IMAGE_AUDIT_RETRIES", "2") or "2"),
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


class ImageSpec(BaseModel):
    """記事に挿入する画像 1 枚の仕様（Structured Output）。"""

    role: str = Field(..., description='"featured"（アイキャッチ）または "section"（本文挿絵）')
    prompt: str = Field(
        ...,
        description="画像生成用の説明（英語）。被写体・構図のみ。スタイルはコードが付与する。文字・実写・顔・ビフォーアフターは描かせない。",
    )
    alt: str = Field(..., description="日本語の alt テキスト（SEO・アクセシビリティ用）")
    after_heading: str = Field(
        default="",
        description='section の場合、この画像を直後に置く既存の H2 見出し文字列。featured は空。',
    )


class ImagePlan(BaseModel):
    """記事全体の画像配置プラン（Structured Output）。"""

    images: list[ImageSpec] = Field(default_factory=list)


class ImageAudit(BaseModel):
    """生成画像の品質監査（Claude vision の Structured Output）。"""

    ok: bool = Field(..., description="記事に使える品質なら true")
    garbled_text: bool = Field(
        default=False, description="日本語に文字化け・誤字・意味不明な文字があれば true"
    )
    reason: str = Field(default="", description="判定理由の要約")
    issues: list[str] = Field(
        default_factory=list, description="不合格時の具体的な問題点（再生成の指示に使う）"
    )


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
    # 競合 H2 集計で得た「必須テーマ」（監査での網羅性突合に使う）
    must_cover: list[str] = field(default_factory=list)
    # 競合分析を取得済みか（空文字でも再取得しないためのフラグ）
    competitor_loaded: bool = False
    # 直近の監査フィードバック（リライト時に各フェーズへ渡す）
    feedback: Optional[AuditResult] = None
    # この記事で紹介する提携クリニック（キーワードに応じて選定）
    clinics: list[dict] = field(default_factory=list)
    # アイキャッチ画像の WordPress メディア ID（画像フェーズで設定）
    featured_media_id: Optional[int] = None


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
# アフィリエイト案件（提携クリニック）— 読込・選定・リンク注入
# -----------------------------------------------------------------------------
# 方針: LLM には URL を一切書かせず、本文には目印（プレースホルダ）だけ置かせる。
# 実際のアフィリエイトリンクはコードがデータから正確に組み立てて注入する
# （URL 捏造の防止と、rel="sponsored nofollow" 等の規約準拠を担保するため）。

CLINICS_TABLE_MARKER = "{{CLINICS_TABLE}}"


def load_clinics(path: str) -> list[dict]:
    """提携クリニック一覧を JSON から読む。無ければ空リスト＝機能オフ（安全縮退）。"""
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.warning("clinics ファイルの読込に失敗（アフィリ注入を無効化）: %s", exc)
        return []
    raw = data.get("clinics", data) if isinstance(data, dict) else data
    clinics = [c for c in raw if isinstance(c, dict) and c.get("name") and c.get("url")]
    if clinics:
        logger.info("提携クリニックを %d 件読み込みました", len(clinics))
    return clinics


def select_clinics(keyword: str, clinics: list[dict], max_n: int = 5) -> list[dict]:
    """キーワードに合うクリニックを選ぶ（施術種別・対応地域でスコアリング）。"""
    if not clinics:
        return []
    kw = keyword.lower()
    wants_lasik = ("レーシック" in keyword) or ("lasik" in kw)
    wants_icl = ("icl" in kw) or ("眼内レンズ" in keyword)
    scored: list[tuple[int, dict]] = []
    for c in clinics:
        types = " ".join(c.get("types", [])).lower()
        score = 0
        if wants_lasik and ("レーシック" in types or "lasik" in types):
            score += 2
        if wants_icl and "icl" in types:
            score += 2
        for region in c.get("regions", []):
            if region and region.lower() in kw:
                score += 3
        scored.append((score, c))
    # 施術種別の指定がある場合は、該当クリニックを優先（無ければ全件）。
    if wants_lasik or wants_icl:
        matched = [(s, c) for s, c in scored if s > 0]
        scored = matched or scored
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:max_n]]


def _clinic_link(clinic: dict, label: str) -> str:
    """案件リンクを生成する。URL はデータ由来のみ。rel に sponsored/nofollow を付与。"""
    url = html.escape(clinic.get("url", ""), quote=True)
    return (
        f'<a href="{url}" target="_blank" '
        f'rel="sponsored nofollow noopener">{html.escape(label)}</a>'
    )


def render_clinics_table(clinics: list[dict]) -> str:
    """提携クリニックの比較表 HTML を組み立てる（各行に公式サイトへの案件リンク）。"""
    if not clinics:
        return ""
    rows = []
    for c in clinics:
        name = html.escape(c.get("name", ""))
        types = html.escape("・".join(c.get("types", [])))
        catch = html.escape(c.get("catch", ""))
        cta = _clinic_link(c, "公式サイト")
        rows.append(
            f"<tr><td><strong>{name}</strong></td><td>{types}</td>"
            f"<td>{catch}</td><td>{cta}</td></tr>"
        )
    # 医療広告ガイドラインに配慮し、費用を強調する列は置かず「対応施術・特徴」で比較する。
    return (
        '<figure class="wp-block-table clinic-compare"><table>'
        "<thead><tr><th>クリニック</th><th>対応施術</th><th>特徴</th><th>公式</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table></figure>"
    )


def _append_clinics_block(body_html: str, table: str) -> str:
    """目印が無い場合のフォールバック：比較表を「まとめ/FAQ」の前、無ければ末尾に挿入。"""
    block = "<h2>おすすめクリニック比較</h2>" + table
    m = re.search(r"<h2[^>]*>[^<]*(まとめ|よくある|FAQ|Q&A)", body_html)
    if m:
        return body_html[: m.start()] + block + body_html[m.start():]
    return body_html + block


def inject_clinics(body_html: str, clinics: list[dict]) -> str:
    """本文中の目印を、実際の案件リンク（比較表・CTA）に置換する。"""
    if not clinics:
        return body_html
    table = render_clinics_table(clinics)
    if CLINICS_TABLE_MARKER in body_html:
        body_html = body_html.replace(CLINICS_TABLE_MARKER, table, 1)
    else:
        body_html = _append_clinics_block(body_html, table)

    def _cta(match: "re.Match") -> str:
        name = match.group(1).strip()
        clinic = next((x for x in clinics if x.get("name") == name), None)
        if clinic is None:  # 完全一致しなければ部分一致で救済
            clinic = next((x for x in clinics if name and name in x.get("name", "")), None)
        if clinic is None:
            return ""
        label = f"▶ {clinic.get('name')}の無料カウンセリングはこちら"
        return '<p class="clinic-cta">' + _clinic_link(clinic, label) + "</p>"

    body_html = re.sub(r"\{\{CTA:([^}]+)\}\}", _cta, body_html)
    # 捏造リンク防止のため、残った {{...}} 目印はすべて除去する。
    body_html = re.sub(r"\{\{[^}]*\}\}", "", body_html)
    # 医療広告/ASP 規約: 「広告と分かる表示」を冒頭に必ず付与する（コードで担保）。
    disclosure = (
        '<p class="ad-disclosure"><small>※本記事はアフィリエイト広告（PR）を含みます。'
        "掲載情報は執筆時点のものです。施術の適応・料金・リスクは各クリニックの公式サイトで"
        "必ずご確認ください。</small></p>"
    )
    return disclosure + body_html


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

    def upload_media(
        self, image_bytes: bytes, filename: str, mime: str = "image/png", alt: str = ""
    ) -> dict:
        """画像をメディアライブラリにアップロードし、メディア情報（id, source_url）を返す。"""
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": mime,
        }
        resp = self.session.post(
            self._api("media"), headers=headers, data=image_bytes, timeout=self.timeout
        )
        resp.raise_for_status()
        media = resp.json()
        media_id = int(media["id"])
        if alt:  # alt/タイトルは別リクエストで設定する
            self.session.post(
                self._api(f"media/{media_id}"),
                json={"alt_text": alt, "title": alt},
                timeout=self.timeout,
            )
        logger.info("メディアアップロード完了: id=%s url=%s", media_id, media.get("source_url"))
        return media

    def create_draft(
        self,
        title: str,
        content_html: str,
        categories: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        featured_media: Optional[int] = None,
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
        if featured_media:
            payload["featured_media"] = featured_media
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

    def _competitor_report(self, keyword: str) -> tuple[str, list[str]]:
        """
        競合ページを収集し、per-page 概要 + 必須/手薄テーマ集計をテキスト化する。

        Returns:
            (レポートテキスト, 必須テーマのリスト)。必須テーマは監査での突合に使う。
        """
        pages = gather_competitor_pages(keyword, self.settings)
        if not pages:
            return "", []

        report = CompetitorAnalyzer.format_pages(pages)
        must_cover: list[str] = []

        headings = [h for p in pages for h in p.get("h2", [])]
        # 集計はある程度の見出し数があるときのみ意味を持つ。
        if len(headings) >= 5:
            themes = self._cluster_themes(keyword, headings, len(pages))
            if themes:
                must_cover = themes.must_cover
                report += "\n\n=== 競合 H2 集計 ===\n"
                report += "■ 必須テーマ（網羅性のため外せない）:\n"
                report += "\n".join(f"- {t}" for t in themes.must_cover) or "- （特になし）"
                report += "\n■ 手薄テーマ（独自性の好機。差別化材料に）:\n"
                report += "\n".join(f"- {t}" for t in themes.underserved) or "- （特になし）"
                if themes.notes:
                    report += f"\n■ 所見: {themes.notes}"
        return report, must_cover

    # --- 各フェーズ ----------------------------------------------------------
    def analyze(self, draft: Draft) -> None:
        """[分析] 検索意図（潜在・顕在ニーズ）と E-E-A-T 方針を分析する。"""
        logger.info("[分析] keyword=%s", draft.keyword)

        # 競合分析はループ間で不変なので初回のみ取得してキャッシュ。
        if not draft.competitor_loaded:
            draft.competitor, draft.must_cover = self._competitor_report(draft.keyword)
            draft.competitor_loaded = True

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
        # この記事で紹介する提携クリニックを選定（案件が無ければ空＝従来動作）。
        draft.clinics = select_clinics(
            draft.keyword, self.settings.clinics, self.settings.clinics_per_article
        )
        if draft.clinics:
            logger.info(
                "[作成] 紹介クリニック %d 件: %s",
                len(draft.clinics),
                "、".join(c.get("name", "") for c in draft.clinics),
            )
        system = (
            "あなたは読みやすさを最優先する日本語 Web ライターです。"
            "スマホ閲覧を意識し、1 段落を短く保ち、箇条書き（<ul>/<ol>）や"
            "比較表（<table>）を適切に使って情報を整理します。"
            "出力は記事本文の HTML 断片のみ。<h2>/<h3>/<p>/<ul>/<ol>/<table> 等を用い、"
            "<html> や <body>、Markdown コードフェンス（```）は使わないこと。"
            "アフィリエイトリンクを自然に挿入できる文脈（おすすめ提示・比較・CTA）を"
            "意識的に作りつつ、実在しない事実は書かないこと。"
        )
        if draft.clinics:
            system += (
                " 提携クリニックの紹介を必ず含めます。ただしリンク（URL）や <a> タグは"
                "自分で書かず、指定された目印（プレースホルダ）だけを置くこと。"
                " この記事は医療（自由診療）のアフィリエイト記事です。医療広告ガイドラインを順守し、"
                "次を厳守すること: (1) 患者の体験談・口コミ・感想を創作しない。"
                "(2)『No.1』『日本一』『最高』『必ず治る』等の最上級・優良誤認・効果保証の表現を使わない。"
                "(3) ビフォーアフターや誇大・虚偽の表現を使わない。(4) 費用を過度に煽らない。"
                "(5) 効果には個人差がある前提で断定を避け、リスクや自由診療である旨にも触れる。"
                "(6) 各クリニック公式サイトの文章・体験談をそのまま転載しない。"
                " PR（広告）である旨の明記は冒頭にコードが付与するので、本文では繰り返さないこと。"
            )
        user = (
            f"狙うキーワード: 「{draft.keyword}」\n"
            f"タイトル: {draft.title}\n\n"
            f"=== 構成案 ===\n{draft.outline}\n\n"
            f"=== 分析（検索意図）===\n{draft.analysis}\n\n"
            "上記に忠実に、本文 HTML を出力してください。導入文・各 H2 セクション・"
            "まとめ（CTA を含む）まで一気通貫で書いてください。"
        )
        if draft.clinics:
            lines = ["=== 紹介する提携クリニック（アフィリエイト送客）==="]
            for i, c in enumerate(draft.clinics, 1):
                pts = "・".join(c.get("points", []))
                line = f"{i}. {c['name']}｜{c.get('catch', '')}"
                if c.get("price"):
                    line += f"｜料金: {c['price']}"
                if pts:
                    line += f"｜推し: {pts}"
                lines.append(line)
            user += (
                "\n" + "\n".join(lines) + "\n\n"
                "【アフィリエイト挿入ルール（厳守）】\n"
                "- 「おすすめクリニック比較」等の H2 セクションを設け、その中に必ず "
                f"{CLINICS_TABLE_MARKER} を 1 回だけ単独で置くこと（コードが比較表に置換します）。\n"
                "- 各クリニックを本文で名前を挙げて具体的に紹介し、その紹介の直後に "
                "{{CTA:正式名}} を置くこと（コードが申込ボタンに置換します）。"
                "正式名は上記リストの名称と完全一致させること。\n"
                "- URL・href・<a> タグは絶対に自分で書かないこと（リンクはコードが付与します）。\n"
                "- 料金や実績などの事実は上記データの範囲で書き、誇大表現・断定を避けること。\n"
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
            " {{...}} 形式の目印（プレースホルダ）は変更・削除せず、そのままの位置に残すこと。"
        )
        user = (
            "次の HTML を校正して、修正後の HTML 断片だけを返してください。\n\n"
            f"{draft.body_html}"
        )
        draft.body_html = self._strip_code_fence(
            self._complete(system, user, max_tokens=16000, stream=True)
        )
        logger.info("[校正] 完了（%d 文字）", len(draft.body_html))

    def inject_affiliates(self, draft: Draft) -> None:
        """[案件注入] 本文中の目印を、実際の提携クリニックのリンク（比較表・CTA）に置換する。"""
        if not draft.clinics:
            return
        before = len(draft.body_html)
        draft.body_html = inject_clinics(draft.body_html, draft.clinics)
        logger.info(
            "[案件注入] クリニック %d 件のリンクを反映（%d→%d 文字）",
            len(draft.clinics),
            before,
            len(draft.body_html),
        )

    # --- 画像生成（OpenAI gpt-image-1）---------------------------------------
    IMAGE_STYLE = (
        "clean modern infographic-style flat illustration for a Japanese eye-care / medical article. "
        "Soft rounded shapes, calm palette of light blue and teal on a white background with one warm "
        "accent color, friendly and easy to understand at a glance. "
        "Render the specified Japanese labels in CORRECT, LARGE, highly legible Japanese gothic "
        "(sans-serif) lettering, kept minimal so it is readable on a smartphone: only a few short words, "
        "plenty of whitespace, not cluttered. "
        "NO photographs, NO real or identifiable person, NO before-and-after photos, NO exaggerated or "
        "guaranteeing claims, NO logos."
    )

    @staticmethod
    def _extract_h2(body_html: str) -> list[str]:
        return [
            re.sub(r"<[^>]+>", "", m).strip()
            for m in re.findall(r"<h2[^>]*>(.*?)</h2>", body_html, re.S)
        ]

    def _plan_images(self, draft: Draft) -> list[ImageSpec]:
        """記事に合う画像（アイキャッチ＋本文挿絵）の配置とプロンプトを設計する。"""
        headings = self._extract_h2(draft.body_html)
        system = (
            "あなたは Web 記事のアートディレクターです。各見出しの内容が『ぱっと見でわかる』"
            "図解（インフォグラフィック風のフラットイラスト）を計画します。"
            "スマホでも読めるよう、画像内のラベルは短く・少なく・大きく。医療系のため、実在人物の"
            "写真・ビフォーアフター・誇大表現は不可。"
        )
        user = (
            f"記事タイトル: {draft.title}\n"
            "H2 見出し一覧:\n" + "\n".join(f"- {h}" for h in headings) + "\n\n"
            "各見出しの要点が一目で伝わる図解を計画し、JSON で出してください:\n"
            "- featured（アイキャッチ）を必ず 1 枚。記事タイトルを象徴する図解。\n"
            f"- section（本文挿絵）を {self.settings.image_section_max} 枚まで。各章の直後に置く。\n"
            "各画像の項目:\n"
            "  role: featured または section\n"
            "  prompt: 画像生成用の指示（英語で構図・図解内容を説明し、画像内に表示する"
            "『短い日本語ラベル（最大4個・各おおむね1〜6文字）』を引用符付きで明示する。"
            'たとえば show a cross-section of an eye, label the implanted lens as "ICLレンズ"。'
            "文字は少なく大きく、スマホで読めるシンプルさを最優先）\n"
            "  alt: 日本語の説明文（SEO・アクセシビリティ用）\n"
            "  after_heading: section のみ。上記 H2 の文字列と一致させる（featured は空）\n"
            "1 枚に情報を詰め込みすぎないこと。"
        )
        message = self.client.messages.parse(
            model=self.settings.model,
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=ImagePlan,
        )
        plan = message.parsed_output
        specs = plan.images if plan else []
        featured = [s for s in specs if s.role == "featured"][:1]
        sections = [s for s in specs if s.role != "featured"][: self.settings.image_section_max]
        return featured + sections

    def _image_mime_ext(self) -> tuple[str, str]:
        """設定の出力フォーマットから (mime, 拡張子) を返す。"""
        fmt = (self.settings.image_format or "webp").lower()
        if fmt in ("jpg", "jpeg"):
            return "image/jpeg", "jpg"
        if fmt == "png":
            return "image/png", "png"
        return "image/webp", "webp"

    def _generate_image(self, prompt: str, featured: bool) -> bytes:
        """OpenAI で画像を 1 枚生成し、画像バイト列を返す（既定 WebP）。"""
        from openai import OpenAI  # 遅延 import（未導入でも他機能に影響しない）

        client = OpenAI(api_key=self.settings.openai_api_key)
        fmt = "jpeg" if self.settings.image_format in ("jpg", "jpeg") else self.settings.image_format
        kwargs: dict = {
            "model": self.settings.image_model,
            "prompt": f"{prompt}. {self.IMAGE_STYLE}",
            "size": "1536x1024" if featured else "1024x1024",
            "quality": self.settings.image_quality,
            "n": 1,
            "output_format": fmt,
        }
        if fmt in ("webp", "jpeg"):  # 圧縮率は webp/jpeg のみ有効
            kwargs["output_compression"] = self.settings.image_compression
        resp = client.images.generate(**kwargs)
        return base64.b64decode(resp.data[0].b64_json)

    @staticmethod
    def _insert_image(body_html: str, url: str, alt: str, after_heading: str) -> str:
        """本文の該当 H2 の直後に <figure><img></figure> を挿入する。"""
        fig = (
            '<figure class="wp-block-image size-large">'
            f'<img src="{html.escape(url, quote=True)}" alt="{html.escape(alt)}" loading="lazy" />'
            "</figure>"
        )
        if after_heading:
            key = after_heading.strip()[:12]
            for m in re.finditer(r"<h2[^>]*>(.*?)</h2>", body_html, re.S):
                inner = re.sub(r"<[^>]+>", "", m.group(1))
                if key and key in inner:
                    return body_html[: m.end()] + fig + body_html[m.end():]
        m = re.search(r"</h2>", body_html)  # フォールバック: 最初の H2 直後、無ければ末尾
        if m:
            return body_html[: m.end()] + fig + body_html[m.end():]
        return body_html + fig

    def _audit_image(self, image_bytes: bytes, spec: ImageSpec) -> ImageAudit:
        """生成画像を Claude vision で検査する（文字化け・内容・コンプラ・スマホ可読性）。"""
        media_type, _ = self._image_mime_ext()
        b64 = base64.b64encode(image_bytes).decode("ascii")
        system = (
            "あなたは記事用の図解画像の品質監査者です。次を厳格に検査します:\n"
            "1) 画像内の日本語に文字化け・誤字・実在しない文字が無いか（あれば garbled_text=true, ok=false）\n"
            "2) 内容が意図したテーマ・ラベルと合致しているか\n"
            "3) 医療コンプラ: 実在人物の写真・ビフォーアフター・誇大/効果保証表現が無いか\n"
            "4) スマホで読めるか（文字が多すぎ／小さすぎ／詰め込みすぎでないか）\n"
            "いずれか問題があれば ok=false とし、issues に再生成用の具体的な修正指示を書くこと。"
        )
        user_text = (
            f"この画像の意図（alt）: {spec.alt}\n"
            f"狙った図解内容: {spec.prompt[:400]}\n"
            "上記を踏まえ画像を検査し、ok / garbled_text / reason / issues を返してください。"
        )
        message = self.client.messages.parse(
            model=self.settings.model,
            max_tokens=1000,
            system=system,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                    {"type": "text", "text": user_text},
                ],
            }],
            output_format=ImageAudit,
        )
        return message.parsed_output or ImageAudit(ok=True)

    def _make_audited_image(self, spec: ImageSpec, featured: bool) -> Optional[bytes]:
        """生成→監査→必要なら再生成。文字化けが解消しなければ採用を見送る（None）。"""
        prompt = spec.prompt
        last_bytes: Optional[bytes] = None
        last_verdict: Optional[ImageAudit] = None
        attempts = 1 + (self.settings.image_audit_retries if self.settings.image_audit_enabled else 0)
        for attempt in range(1, attempts + 1):
            try:
                img = self._generate_image(prompt, featured=featured)
            except Exception as exc:
                logger.warning("画像生成に失敗: %s", exc)
                return last_bytes
            last_bytes = img
            if not self.settings.image_audit_enabled:
                return img
            try:
                v = self._audit_image(img, spec)
            except Exception as exc:
                logger.warning("画像監査に失敗（その画像を採用）: %s", exc)
                return img
            last_verdict = v
            if v.ok:
                logger.info("[画像監査] 合格（attempt=%d）: %s", attempt, spec.alt[:24])
                return img
            logger.warning(
                "[画像監査] 不合格（attempt=%d, garbled=%s）: %s",
                attempt, v.garbled_text, "／".join(v.issues)[:120],
            )
            prompt = spec.prompt + " | Fix these issues: " + "; ".join(v.issues)
        # 規定回数で合格せず: 文字化けが残るなら採用見送り、軽微な不一致なら最後の画像を採用。
        if last_verdict and last_verdict.garbled_text:
            logger.warning("[画像監査] 文字化けが解消せず画像を見送り: %s", spec.alt[:24])
            return None
        logger.warning("[画像監査] 規定回数で合格せず最後の画像を採用: %s", spec.alt[:24])
        return last_bytes

    def illustrate(self, draft: Draft, wp: "WordPressClient") -> None:
        """[画像] 図解を生成・監査し、アイキャッチ設定＋本文へ挿絵を挿入する（best-effort）。"""
        if not (self.settings.image_enabled and self.settings.openai_api_key):
            return
        logger.info("[画像] 画像プランを作成します（model=%s）", self.settings.image_model)
        try:
            specs = self._plan_images(draft)
        except Exception as exc:
            logger.warning("画像プラン作成に失敗（画像なしで続行）: %s", exc)
            return
        mime, ext = self._image_mime_ext()
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", draft.keyword)[:20] or "img"
        added = 0
        first_media_id: Optional[int] = None
        for i, spec in enumerate(specs):
            featured = spec.role == "featured"
            img = self._make_audited_image(spec, featured)
            if img is None:
                continue
            try:
                media = wp.upload_media(img, filename=f"seo-{slug}-{i}.{ext}", mime=mime, alt=spec.alt)
            except Exception as exc:
                logger.warning("画像アップロードに失敗（スキップ）: %s", exc)
                continue
            media_id = int(media["id"])
            if first_media_id is None:
                first_media_id = media_id
            if featured and draft.featured_media_id is None:
                draft.featured_media_id = media_id
            else:
                draft.body_html = self._insert_image(
                    draft.body_html, media.get("source_url", ""), spec.alt, spec.after_heading
                )
            added += 1
        # サムネ（アイキャッチ）は必ず設定する: featured が無ければ最初の画像で代替する。
        if draft.featured_media_id is None and first_media_id is not None:
            draft.featured_media_id = first_media_id
            logger.info("[画像] featured 未取得のため最初の画像をサムネに採用: id=%s", first_media_id)
        logger.info("[画像] %d 枚を反映（アイキャッチ=%s）", added, draft.featured_media_id is not None)

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
            "- 競合の必須テーマ（提示があれば）の網羅\n"
            "甘い評価は禁止。基準を満たさなければ容赦なく不合格にし、"
            "改善点を具体的に列挙すること。必須テーマの取りこぼしは重大な欠陥として"
            "減点し、不足テーマ名を improvements に明記すること。"
        )
        if draft.clinics:
            system += (
                " なお本記事は医療（自由診療）のアフィリエイト記事である。医療広告ガイドライン上、"
                "患者の体験談・口コミ、『No.1/最高/必ず治る』等の優良誤認・効果保証、"
                "ビフォーアフターは禁止である。これらが含まれていれば重大な欠陥として減点すること。"
                "逆に、改善提案（improvements）として体験談の追加や最上級表現の使用を勧めてはならない。"
            )
        must_cover_block = ""
        if draft.must_cover:
            must_cover_block = (
                "\n=== 競合の必須テーマ（網羅必須。取りこぼしは減点）===\n"
                + "\n".join(f"- {t}" for t in draft.must_cover)
                + "\n各テーマが本文で実質的に扱われているか確認すること。\n"
            )
        affiliate_block = ""
        if draft.clinics:
            names = "、".join(c.get("name", "") for c in draft.clinics)
            affiliate_block = (
                "\n=== アフィリエイト要件（送客サイト）===\n"
                f"この記事は提携クリニック（{names}）への送客が目的。"
                "比較表・各クリニックの紹介・申込導線（CTA リンク）が本文に含まれているか確認し、"
                "欠けていれば重大な欠陥として減点し改善点に明記すること。\n"
            )
        user = (
            f"狙うキーワード: 「{draft.keyword}」\n"
            f"タイトル: {draft.title}\n"
            f"合格ライン: score >= {self.settings.pass_score} かつ 重大な欠陥なし\n"
            f"{must_cover_block}"
            f"{affiliate_block}\n"
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
            self.inject_affiliates(draft)
            result = self.audit(draft)

            if result.pass_ and result.score >= self.settings.pass_score:
                logger.info("監査合格（attempt=%d, score=%d）", attempt, result.score)
                post = None
                if dry_run:
                    logger.info("dry-run のため WordPress 投稿はスキップします。")
                else:
                    self.settings.require_wordpress()
                    wp = WordPressClient(self.settings)
                    self.illustrate(draft, wp)
                    post = wp.create_draft(
                        title=draft.title,
                        content_html=draft.body_html,
                        categories=draft.categories,
                        tags=draft.tags,
                        featured_media=draft.featured_media_id,
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
