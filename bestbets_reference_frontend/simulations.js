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
const state={day:"",gameId:"",model:"research_form_v74",chart:"match",expanded:false,requestedDay:"",gamePending:"",playersPending:"",lastHome:null,lastPremium:null};
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
  state.model=model;state.gamePending="";state.playersPending="";
  render(state.lastHome,state.lastPremium);
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
  const plot=$("hzm-plot");
  if(!premium?.entitled){plot.innerHTML='<div class="hzm-no-chart"><strong>Rozkład punktów w Premium</strong><span>Wykres meczu i każdej drużyny zostanie odblokowany po aktywacji.</span></div>';return}
  if(!game){plot.innerHTML='<div class="hzm-no-chart">Wybierz spotkanie NBA.</div>';return}
  if(!sim){plot.innerHTML='<div class="hzm-no-chart">Obliczanie symulacji wybranego meczu…</div>';return}
  if(sim.error){plot.innerHTML='<div class="hzm-no-chart">'+esc(sim.error)+'</div>';return}
  const dist=sim.distributions?.[state.chart];
  plot.innerHTML=chartSvg(dist,code);
  if(Number.isFinite(Number(dist?.threshold))&&Number.isFinite(Number(dist?.over_pct))){
    $("hzm-chart-source").textContent='P('+code+' ≥ '+dist.threshold+' pkt): '+fmt(dist.over_pct)+'% · przedział 80%: '+dist.p10+'–'+dist.p90+' pkt';
  }
}
function showPlayers(premium,players){
  const panel=$("hzm-players-panel"),button=$("hzm-expand-players"),rows=$("hzm-player-rows");
  const withMinutes=state.model==="research_context_v75";
  const headings=$("hzm-player-headings");
  headings.classList.toggle("with-min",withMinutes);
  headings.innerHTML=(withMinutes?'<span>MIN</span>':'')+'<span>PTS</span><span>REB</span><span>AST</span>';
  panel.classList.toggle("expanded",state.expanded);
  button.setAttribute("aria-expanded",String(state.expanded));
  button.innerHTML=(state.expanded?'Zwiń listę':'Rozwiń pełną listę zawodników')+' <span aria-hidden="true">⌄</span>';
  if(!premium?.entitled){
    rows.innerHTML='<div class="hzm-no-players">'+(state.expanded
      ?'Pełna lista i projekcje graczy wymagają zweryfikowanej subskrypcji Premium.'
      :'Projekcje PTS, REB i AST są dostępne w Premium.')+'</div>';return;
  }
  if(!players){rows.innerHTML='<div class="hzm-no-players">Pobieranie projekcji zawodników z ESPN…</div>';return}
  if(!Array.isArray(players.players)||!players.players.length){
    rows.innerHTML='<div class="hzm-no-players">'+esc(players.error||'Brak zweryfikowanych danych zawodników.')+'</div>';return;
  }
  const visible=state.expanded?players.players:players.players.slice(0,4);
  rows.innerHTML=visible.map(item=>{
    const initials=String(item.name||'').split(/\s+/).filter(Boolean).slice(0,2).map(x=>x[0]).join('').toUpperCase();
    const status=withMinutes?String(item.availability||''):'';
    const atRisk=["Questionable","Doubtful","Day-to-day"].includes(status);
    const statusHtml=status==="Out"?'<small class="hzm-injured">'+esc(item.team)+' · OUT (ESPN)</small>':
      atRisk?'<small class="hzm-uncertain">'+esc(item.team)+' · '+esc(status)+' (ESPN)</small>':
      '<small class="'+(item.team===players.home?'home':'')+'">'+esc(item.team)+'</small>';
    return '<div class="hzm-player-row"><span class="hzm-player-initials">'+esc(initials)+'</span>'+
      '<div class="hzm-player-info"><strong>'+esc(item.name)+'</strong>'+statusHtml+'</div>'+
      '<div class="hzm-player-stats'+(withMinutes?' with-min':'')+'">'+
      (withMinutes?'<span title="Szacowane minuty z '+esc(item.minutes_sample||0)+' występów">'+fmt(item.minutes)+'</span>':'')+
      '<span>'+fmt(item.pts)+'</span><span>'+fmt(item.reb)+'</span><span>'+fmt(item.ast)+'</span></div></div>';
  }).join("");
  if(!state.expanded&&players.players.length>4){button.textContent='Pokaż wszystkich zawodników ('+players.players.length+') ▾'}
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
  if(!state.day)state.day=safeDate(home?.calendar_today)?home.calendar_today:localDay(new Date().toISOString());
  const data=gamesForDay(home);
  if(!data.known&&home&&state.requestedDay!==state.day){state.requestedDay=state.day;callbacks?.selectDay?.(state.day)}
  if(data.known&&state.requestedDay===state.day)state.requestedDay="";
  if(!data.games.some(game=>game.id===state.gameId)){
    const next=data.games.find(game=>game.state==="scheduled")||data.games[0];
    state.gameId=next?.id||"";state.expanded=false;
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
  $("hzm-match-label").innerHTML=esc(away)+' <span>VS</span> <span class="hzm-home-code">'+esc(homeCode)+'</span>';
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
  showChart(sim,game,premium);showPlayers(premium,players);
  maybeLoadPaid(game,premium,sim,players);
}
function navigate(day){
  if(!safeDate(day)||!withinRange(day)||state.day===day)return;
  state.day=day;state.gameId="";state.chart="match";state.expanded=false;state.gamePending="";state.playersPending="";
  render(state.lastHome,state.lastPremium);
}
function init(api){
  callbacks=api;
  $("hzm-model-select").addEventListener("change",event=>chooseModel(event.target.value));
  $("simulations-pane").addEventListener("click",event=>{
    if(event.target.closest("#hzm-model-trigger")){
      toggleModelDropdown($("hzm-model-options").hidden);return;
    }
    const modelOption=event.target.closest("[data-hzm-model]");
    if(modelOption){toggleModelDropdown(false,true);chooseModel(modelOption.dataset.hzmModel);return}
    const arrow=event.target.closest("[data-hzm-shift]");
    if(arrow){navigate(dayShift(state.day,Number(arrow.dataset.hzmShift)));return}
    const gameButton=event.target.closest("[data-hzm-game]");
    if(gameButton){state.gameId=gameButton.dataset.hzmGame;state.chart="match";state.expanded=false;render(state.lastHome,state.lastPremium);return}
    const metric=event.target.closest("[data-hzm-chart]");
    if(metric){state.chart=metric.dataset.hzmChart;render(state.lastHome,state.lastPremium);return}
    if(event.target.closest("#hzm-expand-players")){state.expanded=!state.expanded;render(state.lastHome,state.lastPremium);return}
    if(event.target.closest("#hzm-premium-link")){callbacks?.premium?.()}
  });
  $("simulations-pane").addEventListener("keydown",event=>{
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
  });
  $("hzm-day-input").addEventListener("change",event=>navigate(event.target.value));
}
window.HoopzaroSimulations={init,render};
})();
