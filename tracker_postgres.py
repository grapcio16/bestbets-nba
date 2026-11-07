"""Optional persistent PostgreSQL backend for BestBets pregame forecasts.

Configure TRACKER_DATABASE_URL via Streamlit Secrets, never GitHub. Without it
BestBets stays on temporary SQLite; no automatic migration or invented history.
Parameter-bound SQL, append-only forecasts, finalized games settled once.
"""
from __future__ import annotations

from datetime import datetime, timezone
import pandas as pd

from performance_tracker import COLUMNS, utc_timestamp

POSTGRES_DDL = """
CREATE TABLE IF NOT EXISTS bestbets_forecasts (
 game_id TEXT PRIMARY KEY,
 season TEXT NOT NULL,
 forecast_time_utc TIMESTAMPTZ NOT NULL,
 start_utc TIMESTAMPTZ NOT NULL,
 away TEXT NOT NULL,
 home TEXT NOT NULL,
 away_points DOUBLE PRECISION NOT NULL,
 home_points DOUBLE PRECISION NOT NULL,
 away_win_pct DOUBLE PRECISION NOT NULL,
 home_win_pct DOUBLE PRECISION NOT NULL,
 total_points DOUBLE PRECISION NOT NULL,
 source TEXT NOT NULL,
 warning TEXT NOT NULL DEFAULT '',
 away_score INTEGER,
 home_score INTEGER,
 settled_at_utc TIMESTAMPTZ,
 model_id TEXT NOT NULL DEFAULT 'legacy_v72'
);
CREATE INDEX IF NOT EXISTS bestbets_forecasts_start
 ON bestbets_forecasts(start_utc);
"""


def connect(url):
    if not url or not str(url).startswith(("postgresql://","postgres://")):
        raise ValueError("TRACKER_DATABASE_URL musi wskazywać PostgreSQL")
    import psycopg  # imported ONLY when remote DB configured
    conn=psycopg.connect(str(url),connect_timeout=8)
    # Do not log URLs or messages that could expose credentials.
    return conn


def init_remote(conn):
    for statement in POSTGRES_DDL.split(";"):
        if statement.strip():
            conn.execute(statement)
    conn.commit()


def remote_store(url,season,summaries,captured_at=None):
    stamp=utc_timestamp(captured_at if captured_at is not None
                        else datetime.now(timezone.utc))
    stored=0
    invalid=0
    with connect(url) as conn:
        init_remote(conn)
        for s in summaries:
            try:
                gid=str(s["game_id"]).strip()
                start=utc_timestamp(s["start_utc"])
                h,a=float(s["home_points"]),float(s["away_points"])
                ph,pa=float(s["home_win_pct"]),float(s["away_win_pct"])
                total=float(s["total_points"])
                if (not gid.isdecimal() or len(gid)>20 or start<=stamp or
                    not 60<h<180 or not 60<a<180 or not 120<total<360 or
                    abs(h+a-total)>.25 or not 0<=ph<=100 or
                    not 0<=pa<=100 or abs(ph+pa-100)>.2):
                    invalid+=1
                    continue
                cursor=conn.execute(
                    """INSERT INTO bestbets_forecasts
                    (game_id,season,forecast_time_utc,start_utc,away,home,
                    away_points,home_points,away_win_pct,home_win_pct,total_points,
                    source,warning,model_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (game_id) DO NOTHING""",
                    (gid,str(season),stamp.to_pydatetime(),start.to_pydatetime(),
                     str(s["away"]),str(s["home"]),a,h,pa,ph,total,
                     str(s.get("source") or "unknown"),
                     str(s.get("warning") or "")[:500],
                     str(s.get("model_id") or "legacy_v72")[:40]))
                stored+=cursor.rowcount
        conn.commit()
    return {"saved":stored,"duplicates_or_rejected":len(summaries)-stored,
            "invalid_or_past":invalid}


def remote_settle(url,completed_games,settled_at=None):
    if completed_games is None or completed_games.empty:
        return 0
    stamp=utc_timestamp(settled_at if settled_at is not None
                        else datetime.now(timezone.utc))
    count=0
    with connect(url) as conn:
        init_remote(conn)
        for g in completed_games.to_dict("records"):
            try:
                if int(g.get("status_code") or 0)!=3:
                    continue
                gid=str(g.get("game_id") or "")
                a,h=int(g["away_score"]),int(g["home_score"])
                if not gid.isdecimal() or min(a,h)<55 or max(a,h)>200 or a==h:
                    continue
                cursor=conn.execute(
                    """UPDATE bestbets_forecasts SET away_score=%s,
                    home_score=%s,settled_at_utc=%s WHERE game_id=%s
                    AND away_score IS NULL AND home_score IS NULL
                    AND forecast_time_utc<start_utc AND start_utc<=%s""",
                    (a,h,stamp.to_pydatetime(),gid,stamp.to_pydatetime()))
                count+=cursor.rowcount
            except (ValueError,TypeError,KeyError):
                continue
        conn.commit()
    return count


def remote_read(url,season=None):
    from psycopg.rows import dict_row
    with connect(url) as conn:
        init_remote(conn)
        with conn.cursor(row_factory=dict_row) as cur:
            if season:
                cur.execute("""SELECT * FROM bestbets_forecasts WHERE season=%s
                             ORDER BY start_utc DESC""",(str(season),))
            else:
                cur.execute("SELECT * FROM bestbets_forecasts ORDER BY start_utc DESC")
            records=cur.fetchall()
    df=pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=COLUMNS+["model_id"])
    for col in ("forecast_time_utc","start_utc","settled_at_utc"):
        df[col]=pd.to_datetime(df[col],errors="coerce",utc=True).astype(str)
    return df.reindex(columns=COLUMNS+["model_id"])
