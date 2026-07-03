"""shitamachi-movie-ai パイプライン司令塔。

3ステップを順番に実行する。各ステップは冪等（生成済みならスキップ）に
実装するので、途中で落ちても同じコマンドで再開できる。

  1. 台本生成（Claude + Web検索）
  2. 画像発注書の出力 + Codex納品画像の検収
  3. Canva入稿パッケージの出力
  → 以降（音声・字幕・組み立て・MP4書き出し）は Canva 上で行う。
    手順は data/canva/CANVA_TASK.md に自動生成される

使い方:
    python main.py                        # 全ステップ実行
    python main.py --from-step 3          # ステップ3から再開
    python main.py --topic "◯◯精工"      # 題材を指定して生成
"""

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="YouTube動画 全自動生成パイプライン")
    parser.add_argument("--from-step", type=int, default=1, choices=[1, 2, 3],
                        help="このステップから再開する")
    parser.add_argument("--topic", type=str, default=None,
                        help="題材の企業・技術を指定（省略時はLLMが自動リサーチで選定）")
    parser.add_argument("--series", type=str, default=None,
                        help="シリーズ: machikoba=町工場 / dento=伝統×ハイテク")
    args = parser.parse_args()

    steps = [
        (1, "リサーチ・台本生成", "scripts.generate_script"),
        (2, "画像発注書の出力 + 納品検収", "scripts.generate_images"),
        (3, "Canva入稿パッケージの出力", "scripts.export_canva"),
    ]

    for num, name, module in steps:
        if num < args.from_step:
            continue
        print(f"\n{'=' * 60}\nステップ{num}: {name}\n{'=' * 60}")
        # 各ステップは run(topic=None) -> None を公開する契約
        mod = __import__(module, fromlist=["run"])
        kwargs = {"topic": args.topic}
        # シリーズは台本生成だけが受け取る（以降のステップは台本JSONの_metaから読む）
        if num == 1 and args.series:
            kwargs["series"] = args.series
        mod.run(**kwargs)

    print("\nパイプライン完了。以降は data/canva/CANVA_TASK.md の手順でCanva上で組み立てる")
    return 0


if __name__ == "__main__":
    sys.exit(main())
