/* BestBets Centrum: real ESPN/NBA schedule only, no simulated fixtures or probabilities.
   This module is isolated from the approved Player Props rendering and sizing. */
(function(){
"use strict";
let api=null,homeData=null,selectedDay="",pendingDay="";
function dayFromTimestamp(iso){
 const date=new Date(iso);if(!Number.isFinite(date.getTime()))return "";
 const parts=new Intl.DateTimeFormat("en-GB",{timeZone:"Europe/Warsaw",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(date);
 const get=type=>parts.find(p=>p.type===type)?.value||"";
 return get("year")+"-"+get("month")+"-"+get("day");
}
function dayOfGame(game){return game.day||dayFromTimestamp(game.start)}
function offsetDay(day,delta){
 const d=new Date(day+"T12:00:00Z");
 if(!Number.isFinite(d.getTime()))return day;
 d.setUTCDate(d.getUTCDate()+delta);
 return d.toISOString().slice(0,10);
}
function displayDay(day){
 const d=new Date(day+"T12:00:00Z");
 if(!Number.isFinite(d.getTime()))return day;
 return new Intl.DateTimeFormat("pl-PL",{weekday:"short",day:"numeric",month:"short",timeZone:"UTC"}).format(d);
}
function loadedGames(data,day){
 const extras=data?.calendar_extras||{};
 if(Object.prototype.hasOwnProperty.call(extras,day)){
   const extra=extras[day]||{};
   return {games:Array.isArray(extra.games)?extra.games:[],known:true,error:extra.error||""};
 }
 const loaded=Array.isArray(data?.calendar_loaded_days)?data.calendar_loaded_days:[];
 const all=Array.isArray(data?.calendar_games)?data.calendar_games:
           Array.isArray(data?.games)?data.games:[];
 const matches=all.filter(g=>dayOfGame(g)===day);
 // Old fixtures without calendar metadata still render, for regression QA.
 const known=loaded.includes(day)||matches.length>0||
  (!Array.isArray(data?.calendar_games) && Array.isArray(data?.games));
 return {games:matches,known:known,error:""};
}
function changeDay(direction){
 if(!homeData)return;
 const next=offsetDay(selectedDay,direction);
 if(!next || next===selectedDay)return;
 const today=homeData.calendar_today||selectedDay;
 const diff=Math.round((Date.parse(next+"T12:00:00Z")-Date.parse(today+"T12:00:00Z"))/86400000);
 if(Math.abs(diff)>366)return;
 selectedDay=next;
 const state=loadedGames(homeData,next);
 pendingDay=state.known?"":next;
 renderGames(homeData);
 if(pendingDay && api?.selectDay)api.selectDay(next);
}

const $=id=>document.getElementById(id);
const escapeHtml=raw=>String(raw==null?"":raw).replace(/[&<>"']/g,ch=>({
 "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
})[ch]);
function logo(code,uri) {
 if(typeof uri==="string" && uri.startsWith("data:image/png;base64,"))
   return '<img alt="" src="'+uri+'" loading="lazy">';
 return '<span>'+escapeHtml(code||"NBA")+'</span>';
}
function teamLogoUri(code){
 const list=Array.isArray(homeData?.form_options)?homeData.form_options:[];
 const row=list.find(item=>item.team===code);
 return row?.logo||"";
}
function teamBadge(code){
 const uri=teamLogoUri(code);
 return '<span class="bc-free-team">'+
   (typeof uri==="string"&&uri.startsWith("data:image/png;base64,")?'<img src="'+uri+'" alt="" loading="lazy">':"")+
   '<strong>'+escapeHtml(code||"NBA")+'</strong></span>';
}
function localTime(iso){
 if(!iso)return "—";
 const d=new Date(iso);
 if(!Number.isFinite(d.getTime()))return "—";
 return new Intl.DateTimeFormat("pl-PL",{hour:"2-digit",minute:"2-digit"}).format(d);
}
function status(g){
 if(g.state==="live")return '<b class="bc-gstatus live">NA ŻYWO</b>';
 if(g.state==="final")return '<span class="bc-gstatus">KONIEC</span>';
 return '<span class="bc-gstatus">'+escapeHtml(localTime(g.start))+'</span>';
}
function scoreboard(g) {
 if(g.state==="live"||g.state==="final"){
   if(g.home_score!=null && g.away_score!=null)
      return escapeHtml(String(g.away_score)+"–"+String(g.home_score));
 }
 return "vs";
}
function shortTeam(code,src){
 return logo(code,src)+'<b>'+escapeHtml(code||"NBA")+'</b>';
}
function renderTicker(data){
 const host=$("bc-ticker-games");
 if(!host)return;
 const games=(data&&Array.isArray(data.ticker))?data.ticker.slice(0,5):[];
 if(!games.length){
  host.innerHTML='<div class="bc-ticker-loading">'+(data&&data.error
    ? 'Dane terminarza niedostępne. Użyj ⟳, aby ponowić próbę.'
    : 'Brak potwierdzonych spotkań w najbliższym terminarzu.')+'</div>';
  return;
 }
 host.innerHTML=games.map((g,i)=>
  '<button type="button" class="bc-ticker-card'+(g.state==="live"?' live':'')+'" data-centre-game="'+i+'" aria-label="Szczegóły meczu '+escapeHtml(g.away)+' – '+escapeHtml(g.home)+'">'+
  '<span class="bc-ticker-time">'+escapeHtml(g.state==="live"?"NA ŻYWO":g.state==="final"?"KONIEC":localTime(g.start))+'</span>'+
  '<strong>'+escapeHtml(g.away)+' '+scoreboard(g)+' '+escapeHtml(g.home)+'</strong>'+
  '<small>'+escapeHtml(g.status||"NBA")+'</small></button>').join("");
}
function renderGames(data){
 const host=$("bc-games-list");if(!host)return;
 const today=data?.calendar_today||
    (data?.games?.[0]&&dayOfGame(data.games[0]))||dayFromTimestamp(new Date().toISOString());
 if(!selectedDay)selectedDay=data?.calendar_requested_day||today;
 const dateLabel=$("bc-selected-day");
 if(dateLabel){
  dateLabel.textContent=displayDay(selectedDay);
  dateLabel.title=selectedDay+(selectedDay===today?" — dzisiaj":"");
 }
 const day=loadedGames(data,selectedDay);
 if(day.known && pendingDay===selectedDay)pendingDay="";
 const title=host.closest(".bc-panel").querySelector(".bc-panel-title");
 if(title)title.setAttribute("aria-label","Mecze NBA: "+selectedDay);
 const prev=host.closest(".bc-panel").querySelector('[data-centre-day-dir="-1"]');
 const next=host.closest(".bc-panel").querySelector('[data-centre-day-dir="1"]');
 for(const control of [prev,next]){
  if(!control)continue;
  const diff=Number(control.getAttribute("data-centre-day-dir"));
  const boundary=Math.abs(Math.round((Date.parse(offsetDay(selectedDay,diff)+"T12:00:00Z")-
                  Date.parse(today+"T12:00:00Z"))/86400000))>366;
  control.disabled=boundary;
 }
 if(!day.known){
  host.innerHTML='<div class="bc-muted">'+(pendingDay===selectedDay
     ?'Pobieranie potwierdzonych spotkań z '+escapeHtml(selectedDay)+'…'
     :'Wybierz datę, aby pobrać spotkania.')+'</div>';
  return;
 }
 const games=day.games;
 if(!games.length){
  host.innerHTML='<div class="bc-muted">'+(day.error
    ?escapeHtml(day.error)
    :data?.error?'Terminarz niedostępny. Spróbuj odświeżyć dane NBA.'
    :'Brak spotkań NBA '+escapeHtml(selectedDay)+'.')+'</div>';
  return;
 }
 host.innerHTML=games.slice(0,20).map((g,i)=>{
   const scored=(g.state==="final"||g.state==="live");
   const valid=(g.away_score!=null && g.home_score!=null);
   const result=scored
     ?'<span class="bc-row-score'+(g.state==="live"?' live':'')+'" title="Wynik: '+escapeHtml(g.away)+' – '+escapeHtml(g.home)+'">'+
        (valid?escapeHtml(String(g.away_score)+" : "+String(g.home_score)):"—")+'</span>'
     :'<span class="bc-mini-btn">Podgląd ›</span>';
   return '<button class="bc-game" type="button" data-centre-row="'+i+'">'+
    '<span class="bc-gteam">'+shortTeam(g.away,g.away_logo)+'</span>'+
    '<span class="bc-gteam">'+shortTeam(g.home,g.home_logo)+'</span>'+
    status(g)+result+'</button>';
 }).join("");
}
function renderFinals(data){
 const host=$("bc-finals");if(!host)return;
 const games=data&&Array.isArray(data.finals)?data.finals.slice(0,2):[];
 if(!games.length){host.innerHTML='<div class="bc-muted">'+(data&&data.error
   ?'Wyniki niedostępne — źródło danych nie odpowiedziało.'
   :'Brak wyników potwierdzonych w bieżącym źródle.')+'</div>';return}
 host.innerHTML=games.map(g=>
   '<div class="bc-result">'+
   '<span>'+logo(g.away,g.away_logo)+' '+escapeHtml(g.away)+'</span>'+
   '<strong>'+scoreboard(g)+'</strong>'+
   '<span>'+escapeHtml(g.home)+' '+logo(g.home,g.home_logo)+'</span>'+
   '<span class="bc-result-time">KONIEC</span></div>'
 ).join("");
}

const TEAM_FAVORITES_KEY="bestbets.centrum.favoriteTeams.v1";
let favoriteTeams=[],teamPickerOpen=false;
function restoreTeamFavorites(){
 try{
  const stored=JSON.parse(window.localStorage.getItem(TEAM_FAVORITES_KEY)||"[]");
  if(Array.isArray(stored)){
   favoriteTeams=[...new Set(stored.filter(code=>typeof code==="string" && /^[A-Z]{3}$/.test(code)))].slice(0,2);
  }
 }catch(_){favoriteTeams=[];}
}
function storeTeamFavorites(){
 try{window.localStorage.setItem(TEAM_FAVORITES_KEY,JSON.stringify(favoriteTeams));}catch(_){}
}
function formCatalog(data){
 const options=Array.isArray(data?.form_options)?data.form_options:[];
 return options.filter(t=>t && /^[A-Z]{3}$/.test(t.team||""));
}
function favoriteStar(team){
 const selected=favoriteTeams.includes(team);
 return '<button type="button" class="bc-form-star'+(selected?' is-favorite':'')+
   '" data-centre-favorite="'+escapeHtml(team)+'" aria-pressed="'+String(selected)+
   '" aria-label="'+(selected?'Usuń '+escapeHtml(team)+' z ulubionych':'Dodaj '+escapeHtml(team)+' do ulubionych')+
   '" title="'+(selected?'Usuń z ulubionych':'Dodaj do ulubionych')+'">'+(selected?'★':'☆')+'</button>';
}
function renderFormPicker(data){
 const picker=$("bc-form-picker"),toggle=$("bc-form-toggle");
 if(!picker||!toggle)return;
 toggle.setAttribute("aria-expanded",String(teamPickerOpen));
 if(!teamPickerOpen){picker.hidden=true;return;}
 const oldScroll=picker.querySelector(".bc-form-picker-list")?.scrollTop||0;
 const catalog=formCatalog(data).sort((a,b)=>{
  const af=favoriteTeams.indexOf(a.team),bf=favoriteTeams.indexOf(b.team);
  if(af!==-1||bf!==-1)return af===-1?1:bf===-1?-1:af-bf;
  return String(a.name||a.team).localeCompare(String(b.name||b.team),"en");
 });
 picker.hidden=false;
 picker.innerHTML=
   '<div class="bc-form-picker-head"><strong>Wybierz drużyny</strong>'+
   '<span>'+favoriteTeams.length+'/2 ulubione</span></div>'+
   '<div class="bc-form-picker-hint" id="bc-form-picker-hint">Kliknij ☆, aby przypiąć drużynę u góry.</div>'+
   '<div class="bc-form-picker-list" role="group" aria-label="Wszystkie drużyny NBA">'+
   (catalog.length?catalog.map(t=>{
    const sample=Number(t.sample)||0;
    const known=t.record_verified===true || (!data?.form_period && sample>0);
    const recent=known?'Sezon '+escapeHtml(data?.form_period||'NBA')+
      ': '+escapeHtml(t.wins)+'–'+escapeHtml(t.losses):
      'Bilans sezonu niedostępny';
    return '<div class="bc-form-option'+(favoriteTeams.includes(t.team)?' is-favorite':'')+'">'+
      logo(t.team,t.logo)+
      '<span class="bc-form-option-label"><strong>'+escapeHtml(t.name||t.team)+'</strong>'+
      '<small>'+escapeHtml(t.team)+' · '+recent+'</small></span>'+
      favoriteStar(t.team)+'</div>';
   }).join(""):'<div class="bc-muted">Lista drużyn jest tymczasowo niedostępna.</div>')+
   '</div>';
 const scroll=picker.querySelector(".bc-form-picker-list");
 if(scroll)scroll.scrollTop=oldScroll;
}
function renderForm(data){
 const host=$("bc-forms");if(!host)return;
 const defaults=Array.isArray(data?.form)?data.form:[];
 const catalog=formCatalog(data);
 const byCode=new Map([...catalog,...defaults].filter(t=>t && t.team).map(t=>[t.team,t]));
 const visible=[],seen=new Set();
 for(const entry of [...favoriteTeams.map(code=>byCode.get(code)),...defaults]){
  if(!entry||seen.has(entry.team))continue;
  seen.add(entry.team);visible.push(entry);
  if(visible.length===2)break;
 }
 if(!visible.length){
  host.innerHTML='<div class="bc-muted">Brak wyników. Wybierz ulubione drużyny ☆.</div>';
 }else{
  host.innerHTML=visible.map(t=>{
   const sample=Number(t.sample)||0;
   const known=t.record_verified===true || (!data?.form_period && sample>0);
   return '<div class="bc-team-form">'+logo(t.team,t.logo)+
    '<strong>'+escapeHtml(t.team)+'</strong>'+
    '<span class="bc-form-record">'+(known?'Bilans '+escapeHtml(t.wins)+'–'+escapeHtml(t.losses):'Brak danych')+'</span>'+
    '<i>'+(known?escapeHtml(sample)+' mecz.':'—')+'</i>'+
    favoriteStar(t.team)+'</div>';
  }).join("");
 }
 const note=document.querySelector("#bestbets-centre .bc-team-panel .bc-panel-note");
 if(note && data?.form_period){
  note.textContent=data.form_available
    ?'☆ Sezon zasadniczy '+data.form_period+(data.form_stale?' · dane opóźnione':' · maks. 2 ulubione')
    :'☆ Sezon '+data.form_period+' · tabela niedostępna';
 }
 renderFormPicker(data);
}
function toggleTeamFavorite(code){
 if(!formCatalog(homeData).some(team=>team.team===code))return;
 if(favoriteTeams.includes(code)){
  favoriteTeams=favoriteTeams.filter(item=>item!==code);
 }else if(favoriteTeams.length>=2){
  const hint=$("bc-form-picker-hint");
  if(hint){
   hint.textContent="Możesz wybrać maksymalnie 2 drużyny. Najpierw usuń jedną gwiazdkę.";
   hint.classList.add("bc-form-limit");
  }else{
   const toggle=$("bc-form-toggle");
   if(toggle){teamPickerOpen=true;renderFormPicker(homeData);}
   const message=$("bc-form-picker-hint");
   if(message){message.textContent="Limit 2 ulubionych. Odznacz jedną drużynę.";message.classList.add("bc-form-limit");}
  }
  return;
 }else{
  favoriteTeams.push(code);
 }
 storeTeamFavorites();
 renderForm(homeData);
}
function renderPlayers(data){
 const rows=Array.isArray(data&&data.players)?data.players.slice(0,3):[];
 const watch=document.querySelector(".bc-watch");
 if(!watch)return;
 const mappers={PTS:"points",REB:"rebounds",AST:"assists","3PM":"three-pointers"};
 const real=rows.filter(p=>p && typeof p.name==="string" &&
   Number.isFinite(Number(p.value)) && Number(p.value)>0 && mappers[p.market]);
 if(!real.length){
   watch.innerHTML='<div class="bc-muted">Dane zawodników są tymczasowo niedostępne.</div>';
   return;
 }
 const initial=p=>String(p.name).trim().split(/\\s+/).map(n=>n[0]||"").slice(0,2).join("").toUpperCase();
 const sampleLine=p=>Math.max(.5,Math.floor(Number(p.value))-.5).toFixed(1);
 const query=p=>p.name+" over "+sampleLine(p)+" "+mappers[p.market];
 const safeQuery=p=>escapeHtml(query(p));
 watch.innerHTML=real.map(p=>
  '<button type="button" data-centre-query="'+safeQuery(p)+'" title="Przykładowy próg do analizy historii, nie typ bukmacherski">'+
  freeAvatar(p).replace('bc-free-avatar','bc-free-avatar bc-watch-avatar')+
  '<span class="bc-watch-name">'+escapeHtml(p.name)+'</span>'+teamBadge(p.team)+
  '<span class="bc-watch-chevron">›</span></button>').join("");
 window.HoopzaroPortraits?.observe(watch);
}
let pendingFreeLeaderKey=null, freeRenderSignature="",freeInfoOpen=false,pendingFreeReferral=null;
const freeLabels={PTS:"Lider punktów",REB:"Lider zbiórek",AST:"Lider asyst"};
const FREE_REFERRAL_KEY="hoopzaro.freePropsReferral.v1";
function localDay(){
 const d=new Date();return [d.getFullYear(),String(d.getMonth()+1).padStart(2,"0"),String(d.getDate()).padStart(2,"0")].join("-");
}
function usedFreeReferral(){
 try{
  const stored=JSON.parse(localStorage.getItem(FREE_REFERRAL_KEY)||"null");
  return stored&&stored.day===localDay()&&typeof stored.leaderKey==="string"?stored:null;
 }catch(_){return null;}
}
function freeReferralQuery(p){
 const markets={PTS:"points",REB:"rebounds",AST:"assists"};
 const value=Number(p.value);
 if(!markets[p.market]||!Number.isFinite(value)||value<=0)return "";
 return p.name+" over "+Math.max(.5,Math.floor(value)-.5).toFixed(1)+" "+markets[p.market];
}
function referralButton(p,verified){
 if(!verified)return "";
 const query=freeReferralQuery(p),used=usedFreeReferral();
 if(!query)return "";
 if(used&&used.leaderKey!==p.detail_key){
  return '<div class="bc-free-referral used">Dzisiejsze darmowe przejście do Player Props zostało wykorzystane. Kolejne analizy będą dostępne w Premium.</div>';
 }
 return '<div class="bc-free-referral"><span>'+(used?"Otwórz ponownie dzisiejszą analizę":"1 darmowe przejście do Player Props dziennie")+
  ' · próg przykładowy, nie rekomendacja zakładu</span><button type="button" data-centre-free-props="'+
  escapeHtml(p.detail_key)+'">'+(used?"Otwórz ponownie ›":"Przejdź do Player Props ›")+'</button></div>';
}
function recordFreePropsResult(player,error,currentQuery){
 if(!pendingFreeReferral)return;
 if(error||!player){if(error)pendingFreeReferral=null;return;}
 if(currentQuery!==pendingFreeReferral.query)return;
 if(!Array.isArray(player.games)||!player.games.length){pendingFreeReferral=null;return;}
 try{localStorage.setItem(FREE_REFERRAL_KEY,JSON.stringify({day:pendingFreeReferral.day,leaderKey:pendingFreeReferral.leaderKey}));}catch(_){}
 pendingFreeReferral=null;
}
const initials=p=>String(p.name||"").trim().split(/\s+/).slice(0,2).map(v=>v[0]||"").join("").toUpperCase();
function freeAvatar(p){
 const allowed=homeData?.free_photos_enabled===true && /^[0-9]{1,20}$/.test(p.athlete_id||"");
 const photo=allowed?'<img hidden loading="eager" decoding="async" alt="'+escapeHtml(p.name)+
   '" src="https://a.espncdn.com/i/headshots/nba/players/full/'+p.athlete_id+'.png">':"";
 return '<span class="bc-player-circle bc-free-avatar" data-hoop-player="'+escapeHtml(p.name||"")+'"><span>'+escapeHtml(initials(p))+'</span>'+photo+'</span>';
}
function renderFreeLeaders(data){
 const host=document.querySelector(".bc-pick-list");if(!host)return;
 const rows=Array.isArray(data?.free_leaders)?data.free_leaders:[];
 const signature=JSON.stringify([rows,data?.free_leader_day,data?.free_warning,data?.free_photos_enabled]);
 if(signature===freeRenderSignature)return;
 freeRenderSignature=signature;
 if(!data?.free_leader_day || data?.free_warning){
  host.innerHTML='<div class="bc-muted">'+escapeHtml(data?.free_warning||
    "Brak potwierdzonych liderów zakończonych spotkań NBA. Sprawdź ponownie po meczach.")+'</div>';return;
 }
 host.innerHTML=Object.keys(freeLabels).map(market=>{
  const p=rows.find(r=>r.market===market && /^[0-9a-f]{64}$/.test(r.detail_key||""));
  if(!p)return '<div class="bc-pick bc-free-missing"><span class="bc-pick-tag">'+market+
    '</span><span>Brak pełnych danych '+market+' · '+escapeHtml(data.free_leader_day)+' NBA/ET</span></div>';
  return '<button class="bc-pick" type="button" data-centre-free-key="'+p.detail_key+
    '" title="'+escapeHtml(p.name)+' · '+escapeHtml(freeLabels[market])+
    (p.tie_count>1?' (ex aequo)':'')+' — zakończone mecze NBA/ET">'+freeAvatar(p)+
    '<span class="bc-pick-info"><strong>'+escapeHtml(p.name)+'</strong><small>'+escapeHtml(freeLabels[market])+
    ' · '+escapeHtml(p.value)+' '+market+(p.tie_count>1?' · ex aequo':'')+'</small></span>'+
    '<span class="bc-pick-tag">'+market+'</span><span class="bc-pick-explain">'+teamBadge(p.team)+' vs '+
    teamBadge(p.opponent)+'<br><i>'+escapeHtml(p.date)+' NBA/ET</i></span>'+
    '<span class="bc-mini-btn">Szczegóły ›</span></button>';
 }).join("");
 window.HoopzaroPortraits?.observe(host);
}
function freeDetailsBody(p,stats,note,verified=false){
 return '<div class="bc-free-heading">'+freeAvatar(p)+'<div><strong>'+escapeHtml(p.name)+
  '</strong><div class="bc-free-match">'+teamBadge(p.team)+' vs '+teamBadge(p.opponent)+
  ' · '+escapeHtml(p.date)+' NBA/ET</div></div></div><div class="bc-free-stats">'+
  ["PTS","REB","AST","3PM"].map(key=>'<div class="bc-free-stat"><strong>'+escapeHtml(stats?.[key]??"—")+
  '</strong><span>'+key+'</span></div>').join("")+'</div><p class="bc-free-note" role="status">'+escapeHtml(note)+
  '</p>'+referralButton(p,verified)+'<div class="bc-free-premium"><strong>Odkryj więcej z HOOPZARO Premium</strong>'+
  '<span>Zaawansowane wykresy, analizy zawodników i symulacje.</span>'+
  '<button type="button" data-centre-premium>Premium — wkrótce ›</button></div>';
}
function showFreeDetails(p,stats,note,verified=false){
 setText("bc-dialog-title",p.name+" — występ NBA");
 $("bc-dialog-body").innerHTML=freeDetailsBody(p,stats,note,verified);
 window.HoopzaroPortraits?.observe($("bc-dialog-body"));
 $("bc-dialog").classList.add("bc-free-detail-dialog");
 $("bc-dialog").hidden=false;
}
function openFreeLeader(key){
 const leader=(homeData?.free_leaders||[]).find(p=>p.detail_key===key);
 if(!leader)return;
 pendingFreeLeaderKey=key;
 showFreeDetails(leader,null,"Pobieram statystyki tego spotkania z ESPN…");
 $("bc-dialog").querySelector(".bc-dialog-close").focus();
 if(api.leaderDetails)api.leaderDetails(key);
}
function renderFreeLeaderDetails(reply){
 if(!reply||!pendingFreeLeaderKey||reply.key!==pendingFreeLeaderKey)return;
 const leader=(homeData?.free_leaders||[]).find(p=>p.detail_key===pendingFreeLeaderKey);
 pendingFreeLeaderKey=null;
 if(!leader){modal("Statystyki meczu","Lista liderów została zaktualizowana. Otwórz szczegóły ponownie.");return;}
 const p=reply.data;
 const valid=p?.verified===true && p.athlete_id===leader.athlete_id && p.date===leader.date &&
   ["PTS","REB","AST","3PM"].every(k=>Number.isInteger(p[k])&&p[k]>=0);
 if(reply.error||!valid){
  showFreeDetails(leader,null,String(reply.error||"Pełne statystyki tego meczu są chwilowo niedostępne w ESPN."));return;
 }
 showFreeDetails(leader,p,(p.stale?"Dane z pamięci podręcznej — ESPN chwilowo niedostępne. ":"")+
  "Potwierdzony wynik jednego zakończonego meczu ESPN. Nie jest prognozą przyszłego występu.",true);
}
function renderSimulationPreview(data){
 const box=document.querySelector(".bc-lock-teams");
 if(!box)return;
 const teams=box.querySelectorAll(":scope > span");
 if(teams.length<2)return;
 const games=Array.isArray(data&&data.games)?data.games:[];
 const g=games.find(x=>x.state==="scheduled") || games[0];
 teams[0].textContent=g?g.away:"—";
 teams[1].textContent=g?g.home:"—";
}
function setText(id,v){const e=$(id);if(e)e.textContent=v}
function renderHome(data,details){
 homeData=data;
 if(data && !selectedDay){
   selectedDay=data.calendar_requested_day||data.calendar_today||
     (data.games?.[0]&&dayOfGame(data.games[0]))||
     dayFromTimestamp(new Date().toISOString());
 }
 const button=$("bc-refresh");
 if(button){
   button.disabled=false;
   button.title=data&&data.error?data.error:"Odśwież terminarz, wyniki i statystyki";
 }
 const signal=$("bc-source-state");
 if(signal){
   const color=data?(data.error?"#ff9b40":data.stale?"#ffb24a":"#04ee8a"):"#8aa9c5";
   signal.style.color=color;
   signal.textContent=data?(data.error?"● Problem":"● Dane NBA"):"● Ładowanie";
 }
 if(!data){
  renderPlayers({players:[]});renderFreeLeaders(null);
  setText("bc-data-meta","Ładowanie potwierdzonych danych NBA / ESPN…");
  return;
 }
 renderTicker(data);renderGames(data);renderFinals(data);renderForm(data);renderPlayers(data);renderFreeLeaders(data);renderSimulationPreview(data);
 renderFreeLeaderDetails(details);
 const now=new Date();
 setText("bc-local-time","Czas lokalny: "+new Intl.DateTimeFormat("pl-PL",{hour:"2-digit",minute:"2-digit",timeZoneName:"short"}).format(now));
 const message=data.error
  ? "Aktualne dane chwilowo niedostępne: "+data.error
  : "Dane: "+(data.source||"NBA / ESPN")+" · "+(data.coverage||"wybrany okres")+" · aktualizacja "+(data.fetched_at||data.as_of||"")+". Status LIVE może być opóźniony.";
 setText("bc-data-meta",message);
}
function modal(title,body){
 setText("bc-dialog-title",title);
 const e=$("bc-dialog-body");if(e)e.textContent=body;
 $("bc-dialog").classList.remove("bc-free-detail-dialog");
 $("bc-dialog").hidden=false;
 $("bc-dialog").querySelector(".bc-dialog-close").focus();
}
function close(){pendingFreeLeaderKey=null;$("bc-dialog").hidden=true}
function gameDetails(g){
 if(!g)return;
 const kick=localTime(g.start);
 const description=(g.state==="live"?"Mecz trwa":g.state==="final"?"Mecz zakończony":"Mecz zaplanowany")+
  ".\n"+g.away+" vs "+g.home+" · "+kick+
  (g.state!=="scheduled" && g.away_score!=null && g.home_score!=null
   ? "\nWynik: "+g.away+" "+g.away_score+" – "+g.home_score+" "+g.home_score:"")+
   "\nŹródło: "+(homeData&&homeData.source||"NBA / ESPN");
 modal("Mecz NBA",description);
}
function showSchedule(){
 const list=homeData&&(homeData.all_games||homeData.games)||[];
 modal("Terminarz NBA — pobrane spotkania",list.length
  ?list.map(g=>g.day+" · "+g.away+" vs "+g.home+" • "+(g.state==="live"?"NA ŻYWO":g.state==="final"?"Koniec":localTime(g.start))).join("\n")
  :"Nie ma obecnie dostępnego, potwierdzonego terminarza dla tej daty.");
}
function premium(){
 modal("HOOPZARO Premium — wkrótce",
   "Przygotowujemy rozbudowane modele, głębsze analizy zawodników i symulacje NBA.\n\n"+
   "Subskrypcje i płatności NIE są jeszcze uruchomione. Wszystkie widoczne informacje w Centrum są darmowe.");
}
function photoCredits(){
 const photos=window.HoopzaroPortraits?.credits()||[];
 setText("bc-dialog-title","Zdjęcia zawodników — autorzy i licencje");
 const body=$("bc-dialog-body");
 body.innerHTML='<div class="bc-photo-credit-list"><p>Fotografie pochodzą z Wikimedia Commons. Autorzy i warunki użycia dla zdjęć załadowanych na tym ekranie:</p>'+
  (photos.length?'<ul>'+photos.map(p=>'<li>'+escapeHtml(p.artist)+' · '+
   '<a target="_blank" rel="noopener noreferrer" href="'+escapeHtml(p.source)+'">oryginalne zdjęcie</a> · '+
   '<a target="_blank" rel="noopener noreferrer" href="'+escapeHtml(p.licenseUrl)+'">'+escapeHtml(p.license)+'</a> · kadrowanie do miniatury</li>').join("")+'</ul>':
   '<p>Nie załadowano jeszcze zdjęć z otwartą licencją. Dla niedostępnych fotografii wyświetlamy inicjały.</p>')+
   '<p>Publiczne wykorzystanie wizerunków sportowców i dodatkowe prawa należy osobno zweryfikować przed premierą płatną.</p></div>';
 $("bc-dialog").classList.remove("bc-free-detail-dialog");
 $("bc-dialog").hidden=false;
 $("bc-dialog").querySelector(".bc-dialog-close")?.focus();
}
function toggleFreeInfo(force){
 const panel=$("bc-free-info-popup"),button=$("bc-free-info-toggle"),backdrop=$("bc-free-info-backdrop");
 if(!panel||!button||!backdrop)return;
 freeInfoOpen=typeof force==="boolean"?force:!freeInfoOpen;
 backdrop.hidden=!freeInfoOpen;
 button.setAttribute("aria-expanded",String(freeInfoOpen));
 if(freeInfoOpen)panel.querySelector(".bc-free-info-heading button")?.focus();
}
function init(context){
 api=context;
 const centre=$("bestbets-centre");
 if(!centre || centre.dataset.ready==="1")return;
 centre.dataset.ready="1";
 restoreTeamFavorites();
 // A transformed app stage would constrain position:fixed to the scaled canvas.
 // Move the glossary into <body> so the backdrop can cover the full iframe.
 const freeInfoPopup=$("bc-free-info-popup");
 if(freeInfoPopup && !$("bc-free-info-backdrop")){
  const backdrop=document.createElement("div");
  backdrop.id="bc-free-info-backdrop";
  backdrop.className="bc-free-info-backdrop";
  backdrop.hidden=true;
  document.body.appendChild(backdrop);
  backdrop.appendChild(freeInfoPopup);
  freeInfoPopup.hidden=false;
 }
 // Small noninvasive refresh icon and data-source indicator in the ticker.
 // Adds no layout width and doesn't change the approved neon design.
 const tickerHead=centre.querySelector(".bc-ticker-head");
 if(tickerHead){
   tickerHead.style.position="relative";
   const badge=document.createElement("span");
   badge.id="bc-source-state";badge.textContent="● Ładowanie";
   badge.style.cssText="position:absolute;right:4px;bottom:2px;font-size:7px;font-weight:800;white-space:nowrap;background:#071b2e;padding:1px 2px;border-radius:4px";
   badge.setAttribute("aria-live","polite");
   tickerHead.appendChild(badge);
   const refresh=document.createElement("button");
   refresh.type="button";refresh.id="bc-refresh";
   refresh.textContent="⟳";
   refresh.style.cssText="position:absolute;right:3px;top:3px;display:grid;place-items:center;width:18px;height:18px;padding:0;border:1px solid #4989b0;border-radius:50%;background:#082841;color:#a6e8ff;font-size:17px;line-height:16px";
   refresh.setAttribute("data-centre-refresh","");
   refresh.setAttribute("aria-label","Odśwież dane NBA");
   refresh.title="Odśwież terminarz, wyniki i statystyki";
   tickerHead.appendChild(refresh);
 }
 centre.addEventListener("load",event=>{
  const img=event.target;if(!img.matches?.(".bc-free-avatar img"))return;
  img.hidden=false;img.previousElementSibling.hidden=true;
 },true);
 centre.addEventListener("error",event=>{
  const img=event.target;if(!img.matches?.(".bc-free-avatar img"))return;
  img.hidden=true;img.previousElementSibling.hidden=false;img.removeAttribute("src");
 },true);
 centre.addEventListener("click",function(event){
  const button=event.target.closest("button");
  if(!button)return;
  if(button.matches("[data-centre-free-info]")){
   toggleFreeInfo(button.id==="bc-free-info-toggle"?!freeInfoOpen:false);
   if(!freeInfoOpen && button.id!=="bc-free-info-toggle")$("bc-free-info-toggle")?.focus();
   return;
  }
  if(button.matches("[data-centre-photo-credits]")){photoCredits();return;}
  if(button.matches("[data-centre-form-toggle]")){
   teamPickerOpen=!teamPickerOpen;
   renderFormPicker(homeData);
   return;
  }
  const team=button.getAttribute("data-centre-favorite");
  if(team!==null){event.stopPropagation();toggleTeamFavorite(team);return;}
  const leader=button.getAttribute("data-centre-free-key");
  if(leader!==null){openFreeLeader(leader);return;}
  const freeProps=button.getAttribute("data-centre-free-props");
  if(freeProps!==null){
   const row=(homeData?.free_leaders||[]).find(p=>p.detail_key===freeProps);
   if(!row||!api.search)return;
   const used=usedFreeReferral();
   if(used&&used.leaderKey!==freeProps){premium();return;}
   const query=freeReferralQuery(row);
   if(!query)return;
   pendingFreeReferral={day:localDay(),leaderKey:freeProps,query:query};
   close();api.search(query);return;
  }
  const nav=button.getAttribute("data-centre-nav");
  const query=button.getAttribute("data-centre-query");
  if(nav&&api.go){api.go(nav);return}
  if(query&&api.search){api.search(query);return}
  const dayDirection=button.getAttribute("data-centre-day-dir");
  if(dayDirection==="1"||dayDirection==="-1"){changeDay(Number(dayDirection));return}
  if(button.matches("[data-centre-refresh]")){
    setText("bc-data-meta","Sprawdzanie dostępnych aktualizacji danych NBA…");
    if(api.refresh)api.refresh();
    return;
  }
  if(button.matches("[data-centre-premium]")){premium();return}
  if(button.matches("[data-centre-all-games]")){showSchedule();return}
  if(button.matches("[data-centre-close]")){close();return}
  const row=button.getAttribute("data-centre-row");
  if(row!=null){
    const day=loadedGames(homeData,selectedDay);
    gameDetails(day.games&&day.games[Number(row)]);return
  }
  const idx=button.getAttribute("data-centre-game");
  if(idx!=null){gameDetails(homeData&&homeData.ticker&&homeData.ticker[Number(idx)]);return}
 });
 $("bc-dialog").addEventListener("click",ev=>{if(ev.target===$("bc-dialog"))close()});
 document.addEventListener("click",ev=>{
  if(teamPickerOpen && !ev.target.closest("#bestbets-centre .bc-team-panel")){
   teamPickerOpen=false;renderFormPicker(homeData);
  }
  if(freeInfoOpen&&!ev.target.closest("#bc-free-info-backdrop .bc-free-info-popup") &&
     !ev.target.closest("#bc-free-info-toggle"))toggleFreeInfo(false);
 });
 // The close button is outside the Centrum click delegate after the popup is moved.
 $("bc-free-info-popup")?.addEventListener("click",ev=>{
  if(ev.target.closest("[data-centre-free-info]")){
   toggleFreeInfo(false);$("bc-free-info-toggle")?.focus();
  }
 });
 document.addEventListener("keydown",ev=>{
  if(ev.key!=="Escape")return;
  if(freeInfoOpen){
   toggleFreeInfo(false);
   $("bc-free-info-toggle")?.focus();
  }else if(teamPickerOpen){
   teamPickerOpen=false;renderFormPicker(homeData);
   $("bc-form-toggle")?.focus();
  }else if(!$("bc-dialog").hidden)close();
 });
}
window.BestBetsCentre={init:init,render:renderHome,openPremium:premium,recordFreePropsResult:recordFreePropsResult};
})();
