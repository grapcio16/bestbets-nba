/* HOOPZARO Player Simulations v3 — standalone, model-safe Premium view.
 * A clean implementation with no dependency on legacy .hzm-player-lab-body.
 * Only verified selected-fixture server data reaches this component.
 */
(function(){
"use strict";
const root=document.getElementById("hzv3");
if(!root)return;
const $=id=>document.getElementById(id);
const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const num=v=>v!==null&&v!==undefined&&v!==""&&Number.isFinite(Number(v))?Number(v):null;
const fmt=v=>num(v)===null?"—":Number(v).toLocaleString("pl-PL",{minimumFractionDigits:1,maximumFractionDigits:1});
const int=v=>v!==null&&v!==undefined&&v!==""&&Number.isInteger(Number(v))&&Number(v)>=0?Number(v):null;
const version=id=>id==="research_context_v75"?"V7.5":id==="research_form_v74"?"V7.4":"V7.2";
let active=null;

function metric(player,key){
 if(!player)return null;
 if(active?.model==="research_context_v75"&&player.availability==="Out")return null;
 const clean=v=>num(v)!==null&&num(v)>=0?num(v):null;
 const p=clean(player.pts),r=clean(player.reb),a=clean(player.ast);
 return key==="PTS"?p:key==="REB"?r:key==="AST"?a:
   key==="PRA"&&[p,r,a].every(v=>v!==null)?p+r+a:null;
}
function history(player,key){
 if(!Array.isArray(player?.history))return [];
 const k=key.toLowerCase();
 return player.history.filter(row=>row&&/^\d{4}-\d{2}-\d{2}$/.test(String(row.date||""))&&
   num(row[k])!==null&&num(row[k])>=0)
   .slice(-15).map(row=>({date:row.date,value:Number(row[k])}));
}
function mean(rows,n){
 if(rows.length<n)return null;
 return rows.slice(-n).reduce((a,b)=>a+b.value,0)/n;
}
function teamOf(player){return String(player?.team||"").trim().toUpperCase();}
function initials(name){
 return String(name||"").trim().split(/\s+/).slice(0,2).map(v=>v.charAt(0)).join("").toUpperCase();
}
// Preserve a readable surname instead of trimming both the name AND the
// team abbreviation to a handful of characters in the 390px roster card.
// The complete identity remains in the row title and aria-label.
function rosterName(name){
 const parts=String(name||"").trim().split(/\s+/);
 if(parts.length<2)return parts[0]||"";
 return parts[0].slice(0,1)+". "+parts.slice(1).join(" ");
}
// Reuse the verified team badge already delivered for the selected fixture
// (the same image displayed in the match hero). No external logo request and
// no hardcoded roster-to-team mapping. Require an actual player/game match.
function playerTeamLogo(player){
 const team=teamOf(player),game=active?.game;
 if(!game||![String(game.away||"").toUpperCase(),String(game.home||"").toUpperCase()].includes(team))return "";
 const token=team===String(game.home||"").toUpperCase()?game.home_logo:game.away_logo;
 const resolved=window.hzResolveTeamLogo?.(token||"team-logo:"+team)||"";
 return typeof resolved==="string"&&/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(resolved)?resolved:"";
}
function portrait(player,large){
 // Use original neon initials and the fixture's authorized badge only.
 // Do not hotlink third-party player headshots without image rights.
 const caption=esc(initials(player?.name));
 const logo=large?playerTeamLogo(player):"";
 const team=esc(teamOf(player));
 const mark=large?'<span class="hzv3-team-watermark'+(logo?' has-logo':'')+'" aria-hidden="true">'+
   '<span class="hzv3-team-watermark-label">'+team+'</span>'+
   (logo?'<img alt="" src="'+logo+'" loading="lazy">':"")+'</span>':"";
 return '<span class="'+(large?"hzv3-athlete-photo":"hzv3-face")+'" aria-hidden="true">'+
  mark+'<span class="hzv3-avatar-fallback">'+caption+'</span></span>';
}
function fullList(){
 const {players,game,state,premium}=active;
 if(premium?.entitled!==true||!game||!Array.isArray(players?.players))return [];
 const teams=[String(game.away||"").toUpperCase(),String(game.home||"").toUpperCase()];
 const entries=players.players.map((player,index)=>({player,index})).filter(
   ({player})=>player&&teams.includes(teamOf(player))&&String(player.name||"").trim());
 const team=state.playerTeam==="away"?teams[0]:state.playerTeam==="home"?teams[1]:"";
 const query=String(state.playerQuery||"").trim().toLocaleLowerCase("pl");
 return entries.filter(({player})=>(!team||teamOf(player)===team)&&
   (!query||String(player.name||"").toLocaleLowerCase("pl").includes(query)))
   .sort((a,b)=>(metric(b.player,state.playerMarket)??-1)-(metric(a.player,state.playerMarket)??-1));
}
function selected(entries){
 const s=active.state;
 if(!entries.length){s.playerIndex=-1;return null;}
 if(!entries.some(e=>e.index===s.playerIndex))s.playerIndex=entries[0].index;
 return entries.find(e=>e.index===s.playerIndex)?.player||null;
}
function showList(entries){
 const {state}=active,roster=$("hzv3-roster");
 const scroll=roster.scrollTop;
 if(!entries.length){
   roster.innerHTML='<div class="hzv3-muted">Brak zawodników pasujących do filtra lub zweryfikowanej próbki.</div>';return;
 }
 roster.innerHTML=entries.map(({player,index})=>{
  const team=teamOf(player);
  const vals=["PTS","REB","AST","PRA"].map(m=>
   '<span class="hzv3-player-stat" title="'+m+': '+esc(fmt(metric(player,m)))+'">'+fmt(metric(player,m))+'</span>').join("");
  const selected=index===state.playerIndex;
  return '<button class="hzv3-player" type="button" data-hzv3-pick="'+index+'" aria-pressed="'+selected+
    '" aria-label="'+esc(player.name)+' · '+esc(team)+'" title="'+esc(player.name)+' · '+esc(team)+'">'+portrait(player,false)+
    '<span class="hzv3-player-name"><strong>'+esc(rosterName(player.name))+'</strong><small>'+esc(team)+'</small></span>'+
    vals+'</button>';
 }).join("");
 roster.scrollTop=scroll;
}
function status(player){
 const v=String(player?.availability||"").trim();
 const model=active.model;
 if(model!=="research_context_v75")return {text:"Dostępność: nieoceniana w "+version(model),kind:"neutral",icon:"ⓘ"};
 if(v==="Out")return {text:"ESPN: OUT — prognoza nieaktywna",kind:"negative",icon:"×"};
 if(v==="Probable")return {text:"ESPN: prawdopodobny występ (Probable)",kind:"positive",icon:"✓"};
 if(["Questionable","Doubtful","Day-to-day","Sprzeczne"].includes(v))
  return {text:"ESPN: "+v+" — występ niepewny",kind:"neutral",icon:"!"};
 return {text:"Status ESPN: "+(v||"brak potwierdzenia"),kind:"neutral",icon:"ⓘ"};
}
function drawInspector(player){
 const pane=$("hzv3-inspector"),{model,state,players}=active;
 if(!player){pane.innerHTML='<div class="hzv3-muted">Wybierz zawodnika, aby zobaczyć projekcje i historię ESPN.</div>';return;}
 const badge=status(player),rows=history(player,state.playerMarket),avg=mean(rows,5);
 const minuteRows=history(player,"MIN");
 const verifiedMinutes=mean(minuteRows,5);
 const position=["PG","SG","SF","PF","C","G","F"].includes(player.position)?player.position:"";
 const minutes=model==="research_context_v75"?num(player.minutes):null;
 const projectedMinutes=minutes!==null&&player.availability!=="Out";
 // V7.2/V7.4 have NO predicted minutes; display actual ESPN L5 minutes,
 // clearly labeled as history, rather than a misleading empty projection.
 const minutesLabel=projectedMinutes?fmt(minutes)+" min":
   verifiedMinutes!==null?fmt(verifiedMinutes)+" min":"—";
 const minutesType=projectedMinutes?"Minuty (proj.)":"Minuty (ESPN L5)";
 const minutesSample=projectedMinutes
   ?int(player.minutes_sample)
   :minuteRows.length;
 const metrics=["PTS","REB","AST","PRA"].map(k=>
   '<div class="hzv3-metric" data-hzv3-metric="'+k+'" data-active="'+(k===state.playerMarket)+'">'+
   '<small>'+k+'</small><strong>'+fmt(metric(player,k))+'</strong></div>').join("");
 const actions=["PTS","REB","AST","PRA"].map(k=>
   '<button type="button" data-hzv3-props="'+k+'"'+(metric(player,k)===null?' disabled':'')+
   '>Historia '+k+' ›</button>').join("");
 pane.innerHTML='<div class="hzv3-athlete-top">'+portrait(player,true)+
   '<div class="hzv3-athlete-info"><span class="hzv3-forecast-label">PLAYER FORECAST · '+version(model)+'</span>'+
   '<span class="hzv3-athlete-team">'+esc(teamOf(player))+(position?' · '+position:'')+'</span>'+
   '<h3 class="hzv3-athlete-name">'+esc(player.name)+'</h3></div></div>'+
   '<div class="hzv3-metrics">'+metrics+'</div>'+
   '<div class="hzv3-status" data-kind="'+badge.kind+'"><span class="hzv3-status-dot">'+badge.icon+'</span>'+
   '<span>'+esc(badge.text)+'</span></div>'+
   '<div class="hzv3-facts">'+
   '<div class="hzv3-fact" title="'+esc(projectedMinutes?"Minuty prognozowane przez "+version(model)+", próba: "+(minutesSample??"brak"):"Średnie rzeczywiste minuty z ostatnich 5 potwierdzonych meczów ESPN, nie prognoza")+'"><span>◷</span><span>'+minutesType+'</span><strong>'+minutesLabel+'</strong></div>'+
   '<div class="hzv3-fact"><span>⌁</span><span>Forma L5 ('+state.playerMarket+')</span><strong>'+fmt(avg)+'</strong></div>'+
   '<div class="hzv3-fact"><span>▥</span><span>Próba ESPN</span><strong>'+rows.length+' występów</strong></div>'+
   '<div class="hzv3-fact"><span>ⓘ</span><span>Model</span><strong>'+version(model)+'</strong></div></div>'+
   '<p class="hzv3-inspector-note">PRA = średnie PTS + REB + AST. Wykresy i over to wyłącznie wcześniejsze mecze ESPN.</p>'+
   '<div class="hzv3-history-actions">'+actions+'</div>'+
   (state.fromProps?.name===player.name&&state.fromProps?.team===teamOf(player)?
      '<button type="button" class="hzv3-return-props" data-hzv3-return>← Wróć do Player Props</button>':'');
}
function empty(label){
 return '<p class="hzv3-muted">'+esc(label)+'</p>';
}
/* Empirical Gaussian kernel density, normalized over displayed bins.
   This smoothing is descriptive and explicitly NOT a player-model PDF. */
function histogram(player,m){
 const rows=history(player,m),projected=metric(player,m),plot=$("hzv3-hist");
 if(rows.length<3){plot.innerHTML=empty("Wykres wymaga minimum 3 potwierdzonych występów.");return;}
 const values=rows.map(x=>x.value);
 const n=values.length,average=values.reduce((a,b)=>a+b,0)/n;
 const sd=Math.sqrt(values.reduce((a,b)=>a+(b-average)**2,0)/Math.max(1,n-1));
 const bw=Math.max(1.25,1.06*Math.max(sd,1)*Math.pow(n,-.2));
 const min=Math.max(0,Math.floor(Math.min(...values,projected??Infinity)-2*bw));
 const max=Math.max(min+8,Math.ceil(Math.max(...values,projected??0)+2*bw));
 const bins=24,dx=(max-min)/bins;
 const densities=Array.from({length:bins},(_,i)=>{
   const x=min+(i+.5)*dx;
   return values.reduce((acc,v)=>acc+Math.exp(-.5*((x-v)/bw)**2),0);
 });
 const sum=densities.reduce((a,b)=>a+b,0);
 const probs=densities.map(d=>100*d/sum);
 const w=555,h=190,x0=40,x1=543,y0=20,y1=158;
 const ceiling=Math.max(12,Math.ceil(Math.max(...probs)/4)*4);
 const x=v=>x0+(v-min)/(max-min)*(x1-x0);
 const y=p=>y1-p/ceiling*(y1-y0);
 const ticks=Array.from({length:5},(_,i)=>{
   const value=i*ceiling/4;
   return '<line x1="'+x0+'" y1="'+y(value).toFixed(1)+'" x2="'+x1+'" y2="'+y(value).toFixed(1)+
    '" stroke="#25466f" stroke-width="0.8"/><text x="'+(x0-8)+'" y="'+(y(value)+4).toFixed(1)+
    '" text-anchor="end" font-size="11" fill="#b2c8e1">'+value.toFixed(0)+'%</text>';
 }).join("");
 const bars=probs.map((v,i)=>{
   const bx=x0+i*(x1-x0)/bins+1, barw=(x1-x0)/bins-1.5;
   return '<rect x="'+bx.toFixed(1)+'" y="'+y(v).toFixed(1)+'" width="'+barw.toFixed(1)+
      '" height="'+Math.max(0,y1-y(v)).toFixed(1)+'" fill="'+(i<bins*.5?'url(#hzv3-cyan)':'url(#hzv3-purple)')+
      '" opacity="'+(.8+.2*v/ceiling).toFixed(2)+'"/>';
 }).join("");
 const xt=Array.from({length:7},(_,i)=>{
   const value=min+i*(max-min)/6;
   return '<text x="'+x(value).toFixed(1)+'" y="177" text-anchor="middle" font-size="10.5" fill="#b9cbe3">'+Math.round(value)+'</text>';
 }).join("");
 let marker="";
 if(projected!==null){
   const mx=Math.max(x0,Math.min(x1,x(projected)));
   marker='<line x1="'+mx+'" y1="20" x2="'+mx+'" y2="'+y1+
    '" stroke="#f7e5ff" stroke-dasharray="5 3" stroke-width="1.8"/>'+
    '<rect x="'+Math.max(x0,Math.min(x1-67,mx-33))+'" y="1" width="67" height="21" rx="4" fill="#9c29c9"/>'+
    '<text x="'+Math.max(x0+33,Math.min(x1-34,mx))+'" y="16" text-anchor="middle" font-size="11.5" font-weight="900" fill="#fff">Proj. '+fmt(projected)+'</text>';
 }
 plot.innerHTML='<svg viewBox="0 0 '+w+' '+h+'" role="img" aria-label="Wygładzony histogram historycznych '+m+
  ' z '+n+' meczów. Nie jest prognozą przyszłego rozkładu."><defs>'+
  '<linearGradient id="hzv3-cyan" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#25f8ff"/><stop offset="1" stop-color="#006bc3"/></linearGradient>'+
  '<linearGradient id="hzv3-purple" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#fa58f8"/><stop offset="1" stop-color="#6820ad"/></linearGradient></defs>'+
  ticks+bars+marker+xt+'</svg>';
}
function trendChart(player,m){
 const all=history(player,m);
 const win=active.state.playerHistoryWindow,needed=win==="season"?all.length:Number(win);
 const rows=all.slice(-Math.max(1,needed)),plot=$("hzv3-trend");
 if(rows.length<3){plot.innerHTML=empty("Brak minimum 3 potwierdzonych występów ESPN.");return;}
 const vals=rows.map(r=>r.value),lo=Math.max(0,Math.floor(Math.min(...vals)-3)),hi=Math.ceil(Math.max(...vals)+3);
 const x0=36,x1=535,y0=17,y1=150,h=175;
 const x=i=>x0+i/(rows.length-1)*(x1-x0),y=v=>y1-(v-lo)/(hi-lo)*(y1-y0);
 const xy=vals.map((v,i)=>[x(i),y(v)]);
 const line=xy.map(([xx,yy])=>xx.toFixed(1)+','+yy.toFixed(1)).join(' ');
 const area='M'+x0+','+y1+' L '+line.replace(/ /g,' L ')+' L '+x1+','+y1+' Z';
 const ticks=Array.from({length:5},(_,i)=>{
  const val=lo+(hi-lo)*i/4,yy=y(val);
  return '<line x1="'+x0+'" y1="'+yy+'" x2="'+x1+'" y2="'+yy+'" stroke="#2a4b71" opacity=".7"/>'+
  '<text x="'+(x0-9)+'" y="'+(yy+3)+'" text-anchor="end" font-size="11" fill="#aec7dc">'+Math.round(val)+'</text>';
 }).join("");
 const dots=xy.map(([xx,yy],i)=>{
  const textY=Math.max(13,yy-10),below=yy<35?yy+20:textY;
  return '<circle cx="'+xx+'" cy="'+yy+'" r="5.2" fill="#f7f6ff" stroke="#56eefd" stroke-width="1.1"/>'+
   '<text x="'+xx+'" y="'+below+'" text-anchor="middle" fill="#f1ecff" font-size="11" font-weight="850">'+fmt(vals[i])+'</text>';
 }).join("");
 plot.innerHTML='<svg viewBox="0 0 550 '+h+'" role="img" aria-label="Historyczna forma '+m+' z '+rows.length+' występów">'+
  '<defs><linearGradient id="hzv3-area" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#bb4bf5" stop-opacity=".48"/>'+
  '<stop offset="1" stop-color="#5716a0" stop-opacity=".04"/></linearGradient></defs>'+
  ticks+'<path d="'+area+'" fill="url(#hzv3-area)"/><polyline points="'+line+'" stroke="#1af1f4" stroke-width="1.8" fill="none"/>'+
  dots+'<text x="'+x1+'" y="169" text-anchor="end" fill="#89adcf" font-size="10">'+
  (win==="season"?"Dostępna próba":'L'+needed)+'</text></svg>';
}
function drawCharts(player){
 const m=active.state.playerMarket;
 const titles={PTS:"punkty",REB:"zbiórki",AST:"asysty",PRA:"PTS + REB + AST"};
 // Preserve the original accessible help buttons. Replacing headings
 // through innerHTML used to delete both click handlers and dialog semantics.
 function titleWithHelp(id,label){
   const h=$(id),button=h?.querySelector('button.hzm-help-trigger');
   if(!h)return;
   h.replaceChildren(document.createTextNode(label+' '));
   if(button)h.append(button);
 }
 titleWithHelp("hzv3-hist-title","Rozkład historyczny — "+titles[m]+" · "+(player?.name||"zawodnik"));
 $("hzv3-rates-title").textContent="Historyczne over ("+m+")";
 titleWithHelp("hzv3-trend-title","Forma historyczna — "+titles[m]);
 $("hzv3-averages-title").textContent="Średnie "+titles[m];
 root.querySelectorAll("[data-hzv3-window]").forEach(b=>b.setAttribute("aria-pressed",
   String(b.dataset.hzv3Window===String(active.state.playerHistoryWindow))));
 if(!player){
  ["hzv3-hist","hzv3-trend","hzv3-rates","hzv3-averages"].forEach(id=>$(id).innerHTML=empty("Wybierz zawodnika."));
  return;
 }
 const rows=history(player,m),model=metric(player,m);
 histogram(player,m);trendChart(player,m);
 $("hzv3-rates-note").textContent="ESPN · "+rows.length+" meczów · tylko historia";
 $("hzv3-rates-note").title="Odsetki osiągnięte w rzeczywistych wcześniejszych meczach dla progów wyznaczonych na podstawie projekcji. To nie są skalibrowane szanse na kolejny mecz ani linie bukmachera.";
 if(rows.length>=3&&model!==null){
  const values=[model-4.5,model+.5,model+4.5,model+9.5].map(v=>Math.max(.5,Math.round(v*2)/2));
  $("hzv3-rates").innerHTML=values.map(v=>
    '<div><span>&gt; '+fmt(v)+'</span><strong>'+fmt(100*rows.filter(r=>r.value>v).length/rows.length)+'%</strong></div>').join("");
 }else $("hzv3-rates").innerHTML=empty("Za mało danych historycznych.");
 const complete=player.season_team_mean&&typeof player.season_team_mean==="object";
 const seasonValue=complete?num(player.season_team_mean[m.toLowerCase()]):null;
 const seasonGames=int(player.season_team_games);
 $("hzv3-averages").innerHTML=[5,10,15].map(n=>
   '<div title="'+(rows.length<n?'Zarejestrowano tylko '+rows.length+' występów — minimum '+n+' potrzebnych do L'+n:'Średnia z ostatnich '+n+' rzeczywiście rozegranych meczów ESPN')+
   '"><span>L'+n+(rows.length<n?' ('+rows.length+'/'+n+')':'')+'</span><strong>'+fmt(mean(rows,n))+'</strong></div>').join("")+
   '<div title="'+(seasonValue!==null?'Zweryfikowana średnia sezonu w tej drużynie z '+seasonGames+' meczów ESPN. Nie obejmuje poprzednich drużyn zawodnika.':'Nie mamy pełnego archiwum wszystkich dotychczasowych spotkań tej drużyny. Nie pokazujemy średniej z części danych jako całego sezonu.')+
   '"><span>Sezon'+(seasonValue!==null?' · '+esc(teamOf(player)):'')+'</span><strong>'+fmt(seasonValue)+'</strong></div>';
}
function drawSummary(){
 const {game,sim,premium}=active,ctx=sim?.model_context||{};
 const c=ctx.team_comparison||{},teams=[c.away,c.home];
 const team=Array.isArray(teams)?teams:[];
 if(premium?.entitled!==true||!sim){
  ["hzv3-teamform","hzv3-pace","hzv3-rest"].forEach(id=>$(id).innerHTML=empty("Brak zweryfikowanych danych meczu."));return;
 }
 $("hzv3-teamform").innerHTML=team.map(t=>
  '<div class="hzv3-teamline"><strong>'+esc(t?.team||"—")+'</strong>'+
  '<span>'+((int(t?.wins10)!==null&&int(t?.losses10)!==null)?t.wins10+'–'+t.losses10:'—')+'</span>'+
  '<strong>'+fmt(t?.pts10)+' PTS</strong><span>'+fmt(t?.allowed10)+' STR</span></div>').join("");
 const pace=(c.advanced_available===true&&num(c.away?.pace)!==null&&num(c.home?.pace)!==null)
  ?fmt((Number(c.away.pace)+Number(c.home.pace))/2):"—";
 const sd=Array.isArray(ctx.score_sd_points)?ctx.score_sd_points:[];
 const sample=Array.isArray(ctx.score_sd_samples)?ctx.score_sd_samples:[];
 const sdValid=active.model!=="legacy_v72"&&sd.length===2&&sd.every(v=>num(v)!==null&&num(v)>=0);
 const deviation=sdValid?"±"+fmt(Math.sqrt((Number(sd[0])**2+Number(sd[1])**2)/2)):"—";
 const sampleLabel=sample.length===2&&sample.every(n=>int(n)!==null)
   ?'Próby: '+sample.join(" / "):"Brak potwierdzonej próby";
 $("hzv3-pace").innerHTML='<div class="hzv3-pace-cols">'+
  '<div title="PACE wyłącznie z aktualnego NBA Advanced dla obu drużyn"><small>PACE</small><strong>'+pace+'</strong></div>'+
  '<div title="Orientacyjne modelowe SD punktów drużyn; '+esc(sampleLabel)+'. To nie jest liczba meczów ani pewny zakres."><small>Model SD</small><strong>'+deviation+'</strong></div>'+
  '<div title="Prognozowana suma punktów z modelu '+version(active.model)+'"><small>Total (proj.)</small><strong>'+fmt(sim.total_points)+'</strong></div></div>';
 const rest=Array.isArray(ctx.rest_days)?ctx.rest_days:[];
 const injury=ctx.v75_factors;
 $("hzv3-rest").innerHTML=[game?.away,game?.home].map((code,i)=>{
  const day=int(rest[i]);const label=day===null?"brak danych":day===0?"B2B · 0 dni":day===1?"1 dzień":day+" dni";
  const fresh=injury?.injuries_espn_fresh===true;
  const uncertain=fresh?(i===0?int(injury.injury_uncertain_away):int(injury.injury_uncertain_home)):null;
  const stat=fresh?(uncertain===null?"raport ESPN":uncertain+" niepewnych"):"raport niezweryfikowany";
  return '<div class="hzv3-restline"><strong>'+esc(code||"—")+'</strong><span>'+label+'</span>'+
    '<span style="grid-column:span 2">'+stat+'</span></div>';
 }).join("");
}
function refresh(){
 if(!active)return;
 const {premium,game,players,state}=active;
 const v=version(active.model);
 $("hzv3-version").textContent=v;
 $("hzv3-model-context").textContent="MODEL "+v+" · PROJEKCJA";
 $("hzv3-away-filter").textContent=game?.away||"GOŚCIE";
 $("hzv3-home-filter").textContent=game?.home||"GOSPODARZE";
 root.querySelectorAll("[data-hzv3-team]").forEach(button=>button.setAttribute("aria-pressed",
    String(button.dataset.hzv3Team===(state.playerTeam||"all"))));
 root.querySelectorAll("[data-hzv3-market]").forEach(button=>button.setAttribute("aria-pressed",
    String(button.dataset.hzv3Market===(state.playerMarket||"PTS"))));
 if($("hzv3-query").value!==String(state.playerQuery||""))$("hzv3-query").value=state.playerQuery||"";
 if(premium?.entitled!==true){
  $("hzv3-count").textContent="Premium";
  $("hzv3-roster").innerHTML=empty("Zaloguj się na konto Premium, aby zobaczyć projekcje.");
  $("hzv3-inspector").innerHTML=empty("Dane zawodników są dostępne wyłącznie dla Premium.");
  drawCharts(null);drawSummary();return;
 }
 const all=Array.isArray(players?.players)?players.players:[];
 const entries=fullList();
 $("hzv3-count").textContent=players?entries.length+" z "+all.length+" projekcji":"Ładowanie zawodników…";
 const chosen=selected(entries);
 showList(entries);drawInspector(chosen);drawCharts(chosen);drawSummary();
}
function render(args){
 active=args;
 root.hidden=false;
 refresh();
}
root.addEventListener("click",event=>{
 if(!active)return;
 const target=event.target;
 if(target.closest("[data-hzv3-return]")){
   if(active.premium?.entitled===true&&active.state.fromProps)active.onReturn?.();
   return;
 }
 const m=target.closest("[data-hzv3-market]");
 if(m){const v=m.dataset.hzv3Market;
  if(["PTS","REB","AST","PRA"].includes(v)){active.state.playerMarket=v;refresh();}return;}
 const t=target.closest("[data-hzv3-team]");
 if(t){const v=t.dataset.hzv3Team;
  if(["all","away","home"].includes(v)){active.state.playerTeam=v;active.state.playerIndex=-1;refresh();}return;}
 const w=target.closest("[data-hzv3-window]");
 if(w){const v=w.dataset.hzv3Window;
  if(["5","10","15","season"].includes(v)){active.state.playerHistoryWindow=v==="season"?"season":Number(v);refresh();}return;}
 const pick=target.closest("[data-hzv3-pick]");
 if(pick){
   const i=Number(pick.dataset.hzv3Pick),all=active.players?.players;
   if(active.premium?.entitled===true&&Number.isInteger(i)&&i>=0&&i<all?.length){
    active.state.playerIndex=i;refresh();
   }return;
 }
 const props=target.closest("[data-hzv3-props]");
 if(props){
  const m=props.dataset.hzv3Props,all=active.players?.players,item=all?.[active.state.playerIndex];
  if(active.premium?.entitled===true&&item&&["PTS","REB","AST","PRA"].includes(m)&&metric(item,m)!==null)
    active.onHistory?.(item,m);
 }
});
$("hzv3-query").addEventListener("input",event=>{
 if(!active||active.premium?.entitled!==true)return;
 active.state.playerQuery=String(event.target.value||"").slice(0,80);
 active.state.playerIndex=-1;
 refresh();
 $("hzv3-query").focus();
});
root.addEventListener("error",event=>{
 if(event.target?.matches?.(".hzv3-team-watermark img")){
   event.target.closest(".hzv3-team-watermark")?.classList.remove("has-logo");
   event.target.remove();
 }else if(event.target?.matches?.(".hzv3-face img,.hzv3-athlete-photo img")){
   event.target.remove();
 }
},true);
window.HoopzaroPlayerV3={render,clear(){
 active=null;
 root.hidden=true;
 $("hzv3-roster").replaceChildren();
 $("hzv3-inspector").replaceChildren();
 ["hzv3-hist","hzv3-trend","hzv3-rates","hzv3-averages","hzv3-teamform","hzv3-pace","hzv3-rest"]
   .forEach(id=>$(id).replaceChildren());
}};
})();