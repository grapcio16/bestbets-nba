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
        st.markdown("Historia prognoz · wynik przewidywany, rzeczywisty i błąd")
        kind=st.radio("Rodzaj prognozy",list(KINDS),format_func=KINDS.__getitem__,horizontal=True,
                      label_visibility="collapsed",key="hz_tracker_kind")
        left,right=st.columns([2,1])
        with left:
            period=st.date_input("Zakres dat meczów (czas polski)",value=(today-timedelta(days=6),today),
                                 key="hz_tracker_period",format="DD.MM.YYYY")
        with right:
            stat=st.selectbox("Statystyka",list(STAT_NAMES),format_func=STAT_NAMES.__getitem__,key="hz_tracker_stat") if kind=="players" else "PTS"
            if kind!="players":
                st.markdown(health_markup("Zakres danych","Archiwum przedmeczowe","ok"),unsafe_allow_html=True)
        if len(period)!=2:
            st.info("Wybierz początek i koniec zakresu.")
            return
        start,end=period
        if (end-start).days>30:
            st.warning("Wybierz maksymalnie 31 dni.")
            return
        result=load_history(season,kind,start,end)
        if result.get("status")!="ok":
            message={"too_many":"Za dużo prognoz w zakresie. Wybierz krótszy okres.",
                     "setup_required":"Baza Trackera nie jest podłączona.",
                     "invalid_range":"Nieprawidłowy zakres dat."}.get(result.get("status"),"Nie udało się pobrać archiwum.")
            st.warning(message)
            if result.get("diagnostic"):
                st.write("Kod diagnostyczny:",result["diagnostic"])
            return
        records=result.get("rows",[])
        models=sorted({r["model_id"] for r in records},key=model_name)
        a,b,c=st.columns([1,1,2])
        with a:
            model=st.selectbox("Model",[""]+models,format_func=lambda m:model_name(m) if m else "Wszystkie modele",key="hz_tracker_model_"+kind)
        with b:
            status=st.selectbox("Status",["","settled","waiting","upcoming","excluded"],
                                format_func=lambda s:STATE_NAMES[s] if s else "Wszystkie statusy",key="hz_tracker_status")
        with c:
            query=st.text_input("Szukaj zawodnika lub drużyny" if kind=="players" else "Szukaj drużyny",key="hz_tracker_search",placeholder="np. BOS").strip().casefold()
        filtered=[r for r in records if (not model or r["model_id"]==model) and
                  (not query or query in subject(r,kind).casefold()) and
                  (not status or classify(r,kind,stat,now)==status)]
        summary=summarize(filtered,kind,stat,now)
        st.markdown(grid_markup([("Wszystkie prognozy",summary["total"]),
             ("Rozliczone prognozy",summary["settled"]),
             ("Do rozliczenia",summary["waiting"]),
             ("Nadchodzące",summary["upcoming"]),
             ("Wykluczone",summary["excluded"]),
             ("Średni błąd",number(summary["mae"]) if summary["mae"] is not None else "Brak danych",
              "Średni bezwzględny błąd wybranej statystyki lub średni błąd punktów obu drużyn.")],3),unsafe_allow_html=True)
        if summary["daily"]:
            st.subheader("Błąd prognoz według daty")
            st.line_chart(summary["daily"],x="Data",y="Średni błąd",height=210,color="#a99af5")
        st.subheader("Historia rozliczeń")
        if not filtered:
            st.info("Brak prognoz spełniających wybrane filtry.")
        else:
            pages=(len(filtered)+PAGE_SIZE-1)//PAGE_SIZE
            page=st.selectbox("Strona wyników",list(range(1,pages+1)),format_func=lambda i:f"{i} / {pages}",
                              key="hz_tracker_page_"+str(pages))
            offset=(page-1)*PAGE_SIZE
            st.write(f"Pozycje {offset+1}–{min(offset+PAGE_SIZE,len(filtered))} z {len(filtered)}")
            shown=filtered[offset:offset+PAGE_SIZE]
            st.markdown(status_table(history_table(shown,kind,stat,now)),unsafe_allow_html=True)
            with st.expander("Szczegóły wybranej prognozy"):
                index=st.selectbox("Wybierz prognozę z tej strony",list(range(len(shown))),
                    format_func=lambda i:f'{subject(shown[i],kind)} · {model_name(shown[i]["model_id"])} · {date_label(shown[i]["start_utc"])}',
                    key="hz_tracker_detail_"+kind+"_"+str(len(shown)))
                render_detail(st,shown[index],kind,stat,now)
        with st.expander("Ostatnia aktualizacja Trackera i zasady rozliczeń"):
            latest=load_summary(season)
            runs=latest.get("last_run",[])
            if runs:
                r=runs[0]
                st.markdown(health_markup("Ostatnie uruchomienie V7",date_label(r.get("finished_at_utc")),"ok" if r.get("player_status")=="ok" else "warn"),unsafe_allow_html=True)
                st.markdown(grid_markup([("Nowe prognozy drużyn",r.get("team_new")),
                    ("Rozliczenia drużyn",r.get("team_settled")),
                    ("Nowe prognozy zawodników",r.get("player_new")),
                    ("Rozliczenia zawodników",r.get("player_settled"))],4),unsafe_allow_html=True)
            else:
                st.info("Brak danych o ostatnim uruchomieniu Trackera.")
            st.write("Każdy wiersz to osobna zapisana prognoza modelu, nie unikalny mecz. Wyniki są odczytywane z archiwum, bez ponownego generowania.")
            st.write("Rozliczone prognozy mają poprawne dane i zapis przed rozpoczęciem meczu (dla meczów co najmniej 15 minut wcześniej). Brak rozliczenia po starcie to oczekiwanie; nie oznacza automatycznie błędu.")
            st.write("Wyniki drużyn są w kolejności goście : gospodarze. Scenariusz V8 jest osobny od średniej, a błąd meczu dotyczy średniej. Porównanie skuteczności modeli znajduje się w zakładce Silniki AI.")
