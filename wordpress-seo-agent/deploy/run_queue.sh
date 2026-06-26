#!/usr/bin/env bash
# =============================================================================
# run_queue.sh — キーワードキューから「次の1件」を処理するランナー
# -----------------------------------------------------------------------------
# cron から定期実行する想定。1回の実行で keywords.csv の先頭にある未処理
# キーワードを1件だけ処理する（= cron の発火回数で1日の記事本数を制御できる）。
#
#   exit 0 = 監査合格 → WordPress に下書き投稿済み（posted）
#   exit 2 = 規定回数(既定3回)でも不合格（failed）→ キューから外す
#   exit 1 = 実行エラー（APIエラー等）→ キューに残して次回リトライ
#
# キーワードファイルの書式（keywords.csv）:
#   - 1行に1キーワード
#   - 空行と「#」で始まる行は無視（コメント可）
# =============================================================================
set -euo pipefail

# このスクリプトのある場所から相対でパスを解決（どこに置いても動く）
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$DEPLOY_DIR")"          # wordpress-seo-agent/
cd "$AGENT_DIR"                               # .env はここから読み込まれる

QUEUE="$DEPLOY_DIR/keywords.csv"
DONE="$DEPLOY_DIR/keywords.done.csv"
LOG_DIR="$DEPLOY_DIR/logs"
LOCK="$DEPLOY_DIR/.run.lock"
VENV="${VENV_PATH:-$AGENT_DIR/.venv}"         # 必要なら VENV_PATH=... で上書き可
PYTHON="$VENV/bin/python"

mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/run-$(date +%Y%m%d).log"
log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG"; }

# 多重起動防止: 前回の実行がまだ走っていたら今回はスキップ
exec 9>"$LOCK"
if ! flock -n 9; then
  log "別の実行が進行中のためスキップしました。"
  exit 0
fi

[ -f "$QUEUE" ]  || { log "キューファイルがありません: $QUEUE"; exit 0; }
[ -x "$PYTHON" ] || { log "venv の python が見つかりません: $PYTHON （DEPLOY.md のセットアップ参照）"; exit 1; }

# 先頭の有効行（空行/コメントを除く）を1件取得し、前後の空白を除去
KEYWORD="$(grep -vE '^[[:space:]]*($|#)' "$QUEUE" | head -n1 | sed -E 's/^[[:space:]]+|[[:space:]]+$//g' || true)"
if [ -z "${KEYWORD:-}" ]; then
  log "未処理のキーワードはありません。終了します。"
  exit 0
fi

log "▶ 開始: ${KEYWORD}"
set +e
"$PYTHON" main.py "$KEYWORD" >>"$LOG" 2>&1
CODE=$?
set -e

case "$CODE" in
  0) STATUS=posted ;;   # 合格 → 下書き投稿済み
  2) STATUS=failed ;;   # 規定回数でも不合格
  *) STATUS=error  ;;   # 実行エラー
esac
log "■ 終了: ${KEYWORD} (exit=${CODE} status=${STATUS})"

# 一時的なエラーはキューに残して次回リトライ
if [ "$STATUS" = "error" ]; then
  log "エラーのためキューに残します（次回リトライ）: ${KEYWORD}"
  exit "$CODE"
fi

# posted / failed は done に記録し、キューから先頭一致の1件だけ削除
printf '%s,%s,%s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$STATUS" "$KEYWORD" >> "$DONE"
tmp="$(mktemp)"
removed=0
while IFS= read -r line || [ -n "$line" ]; do
  trimmed="$(printf '%s' "$line" | sed -E 's/^[[:space:]]+|[[:space:]]+$//g')"
  if [ "$removed" -eq 0 ] && [ "$trimmed" = "$KEYWORD" ]; then
    removed=1
    continue
  fi
  printf '%s\n' "$line" >> "$tmp"
done < "$QUEUE"
mv "$tmp" "$QUEUE"
log "キューから除去しました: ${KEYWORD} → ${STATUS}（記録: keywords.done.csv）"
