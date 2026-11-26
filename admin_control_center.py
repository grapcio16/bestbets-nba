"""Private Hoopzaro Control Center; opt-in audit only, no production setting mutations."""
from __future__ import annotations

SECTIONS = (
    "Overview", "Data Center", "AI Engines", "Tracker", "Users",
    "Revenue", "Performance", "Security", "Settings",
)

SECTION_LABELS = {"Overview":"Przegląd", "Data Center":"Centrum danych", "AI Engines":"Silniki AI",
    "Tracker":"Tracker", "Users":"Użytkownicy", "Revenue":"Przychody",
    "Performance":"Wydajność", "Security":"Bezpieczeństwo", "Settings":"Ustawienia"}
STATUS_LABELS = {"ok":"Poprawnie", "setup_required":"Wymaga konfiguracji", "unavailable":"Niedostępne",
    "recent_evidence":"Aktualne dane", "stale":"Nieaktualne dane", "no_evidence":"Brak danych",
    "invalid_timestamp":"Nieprawidłowa data", "insufficient_training":"Za mało próbek",
    "waiting_for_settled_games":"Oczekiwanie na rozliczenia", "schema_ok":"Poprawna odpowiedź",
    "empty_response":"Pusta odpowiedź", "invalid_schema":"Błędny format", "http_error":"Błąd HTTP",
    "no_recent_report":"Brak aktualnego raportu", "test":"Testowy", "non_test":"Nietestowy",
    "missing":"Brak", "invalid":"Nieprawidłowy", "denied":"Brak dostępu", "active":"Aktywna",
    "trialing":"Okres próbny", "past_due":"Zaległa", "canceled":"Anulowana", "unpaid":"Nieopłacona",
    "incomplete":"Niekompletna", "incomplete_expired":"Wygasła", "paused":"Wstrzymana",
    "page_limit_reached":"Przekroczono limit stron", "test_restricted_key_required":"Wymagany ograniczony klucz testowy",
    "success":"Sukces", "failure":"Błąd", "subjects":"Identyfikatory OIDC", "emails":"Adresy e-mail", "admin":"ADMIN", "premium":"Premium", "free":"Free",
    "refresh_telemetry":"Odświeżenie danych", "review_access":"Przegląd uprawnień", "review_models":"Przegląd modeli",
    "ESPN scoreboard":"ESPN · wyniki", "NBA scoreboard":"NBA · wyniki", "ESPN injuries":"ESPN · kontuzje"}
COLUMN_LABELS = {"model_id":"Model", "archived":"Zarchiwizowane", "settled":"Rozliczone",
    "source":"Źródło", "status":"Status", "http_status":"HTTP", "elapsed_ms":"Czas (ms)", "rows":"Rekordy",
    "checked_utc":"Sprawdzono (UTC)", "pts_mae":"MAE punktów", "reb_mae":"MAE zbiórek", "ast_mae":"MAE asyst",
    "team_points_mae":"MAE punktów drużyny", "finished_at_utc":"Zakończono (UTC)", "team_new":"Nowe prognozy drużyn",
    "team_settled":"Rozliczone drużyny", "player_new":"Nowe prognozy zawodników", "player_settled":"Rozliczeni zawodnicy",
    "player_status":"Status zawodników", "last_observed_role":"Rola", "observed_accounts":"Konta",
    "seen_last_24_hours":"Aktywni 24 godz.", "seen_last_7_days":"Aktywni 7 dni", "seen_last_30_days":"Aktywni 30 dni",
    "first_seen_last_7_days":"Nowe konta 7 dni", "Identifier type":"Typ identyfikatora", "Admin entries":"Wpisy ADMIN",
    "Premium entries":"Wpisy Premium", "Overlapping entries":"Wspólne wpisy", "occurred_at":"Data zdarzenia",
    "action":"Zdarzenie", "outcome":"Wynik"}
def localized(value):
    if isinstance(value, bool):
        return "Tak" if value else "Nie"
    if isinstance(value, str):
        return STATUS_LABELS.get(value, value)
    return value

def authorized(role: str) -> bool:
    return role == "admin"

def render(*, dedicated=False):
    import streamlit as st
    from access_control import current_role
    # Never rely on URL, browser state or premium entitlement for authorization.
    if not authorized(current_role()):
        st.error("Brak dostępu.")
        st.stop()
        return
    from admin_data_intelligence import read_snapshot, read_scorecard
    from tracker_storage import tracker_database_url
    from admin_source_monitor import source_snapshot
    from admin_performance import database_probe, summarize_sources
    from admin_live_data import tracker_summary, account_summary, stripe_test_summary, official_injury_freshness
    from admin_security import audit_enabled, record_admin_event
    from account_registry import registry_enabled, free_props_enabled

    def table(rows, **kwargs):
        st.dataframe([{COLUMN_LABELS.get(k,k): localized(v) for k,v in dict(row).items()} for row in rows], **kwargs)

    @st.cache_data(ttl=120, show_spinner=False)
    def snapshot(season):
        return read_snapshot(tracker_database_url(), season)

    @st.cache_data(ttl=300, show_spinner=False)
    def scorecard(season):
        return read_scorecard(tracker_database_url(), season)

    @st.cache_data(ttl=300, show_spinner=False)
    def sources():
        return source_snapshot()

    @st.cache_data(ttl=300, show_spinner=False)
    def database_health():
        return database_probe(tracker_database_url())

    @st.cache_data(ttl=180, show_spinner=False)
    def tracker_metrics(season):
        return tracker_summary(tracker_database_url(), season)

    @st.cache_data(ttl=300, show_spinner=False)
    def accounts():
        return account_summary()

    @st.cache_data(ttl=300, show_spinner=False)
    def stripe_test():
        return stripe_test_summary()

    @st.cache_data(ttl=300, show_spinner=False)
    def injury_index():
        return official_injury_freshness()

    st.markdown("""<style>
    .stApp {background:radial-gradient(ellipse at 94% 0%,#241644 0%,#0a1224 38%,#080d19 75%);color:#eaf1ff;}
    [data-testid="stHeader"]{background:rgba(8,13,25,.94);}
    [data-testid="stMainBlockContainer"]{max-width:1780px;padding:4.6rem 2.8rem 3rem;}
    [data-testid="stSidebar"]{background:linear-gradient(180deg,#121c34,#0c1224);border-right:1px solid #344363;min-width:255px;}
    [data-testid="stSidebar"] [data-testid="stSidebarContent"]{padding:1rem .5rem;}
    [data-testid="stSidebar"] h1{font-size:27px!important;color:#c1a8ff!important;letter-spacing:.075em;margin-bottom:0;}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p{color:#c0cce5;font-size:14px;}
    [data-testid="stSidebar"] [role="radiogroup"]{gap:5px;}
    [data-testid="stSidebar"] [data-testid="stRadio"] label{width:100%;padding:12px 14px;border:1px solid transparent;border-radius:10px;cursor:pointer;transition:background .15s;}
    [data-testid="stSidebar"] [data-testid="stRadio"] label p{font-size:16px;font-weight:600;color:#e3ecff;}
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover{background:#20304c;}
    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked){background:linear-gradient(90deg,#2a2454,#182a48);border-color:#6e55c4;box-shadow:inset 3px 0 #a58aff,0 0 15px #7758e521;}
    [data-testid="stSidebar"] [data-testid="stRadio"] label:focus-within{outline:2px solid #c4a5ff;outline-offset:2px;}
    [data-testid="stSidebar"] [data-testid="stRadio"] label>div:first-child{position:absolute;opacity:0;pointer-events:none;}
    [data-testid="stMainBlockContainer"] h1{font-size:42px;font-weight:750;letter-spacing:-.035em;color:#f2f5ff;}
    [data-testid="stMainBlockContainer"] h2,[data-testid="stMainBlockContainer"] h3{font-weight:650;color:#eef4ff;letter-spacing:-.018em;}
    [data-testid="stMainBlockContainer"] h3{font-size:23px;}
    [data-testid="stMainBlockContainer"] [data-testid="stMarkdownContainer"] p{color:#c9d6ee;font-size:15px;line-height:1.5;}
    [data-testid="stMetric"]{border:1px solid #394664;border-top:2px solid #9876ff;border-radius:17px;padding:20px 22px;min-height:138px;background:linear-gradient(145deg,#192840,#121a30);box-shadow:0 10px 30px #0004,0 0 17px #7955e316;}
    [data-testid="stMetricLabel"] p{color:#b7c5e1!important;font-size:15px!important;font-weight:600;white-space:normal;}
    [data-testid="stMetricValue"]{color:#d5c8ff;font-size:clamp(23px,2.05vw,36px);font-weight:750;font-variant-numeric:tabular-nums;letter-spacing:-.035em;}
    [data-testid="stMetricValue"]>div{white-space:normal;overflow-wrap:anywhere;}
    [data-testid="stDataFrame"],[data-testid="stExpander"],[data-testid="stVegaLiteChart"],[data-testid="stForm"]{border:1px solid #34435f;border-radius:14px;overflow:hidden;background:#111a2d;}
    [data-testid="stAlert"]{border:1px solid #344b72;border-radius:12px;}
    [data-testid="stButton"] button,[data-testid="stFormSubmitButton"] button{border:1px solid #7259be;border-radius:10px;background:#222846;color:#f1edff;font-weight:600;min-height:42px;}
    [data-testid="stButton"] button:hover{background:#3b2c70;border-color:#b29bff;}
    [data-testid="stSidebar"] [data-testid="stButton"] button{width:100%;}
    [data-testid="stMainBlockContainer"] hr{border-color:#34415a;margin:1.4rem 0;}
    @media(max-width:1100px){[data-testid="stMainBlockContainer"]{padding:4rem 1.5rem 2rem;}}
    @media(max-width:700px){[data-testid="stMainBlockContainer"]{padding:4rem 1rem 2rem;}[data-testid="stMetric"]{min-height:100px;padding:14px;}[data-testid="stMainBlockContainer"] h1{font-size:31px;}[data-testid="stSidebar"]{min-width:0;}}
    </style>""", unsafe_allow_html=True)
    st.sidebar.title("HOOPZARO")
    st.sidebar.markdown("**CENTRUM STEROWANIA · ADMIN**")
    section = st.sidebar.radio("Menu", SECTIONS, format_func=SECTION_LABELS.__getitem__, label_visibility="collapsed")
    if not dedicated:
        st.sidebar.markdown("[Powrót do Hoopzaro](?)")
    st.title(SECTION_LABELS[section])
    if st.sidebar.button("Odśwież dane"):
        snapshot.clear()
        scorecard.clear()
        sources.clear()
        database_health.clear()
        tracker_metrics.clear()
        accounts.clear()
        stripe_test.clear()
        injury_index.clear()
        if audit_enabled() and not record_admin_event("refresh_telemetry", "success"):
            st.warning("Dane odświeżone. Nie zapisano zdarzenia audytu.")
    if dedicated and st.sidebar.button("Wyloguj się"):
        st.logout()
        st.stop()
        return
    if section == "Overview":
        st.subheader("Użytkownicy i aktywność")
        registry = accounts()
        fields = (("Zaobserwowane konta", "observed_accounts"),
                  ("Aktywni · 24 godz.", "seen_last_24_hours"),
                  ("Aktywni · 7 dni", "seen_last_7_days"),
                  ("Aktywni · 30 dni", "seen_last_30_days"),
                  ("Nowe konta · 7 dni", "first_seen_last_7_days"))
        rows = registry.get("accounts", [])
        available = registry.get("status") == "ok"
        cols = st.columns(3)
        for i, (label, key) in enumerate(fields):
            if i == 3:
                cols = st.columns(3)
            value = sum(r[key] for r in rows) if available and all(key in r for r in rows) else "Brak danych"
            cols[i % 3].metric(label, value, help="Liczba zalogowanych kont zaobserwowanych przez aplikację, w tym ADMIN. Nie obejmuje anonimowych wizyt ani pomiaru użytkowników online.")
        cols[2].metric("Darmowe analizy · dziś (UTC)",
                       registry["quota"][0]["reservations_today"] if available else "Brak danych")
        if not available:
            st.info("Rejestr kont nie jest podłączony lub jest niedostępny.")
        cols = st.columns(2)
        cols[0].metric("Rzeczywiste przychody", "Nie podłączono")
        cols[1].metric("Aktywne płatne subskrypcje", "Nie podłączono")
        if available and rows and all("last_observed_role" in r for r in rows):
            st.subheader("Podział kont według uprawnień")
            st.bar_chart([{"Rola":localized(r["last_observed_role"]), "Konta":r["observed_accounts"]} for r in rows], x="Rola", y="Konta")
            st.markdown("Role kont, nie płatne subskrypcje.")
        st.divider()
        st.subheader("Dane i silniki AI")
    if section in ("Overview", "Data Center", "AI Engines", "Tracker"):
        data = snapshot("2026-27")
        worker = data.get("worker") or {}
        models = data.get("models") or []
        st.write("Status silnika V8:", localized(data.get("status", "unavailable")))
        if section in ("Overview", "Data Center"):
            cols = st.columns(3)
            for col, name, field in zip(cols, ("Zebrane mecze", "Próbki treningowe", "Odrzucone statystyki meczowe"),
                                      ("observed_games", "trainable_examples", "rejected_boxscores")):
                col.metric(name, worker.get(field, "Brak danych"))
            if worker.get("run_utc"):
                st.write("Ostatnia praca silnika (UTC): " + worker["run_utc"])
            if section == "Data Center":
                st.write("Minimum próbek treningowych:", worker.get("minimum_examples", "Brak danych"))
                st.write("Nowe statystyki meczowe:", worker.get("newly_ingested_boxscores", "Brak danych"))
                st.subheader("Dostępność źródeł danych")
                st.markdown("Test odpowiedzi API, nie całej aplikacji.")
                results = sources()
                table(results, hide_index=True, use_container_width=True)
                issues = [r["source"] for r in results if r["status"] not in ("schema_ok", "empty_response")]
                if issues:
                    st.warning("Źródła wymagające sprawdzenia: " + ", ".join(localized(i) for i in issues))
                if any(r["status"] == "empty_response" for r in results):
                    st.info("Pusta odpowiedź nie potwierdza kompletności danych.")
                st.subheader("Oficjalny raport kontuzji NBA")
                injury = injury_index()
                st.write("Status publikacji:", localized(injury.get("status", "unavailable")))
                if injury.get("published_utc"):
                    st.write("Publikacja (UTC): " + injury["published_utc"])
                st.markdown("Status publikacji nie potwierdza kompletności raportu.")
        if section in ("Overview", "AI Engines", "Tracker"):
            st.subheader("Archiwum V8")
            if models:
                table(models, hide_index=True, use_container_width=True)
            else:
                st.info("Brak zweryfikowanego archiwum.")
        if section in ("AI Engines", "Tracker"):
            report = scorecard("2026-27")
            st.subheader("Skuteczność prognoz przedmeczowych")
            if report.get("status") in ("unavailable", "setup_required"):
                st.warning("Brak zweryfikowanej oceny modeli.")
            elif report.get("status") == "waiting_for_settled_games":
                st.info("Oczekiwanie na rozliczone prognozy V8.")
            rows = report.get("common_game_comparisons") or []
            if rows:
                st.markdown("Porównania na tych samych meczach w obrębie pary modeli.")
                for comparison in rows:
                    with st.expander(f'{comparison["left"]} / {comparison["right"]} · {comparison["same_game_n"]} meczów'):
                        if comparison.get("historical_training_sample_differs"):
                            st.warning("Różne próbki treningowe — nie można wyizolować wpływu zmian modelu.")
                        metrics = []
                        for side in ("left", "right"):
                            m = comparison[side + "_metrics"]
                            metrics.append({
                                "Model": comparison[side],
                                "Mecze": m.get("n"),
                                "MAE drużyn": m.get("team_points_mae"),
                                "MAE sumy": m.get("total_points_mae"),
                                "Trafność zwycięzcy (%)": m.get("winner_hit_pct"),
                                "Brier": m.get("brier"),
                                "MAE scenariusza": m.get("scenario_team_points_mae"),
                                "Pokrycie przedziału (%)": m.get("total_80pct_interval_coverage"),
                                "Sprawdzone przedziały": m.get("total_intervals_checked"),
                            })
                        table(metrics, hide_index=True, use_container_width=True)
            else:
                st.info("Brak porównań na wspólnych meczach.")
            st.markdown("Mała próba nie przesądza o przewadze modelu. Niższe MAE i Brier są lepsze.")
        if section in ("Overview", "Tracker"):
            detail = tracker_metrics("2026-27")
            st.subheader("Tracker · zawodnicy i kwarty")
            if detail.get("status") == "ok":
                player_rows = detail.get("players", [])
                quarter_rows = detail.get("quarters", [])
                cols = st.columns(2)
                cols[0].metric("Rozliczone prognozy zawodników", sum(row["settled"] for row in player_rows))
                cols[1].metric("Rozliczone prognozy kwart", sum(row["settled"] for row in quarter_rows))
                if detail.get("last_run"):
                    st.write("**Ostatnie rozliczenie V7**")
                    table(detail["last_run"], hide_index=True, use_container_width=True)
                if section == "Tracker":
                    st.write("Punkty, zbiórki i asysty zawodników")
                    table(player_rows, hide_index=True, use_container_width=True)
                    st.write("Archiwum kwart")
                    table(quarter_rows, hide_index=True, use_container_width=True)
                    st.markdown("Własna próba każdego modelu — nie porównanie wspólnych meczów.")
            else:
                st.info("Archiwum prognoz zawodników i kwart niedostępne.")
        return
    if section == "Performance":
        st.subheader("Neon · połączenie z bazą")
        db = database_health()
        cols = st.columns(3)
        for col, label, key in zip(cols, ("Połączenie", "Zapytanie", "Łącznie"),
                                   ("connect_ms", "query_ms", "total_ms")):
            value = db.get(key)
            col.metric(label, f"{value:.1f} ms" if value is not None else "Brak danych")
        if db["status"] != "ok":
            st.warning("Nie udało się sprawdzić bazy danych.")
        st.write("Sprawdzono (UTC): " + db["checked_utc"])
        st.subheader("Czas odpowiedzi źródeł")
        results = sources()
        ranked = summarize_sources(results)
        if ranked:
            st.bar_chart([{"Źródło": localized(r["source"]), "Milisekundy": r["elapsed_ms"]} for r in ranked], x="Źródło", y="Milisekundy")
            st.markdown("Udane pomiary API wraz z przetworzeniem odpowiedzi.")
        else:
            st.info("Brak pomiarów czasu odpowiedzi.")
        table(results, hide_index=True, use_container_width=True)
        st.info("Pomiar czasu renderowania, zasobów i historii zapytań nie jest podłączony.")
        return
    if section == "Users":
        from admin_user_management import access_snapshot
        access = access_snapshot()
        if access.get("status") != "ok":
            st.error("Brak dostępu.")
            return
        st.subheader("Konta i uprawnienia")
        st.write("Logowanie OIDC:", "Skonfigurowano" if access["oidc_configured"] else "Nie skonfigurowano")
        table(access["allowlist_counts"], hide_index=True, use_container_width=True)
        st.markdown("Identyfikatory konfiguracji, nie liczba osób.")
        st.write("Rejestracja aktywności:", "Włączona" if registry_enabled() else "Wyłączona")
        st.write("Limit darmowych analiz:", "Włączona" if free_props_enabled() else "Wyłączona")
        st.markdown("Limit resetuje się o północy UTC, jeśli został włączony.")
        st.subheader("Rejestr kont i aktywność")
        registry = accounts()
        if registry.get("status") == "ok":
            rows = registry["accounts"]
            cols = st.columns(3)
            cols[0].metric("Zaobserwowane konta", sum(r["observed_accounts"] for r in rows), help="Konta zaobserwowane przez aplikację, nie rejestr Google ani płatności.")
            cols[1].metric("Aktywni · 30 dni", sum(r["seen_last_30_days"] for r in rows))
            cols[2].metric("Darmowe analizy · dziś (UTC)", registry["quota"][0]["reservations_today"])
            table(rows, hide_index=True, use_container_width=True)
        else:
            st.info("Rejestr kont niedostępny.")
        return
    if section == "Security":
        from admin_security import security_snapshot, read_recent_events
        security = security_snapshot()
        if security.get("status") != "ok":
            st.error("Brak dostępu.")
            return
        st.subheader("Diagnostyka dostępu")
        cols = st.columns(2)
        cols[0].metric("Identyfikatory ADMIN", security["admin_identifier_entries"])
        cols[1].metric("Powielone identyfikatory", security["overlap_entries"])
        st.markdown("Identyfikatory nie oznaczają unikalnych osób.")
        st.write("Logowanie OIDC:", "Skonfigurowano" if security["oidc_configured"] else "Brak")
        st.write("Baza audytu:", "Skonfigurowano" if security["audit_storage_configured"] else "Brak")
        st.write("Klucz audytu:", "Skonfigurowano" if security["audit_key_configured"] else "Brak lub zbyt krótki")
        if security["overlap_entries"]:
            st.warning("Listy ADMIN i Premium nakładają się. Pierwszeństwo ma ADMIN.")
        st.subheader("Dziennik administracyjny")
        audit = read_recent_events()
        if audit.get("status") == "ok":
            if audit["events"]:
                table(audit["events"], hide_index=True, use_container_width=True)
            else:
                st.info("Brak zapisanych zdarzeń.")
        else:
            st.info("Dziennik audytu niedostępny.")
        st.write("Rejestrowanie audytu:", "Włączona" if security.get("audit_recording_enabled") else "Wyłączona")
        if audit_enabled() and st.button("Zapisz przegląd uprawnień"):
            if record_admin_event("review_access", "success"):
                st.success("Przegląd zapisany.")
            else:
                st.warning("Nie udało się zapisać zdarzenia.")
        st.info("Monitoring anomalii logowania i kopii zapasowych nie jest podłączony.")
        return
    if section == "Revenue":
        from admin_revenue import revenue_snapshot, project_revenue
        revenue = revenue_snapshot()
        if revenue.get("status") != "ok":
            st.error("Brak dostępu.")
            return
        st.subheader("Stripe · konfiguracja płatności")
        st.write("Tryb płatności:", localized(revenue["checkout_mode"]))
        st.write("Zadeklarowana gotowość obsługi subskrypcji:", localized(revenue["fulfillment_declared_ready"]))
        st.markdown("Konfiguracja nie potwierdza rzeczywistych płatności.")
        cols = st.columns(2)
        cols[0].metric("Rzeczywiste przychody", "Nie podłączono")
        cols[1].metric("Aktywne płatne subskrypcje", "Nie podłączono")
        st.subheader("Stripe · subskrypcje testowe")
        stripe = stripe_test()
        if stripe.get("status") == "ok":
            counts = stripe["subscription_counts"]
            if counts:
                table([{"Status": k, "Subskrypcje testowe": v} for k,v in sorted(counts.items())], hide_index=True, use_container_width=True)
            else:
                st.info("Brak subskrypcji testowych.")
            st.markdown("Wyłącznie dane testowe, bez rzeczywistych przychodów.")
        else:
            st.info("Stripe test: " + localized(stripe.get("status","unavailable")))
        st.divider()
        st.subheader("Symulator przychodów · USD")
        st.markdown("Symulacja, nie rzeczywiste wpływy.")
        cols = st.columns(2)
        n = cols[0].number_input("Płacący subskrybenci", min_value=0, max_value=10000000, value=100, step=1)
        price = cols[1].number_input("Cena miesięczna (USD)", min_value=0.0, max_value=100000.0, value=9.99, step=0.01)
        cols = st.columns(2)
        fixed = cols[0].number_input("Koszty stałe miesięczne (USD)", min_value=0.0, max_value=100000000.0, value=100.0)
        variable = cols[1].number_input("Koszt zmienny na subskrybenta (USD)", min_value=0.0, max_value=100000.0, value=0.0)
        cols = st.columns(2)
        pct = cols[0].number_input("Prowizja (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.1)
        fee = cols[1].number_input("Opłata za płatność (USD)", min_value=0.0, max_value=100000.0, value=0.0, step=0.01)
        p = project_revenue(n, price, fixed, pct, fee, variable)
        cols = st.columns(3)
        cols[0].metric("Przychód miesięczny", f'${p["monthly_gross"]:,.2f}')
        cols[1].metric("Przychód roczny (ekstrapolacja)", f'${p["annualized_gross"]:,.2f}')
        cols[2].metric("Miesięczny wynik operacyjny", f'${p["monthly_operating_result"]:,.2f}')
        st.metric("Próg rentowności · subskrybenci", p["break_even_subscribers"] if p["break_even_subscribers"] is not None else "Brak dodatniej marży")
        table([{"Miesięczne prowizje": float(p["monthly_payment_fees"]),
                       "Miesięczne koszty stałe": float(p["monthly_fixed_cost"]),
                       "Miesięczne koszty zmienne": float(p["monthly_variable_cost"])}], hide_index=True, use_container_width=True)
        st.markdown("Wynik przed podatkami, zwrotami i odpływem klientów, o ile nie uwzględniono ich w kosztach.")
        return
    if section == "Settings":
        from admin_settings import settings_snapshot, validate_draft
        config = settings_snapshot()
        if config.get("status") != "ok":
            st.error("Brak dostępu.")
            return
        st.subheader("Konfiguracja wdrożenia")
        for label, key in (("OIDC", "oidc_configured"), ("Baza Trackera", "tracker_url_configured"),
                           ("Baza audytu", "audit_storage_configured"), ("Klucz audytu", "audit_key_configured")):
            st.write(label + ":", "Skonfigurowano" if config[key] else "Brak")
        st.write("Tryb płatności:", localized(config["checkout_mode"]))
        st.write("Zadeklarowana gotowość obsługi subskrypcji:", localized(config["fulfillment_declared_ready"]))
        st.write("Rejestr kont:", "Włączona" if registry_enabled() else "Wyłączona")
        st.write("Limit darmowych analiz:", "Włączona" if free_props_enabled() else "Wyłączona")
        st.write("Rejestrowanie audytu:", "Włączona" if audit_enabled() else "Wyłączona")
        st.divider()
        st.subheader("Podgląd zmian")
        st.warning("Wyłącznie podgląd — bez zmian aplikacji publicznej.")
        with st.form("control_center_settings_preview"):
            maintenance = st.checkbox("Tryb konserwacji", value=False)
            enabled = st.checkbox("Włącz ogłoszenie", value=False)
            announcement = st.text_input("Treść ogłoszenia", max_chars=300)
            submitted = st.form_submit_button("Sprawdź konfigurację")
        if submitted:
            try:
                draft = validate_draft({"maintenance_requested":maintenance,
                    "announcement_enabled":enabled, "announcement_text":announcement})
                st.success("Konfiguracja poprawna. Zmian nie zastosowano.")
                st.write("Tryb konserwacji:", localized(draft["maintenance_requested"]))
                st.write("Ogłoszenie aktywne:", localized(draft["announcement_enabled"]))
                if draft["announcement_enabled"]:
                    st.text(draft["announcement_text"])
            except ValueError as exc:
                st.error("Nieprawidłowa konfiguracja. Sprawdź wprowadzone wartości.")
        st.info("Zdalne sterowanie funkcjami, płatnościami i modelami nie jest aktywne.")
        return

