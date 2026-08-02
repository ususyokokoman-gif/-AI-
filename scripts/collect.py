import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path("data/items.json")
SOURCE_PATH = Path("config/github-sources.json")
PROFILE_PATH = Path("config/personalization.json")
API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "zun-ai-practice-radar",
    "X-GitHub-Api-Version": "2022-11-28",
}
if os.getenv("GITHUB_TOKEN"):
    HEADERS["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]

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


def load_json(path):
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def get_json(path):
    request = urllib.request.Request(API + path, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def parse_date(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def clean_text(value, limit=180):
    text = re.sub(r"\s+", " ", value or "").strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def recency_score(published_at):
    date = parse_date(published_at)
    if not date:
        return 0
    days = max(0, (datetime.now(timezone.utc) - date).days)
    return 5 if days <= 3 else 3 if days <= 7 else 1 if days <= 14 else 0


def topic_summary(text):
    lower = (text or "").lower()
    topics = [label for words, label in TOPIC_RULES if any(word in lower for word in words)]
    return ("、".join(topics[:3]) + "に関する変更です") if topics else "詳細は公式の更新内容で確認が必要です"


def matched_any(text, keywords):
    return any(str(keyword).lower() in text for keyword in keywords)


def personalize(item, profile):
    text = " ".join([
        item.get("title", ""), item.get("summary", ""), item.get("reason", ""),
        item.get("category", ""), item.get("source_name", ""),
        item.get("original_excerpt", ""), " ".join(item.get("tags", [])),
    ]).lower()
    adjustment = int(profile.get("category_bonus", {}).get(item.get("category", ""), 0))
    matches, penalties = [], []
    for group_name in ("priority_themes", "active_projects"):
        for rule in profile.get(group_name, []):
            if matched_any(text, rule.get("keywords", [])):
                adjustment += int(rule.get("weight", 0))
                matches.append(rule.get("label", rule.get("id", "一致")))
    for signal in profile.get("quality_signals", []):
        if matched_any(text, signal.get("keywords", [])):
            adjustment += int(signal.get("weight", 0))
            matches.append(signal.get("label", "品質シグナル"))
    for penalty in profile.get("penalties", []):
        if matched_any(text, penalty.get("keywords", [])):
            adjustment += int(penalty.get("weight", 0))
            penalties.append(penalty.get("label", "減点"))
    return max(-20, min(15, adjustment)), list(dict.fromkeys(matches))[:5], penalties[:3]


def finalize_item(item, profile):
    adjustment, matches, penalties = personalize(item, profile)
    item["personalization_adjustment"] = adjustment
    item["personalization_matches"] = matches
    item["personalization_penalties"] = penalties
    item["score"] = max(0, min(100, item["score"] + adjustment))
    item["personalization_reason"] = (
        "あなたとの一致：" + "、".join(matches)
        if matches else "直接一致は弱いため、公式更新として必要時に確認"
    )
    item["verdict"] = "最優先" if item["score"] >= 95 else "読む価値あり" if item["score"] >= 86 else "必要時に確認"
    return item


def latest_stable_release(source, profile):
    releases = get_json(f"/repos/{source['repo']}/releases?per_page=10")
    cutoff = datetime.now(timezone.utc) - timedelta(days=RELEASE_DAYS)
    for release in releases:
        published = release.get("published_at") or release.get("created_at")
        date = parse_date(published)
        if not date or date < cutoff or release.get("draft") or release.get("prerelease"):
            continue
        body = release.get("body") or ""
        item = {
            "source_kind": "github_release",
            "source_name": source["repo"],
            "title": f"{source['label']}：{clean_text(release.get('name') or release.get('tag_name') or '新しいリリース', 70)}",
            "summary": f"{source['summary']}。主な論点は、{topic_summary(body)}。",
            "reason": f"あなたへの使い道：{source['use_case']}。次にすること：{source['action']}。",
            "category": source["category"],
            "tags": source["tags"] + ["正式版"],
            "score": min(95, source["base_score"] + recency_score(published)),
            "published_at": published,
            "url": release.get("html_url") or f"https://github.com/{source['repo']}/releases",
            "original_excerpt": clean_text(body, 300),
        }
        return finalize_item(item, profile)
    return None


def latest_meaningful_commit(source, profile):
    commits = get_json(f"/repos/{source['repo']}/commits?per_page=10")
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
        item = {
            "source_kind": "github_commit",
            "source_name": source["repo"],
            "title": f"{source['label']}：公式情報が更新",
            "summary": f"{source['summary']}。主な論点は、{topic_summary(message)}。",
            "reason": f"あなたへの使い道：{source['use_case']}。次にすること：{source['action']}。",
            "category": source["category"],
            "tags": source["tags"] + ["公式更新"],
            "score": min(91, source["base_score"] - 5 + recency_score(published)),
            "published_at": published,
            "url": commit.get("html_url") or f"https://github.com/{source['repo']}/commits",
            "original_excerpt": clean_text(message, 220),
        }
        return finalize_item(item, profile)
    return None


def main():
    profile = load_json(PROFILE_PATH)
    sources = load_json(SOURCE_PATH)["sources"]
    items, source_status = [], []
    for source in sources:
        try:
            item = latest_stable_release(source, profile) or latest_meaningful_commit(source, profile)
            if item:
                items.append(item)
            source_status.append({"name": source["repo"], "ok": True, "items": 1 if item else 0})
        except urllib.error.HTTPError as error:
            source_status.append({"name": source["repo"], "ok": False, "error": f"HTTP {error.code}"})
        except Exception as error:
            source_status.append({"name": source["repo"], "ok": False, "error": str(error)[:160]})

    items = sorted(items, key=lambda item: (
        parse_date(item["published_at"]) or datetime.min.replace(tzinfo=timezone.utc), item["score"]
    ), reverse=True)[:MAX_ITEMS]
    payload = {
        "site": {
            "title": "AI実務レーダー",
            "editorial_policy": "公式・信頼できる情報源をZun実務優先プロファイルで採点。鮮度、実装可能性、現在案件との一致、証拠と再現性を重視する。",
        },
        "personalization": {
            "profile_name": profile.get("profile_name", "未設定"),
            "mission": profile.get("mission", ""),
            "sort": profile.get("freshness", {}).get("default_sort", "newest_then_personalized"),
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "item_count": len(items),
        "sources": source_status,
        "items": items,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {len(items)} personalized items from {len(sources)} sources")


if __name__ == "__main__":
    main()
