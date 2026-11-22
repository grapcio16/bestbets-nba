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
const state={day:"",gameId:"",model:"research_form_v74",chart:"match",chartPoint:{match:null,away:null,home:null},view:"results",resultTeam:"all",playerMarket:"PTS",playerHistoryWindow:5,comparisonWindow:10,backtestPending:false,expanded:false,playerTeam:"all",playerQuery:"",playerIndex:-1,fromProps:null,scenarioPct:0,offAwayPct:0,offHomePct:0,scenarioPending:"",minuteIndex:-1,minuteDelta:0,minutePending:"",requestedDay:"",localDayIntent:false,gamePending:"",playersPending:"",lastHome:null,lastPremium:null};
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
  state.model=model;state.gamePending="";state.playersPending="";state.scenarioPct=0;state.offAwayPct=0;state.offHomePct=0;state.scenarioPending="";state.minuteIndex=-1;state.minuteDelta=0;state.minutePending="";state.playerIndex=-1;state.playerQuery="";state.playerTeam="all";
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
 if(!["results","players","scenario","intelligence","comparison","backtest"].includes(view)||view===state.view)return;
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
 state.day=game.day;state.localDayIntent=true;state.gameId=String(game.id);
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
 if($("hzm-detail-grid"))$("hzm-detail-grid").hidden=["players","scenario","intelligence","comparison","backtest"].includes(state.view);
 if($("hzv3"))$("hzv3").hidden=state.view!=="players";
 if($("hzm-scenario-panel"))$("hzm-scenario-panel").hidden=state.view!=="scenario";
 if($("hzm-intel-panel"))$("hzm-intel-panel").hidden=state.view!=="intelligence";
 if($("hzm-compare-panel"))$("hzm-compare-panel").hidden=state.view!=="comparison";
 if($("hzm-backtest-panel"))$("hzm-backtest-panel").hidden=state.view!=="backtest";
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
/* The slider follows the actual five-point histogram; each bin represents
   the probability of a five-point RANGE, not the chance of one exact score.
   Exact cumulative OVER/UNDER uses preaggregated counts from the same 5000
   score draws. No model or simulation settings are changed. */
function chartBins(dist){
 return Array.isArray(dist?.bins)?dist.bins.filter(row=>
   row&&Number.isFinite(Number(row.x))&&Number.isFinite(Number(row.p))&&
   Number(row.p)>=0).map(row=>({x:Number(row.x),p:Number(row.p)}))
   .sort((a,b)=>a.x-b.x):[];
}
function chartBinIndex(bins,dist){
 if(!bins.length)return -1;
 const picked=state.chartPoint?.[state.chart];
 const target=picked!==null&&picked!==undefined&&Number.isFinite(Number(picked))
    ?Number(picked)+2.5:Number(dist?.average);
 const selected=Number.isFinite(target)?target:bins[Math.floor(bins.length/2)].x+2.5;
 return bins.reduce((best,bin,i)=>
   Math.abs(bin.x+2.5-selected)<Math.abs(bins[best].x+2.5-selected)?i:best,0);
}
function chartProbabilityProfile(dist,bins,index){
 if(!bins.length||index<0||index>=bins.length)return null;
 const row=bins[index],start=row.x;
 const counts=Array.isArray(dist?.score_counts)?dist.score_counts
   .filter(v=>Array.isArray(v)&&v.length===2&&Number.isInteger(Number(v[0]))&&
     Number.isInteger(Number(v[1]))&&Number(v[1])>=0&&Number(v[1])<=5000)
   .map(v=>[Number(v[0]),Number(v[1])]):[];
 const countTotal=counts.reduce((n,item)=>n+item[1],0);
 const hasExact=countTotal===5000;
 const binsTotal=bins.reduce((n,item)=>n+item.p,0);
 const exactOver=t=>100*counts.reduce((n,item)=>n+(item[0]>t?item[1]:0),0)/countTotal;
 const histogramOver=t=>binsTotal>0?100*bins.reduce((n,item)=>
     n+(item.x+2.5>t?item.p:0),0)/binsTotal:null;
 const over=t=>hasExact?exactOver(t):histogramOver(t);
 const first=over(start-.5),second=over(start+4.5);
 const probBin=hasExact?100*counts.reduce((n,item)=>
    n+(item[0]>=start&&item[0]<start+5?item[1]:0),0)/countTotal:row.p;
 return {start,end:start+4,binPct:probBin,exact:hasExact,
   lines:[
     {line:start-.5,over:first,under:first===null?null:100-first,approx:!hasExact},
     {line:start+4.5,over:second,under:second===null?null:100-second,approx:!hasExact}
   ]};
}
function chartSvg(dist,code){
 const bins=chartBins(dist);
 if(bins.length<3)return '<div class="hzm-no-chart">Brak danych do wyświetlenia wykresu.</div>';
 const w=456,h=188,x0=43,y0=15,x1=w-11,y1=147;
 const xmin=bins[0].x,xmax=bins[bins.length-1].x+5;
 const peak=Math.max(1,...bins.map(row=>row.p)),maxp=peak*1.22;
 if(!Number.isFinite(xmin)||!Number.isFinite(xmax)||xmax<=xmin)
   return '<div class="hzm-no-chart">Brak poprawnej skali rozkładu.</div>';
 const px=x=>x0+(x-xmin)/(xmax-xmin)*(x1-x0);
 const py=p=>y1-p/maxp*(y1-y0);
 const coords=bins.map(row=>[px(row.x+2.5),py(row.p)]);
 const line=coords.map(([x,y],i)=>(i?'L':'M')+x.toFixed(2)+' '+y.toFixed(2)).join(' ');
 const area=line+' L '+coords[coords.length-1][0].toFixed(2)+' '+y1+
   ' L '+coords[0][0].toFixed(2)+' '+y1+' Z';
 const selectedIndex=chartBinIndex(bins,dist),selection=chartProbabilityProfile(dist,bins,selectedIndex);
 const selected=bins[selectedIndex],mx=px(selected.x+2.5),my=py(selected.p);
 const pillX=Math.max(x0,Math.min(mx-67,x1-134));
 const label=selected.x+'–'+(selected.x+4)+' · '+fmt(selection.binPct)+'%';
 const grids=Array.from({length:5},(_,i)=>{
   const y=y1-i*(y1-y0)/4;
   return '<line x1="'+x0+'" y1="'+y+'" x2="'+x1+'" y2="'+y+
     '" stroke="#4275b2" stroke-opacity="'+(i===0?'.65':'.36')+'"/>'+
     '<text x="'+(x0-7)+'" y="'+(y+3)+
     '" text-anchor="end" fill="#b9cae8" font-size="10">'+(i*maxp/4).toFixed(0)+'%</text>';
 }).join("");
 const xticks=Array.from({length:6},(_,i)=>{
   const x=xmin+(xmax-xmin)*i/5;
   return '<text x="'+px(x)+'" y="164" text-anchor="middle" fill="#c4d7f4" font-size="11">'+Math.round(x)+'</text>';
 }).join("");
 return '<svg class="hzm-neon-curve" viewBox="0 0 '+w+' '+h+
   '" role="slider" tabindex="0" aria-label="Przesuń punkt, aby zbadać prawdopodobieństwo punktów: '+esc(code)+
   '" aria-valuemin="'+bins[0].x+'" aria-valuemax="'+bins[bins.length-1].x+
   '" aria-valuenow="'+selected.x+'" aria-valuetext="'+esc(selected.x+' do '+(selected.x+4)+
   ' punktów; '+fmt(selection.binPct)+'% symulacji')+'">'+
   '<defs>'+
     '<linearGradient id="hzm-curve-fill" x1="0%" y1="0%" x2="100%" y2="0%">'+
       '<stop offset="0%" stop-color="#06e9f1" stop-opacity=".32"/>'+
       '<stop offset="30%" stop-color="#17dffc" stop-opacity=".53"/>'+
       '<stop offset="59%" stop-color="#4889fa" stop-opacity=".57"/>'+
       '<stop offset="85%" stop-color="#9662f5" stop-opacity=".49"/>'+
       '<stop offset="100%" stop-color="#d65cf8" stop-opacity=".28"/>'+
     '</linearGradient>'+
     '<linearGradient id="hzm-curve-stroke" x1="0%" y1="0%" x2="100%" y2="0%">'+
       '<stop offset="0%" stop-color="#07f6f4"/>'+
       '<stop offset="36%" stop-color="#19ecfc"/>'+
       '<stop offset="66%" stop-color="#70b9ff"/>'+
       '<stop offset="100%" stop-color="#c969fb"/>'+
     '</linearGradient>'+
     '<filter id="hzm-line-glow" x="-30%" y="-45%" width="170%" height="190%">'+
       '<feGaussianBlur stdDeviation="2.5"/>'+
     '</filter>'+
     '<filter id="hzm-peak-glow" x="-160%" y="-160%" width="420%" height="420%">'+
       '<feGaussianBlur stdDeviation="5"/>'+
     '</filter>'+
   '</defs>'+
   grids+
   '<path class="hzm-area-gradient" d="'+area+'" fill="url(#hzm-curve-fill)"/>'+
   '<path class="hzm-curve-glow" d="'+line+'" fill="none" stroke="url(#hzm-curve-stroke)" stroke-width="7" opacity=".66" filter="url(#hzm-line-glow)"/>'+
   '<path class="hzm-curve-line" d="'+line+'" fill="none" stroke="url(#hzm-curve-stroke)" stroke-width="2.8" stroke-linejoin="round" stroke-linecap="round"/>'+
   '<g class="hzm-selection-marker">'+
     '<line class="hzm-marker-guide" x1="'+mx+'" y1="'+(y0+3)+'" x2="'+mx+'" y2="'+y1+
       '" stroke="#f0e9ff" opacity=".78" stroke-dasharray="5 4" stroke-width="1.2"/>'+
     '<circle class="hzm-peak-halo hzm-marker-halo" cx="'+mx+'" cy="'+my+'" r="10" fill="#57deff" opacity=".55" filter="url(#hzm-peak-glow)"/>'+
     '<circle class="hzm-marker-ring" cx="'+mx+'" cy="'+my+'" r="6" fill="#0b2745" stroke="#69eaff" stroke-width="1.7"/>'+
     '<circle class="hzm-marker-centre" cx="'+mx+'" cy="'+my+'" r="3.5" fill="#f7ffff"/>'+
     '<rect class="hzm-marker-pill" x="'+pillX+'" y="1" width="134" height="23" rx="9" fill="#1a1c4a" stroke="#cb79ff" stroke-width="1.15"/>'+
     '<text class="hzm-marker-pill-text" x="'+(pillX+67)+'" y="17" fill="#fff" font-weight="900" font-size="11" text-anchor="middle">'+esc(label)+'</text>'+
   '</g>'+
   xticks+'<text x="'+w/2+'" y="183" text-anchor="middle" fill="#c5dbef" font-size="10">Punkty – '+esc(code)+'</text></svg>';
}
function updateChartMarker(svg,dist,bins,index){
 const profile=chartProbabilityProfile(dist,bins,index);
 if(!svg||!profile)return;
 const row=bins[index],x0=43,x1=445,y0=15,y1=147;
 const xmin=bins[0].x,xmax=bins[bins.length-1].x+5;
 const maxp=Math.max(1,...bins.map(b=>b.p))*1.22;
 const mx=x0+(row.x+2.5-xmin)/(xmax-xmin)*(x1-x0);
 const my=y1-row.p/maxp*(y1-y0);
 const pillX=Math.max(x0,Math.min(mx-67,x1-134));
 const line=svg.querySelector(".hzm-marker-guide");
 if(line){line.setAttribute("x1",String(mx));line.setAttribute("x2",String(mx))}
 for(const cls of [".hzm-marker-halo",".hzm-marker-ring",".hzm-marker-centre"]){
   const node=svg.querySelector(cls);
   if(node){node.setAttribute("cx",String(mx));node.setAttribute("cy",String(my))}
 }
 const pill=svg.querySelector(".hzm-marker-pill"),text=svg.querySelector(".hzm-marker-pill-text");
 if(pill)pill.setAttribute("x",String(pillX));
 if(text){
   text.setAttribute("x",String(pillX+67));
   text.textContent=row.x+"–"+(row.x+4)+" · "+fmt(profile.binPct)+"%";
 }
 svg.setAttribute("aria-valuenow",String(row.x));
 svg.setAttribute("aria-valuetext",row.x+" do "+(row.x+4)+
   " punktów; "+fmt(profile.binPct)+"% symulacji");
}

/* Results screenshot: derive every metric from the entitled game simulation.
   The histogram is grouped into five-point buckets, hence estimates are
   explicitly approximate. No bookmaker ROI or hit rate is synthesized. */
function showDistributionOverview(sim,game,premium){
 const paid=premium?.entitled===true&&sim&&!sim.error&&game;
 const set=(id,value)=>{const el=$(id);if(el)el.textContent=value};
 const dist=paid?sim.distributions?.[state.chart]:null;
 const average=dist?.average===null||dist?.average===undefined?NaN:Number(dist.average);
 const bins=Array.isArray(dist?.bins)?dist.bins.filter(row=>
    Number.isFinite(Number(row.x))&&Number.isFinite(Number(row.p))&&Number(row.p)>=0):[];
 const count=bins.reduce((sum,row)=>sum+Number(row.p),0);
 const estimate=t=>count>0?100*bins.reduce((sum,row)=>
    sum+(Number(row.x)+2.5>=t?Number(row.p):0),0)/count:null;
 const probability=$("hzm-probability-rows");
 const context=$("hzm-prob-context"),explanation=$("hzm-prob-explanation");
 if(context)context.textContent=state.chart==="match"?"MECZ":state.chart==="away"?
   (game?.away||"GOŚCIE"):(game?.home||"GOSP.");
 if(probability){
   if(!paid||!Number.isFinite(average)||!bins.length){
     probability.textContent=paid?"Brak zweryfikowanego rozkładu punktów.":"Dostępne w Premium.";
     if(explanation)explanation.textContent="Prognoza z modelu · nie kurs bukmacherski";
   }else{
     const sorted=chartBins(dist);
     const selectedIndex=chartBinIndex(sorted,dist);
     const profile=chartProbabilityProfile(dist,sorted,selectedIndex);
     if(!profile){
       probability.textContent="Brak poprawnego rozkładu.";return;
     }
     const fmtLine=value=>Number(value).toFixed(1).replace(".",",");
     const renderPair=item=>[
       {kind:"over",label:"Ponad "+fmtLine(item.line)+" pkt",pct:item.over},
       {kind:"under",label:"Poniżej "+fmtLine(item.line)+" pkt",pct:item.under}
     ].map(row=>
       '<div class="hzm-prob-row '+row.kind+'"><span class="hzm-prob-direction" aria-hidden="true">'+
       (row.kind==="over"?"↑":"↓")+'</span><span class="hzm-prob-threshold" title="'+esc(row.label)+'">'+esc(row.label)+
       '</span><b>'+(row.pct===null?"—":(item.approx?"≈":"")+percent(row.pct))+'</b></div>'
     ).join("");
     probability.innerHTML=profile.lines.map(renderPair).join("");
     if(explanation)explanation.textContent=
       "Wybrano "+profile.start+"–"+profile.end+" pkt: "+
       (profile.exact?"dokładne wyniki z 5 000 symulacji":"≈ z histogramu 5 pkt")+" · nie kursy";
   }
 }
 set("hzm-result-favorite",paid?(sim.home_win_pct>=sim.away_win_pct?
    String(game.home)+" "+percent(sim.home_win_pct):String(game.away)+" "+percent(sim.away_win_pct)):"—");
 set("hzm-result-total",paid?fmt(sim.total_points):"—");
 const range=dist&&Number.isFinite(Number(dist.p10))&&Number.isFinite(Number(dist.p90))&&dist.p10!==null&&dist.p90!==null
  ?Math.round(Number(dist.p10))+"–"+Math.round(Number(dist.p90)):"—";
 set("hzm-result-range",paid?range:"—");
 const variance=count>0&&Number.isFinite(average)?
   bins.reduce((sum,row)=>sum+Math.pow(Number(row.x)+2.5-average,2)*Number(row.p),0)/count:null;
 set("hzm-result-sd",paid&&variance!==null?"±"+fmt(Math.sqrt(variance)):"—");
}
function showResultsDashboard(game,sim,premium){
 const paid=premium?.entitled===true;
 const ctx=paid&&sim&&!sim.error?sim.model_context:null;
 const set=(id,value)=>{const el=$(id);if(el)el.textContent=value};
 set("hzm-hero-away-label",game?.away||"goście");
 set("hzm-hero-home-label",game?.home||"gospodarze");
 set("hzm-hero-away-points",paid&&sim&&!sim.error?fmt(sim.away_points):"—");
 set("hzm-hero-home-points",paid&&sim&&!sim.error?fmt(sim.home_points):"—");
 set("hzm-mini-away-code",game?.away||"gości");
 set("hzm-mini-home-code",game?.home||"gospodarzy");
 const sliders=[["hzm-mini-pace","hzm-mini-pace-output",state.scenarioPct],
                ["hzm-mini-off-away","hzm-mini-off-away-output",state.offAwayPct],
                ["hzm-mini-off-home","hzm-mini-off-home-output",state.offHomePct]];
 sliders.forEach(([id,output,value])=>{
   const element=$(id);if(element&&Number(element.value)!==value)element.value=String(value);
   set(output,(value>0?"+":"")+value+"%");
 });
 const eligible=paid&&game?.state==="scheduled"&&Date.parse(game?.start||"")>Date.now()&&sim&&!sim.error;
 const run=$("hzm-mini-run");if(run)run.disabled=!eligible;
 set("hzm-mini-finding-form",ctx?
   "Zweryfikowane mecze obu drużyn: "+String(ctx.away_sample??"—")+" / "+String(ctx.home_sample??"—")+
   ". Próbki mogą być ograniczone.":"Forma: brak wystarczających danych w bieżącym widoku.");
 set("hzm-mini-finding-winner",paid&&sim&&!sim.error&&game?
   "Model wskazuje "+String(sim.home_win_pct>=sim.away_win_pct?game.home:game.away)+
   " ("+percent(Math.max(Number(sim.home_win_pct),Number(sim.away_win_pct)))+") — szansa niekalibrowana.":
   "Wybierz mecz Premium, aby poznać prognozę zwycięzcy.");
 set("hzm-mini-finding-context",ctx?
   (ctx.advanced_available?"NBA Advanced i historia ESPN w danych modelu. ":
    "Brak pełnego NBA Advanced; model opiera się na historii meczów. ")+
    (ctx.v75_factors?.injuries_espn_fresh?
     "Statusy ESPN wymagają potwierdzenia.":"Kontuzje/składy mogą być niepotwierdzone."):
   "Informacje o kontuzjach i składach mogą być niepełne.");
 const report=paid?premium?.backtest:null;
 const key=state.model==="legacy_v72"?"old":state.model==="research_form_v74"?"enriched":"v75";
 const model=report&&!report.error&&Array.isArray(report.models)?
   report.models.find(row=>row?.key===key):null;
 const validReport=Number.isInteger(report?.games)&&report.games>0&&report.games<=40&&
   model&&Number.isFinite(Number(model.winner_accuracy_pct))&&
   Number(model.winner_accuracy_pct)>=0&&Number(model.winner_accuracy_pct)<=100;
 set("hzm-recent-accuracy",validReport?percent(model.winner_accuracy_pct):"—");
 set("hzm-recent-roi","N/D");
 set("hzm-recent-sample",validReport?String(report.games):"—");
 set("hzm-recent-note",validReport?"Backtest offline · nie jest potwierdzeniem skuteczności wersji produkcyjnej. ROI: brak kursów.":
   "Uruchom Model & Backtest, aby zobaczyć zweryfikowaną próbę. ROI wymaga kursów.");
}

function showChart(sim,game,premium){
  showDistributionOverview(sim,game,premium);
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
  const heading=$("hzm-chart-heading");if(heading)heading.textContent=state.chart==="match"?"Rozkład punktów meczu":"Rozkład punktów "+(code||"drużyny");
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

function playerInitials(item){
 return String(item?.name||"").split(/\s+/).filter(Boolean).slice(0,2)
   .map(name=>name[0]).join("").toUpperCase().slice(0,3);
}
function playerAvatar(item,large=false){
 const id=String(item?.espn_id||"");
 const initials=playerInitials(item);
 // ESPN ID comes from the same verified historical boxscore as the name and
 // team; unverified identities use the typographic portrait fallback.
 const image=/^\d{1,12}$/.test(id)
    ?'<img src="https://a.espncdn.com/i/headshots/nba/players/full/'+id+
      '.png" alt="" loading="lazy" referrerpolicy="no-referrer">':"";
 return '<span class="hzm-player-avatar'+(large?' large':'')+'" aria-hidden="true">'+
   '<span class="hzm-avatar-fallback">'+esc(initials||"NBA")+'</span>'+image+'</span>';
}
function playerMetric(item,market){
 const a=safeProjection(item?.pts),b=safeProjection(item?.reb),c=safeProjection(item?.ast);
 if(item?.availability==="Out"&&state.model==="research_context_v75")return null;
 return market==="PTS"?a:market==="REB"?b:market==="AST"?c:
   market==="PRA"&&a!==null&&b!==null&&c!==null?a+b+c:null;
}
function playerHistory(item,market){
 const data=Array.isArray(item?.history)?item.history:[];
 const key=market.toLowerCase();
 return data.filter(row=>row&&/^\d{4}-\d{2}-\d{2}$/.test(String(row.date||""))&&
    safeProjection(row[key])!==null).slice(-15).map(row=>({
     date:row.date,value:Number(row[key])
   }));
}
function historyMean(rows,count){
 return rows.length>=count?rows.slice(-count).reduce((sum,row)=>sum+row.value,0)/count:null;
}
function playerInspector(item,players,game,withMinutes){
 const container=$("hzm-player-inspector");
 if(!container)return;
 if(!item){
  container.innerHTML='<div class="hzm-inspector-placeholder">Wybierz zawodnika, aby zobaczyć jego projekcję i historyczne występy.</div>';
  return;
 }
 const name=String(item.name||"").slice(0,70),code=String(item.team||"").slice(0,4);
 const status=withMinutes?String(item.availability||"Niezweryfikowany").slice(0,50):"";
 const out=withMinutes&&status==="Out";
 const forecasts=["PTS","REB","AST","PRA"].map(key=>[key,playerMetric(item,key)]);
 const metrics=forecasts.map(([key,value])=>
  '<div class="hzm-inspector-metric'+(key==="PRA"?' pra':'')+
  (key===state.playerMarket?' current':'')+'"><span>'+key+
  '</span><strong>'+fmt(value)+'</strong></div>').join("");
 const sample=withMinutes&&Number.isInteger(Number(item.minutes_sample))?Math.max(0,Number(item.minutes_sample)):0;
 const minutes=withMinutes?safeProjection(item.minutes):null;
 const minuteLabel=withMinutes
  ?minutes===null?'— · brak danych':fmt(minutes)+' min ('+sample+' gier)'
  :'— · '+esc(modelLabel());
 const recent=playerHistory(item,state.playerMarket);
 const l5=historyMean(recent,5);
 const statusText=withMinutes?("ESPN: "+status):"Dostępność: nieoceniana w tym modelu";
 const statusClass=out?" is-out":["Questionable","Doubtful","Day-to-day","Sprzeczne"].includes(status)?" is-uncertain":"";
 const playerPosition=["PG","SG","SF","PF","C","G","F"].includes(item.position)?item.position:"";
 container.innerHTML=
  '<div class="hzm-inspector-identity">'+playerAvatar(item,true)+
  '<div class="hzm-inspector-identity-copy"><div class="hzm-inspector-top"><span>PLAYER FORECAST · '+esc(modelLabel())+'</span><strong>'+esc(code)+'</strong></div>'+
  '<h3>'+esc(name)+'</h3><div class="hzm-inspector-sub">'+esc(code)+
  (playerPosition?' · '+esc(playerPosition):'')+' · szacunek na wybrany mecz</div></div></div>'+
  '<div class="hzm-inspector-metrics">'+metrics+'</div>'+
  '<span class="hzm-inspector-status'+statusClass+'">'+esc(statusText)+'</span>'+
  '<div class="hzm-inspector-facts"><div title="Minuty: brak zweryfikowanego szacunku w modelach bez estymatora minut"><span>◷</span> Minuty<strong>'+minuteLabel+'</strong></div>'+
  '<div><span>⌁</span> Forma L5 · '+state.playerMarket+'<strong>'+(l5!==null?fmt(l5):'— · '+recent.length+'/5')+'</strong></div>'+
  '<div><span>▥</span> Historia ESPN<strong>'+recent.length+' występów</strong></div>'+
  '<div><span>ⓘ</span> Model<strong>'+esc(modelLabel())+'</strong></div></div>'+
  '<p class="hzm-inspector-disclaimer">'+(out?
    'ESPN: OUT — model nie pokazuje projekcji aktywnego występu.':
    'PRA to suma średnich PTS + REB + AST, nie odrębny rozkład. Historia to rzeczywiste wyniki, a nie prognoza.')+
  '</p>'+(withMinutes&&players?.minutes_warning?
    '<small class="hzm-inspector-warning">'+esc(players.minutes_warning)+'</small>':'')+
  '<div class="hzm-inspector-actions" role="group" aria-label="Historia w Player Props">'+
  (out?'':forecasts.map(([key,value])=>value===null?'':'<button type="button" data-hzm-history-market="'+key+'"'+
    (state.fromProps?.market===key?' class="is-related"':'')+
    '>Historia '+key+' ›</button>').join(""))+'</div>'+
  (state.fromProps?.name===name&&state.fromProps?.team===code?
    '<button type="button" class="hzm-return-to-props" data-hzm-return-props>← Wróć do Player Props</button>':'');
}
function playerHistogramMarkup(item,market){
 const history=playerHistory(item,market);
 const model=playerMetric(item,market);
 if(history.length<3)return '<div class="hzm-player-plot-empty">Za mało potwierdzonych występów do wykresu (min. 3).</div>';
 const values=history.map(row=>row.value);
 const lo=Math.max(0,Math.floor(Math.min(...values,model??Infinity)-3));
 const hi=Math.max(lo+6,Math.ceil(Math.max(...values,model??0)+3));
 const count=Math.min(17,Math.max(7,Math.ceil((hi-lo)/3)));
 const step=(hi-lo)/count,bins=Array(count).fill(0);
 values.forEach(v=>{const index=Math.min(count-1,Math.max(0,Math.floor((v-lo)/step)));bins[index]++});
 const max=Math.max(...bins,1),x0=34,x1=552,y0=22,y1=164;
 const toX=v=>x0+((v-lo)/(hi-lo))*(x1-x0);
 const bars=bins.map((c,i)=>{
  const x=x0+i*(x1-x0)/count+1.4,w=(x1-x0)/count-2.8;
  const y=y1-c/max*117;
  return '<rect x="'+x.toFixed(1)+'" y="'+y.toFixed(1)+'" width="'+Math.max(1,w).toFixed(1)+
   '" height="'+(y1-y).toFixed(1)+'" rx="2" fill="'+(i<count*.55?'url(#hzm-hist-blue)':'url(#hzm-hist-purple)')+'"/>';
 }).join("");
 const tickValues=Array.from({length:6},(_,i)=>lo+(hi-lo)*i/5);
 const ticks=tickValues.map(v=>'<text x="'+toX(v).toFixed(1)+'" y="188" fill="#a2bdd9" font-size="12" text-anchor="middle">'+
  Math.round(v)+'</text>').join("");
 const grids=Array.from({length:4},(_,i)=>'<line x1="'+x0+'" y1="'+(y1-i*35)+'" x2="'+x1+
  '" y2="'+(y1-i*35)+'" stroke="#365179" opacity=".55" stroke-width=".7"/>').join("");
 const projection=model===null?'':('<line x1="'+toX(Math.max(lo,Math.min(hi,model))).toFixed(1)+
  '" y1="17" x2="'+toX(Math.max(lo,Math.min(hi,model))).toFixed(1)+
  '" y2="'+y1+'" stroke="#f0c2ff" stroke-width="2" stroke-dasharray="5 4"/>'+
  '<text x="'+Math.min(x1-50,Math.max(x0+54,toX(model))).toFixed(1)+
  '" y="14" text-anchor="middle" fill="#f4ddff" font-weight="900" font-size="11">Proj. '+fmt(model)+'</text>');
 return '<svg viewBox="0 0 574 205" role="img" aria-label="'+esc('Historyczny histogram '+market+', '+history.length+' meczów')+'">'+
  '<defs><linearGradient id="hzm-hist-blue" x2="0" y2="1"><stop stop-color="#14efff"/><stop offset="1" stop-color="#1460ad"/></linearGradient>'+
  '<linearGradient id="hzm-hist-purple" x2="0" y2="1"><stop stop-color="#f369f6"/><stop offset="1" stop-color="#5d35b2"/></linearGradient></defs>'+
  grids+bars+projection+ticks+'</svg>';
}
function playerTrendMarkup(item,market,n){
 const history=playerHistory(item,market);
 if(history.length<3)return '<div class="hzm-player-plot-empty">Brak przynajmniej 3 potwierdzonych występów ESPN.</div>';
 const rows=history.slice(-n),values=rows.map(row=>row.value);
 const low=Math.max(0,Math.floor(Math.min(...values)-3));
 const high=Math.max(low+4,Math.ceil(Math.max(...values)+3));
 const x0=38,x1=526,y0=20,y1=154;
 const xy=(v,i)=>[x0+(rows.length<2?0:i/(rows.length-1)*(x1-x0)),
   y1-(v-low)/(high-low)*(y1-y0)];
 const points=values.map((v,i)=>xy(v,i));
 const line=points.map(([x,y])=>x.toFixed(2)+','+y.toFixed(2)).join(' ');
 const area='M '+points[0][0]+','+y1+' L '+points.map(([x,y])=>x.toFixed(1)+','+y.toFixed(1)).join(' L ')+
  ' L '+points[points.length-1][0]+','+y1+' Z';
 const circles=points.map(([x,y],i)=>'<circle cx="'+x.toFixed(1)+'" cy="'+y.toFixed(1)+'" r="4.2" fill="#f4fcff" stroke="#48eaff" stroke-width="2"/>'+
  '<text x="'+x.toFixed(1)+'" y="'+Math.max(13,y-11).toFixed(1)+'" font-size="10" font-weight="800" text-anchor="middle" fill="#e8dcff">'+fmt(values[i])+'</text>').join("");
 const grids=Array.from({length:4},(_,i)=>'<line x1="'+x0+'" x2="'+x1+'" y1="'+(y1-38*i)+'" y2="'+(y1-38*i)+'" stroke="#365179" stroke-width=".7" opacity=".55"/>').join("");
 return '<svg viewBox="0 0 552 184" role="img" aria-label="'+esc('Forma historyczna '+market+', '+rows.length+' z '+n+' meczów')+'">'+
  '<defs><linearGradient id="hzm-trend-glow" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#bc6eff" stop-opacity=".38"/><stop offset="1" stop-color="#0a2446" stop-opacity="0"/></linearGradient></defs>'+
  grids+'<path d="'+area+'" fill="url(#hzm-trend-glow)"/><polyline points="'+line+
  '" fill="none" stroke="#18eafa" stroke-width="2.3"/>'+circles+
  '<text x="'+x1+'" y="179" fill="#91b9d5" text-anchor="end" font-size="10">ESPN · '+rows.length+' obserwacji</text></svg>';
}
function showPlayerAnalytics(item){
 const hist=$("hzm-player-histogram"),trend=$("hzm-player-trend"),rates=$("hzm-player-rates"),averages=$("hzm-player-averages");
 if(!hist||!trend||!rates||!averages)return;
 const market=state.playerMarket;
 $("hzm-player-chart-name").textContent=item?.name||"wybrany zawodnik";
 $("hzm-player-rate-metric").textContent=market;
 $("hzm-player-trend-metric").textContent=market;
 $("hzm-player-average-metric").textContent=market;
 for(const b of document.querySelectorAll("[data-hzm-player-market]")){
  const active=b.dataset.hzmPlayerMarket===market;
  b.classList.toggle("active",active);b.setAttribute("aria-pressed",String(active));
 }
 for(const b of document.querySelectorAll("[data-hzm-history-window]")){
  const active=b.dataset.hzmHistoryWindow==="season"
     ?state.playerHistoryWindow==="season"
     :Number(b.dataset.hzmHistoryWindow)===state.playerHistoryWindow;
  b.classList.toggle("active",active);b.setAttribute("aria-pressed",String(active));
 }
 if(!item){
  hist.innerHTML='<div class="hzm-player-plot-empty">Wybierz zawodnika z listy.</div>';
  trend.innerHTML='<div class="hzm-player-plot-empty">Brak wybranego zawodnika.</div>';
  rates.innerHTML='<div class="hzm-player-plot-empty">—</div>';
  averages.innerHTML='<div class="hzm-player-plot-empty">—</div>';
  $("hzm-player-rates-source").textContent="Źródło: wcześniejsze mecze ESPN";
  return;
 }
 const rows=playerHistory(item,market);
 hist.innerHTML=playerHistogramMarkup(item,market);
 trend.innerHTML=playerTrendMarkup(item,market,
  state.playerHistoryWindow==="season"?rows.length:state.playerHistoryWindow);
 $("hzm-player-rates-source").textContent="Historyczna częstość · "+rows.length+" meczów (nie prawdopodobieństwo modelu)";
 const projection=playerMetric(item,market);
 if(projection!==null&&rows.length>=3){
  const anchor=Math.max(0.5,Math.round(projection/5)*5-7.5);
  rates.innerHTML=[0,5,10,15].map(k=>{
   const line=anchor+k;
   const over=rows.filter(r=>r.value>line).length;
   const pct=over/rows.length*100;
   return '<div><span>&gt; '+fmt(line)+'</span><strong>'+fmt(pct)+'%</strong></div>';
  }).join('');
 }else rates.innerHTML='<div class="hzm-player-plot-empty">Niepełna próba historyczna.</div>';
 averages.innerHTML=[5,10,15].map(n=>{
  const mean=historyMean(rows,n);
  return '<div><span>L'+n+'</span><strong>'+fmt(mean)+'</strong>'+
    '<small>'+(rows.length>=n?n+' meczów':'próba '+rows.length+'/'+n)+'</small></div>';
 }).join('')+'<div><span>Sezon</span><strong>—</strong><small>brak pełnej próby</small></div>';
 $("hzm-player-averages-source").textContent="Przed wybranym meczem · "+rows.length+
  " potwierdzonych występów; niepełne okna i sezon oznaczono —.";
}
function showPlayers(premium,players,game){
 const panel=$("hzm-players-panel"),button=$("hzm-expand-players"),rows=$("hzm-player-rows");
 const focused=state.view==="players",withMinutes=state.model==="research_context_v75"&&focused;
 const version=$("hzm-player-version");
 if(version)version.textContent=state.model==="research_context_v75"?"V7.5":state.model==="research_form_v74"?"V7.4":"V7.2";
 const headings=$("hzm-player-headings");
 headings.classList.toggle("with-min",withMinutes);
 headings.innerHTML=focused?(withMinutes?'<span>MIN</span>':'')+'<span>PTS</span><span>REB</span><span>AST</span>':
   '<span>PTS</span><span>REB</span><span>AST</span><span>PRA</span>';
 for(const side of ["away","home"]){
   const btn=$("hzm-result-team-"+side);
   if(btn)btn.textContent=game?.[side]|| (side==="away"?"GOŚCIE":"GOSP.");
 }
 $("hzm-players-panel")?.querySelectorAll("[data-hzm-result-team]").forEach(button=>{
   button.setAttribute("aria-pressed",String(button.dataset.hzmResultTeam===state.resultTeam));
 });
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
   showPlayerAnalytics(null);
   return;
 }
 if(!players){
   rows.innerHTML='<div class="hzm-no-players">Pobieranie projekcji zawodników z ESPN…</div>';
   if(count)count.textContent="";
   playerInspector(null,players,game,withMinutes);showPlayerAnalytics(null);return;
 }
 if(!Array.isArray(players.players)||!players.players.length){
   rows.innerHTML='<div class="hzm-no-players">'+esc(players.error||'Brak zweryfikowanych danych zawodników.')+'</div>';
   if(count)count.textContent="0 zawodników";
   playerInspector(null,players,game,withMinutes);showPlayerAnalytics(null);return;
 }
 // Team and fixture identities come from the server-entitled selected game.
 const athletes=players.players.map((item,index)=>({item,index})).filter(({item})=>
   item&&[String(game?.away||"").toUpperCase(),String(game?.home||"").toUpperCase()]
     .includes(String(item.team||"").toUpperCase()));
 const query=state.playerQuery.trim().toLocaleLowerCase("pl");
 const filtered=focused?athletes.filter(({item})=>
   (state.playerTeam==="all"||String(item.team).toUpperCase()===String(codes[state.playerTeam]||"").toUpperCase())&&
   (!query||String(item.name||"").toLocaleLowerCase("pl").includes(query))):
   athletes.filter(({item})=>state.resultTeam==="all"||
     String(item.team||"").toUpperCase()===String(game?.[state.resultTeam]||"").toUpperCase());
 if(!focused)filtered.sort((a,b)=>(safeProjection(b.item.pts)??-1)-(safeProjection(a.item.pts)??-1));
 if(focused){
   const market=state.playerMarket;
   filtered.sort((a,b)=>(playerMetric(b.item,market)??-1)-(playerMetric(a.item,market)??-1));
 }
 const visible=focused?filtered:(state.expanded?filtered:filtered.slice(0,5));
 if(count)count.textContent=focused?filtered.length+" z "+athletes.length+" zawodników":"";
 if(focused&&!filtered.some(p=>p.index===state.playerIndex))state.playerIndex=filtered[0]?.index??-1;
 if(!visible.length){
   rows.innerHTML='<div class="hzm-no-players">Brak zawodników spełniających wybrane filtry.</div>';
   playerInspector(null,players,game,withMinutes);showPlayerAnalytics(null);return;
 }
 const lastScroll=rows.scrollTop;
 rows.innerHTML=visible.map(({item,index})=>{
   const initials=playerInitials(item);
   const status=withMinutes?String(item.availability||''):'';
   const atRisk=["Questionable","Doubtful","Day-to-day","Sprzeczne"].includes(status);
   const statusHtml=status==="Out"?'<small class="hzm-injured">'+esc(item.team)+' · OUT (ESPN)</small>':
     atRisk?'<small class="hzm-uncertain">'+esc(item.team)+' · '+esc(status)+' (ESPN)</small>':
     '<small class="'+(item.team===players.home?'home':'')+'">'+esc(item.team)+'</small>';
   const avatar=focused?playerAvatar(item):'<span class="hzm-player-initials">'+esc(initials)+'</span>';
   if(focused){
     const market=state.playerMarket;
     const scores=["PTS","REB","AST","PRA"].map(key=>
       '<span class="hzm-focus-stat'+(key===market?' active':'')+'">'+fmt(playerMetric(item,key))+'</span>').join("");
     return '<button type="button" class="hzm-player-row hzm-player-row-rich" data-hzm-player-index="'+index+
       '" aria-pressed="'+(index===state.playerIndex)+'" aria-label="'+esc('Projekcja '+item.name+', '+item.team)+'">'+
       avatar+'<span class="hzm-player-info"><strong title="'+esc(item.name)+'">'+esc(item.name)+'</strong>'+statusHtml+'</span>'+
       '<span class="hzm-player-stats">'+scores+'</span></button>';
   }
   const pts=safeProjection(item.pts);
   const meter=pts===null?0:Math.max(0,Math.min(100,Math.round(pts/40*100)));
   const pra=playerMetric(item,"PRA");
   return '<button type="button" class="hzm-player-row" data-hzm-player-index="'+index+
      '" aria-pressed="false" aria-label="'+esc('Szczegóły prognozy '+item.name+', '+item.team)+'">'+
     avatar+'<span class="hzm-player-info"><strong>'+esc(item.name)+'</strong>'+statusHtml+
     '<span class="hzm-result-roster-bar" aria-hidden="true" title="Względna projekcja PTS, nie prawdopodobieństwo trafienia"><i style="width:'+meter+'%"></i></span></span>'+
     '<span class="hzm-player-stats"><span>'+fmt(item.pts)+'</span><span>'+fmt(item.reb)+
     '</span><span>'+fmt(item.ast)+'</span><span>'+fmt(pra)+'</span></span></button>';
 }).join("");
 if(focused)rows.scrollTop=lastScroll;
 if(!state.expanded&&filtered.length>5)button.textContent='Pokaż wszystkich zawodników ('+filtered.length+') ▾';
 if(focused){
   const item=filtered.find(p=>p.index===state.playerIndex)?.item||null;
   playerInspector(item,players,game,withMinutes);
   showPlayerAnalytics(item);
 }else if(inspector)inspector.innerHTML='';
}

function maybeLoadPaid(game,premium,sim,players){
  if(!premium?.entitled||!game||!["scheduled","final"].includes(game.state))return;
  // The Backtest panel has its own server endpoint and needs no selected-game
  // simulation. Match Intelligence / Team Comparison need team-level results,
  // but must not trigger expensive player-roster projections.
  if(state.view==="backtest")return;
  const key=state.day+"|"+game.id+"|"+state.model;
  if(!sim&&state.gamePending!==key){
    state.gamePending=key;
    callbacks?.loadGame?.(state.day,game.id,state.model);
  }
  const needsPlayers=state.view==="players"||state.view==="results"||
    (state.view==="scenario"&&state.model==="research_context_v75");
  if(needsPlayers&&sim&&!sim.error&&!players&&state.playersPending!==key){
    state.playersPending=key;
    callbacks?.loadPlayers?.(state.day,game.id,state.model);
  }
}
function showScenario(game,sim,premium){
 const panel=$("hzm-scenario-panel");
 if(!panel)return;
 const paid=premium?.entitled===true;
 const eligible=paid&&game?.state==="scheduled"&&Date.parse(game?.start||"")>Date.now()&&sim&&!sim.error;
 const pace=$("hzm-scenario-pace"),run=$("hzm-scenario-run");
 if(pace&&Number(pace.value)!==state.scenarioPct)pace.value=String(state.scenarioPct);
 const label=$("hzm-scenario-pace-display");
 if(label)label.textContent=(state.scenarioPct>0?"+":"")+state.scenarioPct+"%";
 for(const side of ["away","home"]){
   const val=side==="away"?state.offAwayPct:state.offHomePct;
   const input=$("hzm-scenario-off-"+side),value=$("hzm-scenario-off-"+side+"-display"),code=$("hzm-scenario-off-"+side+"-code");
   if(input&&Number(input.value)!==val)input.value=String(val);
   if(value)value.textContent=(val>0?"+":"")+val+"%";
   if(code)code.textContent=game?.[side]||(side==="away"?"GOŚCIE":"GOSPODARZE");
 }
 if(run)run.disabled=!eligible;
 const baseline=$("hzm-scenario-base"),changed=$("hzm-scenario-whatif"),delta=$("hzm-scenario-delta"),status=$("hzm-scenario-status");
 if(!baseline||!changed||!delta||!status)return;
 baseline.textContent=eligible?fmt(sim.total_points)+" pkt":"—";
 changed.textContent="—";delta.textContent="—";
 const valid=v=>v!==null&&v!==undefined&&v!==""&&Number.isFinite(Number(v));
 const points=v=>valid(v)?fmt(v)+" pkt":"—";
 const wins=v=>valid(v)&&Number(v)>=0&&Number(v)<=100?fmt(v)+"%":"—";
 for(const side of ["away","home"]){
   const code=$("hzm-scenario-"+side+"-code"),pt=$("hzm-scenario-"+side+"-points"),win=$("hzm-scenario-"+side+"-win");
   if(code)code.textContent=game?.[side]|| (side==="away"?"GOŚCIE":"GOSPODARZE");
   if(pt)pt.textContent=eligible?points(sim[side+"_points"])+" → —":"—";
   if(win)win.textContent=eligible?wins(sim[side+"_win_pct"])+" → —":"—";
 }
 if(!paid){status.textContent="Wymagane aktywne Premium. Scenariusz nie ujawnia danych modelu.";return}
 if(!game){status.textContent="Wybierz mecz.";return}
 if(game.state!=="scheduled"||!(Date.parse(game.start||"")>Date.now())){
   status.textContent="Scenariusze dostępne tylko dla potwierdzonych przyszłych spotkań.";return
 }
 if(!sim){status.textContent="Pobieranie bazowej prognozy…";return}
 if(sim.error){status.textContent=sim.error;return}
 const data=premium?.scenario;
 const matched=data&&data.date===state.day&&String(data.game_id)===String(game.id)&&
   data.model_id===state.model&&data.pace_pct===state.scenarioPct&&
   Number(data.off_away_pct??0)===state.offAwayPct&&
   Number(data.off_home_pct??0)===state.offHomePct;
 if(matched){
   if(data.error){status.textContent=String(data.error).slice(0,180);return}
   const total=data.scenario?.total_points,base=data.baseline?.total_points;
   if(valid(total)&&valid(base)){
     changed.textContent=fmt(total)+" pkt";
     delta.textContent=(total-base>0?"+":"")+fmt(total-base)+" pkt";
     for(const side of ["away","home"]){
       const a=data.baseline||{},b=data.scenario||{};
       const pt=$("hzm-scenario-"+side+"-points"),win=$("hzm-scenario-"+side+"-win");
       if(pt)pt.textContent=points(a[side+"_points"])+" → "+points(b[side+"_points"]);
       const aw=a[side+"_win_pct"],bw=b[side+"_win_pct"];
       if(win)win.textContent=wins(aw)+" → "+wins(bw)+
         (valid(aw)&&valid(bw)&&Number(aw)<=100&&Number(bw)<=100
           ?" ("+(bw-aw>0?"+":"")+fmt(bw-aw)+" pp)":"");
     }
     status.textContent="5 000 symulacji · tempo: "+(state.scenarioPct>0?"+":"")+state.scenarioPct+
       "% · ofensywa "+esc(game.away)+": "+(state.offAwayPct>0?"+":"")+state.offAwayPct+
       "% / "+esc(game.home)+": "+(state.offHomePct>0?"+":"")+state.offHomePct+"%.";
     return;
   }
 }
 status.textContent=state.scenarioPending===state.day+"|"+game.id+"|"+state.model+"|"+state.scenarioPct+"|"+state.offAwayPct+"|"+state.offHomePct
   ?"Trwa przeliczanie scenariusza…":"Zmień założenie i kliknij Przelicz 5 000 symulacji.";
}

function showPlayerMinutes(game,players,premium){
 const select=$("hzm-minute-player"),slider=$("hzm-minute-delta"),run=$("hzm-minute-run");
 const status=$("hzm-minute-status"),display=$("hzm-minute-delta-output");
 if(!select||!slider||!run||!status||!display)return;
 const ids=["minutes","pts","reb","ast","pra"];
 const clear=()=>{for(const id of ids){const el=$("hzm-minute-"+id);if(el)el.textContent=(id==="minutes"?"Minuty":id.toUpperCase())+": —";}};
 clear();
 const validGame=game?.state==="scheduled"&&Date.parse(game?.start||"")>Date.now();
 const entitled=premium?.entitled===true;
 const allowed=entitled&&validGame&&state.model==="research_context_v75";
 const list=allowed&&Array.isArray(players?.players)?players.players:[];
 const validMetric=p=>safeProjection(p?.pts)!==null&&safeProjection(p?.reb)!==null&&safeProjection(p?.ast)!==null;
 const good=(p)=>p&&p.availability!=="Out"&&
   [game?.away,game?.home].includes(p.team)&&Number.isInteger(Number(p.minutes_sample))&&
   Number(p.minutes_sample)>=3&&safeProjection(p.minutes)!==null&&
   Number(p.minutes)>=5&&Number(p.minutes)<=44&&validMetric(p);
 const eligible=list.map((p,i)=>({p,i})).filter(x=>good(x.p));
 if(!eligible.some(x=>x.i===state.minuteIndex)){
   state.minuteIndex=eligible.length?eligible[0].i:-1;
   state.minuteDelta=0;
   state.minutePending="";
 }
 select.innerHTML=eligible.length
  ?eligible.map(({p,i})=>'<option value="'+i+'">'+esc(p.name)+' · '+esc(p.team)+'</option>').join("")
  :'<option value="">Brak dostępnych minut</option>';
 select.disabled=!eligible.length;
 select.value=state.minuteIndex<0?"":String(state.minuteIndex);
 slider.disabled=!eligible.length;
 slider.value=String(state.minuteDelta);
 display.textContent=(state.minuteDelta>0?"+":"")+state.minuteDelta+" min";
 const item=list[state.minuteIndex];
 const newMinutes=item?Number(item.minutes)+state.minuteDelta:null;
 run.disabled=!item||newMinutes<5||newMinutes>44;
 if(!entitled){status.textContent="Dostępne tylko w Premium.";return}
 if(state.model!=="research_context_v75"){status.textContent="Wybierz V7.5: pozostałe modele nie mają zweryfikowanych szacunków minut.";return}
 if(!validGame){status.textContent="Analiza minut dostępna wyłącznie przed potwierdzonym meczem.";return}
 if(!players){status.textContent="Pobieranie projekcji V7.5 z ESPN…";return}
 if(!eligible.length){status.textContent="Brak zawodnika z próbką ≥3 występów, prawidłowym szacunkiem minut i kompletem PTS/REB/AST. OUT jest wykluczony.";return}
 if(run.disabled){status.textContent="Zakładany czas gry musi mieścić się w zakresie 5–44 minut.";return}
 const record=premium?.minute_scenario;
 const matched=record&&record.date===state.day&&record.game_id===String(game.id)&&
    record.model_id===state.model&&record.name===item.name&&record.team===item.team&&
    record.minute_delta===state.minuteDelta;
 if(matched){
   if(record.error){status.textContent=String(record.error).slice(0,180);return}
   const base=record.baseline||{},hyp=record.scenario||{};
   if(["pts","reb","ast","pra"].every(k=>safeProjection(base[k])!==null&&safeProjection(hyp[k])!==null)&&
      safeProjection(record.baseline_minutes)!==null&&safeProjection(record.scenario_minutes)!==null){
     $("hzm-minute-minutes").textContent="MIN: "+fmt(record.baseline_minutes)+" → "+fmt(record.scenario_minutes);
     for(const k of ["pts","reb","ast","pra"])
       $("hzm-minute-"+k).textContent=k.toUpperCase()+": "+fmt(base[k])+" → "+fmt(hyp[k]);
     status.textContent="Szacunek liniowy: stała produkcja na minutę; "+record.minutes_sample+
        " występów. ESPN: "+String(record.availability||"niezweryfikowany")+
        ". Bez korekty wyniku drużyny, rotacji i wpływu kontuzji.";
     return;
   }
 }
 const key=state.day+"|"+game.id+"|"+state.model+"|"+item.team+"|"+item.name+"|"+state.minuteDelta;
 status.textContent=state.minutePending===key?"Obliczanie wrażliwości minut…":
    "Wariant hipotetyczny: "+fmt(item.minutes)+" → "+fmt(newMinutes)+" min · ESPN: "+
    String(item.availability||"niezweryfikowany")+". Kliknij Oblicz projekcję.";
}
function showAvailability(game,players,sim,premium){
 const message=$("hzm-availability-message"),freshness=$("hzm-availability-freshness");
 if(!message||!freshness)return;
 const reset=()=>{
   for(const side of ["away","home"]){
     $("hzm-availability-"+side+"-code").textContent=game?.[side]||
       (side==="away"?"GOŚCIE":"GOSPODARZE");
     $("hzm-availability-"+side+"-count").textContent="—";
     $("hzm-availability-"+side+"-list").textContent="Brak zweryfikowanego raportu.";
     $("hzm-availability-"+side+"-impact").textContent="Korekta modelu V7.5: —";
   }
 };
 reset();
 freshness.textContent="BRAK POTWIERDZENIA";
 if(premium?.entitled!==true){
   message.textContent="Wymagane Premium. Dane dostępności nie są udostępniane w wersji darmowej.";
   return;
 }
 if(state.model!=="research_context_v75"){
   message.textContent="Wybierz model V7.5 — w V7.2 i V7.4 nie ma weryfikowanych statusów kontuzji.";
   return;
 }
 if(game?.state!=="scheduled"||!(Date.parse(game.start||"")>Date.now())){
   message.textContent="Injury Watch obejmuje tylko potwierdzone przyszłe spotkania.";
   return;
 }
 if(!players||!sim){
   message.textContent="Pobieranie danych zawodników oraz czynników modelu V7.5…";
   return;
 }
 if(players.error||sim.error){
   message.textContent=String(players.error||sim.error).slice(0,160);
   return;
 }
 const factors=sim.model_context?.v75_factors;
 const validUntil=Date.parse(String(players.injury_report_valid_until||""));
 const fresh=players.injury_report_fresh===true&&
   factors?.injuries_espn_fresh===true&&
   Number.isFinite(validUntil)&&validUntil>Date.now();
 if(!fresh){
   message.textContent="Brak raportu ESPN z aktualną oceną świeżości (do 90 minut od publikacji). Nie można potwierdzić statusów.";
   freshness.textContent="DANE NIEAKTUALNE LUB BRAK RAPORTU";
   return;
 }
 freshness.textContent="RAPORT ESPN · W OKNIE 90 MIN";
 message.textContent="Statusy z raportu ESPN powiązane z zawodnikami wybranego meczu. Wpływ punktowy to wcześniejsza ograniczona korekta modelu V7.5.";
 const statuses=new Set(["Out","Questionable","Doubtful","Day-to-day","Probable","Sprzeczne"]);
 for(const side of ["away","home"]){
   const team=game[side];
   const rows=(Array.isArray(players.players)?players.players:[])
      .filter(p=>p&&p.team===team&&statuses.has(p.availability)).slice(0,24);
   const out=rows.filter(p=>p.availability==="Out").length;
   const uncertain=rows.filter(p=>["Questionable","Doubtful","Day-to-day","Sprzeczne"].includes(p.availability)).length;
   $("hzm-availability-"+side+"-count").textContent=
      "OUT "+out+" · NIEPEWNI "+uncertain;
   const list=$("hzm-availability-"+side+"-list");
   if(!rows.length){list.textContent="Brak powiązanych wpisów statusowych ESPN; nie oznacza to potwierdzonego pełnego składu.";}
   else{
     list.innerHTML=rows.map(p=>{
       const severity=p.availability==="Out"?"out":
         ["Questionable","Doubtful","Day-to-day","Sprzeczne"].includes(p.availability)?"uncertain":"probable";
       const mins=safeProjection(p.minutes);
       const label=mins!==null&&mins>0?" · szacunek "+fmt(mins)+" min":"";
       return '<div class="hzm-availability-row"><span class="hzm-availability-name">'+
         esc(String(p.name||""))+'</span><span class="hzm-availability-status '+severity+'">'+
         esc(p.availability)+ '</span><small>'+esc(label)+'</small></div>';
     }).join("");
   }
   const val=Number(factors["injury_"+side+"_pts"]);
   const applied=Number(factors["injury_out_"+side]);
   $("hzm-availability-"+side+"-impact").textContent=
     Number.isFinite(val)&&val>=-3.5&&val<=0&&Number.isInteger(applied)&&applied>=0
      ?"Korekta V7.5: "+fmt(val)+" pkt · uwzględnione w modelu OUT: "+applied
      :"Korekta modelu V7.5: brak wiarygodnych danych.";
 }
}

function showMatchIntelligence(game,sim,premium){
 const ids=["completed","source","advanced",
   "away-sample","away-venue-sample","away-rest","away-sd-sample",
   "home-sample","home-venue-sample","home-rest","home-sd-sample",
   "venue-away","venue-home","rest-away","rest-home",
   "injury-away","injury-home","total-away","total-home"];
 for(const id of ids){const el=$("hzm-intel-"+id);if(el)el.textContent="—";}
 const status=$("hzm-intel-status"),caveat=$("hzm-intel-caveat"),model=$("hzm-intel-model");
 if(!status||!caveat||!model)return;
 model.textContent=modelLabel();
 for(const side of ["away","home"]){
   const code=game?.[side]||(side==="away"?"GOŚCIE":"GOSPODARZE");
   $("hzm-intel-"+side+"-name").textContent=code;
   $("hzm-intel-factor-"+side).textContent=code;
 }
 caveat.textContent="Nieskalibrowany model eksperymentalny. Korekty nie stanowią prognozy dostępności składu, gwarancji zwycięstwa ani linii bukmachera.";
 if(premium?.entitled!==true){
   status.textContent="Dane modelu dostępne tylko w Premium.";return;
 }
 if(!game){status.textContent="Wybierz mecz NBA.";return;}
 if(!sim){status.textContent="Pobieranie modelu i jego udokumentowanych czynników…";return;}
 if(sim.error){status.textContent=String(sim.error).slice(0,180);return;}
 const ctx=sim.model_context;
 if(!ctx||typeof ctx!=="object"){
   status.textContent="Wybrany model nie dostarczył danych do wyjaśnienia prognozy.";return;
 }
 const count=n=>Number.isInteger(n)&&n>=0?String(n):"—";
 const value=n=>n!==null&&n!==undefined&&Number.isFinite(Number(n))?Number(n):null;
 const rest=n=>value(n)!==null&&Number(n)>=0?fmt(n)+" dni":"Brak danych";
 const corrected=n=>value(n)===null?"—":(Number(n)>0?"+":"")+fmt(n)+" pkt";
 $("hzm-intel-completed").textContent=count(ctx.completed_games);
 $("hzm-intel-source").textContent=typeof ctx.source==="string"?ctx.source.slice(0,50):"—";
 $("hzm-intel-advanced").textContent=ctx.advanced_available===true?"Dostępne":ctx.advanced_available===false?"Brak danych":"—";
 for(const [side,i] of [["away",0],["home",1]]){
   $("hzm-intel-"+side+"-sample").textContent=count(ctx[side+"_sample"]);
   $("hzm-intel-"+side+"-venue-sample").textContent=count(ctx.venue_samples?.[i]);
   $("hzm-intel-"+side+"-rest").textContent=rest(ctx.rest_days?.[i]);
   $("hzm-intel-"+side+"-sd-sample").textContent=count(ctx.score_sd_samples?.[i]);
 }
 const factor=ctx.v75_factors;
 if(state.model==="research_context_v75"&&factor&&typeof factor==="object"){
   for(const side of ["away","home"]){
     const venue=value(factor["venue_"+side+"_pts"]);
     const restPts=value(factor["rest_"+side+"_pts"]);
     const injury=value(factor["injury_"+side+"_pts"]);
     $("hzm-intel-venue-"+side).textContent=corrected(venue);
     $("hzm-intel-rest-"+side).textContent=corrected(restPts);
     $("hzm-intel-injury-"+side).textContent=corrected(injury);
     if([venue,restPts,injury].every(v=>v!==null))
       $("hzm-intel-total-"+side).textContent=corrected(venue+restPts+injury);
   }
   const report=factor.injuries_espn_fresh===true?
     "W modelu uwzględniono raport ESPN oceniony jako świeży w chwili obliczenia.":"Brak świeżego raportu ESPN w chwili obliczenia.";
   const warnings=Array.isArray(ctx.warnings)?ctx.warnings.filter(x=>typeof x==="string").slice(0,2):[];
   status.textContent="V7.5: rozbicie dodatków do średniej V7.4 · "+report;
   caveat.textContent="Korekty V7.5 są eksperymentalne, niekalibrowane; "+report+
      " Status raportu może później wygasnąć. "+warnings.join(" · ").slice(0,200);
 }else{
   status.textContent=state.model==="legacy_v72"?
     "V7.2: bazowa metoda punktowa. Kontekst historyczny jest informacyjny; brak rozbicia korekt V7.5.":
     "V7.4: historyczna forma i kontekst. Korekty dom/wyjazd, odpoczynku i ESPN OUT są liczone dopiero w V7.5.";
 }
}

function showTeamComparison(game,sim,premium){
 const status=$("hzm-compare-status"),disclaimer=$("hzm-compare-disclaimer");
 if(!status||!disclaimer)return;
 const n=state.comparisonWindow===5?5:10;
 const fields=["pts","allowed","margin","win-pct","venue-scored","venue-allowed","pace","off-rating","def-rating"];
 const count=v=>Number.isInteger(v)&&v>=0&&v<=200?String(v):"—";
 const mean=v=>v!==null&&v!==undefined&&v!==""&&Number.isFinite(Number(v))?fmt(v):"—";
 const signed=v=>v!==null&&v!==undefined&&v!==""&&Number.isFinite(Number(v))
    ?(Number(v)>0?"+":"")+fmt(v):"—";
 const pct=v=>v!==null&&v!==undefined&&v!==""&&Number.isFinite(Number(v))&&Number(v)>=0&&Number(v)<=100
    ?fmt(v)+"%":"—";
 for(const side of ["away","home"]){
   $("hzm-compare-"+side+"-name").textContent=game?.[side]||(side==="away"?"GOŚCIE":"GOSPODARZE");
   $("hzm-compare-table-"+side).textContent=game?.[side]||"—";
   $("hzm-compare-"+side+"-record").textContent="— W / — L";
   $("hzm-compare-"+side+"-observed").textContent="Próba: —";
   for(const field of fields)$("hzm-compare-"+side+"-"+field).textContent="—";
 }
 for(const k of ["pts","allowed","margin","win"])
   $("hzm-compare-"+k+"-window").textContent="L"+n;
 for(const button of document.querySelectorAll("[data-hzm-comparison-window]")){
   const active=Number(button.dataset.hzmComparisonWindow)===n;
   button.classList.toggle("selected",active);
   button.setAttribute("aria-pressed",String(active));
 }
 status.textContent="Wybierz spotkanie i model.";
 disclaimer.textContent="Statystyki historyczne nie są prognozą ani rekomendacją bukmacherską.";
 if(premium?.entitled!==true){
   status.textContent="Team Comparison wymaga aktywnego Premium.";return;
 }
 if(!game)return;
 if(!sim){status.textContent="Pobieranie zweryfikowanych danych ESPN i NBA Advanced…";return;}
 if(sim.error){status.textContent=String(sim.error).slice(0,170);return;}
 const data=sim.model_context?.team_comparison;
 if(!data||data.away?.team!==game.away||data.home?.team!==game.home){
   status.textContent="Brak kompletnych danych drużyn dla wybranego meczu.";return;
 }
 for(const side of ["away","home"]){
   const t=data[side];
   $("hzm-compare-"+side+"-observed").textContent="Zaobserwowane: "+count(t["n"+n])+" / "+n+" meczów";
   $("hzm-compare-"+side+"-record").textContent=count(t["wins"+n])+" W / "+count(t["losses"+n])+" L";
   $("hzm-compare-"+side+"-pts").textContent=mean(t["pts"+n]);
   $("hzm-compare-"+side+"-allowed").textContent=mean(t["allowed"+n]);
   $("hzm-compare-"+side+"-margin").textContent=signed(t["margin"+n]);
   $("hzm-compare-"+side+"-win-pct").textContent=pct(t["win_pct"+n]);
   const venueEnough=Number.isInteger(t.venue_sample)&&t.venue_sample>0;
   $("hzm-compare-"+side+"-venue-scored").textContent=venueEnough?mean(t.venue_scored):"—";
   $("hzm-compare-"+side+"-venue-allowed").textContent=venueEnough?mean(t.venue_allowed):"—";
   for(const [key,val] of [
      ["pace",t.pace],["off-rating",t.off_rating],["def-rating",t.def_rating]])
      $("hzm-compare-"+side+"-"+key).textContent=data.advanced_available===true?mean(val):"—";
 }
 status.textContent="Forma L"+n+": "+game.away+" "+count(data.away["n"+n])+
    " meczów · "+game.home+" "+count(data.home["n"+n])+
    " meczów; wyłącznie zakończone spotkania sprzed rozpoczęcia wybranego meczu.";
 disclaimer.textContent="ESPN: historyczne punkty, forma i W/L (maks. 20 meczów), także split wyjazd/u siebie. "+
   (data.advanced_available===true?
    "Tempo PACE, OFFRTG i DEFRTG wyłącznie z pełnych rzeczywistych danych NBA Advanced dla obu drużyn.":
    "Brak kompletnych NBA Advanced dla obu drużyn — PACE, OFFRTG, DEFRTG niedostępne.")+
   " Średnie punktów straconych to nie DEFRTG; żadna z tych statystyk nie gwarantuje wyniku.";
}

function showModelBacktest(premium){
 const status=$("hzm-backtest-status"),run=$("hzm-backtest-run"),note=$("hzm-backtest-caveat");
 if(!status||!run||!note)return;
 const paid=premium?.entitled===true;
 const report=paid?premium.backtest:null;
 for(const key of ["old","new","enriched","v75"])
   for(const metric of ["total","team","accuracy","brier"])
     $("hzm-backtest-"+key+"-"+metric).textContent="—";
 for(const metric of ["games","season","range"])$("hzm-backtest-"+metric).textContent="—";
 note.textContent="Walk-forward (tylko zweryfikowane wcześniejsze mecze). Raport offline nie odtwarza dostępności NBA Advanced ani dawnych raportów kontuzji ESPN — nie przedstawia pełnej skuteczności produkcyjnego V7.5.";
 if(!paid){
   state.backtestPending=false;run.disabled=true;
   status.textContent="Model & Backtest jest dostępny wyłącznie w Premium.";
   return;
 }
 if(report)state.backtestPending=false;
 run.disabled=state.backtestPending;
 if(!report){
   status.textContent=state.backtestPending?"Analizowanie maks. 40 meczów walk-forward…":
     "Uruchom test historyczny. Dane nie są pobierane przy otwieraniu aplikacji.";
   return;
 }
 if(report.error){
   status.textContent=String(report.error).slice(0,180);return;
 }
 if(!/^\d{4}-\d{2}$/.test(String(report.season||""))||
    !Number.isInteger(report.games)||report.games<1||report.games>40||
    !Array.isArray(report.models)){
   status.textContent="Niekompletny raport walidacyjny.";return;
 }
 $("hzm-backtest-season").textContent=report.season;
 $("hzm-backtest-games").textContent=String(report.games)+" / "+String(report.max_games||40);
 if(/^\d{4}-\d{2}-\d{2}$/.test(String(report.first_game||""))&&
    /^\d{4}-\d{2}-\d{2}$/.test(String(report.last_game||"")))
    $("hzm-backtest-range").textContent=report.first_game+" – "+report.last_game;
 const keys=new Set(["old","new","enriched","v75"]);
 let shown=0;
 for(const row of report.models){
   if(!row||!keys.has(row.key))continue;
   const n=v=>v!==null&&v!==undefined&&v!==""&&Number.isFinite(Number(v))?Number(v):null;
   const total=n(row.total_mae),team=n(row.team_mae),acc=n(row.winner_accuracy_pct),brier=n(row.brier);
   if([total,team,acc,brier].some(v=>v===null)||total<0||team<0||
      acc<0||acc>100||brier<0||brier>1)continue;
   $("hzm-backtest-"+row.key+"-total").textContent=fmt(total);
   $("hzm-backtest-"+row.key+"-team").textContent=fmt(team);
   $("hzm-backtest-"+row.key+"-accuracy").textContent=fmt(acc)+"%";
   $("hzm-backtest-"+row.key+"-brier").textContent=brier.toFixed(4).replace(".",",");
   shown++;
 }
 if(shown!==4){
   status.textContent="Wyniki nie wszystkich metod są dostępne; brakujące metryki pozostają puste.";
 }else{
   const stamped=Date.parse(String(report.as_of_utc||""));
   const when=Number.isFinite(stamped)?new Date(stamped).toISOString().slice(0,16).replace("T"," ")+" UTC":"brak godziny";
   status.textContent="Walk-forward gotowy: "+report.games+" ukończonych spotkań. Opracowano: "+when+
      ". Próbka ograniczona do maks. 40 ostatnich ocenionych meczów.";
 }
 if(typeof report.limitation==="string")note.textContent=report.limitation.slice(0,320)+
   " Bez kursów historycznych ROI pozostaje niedostępne.";
}
function render(home,premium){
  state.lastHome=home;state.lastPremium=premium;
  syncModelDropdown();
  syncLabView();
  // Streamlit may deliver its first payload after the user opens the tab.
  // A fallback day initialized before that packet must not prevent restoring
  // the server-confirmed day, even if state.day is already nonempty.
  // Local clicks win over stale/out-of-order server packets until acknowledged.
  const serverDay=home?.calendar_requested_day;
  if(withinRange(serverDay)&&(!state.localDayIntent||serverDay===state.day)){
    if(serverDay!==state.day){
      state.day=serverDay;
      state.gameId="";state.gamePending="";state.playersPending="";
      state.playerIndex=-1;state.fromProps=null;
      state.requestedDay="";
    }
    state.localDayIntent=false;
  }
  if(!state.day)
    state.day=withinRange(home?.calendar_today)?home.calendar_today:localDay(new Date().toISOString());
  const data=gamesForDay(home);
  // Persist all user choices, including dates already cached in calendar_extras.
  // Otherwise a later Streamlit remount silently restores an older date.
  if(home&&state.requestedDay!==state.day&&
     ((state.localDayIntent&&serverDay!==state.day)||!data.known)){
    state.requestedDay=state.day;
    callbacks?.selectDay?.(state.day);
  }
  if(withinRange(serverDay)&&serverDay===state.day){
    state.requestedDay="";state.localDayIntent=false;
  }
  if(!data.games.some(game=>game.id===state.gameId)){
    const next=data.games.find(game=>game.state==="scheduled")||data.games[0];
    state.gameId=next?.id||"";state.gamePending="";state.playersPending="";state.expanded=state.view==="players";state.playerIndex=-1;state.fromProps=null;state.scenarioPct=0;state.offAwayPct=0;state.offHomePct=0;state.scenarioPending="";state.minuteIndex=-1;state.minuteDelta=0;state.minutePending="";
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
  if(state.view==="results"||premium?.entitled!==true)showResultsDashboard(game,sim,premium);
  // Heavy charts, player lists and scenario cards are only rebuilt while
  // visible. On entitlement revocation update everything so hidden Premium
  // panes cannot retain a paid result in the in-memory DOM.
  const revoking=premium?.entitled!==true;
  if(revoking||state.view==="results"||
     (state.view==="players"&&!window.HoopzaroPlayerV3)){
    // Legacy Results view stays intact; the Node mock harness intentionally
    // runs without the browser-only Player V3 module.
    showChart(sim,game,premium);showPlayers(premium,players,game);
  }
  if(state.view==="players"){
    window.HoopzaroPlayerV3?.render({
      game,sim,players,premium,model:state.model,state,
      onReturn:()=>callbacks?.backToProps?.(),
      onHistory:(item,market)=>{
        if(!premium?.entitled||!game||!players||!item)return;
        if(players.players?.[state.playerIndex]!==item)return;
        bridgeToHistory(market);
      }
    });
  }else if(revoking){
    window.HoopzaroPlayerV3?.clear();
  }
  if(revoking||state.view==="scenario"){
    showScenario(game,sim,premium);showPlayerMinutes(game,players,premium);
    showAvailability(game,players,sim,premium);
  }
  if(revoking||state.view==="intelligence")showMatchIntelligence(game,sim,premium);
  if(revoking||state.view==="comparison")showTeamComparison(game,sim,premium);
  if(revoking||state.view==="backtest")showModelBacktest(premium);
  maybeLoadPaid(game,premium,sim,players);
}
function navigate(day){
  if(!safeDate(day)||!withinRange(day)||state.day===day)return;
  state.day=day;state.localDayIntent=true;state.gameId="";state.chart="match";state.fromProps=null;state.scenarioPct=0;state.offAwayPct=0;state.offHomePct=0;state.scenarioPending="";state.minuteIndex=-1;state.minuteDelta=0;state.minutePending="";state.expanded=state.view==="players";state.gamePending="";state.playersPending="";state.playerIndex=-1;state.playerQuery="";state.playerTeam="all";
  render(state.lastHome,state.lastPremium);
}
function init(api){
  callbacks=api;
  // Keep the verified ESPN photo optional: network and CDN errors should
  // reveal the local initials fallback, not a broken-image icon.
  $("simulations-pane")?.addEventListener("error",event=>{
    if(event.target?.matches?.(".hzm-player-avatar img"))
      event.target.remove();
  },true);
  // Bind calendar navigation directly to persistent controls. Delegating
  // through the scrolling premium canvas can miss clicks near its top edge.
  // stopPropagation avoids a second date shift from older delegated routes.
  for(const [id,amount] of [["hzm-day-prev",-1],["hzm-day-next",1]]){
    $(id)?.addEventListener("click",event=>{
      event.preventDefault();event.stopPropagation();
      navigate(dayShift(state.day,amount));
    });
  }
  $("hzm-day-title")?.addEventListener("click",event=>{
    const picker=$("hzm-day-input");
    if(!picker)return;
    // Open the native calendar when allowed by the browser/iframe.
    // A blocked showPicker does not prevent keyboard entry or date changes.
    try{picker.showPicker?.()}catch(error){picker.focus();}
  });
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
  for(const [id,stateKey] of [["hzm-mini-pace","scenarioPct"],["hzm-mini-off-away","offAwayPct"],["hzm-mini-off-home","offHomePct"]]){
    $(id)?.addEventListener("input",event=>{
      const value=Number(event.target.value);
      if(!Number.isInteger(value)||value< -5||value>5)return;
      state[stateKey]=value;state.scenarioPending="";
      const out=$(id+"-output");if(out)out.textContent=(value>0?"+":"")+value+"%";
    });
  }
  $("hzm-scenario-pace")?.addEventListener("input",event=>{
    const value=Number(event.target.value);
    if(!Number.isInteger(value)||value< -5||value>5)return;
    state.scenarioPct=value;state.scenarioPending="";
    showScenario(gamesForDay(state.lastHome).games.find(g=>g.id===state.gameId),
      trustedResult(state.lastPremium,gamesForDay(state.lastHome).games.find(g=>g.id===state.gameId)),state.lastPremium);
  });
  for(const side of ["away","home"]){
    $("hzm-scenario-off-"+side)?.addEventListener("input",event=>{
      const value=Number(event.target.value);
      if(!Number.isInteger(value)||value < -5||value>5)return;
      if(side==="away")state.offAwayPct=value;else state.offHomePct=value;
      state.scenarioPending="";
      const game=gamesForDay(state.lastHome).games.find(g=>g.id===state.gameId);
      showScenario(game,trustedResult(state.lastPremium,game),state.lastPremium);
    });
  }
  $("hzm-scenario-run")?.addEventListener("click",()=>{
    const game=gamesForDay(state.lastHome).games.find(g=>g.id===state.gameId);
    const sim=trustedResult(state.lastPremium,game);
    if(!state.lastPremium?.entitled||!sim||sim.error||game?.state!=="scheduled"||
       !(Date.parse(game.start||"")>Date.now()))return;
    const key=state.day+"|"+game.id+"|"+state.model+"|"+state.scenarioPct+"|"+state.offAwayPct+"|"+state.offHomePct;
    state.scenarioPending=key;
    callbacks?.loadScenario?.(state.day,game.id,state.model,state.scenarioPct,state.offAwayPct,state.offHomePct);
    showScenario(game,sim,state.lastPremium);
  });
  $("hzm-minute-player")?.addEventListener("change",event=>{
    const next=Number(event.target.value);
    if(!Number.isInteger(next)||next<0)return;
    state.minuteIndex=next;state.minuteDelta=0;state.minutePending="";
    const game=gamesForDay(state.lastHome).games.find(g=>g.id===state.gameId);
    showPlayerMinutes(game,trustedPlayers(state.lastPremium,game),state.lastPremium);
  });
  $("hzm-minute-delta")?.addEventListener("input",event=>{
    const v=Number(event.target.value);
    if(!Number.isInteger(v)||v< -5||v>5)return;
    state.minuteDelta=v;state.minutePending="";
    const game=gamesForDay(state.lastHome).games.find(g=>g.id===state.gameId);
    showPlayerMinutes(game,trustedPlayers(state.lastPremium,game),state.lastPremium);
  });
  $("hzm-minute-run")?.addEventListener("click",()=>{
    const game=gamesForDay(state.lastHome).games.find(g=>g.id===state.gameId);
    const players=trustedPlayers(state.lastPremium,game);
    const player=players?.players?.[state.minuteIndex];
    if(!state.lastPremium?.entitled||state.model!=="research_context_v75"||
       game?.state!=="scheduled"||!(Date.parse(game.start||"")>Date.now())||
       !player||player.availability==="Out"||
       ![game.away,game.home].includes(player.team)||
       !Number.isInteger(Number(player.minutes_sample))||Number(player.minutes_sample)<3||
       safeProjection(player.minutes)===null||Number(player.minutes)+state.minuteDelta<5||
       Number(player.minutes)+state.minuteDelta>44||
       ["pts","reb","ast"].some(k=>safeProjection(player[k])===null))return;
    state.minutePending=state.day+"|"+game.id+"|"+state.model+"|"+
      player.team+"|"+player.name+"|"+state.minuteDelta;
    callbacks?.loadMinuteScenario?.({
      day:state.day,gameId:String(game.id),modelId:state.model,
      playerName:String(player.name),team:String(player.team),minuteDelta:state.minuteDelta
    });
    showPlayerMinutes(game,players,state.lastPremium);
  });
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
    state.gameId=selected.dataset.hzmGame;state.gamePending="";state.playersPending="";state.chart="match";state.playerIndex=-1;state.fromProps=null;state.scenarioPct=0;state.offAwayPct=0;state.offHomePct=0;state.scenarioPending="";state.minuteIndex=-1;state.minuteDelta=0;state.minutePending="";
    state.expanded=state.view==="players";state.resultTeam="all";
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
    const resultTeam=event.target.closest("[data-hzm-result-team]");
    if(resultTeam&&["all","away","home"].includes(resultTeam.dataset.hzmResultTeam)){
      state.resultTeam=resultTeam.dataset.hzmResultTeam;
      const game=gamesForDay(state.lastHome).games.find(g=>g.id===state.gameId);
      showPlayers(state.lastPremium,trustedPlayers(state.lastPremium,game),game);return;
    }
    if(event.target.closest("#hzm-mini-run")){
      if($("hzm-mini-run").disabled)return;
      chooseView("scenario");
      $("hzm-scenario-run")?.click();return;
    }
    if(event.target.closest("#hzm-mini-minutes")){
      chooseView("scenario");
      $("hzm-minute-player")?.focus();return;
    }
    if(event.target.closest("#hzm-mini-backtest")){
      chooseView("backtest");
      if(state.lastPremium?.entitled)$("hzm-backtest-run")?.click();
      return;
    }
    if(event.target.closest("#hzm-backtest-run")){
      if(state.lastPremium?.entitled===true&&!state.backtestPending){
        state.backtestPending=true;
        showModelBacktest(state.lastPremium);
        callbacks?.loadBacktest?.();
      }
      return;
    }
    const marketButton=event.target.closest("[data-hzm-player-market]");
    if(marketButton){
      const next=marketButton.dataset.hzmPlayerMarket;
      if(state.view==="players"&&["PTS","REB","AST","PRA"].includes(next)){
        state.playerMarket=next;
        render(state.lastHome,state.lastPremium);
      }
      return;
    }
    const historyButton=event.target.closest("[data-hzm-history-window]");
    if(historyButton){
      const raw=historyButton.dataset.hzmHistoryWindow;
      const next=raw==="season"?"season":Number(raw);
      if(state.view==="players"&&(next==="season"||[5,10,15].includes(next))){
        state.playerHistoryWindow=next;
        const game=gamesForDay(state.lastHome).games.find(g=>g.id===state.gameId);
        const pack=trustedPlayers(state.lastPremium,game);
        const item=pack?.players?.[state.playerIndex];
        showPlayerAnalytics(item);
      }
      return;
    }
        const comparison=event.target.closest("[data-hzm-comparison-window]");
    if(comparison){
      const n=Number(comparison.dataset.hzmComparisonWindow);
      if(n===5||n===10){
        state.comparisonWindow=n;
        const game=gamesForDay(state.lastHome).games.find(g=>g.id===state.gameId);
        showTeamComparison(game,trustedResult(state.lastPremium,game),state.lastPremium);
      }
      return;
    }
    if(event.target.closest("#hzm-match-picker")){toggleMatchPicker();return}
    const viewButton=event.target.closest("[data-hzm-view]");
    if(viewButton){chooseView(viewButton.dataset.hzmView);return}
    if(event.target.closest("#hzm-model-trigger")){
      toggleModelDropdown($("hzm-model-options").hidden);return;
    }
    const modelOption=event.target.closest("[data-hzm-model]");
    if(modelOption){toggleModelDropdown(false,true);chooseModel(modelOption.dataset.hzmModel);return}
    // The date buttons are wired directly above rather than delegated.
    const gameButton=event.target.closest("[data-hzm-game]");
    if(gameButton){
      state.gameId=gameButton.dataset.hzmGame;state.gamePending="";state.playersPending="";state.chart="match";state.playerIndex=-1;state.fromProps=null;state.scenarioPct=0;state.offAwayPct=0;state.offHomePct=0;state.scenarioPending="";
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
  $("hzm-day-input").addEventListener("change",event=>{
    const chosen=event.target.value;
    if(withinRange(chosen))navigate(chosen);
    else event.target.value=state.day; // reject invalid or out-of-range dates
  });
}
window.HoopzaroSimulations={init,render,openFromProps,clearBridge};
})();
