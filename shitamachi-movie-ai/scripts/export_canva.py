"""ステップ3: Canva入稿パッケージのエクスポート。

音声（AIナレーター）・字幕（自動キャプション）・最終組み立て・MP4書き出しは
Canva（定額枠）で行う。このスクリプトの仕事は、そのCanva作業が最速で終わる
入稿パッケージを data/canva/ に書き出すこと:

  - narration/section_XX_<role>.txt … 章ごとのナレ原稿（AIナレーターに貼るだけ）
  - storyboard.csv                  … 章×画像×推定尺の設計図（スプレッドシート互換）
  - CANVA_TASK.md                   … 組み立て手順書（公開前チェックリスト付き）

使い方:
    python -m scripts.export_canva
"""

from __future__ import annotations

import argparse
import csv
import json
import sys

from config import settings

NARRATION_DIR = settings.CANVA_DIR / "narration"
STORYBOARD_PATH = settings.CANVA_DIR / "storyboard.csv"
TASK_PATH = settings.CANVA_DIR / "CANVA_TASK.md"


def load_script() -> dict:
    latest = settings.SCRIPTS_DATA_DIR / "latest.json"
    if not latest.exists():
        sys.exit("台本が無い。先にステップ1（python -m scripts.generate_script）を実行せよ")
    return json.loads(latest.read_text(encoding="utf-8"))


def sec_to_mmss(seconds: float) -> str:
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def build_plan(script: dict) -> list[dict]:
    """章ごとの尺・画像・原稿ファイル名を計算した設計図を作る。"""
    plan = []
    for sec in script["sections"]:
        n_chars = len(sec["narration"])
        duration = n_chars / settings.NARRATION_CHARS_PER_MIN * 60  # 秒
        images = [f"s{sec['id']:02d}_{i:02d}.png"
                  for i in range(1, len(sec["image_prompts"]) + 1)]
        plan.append({
            "section_id": sec["id"],
            "role": sec["role"],
            "heading": sec["heading"],
            "narration": sec["narration"],
            "narration_file": f"section_{sec['id']:02d}_{sec['role']}.txt",
            "duration_sec": duration,
            "duration": sec_to_mmss(duration),
            "images": images,
            "sec_per_image": round(duration / len(images), 1) if images else 0,
        })
    return plan


def export(script: dict, plan: list[dict]) -> None:
    NARRATION_DIR.mkdir(parents=True, exist_ok=True)

    for p in plan:
        (NARRATION_DIR / p["narration_file"]).write_text(
            p["narration"], encoding="utf-8"
        )

    with STORYBOARD_PATH.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "section_id", "role", "heading", "duration",
            "sec_per_image", "images", "narration_file", "narration",
        ])
        writer.writeheader()
        for p in plan:
            row = {k: p[k] for k in writer.fieldnames if k != "images"}
            row["images"] = "; ".join(p["images"])
            writer.writerow(row)

    total = sum(p["duration_sec"] for p in plan)
    n_images = sum(len(p["images"]) for p in plan)
    section_lines = "\n".join(
        f"| {p['section_id']} | {p['heading']} | {p['duration']} | "
        f"{len(p['images'])}枚 | 約{p['sec_per_image']}秒/枚 | `{p['narration_file']}` |"
        for p in plan
    )

    TASK_PATH.write_text(f"""\
# Canva 組み立て手順書: 『{script["title"]}』

- 想定尺: **約{sec_to_mmss(total)}**（ナレーション{sum(len(p["narration"]) for p in plan)}文字 ÷ {settings.NARRATION_CHARS_PER_MIN}文字/分）
- 画像: {n_images}枚（`assets/images/`）/ ナレ原稿: {len(plan)}章（`data/canva/narration/`）

## 章別設計図

| 章 | 見出し | 推定尺 | 画像 | 表示時間 | ナレ原稿 |
| --- | --- | --- | --- | --- | --- |
{section_lines}

## 手順

1. **デザイン作成**: Canvaで「動画（1920×1080）」を新規作成
2. **画像配置**: 章ごとにページを分け、`assets/images/` の連番画像を順に
   全画面配置。各ページの表示時間は上表の「表示時間」に合わせる。
   **全画像に「ズーム」系アニメーション（ゆっくり拡大）を付けて
   静止画の間延びを消す**（1枚30秒超の表示に耐えるのはこれが前提）
3. **ナレーション**: AIナレーター（またはText to Speechアプリ）に
   `narration/` の各章テキストを貼り付けて生成。
   **声の指定: {settings.VOICE_DIRECTION}**
   章の音声を該当ページ範囲に配置し、画像の表示時間を音声実尺に微調整する
4. **字幕**: 自動キャプションを有効化（表示位置: 下部 / 白文字・黒フチ /
   1行あたり20文字目安）。**誤変換は必ず目視で直す**（固有名詞・数字が命）
5. **BGM**: エピック・オーケストラ調（Canvaオーディオ素材の商用可のもの）。
   音量は**{settings.BGM_VOLUME_PCT}%前後**。ナレーションに被せない
6. **書き出し**: MP4・1080p で `output/` に保存

## 公開前チェックリスト（1つでも未達なら公開しない）

- [ ] 台本JSONの `sources` のURLと本文を照合した（`_meta.human_verified` を true に）
- [ ] ナレーションに称賛語（すごい・世界が絶賛 等）が混入していない
- [ ] 冒頭3秒を実機で再生し、1文目が音声・字幕とも即座に立ち上がる
- [ ] 字幕の固有名詞・数字の誤変換ゼロ
- [ ] BGMの商用ライセンスを確認した
""", encoding="utf-8")

    print(f"  エクスポート完了: data/canva/")
    print(f"    - narration/ {len(plan)}章分 / storyboard.csv / CANVA_TASK.md")
    print(f"    - 想定尺 約{sec_to_mmss(total)} / 画像{n_images}枚")

    # 画像がまだ揃っていなければ知らせる（ここでは止めない。Canva作業前に必要）
    missing = [f for p in plan for f in p["images"]
               if not (settings.IMAGES_DIR / f).exists()]
    if missing:
        print(f"  [注意] 画像が{len(missing)}枚未納品。Canva作業前にステップ2の検収を通すこと")


def run(topic: str | None = None, force: bool = False) -> None:
    script = load_script()
    export(script, build_plan(script))


if __name__ == "__main__":
    argparse.ArgumentParser(description="ステップ3: Canva入稿パッケージ出力").parse_args()
    run()
