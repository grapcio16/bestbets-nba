"""Verified-data adapter for the HOOPZARO Premium simulation canvas.

Results are restricted by server-verified identity and an explicit entitlement
(administrator or manually confirmed Premium). A payment integration must
verify subscriptions on the server before granting customer entitlements.
"""
from __future__ import annotations

from math import isfinite

import numpy as np
import pandas as pd
import streamlit as st
from access_control import premium_entitled as _verified_entitlement

SIMULATION_MODELS = {"legacy_v72", "research_form_v74", "research_context_v75"}


def premium_entitled() -> bool:
    """Enforce role checks on every server-side Premium access."""
    return _verified_entitlement()


def _clean_float(value):
    try:
        result = float(value)
        return round(result, 2) if isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _distribution(values):
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return {"bins": [], "p10": None, "p90": None, "average": None,
                "threshold": None, "over_pct": None, "lines": [], "score_counts": []}
    lo = int(np.floor(float(values.min()) / 5) * 5)
    hi = int(np.ceil(float(values.max()) / 5) * 5) + 5
    edges = np.arange(lo, hi + 1, 5)
    counts, _ = np.histogram(values, bins=edges)
    # Exact integer score frequencies from the existing 5,000 draws. They
    # support interactive thresholds without rerunning or changing the model.
    score_values, score_frequencies = np.unique(values.astype(int), return_counts=True)
    average = float(values.mean())
    threshold = int(round(average / 5) * 5)
    # Display only: exact OVER/UNDER percentages from the same 5,000
    # simulated final scores. Half-point thresholds cannot push on the
    # integer NBA scoreboard. No additional simulations or model changes.
    lines = []
    for line in (threshold - 0.5, threshold + 4.5):
        over = int(np.count_nonzero(values > line))
        lines.append({
            "line": line,
            "over_pct": round(100 * over / values.size, 1),
            "under_pct": round(100 * (values.size - over) / values.size, 1),
        })
    return {
        "bins": [{"x": int(edges[i]), "p": round(100 * int(count) / values.size, 3)}
                 for i, count in enumerate(counts)],
        "p10": int(np.percentile(values, 10)),
        "p90": int(np.percentile(values, 90)),
        "average": round(average, 1),
        "threshold": threshold,
        "over_pct": round(100 * float(np.count_nonzero(values >= threshold)) / values.size, 1),
        "lines": lines,
        "score_counts": [[int(score), int(count)] for score, count in zip(score_values, score_frequencies)],
    }


def _season_at(tipoff) -> str:
    stamp = pd.to_datetime(tipoff, utc=True)
    first_year = stamp.year if stamp.month >= 10 else stamp.year - 1
    return f"{first_year}-{(first_year + 1) % 100:02d}"


@st.cache_data(ttl=3600, max_entries=4, show_spinner=False)
def _advanced_from_verified_cache(season: str):
    """Never delay an interactive simulation on blocked stats.nba.com calls."""
    from sources import read_cache
    from teams import standardize_teams

    cached, meta = read_cache('extended-Drużyny • advanced (pace/def)-' + season, 12 * 3600)
    if cached and meta and not meta.get('stale'):
        return standardize_teams(pd.DataFrame(cached))
    return pd.DataFrame()


@st.cache_data(ttl=120, max_entries=18, show_spinner=False)
def _day_for_simulations(day: str):
    """Reuse parsed ESPN calendar and local team-logo data across match picks."""
    from bestbets_centre_live import get_centre_day_data
    return get_centre_day_data(day)


@st.cache_data(ttl=600, max_entries=4, show_spinner=False)
def _history_for_simulations(season: str):
    """Version 2: read season finals WITH verified ESPN regulation Q1–Q4 when available.

    Explicit body change invalidates previously cached schedule-only DataFrames
    after deploy. Missing quarterly evidence is a known unavailable state.
    """
    from simulation_sources import historical_espn_results
    history, warning = historical_espn_results(season)
    return history, warning


@st.cache_data(ttl=600, max_entries=90, show_spinner=False)
def _v75_player_evidence(day: str, game_id: str):
    """One bounded, cached selected-matchup fetch for V7.5 only.

    No current injury report is ever applied retrospectively to a final game.
    A failed ESPN request degrades to zero injury correction, not an invented
    active lineup. Other simulation models never enter this routine.
    """
    from availability_context import matchup_injuries
    from espn_player_data import matchup_espn_logs
    from simulation_availability_v75 import availability_evidence
    from simulation_view import matchup_players_cached

    event = _day_for_simulations(day)
    match = next((g for g in event.get("games", []) if str(g.get("id")) == game_id), None)
    if match is None or match.get("state") not in ("scheduled", "final"):
        return pd.DataFrame(), {}
    tipoff = pd.to_datetime(match.get("start"), utc=True, errors="coerce")
    if pd.isna(tipoff):
        return pd.DataFrame(), {}
    season = _season_at(tipoff)
    historical, _ = _history_for_simulations(season)
    game = {"game_id": game_id, "home": str(match["home"]),
            "away": str(match["away"]), "start_utc": tipoff}
    advanced = (_advanced_from_verified_cache(season)
                if match.get("state") == "scheduled" else pd.DataFrame())
    table, _ = matchup_players_cached(season, game, historical, advanced, 0,
                                      research_mode=True)
    logs, _ = matchup_espn_logs(historical, game)
    report, meta = pd.DataFrame(), {}
    if match.get("state") == "scheduled":
        try:
            from sources import injuries
            raw, source_meta = injuries()
            report, report_meta = matchup_injuries(raw, game["home"], game["away"], source_meta)
            meta = {**source_meta, "available": report_meta["available"]}
        except (OSError, RuntimeError, ValueError, KeyError, TypeError):
            # Missing or broken feed must never be interpreted as 'healthy'.
            meta = {"available": False, "stale": True}
    result = availability_evidence(
        table, report, meta, game, logs=logs,
        historical=match.get("state") == "final")
    # Reuse the SAME already fetched ESPN boxscores for the selected
    # Premium player chart. These logs never enter the iframe wholesale.
    result["verified_history_logs"] = logs
    return table, result


@st.cache_data(ttl=600, max_entries=90, show_spinner=False)
def _game_simulation(day: str, game_id: str, model_id: str = "research_form_v74",
                     pace_pct: int = 0, off_away_pct: int = 0,
                     off_home_pct: int = 0):
    """Future model, or clearly labeled retrospective model for a final game."""
    from espn_player_data import prefetch_matchup_boxscores
    from simulation_engine import (advanced_ratings, completed_team_scores,
                                   legacy_matchup_means, simulate_game)
    from simulation_context_v2 import simulation_inputs
    from simulation_context_v75 import simulation_inputs_v75
    from simulation_data_audit import verified_history

    event = _day_for_simulations(day)
    games = event.get("games", [])
    match = next((g for g in games if str(g.get("id")) == game_id), None)
    if match is None or match.get("state") not in ("scheduled", "final"):
        return {"error": "Wybierz potwierdzony przyszły lub zakończony mecz NBA."}
    tipoff = pd.to_datetime(match.get("start"), utc=True, errors="coerce")
    if pd.isna(tipoff) or (match.get("state") == "scheduled" and
                            tipoff <= pd.Timestamp.now(tz="UTC")):
        return {"error": "Termin spotkania jest nieaktualny. Odśwież terminarz."}
    season = _season_at(tipoff)
    historical, warning = _history_for_simulations(season)
    if historical is None or historical.empty:
        return {"error": "Brak wystarczającej zweryfikowanej historii ESPN."}
    away, home = str(match.get("away", "")), str(match.get("home", ""))
    game = {"game_id": game_id, "home": home, "away": away, "start_utc": tipoff}
    # A present-day NBA Advanced cache contains games that happened AFTER a
    # historical final. Using it here would leak future information.
    advanced = (_advanced_from_verified_cache(season)
                if match.get("state") == "scheduled" else pd.DataFrame())
    # Start the selected matchup's real ESPN boxscores early; team and player
    # calculations use the same shared in-flight requests and cached results.
    try:
        prefetch_matchup_boxscores(historical, game)
    except (OSError, RuntimeError, ValueError):
        pass
    evidence = None
    if model_id == "research_context_v75" and match.get("state") == "scheduled":
        try:
            _, evidence = _v75_player_evidence(day, game_id)
        except (OSError, RuntimeError, ValueError, KeyError, TypeError):
            # Team predictions still work when ESPN player endpoints time out.
            evidence = None
    context = (simulation_inputs_v75(historical, game, advanced, availability=evidence)
               if model_id == "research_context_v75" else
               simulation_inputs(historical, game, advanced))
    # All modes use verified pregame evidence. The legacy baseline retains its
    # fixed variance; both research variants use shrunk observed scoring SD.
    means = (legacy_matchup_means(
        home, away, advanced_ratings(advanced),
        completed_team_scores(verified_history(historical, tipoff)))
        if model_id == "legacy_v72" else context["means"])
    if means is None:
        return {"error": "Za mało historycznych spotkań do wiarygodnej symulacji."}
    # What-if changes only expected points. No injuries, rotations or
    # verified team form is fabricated or silently re-estimated.
    params = (pace_pct, off_away_pct, off_home_pct)
    if any(type(v) is not int or not -5 <= v <= 5 for v in params):
        return {"error": "Parametry scenariusza muszą wynosić od −5% do +5%."}
    if any(params):
        tempo = 1 + pace_pct / 100
        means = {**means,
                 "home": float(means["home"]) * tempo * (1 + off_home_pct / 100),
                 "away": float(means["away"]) * tempo * (1 + off_away_pct / 100),
                 "source": str(means.get("source") or "ESPN") +
                           " · hipotetyczne tempo i efektywność ofensywna"}
        if any(not 60 < means[k] < 170 for k in ("home", "away")):
            return {"error": "Założenia scenariusza przekraczają zakres modelu."}
    summary, _, home_scores, away_scores = simulate_game(
        game, means, score_noise=(context["score_noise"]
                                 if model_id != "legacy_v72" else None))
    from simulation_flow import conditional_flow
    from simulation_quarter_model import pregame_quarter_evidence
    quarters = pregame_quarter_evidence(historical, game)
    flow = conditional_flow(away_scores, home_scores, game_id=game_id,
                            model_id=model_id, quarter_evidence=quarters)
    return {
        "game_id": game_id, "model_id": model_id, "away": away, "home": home,
        "away_win_pct": summary["away_win_pct"],
        "home_win_pct": summary["home_win_pct"],
        "away_points": summary["away_points"],
        "home_points": summary["home_points"],
        "total_points": summary["total_points"],
        "distributions": {
            "match": _distribution(home_scores + away_scores),
            "away": _distribution(away_scores),
            "home": _distribution(home_scores),
        },
        "flow": flow,
        "n_sims": summary["n_sims"], "source": str(summary.get("source") or "ESPN"),
        "warning": str(warning or "")[:150],
        "retrospective": match.get("state") == "final",
        "model_context": context["context"],
        "players": None,
    }


def _compact_pregame_player_history(raw, tipoff, away: str, home: str) -> dict:
    """Previously played ESPN boxscore observations ONLY, never new model odds.

    Up to seven completed team fixtures are already downloaded by the
    projection engine. Do not request 15 more and slow down Player Simulations.
    The browser displays L10/L15 only when all observations actually exist.
    """
    from core import norm_name
    if raw is None or not isinstance(raw, pd.DataFrame) or raw.empty:
        return {}
    required = {"GAME_ID", "GAME_DATE", "TEAM_ABBREVIATION",
                "PLAYER_NAME", "PLAYER_ID", "PTS", "REB", "AST", "MIN"}
    if not required.issubset(raw.columns):
        return {}
    frame = raw.copy()
    frame["GAME_DATE"] = pd.to_datetime(frame["GAME_DATE"], utc=True, errors="coerce")
    frame = frame[(frame["GAME_DATE"] < tipoff) &
                  (frame["TEAM_ABBREVIATION"].isin((away, home))) &
                  (pd.to_numeric(frame["MIN"], errors="coerce") > 0)]
    frame = frame.sort_values("GAME_DATE").drop_duplicates(
        subset=["GAME_ID", "TEAM_ABBREVIATION", "PLAYER_NAME"], keep="last")
    histories = {}
    for row in frame.to_dict("records"):
        team = str(row.get("TEAM_ABBREVIATION") or "").strip().upper()
        name = str(row.get("PLAYER_NAME") or "").strip()
        key = (team, norm_name(name))
        eid = str(row.get("PLAYER_ID") or "")
        pts, reb, ast = (_clean_float(row.get(k)) for k in ("PTS", "REB", "AST"))
        if not name or any(v is None or v < 0 or v > 100 for v in (pts, reb, ast)):
            continue
        position = str(row.get("POSITION") or "").strip().upper()
        position = position if position in {"PG", "SG", "SF", "PF", "C", "G", "F"} else ""
        item = {
            "date": row["GAME_DATE"].date().isoformat(),
            "game_id": str(row["GAME_ID"]),
            "pts": pts, "reb": reb, "ast": ast,
            "pra": round(pts + reb + ast, 1),
            # Observed ESPN playing time, NEVER a model minute projection.
            "min": _clean_float(row.get("MIN")),
        }
        if key not in histories:
            histories[key] = {"history": [], "espn_id": "", "position": position}
        histories[key]["history"].append(item)
        if eid.isdigit() and 1 <= len(eid) <= 12:
            histories[key]["espn_id"] = eid
        if position:
            histories[key]["position"] = position
    for data in histories.values():
        # Exact arithmetic means from every verified boxscore we received,
        # before limiting the frontend L5/L10/L15 trend to 15 observations.
        # Label as "Season for current team" ONLY if every previous team
        # fixture has a verified boxscore (computed by the caller).
        rows = data["history"]
        data["observed_mean"] = {
            metric: round(sum(float(r[metric]) for r in rows) / len(rows), 2)
            for metric in ("pts", "reb", "ast", "pra")
        } if rows else {}
        data["observed_games"] = len(rows)
        data["history"] = rows[-15:]
    return histories


def _complete_player_team_coverage(historical, logs, tipoff, teams) -> set[str]:
    """Only assert season-to-date coverage when every ESPN final ID matches.

    Counting n distinct boxscores is insufficient: skipped games could be
    hidden by unrelated fixtures. Missing or malformed provider data makes
    coverage incomplete, never a fabricated full-season average.
    """
    need = {"game_id", "start_utc", "home", "away", "status_code"}
    have = {"GAME_ID", "TEAM_ABBREVIATION"}
    if (not isinstance(historical, pd.DataFrame) or
            not isinstance(logs, pd.DataFrame) or
            not need.issubset(historical.columns) or
            not have.issubset(logs.columns) or
            historical.empty or logs.empty):
        return set()
    previous = historical.copy()
    previous["start_utc"] = pd.to_datetime(
        previous["start_utc"], utc=True, errors="coerce")
    previous = previous[
        (pd.to_numeric(previous["status_code"], errors="coerce") == 3)
        & (previous["start_utc"] < tipoff)
    ]
    verified = set()
    for team in teams:
        played = previous[
            (previous["away"] == team) | (previous["home"] == team)
        ]
        expected = {str(x) for x in played["game_id"].dropna()}
        seen = {str(x) for x in logs.loc[
            logs["TEAM_ABBREVIATION"] == team, "GAME_ID"].dropna()}
        if expected and expected.issubset(seen):
            verified.add(team)
    return verified


@st.cache_data(ttl=900, max_entries=90, show_spinner=False)
def _minute_roster_for_fixture(away: str, home: str):
    """Read both ESPN team roster catalogs only for a selected Premium fixture.

    A current roster entry is NOT a player projection or injury clearance.
    Missing/stale provider responses are labeled incomplete, not filled with
    historical players attributed to an unverified current roster.
    """
    from concurrent.futures import ThreadPoolExecutor
    from roster_data import team_roster, ESPN_TEAM_IDS

    teams = (str(away).upper(), str(home).upper())
    if teams[0] == teams[1] or any(t not in ESPN_TEAM_IDS for t in teams):
        return [], [], "Nieznane drużyny meczu."
    output, verified = [], []
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {team: pool.submit(team_roster, team) for team in teams}
        for team in teams:
            try:
                roster, metadata = jobs[team].result()
                if roster.empty or bool((metadata or {}).get("stale")):
                    continue
                verified.append(team)
                for row in roster.to_dict("records"):
                    name = str(row.get("PLAYER_NAME") or "").strip()
                    if not name:
                        continue
                    pos = str(row.get("POSITION") or "").strip().upper()
                    output.append({
                        "name": name[:70], "team": team,
                        "position": pos if pos in {"PG", "SG", "SF", "PF", "C", "G", "F"} else "",
                        "espn_id": str(row.get("PLAYER_ID") or "")[:20],
                        "roster_status": str(row.get("ROSTER_STATUS") or "")[:35],
                    })
            except (OSError, RuntimeError, ValueError, TypeError, KeyError):
                continue
    warning = ("" if set(verified) == set(teams) else
               "ESPN nie udostępnił aktualnego pełnego składu obu drużyn. "
               "Widoczne pozycje są niepełne; brak zawodnika nie oznacza jego nieobecności.")
    return output, verified, warning


@st.cache_data(ttl=150, max_entries=1, show_spinner=False)
def _fresh_selected_injury_feed():
    """One fresh ESPN read per app instance, shared across Premium matchups.

    The regular source cache is 45 minutes: too long for a medical status.
    The explicit refresh is deduplicated for all users and fixtures for
    150 seconds. If ESPN fails, no player projections are authorized.
    """
    from sources import injuries
    return injuries(refresh=True)


@st.cache_data(ttl=60, max_entries=90, show_spinner=False)
def _selected_injury_watch(day: str, game_id: str) -> dict:
    """Read ESPN injury entries for the exact upcoming matchup, independent of
    the selected MODEL. Purely informational: never adjusts V7.2/V7.4 points.

    Cache freshness describes when ESPN was FETCHED, not when its medical
    report was published. A missing entry is not proof that a player is fit.
    """
    from availability_context import matchup_injuries
    from rotation_intelligence import status_class
    from core import norm_name
    event = _day_for_simulations(day)
    fixture = next((g for g in event.get("games", [])
                    if str(g.get("id")) == game_id), None)
    if fixture is None or fixture.get("state") != "scheduled":
        return {"fresh": False, "valid_until": None, "rows": [],
                "reason": "Raport dotyczy wyłącznie przyszłych meczów."}
    start = pd.to_datetime(fixture.get("start"), utc=True, errors="coerce")
    now = pd.Timestamp.now(tz="UTC")
    if pd.isna(start) or start <= now:
        return {"fresh": False, "valid_until": None, "rows": [],
                "reason": "Mecz nie jest już przed rozpoczęciem."}
    try:
        raw, meta = _fresh_selected_injury_feed()
        report, match_meta = matchup_injuries(
            raw, str(fixture["home"]), str(fixture["away"]), meta)
        fetched = pd.to_datetime((meta or {}).get("timestamp"),
                                 utc=True, errors="coerce")
        fresh = bool(pd.notna(fetched) and fetched <= now
                     and (now - fetched).total_seconds() <= 90 * 60
                     and not (meta or {}).get("stale")
                     and match_meta.get("available"))
        if not fresh:
            return {"fresh": False, "valid_until": None, "rows": [],
                    "reason": "Brak aktualnego odczytu ESPN. Nie potwierdzono statusów."}
        grouped = {}
        for row in report.to_dict("records"):
            code = str(row.get("Drużyna") or "")
            name = str(row.get("Zawodnik") or "").strip()
            key = (code, norm_name(name))
            if code not in (str(fixture["away"]), str(fixture["home"])) or not name:
                continue
            item = grouped.setdefault(key, {"name": name[:70], "team": code,
                                            "statuses": set(), "espn_ids": set()})
            ident = str(row.get("ESPN_ID") or "").strip()
            if ident.isdigit() and len(ident) <= 20:
                item["espn_ids"].add(ident)
            item["statuses"].add(status_class(row.get("Status ESPN")))
        rows = []
        for item in grouped.values():
            statuses = item["statuses"]
            status = next(iter(statuses)) if len(statuses) == 1 else "Sprzeczne"
            rows.append({"name": item["name"], "team": item["team"],
                         "status": status,
                         "espn_id": next(iter(item["espn_ids"]))
                             if len(item["espn_ids"]) == 1 else ""})
        rows.sort(key=lambda x: (x["team"], x["name"]))
        return {"fresh": True,
                "checked_at": fetched.isoformat(),
                "valid_until": (fetched + pd.Timedelta(minutes=90)).isoformat(),
                "rows": rows[:80], "reason": ""}
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Selected ESPN injuries unavailable: %s", type(exc).__name__)
        return {"fresh": False, "valid_until": None, "rows": [],
                "reason": "Nie udało się odczytać ESPN. Brak potwierdzonych statusów."}


@st.cache_data(ttl=60, max_entries=50, show_spinner=False)
def _game_players(day: str, game_id: str, model_id: str = "research_form_v74"):
    """Lazily fetch only the selected matchup's two actual ESPN player histories."""
    from simulation_view import matchup_players_cached
    from simulation_player_availability_guard import (
        injury_status, report_is_current, suppress_player_forecasts)

    event = _day_for_simulations(day)
    match = next((g for g in event.get("games", []) if str(g.get("id")) == game_id), None)
    if match is None or match.get("state") not in ("scheduled", "final"):
        return {"error": "Nie znaleziono potwierdzonego spotkania.", "players": []}
    tipoff = pd.to_datetime(match.get("start"), utc=True, errors="coerce")
    if pd.isna(tipoff) or (match.get("state") == "scheduled" and
                            tipoff <= pd.Timestamp.now(tz="UTC")):
        return {"error": "Nieaktualny termin spotkania.", "players": []}
    # Verify the current report BEFORE computing new player numbers.
    future = match.get("state") == "scheduled"
    injury_watch = (_selected_injury_watch(day, game_id)
                    if future else {"fresh": False, "rows": [],
                                    "reason": "Mecz zakończony."})
    if future and not report_is_current(injury_watch):
        return {"players": [], "minute_roster": [],
                "injury_watch": injury_watch, "excluded_players": [],
                "error": ("Wstrzymano prognozy zawodników: brak aktualnego "
                          "raportu kontuzji ESPN. Odśwież Injury Watch.")}

    season = _season_at(tipoff)
    historical, _ = _history_for_simulations(season)
    game = {"game_id": game_id, "home": str(match["home"]),
            "away": str(match["away"]), "start_utc": tipoff}
    advanced = (_advanced_from_verified_cache(season)
                if match.get("state") == "scheduled" else pd.DataFrame())
    availability = {}
    if model_id == "research_context_v75":
        table, availability = _v75_player_evidence(day, game_id)
        historical_logs = availability.get("verified_history_logs")
    else:
        table, _ = matchup_players_cached(season, game, historical,
                                          advanced, 0,
                                          research_mode=model_id != "legacy_v72")
        # This reads the boxscores already fetched/cached by the projector.
        from espn_player_data import matchup_espn_logs
        # Player evidence extends beyond the 7 game projection engine sample.
        # This is on-demand for an ENTITLED, selected match only; per-event
        # ESPN boxscores are cached and fetched concurrently. When fewer than
        # 10/15 played games exist, the UI says so rather than inventing data.
        historical_logs, _ = matchup_espn_logs(historical, game, games_per_team=20)
    # For V7.5 the medical/rotation evidence shares the seven-game projector,
    # but the historical charts may still use up to 20 previous team games.
    if model_id == "research_context_v75":
        from espn_player_data import matchup_espn_logs
        historical_logs, _ = matchup_espn_logs(historical, game, games_per_team=20)
    evidence_by_player = _compact_pregame_player_history(
        historical_logs, tipoff, str(match["away"]), str(match["home"]))
    complete_teams = _complete_player_team_coverage(
        historical, historical_logs, tipoff,
        (str(match["away"]), str(match["home"]))
    )
    # Injury Watch was validated before running the player projector.
    roster, verified_roster_teams, roster_warning = _minute_roster_for_fixture(
        str(match["away"]), str(match["home"]))
    if table is None or table.empty:
        return {"players": [], "minute_roster": roster,
                "minute_roster_warning": roster_warning,
                "injury_watch": injury_watch,
                "error": "ESPN nie dostarczył projekcji graczy dla tego spotkania."}
    required = {"Zawodnik", "Drużyna", "PTS", "REB", "AST"}
    if not required.issubset(table.columns):
        return {"players": [], "minute_roster": roster,
                "minute_roster_warning": roster_warning,
                "injury_watch": injury_watch,
                "error": "Źródło nie dostarczyło pełnych statystyk zawodników."}
    from core import norm_name
    injury_lookup = {(item["team"], norm_name(item["name"])): item["status"]
                     for item in injury_watch.get("rows", [])}
    roster_by_key = {(p["team"], norm_name(p["name"])): p for p in roster}
    roster_by_id = {(p["team"], p.get("espn_id")): p for p in roster
                    if p.get("espn_id")}
    players = []
    for row in table.to_dict("records"):
        name = str(row.get("Zawodnik") or "").strip()
        team = str(row.get("Drużyna") or "").upper().strip()
        points = _clean_float(row.get("PTS"))
        # Never show a player whose verified team identity is outside the two
        # sides of the selected fixture, even if the ESPN table is stale.
        if (not name or team not in {str(match["away"]), str(match["home"])}
                or points is None):
            continue
        observed = evidence_by_player.get((team, norm_name(name)), {})
        roster_entry = (roster_by_id.get((team, observed.get("espn_id")))
                        or roster_by_key.get((team, norm_name(name))))
        if future and team in verified_roster_teams and roster_entry is None:
            # Historical boxscores do not prove the athlete still plays here.
            continue
        player = {"name": name[:70], "team": team[:4],
                  "pts": points, "reb": _clean_float(row.get("REB")),
                  "ast": _clean_float(row.get("AST")),
                  # Distinct: history = ACTUAL ESPN boxscores, never simulated
                  # distributions or bookmakers' pregame player lines.
                  "history": observed.get("history", []),
                  "espn_id": observed.get("espn_id", ""),
                  "position": observed.get("position", ""),
                  "history_games": observed.get("observed_games", 0),
                  "season_team_mean": (
                      observed.get("observed_mean", {})
                      if team in complete_teams else None
                  ),
                  "season_team_games": (
                      observed.get("observed_games", 0)
                      if team in complete_teams else None
                  )}
        # Verified, pre-tipoff ESPN MIN from the last <=7 actual appearances:
        # observational baseline for what-if; NOT forecasted playing time.
        appearances = [
            _clean_float(game_row.get("min"))
            for game_row in (observed.get("history") or [])[-7:]
        ]
        minutes_observed = [v for v in appearances if v is not None and 5 <= v <= 44]
        if len(minutes_observed) >= 3:
            player["minutes"] = round(sum(minutes_observed) / len(minutes_observed), 1)
            player["minutes_sample"] = len(minutes_observed)
            player["minutes_source"] = "ESPN · średnia historyczna ostatnich występów"
        else:
            player["minutes"] = None
            player["minutes_sample"] = len(minutes_observed)
            player["minutes_source"] = "Brak wystarczającej historii minut"
        player["availability"] = (
            injury_status(name, team, observed.get("espn_id", ""), injury_watch,
                          (roster_entry or {}).get("roster_status", ""))
            if future else "Historyczny")
        if model_id == "research_context_v75":
            pctx = (availability.get("players") or {}).get((team, norm_name(name)), {})
            # Preserve V7.5's own estimated minutes when verified; otherwise
            # retain the independent historical ESPN baseline above.
            verified_minutes = _clean_float(pctx.get("minutes"))
            verified_sample = pctx.get("sample", 0)
            if (type(verified_sample) is int and verified_sample >= 3
                    and verified_minutes is not None and 5 <= verified_minutes <= 44):
                player["minutes"] = verified_minutes
                player["minutes_sample"] = verified_sample
                player["minutes_source"] = "V7.5 · szacunek na podstawie historii ESPN"
            # Never overwrite a freshly checked status with a cached V7.5
            # claim of health. Previous unresolved OUT may only block play.
            if (player["availability"] == "Niezweryfikowany"
                    and pctx.get("status") in ("Out", "Questionable",
                                               "Doubtful", "Day-to-day",
                                               "Sprzeczne")):
                player["availability"] = pctx["status"]
        players.append(player)
    # OUT and uncertain players are absent from ALL numerical projection
    # markets (including PRA and the roster-linked minute scenario).
    players, excluded_players = suppress_player_forecasts(
        players, injury_watch, future=future)
    players.sort(key=lambda item: (-(item["pts"] or 0), item["name"]))
    players = players[:40]
    # Link team-roster identities to existing, independently verified player
    # projections. A roster-only player has NO calculated minute sensitivity.
    by_key = {(p["team"], norm_name(p["name"])): idx
              for idx, p in enumerate(players)}
    minute_roster = []
    seen = set()
    for item in roster:
        key = (item["team"], norm_name(item["name"]))
        if key in seen:
            continue
        seen.add(key)
        idx = by_key.get(key)
        p = players[idx] if idx is not None else None
        minute_roster.append({
            **item, "projection_index": idx,
            "availability": (p.get("availability") if p else
                injury_lookup.get(key, "Niezweryfikowany")
                if injury_watch.get("fresh") else "Niezweryfikowany"),
        })
    # A failed ESPN team-roster endpoint must not silently hide the actual
    # historical projections already available for that team.
    for idx, p in enumerate(players):
        key = (p["team"], norm_name(p["name"]))
        if key not in seen and p["team"] not in verified_roster_teams:
            minute_roster.append({
                "name": p["name"], "team": p["team"],
                "position": p.get("position", ""), "roster_status": "",
                "projection_index": idx, "availability": p["availability"],
                "historical_only": True,
            })
            seen.add(key)
    minute_roster.sort(key=lambda item: (
        0 if item["team"] == str(match["away"]) else 1,
        str(item["name"]).casefold()))
    return {"players": players, "minute_roster": minute_roster,
            "excluded_players": excluded_players,
            "availability_policy": ("OUT / niepewny występ bez prognozy"
                                    if future else "Mecz historyczny"),
            "minute_roster_warning": roster_warning,
            "home": str(match["home"]),
            "model_id": model_id, "error": "",
            "minutes_warning": (availability.get("warning", "")
                                if model_id == "research_context_v75" else ""),
            # Current injury availability applies to every player market
            # regardless of team probability model V7.2/V7.4/V7.5.
            "injury_report_fresh": report_is_current(injury_watch) if future else False,
            "injury_report_valid_until": (
                injury_watch.get("valid_until") if future else None),
            # Informational ESPN statuses; unfit/uncertain athletes have no
            # numerical projections in any of the three models.
            "injury_watch": injury_watch}


def simulation_for_entitled_user(day: str, game_id: str, players: bool = False,
                                 model_id: str = "research_form_v74"):
    """Single server-side authorization check for every premium data read."""
    if not premium_entitled():
        return {"error": "Wymagana jest zweryfikowana subskrypcja Premium."}
    try:
        pd.Timestamp(day)
        if (len(day) != 10 or not game_id.isdigit() or len(game_id) > 30
                or model_id not in SIMULATION_MODELS):
            raise ValueError("Niepoprawny identyfikator spotkania")
        return (_game_players(day, game_id, model_id) if players
                else _game_simulation(day, game_id, model_id))
    except (ValueError, TypeError, KeyError, RuntimeError) as exc:
        import logging
        logging.getLogger(__name__).warning("Premium simulation unavailable: %s", type(exc).__name__)
        return {"error": "Dane symulacji są obecnie niedostępne. Spróbuj później."}



def scenario_for_entitled_user(day: str, game_id: str, model_id: str,
                               pace_pct: int, off_away_pct: int = 0,
                               off_home_pct: int = 0) -> dict:
    """Server-side Premium-only what-if model. Never treated as injury news.

    Tempo applies a common percent multiplier to both teams' scoring means.
    Each offense adjustment applies a separate, independent percent multiplier
    to that team's scoring mean. The score variance is held constant.
    These are user assumptions, NOT measured team form, possessions,
    official injury status or player-level production.
    """
    if not premium_entitled():
        return {"error": "Wymagana jest zweryfikowana subskrypcja Premium."}
    if (any(type(v) is not int or not -5 <= v <= 5
            for v in (pace_pct, off_away_pct, off_home_pct))
            or model_id not in SIMULATION_MODELS or not isinstance(day, str)
            or not isinstance(game_id, str)
            or len(day) != 10 or not game_id.isdigit() or len(game_id) > 30):
        return {"error": "Niepoprawne parametry scenariusza."}
    try:
        if pd.Timestamp(day).strftime("%Y-%m-%d") != day:
            return {"error": "Niepoprawna data scenariusza."}
        now = pd.Timestamp.now(tz="UTC")
        if abs((pd.Timestamp(day).date() - now.date()).days) > 366:
            return {"error": "Data poza dozwolonym okresem."}
        event = _day_for_simulations(day)
        fixture = next((g for g in event.get("games", [])
                        if str(g.get("id")) == game_id), None)
        if not fixture or fixture.get("state") != "scheduled":
            return {"error": "Scenariusze dostępne tylko przed meczem."}
        start = pd.to_datetime(fixture.get("start"), utc=True, errors="coerce")
        if pd.isna(start) or start <= now:
            return {"error": "Mecz już się rozpoczął lub brak potwierdzonego terminu."}
        baseline = _game_simulation(day, game_id, model_id)
        if baseline.get("error"):
            return {"error": baseline["error"]}
        modified = (_game_simulation(
            day, game_id, model_id, pace_pct=pace_pct,
            off_away_pct=off_away_pct, off_home_pct=off_home_pct)
            if any((pace_pct, off_away_pct, off_home_pct)) else baseline)
        if modified.get("error"):
            return {"error": modified["error"]}
        keys = ("away_points", "home_points", "total_points",
                "away_win_pct", "home_win_pct")
        return {
            "date": day, "game_id": game_id, "model_id": model_id,
            "pace_pct": pace_pct, "off_away_pct": off_away_pct,
            "off_home_pct": off_home_pct, "n_sims": 5000,
            "baseline": {key: baseline[key] for key in keys},
            "scenario": {key: modified[key] for key in keys},
            # Reuse already generated Monte Carlo distributions (no model
            # re-run): 5-point bins for the two overlay curves and exact
            # integer score frequencies for editable OVER/UNDER comparisons.
            "baseline_distribution": baseline["distributions"]["match"],
            "scenario_distribution": modified["distributions"]["match"],
            "baseline_flow": baseline.get("flow"),
            "scenario_flow": modified.get("flow"),
            "hypothetical": True,
            "description": (
                f"Hipotetyczne tempo {pace_pct:+d}%; "
                f"ofensywa gości {off_away_pct:+d}%; "
                f"ofensywa gospodarzy {off_home_pct:+d}%. "
                "Bez symulacji zmian składu, minut i kontuzji."),

        }
    except (ValueError, TypeError, KeyError, RuntimeError, OverflowError) as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Scenario Builder unavailable: %s", type(exc).__name__)
        return {"error": "Scenariusz chwilowo niedostępny."}



def player_minutes_scenario_for_entitled_user(
        day: str, game_id: str, model_id: str, player_name: str,
        team: str, minute_delta: int) -> dict:
    """Isolated ESPN-history minute sensitivity, not another Monte Carlo run.

    Reuses server-confirmed historical player means and minutes for the
    exact future NBA fixture. Assumes constant rate per minute. It does NOT
    simulate lineup substitution, pace, injuries, win chance, uncertainty,
    team totals or independently sampled PRA. No cross-account cache.
    """
    if not premium_entitled():
        return {"error": "Wymagana jest zweryfikowana subskrypcja Premium."}
    if (model_id not in SIMULATION_MODELS or
            not isinstance(day, str) or len(day) != 10 or
            not isinstance(game_id, str) or
            not game_id.isdigit() or len(game_id) > 30 or
            not isinstance(player_name, str) or
            not player_name.strip() or len(player_name) > 70 or
            not isinstance(team, str) or len(team) != 3 or
            not team.isalpha() or team != team.upper() or
            type(minute_delta) is not int or not -5 <= minute_delta <= 5):
        return {"error": "Niepoprawne parametry analizy minut."}
    try:
        if pd.Timestamp(day).strftime("%Y-%m-%d") != day:
            return {"error": "Niepoprawna data spotkania."}
        now = pd.Timestamp.now(tz="UTC")
        if abs((pd.Timestamp(day).date() - now.date()).days) > 366:
            return {"error": "Data poza dozwolonym okresem."}
        fixture = next((g for g in _day_for_simulations(day).get("games", [])
                        if str(g.get("id")) == game_id), None)
        if (fixture is None or fixture.get("state") != "scheduled" or
                team not in {fixture.get("away"), fixture.get("home")}):
            return {"error": "Dostępne tylko dla potwierdzonego przyszłego meczu i drużyny."}
        tipoff = pd.to_datetime(fixture.get("start"), utc=True, errors="coerce")
        if pd.isna(tipoff) or tipoff <= now:
            return {"error": "Spotkanie już się rozpoczęło."}
        player_pack = _game_players(day, game_id, model_id)
        if not isinstance(player_pack, dict) or player_pack.get("error"):
            return {"error": "Zweryfikowane projekcje zawodników są niedostępne."}
        choices = [p for p in player_pack.get("players", [])
                   if p.get("name") == player_name.strip() and p.get("team") == team]
        if len(choices) != 1:
            return {"error": "Nie udało się jednoznacznie dopasować zawodnika i drużyny."}
        player = choices[0]
        status = str(player.get("availability") or "Niezweryfikowany")
        if status == "Out":
            return {"error": "Status OUT w raporcie ESPN — nie można wyświetlić scenariusza minut."}
        minutes = _clean_float(player.get("minutes"))
        sample = player.get("minutes_sample")
        if (type(sample) is not int or sample < 3 or
                minutes is None or not 5 <= minutes <= 44):
            return {"error": "Brak wiarygodnej próbki co najmniej trzech występów i szacunku minut."}
        new_minutes = round(minutes + minute_delta, 2)
        if not 5 <= new_minutes <= 44:
            return {"error": "Zmiana powodowałaby minuty poza zakresem 5–44."}
        baseline, adjusted = {}, {}
        for metric in ("pts", "reb", "ast"):
            estimate = _clean_float(player.get(metric))
            if estimate is None or not 0 <= estimate <= 70:
                return {"error": "Niepełne projekcje PTS, REB i AST; nie wyliczono wariantu."}
            baseline[metric] = round(estimate, 2)
            adjusted[metric] = round(estimate * new_minutes / minutes, 2)
        baseline["pra"] = round(sum(baseline.values()), 2)
        adjusted["pra"] = round(sum(adjusted[k] for k in ("pts", "reb", "ast")), 2)
        return {
            "date": day, "game_id": game_id, "model_id": model_id,
            "name": player_name.strip(), "team": team,
            "minute_delta": minute_delta, "baseline_minutes": minutes,
            "scenario_minutes": new_minutes, "minutes_sample": sample,
            "availability": status,
            "minutes_source": str(player.get("minutes_source") or "ESPN · ostatnie mecze")[:110],
            "baseline": baseline, "scenario": adjusted,
            "hypothetical": True,
            "method": "Stała produkcja na minutę; skalowanie średnich, bez symulacji rozkładu.",
            "warning": ("Minuty z historii ESPN / V7.5: " + status +
                        ". Nie jest to potwierdzony czas gry. "
                        "Bez wpływu na wynik meczu i produkcję kolegów z drużyny."),
        }
    except (ValueError, TypeError, KeyError, RuntimeError, OverflowError) as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Player minute sensitivity unavailable: %s", type(exc).__name__)
        return {"error": "Analiza minut jest obecnie niedostępna."}



@st.cache_data(ttl=3600, max_entries=3, show_spinner=False)
def _cached_walkforward_report(season: str) -> dict:
    """Bounded on-demand season report; no live injury/advanced lookahead.

    This is the *offline historical research core*, not a fully replicated
    production V7.5 forecast. Historical odds were not recorded and ROI
    therefore cannot be computed truthfully.
    """
    from simulation_backtest import walk_forward_comparison
    from simulation_data_audit import verified_history

    generated = pd.Timestamp.now(tz="UTC")
    history, warning = _history_for_simulations(season)
    evidence = verified_history(history, generated)
    if evidence.empty:
        return {"error": "Brak potwierdzonych zakończonych spotkań ESPN w bieżącym sezonie."}
    events, results = walk_forward_comparison(evidence, max_games=40)
    n = results.get("games", 0)
    if not isinstance(n, int) or n < 1 or events.empty:
        return {"error": "Za mało historycznych danych do testu walk-forward."}
    labels = (
        ("old", "Baseline · średnie historyczne"),
        ("new", "Forma · średnie ważone"),
        ("enriched", "V7.4 · rdzeń offline"),
        ("v75", "V7.5 · rdzeń offline"),
    )
    comparisons = []
    for key, label in labels:
        total = _clean_float(results.get(key + "_total_mae"))
        team = _clean_float(results.get(key + "_team_mae"))
        brier_raw = results.get(key + "_brier")
        accuracy_raw = results.get(key + "_winner_accuracy")
        try:
            accuracy = float(accuracy_raw)
            brier = float(brier_raw)
        except (ValueError, TypeError, OverflowError):
            return {"error": "Niekompletne wyniki walidacji historycznej."}
        if (total is None or team is None or
                not isfinite(accuracy) or not 0 <= accuracy <= 1 or
                not isfinite(brier) or not 0 <= brier <= 1):
            return {"error": "Niepoprawne metryki walidacji historycznej."}
        comparisons.append({
            "key": key, "label": label, "total_mae": total,
            "team_mae": team, "winner_accuracy_pct": round(accuracy * 100, 1),
            "brier": round(brier, 4),
        })
    start = pd.to_datetime(events["date"].min(), utc=True, errors="coerce")
    end = pd.to_datetime(events["date"].max(), utc=True, errors="coerce")
    return {
        "season": season, "games": n, "max_games": 40,
        "as_of_utc": generated.isoformat(),
        "first_game": start.date().isoformat() if pd.notna(start) else None,
        "last_game": end.date().isoformat() if pd.notna(end) else None,
        "models": comparisons,
        "data_source": "ESPN · potwierdzone wyniki rozegranych meczów",
        "method": "Walk-forward: każdy oceniany mecz prognozowany tylko z wcześniejszych wyników; maks. 40 ocenianych spotkań.",
        "limitation": (
            "Testowany rdzeń historyczny bez rzeczywistego NBA Advanced "
            "ani raportu ESPN kontuzji dostępnego przed dawnymi meczami. "
            "To nie jest dokładny wynik pełnego modelu produkcyjnego V7.5."
        ),
        "roi_available": False,
        "odds_available": False,
        "warning": str(warning or "")[:180],
    }


def backtest_for_entitled_user() -> dict:
    """On-demand report, never requested by free users or on page startup."""
    if not premium_entitled():
        return {"error": "Wymagana jest zweryfikowana subskrypcja Premium."}
    try:
        season = _season_at(pd.Timestamp.now(tz="UTC"))
        return _cached_walkforward_report(season)
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, OverflowError) as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Premium walk-forward report unavailable (%s)", type(exc).__name__)
        return {"error": "Nie udało się obliczyć raportu historycznego."}
