const state={items:[],query:"",category:"",source:"",sort:"newest",highValue:false};
const $=selector=>document.querySelector(selector);
const fmtDate=value=>{
  const date=new Date(value);
  return Number.isNaN(date.getTime())?"日付不明":new Intl.DateTimeFormat("ja-JP",{
    year:"numeric",month:"short",day:"numeric",hour:"2-digit",minute:"2-digit",timeZone:"Asia/Tokyo"
  }).format(date);
};
const relativeDate=value=>{
  const date=new Date(value);
  if(Number.isNaN(date.getTime()))return "日付不明";
  const days=Math.max(0,Math.floor((Date.now()-date.getTime())/86400000));
  if(days===0)return "今日";
  if(days===1)return "昨日";
  if(days<7)return `${days}日前`;
  if(days<31)return `${Math.floor(days/7)}週間前`;
  return `${Math.floor(days/30)}か月前`;
};
const sourceGroup=item=>item.source_kind==="x"?"x":"github";

function render(){
  let items=state.items.filter(item=>{
    const text=[
      item.title,item.summary,item.reason,item.personalization_reason,item.source_name,item.category,
      ...(item.tags||[]),...(item.personalization_matches||[])
    ].join(" ").toLowerCase();
    return(!state.query||text.includes(state.query.toLowerCase()))
      &&(!state.category||item.category===state.category)
      &&(!state.source||sourceGroup(item)===state.source)
      &&(!state.highValue||item.score>=86);
  });
  items.sort((a,b)=>state.sort==="newest"
    ?new Date(b.published_at)-new Date(a.published_at)||(b.score-a.score)
    :(b.score-a.score)||new Date(b.published_at)-new Date(a.published_at));

  const cards=$("#cards");
  cards.innerHTML="";
  const template=$("#cardTemplate");
  for(const item of items){
    const node=template.content.cloneNode(true);
    const group=sourceGroup(item);
    const source=node.querySelector(".badge--source");
    source.textContent=group==="x"?"X":"GitHub";
    source.dataset.source=group;
    node.querySelector(".badge--category").textContent=item.category||"その他";
    node.querySelector(".score strong").textContent=item.score;
    node.querySelector("h2").textContent=item.title;
    node.querySelector(".summary").textContent=item.summary||"概要はリンク先で確認してください。";
    const reasons=[item.personalization_reason,item.reason].filter(Boolean);
    node.querySelector(".reason").textContent=reasons.join("。 ")||"一次情報を直接確認できます。";
    const tags=node.querySelector(".tags");
    const displayTags=[...(item.personalization_matches||[]).slice(0,2),...(item.tags||[])];
    [...new Set(displayTags)].slice(0,6).forEach(tag=>{
      const span=document.createElement("span");
      span.textContent=tag;
      tags.appendChild(span);
    });
    node.querySelector(".source-name").textContent=item.source_name;
    node.querySelector(".relative-date").textContent=relativeDate(item.published_at);
    node.querySelector(".published-date").textContent=fmtDate(item.published_at);
    const link=node.querySelector("a");
    link.href=item.url;
    cards.appendChild(node);
  }
  $("#visibleCount").textContent=items.length;
  $("#emptyState").hidden=items.length>0;
  $("#activeSummary").textContent=state.highValue
    ?"実務価値86点以上に絞り込み中です。"
    :state.sort==="newest"?"新しい情報から表示しています。":"あなたとの一致度が高い情報から表示します。";
}

function bind(){
  $("#searchInput").addEventListener("input",event=>{state.query=event.target.value;render()});
  $("#categoryFilter").addEventListener("change",event=>{state.category=event.target.value;render()});
  $("#sourceFilter").addEventListener("change",event=>{state.source=event.target.value;render()});
  $("#sortOrder").addEventListener("change",event=>{state.sort=event.target.value;render()});
  $("#highValueOnly").addEventListener("click",event=>{
    state.highValue=!state.highValue;
    event.currentTarget.setAttribute("aria-pressed",String(state.highValue));
    render();
  });
}

async function init(){
  bind();
  try{
    const response=await fetch(`data/items.json?v=${Date.now()}`);
    if(!response.ok)throw new Error(`HTTP ${response.status}`);
    const data=await response.json();
    state.items=data.items||[];
    document.title=data.site?.title||"AI実務レーダー";
    $("#updatedAt").textContent=`最終更新 ${fmtDate(data.updated_at)}`;
    const ok=(data.sources||[]).filter(source=>source.ok).length;
    const profile=data.personalization?.profile_name?` · ${data.personalization.profile_name}`:"";
    $("#sourceStatus").textContent=`${data.item_count||state.items.length}件 · ${ok}/${(data.sources||[]).length}系統から取得${profile}`;
    const categories=[...new Set(state.items.map(item=>item.category).filter(Boolean))].sort();
    for(const category of categories){
      const option=document.createElement("option");
      option.value=category;
      option.textContent=category;
      $("#categoryFilter").appendChild(option);
    }
    $("#sortOrder").value="newest";
    render();
  }catch(error){
    $("#updatedAt").textContent="データを読み込めませんでした";
    $("#sourceStatus").textContent=String(error);
    $("#emptyState").hidden=false;
  }
}

init();
