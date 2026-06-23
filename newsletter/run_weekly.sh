#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# 毎週の自動下書き作成用ラッパースクリプト（cron から呼ばれる想定）
# 実行結果は newsletter/weekly.log に追記される。
# -----------------------------------------------------------------------------
set -euo pipefail

# このスクリプト自身のあるディレクトリへ移動（cron はカレントが固定でないため必須）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 仮想環境を使っている場合はここで有効化（使わないなら次の2行は不要）
# shellcheck disable=SC1091
[ -f ".venv/bin/activate" ] && source ".venv/bin/activate"

echo "===== $(date '+%Y-%m-%d %H:%M:%S') 実行開始 =====" >> weekly.log
# テーマ未指定 = ランダム。特定テーマにしたいなら --theme four_seasons 等を付ける
python3 create_draft.py >> weekly.log 2>&1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') 実行終了 =====" >> weekly.log
echo "" >> weekly.log
