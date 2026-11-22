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
function validSample(data){
 return Array.isArray(data.sample_path)&&data.sample_path.length===17&&
   data.sample_path.every(r=>number(r.minute)!==null&&number(r.away_minus_home)!==null);
}
const sampleLabel="Przykładowy przebieg — 1 z 5 000";
function drawChart(data,period,away,home){
 const rows=data?.timeline;
 if(!Array.isArray(rows)||rows.length!==9||
    !rows.every(r=>[r.minute,r.margin_mean].every(v=>number(v)!==null)))
   return '<p>Brak pełnej trajektorii z 5 000 wyników.</p>';
 if(data?.quarter_model?.available!==true)
   return '<p>Brak potwierdzonego profilu kwart ESPN. Nie wyświetlamy sztucznej prognozy Q1–Q4.</p>';
 // The visible advantage line and Q labels MUST show the same expectation
 // over 5,000 draws, not one dramatic but unrelated sample path.
 const avg=rows.map(r=>({minute:Number(r.minute),diff:Number(r.margin_mean)}));
 const series=avg;
 const maxAbs=Math.max(5,...series.map(p=>Math.abs(p.diff)));
 const limit=Math.max(10,Math.ceil((maxAbs+2)/5)*5);
 const left=48,top=66,right=882,bottom=198,center=(top+bottom)/2;
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
 // Conditional quarter point estimates from the exact same 5,000 final-score
 // Monte Carlo draws. Not calibrated quarter forecasts or NBA play-by-play.
 const quarterPoints=[0,1,2,3].map(i=>{
   const q=data.quarter_model?.available===true&&Array.isArray(data.quarters)?
     data.quarters[i]:null;
   const homePts=number(q?.home_mean),awayPts=number(q?.away_mean);
   if(Number(q?.quarter)!==i+1||homePts===null||awayPts===null||
      homePts<0||awayPts<0||homePts>100||awayPts>100)return "";
   const mid=x(6+i*12),leftEdge=mid-68;
   const picked=period==="all"||period===String(i+1)||(period==="clutch"&&i===3);
   const hasRange=[q?.away_p10,q?.away_p90,q?.home_p10,q?.home_p90]
     .every(v=>number(v)!==null);
   const range=hasRange?
     " P10–P90: "+home+" "+fmt(q.home_p10)+"–"+fmt(q.home_p90)+
     " pkt, "+away+" "+fmt(q.away_p10)+"–"+fmt(q.away_p90)+" pkt.":"";
   const note="Q"+(i+1)+": "+home+" gospodarze śr. "+fmt(homePts)+" pkt, "+
     away+" goście śr. "+fmt(awayPts)+
     " pkt. Historyczne punkty kwartowe ESPN i 5 000 wyników meczu; model eksperymentalny."+
     range;
   return '<g class="hzm-flow-quarter-points'+(picked?" selected":"")+
     '" data-flow-quarter-points="'+(i+1)+'" role="group" aria-label="'+esc(note)+'">'+
     '<title>'+esc(note)+'</title>'+
     '<rect x="'+leftEdge+'" y="21" width="136" height="39" rx="7"/>'+
     '<text class="hzm-flow-q-home" x="'+mid+'" y="37" text-anchor="middle">'+
     esc(home)+' śr. '+fmt(homePts)+' pkt</text>'+
     '<text class="hzm-flow-q-away" x="'+mid+'" y="53" text-anchor="middle">'+
     esc(away)+' śr. '+fmt(awayPts)+' pkt</text></g>';
 }).join("");
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
   '<text x="'+x(45)+'" y="79" class="flow-clutch" text-anchor="middle">CLUTCH</text>';
 const segments=[];
 for(let i=1;i<series.length;i++){
   const p=series[i-1],q=series[i];
   if(p.diff*q.diff<0){
     const crossing=p.minute+(q.minute-p.minute)*Math.abs(p.diff)/(Math.abs(p.diff)+Math.abs(q.diff));
     const a={minute:crossing,diff:0};
     segments.push([p,a],[a,q]);
   }else segments.push([p,q]);
 }
 const leadColor=diff=>diff>0?"#D374FF":diff<0?"#24F1F6":"#849AB1";
 const leadLabel=diff=>diff===0?"REMIS":
   (diff>0?home:away)+" +"+Math.abs(diff).toLocaleString("pl-PL",{maximumFractionDigits:2})+" pkt";
 const strokes=[],fills=[];
 for(const [p,q] of segments){
   const color=leadColor((p.diff+q.diff)/2);
   const path=line([p,q]);
   strokes.push(`<path d="${path}" fill="none" stroke="${color}" stroke-width="3.25" stroke-linecap="round"/>`);
   fills.push(`<path d="${path} L ${x(q.minute)} ${center} L ${x(p.minute)} ${center} Z" fill="${color}" opacity=".13"/>`);
 }
 const end=series[series.length-1];
 const color=leadColor(end.diff), finalLabel=leadLabel(end.diff);
 const src="Średnia przewaga z 5 000 losowań z historycznym profilem kwart";
 const description=src+". Powyżej zera: gospodarze ("+home+
   "), poniżej: goście ("+away+"), zero: remis. Koniec: "+finalLabel+
   ". Prognozy Q1–Q4 i linia wyliczone z tych samych losowań.";
 const labelX=x(end.minute)-5,labelY=Math.max(top+2,y(end.diff)-23);
 const labelWidth=finalLabel.length*7.5+12;
 return '<svg viewBox="0 0 910 234" role="img" aria-label="'+esc(description)+'">'+
   '<title>'+esc(description)+'</title>'+
   '<defs><filter id="hzm-flow-glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="3"/></filter></defs>'+
   zone+shaded+fills.join("")+grid+dividers+quarter+quarterPoints+marks+
   '<path class="flow-mean" d="'+line(avg)+'" fill="none" stroke="#a3c9df" stroke-opacity=".14" stroke-width="1.5"/>'+
   '<g id="hzm-flow-strokes">'+strokes.join("")+'</g>'+
   '<use href="#hzm-flow-strokes" opacity=".45" filter="url(#hzm-flow-glow)"/>'+
   `<circle cx="${x(end.minute)}" cy="${y(end.diff)}" r="4.4" fill="${color}" stroke="#f7ebff" stroke-width="1.3"/>`+
   `<rect x="${labelX-labelWidth}" y="${labelY}" width="${labelWidth}" height="19" rx="5" fill="#141b32" stroke="${color}"/>`+
   `<text x="${labelX-labelWidth/2}" y="${labelY+13}" text-anchor="middle" fill="#fff" font-size="11" font-weight="800">${esc(finalLabel)}</text>`+
   '<text x="50" y="232" class="flow-axis">Minuta meczu</text></svg>';
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
   (data?.quarter_model?.available===true?
      "Q1–Q4: historyczny profil ESPN, dopasowany do 5 000 symulacji (bez osobnej kalibracji). ":
      "Brak potwierdzonych kwart ESPN. "+String(data?.quarter_model?.basis||"").slice(0,150))+
   " Nie jest to rzeczywisty przebieg play-by-play."+
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
 const hasQuarterProof=ready&&data?.quarter_model?.available===true;
 $("hzm-flow-timeline-desc").textContent=hasQuarterProof?
   "Średnia przewaga 5 000 symulacji · Q1–Q4 to ŚREDNIE, nie pewne wyniki; historia ESPN ("+
   d.game.away+": "+data.quarter_model.away_sample+", "+
   d.game.home+": "+data.quarter_model.home_sample+")":
   "Brak wystarczającej historii kwart ESPN — sztucznych prognoz nie wyświetlamy.";
 $("hzm-flow-plot").innerHTML=ready?
   drawChart(data,cfg.period,d.game.away,d.game.home):
   '<p>Brak danych Premium dla wybranego meczu.</p>';
 $("hzm-flow-final-margin").textContent=ready&&Array.isArray(data.timeline)&&data.timeline.length===9?
   "Śr. przewaga "+(number(data.timeline[8].margin_mean)>0?d.game.home:
     number(data.timeline[8].margin_mean)<0?d.game.away:"remis")+
   ": "+fmt(Math.abs(Number(data.timeline[8].margin_mean)))+" pkt":"—";
 const quarterMarkup=hasQuarterProof&&Array.isArray(data.quarters)?
   data.quarters.map(q=>{
     const a=number(q.away_outscores_pct),h=number(q.home_outscores_pct),tie=number(q.tie_pct);
     if(a===null||h===null||tie===null||a+h+tie>100.3)return "";
     const hi=cfg.period==="all"||cfg.period===String(q.quarter);
     return '<div class="hzm-flow-quarter-row '+(hi?"highlight":"")+
       '" title="Warunkowe losowania punktów; nie zweryfikowana skuteczność kwart"><b>Q'+
       Number(q.quarter)+'</b><div class="hzm-flow-quarter-content">'+
       '<div class="hzm-flow-quarter-values"><b>'+esc(d.game.away)+' '+pct(a)+'</b>'+
       '<b>'+pct(h)+' '+esc(d.game.home)+'</b></div>'+
       '<div class="hzm-flow-quarter-track"><i style="width:'+a+
       '%"></i><i style="width:'+h+'%"></i></div></div>'+
       '<small class="hzm-flow-tie">Remis '+pct(tie)+'</small></div>';
   }).join(""):"";
 $("hzm-flow-quarter-data").innerHTML=quarterMarkup||
   '<p class="hzm-flow-empty">Brak zweryfikowanej historii Q1–Q4 ESPN. Nie pokazujemy sztucznych szans ani punktów kwart.</p>';
 const clutch=ready?data.clutch:null;
 const clutchDiff=number(clutch?.home_margin_mean);
 $("hzm-flow-clutch").textContent=clutchDiff!==null?
   (clutchDiff>0?d.game.home:clutchDiff<0?d.game.away:"REMIS")+
   " "+(clutchDiff===0?"":signed(Math.abs(clutchDiff)))+
   (clutchDiff===0?"":"+ pkt"):"—";
 const proxy=ready&&data.run_proxy?.n_sims===5000&&
   data.run_proxy?.method==="neutral_order_two_point_events_v1"?data.run_proxy:null;
 const eight=number(proxy?.at_least_8_pct);
 $("hzm-flow-runrisk").textContent=eight!==null?"≈"+pct(eight)+" (neutralny)":"Brak danych";
 const change=ready?number(data.neutral_scoring_window_sd):null;
 $("hzm-flow-volatility").textContent=change!==null?
   "σ "+fmt(change)+" pkt / 6 min":"—";
 $("hzm-flow-run-data").innerHTML=[6,8,10].map((threshold,i)=>{
   const value=number(proxy?.["at_least_"+threshold+"_pct"]);
   const good=value!==null&&value>=0&&value<=100;
   return '<div class="hzm-flow-run-row"><span>≥'+threshold+
     '–0</span><div class="hzm-flow-run-track"><i style="width:'+(good?value:0)+
     '%;'+(i===2?'background:linear-gradient(90deg,#8c50cf,#db78ef)':'')+
     '"></i></div><strong>'+(good?"≈"+pct(value):"—")+'</strong></div>';
 }).join("");
 $("hzm-flow-run-note").textContent=proxy?
   "Neutralne losowanie kolejności trafień 2 pkt · bez play-by-play i bez kalibracji":
   "Brak modelu sekwencji; nie są pokazywane fikcyjne prawdopodobieństwa.";
 const observed=ready&&Array.isArray(d?.players?.players)?d.players.players:[];
 const eligible=observed.filter(p=>
   number(p.minutes)!==null&&Number(p.minutes)>=5&&Number(p.minutes)<=48&&
   Number(p.minutes_sample)>=3&&p.availability!=="Out"&&
   [d.game.away,d.game.home].includes(p.team));
 const sorted=(team)=>eligible.filter(p=>p.team===team)
   .sort((a,b)=>Number(b.minutes)-Number(a.minutes));
 const topAway=sorted(d?.game?.away),topHome=sorted(d?.game?.home);
 const picked=[...topAway.slice(0,3),...topHome.slice(0,3)];
 const ticks=Array.from({length:17},(_,i)=>"<span>"+i*3+"′</span>").join("");
 const heat=(p)=>{
   const sample=Array.isArray(p.history)?
     p.history.map(x=>number(x?.min)).filter(v=>v!==null&&v>=0&&v<=48):[];
   return Array.from({length:16},(_,i)=>{
     const threshold=(i+1)*3;
     const rate=sample.length>=3?100*sample.filter(m=>m>=threshold).length/sample.length:null;
     const level=rate===null?"hzm-heat-off":rate>=75?"hzm-heat-hi":
       rate>=50?"hzm-heat-med":rate>=25?"hzm-heat-low":"hzm-heat-off";
     const description=rate===null?"Brak minimum 3 obserwacji":"W "+sample.length+
       " meczach ESPN co najmniej "+threshold+" minut: "+pct(rate);
     return '<span class="hzm-flow-heat-cell '+level+
       '" title="'+esc(description)+'"></span>';
   }).join("");
 };
 $("hzm-flow-roster").innerHTML=!ready?
   '<p>Zweryfikowane minuty ESPN są niedostępne dla konta bez wyniku Premium.</p>':
   !picked.length?
     '<p>Brak wymaganych 3 obserwacji minut zawodników. Użyj „Odśwież skład”.</p>':
   '<div class="hzm-flow-history-grid">'+
   '<div class="hzm-flow-history-head"><span>Zawodnik (drużyna)</span><span>POZ.</span>'+
   '<div class="hzm-flow-time-ticks">'+ticks+'</div><span>ŚR. MIN</span></div>'+
   picked.map(p=>
     '<div class="hzm-flow-player-row '+(p.team===d.game.home?"home":"away")+'">'+
     '<span class="hzm-flow-player-name" title="'+esc(p.name)+'">'+esc(p.name)+
       ' <small>('+esc(p.team)+')</small></span>'+
     '<span class="hzm-flow-player-role">'+esc(p.position||"—")+'</span>'+
     '<div class="hzm-flow-player-track" role="img" aria-label="'+
       esc('Odsetek występów ESPN, w których zawodnik osiągnął kolejne progi łącznego czasu gry. Średnio '+fmt(p.minutes)+' minut.')+
       '">'+heat(p)+'</div>'+
     '<strong>'+fmt(p.minutes)+'′</strong></div>').join("")+
   '</div><p class="hzm-flow-roster-note">Oś 0–48′ pokazuje <b>osiągnięty łączny czas gry</b> w poprzednich meczach ESPN, a nie to, kiedy zawodnik był na boisku. Kolor = odsetek występów z minimum X minutami.</p>';
 // The cards below are exclusively model projections. "Bench" and
 // "rim attempts" cannot be inferred from ESPN minutes/points alone.
 const modelValues=team=>observed.filter(p=>p.team===team&&
   p.availability!=="Out"&&number(p.pts)!==null);
 const ranked=team=>modelValues(team).sort((a,b)=>Number(b.pts)-Number(a.pts));
 const lead=(team)=>ranked(team).filter(p=>number(p.ast)!==null)
   .sort((a,b)=>Number(b.pts)+Number(b.ast)-Number(a.pts)-Number(a.ast))[0];
 const A=lead(d?.game?.away),H=lead(d?.game?.home);
 const duelText=A&&H?{
   title:esc(A.name.split(" ").slice(-1)[0])+" vs "+esc(H.name.split(" ").slice(-1)[0]),
   subtitle:"Prognoza PTS + AST · bez pojedynku 1 na 1",
   away:Number(A.pts)+Number(A.ast),home:Number(H.pts)+Number(H.ast)
 }:{title:"Liderzy ofensywy",subtitle:"Brak danych obu zawodników",away:null,home:null};
 const depth=team=>ranked(team).slice(5,8);
 const depA=depth(d?.game?.away),depH=depth(d?.game?.home);
 const points=arr=>arr.length===3?arr.reduce((sum,p)=>sum+Number(p.pts),0):null;
 const rankReb=team=>modelValues(team).filter(p=>number(p.reb)!==null)
   .sort((a,b)=>Number(b.reb)-Number(a.reb)).slice(0,5);
 const rebA=rankReb(d?.game?.away),rebH=rankReb(d?.game?.home);
 const rebSum=arr=>arr.length===5?arr.reduce((sum,p)=>sum+Number(p.reb),0):null;
 const cards=[
   {title:duelText.title,subtitle:duelText.subtitle,away:duelText.away,home:duelText.home,icon:"◎"},
   {title:"Depth Edge",subtitle:"PTS · miejsca 6–8 wg prognozy (nie potwierdzona ławka)",
      away:points(depA),home:points(depH),icon:"♙"},
   {title:"Rebound Pressure",subtitle:"REB · pięciu liderów wg modelu (nie rzuty spod kosza)",
      away:rebSum(rebA),home:rebSum(rebH),icon:"▥"}
 ];
 $("hzm-flow-matchups").innerHTML=cards.map((card,i)=>{
   const supported=ready&&number(card.away)!==null&&number(card.home)!==null;
   const a=supported?Number(card.away):null,h=supported?Number(card.home):null;
   const leader=!supported?"BRAK DANYCH":a>h?d.game.away:h>a?d.game.home:"REMIS";
   const delta=supported?Math.abs(a-h):null;
   return '<div class="hzm-flow-duel '+(i===1?"purple":"")+'">'+
     '<div class="hzm-flow-duel-head"><span>'+card.icon+'</span><h3>'+card.title+'</h3></div>'+
     '<p>'+card.subtitle+'</p>'+
     '<div class="hzm-flow-duel-nums"><strong>'+(supported?fmt(a):"—")+
       '</strong><b>vs</b><strong>'+(supported?fmt(h):"—")+'</strong></div>'+
     '<div class="hzm-flow-duel-advantage"><small>PRZEWAGA</small>'+
       '<b>'+esc(leader)+(delta!==null&&delta>0?" +"+fmt(delta):"")+'</b></div>'+
     '</div>';
 }).join("");
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
