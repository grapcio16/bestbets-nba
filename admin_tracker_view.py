"""Tracker: daily settlement workflow, distinct from AI model evaluation."""
from datetime import datetime, timedelta, timezone
from html import escape
from admin_tracker_history import TZ, KINDS, STATS, classify, summarize, values, error_value, finite
from admin_dashboard_ui import grid_markup, table_markup, health_markup, model_name, number

STAT_NAMES = {"PTS":"Punkty (PTS)","REB":"Zbiórki (REB)","AST":"Asysty (AST)",
              "3PM":"Celne trójki (3PM)","MIN":"Minuty (MIN)"}
STATE_NAMES = {"settled":"Rozliczona","waiting":"Do rozliczenia","upcoming":"Nadchodząca","excluded":"Wykluczona"}
PAGE_SIZE = 20

TRACKER_CSS = """<style>
.st-key-hz_tracker_scope [data-testid="stRadio"] [role="radiogroup"]{gap:10px;flex-wrap:wrap}
.st-key-hz_tracker_scope [data-testid="stRadio"] label{background:#172339;border:1px solid #34435e;padding:9px 17px;border-radius:9px;min-width:130px}
.st-key-hz_tracker_scope [data-testid="stRadio"] label:has(input:checked){background:#36345b;border-color:#a28beb}
.st-key-hz_tracker_scope [data-testid="stRadio"] label p{font-size:16px;font-weight:650}
.st-key-hz_tracker_scope [data-testid="stWidgetLabel"] p{font-size:15px;font-weight:600;color:#c8d4e8}
.st-key-hz_tracker_scope [data-baseweb="select"]>div,.st-key-hz_tracker_scope [data-baseweb="input"]{background:#172339;border-color:#34435e;border-radius:9px;min-height:43px}
.st-key-hz_tracker_scope [data-testid="stHeading"] h3{margin-top:.7rem}
.st-key-hz_tracker_scope [data-testid="stVegaLiteChart"]{padding:12px}
.st-key-hz_tracker_scope .hz-data-table td{padding:12px 15px}
.st-key-hz_tracker_scope .hz-data-table td:last-child{font-weight:650}
.st-key-hz_tracker_scope .hz-kpi{min-height:105px}
.st-key-hz_tracker_scope .hz-status{display:inline-block;padding:5px 9px;border-radius:6px;font-size:14px;line-height:1.3;border:1px solid transparent}
.st-key-hz_tracker_scope .hz-status-settled{color:#8be0bd;background:#1c3c37;border-color:#356351}
.st-key-hz_tracker_scope .hz-status-waiting{color:#edc789;background:#3b3328;border-color:#675337}
.st-key-hz_tracker_scope .hz-status-upcoming{color:#acc4ff;background:#26395b;border-color:#415d89}
.st-key-hz_tracker_scope .hz-status-excluded{color:#ffb0b5;background:#442c3a;border-color:#69404c}

.st-key-hz_tracker_scope .hz-match-hero{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:22px;background:linear-gradient(115deg,#1c2b45,#252d4a 50%,#1b2a40);border:1px solid #4b5d83;border-radius:16px;padding:23px 28px;margin:6px 0 10px;text-align:center}
.st-key-hz_tracker_scope .hz-match-team{font-size:29px;font-weight:750;color:#eff4ff;letter-spacing:.02em}
.st-key-hz_tracker_scope .hz-match-role{font-size:15px;color:#b5c6e1;margin-bottom:5px}
.st-key-hz_tracker_scope .hz-match-score{font-size:clamp(27px,3.4vw,48px);font-weight:800;color:#f5f7ff;line-height:1.1;font-variant-numeric:tabular-nums}
.st-key-hz_tracker_scope .hz-match-state{font-size:14px;color:#8be0bd;margin-top:8px}
.st-key-hz_tracker_scope .hz-match-state.pending{color:#edc789}
.st-key-hz_tracker_scope .hz-step-title{font-size:17px;font-weight:700;color:#eaf1ff;margin:7px 0 3px}
.st-key-hz_tracker_scope [data-testid="stButton"] button{min-height:46px;font-size:16px}
.st-key-hz_tracker_scope [data-testid="stButton"] button[kind="primary"]{background:#413b70;border-color:#ac98f2}
.st-key-hz_tracker_scope [data-testid="stButton"] button p{font-size:16px!important}
.st-key-hz_tracker_scope [data-testid="stWidgetLabel"] p{font-size:16px!important}
.st-key-hz_tracker_scope .hz-data-table th{font-size:15px}
.st-key-hz_tracker_scope .hz-data-table td{font-size:17px;padding:15px}
.st-key-hz_tracker_scope .hz-actual{color:#8be0bd;font-weight:750}
@media(max-width:700px){.st-key-hz_tracker_scope .hz-match-hero{padding:16px 10px;gap:8px}.st-key-hz_tracker_scope .hz-match-team{font-size:20px}.st-key-hz_tracker_scope .hz-data-table td{font-size:14px}}
</style>"""

def date_label(value):
    return value.astimezone(TZ).strftime("%d.%m.%Y · %H:%M") if value else "—"

def score_pair(pair, digits=1):
    return " : ".join(number(v,digits) for v in pair) if all(v is not None for v in pair) else "—"

def subject(row,kind):
    if kind=="players":
        return f'{row.get("player_name","")} · {row.get("team","")}'
    game=f'{row.get("away","")} – {row.get("home","")}'
    return f'{game} · Q{row.get("quarter")}' if kind=="quarters" else game

def history_table(rows,kind,stat,now):
    out=[]
    for r in rows:
        state=classify(r,kind,stat,now)
        pred,actual=values(r,kind,stat)
        data={"Data meczu (PL)":date_label(r.get("start_utc")), "Prognoza dla":subject(r,kind),
              "Model":model_name(r["model_id"])}
        if kind=="players":
            data["Prognoza"]=number(pred[0],1)
            data["Wynik"]=number(actual[0],1) if state=="settled" else "—"
        else:
            data["Prognoza (średnia)" if kind=="games" else "Prognoza"]=score_pair(pred)
            if kind=="games":
                data["Scenariusz V8"]=score_pair((r.get("scenario_away"),r.get("scenario_home")),0)
            data["Wynik"]=score_pair(actual,0) if state=="settled" else "—"
        data["Błąd"]=number(error_value(r,kind,stat),2) if state=="settled" else "—"
        data["Status"]=STATE_NAMES[state]
        out.append(data)
    return out

def status_table(rows):
    # All dynamic cells remain escaped by the shared table helper. Replace
    # only exact static status cells, never inject provider-supplied markup.
    markup=table_markup(rows)
    for key,label in STATE_NAMES.items():
        markup=markup.replace(f"<td>{escape(label)}</td>",
            f'<td><span class="hz-status hz-status-{key}">{escape(label)}</span></td>')
    return markup

def render_detail(st,row,kind,stat,now):
    state=classify(row,kind,stat,now)
    pred,actual=values(row,kind,stat)
    st.markdown(health_markup(subject(row,kind),STATE_NAMES[state],
        "ok" if state=="settled" else "bad" if state=="excluded" else "warn"),unsafe_allow_html=True)
    st.write(f"Model {model_name(row['model_id'])} · {date_label(row.get('start_utc'))}")
    if kind=="players":
        kpis=[("Prognoza · "+stat,number(pred[0],1)),
              ("Rzeczywisty wynik",number(actual[0],1) if state=="settled" else "Brak danych"),
              ("Różnica (wynik − prognoza)",number(float(actual[0])-float(pred[0]),2) if state=="settled" else "Brak danych")]
        st.markdown(grid_markup(kpis,3),unsafe_allow_html=True)
    else:
        rows=[]
        for i,team in enumerate((row.get("away"),row.get("home"))):
            rows.append({"Drużyna":team, "Prognoza":number(pred[i],1),
                "Wynik":number(actual[i],0) if state=="settled" else "—",
                "Różnica (wynik − prognoza)":number(float(actual[i])-float(pred[i]),2) if state=="settled" else "—"})
        st.markdown(table_markup(rows),unsafe_allow_html=True)
        if kind=="games" and all(finite(row.get(k)) for k in ("scenario_away","scenario_home")):
            st.markdown(grid_markup([("Scenariusz V8",score_pair((row["scenario_away"],row["scenario_home"]),0)),
                ("Błąd scenariusza",number((abs(float(actual[0])-row["scenario_away"])+abs(float(actual[1])-row["scenario_home"]))/2)
                    if state=="settled" else "Brak danych")],2),unsafe_allow_html=True)
        if finite(row.get("home_win_pct")):
            st.write("Prognozowane prawdopodobieństwo wygranej gospodarzy:", number(row["home_win_pct"],1)+"%")
    st.write("Zapis prognozy:",date_label(row.get("issued")),"· Rozliczenie:",date_label(row.get("settled")))

def consensus(rows,kind,stat="PTS",now=None):
    """Only show a common actual if eligible archived observations agree."""
    actuals={tuple(float(v) for v in values(r,kind,stat)[1])
             for r in rows if classify(r,kind,stat,now)=="settled"}
    if len(actuals)==1:
        return next(iter(actuals)),"settled"
    return None,"conflict" if actuals else "waiting"

def match_hero(away,home,actual,state):
    score=score_pair(actual,0) if actual else "— : —"
    label={"settled":"WYNIK RZECZYWISTY","conflict":"ROZBIEŻNE WYNIKI W ARCHIWUM",
           "waiting":"OCZEKIWANIE NA ROZLICZENIE","upcoming":"MECZ NADCHODZĄCY"}[state]
    css="" if state=="settled" else " pending"
    return (f'<div class="hz-match-hero"><div><div class="hz-match-role">GOŚCIE</div><div class="hz-match-team">{escape(str(away))}</div></div>'
            f'<div><div class="hz-match-score">{escape(score)}</div><div class="hz-match-state{css}">{label}</div></div>'
            f'<div><div class="hz-match-role">GOSPODARZE</div><div class="hz-match-team">{escape(str(home))}</div></div></div>')

def compact_rows(rows,kind,stat,now):
    out=[]
    for r in sorted(rows,key=lambda r:(r.get("quarter") or 0,model_name(r["model_id"]))):
        state=classify(r,kind,stat,now)
        p,a=values(r,kind,stat)
        item={"Model":model_name(r["model_id"])}
        if kind=="quarters":
            item["Kwarta"]=f'Q{r["quarter"]}'
        if kind=="players":
            item["Prognoza"]=number(p[0],1)
            item["Wynik"]=number(a[0],1) if state=="settled" else "—"
            item["Różnica (wynik − prognoza)"]=number(float(a[0])-float(p[0]),1) if state=="settled" else "—"
        else:
            item["Prognoza (średnia)" if kind=="games" else "Prognoza"]=score_pair(p)
            if kind=="games":
                item["Scenariusz V8"]=score_pair((r.get("scenario_away"),r.get("scenario_home")),0)
            item["Wynik"]=score_pair(a,0) if state=="settled" else "—"
            item["Błąd na drużynę"]=number(error_value(r,kind,stat)) if state=="settled" else "—"
            if kind=="games":
                prob=r.get("home_win_pct")
                item["Typ zwycięzcy"]="—"
                if finite(prob) and 0<=float(prob)<=100 and float(prob)!=50:
                    home=float(prob)>50
                    item["Typ zwycięzcy"]=r.get("home") if home else r.get("away")
                    if state=="settled":
                        item["Trafienie"]="Tak" if home==(float(a[1])>float(a[0])) else "Nie"
                item.setdefault("Trafienie","—")
        item["Status"]=STATE_NAMES[state]
        out.append(item)
    return out

def render_tracker(load_history, load_summary):
    import streamlit as st
    from access_control import current_role
    if current_role()!="admin":
        st.error("Brak dostępu.")
        return
    now=datetime.now(timezone.utc)
    today=now.astimezone(TZ).date()
    season="2026-27"
    with st.container(key="hz_tracker_scope"):
        st.markdown(TRACKER_CSS,unsafe_allow_html=True)
        st.markdown("**1. Wybierz dzień · 2. Wybierz mecz · 3. Sprawdź prognozy**")
        date_key="hz_tracker_day"
        if date_key not in st.session_state:
            st.session_state[date_key]=today
        def shift(delta):
            st.session_state[date_key]+=timedelta(days=delta)
        def reset_day():
            st.session_state[date_key]=today
        a,b,c,d=st.columns([1,3,1,1])
        a.button("‹ Wcześniej",key="hz_tracker_prev",on_click=shift,args=(-1,),use_container_width=True)
        day=b.date_input("Dzień meczu (czas polski)",key=date_key,format="DD.MM.YYYY",label_visibility="collapsed")
        c.button("Później ›",key="hz_tracker_next",on_click=shift,args=(1,),use_container_width=True)
        d.button("Dzisiaj",key="hz_tracker_today",on_click=reset_day,use_container_width=True)
        games=load_history(season,"games",day,day)
        if games.get("status")!="ok":
            st.warning("Nie udało się odczytać archiwum meczów.")
            if games.get("diagnostic"):
                st.write("Kod diagnostyczny:",games["diagnostic"])
            return
        all_games=games.get("rows",[])
        if not all_games:
            st.info("Tego dnia nie ma zapisanych prognoz meczowych. Wybierz inną datę.")
            return
        grouped={}
        for row in all_games:
            grouped.setdefault(row["game_id"],[]).append(row)
        ids=sorted(grouped,key=lambda gid:(grouped[gid][0]["start_utc"],gid))
        st.markdown(f'<div class="hz-step-title">Mecze · {len(ids)}</div>',unsafe_allow_html=True)
        def game_label(gid):
            rows=grouped[gid]
            first=rows[0]
            actual,state=consensus(rows,"games",now=now)
            result=score_pair(actual,0) if actual else "brak wyniku"
            return f'{first["start_utc"].astimezone(TZ):%H:%M}  ·  {subject(first,"games")}  ·  {result}'
        gid=st.selectbox("Wybierz mecz",ids,format_func=game_label,key="hz_tracker_match",label_visibility="collapsed")
        selected=grouped[gid]
        first=selected[0]
        actual,state=consensus(selected,"games",now=now)
        if state=="waiting" and first["start_utc"]>now:
            state="upcoming"
        st.markdown(match_hero(first["away"],first["home"],actual,state),unsafe_allow_html=True)
        if state=="conflict":
            st.warning("Modele mają różne zapisane wyniki rzeczywiste. Nie można potwierdzić wspólnego wyniku.")
        kind_key="hz_tracker_kind"
        if st.session_state.get(kind_key) not in KINDS:
            st.session_state[kind_key]="games"
        kind=st.session_state[kind_key]
        def change_kind(k):
            st.session_state[kind_key]=k
        for col,(key,label) in zip(st.columns(3),KINDS.items()):
            col.button({"games":"Wynik meczu","players":"Zawodnicy","quarters":"Kwarty"}[key],
                key="hz_tracker_tab_"+key,type="primary" if kind==key else "secondary",
                use_container_width=True,on_click=change_kind,args=(key,))
        stat="PTS"
        if kind=="games":
            rows=selected
            st.subheader("Jak prognozowały poszczególne modele?")
            st.markdown("Błąd na drużynę: średnia różnica bezwzględna punktów gości i gospodarzy. Typ zwycięzcy wynika z prawdopodobieństwa wygranej.")
        else:
            result=load_history(season,kind,day,day)
            if result.get("status")!="ok":
                st.warning("Nie udało się odczytać prognoz dla tej zakładki.")
                return
            rows=[r for r in result.get("rows",[]) if r["game_id"]==gid]
            if not rows:
                st.info("Brak zapisanych prognoz tego rodzaju dla wybranego meczu.")
                return
            if kind=="players":
                players={r["player_id"]:subject(r,kind) for r in rows}
                a,b=st.columns([2,1])
                pid=a.selectbox("Zawodnik",sorted(players,key=lambda p:(players[p],p)),format_func=players.__getitem__,key="hz_tracker_player")
                stat=b.selectbox("Statystyka",list(STAT_NAMES),format_func=STAT_NAMES.__getitem__,key="hz_tracker_stat")
                rows=[r for r in rows if r["player_id"]==pid]
                actual_player,player_state=consensus(rows,kind,stat,now)
                st.subheader(players[pid])
                st.markdown(grid_markup([("Rzeczywisty wynik · "+stat,number(actual_player[0],1) if actual_player else "Brak danych"),
                    ("Zapisane prognozy",len(rows))],2),unsafe_allow_html=True)
                if player_state=="conflict":
                    st.warning("Różne wyniki rzeczywiste w archiwum modeli.")
            else:
                opts=sorted({r["quarter"] for r in rows})
                quarter=st.selectbox("Kwarta",opts,format_func=lambda q:f"Q{q}",key="hz_tracker_quarter")
                rows=[r for r in rows if r["quarter"]==quarter]
                qa,qs=consensus(rows,kind,stat,now)
                st.subheader(f"Kwarta {quarter}")
                st.markdown(match_hero(first["away"],first["home"],qa,qs),unsafe_allow_html=True)
        st.markdown(status_table(compact_rows(rows,kind,stat,now)),unsafe_allow_html=True)
        with st.expander("Szczegóły zapisu prognozy"):
            idx=st.selectbox("Model",range(len(rows)),format_func=lambda i:model_name(rows[i]["model_id"]),key="hz_tracker_detail_model")
            render_detail(st,rows[idx],kind,stat,now)
        with st.expander("Ostatnie rozliczenie Trackera i zasady"):
            runs=load_summary(season).get("last_run",[])
            if runs:
                st.write("Ostatnie uruchomienie V7:",date_label(runs[0].get("finished_at_utc")))
            st.write("Wszystkie wyniki pochodzą z archiwum. Prognozy meczowe muszą być zapisane co najmniej 15 minut przed startem; zawodników i kwart przed startem. Brak rozliczenia nie oznacza automatycznie błędu.")
            st.write("Porównanie średniej skuteczności wielu meczów znajduje się w zakładce Silniki AI.")
