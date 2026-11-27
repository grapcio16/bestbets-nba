/* HOOPZARO historical player directory: no fake numbers and no forecasts. */
(function(global){
"use strict";
const $=id=>document.getElementById(id);
const PAGE_SIZE=7;
let callbacks={},catalog=null,averages=null,role="guest",page=0,query="",team="",position="";
let selectedKey="",lastSelectedPlayer=null;
const requestedIds=new Set();
const DEFAULT_SPOTLIGHT={name:"Jayson Tatum",team:"BOS",position:"F",id:""};
const norm=name=>String(name||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"")
  .toLowerCase().replace(/[^a-z0-9]/g,"");
const entitled=()=>role==="premium"||role==="admin";
const safeNumber=(value,percent)=>{
  if(typeof value!=="number"||!Number.isFinite(value))return "—";
  return value.toFixed(1).replace(".",",")+(percent?"%":"");
};
function setOptions(players){
  const select=$("hzp-team"),existing=select.value;
  const values=Array.from(new Set(players.map(p=>String(p.team||"").trim()).filter(Boolean))).sort();
  const signature=values.join("|");
  if(select.dataset.signature===signature)return;
  select.dataset.signature=signature;
  select.replaceChildren(new Option("Wszystkie",""));
  values.forEach(value=>select.append(new Option(value,value)));
  select.value=values.includes(existing)?existing:"";
  team=select.value;
}
function make(tag,cls,text){
  const el=document.createElement(tag);if(cls)el.className=cls;
  if(text!==undefined)el.textContent=String(text);return el;
}
function filteredPlayers(){
  const players=Array.isArray(catalog?.players)?catalog.players:[];
  const found=players.filter(p=>(!query||norm(p.name).includes(norm(query)))&&
    (!team||p.team===team)&&(!position||String(p.position||"").split("-").includes(position)));
  // Featured players are only a visual default ordering, never fabricated.
  const featured=["jaysontatum","stephencurry","nikolajokic","lukadoncic",
                  "shaigilgeousalexander","anthonyedwards"];
  return found.sort((a,b)=>{
    const i=featured.indexOf(norm(a.name)),j=featured.indexOf(norm(b.name));
    if(i!==j)return (i<0?999:i)-(j<0?999:j);
    return String(a.name).localeCompare(String(b.name),"pl");
  });
}
const keyFor=player=>String(player.id||"")||norm(player.name)+"@"+String(player.team||"");
function avatarFor(player,spotlight=false){
  const initials=String(player.name||"").trim().split(/\s+/).filter(Boolean)
    .slice(0,2).map(part=>part[0]).join("").toUpperCase();
  const avatar=make("span","hzp-player-avatar"+(spotlight?" hzp-spotlight-avatar":""));
  avatar.setAttribute("aria-hidden","true");
  avatar.dataset.hoopPlayer=String(player.name||"");
  avatar.dataset.hoopTeam=String(player.team||"");
  if(/^\d{1,20}$/.test(String(player.id||"")))avatar.dataset.hoopId=String(player.id);
  avatar.append(make("span","hzp-avatar-fallback",initials));
  return avatar;
}
function dataFor(player){
  const id=String(player.id||"");
  // The ESPN ID is the authority for identity. Names can collide and a
  // player's roster team can differ from the team in historical game logs.
  const data=entitled()?(averages?.id_rows?averages.id_rows[id]:averages?.rows?.[norm(player.name)]):null;
  const reportedGames=Number(data?.games);
  const gameCount=Number.isInteger(reportedGames)&&reportedGames>0?reportedGames:0;
  const waiting=entitled()&&!data&&!((averages?.attempted_ids||[]).includes(id));
  const unavailable=(averages?.unavailable_ids||[]).includes(id);
  return {data,id,gameCount,waiting,unavailable};
}
const countFor=(info,field)=>({three_pm:info.data?.three_pm_games,
  three_pa:info.data?.three_pa_games,three_pct:info.data?.three_pct_games})[field];
function statFor(info,field,percent=false){
  const {data,gameCount,waiting,unavailable}=info;
  if(!entitled())return {text:"♢",status:"is-locked",title:"Dostępne w Hoopzaro Premium"};
  if(waiting)return {text:"…",status:"is-loading",title:"Pobieranie zweryfikowanej historii zawodnika…"};
  const value=field==="games"?gameCount:data?.[field];
  const valid=field==="games"?gameCount>0:typeof value==="number"&&Number.isFinite(value);
  if(!valid)return {text:"—",status:"is-missing",title:unavailable?
    "ESPN nie udostępnia teraz potwierdzonej historii. Spróbuj odświeżyć.":"Brak zweryfikowanych występów"};
  const sample=countFor(info,field);
  const count=Number.isFinite(sample)?sample:gameCount;
  return {text:field==="games"?String(gameCount):safeNumber(value,percent),status:"",title:
    "Potwierdzone występy: "+count+"/"+gameCount+
    (field!=="games"&&Number.isFinite(sample)&&count<gameCount?" · część meczów bez danych rzutowych":"")+
    (data?.partial?" · historia może być niepełna":"")+
    (data?.last_game?" · ostatni: "+data.last_game:"")+
    (data?.sample_source?" · "+data.sample_source:"")};
}
function playerRow(player,active){
  const row=make("button","hzp-player-row"+(active?" is-active":""));row.type="button";
  row.dataset.playerKey=keyFor(player);
  row.setAttribute("aria-pressed",String(active));
  row.setAttribute("aria-label","Pokaż profil zawodnika: "+player.name);
  const name=make("span","hzp-player-name");
  name.append(avatarFor(player));
  const identity=make("span","hzp-player-identity");
  const fullName=make("strong","",player.name);fullName.title=String(player.name||"");
  identity.append(fullName,make("small","",player.position||"NBA"));
  name.append(identity);row.append(name);
  const teamCell=make("span","hzp-player-team");teamCell.append(make("span","hzp-team-tag",player.team||"NBA"));
  row.append(teamCell);
  const info=dataFor(player),games=statFor(info,"games");
  const gpCell=make("span","hzp-games "+games.status,games.text);
  gpCell.title=games.title;
  if(!entitled())gpCell.setAttribute("aria-label","Liczba meczów Premium");
  row.append(gpCell);
  const pts=statFor(info,"pts");
  const ptsCell=make("span","hzp-stat hzp-stat-primary "+pts.status,pts.text);
  ptsCell.title=pts.title;row.append(ptsCell);
  const extra=make("span","hzp-row-extra");
  for(const [label,field] of [["REB","reb"],["AST","ast"]]){
    const stat=statFor(info,field),line=make("span","hzp-extra-line");
    line.append(make("span","",label));
    const value=make("strong",stat.status,stat.text);value.title=stat.title;
    line.append(value);extra.append(line);
  }
  row.append(extra);
  row.addEventListener("click",()=>{
    selectedKey=keyFor(player);lastSelectedPlayer=player;
    $("hzp-table-rows").querySelectorAll(".hzp-player-row").forEach(button=>{
      const selected=button.dataset.playerKey===selectedKey;
      button.classList.toggle("is-active",selected);
      button.setAttribute("aria-pressed",String(selected));
    });
    renderSpotlight(player,"");
  });
  return row;
}
function renderSpotlight(player,note){
  const target=$("hzp-spotlight-body");target.replaceChildren();
  const info=dataFor(player);
  const hero=make("div","hzp-spotlight-hero");
  hero.append(avatarFor(player,true));
  const copy=make("div","hzp-spotlight-identity");
  const heading=make("h2",String(player.name||"").length>23?"hzp-long-name":"",player.name);heading.title=String(player.name||"");copy.append(heading);
  copy.append(make("p","",(player.team||"NBA")+" · "+(player.position||"NBA")));
  hero.append(copy);target.append(hero);
  const metrics=make("div","hzp-spotlight-metrics");
  const main=make("div","hzp-spotlight-points");
  const pts=statFor(info,"pts");
  const big=make("strong",pts.status,pts.text);big.title=pts.title;
  main.append(big,make("span","","PTS / MECZ"));metrics.append(main);
  const secondary=make("div","hzp-spotlight-secondary");
  for(const [label,field] of [["REB","reb"],["AST","ast"],["3PM","three_pm"],["3PA","three_pa"]]){
    const stat=statFor(info,field),cell=make("div","hzp-spotlight-metric");
    cell.append(make("span","",label));
    const value=make("strong",stat.status,stat.text);value.title=stat.title;
    cell.append(value);secondary.append(cell);
  }
  metrics.append(secondary);target.append(metrics);
  const bottom=make("div","hzp-spotlight-bottom");
  const accuracy=make("div","hzp-spotlight-accuracy");
  const accuracyHead=make("div","hzp-spotlight-accuracy-head");
  accuracyHead.append(make("span","","SKUTECZNOŚĆ ZA 3"));
  const pct=statFor(info,"three_pct",true);
  const pctValue=make("strong",pct.status,pct.text);pctValue.title=pct.title;
  accuracyHead.append(pctValue);accuracy.append(accuracyHead);
  const track=make("div","hzp-spotlight-meter");
  const fill=make("span");
  const percentage=info.data?.three_pct;
  fill.style.width=entitled()&&Number.isFinite(percentage)?Math.max(0,Math.min(100,percentage))+"%":"0%";
  track.append(fill);accuracy.append(track);bottom.append(accuracy);
  const gp=statFor(info,"games"),games=make("div","hzp-spotlight-games");
  const gpValue=make("strong",gp.status,gp.text);gpValue.title=gp.title;
  games.append(gpValue,make("span","","ROZEGRANYCH\nMECZÓW"));bottom.append(games);
  target.append(bottom);
  const foot=make("div","hzp-spotlight-note");
  foot.append(make("span","hzp-note-icon","ⓘ"));
  foot.append(make("span","",note||(!entitled()?
    "Statystyki tego zawodnika dostępne są w Premium.":
    "Średnie z potwierdzonych występów · nie są prognozą.")));
  target.append(foot);
}
function render(nextCatalog,nextAverages,nextRole){
  catalog=nextCatalog&&typeof nextCatalog==="object"?nextCatalog:null;
  averages=nextAverages&&typeof nextAverages==="object"?nextAverages:null;
  role=String(nextRole||"guest");
  const players=Array.isArray(catalog?.players)?catalog.players:[];
  setOptions(players);
  const matches=filteredPlayers(),limit=entitled()?matches.length:Math.min(matches.length,7);
  const totalPages=Math.max(1,Math.ceil(limit/PAGE_SIZE));page=Math.min(page,totalPages-1);
  const visible=matches.slice(page*PAGE_SIZE,Math.min((page+1)*PAGE_SIZE,limit));
  const chosen=visible.find(p=>keyFor(p)===selectedKey)||visible[0]||null;
  if(chosen){selectedKey=keyFor(chosen);lastSelectedPlayer=chosen;}
  renderSpotlight(chosen||lastSelectedPlayer||players[0]||DEFAULT_SPOTLIGHT,
    !catalog?"Trwa pobieranie składów NBA / ESPN. Statystyki pojawią się po weryfikacji.":
    catalog.error?"Nie udało się odświeżyć składów · ostatnio wybrany profil.":
    !matches.length?"Brak zawodników dla wybranych filtrów · ostatnio wybrany profil.":"");
  const rows=$("hzp-table-rows"),scroll=rows.scrollTop;rows.replaceChildren();
  if(!catalog){rows.append(make("div","hzp-empty","Pobieranie aktualnych składów NBA / ESPN…"));}
  else if(catalog.error||!players.length){
    rows.append(make("div","hzp-empty",catalog.error||"Brak potwierdzonych składów NBA. Spróbuj odświeżyć."));
  }else if(!matches.length){rows.append(make("div","hzp-empty","Nie znaleziono zawodnika dla wybranych filtrów."));}
  else{
    visible.forEach(p=>rows.append(playerRow(p,keyFor(p)===selectedKey)));
    // Original HOOPZARO identity badges are shown instead of unlicensed
    // ESPN/NBA photographs, for both free and premium visitors.
  }
  rows.scrollTop=scroll;
  $("hzp-page").textContent=(page+1)+" / "+totalPages;
  $("hzp-prev").disabled=page===0;$("hzp-next").disabled=page+1>=totalPages;
  $("hzp-table-count").textContent=!catalog?"Trwa pobieranie…":
    !entitled()?"Darmowy podgląd · odblokuj statystyki Premium":
    "Wyświetlono "+visible.length+" z "+matches.length+" zawodników";
  const source=$("hzp-source");
  const loaded=visible.filter(p=>(averages?.attempted_ids||[]).includes(String(p.id||""))).length;
  const failed=visible.filter(p=>(averages?.unavailable_ids||[]).includes(String(p.id||""))).length;
  source.textContent=!entitled()?"Lista zawodników: ESPN · Statystyki zablokowane w Premium.":
    "Źródło: ESPN · sezon 2026/27 · "+(loaded-failed)+"/"+visible.length+" historii na tej stronie"+
    (failed?" · "+failed+" chwilowo niedostępnych (Odśwież)":"")+
    " · średnie z potwierdzonych występów · najedź na statystykę, aby sprawdzić próbkę";
  $("hzp-cta-title").textContent=entitled()?"Chcesz przeanalizować kolejny mecz?":"Odblokuj statystyki zawodników";
  $("hzp-cta-text").textContent=entitled()?"Prognozy, linie OVER/UNDER i symulacje znajdziesz w Player Props.":
    "Średnie PTS, REB, AST, 3PM, 3PA i 3P% dostępne z Hoopzaro Premium.";
  $("hzp-cta").firstChild.textContent=entitled()?"Otwórz Player Props ":"Premium · 9,99 USD/mies. ";
  if(entitled()&&catalog&&visible.length&&typeof callbacks.requestAverages==="function"){
    const done=new Set(averages?.attempted_ids||[]);
    const missing=visible.map(p=>String(p.id||"")).filter(id=>
      id&&/^\d+$/.test(id)&&!done.has(id)&&!requestedIds.has(id));
    if(missing.length){
      missing.forEach(id=>requestedIds.add(id));
      callbacks.requestAverages(missing.slice(0,7));
    }
  }
}
function init(api){
  callbacks=api||{};
  const resetListScroll=()=>{$("hzp-table-rows").scrollTop=0};
  $("hzp-search").addEventListener("input",e=>{query=e.target.value;page=0;resetListScroll();render(catalog,averages,role)});
  $("hzp-team").addEventListener("change",e=>{team=e.target.value;page=0;resetListScroll();render(catalog,averages,role)});
  $("hzp-position").addEventListener("change",e=>{position=e.target.value;page=0;resetListScroll();render(catalog,averages,role)});
  $("hzp-prev").addEventListener("click",()=>{page=Math.max(0,page-1);resetListScroll();render(catalog,averages,role)});
  $("hzp-next").addEventListener("click",()=>{page++;resetListScroll();render(catalog,averages,role)});
  $("hzp-refresh").addEventListener("click",()=>callbacks.refresh?.());
  $("hzp-cta").addEventListener("click",()=>entitled()?callbacks.openProps?.():callbacks.openPremium?.());
}
global.HoopzaroPlayers={init,render,resetRequests:()=>requestedIds.clear()};
})(window);
