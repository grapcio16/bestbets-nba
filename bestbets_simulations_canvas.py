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

SIMULATION_MODELS = {"legacy_v72", "research_form_v74"}


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


@st.cache_data(ttl=1800, max_entries=90, show_spinner=False)
def _game_simulation(day: str, game_id: str, model_id: str = "research_form_v74"):
    """Future model, or clearly labeled retrospective model for a final game."""
    from espn_player_data import prefetch_matchup_boxscores
    from simulation_engine import (advanced_ratings, completed_team_scores,
                                   legacy_matchup_means, simulate_game)
    from simulation_context_v2 import simulation_inputs
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
    context = simulation_inputs(historical, game, advanced)
    # Both modes use identical verified pregame evidence. The legacy baseline
    # retains its original fixed variance; the research variant additionally
    # uses observed, shrunk team scoring variance.
    means = (legacy_matchup_means(
        home, away, advanced_ratings(advanced),
        completed_team_scores(verified_history(historical, tipoff)))
        if model_id == "legacy_v72" else context["means"])
    if means is None:
        return {"error": "Za mało historycznych spotkań do wiarygodnej symulacji."}
    # Warm actual player boxscores while the independent team model runs.
    # Only the server-authorized Premium simulation calls this path; warming
    # failures cannot affect the primary 5,000-run model.
    try:
        prefetch_matchup_boxscores(historical, game)
    except (OSError, RuntimeError, ValueError):
        pass
    summary, _, home_scores, away_scores = simulate_game(
        game, means, score_noise=(context["score_noise"]
                                 if model_id == "research_form_v74" else None))
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


@st.cache_data(ttl=1800, max_entries=50, show_spinner=False)
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
    table, _ = matchup_players_cached(season, game, historical,
                                      advanced, 0,
                                      research_mode=model_id == "research_form_v74")
    if table is None or table.empty:
        return {"players": [], "error": "ESPN nie dostarczył projekcji graczy dla tego spotkania."}
    required = {"Zawodnik", "Drużyna", "PTS", "REB", "AST"}
    if not required.issubset(table.columns):
        return {"players": [], "error": "Źródło nie dostarczyło pełnych statystyk zawodników."}
    players = []
    for row in table.to_dict("records"):
        name = str(row.get("Zawodnik") or "").strip()
        team = str(row.get("Drużyna") or "").upper().strip()
        points = _clean_float(row.get("PTS"))
        if not name or not team or points is None:
            continue
        players.append({"name": name[:70], "team": team[:4],
                        "pts": points, "reb": _clean_float(row.get("REB")),
                        "ast": _clean_float(row.get("AST"))})
    players.sort(key=lambda item: (-item["pts"], item["name"]))
    return {"players": players[:40], "home": str(match["home"]),
            "model_id": model_id, "error": ""}


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
