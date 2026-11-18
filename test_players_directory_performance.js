/* No dependencies or live endpoints. Verify the premium directory's search
 * index remains correct and does not re-normalize 500 athletes per rerender. */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");

class Element{
  constructor(){this.children=[];this.dataset={};this.value="";this.textContent="";
    this.disabled=false;this.firstChild={textContent:""};this.handlers={};}
  append(...nodes){this.children.push(...nodes)}
  replaceChildren(...nodes){this.children=nodes}
  setAttribute(name,value){this[name]=value}
  addEventListener(name,callback){this.handlers[name]=callback}
}
const ids=["hzp-team","hzp-table-rows","hzp-page","hzp-prev","hzp-next",
  "hzp-table-count","hzp-source","hzp-cta-title","hzp-cta-text","hzp-cta",
  "hzp-search","hzp-position","hzp-refresh"];
const elements=Object.fromEntries(ids.map(id=>[id,new Element()]));
const context={window:{__normalizeCalls:0},document:{
  getElementById:id=>elements[id],createElement:()=>new Element(),
},Option:class{constructor(label,value){this.label=label;this.value=value}}};
vm.createContext(context);
vm.runInContext(`const originalNormalize=String.prototype.normalize;
  String.prototype.normalize=function(...args){
    window.__normalizeCalls++;
    return originalNormalize.apply(this,args);
  };`,context);
vm.runInContext(fs.readFileSync(path.join(__dirname,"bestbets_reference_frontend/players.js"),"utf8"),context);
const directory=context.window.HoopzaroPlayers;
const requested=[];
directory.init({requestAverages:ids=>requested.push(ids)});

const featured=["Jayson Tatum","Stephen Curry","Nikola Jokić","Luka Dončić",
  "Shai Gilgeous-Alexander","Anthony Edwards"];
const players=[...featured.map((name,index)=>({id:String(index+1),name,team:"BOS",position:"SF"})),
  ...Array.from({length:520},(_,index)=>({id:String(index+100),name:`Athlete ${index}`,
    team:index%2?"NYK":"DEN",position:index%2?"PG":"C"}))];
const catalog={players};
directory.render(catalog,null,"guest");
const initiallyNormalized=context.window.__normalizeCalls;
assert.ok(initiallyNormalized>=players.length,"First render should index every verified athlete");

// Streamlit can rerender on auth, schedule, payment or navigation updates.
// These must not rescan the complete catalog on each identical update.
for(let index=0;index<30;index++)directory.render(catalog,null,"guest");
assert.ok(context.window.__normalizeCalls-initiallyNormalized<=35,
  "30 unchanged rerenders should normalize only the search text");
assert.equal(requested.length,0,"Free users must never request Premium histories");

const firstNames=elements["hzp-table-rows"].children.slice(0,6).map(row=>
  row.children[0].children[1].children[0].textContent);
assert.deepEqual(firstNames,featured,"Featured priority and Polish-name sorting must remain unchanged");

elements["hzp-search"].handlers.input({target:{value:"jokic"}});
assert.equal(elements["hzp-table-rows"].children.length,1);
assert.equal(elements["hzp-table-rows"].children[0].children[0].children[1]
  .children[0].textContent,"Nikola Jokić","Diacritics-free search stays correct");

elements["hzp-search"].handlers.input({target:{value:""}});
elements["hzp-team"].handlers.change({target:{value:"NYK"}});
assert.equal(elements["hzp-table-count"].textContent,
  "Darmowy podgląd · odblokuj statystyki Premium");
assert.equal(elements["hzp-table-rows"].children.length,7);

const updated={players:[{id:"99999",name:"Fresh Verified Player",team:"BOS",position:"C"}]};
directory.render(updated,null,"guest");
assert.equal(elements["hzp-team"].value,"","Removed team options must reset to All teams");
assert.equal(elements["hzp-table-rows"].children.length,1,"New catalog rebuilds the index");
assert.equal(elements["hzp-table-rows"].children[0].children[0].children[1]
  .children[0].textContent,"Fresh Verified Player");
console.log("Player directory: fast cached search, stable sorting, filters and fresh catalog OK");
