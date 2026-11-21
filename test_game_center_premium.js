/* Synthetic local fixtures only. No scores or test hooks enter production. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const source = fs.readFileSync(path.join(__dirname, "bestbets_reference_frontend/schedule.js"), "utf8");
const context = {window:{}, document:{getElementById(){return null}},
  localStorage:{getItem(){return null}}, Date, Intl, Number, String, Array, Map, Set, Math};
const hooks = `window.__gcTest={winner:gameCenterWinner,tone:gameCenterTone,score:gameCenterScore,graph:quarterGraph,
  render:(data,game,packet)=>{selectedDay=game.day;lastDetails=packet;historyTab="h2h";return detailsMarkup(data,game,packet)},
  history:(data,game,packet,tab)=>{selectedDay=game.day;lastDetails=packet;historyTab=tab;return historyMarkup(data,game)}};`;
vm.runInNewContext(source.replace("window.HoopzaroSchedule={", hooks+"window.HoopzaroSchedule={"), context);
const api = context.window.__gcTest;
const selected = {id:"401999001",day:"2026-11-21",start:"2026-11-21T00:00:00Z",
  away:"CHA",home:"ATL",away_score:97,home_score:111,state:"final"};
const periods = [{period:"Q1",away:31,home:23},{period:"Q2",away:26,home:33},
  {period:"Q3",away:19,home:31},{period:"Q4",away:21,home:24}];
const previous = {id:"401999002",start:"2026-10-24T23:00:00Z",
  away:"ATL",home:"CHA",away_score:128,home_score:81,state:"final"};
const data = {form_options:[]};
function packet(game, quarters=periods){
  return {id:game.id,day:game.day,data:{away:game.away,home:game.home,quarters,
    team_stats:[],leaders:{away:[],home:[]},history:{h2h:[previous],recent:{CHA:[previous],ATL:[previous]}}}};
}
assert.equal(api.winner(selected),"home");
assert.equal(api.winner({...selected,away_score:112}),"away");
for(const game of [{...selected,state:"live"},{...selected,home_score:null},
    {...selected,away_score:"97"},{...selected,home_score:97},{...selected,away_score:-1}]){
  assert.equal(api.winner(game),"", "Unverified, tied or live scores cannot declare a winner");
}
assert.equal(api.tone("CHA",selected),"hzv-tone-cyan");
assert.equal(api.tone("ATL",selected),"hzv-tone-violet");
assert.equal(api.tone("ORL",selected),"hzv-tone-gold");
const history = api.history(data,selected,packet(selected),"h2h");
assert.match(history,/data-hzv-winner="ATL"/);
assert.match(history,/data-hzv-team="ATL" class="hzv-history-participant hzv-tone-violet is-winner/);
assert.match(history,/data-hzv-score-team="ATL" class="hzv-score-value hzv-tone-violet is-winner/);
assert.match(history,/25 października 2026/); // full Warsaw calendar date
assert.match(history,/hzv-calendar-icon/);
const recent = api.history(data,selected,packet(selected),"recent");
assert.equal((recent.match(/hzv-history-row"/g)||[]).length,2);
const home = api.render(data,selected,packet(selected));
assert.equal((home.match(/ZWYCIĘZCA/g)||[]).length,1);
assert.match(home,/hzv-quarter-total hzv-tone-violet is-winner/);
assert.match(home,/data-hzv-team="ATL" data-hzv-points="111"/);
assert.match(home,/data-hzv-team="CHA" data-hzv-points="97"/);
assert.match(home,/12 pkt \(Q3\)/);
const awayGame={...selected,away_score:117};
const awayPeriods=periods.map((q,i)=>({...q,away:q.away+(i===3?20:0)}));
const away = api.render(data,awayGame,packet(awayGame,awayPeriods));
assert.match(away,/hzv-quarter-total hzv-tone-cyan is-winner/);
assert.match(away,/data-hzv-team="CHA" data-hzv-points="117"/);
const otPeriods=[...periods,{period:"OT1",away:14,home:3}];
const overtime={...selected,away_score:111,home_score:114};
assert.match(api.render(data,overtime,packet(overtime,otPeriods)),/>OT1<\/text>/);
for(const quarters of [[],periods.slice(0,2),periods.map(q=>({...q,home:q.home+1}))]){
  const fallback=api.render(data,selected,packet(selected,quarters));
  assert.match(fallback,/hzv-xfactor-final/);
  assert.doesNotMatch(fallback,/hzv-quarter-endpoint/);
  assert.doesNotMatch(fallback,/hzv-quarter-table/);
}
const live={...selected,state:"live"};
assert.doesNotMatch(api.render(data,live,packet(live)),/hzv-winner-badge/);
const missing={...selected,away_score:null};
assert.doesNotMatch(api.render(data,missing,packet(missing,[])),/ZWYCIĘZCA|NaN|undefined/);
assert.match(api.graph(periods,"CHA","ATL"),/stroke="#02e5ef"/);
assert.match(api.graph(periods,"CHA","ATL"),/stroke="#cb57ef"/);
console.log("PASS: Game Center winners, stable club colors, verified endpoints, OT and safe fallbacks");
