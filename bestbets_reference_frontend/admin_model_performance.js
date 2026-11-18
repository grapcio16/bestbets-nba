/* A read-only presentation of model snapshots that the server has authorized. */
(function(){
 "use strict";
 const target=()=>document.getElementById("hz-admin-dashboard");
 const escapeHtml=value=>String(value==null?"":value).replace(/[&<>"']/g,char=>({
   "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"
 }[char]));
 const number=value=>typeof value==="number"&&Number.isFinite(value)?value.toLocaleString("pl-PL"):"—";
 const percentage=value=>typeof value==="number"&&Number.isFinite(value)?(value*100).toFixed(1).replace(".",",")+"%":"—";
 const signed=value=>typeof value==="number"&&Number.isFinite(value)?value.toFixed(2).replace(".",","):"—";
 const metric=(label,value,help)=>'<div class="hz-admin-stat"><span>'+label+'</span><b>'+value+'</b><small>'+help+'</small></div>';
 function modelCard(model){
   const m=model.metrics||{},ready=Number(m.games)||0;
   return '<article class="hz-admin-model">'+
     '<div class="hz-admin-model-top"><div><span>MODEL · ZAMROŻONE PROGNOZY</span><h2>'+escapeHtml(model.id)+'</h2></div>'+
     '<span class="hz-admin-counter">'+number(model.snapshots)+' zapisów</span></div>'+
     '<div class="hz-admin-stats">'+
       metric("Trafność zwycięzcy",percentage(m.winner_accuracy),ready+' zakończonych meczów')+
       metric("Błąd sumy punktów",signed(m.total_mae),"MAE · punkty")+
       metric("Błąd punktów drużyn",signed(m.team_mae),"MAE · punkty")+
       metric("Brier score",signed(m.brier),"Im niżej, tym lepiej")+
     '</div><div class="hz-admin-model-foot"><span>Rozliczone: <b>'+number(model.settled)+'</b> / '+number(model.snapshots)+'</span>'+
     '<span>Zweryfikowane przez audyt: <b>'+number(ready)+'</b></span></div>'+
     (!ready?'<div class="hz-admin-pending">Brak zakończonych i zweryfikowanych prognoz. Wyniki oceny pojawią się po meczach.</div>':'')+
     '</article>';
 }
 function row(record){
   const final=record.home_actual!==null&&record.away_actual!==null;
   return '<tr><td>'+escapeHtml(record.date)+' UTC</td><td><b>'+escapeHtml(record.away)+' @ '+escapeHtml(record.home)+'</b></td>'+
     '<td>'+number(record.away_pred)+' : '+number(record.home_pred)+'</td>'+
     '<td>'+(final?number(record.away_actual)+' : '+number(record.home_actual):'<span class="hz-admin-wait">Oczekuje</span>')+'</td></tr>';
 }
 function render(report,loading){
   const root=target();if(!root)return;
   if(!report){
     root.innerHTML='<div class="hz-admin-empty">'+(loading?'Łączenie z archiwum prognoz…':'Raport nie został jeszcze wczytany.')+'</div>';
     return;
   }
   if(report.error){
     root.innerHTML='<div class="hz-admin-empty hz-admin-error">'+escapeHtml(report.error)+'</div>';
     return;
   }
   const models=Array.isArray(report.models)?report.models:[];
   if(!models.length){
     root.innerHTML='<div class="hz-admin-empty">Brak zamrożonych prognoz w sezonie '+escapeHtml(report.season)+'. Tracker musi najpierw zapisać dane.</div>';
     return;
   }
   const options=models.map((m,index)=>'<option value="'+index+'">'+escapeHtml(m.id)+'</option>').join("");
   root.innerHTML='<div class="hz-admin-meta"><span>Sezon '+escapeHtml(report.season)+'</span><span>Aktualizacja '+escapeHtml(String(report.as_of_utc||"").slice(0,16).replace("T"," "))+' UTC</span>'+
     '<span>Dokładność liczona wyłącznie dla zapisów sprzed rozpoczęcia meczów.</span></div>'+
     '<div class="hz-admin-models">'+models.map(modelCard).join("")+'</div>'+
     '<section class="hz-admin-history"><header><h2>Historia prognoz</h2><label>Model <select id="hz-admin-history-model">'+options+'</select></label></header>'+
     '<div class="hz-admin-table-scroll"><table><thead><tr><th>Data</th><th>Mecz</th><th>Prognoza</th><th>Wynik</th></tr></thead>'+
     '<tbody id="hz-admin-history-rows"></tbody></table></div>'+
     '<p>Wyniki modelu nie są gwarancją skuteczności typów ani rentowności zakładów.</p></section>';
   const chooser=document.getElementById("hz-admin-history-model"),body=document.getElementById("hz-admin-history-rows");
   function updateRows(){
     const index=Number(chooser.value),records=models[index]?.recent||[];
     body.innerHTML=records.length?records.map(row).join(""):'<tr><td colspan="4">Brak zapisów.</td></tr>';
   }
   chooser.addEventListener("change",updateRows);updateRows();
 }
 window.HoopzaroAdmin={render};
})();
