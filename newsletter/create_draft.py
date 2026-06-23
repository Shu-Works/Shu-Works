#!/usr/bin/env python3
"""
create_draft.py — 海外向けデジタル塗り絵のメルマガ「下書き」自動生成ツール

指定テーマ（日本文化・四季・レトロ風景など）から、海外ユーザーに刺さる英語の
メルマガ（件名・本文・ヘッダー画像・CTA・フッター）を生成し、MailerLite の
新 API 経由で「Draft（下書き）」キャンペーンとして保存する。

人間は MailerLite 管理画面（スマホ可）で最終確認して配信ボタンを押すだけ。

使い方:
    python3 create_draft.py                  # ランダムなテーマで下書き作成
    python3 create_draft.py --theme four_seasons
    python3 create_draft.py --list           # 利用可能なテーマ一覧
    python3 create_draft.py --dry-run        # 投稿せず HTML を output/ に保存して確認

設定はすべて .env で管理する（.env.example を参照）。
"""

import argparse
import datetime as _dt
import html
import json
import os
import random
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# --- パス類 ---
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

THEMES_PATH = BASE_DIR / "themes.json"
TEMPLATE_PATH = BASE_DIR / "email_template.html"
OUTPUT_DIR = BASE_DIR / "output"

# --- MailerLite 新 API ---
MAILERLITE_BASE = "https://connect.mailerlite.com/api"

# --- Anthropic (Claude) Messages API ---
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


# ---------------------------------------------------------------------------
# 設定の読み込み
# ---------------------------------------------------------------------------
def get_config():
    """環境変数から設定を読む。必須・任意を区別して返す。"""
    return {
        # 必須（MailerLite 投稿に必要）
        "mailerlite_api_key": os.getenv("MAILERLITE_API_KEY", "").strip(),
        "from_name": os.getenv("FROM_NAME", "").strip(),
        "from_email": os.getenv("FROM_EMAIL", "").strip(),
        # 任意
        "group_id": os.getenv("MAILERLITE_GROUP_ID", "").strip(),
        "shop_url": os.getenv("SHOP_URL", "https://example.com").strip(),
        "cta_text": os.getenv("CTA_TEXT", "Browse the colouring pages").strip(),
        "brand_name": os.getenv("BRAND_NAME", "Your Colouring Studio").strip(),
        # Claude（任意。無ければテンプレ生成）
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", "").strip(),
        "anthropic_model": os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8").strip(),
        # Pexels 画像（任意。無ければプレースホルダ画像）
        "pexels_api_key": os.getenv("PEXELS_API_KEY", "").strip(),
        "header_image_url": os.getenv("HEADER_IMAGE_URL", "").strip(),
    }


def load_themes():
    with open(THEMES_PATH, encoding="utf-8") as f:
        return json.load(f)["themes"]


# ---------------------------------------------------------------------------
# 1. コンテンツ生成（Claude API または テンプレート）
# ---------------------------------------------------------------------------
def generate_with_claude(theme_key, theme, cfg):
    """Claude にテーマを渡して件名・preheader・本文段落を生成させる。
    失敗したら None を返し、呼び出し側がテンプレートにフォールバックする。"""
    prompt = (
        "You are a copywriter for a brand that sells digital colouring pages of "
        "Japan to an English-speaking, overseas audience. Write a warm, "
        "emotional newsletter about the theme below.\n\n"
        f"THEME: {theme['title']}\n"
        f"ANGLE: {theme['angle']}\n\n"
        "Requirements:\n"
        "- A magnetic subject line that makes overseas readers want to open it.\n"
        "- A one-line preheader (inbox preview text).\n"
        "- A body of about 300 words, in 4 short paragraphs, telling a vivid, "
        "real story about Japanese culture/daily life. Sensory, intimate, not "
        "salesy. End by gently connecting the feeling to colouring.\n"
        "- British or neutral English is fine. No emojis.\n\n"
        "Return ONLY valid JSON, no markdown, in exactly this shape:\n"
        '{"subject": "...", "preheader": "...", "paragraphs": ["...", "...", "...", "..."]}'
    )

    headers = {
        "content-type": "application/json",
        "x-api-key": cfg["anthropic_api_key"],
        "anthropic-version": ANTHROPIC_VERSION,
    }
    body = {
        "model": cfg["anthropic_model"],
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        resp = requests.post(ANTHROPIC_URL, headers=headers, json=body, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        text = "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        ).strip()
        parsed = _extract_json(text)
        if parsed and parsed.get("subject") and parsed.get("paragraphs"):
            print(f"  [AI] Claude ({cfg['anthropic_model']}) で文面を生成しました。")
            return {
                "subject": parsed["subject"],
                "preheader": parsed.get("preheader", ""),
                "paragraphs": parsed["paragraphs"],
            }
        print("  [AI] 応答を解析できませんでした。テンプレートにフォールバックします。")
    except requests.RequestException as e:
        print(f"  [AI] Claude 呼び出しに失敗しました（{e}）。テンプレートにフォールバックします。")
    return None


def _extract_json(text):
    """テキストから最初の JSON オブジェクトを取り出してパースする。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def generate_from_template(theme):
    """API キーが無い／失敗時のフォールバック。themes.json の文面を使う。"""
    t = theme["template"]
    print("  [Template] themes.json の定番文面を使用しました。")
    return {
        "subject": t["subject"],
        "preheader": t.get("preheader", ""),
        "paragraphs": t["paragraphs"],
    }


# ---------------------------------------------------------------------------
# 2. ヘッダー画像の選定
# ---------------------------------------------------------------------------
def select_image(theme, cfg):
    """ヘッダー画像 URL を決める。優先順位:
    1) .env の HEADER_IMAGE_URL（固定指定）
    2) Pexels API（PEXELS_API_KEY があれば著作権フリー画像を検索）
    3) プレースホルダ画像
    """
    if cfg["header_image_url"]:
        return cfg["header_image_url"]

    if cfg["pexels_api_key"]:
        url = _fetch_pexels_image(theme["image_keywords"], cfg["pexels_api_key"])
        if url:
            print("  [画像] Pexels から著作権フリー画像を取得しました。")
            return url

    # フォールバック: テーマ名入りのプレースホルダ
    label = requests.utils.quote(theme["title"])
    print("  [画像] プレースホルダ画像を使用しました（Pexels 未設定）。")
    return f"https://placehold.co/1200x500/1a1a2e/e0e0e0/png?text={label}"


def _fetch_pexels_image(keywords, api_key):
    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": api_key},
            params={"query": keywords, "per_page": 15, "orientation": "landscape"},
            timeout=30,
        )
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if photos:
            return random.choice(photos)["src"]["large"]
    except (requests.RequestException, KeyError) as e:
        print(f"  [画像] Pexels 取得に失敗しました（{e}）。")
    return None


# ---------------------------------------------------------------------------
# 3. HTML 組み立て
# ---------------------------------------------------------------------------
def build_html(content, image_url, cfg):
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    body_html = "\n".join(
        f'<p style="margin:0 0 18px 0;">{html.escape(p)}</p>'
        for p in content["paragraphs"]
    )

    replacements = {
        "{{PREHEADER}}": html.escape(content.get("preheader", "")),
        "{{HEADER_IMAGE}}": html.escape(image_url),
        "{{TITLE}}": html.escape(content["subject"]),
        "{{BODY}}": body_html,
        "{{CTA_TEXT}}": html.escape(cfg["cta_text"]),
        "{{CTA_URL}}": html.escape(cfg["shop_url"]),
        "{{BRAND_NAME}}": html.escape(cfg["brand_name"]),
        "{{YEAR}}": str(_dt.date.today().year),
    }
    for key, val in replacements.items():
        template = template.replace(key, val)
    return template


# ---------------------------------------------------------------------------
# 4. MailerLite に下書きキャンペーンを作成
# ---------------------------------------------------------------------------
def create_mailerlite_draft(content, html_body, cfg):
    today = _dt.date.today().isoformat()
    payload = {
        "name": f"[Auto Draft] {content['subject']} ({today})",
        "type": "regular",
        "emails": [
            {
                "subject": content["subject"],
                "from_name": cfg["from_name"],
                "from": cfg["from_email"],
                "content": html_body,
            }
        ],
    }
    # 受信グループが指定されていれば紐付ける（未指定でも下書きは作れるが推奨）
    if cfg["group_id"]:
        payload["groups"] = [cfg["group_id"]]

    headers = {
        "Authorization": f"Bearer {cfg['mailerlite_api_key']}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    resp = requests.post(
        f"{MAILERLITE_BASE}/campaigns", headers=headers, json=payload, timeout=60
    )
    if resp.status_code in (200, 201):
        data = resp.json().get("data", {})
        return {"id": data.get("id"), "name": data.get("name")}
    # エラーは中身を見せて原因を分かりやすく
    raise RuntimeError(
        f"MailerLite API エラー (HTTP {resp.status_code}): {resp.text}"
    )


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="MailerLite にメルマガ下書きを自動作成する"
    )
    parser.add_argument("--theme", help="テーマキー（--list で一覧）")
    parser.add_argument("--list", action="store_true", help="テーマ一覧を表示して終了")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="MailerLite に投稿せず、HTML を output/ に保存して確認する",
    )
    args = parser.parse_args()

    themes = load_themes()

    if args.list:
        print("利用可能なテーマ:")
        for key, t in themes.items():
            print(f"  - {key:20s} : {t['title']}")
        return 0

    cfg = get_config()

    # テーマ選択
    if args.theme:
        if args.theme not in themes:
            print(f"エラー: テーマ '{args.theme}' は存在しません。--list で確認してください。")
            return 1
        theme_key = args.theme
    else:
        theme_key = random.choice(list(themes.keys()))
    theme = themes[theme_key]

    print(f"\n=== テーマ: {theme['title']} ({theme_key}) ===")

    # 1. コンテンツ生成
    content = None
    if cfg["anthropic_api_key"]:
        content = generate_with_claude(theme_key, theme, cfg)
    if content is None:
        content = generate_from_template(theme)

    # 2. 画像
    image_url = select_image(theme, cfg)

    # 3. HTML
    html_body = build_html(content, image_url, cfg)

    print(f"  件名: {content['subject']}")

    # 4a. ドライラン: ファイル保存のみ
    if args.dry_run:
        OUTPUT_DIR.mkdir(exist_ok=True)
        out_path = OUTPUT_DIR / f"preview_{theme_key}_{_dt.date.today().isoformat()}.html"
        out_path.write_text(html_body, encoding="utf-8")
        print(f"\n[dry-run] HTML を保存しました: {out_path}")
        print("ブラウザで開いて見た目を確認してください。MailerLite には投稿していません。")
        return 0

    # 4b. 本番: MailerLite に下書き作成（必須設定チェック）
    missing = [
        name
        for name, val in [
            ("MAILERLITE_API_KEY", cfg["mailerlite_api_key"]),
            ("FROM_NAME", cfg["from_name"]),
            ("FROM_EMAIL", cfg["from_email"]),
        ]
        if not val
    ]
    if missing:
        print(f"\nエラー: .env に次の必須項目がありません: {', '.join(missing)}")
        print("（先に見た目だけ確認したい場合は --dry-run を使ってください）")
        return 1

    try:
        result = create_mailerlite_draft(content, html_body, cfg)
    except RuntimeError as e:
        print(f"\n{e}")
        return 1

    print("\n下書きを作成しました。")
    print(f"  キャンペーン名: {result['name']}")
    print(f"  ID: {result['id']}")
    print("MailerLite 管理画面（スマホ可）で最終確認 → 配信ボタンを押してください。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
