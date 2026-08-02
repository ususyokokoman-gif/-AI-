#!/bin/zsh
set -u

cd "$(dirname "$0")"

# リポジトリ本体を更新。失敗しても手元の版で続行する。
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git pull --ff-only || echo "GitHubからの更新に失敗したため、手元の版で続行します。"
fi

# 公開情報を再収集し、twitter-cliが使える場合だけXも追加する。
# ローカル結果はgit管理外の data/local-items.json に保存する。
echo "AI実務情報を更新しています…"
if command -v python3 >/dev/null 2>&1; then
  PYTHONUNBUFFERED=1 python3 scripts/collect_local.py \
    || echo "一部の収集に失敗しました。前回データまたはGitHub上のデータで表示します。"
else
  echo "python3が見つからないため、既存データで表示します。"
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
