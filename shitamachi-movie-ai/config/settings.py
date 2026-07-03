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
IMAGES_DIR = PROJECT_ROOT / "assets" / "images"           # 生成画像（Codexが納品）
AUDIO_DIR = PROJECT_ROOT / "assets" / "audio"             # ナレーション音声
BGM_DIR = PROJECT_ROOT / "assets" / "bgm"                 # BGM（手動配置）
SUBTITLES_DIR = PROJECT_ROOT / "assets" / "subtitles"     # SRT字幕
OUTPUT_DIR = PROJECT_ROOT / "output"                      # 完成MP4

# ─── APIキー ───
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")

# ─── プロバイダ切り替え ───
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "openai")        # "openai" | "elevenlabs"
# 画像は Codex（ChatGPT定額枠）に委譲。API課金に戻す場合のみ "dalle"/"flux"
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "codex")     # "codex" | "dalle" | "flux"

# ─── ステップ1: 台本 ───
SCRIPT_MODEL = "claude-sonnet-5"
SECTION_COUNT = 6                  # 章の数（5〜6）
TARGET_MINUTES = (15, 20)          # 目標尺
# 日本語ナレーションは約300字/分 → 15〜20分で 4,500〜6,000字
TARGET_CHARS = (4500, 6000)

# ─── ステップ2: 画像 ───
IMAGES_PER_SECTION = 5             # 1章あたり3〜5枚
IMAGE_SIZE = "1792x1024"           # DALL-E 3 の16:9相当（APIフォールバック用）
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

# ─── ステップ3: 音声 ───
# OpenAI TTS: 落ち着いた知的な女性声に最も近いのは "nova"（"shimmer" も候補）
OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
OPENAI_TTS_VOICE = "nova"
OPENAI_TTS_INSTRUCTIONS = (
    "NHKの解説番組のナレーターのように、落ち着いた知的な女性の声で、"
    "ゆっくり明瞭に、聞き取りやすく読み上げてください。"
)
WHISPER_MODEL = "whisper-1"        # 字幕タイムスタンプ取得用

# ─── ステップ4: 編集 ───
VIDEO_SIZE = (1920, 1080)
VIDEO_FPS = 30
BGM_VOLUME = 0.12                  # ナレーションを邪魔しない音量
CROSSFADE_SEC = 0.7                # 画像切り替えのクロスフェード
SUBTITLE_FONT_SIZE = 52
SUBTITLE_MARGIN_BOTTOM = 80
