/* BestBets Centrum: real ESPN/NBA schedule only, no simulated fixtures or probabilities.
   This module is isolated from the approved Player Props rendering and sizing. */
(function(){
"use strict";
let api=null,homeData=null;
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
  host.innerHTML='<div class="bc-ticker-loading">Brak potwierdzonych spotkań w najbliższym terminarzu.</div>';return;
 }
 host.innerHTML=games.map((g,i)=>
  '<button type="button" class="bc-ticker-card'+(g.state==="live"?' live':'')+'" data-centre-game="'+i+'" aria-label="Szczegóły meczu '+escapeHtml(g.away)+' – '+escapeHtml(g.home)+'">'+
  '<span class="bc-ticker-time">'+escapeHtml(g.state==="live"?"NA ŻYWO":g.state==="final"?"KONIEC":localTime(g.start))+'</span>'+
  '<strong>'+escapeHtml(g.away)+' '+scoreboard(g)+' '+escapeHtml(g.home)+'</strong>'+
  '<small>'+escapeHtml(g.status||"NBA")+'</small></button>').join("");
}
function renderGames(data){
 const host=$("bc-games-list");if(!host)return;
 const games=data&&Array.isArray(data.games)?data.games.slice(0,5):[];
 const title=host.closest(".bc-panel").querySelector(".bc-panel-title");
 if(title)title.childNodes.forEach(n=>{if(n.nodeType===3)n.textContent=games.length&&data.day_label!=="Dziś"?" Mecze najbliższe ":" Mecze dnia "});
 if(!games.length){host.innerHTML='<div class="bc-muted">Brak potwierdzonych spotkań na dziś. Sprawdź terminarz później.</div>';return}
 host.innerHTML=games.map((g,i)=>
  '<button class="bc-game" type="button" data-centre-row="'+i+'">'+
  '<span class="bc-gteam">'+shortTeam(g.away,g.away_logo)+'</span>'+
  '<span class="bc-gteam">'+shortTeam(g.home,g.home_logo)+'</span>'+
  status(g)+
  '<span class="bc-mini-btn">Podgląd ›</span></button>').join("");
}
function renderFinals(data){
 const host=$("bc-finals");if(!host)return;
 const games=data&&Array.isArray(data.finals)?data.finals.slice(0,2):[];
 if(!games.length){host.innerHTML='<div class="bc-muted">Brak wyników potwierdzonych w bieżącym źródle.</div>';return}
 host.innerHTML=games.map(g=>
   '<div class="bc-result">'+
   '<span>'+logo(g.away,g.away_logo)+' '+escapeHtml(g.away)+'</span>'+
   '<strong>'+scoreboard(g)+'</strong>'+
   '<span>'+escapeHtml(g.home)+' '+logo(g.home,g.home_logo)+'</span>'+
   '<span class="bc-result-time">KONIEC</span></div>'
 ).join("");
}
function renderForm(data){
 const host=$("bc-forms");if(!host)return;
 const teams=data&&Array.isArray(data.form)?data.form.slice(0,2):[];
 if(!teams.length){host.innerHTML='<div class="bc-muted">Brak wystarczających wyników do oceny formy.</div>';return;}
 host.innerHTML=teams.map(t=>
   '<div class="bc-team-form">'+logo(t.team,t.logo)+'<strong>'+escapeHtml(t.team)+'</strong>'+
   '<span>Bilans '+escapeHtml(t.wins)+"–"+escapeHtml(t.losses)+'</span>'+
   '<i>'+escapeHtml(t.sample)+' mecz.</i></div>').join("");
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
 centre.addEventListener("click",function(event){
  const button=event.target.closest("button");
  if(!button)return;
  const nav=button.getAttribute("data-centre-nav");
  const query=button.getAttribute("data-centre-query");
  if(nav&&api.go){api.go(nav);return}
  if(query&&api.search){api.search(query);return}
  if(button.matches("[data-centre-premium]")){premium();return}
  if(button.matches("[data-centre-all-games]")){showSchedule();return}
  if(button.matches("[data-centre-close]")){close();return}
  const row=button.getAttribute("data-centre-row");
  if(row!=null){gameDetails(homeData&&homeData.games&&homeData.games[Number(row)]);return}
  const idx=button.getAttribute("data-centre-game");
  if(idx!=null){gameDetails(homeData&&homeData.ticker&&homeData.ticker[Number(idx)]);return}
 });
 $("bc-dialog").addEventListener("click",ev=>{if(ev.target===$("bc-dialog"))close()});
 document.addEventListener("keydown",ev=>{if(ev.key==="Escape"&&!$("bc-dialog").hidden)close()});
}
function failLoading(message){
 const safe=String(message||"Źródło danych NBA jest niedostępne.");
 const msg='<div class="bc-muted">'+escapeHtml(safe)+'</div>';
 const ticker=$("bc-ticker-games"),games=$("bc-games-list"),finals=$("bc-finals"),forms=$("bc-forms");
 if(ticker)ticker.innerHTML='<div class="bc-ticker-loading">'+escapeHtml(safe)+'</div>';
 if(games)games.innerHTML=msg;
 if(finals)finals.innerHTML=msg;
 if(forms)forms.innerHTML=msg;
 renderPlayers({players:[]});
 setText("bc-data-meta","Status źródeł NBA: "+safe);
}
window.BestBetsCentre={init:init,render:renderHome,error:failLoading};
})();