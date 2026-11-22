/* HOOPZARO Flow meczu · Premium, no synthetic source presented as play-by-play.
   Contract: conditional score trajectories are server-allocated from the SAME
   5,000 final Monte Carlo draws. Browser renders ONLY authenticated snapshots. */
(function(){
"use strict";
const $=id=>document.getElementById(id);
const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const number=v=>v!==null&&v!==undefined&&v!==""&&Number.isFinite(Number(v))?Number(v):null;
const fmt=v=>number(v)===null?"—":Number(v).toFixed(1).replace(".",",");
const pct=v=>number(v)===null?"—":fmt(v)+"%";
const signed=v=>number(v)===null?"—":(Number(v)>0?"+":"")+fmt(v);
const cfg={mode:"base",period:"all",context:"",onSave:null,onExport:null,onPlayers:null,onScenario:null,last:null};
function gameKey(d){return [d?.day,d?.game?.id,d?.model].join("|")}
function matchingScenario(d){
 const rec=d?.premium?.scenario, s=d?.selection||{};
 return d?.premium?.entitled===true&&rec&&!rec.error&&
   rec.date===d.day&&String(rec.game_id)===String(d?.game?.id)&&
   rec.model_id===d.model&&rec.pace_pct===s.pacePct&&
   Number(rec.off_away_pct??0)===s.offAwayPct&&
   Number(rec.off_home_pct??0)===s.offHomePct&&
   rec.scenario_flow?.available===true;
}
function active(d){
 const paid=d?.premium?.entitled===true&&d?.sim&&!d.sim.error&&d?.game;
 const scenario=matchingScenario(d);
 return {scenario:!!scenario,data:paid?
   (cfg.mode==="scenario"&&scenario?d.premium.scenario.scenario_flow:d.sim.flow):null,
   effective:cfg.mode==="scenario"&&scenario?"scenario":"base",paid:!!paid};
}
function drawChart(data,period,away,home){
 const rows=data?.timeline;
 if(!Array.isArray(rows)||rows.length!==9||
    !rows.every(r=>[r.minute,r.margin_mean].every(v=>number(v)!==null)))
   return '<p>Brak pełnej trajektorii z 5 000 wyników.</p>';
 const hasSample=Array.isArray(data.sample_path)&&data.sample_path.length===17&&
   data.sample_path.every(r=>number(r.minute)!==null&&number(r.away_minus_home)!==null);
 // The mean is a conditional allocation, whereas the highlighted jagged
 // stroke is ONE deterministic individual draw, not a fake 5k mean.
 const avg=rows.map(r=>({minute:Number(r.minute),diff:-Number(r.margin_mean)}));
 const series=hasSample?
   data.sample_path.map(r=>({minute:Number(r.minute),diff:Number(r.away_minus_home)})):avg;
 const maxAbs=Math.max(5,...series.map(p=>Math.abs(p.diff)),...avg.map(p=>Math.abs(p.diff)));
 const limit=Math.max(10,Math.ceil((maxAbs+2)/5)*5);
 const left=48,top=25,right=882,bottom=198,center=(top+bottom)/2;
 const x=m=>left+Number(m)/48*(right-left);
 const y=v=>center-Number(v)/limit*(bottom-top)/2;
 const line=pts=>pts.map((p,i)=>(i?"L ":"M ")+x(p.minute).toFixed(1)+" "+y(p.diff).toFixed(1)).join(" ");
 const grid=[-limit,-limit/2,0,limit/2,limit].map(v=>
   '<line x1="'+left+'" x2="'+right+'" y1="'+y(v)+'" y2="'+y(v)+
   '" stroke="#3c6387" stroke-opacity="'+(v===0?".7":".32")+'"/>'+
   '<text class="flow-axis" x="39" y="'+(y(v)+4)+'" text-anchor="end">'+
   (v>0?"+":"")+fmt(v).replace(",0","")+'</text>').join("");
 const marks=[0,3,6,9,12,15,18,21,24,27,30,33,36,39,42,45,48].map(m=>
   '<text class="flow-axis" x="'+x(m)+'" y="217" text-anchor="middle">'+
   (m%6===0?m:"")+'</text>').join("");
 const quarter=[0,1,2,3].map(i=>
   '<text class="flow-quarter" x="'+x(6+12*i)+'" y="14" text-anchor="middle">Q'+(i+1)+'</text>').join("");
 const dividers=[12,24,36,42].map(m=>
   '<line x1="'+x(m)+'" x2="'+x(m)+'" y1="'+top+'" y2="'+bottom+
   '" stroke="#7c90bc" stroke-width=".8" stroke-dasharray="4 5" stroke-opacity=".6"/>').join("");
 const select=period==="all"?null:period==="clutch"?[42,48]:
   [(Number(period)-1)*12,Number(period)*12];
 const shaded=select?'<rect x="'+x(select[0])+'" y="'+top+'" width="'+
   (x(select[1])-x(select[0]))+'" height="'+(bottom-top)+
   '" fill="#c766ff" fill-opacity=".13" stroke="#db8aff" stroke-opacity=".45"/>':'';
 const zone='<rect x="'+x(42)+'" y="'+top+'" width="'+(x(48)-x(42))+
   '" height="'+(bottom-top)+'" fill="#a64dd7" fill-opacity=".09"/>'+
   '<text x="'+x(45)+'" y="38" class="flow-clutch" text-anchor="middle">CLUTCH</text>';
 const segments=[];
 for(let i=1;i<series.length;i++){
   const p=series[i-1],q=series[i];
   if(p.diff*q.diff<0){
     const crossing=p.minute+(q.minute-p.minute)*Math.abs(p.diff)/(Math.abs(p.diff)+Math.abs(q.diff));
     const a={minute:crossing,diff:0};
     segments.push([p,a],[a,q]);
   }else segments.push([p,q]);
 }
 const strokes=segments.map(([p,q])=>{
   const color=(p.diff+q.diff)/2>=0?"#24f1f6":"#d374ff";
   return '<path d="M '+x(p.minute).toFixed(1)+' '+y(p.diff).toFixed(1)+
     ' L '+x(q.minute).toFixed(1)+' '+y(q.diff).toFixed(1)+
     '" fill="none" stroke="'+color+'" stroke-width="3.25" stroke-linecap="round"/>';
 }).join("");
 const end=series[series.length-1];
 const color=end.diff>=0?"#2df6fc":"#d479ff";
 const text=(end.diff>=0?"+":"")+fmt(end.diff);
 const centerName=end.diff>0?away:end.diff<0?home:"REMIS";
 const expected=avg[avg.length-1].diff;
 const finalLabel=(expected>0?away:expected<0?home:"REMIS")+" "+
   signed(Math.abs(expected))+" pkt";
 const srclabel=hasSample?"Przykładowy scenariusz (1 z 5 000)":"Średnia warunkowa z 5 000";
 return '<svg viewBox="0 0 910 234" role="img" aria-label="'+
   esc(srclabel+'. Wartości powyżej zera to przewaga '+away+
   ', poniżej to przewaga '+home+
   '. Średnia końcowa '+fmt(expected)+' pkt. Model warunkowy, nie NBA play-by-play.')+'">'+
   '<defs><linearGradient id="hzm-flow-a" x1="0" y1="0" x2="0" y2="1">'+
   '<stop stop-color="#14e9f3" stop-opacity=".35"/><stop offset="1" stop-color="#1169b7" stop-opacity=".03"/></linearGradient>'+
   '<linearGradient id="hzm-flow-h" x1="0" y1="0" x2="0" y2="1">'+
   '<stop stop-color="#602c8f" stop-opacity=".04"/><stop offset="1" stop-color="#b858f4" stop-opacity=".33"/></linearGradient>'+
   '<filter id="hzm-flow-glow"><feGaussianBlur stdDeviation="3"/></filter></defs>'+
   zone+shaded+grid+dividers+quarter+marks+
   '<path d="'+line(series)+' L '+x(48)+' '+y(0)+' L '+x(0)+' '+y(0)+
   ' Z" fill="url(#hzm-flow-a)" opacity=".7"/>'+
   (hasSample?'<path d="'+line(avg)+'" fill="none" stroke="#a3c9df" stroke-opacity=".7" stroke-dasharray="5 5" stroke-width="1.5"/>':'')+
   '<path d="'+line(series)+'" fill="none" stroke="#6ae3ff" stroke-opacity=".25" stroke-width="8" filter="url(#hzm-flow-glow)"/>'+
   strokes+'<circle cx="'+x(end.minute)+'" cy="'+y(end.diff)+'" r="4.4" fill="'+color+'" stroke="#f7ebff" stroke-width="1.3"/>'+
   '<rect x="'+Math.max(left+20,x(48)-63)+'" y="'+Math.max(top+5,y(end.diff)-23)+
   '" width="54" height="19" rx="5" fill="#321a5b" stroke="'+color+'"/>'+
   '<text x="'+Math.max(left+20,x(48)-63+27)+'" y="'+Math.max(top+5,y(end.diff)-23+13)+
   '" text-anchor="middle" fill="#fff" font-size="11" font-weight="800">'+text+'</text>'+
   '<text x="50" y="232" class="flow-axis">Minuta meczu</text>'+
   '<title>'+esc(srclabel+' · '+centerName+' · średnio '+finalLabel)+'</title></svg>';
}
function render(d){
 cfg.last=d;
 const key=gameKey(d);
 if(key!==cfg.context){cfg.context=key;cfg.mode="base";cfg.period="all"}
 const context=active(d),data=context.data,ready=context.paid&&data?.available===true&&data.n_sims===5000;
 const scenarioBtn=$("hzm-flow-scenario"),baseBtn=$("hzm-flow-base");
 if(scenarioBtn)scenarioBtn.disabled=!context.scenario;
 if(!context.scenario&&cfg.mode==="scenario"){cfg.mode="base";context.data=d?.sim?.flow}
 for(const button of [baseBtn,scenarioBtn]){
   if(!button)continue;
   const isOn=button.dataset.flowMode===cfg.mode;
   button.classList.toggle("on",isOn);
   button.setAttribute("aria-pressed",String(isOn));
 }
 for(const button of $("hzm-flow-quarters")?.querySelectorAll("button")||[]){
   const on=button.dataset.flowQuarter===cfg.period;
   button.classList.toggle("on",on);button.setAttribute("aria-pressed",String(on));
 }
 $("hzm-flow-save").disabled=!ready;
 $("hzm-flow-export").disabled=!ready;
 $("hzm-flow-load-players").disabled=!ready||!!d?.players;
 const periodLabel=cfg.period==="all"?"ALL · 48 MIN":cfg.period==="clutch"?"CLUTCH · 42–48'":
   "Q"+cfg.period+" · "+(Number(cfg.period)-1)*12+"–"+Number(cfg.period)*12+"'";
 $("hzm-flow-selected-period").textContent=periodLabel;
 const feedback=$("hzm-flow-feedback"),saved=d?.premium?.flow_saved;
 const pdf=d?.premium?.flow_pdf;
 feedback.textContent=!d?.premium?.entitled?"Wymagana jest zweryfikowana subskrypcja Premium.":
   !d?.game?"Wybierz spotkanie NBA.":
   !d?.sim?"Wczytaj bazowe 5 000 symulacji, aby otworzyć Flow meczu.":
   d.sim.error?String(d.sim.error).slice(0,180):
   !ready?"Dane Flow niedostępne. Nie przedstawiamy prognoz z niepełnych losowań.":
   "Warunkowa rekonstrukcja z tego samego modelu 5 000 wyników — nie dane play-by-play."+
   (!context.scenario?" Scenariusz obliczysz w zakładce Scenariusze.":"");
 if(saved?.date===d.day&&saved?.game_id===String(d?.game?.id)&&saved?.model_id===d.model)
   feedback.textContent+=" · Zapisano "+esc(String(saved.variant||"bazowy"))+" w tej sesji.";
 const link=$("hzm-flow-pdf-link");
 if(link)link.remove();
 if(pdf?.date===d.day&&String(pdf?.game_id)===String(d?.game?.id)&&pdf?.model_id===d.model&&
   pdf?.variant===context.effective&&
   /^[A-Za-z0-9+/=]{100,180000}$/.test(String(pdf.content_base64||""))){
   const a=document.createElement("a");a.id="hzm-flow-pdf-link";
   a.textContent="Pobierz gotowy raport PDF";a.download="Hoopzaro-Flow-"+d.day+".pdf";
   a.href="data:application/pdf;base64,"+pdf.content_base64;a.className="hzm-flow-pdf-link";
   a.setAttribute("aria-label","Pobierz zweryfikowany raport PDF dla meczu");
   feedback.append(" · ");feedback.appendChild(a);
 }
 $("hzm-flow-timeline-desc").textContent=ready?
   "Różnica punktów "+d.game.home+" − "+d.game.away+" (dodatnia = gospodarze)"+
     " · warunkowy podział wyniku na odcinki 6 minut":
   "Brak pełnych danych symulacji dla wybranego meczu.";
 $("hzm-flow-plot").innerHTML=ready?
   drawChart(data,cfg.period,d.game.away,d.game.home):'<p>Brak danych bazowych. Nie pokazujemy przykładowego przebiegu.</p>';
 $("hzm-flow-final-margin").textContent=ready?
   "Śr. przewaga "+(number(data.timeline[8]?.margin_mean)>0?d.game.home:
     number(data.timeline[8]?.margin_mean)<0?d.game.away:"remis")+
   ": "+fmt(Math.abs(Number(data.timeline[8]?.margin_mean)))+" pkt":"—";
 $("hzm-flow-quarter-data").innerHTML=ready&&Array.isArray(data.quarters)?
   data.quarters.map(q=>{
     const a=number(q.away_outscores_pct),h=number(q.home_outscores_pct),tie=number(q.tie_pct);
     if(a===null||h===null||tie===null)return "";
     const hi=cfg.period==="all"||cfg.period===String(q.quarter);
     return '<div class="hzm-flow-quarter-row '+(hi?"highlight":"")+'"><b>Q'+q.quarter+
       '</b><div><div class="hzm-flow-quarter-values"><b>'+esc(d.game.away)+' '+pct(a)+
       '</b><b>'+pct(h)+' '+esc(d.game.home)+'</b></div>'+
       '<div class="hzm-flow-quarter-track"><i style="width:'+a+'%"></i><i style="width:'+h+'%"></i></div></div>'+
       '<small>Remis kwarty: '+pct(tie)+'</small></div>';
   }).join(""):'<p class="hzm-flow-empty">Brak danych kwart.</p>';
 const clutch=ready?data.clutch:null;
 $("hzm-flow-clutch").textContent=clutch?
   (number(clutch.home_margin_mean)>0?d.game.home:d.game.away)+
   " · "+fmt(Math.abs(Number(clutch.home_margin_mean)))+" pkt":"—";
 $("hzm-flow-volatility").textContent=ready&&number(data.volatility?.final_spread_sd)!==null?
   "σ "+fmt(data.volatility.final_spread_sd)+" pkt":"—";
 $("hzm-flow-runrisk").textContent="Brak play-by-play";
 const actual=ready?Array.isArray(d?.players?.players)?d.players.players:[]:[];
 const eligible=actual.filter(p=>number(p.minutes)!==null&&
   Number(p.minutes)>=5&&Number(p.minutes)<=48&&Number(p.minutes_sample)>=3&&
   p.availability!=="Out"&&[d.game.away,d.game.home].includes(p.team));
 const awayPlayers=eligible.filter(p=>p.team===d.game.away).sort((a,b)=>b.minutes-a.minutes).slice(0,3);
 const homePlayers=eligible.filter(p=>p.team===d.game.home).sort((a,b)=>b.minutes-a.minutes).slice(0,3);
 $("hzm-flow-roster").innerHTML=!ready?
   "<p>Zweryfikowane minuty historyczne są niedostępne.</p>":
   !eligible.length?"<p>Brak zweryfikowanych minut zawodników z tego meczu. Użyj „Pobierz dane zawodników”.</p>":
   '<div class="hzm-flow-time-ticks"><span>0′</span><span>12′</span><span>24′</span><span>36′</span><span>48′</span></div>'+
   [...awayPlayers,...homePlayers].map(p=>
     '<div class="hzm-flow-player-row '+(p.team===d.game.home?"home":"")+'">'+
     '<span>'+esc(p.name)+' ('+esc(p.team)+')</span>'+
     '<div class="hzm-flow-player-track" role="img" aria-label="'+esc('Średnio '+fmt(p.minutes)+' minut w historii ESPN; bez określania momentu gry')+'">'+
     '<i style="width:'+Math.min(100,Number(p.minutes)/48*100).toFixed(2)+'%"></i></div>'+
     '<strong>'+fmt(p.minutes)+'′</strong></div>').join("")+
   '<p class="hzm-flow-roster-note">Długość paska to <b>łączny historyczny czas gry</b>; położenie nie oznacza minut wejścia, wyjścia ani składu na parkiecie.</p>';
 const topA=awayPlayers.filter(p=>number(p.pts)!==null&&number(p.ast)!==null)
   .sort((a,b)=>Number(b.pts)+Number(b.ast)-Number(a.pts)-Number(a.ast))[0];
 const topH=homePlayers.filter(p=>number(p.pts)!==null&&number(p.ast)!==null)
   .sort((a,b)=>Number(b.pts)+Number(b.ast)-Number(a.pts)-Number(a.ast))[0];
 const duel=topA&&topH?'<h3>'+esc(topA.name.split(" ").slice(-1)[0])+' vs '+
     esc(topH.name.split(" ").slice(-1)[0])+'</h3><p>PTS + AST · prognozy wybranego modelu</p>'+
     '<strong>'+fmt(Number(topA.pts)+Number(topA.ast))+' vs '+
     fmt(Number(topH.pts)+Number(topH.ast))+'</strong>':
     '<h3>Liderzy ofensywy</h3><p>Wymagane projekcje obu zespołów.</p><strong>—</strong>';
 $("hzm-flow-matchups").innerHTML='<div class="hzm-flow-duel">'+duel+'</div>'+
   '<div class="hzm-flow-duel"><h3>Suma punktów</h3><p>Średnie końcowe tego samego modelu</p><strong>'+
   (ready?fmt(d.sim.away_points)+" / "+fmt(d.sim.home_points):"—")+
   '</strong></div><div class="hzm-flow-duel purple"><h3>Rozpiętość przewagi</h3>'+
   '<p>P10–P90 końcowej różnicy gospodarze − goście</p><strong>'+
   (ready?fmt(data.volatility.final_spread_p10)+" do "+fmt(data.volatility.final_spread_p90):"—")+
   '</strong></div>';
 $("hzm-flow-method").textContent=ready?String(data.source||"").slice(0,560):
   "Flow nie korzysta z fikcyjnych rotacji, serii punktowych ani wyników kwart. Model dostępny wyłącznie po zweryfikowanej symulacji Premium.";
}
function init(api={}){
 cfg.onSave=api.onSave;cfg.onExport=api.onExport;
 cfg.onPlayers=api.onPlayers;cfg.onScenario=api.onScenario;
 $("hzm-flow-panel")?.addEventListener("click",e=>{
   const b=e.target.closest?.("button");if(!b||b.disabled)return;
   if(b.dataset.flowMode){
     cfg.mode=b.dataset.flowMode;render(cfg.last);return;
   }
   if(b.dataset.flowQuarter){
     cfg.period=b.dataset.flowQuarter;render(cfg.last);return;
   }
   if(b.id==="hzm-flow-load-players"){
     const d=cfg.last;if(d?.premium?.entitled===true&&d?.game)
       cfg.onPlayers?.(d.day,String(d.game.id),d.model);
   }else if(b.id==="hzm-flow-save"||b.id==="hzm-flow-export"){
     const d=cfg.last,info=active(d);
     if(d?.premium?.entitled!==true||!info.data?.available)return;
     const action=b.id==="hzm-flow-save"?cfg.onSave:cfg.onExport;
     action?.(d.day,String(d.game.id),d.model,info.effective);
   }
 });
}
window.HoopzaroFlow={init,render};
})();
