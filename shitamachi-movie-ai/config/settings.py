"""shitamachi-movie-ai 全体設定。

パイプライン4ステップ（台本→画像→音声→編集）が共有する定数と
パス定義をここに集約する。各ステップのスクリプトはこのファイルだけを
import すれば動く状態を保つ。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ─── パス ───
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DATA_DIR = PROJECT_ROOT / "data" / "scripts"      # 台本JSON
PROMPTS_DIR = PROJECT_ROOT / "data" / "prompts"           # 画像プロンプトCSV+Codex指示書
CANVA_DIR = PROJECT_ROOT / "data" / "canva"               # Canva入稿パッケージ
IMAGES_DIR = PROJECT_ROOT / "assets" / "images"           # 生成画像（Codexが納品）
OUTPUT_DIR = PROJECT_ROOT / "output"                      # 完成MP4（Canvaから書き出し）

# ─── APIキー ───
# 使う外部APIはClaude（台本）だけ。画像はCodex、音声・字幕・編集はCanvaの定額枠
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ─── ステップ1: 台本 ───
SCRIPT_MODEL = "claude-sonnet-5"
SECTION_COUNT = 6                  # 章の数（5〜6）
TARGET_MINUTES = (15, 20)          # 目標尺
# 日本語ナレーションは約300字/分 → 15〜20分で 4,500〜6,000字
TARGET_CHARS = (4500, 6000)

# ─── ステップ2: 画像 ───
IMAGES_PER_SECTION = 5             # 1章あたり3〜5枚
MIN_IMAGE_WIDTH = 1280             # 検収時の最低幅（これ未満は不良品）
# 世界観を統一する共通プロンプト（全シリーズ・全画像に必ず付与）
STYLE_PROMPT = (
    "CG-style illustration, dramatic and weighty atmosphere like the Japanese "
    "drama 'Shitamachi Rocket', cinematic movie-poster composition, "
    "16:9 aspect ratio, no text, no letters"
)

# ─── シリーズ定義（1チャンネル2シリーズ運用）───
# チャンネルの看板:「無名の日本人の手が、世界を動かしている物語」
# 構成の型（不安→反転→技術→ドラマ→誇り）は全シリーズ共通。
# 変わるのはリサーチの照準と画像の質感だけ。
SERIES = {
    "machikoba": {
        "label": "町工場・世界を支える無名企業",
        "research_focus": (
            "iPhone・EV・ロケット・半導体・AIチップなど世界の最先端製品の"
            "命綱を握る、実在の日本の無名中小企業・町工場を1社選定せよ。"
            "世界シェアの高いニッチ部品・素材・工程を持つ企業を優先する。"
            "有名すぎる大企業（トヨタ・ソニー等）は不可。"
        ),
        "style_suffix": "modern precision factory, machinery and steel textures",
    },
    "dento": {
        "label": "伝統×ハイテク・職人技が最先端を支える",
        "research_focus": (
            "宮大工・刀鍛冶・鋳物・漆・織物・和紙などの日本の伝統技術が、"
            "宇宙開発・医療・半導体・耐震建築などの最先端分野で実際に"
            "応用されている実在の事例・企業・工房を1つ選定せよ。"
            "逸話の真偽に特に注意し、一次情報で確認できた事実のみ扱う"
            "（『NASAが認めた』系の都市伝説を検証なしに使うことは禁止）。"
        ),
        "style_suffix": (
            "traditional Japanese craftsmanship meets high technology, "
            "warm wood, washi and forged steel textures"
        ),
    },
}
DEFAULT_SERIES = "machikoba"

# ─── ステップ3: Canva入稿パッケージ ───
# 音声・字幕・組み立て・書き出しはCanvaで行う。ここはその指示に使う定数
NARRATION_CHARS_PER_MIN = 300      # 日本語ナレーションの読み速度（尺の推定に使用）
VOICE_DIRECTION = "NHKの解説番組のような、落ち着いた知的な女性の声。ゆっくり明瞭に"
BGM_VOLUME_PCT = 12                # ナレーションを邪魔しないBGM音量の目安（%）

# ─── 動画仕様（画像検収とCanva手順書が共有）───
VIDEO_SIZE = (1920, 1080)
