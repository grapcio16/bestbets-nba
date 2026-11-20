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
 const signedBias=value=>typeof value==="number"&&Number.isFinite(value)?(value>0?"+":"")+value.toFixed(2).replace(".",","):"—";
 const metric=(label,value,help)=>'<div class="hz-admin-stat"><span>'+label+'</span><b>'+value+'</b><small>'+help+'</small></div>';
 let playerSearch="",playerMarket="pts",playerOrder="recent";
 const setupCard=(failure)=>'<section class="hz-admin-connection">'+
   '<div class="hz-admin-connection-head"><div class="hz-admin-connection-icon">◇</div><div>'+
   '<span class="hz-admin-connection-eyebrow">PRYWATNE ARCHIWUM · MODEL PERFORMANCE</span>'+
   '<h2>'+(failure?'Połączenie wymaga uwagi':'Połącz archiwum prognoz')+'</h2>'+
   '<p>'+(failure?'Dane nie zostały teraz odczytane. Wyniki pozostają bez zmian w bazie.':
     'Panel jest gotowy. Wystarczy połączyć tę aplikację z bazą, w której tracker zapisuje prognozy sprzed meczów.')+'</p></div>'+
   '<span class="hz-admin-connection-status">'+(failure?'PRÓBA PONOWIENIA':'DO KONFIGURACJI')+'</span></div>'+
   '<div class="hz-admin-setup-steps">'+
     '<div class="hz-admin-setup-step"><span>01</span><b>Otwórz Streamlit Cloud</b><p>Przejdź do ustawień tej aplikacji i sekcji Secrets.</p></div>'+
     '<div class="hz-admin-setup-step"><span>02</span><b>Podłącz PostgreSQL</b><p>Dodaj TRACKER_DATABASE_URL z adresem tej samej bazy, której używa tracker.</p></div>'+
     '<div class="hz-admin-setup-step"><span>03</span><b>Odśwież raport</b><p>Po zapisaniu konfiguracji użyj przycisku Odśwież powyżej.</p></div></div>'+
   '<div class="hz-admin-connection-foot"><span>◈</span> Nie publikuj adresu bazy ani hasła w GitHubie lub na czacie. Sekret pozostaje po stronie serwera.</div>'+
   '</section>';
 function modelCard(model){
   const m=model.metrics||{},ready=Number(m.games)||0;
   return '<article class="hz-admin-model">'+
     '<div class="hz-admin-model-top"><div><span>MODEL · ZAMROŻONE PROGNOZY</span><h2>'+escapeHtml(model.label||model.id)+'</h2></div>'+
     '<span class="hz-admin-counter">'+number(model.snapshots)+' zapisów</span></div>'+
     '<div class="hz-admin-stats">'+
       metric("Trafność zwycięzcy",percentage(m.winner_accuracy),ready+' zakończonych meczów')+
       metric("Błąd sumy punktów",signed(m.total_mae),"MAE · punkty")+
       metric("Błąd punktów drużyn",signed(m.team_mae),"MAE · punkty")+
       metric("Brier score",signed(m.brier),"Im niżej, tym lepiej")+
     '</div>'+(ready?'<div class="hz-admin-bias">Średni błąd ze znakiem: <b>'+signedBias(m.total_bias)+' pkt</b> <small>(wynik − prognoza; wartość ujemna oznacza zawyżanie)</small></div>':'')+
     '<div class="hz-admin-model-foot"><span>Rozliczone: <b>'+number(model.settled)+'</b> / '+number(model.snapshots)+'</span>'+
     '<span>Zweryfikowane przez audyt: <b>'+number(ready)+'</b></span></div>'+
     (!ready?'<div class="hz-admin-pending">Brak zakończonych i zweryfikowanych prognoz. Wyniki oceny pojawią się po meczach.</div>':'')+
     '</article>';
 }
 function playerAudit(report){
   const models=Array.isArray(report?.models)?report.models:[];
   const error=report?.error||"";
   const marketNames=[["pts","Punkty (PTS)"],["reb","Zbiórki (REB)"],
     ["ast","Asysty (AST)"],["fg3m","Trójki (3PM)"],
     ["pra","Suma PRA"],["minutes","Minuty gry"]];
   const cards=models.map(model=>{
     const stats=model.metrics||{};
     const cells=marketNames.map(([key,label])=>{
       const m=stats[key]||{};
       return '<tr><td>'+label+'</td><td>'+number(m.n)+'</td><td>'+signed(m.mae)+
         '</td><td>'+percentage(m.within_pct)+'</td><td>±'+number(m.tolerance)+'</td></tr>';
     }).join("");
     const title=model.id==="auto_player_form_v74"
       ?"V7.4 · Symulacje zawodników (ESPN)"
       :model.id==="auto_player_minutes_v76"
       ?"V7.6 · Test trendu minut (ESPN)":model.id;
     return '<div class="hz-admin-player-model"><h3>'+escapeHtml(title)+
       '</h3><p>Prognozy zawodników: <b>'+number(model.saved)+
       '</b> · ocenione występy: <b>'+number(model.evaluated_players)+
       '</b> · mecze: <b>'+number(model.games_with_results)+'</b></p>'+
       '<div class="hz-admin-player-table"><table><thead><tr><th>Statystyka</th><th>Próba</th><th>MAE</th><th>W progu</th><th>Próg</th></tr></thead><tbody>'+
       cells+'</tbody></table></div></div>';
   }).join("");
   return '<section class="hz-admin-players-audit"><div class="hz-admin-players-head">'+
     '<span>NOWY TRACKER · SYMULACJE ZAWODNIKÓW</span><h2>Jak trafnie prognozujemy graczy?</h2>'+
     '<p>PTS, REB, AST, 3PM, PRA i minuty · prognozy sprzed meczu, zweryfikowane po oficjalnym box score.</p></div>'+
     (error?'<p class="hz-admin-players-note">'+escapeHtml(error)+'</p>':
      cards||'<p class="hz-admin-players-note">Zbieramy pierwsze prognozy. Wyniki pojawią się po zakończonych meczach.</p>')+
     '<p class="hz-admin-players-note">MAE = średni błąd bezwzględny; „w progu” oznacza odchylenie nie większe niż wskazana tolerancja dla danej statystyki. '+
     'To NIE jest skuteczność zakładów Over/Under. Brak występu lub danych nie jest liczony jako zero.</p></section>';
 }
 function trackerMonitor(monitor){
   const issue=monitor?.error||"";
   const last=monitor?.last_cycle||{},team=monitor?.team||{},players=monitor?.players||{};
   const running=!!monitor?.last_run_utc;
   const impaired=monitor?.last_player_status&&monitor.last_player_status!=="ok";
   const badge=monitor?.stale?"OPÓŹNIONY":impaired?"WYMAGA UWAGI":running?"AKTYWNY":"OCZEKUJE";
   const statusClass=monitor?.stale||impaired?"warn":running?"healthy":"idle";
   return '<section class="hz-admin-monitor"><header><div><span>TRACKER · STAN AUTOMATYCZNEJ ARCHIWIZACJI</span>'+
     '<h2>Monitoring prognoz NBA</h2></div><b class="hz-admin-monitor-state '+statusClass+'">'+badge+'</b></header>'+
     '<p class="hz-admin-monitor-time">Ostatni zapis pracy: <strong>'+
     escapeHtml(monitor?.last_run_utc||"Brak danych z nowego monitoringu")+'</strong>'+
     (running?' UTC · '+number(monitor.last_run_age_hours)+' godz. temu':'')+'</p>'+
     (issue?'<p class="hz-admin-players-note">'+escapeHtml(issue)+'</p>':'')+
     '<div class="hz-admin-monitor-grid">'+
       metric("Prognozy meczów",number(team.saved),"Zapisane rekordy modeli")+
       metric("Mecze · rozliczone rekordy",number(team.settled),"Oczekuje: "+number(team.pending))+
       metric("Prognozy zawodników",number(players.saved),"Zapisane występy modeli")+
       metric("Zawodnicy · ocenione",number(players.settled),"Oczekuje: "+number(players.pending))+
     '</div><p class="hz-admin-players-note">Ostatni cykl: nowe rekordy meczów <b>'+number(last.team_new)+
     '</b>, zawodników <b>'+number(last.player_new)+'</b>; rozliczone rekordy meczowe <b>'+number(last.team_settled)+
     '</b>, zawodników <b>'+number(last.player_settled)+'</b>. Sprawdzono <b>'+number(last.player_games_checked)+
     '</b> meczów pod kątem graczy, prognozy powstały dla <b>'+number(last.player_games_projected)+'</b>.</p>'+
     '<p class="hz-admin-players-note">Liczby oznaczają zapisy modeli i występy graczy, nie unikalne spotkania. '+
     'Opóźnienie jest sygnalizowane po ponad 10 godzinach bez zarejestrowanego cyklu.</p></section>';
 }
 function playerHistory(){
   return '<section class="hz-admin-players-audit hz-admin-player-history"><div class="hz-admin-players-head">'+
     '<span>SZCZEGÓŁOWY AUDYT · ZAWODNICY</span><h2>Prognoza kontra rzeczywisty występ</h2>'+
     '<p>Ostatnie 150 wpisów każdego modelu · wyszukaj zawodnika lub drużynę i sprawdź konkretne błędy.</p></div>'+
     '<div class="hz-admin-player-filters"><input id="hz-admin-player-search" type="search" placeholder="Szukaj zawodnika lub drużyny..." aria-label="Szukaj zawodnika">'+
     '<select id="hz-admin-player-market" aria-label="Wybierz statystykę">'+
     '<option value="pts">Punkty (PTS)</option><option value="reb">Zbiórki (REB)</option>'+
     '<option value="ast">Asysty (AST)</option><option value="fg3m">Trójki (3PM)</option>'+
     '<option value="pra">PRA</option><option value="minutes">Minuty</option></select>'+
     '<select id="hz-admin-player-order" aria-label="Sortowanie">'+
     '<option value="recent">Najnowsze</option><option value="largest">Największe błędy</option></select></div>'+
     '<div class="hz-admin-player-history-count" id="hz-admin-player-history-count"></div>'+
     '<div class="hz-admin-player-history-scroll"><table><thead><tr><th>Data (UTC)</th><th>Zawodnik</th><th>Mecz</th><th>Prognoza</th><th>Wynik</th><th>Wynik − prognoza</th></tr></thead>'+
     '<tbody id="hz-admin-player-history-rows"></tbody></table></div>'+
     '<p class="hz-admin-players-note">„Brak rozliczenia” nie oznacza występu za zero — może chodzić o DNP, brak statystyk albo nierozpoczęty mecz.</p></section>';
 }
 function wirePlayerHistory(report){
   const search=document.getElementById("hz-admin-player-search"),
     market=document.getElementById("hz-admin-player-market"),
     order=document.getElementById("hz-admin-player-order"),
     body=document.getElementById("hz-admin-player-history-rows"),
     count=document.getElementById("hz-admin-player-history-count");
   if(!search||!market||!order||!body||!count)return;
   const records=(report?.models||[]).flatMap(model=>model.recent||[]);
   search.value=playerSearch;market.value=playerMarket;order.value=playerOrder;
   const isNumber=value=>typeof value==="number"&&Number.isFinite(value);
   function update(){
     const phrase=playerSearch.trim().toLocaleLowerCase("pl-PL");
     const filtered=records.filter(r=>[
       r.player,r.team,r.opponent,r.game_id].some(v=>String(v||"").toLocaleLowerCase("pl-PL").includes(phrase)));
     filtered.sort((a,b)=>{
       if(playerOrder==="largest"){
         const delta=r=>isNumber(r.actual?.[playerMarket])&&isNumber(r.pred?.[playerMarket])
           ?Math.abs(r.actual[playerMarket]-r.pred[playerMarket]):-1;
         const difference=delta(b)-delta(a);
         if(difference)return difference;
       }
       return String(b.date||"").localeCompare(String(a.date||""));
     });
     count.textContent="Wyświetlono "+Math.min(filtered.length,70)+" z "+filtered.length+" ostatnich zapisów";
     const tolerance={pts:5,reb:2,ast:2,fg3m:1,pra:7,minutes:5}[playerMarket]||5;
     body.innerHTML=filtered.slice(0,70).map(r=>{
       const pred=r.pred?.[playerMarket],actual=r.actual?.[playerMarket];
       const delta=isNumber(pred)&&isNumber(actual)?actual-pred:null;
       const matchup=r.opponent?r.team+" vs "+r.opponent:r.team;
       return '<tr><td>'+escapeHtml(r.date)+'</td><td><b>'+escapeHtml(r.player)+'</b></td>'+
         '<td>'+escapeHtml(matchup)+'</td><td>'+number(pred)+'</td><td>'+
         (isNumber(actual)?number(actual):'<span class="hz-admin-wait">Brak rozliczenia</span>')+'</td><td>'+
         (delta===null?'—':'<b class="'+(Math.abs(delta)>tolerance?'hz-admin-high-error':'')+'">'+signedBias(delta)+'</b>')+'</td></tr>';
     }).join("")||'<tr><td colspan="6">Brak zapisów dla wybranych filtrów.</td></tr>';
   }
   search.addEventListener("input",()=>{playerSearch=search.value;update()});
   market.addEventListener("change",()=>{playerMarket=market.value;update()});
   order.addEventListener("change",()=>{playerOrder=order.value;update()});
   update();
 }
 function pairedAudit(comparison){
   const models=Array.isArray(comparison?.models)?comparison.models:[];
   const n=Number(comparison?.games)||0;
   const body=models.map(model=>{
     const m=model.metrics||{};
     return '<tr><td>'+escapeHtml(model.label||model.id)+'</td><td>'+percentage(m.winner_accuracy)+
       '</td><td>'+signed(m.total_mae)+'</td><td>'+signed(m.team_mae)+
       '</td><td>'+signed(m.brier)+'</td></tr>';
   }).join("");
   return '<section class="hz-admin-players-audit"><div class="hz-admin-players-head">'+
     '<span>UCZCIWE PORÓWNANIE MODELI</span><h2>Te same zakończone mecze · '+number(n)+'</h2>'+
     '<p>Każdy uwzględniony model oceniamy wyłącznie na wspólnych, zweryfikowanych spotkaniach.</p></div>'+
     (n?'<div class="hz-admin-player-table"><table><thead><tr><th>Model</th><th>Zwycięzca</th><th>MAE sumy</th><th>MAE drużyn</th><th>Brier</th></tr></thead><tbody>'+body+'</tbody></table></div>':
       '<p class="hz-admin-players-note">Za mało wspólnych, rozliczonych spotkań do porównania.</p>')+
     '<p class="hz-admin-players-note">'+(n<30?'Mała próba: różnice nie oznaczają jeszcze przewagi modelu. ':'')+
     'Wszystkie prognozy są historyczne i zapisane przed meczem; mniejszy MAE/Brier jest lepszy.</p></section>';
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
    root.innerHTML='<div class="hz-admin-loading"><span class="hz-admin-loader">◈</span><b>'+(
      loading?'Pobieramy archiwum modeli':'Raport czeka na pierwsze odświeżenie')+'</b>'+
      '<p>Wszystkie wyniki są liczone wyłącznie z zapisanych przed meczem prognoz.</p></div>';
     return;
   }
  if(report.status==="setup_required"||report.status==="connection_issue"){
    root.innerHTML=setupCard(report.status==="connection_issue");
    return;
  }
   if(report.error){
    root.innerHTML='<div class="hz-admin-connection hz-admin-small-error"><b>Archiwum wymaga sprawdzenia</b><p>'+
      escapeHtml(report.error)+'</p></div>';
     return;
   }
   const models=Array.isArray(report.models)?report.models:[];
   if(!models.length){
     root.innerHTML=trackerMonitor(report.tracker_monitor)+
       '<div class="hz-admin-empty">Brak zamrożonych prognoz w sezonie '+escapeHtml(report.season)+'. Tracker musi najpierw zapisać dane.</div>'+
       playerAudit(report.player_tracking)+playerHistory();
     wirePlayerHistory(report.player_tracking);
     return;
   }
   const options=models.map((m,index)=>'<option value="'+index+'">'+escapeHtml(m.label||m.id)+'</option>').join("");
   root.innerHTML='<div class="hz-admin-meta"><span>Sezon '+escapeHtml(report.season)+'</span><span>Aktualizacja '+escapeHtml(String(report.as_of_utc||"").slice(0,16).replace("T"," "))+' UTC</span>'+
     '<span>Dokładność liczona wyłącznie dla zapisów sprzed rozpoczęcia meczów.</span></div>'+
     trackerMonitor(report.tracker_monitor)+
     '<div class="hz-admin-models">'+models.map(modelCard).join("")+'</div>'+
     pairedAudit(report.paired_comparison)+
     playerAudit(report.player_tracking)+
     playerHistory()+
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
   wirePlayerHistory(report.player_tracking);
 }
 window.HoopzaroAdmin={render};
})();
