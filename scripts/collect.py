import json, os, urllib.parse, urllib.request
from datetime import datetime, timezone

OUT='data/items.json'
HEADERS={'Accept':'application/vnd.github+json','User-Agent':'ai-practice-radar','X-GitHub-Api-Version':'2022-11-28'}
if os.getenv('GITHUB_TOKEN'): HEADERS['Authorization']='Bearer '+os.environ['GITHUB_TOKEN']
QUERIES=['ai agent automation stars:>500 pushed:>2026-05-01','mcp server stars:>100 pushed:>2026-05-01','llm workflow automation stars:>100 pushed:>2026-05-01']

def get(url,headers=None):
    req=urllib.request.Request(url,headers=headers or HEADERS)
    with urllib.request.urlopen(req,timeout=25) as r:return json.load(r)

def score(repo):
    stars=repo.get('stargazers_count',0); text=((repo.get('description') or '')+' '+repo.get('name','')).lower()
    s=45+min(25,stars//500)
    if any(x in text for x in ['agent','automation','workflow','mcp','rag','tool']):s+=15
    return min(100,s)

def main():
    items=[]; seen=set(); sources=[]
    for q in QUERIES:
        try:
            data=get('https://api.github.com/search/repositories?sort=updated&order=desc&per_page=20&q='+urllib.parse.quote(q))
            sources.append({'name':'GitHub repository search','ok':True})
            for r in data.get('items',[]):
                if r['html_url'] in seen:continue
                seen.add(r['html_url']); sc=score(r)
                items.append({'source_kind':'github','source_name':r['full_name'],'title':r['full_name'],'summary':r.get('description') or 'GitHubで更新中のAI関連プロジェクト','reason':'更新が継続し、実装や検証に使える一次情報です。','category':'AIエージェント' if 'agent' in ((r.get('name') or '')+' '+(r.get('description') or '')).lower() else '業務自動化','tags':(r.get('topics') or [])[:5],'score':sc,'published_at':r.get('pushed_at') or r.get('updated_at'),'url':r['html_url']})
        except Exception as e:sources.append({'name':'GitHub repository search','ok':False,'error':str(e)})
    items=sorted(items,key=lambda x:(x['score'],x['published_at']),reverse=True)[:80]
    payload={'site':{'title':'AI実務レーダー'},'updated_at':datetime.now(timezone.utc).isoformat(),'item_count':len(items),'sources':sources,'items':items}
    os.makedirs('data',exist_ok=True)
    with open(OUT,'w',encoding='utf-8') as f:json.dump(payload,f,ensure_ascii=False,indent=2)
    print('saved',len(items),'items')

if __name__=='__main__':main()
