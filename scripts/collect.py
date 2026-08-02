import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

OUT = "data/items.json"
API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "zun-ai-practice-radar",
    "X-GitHub-Api-Version": "2022-11-28",
}
if os.getenv("GITHUB_TOKEN"):
    HEADERS["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]

# 無差別検索は禁止。Zunの実務と関係が深く、公式または実績が確認できる情報源だけを追跡する。
SOURCES = [
    {
        "repo": "openai/codex",
        "label": "OpenAI Codex",
        "category": "AI開発エージェント",
        "summary": "Codex CLIとクラウド型コーディングエージェントの公式更新です",
        "use_case": "Codexへ任せられる開発作業、承認方法、サンドボックス、並列実行の変化を把握できます",
        "action": "自分の検証用リポジトリで、変更点を一つだけ再現して採用可否を判断する",
        "base_score": 94,
        "tags": ["Codex", "開発自動化", "公式"],
    },
    {
        "repo": "anthropics/claude-code",
        "label": "Claude Code",
        "category": "AI開発エージェント",
        "summary": "Claude Codeの機能追加、修正、運用上の注意点に関する公式更新です",
        "use_case": "Codexとの役割分担、長時間タスク、権限管理、エージェント運用の改善判断に使えます",
        "action": "現在の開発手順に影響する変更だけを確認し、既存フローをむやみに変えない",
        "base_score": 94,
        "tags": ["Claude Code", "開発自動化", "公式"],
    },
    {
        "repo": "google-gemini/gemini-cli",
        "label": "Gemini CLI",
        "category": "AI開発エージェント",
        "summary": "Google公式のGemini CLIに関する機能追加と修正です",
        "use_case": "Codex・Claude Code以外の選択肢として、長い文脈やGoogle連携を検証できます",
        "action": "無料枠や既存Google環境で代替価値が出る作業だけを小さく試す",
        "base_score": 88,
        "tags": ["Gemini CLI", "開発自動化", "公式"],
    },
    {
        "repo": "openai/openai-agents-python",
        "label": "OpenAI Agents SDK",
        "category": "AIエージェント",
        "summary": "OpenAI公式のエージェント開発SDKに関する更新です",
        "use_case": "複数エージェント、ツール実行、引き継ぎ、監視を業務システムへ組み込む判断材料になります",
        "action": "LINE会員基盤や内部支援ツールへ直結する機能だけをサンプルで検証する",
        "base_score": 91,
        "tags": ["Agents SDK", "エージェント設計", "公式"],
    },
    {
        "repo": "modelcontextprotocol/servers",
        "label": "MCP公式サーバー集",
        "category": "MCP・外部連携",
        "summary": "AIから外部サービスやデータへ接続するMCPの公式実装例です",
        "use_case": "Google Drive、GitHub、データベース等をAIへ安全につなぐ際の基準として使えます",
        "action": "導入前に権限範囲、読み書き可否、秘密情報の扱いを確認する",
        "base_score": 92,
        "tags": ["MCP", "外部連携", "公式"],
    },
    {
        "repo": "openai/openai-cookbook",
        "label": "OpenAI Cookbook",
        "category": "実装例・ノウハウ",
        "summary": "OpenAI公式の実装例、設計例、評価方法に関する更新です",
        "use_case": "新機能の宣伝ではなく、実際にどう組み込むかをコードと手順で確認できます",
        "action": "相談案件や自作ツールに近い例だけを選び、再現してから知識化する",
        "base_score": 90,
        "tags": ["実装例", "評価", "公式"],
    },
    {
        "repo": "anthropics/anthropic-cookbook",
        "label": "Anthropic Cookbook",
        "category": "実装例・ノウハウ",
        "summary": "Claudeを業務やシステムへ組み込む公式実装例の更新です",
        "use_case": "Claude API、ツール利用、長文処理、評価設計の具体例を確認できます",
        "action": "OpenAI側の実装例と比較し、モデル依存を避けられる設計を選ぶ",
        "base_score": 88,
        "tags": ["Claude", "実装例", "公式"],
    },
    {
        "repo": "n8n-io/n8n",
        "label": "n8n",
        "category": "業務自動化",
        "summary": "ノーコード・ローコードで業務フローを自動化するn8nの更新です",
        "use_case": "メール、表計算、Web API、AIをつなぎ、中小企業の定型業務を自動化できます",
        "action": "実案件の一工程だけを自動化し、削減時間とエラー率を測る",
        "base_score": 84,
        "tags": ["n8n", "業務自動化", "ワークフロー"],
    },
    {
        "repo": "langgenius/dify",
        "label": "Dify",
        "category": "AI業務アプリ",
        "summary": "RAG、チャットボット、エージェント型業務アプリを構築するDifyの更新です",
        "use_case": "社内文書検索、相談受付、補助金候補整理などの試作を短期間で作れます",
        "action": "機密情報を入れず、公開資料だけで小規模な業務試作を行う",
        "base_score": 82,
        "tags": ["Dify", "RAG", "業務アプリ"],
    },
    {
        "repo": "browser-use/browser-use",
        "label": "Browser Use",
        "category": "ブラウザ自動化",
        "summary": "AIエージェントによるブラウザ操作を実装するための更新です",
        "use_case": "APIがないWeb画面の調査や定型入力を自動化できる可能性があります",
        "action": "利用規約、誤操作、認証情報を確認し、読み取り専用の作業から試す",
        "base_score": 83,
        "tags": ["ブラウザ操作", "AIエージェント", "自動化"],
    },
    {
        "repo": "microsoft/playwright",
        "label": "Playwright",
        "category": "ブラウザ自動化",
        "summary": "ブラウザ操作と自動テストの基盤であるPlaywrightの公式更新です",
        "use_case": "Garoonや各種Webサービスの操作検証、自動テスト、画面取得の安定性向上に使えます",
        "action": "AI任せにする前に、固定手順をPlaywrightで再現可能にする",
        "base_score": 86,
        "tags": ["Playwright", "ブラウザ自動化", "テスト"],
    },
    {
        "repo": "ollama/ollama",
        "label": "Ollama",
        "category": "ローカルAI",
        "summary": "MacやPC内でLLMを動かすOllamaの公式更新です",
        "use_case": "機密性の高い文書の要約、分類、下処理を外部送信せず実行する判断材料になります",
        "action": "速度、精度、メモリ使用量を実データではなく匿名化データで測る",
        "base_score": 86,
        "tags": ["Ollama", "ローカルLLM", "機密情報"],
    },
    {
        "repo": "langchain-ai/langgraph",
        "label": "LangGraph",
        "category": "AIエージェント",
        "summary": "状態を持つ複数工程のAIエージェントを構築するLangGraphの更新です",
        "use_case": "相談整理、調査、反証、提案、レビューを段階化した支援フローの設計に使えます",
        "action": "単純な処理を無理にエージェント化せず、分岐と再試行が必要な案件だけに使う",
        "base_score": 82,
        "tags": ["LangGraph", "エージェント設計", "ワークフロー"],
    },
]

MAX_ITEMS = 13
RELEASE_DAYS = 90
COMMIT_DAYS = 30

TOPIC_RULES = [
    (("security", "sandbox", "permission", "allowlist", "auth", "redact", "secret"), "権限・認証・サンドボックスなど安全性"),
    (("agent", "subagent", "handoff", "tool", "workflow", "background"), "エージェント実行・ツール連携・ワークフロー"),
    (("model", "context", "opus", "gpt", "gemini", "token"), "対応モデル・コンテキスト・トークン"),
    (("mcp", "server", "connector", "integration"), "MCP・外部サービス連携"),
    (("browser", "playwright", "chromium", "firefox", "webkit"), "ブラウザ操作・自動テスト"),
    (("rag", "retrieval", "embedding", "vector", "document"), "RAG・文書検索・知識活用"),
    (("performance", "speed", "latency", "memory", "cache"), "速度・メモリ・処理性能"),
    (("fix", "bug", "reliability", "crash", "error"), "不具合修正・安定性"),
    (("example", "cookbook", "guide", "docs", "sample"), "実装例・ガイド・ドキュメント"),
]


def get_json(path):
    request = urllib.request.Request(API + path, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def parse_date(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def clean_text(value, limit=180):
    text = re.sub(r"\s+", " ", value or "").strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def recency_score(published_at):
    date = parse_date(published_at)
    if not date:
        return 0
    days = max(0, (datetime.now(timezone.utc) - date).days)
    if days <= 3:
        return 5
    if days <= 7:
        return 3
    if days <= 14:
        return 1
    return 0


def topic_summary(text):
    lower = (text or "").lower()
    topics = []
    for words, japanese in TOPIC_RULES:
        if any(word in lower for word in words):
            topics.append(japanese)
    if not topics:
        return "詳細は公式の更新内容で確認が必要です"
    return "、".join(topics[:3]) + "に関する変更です"


def latest_stable_release(source):
    repo = source["repo"]
    releases = get_json(f"/repos/{repo}/releases?per_page=10")
    cutoff = datetime.now(timezone.utc) - timedelta(days=RELEASE_DAYS)
    for release in releases:
        published = release.get("published_at") or release.get("created_at")
        date = parse_date(published)
        if not date or date < cutoff or release.get("draft") or release.get("prerelease"):
            continue
        name = clean_text(release.get("name") or release.get("tag_name") or "新しいリリース", 70)
        body = release.get("body") or ""
        score = min(100, source["base_score"] + recency_score(published))
        if body and topic_summary(body).startswith("不具合修正"):
            score = max(72, score - 5)
        return {
            "source_kind": "github_release",
            "source_name": repo,
            "title": f"{source['label']}：{name}",
            "summary": f"{source['summary']}。主な論点は、{topic_summary(body)}。",
            "reason": f"あなたへの使い道：{source['use_case']}。次にすること：{source['action']}。",
            "category": source["category"],
            "tags": source["tags"] + ["正式版"],
            "score": score,
            "published_at": published,
            "url": release.get("html_url") or f"https://github.com/{repo}/releases",
            "verdict": "読む価値あり" if score >= 88 else "必要時に確認",
            "original_excerpt": clean_text(body, 300),
        }
    return None


def latest_meaningful_commit(source):
    repo = source["repo"]
    commits = get_json(f"/repos/{repo}/commits?per_page=10")
    cutoff = datetime.now(timezone.utc) - timedelta(days=COMMIT_DAYS)
    useful_words = ("example", "cookbook", "guide", "docs", "support", "feature", "add", "improve", "fix", "update")
    for commit in commits:
        info = commit.get("commit", {})
        published = info.get("committer", {}).get("date") or info.get("author", {}).get("date")
        date = parse_date(published)
        message = (info.get("message") or "").splitlines()[0]
        if not date or date < cutoff:
            continue
        if source["category"] == "実装例・ノウハウ" and not any(word in message.lower() for word in useful_words):
            continue
        score = min(94, source["base_score"] - 5 + recency_score(published))
        return {
            "source_kind": "github_commit",
            "source_name": repo,
            "title": f"{source['label']}：公式情報が更新",
            "summary": f"{source['summary']}。主な論点は、{topic_summary(message)}。",
            "reason": f"あなたへの使い道：{source['use_case']}。次にすること：{source['action']}。",
            "category": source["category"],
            "tags": source["tags"] + ["公式更新"],
            "score": score,
            "published_at": published,
            "url": commit.get("html_url") or f"https://github.com/{repo}/commits",
            "verdict": "読む価値あり" if score >= 88 else "必要時に確認",
            "original_excerpt": clean_text(message, 220),
        }
    return None


def main():
    items = []
    source_status = []
    for source in SOURCES:
        try:
            # 1情報源につき最大1件。細かなバージョン違いで一覧を埋めない。
            item = latest_stable_release(source) or latest_meaningful_commit(source)
            if item:
                items.append(item)
            source_status.append({"name": source["repo"], "ok": True, "items": 1 if item else 0})
        except urllib.error.HTTPError as error:
            source_status.append({"name": source["repo"], "ok": False, "error": f"HTTP {error.code}"})
        except Exception as error:
            source_status.append({"name": source["repo"], "ok": False, "error": str(error)[:160]})

    items = sorted(
        items,
        key=lambda item: (
            item["score"],
            parse_date(item["published_at"]) or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )[:MAX_ITEMS]

    payload = {
        "site": {
            "title": "AI実務レーダー",
            "editorial_policy": "公式・信頼できる情報源のみ。1情報源1件。日本語で論点、使い道、次の行動を示す。",
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "item_count": len(items),
        "sources": source_status,
        "items": items,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    print(f"saved {len(items)} curated items from {len(SOURCES)} sources")


if __name__ == "__main__":
    main()
