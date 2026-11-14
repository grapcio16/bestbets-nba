"""Verified-data adapter for the HOOPZARO Premium simulation canvas.

No simulation data may be sent to the browser unless the Streamlit session has
been authenticated and marked entitled by a trusted server-side payment flow.
The public interface deliberately shows an empty (not invented) preview until
that integration is available.
"""
from __future__ import annotations

from math import isfinite

import numpy as np
import pandas as pd
import streamlit as st


def premium_entitled() -> bool:
    """Fail closed; no client event or query parameter can grant access.

    An eventual Stripe webhook/auth callback must validate the *current user*
    and explicitly set this server-side session value. It is never set here.
    """
    return st.session_state.get("bb_verified_premium_entitlement") is True


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


@st.cache_data(ttl=1800, max_entries=90, show_spinner=False)
def _game_simulation(day: str, game_id: str):
    """Run the existing model only for a confirmed, future ESPN fixture."""
    from bestbets_centre_live import get_centre_day_data
    from simulation_sources import historical_espn_results
    from simulation_engine import (completed_team_scores, select_matchup_means,
                                   simulate_game)

    event = get_centre_day_data(day)
    games = event.get("games", [])
    match = next((g for g in games if str(g.get("id")) == game_id), None)
    if match is None or match.get("state") != "scheduled":
        return {"error": "Symulacje obejmują tylko przyszłe potwierdzone spotkania NBA."}
    tipoff = pd.to_datetime(match.get("start"), utc=True, errors="coerce")
    if pd.isna(tipoff) or tipoff <= pd.Timestamp.now(tz="UTC"):
        return {"error": "Spotkanie już się rozpoczęło. Prognoza przedmeczowa jest niedostępna."}
    historical, warning = historical_espn_results("2026-27")
    if historical is None or historical.empty:
        return {"error": "Brak wystarczającej zweryfikowanej historii ESPN."}
    away, home = str(match.get("away", "")), str(match.get("home", ""))
    means = select_matchup_means(home, away, {}, completed_team_scores(historical))
    if means is None:
        return {"error": "Za mało historycznych spotkań do wiarygodnej symulacji."}
    game = {"game_id": game_id, "home": home, "away": away, "start_utc": tipoff}
    summary, _, home_scores, away_scores = simulate_game(game, means)
    return {
        "game_id": game_id, "away": away, "home": home,
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
        "players": None,
    }


@st.cache_data(ttl=1800, max_entries=50, show_spinner=False)
def _game_players(day: str, game_id: str):
    """Lazily fetch only the selected matchup's two actual ESPN player histories."""
    from bestbets_centre_live import get_centre_day_data
    from simulation_sources import historical_espn_results
    from simulation_view import matchup_players_cached

    event = get_centre_day_data(day)
    match = next((g for g in event.get("games", []) if str(g.get("id")) == game_id), None)
    if match is None or match.get("state") != "scheduled":
        return {"error": "Nie znaleziono nadchodzącego spotkania.", "players": []}
    tipoff = pd.to_datetime(match.get("start"), utc=True, errors="coerce")
    if pd.isna(tipoff) or tipoff <= pd.Timestamp.now(tz="UTC"):
        return {"error": "Projekcje przedmeczowe są niedostępne.", "players": []}
    historical, _ = historical_espn_results("2026-27")
    game = {"game_id": game_id, "home": str(match["home"]),
            "away": str(match["away"]), "start_utc": tipoff}
    table, _ = matchup_players_cached("2026-27", game, historical,
                                      pd.DataFrame(), 0, research_mode=False)
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
    return {"players": players[:40], "home": str(match["home"]), "error": ""}


def simulation_for_entitled_user(day: str, game_id: str, players: bool = False):
    """Single server-side authorization check for every premium data read."""
    if not premium_entitled():
        return {"error": "Wymagana jest zweryfikowana subskrypcja Premium."}
    try:
        pd.Timestamp(day)
        if len(day) != 10 or not game_id.isdigit() or len(game_id) > 30:
            raise ValueError("Niepoprawny identyfikator spotkania")
        return _game_players(day, game_id) if players else _game_simulation(day, game_id)
    except (ValueError, TypeError, KeyError, RuntimeError) as exc:
        import logging
        logging.getLogger(__name__).warning("Premium simulation unavailable: %s", type(exc).__name__)
        return {"error": "Dane symulacji są obecnie niedostępne. Spróbuj później."}
