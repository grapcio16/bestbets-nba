/* Free HOOPZARO Terminarz: confirmed ESPN games and verified season stats only. */
(function(){
"use strict";
let callback=null,selectedDay="",requestedDay="",selectedFilter="all",lastData=null;
let selectedGameId="",requestedDetailsId="",lastDetails=null;
const FAV_KEY="hoopzaro.schedule.favoriteTeams.v1";
const VALID_TEAMS=new Set("ATL BOS BKN CHA CHI CLE DAL DEN DET GSW HOU IND LAC LAL MEM MIA MIL MIN NOP NYK OKC ORL PHI PHX POR SAC SAS TOR UTA WAS".split(" "));
function readFavorites(){
  try{
    const stored=JSON.parse(window.localStorage.getItem(FAV_KEY)||"[]");
    return Array.isArray(stored)?stored.filter(code=>typeof code==="string"&&VALID_TEAMS.has(code)):[];
  }catch(_){return []}
}
const favorites=new Set(readFavorites());
function persistFavorites(){
  try{window.localStorage.setItem(FAV_KEY,JSON.stringify([...favorites].sort()))}catch(_){
    // Private browsing and restricted contexts still allow session favorites.
  }
}
function isFavoriteGame(game){return favorites.has(game?.away)||favorites.has(game?.home)}
function favoriteStar(code,gameId,side){
  if(!VALID_TEAMS.has(code))return "";
  const active=favorites.has(code),title=active?"Usuń z ulubionych: ":"Dodaj do ulubionych: ";
  return '<button type="button" class="hzs-favorite-star hzs-favorite-'+side+
    (active?' is-favorite':'')+'" data-hzs-star="'+escapeHtml(code)+
    '" aria-label="'+title+escapeHtml(code)+'" aria-pressed="'+String(active)+
    '" title="'+title+escapeHtml(code)+'"><span aria-hidden="true">'+(active?'★':'☆')+'</span></button>';
}
const $=id=>document.getElementById(id);
const escapeHtml=value=>String(value==null?"":value).replace(/[&<>"']/g,ch=>({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
})[ch]);
const WARSAW="Europe/Warsaw";
const safeDay=day=>/^\d{4}-\d{2}-\d{2}$/.test(String(day||""));
function dateAtNoon(day){return new Date(day+"T12:00:00Z")}
function shiftDay(day,offset){
  const time=dateAtNoon(day);time.setUTCDate(time.getUTCDate()+offset);
  return time.toISOString().slice(0,10);
}
function localDay(timestamp){
  const date=new Date(timestamp);
  if(!Number.isFinite(date.getTime()))return "";
  const parts=new Intl.DateTimeFormat("en-GB",{timeZone:WARSAW,day:"2-digit",month:"2-digit",year:"numeric"}).formatToParts(date);
  const get=type=>parts.find(part=>part.type===type)?.value||"";
  return get("year")+"-"+get("month")+"-"+get("day");
}
function today(){return localDay(new Date().toISOString())}
function localTime(timestamp){
  const date=new Date(timestamp);
  return Number.isFinite(date.getTime())
    ?new Intl.DateTimeFormat("pl-PL",{timeZone:WARSAW,hour:"2-digit",minute:"2-digit",hour12:false}).format(date)
    :"—";
}
function withinRange(day){return Math.abs(Math.round((dateAtNoon(day)-dateAtNoon(today()))/86400000))<=366}
function dateNavigation(){
  const host=$("hzs-date-strip");if(!host)return;
  const weekdays=["NIE","PON","WTO","ŚRO","CZW","PIĄ","SOB"];
  const months=["STY","LUT","MAR","KWI","MAJ","CZE","LIP","SIE","WRZ","PAŹ","LIS","GRU"];
  host.innerHTML=Array.from({length:7},(_,index)=>{
    const day=shiftDay(selectedDay,index-3),date=dateAtNoon(day);
    const label=weekdays[date.getUTCDay()]+" "+date.getUTCDate()+" "+months[date.getUTCMonth()];
    return '<button type="button" class="hzs-date'+(day===selectedDay?' selected':'')+'"'+
      ' data-hzs-day="'+day+'"'+(withinRange(day)?'':' disabled')+
      ' aria-label="Mecze NBA '+escapeHtml(day)+'" aria-pressed="'+(day===selectedDay?'true':'false')+'">'+
      '<strong>'+weekdays[date.getUTCDay()]+'</strong><span>'+date.getUTCDate()+' '+months[date.getUTCMonth()]+'</span></button>';
  }).join("");
  document.querySelectorAll("[data-hzs-direction]").forEach(button=>{
    const candidate=shiftDay(selectedDay,Number(button.dataset.hzsDirection));
    button.disabled=!withinRange(candidate);
  });
  const datePicker=$("hzs-date-picker");
  if(datePicker){
    datePicker.value=selectedDay;
    datePicker.min=shiftDay(today(),-366);
    datePicker.max=shiftDay(today(),366);
  }
  if($("hzs-today"))$("hzs-today").disabled=selectedDay===today();
}
function selectedGames(data){
  const extra=data?.calendar_extras?.[selectedDay];
  if(extra && typeof extra==="object")return {
    games:Array.isArray(extra.games)?extra.games:[],known:true,
    error:String(extra.error||""),complete:extra.complete!==false
  };
  const all=Array.isArray(data?.calendar_games)?data.calendar_games:
    Array.isArray(data?.games)?data.games:[];
  const games=all.filter(game=>(game.day||localDay(game.start))===selectedDay);
  const known=(data?.calendar_loaded_days||[]).includes(selectedDay)||games.length>0;
  return {games:games,known:known,error:String(data?.error||""),complete:true};
}
function seasonMatches(day){
  // The verified 2026/27 standings must not be misrepresented as another season.
  return day>="2026-10-01"&&day<="2027-09-30";
}
function currentStats(data,code){
  if(!seasonMatches(selectedDay))return {ppg:"—",record:"—"};
  const row=(data?.form_options||[]).find(entry=>entry.team===code);
  const verified=row?.record_verified===true;
  const points=Number(row?.ppg);
  return {
    ppg:verified&&row?.ppg!=null&&Number.isFinite(points)&&points>=50&&points<=160
      ?points.toFixed(1).replace(".",","):"—",
    record:verified&&Number.isInteger(row?.wins)&&Number.isInteger(row?.losses)
      ?row.wins+"–"+row.losses:"—"
  };
}
function verifiedStats(data,code){
  if(!seasonMatches(selectedDay))return null;
  const row=(data?.form_options||[]).find(entry=>entry.team===code);
  const ppg=Number(row?.ppg),wins=row?.wins,losses=row?.losses;
  if(row?.record_verified!==true||row?.ppg==null||!Number.isFinite(ppg)||
     ppg<50||ppg>160||!Number.isInteger(wins)||!Number.isInteger(losses)||
     wins<0||losses<0||wins+losses===0)return null;
  return {ppg,winRate:wins/(wins+losses)};
}
const clamp01=n=>Math.max(0,Math.min(1,n));
function gameOfDay(games,data){
  // FREE editorial selection: public, verified W/L and season PPG only.
  // Never read projections, Premium state, model probabilities or game scores.
  let best=null,bestScore=-1;
  games.forEach(game=>{
    const away=verifiedStats(data,game.away),home=verifiedStats(data,game.home);
    if(!away||!home)return;
    const quality=(away.winRate+home.winRate)/2;
    const parity=1-Math.abs(away.winRate-home.winRate);
    const scoring=clamp01(((away.ppg+home.ppg)/2-90)/40);
    // The most compelling game is usually two strong, similarly matched
    // teams; raw offensive pace must not dominate the spotlight.
    const rating=.45*quality+.45*parity+.10*scoring;
    if(rating>bestScore){best=game;bestScore=rating;}
  });
  return best;
}
function teamMark(code,url){
  url=window.hzResolveTeamLogo?.(url)||"";
  const safe=typeof url==="string"&&/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(url);
  return '<span class="hzs-team-mark">'+(safe
    ?'<img src="'+url+'" alt="" loading="lazy">'
    :'<b>'+escapeHtml(code)+'</b>')+'</span>';
}
function teamText(code,data){
  const stats=currentStats(data,code);
  const team=(data?.form_options||[]).find(row=>row.team===code);
  const name=String(team?.name||"").trim();
  return '<span class="hzs-team-info"><strong>'+escapeHtml(code)+'</strong>'+
    (name?'<small class="hzs-team-full" title="'+escapeHtml(name)+'">'+escapeHtml(name)+'</small>':'')+
    '<small class="hzs-team-stat"><em>'+escapeHtml(stats.ppg)+' PPG</em> &nbsp;·&nbsp; <b>'+escapeHtml(stats.record)+'</b></small></span>';
}
function score(game){
  if(game.state==="scheduled")return localTime(game.start);
  const away=game.away_score,home=game.home_score;
  return Number.isInteger(away)&&away>=0&&Number.isInteger(home)&&home>=0
    ?away+" : "+home:"—";
}
function liveLabel(raw){
  const text=String(raw||"");
  const match=text.match(/\bQ([1-4])\b/i)||text.match(/\b([1-4])(?:st|nd|rd|th)\b/i);
  return match?"NA ŻYWO · "+match[1]+". KWARTA":"NA ŻYWO";
}
function gameMarkup(game,data,featured=false){
  const away=String(game.away||"NBA").toUpperCase(),home=String(game.home||"NBA").toUpperCase();
  const badge=game.state==="live"?liveLabel(game.status):game.state==="final"?"KONIEC":"NADCHODZĄCE";
  const kind=game.state==="live"?"live":game.state==="final"?"final":"upcoming";
  const awayScore=game.away_score,homeScore=game.home_score;
  const final=game.state==="final"&&Number.isInteger(awayScore)&&Number.isInteger(homeScore);
  const winner=final&&awayScore!==homeScore?(awayScore>homeScore?"away":"home"):"";
  const id=String(game.id||"");
  const expanded=id!==""&&id===selectedGameId;
  return '<div class="hzs-game-shell'+(featured?' hzs-featured-shell':'')+
    (isFavoriteGame(game)?' hzs-favorite-game':'')+'" data-hzs-shell-id="'+escapeHtml(id)+'">'+
    '<button type="button" class="hzs-game hzs-'+kind+(featured?' hzs-featured':'')+
    '" data-hzs-game="'+escapeHtml(id)+'" aria-expanded="'+String(expanded)+
    '" aria-label="'+escapeHtml(away+' – '+home+', '+badge+', pokaż szczegóły meczu')+'">'+
    (featured?'<span class="hzs-feature-ribbon" title="Mecz dnia: 45% siła bilansów, 45% wyrównanie bilansów, 10% średnia punktów. Wyłącznie zweryfikowane dane sezonu, bez symulacji."><span aria-hidden="true">✦</span> MECZ DNIA <span aria-hidden="true">✦</span></span>':'')+
    '<span class="hzs-team away'+(winner==="away"?' hzs-winner':'')+'">'+teamMark(away,game.away_logo)+teamText(away,data)+'</span>'+
    '<span class="hzs-score"><strong>'+escapeHtml(score(game))+'</strong><span class="hzs-status">'+escapeHtml(badge)+'</span></span>'+
    '<span class="hzs-team home'+(winner==="home"?' hzs-winner':'')+'">'+teamText(home,data)+teamMark(home,game.home_logo)+'</span>'+
    '<span class="hzs-expand-mark" aria-hidden="true">'+(expanded?'⌃':'⌄')+'</span></button>'+
    favoriteStar(away,id,"away")+favoriteStar(home,id,"home")+'</div>';
}
function detailMarkup(game,data){
  const id=String(game.id||"");
  if(!id||id!==selectedGameId)return "";
  const away=String(game.away||""),home=String(game.home||"");
  const awayStats=currentStats(data,away),homeStats=currentStats(data,home);
  const season=seasonMatches(selectedDay);
  const packet=lastDetails?.id===id&&lastDetails?.day===selectedDay?lastDetails:null;
  const details=packet?.data&&packet.data.away===away&&packet.data.home===home?packet.data:null;
  const noGameStats=game.state==="scheduled"
    ?'<p class="hzs-detail-note">Spotkanie jeszcze się nie rozpoczęło. Wyniki kwart i box score pojawią się po ich opublikowaniu przez ESPN.</p>'
    :packet?.error
      ?'<p class="hzs-detail-note hzs-detail-error">'+escapeHtml(packet.error)+'</p>'
      :!packet
        ?'<p class="hzs-detail-note">Pobieranie potwierdzonego box score ESPN…</p>'
        :'';
  const columns=(rows,heading)=>
    '<section class="hzs-detail-section"><h3>'+heading+'</h3><div class="hzs-detail-table">'+rows+'</div></section>';
  let parts='';
  if(details?.quarters?.length){
    parts+=columns('<div class="hzs-detail-row hzs-detail-subhead"><span>KWARTA</span><span>'+escapeHtml(away)+'</span><span>'+escapeHtml(home)+'</span></div>'+
      details.quarters.map(q=>'<div class="hzs-detail-row"><span>'+escapeHtml(q.period)+'</span><b>'+escapeHtml(q.away)+'</b><b>'+escapeHtml(q.home)+'</b></div>').join(""),
      "Wyniki kwart");
  }
  if(details?.team_stats?.length){
    parts+=columns('<div class="hzs-detail-row hzs-detail-subhead"><span>STATYSTYKA</span><span>'+escapeHtml(away)+'</span><span>'+escapeHtml(home)+'</span></div>'+
      details.team_stats.map(q=>'<div class="hzs-detail-row"><span>'+escapeHtml(q.label)+'</span><b>'+escapeHtml(q.away)+'</b><b>'+escapeHtml(q.home)+'</b></div>').join(""),
      "Statystyki drużyn");
  }
  const leaderGroups=details?.leaders||{};
  if((leaderGroups.away||[]).length||(leaderGroups.home||[]).length){
    const markup=(code,players)=>'<div class="hzs-leader-team"><h4>'+escapeHtml(code)+'</h4>'+
      (players.length?players.map(player=>
        '<div class="hzs-leader"><strong>'+escapeHtml(player.name)+'</strong><span>'+
        escapeHtml(player.pts)+' PTS · '+escapeHtml(player.reb)+' REB · '+escapeHtml(player.ast)+' AST</span></div>').join("")
        :'<span class="hzs-detail-muted">Brak potwierdzonych statystyk</span>')+'</div>';
    parts+='<section class="hzs-detail-section hzs-detail-leaders"><h3>Liderzy meczu · PTS / REB / AST</h3>'+
      '<div class="hzs-leader-grid">'+markup(away,leaderGroups.away||[])+markup(home,leaderGroups.home||[])+'</div></section>';
  }
  if(details&&!parts)parts='<p class="hzs-detail-note">ESPN nie opublikował jeszcze pełnych statystyk kwart, drużyn i zawodników.</p>';
  const teams='<div class="hzs-detail-teams">'+
    '<div><strong>'+escapeHtml(away)+'</strong><span>'+escapeHtml(awayStats.record)+' W–L · '+escapeHtml(awayStats.ppg)+' PPG</span></div>'+
    '<div class="hzs-detail-vs">VS</div>'+
    '<div><strong>'+escapeHtml(home)+'</strong><span>'+escapeHtml(homeStats.record)+' W–L · '+escapeHtml(homeStats.ppg)+' PPG</span></div></div>';
  return '<div class="hzs-detail-panel" id="hzs-game-details" role="region" aria-label="Szczegóły meczu '+escapeHtml(away)+' i '+escapeHtml(home)+'">'+
    '<div class="hzs-detail-header"><div><span class="hzs-detail-kicker">HOOPZARO · GAME CENTER · FREE</span>'+
    '<h2>'+escapeHtml(away)+' <span>vs</span> '+escapeHtml(home)+'</h2></div>'+
    '<span class="hzs-detail-state">'+escapeHtml(game.state==="scheduled"?localTime(game.start):score(game))+'</span></div>'+
    teams+'<p class="hzs-detail-caption">'+(season?'Bilans i PPG: potwierdzone dane sezonu 2026/27 (stan bieżący).':'Statystyki sezonowe niedostępne dla wybranej daty.')+'</p>'+
    noGameStats+(parts?'<div class="hzs-detail-grid">'+parts+'</div>':'')+
    '<div class="hzs-detail-source">Źródło: ESPN · bez symulacji i prognoz'+(details?.stale?' · dane źródłowe mogą być opóźnione':'')+'</div>'+
    '</div>';
}
function syncFilters(){
  document.querySelectorAll("[data-hzs-filter]").forEach(button=>{
    const active=button.dataset.hzsFilter===selectedFilter;
    button.classList.toggle("selected",active);
    button.setAttribute("aria-pressed",String(active));
  });
}
function render(data,details){
  lastData=data;
  lastDetails=details||null;
  if(!selectedDay)selectedDay=safeDay(data?.calendar_today)?data.calendar_today:today();
  dateNavigation();
  syncFilters();
  const host=$("hzs-board");if(!host)return;
  const previousScroll=host.scrollTop;
  const footnote=$("hzs-source-note");
  const counter=$("hzs-match-count");
  if(footnote)footnote.textContent="ESPN · rzeczywiste mecze · statystyki sezonu 2026/27 (stan bieżący)";
  if(!data){
    if(counter)counter.textContent="— meczów";
    host.innerHTML='<div class="hzs-empty">Wczytywanie potwierdzonych spotkań NBA…</div>';return;
  }
  const day=selectedGames(data);
  if(!day.known){
    if(counter)counter.textContent="— meczów";
    host.innerHTML='<div class="hzs-empty">'+(requestedDay===selectedDay
      ?'Pobieranie spotkań NBA z '+escapeHtml(selectedDay)+'…'
      :'Wybierz dzień, aby pobrać jego terminarz NBA.')+'</div>';
    if(requestedDay!==selectedDay)requestDay(selectedDay);
    return;
  }
  if(requestedDay===selectedDay)requestedDay="";
  // Every unique confirmed event is shown; never slice to a decorative card count.
  const unique=new Map();
  day.games.forEach(game=>{
    if(!game)return;
    const key=game.id||[game.start,game.away,game.home].join("|");
    unique.set(String(key),game);
  });
  const games=[...unique.values()].sort((a,b)=>String(a.start||"").localeCompare(String(b.start||"")));
  if(counter)counter.textContent=games.length+" "+(games.length===1?"mecz":games.length>=2&&games.length<=4?"mecze":"meczów");
  const alert=day.error?'<div class="hzs-alert">'+escapeHtml(day.error.slice(0,180))+'</div>':"";
  if(!games.length){
    host.innerHTML=alert+'<div class="hzs-empty">Brak potwierdzonych meczów NBA '+escapeHtml(selectedDay)+'.</div>';
    return;
  }
  const filtered=selectedFilter==="all"?games:
    selectedFilter==="favorites"?games.filter(isFavoriteGame):
    games.filter(game=>game.state===selectedFilter);
  if(!filtered.length){
    const empty={live:"Brak trwających meczów.",scheduled:"Brak nadchodzących meczów.",
      final:"Brak zakończonych meczów.",
      favorites:favorites.size===0?"Oznacz drużynę gwiazdką ☆, aby zobaczyć jej mecze.":"Ulubione drużyny nie rozgrywają meczów w wybranym dniu."};
    host.innerHTML=alert+'<div class="hzs-empty">'+(empty[selectedFilter]||"Brak meczów.")+'</div>';
    return;
  }
  const featured=selectedFilter==="all"?gameOfDay(games,data):null;
  const remaining=featured?filtered.filter(game=>game!==featured):filtered;
  const favoriteRemaining=remaining.filter(isFavoriteGame);
  const ordinaryRemaining=remaining.filter(game=>!isFavoriteGame(game));
  const title=featured?"POZOSTAŁE MECZE":selectedFilter==="all"?"WSZYSTKIE MECZE":"MECZE";
  const group=(heading,items,highlight)=>
    items.length?'<div class="hzs-section-title'+(highlight?' hzs-favorite-section-title':'')+'"><span class="hzs-section-dot" aria-hidden="true"></span>'+
      heading+' · '+items.length+'</div><div class="hzs-rows">'+
      items.map(game=>gameMarkup(game,data)+detailMarkup(game,data)).join("")+'</div>':"";
  const favoriteMarkup=group("★ ULUBIONE DRUŻYNY",favoriteRemaining,true);
  const regularMarkup=group(title,ordinaryRemaining,false);
  const featureMarkup=featured?gameMarkup(featured,data,true)+detailMarkup(featured,data):"";
  const placeFavoritesFirst=Boolean(featured&&!isFavoriteGame(featured)&&favoriteRemaining.length);
  host.innerHTML=alert+'<section class="hzs-section" aria-label="Mecze NBA">'+
    (placeFavoritesFirst?favoriteMarkup:"")+featureMarkup+
    (placeFavoritesFirst?"":favoriteMarkup)+regularMarkup+'</section>';
  host.scrollTop=previousScroll;
}
function requestDay(day){
  if(!callback?.selectDay||!safeDay(day)||!withinRange(day))return;
  requestedDay=day;callback.selectDay(day);
}
function selectDay(day){
  if(!safeDay(day)||!withinRange(day)||day===selectedDay)return;
  selectedDay=day;requestedDay="";selectedFilter="all";
  selectedGameId="";requestedDetailsId="";
  render(lastData,lastDetails);
}
function init(api){
  callback=api;
  $("hzs-board")?.addEventListener("click",event=>{
    const star=event.target.closest("[data-hzs-star]");
    if(star){
      event.preventDefault();
      const code=star.dataset.hzsStar||"";
      const gameId=star.closest("[data-hzs-shell-id]")?.dataset.hzsShellId||"";
      if(!VALID_TEAMS.has(code))return;
      if(favorites.has(code))favorites.delete(code);
      else favorites.add(code);
      persistFavorites();
      render(lastData,lastDetails);
      const replacement=[...$("hzs-board").querySelectorAll("[data-hzs-star]")].find(el=>
        el.dataset.hzsStar===code&&el.closest("[data-hzs-shell-id]")?.dataset.hzsShellId===gameId);
      replacement?.focus({preventScroll:true});
      return;
    }
    const target=event.target.closest("[data-hzs-game]");
    if(!target||!lastData)return;
    const id=target.dataset.hzsGame||"";
    const game=selectedGames(lastData).games.find(g=>String(g?.id||"")===id);
    if(!id||!game)return;
    selectedGameId=selectedGameId===id?"":id;
    if(!selectedGameId){requestedDetailsId="";render(lastData,lastDetails);return}
    if(game.state!=="scheduled"&&(!lastDetails||lastDetails.id!==id||lastDetails.day!==selectedDay)){
      if(requestedDetailsId!==id){
        requestedDetailsId=id;
        callback?.gameDetails?.({game_id:id,date:selectedDay});
      }
    }
    render(lastData,lastDetails);
    requestAnimationFrame(()=>{
      const section=$("hzs-game-details");
      if(section)section.scrollIntoView({block:"nearest",behavior:"smooth"});
    });
  });
  document.querySelector(".hzs-filters")?.addEventListener("click",event=>{
    const button=event.target.closest("[data-hzs-filter]");
    if(!button||selectedFilter===button.dataset.hzsFilter)return;
    selectedFilter=button.dataset.hzsFilter;
    selectedGameId="";requestedDetailsId="";
    render(lastData,lastDetails);
  });
  $("hzs-date-strip")?.addEventListener("click",event=>{
    const button=event.target.closest("[data-hzs-day]");
    if(button&&!button.disabled)selectDay(button.dataset.hzsDay);
  });
  document.querySelectorAll("[data-hzs-direction]").forEach(button=>{
    button.addEventListener("click",()=>selectDay(shiftDay(selectedDay,Number(button.dataset.hzsDirection))));
  });
  $("hzs-today")?.addEventListener("click",()=>selectDay(today()));
  $("hzs-date-picker")?.addEventListener("change",event=>{
    const value=event.target.value;
    if(safeDay(value)&&withinRange(value))selectDay(value);
    else event.target.value=selectedDay;
  });
}
window.HoopzaroSchedule={init,render};
})();
