#!/bin/zsh
set -e

cd "$(dirname "$0")"

echo "X収集専用のtwitter-cliを、AI実務レーダー内の隔離環境へ入れます。"
echo "本アカウントではなく、収集専用XアカウントでログインしたChromeプロファイルを使ってください。"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3が見つかりません。"
  read -k 1 "?何かキーを押すと閉じます。"
  exit 1
fi

python3 - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10以上が必要です。")
print("Python:", sys.version.split()[0])
PY

VENV=".venv-twitter-cli"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install --upgrade twitter-cli

echo
echo "Chromeのプロファイル候補:"
CHROME_ROOT="$HOME/Library/Application Support/Google/Chrome"
if [[ -d "$CHROME_ROOT" ]]; then
  find "$CHROME_ROOT" -maxdepth 1 -type d \( -name "Default" -o -name "Profile *" \) -print | sed 's#^.*/#  #'
else
  echo "  Chromeの設定フォルダが見つかりません。"
fi

echo
read "PROFILE?収集専用XアカウントでログインしたChromeプロファイル名を入力してください（例: Profile 2）: "
if [[ -z "$PROFILE" ]]; then
  echo "プロファイルが未指定のため、X収集は有効化しません。"
  read -k 1 "?何かキーを押すと閉じます。"
  exit 1
fi

cat > .ai-radar-env <<EOF
export AI_RADAR_X_ENABLED=0
export TWITTER_BROWSER=chrome
export TWITTER_CHROME_PROFILE=${(q)PROFILE}
EOF

export PATH="$PWD/$VENV/bin:$PATH"
export TWITTER_BROWSER=chrome
export TWITTER_CHROME_PROFILE="$PROFILE"

echo
echo "読み取りテストを実行します。投稿・いいね・フォロー等は行いません。"
if twitter feed --max 1 --json >/dev/null 2>&1; then
  cat > .ai-radar-env <<EOF
export AI_RADAR_X_ENABLED=1
export TWITTER_BROWSER=chrome
export TWITTER_CHROME_PROFILE=${(q)PROFILE}
EOF
  echo "X収集を有効化しました。次回から start-local.command で自動収集します。"
else
  echo "認証確認に失敗しました。"
  echo "指定したChromeプロファイルで、収集専用Xアカウントへログインしてから、この設定をもう一度実行してください。"
fi

read -k 1 "?何かキーを押すと閉じます。"
