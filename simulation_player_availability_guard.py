"""Strict pregame injury availability gate for the Premium Player Simulations UI.

Independent of V7.2/V7.4/V7.5. ESPN's injury feed is not an official NBA
starting-lineup confirmation. Unknown status never means confirmed available.
For future matches, no projection is shown without a fresh injury report.
"""
from __future__ import annotations

import pandas as pd

from core import norm_name
from rotation_intelligence import status_class

# If a player's appearance is doubtful, conditional or contradicted, do not
# provide a numerical prediction that resembles a confirmed active appearance.
NON_PLAYING_OR_UNCERTAIN = frozenset({
    "Out", "Doubtful", "Questionable", "Day-to-day",
    "Sprzeczne", "Inny / niepotwierdzony",
})


def report_is_current(watch: dict | None, now=None) -> bool:
    """True only if a successful explicitly time-bounded ESPN read remains valid."""
    if not isinstance(watch, dict) or watch.get("fresh") is not True:
        return False
    moment = (pd.to_datetime(now, utc=True, errors="coerce") if now is not None
              else pd.Timestamp.now(tz="UTC"))
    until = pd.to_datetime(watch.get("valid_until"), utc=True, errors="coerce")
    checked = pd.to_datetime(watch.get("checked_at"), utc=True, errors="coerce")
    return bool(pd.notna(moment) and pd.notna(until) and pd.notna(checked)
                and checked <= moment < until
                and (until - checked) <= pd.Timedelta(minutes=90))


def _id(value) -> str:
    value = str(value or "").strip()
    return value if value.isdigit() and len(value) <= 20 else ""


def injury_status(name: str, team: str, espn_id: str, watch: dict,
                  roster_status: str = "") -> str:
    """Match only a verified same-team ESPN name or unique player ID.

    A direct inactive/out roster designation or a fresh OUT injury designation
    takes precedence over any missing, ambiguous or optimistic status.
    Inconsistent distinct statuses are never treated as available.
    """
    if status_class(roster_status) == "Out":
        return "Out"
    if not report_is_current(watch):
        return "Niezweryfikowany"
    key = norm_name(str(name or ""))
    team = str(team or "").strip().upper()
    ident = _id(espn_id)
    statuses = set()
    for item in watch.get("rows", []):
        if not isinstance(item, dict) or str(item.get("team") or "").upper() != team:
            continue
        item_id = _id(item.get("espn_id"))
        same_athlete = (bool(ident and item_id and ident == item_id)
                        or bool(key and norm_name(str(item.get("name") or "")) == key))
        if not same_athlete:
            continue
        label = str(item.get("status") or "").strip()
        statuses.add(label if label in {
            "Out", "Questionable", "Doubtful", "Day-to-day", "Probable",
            "Sprzeczne", "Inny / niepotwierdzony", "Brak potwierdzenia"
        } else status_class(label))
    if "Out" in statuses:
        return "Out"
    if "Sprzeczne" in statuses or len(statuses) > 1:
        return "Sprzeczne"
    return next(iter(statuses)) if statuses else "Niezweryfikowany"


def should_suppress_forecast(status: str) -> bool:
    return status in NON_PLAYING_OR_UNCERTAIN


def suppress_player_forecasts(players: list[dict], watch: dict | None,
                              *, future: bool) -> tuple[list[dict], list[dict]]:
    """Return safe projections and excluded identities without changing math.

    Finished matches retain their historical output and must not receive
    *current* injury decisions retrospectively. If the feed is unavailable
    before a future game, hold all upcoming player predictions.
    """
    if not future:
        return players, []
    if not report_is_current(watch):
        return [], [{"name": p.get("name", ""), "team": p.get("team", ""),
                     "status": "Brak aktualnego raportu"} for p in players]
    visible, excluded = [], []
    for player in players:
        status = str(player.get("availability") or "Niezweryfikowany")
        if should_suppress_forecast(status):
            excluded.append({"name": player.get("name", ""),
                             "team": player.get("team", ""), "status": status})
        else:
            visible.append(player)
    return visible, excluded
