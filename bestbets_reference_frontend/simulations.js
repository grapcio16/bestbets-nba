/* Premium NBA simulation canvas: real ESPN fixtures; no fictional projections.
   Paid analytics data is supplied solely after a server-verified entitlement. */
(function(){
"use strict";
const $=id=>document.getElementById(id);
const esc=value=>String(value==null?"":value).replace(/[&<>"']/g,char=>({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
})[char]);
const safeDate=day=>/^\d{4}-\d{2}-\d{2}$/.test(String(day||""));
const WARSAW="Europe/Warsaw";
const fmt=value=>value!==null&&value!==undefined&&value!==""&&Number.isFinite(Number(value))
  ?Number(value).toFixed(1).replace(".",","):"—";
const percent=value=>Number.isFinite(Number(value))?fmt(value)+"%":"—";
const modelLabel=()=>state.model==="legacy_v72"?"V7.2":state.model==="research_form_v74"?"V7.4":"V7.5 · PEŁNY KONTEKST (BADAWCZY)";
const dayShift=(day,n)=>{const d=new Date(day+"T12:00:00Z");d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10)};
function localDay(iso){
  const parts=new Intl.DateTimeFormat("en-GB",{timeZone:WARSAW,year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date(iso));
  const get=type=>parts.find(part=>part.type===type)?.value||"";
  return get("year")+"-"+get("month")+"-"+get("day");
}
function clock(start){
  if(!start)return "—";
  const d=new Date(start);
  if(!Number.isFinite(d.getTime()))return "—";
  return new Intl.DateTimeFormat("pl-PL",{hour:"2-digit",minute:"2-digit",hour12:false}).format(d);
}
function labelDay(day){
  if(!safeDate(day))return "Wybierz dzień";
  return new Intl.DateTimeFormat("pl-PL",{timeZone:"UTC",day:"numeric",month:"long",year:"numeric"})
    .format(new Date(day+"T12:00:00Z")).toUpperCase();
}
function withinRange(day){
  if(!safeDate(day))return false;
  return Math.abs(Math.round((new Date(day+"T12:00:00Z")-new Date(localDay(new Date().toISOString())+"T12:00:00Z"))/86400000))<=366;
}
const state={day:"",gameId:"",model:"research_form_v74",chart:"match",view:"results",expanded:false,playerTeam:"all",playerQuery:"",playerIndex:-1,fromProps:null,requestedDay:"",gamePending:"",playersPending:"",lastHome:null,lastPremium:null};
let callbacks=null;
const MODEL_CHOICES=[
  {id:"research_context_v75",label:"V7.5 · PEŁNY KONTEKST"},
  {id:"research_form_v74",label:"V7.4 · FORMA + KONTEKST"},
  {id:"legacy_v72",label:"V7.2 · PODSTAWOWY"},
];
function syncModelDropdown(){
  $("hzm-model-select").value=state.model;
  const current=$("hzm-model-current");
  if(current)current.textContent=MODEL_CHOICES.find(item=>item.id===state.model)?.label||"";
  MODEL_CHOICES.forEach(item=>{
    const option=$("hzm-model-option-"+item.id);
    if(!option)return;
    const active=item.id===state.model;
    option.setAttribute("aria-selected",String(active));
    option.classList.toggle("selected",active);
  });
}
function toggleModelDropdown(open,restoreFocus=false){
  const menu=$("hzm-model-options"),trigger=$("hzm-model-trigger");
  if(!menu||!trigger)return;
  menu.hidden=!open;
  trigger.setAttribute("aria-expanded",String(open));
  if(open)$("hzm-model-option-"+state.model)?.focus();
  else if(restoreFocus)trigger.focus();
}
function chooseModel(model){
  if(!MODEL_CHOICES.some(item=>item.id===model)||model===state.model)return;
  state.model=model;state.gamePending="";state.playersPending="";state.playerIndex=-1;state.playerQuery="";state.playerTeam="all";
  render(state.lastHome,state.lastPremium);
}
function toggleMatchPicker(open){
 const list=$("hzm-match-list"),trigger=$("hzm-match-picker");
 if(!list||!trigger)return;
 const visible=typeof open==="boolean"?open:list.hidden;
 list.hidden=!visible;
 trigger.setAttribute("aria-expanded",String(visible));
}
function chooseView(view){
 if(!["results","players"].includes(view)||view===state.view)return;
 state.view=view;
 state.expanded=view==="players";
 render(state.lastHome,state.lastPremium);
}
function openFromProps(ctx,home){
 const name=String(ctx?.name||"").trim(),team=String(ctx?.team||"").trim().toUpperCase();
 if(!name||name.length>85||!/^[A-Z]{3}$/.test(team)||!["PTS","REB","AST","PRA","FG3M"].includes(ctx?.market))
  return {ok:false,message:"Nieprawidłowy zawodnik lub rynek Player Props."};
 // Choose only a verified upcoming NBA fixture in the already received
 // trusted schedule. Never quietly open a different team's game.
 const all=(Array.isArray(home?.calendar_games)?home.calendar_games:[]).concat(
   Object.values(home?.calendar_extras||{}).flatMap(pack=>Array.isArray(pack?.games)?pack.games:[]));
 const unique=new Map();
 for(const g of all){
   if(!g||g.state!=="scheduled"||![g.away,g.home].includes(team)||
      !/^\d{6,15}$/.test(String(g.id||"")))continue;
   const day=safeDate(g.day)?g.day:(g.start?localDay(g.start):"");
   const start=Date.parse(g.start||"");
   if(!safeDate(day)||!withinRange(day)||!Number.isFinite(start)||start<=Date.now())continue;
   unique.set(String(g.id),{...g,day});
 }
 const games=[...unique.values()].sort((a,b)=>Date.parse(a.start)-Date.parse(b.start));
 const game=games.find(g=>g.id===state.gameId)||games[0];
 if(!game)return {ok:false,message:"Brak potwierdzonego nadchodzącego meczu "+team+
   " w pobranym terminarzu. Możesz wybrać datę w Simulation Lab."};
 state.day=game.day;state.gameId=String(game.id);
 state.gamePending="";state.playersPending="";
 state.view="players";state.expanded=true;
 state.playerTeam=team===game.away?"away":"home";
 state.playerQuery=name;state.playerIndex=-1;
 state.fromProps={name,team,market:ctx.market,day:game.day,gameId:String(game.id)};
 state.lastHome=home;
 return {ok:true,day:game.day,gameId:String(game.id)};
}
function clearBridge(){state.fromProps=null}
function bridgeToHistory(market){
 if(!["PTS","REB","AST","PRA"].includes(market)||!state.lastPremium?.entitled)return;
 const game=gamesForDay(state.lastHome).games.find(g=>g.id===state.gameId);
 const pack=trustedPlayers(state.lastPremium,game);
 const item=pack?.players?.[state.playerIndex];
 if(!item||![game?.away,game?.home].includes(item.team))return;
 const a=safeProjection(item.pts),b=safeProjection(item.reb),c=safeProjection(item.ast);
 const values={PTS:a,REB:b,AST:c,PRA:a!==null&&b!==null&&c!==null?a+b+c:null};
 if(values[market]===null)return;
 callbacks?.openProps?.({
  name:item.name,team:item.team,market,day:state.day,
  gameId:String(game.id),model:state.model
 });
}
function syncLabView(){
 const pane=$("simulations-pane");
 if(pane)pane.dataset.hzmView=state.view;
 const nav=$("hzm-lab-nav");
 if(nav)nav.querySelectorAll("[data-hzm-view]").forEach(tab=>{
   const active=tab.dataset.hzmView===state.view;
   tab.classList.toggle("selected",active);
   tab.setAttribute("aria-selected",String(active));
   tab.tabIndex=active?0:-1;
 });
 $("hzm-lab-main")?.setAttribute("aria-labelledby","hzm-lab-tab-"+state.view);
}
function fixtures(home){
  const extra=home?.calendar_extras?.[state.day];
  if(extra&&typeof extra==="object")return {known:true,rows:Array.isArray(extra.games)?extra.games:[]};
  const rows=(Array.isArray(home?.calendar_games)?home.calendar_games:[])
    .filter(game=>(game.day||localDay(game.start))===state.day);
  const known=rows.length>0||(home?.calendar_loaded_days||[]).includes(state.day);
  return {known,rows};
}
function gamesForDay(home){
  const found=fixtures(home);
  const unique=new Map();
  found.rows.forEach(game=>{
    if(!game||!game.away||!game.home)return;
    const key=String(game.id||[game.start,game.away,game.home].join("|"));
    unique.set(key,{...game,id:key});
  });
  return {known:found.known,games:[...unique.values()].sort((a,b)=>String(a.start||"").localeCompare(String(b.start||"")))};
}
function teamLogo(code,url){
  url=window.hzResolveTeamLogo?.(url)||"";
  const safe=typeof url==="string"&&/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(url);
  return '<span class="hzm-mark">'+(safe?'<img src="'+url+'" alt="" loading="lazy">':esc(code))+'</span>';
}
function gameButtons(games){
  const list=$("hzm-matches");
  if(!games.length){list.innerHTML='<div class="hzm-no-players">Brak potwierdzonych spotkań NBA w tym dniu.</div>';return}
  list.innerHTML=games.map(game=>{
    const away=String(game.away).toUpperCase(),home=String(game.home).toUpperCase();
    const finished=game.state==="final",live=game.state==="live";
    const status=finished?"Koniec":live?"Na żywo":clock(game.start);
    const selected=game.id===state.gameId;
    return '<button type="button" class="hzm-match'+(selected?' selected':'')+'" data-hzm-game="'+esc(game.id)+'"'+
      ' aria-pressed="'+selected+'" aria-label="'+esc(away+' – '+home+', '+status)+'">'+
      teamLogo(away,game.away_logo)+'<span class="hzm-match-center"><strong>'+esc(away)+' – '+esc(home)+'</strong><small>'+esc(status)+'</small></span>'+teamLogo(home,game.home_logo)+'</button>';
  }).join("");
}
function trustedResult(premium,game){
  const data=premium?.game;
  return premium?.entitled===true&&data&&data.date===state.day&&data.model_id===state.model&&String(data.game_id)===String(game?.id)
    ?data:null;
}
function trustedPlayers(premium,game){
  const data=premium?.players;
  return premium?.entitled===true&&data&&data.date===state.day&&data.model_id===state.model&&String(data.game_id)===String(game?.id)
    ?data:null;
}
function chartSvg(dist,code){
  const bins=Array.isArray(dist?.bins)?dist.bins.filter(row=>Number.isFinite(Number(row.x))&&Number.isFinite(Number(row.p))):[];
  if(bins.length<3)return '<div class="hzm-no-chart">Brak danych do wyświetlenia wykresu.</div>';
  const w=456,h=188,x0=43,y0=15,x1=w-11,y1=147;
  const xmin=bins[0].x,xmax=bins[bins.length-1].x+5,maxp=Math.max(1,...bins.map(row=>Number(row.p)))*1.18;
  const px=x=>x0+(x-xmin)/(xmax-xmin)*(x1-x0);
  const py=p=>y1-p/maxp*(y1-y0);
  const coords=bins.map(row=>[px(Number(row.x)+2.5),py(Number(row.p))]);
  const line=coords.map(([x,y],i)=>(i?'L':'M')+x.toFixed(2)+' '+y.toFixed(2)).join(' ');
  const area=line+' L '+coords[coords.length-1][0].toFixed(2)+' '+y1+' L '+coords[0][0].toFixed(2)+' '+y1+' Z';
  const mean=Number(dist.average),mx=px(mean),my=py(Math.max(...bins.map(row=>Number(row.p))));
  const grids=Array.from({length:5},(_,i)=>{
    const y=y1-i*(y1-y0)/4;
    return '<line x1="'+x0+'" y1="'+y+'" x2="'+x1+'" y2="'+y+'" stroke="#245076" stroke-opacity=".45"/>'+
      '<text x="'+(x0-7)+'" y="'+(y+3)+'" text-anchor="end" fill="#afc6e4" font-size="10">'+(i*maxp/4).toFixed(0)+'%</text>';
  }).join("");
  const xticks=Array.from({length:6},(_,i)=>{
    const x=xmin+(xmax-xmin)*i/5;
    return '<text x="'+px(x)+'" y="164" text-anchor="middle" fill="#bdd8ef" font-size="11">'+Math.round(x)+'</text>';
  }).join("");
  return '<svg viewBox="0 0 '+w+' '+h+'" role="img" aria-label="Rozkład punktów: '+esc(code)+'; średnia '+fmt(mean)+'">'+
    '<defs><linearGradient id="hzm-curve-fill" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#14e9f5" stop-opacity=".42"/><stop offset="1" stop-color="#b54df5" stop-opacity=".49"/></linearGradient></defs>'+
    grids+'<path d="'+area+'" fill="url(#hzm-curve-fill)"/>'+
    '<path d="'+line+'" fill="none" stroke="#37ecfa" stroke-width="2.2"/>'+
    '<line x1="'+mx+'" y1="'+(y0+3)+'" x2="'+mx+'" y2="'+y1+'" stroke="#e7e5ff" stroke-dasharray="5 4"/>'+
    '<circle cx="'+mx+'" cy="'+my+'" r="4" fill="#fff" stroke="#28ecfc" stroke-width="2"/>'+
    '<rect x="'+Math.max(55,Math.min(mx-48,w-106))+'" y="1" width="101" height="23" rx="9" fill="#0e2243" stroke="#bc70f4"/>'+
    '<text x="'+Math.max(105,Math.min(mx+2,w-56))+'" y="17" fill="#fff" font-weight="800" font-size="12" text-anchor="middle">'+fmt(mean)+' PTS</text>'+
    xticks+'<text x="'+w/2+'" y="183" text-anchor="middle" fill="#c4d9ea" font-size="10">Punkty – '+esc(code)+'</text></svg>';
}
function showChart(sim,game,premium){
  const tabs=$("hzm-chart-tabs").querySelectorAll("button");
  tabs.forEach(btn=>{
    btn.classList.toggle("active",btn.dataset.hzmChart===state.chart);
    if(btn.dataset.hzmChart==="away")btn.textContent=game?.away||"GOŚCIE";
    if(btn.dataset.hzmChart==="home")btn.textContent=game?.home||"GOSPODARZE";
    btn.setAttribute("aria-pressed",String(btn.dataset.hzmChart===state.chart));
  });
  $("hzm-away-average-label").textContent="Śr. "+(game?.away||"goście");
  $("hzm-home-average-label").textContent="Śr. "+(game?.home||"gospodarze");
  $("hzm-away-average").textContent=sim&&!sim.error?fmt(sim.away_points):"—";
  $("hzm-home-average").textContent=sim&&!sim.error?fmt(sim.home_points):"—";
  $("hzm-total-average").textContent=sim&&!sim.error?fmt(sim.total_points):"—";
  const code=state.chart==="match"?"MECZ":state.chart==="away"?game?.away:game?.home;
  $("hzm-chart-context").textContent=(code||"NBA")+" · 5 000 symulacji · "+modelLabel();
  $("hzm-chart-source").textContent="Średnie wyłącznie z 5 000 symulacji; model eksperymentalny.";
  const range=$("hzm-lab-range");
  if(range)range.textContent="Przedział 80%: —";
  const plot=$("hzm-plot");
  if(!premium?.entitled){plot.innerHTML='<div class="hzm-no-chart"><strong>Rozkład punktów w Premium</strong><span>Wykres meczu i każdej drużyny zostanie odblokowany po aktywacji.</span></div>';return}
  if(!game){plot.innerHTML='<div class="hzm-no-chart">Wybierz spotkanie NBA.</div>';return}
  if(!sim){plot.innerHTML='<div class="hzm-no-chart">Obliczanie symulacji wybranego meczu…</div>';return}
  if(sim.error){plot.innerHTML='<div class="hzm-no-chart">'+esc(sim.error)+'</div>';return}
  const dist=sim.distributions?.[state.chart];
  plot.innerHTML=chartSvg(dist,code);
  if(range&&dist&&Number.isFinite(Number(dist.p10))&&Number.isFinite(Number(dist.p90))&&
     dist.p10!==null&&dist.p90!==null){
   range.textContent="Przedział 80%: "+fmt(dist.p10)+" – "+fmt(dist.p90)+" pkt";
  }
  if(Number.isFinite(Number(dist?.threshold))&&Number.isFinite(Number(dist?.over_pct))){
    $("hzm-chart-source").textContent='P('+code+' ≥ '+dist.threshold+' pkt): '+fmt(dist.over_pct)+'% · przedział 80%: '+dist.p10+'–'+dist.p90+' pkt';
  }
}
function safeProjection(value){
 return value!==null&&value!==undefined&&value!==""&&Number.isFinite(Number(value))&&Number(value)>=0
  ?Number(value):null;
}
function playerInspector(item,players,game,withMinutes){
 const container=$("hzm-player-inspector");
 if(!container)return;
 if(!item){container.innerHTML='<div class="hzm-inspector-placeholder">Wybierz zawodnika z listy, aby zobaczyć szczegóły jego projekcji.</div>';return}
 const name=String(item.name||"").slice(0,70),code=String(item.team||"").slice(0,4);
 const status=withMinutes?String(item.availability||"Niezweryfikowany").slice(0,50):"";
 const out=withMinutes&&status==="Out";
 const pts=out?null:safeProjection(item.pts),reb=out?null:safeProjection(item.reb),ast=out?null:safeProjection(item.ast);
 const pra=pts!==null&&reb!==null&&ast!==null?pts+reb+ast:null;
 const metrics=[["PTS",pts],["REB",reb],["AST",ast],["PRA",pra]]
  .map(([key,value])=>'<div class="hzm-inspector-metric'+(key==="PRA"?' pra':'')+'"><span>'+key+'</span><strong>'+fmt(value)+'</strong></div>').join("");
 const sample=withMinutes&&Number.isInteger(Number(item.minutes_sample))?Math.max(0,Number(item.minutes_sample)):0;
 const minutes=withMinutes?safeProjection(item.minutes):null;
 const minuteLabel=withMinutes
  ?minutes===null?'Brak wiarygodnego szacunku minut':fmt(minutes)+' min · '+sample+' wcześniejszych występów'
  :'Minuty: brak zweryfikowanego szacunku w modelu '+esc(modelLabel());
 const availability=withMinutes
  ?'<span class="hzm-inspector-status'+(out?' is-out':(["Questionable","Doubtful","Day-to-day"].includes(status)?' is-uncertain':''))+'">'+
    'ESPN: '+esc(status)+'</span>'
  :'<span class="hzm-inspector-status">Dostępność: nieoceniana w tym modelu</span>';
 container.innerHTML=
  '<div class="hzm-inspector-top"><span>PLAYER FORECAST · '+esc(modelLabel())+'</span><strong>'+esc(code)+'</strong></div>'+
  '<h3>'+esc(name)+'</h3><div class="hzm-inspector-sub">'+esc(game?.away||"NBA")+
  ' vs '+esc(game?.home||"NBA")+' · szacunki na wybrany mecz</div>'+
  availability+
  '<div class="hzm-inspector-metrics">'+metrics+'</div>'+
  '<div class="hzm-inspector-minutes">'+(withMinutes?'◷ ':'')+minuteLabel+'</div>'+
  '<p class="hzm-inspector-disclaimer">'+(out?
    'ESPN zgłasza OUT — model nie wyświetla projekcji produkcji zawodnika.':
    'PRA to suma średnich prognoz PTS, REB i AST. Nie jest osobną symulacją ani rozkładem prawdopodobieństwa.')+
  '</p>'+
  (withMinutes&&players?.minutes_warning?
    '<small class="hzm-inspector-warning">'+esc(players.minutes_warning)+'</small>':'')+
  '<div class="hzm-inspector-actions" role="group" aria-label="Przejdź do historii zawodnika w Player Props">'+
  (out?'':metrics.map(([key,value])=>value===null?"":'<button type="button" data-hzm-history-market="'+key+'"'+
    (state.fromProps?.market===key?' class="is-related"':'')+' title="Historia '+key+' w Player Props">'+
    'Historia '+key+' ›</button>').join(""))+
  '</div>'+
  (state.fromProps?.name===name&&state.fromProps?.team===code?
    '<button type="button" class="hzm-return-to-props" data-hzm-return-props>← Wróć do poprzedniej analizy Player Props</button>':"");
}
function showPlayers(premium,players,game){
 const panel=$("hzm-players-panel"),button=$("hzm-expand-players"),rows=$("hzm-player-rows");
 const focused=state.view==="players",withMinutes=state.model==="research_context_v75";
 const headings=$("hzm-player-headings");
 headings.classList.toggle("with-min",withMinutes);
 headings.innerHTML=(withMinutes?'<span>MIN</span>':'')+'<span>PTS</span><span>REB</span><span>AST</span>';
 panel.classList.toggle("expanded",state.expanded);
 button.setAttribute("aria-expanded",String(state.expanded));
 button.innerHTML=(state.expanded?'Zwiń listę':'Rozwiń pełną listę zawodników')+' <span aria-hidden="true">⌄</span>';
 const search=$("hzm-player-search"),count=$("hzm-player-count");
 if(search&&search.value!==state.playerQuery)search.value=state.playerQuery;
 const codes={away:game?.away||"Goście",home:game?.home||"Gospodarze"};
 for(const side of ["away","home"]){const element=$("hzm-player-team-"+side);if(element)element.textContent=codes[side]}
 $("hzm-player-tools")?.querySelectorAll("[data-hzm-player-team]").forEach(element=>{
   const active=element.dataset.hzmPlayerTeam===state.playerTeam;
   element.setAttribute("aria-pressed",String(active));element.classList.toggle("selected",active);
 });
 const inspector=$("hzm-player-inspector");
 if(!premium?.entitled){
   rows.innerHTML='<div class="hzm-no-players">'+(state.expanded
     ?'Pełna lista i projekcje graczy wymagają zweryfikowanej subskrypcji Premium.'
     :'Projekcje PTS, REB i AST są dostępne w Premium.')+'</div>';
   if(count)count.textContent="";
   if(inspector)inspector.innerHTML='<div class="hzm-inspector-placeholder">Dane zawodników dostępne wyłącznie z aktywnym Premium.</div>';
   return;
 }
 if(!players){
   rows.innerHTML='<div class="hzm-no-players">Pobieranie projekcji zawodników z ESPN…</div>';
   if(count)count.textContent="";
   playerInspector(null,players,game,withMinutes);return;
 }
 if(!Array.isArray(players.players)||!players.players.length){
   rows.innerHTML='<div class="hzm-no-players">'+esc(players.error||'Brak zweryfikowanych danych zawodników.')+'</div>';
   if(count)count.textContent="0 zawodników";
   playerInspector(null,players,game,withMinutes);return;
 }
 // Team-scoped row identities prevent a mismatched roster record appearing
 // for the selected matchup. All rows come from the Premium-protected payload.
 const athletes=players.players.map((item,index)=>({item,index})).filter(({item})=>
   item&&String(item.team||"").toUpperCase()===String(game?.away||"").toUpperCase()||
   item&&String(item.team||"").toUpperCase()===String(game?.home||"").toUpperCase());
 const query=state.playerQuery.trim().toLocaleLowerCase("pl");
 const filtered=focused?athletes.filter(({item})=>
   (state.playerTeam==="all"||String(item.team).toUpperCase()===String(codes[state.playerTeam]||"").toUpperCase())&&
   (!query||String(item.name||"").toLocaleLowerCase("pl").includes(query))):athletes;
 const visible=focused?filtered:(state.expanded?filtered:filtered.slice(0,4));
 if(count)count.textContent=focused?filtered.length+" z "+athletes.length+" zawodników":"";
 if(focused&&!filtered.some(p=>p.index===state.playerIndex))state.playerIndex=filtered[0]?.index??-1;
 if(!visible.length){
   rows.innerHTML='<div class="hzm-no-players">Brak zawodników spełniających wybrane filtry.</div>';
   playerInspector(null,players,game,withMinutes);return;
 }
 rows.innerHTML=visible.map(({item,index})=>{
   const initials=String(item.name||'').split(/\s+/).filter(Boolean).slice(0,2).map(x=>x[0]).join('').toUpperCase();
   const status=withMinutes?String(item.availability||''):'';
   const atRisk=["Questionable","Doubtful","Day-to-day"].includes(status);
   const statusHtml=status==="Out"?'<small class="hzm-injured">'+esc(item.team)+' · OUT (ESPN)</small>':
     atRisk?'<small class="hzm-uncertain">'+esc(item.team)+' · '+esc(status)+' (ESPN)</small>':
     '<small class="'+(item.team===players.home?'home':'')+'">'+esc(item.team)+'</small>';
   return '<button type="button" class="hzm-player-row" data-hzm-player-index="'+index+'" aria-pressed="'+(focused&&index===state.playerIndex)+'" aria-label="'+esc('Szczegóły prognozy '+item.name+', '+item.team)+'">'+
     '<span class="hzm-player-initials">'+esc(initials)+'</span>'+
     '<span class="hzm-player-info"><strong>'+esc(item.name)+'</strong>'+statusHtml+'</span>'+
     '<span class="hzm-player-stats'+(withMinutes?' with-min':'')+'">'+
     (withMinutes?'<span title="Szacowane minuty z '+esc(item.minutes_sample||0)+' występów">'+fmt(item.minutes)+'</span>':'')+
     '<span>'+fmt(item.pts)+'</span><span>'+fmt(item.reb)+'</span><span>'+fmt(item.ast)+'</span></span></button>';
 }).join("");
 if(!state.expanded&&athletes.length>4)button.textContent='Pokaż wszystkich zawodników ('+athletes.length+') ▾';
 if(focused)playerInspector(filtered.find(p=>p.index===state.playerIndex)?.item||null,players,game,withMinutes);
 else if(inspector)inspector.innerHTML='';
}

function maybeLoadPaid(game,premium,sim,players){
  if(!premium?.entitled||!game||!["scheduled","final"].includes(game.state))return;
  const key=state.day+"|"+game.id+"|"+state.model;
  if(!sim&&state.gamePending!==key){state.gamePending=key;callbacks?.loadGame?.(state.day,game.id,state.model)}
  if(sim&&!sim.error&&!players&&state.playersPending!==key){state.playersPending=key;callbacks?.loadPlayers?.(state.day,game.id,state.model)}
}
function render(home,premium){
  state.lastHome=home;state.lastPremium=premium;
  syncModelDropdown();
  syncLabView();
  if(!state.day)state.day=safeDate(home?.calendar_today)?home.calendar_today:localDay(new Date().toISOString());
  const data=gamesForDay(home);
  if(!data.known&&home&&state.requestedDay!==state.day){state.requestedDay=state.day;callbacks?.selectDay?.(state.day)}
  if(data.known&&state.requestedDay===state.day)state.requestedDay="";
  if(!data.games.some(game=>game.id===state.gameId)){
    const next=data.games.find(game=>game.state==="scheduled")||data.games[0];
    state.gameId=next?.id||"";state.expanded=state.view==="players";state.playerIndex=-1;state.fromProps=null;
  }
  $("hzm-day-title").textContent=labelDay(state.day);
  $("hzm-day-input").value=state.day;
  gameButtons(data.games);
  const game=data.games.find(item=>item.id===state.gameId);
  const sim=trustedResult(premium,game),players=trustedPlayers(premium,game);
  const ctx=sim?.model_context;
  $("hzm-evidence-form").textContent=ctx
    ?"Zweryfikowane mecze: "+ctx.away_sample+" / "+ctx.home_sample+
       (ctx.v75_factors?" · dom/wyjazd: "+ctx.v75_factors.away_venue_games+" / "+ctx.v75_factors.home_venue_games:"")
    :"Ostatnie potwierdzone mecze";
  $("hzm-evidence-pace").textContent=ctx?.advanced_available
    ?"NBA Advanced: PACE / OFF / DEF + historia ESPN"
    :ctx?(state.model==="legacy_v72"?"Stała zmienność punktów V7.2; brak NBA Advanced":"Rzeczywiste odchylenia punktów; brak NBA Advanced")
    :"Heurystyczna zmienność punktów";
  const availability=ctx?.v75_factors;
  const injuryLine=availability?(availability.injuries_espn_fresh
    ?" · OUT ESPN: "+(availability.injury_out_away||0)+" / "+(availability.injury_out_home||0)+
      " · wpływ pkt: "+fmt(availability.injury_away_pts)+" / "+fmt(availability.injury_home_pts)
    :" · brak świeżego raportu kontuzji")
    :" · kontuzje niezweryfikowane";
  $("hzm-evidence-rest").textContent=ctx?.rest_days?.every(n=>Number.isFinite(n))
    ?"Dni odpoczynku: "+ctx.rest_days.join(" / ")+
      (availability?" · korekta B2B: "+fmt(availability.rest_away_pts)+" / "+fmt(availability.rest_home_pts):"")+
      injuryLine
    :"Raport ESPN nie jest oficjalnym potwierdzeniem składu";
  const away=game?.away||"NBA",homeCode=game?.home||"NBA";
  const pickerLabel=$("hzm-match-picker-label");
  if(pickerLabel)pickerLabel.textContent=game?away+" – "+homeCode:"Wybierz mecz";
  $("hzm-match-label").innerHTML='<span class="hzm-hero-team away">'+teamLogo(away,game?.away_logo)+'<strong>'+esc(away)+'</strong></span>'+
    '<span class="hzm-versus-divider">VS</span>'+
    '<span class="hzm-hero-team home">'+teamLogo(homeCode,game?.home_logo)+'<strong>'+esc(homeCode)+'</strong></span>';
  $("hzm-away-code").textContent=away;$("hzm-home-code").textContent=homeCode;
  const isValid=sim&&!sim.error;
  $("hzm-score").textContent=isValid?Math.round(sim.away_points)+' : '+Math.round(sim.home_points):"— : —";
  $("hzm-away-win").textContent=isValid?percent(sim.away_win_pct):"—";
  $("hzm-home-win").textContent=isValid?percent(sim.home_win_pct):"—";
  $("hzm-donut").style.background=isValid
    ?'conic-gradient(#16e9f6 0 '+Math.min(100,Math.max(0,sim.away_win_pct))+'%,#b15cef '+Math.min(100,Math.max(0,sim.away_win_pct))+'% 100%)'
    :'conic-gradient(#193d5c 0 50%,#351a54 50% 100%)';
  $("hzm-simulation-message").textContent=!premium?.entitled
    ?"Zweryfikowane Premium wymagane":!game?"Wybierz mecz":sim?.error||(!sim?"Trwa obliczanie modelu":
      sim.retrospective?"Analiza retrospektywna · nie zapisany typ sprzed meczu":"Średnia z 5 000 symulacji · "+modelLabel());
  $("simulations-pane").classList.toggle("hzm-premium-locked",!premium?.entitled);
  showChart(sim,game,premium);showPlayers(premium,players,game);
  maybeLoadPaid(game,premium,sim,players);
}
function navigate(day){
  if(!safeDate(day)||!withinRange(day)||state.day===day)return;
  state.day=day;state.gameId="";state.chart="match";state.fromProps=null;state.expanded=state.view==="players";state.gamePending="";state.playersPending="";state.playerIndex=-1;state.playerQuery="";state.playerTeam="all";
  render(state.lastHome,state.lastPremium);
}
function init(api){
  callbacks=api;
  $("hzm-model-select").addEventListener("change",event=>chooseModel(event.target.value));
  // Give the model dropdown its own control listeners. The new Simulation Lab
  // has a scrollable canvas and overlay fixture picker: model controls must
  // not depend on event delegation through the entire pane.
  $("hzm-model-trigger").addEventListener("click",event=>{
    event.stopPropagation();
    toggleModelDropdown($("hzm-model-options").hidden);
  });
  MODEL_CHOICES.forEach(choice=>{
    $("hzm-model-option-"+choice.id)?.addEventListener("click",event=>{
      event.stopPropagation();
      toggleModelDropdown(false,true);
      chooseModel(choice.id);
    });
  });
  // Popup buttons are rerendered in place, but the list container stays
  // mounted. Handle its clicks directly so selecting a game always closes it.
  $("hzm-player-search").addEventListener("input",event=>{
    state.playerQuery=String(event.target.value||"").slice(0,70);
    state.playerIndex=-1;
    render(state.lastHome,state.lastPremium);
  });
  $("hzm-player-tools").addEventListener("click",event=>{
    const button=event.target.closest("[data-hzm-player-team]");
    if(!button||!["all","away","home"].includes(button.dataset.hzmPlayerTeam))return;
    state.playerTeam=button.dataset.hzmPlayerTeam;state.playerIndex=-1;
    render(state.lastHome,state.lastPremium);
  });
  $("hzm-player-inspector").addEventListener("click",event=>{
    const link=event.target.closest("[data-hzm-history-market]");
    if(link){bridgeToHistory(link.dataset.hzmHistoryMarket);return;}
    if(event.target.closest("[data-hzm-return-props]")&&state.fromProps)
      callbacks?.backToProps?.();
  });
  $("hzm-player-rows").addEventListener("click",event=>{
    const row=event.target.closest("[data-hzm-player-index]");
    if(!row)return;
    const idx=Number(row.dataset.hzmPlayerIndex);
    if(!Number.isInteger(idx)||idx<0)return;
    state.playerIndex=idx;
    if(state.view!=="players"){state.view="players";state.expanded=true}
    render(state.lastHome,state.lastPremium);
  });
  $("hzm-matches").addEventListener("click",event=>{
    const selected=event.target.closest("[data-hzm-game]");
    if(!selected)return;
    event.stopPropagation();
    state.gameId=selected.dataset.hzmGame;state.chart="match";state.playerIndex=-1;state.fromProps=null;
    state.expanded=state.view==="players";
    toggleMatchPicker(false);
    render(state.lastHome,state.lastPremium);
  });
  // The expand button stays in the DOM while switching lab modules. Handling
  // it directly avoids a missed delegated click after a panel reflow.
  $("hzm-expand-players").addEventListener("click",event=>{
    event.stopPropagation();
    state.expanded=!state.expanded;
    render(state.lastHome,state.lastPremium);
  });
  $("simulations-pane").addEventListener("click",event=>{
    if(event.target.closest("#hzm-match-picker")){toggleMatchPicker();return}
    const viewButton=event.target.closest("[data-hzm-view]");
    if(viewButton){chooseView(viewButton.dataset.hzmView);return}
    if(event.target.closest("#hzm-model-trigger")){
      toggleModelDropdown($("hzm-model-options").hidden);return;
    }
    const modelOption=event.target.closest("[data-hzm-model]");
    if(modelOption){toggleModelDropdown(false,true);chooseModel(modelOption.dataset.hzmModel);return}
    const arrow=event.target.closest("[data-hzm-shift]");
    if(arrow){navigate(dayShift(state.day,Number(arrow.dataset.hzmShift)));return}
    const gameButton=event.target.closest("[data-hzm-game]");
    if(gameButton){
      state.gameId=gameButton.dataset.hzmGame;state.chart="match";state.playerIndex=-1;state.fromProps=null;
      state.expanded=state.view==="players";toggleMatchPicker(false);
      render(state.lastHome,state.lastPremium);return;
    }
    const metric=event.target.closest("[data-hzm-chart]");
    if(metric){state.chart=metric.dataset.hzmChart;render(state.lastHome,state.lastPremium);return}
    if(event.target.closest("#hzm-expand-players")){state.expanded=!state.expanded;render(state.lastHome,state.lastPremium);return}
    if(event.target.closest("#hzm-premium-link")){callbacks?.premium?.()}
  });
  $("simulations-pane").addEventListener("keydown",event=>{
    if(event.key==="Escape" &&
       (event.target.closest("#hzm-match-picker")||event.target.closest("#hzm-match-list"))){
      toggleMatchPicker(false);$("hzm-match-picker")?.focus();return;
    }
    const trigger=event.target.closest("#hzm-model-trigger");
    const option=event.target.closest("[data-hzm-model]");
    if(!trigger&&!option)return;
    if(event.key==="Escape"){
      if(!$("hzm-model-options").hidden){event.preventDefault();toggleModelDropdown(false,true)}
      return;
    }
    if(event.key==="Tab"){toggleModelDropdown(false);return}
    if(!["ArrowDown","ArrowUp","Home","End"].includes(event.key))return;
    event.preventDefault();
    const index=MODEL_CHOICES.findIndex(item=>item.id===(option?.dataset.hzmModel||state.model));
    const next=event.key==="Home"?0:event.key==="End"?MODEL_CHOICES.length-1:
      (index+(event.key==="ArrowDown"?1:-1)+MODEL_CHOICES.length)%MODEL_CHOICES.length;
    toggleModelDropdown(true);
    $("hzm-model-option-"+MODEL_CHOICES[next].id)?.focus();
  });
  document.addEventListener?.("pointerdown",event=>{
    if(!event.target.closest(".hzm-model-choice"))toggleModelDropdown(false);
    if(!event.target.closest("#hzm-match-picker")&&!event.target.closest("#hzm-match-list"))
      toggleMatchPicker(false);
  });
  $("hzm-day-input").addEventListener("change",event=>navigate(event.target.value));
}
window.HoopzaroSimulations={init,render,openFromProps,clearBridge};
})();
