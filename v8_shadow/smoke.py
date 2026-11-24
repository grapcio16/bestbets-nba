"""One-game, read-only V8 source smoke; NO DB write and no model output."""
from __future__ import annotations
import json
from v8_shadow.data import fetch_espn_summary

SAMPLE = {
    "game_id": "401910038", "season": "2026-27",
    "start_utc": "2026-11-24T00:30:00Z",
    "away": "OKC", "home": "IND", "away_score": 120,
    "home_score": 125, "status_code": 3,
}


if __name__ == "__main__":
    try:
        row = fetch_espn_summary(SAMPLE)
        print(json.dumps({
            "status": "validated_officially_reported_game",
            "provider": "ESPN boxscore",
            "game_id": row["game_id"],
            "observed_home_poss_estimate": row["home_poss"],
            "observed_away_poss_estimate": row["away_poss"],
            "validated_teams": [row["away"], row["home"]],
            "no_user_facing_forecast": True
        }, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({
            "status": "not_verified", "error_type": type(exc).__name__,
            "error": str(exc)[:180], "source": "ESPN boxscore",
            "safety": "no invented possessions and no forecasts"
        }))
        raise SystemExit(2)
