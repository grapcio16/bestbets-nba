"""Verified, cache-backed ESPN injury summaries for the public Centrum card.

An unavailable or stale source must never silently become an invented report.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache


def _name_key(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(name or ""))
    return re.sub(r"[^a-z0-9]+", " ", "".join(
        c for c in normalized.casefold() if not unicodedata.combining(c)
    )).strip()


@lru_cache(maxsize=1)
def _nba_player_ids() -> dict[str, str]:
    """NBA headshot IDs from the installed, offline NBA player catalog."""
    try:
        from nba_api.stats.static.players import get_players

        players = get_players()
    except (ImportError, OSError, ValueError, TypeError):
        return {}
    # Prefer currently active players if a historical name is duplicated.
    result = {}
    for player in sorted(players, key=lambda p: not bool(p.get("is_active"))):
        key = _name_key(player.get("full_name", ""))
        identifier = str(player.get("id") or "")
        if key and identifier.isdigit() and len(identifier) <= 20:
            result.setdefault(key, identifier)
    return result


def status_badge(value: str) -> tuple[str, str, int]:
    """Return a concise label, UI tone and display priority, without guessing."""
    status = re.sub(r"\s+", " ", str(value or "").strip()).lower()
    if status in {"out", "inactive", "ruled out"}:
        return "OUT", "out", 0
    if "doubtful" in status:
        return "DBT", "question", 1
    if "game-time decision" in status or status == "gtd":
        return "GTD", "question", 2
    if "questionable" in status:
        return "QST", "question", 3
    if "day-to-day" in status or "day to day" in status or status == "dtd":
        return "DTD", "question", 4
    if "probable" in status:
        return "PROB", "probable", 5
    return "INFO", "unknown", 6


def summarize_injuries(table, meta=None, limit=600, nba_ids=None) -> dict:
    """Normalize injury rows for an untrusted HTML client; no player examples."""
    meta = meta if isinstance(meta, dict) else {}
    timestamp = str(meta.get("timestamp") or "")[:35]
    stale = bool(meta.get("stale"))
    try:
        age_minutes = float(meta.get("age_min") or 0)
    except (TypeError, ValueError):
        age_minutes = 0
    if table is None or not hasattr(table, "to_dict"):
        table = []
    else:
        table = table.to_dict(orient="records")
    nba_ids = _nba_player_ids() if nba_ids is None else nba_ids
    rows = []
    for item in table:
        if not isinstance(item, dict):
            continue
        player = str(item.get("player") or "").strip()[:90]
        status = str(item.get("status") or "").strip()[:60]
        team = str(item.get("team") or "—").strip().upper()[:4]
        if not player or not status:
            continue
        badge, tone, priority = status_badge(status)
        athlete_id = str(item.get("athlete_id") or "").strip()
        rows.append({
            "name": player, "team": team, "status": status,
            "badge": badge, "tone": tone,
            "note": str(item.get("note") or "").strip()[:125],
            "athlete_id": athlete_id if athlete_id.isdigit() and len(athlete_id) <= 20 else "",
            "nba_id": str(nba_ids.get(_name_key(player), ""))[:20],
            "_priority": priority,
        })
    # Preserve one report per player; high-impact, explicit statuses go first.
    rows.sort(key=lambda item: (item["_priority"], item["name"].casefold()))
    unique = []
    seen = set()
    for row in rows:
        key = (row["name"].casefold(), row["team"])
        if key in seen:
            continue
        seen.add(key)
        row.pop("_priority")
        unique.append(row)
        if len(unique) >= limit:
            break
    # Injury status is a time-sensitive fact. Refuse old fallback cache data.
    if stale and age_minutes > 120:
        return {"rows": [], "available": False, "stale": True,
                "as_of": timestamp, "source": "ESPN"}
    return {"rows": unique, "available": True, "stale": stale,
            "as_of": timestamp, "source": "ESPN"}


def get_centre_injury_watch() -> dict:
    """Keep lookup bounded so injury-report failure cannot block all scores."""
    from sources import ESPN_INJURIES, memoized_json, injury_rows

    try:
        payload, meta = memoized_json(
            "bb-centre-injuries-2026-27", ESPN_INJURIES,
            ttl_seconds=12 * 60, request_timeout=6,
        )
        return summarize_injuries(injury_rows(payload), meta)
    except Exception:
        return {"rows": [], "available": False, "stale": False,
                "as_of": "", "source": "ESPN"}
