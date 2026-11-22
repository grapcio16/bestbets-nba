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
MODEL_DDL = """
CREATE TABLE IF NOT EXISTS bestbets_forecasts_by_model (
 game_id TEXT NOT NULL,
 model_id TEXT NOT NULL,
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
 PRIMARY KEY (game_id,model_id)
);
CREATE INDEX IF NOT EXISTS bestbets_model_forecasts_start
 ON bestbets_forecasts_by_model(start_utc);
"""
PLAYER_DDL = """
CREATE TABLE IF NOT EXISTS bestbets_player_forecasts (
 game_id TEXT NOT NULL,
 model_id TEXT NOT NULL,
 player_id TEXT NOT NULL,
 season TEXT NOT NULL,
 forecast_time_utc TIMESTAMPTZ NOT NULL,
 start_utc TIMESTAMPTZ NOT NULL,
 team TEXT NOT NULL,
 player_name TEXT NOT NULL,
 pts_pred DOUBLE PRECISION NOT NULL,
 reb_pred DOUBLE PRECISION NOT NULL,
 ast_pred DOUBLE PRECISION NOT NULL,
 fg3m_pred DOUBLE PRECISION NOT NULL,
 minutes_pred DOUBLE PRECISION NOT NULL,
 sample_games INTEGER NOT NULL,
 source TEXT NOT NULL,
 pts_actual DOUBLE PRECISION,
 reb_actual DOUBLE PRECISION,
 ast_actual DOUBLE PRECISION,
 fg3m_actual DOUBLE PRECISION,
 minutes_actual DOUBLE PRECISION,
 settled_at_utc TIMESTAMPTZ,
 PRIMARY KEY (game_id,model_id,player_id)
);
CREATE INDEX IF NOT EXISTS bestbets_player_forecasts_start
 ON bestbets_player_forecasts(start_utc);
"""
QUARTER_DDL = """
CREATE TABLE IF NOT EXISTS bestbets_quarter_forecasts (
 game_id TEXT NOT NULL,
 model_id TEXT NOT NULL,
 quarter SMALLINT NOT NULL CHECK (quarter BETWEEN 1 AND 4),
 season TEXT NOT NULL,
 forecast_time_utc TIMESTAMPTZ NOT NULL,
 start_utc TIMESTAMPTZ NOT NULL,
 away TEXT NOT NULL,
 home TEXT NOT NULL,
 away_points DOUBLE PRECISION NOT NULL,
 home_points DOUBLE PRECISION NOT NULL,
 away_win_pct DOUBLE PRECISION NOT NULL,
 home_win_pct DOUBLE PRECISION NOT NULL,
 tie_pct DOUBLE PRECISION NOT NULL,
 away_sample INTEGER NOT NULL,
 home_sample INTEGER NOT NULL,
 source TEXT NOT NULL,
 away_actual SMALLINT,
 home_actual SMALLINT,
 settled_at_utc TIMESTAMPTZ,
 PRIMARY KEY (game_id,model_id,quarter)
);
CREATE INDEX IF NOT EXISTS bestbets_quarter_forecasts_start
 ON bestbets_quarter_forecasts(season, start_utc);
"""
RUN_MONITOR_DDL = """
CREATE TABLE IF NOT EXISTS bestbets_tracker_runs (
 run_id BIGSERIAL PRIMARY KEY,
 finished_at_utc TIMESTAMPTZ NOT NULL,
 season TEXT NOT NULL,
 team_new INTEGER NOT NULL,
 team_settled INTEGER NOT NULL,
 player_new INTEGER NOT NULL,
 player_settled INTEGER NOT NULL,
 player_games_checked INTEGER NOT NULL,
 player_games_projected INTEGER NOT NULL,
 player_status TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS bestbets_tracker_runs_latest
 ON bestbets_tracker_runs(season, finished_at_utc DESC);
"""


def connect(url):
    if not url or not str(url).startswith(("postgresql://","postgres://")):
        raise ValueError("TRACKER_DATABASE_URL musi wskazywać PostgreSQL")
    import psycopg  # imported ONLY when remote DB configured
    conn=psycopg.connect(str(url),connect_timeout=8)
    # Do not log URLs or messages that could expose credentials.
    return conn


def init_remote(conn):
    for ddl in (POSTGRES_DDL, MODEL_DDL, PLAYER_DDL, QUARTER_DDL, RUN_MONITOR_DDL):
        for statement in ddl.split(";"):
            if statement.strip():
                conn.execute(statement)
    # Preserve old game-only records. Never erase or modify a frozen forecast.
    conn.execute("""
        INSERT INTO bestbets_forecasts_by_model
        (game_id,model_id,season,forecast_time_utc,start_utc,away,home,
        away_points,home_points,away_win_pct,home_win_pct,total_points,
        source,warning,away_score,home_score,settled_at_utc)
        SELECT game_id,COALESCE(model_id,'legacy_v72'),season,forecast_time_utc,
        start_utc,away,home,away_points,home_points,away_win_pct,
        home_win_pct,total_points,source,warning,away_score,home_score,
        settled_at_utc FROM bestbets_forecasts
        WHERE TRUE
        ON CONFLICT (game_id,model_id) DO NOTHING
    """)
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
                    """INSERT INTO bestbets_forecasts_by_model
                    (game_id,model_id,season,forecast_time_utc,start_utc,away,home,
                    away_points,home_points,away_win_pct,home_win_pct,total_points,
                    source,warning)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (game_id,model_id) DO NOTHING""",
                    (gid,str(s.get("model_id") or "legacy_v72")[:40],
                     str(season),stamp.to_pydatetime(),start.to_pydatetime(),
                     str(s["away"]),str(s["home"]),a,h,pa,ph,total,
                     str(s.get("source") or "unknown"),
                     str(s.get("warning") or "")[:500]))
                stored+=cursor.rowcount
            except (ValueError,TypeError,KeyError,OverflowError):
                invalid+=1
                continue
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
                    """UPDATE bestbets_forecasts_by_model SET away_score=%s,
                    home_score=%s,settled_at_utc=%s WHERE game_id=%s
                    AND away_score IS NULL AND home_score IS NULL
                    AND forecast_time_utc<start_utc AND start_utc<=%s""",
                    (a,h,stamp.to_pydatetime(),gid,stamp.to_pydatetime()))
                count+=cursor.rowcount
            except (ValueError,TypeError,KeyError):
                continue
        conn.commit()
    return count


def _report_frame(records):
    """Normalize PostgreSQL rows without duplicate column labels."""
    df=pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=COLUMNS)
    for col in ("forecast_time_utc","start_utc","settled_at_utc"):
        df[col]=pd.to_datetime(df[col],errors="coerce",utc=True).astype(str)
    # COLUMNS already contains model_id. Duplicating this label makes the
    # administrator's groupby("model_id") fail with a ValueError as soon as
    # the PostgreSQL archive contains a forecast.
    return df.reindex(columns=COLUMNS)


def remote_read(url,season=None):
    from psycopg.rows import dict_row
    with connect(url) as conn:
        init_remote(conn)
        with conn.cursor(row_factory=dict_row) as cur:
            if season:
                cur.execute("""SELECT * FROM bestbets_forecasts_by_model WHERE season=%s
                             ORDER BY start_utc DESC""",(str(season),))
            else:
                cur.execute("SELECT * FROM bestbets_forecasts_by_model ORDER BY start_utc DESC")
            records=cur.fetchall()
    return _report_frame(records)


def remote_store_players(url, season, forecasts, captured_at=None):
    """Freeze one player/model/game prediction, strictly before tipoff."""
    from math import isfinite
    from player_simulation_tracker import MODEL_ID
    from simulation_shadow_v76 import SHADOW_PLAYER_MODEL_ID
    allowed_models = {MODEL_ID, SHADOW_PLAYER_MODEL_ID}

    stamp = utc_timestamp(captured_at if captured_at is not None
                          else datetime.now(timezone.utc))
    saved = 0
    with connect(url) as conn:
        init_remote(conn)
        for row in forecasts:
            try:
                gid, pid = str(row["game_id"]), str(row["player_id"])
                model_id = str(row["model_id"])
                team = str(row["team"])
                name = str(row["player_name"]).strip()
                start = utc_timestamp(row["start_utc"])
                sample = int(row["sample_games"])
                vals = [float(row[key]) for key in (
                    "pts_pred", "reb_pred", "ast_pred", "fg3m_pred", "minutes_pred")]
                if (model_id not in allowed_models or not gid.isdecimal()
                    or not pid.isdecimal() or max(len(gid), len(pid)) > 20
                    or not team or len(team) > 4 or not name or len(name) > 100
                    or start <= stamp or sample < 3 or sample > 100
                    or not all(isfinite(v) for v in vals)
                    or not all(0 <= v <= limit for v, limit in zip(vals, (80, 35, 30, 15, 50)))):
                    continue
                cur = conn.execute("""
                    INSERT INTO bestbets_player_forecasts
                    (game_id,model_id,player_id,season,forecast_time_utc,start_utc,
                     team,player_name,pts_pred,reb_pred,ast_pred,fg3m_pred,
                     minutes_pred,sample_games,source)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (game_id,model_id,player_id) DO NOTHING
                """, (gid, model_id, pid, str(season), stamp.to_pydatetime(),
                      start.to_pydatetime(), team, name, *vals, sample,
                      str(row.get("source") or "ESPN")[:160]))
                saved += cur.rowcount
            except (KeyError, ValueError, TypeError, OverflowError):
                continue
        conn.commit()
    return {"saved": saved, "duplicates_or_rejected": len(forecasts)-saved}


def remote_settle_players(url, completed_games, *, fetch_boxscore=None, settled_at=None):
    """Attach verified final boxscores by ESPN game AND athlete ID.

    No match (including DNP) stays NULL. We do not assume missing=0.
    Fetch only final games having still-unsettled player forecasts.
    """
    from espn_player_data import fetch_boxscore as official_boxscore

    if completed_games is None or completed_games.empty:
        return 0
    stamp = utc_timestamp(settled_at if settled_at is not None
                          else datetime.now(timezone.utc))
    finals = {}
    for game in completed_games.to_dict("records"):
        try:
            if int(game.get("status_code") or 0) != 3:
                continue
            gid = str(game["game_id"])
            if (not gid.isdecimal() or not 55 <= int(game["home_score"]) <= 200
                    or not 55 <= int(game["away_score"]) <= 200):
                continue
            if utc_timestamp(game["start_utc"]) > stamp:
                continue
            finals[gid] = game
        except (KeyError, ValueError, TypeError, OverflowError):
            continue
    if not finals:
        return 0
    with connect(url) as conn:
        init_remote(conn)
        pending = {str(row[0]) for row in conn.execute("""
            SELECT DISTINCT game_id FROM bestbets_player_forecasts
            WHERE pts_actual IS NULL AND forecast_time_utc < start_utc
              AND start_utc <= %s
        """, (stamp.to_pydatetime(),)).fetchall()}
    reader = fetch_boxscore or official_boxscore
    updates = []
    for gid in sorted(pending & finals.keys()):
        try:
            player_rows = reader(finals[gid])
        except (KeyError, ValueError, TypeError, OverflowError, RuntimeError,
                OSError, ConnectionError, TimeoutError):
            continue
        for row in player_rows:
            try:
                if str(row.get("GAME_ID")) != gid:
                    continue
                pid = str(row.get("PLAYER_ID") or "")
                pts, reb, ast = (float(row[name]) for name in ("PTS", "REB", "AST"))
                minutes = float(row["MIN"])
                fg3m = row.get("FG3M")
                fg3m = float(fg3m) if fg3m is not None else None
                # Some verified ESPN boxscores publish PTS/REB/AST before the
                # 3-point split. Keep the verified stats and leave 3PM NULL.
                if fg3m is not None and not 0 <= fg3m <= 20:
                    fg3m = None
                if (not pid.isdecimal() or minutes <= 0 or minutes > 60
                    or not all(0 <= val <= limit for val, limit in (
                        (pts, 100), (reb, 50), (ast, 40)))):
                    continue
                updates.append((pts, reb, ast, fg3m, minutes, stamp.to_pydatetime(),
                                gid, pid, str(row.get("TEAM_ABBREVIATION") or ""),
                                stamp.to_pydatetime()))
            except (KeyError, ValueError, TypeError, OverflowError):
                continue
    matched = 0
    if updates:
        with connect(url) as conn:
            init_remote(conn)
            for values in updates:
                cursor = conn.execute("""
                    UPDATE bestbets_player_forecasts SET
                    pts_actual=%s,reb_actual=%s,ast_actual=%s,fg3m_actual=%s,
                    minutes_actual=%s,settled_at_utc=%s
                    WHERE game_id=%s AND player_id=%s AND team=%s
                      AND pts_actual IS NULL AND forecast_time_utc < start_utc
                      AND start_utc <= %s
                """, values)
                matched += cursor.rowcount
            conn.commit()
    return matched


def remote_read_players(url, season=None):
    """Read-only admin evaluation input; never exposed to public sessions."""
    from psycopg.rows import dict_row

    with connect(url) as conn:
        init_remote(conn)
        with conn.cursor(row_factory=dict_row) as cur:
            if season:
                cur.execute("""SELECT * FROM bestbets_player_forecasts
                    WHERE season=%s ORDER BY start_utc DESC""", (str(season),))
            else:
                cur.execute("SELECT * FROM bestbets_player_forecasts ORDER BY start_utc DESC")
            records = cur.fetchall()
    return pd.DataFrame(records)


def remote_record_tracker_run(url, summary):
    """Write a small, credential-free heartbeat after a completed worker cycle."""
    player = summary.get("player_tracking") or {}
    status = ("ok" if player.get("status", "ok") == "ok"
              else "temporarily_unavailable")

    def counter(value):
        number = int(value or 0)
        if not 0 <= number <= 100000:
            raise ValueError("Niepoprawna liczba wyników trackera")
        return number

    stamp = datetime.now(timezone.utc)
    with connect(url) as conn:
        init_remote(conn)
        conn.execute("""INSERT INTO bestbets_tracker_runs
            (finished_at_utc,season,team_new,team_settled,player_new,
             player_settled,player_games_checked,player_games_projected,player_status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (stamp, str(summary["season"]),
             counter(summary.get("new_pregame_snapshots")),
             counter(summary.get("matched_forecast_rows_settled")),
             counter(player.get("new_player_snapshots")),
             counter(player.get("player_rows_settled")),
             counter(player.get("pregame_games_checked")),
             counter(player.get("games_with_player_projections")), status))
        conn.commit()
    return {"recorded": True}


def remote_tracker_status(url, season):
    """Read-only summary for the admin panel; counts are forecast ROWS."""
    with connect(url) as conn:
        init_remote(conn)
        last = conn.execute("""SELECT finished_at_utc,team_new,team_settled,
            player_new,player_settled,player_games_checked,
            player_games_projected,player_status
            FROM bestbets_tracker_runs WHERE season=%s
            ORDER BY finished_at_utc DESC LIMIT 1""", (str(season),)).fetchone()
        team = conn.execute("""SELECT COUNT(*),
            COUNT(*) FILTER (WHERE home_score IS NOT NULL AND away_score IS NOT NULL)
            FROM bestbets_forecasts_by_model WHERE season=%s""", (str(season),)).fetchone()
        players = conn.execute("""SELECT COUNT(*),
            COUNT(*) FILTER (WHERE pts_actual IS NOT NULL)
            FROM bestbets_player_forecasts WHERE season=%s""", (str(season),)).fetchone()
    team_total, team_settled = map(int, team or (0, 0))
    player_total, player_settled = map(int, players or (0, 0))
    result = {
        "season": str(season),
        "team": {"saved": team_total, "settled": team_settled,
                 "pending": team_total-team_settled},
        "players": {"saved": player_total, "settled": player_settled,
                    "pending": player_total-player_settled},
        "last_run_utc": None, "last_run_age_hours": None,
        "stale": None, "last_player_status": None, "last_cycle": None,
    }
    if last:
        stamp = utc_timestamp(last[0])
        age = max(0.0, (datetime.now(timezone.utc)-stamp.to_pydatetime()).total_seconds()/3600)
        result.update({
            "last_run_utc": stamp.strftime("%Y-%m-%d %H:%M"),
            "last_run_age_hours": round(age, 1),
            "stale": age > 10,
            "last_player_status": str(last[7]),
            "last_cycle": {
                "team_new": int(last[1]), "team_settled": int(last[2]),
                "player_new": int(last[3]), "player_settled": int(last[4]),
                "player_games_checked": int(last[5]),
                "player_games_projected": int(last[6]),
            },
        })
    return result


def remote_store_quarters(url, season, forecasts, captured_at=None):
    """Freeze only complete quartet predictions matching an archived parent."""
    from math import isfinite
    from simulation_quarter_shadow import MODEL_IDS

    stamp = utc_timestamp(captured_at if captured_at is not None
                          else datetime.now(timezone.utc))
    groups = {}
    for f in forecasts:
        key = (str(f.get("game_id") or ""), str(f.get("base_model_id") or ""))
        groups.setdefault(key, []).append(f)

    saved = 0
    with connect(url) as conn:
        init_remote(conn)
        valid_groups = set()
        for (gid, parent_id), items in groups.items():
            if (parent_id not in MODEL_IDS or len(items) != 4
                    or {item.get("quarter") for item in items} != {1, 2, 3, 4}
                    or not gid.isdecimal()):
                continue
            # The parent complete-game forecast must already be frozen.
            parent = conn.execute("""
                SELECT home_points,away_points,start_utc,home,away
                FROM bestbets_forecasts_by_model
                WHERE game_id=%s AND model_id=%s
            """, (gid, parent_id)).fetchone()
            if parent is None:
                continue
            try:
                home_total = sum(float(item["home_points"]) for item in items)
                away_total = sum(float(item["away_points"]) for item in items)
                start = utc_timestamp(items[0]["start_utc"])
                if (start <= stamp or start != utc_timestamp(parent[2])
                        or any(item.get("model_id") != MODEL_IDS[parent_id]
                               or str(item.get("home")) != str(parent[3])
                               or str(item.get("away")) != str(parent[4])
                               for item in items)
                        or abs(home_total - float(parent[0])) > .15
                        or abs(away_total - float(parent[1])) > .15):
                    continue
            except (KeyError, ValueError, TypeError, OverflowError):
                continue
            valid_groups.add((gid, parent_id))

        for f in forecasts:
            try:
                gid = str(f["game_id"])
                base_id = str(f["base_model_id"])
                if (gid, base_id) not in valid_groups:
                    continue
                start = utc_timestamp(f["start_utc"])
                q = int(f["quarter"])
                home, away = float(f["home_points"]), float(f["away_points"])
                hp, ap, tie = (float(f[key]) for key in
                               ("home_win_pct", "away_win_pct", "tie_pct"))
                n_h, n_a = int(f["home_sample"]), int(f["away_sample"])
                if (not gid.isdecimal() or len(gid) > 20 or start <= stamp
                        or f.get("model_id") != MODEL_IDS[base_id] or not 1 <= q <= 4
                        or not all(isfinite(x) for x in (home, away, hp, ap, tie))
                        or not 8 <= home <= 55 or not 8 <= away <= 55
                        or min(hp, ap, tie) < 0 or max(hp, ap, tie) > 100
                        or abs(hp + ap + tie - 100) > .15
                        or min(n_h, n_a) < 6):
                    continue
                cur = conn.execute("""
                    INSERT INTO bestbets_quarter_forecasts
                    (game_id,model_id,quarter,season,forecast_time_utc,start_utc,
                     away,home,away_points,home_points,away_win_pct,home_win_pct,
                     tie_pct,away_sample,home_sample,source)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (game_id,model_id,quarter) DO NOTHING
                """, (gid,str(f["model_id"]),q,str(season),stamp.to_pydatetime(),
                      start.to_pydatetime(),str(f["away"]),str(f["home"]),
                      away,home,ap,hp,tie,n_a,n_h,str(f["source"])[:220]))
                saved += cur.rowcount
            except (ValueError, TypeError, KeyError, OverflowError):
                continue
        conn.commit()
    return {"saved": saved, "duplicates_or_rejected": len(forecasts)-saved}


def remote_settle_quarters(url, completed_games, settled_at=None):
    """Grade only actual complete, non-overtime regulation line scores."""
    from simulation_quarter_shadow import complete_quarter_history

    stamp = utc_timestamp(settled_at if settled_at is not None
                          else datetime.now(timezone.utc))
    verified = complete_quarter_history(completed_games, stamp)
    if verified.empty:
        return 0
    settled = 0
    with connect(url) as conn:
        init_remote(conn)
        for game in verified.to_dict("records"):
            gid = str(game.get("game_id") or "")
            if not gid.isdecimal():
                continue
            for q in range(1, 5):
                away = int(game[f"away_q{q}"])
                home = int(game[f"home_q{q}"])
                cur = conn.execute("""
                    UPDATE bestbets_quarter_forecasts
                    SET away_actual=%s,home_actual=%s,settled_at_utc=%s
                    WHERE game_id=%s AND quarter=%s AND
                    away_actual IS NULL AND home_actual IS NULL
                    AND forecast_time_utc<start_utc AND start_utc<=%s
                """, (away,home,stamp.to_pydatetime(),gid,q,stamp.to_pydatetime()))
                settled += cur.rowcount
        conn.commit()
    return settled


def remote_read_quarters(url, season=None):
    from psycopg.rows import dict_row

    with connect(url) as conn:
        init_remote(conn)
        with conn.cursor(row_factory=dict_row) as cur:
            if season is not None:
                cur.execute("""SELECT * FROM bestbets_quarter_forecasts
                    WHERE season=%s ORDER BY start_utc DESC,quarter""",
                    (str(season),))
            else:
                cur.execute("""SELECT * FROM bestbets_quarter_forecasts
                    ORDER BY start_utc DESC,quarter""")
            records = cur.fetchall()
    return pd.DataFrame(records)
