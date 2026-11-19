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
import os
import uuid
import time

import pandas as pd
import streamlit as st

from teams import TEAM_FULL
from bestbets_free_analyses import SCHEMA, photo_policy, select_leader
from bestbets_simulations_canvas import premium_entitled, simulation_for_entitled_user
from access_control import (auth_configured, auth_context, current_principal,
                            current_role, login_provider)
from checkout_links import validated_checkout_url, is_test_checkout_url
from streamlit.components.v1 import declare_component

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "bestbets_reference_frontend"
COMPONENT = declare_component("bestbets_reference_canvas_v10", path=str(FRONTEND))
SEASON = "2026-27"


def premium_checkout_url() -> str:
    """Only expose a public, explicitly configured Stripe checkout destination.

    Stripe secret keys and unverified URLs must never reach the browser.
    """
    url = os.environ.get("HOOPZARO_PREMIUM_CHECKOUT_URL", "").strip()
    if not url:
        try:
            url = str(st.secrets.get("HOOPZARO_PREMIUM_CHECKOUT_URL", "")).strip()
        except (FileNotFoundError, KeyError, AttributeError, RuntimeError):
            return ""
    url = validated_checkout_url(url)
    if not url:
        return ""
    # A Payment Link alone cannot grant an account access. Until Stripe's
    # fulfillment/webhook path is verified, only test links may be exposed.
    if not is_test_checkout_url(url):
        ready = os.environ.get("HOOPZARO_PREMIUM_FULFILLMENT_READY", "").lower()
        if not ready:
            try:
                ready = str(st.secrets.get("HOOPZARO_PREMIUM_FULFILLMENT_READY", "")).lower()
            except (FileNotFoundError, KeyError, AttributeError, RuntimeError):
                return ""
        if ready not in ("true", "1", "yes"):
            return ""
    return url


@st.cache_data(ttl=100, show_spinner=False)
def _cached_centre_live() -> dict:
    """Share fresh public scoreboard data between sessions, no secrets."""
    from bestbets_centre_live import get_centre_live_data
    return get_centre_live_data()


@st.cache_data(ttl=120, show_spinner=False)
def _cached_free_details(leader: dict) -> dict:
    from bestbets_free_analyses import get_free_leader_boxscore
    return get_free_leader_boxscore(leader)


@st.cache_data(ttl=900, show_spinner=False)
def _cached_centre_day(day: str) -> dict:
    from bestbets_centre_live import get_centre_day_data
    return get_centre_day_data(day)


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
        "injury_watch": {"rows": [], "available": False, "stale": False, "as_of": "", "source": "ESPN"},
        "free_schema": SCHEMA, "free_leaders": [], "free_leader_day": "",
        "form": [], "form_options": [
            {"team": code, "name": name, "logo": "", "wins": 0, "losses": 0, "sample": 0}
            for code, name in sorted(TEAM_FULL.items(), key=lambda pair: pair[1])
        ], "players": [], "source": "NBA / ESPN",
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
    file = ROOT / "assets" / "hoopzaro.svg"
    if not file.is_file():
        return ""
    return "data:image/svg+xml;base64," + b64encode(file.read_bytes()).decode("ascii")


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_brand() -> str:
    return _brand_image()

@st.cache_data(ttl=3600, max_entries=2, show_spinner=False)
def _cached_centre_player_catalog(force_refresh: bool = False):
    """Load all ESPN team rosters only on explicit player-picker request."""
    from datetime import datetime, timezone
    from global_player_catalog import build_global_catalog

    table, coverage = build_global_catalog(refresh_all=force_refresh)
    players = []
    for row in table.to_dict("records"):
        pid = str(row.get("PLAYER_ID") or "")
        name = str(row.get("PLAYER_NAME") or "").strip()
        team = str(row.get("TEAM_ABBREVIATION") or "")
        if pid.isdigit() and name and team in TEAM_FULL:
            position = str(row.get("POSITION") or "").strip().upper()
            if position not in {"PG", "SG", "SF", "PF", "C", "G", "F", "G-F", "F-G", "F-C", "C-F"}:
                position = ""
            players.append({"id": pid, "name": name[:90], "team": team, "position": position})
    return {"players": players, "coverage": {**coverage,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
            "photo_license_enabled": photo_policy()}}


@st.cache_data(ttl=3*3600, max_entries=512, show_spinner=False)
def _cached_premium_player_history(player_id: str, name: str, team: str) -> dict:
    """Fetch a verified athlete's season, with a bounded real-boxscore fallback.

    Only called for server-verified roster athletes after Premium entitlement
    is confirmed. ESPN's season gamelog includes each completed appearance;
    request-size and concurrency are bounded by the caller.
    """
    from premium_player_stats import load_verified_player_history

    return load_verified_player_history(player_id, name, team, SEASON)


@st.cache_data(ttl=3600, max_entries=2, show_spinner=False)
def _cached_premium_team_analytics() -> dict:
    """Use ESPN results and try bounded, official NBA Advanced on Premium demand.

    NBA Stats can reject cloud hosts. A failed request never blocks historical
    scores from being shown or fabricates possessions-based ratings.
    """
    from bestbets_simulations_canvas import _advanced_from_verified_cache, _history_for_simulations
    from premium_team_stats import build_team_analytics
    from simulation_engine import advanced_ratings
    from sources import extended_set

    games, warning = _history_for_simulations(SEASON)
    verified = _advanced_from_verified_cache(SEASON)
    if verified.empty:
        try:
            loaded, meta = extended_set("Drużyny • advanced (pace/def)", SEASON)
            if not meta.get("stale"):
                verified = loaded
        except Exception:
            # Stats.nba.com often times out from cloud hosting. Its adapter
            # already bounds the request and caches errors for 20 minutes.
            pass
    advanced = advanced_ratings(verified)
    report = build_team_analytics(games, advanced)
    if warning:
        report["notice"] = "Niektóre wyniki ESPN są tymczasowo niedostępne."
    return report



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
    # No player portraits from ESPN/NBA are licensed for HOOPZARO yet.
    # Keep this empty even for valid athlete IDs; the frontend uses its
    # original identity artwork and the separately loaded team logo.
    photo = ""
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
            /* Preserve the approved proportional stage, including its full
               height when wider screens require vertical page scrolling. */
            height:calc(100vh - 4px)!important;
            height:calc(100dvh - 4px)!important;
            /* Keep the exact full-width canvas and let the Streamlit page
               scroll vertically when that canvas is taller than the window.
               Never squeeze or crop the Players/Teams bottom panels. */
            height:max(calc(100dvh - 4px), 56.1332vw)!important;
            min-height:0!important;
        }
        /* A phone held horizontally must keep its iframe within the visible
           viewport so the fixed mobile tab bar remains reachable. */
        @media (max-width:1200px) and (max-height:500px) and (orientation:landscape){
            [data-testid="stMain"] iframe{
                height:calc(100dvh - 4px)!important;
            }
        }
        .stApp{background:#020713!important}
        </style>""", unsafe_allow_html=True
    )
    if "bb10_payload" not in st.session_state:
        st.session_state["bb10_payload"] = {"player": None, "error": ""}
    # Streamlit sessions can survive a login/logout round trip. Never send a
    # previous account's cached paid results to a different authenticated user.
    principal = current_principal()
    if st.session_state.get("bb10_premium_principal") != principal:
        # Player Props is paid output too. It must not survive logout or a
        # switch between two accounts that both happen to have Premium.
        st.session_state["bb10_payload"] = {"player": None, "error": ""}
        st.session_state.pop("bb10_premium_game", None)
        st.session_state.pop("bb10_premium_players", None)
        st.session_state.pop("bb10_premium_player_averages", None)
        st.session_state.pop("bb10_premium_team_analytics", None)
        st.session_state.pop("bb10_team_analytics_attempt_at", None)
        st.session_state.pop("bb10_player_averages_attempt_at", None)
        st.session_state.pop("bb10_admin_report", None)
        st.session_state.pop("bb10_admin_report_at", None)
        st.session_state["bb10_premium_principal"] = principal
        # A session-local counter lets the iframe discard an old search when
        # identity changes, without exposing the OIDC subject to JavaScript.
        st.session_state["bb10_identity_epoch"] = st.session_state.get("bb10_identity_epoch", 0) + 1
    # CRITICAL: preload data BEFORE mounting the v1 iframe. Production
    # sometimes discards the initial setComponentValue/home_data message,
    # leaving the dashboard spinning indefinitely. The home snapshot is
    # now supplied in the very first streamlit:render packet.
    if ("bb10_centre_data" not in st.session_state or
            (st.session_state["bb10_centre_data"] or {}).get("free_schema") != SCHEMA):
        st.session_state["bb10_centre_data"] = _safe_centre_live()
        st.session_state["bb10_centre_last_at"] = time.monotonic()
    home_data = st.session_state.get("bb10_centre_data")
    if isinstance(home_data, dict):
        home_data = {
            **home_data,
            "free_photos_enabled": photo_policy(),
            "calendar_extras": st.session_state.get("bb10_centre_extra_days", {}),
            "calendar_requested_day": st.session_state.get("bb10_centre_requested_day"),
        }
    has_premium = premium_entitled()
    is_admin = current_role() == "admin"
    if not has_premium and st.session_state["bb10_payload"].get("player") is not None:
        # Also discard paid output if an unchanged account loses entitlement.
        st.session_state["bb10_payload"] = {"player": None, "error": ""}
    payload = {
        "brand": _cached_brand(),
        "auth": {**auth_context(), "session_epoch": st.session_state.get("bb10_identity_epoch", 0)},
        "premium_checkout_url": premium_checkout_url(),
        "player": st.session_state["bb10_payload"].get("player") if has_premium else None,
        "error": st.session_state["bb10_payload"].get("error", ""),
        "home": home_data,
        "player_catalog": st.session_state.get("bb10_player_catalog"),
        # No premium averages in guest or free browser payloads.
        "premium_player_averages": (
            st.session_state.get("bb10_premium_player_averages") if has_premium else None
        ),
        # Never disclose paid team trends/ratings to guests or free accounts.
        "premium_team_analytics": (
            st.session_state.get("bb10_premium_team_analytics") if has_premium else None
        ),
        "free_details": st.session_state.get("bb10_free_leader_details"),
        # This is intentionally absent for all non-admin identities.
        "admin_report": st.session_state.get("bb10_admin_report") if is_admin else None,
        # Never serialize premium model output into a guest's iframe.
        "premium_simulation": {
            "entitled": has_premium,
            "game": st.session_state.get("bb10_premium_game") if has_premium else None,
            "players": st.session_state.get("bb10_premium_players") if has_premium else None,
        },
    }
    event = COMPONENT(payload=payload, default=None, key="bb10_reference_canvas")
    if not isinstance(event, dict):
        return
    event_id = _plain(event.get("id"))
    if not event_id or event_id == st.session_state.get("bb10_last_event"):
        return
    st.session_state["bb10_last_event"] = event_id
    if event.get("type") == "auth_login":
        if auth_configured():
            provider = login_provider()
            st.login(provider) if provider else st.login()
        return
    if event.get("type") == "auth_logout":
        if auth_configured() and bool(getattr(st.user, "is_logged_in", False)):
            st.logout()
        return
    if event.get("type") == "admin_report":
        # Never infer access from event payload or the browser's visible role.
        if current_role() != "admin":
            return
        now = time.monotonic()
        if now - st.session_state.get("bb10_admin_report_at", 0.0) < 30:
            return
        try:
            from tracker_storage import tracker_backend, read, read_players
            from admin_model_performance import build_model_report
            from player_simulation_tracker import player_model_report
            backend = tracker_backend()
            if not backend["remote"]:
                # Missing deployment configuration is not a broken model.
                # Report a structured setup state rather than a huge error
                # banner; no ephemeral SQLite data is passed off as history.
                result = {"season": SEASON, "models": [], "status": "setup_required"}
            else:
                result = build_model_report(read(season=SEASON, config=backend), season=SEASON)
                try:
                    result["player_tracking"] = player_model_report(
                        read_players(season=SEASON, config=backend), season=SEASON)
                except (ValueError, TypeError, KeyError, RuntimeError, OSError,
                        ConnectionError, TimeoutError):
                    # The new player archive may be temporarily unavailable;
                    # the existing team-model report remains fully usable.
                    result["player_tracking"] = {
                        "models": [], "error": "Nie udało się odczytać archiwum zawodników."}
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Admin model report temporarily unavailable: %s", type(exc).__name__)
            result = {"season": SEASON, "models": [], "status": "connection_issue"}
        st.session_state["bb10_admin_report"] = result
        st.session_state["bb10_admin_report_at"] = now
        st.rerun()
        return
    if event.get("type") == "premium_player_averages":
        # Authorization comes from Streamlit's verified identity, not JS.
        if not premium_entitled():
            return
        from premium_player_stats import verified_roster_targets
        targets = verified_roster_targets(
            event.get("player_ids"), st.session_state.get("bb10_player_catalog"))
        if not targets:
            return
        current = st.session_state.get("bb10_premium_player_averages") or {}
        completed = set(current.get("attempted_ids") or [])
        pending = [target for target in targets if target["id"] not in completed]
        if not pending:
            return
        # Seven at most per page, three concurrent ESPN calls. The normalized
        # gamelog cache avoids re-downloading a player's entire season.
        from concurrent.futures import ThreadPoolExecutor, as_completed
        rows = dict(current.get("rows") or {})
        id_rows = dict(current.get("id_rows") or {})
        unavailable = set(current.get("unavailable_ids") or [])
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(_cached_premium_player_history,
                                target["id"], target["name"], target["team"]): target
                for target in pending
            }
            for future in as_completed(futures):
                target = futures[future]
                try:
                    stats = future.result()
                    player_stats = (stats.get("id_rows") or {}).get(target["id"])
                    if player_stats:
                        id_rows[target["id"]] = {
                            **player_stats, "sample_source": stats.get("source", "ESPN"),
                            "partial": bool(stats.get("partial", True)),
                        }
                        rows.update(stats.get("rows") or {})
                        unavailable.discard(target["id"])
                    else:
                        unavailable.add(target["id"])
                except Exception as exc:
                    import logging
                    logging.getLogger(__name__).warning(
                        "ESPN athlete history unavailable (%s): %s",
                        target["id"], type(exc).__name__)
                    unavailable.add(target["id"])
                completed.add(target["id"])
        st.session_state["bb10_premium_player_averages"] = {
            "rows": rows, "id_rows": id_rows, "attempted_ids": sorted(completed),
            "unavailable_ids": sorted(unavailable),
            "season": "2026/27", "source": "ESPN · sezonowe historie zawodników",
            "scope": "zweryfikowane występy · kolumna MECZE (GP)",
            "partial": True,
        }
        st.rerun()
        return
    if event.get("type") == "premium_team_analytics":
        # The user-controlled browser cannot authorize or supply metrics.
        if not premium_entitled():
            return
        now = time.monotonic()
        if now - st.session_state.get("bb10_team_analytics_attempt_at", 0.0) < 60:
            return
        st.session_state["bb10_team_analytics_attempt_at"] = now
        try:
            result = _cached_premium_team_analytics()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Premium team analytics temporarily unavailable: %s", type(exc).__name__)
            result = {"teams": {}, "source": "ESPN / NBA Stats", "partial": True,
                      "error": "Zaawansowane statystyki drużyn są chwilowo niedostępne."}
        st.session_state["bb10_premium_team_analytics"] = result
        st.rerun()
        return
    if event.get("type") in ("premium_sim_game", "premium_sim_players"):
        # Entitlement is read from the *server*, never the browser event.
        if not premium_entitled():
            return
        import re
        day = _plain(event.get("date"))
        game_id = _plain(event.get("game_id"))
        model_id = _plain(event.get("model_id"))
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            return
        if not re.fullmatch(r"\d{1,30}", game_id):
            return
        if model_id not in ("legacy_v72", "research_form_v74", "research_context_v75"):
            return
        try:
            today = pd.Timestamp.now(tz="Europe/Warsaw").tz_localize(None).normalize()
            if abs((pd.Timestamp(day)-today).days) > 366:
                return
        except (ValueError, TypeError, OverflowError):
            return
        is_players = event["type"] == "premium_sim_players"
        result = simulation_for_entitled_user(
            day, game_id, players=is_players, model_id=model_id)
        key = "bb10_premium_players" if is_players else "bb10_premium_game"
        st.session_state[key] = {"date": day, "game_id": game_id,
                                 **result, "model_id": model_id}
        if not is_players:
            st.session_state.pop("bb10_premium_players", None)
        st.rerun()
        return
    if event.get("type") == "free_leader_details":
        # Only one verified leaderboard row from the trusted server snapshot
        # can trigger a boxscore read. Client-supplied athlete IDs are ignored.
        key = event.get("key")
        snapshot = st.session_state.get("bb10_centre_data") or {}
        leader = select_leader(snapshot, key)
        if leader is None:
            st.session_state["bb10_free_leader_details"] = {
                "key": key if isinstance(key, str) and len(key) == 64 else "",
                "data": None, "error": "Lista liderów została zaktualizowana. Otwórz szczegóły ponownie.",
            }
            st.rerun()
            return
        try:
            details = _cached_free_details(leader)
            st.session_state["bb10_free_leader_details"] = {
                "key": key, "data": details, "error": "",
            }
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Free boxscore unavailable: %s", type(exc).__name__)
            st.session_state["bb10_free_leader_details"] = {
                "key": key, "data": None,
                "error": "Pełne statystyki tego meczu są chwilowo niedostępne w ESPN.",
            }
        st.rerun()
        return
    if event.get("type") == "player_catalog":
        # Do not delay first-paint Centrum: fetch full 30-team player index
        # only after explicit interaction with the picker.
        last = st.session_state.get("bb10_player_catalog_at", 0.0)
        force = event.get("force") is True
        last_force = st.session_state.get("bb10_player_catalog_force_at", 0.0)
        allowed_force = force and (not last_force or time.monotonic()-last_force >= 180)
        if (allowed_force or "bb10_player_catalog" not in st.session_state
                or time.monotonic()-last >= 3600):
            try:
                st.session_state["bb10_player_catalog"] = _cached_centre_player_catalog(
                    force_refresh=allowed_force)
            except Exception:
                st.session_state["bb10_player_catalog"] = {
                    "players": [],
                    "coverage": {"missing_teams": list(TEAM_FULL)},
                    "error": "Nie udało się pobrać pełnej listy ESPN. Spróbuj ponownie.",
                }
            st.session_state["bb10_player_catalog_at"] = time.monotonic()
            if allowed_force:
                st.session_state["bb10_player_catalog_force_at"] = time.monotonic()
                st.session_state.pop("bb10_premium_player_averages", None)
        st.rerun()
        return
    if event.get("type") == "home_date":
        # Only a valid calendar date can trigger the server-side NBA query.
        # Keep the request isolated from Props, initial page and resizing.
        import re
        raw_date=_plain(event.get("date"))
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date):
            return
        try:
            chosen=pd.Timestamp(raw_date)
            today=pd.Timestamp.now(tz="Europe/Warsaw").tz_localize(None).normalize()
            if abs((chosen-today).days)>366:
                return
        except (ValueError,TypeError,OverflowError):
            return
        try:
            response=_cached_centre_day(raw_date)
        except Exception:
            response={"date":raw_date,"games":[],"error":"Nie udało się pobrać terminarza z ESPN.","complete":False}
        extras=st.session_state.setdefault("bb10_centre_extra_days",{})
        extras[raw_date]=response
        if len(extras)>24:
            del extras[next(iter(extras))]
        st.session_state["bb10_centre_requested_day"]=raw_date
        st.rerun()
        return
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
    # Player Props is a paid research tool. Keep the protection on the server;
    # browser-only hiding can be bypassed by sending a component event.
    if not premium_entitled():
        st.session_state["bb10_payload"] = {
            "player": None,
            "error": "Player Props wymaga konta Premium. Zaloguj się w Ustawieniach.",
        }
        st.rerun()
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
