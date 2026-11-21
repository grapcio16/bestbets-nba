/* HOOPZARO Terminarz v4: verified NBA, approved scoreboard and separate FREE Game Center. */
(function(){
"use strict";
const $=id=>document.getElementById(id);
const esc=value=>String(value==null?"":value).replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
const WARSAW="Europe/Warsaw",FAV_KEY="hoopzaro.schedule.favoriteTeams.v1";
const OPEN_GAME_KEY="hoopzaro.schedule.openGame.v1";
const VALID=new Set("ATL BOS BKN CHA CHI CLE DAL DEN DET GSW HOU IND LAC LAL MEM MIA MIL MIN NOP NYK OKC ORL PHI PHX POR SAC SAS TOR UTA WAS".split(" "));
const EAST=new Set("ATL BOS BKN CHA CHI CLE DET IND MIA MIL NYK ORL PHI TOR WAS".split(" "));
const WEST=new Set([...VALID].filter(t=>!EAST.has(t)));
const MONTHS=["stycznia","lutego","marca","kwietnia","maja","czerwca","lipca","sierpnia","września","października","listopada","grudnia"];
const MONTH_CAP=["Styczeń","Luty","Marzec","Kwiecień","Maj","Czerwiec","Lipiec","Sierpień","Wrzesień","Październik","Listopad","Grudzień"];
let callback=null,selectedDay="",selectedGameId="",selectedFilter="all",requestedDay="";
let requestedDetailsId="",lastData=null,lastDetails=null,monthView="",searchText="",historyTab="h2h";
let renderedGameId="";
const expandedTables=new Set();
const readFavorites=()=>{try{const obj=JSON.parse(localStorage.getItem(FAV_KEY)||"[]");return Array.isArray(obj)?obj.filter(x=>VALID.has(x)):[];}catch(_){return [];}};
const favorites=new Set(readFavorites());
const safeDay=value=>/^\d{4}-\d{2}-\d{2}$/.test(String(value||""))&&!Number.isNaN(Date.parse(value+"T12:00:00Z"));
const noon=day=>new Date(day+"T12:00:00Z");
function shiftDay(day,offset){const d=noon(day);d.setUTCDate(d.getUTCDate()+offset);return d.toISOString().slice(0,10)}
function localDay(value){const d=new Date(value);if(!Number.isFinite(d.getTime()))return "";
 const parts=new Intl.DateTimeFormat("en-GB",{timeZone:WARSAW,year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(d);
 const part=k=>parts.find(p=>p.type===k)?.value||"";return part("year")+"-"+part("month")+"-"+part("day");
}
function today(){return localDay(new Date().toISOString())}
function withinRange(day){return safeDay(day)&&Math.abs((noon(day)-noon(today()))/86400000)<=366}
/* Streamlit can remount a custom component after a server rerun (for example
   while loading ESPN box scores). Preserve ONLY the public selected game ID,
   never player data, and guard browsers that disallow iframe sessionStorage. */
function readOpenGame(){
 try{
  const item=JSON.parse(sessionStorage.getItem(OPEN_GAME_KEY)||"null");
  return item&&/^\d{6,15}$/.test(String(item.id||""))&&withinRange(item.day)?item:null;
 }catch(_){return null;}
}
function saveOpenGame(game){
 try{if(game)sessionStorage.setItem(OPEN_GAME_KEY,JSON.stringify(game));
     else sessionStorage.removeItem(OPEN_GAME_KEY);}catch(_){}
}
const previousGame=readOpenGame();
if(previousGame){selectedGameId=String(previousGame.id);selectedDay=previousGame.day;}

function shortDate(day){const d=noon(day);return d.getUTCDate()+" "+MONTHS[d.getUTCMonth()]}
function fullHistoryDate(start){
 const day=localDay(start);
 if(!safeDay(day))return "—";
 const d=noon(day);
 return d.getUTCDate()+" "+MONTHS[d.getUTCMonth()]+" "+d.getUTCFullYear();
}
function localTime(value){const d=new Date(value);return Number.isFinite(d.getTime())?
 new Intl.DateTimeFormat("pl-PL",{timeZone:WARSAW,hour:"2-digit",minute:"2-digit",hour12:false}).format(d):"—"}
function displayDate(day){return day===today()?"Dzisiaj, "+shortDate(day):shortDate(day)+(noon(day).getUTCFullYear()===noon(today()).getUTCFullYear()?"":" "+noon(day).getUTCFullYear())}
/* The middle selector shows the selected Warsaw-local day.
   It still acts as a quick return-to-today control on other dates. */
function selectedDateLabel(day){
 const reference=today();
 if(day===reference)return "Dzisiaj";
 if(day===shiftDay(reference,-1))return "Wczoraj";
 if(day===shiftDay(reference,1))return "Jutro";
 return shortDate(day)+(noon(day).getUTCFullYear()!==noon(reference).getUTCFullYear()?" "+noon(day).getUTCFullYear():"");
}
function persistFavorites(){try{localStorage.setItem(FAV_KEY,JSON.stringify([...favorites].sort()))}catch(_){}}
function favGame(game){return favorites.has(game.away)||favorites.has(game.home)}
function star(code,id,side){if(!VALID.has(code))return "";
 const is=favorites.has(code),title=(is?"Usuń ":"Dodaj ")+"z ulubionych: "+code;
 return '<button type="button" class="hzs-favorite-star hzs-favorite-'+side+(is?' is-favorite':'')+
  '" data-hzs-star="'+esc(code)+'" data-hzs-star-game="'+esc(id)+'" aria-label="'+esc(title)+
  '" aria-pressed="'+String(is)+'" title="'+esc(title)+'">'+(is?'★':'☆')+'</button>';
}
function selectedGames(data){
 const extra=data?.calendar_extras?.[selectedDay];
 if(extra&&typeof extra==="object")return {games:Array.isArray(extra.games)?extra.games:[],known:true,error:String(extra.error||"")};
 const all=Array.isArray(data?.calendar_games)?data.calendar_games:Array.isArray(data?.games)?data.games:[];
 const games=all.filter(g=>(g.day||localDay(g.start))===selectedDay);
 return {games,known:(data?.calendar_loaded_days||[]).includes(selectedDay)||games.length>0,error:String(data?.error||"")};
}
function allKnownGames(data){
 const list=[...(data?.calendar_games||[])];
 for(const entry of Object.values(data?.calendar_extras||{}))if(entry&&Array.isArray(entry.games))list.push(...entry.games);
 const unique=new Map();for(const g of list)if(g?.id)unique.set(String(g.id),g);
 return [...unique.values()];
}
function seasonMatches(day){return day>="2026-10-01"&&day<="2027-09-30"}
function seasonRow(data,code){return (data?.form_options||[]).find(row=>row.team===code)||null}
function verified(data,code){if(!seasonMatches(selectedDay))return null;
 const row=seasonRow(data,code);return row?.record_verified===true&&Number.isInteger(row.wins)&&Number.isInteger(row.losses)&&row.wins+row.losses>0?row:null;
}
function gameOfDay(games,data){let winner=null,high=-Infinity;
 for(const g of games){const a=verified(data,g.away),h=verified(data,g.home);if(!a||!h)continue;
 const aw=a.wins/(a.wins+a.losses),hw=h.wins/(h.wins+h.losses);
 const quality=(aw+hw)/2,parity=1-Math.abs(aw-hw);
 const p=(Number(a.ppg)+Number(h.ppg))/2;
 const pace=Number.isFinite(p)?Math.max(0,Math.min(1,(p-90)/40)):0;
 const rating=.45*quality+.45*parity+.1*pace;
 if(rating>high){high=rating;winner=g;}
 }
 return winner;
}
function logo(code,value){const url=window.hzResolveTeamLogo?.(value)||"";
 const safe=typeof url==="string"&&/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(url);
 return '<span class="hzs-team-mark">'+(safe?'<img src="'+url+'" alt="" loading="lazy">':'<b>'+esc(code)+'</b>')+'</span>';
}
function teamLogo(data,code,game,side){
 const value=game?.[side+"_logo"]||seasonRow(data,code)?.logo||
  (typeof data?.team_logos?.[code]==="string"&&data.team_logos[code]?"team-logo:"+code:"");
 return logo(code,value);
}
function codeLabel(data,code){const name=seasonRow(data,code)?.name||code;return String(name||code)}
function score(g){if(g.state==="scheduled")return localTime(g.start);
 return Number.isInteger(g.away_score)&&Number.isInteger(g.home_score)?g.away_score+" – "+g.home_score:"—"}
function badge(g){return g.state==="live"?"NA ŻYWO":g.state==="final"?"KONIEC":"WKRÓTCE"}
function isFinal(g){return g.state==="final"&&Number.isInteger(g.away_score)&&Number.isInteger(g.home_score)}
function winner(g,side){return isFinal(g)&&g.away_score!==g.home_score&&g[side+"_score"]>g[(side==="home"?"away":"home")+"_score"]}
function heroMarkup(game,data){
 if(!game)return '<div class="hzv-skeleton">Brak zweryfikowanego meczu dnia dla wybranej daty</div>';
 const away=String(game.away||""),home=String(game.home||"");
 return '<button type="button" id="hzv-featured-button" class="hzv-featured-button" data-hzs-game="'+esc(game.id)+'" aria-label="Szczegóły meczu '+esc(away)+' – '+esc(home)+'">'+
 '<span class="hzv-featured-team">'+teamLogo(data,away,game,"away")+'<strong>'+esc(away)+'</strong></span>'+
 '<span class="hzv-featured-center"><span class="hzv-featured-label">♛ MECZ DNIA</span>'+
 '<strong class="hzv-featured-score">'+esc(score(game))+'</strong><span class="hzv-featured-status">'+esc(badge(game))+'</span></span>'+
 '<span class="hzv-featured-team">'+teamLogo(data,home,game,"home")+'<strong>'+esc(home)+'</strong></span>'+
 '</button><div class="hzv-hero-foot" aria-hidden="true"><span></span><span></span><span></span><span></span></div>';
}
function card(game,data){
 const a=String(game.away||"NBA"),h=String(game.home||"NBA"),id=String(game.id||"");
 return '<div class="hzs-game-shell'+(favGame(game)?' hzs-favorite-game':'')+'" data-hzs-shell-id="'+esc(id)+'">'+
 '<button type="button" class="hzs-game hzs-'+esc(game.state||"scheduled")+'" data-hzs-game="'+esc(id)+
 '" aria-label="'+esc("Otwórz Game Center: "+codeLabel(data,a)+" – "+codeLabel(data,h))+'">'+
 '<span class="hzs-mini-top"><span>🏀 NBA</span><span class="hzs-status">'+esc(badge(game))+'</span></span>'+
 '<span class="hzs-mini-middle"><span class="hzs-mini-team">'+teamLogo(data,a,game,"away")+
 '<strong'+(winner(game,"away")?' style="color:#70ffd5"':'')+'>'+esc(a)+'</strong></span>'+
 '<strong class="hzs-mini-score">'+esc(score(game))+'</strong>'+
 '<span class="hzs-mini-team">'+teamLogo(data,h,game,"home")+
 '<strong'+(winner(game,"home")?' style="color:#70ffd5"':'')+'>'+esc(h)+'</strong></span></span>'+
 '<span class="hzs-mini-bottom">'+(game.state==="scheduled"?"Planowany początek: ":"Wynik meczu · ")+
 esc(game.state==="scheduled"?localTime(game.start):shortDate(game.day||selectedDay))+'</span></button>'+
 star(a,id,"away")+star(h,id,"home")+'</div>';
}
function dateNavigation(){
 const date=$("hzv-day-title");if(date)date.textContent=displayDate(selectedDay);
 const strip=$("hzs-date-strip");if(strip){
  const names=["Nd","Pn","Wt","Śr","Cz","Pt","Sb"];
  strip.innerHTML=Array.from({length:7},(_,i)=>{
   const day=shiftDay(selectedDay,i-3),d=noon(day);
   const selected=day===selectedDay;
   return '<button type="button" class="hzs-date'+(selected?' selected':'')+'" data-hzs-day="'+day+
     '" aria-label="Pokaż mecze '+esc(day)+'" aria-pressed="'+String(selected)+'"'+(!withinRange(day)?' disabled':'')+
     '><strong>'+names[d.getUTCDay()]+'</strong><span>'+d.getUTCDate()+'</span></button>';
  }).join("");
 }
 document.querySelectorAll("#schedule-pane [data-hzs-direction]").forEach(b=>b.disabled=!withinRange(shiftDay(selectedDay,Number(b.dataset.hzsDirection))));
 const dayButton=$("hzs-today");
 if(dayButton){
  const isToday=selectedDay===today();
  const label=selectedDateLabel(selectedDay);
  dayButton.textContent=label;
  dayButton.disabled=isToday;
  dayButton.setAttribute("aria-label",isToday?"Wybrano dzisiejszy dzień":"Wybrano "+label+". Kliknij, aby wrócić do dzisiaj");
  dayButton.title=isToday?"Dzisiejsze mecze":"Powrót do dzisiejszych meczów";
 }
}
function renderCalendar(){
 const host=$("hzv-calendar-grid");if(!host)return;
 const base=noon(monthView||selectedDay),year=base.getUTCFullYear(),month=base.getUTCMonth();
 $("hzv-month-title").textContent=MONTH_CAP[month]+" "+year;
 const first=new Date(Date.UTC(year,month,1,12)),days=new Date(Date.UTC(year,month+1,0,12)).getUTCDate();
 const leading=(first.getUTCDay()+6)%7;
 host.innerHTML=Array.from({length:leading},()=>'<span aria-hidden="true"></span>').join("")+
 Array.from({length:days},(_,i)=>{
  const day=year+"-"+String(month+1).padStart(2,"0")+"-"+String(i+1).padStart(2,"0");
  return '<button type="button" data-hzv-calendar-day="'+day+'"'+(!withinRange(day)?' disabled':'')+
   ' aria-pressed="'+String(day===selectedDay)+'" aria-label="Wybierz '+day+'">'+(i+1)+'</button>';
 }).join("");
 const monthFirst=year+"-"+String(month+1).padStart(2,"0")+"-01";
 document.querySelectorAll("[data-hzv-month]").forEach(button=>{
  const next=new Date(Date.UTC(year,month+Number(button.dataset.hzvMonth),1,12));
  const nextDay=next.toISOString().slice(0,10);
  button.disabled=!withinRange(nextDay)&&Math.abs((noon(nextDay)-noon(today()))/86400000)>397;
 });
}
function toggleCalendar(open){
 const el=$("hzv-calendar-popup");if(!el)return;
 if(open){monthView=selectedDay.slice(0,7)+"-01";renderCalendar();}
 el.hidden=!open;$("hzv-calendar-toggle").setAttribute("aria-expanded",String(open));
}
function syncFilters(){document.querySelectorAll("#schedule-pane [data-hzs-filter]").forEach(b=>{
 const active=b.dataset.hzsFilter===selectedFilter;b.classList.toggle("selected",active);b.setAttribute("aria-pressed",String(active));
});}
function standings(data,conference){
 const host=$(conference==="east"?"hzv-east":"hzv-west");if(!host)return;
 const pool=conference==="east"?EAST:WEST,all=(data?.form_options||[]).filter(row=>pool.has(row.team)&&row.record_verified===true&&Number.isInteger(row.wins)&&Number.isInteger(row.losses)&&row.wins+row.losses>0);
 if(!all.length){host.innerHTML='<p>Brak potwierdzonej tabeli sezonu 2026/27.</p>';return;}
 all.sort((a,b)=>b.wins/(b.wins+b.losses)-a.wins/(a.wins+a.losses)||b.wins-a.wins||a.team.localeCompare(b.team));
 const shown=expandedTables.has(conference)?all:all.slice(0,5);
 const head='<div class="hzv-stand-row hzv-stand-head"><span>#</span><span>Drużyna</span><span>W</span><span>P</span><span>%</span></div>';
 host.innerHTML=head+shown.map((row,i)=>{
  const pct=(row.wins/(row.wins+row.losses)).toFixed(3).replace(/^0/,"");
  const name=String(row.name||row.team).replace(/^(?:Los Angeles|New York|Golden State|Oklahoma City|Portland|San Antonio|New Orleans|Minnesota|Philadelphia|Sacramento)\s+/,"");
  return '<div class="hzv-stand-row"><span>'+(i+1)+'</span><span class="hzv-stand-team">'+logo(row.team,row.logo)+
   '<b title="'+esc(row.name||row.team)+'">'+esc(name)+'</b></span><span>'+row.wins+'</span><span>'+row.losses+'</span><span>'+pct+'</span></div>';
 }).join("")+'<p class="hzv-standing-foot">Kolejność wg % zwycięstw · ESPN'+(data?.form_stale?' · dane opóźnione':'')+'</p>';
 document.querySelector('[data-hzv-table="'+conference+'"]')?.setAttribute("aria-expanded",String(expandedTables.has(conference)));
 const control=document.querySelector('[data-hzv-table="'+conference+'"]');
 if(control)control.textContent=expandedTables.has(conference)?"Pokaż mniej ↑":"Zobacz całość ›";
}
function renderBoard(data){
 const host=$("hzs-board");if(!host)return;
 const keepScroll=host.scrollTop;
 const counter=$("hzs-match-count");
 if(!data){host.innerHTML='<div class="hzs-empty">Wczytywanie terminarza NBA…</div>';return;}
 const selected=selectedGames(data);
 if(!selected.known){
  if(counter)counter.textContent="— meczów";
  $("hzv-hero").innerHTML='<p class="hzv-skeleton">Wybierz datę, aby zobaczyć mecz dnia.</p>';
  host.innerHTML='<div class="hzs-empty">'+(requestedDay===selectedDay?'Pobieranie meczów NBA z '+esc(selectedDay)+'…':'Pobieranie terminarza NBA…')+'</div>';
  if(requestedDay!==selectedDay)requestDay(selectedDay);
  return;
 }
 if(requestedDay===selectedDay)requestedDay="";
 const unique=new Map();for(const game of selected.games)if(game){const key=game.id||[game.start,game.away,game.home].join("|");unique.set(String(key),game);}
 const games=[...unique.values()].sort((a,b)=>String(a.start||"").localeCompare(String(b.start||"")));
 if(counter)counter.textContent=games.length+" "+(games.length===1?"mecz":games.length<5&&games.length>1?"mecze":"meczów");
 const hero=gameOfDay(games,data);
 $("hzv-hero").innerHTML=heroMarkup(hero,data);
 const alert=selected.error?'<div class="hzs-alert">'+esc(selected.error.slice(0,150))+'</div>':"";
 let filtered=selectedFilter==="all"?games:selectedFilter==="favorites"?games.filter(favGame):games.filter(g=>g.state===selectedFilter);
 const query=searchText.trim().toLocaleLowerCase("pl");
 if(query)filtered=filtered.filter(g=>[g.away,g.home,codeLabel(data,g.away),codeLabel(data,g.home)].some(v=>String(v).toLocaleLowerCase("pl").includes(query)));
 if(!filtered.length){
  const empty=selectedFilter==="favorites"?(favorites.size===0?"Oznacz gwiazdką ulubioną drużynę.":"Ulubione drużyny nie grają w wybranym dniu."):"Brak meczów spełniających filtry.";
  host.innerHTML=alert+'<div class="hzs-empty">'+(games.length?empty:'Brak potwierdzonych spotkań NBA '+esc(selectedDay)+'.')+'</div>';return;
 }
 const favs=filtered.filter(favGame),others=filtered.filter(g=>!favGame(g));
 const group=(label,items)=>items.length?'<div class="hzs-section-title"><span class="hzs-section-dot"></span>'+esc(label)+' · '+items.length+'</div><div class="hzs-rows">'+items.map(g=>card(g,data)).join("")+'</div>':"";
 const showGroups=favs.length>0&&selectedFilter!=="favorites";
 host.innerHTML=alert+'<section class="hzs-section" aria-label="Mecze NBA">'+
  (showGroups?group("★ ULUBIONE",favs):"")+group(showGroups?"POZOSTAŁE MECZE":"MECZE",showGroups?others:filtered)+'</section>';
 host.scrollTop=keepScroll;
}
function requestDay(day){if(!callback?.selectDay||!withinRange(day)||requestedDay===day)return;requestedDay=day;callback.selectDay(day);}
function selectDay(day){
 if(!withinRange(day))return;
 toggleCalendar(false);
 if(day===selectedDay)return;
 selectedDay=day;selectedFilter="all";selectedGameId="";renderedGameId="";requestedDetailsId="";requestedDay="";searchText="";
 saveOpenGame(null);
 if($("hzv-search"))$("hzv-search").value="";
 $("hzv-game-page").hidden=true;$("schedule-pane").classList.remove("hzv-show-game");
 render(lastData,lastDetails);
}
function gameFromSelected(data){
 const games=selectedGames(data).games;
 return games.find(g=>String(g.id||"")===selectedGameId)||null;
}
function initials(name){return String(name||"").split(/\s+/).map(part=>part[0]||"").slice(0,2).join("").toUpperCase()}
function quarterGraph(quarters,away,home){
 if(!quarters.length)return '<p class="hzv-history-empty">Brak potwierdzonych wyników kwart do wykresu.</p>';
 let a=0,h=0;const av=[],hv=[];for(const q of quarters){a+=q.away;h+=q.home;av.push(a);hv.push(h)}
 const high=Math.max(...av,...hv,1),W=265,H=122,left=18,right=245,top=11,bottom=100;
 const x=i=>left+(right-left)*(i+1)/quarters.length,y=v=>bottom-(bottom-top)*v/high;
 const path=arr=>"M"+arr.map((v,i)=>x(i).toFixed(1)+","+y(v).toFixed(1)).join(" L");
 const grid=[0,.25,.5,.75,1].map(p=>'<line x1="18" x2="245" y1="'+y(high*p).toFixed(1)+'" y2="'+y(high*p).toFixed(1)+'" stroke="#285071" stroke-width=".7"/>').join("");
 return '<svg viewBox="0 0 265 122" role="img" aria-label="Zweryfikowany przebieg punktów na koniec każdej kwarty">'+grid+
 '<path d="'+path(av)+'" fill="none" stroke="#02e5ef" stroke-width="2.5"/>'+
 '<path d="'+path(hv)+'" fill="none" stroke="#cb57ef" stroke-width="2.5"/>'+
 quarters.map((q,i)=>'<text x="'+x(i)+'" y="115" fill="#84acc9" font-size="8" text-anchor="middle">'+esc(q.period)+'</text>').join("")+
 '</svg><small style="color:#9fc2d9;font-size:9px">Cyan: '+esc(away)+' · Fiolet: '+esc(home)+' · końce kwart</small>';
}
function lastGamesForTeams(data,game){
 const known=allKnownGames(data),t=String(game.start||"");
 return known.filter(g=>g.state==="final"&&Number.isInteger(g.away_score)&&Number.isInteger(g.home_score)&&String(g.id)!==String(game.id)&&
   String(g.start||"")<t&&(g.away===game.away||g.home===game.away||g.away===game.home||g.home===game.home))
   .sort((a,b)=>String(b.start).localeCompare(String(a.start))).slice(0,5);
}
function recentMeetings(data,game){return lastGamesForTeams(data,game).filter(g=>
 (g.away===game.away&&g.home===game.home)||(g.away===game.home&&g.home===game.away));}
/* The short Centrum fixture window is not a season-long H2H.
   Use separately verified ESPN team schedules once a game is selected. */
function historyMarkup(data,game){
 const active=lastDetails?.id===String(game.id)&&lastDetails?.day===selectedDay
   &&lastDetails?.data?.away===game.away&&lastDetails?.data?.home===game.home;
 const history=active?lastDetails.data.history:null;
 const official=history&&Array.isArray(history.h2h)&&history.recent;
 const renderRows=games=>
  '<div class="hzv-history-list">'+games.map(g=>
   '<div class="hzv-history-row"><time class="hzv-history-date" datetime="'+esc(localDay(g.start))+'">'+
    esc(fullHistoryDate(g.start))+'</time>'+
   '<span class="hzv-history-matchup">'+
    '<span class="hzv-history-participant">'+teamLogo(data,g.away,g,"away")+'<b>'+esc(g.away)+'</b></span>'+
    '<span class="hzv-history-versus">–</span>'+
    '<span class="hzv-history-participant">'+teamLogo(data,g.home,g,"home")+'<b>'+esc(g.home)+'</b></span>'+
   '</span>'+
   '<strong class="hzv-history-score">'+Number(g.away_score)+' : '+Number(g.home_score)+'</strong></div>').join("")+'</div>';
 if(official){
  const coverage=Array.isArray(history.coverage)?history.coverage:[];
  if(historyTab==="h2h"){
   const games=history.h2h.filter(g=>g.state==="final"&&Number.isInteger(g.away_score)&&Number.isInteger(g.home_score));
   if(games.length)return renderRows(games);
   return '<div class="hzv-history-empty">'+(history.error?esc(history.error):
    'Brak potwierdzonych wcześniejszych spotkań tych drużyn w pobranych sezonach ESPN.')+
    (coverage.length?'<small class="hzv-history-coverage"> Zweryfikowano '+esc([...new Set(coverage.map(x=>x.season-1+"/"+String(x.season).slice(-2)))].join(", "))+'.</small>':'')+'</div>';
  }
  const recent=history.recent||{};
  const teams=[game.away,game.home];
  const panels=teams.map(team=>{
   const games=(Array.isArray(recent[team])?recent[team]:[]).filter(g=>
    g?.state==="final"&&Number.isInteger(g.away_score)&&Number.isInteger(g.home_score));
   return '<div class="hzv-history-team"><h3>'+teamLogo(data,team,null,"home")+esc(team)+' · ostatnie mecze</h3>'+
    (games.length?renderRows(games):'<p class="hzv-history-empty">Brak potwierdzonych spotkań.</p>')+'</div>';
  });
  if(panels.some(panel=>panel.includes("hzv-history-row")))return panels.join("");
  return '<p class="hzv-history-empty">'+esc(history.error||"Brak potwierdzonych poprzednich meczów w pobranej historii ESPN.")+'</p>';
 }
 // Before the on-demand history arrives, never present a short cached
 // scoreboard selection as though it were complete historical coverage.
 if(active)return '<p class="hzv-history-empty">Pobieranie potwierdzonej historii ESPN…</p>';
 if(lastDetails?.id===String(game.id)&&lastDetails?.day===selectedDay&&lastDetails?.error){
  return '<p class="hzv-history-empty">Historia ESPN jest chwilowo niedostępna. <button type="button" class="hzv-retry-button" data-hzv-retry-game="'+esc(game.id)+'">Ponów pobieranie historii</button></p>';
 }
 return '<p class="hzv-history-empty">'+(game.state==="scheduled"?
  'Pobieranie Head to Head i ostatnich meczów z ESPN…':
  'Pobieranie historii bezpośrednich spotkań i ostatnich meczów z ESPN…')+'</p>';
}
/* Verified ESPN data only. For turnovers and fouls fewer is favorable. */
function teamComparisonMarkup(metrics,data,away,home,game){
 const team=(code,side)=>'<div class="hzv-compare-team hzv-compare-'+side+'">'+
  teamLogo(data,code,game,side)+'<span><strong>'+esc(code)+'</strong><small>'+esc(codeLabel(data,code))+'</small></span></div>';
 const rows=metrics.map(item=>{
  const label=String(item?.label??"").trim(),rawA=String(item?.away??"").trim(),rawH=String(item?.home??"").trim();
  if(!label||!rawA||!rawH)return "";
  const valid=/^\d+(?:[.,]\d+)?%?$/.test(rawA)&&/^\d+(?:[.,]\d+)?%?$/.test(rawH);
  const a=valid?Number(rawA.replace("%","").replace(",",".")):NaN;
  const h=valid?Number(rawH.replace("%","").replace(",",".")):NaN;
  const good=Number.isFinite(a)&&Number.isFinite(h)&&a>=0&&h>=0;
  const percent=label.includes("%")||rawA.endsWith("%")||rawH.endsWith("%");
  const lowerBetter=/^(straty|faule)$/i.test(label);
  const advantage=good&&a!==h?(lowerBetter?(a<h?"away":"home"):(a>h?"away":"home")):"tie";
  const max=percent?100:Math.max(a||0,h||0,1);
  const width=v=>good?Math.round(10*Math.min(100,Math.max(0,100*v/max)))/10:0;
  return '<div class="hzv-compare-row" data-hzv-metric="'+esc(label)+'" data-hzv-advantage="'+advantage+'">'+
   '<div class="hzv-compare-values"><strong'+(advantage==="away"?' class="is-leading"':'')+'>'+esc(rawA)+'</strong>'+
   '<span>'+esc(label)+'</span><strong'+(advantage==="home"?' class="is-leading"':'')+'>'+esc(rawH)+'</strong></div>'+
   '<div class="hzv-compare-bars" aria-label="'+esc(away+" "+rawA+", "+home+" "+rawH)+'">'+
    '<span class="hzv-compare-track hzv-compare-track-away">'+(good?'<i class="hzv-compare-fill hzv-compare-fill-away" style="width:'+width(a)+'%"></i>':'')+'</span>'+
    '<span class="hzv-compare-track hzv-compare-track-home">'+(good?'<i class="hzv-compare-fill hzv-compare-fill-home" style="width:'+width(h)+'%"></i>':'')+'</span>'+
   '</div></div>';
 }).filter(Boolean).join("");
 return '<section class="hzv-compare-panel" aria-label="Porównanie drużyn NBA">'+
 '<div class="hzv-compare-title"><h3>▥ STATYSTYKI DRUŻYN</h3><span>ESPN · BOX SCORE</span></div>'+
 '<div class="hzv-compare-teams">'+team(away,"away")+'<b>VS</b>'+team(home,"home")+'</div>'+
 '<div class="hzv-compare-stats">'+rows+'</div>'+
 '<div class="hzv-compare-legend"><span><i class="hzv-dot-away"></i>'+esc(away)+'</span>'+
 '<small>% do 100 · pozostałe: skala wiersza</small>'+
 '<span><i class="hzv-dot-home"></i>'+esc(home)+'</span></div></section>';
}
function scoreFallbackGraph(game){
 if(!Number.isInteger(game.away_score)||!Number.isInteger(game.home_score))
  return '<p class="hzv-history-empty">Brak potwierdzonego wykresu kwartowego ESPN.</p>';
 const a=game.away_score,h=game.home_score,max=Math.max(a,h,1);
 return '<div class="hzv-xfactor-final" role="img" aria-label="'+esc("Wynik końcowy "+game.away+" "+a+", "+game.home+" "+h)+'">'+
  '<p>Przebieg kwartowy niedostępny. Wynik końcowy:</p>'+
  '<div class="hzv-xfactor-final-row"><b>'+esc(game.away)+'</b><div class="hzv-xfactor-final-track"><i class="hzv-xfactor-final-away" style="width:'+(100*a/max).toFixed(1)+'%"></i></div><strong>'+a+'</strong></div>'+
  '<div class="hzv-xfactor-final-row"><b>'+esc(game.home)+'</b><div class="hzv-xfactor-final-track"><i class="hzv-xfactor-final-home" style="width:'+(100*h/max).toFixed(1)+'%"></i></div><strong>'+h+'</strong></div>'+
 '</div>';
}
function pregameMarkup(data,game){
 const away=String(game.away||""),home=String(game.home||"");
 const status='<section class="hzv-game-card hzv-game-summary hzv-pregame-summary">'+
  '<div class="hzv-game-ribbon">✦ NADCHODZĄCY MECZ NBA ✦</div>'+
  '<div class="hzv-pregame-teams">'+
   '<div>'+teamLogo(data,away,game,"away")+'<strong>'+esc(away)+'</strong></div>'+
   '<span>VS</span>'+
   '<div>'+teamLogo(data,home,game,"home")+'<strong>'+esc(home)+'</strong></div></div>'+
  '<p class="hzv-pregame-time">◷ '+esc(fullHistoryDate(game.start))+' · '+esc(localTime(game.start))+'</p>'+
  '<div class="hzv-pregame-notice"><span aria-hidden="true">◷</span>'+
   '<h2>Mecz jeszcze się nie rozpoczął</h2>'+
   '<p>Statystyki drużyn, X-Factor i przebieg punktacji będą dostępne po meczu.</p></div></section>';
 const right='<section class="hzv-game-card hzv-gc-history hzv-pregame-history">'+
  '<h2 class="hzv-pregame-history-title">Historia drużyn</h2>'+
  '<div class="hzv-history-tabs" role="group" aria-label="Historia spotkań">'+
   '<button type="button" data-hzv-history="h2h" class="'+(historyTab==="h2h"?"selected":"")+'">Head to Head</button>'+
   '<button type="button" data-hzv-history="recent" class="'+(historyTab==="recent"?"selected":"")+'">Ostatnie mecze</button></div>'+
  '<div id="hzv-history-results">'+historyMarkup(data,game)+'</div></section>';
 return status+right;
}
function detailsMarkup(data,game,packet){
 if(game.state==="scheduled")return pregameMarkup(data,game);
 const away=String(game.away||""),home=String(game.home||"");
 const statsAway=verified(data,away),statsHome=verified(data,home);
 const packetForGame=packet?.id===String(game.id)&&packet?.day===selectedDay?packet:null;
 const details=packetForGame?.data?.away===away&&packetForGame?.data?.home===home?packetForGame.data:null;
 const loading=game.state!=="scheduled"&&!details&&!packetForGame?.error;
 const quarters=Array.isArray(details?.quarters)?details.quarters.filter(q=>Number.isInteger(q.away)&&Number.isInteger(q.home)):[];
 const metrics=Array.isArray(details?.team_stats)?details.team_stats:[];
 const leaderRows=[...(details?.leaders?.away||[]).map(p=>({...p,team:away})),...(details?.leaders?.home||[]).map(p=>({...p,team:home}))];
 leaderRows.sort((a,b)=>b.pts-a.pts||b.reb-a.reb);
 const leader=leaderRows[0]||null;
 let periodChange="Kluczowe momenty wymagają potwierdzonych danych play-by-play.";
 if(quarters.length>=2){
  let prevDiff=0,maxChange=0,changedPeriod="";
  let a=0,h=0;for(const q of quarters){a+=q.away;h+=q.home;const diff=h-a;const swing=Math.abs(diff-prevDiff);
   if(swing>maxChange){maxChange=swing;changedPeriod=q.period;}prevDiff=diff;}
  periodChange="Największa zmiana różnicy punktów między końcami kwart: "+maxChange+" pkt ("+changedPeriod+").";
 }
 const first='<section class="hzv-game-card hzv-game-summary">'+
 '<div class="hzv-game-ribbon">✦ MECZ NBA ✦</div>'+
 '<div class="hzv-game-scoreboard"><div class="hzv-gc-team">'+teamLogo(data,away,game,"away")+
 '<strong>'+esc(away)+'</strong><small>'+esc(codeLabel(data,away))+'</small><span>'+esc(statsAway?statsAway.wins+"–"+statsAway.losses:"—")+' W–L</span></div>'+
 '<div class="hzv-gc-score"><strong>'+esc(score(game))+'</strong><em>'+esc(badge(game))+'</em></div>'+
 '<div class="hzv-gc-team">'+teamLogo(data,home,game,"home")+
 '<strong>'+esc(home)+'</strong><small>'+esc(codeLabel(data,home))+'</small><span>'+esc(statsHome?statsHome.wins+"–"+statsHome.losses:"—")+' W–L</span></div></div>'+
 '<div class="hzv-game-meta"><span>◷ '+esc(game.state==="scheduled"?"Rozpoczęcie "+localTime(game.start):"Czas "+localTime(game.start))+'</span>'+
 '<span>▦ '+esc(shortDate(game.day||selectedDay))+'</span>'+
 (details?.arena?'<span>⌖ '+esc(details.arena)+'</span>':'')+'</div>'+
 (quarters.length?'<div class="hzv-quarter-table"><h3>Przebieg meczu · kwarty</h3><div style="--quarter-count:'+Math.min(quarters.length+1,9)+'" class="hzv-quarter-row hzv-quarter-head"><span>Drużyna</span>'+quarters.map(q=>'<span>'+esc(q.period)+'</span>').join("")+'<span>SUMA</span></div>'+
 ['away','home'].map(side=>'<div style="--quarter-count:'+Math.min(quarters.length+1,9)+'" class="hzv-quarter-row"><strong>'+esc(game[side])+'</strong>'+quarters.map(q=>'<span>'+esc(q[side])+'</span>').join("")+
 '<span>'+quarters.reduce((sum,q)=>sum+q[side],0)+'</span></div>').join("")+'</div>':'')+
 (metrics.length?teamComparisonMarkup(metrics,data,away,home,game):'<div class="hzv-history-empty">'+(game.state==="scheduled"?"Spotkanie jeszcze się nie rozpoczęło — statystyki będą dostępne po ich publikacji przez ESPN.":packetForGame?.error?esc(packetForGame.error):loading?"Pobieranie zweryfikowanego box score ESPN…":"Brak potwierdzonych statystyk drużyn.")+
 (packetForGame?.error?'<div><button type="button" class="hzv-retry-button" data-hzv-retry-game="'+esc(game.id)+'">Ponów pobieranie statystyk</button></div>':"")+'</div>')+
 '<p class="hzv-game-source">Źródło: ESPN · statystyki historyczne, bez symulacji i prognoz'+(details?.stale?' · dane opóźnione':'')+'</p>'+
 '</section>';
 const right='<div class="hzv-gc-right"><section class="hzv-game-card hzv-gc-xfactor">'+
 '<h2 class="hzv-xfactor-title"><span>ϟ</span> X-FACTOR MECZU</h2>'+
 '<div class="hzv-xfactor-body"><div class="hzv-xfactor-player">'+
 (leader?'<span class="hzv-xfactor-avatar" aria-hidden="true">'+esc(initials(leader.name))+'</span>'+
  '<strong>'+esc(leader.name)+'</strong><small>'+esc(leader.team)+' · lider punktowy</small>'+
  '<small>'+leader.pts+' PTS · '+leader.reb+' REB · '+leader.ast+' AST</small>':
  '<p class="hzv-history-empty">Brak potwierdzonego lidera punktowego.</p>')+
 '</div><div class="hzv-xfactor-chart"><h3>'+(quarters.length?"Przebieg punktacji":"Porównanie punktów")+'</h3>'+
 (quarters.length?quarterGraph(quarters,away,home):scoreFallbackGraph(game))+'</div></div>'+
 '<div class="hzv-gc-callout"><b>✦ KLUCZOWY MOMENT</b><span>'+esc(periodChange)+'</span></div>'+
 '</section><section class="hzv-game-card hzv-gc-history">'+
 '<div class="hzv-history-tabs" role="group" aria-label="Porównanie historyczne">'+
 '<button type="button" data-hzv-history="h2h" class="'+(historyTab==="h2h"?"selected":"")+'">Head to Head</button>'+
 '<button type="button" data-hzv-history="recent" class="'+(historyTab==="recent"?"selected":"")+'">Ostatnie mecze</button></div>'+
 '<div id="hzv-history-results">'+historyMarkup(data,game)+'</div>'+
 '</section></div>';
 return first+right;
}
function renderGamePage(){
 const pane=$("schedule-pane"),page=$("hzv-game-page"),content=$("hzv-game-content");
 if(!pane||!page||!content)return;
 const game=selectedGameId&&lastData?gameFromSelected(lastData):null;
 const active=Boolean(game);
 pane.classList.toggle("hzv-show-game",active);page.hidden=!active;
 if(active){
  try{
   content.innerHTML=detailsMarkup(lastData,game,lastDetails);
  }catch(_){
   // Never leave a blank screen without a working Back button.
   content.innerHTML='<section class="hzv-game-card"><h2 class="hzv-gc-subheading">Szczegóły meczu</h2>'+
    '<p class="hzv-history-empty">Nie udało się wyświetlić wszystkich szczegółów. Wróć do Terminarza i spróbuj ponownie.</p></section>';
  }
  if(renderedGameId!==selectedGameId){
   renderedGameId=selectedGameId;
   const container=$("hzv-game-page");if(container)container.scrollTop=0;
  }
 }else{renderedGameId="";}
}
function render(data,packet){
 lastData=data;lastDetails=packet||null;
 if(!selectedDay)selectedDay=safeDay(data?.calendar_today)?data.calendar_today:today();
 dateNavigation();syncFilters();standings(data,"east");standings(data,"west");
 if(selectedGameId)renderGamePage();else{
  const pane=$("schedule-pane");pane?.classList.remove("hzv-show-game");
  if($("hzv-game-page"))$("hzv-game-page").hidden=true;
 }
 renderBoard(data);
}
function openGame(id){
 if(!lastData)return;const game=selectedGames(lastData).games.find(g=>String(g.id||"")===id);if(!game)return;
 selectedGameId=id;historyTab="h2h";toggleCalendar(false);
 saveOpenGame({id,day:selectedDay});
 if(!lastDetails||lastDetails.id!==id||lastDetails.day!==selectedDay){
  if(requestedDetailsId!==id){requestedDetailsId=id;callback?.gameDetails?.({game_id:id,date:selectedDay});}
 }
 renderGamePage();const page=$("hzv-game-page");if(page)page.scrollTop=0;
}
function closeGame(){selectedGameId="";requestedDetailsId="";renderedGameId="";saveOpenGame(null);$("schedule-pane")?.classList.remove("hzv-show-game");
 $("hzv-game-page").hidden=true;renderBoard(lastData);$("hzv-featured-button")?.focus({preventScroll:true});}
function init(api){
 callback=api;
 $("hzs-board")?.addEventListener("click",event=>{
  const starBtn=event.target.closest("[data-hzs-star]");
  if(starBtn){const code=starBtn.dataset.hzsStar;if(!VALID.has(code))return;
   if(favorites.has(code))favorites.delete(code);else favorites.add(code);
   persistFavorites();renderBoard(lastData);
   const replacement=[...document.querySelectorAll("#hzs-board [data-hzs-star]")].find(el=>
    el.dataset.hzsStar===code&&el.dataset.hzsStarGame===starBtn.dataset.hzsStarGame);
   replacement?.focus({preventScroll:true});return;
  }
  const button=event.target.closest("[data-hzs-game]");if(button)openGame(button.dataset.hzsGame);
 });
 $("hzv-hero")?.addEventListener("click",event=>{const btn=event.target.closest("[data-hzs-game]");if(btn)openGame(btn.dataset.hzsGame)});
 $("hzv-game-back")?.addEventListener("click",closeGame);
 $("hzv-game-content")?.addEventListener("click",event=>{
  const retry=event.target.closest("[data-hzv-retry-game]");
  if(retry&&retry.dataset.hzvRetryGame===selectedGameId&&withinRange(selectedDay)){
   requestedDetailsId=selectedGameId;
   lastDetails=null;
   renderGamePage();
   callback?.gameDetails?.({game_id:selectedGameId,date:selectedDay});
   return;
  }
  const button=event.target.closest("[data-hzv-history]");if(!button)return;
  if(!["h2h","recent"].includes(button.dataset.hzvHistory))return;
  historyTab=button.dataset.hzvHistory;
  document.querySelectorAll("[data-hzv-history]").forEach(b=>b.classList.toggle("selected",b.dataset.hzvHistory===historyTab));
  const game=gameFromSelected(lastData);
  if(game&&$("hzv-history-results"))$("hzv-history-results").innerHTML=historyMarkup(lastData,game);
 });
 document.querySelector(".hzs-filters")?.addEventListener("click",event=>{
  const button=event.target.closest("[data-hzs-filter]");if(!button||selectedFilter===button.dataset.hzsFilter)return;
  selectedFilter=button.dataset.hzsFilter;syncFilters();renderBoard(lastData);
 });
 $("hzs-date-strip")?.addEventListener("click",event=>{
  const button=event.target.closest("[data-hzs-day]");if(button&&!button.disabled)selectDay(button.dataset.hzsDay);
 });
 document.querySelectorAll("#schedule-pane [data-hzs-direction]").forEach(b=>
  b.addEventListener("click",()=>selectDay(shiftDay(selectedDay,Number(b.dataset.hzsDirection)))));
 $("hzs-today")?.addEventListener("click",()=>selectDay(today()));
 $("hzv-search")?.addEventListener("input",event=>{searchText=event.target.value.slice(0,100);renderBoard(lastData)});
 $("hzv-calendar-toggle")?.addEventListener("click",()=>toggleCalendar($("hzv-calendar-popup").hidden));
 $("hzv-calendar-popup")?.addEventListener("click",event=>{
  const month=event.target.closest("[data-hzv-month]");
  if(month){const d=noon(monthView);d.setUTCMonth(d.getUTCMonth()+Number(month.dataset.hzvMonth));monthView=d.toISOString().slice(0,7)+"-01";renderCalendar();return;}
  const date=event.target.closest("[data-hzv-calendar-day]");
  if(date&&!date.disabled)selectDay(date.dataset.hzvCalendarDay);
 });
 document.querySelectorAll("[data-hzv-table]").forEach(b=>b.addEventListener("click",()=>{
  const which=b.dataset.hzvTable;
  if(expandedTables.has(which))expandedTables.delete(which);else expandedTables.add(which);
  b.closest(".hzv-standing-card")?.classList.toggle("hzv-expanded",expandedTables.has(which));
  standings(lastData,which);
 }));
 document.addEventListener("click",event=>{
  if(!$("hzv-calendar-popup")?.hidden&&!event.target.closest(".hzv-week-panel"))toggleCalendar(false);
 });
 document.addEventListener("keydown",event=>{
  if(event.key==="Escape"&&!$("hzv-calendar-popup")?.hidden){toggleCalendar(false);$("hzv-calendar-toggle")?.focus();}
  else if(event.key==="Escape"&&selectedGameId&&$("schedule-pane")&&!$("schedule-pane").hidden)closeGame();
 });
}
window.HoopzaroSchedule={
 init,render,
 hasRestorableGame:()=>Boolean(readOpenGame()),
 dismissOnNavigation:()=>{selectedGameId="";requestedDetailsId="";renderedGameId="";saveOpenGame(null);}
};
})();
