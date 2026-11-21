/* Dependency-free DOM checks for the Premium simulation screen. Test data are
 * synthetic ONLY here and never placed in the public application. */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const path=require("node:path");

const elements={};
const ids=[
  "simulations-pane","hzm-matches","hzm-day-title","hzm-day-input","hzm-model-select",
  "hzm-model-trigger","hzm-model-current","hzm-model-options",
  "hzm-model-option-research_context_v75","hzm-model-option-research_form_v74",
  "hzm-model-option-legacy_v72",
  "hzm-match-label","hzm-away-code","hzm-home-code","hzm-score",
  "hzm-away-win","hzm-home-win","hzm-donut","hzm-simulation-message",
  "hzm-away-average-label","hzm-home-average-label","hzm-away-average",
  "hzm-home-average","hzm-total-average","hzm-chart-context","hzm-chart-source",
  "hzm-plot","hzm-players-panel","hzm-player-headings","hzm-expand-players","hzm-player-rows",
  "hzm-evidence-form","hzm-evidence-pace","hzm-evidence-rest",
  "hzm-match-list","hzm-match-picker","hzm-match-picker-label","hzm-lab-main","hzm-lab-range",
  "hzm-player-tools","hzm-player-search","hzm-player-count","hzm-player-team-away","hzm-player-team-home","hzm-player-inspector",
];
for(const id of ids){
  elements[id]={innerHTML:"",textContent:"",value:"",style:{},dataset:{},attributes:{},
    classList:{toggle(){},add(){},remove(){}},
    setAttribute(k,v){this.attributes[k]=v},addEventListener(type,fn){this["on_"+type]=fn},
    focus(){this.focused=true}};
}
elements["hzm-model-options"].hidden=true;
elements["hzm-match-list"].hidden=true;
const tabs=["match","away","home"].map(chart=>({dataset:{hzmChart:chart},textContent:"",attributes:{},
  classList:{toggle(){}},setAttribute(k,v){this.attributes[k]=v}}));
elements["hzm-chart-tabs"]={querySelectorAll(){return tabs}};
const labTabs=["results","players"].map(view=>({dataset:{hzmView:view},attributes:{},
  classList:{toggle(){}},setAttribute(k,v){this.attributes[k]=v}}));
elements["hzm-lab-nav"]={querySelectorAll(){return labTabs}};
const playerTeamButtons=["all","away","home"].map(team=>({
  dataset:{hzmPlayerTeam:team},attributes:{},classList:{toggle(){}},
  setAttribute(k,v){this.attributes[k]=v}
}));
elements["hzm-player-tools"].querySelectorAll=()=>playerTeamButtons;
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
assert.equal(elements["simulations-pane"].dataset.hzmView,"results");
assert.equal(elements["hzm-lab-range"].textContent,"Przedział 80%: —",
  "Guest must never receive Premium percentiles");

app.render(home,{entitled:true,game:fakeGame,players:fakePlayers});
assert.equal(elements["hzm-score"].textContent,"117 : 112");
assert.equal(elements["hzm-away-average"].textContent,"116,8");
assert.equal(elements["hzm-home-average"].textContent,"111,6");
assert.match(elements["hzm-plot"].innerHTML,/<svg/);
assert.match(elements["hzm-lab-range"].textContent,/102,0 – 131,0 pkt/,
  "Premium range derives from verified model P10/P90");
assert.equal((elements["hzm-player-rows"].innerHTML.match(/class="hzm-player-row"/g)||[]).length,4);
elements["simulations-pane"].on_click({target:{closest(selector){
  return selector==="#hzm-expand-players"?{}:null;
}}});
assert.equal(elements["hzm-expand-players"].attributes["aria-expanded"],"true");
assert.equal((elements["hzm-player-rows"].innerHTML.match(/class="hzm-player-row"/g)||[]).length,14,
  "Expanded panel contains all 14 verified test players");
assert.equal(requests,0,"Matching cached data does not trigger a network request");

// Phase 2: player detail derives from the currently entitled model only.
elements["simulations-pane"].on_click({target:{closest(selector){
  return selector==="[data-hzm-view]"?{dataset:{hzmView:"players"}}:null;
}}});
assert.match(elements["hzm-player-inspector"].innerHTML,/Test Athlete 1/);
assert.match(elements["hzm-player-inspector"].innerHTML,/39,2/,
  "PTS + REB + AST derives mean PRA without claiming an independent distribution");
assert.match(elements["hzm-player-inspector"].innerHTML,/Minuty: brak zweryfikowanego szacunku/);
elements["hzm-player-tools"].on_click({target:{closest(selector){
  return selector==="[data-hzm-player-team]"?{dataset:{hzmPlayerTeam:"home"}}:null;
}}});
assert.equal((elements["hzm-player-rows"].innerHTML.match(/class="hzm-player-row"/g)||[]).length,7);
elements["hzm-player-search"].on_input({target:{value:"Test Athlete 14"}});
assert.equal((elements["hzm-player-rows"].innerHTML.match(/class="hzm-player-row"/g)||[]).length,1);
assert.match(elements["hzm-player-inspector"].innerHTML,/Test Athlete 14/);
assert.match(elements["hzm-player-inspector"].innerHTML,/26,2/);
elements["hzm-player-search"].on_input({target:{value:""}});
elements["hzm-player-tools"].on_click({target:{closest(selector){
  return selector==="[data-hzm-player-team]"?{dataset:{hzmPlayerTeam:"all"}}:null;
}}});
elements["simulations-pane"].on_click({target:{closest(selector){
  return selector==="[data-hzm-view]"?{dataset:{hzmView:"results"}}:null;
}}});
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

elements["hzm-model-select"].on_change({target:{value:"research_context_v75"}});
assert.equal(elements["hzm-score"].textContent,"— : —","Research V7.5 cannot show V7.2 result");
assert.equal(requests,2,"V7.5 triggers independent simulation");
const advanced={...fakeGame,model_id:"research_context_v75",away_points:119.2,home_points:105.4,
  model_context:{v75_factors:{away_venue_games:9,home_venue_games:11,rest_away_pts:-0.8,rest_home_pts:0.4,
    injury_out_away:0,injury_out_home:1,injury_away_pts:0,injury_home_pts:-2.4,injuries_espn_fresh:true},
  away_sample:19,home_sample:21,rest_days:[0,1]}};
app.render(home,{entitled:true,game:advanced,players:null});
assert.equal(elements["hzm-score"].textContent,"119 : 105");
assert.match(elements["hzm-evidence-rest"].textContent,/korekta B2B/);
assert.match(elements["hzm-evidence-rest"].textContent,/OUT ESPN/);
assert.equal(elements["hzm-model-select"].value,"research_context_v75");
const v75Players={...fakePlayers,model_id:"research_context_v75",players:[
  {name:"Sample Star",team:"IND",pts:null,reb:null,ast:null,minutes:0,minutes_sample:7,availability:"Out"},
  {name:"Sample Guard",team:"NYK",pts:22,reb:5,ast:8,minutes:31.5,minutes_sample:6,availability:"Questionable"},
]};
app.render(home,{entitled:true,game:advanced,players:v75Players});
assert.match(elements["hzm-player-headings"].innerHTML,/MIN/);
assert.match(elements["hzm-player-rows"].innerHTML,/OUT \(ESPN\)/);
assert.match(elements["hzm-player-rows"].innerHTML,/31,5/);
assert.match(elements["hzm-player-rows"].innerHTML,/Questionable/);
elements["simulations-pane"].on_click({target:{closest(selector){
  return selector==="[data-hzm-view]"?{dataset:{hzmView:"players"}}:null;
}}});
assert.match(elements["hzm-player-inspector"].innerHTML,/Sample Star/);
assert.match(elements["hzm-player-inspector"].innerHTML,/ESPN: Out/);
assert.match(elements["hzm-player-inspector"].innerHTML,/0,0 min/);
assert.match(elements["hzm-player-inspector"].innerHTML,/OUT — model nie wyświetla/);
assert.doesNotMatch(elements["hzm-player-inspector"].innerHTML,/>0,0<\/strong>/,
  "No fake zero-point production for OUT player");
elements["simulations-pane"].on_click({target:{closest(selector){
  return selector==="[data-hzm-view]"?{dataset:{hzmView:"results"}}:null;
}}});

app.render(home,{entitled:false,game:fakeGame,players:fakePlayers});
assert.equal(elements["hzm-score"].textContent,"— : —","Premium expiry instantly hides figures");
assert.doesNotMatch(elements["hzm-player-rows"].innerHTML,/Test Athlete/);
assert.doesNotMatch(elements["hzm-player-inspector"].innerHTML,/Sample Star|Test Athlete/,
  "Player inspector must clear immediately when Premium expires");
// The custom Premium dropdown must preserve the existing model-selection flow.
elements["simulations-pane"].on_click({target:{closest(selector){
  return selector==="#hzm-model-trigger"?{}:null;
}}});
assert.equal(elements["hzm-model-options"].hidden,false);
assert.equal(elements["hzm-model-trigger"].attributes["aria-expanded"],"true");
elements["simulations-pane"].on_click({target:{closest(selector){
  return selector==="[data-hzm-model]"?{dataset:{hzmModel:"research_form_v74"}}:null;
}}});
assert.equal(elements["hzm-model-options"].hidden,true);
assert.equal(elements["hzm-model-trigger"].attributes["aria-expanded"],"false");
assert.equal(elements["hzm-model-select"].value,"research_form_v74");
assert.equal(elements["hzm-model-current"].textContent,"V7.4 · FORMA + KONTEKST");
assert.equal(elements["hzm-model-option-research_form_v74"].attributes["aria-selected"],"true");
elements["hzm-model-trigger"].on_click({stopPropagation(){}});
assert.equal(elements["hzm-model-options"].hidden,false,
  "Direct dropdown trigger works independently of pane delegation");
elements["hzm-model-option-legacy_v72"].on_click({stopPropagation(){}});
assert.equal(elements["hzm-model-options"].hidden,true);
assert.equal(elements["hzm-model-select"].value,"legacy_v72");
// The research-form fixture is authorized only for research_form_v74.
// Restore that model before checking its 14-player list; showing it under
// V7.2 would be a serious Premium projection data-integrity regression.
elements["hzm-model-option-research_form_v74"].on_click({stopPropagation(){}});
assert.equal(elements["hzm-model-select"].value,"research_form_v74");

// Simulation Lab 2.0: working tabs and match selector, not empty UI controls.
app.render(home,{entitled:true,game:fakeGame,players:fakePlayers});
elements["simulations-pane"].on_click({target:{closest(selector){
  return selector==="[data-hzm-view]"?{dataset:{hzmView:"players"}}:null;
}}});
assert.equal(elements["simulations-pane"].dataset.hzmView,"players");
assert.equal(elements["hzm-lab-main"].attributes["aria-labelledby"],"hzm-lab-tab-players");
assert.equal(labTabs[1].attributes["aria-selected"],"true");
assert.equal(elements["hzm-expand-players"].attributes["aria-expanded"],"true");
assert.equal((elements["hzm-player-rows"].innerHTML.match(/class="hzm-player-row"/g)||[]).length,14);
elements["simulations-pane"].on_click({target:{closest(selector){
  return selector==="[data-hzm-view]"?{dataset:{hzmView:"results"}}:null;
}}});
assert.equal(elements["simulations-pane"].dataset.hzmView,"results");
assert.equal(elements["hzm-lab-main"].attributes["aria-labelledby"],"hzm-lab-tab-results");
assert.equal((elements["hzm-player-rows"].innerHTML.match(/class="hzm-player-row"/g)||[]).length,4);
elements["hzm-expand-players"].on_click({stopPropagation(){}});
assert.equal(elements["hzm-expand-players"].attributes["aria-expanded"],"true");
assert.equal((elements["hzm-player-rows"].innerHTML.match(/class="hzm-player-row"/g)||[]).length,14);
elements["hzm-expand-players"].on_click({stopPropagation(){}});
assert.equal(elements["hzm-expand-players"].attributes["aria-expanded"],"false");
elements["simulations-pane"].on_click({target:{closest(selector){
  return selector==="#hzm-match-picker"?{}:null;
}}});
assert.equal(elements["hzm-match-list"].hidden,false);
assert.equal(elements["hzm-match-picker"].attributes["aria-expanded"],"true");
elements["simulations-pane"].on_click({target:{closest(selector){
  return selector==="[data-hzm-game]"?{dataset:{hzmGame:game.id}}:null;
}}});
assert.equal(elements["hzm-match-list"].hidden,true);
assert.equal(elements["hzm-match-picker"].attributes["aria-expanded"],"false");
elements["simulations-pane"].on_click({target:{closest(selector){
  return selector==="#hzm-match-picker"?{}:null;
}}});
assert.equal(elements["hzm-match-list"].hidden,false);
elements["hzm-matches"].on_click({stopPropagation(){},target:{closest(selector){
  return selector==="[data-hzm-game]"?{dataset:{hzmGame:game.id}}:null;
}}});
assert.equal(elements["hzm-match-list"].hidden,true,
  "Direct fixture click must close the actual popup without relying on bubbling");
app.render(home,{entitled:false,game:fakeGame,players:fakePlayers});
assert.equal(elements["hzm-lab-range"].textContent,"Przedział 80%: —");
assert.doesNotMatch(elements["hzm-player-rows"].innerHTML,/Test Athlete/);
// Stage 3: a Player Props deep link never selects an unrelated fixture or a
// game which already started. No fabricated scheduled matchup.
let link=app.openFromProps({name:"Test Athlete 1",team:"NYK",market:"PTS"},home);
assert.equal(link.ok,false,"A past fixture cannot be used as a future game");
const futureStart=new Date(Date.now()+4*86400000).toISOString();
const futureDay=futureStart.slice(0,10);
const futureGame={id:"401900111",day:futureDay,away:"NYK",home:"BOS",
 state:"scheduled",start:futureStart};
const futureHome={
 calendar_today:futureDay,calendar_games:[futureGame],calendar_loaded_days:[futureDay]
};
link=app.openFromProps({name:"Test Athlete 1",team:"LAL",market:"PTS"},futureHome);
assert.equal(link.ok,false,"Other-team matches cannot be linked");
link=app.openFromProps({name:"Test Athlete 1",team:"NYK",market:"PTS"},futureHome);
assert.equal(link.ok,true);
assert.equal(link.gameId,futureGame.id);
app.render(futureHome,{entitled:false,game:fakeGame,players:fakePlayers});
assert.equal(elements["simulations-pane"].dataset.hzmView,"players");
assert.equal(elements["hzm-player-search"].value,"Test Athlete 1");
assert.equal(elements["hzm-player-team-away"].textContent,"NYK");
assert.doesNotMatch(elements["hzm-player-inspector"].innerHTML,/Test Athlete 1/,
  "Deep linking must not bypass the Premium gate");
app.clearBridge();
console.log("Simulation Lab 2.0: premium-only results, honest ranges, functional tabs and match picker OK");
