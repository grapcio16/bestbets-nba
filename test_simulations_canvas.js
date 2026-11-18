/* Dependency-free DOM checks for the Premium simulation screen. Test data are
 * synthetic ONLY here and never placed in the public application. */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const path=require("node:path");

const elements={};
const ids=[
  "simulations-pane","hzm-matches","hzm-day-title","hzm-day-input","hzm-model-select",
  "hzm-match-label","hzm-away-code","hzm-home-code","hzm-score",
  "hzm-away-win","hzm-home-win","hzm-donut","hzm-simulation-message",
  "hzm-away-average-label","hzm-home-average-label","hzm-away-average",
  "hzm-home-average","hzm-total-average","hzm-chart-context","hzm-chart-source",
  "hzm-plot","hzm-players-panel","hzm-expand-players","hzm-player-rows",
  "hzm-evidence-form","hzm-evidence-pace","hzm-evidence-rest",
];
for(const id of ids){
  elements[id]={innerHTML:"",textContent:"",value:"",style:{},dataset:{},attributes:{},
    classList:{toggle(){},add(){},remove(){}},
    setAttribute(k,v){this.attributes[k]=v},addEventListener(type,fn){this["on_"+type]=fn}};
}
const tabs=["match","away","home"].map(chart=>({dataset:{hzmChart:chart},textContent:"",attributes:{},
  classList:{toggle(){}},setAttribute(k,v){this.attributes[k]=v}}));
elements["hzm-chart-tabs"]={querySelectorAll(){return tabs}};
const context={window:{},document:{getElementById(id){return elements[id]||null}},Date,Intl,Number,Math,Map,String,Array};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,"bestbets_reference_frontend/simulations.js"),"utf8"),context);
const app=context.window.HoopzaroSimulations;
let requests=0;
app.init({selectDay(){requests++},loadGame(){requests++},loadPlayers(){requests++},premium(){requests++}});
const day="2026-11-14",game={id:"401000123",day,away:"NYK",home:"IND",state:"scheduled",start:"2026-11-15T01:00:00Z"};
const home={calendar_today:day,calendar_loaded_days:[day],calendar_games:[game]};
const bins=Array.from({length:10},(_,i)=>({x:90+i*5,p:i<5?i*2:(10-i)*2}));
const dist={bins,average:116.8,p10:102,p90:131,threshold:110,over_pct:68};
const fakeGame={date:day,game_id:game.id,model_id:"research_form_v74",away:"NYK",home:"IND",away_win_pct:59,home_win_pct:41,
  away_points:116.8,home_points:111.6,total_points:228.4,distributions:{match:dist,away:dist,home:dist}};
const fakePlayers={date:day,game_id:game.id,model_id:"research_form_v74",players:Array.from({length:14},(_,i)=>({
  name:"Test Athlete "+(i+1),team:i%2?"IND":"NYK",pts:27-i,reb:5.1,ast:7.1
}))};

app.render(home,{entitled:false,game:fakeGame,players:fakePlayers});
assert.equal(elements["hzm-score"].textContent,"— : —","No premium scores can be displayed in guest mode");
assert.equal(elements["hzm-away-average"].textContent,"—","No simulated averages leaked in guest mode");
assert.match(elements["hzm-player-rows"].innerHTML,/dostępne w Premium/);
assert.equal(requests,0,"Guest requests no paid data");
assert.equal(tabs[1].textContent,"NYK");
assert.equal(tabs[2].textContent,"IND");

app.render(home,{entitled:true,game:fakeGame,players:fakePlayers});
assert.equal(elements["hzm-score"].textContent,"117 : 112");
assert.equal(elements["hzm-away-average"].textContent,"116,8");
assert.equal(elements["hzm-home-average"].textContent,"111,6");
assert.match(elements["hzm-plot"].innerHTML,/<svg/);
assert.equal((elements["hzm-player-rows"].innerHTML.match(/class="hzm-player-row"/g)||[]).length,4);
elements["simulations-pane"].on_click({target:{closest(selector){
  return selector==="#hzm-expand-players"?{}:null;
}}});
assert.equal(elements["hzm-expand-players"].attributes["aria-expanded"],"true");
assert.equal((elements["hzm-player-rows"].innerHTML.match(/class="hzm-player-row"/g)||[]).length,14,
  "Expanded panel contains all 14 verified test players");
assert.equal(requests,0,"Matching cached data does not trigger a network request");

// A model switch must neither reuse stale V7.4 results nor leak cached athletes.
elements["hzm-model-select"].on_change({target:{value:"legacy_v72"}});
assert.equal(elements["hzm-score"].textContent,"— : —");
assert.equal(elements["hzm-away-average"].textContent,"—");
assert.equal(requests,1,"New model requests its own simulation");
const legacy={...fakeGame,model_id:"legacy_v72",away_points:106.1,home_points:103.2};
const legacyPlayers={...fakePlayers,model_id:"legacy_v72"};
app.render(home,{entitled:true,game:legacy,players:legacyPlayers});
assert.equal(elements["hzm-score"].textContent,"106 : 103");
assert.equal(elements["hzm-model-select"].value,"legacy_v72");
assert.equal(requests,1);

app.render(home,{entitled:false,game:fakeGame,players:fakePlayers});
assert.equal(elements["hzm-score"].textContent,"— : —","Premium expiry instantly hides figures");
assert.doesNotMatch(elements["hzm-player-rows"].innerHTML,/Test Athlete/);
console.log("Premium canvas: tabs, verified data, expandable 14-player list, guest gate OK");
