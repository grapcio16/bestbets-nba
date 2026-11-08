"""BestBets v7.4: append-only pregame forecast snapshots and verified settlement.

Local SQLite is a convenience, not durable cloud storage on Streamlit Community
Cloud. Export CSV regularly; without external storage the DB may be lost after
restart/redeploy. A captured prediction is never overwritten or backfilled.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pandas as pd

REQUIRED = ("game_id", "home", "away", "start_utc", "home_points",
            "away_points", "home_win_pct", "away_win_pct", "total_points")

COLUMNS = ["game_id", "season", "forecast_time_utc", "start_utc", "away",
           "home", "away_points", "home_points", "away_win_pct",
           "home_win_pct", "total_points", "source", "warning",
           "away_score", "home_score", "settled_at_utc", "model_id"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS forecasts (
    game_id TEXT PRIMARY KEY,
    season TEXT NOT NULL,
    forecast_time_utc TEXT NOT NULL,
    start_utc TEXT NOT NULL,
    away TEXT NOT NULL,
    home TEXT NOT NULL,
    away_points REAL NOT NULL,
    home_points REAL NOT NULL,
    away_win_pct REAL NOT NULL,
    home_win_pct REAL NOT NULL,
    total_points REAL NOT NULL,
    source TEXT NOT NULL,
    warning TEXT NOT NULL DEFAULT '',
    away_score INTEGER,
    home_score INTEGER,
    settled_at_utc TEXT,
    model_id TEXT NOT NULL DEFAULT 'legacy_v72'
);
CREATE INDEX IF NOT EXISTS forecasts_start ON forecasts(start_utc);
"""
# v1 was keyed on game_id only, losing the second model's frozen forecast.
# Keep v1 as a read-only migration source; new writes use (game_id, model_id).
MODEL_SCHEMA = """
CREATE TABLE IF NOT EXISTS forecasts_by_model (
    game_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    season TEXT NOT NULL,
    forecast_time_utc TEXT NOT NULL,
    start_utc TEXT NOT NULL,
    away TEXT NOT NULL,
    home TEXT NOT NULL,
    away_points REAL NOT NULL,
    home_points REAL NOT NULL,
    away_win_pct REAL NOT NULL,
    home_win_pct REAL NOT NULL,
    total_points REAL NOT NULL,
    source TEXT NOT NULL,
    warning TEXT NOT NULL DEFAULT '',
    away_score INTEGER,
    home_score INTEGER,
    settled_at_utc TEXT,
    PRIMARY KEY (game_id,model_id)
);
CREATE INDEX IF NOT EXISTS forecast_models_start ON forecasts_by_model(start_utc);
"""


def utc_timestamp(value):
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        raise ValueError("Niepoprawna data UTC")
    return ts


def db_connect(db_path):
    location = Path(db_path)
    location.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(location), timeout=12)
    conn.execute("PRAGMA busy_timeout=12000")
    conn.executescript(SCHEMA)
    if 'model_id' not in {row[1] for row in conn.execute('PRAGMA table_info(forecasts)')}:
        conn.execute("ALTER TABLE forecasts ADD COLUMN model_id TEXT NOT NULL DEFAULT 'legacy_v72'")
        conn.commit()
    conn.executescript(MODEL_SCHEMA)
    conn.execute("""
        INSERT OR IGNORE INTO forecasts_by_model
        (game_id,model_id,season,forecast_time_utc,start_utc,away,home,
        away_points,home_points,away_win_pct,home_win_pct,total_points,
        source,warning,away_score,home_score,settled_at_utc)
        SELECT game_id,COALESCE(model_id,'legacy_v72'),season,
        forecast_time_utc,start_utc,away,home,away_points,home_points,
        away_win_pct,home_win_pct,total_points,source,warning,
        away_score,home_score,settled_at_utc FROM forecasts
    """)
    conn.commit()
    return conn


def store_forecasts(db_path, season: str, summaries, captured_at=None):
    """Freeze each (event, model) ONCE, only strictly before tipoff.

    No replacement on reruns. False/invalid probabilities and game identifiers
    are rejected. All SQL is parameterized.
    """
    captured = utc_timestamp(captured_at if captured_at is not None
                             else datetime.now(timezone.utc))
    saved = 0
    ignored = 0
    with closing(db_connect(db_path)) as conn:
        for g in summaries:
            try:
                if any(key not in g for key in REQUIRED):
                    ignored += 1
                    continue
                event_id = str(g["game_id"]).strip()
                start = utc_timestamp(g["start_utc"])
                hp = float(g["home_win_pct"])
                ap = float(g["away_win_pct"])
                hpts, apts = float(g["home_points"]), float(g["away_points"])
                total = float(g["total_points"])
                if (not event_id or not event_id.isdecimal() or len(event_id)>20
                    or start <= captured or
                    not 0 <= hp <= 100 or not 0 <= ap <= 100 or
                    abs(hp+ap-100) > 0.2 or
                    not 60 < hpts < 180 or not 60 < apts < 180 or
                    not 120 < total < 360 or
                    abs(total-(hpts+apts))>0.25):
                    ignored += 1
                    continue
                cur = conn.execute(
                    """INSERT OR IGNORE INTO forecasts_by_model
                    (game_id,season,forecast_time_utc,start_utc,away,home,
                     away_points,home_points,away_win_pct,home_win_pct,
                     total_points,source,warning,model_id)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (event_id,str(season),captured.isoformat(),start.isoformat(),
                     str(g["away"]),str(g["home"]),apts,hpts,ap,hp,total,
                     str(g.get("source") or "nieznane"),
                     str(g.get("warning") or "")[:500],
                     str(g.get("model_id") or "legacy_v72")[:40]))
                saved += cur.rowcount
            except (ValueError, TypeError, KeyError, OverflowError):
                ignored += 1
                continue
        conn.commit()
    return {"saved":saved,"duplicates_or_rejected":len(summaries)-saved,
            "invalid_or_past":ignored}


def settle_forecasts(db_path, completed_games, settled_at=None):
    """Apply only completed NBA scores, once. Never revise a settled game."""
    if completed_games is None or completed_games.empty:
        return 0
    now=utc_timestamp(settled_at if settled_at is not None
                      else datetime.now(timezone.utc))
    count=0
    with closing(db_connect(db_path)) as conn:
        for g in completed_games.to_dict("records"):
            try:
                if int(g.get("status_code") or 0)!=3:
                    continue
                gid=str(g.get("game_id") or "")
                a,b=int(g["away_score"]),int(g["home_score"])
                if not gid.isdecimal() or min(a,b)<55 or max(a,b)>200 or a==b:
                    continue
                cur=conn.execute(
                    """UPDATE forecasts_by_model SET away_score=?,home_score=?,
                    settled_at_utc=? WHERE game_id=? AND away_score IS NULL
                    AND home_score IS NULL AND forecast_time_utc<start_utc
                    AND start_utc<=?""",
                    (a,b,now.isoformat(),gid,now.isoformat()))
                count+=cur.rowcount
            except (ValueError, TypeError, KeyError):
                continue
        conn.commit()
    return count


def read_forecasts(db_path, season=None):
    with closing(db_connect(db_path)) as conn:
        if season:
            df=pd.read_sql_query(
                "SELECT * FROM forecasts_by_model WHERE season=? ORDER BY start_utc DESC",
                conn,params=(str(season),))
        else:
            df=pd.read_sql_query(
                "SELECT * FROM forecasts_by_model ORDER BY start_utc DESC",conn)
    return df.reindex(columns=COLUMNS)


def performance_metrics(df):
    """Descriptive, post-game only. Uses existing no-lookahead audit engine."""
    from forecast_audit import evaluate_frozen_predictions
    if df is None or df.empty:
        return pd.DataFrame(), {"games":0,"winner_accuracy":None,
                                "total_mae":None,"team_mae":None,
                                "total_bias":None,"brier":None}
    ready=df[df["home_score"].notna() & df["away_score"].notna()].copy()
    if ready.empty:
        return evaluate_frozen_predictions(
            pd.DataFrame(columns=["game_id","forecast_time_utc","start_utc",
                                  "away_points","home_points",
                                  "away_win_pct","home_win_pct"]),
            pd.DataFrame(columns=["game_id","away_score","home_score"]))
    forecasts=ready[["game_id","forecast_time_utc","start_utc","away_points",
                     "home_points","away_win_pct","home_win_pct"]]
    results=ready[["game_id","away_score","home_score"]]
    return evaluate_frozen_predictions(forecasts,results)


def audit_summary(df):
    """Flag risky forecast evidence; not a betting performance estimate."""
    if df is None or df.empty:
        return {"games":0,"missing_samples":0,"suspicious_win_probs":0,
                "recent_history_only":0}
    return {
        "games":len(df),
        "missing_samples":int(df["source"].astype(str).str.contains("nieznane",case=False).sum()),
        "suspicious_win_probs":int((pd.to_numeric(df["home_win_pct"],errors="coerce")
                                      .sub(50).abs()>35).sum()),
        "recent_history_only":int(df["source"].astype(str)
                                      .str.contains("metoda zastępcza").sum()),
    }
