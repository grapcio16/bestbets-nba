/* DOM-free regression checks for the public schedule, runnable with Node. */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const path=require("node:path");

const elements={};
for(const id of ["hzs-board","hzs-date-strip","hzs-source-note"]){
  elements[id]={innerHTML:"",textContent:"",addEventListener(){}};
}
const arrows=[-1,1].map(direction=>({dataset:{hzsDirection:String(direction)},disabled:false,addEventListener(){}}));
const context={window:{},document:{
  getElementById(id){return elements[id]||null},
  querySelectorAll(selector){return selector==="[data-hzs-direction]"?arrows:[]}
},Date,Intl,Number,String,Array,Map,Math};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,"bestbets_reference_frontend/schedule.js"),"utf8"),context);
const schedule=context.window.HoopzaroSchedule;
assert.equal(typeof schedule.render,"function");

const day="2026-11-14";
const games=Array.from({length:17},(_,i)=>({
  id:"espn-"+i,day,away:"NYK",home:"IND",state:i%3===0?"live":i%3===1?"final":"scheduled",
  away_score:i%3===2?null:100+i,home_score:i%3===2?null:103+i,
  start:"2026-11-14T02:00:00Z",status:"Q4 02:13"
}));
const data={calendar_today:day,calendar_loaded_days:[day],calendar_games:games,
  form_options:[
    {team:"NYK",wins:9,losses:3,ppg:116.8,record_verified:true},
    {team:"IND",wins:6,losses:7,ppg:112.3,record_verified:true}
  ]};
schedule.render(data);
let html=elements["hzs-board"].innerHTML;
assert.equal((html.match(/<article class="hzs-game /g)||[]).length,17,"All 17 games must render");
assert.match(html,/116,8 PPG/);
assert.match(html,/9–3/);
assert.match(html,/112,3 PPG/);
assert.match(html,/6–7/);
assert.match(html,/MECZE · 17/);
assert.match(html,/NA ŻYWO · 4\. KWARTA/);
assert.match(html,/KONIEC/);
assert.match(html,/NADCHODZĄCE/);
assert.equal((html.match(/class="hzs-rows"/g)||[]).length,1,"One full-width list for every status");
assert.doesNotMatch(html,/hzs-columns/,"No blank second column");
assert.equal((html.match(/hzs-live"/g)||[]).length,6);
assert.equal((html.match(/hzs-final"/g)||[]).length,6);
assert.equal((html.match(/hzs-upcoming"/g)||[]).length,5);
assert.doesNotMatch(html,/typ dnia|kurs|projekcja/i);
assert.match(elements["hzs-date-strip"].innerHTML,/aria-pressed="true"/);

const unavailable={...data,form_options:[{team:"NYK",wins:2,losses:2,ppg:null,record_verified:false}]};
schedule.render(unavailable);
html=elements["hzs-board"].innerHTML;
assert.doesNotMatch(html,/116,8 PPG/);
assert.match(html,/— PPG/);

schedule.render({...data,calendar_games:games.filter(game=>game.state==="scheduled")});
html=elements["hzs-board"].innerHTML;
assert.equal((html.match(/<article class="hzs-game/g)||[]).length,5);
assert.equal((html.match(/class="hzs-rows"/g)||[]).length,1);
assert.doesNotMatch(html,/hzs-columns|hzs-live|hzs-final/);

const offDay={calendar_today:day,calendar_loaded_days:[day],calendar_games:[],form_options:[]};
schedule.render(offDay);
assert.match(elements["hzs-board"].innerHTML,/Brak potwierdzonych meczów/);

console.log("HOOPZARO schedule UI checks passed");
