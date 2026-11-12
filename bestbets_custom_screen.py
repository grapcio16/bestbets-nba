"""BestBets v10 — custom pixel-coordinated Player Props frontend.

The only new public shell is HTML/CSS/JS in a Streamlit v1 component.
All player facts are calculated on the server using the established
ESPN/NBA game-log pipeline. No fake game, odds, grade or rank.
"""
from __future__ import annotations

from base64 import b64encode
from pathlib import Path
from math import isfinite
from typing import Any
import uuid
import time

import pandas as pd
import streamlit as st
from streamlit.components.v1 import declare_component

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "bestbets_reference_frontend"
COMPONENT = declare_component("bestbets_reference_canvas_v10", path=str(FRONTEND))
SEASON = "2026-27"


@st.cache_data(ttl=100, show_spinner=False)
def _cached_centre_live() -> dict:
    """Share fresh public scoreboard data between sessions, no secrets."""
    from bestbets_centre_live import get_centre_live_data
    return get_centre_live_data()


def _safe_centre_live() -> dict:
    """Always give the frontend a complete status, even on backend failures."""
    try:
        snapshot = _cached_centre_live()
        if isinstance(snapshot, dict) and "games" in snapshot and "ticker" in snapshot:
            return snapshot
    except Exception as exc:
        # Log a controlled exception TYPE only; never leak API URLs, tokens
        # or raw exception messages into the public dashboard.
        import logging
        logging.getLogger(__name__).warning(
            "Centrum source failed: %s", type(exc).__name__
        )
    return {
        "games": [], "all_games": [], "ticker": [], "finals": [],
        "form": [], "players": [], "source": "NBA / ESPN",
        "as_of": "", "fetched_at": "", "coverage": "",
        "error": "Nie udało się pobrać danych. Spróbuj odświeżyć Centrum."
    }


def _plain(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() in ("nan", "none", "null", "<na>") else text


def _number(value: Any) -> float | None:
    try:
        num = float(value)
        return round(num, 3) if isfinite(num) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _brand_image() -> str:
    file = ROOT / "assets" / "bestbets_brand_icon_64.png"
    if not file.is_file():
        return ""
    return "data:image/png;base64," + b64encode(file.read_bytes()).decode("ascii")


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_brand() -> str:
    return _brand_image()


def _research(query: str) -> dict:
    """Run the existing strict athlete resolver and verified season analysis."""
    from core import norm_name, normalize_logs
    from mvp_app import get_logs, get_schedule
    from mvp_prop_ui import _match_proposals, _run_research
    from prop_search import parse_prop_batch
    from screenshot_ui import _safe_catalog
    from season_props import clean_player_season
    from team_logos import logo_data_uri
    from teams import TEAM_FULL

    parsed, errors = parse_prop_batch(query.strip(), max_items=1)
    if errors:
        raise ValueError("; ".join(str(error) for error in errors)[:240])
    if len(parsed) != 1:
        raise ValueError("Wpisz jedno zdarzenie: imię i nazwisko, OVER/UNDER, linia oraz rynek.")
    catalog, coverage = _safe_catalog(0)
    if catalog is None or catalog.empty:
        raise ValueError("Nie udało się pobrać aktualnego katalogu zawodników NBA.")
    proposals = _match_proposals(parsed, catalog)
    if proposals.empty:
        raise ValueError("Nie znaleziono zawodnika.")
    quality = _plain(proposals.iloc[0].get("Dopasowanie"))
    if quality != "exact":
        raise ValueError(
            "Wpisz pełne imię i nazwisko zawodnika zgodne z katalogiem NBA. "
            "Nie analizujemy niepotwierdzonych dopasowań."
        )

    def get_normalized_logs():
        logs, meta = get_logs(SEASON, 0)
        return normalize_logs(logs), meta

    today = pd.Timestamp.now(tz="Europe/Warsaw").date()
    table, histories, fixtures, notices = _run_research(
        proposals, SEASON, 0, today, "Europe/Warsaw",
        get_schedule, get_normalized_logs
    )
    if table is None or table.empty:
        raise ValueError("Źródło NBA nie zwróciło potwierdzonej analizy.")
    row = table.iloc[0]
    if pd.isna(row.get("Występy sezon")):
        raise ValueError(
            "Brak pełnej zweryfikowanej historii sezonu dla tego zawodnika."
        )
    name = _plain(row.get("Zawodnik"))
    team = _plain(row.get("Drużyna"))
    player_id = _plain(row.get("_espn_id"))
    raw = histories.get(norm_name(name))
    event = fixtures.get(team)
    asof = (
        event["start_utc"]
        if isinstance(event, dict) and not event.get("ambiguous") and event.get("start_utc") is not None
        else pd.Timestamp.now(tz="UTC")
    )
    games = clean_player_season(raw, name, SEASON, asof, player_id or None)
    if games.empty:
        raise ValueError("Brak potwierdzonych występów do wyświetlenia.")
    records = []
    for _, match in games.iterrows():
        stamp = pd.to_datetime(match.get("GAME_DATE"), utc=True, errors="coerce")
        if pd.isna(stamp):
            continue
        records.append({
            "date": stamp.strftime("%Y-%m-%d"),
            "matchup": _plain(match.get("MATCHUP")),
            "PTS": _number(match.get("PTS")),
            "REB": _number(match.get("REB")),
            "AST": _number(match.get("AST")),
            "FG3M": _number(match.get("FG3M")),
            "PRA": _number(match.get("PRA")),
        })
    if not records:
        raise ValueError("Źródło nie zwróciło użytecznych wyników meczów.")
    market = _plain(row.get("Rynek")) or "PTS"
    if market not in ("PTS", "REB", "AST", "FG3M", "PRA"):
        market = "PTS"
    line = _number(row.get("Linia"))
    if line is None or line < 0 or line > 150:
        raise ValueError("Niepoprawna linia w analizowanym zdarzeniu.")
    side = _plain(row.get("Wybór")).upper()
    if side not in ("OVER", "UNDER"):
        side = "OVER"
    opponent = _plain(row.get("Przeciwnik"))
    photo = (
        f"https://a.espncdn.com/i/headshots/nba/players/full/{player_id}.png"
        if player_id.isdigit() else ""
    )
    logo = ""
    try:
        if team in TEAM_FULL:
            logo = logo_data_uri(team) or ""
    except (RuntimeError, ValueError, KeyError, TypeError):
        pass

    start_label = ""
    if isinstance(event, dict) and not event.get("ambiguous") and event.get("start_utc") is not None:
        time = pd.to_datetime(event["start_utc"], errors="coerce", utc=True)
        if not pd.isna(time):
            start_label = time.tz_convert("Europe/Warsaw").strftime("%d.%m %H:%M")
    defense = _number(row.get("Obrona: stracone pkt/mecz"))
    defense_recent = _number(row.get("Obrona: L10 stracone"))
    return {
        "name": name,
        "team": team,
        "position": _plain(row.get("Pozycja")),
        "opponent": opponent,
        "opponent_full": TEAM_FULL.get(opponent, opponent),
        "next_game": start_label,
        "photo": photo,
        "logo": logo,
        "season": SEASON,
        "market": market,
        "line": line,
        "side": side,
        "games": records,
        "defense": defense,
        "defense_recent": defense_recent,
        "source": _plain(row.get("Źródło statystyk")) or "NBA / ESPN",
        "notices": [str(x)[:150] for x in notices[:3]] if notices else [],
    }


def main() -> None:
    st.markdown(
        """<style>
        [data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],
        [data-testid="stHeader"],[data-testid="stToolbar"],
        [data-testid="stDecoration"],footer{display:none!important}
        [data-testid="stAppViewContainer"],[data-testid="stMain"]{
            background:#020713!important;min-height:100vh!important
        }
        [data-testid="stMainBlockContainer"],.block-container{
            max-width:100%!important;width:100%!important;
            padding:0!important;margin:0!important
        }
        [data-testid="stMain"] [data-testid="stVerticalBlock"]{gap:0!important}
        [data-testid="stMain"] iframe{
            display:block!important;border:0!important;
            width:100%!important;background:#020713!important;
            /* Hard cap the embedded canvas to the visible app area.
               Child resize() scales both axes to keep ALL six tiles visible. */
            height:calc(100vh - 4px)!important;
            height:calc(100dvh - 4px)!important;
            min-height:0!important;
        }
        .stApp{background:#020713!important}
        </style>""", unsafe_allow_html=True
    )
    if "bb10_payload" not in st.session_state:
        st.session_state["bb10_payload"] = {"player": None, "error": ""}
    # CRITICAL: preload data BEFORE mounting the v1 iframe. Production
    # sometimes discards the initial setComponentValue/home_data message,
    # leaving the dashboard spinning indefinitely. The home snapshot is
    # now supplied in the very first streamlit:render packet.
    if "bb10_centre_data" not in st.session_state:
        st.session_state["bb10_centre_data"] = _safe_centre_live()
        st.session_state["bb10_centre_last_at"] = time.monotonic()
    payload = {
        "brand": _cached_brand(),
        "player": st.session_state["bb10_payload"].get("player"),
        "error": st.session_state["bb10_payload"].get("error", ""),
        "home": st.session_state.get("bb10_centre_data"),
    }
    event = COMPONENT(payload=payload, default=None, key="bb10_reference_canvas")
    if not isinstance(event, dict):
        return
    event_id = _plain(event.get("id"))
    if not event_id or event_id == st.session_state.get("bb10_last_event"):
        return
    st.session_state["bb10_last_event"] = event_id
    if event.get("type") == "home_data":
        # Lazy after first paint. Refresh every 2 minutes while home is
        # visible. The shared cache avoids repeated requests per visitor.
        now=time.monotonic()
        last=st.session_state.get("bb10_centre_last_at",0.0)
        force=event.get("force") is True
        # Honor manual refresh with per-session rate limiting. The shared
        # TTL remains the authority to avoid abusing public NBA endpoints.
        if "bb10_centre_data" not in st.session_state or now-last>=120.0 or (force and now-last>=25.0):
            st.session_state["bb10_centre_data"] = _safe_centre_live()
            st.session_state["bb10_centre_last_at"] = now
        st.rerun()
        return
    if event.get("type") != "search":
        return
    query = _plain(event.get("query"))
    if len(query) > 280:
        st.session_state["bb10_payload"] = {"player": None, "error": "Zapytanie jest za długie."}
    elif not query:
        st.session_state["bb10_payload"] = {"player": None, "error": "Wpisz zdarzenie do wyszukania."}
    else:
        try:
            athlete = _research(query)
            st.session_state["bb10_payload"] = {"player": athlete, "error": ""}
        except (ValueError, KeyError, RuntimeError, TypeError, IndexError) as exc:
            st.session_state["bb10_payload"] = {"player": None, "error": str(exc)[:280]}
    st.rerun()
