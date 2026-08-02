#!/bin/zsh
set -e

cd "$(dirname "$0")"

# 最新データを取得。失敗しても手元のデータで起動する。
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git pull --ff-only || echo "最新データの取得に失敗したため、手元のデータで表示します。"
fi

PORT=8765
URL="http://127.0.0.1:${PORT}"
PID_FILE=".ai-radar-server.pid"

if [[ -f "$PID_FILE" ]]; then
  OLD_PID=$(cat "$PID_FILE" 2>/dev/null || true)
  if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    open "$URL"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

python3 -m http.server "$PORT" --bind 127.0.0.1 > /tmp/ai-practice-radar.log 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" > "$PID_FILE"

sleep 1
if ! kill -0 "$SERVER_PID" 2>/dev/null; then
  echo "起動できませんでした。ログ: /tmp/ai-practice-radar.log"
  read -k 1 "?何かキーを押すと閉じます。"
  exit 1
fi

open "$URL"
echo "AI実務レーダーをローカルで開きました。"
echo "外部公開はせず、このMacの 127.0.0.1:${PORT} だけで表示しています。"
