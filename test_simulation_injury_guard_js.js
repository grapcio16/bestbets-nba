/* Exercise the actual production guard in an isolated VM, with no browser,
 * provider calls, or production data. No changes to the application export. */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const path=require("node:path");
const source=fs.readFileSync(path.join(__dirname,"bestbets_reference_frontend/simulations.js"),"utf8");
const anchor="window.HoopzaroSimulations={init,render,openFromProps,clearBridge};";
assert.equal(source.split(anchor).length,2);
const context={window:{},Date};
vm.runInNewContext(source.replace(anchor,anchor+"window.__qa={trustedPlayers,state};"),context);
const {trustedPlayers,state}=context.window.__qa;
state.day="2026-11-27";state.model="research_form_v74";
const game={id:"401000123",state:"scheduled"};
const roster=[
 {name:"Eligible",team:"BOS",espn_id:"11",pts:20},
 {name:"Out",team:"NYK",espn_id:"12",availability:"Out",pts:30},
 {name:"Risk",team:"NYK",espn_id:"13",availability:"Questionable",pts:25}
];
const data={date:state.day,model_id:state.model,game_id:game.id,players:roster,
 minute_roster:roster.map((r,i)=>({...r,projection_index:i}))};
const evaluate=pack=>trustedPlayers({entitled:true,players:pack},game);
for(const missing of [undefined,null,{}, {rows:null}, {rows:{}}]){
 const safe=evaluate({...data,injury_watch:missing});
 assert.equal(safe.availability_conditional,true);
 assert.equal(safe.injury_report_fresh,false);
 assert.equal(safe.players.length,1);
 assert.equal(safe.players[0].name,"Eligible");
 assert.equal(safe.minute_roster[1].projection_index,null);
 assert.equal(safe.minute_roster[2].projection_index,null);
}
const now=Date.now(),watch={fresh:true,checked_at:new Date(now-1000).toISOString(),
 valid_until:new Date(now+1000*60*10).toISOString(),
 rows:[{name:"Eligible",team:"BOS",espn_id:"11",status:"Out"}]};
assert.equal(evaluate({...data,injury_watch:watch}).players.length,0);
assert.equal(evaluate({...data,injury_watch:{...watch,fresh:false}}).players.length,0,
 "An expired report never revives an explicit OUT");
assert.equal(trustedPlayers({entitled:false,players:data},game),null);
assert.equal(evaluate({...data,model_id:"legacy_v72"}),null);
assert.equal(evaluate({...data,game_id:"different"}),null);
assert.equal(roster.length,3,"Guard does not mutate the original pack");
console.log("Missing/malformed injury report: conditional results, explicit exclusions, roster mapping and Premium/model/fixture isolation OK");
