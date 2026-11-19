"""Prospective, pregame-only audit of the existing 5,000-draw player simulator.

No player result is backfilled as a forecast. A forecast is stored only while
the matchup is upcoming; actual boxscores are attached separately after final.
Missing/DNP boxscore rows remain ungraded, never counted as zero production.
"""
from __future__ import annotations

import pandas as pd

MODEL_ID = "auto_player_form_v74"
MARKETS = {
    "pts": ("pts_pred", "pts_actual", 5.0),
    "reb": ("reb_pred", "reb_actual", 2.0),
    "ast": ("ast_pred", "ast_actual", 2.0),
    "fg3m": ("fg3m_pred", "fg3m_actual", 1.0),
    "pra": ("pra_pred", "pra_actual", 7.0),
    "minutes": ("minutes_pred", "minutes_actual", 5.0),
}


def _valid_float(value, maximum):
    try:
        result = float(value)
        return round(result, 2) if pd.notna(result) and 0 <= result <= maximum else None
    except (TypeError, ValueError, OverflowError):
        return None


def build_player_forecasts(upcoming, completed, now, *, fetch_logs=None):
    """Reproduce the ESPN-only V7.4 player simulation, without changing it.

    The public UI may additionally have NBA Advanced data cached. This
    automatic, separately labeled sample therefore measures the ESPN-only
    research path, not an invented equivalent of the visitor's exact inputs.
    """
    from core import norm_name, normalize_logs
    from espn_player_data import matchup_espn_logs
    from simulation_data_audit import verified_history
    from simulation_engine import (completed_team_scores, eligible_roster,
                                   matchup_means, simulate_game)
    from tracker_pregame_availability import near_tipoff

    clock = pd.to_datetime(now, utc=True, errors="coerce")
    if pd.isna(clock):
        raise ValueError("Niepoprawny czas archiwizacji zawodników")
    history = verified_history(completed, clock)
    scored = completed_team_scores(history)
    reader = fetch_logs or matchup_espn_logs
    rows = []
    attempted = covered = 0
    if upcoming is None or upcoming.empty:
        return rows, {"attempted_games": 0, "projected_games": 0}
    for event in upcoming.to_dict("records"):
        game = {"game_id": str(event.get("game_id") or ""),
                "start_utc": event.get("start_utc"),
                "home": str(event.get("home") or ""),
                "away": str(event.get("away") or "")}
        if (str(event.get("status_code")) not in ("1", "1.0") or
                not game["game_id"].isdigit() or
                not near_tipoff(game, clock)):
            continue
        attempted += 1
        try:
            raw, source = reader(history, game, games_per_team=7)
            if raw is None or raw.empty:
                continue
            logs = normalize_logs(raw)
            dates = pd.to_datetime(logs["GAME_DATE"], utc=True, errors="coerce")
            logs = logs[(dates < clock) & (dates < pd.to_datetime(game["start_utc"], utc=True))].copy()
            if logs.empty:
                continue
            if any(logs.loc[logs["TEAM_ABBREVIATION"] == code, "GAME_ID"].nunique() < 4
                   for code in (game["home"], game["away"])):
                continue
            mean = matchup_means(game["home"], game["away"], {}, scored)
            if mean is None:
                continue
            rosters = [eligible_roster(logs, code, opponent, asof=game["start_utc"])
                       for code, opponent in ((game["home"], game["away"]),
                                              (game["away"], game["home"]))]
            if any(roster.empty for roster in rosters):
                continue
            _, projections, _, _ = simulate_game(game, mean, rosters[0], rosters[1])
            if projections.empty:
                continue
            # ESPN athlete IDs, not names, identify a player across settlement.
            identities = {}
            for row in logs.to_dict("records"):
                key = (str(row["TEAM_ABBREVIATION"]), norm_name(str(row["PLAYER_NAME"])))
                identities.setdefault(key, set()).add(str(row.get("PLAYER_ID") or ""))
            selected = []
            for player in projections.to_dict("records"):
                team = str(player.get("Drużyna") or "")
                name = str(player.get("Zawodnik") or "")
                ids = identities.get((team, norm_name(name)), set())
                if len(ids) != 1:
                    continue
                athlete_id = next(iter(ids))
                if not athlete_id.isdigit() or len(athlete_id) > 20:
                    continue
                sample = int(player.get("Próba występów") or 0)
                predicted = {"pts_pred": _valid_float(player.get("PTS"), 80),
                             "reb_pred": _valid_float(player.get("REB"), 35),
                             "ast_pred": _valid_float(player.get("AST"), 30),
                             "fg3m_pred": _valid_float(player.get("3PM"), 15),
                             "minutes_pred": _valid_float(player.get("Minuty"), 50)}
                if sample < 3 or any(v is None for v in predicted.values()):
                    continue
                selected.append({
                    "game_id": game["game_id"], "start_utc": game["start_utc"],
                    "model_id": MODEL_ID, "player_id": athlete_id,
                    "player_name": name[:100], "team": team,
                    "sample_games": sample,
                    "source": "ESPN · 5,000 symulacji · V7.4 (bez NBA Advanced)",
                    **predicted,
                })
            if selected:
                covered += 1
                rows.extend(selected)
        except (ValueError, KeyError, TypeError, RuntimeError, OSError,
                ConnectionError, TimeoutError):
            # Missing ESPN evidence must never create synthetic player rows.
            continue
    return rows, {"attempted_games": attempted, "projected_games": covered}


def player_model_report(frame, *, season, game_forecasts=None):
    """MAE, signed bias and clearly defined tolerance on actual played games.

    These are NOT bookmaker line hit rates, betting returns, or calibrated
    player prop probabilities. Each row represents one player in one game.
    """
    result = {"season": season, "models": []}
    required = {"game_id", "player_id", "model_id", "player_name", "team",
                "forecast_time_utc", "start_utc"}
    if frame is None or frame.empty:
        return result
    if not required.issubset(frame.columns):
        return {**result, "error": "Archiwum zawodników ma niepełny schemat."}
    source = frame.copy()
    source["forecast_time_utc"] = pd.to_datetime(source["forecast_time_utc"], utc=True, errors="coerce")
    source["start_utc"] = pd.to_datetime(source["start_utc"], utc=True, errors="coerce")
    source = source[(source["forecast_time_utc"] < source["start_utc"]) &
                    source["forecast_time_utc"].notna()].copy()
    # PRA is an exact sum of three independently frozen components; do not
    # create a historical bookmaker line or count missing stats as zero.
    for suffix in ("pred", "actual"):
        columns = [f"{market}_{suffix}" for market in ("pts", "reb", "ast")]
        if all(column in source for column in columns):
            numeric = source[columns].apply(pd.to_numeric, errors="coerce")
            source[f"pra_{suffix}"] = numeric.sum(axis=1, min_count=3)
        else:
            source[f"pra_{suffix}"] = float("nan")

    opponents = {}
    if (isinstance(game_forecasts, pd.DataFrame) and
            {"game_id", "home", "away"}.issubset(game_forecasts.columns)):
        for row in game_forecasts[["game_id", "home", "away"]].drop_duplicates("game_id").to_dict("records"):
            opponents[str(row["game_id"])] = (str(row["home"]), str(row["away"]))
    for model_id, group in source.groupby("model_id"):
        metrics = {}
        for market, (pred, actual, tolerance) in MARKETS.items():
            if pred not in group or actual not in group:
                metrics[market] = {"n": 0, "mae": None, "bias": None,
                                   "within_pct": None, "tolerance": tolerance}
                continue
            p = pd.to_numeric(group[pred], errors="coerce")
            a = pd.to_numeric(group[actual], errors="coerce")
            valid = p.notna() & a.notna() & p.between(0, 100) & a.between(0, 100)
            diff = (a[valid] - p[valid])
            metrics[market] = {
                "n": int(len(diff)),
                "mae": round(float(diff.abs().mean()), 2) if len(diff) else None,
                "bias": round(float(diff.mean()), 2) if len(diff) else None,
                "within_pct": round(float(diff.abs().le(tolerance).mean()), 4) if len(diff) else None,
                "tolerance": tolerance,
            }
        evaluated = pd.to_numeric(
            group.get("pts_actual", pd.Series(index=group.index, dtype=float)),
            errors="coerce").notna()
        recent = []
        for row in group.sort_values("start_utc", ascending=False).head(150).to_dict("records"):
            fixture = opponents.get(str(row["game_id"]), ("", ""))
            team = str(row["team"])
            sample = pd.to_numeric(row.get("sample_games"), errors="coerce")
            opponent = fixture[1] if team == fixture[0] else (
                fixture[0] if team == fixture[1] else "")
            recent.append({
                "game_id": str(row["game_id"])[:25],
                "date": row["start_utc"].strftime("%Y-%m-%d %H:%M"),
                "player": str(row["player_name"])[:100],
                "team": team[:4], "opponent": opponent[:4],
                "sample_games": int(sample) if pd.notna(sample) else 0,
                "pred": {market: _valid_float(row.get(fields[0]), 200)
                         for market, fields in MARKETS.items()},
                "actual": {market: _valid_float(row.get(fields[1]), 200)
                           for market, fields in MARKETS.items()},
            })
        result["models"].append({
            "id": str(model_id), "saved": int(len(group)),
            "evaluated_players": int(evaluated.sum()),
            "games_with_results": int(group.loc[evaluated, "game_id"].nunique()),
            "metrics": metrics,
            "recent": recent,
        })
    return result
