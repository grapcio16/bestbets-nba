/* HOOPZARO Teams: all 30 real team identities, original unlicensed monograms.
   Free records must be ESPN-verified. The paid analytics object is supplied
   only by the Streamlit server after a verified account entitlement. */
(function(global){
"use strict";
const $=id=>document.getElementById(id);
const FAV_KEY="bestbets.centrum.favoriteTeams.v1",PAGE_SIZE=9;
// Immutable team identities and conference membership, not sports results.
const DATA=[
 ["ATL","Atlanta Hawks","east","255,91,85","#ff7364","A"],
 ["BOS","Boston Celtics","east","27,242,164","#27f2a4","B"],
 ["BKN","Brooklyn Nets","east","200,208,233","#ced9f3","N"],
 ["CHA","Charlotte Hornets","east","58,210,231","#3ad2e7","C"],
 ["CHI","Chicago Bulls","east","252,80,113","#fc5071","C"],
 ["CLE","Cleveland Cavaliers","east","244,172,85","#f4ac55","C"],
 ["DAL","Dallas Mavericks","west","75,171,255","#4babff","D"],
 ["DEN","Denver Nuggets","west","255,210,87","#ffd257","D"],
 ["DET","Detroit Pistons","east","87,143,255","#578fff","D"],
 ["GSW","Golden State Warriors","west","45,164,255","#2da4ff","W"],
 ["HOU","Houston Rockets","west","244,89,118","#f45976","H"],
 ["IND","Indiana Pacers","east","255,200,90","#ffc85a","I"],
 ["LAC","Los Angeles Clippers","west","87,157,255","#579dff","C"],
 ["LAL","Los Angeles Lakers","west","204,111,255","#cc6fff","L"],
 ["MEM","Memphis Grizzlies","west","109,192,255","#6dc0ff","M"],
 ["MIA","Miami Heat","east","255,127,80","#ff7f50","M"],
 ["MIL","Milwaukee Bucks","east","59,206,161","#3bcea1","M"],
 ["MIN","Minnesota Timberwolves","west","102,166,235","#66a6eb","M"],
 ["NOP","New Orleans Pelicans","west","121,180,250","#79b4fa","N"],
 ["NYK","New York Knicks","east","255,142,57","#ff8e39","N"],
 ["OKC","Oklahoma City Thunder","west","24,229,251","#18e5fb","T"],
 ["ORL","Orlando Magic","east","52,132,255","#3484ff","O"],
 ["PHI","Philadelphia 76ers","east","124,173,255","#7cadff","P"],
 ["PHX","Phoenix Suns","west","202,99,255","#ca63ff","P"],
 ["POR","Portland Trail Blazers","west","255,108,108","#ff6c6c","P"],
 ["SAC","Sacramento Kings","west","179,115,255","#b373ff","S"],
 ["SAS","San Antonio Spurs","west","172,218,246","#acdaf6","S"],
 ["TOR","Toronto Raptors","east","250,95,106","#fa5f6a","T"],
 ["UTA","Utah Jazz","west","240,211,93","#f0d35d","U"],
 ["WAS","Washington Wizards","east","112,162,255","#70a2ff","W"]
].map(([code,name,conference,rgb,accent,mark])=>({code,name,conference,rgb,accent,mark}));
const byCode=new Map(DATA.map(team=>[team.code,team]));
const featured=["BOS","GSW","NYK","LAL","OKC","DEN"];
const nf=s=>String(s||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
const fmt=n=>typeof n==="number"&&Number.isFinite(n)?n.toFixed(1).replace(".",","):"—";
const observed=n=>typeof n==="number"&&Number.isFinite(n)?fmt(n):"Brak danych";
let api={},home=null,analytics=null,role="guest",conference="all",query="",page=0,selected="BOS",compare="",message="";
const ratingPending=new Set();
const entitled=()=>role==="premium"||role==="admin";
const hasRatings=row=>["off","def","pace"].every(key=>typeof row?.[key]==="number"&&Number.isFinite(row[key]));
const ratingValue=(value,row)=>typeof value==="number"&&Number.isFinite(value)?fmt(value):
  row?.rating_attempted?"Brak danych":"Pobieranie…";
function requestMissingRating(code){
 if(!entitled()||!analytics?.teams||!byCode.has(code)||typeof api.requestAdvanced!=="function")return;
 const row=analytics.teams[code];
 if(hasRatings(row)||row?.rating_attempted||ratingPending.has(code))return;
 ratingPending.add(code);api.requestAdvanced(code);
}
function favorites(){
 try{const raw=JSON.parse(localStorage.getItem(FAV_KEY)||"[]");
   return Array.isArray(raw)?[...new Set(raw.filter(code=>byCode.has(code)))].slice(0,2):[];
 }catch(_){return []}
}
function record(team){
 const option=(Array.isArray(home?.form_options)?home.form_options:[]).find(row=>row?.team===team.code);
 return option?.record_verified===true && Number.isInteger(option.wins) &&
   Number.isInteger(option.losses) && option.wins>=0 && option.losses>=0
   ?`${option.wins}–${option.losses}`:"—";
}
function candidates(){
 const favs=favorites();return DATA.filter(team=>
   (conference==="all"||team.conference===conference)&&
   (!query||nf(team.code).includes(nf(query))||nf(team.name).includes(nf(query))))
   .sort((a,b)=>{
     const x=favs.indexOf(a.code),y=favs.indexOf(b.code);
     if(x>=0||y>=0)return x<0?1:y<0?-1:x-y;
     const i=featured.indexOf(a.code),j=featured.indexOf(b.code);
     if(i>=0||j>=0)return i<0?1:j<0?-1:i-j;
     return a.name.localeCompare(b.name,"en");
   });
}
function markup(team){
 const fav=favorites().includes(team.code),isSelected=team.code===selected;
 const conf=team.conference==="east"?"Wschód":"Zachód";
 return `<article class="hzt-team-card${isSelected?" is-selected":""}${fav?" is-favorite":""}"
   style="--hzt-accent:${team.accent};--hzt-rgb:${team.rgb}"
   role="button" tabindex="0" data-hzt-team="${team.code}" aria-pressed="${isSelected}"
   aria-label="Pokaż drużynę ${team.name}">
   <span class="hzt-card-mark" aria-hidden="true">${team.mark}</span>
   <span class="hzt-card-body"><span class="hzt-card-code">${team.code}</span>
   <strong title="${team.name}">${team.name}</strong><small>Konferencja: <em>${conf}</em></small>
   <span class="hzt-record">Bilans W–L: ${record(team)}</span></span>
   <button type="button" class="hzt-card-fav${fav?" is-favorite":""}" data-hzt-fav="${team.code}"
   aria-pressed="${fav}" aria-label="${fav?"Usuń":"Dodaj"} ${team.name} ${fav?"z":"do"} ulubionych"
   title="${fav?"Usuń z ulubionych":"Dodaj do ulubionych"}">${fav?"★":"☆"}</button></article>`;
}
function feature(){
 const team=byCode.get(selected)||DATA[0];
 const mark=$("hzt-feature-mark");mark.textContent=team.mark;mark.style.setProperty("--hzt-accent",team.accent);
 const spotlight=mark.closest(".hzt-spotlight");spotlight.style.setProperty("--hzt-spotlight-rgb",team.rgb);spotlight.style.setProperty("--hzt-spotlight-accent",team.accent);
 const featureName=$("hzt-feature-name");featureName.textContent=team.name;featureName.title=team.name;featureName.classList.toggle("hzt-long-name",team.name.length>20);
 $("hzt-feature-conference").textContent=team.conference==="east"?"Wschód":"Zachód";
 $("hzt-feature-record").textContent=record(team);
 $("hzt-feature-status").textContent=home?.form_stale?"Dane ESPN opóźnione":
   home?.form_available?"Sezon "+(home.form_period||"2026/27"):"Bilans sezonu niedostępny";
}
function dialogOpen(){return !$("hzt-modal-backdrop").hidden}
function updateDialog(){
 const team=byCode.get(selected)||DATA[0],dialog=$("hzt-team-dialog");
 dialog.style.setProperty("--hzt-accent",team.accent);
 dialog.style.setProperty("--hzt-rgb",team.rgb);
 $("hzt-modal-mark").textContent=team.mark;
 $("hzt-modal-code").textContent=team.code;
 $("hzt-modal-name").textContent=team.name;
 $("hzt-modal-conference").textContent=team.conference==="east"?"Wschód":"Zachód";
 $("hzt-modal-record").textContent=record(team);
 $("hzt-modal-season").textContent=home?.form_period||"2026/27";
}
function openModal(code){
 if(!byCode.has(code))return;
 selected=code;render(home,analytics,role);updateDialog();
 $("hzt-modal-backdrop").hidden=false;
 renderPremium();
 $("hzt-modal-close").focus({preventScroll:true});
}
function closeModal(restoreFocus=true){
 if(!dialogOpen())return;
 $("hzt-modal-backdrop").hidden=true;
 if(restoreFocus){
   const card=$("hzt-team-grid").querySelector(`[data-hzt-team="${selected}"]`);
   if(card)card.focus({preventScroll:true});
 }
}
function onDialogKeydown(event){
 if(!dialogOpen()||!$("hz-paywall-backdrop").hidden)return;
 if(event.key==="Escape"){
   event.preventDefault();closeModal();return;
 }
 if(event.key!=="Tab")return;
 const controls=[...$("hzt-team-dialog").querySelectorAll("button,select,a[href]")]
   .filter(el=>!el.hidden&&!el.disabled&&el.getClientRects().length);
 if(!controls.length){event.preventDefault();$("hzt-team-dialog").focus();return}
 const first=controls[0],last=controls[controls.length-1];
 if(event.shiftKey&&(document.activeElement===first||!$("hzt-team-dialog").contains(document.activeElement))){
   event.preventDefault();last.focus();
 }else if(!event.shiftKey&&(document.activeElement===last||!$("hzt-team-dialog").contains(document.activeElement))){
   event.preventDefault();first.focus();
 }
}
function metric(label,key,formatter=observed){
 const first=analytics?.teams?.[selected],second=compare?analytics?.teams?.[compare]:null;
 const a=formatter(first?.[key],first),b=compare?formatter(second?.[key],second):null;
 return `<div class="hzt-metric"><small>${label}</small><strong${a==="Brak danych"||a==="Pobieranie…"?' class="hzt-metric-empty"':""}>${a}</strong>${compare?`<em>${compare}: ${b}</em>`:""}</div>`;
}
function renderPremium(){
 const paid=entitled();$("hzt-premium-locked").hidden=paid;$("hzt-premium-unlocked").hidden=!paid;
 $("hzt-premium-cta").hidden=paid;
 $("hzt-premium-intro").textContent=paid?"Ostatnie mecze · dane historyczne":"Odblokuj statystyki i metryki zespołowe";
 if(!paid){$("hzt-premium-metrics").replaceChildren();return}
 const select=$("hzt-compare");
 const options=DATA.filter(t=>t.code!==selected).sort((a,b)=>a.name.localeCompare(b.name));
 select.replaceChildren(new Option("Bez porównania",""));
 options.forEach(team=>select.append(new Option(team.code+" · "+team.name,team.code)));
 compare=options.some(t=>t.code===compare)?compare:"";select.value=compare;
 if(!analytics){$("hzt-premium-metrics").textContent="Ładowanie zweryfikowanych wyników ESPN…";return}
 const first=analytics.teams?.[selected];
 const official=hasRatings(first)&&first.rating_source==="NBA Stats — advanced";
 const estimated=hasRatings(first)&&first.rating_estimated===true;
 const details=first?`L10: ${first.sample} mecz.`:"Brak potwierdzonych wyników drużyny";
 $("hzt-analytics-source").textContent=official?
   `NBA Stats · oficjalne wskaźniki sezonu · ${details}`:estimated?
   `ESPN · szacunek z ${first.rating_sample} boxscore · posiadania ≈ FGA + 0,44×FTA − OREB + TOV`:
   analytics.error||`ESPN · ${details}`;
 $("hzt-premium-intro").textContent=official?
   "Oficjalne NBA Advanced + ostatnie mecze":estimated?
   "OFF/DEF/PACE obliczone z rzeczywistych statystyk meczowych (szacunek)":
   first?.rating_attempted?"Nie udało się pobrać kompletnych boxscore · spróbuj później":
   "Pobieranie OFF/DEF/PACE z rozegranych spotkań…";
 $("hzt-premium-metrics").innerHTML=[metric("PTS / mecz L10","points"),
  metric("Stracone L10","allowed"),metric("OFF RATING","off",ratingValue),
  metric("DEF RATING","def",ratingValue),metric("PACE","pace",ratingValue)].join("");
 if(dialogOpen()){
   requestMissingRating(selected);
   if(compare)requestMissingRating(compare);
 }
}
function render(nextHome,nextAnalytics,nextRole){
 if(String(nextRole||"guest")!==role)ratingPending.clear();
 home=nextHome&&typeof nextHome==="object"?nextHome:null;
 analytics=nextAnalytics&&typeof nextAnalytics==="object"?nextAnalytics:null;
 role=String(nextRole||"guest");
 const rows=candidates(),pages=Math.max(1,Math.ceil(rows.length/PAGE_SIZE));page=Math.min(page,pages-1);
 const visible=rows.slice(page*PAGE_SIZE,(page+1)*PAGE_SIZE);
 $("hzt-team-grid").innerHTML=visible.length?visible.map(markup).join(""):
   '<div class="hzt-no-data">Nie znaleziono drużyny. Zmień filtr lub wyszukiwane hasło.</div>';
 $("hzt-page").textContent=`${page+1} / ${pages}`;
 $("hzt-prev").disabled=page===0;$("hzt-next").disabled=page+1>=pages;
 $("hzt-team-summary").textContent=`${rows.length} zespołów · ★ ${favorites().length}/2 ulubione`;
 $("hzt-team-message").textContent=message;
 document.querySelectorAll("[data-hzt-conference]").forEach(button=>{
   const active=button.dataset.hztConference===conference;
   button.classList.toggle("active",active);button.setAttribute("aria-pressed",String(active));
 });
 feature();renderPremium();
 if(dialogOpen())updateDialog();
}
function toggleFavorite(code){
 const current=favorites();message="";
 if(current.includes(code))current.splice(current.indexOf(code),1);
 else if(current.length>=2){message="Maksymalnie 2 ulubione. Usuń najpierw jedną gwiazdkę.";render(home,analytics,role);return}
 else current.push(code);
 try{localStorage.setItem(FAV_KEY,JSON.stringify(current))}catch(_){}
 global.dispatchEvent(new CustomEvent("hoopzaro:favorites-changed"));
 page=0;render(home,analytics,role);
}
function init(callbacks){
 api=callbacks||{};
 $("hzt-search").addEventListener("input",e=>{query=e.target.value;page=0;message="";render(home,analytics,role)});
 document.querySelectorAll("[data-hzt-conference]").forEach(button=>button.addEventListener("click",()=>{
   conference=button.dataset.hztConference;page=0;message="";render(home,analytics,role)}));
 $("hzt-team-grid").addEventListener("click",e=>{
   const star=e.target.closest("[data-hzt-fav]");
   if(star){e.stopPropagation();toggleFavorite(star.dataset.hztFav);return}
   const card=e.target.closest("[data-hzt-team]");if(card)openModal(card.dataset.hztTeam);
 });
 $("hzt-team-grid").addEventListener("keydown",e=>{
   const card=e.target.closest("[data-hzt-team]");
   if(card&&e.target===card&&(e.key==="Enter"||e.key===" ")){
     e.preventDefault();openModal(card.dataset.hztTeam);
   }
 });
 $("hzt-modal-close").addEventListener("click",()=>closeModal());
 $("hzt-modal-backdrop").addEventListener("click",e=>{
   if(e.target===$("hzt-modal-backdrop"))closeModal();
 });
 document.addEventListener("keydown",onDialogKeydown);
 $("hzt-prev").addEventListener("click",()=>{page=Math.max(0,page-1);render(home,analytics,role)});
 $("hzt-next").addEventListener("click",()=>{page++;render(home,analytics,role)});
 $("hzt-compare").addEventListener("change",e=>{compare=e.target.value;renderPremium()});
 $("hzt-premium-cta").addEventListener("click",()=>api.openPremium?.());
 global.addEventListener("hoopzaro:favorites-changed",()=>render(home,analytics,role));
 global.addEventListener("storage",e=>{if(e.key===FAV_KEY)render(home,analytics,role)});
}
global.HoopzaroTeams={init,render,closeModal,resetRequests:()=>ratingPending.clear()};
})(window);
