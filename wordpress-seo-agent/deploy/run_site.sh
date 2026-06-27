#!/usr/bin/env bash
# =============================================================================
# run_site.sh <site> — マルチサイト対応ランナー
# -----------------------------------------------------------------------------
# コード本体（main.py / .venv）は共通。サイト固有の設定・データ・キューは
# ~/sites/<site>/ に置き、そこを実行ディレクトリにして 1 キーワード処理する。
#
#   使い方:  run_site.sh eyesclinic
#   cron 例: 0 22 * * * /root/Shu-Works/wordpress-seo-agent/deploy/run_site.sh eyesclinic >> ...
# =============================================================================
set -euo pipefail

SITE="${1:-}"
[ -n "$SITE" ] || { echo "使い方: run_site.sh <site>"; exit 1; }

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODE_DIR="$(dirname "$DEPLOY_DIR")"               # ~/Shu-Works/wordpress-seo-agent
SITES_ROOT="${SITES_ROOT:-$HOME/sites}"
SITE_DIR="$SITES_ROOT/$SITE"
PYTHON="$CODE_DIR/.venv/bin/python"

[ -d "$SITE_DIR" ] || { echo "サイト設定がありません: $SITE_DIR"; exit 1; }
[ -x "$PYTHON" ]   || { echo "venv が見つかりません: $PYTHON"; exit 1; }
cd "$SITE_DIR"                                     # .env / clinics.json 等はここから読む

QUEUE="$SITE_DIR/keywords.csv"
DONE="$SITE_DIR/keywords.done.csv"
LOG_DIR="$SITE_DIR/logs"
LOCK="$SITE_DIR/.run.lock"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/run-$(date +%Y%m%d).log"
log() { printf '%s [%s] %s\n' "$(date '+%F %T')" "$SITE" "$*" | tee -a "$LOG"; }

exec 9>"$LOCK"
if ! flock -n 9; then log "別の実行が進行中のためスキップ"; exit 0; fi
[ -f "$QUEUE" ] || { log "キューがありません: $QUEUE"; exit 0; }

KEYWORD="$(grep -vE '^[[:space:]]*($|#)' "$QUEUE" | head -n1 | sed -E 's/^[[:space:]]+|[[:space:]]+$//g' || true)"
[ -n "${KEYWORD:-}" ] || { log "未処理キーワードなし"; exit 0; }

log "▶ 開始: ${KEYWORD}"
set +e
"$PYTHON" "$CODE_DIR/main.py" "$KEYWORD" >>"$LOG" 2>&1
CODE=$?
set -e
case "$CODE" in 0) ST=posted;; 2) ST=failed;; *) ST=error;; esac
log "■ 終了: ${KEYWORD} (exit=${CODE} status=${ST})"

if [ "$ST" = "error" ]; then log "エラーのためキューに残す（次回リトライ）"; exit "$CODE"; fi
printf '%s,%s,%s\n' "$(date '+%F %T')" "$ST" "$KEYWORD" >> "$DONE"
tmp="$(mktemp)"; removed=0
while IFS= read -r line || [ -n "$line" ]; do
  t="$(printf '%s' "$line" | sed -E 's/^[[:space:]]+|[[:space:]]+$//g')"
  if [ "$removed" -eq 0 ] && [ "$t" = "$KEYWORD" ]; then removed=1; continue; fi
  printf '%s\n' "$line" >> "$tmp"
done < "$QUEUE"
mv "$tmp" "$QUEUE"
log "キューから除去: ${KEYWORD} → ${ST}"
