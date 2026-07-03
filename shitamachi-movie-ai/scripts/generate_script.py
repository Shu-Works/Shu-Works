"""ステップ1: リサーチ・台本生成。

Claude API（Web検索ツール）で実在の「世界シェアトップの日本のニッチ
中小企業・町工場」をリサーチし、構成の型（不安→反転→技術解説→感動）に
沿った6章構造の台本JSONを data/scripts/ に出力する。

冒頭3秒が勝負のため、台本生成後に「フック磨き込みパス」を必ず実行する:
  1コール目: リサーチ + 台本全体の生成（Web検索あり）
  2コール目: 冒頭フックを5案生成 → 3基準で自己採点 → 最強の1案に差し替え

使い方:
    python -m scripts.generate_script                # 自動で題材選定
    python -m scripts.generate_script --topic "◯◯精工"
    python -m scripts.generate_script --force        # 生成済みでも作り直す
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime

from anthropic import Anthropic
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

LATEST_PATH = settings.SCRIPTS_DATA_DIR / "latest.json"

VALID_ROLES = ["hook", "reversal", "tech_1", "tech_2", "drama", "ending"]

# 冒頭で使った瞬間に視聴者が離脱する定型句。1文字目からの使用を禁止する
BANNED_OPENINGS = [
    "皆さん", "みなさん", "こんにちは", "こんばんは", "どうも",
    "今日は", "今回は", "本日は", "この動画", "ご視聴", "チャンネル",
    "さて", "ようこそ",
]


# ─────────────────────────────────────────────
# 台本JSONスキーマ（ステップ間の契約。README準拠）
# ─────────────────────────────────────────────

class Section(BaseModel):
    id: int
    role: str
    heading: str
    narration: str = Field(min_length=200)
    image_prompts: list[str] = Field(min_length=3, max_length=5)

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"role は {VALID_ROLES} のいずれか。'{v}' は不正")
        return v


class Script(BaseModel):
    title: str = Field(min_length=5)
    company: str
    sources: list[str] = Field(min_length=1)
    sections: list[Section] = Field(min_length=5, max_length=6)

    @model_validator(mode="after")
    def check_structure(self) -> "Script":
        roles = [s.role for s in self.sections]
        if roles[0] != "hook":
            raise ValueError("第1章の role は必ず 'hook'")
        if roles[-1] != "ending":
            raise ValueError("最終章の role は必ず 'ending'")

        hook = self.sections[0].narration
        for banned in BANNED_OPENINGS:
            if hook.lstrip("「『（(").startswith(banned):
                raise ValueError(
                    f"冒頭が挨拶・定型句『{banned}』で始まっている。"
                    "1文目から衝撃の事実・数字・固有名詞で始めること"
                )
        first_sentence = re.split(r"[。！？!?]", hook, maxsplit=1)[0]
        if len(first_sentence) > 80:
            raise ValueError(
                f"冒頭の1文が{len(first_sentence)}文字と長すぎる。"
                "3秒で読める80文字以内の短い一撃にすること"
            )
        head = hook[:200]
        if not (re.search(r"[0-9０-９]", head) or "？" in head):
            raise ValueError(
                "冒頭200文字に数字も問いかけも無い。具体的な数字か"
                "強烈な問いで情報ギャップを作ること"
            )

        total = sum(len(s.narration) for s in self.sections)
        lo, hi = settings.TARGET_CHARS
        if total < lo - 500:
            raise ValueError(
                f"ナレーション合計が{total}文字しかない。15〜20分尺には"
                f"{lo}〜{hi}文字が必要。tech_1 / tech_2 / drama を、"
                "具体的なエピソード・数字・証言で厚くすること"
            )
        return self


# ─────────────────────────────────────────────
# プロンプト
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """\
あなたはNHKスペシャルと「下町ロケット」の両方を手がけた放送作家である。
40〜50代男性・ビジネス層・ものづくりと逆転劇が好きな視聴者に向けた
YouTube解説動画（15〜20分）の台本を書く。

# 絶対原則
- 実在の企業・実在の事実のみを扱う。Web検索で確認できた事実だけを書く。
  確認できない数字・取引先・エピソードは絶対に書かない（名誉毀損リスク）
- 【チャンネルの憲法】「すごい」「世界が絶賛」「土下座」「日本の誇り」等の
  称賛語・自画自賛の言葉をナレーションで使わない。事実と数字と物語だけを
  積み、誇りを感じるのは視聴者の仕事として残す。プロジェクトXが
  「日本すごい」と一度も言わずに視聴者を泣かせたのと同じ構造を守る
- ナレーションは丁寧語（です・ます調）。聞き取りやすい放送用の文体。
  1文は短く。難しい漢語は開く。数字は必ず具体的に
- 構成の型: ①冒頭の不安 → ②驚きの反転 → ③技術の証明（2章）→
  ④開発の人間ドラマ → ⑤誇りと感動のエンディング
- 技術章（tech_1 / tech_2）は「解説」ではなく「証明」である。
  反転（②）が真実である動かぬ証拠——特許・世界シェアの数字・
  取引の事実・第三者の評価——を積み上げる。形容詞で語らず、証拠で示す

# 冒頭フック（最重要・視聴維持率のすべてが最初の3秒で決まる）
- 挨拶・自己紹介・「今日は〜を紹介します」は死。絶対に書かない
- 1文目（80文字以内）から始める:
  衝撃の事実 or 具体的な数字 or 固有名詞の意外な組み合わせ
  例の型: 「Appleが、たった一晩で生産停止に追い込まれる——
  その鍵を握るのは、従業員わずか38人の日本の町工場です」
- 冒頭30秒以内に「オープンループ」を最低2つ仕掛ける:
  「なぜ世界最大の企業が、この無名の工場に頭を下げたのか」のように
  答えを後半まで引っ張る謎を明示する
- 各章の終わりにも次章への引き（クリフハンガー）を1文入れる

# 画像プロンプト
各章に3〜5個、英語で書く。人物は特定個人に似せない。実在ロゴ・
商標・文字は入れない。各プロンプトは章の物語の異なる瞬間を切り取る。
"""

JSON_SPEC = f"""\
出力は以下のJSONのみ。JSON以外の文章・前置き・後書きは一切出力しない。

{{
  "title": "YouTube動画タイトル（衝撃と具体性。40文字以内）",
  "company": "企業名",
  "sources": ["リサーチで実際に参照したURL（最低3つ）"],
  "sections": [
    {{
      "id": 1,
      "role": "hook",        // 順に hook / reversal / tech_1 / tech_2 / drama / ending
      "heading": "章タイトル",
      "narration": "ナレーション本文",
      "image_prompts": ["English prompt 1", "English prompt 2", "English prompt 3"]
    }}
  ]
}}

文字数配分（ナレーション合計 {settings.TARGET_CHARS[0]}〜{settings.TARGET_CHARS[1]}文字）:
hook 600 / reversal 800 / tech_1 1200 / tech_2 1200 / drama 1200 / ending 600
"""


def build_research_prompt(topic: str | None, series: str) -> str:
    focus = settings.SERIES[series]["research_focus"]
    if topic:
        subject = (
            f"題材は「{topic}」とする。この企業・技術についてWeb検索で徹底的に調べよ。\n"
            f"シリーズの照準: {focus}"
        )
    else:
        subject = f"Web検索でリサーチし、以下の照準で題材を選定せよ。\n{focus}"
    return f"{subject}\n\nリサーチ結果をもとに台本を書け。\n\n{JSON_SPEC}"


HOOK_REFINE_PROMPT = """\
以下はYouTube動画台本の冒頭章（hook）である。最初の3秒で視聴者を
掴めなければこの動画は存在しないのと同じだ。冒頭を磨き込め。

# 手順
1. 冒頭の書き出し候補を5案作る。それぞれ異なる型を使う:
   A 衝撃事実型 / B 危機感型 / C 謎かけ型 / D 固有名詞ギャップ型 / E 数字の暴力型
2. 各案を3基準で1〜10点で自己採点する:
   意外性（3秒で「え？」と思わせるか）/ 具体性（数字・固有名詞）/
   情報ギャップ（続きを見ないと気が済まないか）
3. 合計点が最高の1案を選び、hook章全体を書き直す。
   選んだ書き出しから元の narration の内容へ自然に接続し、
   オープンループを2つ以上維持し、文字数は元の8割以上を保つ。

# 制約
- 挨拶・「今日は」等の定型句は死。1文目は80文字以内
- 事実の改変は禁止。元の台本にある事実だけを使う
- 丁寧語（です・ます調）を維持

# 元のhook章
{hook_narration}

# 動画全体の文脈（参考）
タイトル: {title} / 企業: {company}
続く章: {section_summaries}

# 出力（JSONのみ）
{{
  "candidates": [
    {{"type": "A", "text": "書き出し案", "scores": {{"意外性": 0, "具体性": 0, "情報ギャップ": 0}}}}
  ],
  "best": "A",
  "revised_hook_narration": "書き直したhook章の全文"
}}
"""


# ─────────────────────────────────────────────
# API呼び出し
# ─────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
def call_claude(client: Anthropic, user_prompt: str, use_search: bool) -> str:
    kwargs: dict = dict(
        model=settings.SCRIPT_MODEL,
        max_tokens=20000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    if use_search:
        kwargs["tools"] = [
            {"type": "web_search_20250305", "name": "web_search", "max_uses": 8}
        ]
    response = client.messages.create(**kwargs)
    return "".join(b.text for b in response.content if b.type == "text")


def extract_json(text: str) -> dict:
    """LLM出力からJSONを取り出す。コードフェンス・前後の文章に耐える。"""
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("出力にJSONが見つからない")
    return json.loads(text[start : end + 1])


# ─────────────────────────────────────────────
# フック磨き込みパス
# ─────────────────────────────────────────────

def refine_hook(client: Anthropic, script: Script) -> tuple[Script, list[dict]]:
    """冒頭フックを5案生成→自己採点→最強案でhook章を書き直す。"""
    summaries = " / ".join(f"{s.role}:{s.heading}" for s in script.sections[1:])
    prompt = HOOK_REFINE_PROMPT.format(
        hook_narration=script.sections[0].narration,
        title=script.title,
        company=script.company,
        section_summaries=summaries,
    )
    raw = call_claude(client, prompt, use_search=False)
    result = extract_json(raw)

    revised = result.get("revised_hook_narration", "")
    candidates = result.get("candidates", [])
    original_len = len(script.sections[0].narration)

    if len(revised) < original_len * 0.6:
        print("  [警告] 磨き込み結果が短すぎるため元のhookを維持する")
        return script, candidates

    data = script.model_dump()
    data["sections"][0]["narration"] = revised
    try:
        return Script(**data), candidates
    except ValidationError as e:
        print(f"  [警告] 磨き込み結果がフック品質基準を満たさず元を維持: {e.errors()[0]['msg']}")
        return script, candidates


# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────

def run(topic: str | None = None, force: bool = False, no_search: bool = False,
        series: str = settings.DEFAULT_SERIES) -> None:
    if series not in settings.SERIES:
        sys.exit(f"series は {list(settings.SERIES)} のいずれか。'{series}' は不正")
    if LATEST_PATH.exists() and not force:
        existing = json.loads(LATEST_PATH.read_text(encoding="utf-8"))
        print(f"  台本は生成済み: 『{existing['title']}』 → スキップ（作り直すには --force）")
        return

    if not settings.ANTHROPIC_API_KEY:
        sys.exit("ANTHROPIC_API_KEY が未設定。.env を確認せよ")

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    use_search = not no_search
    if no_search:
        print("  [警告] Web検索なしモード。事実確認されていない台本になる。公開前の人間チェック必須")

    print(f"  シリーズ: {settings.SERIES[series]['label']}")
    # 生成 → スキーマ検証 → 不合格ならエラー内容をフィードバックして再生成
    prompt = build_research_prompt(topic, series)
    script: Script | None = None
    feedback = ""
    for attempt in range(1, 4):
        print(f"  台本生成 試行 {attempt}/3 ...")
        raw = call_claude(client, prompt + feedback, use_search=use_search)
        try:
            script = Script(**extract_json(raw))
            break
        except (ValueError, ValidationError) as e:
            msg = str(e)
            print(f"  [不合格] {msg[:200]}")
            feedback = (
                f"\n\n# 前回の出力は以下の理由で不合格だった。修正して再出力せよ:\n{msg}"
            )
    if script is None:
        sys.exit("3回試行しても品質基準を満たす台本が生成できなかった")

    print(f"  台本生成OK: 『{script.title}』（{script.company}）")
    total = sum(len(s.narration) for s in script.sections)
    print(f"  合計 {total}文字 / {len(script.sections)}章 / 出典 {len(script.sources)}件")

    # 冒頭3秒の磨き込み
    print("  冒頭フック磨き込みパス実行中 ...")
    script, candidates = refine_hook(client, script)
    first = re.split(r"[。！？!?]", script.sections[0].narration, maxsplit=1)[0]
    print(f"  冒頭1文目: 「{first}」")

    # 保存（タイムスタンプ版 + latest.json。候補案も人間レビュー用に残す）
    payload = script.model_dump()
    payload["_meta"] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": settings.SCRIPT_MODEL,
        "series": series,  # ステップ2が画像の質感（style_suffix）を切り替えるのに使う
        "web_search": use_search,
        "hook_candidates": candidates,
        "human_verified": False,  # 公開前に人間が sources と照合したら true にする
    }
    settings.SCRIPTS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = settings.SCRIPTS_DATA_DIR / f"script_{stamp}.json"
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    archive.write_text(text, encoding="utf-8")
    LATEST_PATH.write_text(text, encoding="utf-8")
    print(f"  保存: {archive.name} / latest.json 更新")
    print("  [重要] 公開前に sources のURLと本文を人間が照合すること（_meta.human_verified）")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ステップ1: リサーチ・台本生成")
    parser.add_argument("--topic", default=None, help="題材の企業・技術（省略時は自動選定）")
    parser.add_argument("--series", default=settings.DEFAULT_SERIES,
                        choices=list(settings.SERIES),
                        help="シリーズ: machikoba=町工場 / dento=伝統×ハイテク")
    parser.add_argument("--force", action="store_true", help="生成済みでも作り直す")
    parser.add_argument("--no-search", action="store_true",
                        help="Web検索を使わない（非推奨・事実未確認になる）")
    a = parser.parse_args()
    run(topic=a.topic, force=a.force, no_search=a.no_search, series=a.series)
