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
                "threshold": None, "over_pct": None}
    lo = int(np.floor(float(values.min()) / 5) * 5)
    hi = int(np.ceil(float(values.max()) / 5) * 5) + 5
    edges = np.arange(lo, hi + 1, 5)
    counts, _ = np.histogram(values, bins=edges)
    average = float(values.mean())
    threshold = int(round(average / 5) * 5)
    return {
        "bins": [{"x": int(edges[i]), "p": round(100 * int(count) / values.size, 3)}
                 for i, count in enumerate(counts)],
        "p10": int(np.percentile(values, 10)),
        "p90": int(np.percentile(values, 90)),
        "average": round(average, 1),
        "threshold": threshold,
        "over_pct": round(100 * float(np.count_nonzero(values >= threshold)) / values.size, 1),
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
    """Parse the season scoreboards once for concurrent Premium selections."""
    from simulation_sources import historical_espn_results
    return historical_espn_results(season)


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
        "n_sims": summary["n_sims"], "source": str(summary.get("source") or "ESPN"),
        "warning": str(warning or "")[:150],
        "retrospective": match.get("state") == "final",
        "model_context": context["context"],
        "players": None,
    }


@st.cache_data(ttl=600, max_entries=50, show_spinner=False)
def _game_players(day: str, game_id: str, model_id: str = "research_form_v74"):
    """Lazily fetch only the selected matchup's two actual ESPN player histories."""
    from simulation_view import matchup_players_cached

    event = _day_for_simulations(day)
    match = next((g for g in event.get("games", []) if str(g.get("id")) == game_id), None)
    if match is None or match.get("state") not in ("scheduled", "final"):
        return {"error": "Nie znaleziono potwierdzonego spotkania.", "players": []}
    tipoff = pd.to_datetime(match.get("start"), utc=True, errors="coerce")
    if pd.isna(tipoff) or (match.get("state") == "scheduled" and
                            tipoff <= pd.Timestamp.now(tz="UTC")):
        return {"error": "Nieaktualny termin spotkania.", "players": []}
    season = _season_at(tipoff)
    historical, _ = _history_for_simulations(season)
    game = {"game_id": game_id, "home": str(match["home"]),
            "away": str(match["away"]), "start_utc": tipoff}
    advanced = (_advanced_from_verified_cache(season)
                if match.get("state") == "scheduled" else pd.DataFrame())
    availability = {}
    if model_id == "research_context_v75":
        table, availability = _v75_player_evidence(day, game_id)
    else:
        table, _ = matchup_players_cached(season, game, historical,
                                          advanced, 0,
                                          research_mode=model_id != "legacy_v72")
    if table is None or table.empty:
        return {"players": [], "error": "ESPN nie dostarczył projekcji graczy dla tego spotkania."}
    required = {"Zawodnik", "Drużyna", "PTS", "REB", "AST"}
    if not required.issubset(table.columns):
        return {"players": [], "error": "Źródło nie dostarczyło pełnych statystyk zawodników."}
    players = []
    from core import norm_name
    for row in table.to_dict("records"):
        name = str(row.get("Zawodnik") or "").strip()
        team = str(row.get("Drużyna") or "").upper().strip()
        points = _clean_float(row.get("PTS"))
        # Never show a player whose verified team identity is outside the two
        # sides of the selected fixture, even if the ESPN table is stale.
        if (not name or team not in {str(match["away"]), str(match["home"])}
                or points is None):
            continue
        player = {"name": name[:70], "team": team[:4],
                  "pts": points, "reb": _clean_float(row.get("REB")),
                  "ast": _clean_float(row.get("AST"))}
        if model_id == "research_context_v75":
            pctx = (availability.get("players") or {}).get((team, norm_name(name)), {})
            player["minutes"] = pctx.get("minutes")
            player["minutes_sample"] = pctx.get("sample", 0)
            player["availability"] = pctx.get("status", "Niezweryfikowany")
            # A fresh OUT designation removes the player's projected minutes
            # and production; other players are NOT blindly credited with them.
            if pctx.get("status") == "Out":
                player.update({"pts": None, "reb": None, "ast": None})
        players.append(player)
    # OUT players have no projected production; keep them visible after
    # available scorers rather than treating missing values as zero points.
    players.sort(key=lambda item: (-(item["pts"] or 0), item["name"]))
    return {"players": players[:40], "home": str(match["home"]),
            "model_id": model_id, "error": "",
            "minutes_warning": (availability.get("warning", "")
                                if model_id == "research_context_v75" else ""),
            # Injury Watch consumes the exact same server-derived V7.5
            # evidence as the team model and the selected player view.
            "injury_report_fresh": bool(availability.get("report_fresh"))
                if model_id == "research_context_v75" else False,
            "injury_report_valid_until": (
                availability.get("report_valid_until")
                if model_id == "research_context_v75" else None)}


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
    """Isolated V7.5 minute *sensitivity*, not another Monte Carlo run.

    Reuses server-confirmed historical player means and minutes for the
    exact future NBA fixture. Assumes constant rate per minute. It does NOT
    simulate lineup substitution, pace, injuries, win chance, uncertainty,
    team totals or independently sampled PRA. No cross-account cache.
    """
    if not premium_entitled():
        return {"error": "Wymagana jest zweryfikowana subskrypcja Premium."}
    if (model_id != "research_context_v75" or
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
        player_pack = _game_players(day, game_id, "research_context_v75")
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
            "baseline": baseline, "scenario": adjusted,
            "hypothetical": True,
            "method": "Stała produkcja na minutę; skalowanie średnich, bez symulacji rozkładu.",
            "warning": ("ESPN: " + status +
                        ". Nie jest to potwierdzony czas gry. "
                        "Bez wpływu na wynik meczu i produkcję kolegów z drużyny."),
        }
    except (ValueError, TypeError, KeyError, RuntimeError, OverflowError) as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Player minute sensitivity unavailable: %s", type(exc).__name__)
        return {"error": "Analiza minut jest obecnie niedostępna."}
