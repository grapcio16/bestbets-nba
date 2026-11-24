"""V8-only append-only Neon tables; absolutely no V7 tracker mutations."""
from __future__ import annotations
import json

import pandas as pd

DDL = """
CREATE TABLE IF NOT EXISTS hoopzaro_v8_boxscores (
 game_id TEXT PRIMARY KEY, season TEXT NOT NULL, start_utc TIMESTAMPTZ NOT NULL,
 away TEXT NOT NULL, home TEXT NOT NULL, away_score INTEGER NOT NULL,
 home_score INTEGER NOT NULL, away_poss DOUBLE PRECISION NOT NULL,
 home_poss DOUBLE PRECISION NOT NULL, away_fga INTEGER NOT NULL,
 home_fga INTEGER NOT NULL, away_fta INTEGER NOT NULL, home_fta INTEGER NOT NULL,
 away_oreb INTEGER NOT NULL, home_oreb INTEGER NOT NULL,
 away_tov INTEGER NOT NULL, home_tov INTEGER NOT NULL,
 source TEXT NOT NULL, collected_utc TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS hz_v8_boxscores_by_date
 ON hoopzaro_v8_boxscores(start_utc);
CREATE TABLE IF NOT EXISTS hoopzaro_v8_ingest_failures (
 game_id TEXT PRIMARY KEY, season TEXT NOT NULL, reason TEXT NOT NULL,
 last_attempt TIMESTAMPTZ NOT NULL DEFAULT now(),
 attempts INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS hoopzaro_v8_shadow_forecasts (
 game_id TEXT NOT NULL,
 model_id TEXT NOT NULL,
 season TEXT NOT NULL,
 issued_at TIMESTAMPTZ NOT NULL,
 start_utc TIMESTAMPTZ NOT NULL,
 away TEXT NOT NULL, home TEXT NOT NULL,
 scenario_away INTEGER NOT NULL, scenario_home INTEGER NOT NULL,
 mean_away DOUBLE PRECISION NOT NULL, mean_home DOUBLE PRECISION NOT NULL,
 away_win_pct DOUBLE PRECISION NOT NULL, home_win_pct DOUBLE PRECISION NOT NULL,
 training_examples INTEGER NOT NULL,
 report JSONB NOT NULL,
 actual_away INTEGER, actual_home INTEGER,
 settled_at TIMESTAMPTZ,
 PRIMARY KEY(game_id, model_id),
 CHECK(issued_at < start_utc - interval '15 minutes')
);
CREATE INDEX IF NOT EXISTS hz_v8_forecast_start
 ON hoopzaro_v8_shadow_forecasts(start_utc);
"""


def _connect(url):
    import psycopg
    if not url:
        raise ValueError("TRACKER_DATABASE_URL required; no ephemeral shadow data")
    return psycopg.connect(url, autocommit=False)


def initialize(url):
    with _connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)


def ids(url, season):
    with _connect(url) as conn:
        with conn.cursor() as cur:
            # An invalid/OT boxscore must not occupy the same top-24
            # collector slots every 4 hours. Retry after a cooling period.
            cur.execute(
                """SELECT game_id FROM hoopzaro_v8_boxscores WHERE season=%s
                   UNION SELECT game_id FROM hoopzaro_v8_ingest_failures
                   WHERE season=%s AND last_attempt > now()-interval '12 hours'""",
                (season, season))
            return {str(row[0]) for row in cur.fetchall()}


COLUMNS = ("game_id", "season", "start_utc", "away", "home",
           "away_score", "home_score", "away_poss", "home_poss",
           "away_fga", "home_fga", "away_fta", "home_fta",
           "away_oreb", "home_oreb", "away_tov", "home_tov", "source")


def record_ingest_failures(url, season, errors):
    """Retriable rejection metadata, no raw restricted ESPN payload stored."""
    with _connect(url) as conn:
        with conn.cursor() as cur:
            for error in errors:
                code = str(error.get("game_id") or "")
                reason = str(error.get("error_type") or "Unknown")[:80]
                if not code.isdigit() or len(code) > 20:
                    continue
                cur.execute(
                    """INSERT INTO hoopzaro_v8_ingest_failures
                       (game_id,season,reason) VALUES (%s,%s,%s)
                       ON CONFLICT(game_id) DO UPDATE SET
                        season=EXCLUDED.season,
                        reason=EXCLUDED.reason,
                        last_attempt=now(),
                        attempts=hoopzaro_v8_ingest_failures.attempts+1""",
                    (code, season, reason))


def store_boxes(url, rows):
    accepted = 0
    with _connect(url) as conn:
        with conn.cursor() as cur:
            for row in rows:
                values = tuple(row[k] for k in COLUMNS)
                cur.execute(
                    "INSERT INTO hoopzaro_v8_boxscores (" + ",".join(COLUMNS) + ") "
                    "VALUES (" + ",".join(["%s"] * len(COLUMNS)) + ") "
                    "ON CONFLICT(game_id) DO NOTHING", values)
                accepted += cur.rowcount
    return accepted


def read_boxes(url, season):
    with _connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT " + ",".join(COLUMNS) +
                        " FROM hoopzaro_v8_boxscores WHERE season=%s "
                        "ORDER BY start_utc, game_id", (season,))
            result = cur.fetchall()
    return [dict(zip(COLUMNS, row)) for row in result]


def save_forecasts(url, results, season):
    added = 0
    with _connect(url) as conn:
        with conn.cursor() as cur:
            for row in results:
                if row.get("status") != "shadow_only":
                    continue
                start = pd.to_datetime(row["start_utc"], utc=True, errors="raise")
                issued = pd.to_datetime(row["forecast_time_utc"], utc=True, errors="raise")
                if start - issued <= pd.Timedelta(minutes=15):
                    raise ValueError("attempt to archive post-cutoff V8 forecast")
                params = (
                    row["game_id"], row["model_id"], season, issued.to_pydatetime(),
                    start.to_pydatetime(), row["away"], row["home"],
                    row["scenario_away"], row["scenario_home"],
                    row["mean_away"], row["mean_home"],
                    row["away_win_probability_pct"], row["home_win_probability_pct"],
                    row["training_examples"], json.dumps(row, ensure_ascii=False)
                )
                cur.execute(
                    """INSERT INTO hoopzaro_v8_shadow_forecasts (
                     game_id,model_id,season,issued_at,start_utc,away,home,
                     scenario_away,scenario_home,mean_away,mean_home,away_win_pct,
                     home_win_pct,training_examples,report)
                     VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                     ON CONFLICT (game_id,model_id) DO NOTHING""",
                    params)
                added += cur.rowcount
    return added


def settle_forecasts(url, final_games):
    """Only verified final scores, no retrospective backfilling of forecasts."""
    checked, settled = 0, 0
    with _connect(url) as conn:
        with conn.cursor() as cur:
            for item in final_games:
                if int(item.get("status_code") or 0) != 3:
                    continue
                try:
                    actual_away = int(item["away_score"])
                    actual_home = int(item["home_score"])
                except (ValueError, TypeError, KeyError):
                    continue
                if not (50 <= actual_away <= 200 and 50 <= actual_home <= 200):
                    continue
                checked += 1
                cur.execute(
                    """UPDATE hoopzaro_v8_shadow_forecasts
                       SET actual_away=%s,actual_home=%s,settled_at=now()
                       WHERE game_id=%s AND actual_away IS NULL
                         AND actual_home IS NULL AND start_utc<now()""",
                    (actual_away, actual_home, str(item["game_id"])))
                settled += cur.rowcount
    return {"finals_seen": checked, "newly_settled": settled}
