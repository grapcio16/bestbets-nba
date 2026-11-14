/* HOOPZARO: use official-style studio headshots by ESPN athlete ID.
   A missing image falls back to credited Wikimedia Commons photographs, then
   to the player's initials. Remote image terms remain the operator's concern. */
(function(){
"use strict";
const COMMONS="https://commons.wikimedia.org/wiki/File:";
const LICENSE_BY="https://creativecommons.org/licenses/by/2.0/";
const LICENSE_BY4="https://creativecommons.org/licenses/by/4.0/";
const LICENSE_CC0="https://creativecommons.org/publicdomain/zero/1.0/";
// Version bump discards negative results written before source metadata was fixed.
const CACHE_KEY="hoopzaro.commonsPortraits.v2";
const DAY=86400000;
const curated=[
 {name:"Alperen Şengün",file:"Alperen Şengün 23 Türkiye 20250823 (18).jpg",artist:"Zafer",license:"CC BY 4.0",licenseUrl:LICENSE_BY4,zoom:2,origin:"50% 15%",position:"center 17%"},
 {name:"Karl-Anthony Towns",file:"Karl-Anthony Towns (51914283512) (square).jpg",artist:"Erik Drost",license:"CC BY 2.0",licenseUrl:LICENSE_BY,zoom:2.15,origin:"50% 9%",position:"center top"},
 {name:"Jayson Tatum",file:"Jayson Tatum (51687926198) (cropped).jpg",artist:"Erik Drost",license:"CC BY-SA 2.0",licenseUrl:"https://creativecommons.org/licenses/by-sa/2.0/",zoom:1.85,origin:"56% 14%",position:"center 15%"},
 {name:"Donovan Mitchell",file:"Donovan Mitchell - 52976499477.jpg",artist:"Erik Drost",license:"CC BY 2.0",licenseUrl:LICENSE_BY},
 {name:"Davion Mitchell",file:"Davion Mitchell.jpg",artist:"LockedIN Magazine",license:"CC BY-SA 2.0",licenseUrl:"https://creativecommons.org/licenses/by-sa/2.0/",zoom:2.15,origin:"53% 43%",position:"center 30%"},
 {name:"Bam Adebayo",file:"Bam-Adebayo.jpg",artist:"Acdixon",license:"CC0 1.0",licenseUrl:LICENSE_CC0,zoom:2,origin:"42% 9%",position:"center top"},
 {name:"Franz Wagner",file:"Franz Wagner Michigan.jpg",artist:"Marc-Grégor Campredon",license:"CC BY 2.0",licenseUrl:LICENSE_BY,zoom:2.05,origin:"50% 40%",position:"center 35%"}
];
const normalized=s=>String(s||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"")
 .toLowerCase().replace(/[^a-z0-9]+/g," ").trim();
const curatedMap=new Map(curated.map(p=>[normalized(p.name),filePortrait(p)]));
function filePortrait(p){
 const encoded=encodeURIComponent(p.file);
 return {url:"https://commons.wikimedia.org/w/thumb.php?f="+encoded+"&w=160",
  source:COMMONS+encoded,artist:p.artist,license:p.license,licenseUrl:p.licenseUrl,
  cropped:true,zoom:p.zoom,origin:p.origin,position:p.position};
}
const memory=new Map(),credited=new Map(),pending=new Map();
try{
 const saved=JSON.parse(localStorage.getItem(CACHE_KEY)||"{}");
 if(saved&&typeof saved==="object")for(const [key,entry] of Object.entries(saved)){
  if(/^[a-z0-9 ]{2,90}$/.test(key)&&entry&&typeof entry.until==="number"&&
     entry.until>Date.now()&&(!entry.photo||validPortrait(entry.photo)))memory.set(key,entry);
 }
}catch(_){}
function validPortrait(p){
 try{
  const image=new URL(p.url),source=new URL(p.source),lic=new URL(p.licenseUrl);
  return image.protocol==="https:"&&["upload.wikimedia.org","commons.wikimedia.org"].includes(image.hostname)&&
   source.hostname==="commons.wikimedia.org"&&lic.hostname==="creativecommons.org"&&
   /^(CC BY(?:-SA)? \d\.\d|CC0 1\.0|Public domain)$/i.test(p.license)&&
   typeof p.artist==="string"&&p.artist.length<240;
 }catch(_){return false;}
}
function persist(){
 try{
  const entries=[...memory].slice(-650);
  localStorage.setItem(CACHE_KEY,JSON.stringify(Object.fromEntries(entries)));
 }catch(_){}
}
async function apiJson(base,params){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),7500);
 try{
  const url=new URL(base);
  for(const [key,value] of Object.entries(params))url.searchParams.set(key,value);
  url.searchParams.set("format","json");url.searchParams.set("origin","*");
  const response=await fetch(url.toString(),{mode:"cors",credentials:"omit",signal:controller.signal});
  if(!response.ok)throw new Error("Wikimedia API "+response.status);
  return await response.json();
 }finally{clearTimeout(timer);}
}
function htmlText(raw){
 const doc=new DOMParser().parseFromString(String(raw||""),"text/html");
 return (doc.body.textContent||"").replace(/\s+/g," ").trim().slice(0,200);
}
function portraitFromPage(page){
 const image=page?.imageinfo?.[0],meta=image?.extmetadata||{};
 const file=String(page?.title||"").replace(/^File:/,"");
 const photo={url:image?.url?"https://commons.wikimedia.org/w/thumb.php?f="+encodeURIComponent(file)+"&w=160":"",
  source:COMMONS+encodeURIComponent(file),
  artist:htmlText(meta.Artist?.value||meta.Attribution?.value),
  license:htmlText(meta.LicenseShortName?.value),licenseUrl:meta.LicenseUrl?.value||"",cropped:true};
 return validPortrait(photo)?photo:null;
}
async function commonsFilenameSearch(name){
 const key=normalized(name);
 const results=await apiJson("https://commons.wikimedia.org/w/api.php",{
  action:"query",generator:"search",gsrsearch:'"'+name+'"',gsrnamespace:"6",gsrlimit:"12",
  prop:"imageinfo",iiprop:"url|extmetadata",iiurlwidth:"160"});
 const pages=Object.values(results?.query?.pages||{}).filter(p=>{
  const title=normalized(String(p.title||"").replace(/^File:/,"").replace(/\.[a-z0-9]{2,5}$/i,""));
  return title===key||title.startsWith(key+" ");
 });
 for(const page of pages){const photo=portraitFromPage(page);if(photo)return photo;}
 return null;
}
async function findFreePortrait(name){
 const result=await apiJson("https://www.wikidata.org/w/api.php",{
  action:"wbsearchentities",search:name,language:"en",uselang:"en",limit:"6"});
 const key=normalized(name);
 const person=(result.search||[]).find(r=>normalized(r.label)===key&&
  /basketball|nba|baloncesto|basketballer/i.test(r.description||""));
 if(!person||!/^Q\d+$/.test(person.id||""))return commonsFilenameSearch(name);
 const entity=await apiJson("https://www.wikidata.org/w/api.php",{
  action:"wbgetentities",ids:person.id,props:"claims"});
 const photos=entity?.entities?.[person.id]?.claims?.P18||[];
 const file=photos.map(c=>c?.mainsnak?.datavalue?.value).find(v=>typeof v==="string"&&v.length<190);
 if(!file)return commonsFilenameSearch(name);
 const record=await apiJson("https://commons.wikimedia.org/w/api.php",{
  action:"query",prop:"imageinfo",iiprop:"url|extmetadata",iiurlwidth:"160",titles:"File:"+file});
 const page=Object.values(record?.query?.pages||{})[0];
 return portraitFromPage(page)||commonsFilenameSearch(name);
}
async function get(name){
 const key=normalized(name);
 if(curatedMap.has(key))return curatedMap.get(key);
 const hit=memory.get(key);if(hit?.until>Date.now())return hit.photo;
 if(pending.has(key))return pending.get(key);
 const promise=findFreePortrait(name).catch(()=>null).then(photo=>{
  memory.delete(key);memory.set(key,{photo,until:Date.now()+(photo?7*DAY:15*60*1000)});
  persist();return photo;
 }).finally(()=>pending.delete(key));
 pending.set(key,promise);return promise;
}
const queue=[];let running=0;
function loadStudioHeadshot(node,id){
 return new Promise(resolve=>{
  if(!/^\d{1,20}$/.test(id||"")){resolve(false);return;}
  const img=new Image();
  let settled=false;
  const done=loaded=>{if(settled)return;settled=true;clearTimeout(timer);resolve(loaded);};
  const timer=setTimeout(()=>{img.src="";done(false);},6500);
  img.alt="Studyjny portret zawodnika: "+node.dataset.hoopPlayer;
  img.title="Portret zawodnika · zdjęcie z ESPN";
  img.className="bc-headshot-photo";
  img.decoding="async";img.loading="eager";
  img.onload=()=>{
   if(settled)return;
   if(!node.isConnected||node.querySelector("img")||img.naturalWidth<50||img.naturalHeight<50){done(false);return;}
   node.appendChild(img);node.dataset.hoopPhotoState="studio";
   done(true);
  };
  img.onerror=()=>done(false);
  img.src="https://a.espncdn.com/i/headshots/nba/players/full/"+id+".png";
 });
}
function pump(){
 while(running<3&&queue.length){
  const job=queue.shift();running++;
  if(!job.node.isConnected){running--;continue;}
  loadStudioHeadshot(job.node,job.id).then(async loaded=>{
   if(!loaded){const photo=await get(job.name);if(photo)apply(job.node,photo);}
  })
   .finally(()=>{running--;pump();});
 }
}
function apply(node,photo){
 if(!node.isConnected||node.querySelector("img")||!validPortrait(photo))return;
 const img=document.createElement("img");
 img.alt="Zdjęcie zawodnika: "+node.dataset.hoopPlayer;
 // The avatar is already visibility-gated by IntersectionObserver. Keep image
 // loading eager here: browser lazy-loading skips elements hidden until load.
 img.loading="eager";img.decoding="async";img.hidden=true;
 img.className="bc-commons-photo";
 const zoom=Number(photo.zoom);
 img.style.setProperty("--hoop-portrait-zoom",String(Number.isFinite(zoom)?Math.max(1,Math.min(2.8,zoom)):1.3));
 if(/^\d{1,3}% \d{1,3}%$/.test(photo.origin||""))img.style.setProperty("--hoop-portrait-origin",photo.origin);
 if(/^(?:center|\d{1,3}%)(?: (?:top|bottom|\d{1,3}%))?$/.test(photo.position||""))img.style.setProperty("--hoop-portrait-position",photo.position);
 img.title="Fot.: "+photo.artist+" · "+photo.license+" · źródło: Wikimedia Commons";
 img.addEventListener("load",()=>{
  if(img.isConnected){credited.set(photo.source,photo);}
 },{once:true});
 img.src=photo.url;node.appendChild(img);
}
const observer=typeof IntersectionObserver==="function"?new IntersectionObserver(entries=>{
 for(const entry of entries){
  if(!entry.isIntersecting)continue;
  observer.unobserve(entry.target);
  queue.unshift({node:entry.target,name:entry.target.dataset.hoopPlayer,id:entry.target.dataset.hoopId});
 }
 pump();
},{rootMargin:"140px"}):null;
function observe(container){
 if(!container)return;
 // The six visible Centrum avatars must not depend on the observer's timing.
 // Keep the 500+ player picker lazy so opening it never downloads every photo.
 const immediate=container.matches?.(".bc-watch,.bc-pick-list,.bc-injury-list,#bc-dialog-body")===true;
 const avatars=container.matches?.("[data-hoop-player]")?[container]:
  [...container.querySelectorAll(".bc-free-avatar[data-hoop-player]")];
 for(const node of avatars){
  if(node.dataset.hoopPhotoState)return;
  if(node.querySelector("img")){node.dataset.hoopPhotoState="licensed";continue;}
  const name=node.dataset.hoopPlayer;
  if(!name)continue;
  node.dataset.hoopPhotoState="queued";
  if(immediate){
   loadStudioHeadshot(node,node.dataset.hoopId).then(async loaded=>{
    if(!loaded){const photo=await get(name);if(photo)apply(node,photo);}
   });
  }else if(observer)observer.observe(node);
  else{queue.push({node,name,id:node.dataset.hoopId});pump();}
 }
}
function credits(){return [...credited.values()].sort((a,b)=>a.artist.localeCompare(b.artist));}
window.HoopzaroPortraits={observe,credits,normaliseName:normalized};
})();
