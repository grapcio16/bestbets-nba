/* Lazy full-NBA player catalog for the Centrum watch panel.
   Loaded only on demand; intentionally never delays public first paint. */
(function(){
"use strict";
const $=id=>document.getElementById(id);
const KEY="bestbets.centrum.watchedPlayers.v1";
let catalog=null,api=null,isOpen=false,filter="",nativeWatch="";
let favorites=[];
try{
 const rows=JSON.parse(localStorage.getItem(KEY)||"[]");
 if(Array.isArray(rows)){
  const seen=new Set();
  favorites=rows.filter(p=>{
   if(!p||!/^\d+$/.test(String(p.id||""))||typeof p.name!=="string"||
      !p.name.trim()||seen.has(String(p.id)))return false;
   seen.add(String(p.id));return true;
  }).slice(0,3).map(p=>({id:String(p.id),name:String(p.name).slice(0,90),team:String(p.team||"").slice(0,4)}));
 }
}catch(_){}
const escape=s=>String(s||"").replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
function save(){try{localStorage.setItem(KEY,JSON.stringify(favorites));}catch(_){}}
function watch(){
 const node=$("bestbets-centre")?.querySelector(".bc-watch");
 if(!node||!favorites.length)return;
 const selected=new Set(favorites.map(p=>p.name.toLocaleLowerCase("pl-PL")));
 const rows=favorites.map(p=>
  '<button type="button" data-centre-nav="props" title="Otwórz Player Props i wybierz linię">'+
  '<b>'+escape(p.name.trim().split(/\s+/).slice(0,2).map(x=>x[0]).join(""))+'</b>'+
  escape(p.name)+' <small>· '+escape(p.team)+'</small><span>›</span></button>');
 const rest=document.createElement("div");
 rest.innerHTML=nativeWatch;
 for(const b of rest.querySelectorAll("button")){
  if(rows.length>=3)break;
  const title=b.textContent.trim().toLocaleLowerCase("pl-PL");
  if([...selected].some(name=>title.includes(name)))continue;
  rows.push(b.outerHTML);
 }
 node.innerHTML=rows.join("");
}
function options(){
 const node=$("bc-players-picker"),toggle=$("bc-players-toggle");
 if(!node||!toggle)return;
 toggle.setAttribute("aria-expanded",String(isOpen));
 if(!isOpen){node.hidden=true;return;}
 node.hidden=false;
 const people=Array.isArray(catalog?.players)?catalog.players:[];
 const meta=catalog?.coverage||{};
 const chosen=new Set(favorites.map(p=>p.id));
 const needle=filter.trim().toLocaleLowerCase("pl-PL");
 const matches=people.filter(p=>(String(p.name||"")+" "+String(p.team||"")).toLocaleLowerCase("pl-PL").includes(needle));
 matches.sort((a,b)=>Number(chosen.has(String(b.id)))-Number(chosen.has(String(a.id)))||
  String(a.name).localeCompare(String(b.name),"pl"));
 const missing=[...(meta.missing_teams||[]),...(meta.sparse_teams||[])];
 const error=missing.length
  ?'<p class="bc-catalog-note">Część składów ESPN może być niepełna: '+escape([...new Set(missing)].join(", "))+'</p>'
  :'';
 const rows=matches.map(p=>{
  const id=String(p.id),on=chosen.has(id);
  return '<div class="bc-catalog-athlete'+(on?' active':'')+'">'+
   '<span><strong>'+escape(p.name)+'</strong><small>'+escape(p.team)+'</small></span>'+
   '<button type="button" data-bb-watch-id="'+escape(id)+'" class="bc-form-star'+(on?' is-favorite':'')+
   '" title="'+(on?'Usuń z obserwowanych':'Dodaj do obserwowanych')+
   '" aria-pressed="'+String(on)+'">'+(on?'★':'☆')+'</button></div>';
 }).join("");
 const info=!catalog?'Pobieranie pełnej listy NBA z ESPN…':
  catalog.error?escape(catalog.error):
  !people.length?'ESPN nie zwrócił katalogu zawodników.':
  !matches.length?'Brak pasujących nazwisk.':'';
 const oldScroll=node.querySelector(".bc-catalog-list")?.scrollTop||0;
 node.innerHTML=
  '<div class="bc-catalog-head"><b>Wszyscy zawodnicy NBA</b><span>'+favorites.length+'/3</span></div>'+
  '<div class="bc-catalog-meta">'+people.length+' graczy · '+(meta.teams_loaded||0)+'/30 drużyn</div>'+error+
  '<input id="bc-players-search" autocomplete="off" type="search" maxlength="70"'+
  ' placeholder="Znajdź zawodnika lub drużynę…" value="'+escape(filter)+'" aria-label="Wyszukaj gracza">'+
  '<div class="bc-catalog-help" id="bc-catalog-help">Kliknij ☆, aby obserwować zawodnika.</div>'+
  '<div class="bc-catalog-list">'+(rows||'<div class="bc-muted">'+info+'</div>')+'</div>';
 const list=node.querySelector(".bc-catalog-list");
 if(list)list.scrollTop=oldScroll;
}
function toggleFavorite(id){
 const target=(catalog?.players||[]).find(p=>String(p.id)===id);
 if(!target)return;
 if(favorites.some(p=>p.id===id))favorites=favorites.filter(p=>p.id!==id);
 else if(favorites.length>=3){
  const msg=$("bc-catalog-help");if(msg){msg.textContent="Maksymalnie 3 obserwowani. Najpierw odznacz jednego.";msg.classList.add("bc-form-limit");}
  return;
 }else favorites.push({id:String(target.id),name:target.name,team:target.team});
 save();watch();options();
}
function install(){
 const centre=$("bestbets-centre");
 if(!centre||centre.dataset.playerPickerReady)return;
 centre.dataset.playerPickerReady="1";
 centre.addEventListener("click",ev=>{
  const button=ev.target.closest("button");
  if(!button)return;
  if(button.matches("[data-centre-players-toggle]")){
   isOpen=!isOpen;
   options();
   if(isOpen&&!catalog&&api?.loadPlayers)api.loadPlayers();
   return;
  }
  const id=button.getAttribute("data-bb-watch-id");
  if(id!==null){ev.stopPropagation();toggleFavorite(id);}
 });
 centre.addEventListener("input",ev=>{
  if(ev.target.id!=="bc-players-search")return;
  filter=ev.target.value.slice(0,70);
  const cursor=ev.target.selectionStart;
  options();
  const input=$("bc-players-search");
  if(input){input.focus();input.setSelectionRange(cursor,cursor);}
 });
 document.addEventListener("click",ev=>{
  if(isOpen&&!ev.target.closest("#bestbets-centre .bc-player-panel")){
   isOpen=false;options();
  }
 });
 document.addEventListener("keydown",ev=>{
  if(ev.key==="Escape"&&isOpen){isOpen=false;options();$("bc-players-toggle")?.focus();}
 });
}
if(!window.BestBetsCentre)return;
const originalInit=window.BestBetsCentre.init,originalRender=window.BestBetsCentre.render;
window.BestBetsCentre.init=function(ctx){api=ctx;originalInit(ctx);install();};
window.BestBetsCentre.render=function(data,players){
 originalRender(data);
 if(players&&typeof players==="object")catalog=players;
 const watchBox=$("bestbets-centre")?.querySelector(".bc-watch");
 if(watchBox){nativeWatch=watchBox.innerHTML;watch();}
 options();
};
})();
