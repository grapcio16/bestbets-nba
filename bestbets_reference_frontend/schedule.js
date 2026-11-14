/* Free HOOPZARO Terminarz: confirmed ESPN games and verified season stats only. */
(function(){
"use strict";
let callback=null,selectedDay="",requestedDay="",lastData=null;
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
function teamMark(code,url){
  const safe=typeof url==="string"&&/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(url);
  return '<span class="hzs-team-mark">'+(safe
    ?'<img src="'+url+'" alt="" loading="lazy">'
    :'<b>'+escapeHtml(code)+'</b>')+'</span>';
}
function teamText(code,data){
  const stats=currentStats(data,code);
  return '<span class="hzs-team-info"><strong>'+escapeHtml(code)+'</strong><small>'+
    '<em>'+escapeHtml(stats.ppg)+' PPG</em> &nbsp;·&nbsp; <b>'+escapeHtml(stats.record)+'</b></small></span>';
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
function gameMarkup(game,data){
  const away=String(game.away||"NBA").toUpperCase(),home=String(game.home||"NBA").toUpperCase();
  const badge=game.state==="live"?liveLabel(game.status):game.state==="final"?"KONIEC":"NADCHODZĄCE";
  const kind=game.state==="live"?"live":game.state==="final"?"final":"upcoming";
  return '<article class="hzs-game hzs-'+kind+'" aria-label="'+escapeHtml(away+' – '+home+', '+badge)+'">'+
    '<div class="hzs-team away">'+teamMark(away,game.away_logo)+teamText(away,data)+'</div>'+
    '<div class="hzs-score"><strong>'+escapeHtml(score(game))+'</strong><span class="hzs-status">'+escapeHtml(badge)+'</span></div>'+
    '<div class="hzs-team home">'+teamText(home,data)+teamMark(home,game.home_logo)+'</div></article>';
}
function render(data){
  lastData=data;
  if(!selectedDay)selectedDay=safeDay(data?.calendar_today)?data.calendar_today:today();
  dateNavigation();
  const host=$("hzs-board");if(!host)return;
  const footnote=$("hzs-source-note");
  if(footnote)footnote.textContent="ESPN · rzeczywiste mecze · statystyki sezonu 2026/27 (stan bieżący)";
  if(!data){host.innerHTML='<div class="hzs-empty">Wczytywanie potwierdzonych spotkań NBA…</div>';return}
  const day=selectedGames(data);
  if(!day.known){
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
  const alert=day.error?'<div class="hzs-alert">'+escapeHtml(day.error.slice(0,180))+'</div>':"";
  if(!games.length){
    host.innerHTML=alert+'<div class="hzs-empty">Brak potwierdzonych meczów NBA '+escapeHtml(selectedDay)+'.</div>';
    return;
  }
  // One chronological full-width list. Each card carries its own current
  // LIVE / FINAL / UPCOMING status; no empty column when a day has one state.
  host.innerHTML=alert+'<section class="hzs-section" aria-label="Mecze NBA">'+
    '<div class="hzs-section-title"><span class="hzs-section-dot" aria-hidden="true"></span>MECZE · '+games.length+'</div>'+
    '<div class="hzs-rows">'+games.map(game=>gameMarkup(game,data)).join("")+'</div></section>';
}
function requestDay(day){
  if(!callback?.selectDay||!safeDay(day)||!withinRange(day))return;
  requestedDay=day;callback.selectDay(day);
}
function selectDay(day){
  if(!safeDay(day)||!withinRange(day)||day===selectedDay)return;
  selectedDay=day;requestedDay="";
  render(lastData);
}
function init(api){
  callback=api;
  $("hzs-date-strip")?.addEventListener("click",event=>{
    const button=event.target.closest("[data-hzs-day]");
    if(button&&!button.disabled)selectDay(button.dataset.hzsDay);
  });
  document.querySelectorAll("[data-hzs-direction]").forEach(button=>{
    button.addEventListener("click",()=>selectDay(shiftDay(selectedDay,Number(button.dataset.hzsDirection))));
  });
}
window.HoopzaroSchedule={init,render};
})();
