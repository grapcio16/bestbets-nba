/* HOOPZARO historical player directory: no fake numbers and no forecasts. */
(function(global){
"use strict";
const $=id=>document.getElementById(id);
const PAGE_SIZE=7;
let callbacks={},catalog=null,averages=null,role="guest",page=0,query="",team="",position="";
const requestedIds=new Set();
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
  select.replaceChildren(new Option("Wszystkie drużyny",""));
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
function playerRow(player){
  const row=make("div","hzp-player-row"),name=make("div","hzp-player-name");
  const initials=String(player.name||"").trim().split(/\s+/).filter(Boolean)
    .slice(0,2).map(part=>part[0]).join("").toUpperCase();
  const avatar=make("span","hzp-player-avatar");
  avatar.setAttribute("aria-hidden","true");
  avatar.dataset.hoopPlayer=String(player.name||"");
  avatar.dataset.hoopTeam=String(player.team||"");
  if(/^\d{1,20}$/.test(String(player.id||"")))avatar.dataset.hoopId=String(player.id);
  avatar.append(make("span","hzp-avatar-fallback",initials));
  name.append(avatar);
  const identity=make("div","hzp-player-identity");
  const id=String(player.id||"");
  // The ESPN ID is the authority for identity. Names can collide and a
  // player's roster team can differ from the team in historical game logs.
  const data=entitled()?(averages?.id_rows?averages.id_rows[id]:averages?.rows?.[norm(player.name)]):null;
  const gameCount=Number(data?.games)||0;
  identity.append(make("strong","",player.name),make("small","",
    (player.position||"NBA")+(entitled()&&gameCount?" · "+gameCount+" mecz.":"")));
  name.append(identity);row.append(name);
  const teamCell=make("div");teamCell.append(make("span","hzp-team-tag",player.team||"NBA"));
  row.append(teamCell);
  const figures=[data?.pts,data?.reb,data?.ast,data?.three_pm,data?.three_pa,data?.three_pct];
  const waiting=entitled()&&!data&&!((averages?.attempted_ids||[]).includes(id));
  const unavailable=(averages?.unavailable_ids||[]).includes(id);
  const fieldCounts=[gameCount,gameCount,gameCount,data?.three_pm_games,
    data?.three_pa_games,data?.three_pct_games];
  figures.forEach((number,index)=>{
    const locked=!entitled();
    const blank=number===null||number===undefined;
    const cell=make("span","hzp-stat"+(locked?" is-locked":blank?" is-missing":index===5?" is-highlight":""),
      locked?"♢":waiting?"…":safeNumber(number,index===5));
    if(locked){cell.title="Dostępne w Hoopzaro Premium";cell.setAttribute("aria-label","Statystyka Premium");}
    else if(unavailable)cell.title="ESPN nie udostępnia teraz potwierdzonej historii. Spróbuj ponownie przyciskiem Odśwież.";
    else if(waiting)cell.title="Pobieranie zweryfikowanej historii zawodnika…";
    else if(gameCount){
      const count=Number.isFinite(fieldCounts[index])?fieldCounts[index]:gameCount;
      cell.title="Potwierdzone występy: "+count+"/"+gameCount+
        (index>=3&&count<gameCount?" · część meczów bez danych rzutowych":"")+
        (data?.last_game?" · ostatni: "+data.last_game:"")+
        (data?.sample_source?" · "+data.sample_source:"");
    }else cell.title="Brak zweryfikowanych występów";
    row.append(cell);
  });
  return row;
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
  const rows=$("hzp-table-rows");rows.replaceChildren();
  if(!catalog){rows.append(make("div","hzp-empty","Pobieranie aktualnych składów NBA / ESPN…"));}
  else if(catalog.error||!players.length){
    rows.append(make("div","hzp-empty",catalog.error||"Brak potwierdzonych składów NBA. Spróbuj odświeżyć."));
  }else if(!matches.length){rows.append(make("div","hzp-empty","Nie znaleziono zawodnika dla wybranych filtrów."));}
  else{
    visible.forEach(p=>rows.append(playerRow(p)));
    // Original HOOPZARO identity badges are shown instead of unlicensed
    // ESPN/NBA photographs, for both free and premium visitors.
  }
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
  $("hzp-search").addEventListener("input",e=>{query=e.target.value;page=0;render(catalog,averages,role)});
  $("hzp-team").addEventListener("change",e=>{team=e.target.value;page=0;render(catalog,averages,role)});
  $("hzp-position").addEventListener("change",e=>{position=e.target.value;page=0;render(catalog,averages,role)});
  $("hzp-prev").addEventListener("click",()=>{page=Math.max(0,page-1);render(catalog,averages,role)});
  $("hzp-next").addEventListener("click",()=>{page++;render(catalog,averages,role)});
  $("hzp-refresh").addEventListener("click",()=>callbacks.refresh?.());
  $("hzp-cta").addEventListener("click",()=>entitled()?callbacks.openProps?.():callbacks.openPremium?.());
}
global.HoopzaroPlayers={init,render,resetRequests:()=>requestedIds.clear()};
})(window);
