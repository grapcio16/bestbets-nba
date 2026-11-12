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
 const picks=document.querySelector(".bc-pick-list"),watch=document.querySelector(".bc-watch");
 const hot=document.querySelector(".bc-hot");
 if(!picks||!watch||!hot)return;
 const mappers={PTS:"points",REB:"rebounds",AST:"assists","3PM":"three-pointers"};
 const real=rows.filter(p=>p && typeof p.name==="string" &&
   Number.isFinite(Number(p.value)) && Number(p.value)>0 && mappers[p.market]);
 if(!real.length){
   picks.innerHTML='<div class="bc-muted">Brak potwierdzonych liderów ostatnich meczów w dostępnym feedzie NBA.</div>';
   watch.innerHTML='<div class="bc-muted">Dane zawodników są tymczasowo niedostępne.</div>';
   hot.querySelectorAll("button").forEach(b=>b.remove());
   const title=hot.querySelector(".bc-hot-title");
   if(title)title.innerHTML='<span class="bc-orange-icon">◎</span> Ostatnie występy <span class="bc-free-tag">FREE</span>';
   return;
 }
 const initial=p=>String(p.name).trim().split(/\s+/).map(n=>n[0]||"").slice(0,2).join("").toUpperCase();
 const sampleLine=p=>Math.max(.5,Math.floor(Number(p.value))-.5).toFixed(1);
 const query=p=>p.name+" over "+sampleLine(p)+" "+mappers[p.market];
 const safeQuery=p=>escapeHtml(query(p));
 picks.innerHTML=real.map(p=>
  '<button class="bc-pick" type="button" data-centre-query="'+safeQuery(p)+'" title="Linia poglądowa; wyłącznie do sprawdzenia historii, nie rekomendacja zakładu">'+
  '<span class="bc-player-circle">'+escapeHtml(initial(p))+'</span>'+
  '<span class="bc-pick-info"><strong>'+escapeHtml(p.name)+'</strong><small>Ostatni mecz: '+escapeHtml(p.value)+' '+escapeHtml(p.market)+'</small></span>'+
  '<span class="bc-pick-tag">'+escapeHtml(p.market)+'</span>'+
  '<span class="bc-pick-explain">Potwierdzony występ<br><i>'+escapeHtml(p.date||"")+" · "+escapeHtml(p.team||"NBA")+'</i></span>'+
  '<span class="bc-mini-btn">Historia ›</span></button>').join("");
 watch.innerHTML=real.map(p=>
  '<button type="button" data-centre-query="'+safeQuery(p)+'" title="Przykładowy próg do analizy historii, nie typ bukmacherski">'+
  '<b>'+escapeHtml(initial(p))+'</b> '+escapeHtml(p.name)+' <span>›</span></button>').join("");
 const title=hot.querySelector(".bc-hot-title");
 if(title)title.innerHTML='<span class="bc-orange-icon">◎</span> Ostatnie występy <span class="bc-free-tag">FREE</span>';
 hot.querySelectorAll("button").forEach(b=>b.remove());
 for(const p of real) {
  const button=document.createElement("button");
  button.type="button";button.setAttribute("data-centre-query",query(p));
  button.title="Dane z ostatniego meczu, linia wyłącznie demonstracyjna";
  button.textContent=initial(p)+"  "+p.name.split(/\s+/).slice(-1)[0]+" "+p.market+" "+p.value+"  ›";
  hot.appendChild(button);
 }
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
function renderHome(data){
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
  renderPlayers({players:[]});
  setText("bc-data-meta","Ładowanie potwierdzonych danych NBA / ESPN…");
  return;
 }
 renderTicker(data);renderGames(data);renderFinals(data);renderForm(data);renderPlayers(data);renderSimulationPreview(data);
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
 $("bc-dialog").hidden=false;
 $("bc-dialog").querySelector(".bc-dialog-close").focus();
}
function close(){$("bc-dialog").hidden=true}
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
 modal("BestBets Premium — wkrótce",
   "Przygotowujemy rozbudowane modele, głębsze analizy zawodników i symulacje NBA.\n\n"+
   "Subskrypcje i płatności NIE są jeszcze uruchomione. Wszystkie widoczne informacje w Centrum są darmowe.");
}
function init(context){
 api=context;
 const centre=$("bestbets-centre");
 if(!centre || centre.dataset.ready==="1")return;
 centre.dataset.ready="1";
 restoreTeamFavorites();
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
 centre.addEventListener("click",function(event){
  const button=event.target.closest("button");
  if(!button)return;
  if(button.matches("[data-centre-form-toggle]")){
   teamPickerOpen=!teamPickerOpen;
   renderFormPicker(homeData);
   return;
  }
  const team=button.getAttribute("data-centre-favorite");
  if(team!==null){event.stopPropagation();toggleTeamFavorite(team);return;}
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
 });
 document.addEventListener("keydown",ev=>{
  if(ev.key!=="Escape")return;
  if(teamPickerOpen){
   teamPickerOpen=false;renderFormPicker(homeData);
   $("bc-form-toggle")?.focus();
  }else if(!$("bc-dialog").hidden)close();
 });
}
window.BestBetsCentre={init:init,render:renderHome};
})();