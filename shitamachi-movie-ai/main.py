"""shitamachi-movie-ai パイプライン司令塔。

4ステップを順番に実行する。各ステップは冪等（生成済みならスキップ）に
実装するので、途中で落ちても同じコマンドで再開できる。

使い方:
    python main.py                        # 全ステップ実行
    python main.py --from-step 3          # ステップ3から再開
    python main.py --topic "◯◯精工"      # 題材を指定して生成
"""

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="YouTube動画 全自動生成パイプライン")
    parser.add_argument("--from-step", type=int, default=1, choices=[1, 2, 3, 4],
                        help="このステップから再開する")
    parser.add_argument("--topic", type=str, default=None,
                        help="題材の企業・技術を指定（省略時はLLMが自動リサーチで選定）")
    args = parser.parse_args()

    steps = [
        (1, "リサーチ・台本生成", "scripts.generate_script"),
        (2, "画像素材の自動生成", "scripts.generate_images"),
        (3, "AI音声・字幕生成", "scripts.generate_audio"),
        (4, "MoviePy編集・書き出し", "scripts.edit_video"),
    ]

    for num, name, module in steps:
        if num < args.from_step:
            continue
        print(f"\n{'=' * 60}\nステップ{num}: {name}\n{'=' * 60}")
        # 各ステップのモジュールは今後の段階で実装する。
        # それぞれ run(topic=None) -> None を公開する契約とする。
        try:
            mod = __import__(module, fromlist=["run"])
        except ImportError:
            print(f"  [未実装] {module} はまだ存在しない。次の開発段階で実装する。")
            continue
        mod.run(topic=args.topic)

    return 0


if __name__ == "__main__":
    sys.exit(main())
