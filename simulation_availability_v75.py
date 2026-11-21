"""Conservative, pregame-only player-minute and ESPN availability evidence.

This is a *research hypothesis*, not an official injury forecast. A player
missing from ESPN's injury feed is NOT deemed fit. Confirmed ESPN ``Out`` is
the only status eligible for a small team-score adjustment; doubtful / DTD /
questionable remain uncertainty markers. Historical final games never read
today's injury report, since that would leak post-game information.
"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd

from core import norm_name
from rotation_intelligence import status_class


def _number(value, low=0.0, high=1000.0):
    try:
        num = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return num if pd.notna(num) and low <= num <= high else None


def _prior_appearances(logs, home, away, tipoff):
    """Recent participation, grouped by team AND player, never by name alone."""
    appearance = {}
    needed = {"GAME_ID", "TEAM_ABBREVIATION", "PLAYER_NAME", "GAME_DATE"}
    if not isinstance(logs, pd.DataFrame) or logs.empty or not needed.issubset(logs.columns):
        return appearance
    x = logs.copy()
    x["GAME_DATE"] = pd.to_datetime(x["GAME_DATE"], utc=True, errors="coerce")
    x = x[x["TEAM_ABBREVIATION"].isin([home, away]) & (x["GAME_DATE"] < tipoff)]
    for code in (home, away):
        team = x[x["TEAM_ABBREVIATION"] == code]
        # Each distinct final game counts once; use the four most recent.
        games = (team[["GAME_ID", "GAME_DATE"]].drop_duplicates("GAME_ID")
                 .sort_values("GAME_DATE").tail(4)["GAME_ID"].astype(str).tolist())
        if len(games) < 3:
            continue
        recent = team[team["GAME_ID"].astype(str).isin(games)]
        for name, group in recent.groupby("PLAYER_NAME"):
            appearance[(code, norm_name(str(name)))] = (
                group["GAME_ID"].astype(str).nunique(), len(games))
    return appearance


def availability_evidence(player_table, injury_table, metadata, game, *,
                          logs=None, now=None, historical=False):
    """Return bounded score hypothesis and player-minute/status metadata.

    Both sources must be pre-tipoff, the injury snapshot must have been read
    within 90 minutes, and the player must have >=3 observed outings plus
    >=2 appearances in the team's recent 4 matches. No hypothetical point
    correction is made for questionable status or missing observations.
    """
    home, away = str(game["home"]), str(game["away"])
    tipoff = pd.to_datetime(game.get("start_utc"), utc=True, errors="coerce")
    current = pd.to_datetime(now, utc=True, errors="coerce") if now is not None else pd.Timestamp.now(tz="UTC")
    meta = metadata or {}
    report_time = pd.to_datetime(meta.get("timestamp"), utc=True, errors="coerce")
    recent_report = bool(
        not historical and pd.notna(tipoff) and pd.notna(report_time)
        and pd.notna(current) and current < tipoff and report_time <= current
        and (current - report_time).total_seconds() <= 90 * 60
        and not meta.get("stale") and meta.get("available")
    )

    reports = injury_table if isinstance(injury_table, pd.DataFrame) else pd.DataFrame()
    status_by_key = defaultdict(set)
    if recent_report and {"Drużyna", "Zawodnik", "Status ESPN"}.issubset(reports.columns):
        for r in reports.to_dict("records"):
            code = str(r.get("Drużyna") or "")
            name = norm_name(str(r.get("Zawodnik") or ""))
            if code in (home, away) and name:
                status_by_key[(code, name)].add(status_class(r.get("Status ESPN")))

    rows = player_table if isinstance(player_table, pd.DataFrame) else pd.DataFrame()
    participation = _prior_appearances(logs, home, away, tipoff)
    player_context = {}
    changes = {home: 0.0, away: 0.0}
    counted_out = {home: 0, away: 0}
    uncertain = {home: 0, away: 0}
    covered = {home: 0, away: 0}
    if {"Zawodnik", "Drużyna", "Minuty", "Próba występów", "PTS"}.issubset(rows.columns):
        for r in rows.to_dict("records"):
            code, name = str(r.get("Drużyna") or ""), str(r.get("Zawodnik") or "")
            if code not in (home, away) or not name:
                continue
            key = (code, norm_name(name))
            statuses = status_by_key.get(key, set())
            status = next(iter(statuses)) if len(statuses) == 1 else (
                "Sprzeczne" if statuses else "Niezweryfikowany")
            minutes = _number(r.get("Minuty"), 5, 44)
            points = _number(r.get("PTS"), 0, 60)
            sample = _number(r.get("Próba występów"), 0, 100)
            minutes = round(minutes, 1) if minutes is not None and sample is not None and sample >= 3 else None
            if minutes is not None:
                covered[code] += 1
            player_context[key] = {
                "status": status, "minutes": minutes,
                "normal_minutes": minutes, "sample": int(sample) if sample is not None else 0,
            }
            # A fresh ESPN OUT report rules out the player's listed baseline
            # minutes, even if this specific athlete has no score correction.
            if status == "Out":
                player_context[key]["minutes"] = 0.0
            if status in ("Questionable", "Doubtful", "Day-to-day"):
                uncertain[code] += 1
            if status != "Out" or minutes is None or minutes < 12 or points is None:
                continue
            outings, team_games = participation.get(key, (0, 0))
            # A recent absence is already partly represented in the team score
            # baseline. Never deduct the player's whole per-game production.
            if outings < 2 or team_games < 3:
                continue
            exposure = outings / team_games
            changes[code] -= 0.10 * points * exposure
            counted_out[code] += 1
    changes = {code: round(max(-3.5, delta), 2) for code, delta in changes.items()}
    return {
        "score_delta": {"home": changes[home], "away": changes[away]},
        "players": player_context,
        "report_fresh": recent_report,
        # Browser must re-check expiry: a cached response can cross the 90m
        # report freshness boundary without fetching again.
        "report_valid_until": (
            (report_time + pd.Timedelta(minutes=90)).isoformat()
            if recent_report else None),
        "out_count": {"home": counted_out[home], "away": counted_out[away]},
        "uncertain_count": {"home": uncertain[home], "away": uncertain[away]},
        "minute_coverage": {"home": covered[home], "away": covered[away]},
        "warning": ("Raport ESPN jest nieoficjalny. Korekta absencji to "
                    "niekalibrowana hipoteza; nie zastępuje potwierdzonego składu."
                    if recent_report else
                    "Brak aktualnego raportu ESPN sprzed meczu — bez korekty absencji."),
    }
