"""ステップ2: 画像プロンプトのエクスポート + Codex生成画像の検収。

画像生成そのものはCodex（ChatGPT定額枠・イメージ生成モデル）に委譲する。
このスクリプトの仕事は2つ:

  A) エクスポート: 台本JSON（latest.json）から画像プロンプト一覧を
     CSV（スプレッドシート互換）と Codex 用タスク指示書に書き出す
  B) 検収: Codexが assets/images/ に納品した画像を、命名規則・解像度・
     アスペクト比でチェックし、不足/不良を報告する

使い方:
    python -m scripts.generate_images            # エクスポート + 検収
    python -m scripts.generate_images --check    # 検収のみ
"""

from __future__ import annotations

import argparse
import csv
import json
import sys

from PIL import Image

from config import settings

CSV_PATH = settings.PROMPTS_DIR / "image_prompts.csv"
TASK_PATH = settings.PROMPTS_DIR / "CODEX_TASK.md"

CODEX_TASK_TEMPLATE = """\
# Codex 画像生成タスク: 『{title}』

あなたの仕事は、YouTube動画用の画像素材 {total}枚 を生成して
`shitamachi-movie-ai/assets/images/` に保存することだ。

## 手順

1. `shitamachi-movie-ai/data/prompts/image_prompts.csv` を読み込む
2. 各行の `prompt` を使って画像を1枚生成する（スタイル指定はプロンプトに
   埋め込み済み。追加の脚色・省略はしない）
3. 生成した画像を、その行の `filename` の名前で
   `shitamachi-movie-ai/assets/images/` に PNG として保存する

## 画像の仕様（全行共通・厳守）

- アスペクト比 **16:9**、幅 **{min_width}px 以上**（推奨 1920x1080 以上）
- 画像内に **文字・ロゴ・商標を入れない**（テロップは動画編集側で載せる）
- 実在の人物・企業ロゴに似せない
- 全 {total}枚 でトーンを統一する（プロンプト末尾の共通スタイル指定に従う）

## 完了確認

全画像の保存後、以下を実行して `不足 0 / 不良 0` になることを確認する:

```
cd shitamachi-movie-ai && python -m scripts.generate_images --check
```
"""


def load_script() -> dict:
    latest = settings.SCRIPTS_DATA_DIR / "latest.json"
    if not latest.exists():
        sys.exit("台本が無い。先にステップ1（python -m scripts.generate_script）を実行せよ")
    return json.loads(latest.read_text(encoding="utf-8"))


def build_rows(script: dict) -> list[dict]:
    """台本の各章の image_prompts を、連番ファイル名付きの行に展開する。"""
    rows = []
    for sec in script["sections"]:
        for i, prompt in enumerate(sec["image_prompts"], start=1):
            rows.append({
                "filename": f"s{sec['id']:02d}_{i:02d}.png",
                "section_id": sec["id"],
                "role": sec["role"],
                "heading": sec["heading"],
                "prompt": f"{prompt}, {settings.STYLE_PROMPT}",
            })
    return rows


def export(script: dict, rows: list[dict]) -> None:
    settings.PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    # utf-8-sig: Excel / Google スプレッドシートで文字化けさせないため
    with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f, fieldnames=["filename", "section_id", "role", "heading", "prompt"]
        )
        writer.writeheader()
        writer.writerows(rows)

    TASK_PATH.write_text(
        CODEX_TASK_TEMPLATE.format(
            title=script["title"],
            total=len(rows),
            min_width=settings.MIN_IMAGE_WIDTH,
        ),
        encoding="utf-8",
    )
    print(f"  エクスポート完了: {CSV_PATH.name}（{len(rows)}枚分） / {TASK_PATH.name}")


def validate(rows: list[dict]) -> bool:
    """納品画像を検収する。全画像が揃って規格を満たせば True。"""
    missing, bad = [], []
    target = settings.VIDEO_SIZE[0] / settings.VIDEO_SIZE[1]  # 16:9
    for row in rows:
        path = settings.IMAGES_DIR / row["filename"]
        if not path.exists():
            missing.append(row["filename"])
            continue
        try:
            with Image.open(path) as im:
                w, h = im.size
        except Exception as e:
            bad.append(f"{row['filename']}: 画像として開けない（{e}）")
            continue
        if w < settings.MIN_IMAGE_WIDTH:
            bad.append(f"{row['filename']}: 幅{w}px は {settings.MIN_IMAGE_WIDTH}px 未満")
        elif abs(w / h - target) > 0.05:
            bad.append(f"{row['filename']}: アスペクト比 {w}x{h} が16:9でない")

    print(f"  検収結果: 期待 {len(rows)}枚 / 不足 {len(missing)} / 不良 {len(bad)}")
    for name in missing[:10]:
        print(f"    [不足] {name}")
    if len(missing) > 10:
        print(f"    ... 他 {len(missing) - 10} 枚")
    for msg in bad:
        print(f"    [不良] {msg}")

    if missing or bad:
        print(f"  → {TASK_PATH} をCodexに渡して生成・修正させること")
        return False
    print("  全画像OK。ステップ4（動画編集）に進める")
    return True


def run(topic: str | None = None, force: bool = False, check_only: bool = False) -> None:
    script = load_script()
    rows = build_rows(script)
    if not check_only:
        export(script, rows)
    validate(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ステップ2: 画像プロンプト出力+検収")
    parser.add_argument("--check", action="store_true", help="検収のみ実行")
    a = parser.parse_args()
    run(check_only=a.check)
