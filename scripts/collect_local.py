#!/usr/bin/env python3
import html
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

BASE_PATH = Path("data/items.json")
OUT_PATH = Path("data/local-items.json")
PROFILE_PATH = Path("config/personalization.json")
EXTERNAL_PATH = Path("config/external-sources.json")
X_PROFILE_PATH = Path("config/x-search-profiles.json")
X_ACCOUNTS_PATH = Path("config/x-priority-accounts.json")
USER_AGENT = "zun-ai-practice-radar/2.0"
MAX_ITEMS = 50

TOPICS = [
    (("security","sandbox","permission","auth","secret","vulnerability"),"権限・認証・安全性"),
    (("agent","subagent","handoff","workflow","orchestration","tool"),"エージェント実行・ワークフロー"),
    (("model","context","gpt","gemini","claude","token","llm"),"モデル・コンテキスト"),
    (("mcp","connector","integration","webhook"),"MCP・外部連携"),
    (("browser","playwright","computer use"),"ブラウザ操作・自動テスト"),
    (("rag","retrieval","embedding","document","knowledge"),"RAG・文書活用"),
    (("benchmark","latency","memory","performance","speed"),"速度・性能評価"),
    (("bug","failure","error","workaround","reliability"),"不具合・失敗・回避策"),
    (("guide","tutorial","setup","example","cookbook"),"実装例・ガイド"),
    (("whisper","transcription","diarization"),"文字起こし・音声処理"),
    (("pricing","margin","cost","roi","small business","smb"),"中小企業・収益改善"),
]
DEFAULT_WORDS = ("agent","codex","claude","mcp","llm","rag","automation","playwright","n8n","dify","ollama","whisper","langgraph","benchmark","workflow")


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read()


def fetch_json(url):
    return json.loads(fetch(url).decode("utf-8"))


def clean(value, limit=260):
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def parse_date(value):
    if not value:
        return None
    if isinstance(value, (int,float)) or str(value).isdigit():
        return datetime.fromtimestamp(int(value), timezone.utc)
    text = str(value).strip()
    try:
        dt = datetime.fromisoformat(text.replace("Z","+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(text)
        except Exception:
            return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def iso(value):
    dt = parse_date(value)
    return dt.isoformat().replace("+00:00","Z") if dt else None


def recent_bonus(value):
    dt = parse_date(value)
    if not dt: return 0
    days = max(0,(datetime.now(timezone.utc)-dt).days)
    return 7 if days <= 1 else 5 if days <= 3 else 3 if days <= 7 else 1 if days <= 14 else 0


def topic(text):
    lower = (text or "").lower()
    found = [label for words,label in TOPICS if any(word in lower for word in words)]
    return "、".join(found[:3]) if found else "具体的な更新内容"


def relevant(text, words=None):
    lower = (text or "").lower()
    return any(str(word).lower() in lower for word in (words or DEFAULT_WORDS))


def personalize(item, profile):
    text = " ".join([item.get("title",""),item.get("summary",""),item.get("reason",""),item.get("category",""),item.get("original_excerpt","")," ".join(item.get("tags",[]))]).lower()
    adjust = int(profile.get("category_bonus",{}).get(item.get("category",""),0))
    matches, penalties = [], []
    for group in ("priority_themes","active_projects"):
        for rule in profile.get(group,[]):
            if relevant(text,rule.get("keywords",[])):
                adjust += int(rule.get("weight",0)); matches.append(rule.get("label","一致"))
    for rule in profile.get("quality_signals",[]):
        if relevant(text,rule.get("keywords",[])):
            adjust += int(rule.get("weight",0)); matches.append(rule.get("label","品質"))
    for rule in profile.get("penalties",[]):
        if relevant(text,rule.get("keywords",[])):
            adjust += int(rule.get("weight",0)); penalties.append(rule.get("label","減点"))
    item["personalization_adjustment"] = max(-20,min(15,adjust))
    item["personalization_matches"] = list(dict.fromkeys(matches))[:5]
    item["personalization_penalties"] = penalties[:3]
    item["score"] = max(0,min(100,int(item.get("score",0))+item["personalization_adjustment"]))
    item["personalization_reason"] = "あなたとの一致："+ "、".join(item["personalization_matches"]) if item["personalization_matches"] else "直接一致は弱いため、必要時に確認"
    item["verdict"] = "最優先" if item["score"] >= 95 else "読む価値あり" if item["score"] >= 86 else "必要時に確認"
    item["published_at"] = iso(item.get("published_at")) or datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    return item


def local(tag):
    return tag.rsplit("}",1)[-1].lower()


def feed_entries(data):
    root = ET.fromstring(data)
    rows = []
    for entry in [node for node in root.iter() if local(node.tag) in {"item","entry"}]:
        values = {}
        for child in list(entry):
            name = local(child.tag)
            if name == "link":
                values["link"] = child.attrib.get("href") or (child.text or "").strip()
            elif name in {"title","published","updated","pubdate","date","description","summary","content","encoded","guid"} and child.text:
                values[name] = child.text.strip()
        title = values.get("title","")
        url = values.get("link") or values.get("guid","")
        date = values.get("published") or values.get("updated") or values.get("pubdate") or values.get("date")
        summary = values.get("description") or values.get("summary") or values.get("content") or values.get("encoded") or ""
        if title and url:
            rows.append({"title":clean(title,180),"url":url,"published_at":iso(date),"summary":clean(summary,600)})
    return rows


def collect_feeds(profile, cfg):
    items,statuses = [],[]
    for source in cfg.get("official_feeds",[]):
        try:
            rows = feed_entries(fetch(source["url"]))
            selected = next((r for r in rows if relevant(r["title"]+" "+r["summary"],source.get("keywords"))),rows[0] if rows else None)
            if selected:
                text = selected["title"]+" "+selected["summary"]
                items.append(personalize({
                    "source_kind":"official_feed","source_name":source["name"],"title":f"{source['name']}：{selected['title']}",
                    "summary":f"{source['name']}の公式発表です。主な内容は、{topic(text)}です。",
                    "reason":source.get("reason","公式情報として現在のツールや案件への影響を確認する。"),
                    "category":source.get("category","公式リリース"),"tags":source.get("tags",["公式"]),
                    "score":int(source.get("base_score",82))+recent_bonus(selected["published_at"]),
                    "published_at":selected["published_at"],"url":selected["url"],"original_excerpt":selected["summary"] or selected["title"]
                },profile))
            statuses.append({"name":source["name"],"kind":"official","ok":True,"items":1 if selected else 0})
        except Exception as e:
            statuses.append({"name":source["name"],"kind":"official","ok":False,"error":clean(e,140)})
    return items,statuses


def hn_item(item_id):
    try: return fetch_json(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json")
    except Exception: return None


def collect_hn(profile,cfg):
    setting = cfg.get("hacker_news",{})
    try:
        ids = fetch_json("https://hacker-news.firebaseio.com/v0/topstories.json")[:int(setting.get("scan",40))]
        stories = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            for future in as_completed([pool.submit(hn_item,i) for i in ids]):
                row = future.result()
                if row and row.get("type")=="story" and relevant(f"{row.get('title','')} {row.get('url','')}",setting.get("keywords")):
                    stories.append(row)
        stories.sort(key=lambda r:(r.get("time",0),r.get("score",0)),reverse=True)
        items = []
        for row in stories[:int(setting.get("max_items",4))]:
            title = clean(row.get("title"),180)
            items.append(personalize({
                "source_kind":"hacker_news","source_name":"Hacker News","title":title,
                "summary":f"開発者コミュニティで注目されている話題です。主な論点は、{topic(title)}です。",
                "reason":"コメント欄の反証、問題点、代替案まで確認し、自分の案件へ採用する前の検証材料にする。",
                "category":"開発者評価・議論","tags":["Hacker News","第三者評価"],
                "score":68+min(10,int(row.get("score",0))//50)+recent_bonus(row.get("time")),
                "published_at":row.get("time"),"url":f"https://news.ycombinator.com/item?id={row['id']}",
                "external_url":row.get("url"),"original_excerpt":title
            },profile))
        return items,[{"name":"Hacker News","kind":"hacker_news","ok":True,"items":len(items)}]
    except Exception as e:
        return [],[{"name":"Hacker News","kind":"hacker_news","ok":False,"error":clean(e,140)}]


def collect_hf(profile,cfg):
    setting = cfg.get("huggingface",{})
    endpoints = [("models","https://huggingface.co/api/models?sort=lastModified&direction=-1&limit=100","huggingface_model"),("spaces","https://huggingface.co/api/spaces?sort=lastModified&direction=-1&limit=100","huggingface_space")]
    items,statuses = [],[]
    for label,url,kind in endpoints:
        try:
            selected=[]
            for row in fetch_json(url):
                ident=row.get("modelId") or row.get("id") or ""
                text=f"{ident} {' '.join(str(x) for x in row.get('tags',[]))}"
                if relevant(text,setting.get("keywords")): selected.append(row)
                if len(selected)>=int(setting.get("max_per_kind",2)): break
            for row in selected:
                ident=row.get("modelId") or row.get("id") or "不明"
                published=row.get("lastModified") or row.get("createdAt")
                kind_label="Space" if kind=="huggingface_space" else "Model"
                items.append(personalize({
                    "source_kind":kind,"source_name":"Hugging Face","title":f"{kind_label}：{ident}",
                    "summary":f"Hugging Faceで最近更新された{'実演アプリ' if kind_label=='Space' else 'モデル'}です。関連領域は、{topic(ident+' '+' '.join(row.get('tags',[])))}です。",
                    "reason":"Mac・ローカル運用、文字起こし、RAG、エージェント用途へ転用できるか、モデルカードと実測値を確認する。",
                    "category":"モデル・実演","tags":["Hugging Face",kind_label,"要検証"],
                    "score":66+min(6,int(row.get("likes") or 0)//25)+min(4,int(row.get("downloads") or 0)//10000)+recent_bonus(published),
                    "published_at":published,"url":f"https://huggingface.co/{'spaces/' if kind_label=='Space' else ''}{ident}",
                    "original_excerpt":clean(f"{ident} {' '.join(row.get('tags',[]))}",300)
                },profile))
            statuses.append({"name":f"Hugging Face {label}","kind":"huggingface","ok":True,"items":len(selected)})
        except Exception as e:
            statuses.append({"name":f"Hugging Face {label}","kind":"huggingface","ok":False,"error":clean(e,140)})
    return items,statuses


def youtube_id(page_url):
    page=fetch(page_url).decode("utf-8",errors="ignore")
    for pattern in (r'"channelId":"(UC[A-Za-z0-9_-]{20,})"',r'<meta itemprop="channelId" content="(UC[A-Za-z0-9_-]{20,})"',r'/channel/(UC[A-Za-z0-9_-]{20,})'):
        match=re.search(pattern,page)
        if match:return match.group(1)
    return None


def collect_youtube(profile,cfg):
    items,statuses=[],[]
    for channel in cfg.get("youtube_channels",[]):
        try:
            channel_id=channel.get("channel_id") or youtube_id(channel["page_url"])
            if not channel_id: raise RuntimeError("channel idを取得できません")
            rows=feed_entries(fetch(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"))
            selected=next((r for r in rows if relevant(r["title"]+" "+r["summary"],cfg.get("youtube_keywords"))),None)
            if selected:
                items.append(personalize({
                    "source_kind":"youtube","source_name":channel["name"],"title":f"{channel['name']}：{selected['title']}",
                    "summary":f"指定チャンネルの新しい実演・解説です。主な内容は、{topic(selected['title']+' '+selected['summary'])}です。",
                    "reason":"画面操作、設定、失敗過程を確認し、文章だけでは分からない実装方法を把握する。",
                    "category":"動画・実演","tags":["YouTube","実演","指定チャンネル"],
                    "score":int(channel.get("base_score",72))+recent_bonus(selected["published_at"]),
                    "published_at":selected["published_at"],"url":selected["url"],"original_excerpt":selected["summary"] or selected["title"]
                },profile))
            statuses.append({"name":channel["name"],"kind":"youtube","ok":True,"items":1 if selected else 0})
        except Exception as e:
            statuses.append({"name":channel["name"],"kind":"youtube","ok":False,"error":clean(e,140)})
    return items,statuses


def walk(value):
    if isinstance(value,dict):
        yield value
        for child in value.values(): yield from walk(child)
    elif isinstance(value,list):
        for child in value: yield from walk(child)


def get_path(row,*paths):
    for path in paths:
        cur=row
        for part in path.split("."):
            if not isinstance(cur,dict) or part not in cur: break
            cur=cur[part]
        else:
            if cur not in (None,""): return cur
    return None


def tweets_from(payload):
    rows,seen=[],set()
    for row in walk(payload):
        text=get_path(row,"full_text","text","legacy.full_text","note_tweet.text")
        tid=get_path(row,"id_str","rest_id","tweet_id","id")
        if not isinstance(text,str) or len(text.strip())<15 or not str(tid).isdigit() or str(tid) in seen: continue
        seen.add(str(tid))
        user=get_path(row,"username","screen_name","user.screen_name","author.username","core.user_results.result.legacy.screen_name") or "unknown"
        rows.append({"id":str(tid),"text":clean(text,700),"user":str(user).lstrip("@"),"date":get_path(row,"created_at","legacy.created_at","date","published_at"),"likes":int(get_path(row,"favorite_count","likes","legacy.favorite_count") or 0),"reposts":int(get_path(row,"retweet_count","retweets","legacy.retweet_count") or 0),"url":get_path(row,"url","tweet_url") or f"https://x.com/{str(user).lstrip('@')}/status/{tid}"})
    return rows


def command_json(text):
    for start in (0,text.find("["),text.find("{")):
        if start>=0:
            try:return json.loads(text[start:])
            except json.JSONDecodeError:pass
    raise ValueError("twitter-cli JSONを解析できません")


def x_search(exe,query,max_results):
    errors=[]
    for cmd in ([exe,"search",query,"-t","Latest","--max",str(max_results),"--json"],[exe,"search",query,"--max",str(max_results),"--json"]):
        run=subprocess.run(cmd,capture_output=True,text=True,timeout=90)
        if run.returncode==0:return tweets_from(command_json(run.stdout))
        errors.append(clean(run.stderr or run.stdout,120))
    raise RuntimeError(" / ".join(errors))


def collect_x(profile,cfg):
    if os.getenv("AI_RADAR_X_ENABLED") != "1":
        return [],[{"name":"X / twitter-cli","kind":"x","ok":False,"skipped":True,"error":"専用Xアカウント設定が未完了"}]
    if not os.getenv("TWITTER_BROWSER") or not os.getenv("TWITTER_CHROME_PROFILE"):
        return [],[{"name":"X / twitter-cli","kind":"x","ok":False,"skipped":True,"error":"専用ブラウザ・プロファイル未指定"}]
    exe=shutil.which("twitter") or shutil.which("twitter-cli")
    if not exe:return [],[{"name":"X / twitter-cli","kind":"x","ok":False,"skipped":True,"error":"twitter-cli未導入"}]
    xcfg=load(X_PROFILE_PATH,{"profiles":[]}); accounts=load(X_ACCOUNTS_PATH,{})
    weights={}
    for group in ("priority_accounts","secondary_accounts"):
        for account in accounts.get(group,[]):weights[str(account.get("handle","")).lower()]=int(account.get("weight",80))
    profiles=sorted(xcfg.get("profiles",[]),key=lambda x:int(x.get("priority",0)),reverse=True)
    count=int(cfg.get("x",{}).get("max_profiles",6)); fixed=profiles[:2]; rest=profiles[2:]
    start=datetime.now(timezone.utc).date().toordinal()%max(1,len(rest))
    selected=fixed+[rest[(start+i)%len(rest)] for i in range(max(0,count-len(fixed)))] if rest else fixed
    excluded=[str(x).lower() for x in xcfg.get("policy",{}).get("exclude_terms",[])]
    items,seen,errors=[],set(),[]
    for index,search_profile in enumerate(selected):
        try:
            for tw in x_search(exe,search_profile["query"],int(cfg.get("x",{}).get("max_results_per_query",12))):
                if tw["id"] in seen or any(word in tw["text"].lower() for word in excluded):continue
                seen.add(tw["id"]); published=iso(tw["date"]); date_kind="公開日" if published else "取得日"
                published=published or datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
                weight=weights.get(tw["user"].lower(),82)
                items.append(personalize({
                    "source_kind":"x","source_name":f"@{tw['user']}","title":clean(tw["text"],110),
                    "summary":f"重点監視または目的別検索で取得した投稿です。主な内容は、{topic(tw['text'])}です。",
                    "reason":f"{search_profile.get('purpose','実務へ転用できる投稿を確認する')}。リンク先のコード、数値、失敗条件まで確認する。",
                    "category":"X実践投稿","tags":["X",search_profile.get("label","目的別検索"),"実践者"],
                    "score":70+max(0,(weight-80)//3)+min(8,tw["likes"]//100+tw["reposts"]//50)+recent_bonus(published),
                    "published_at":published,"date_kind":date_kind,"url":tw["url"],"original_excerpt":tw["text"],
                    "engagement":{"likes":tw["likes"],"reposts":tw["reposts"]}
                },profile))
        except Exception as e:errors.append(f"{search_profile.get('id','query')}: {clean(e,100)}")
        if index<len(selected)-1:time.sleep(float(cfg.get("x",{}).get("wait_seconds",3)))
    items.sort(key=lambda x:(x["score"],parse_date(x["published_at"]) or datetime.min.replace(tzinfo=timezone.utc)),reverse=True)
    status={"name":"X / twitter-cli","kind":"x","ok":len(errors)<len(selected),"items":len(items),"queries":len(selected)}
    if errors:status["error"]=" | ".join(errors[:3])
    return items[:int(cfg.get("x",{}).get("max_items",14))],[status]


def main():
    base=load(BASE_PATH,{"site":{"title":"AI実務レーダー"},"sources":[],"items":[]})
    profile=load(PROFILE_PATH,{})
    cfg=load(EXTERNAL_PATH,{})
    items=list(base.get("items",[])); statuses=list(base.get("sources",[]))
    for collector in (collect_feeds,collect_hn,collect_hf,collect_youtube,collect_x):
        new_items,new_statuses=collector(profile,cfg);items.extend(new_items);statuses.extend(new_statuses)
    unique=[];seen=set()
    for item in items:
        key=item.get("url") or re.sub(r"\W+","",item.get("title","").lower())[:120]
        if key in seen:continue
        seen.add(key);unique.append(item)
    unique.sort(key=lambda x:(parse_date(x.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc),x.get("score",0)),reverse=True)
    payload={"site":base.get("site",{"title":"AI実務レーダー"}),"personalization":base.get("personalization",{"profile_name":profile.get("profile_name","Zun実務優先プロファイル")}),"updated_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),"item_count":len(unique[:MAX_ITEMS]),"sources":statuses,"items":unique[:MAX_ITEMS]}
    OUT_PATH.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"saved {payload['item_count']} items -> {OUT_PATH}")


if __name__=="__main__":
    main()
