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
    from admin_live_data import tracker_summary, account_summary, stripe_test_summary, official_injury_freshness, usage_summary
    from admin_security import audit_enabled, record_admin_event
    from account_registry import registry_enabled, free_props_enabled

    def table(rows, **kwargs):
        from admin_dashboard_ui import table_markup, model_name
        data = [{COLUMN_LABELS.get(k,k): model_name(v) if k in ("model_id", "Model") else localized(v)
                 for k,v in dict(row).items()} for row in rows]
        if data:
            st.markdown(table_markup(data), unsafe_allow_html=True)
        else:
            st.info("Brak rekordów.")

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

    @st.cache_data(ttl=90, max_entries=24, show_spinner=False)
    def tracker_history(season, kind, start, end):
        from admin_tracker_history import read_history
        return read_history(tracker_database_url(), season, kind, start, end)

    @st.cache_data(ttl=300, show_spinner=False)
    def accounts():
        return account_summary()

    @st.cache_data(ttl=60, show_spinner=False)
    def usage():
        return usage_summary()

    @st.cache_data(ttl=300, show_spinner=False)
    def stripe_test():
        return stripe_test_summary()

    @st.cache_data(ttl=300, show_spinner=False)
    def stripe_payments():
        from admin_stripe_payments import stripe_payment_summary
        return stripe_payment_summary()

    @st.cache_data(ttl=300, show_spinner=False)
    def injury_index():
        return official_injury_freshness()

    from admin_dashboard_ui import CSS, BRAND, metric_markup, grid_markup, health_markup
    st.markdown(CSS, unsafe_allow_html=True)
    st.sidebar.markdown(BRAND, unsafe_allow_html=True)
    nav_key = "hz_admin_section"
    if st.session_state.get(nav_key) not in SECTIONS:
        st.session_state[nav_key] = "Overview"
    section = st.session_state[nav_key]
    def select_section(value):
        st.session_state[nav_key] = value
    nav_icons = {"Overview":":material/dashboard:", "Data Center":":material/database:",
                 "AI Engines":":material/memory:", "Tracker":":material/monitoring:",
                 "Users":":material/group:", "Revenue":":material/payments:",
                 "Performance":":material/speed:", "Security":":material/shield:",
                 "Settings":":material/settings:"}
    for item in SECTIONS:
        st.sidebar.button(SECTION_LABELS[item], key="hz_nav_" + item, icon=nav_icons[item],
                          type="primary" if section == item else "secondary",
                          use_container_width=True, on_click=select_section, args=(item,))
    st.sidebar.divider()
    if not dedicated:
        st.sidebar.markdown("[Powrót do Hoopzaro](?)")
    st.title(SECTION_LABELS[section])
    def diagnostic(report):
        code = report.get("diagnostic")
        if code:
            st.write("Kod diagnostyczny:", code)

    def kpis(items, columns=3):
        st.markdown(grid_markup(items, columns), unsafe_allow_html=True)
    def health(label, value, kind="warn"):
        st.markdown(health_markup(label, value, kind), unsafe_allow_html=True)
    if st.sidebar.button("Odśwież dane"):
        snapshot.clear()
        scorecard.clear()
        sources.clear()
        database_health.clear()
        tracker_metrics.clear()
        tracker_history.clear()
        accounts.clear()
        usage.clear()
        stripe_test.clear()
        stripe_payments.clear()
        injury_index.clear()
        if audit_enabled() and not record_admin_event("refresh_telemetry", "success"):
            st.warning("Dane odświeżone. Nie zapisano zdarzenia audytu.")
    if dedicated and st.sidebar.button("Wyloguj się"):
        st.logout()
        st.stop()
        return
    if section == "Tracker":
        from admin_tracker_view import render_tracker
        render_tracker(tracker_history, tracker_metrics)
        return
    def usage_cards():
        report = usage()
        row = (report.get("sessions") or [{}])[0]
        value = lambda key: row.get(key, "Brak danych")
        kpis([("Sesje · ostatnie 3 min", value("recent_sessions"), "Sesje z niedawnym sygnałem aktywności; nie liczba osób online."),
              ("Nowe sesje · 24 godz.", value("new_sessions_24h")),
              ("Aktywne sesje · 24 godz.", value("active_sessions_24h")),
              ("Aktywne sesje · 7 dni", value("active_sessions_7d"))], 4)
        if report.get("status") != "ok":
            health("Monitoring sesji", localized(report.get("status", "unavailable")))
        return report

    def usage_charts(report):
        if report.get("status") != "ok":
            return
        pages = {"home":"Centrum","props":"Player Props","games":"Terminarz",
                 "simulations":"Symulacje","players":"Zawodnicy","teams":"Drużyny","settings":"Ustawienia"}
        if report.get("daily"):
            st.subheader("Aktywne sesje · 30 dni")
            st.line_chart([{"Data":r["day"],"Sesje":r["sessions"]} for r in report["daily"]], x="Data", y="Sesje")
        if report.get("pages"):
            st.subheader("Popularność zakładek · 7 dni")
            st.bar_chart([{"Zakładka":pages.get(r["page"],r["page"]), "Sesje":r["sessions"]}
                          for r in report["pages"]], x="Zakładka", y="Sesje")
        if not report.get("daily") and not report.get("pages"):
            st.info("Brak zarejestrowanych sesji w ostatnich 30 dniach.")
        st.markdown("Próbki aktywności sesji, nie unikalne osoby ani dokładne odsłony.")

    if section == "Overview":
        from admin_overview import render_overview
        render_overview(accounts(), usage(), snapshot("2026-27"), select_section, stripe_test(), stripe_payments())
        return
    if section in ("Data Center", "AI Engines"):
        data = snapshot("2026-27")
        worker = data.get("worker") or {}
        models = data.get("models") or []
        health("Silnik V8", localized(data.get("status", "unavailable")), "ok" if data.get("status") == "recent_evidence" else "warn")
        if section == "Data Center":
            kpis([(name, worker.get(field, "Brak danych")) for name, field in zip(
                ("Zebrane mecze", "Próbki treningowe", "Odrzucone statystyki meczowe"),
                ("observed_games", "trainable_examples", "rejected_boxscores"))])
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
        if section == "AI Engines":
            from admin_dashboard_ui import model_name, number, bars_markup
            report = scorecard("2026-27")
            st.subheader("Porównanie skuteczności modeli")
            if report.get("status") in ("unavailable", "setup_required"):
                st.warning("Nie udało się odczytać wyników modeli.")
                diagnostic(report)
            else:
                cohort = report.get("shared_cohort") or {}
                metrics = cohort.get("metrics") or {}
                pairs = report.get("common_game_comparisons") or []
                if metrics:
                    st.markdown(f'**Wspólna próba: {cohort["n"]} meczów** · wszystkie modele ocenione na tych samych wynikach.')
                elif pairs:
                    st.markdown("Wybierz parę modeli. Każda para jest oceniana na swoich wspólnych meczach.")
                    pair = st.selectbox("Porównanie", range(len(pairs)),
                        format_func=lambda i: f'{model_name(pairs[i]["left"])} i {model_name(pairs[i]["right"])} · {pairs[i]["same_game_n"]} meczów')
                    p = pairs[pair]
                    metrics = {p["left"]:p["left_metrics"], p["right"]:p["right_metrics"]}
                if metrics:
                    ordered = sorted(metrics, key=model_name)
                    left, right = st.columns(2)
                    with left:
                        st.subheader("Błąd punktów drużyny")
                        st.markdown("Im mniej, tym lepiej.")
                        st.markdown(bars_markup([(model_name(k),metrics[k].get("team_points_mae")) for k in ordered], suffix=""), unsafe_allow_html=True)
                    with right:
                        st.subheader("Trafność zwycięzcy")
                        st.markdown("Im więcej, tym lepiej.")
                        st.markdown(bars_markup([(model_name(k),metrics[k].get("winner_hit_pct")) for k in ordered], maximum=100, suffix="%", digits=1), unsafe_allow_html=True)
                    table([{"Model":model_name(k), "Mecze":metrics[k].get("n"),
                        "Błąd drużyny (pkt)":number(metrics[k].get("team_points_mae")),
                        "Błąd sumy (pkt)":number(metrics[k].get("total_points_mae")),
                        "Trafność zwycięzcy":number(metrics[k].get("winner_hit_pct"),1)+"%" if metrics[k].get("winner_hit_pct") is not None else "—",
                        "Brier":number(metrics[k].get("brier"),4)} for k in ordered])
                else:
                    st.info("Brak wspólnej próby rozliczonych meczów.")
                with st.expander("Szczegóły i definicje"):
                    st.write("MAE to średni bezwzględny błąd punktowy. Brier mierzy jakość prawdopodobieństwa zwycięstwa (niższy jest lepszy).")
                    own = report.get("model_metrics") or {}
                    if own:
                        st.write("Pełne archiwum każdego modelu — różne próby, bez rankingu.")
                        table([{"Model":model_name(k), "Mecze":m.get("n"),
                                "Błąd drużyny (pkt)":number(m.get("team_points_mae")),
                                "Błąd sumy (pkt)":number(m.get("total_points_mae")),
                                "Trafność (%)":number(m.get("winner_hit_pct"),1),
                                "Brier":number(m.get("brier"),4),
                                "Błąd scenariusza (pkt)":number(m.get("scenario_team_points_mae")),
                                "Pokrycie przedziału (%)":number(m.get("total_80pct_interval_coverage"),1)}
                               for k,m in sorted(own.items(),key=lambda item:model_name(item[0])) if m])
                    if any(p.get("historical_training_sample_differs") for p in pairs):
                        st.warning("Modele trenowano na różnych próbach. Nie można przypisać różnic wyłącznie zmianom algorytmu.")
                st.info("Wyniki badawcze. Mała próba nie wystarcza do potwierdzenia przewagi modelu.")
        return
    if section == "Performance":
        st.subheader("Funkcje aplikacji · ostatnie 7 dni")
        report = usage()
        if report.get("status") == "ok":
            labels = {"simulation":"Symulacje meczów","player_simulation":"Symulacje zawodników",
                      "scenario":"Scenariusze","minutes":"Minuty zawodników","props":"Player Props","backtest":"Backtest"}
            features = report.get("features", [])
            if features:
                table([{"Funkcja":labels.get(r["feature"],r["feature"]), "Wywołania":r["calls"],
                        "Błędy":r["failures"], "Średni czas (ms)":r["avg_ms"]} for r in features], hide_index=True, use_container_width=True)
                st.bar_chart([{"Funkcja":labels.get(r["feature"],r["feature"]), "Wywołania":r["calls"]} for r in features], x="Funkcja", y="Wywołania")
            else:
                st.info("Brak zapisanych wywołań funkcji.")
        else:
            health("Monitoring funkcji", localized(report.get("status","unavailable")))
        st.subheader("Neon · połączenie z bazą")
        db = database_health()
        kpis([(label, f'{db[key]:.1f} ms' if db.get(key) is not None else "Brak danych")
              for label, key in zip(("Połączenie", "Zapytanie", "Łącznie"),
                                    ("connect_ms", "query_ms", "total_ms"))])
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
        st.info("Pomiar czasu renderowania i zużycia zasobów nie jest podłączony.")
        return
    if section == "Users":
        st.subheader("Ruch i popularność zakładek")
        usage_charts(usage_cards())
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
            kpis([("Zaobserwowane konta", sum(r["observed_accounts"] for r in rows), "Konta zaobserwowane przez aplikację, nie rejestr Google ani płatności."),
                  ("Aktywni · 30 dni", sum(r["seen_last_30_days"] for r in rows)),
                  ("Darmowe analizy · dziś (UTC)", registry["quota"][0]["reservations_today"])])
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
        kpis([("Identyfikatory ADMIN", security["admin_identifier_entries"]),
              ("Powielone identyfikatory", security["overlap_entries"])], 2)
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
        from admin_stripe_payments import payment_rows, money_label
        st.markdown("**Środowisko testowe Stripe** · odczyt bez możliwości pobierania pieniędzy.")
        stripe = stripe_test()
        payments = stripe_payments()
        counts = stripe.get("subscription_counts", {})
        sub_ok = stripe.get("status") == "ok"
        pay_ok = payments.get("status") == "ok"
        currencies = payments.get("currencies", {}) if pay_ok else {}
        kpis([("Aktywne subskrypcje testowe", counts.get("active",0) if sub_ok else "Brak danych"),
              ("W okresie próbnym · test", counts.get("trialing",0) if sub_ok else "Brak danych"),
              ("Udane płatności testowe · 30 dni", sum(v["successful"] for v in currencies.values()) if pay_ok else "Brak danych"),
              ("Nieudane płatności testowe · 30 dni", sum(v["failed"] for v in currencies.values()) if pay_ok else "Brak danych")],4)
        st.subheader("Płatności testowe · ostatnie 30 dni")
        if pay_ok:
            if currencies:
                for currency, values in sorted(currencies.items()):
                    kpis([("Pobrano testowo", money_label(values["captured_minor"],currency)),
                          ("Zwroty zgłoszone przez Stripe", money_label(values["refunded_minor"],currency))],2)
                table(payment_rows(payments), hide_index=True, use_container_width=True)
            else:
                st.info("Brak płatności testowych w tym okresie.")
            st.markdown("Zakres: płatności utworzone w ostatnich 30 dniach. Zwroty dotyczą tych płatności, niezależnie od daty zwrotu. Kwoty przed prowizjami i rozliczeniem podatków.")
        else:
            st.info("Płatności testowe: " + localized(payments.get("status","unavailable")))
        st.subheader("Subskrypcje testowe")
        if sub_ok:
            if counts:
                table([{"Status":k,"Subskrypcje":v} for k,v in sorted(counts.items())],hide_index=True,use_container_width=True)
            else:
                st.info("Brak subskrypcji testowych.")
        else:
            st.info("Subskrypcje testowe: " + localized(stripe.get("status","unavailable")))
        st.markdown("Dane obejmują całe podłączone środowisko Stripe, nie wyłącznie produkt Hoopzaro. Subskrypcje nie są liczbą unikalnych klientów.")
        with st.expander("Konfiguracja i rzeczywiste płatności"):
            st.write("Tryb linku płatności w tej instancji:",localized(revenue["checkout_mode"]))
            st.write("Zadeklarowana gotowość obsługi subskrypcji:",localized(revenue["fulfillment_declared_ready"]))
            st.write("Rzeczywiste przychody i płatne subskrypcje nie są podłączone. Klucz testowy nie nadaje dostępu Premium.")
            st.write("Wymagany klucz ograniczony rk_test_ z uprawnieniami odczytu Subscriptions i Charges, bez zapisu.")
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
        kpis([("Przychód miesięczny", f'${p["monthly_gross"]:,.2f}'),
              ("Przychód roczny (ekstrapolacja)", f'${p["annualized_gross"]:,.2f}'),
              ("Miesięczny wynik operacyjny", f'${p["monthly_operating_result"]:,.2f}'),
              ("Próg rentowności · subskrybenci", p["break_even_subscribers"] if p["break_even_subscribers"] is not None else "Brak dodatniej marży")], 4)
        table([{"Miesięczne prowizje": float(p["monthly_payment_fees"]),
                       "Miesięczne koszty stałe": float(p["monthly_fixed_cost"]),
                       "Miesięczne koszty zmienne": float(p["monthly_variable_cost"])}], hide_index=True, use_container_width=True)
        st.markdown("Wynik przed podatkami, zwrotami i odpływem klientów, o ile nie uwzględniono ich w kosztach.")
        return
    if section == "Settings":
        st.write("Wersja panelu: 2026-11-26-r10")
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

