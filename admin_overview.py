"""Private overview: recorded activity, feature usage and operational health."""
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from html import escape
from admin_dashboard_ui import grid_markup, health_markup, table_markup, number

PAGES={"home":"Centrum","props":"Player Props","games":"Terminarz","simulations":"Symulacje","players":"Zawodnicy","teams":"Drużyny","settings":"Ustawienia"}
FEATURES={"simulation":"Symulacje meczów","player_simulation":"Symulacje zawodników","scenario":"Scenariusze","minutes":"Minuty zawodników","props":"Player Props","backtest":"Backtest"}
MISSING="Brak danych"
CSS="""<style>
.st-key-hz_overview .hz-over-banner{display:flex;justify-content:space-between;align-items:center;gap:16px;border:1px solid #475775;border-radius:14px;background:linear-gradient(110deg,#253352,#242d48 62%,#17263a);padding:18px 22px;margin-bottom:8px}
.st-key-hz_overview .hz-over-banner strong{font-size:21px;color:#f0f5ff;display:block}
.st-key-hz_overview .hz-over-banner span{font-size:15px;color:#bdcce3}
.st-key-hz_overview .hz-over-pill{font-weight:700;color:#d2c3ff!important;background:#393455;border:1px solid #65568b;padding:7px 12px;border-radius:8px;white-space:nowrap}
.st-key-hz_overview .hz-kpi{min-height:126px}
.st-key-hz_overview .hz-kpi-value{font-size:39px!important}
.st-key-hz_overview .hz-over-panel{background:linear-gradient(145deg,#19263a,#151f30);border:1px solid #34435e;border-radius:13px;padding:20px;margin-bottom:4px}
.st-key-hz_overview .hz-over-line{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px;font-size:16px;color:#e6eefb}
.st-key-hz_overview .hz-over-line strong{font-size:25px;color:#edf4ff}
.st-key-hz_overview .hz-over-bars{display:flex;align-items:flex-end;gap:8px;min-height:170px;overflow-x:auto;padding:8px 0}
.st-key-hz_overview .hz-over-day{display:grid;grid-template-rows:20px 115px 22px;align-items:end;min-width:34px;flex:1;gap:4px;text-align:center;font-size:13px;color:#b8c5d8}
.st-key-hz_overview .hz-over-day b{font-size:14px;color:#e7edff}
.st-key-hz_overview .hz-over-track{height:115px;display:flex;align-items:flex-end;justify-content:center;border-bottom:1px solid #42536c}
.st-key-hz_overview .hz-over-fill{width:min(70%,42px);background:linear-gradient(0deg,#587cc7,#a694fa);border-radius:5px 5px 0 0}
.st-key-hz_overview .hz-over-rank{display:grid;grid-template-columns:minmax(110px,1.3fr) minmax(35px,1fr) 46px;gap:10px;align-items:center;margin:15px 0;font-size:15px;color:#e7effb}
.st-key-hz_overview .hz-over-rank strong{text-align:right;font-variant-numeric:tabular-nums}
.st-key-hz_overview .hz-over-meter{height:9px;border-radius:8px;background:#2b3a51;overflow:hidden}
.st-key-hz_overview .hz-over-meter span{height:100%;display:block;border-radius:8px;background:#56cabb}
.st-key-hz_overview .hz-over-empty{color:#b9c7da;font-size:16px;min-height:100px;display:grid;place-items:center;text-align:center}
.st-key-hz_overview [data-testid="stButton"] button{min-height:43px}
@media(max-width:650px){.st-key-hz_overview .hz-over-banner{align-items:flex-start;flex-direction:column}.st-key-hz_overview .hz-over-panel{padding:14px}.st-key-hz_overview .hz-kpi-value{font-size:30px!important}}
</style>"""

def count(value):
    try:
        v=int(value)
        return v if v>=0 else None
    except (TypeError,ValueError,OverflowError):
        return None

def total(rows,key):
    vals=[count(r.get(key)) for r in rows]
    return sum(vals) if all(v is not None for v in vals) else None

def display(v):
    return f"{v:,}".replace(","," ") if isinstance(v,int) else MISSING

def aggregate(registry,usage):
    a=registry.get("status")=="ok"
    u=usage.get("status")=="ok"
    accounts=registry.get("accounts",[])
    session=(usage.get("sessions") or [{}])[0]
    features=usage.get("features",[])
    return {"accounts":total(accounts,"observed_accounts") if a else None,
            "active_accounts":total(accounts,"seen_last_24_hours") if a else None,
            "sessions":count(session.get("recent_sessions")) if u else None,
            "calls":total(features,"calls") if u else None,
            "failures":total(features,"failures") if u else None}

def feature_rows(report):
    if report.get("status")!="ok":
        return []
    return [{"Funkcja":FEATURES.get(r.get("feature"),str(r.get("feature","—"))),
             "Wywołania":display(count(r.get("calls"))),
             "Błędy":display(count(r.get("failures"))),
             "Średni czas (s)":number(float(r["avg_ms"])/1000,2) if r.get("avg_ms") is not None else "—"}
            for r in report.get("features",[])]

def panel_empty(message):
    return '<div class="hz-over-panel"><div class="hz-over-empty">'+escape(message)+'</div></div>'

def daily_chart(report, days, today):
    if report.get("status")!="ok":
        return panel_empty("Dane sesji niedostępne.")
    lower=today-timedelta(days=days-1)
    points=[]
    for r in report.get("daily",[]):
        try:
            d=date.fromisoformat(str(r["day"])[:10])
        except (KeyError,ValueError):
            continue
        n=count(r.get("sessions"))
        if lower<=d<=today and n is not None:
            points.append((d,n))
    if not points:
        return panel_empty("Brak zapisanej aktywności w tym okresie.")
    points.sort()
    maximum=max(1,max(n for _,n in points))
    bars=[]
    for d,n in points:
        label=d.strftime("%d.%m")
        bars.append(f'<div class="hz-over-day" title="{d.isoformat()} · {n} sesji"><b>{n}</b><div class="hz-over-track"><div class="hz-over-fill" style="height:{100*n/maximum:.3f}%"></div></div><span>{label}</span></div>')
    return '<div class="hz-over-panel"><div class="hz-over-line"><span>Dni z zapisaną aktywnością</span><strong>'+str(len(points))+'</strong></div><div class="hz-over-bars">'+''.join(bars)+'</div></div>'

def page_chart(report):
    if report.get("status")!="ok":
        return panel_empty("Dane zakładek niedostępne.")
    rows=[(PAGES.get(r.get("page"),str(r.get("page","—"))),count(r.get("sessions"))) for r in report.get("pages",[])]
    rows=sorted([(label,n) for label,n in rows if n is not None],key=lambda x:(-x[1],x[0]))
    if not rows:
        return panel_empty("Brak zapisanych odwiedzin zakładek.")
    maximum=max(1,max(n for _,n in rows))
    return '<div class="hz-over-panel">'+''.join(f'<div class="hz-over-rank"><span>{escape(label)}</span><div class="hz-over-meter"><span style="width:{100*n/maximum:.3f}%"></span></div><strong>{n}</strong></div>' for label,n in rows)+'</div>'

def render_overview(registry, usage, snapshot, select_section):
    import streamlit as st
    from access_control import current_role
    if current_role()!="admin":
        st.error("Brak dostępu.")
        return
    stats=aggregate(registry,usage)
    with st.container(key="hz_overview"):
        st.markdown(CSS,unsafe_allow_html=True)
        st.markdown('<div class="hz-over-banner"><div><strong>Aktywność Hoopzaro</strong><span>Rzeczywiste pomiary z aktualnego pilota monitoringu</span></div><span class="hz-over-pill">PILOT ADMIN</span></div>',unsafe_allow_html=True)
        st.markdown(grid_markup([
            ("Zaobserwowane konta",display(stats["accounts"])),
            ("Aktywne konta · 24 godz.",display(stats["active_accounts"])),
            ("Sesje · ostatnie 3 min",display(stats["sessions"]),"Niedawny sygnał aktywności, nie liczba osób online."),
            ("Wywołania funkcji · 7 dni",display(stats["calls"]))],4),unsafe_allow_html=True)
        left,right=st.columns([3,2])
        with left:
            st.subheader("Aktywność dzienna")
            period=st.radio("Okres", [7,30],format_func=lambda n:f"{n} dni",horizontal=True,key="hz_over_period",label_visibility="collapsed")
            st.markdown(daily_chart(usage,period,datetime.now(timezone.utc).date()),unsafe_allow_html=True)
            st.markdown("Sesje dzienne (UTC). Brakujące dni nie są uzupełniane zerami.")
        with right:
            st.subheader("Popularność zakładek · 7 dni")
            st.markdown(page_chart(usage),unsafe_allow_html=True)
            st.markdown("Liczba sesji z odnotowaną aktywnością w zakładce.")
        st.button("Przejdź do użytkowników",key="hz_over_users",on_click=select_section,args=("Users",),use_container_width=True)
        st.subheader("Wykorzystanie funkcji · 7 dni")
        rows=feature_rows(usage)
        if rows:
            st.markdown(table_markup(rows),unsafe_allow_html=True)
        else:
            st.markdown(panel_empty("Brak zapisanych wywołań funkcji." if usage.get("status")=="ok" else "Dane funkcji niedostępne."),unsafe_allow_html=True)
        st.markdown(grid_markup([("Zarejestrowane błędy funkcji",display(stats["failures"]))],1),unsafe_allow_html=True)
        st.button("Przejdź do wydajności",key="hz_over_performance",on_click=select_section,args=("Performance",),use_container_width=True)
        st.divider()
        a,b=st.columns(2)
        with a:
            st.subheader("Przychody")
            st.markdown(grid_markup([("Płatne subskrypcje","Nie podłączono"),("Rzeczywiste przychody","Nie podłączono")],2),unsafe_allow_html=True)
            st.button("Przejdź do przychodów",key="hz_over_revenue",on_click=select_section,args=("Revenue",),use_container_width=True)
        with b:
            st.subheader("Stan techniczny")
            status=snapshot.get("status")
            v8={"recent_evidence":"Aktualne dane","stale":"Nieaktualne dane","setup_required":"Wymaga konfiguracji"}.get(status,"Brak potwierdzonych danych")
            for label,ok in [("Rejestr kont",registry.get("status")=="ok"),("Odczyt telemetrii",usage.get("status")=="ok")]:
                st.markdown(health_markup(label,"Połączono" if ok else "Niedostępne","ok" if ok else "warn"),unsafe_allow_html=True)
            st.markdown(health_markup("Silnik V8",v8,"ok" if status=="recent_evidence" else "warn"),unsafe_allow_html=True)
            st.button("Przejdź do centrum danych",key="hz_over_data",on_click=select_section,args=("Data Center",),use_container_width=True)
        with st.expander("Zakres pomiarów"):
            st.write("Pilotaż obejmuje aktywność administratora. Sesje nie są unikalnymi osobami ani dokładnymi odsłonami. Wywołania obejmują pomiary po stronie serwera, nie czas renderowania. Zarejestrowany brak błędów nie potwierdza bezawaryjności całej aplikacji. Okres siedmiu dni obejmuje bieżący dzień UTC i sześć wcześniejszych dni.")
