"""Read-only, bounded admin telemetry for Hoopzaro. No public payload."""
from datetime import datetime, timezone

def classify_worker(row, now=None, stale_hours=8):
    if row is None:
        return "no_evidence"
    now = now or datetime.now(timezone.utc)
    stamp = row["run_utc"]
    if stamp.tzinfo is None or stamp > now:
        return "invalid_timestamp"
    if (now - stamp).total_seconds() > stale_hours * 3600:
        return "stale"
    if row["trainable_examples"] < row["minimum_examples"]:
        return "insufficient_training"
    return "recent_evidence"

def read_snapshot(url, season):
    if not url:
        return {"status": "setup_required"}
    try:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(url, connect_timeout=5, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout = '5000ms'")
                cur.execute("""SELECT run_utc, observed_games, trainable_examples,
                    minimum_examples, eligible_upcoming, calculated_forecasts,
                    newly_archived_forecasts, newly_ingested_boxscores, rejected_boxscores
                    FROM hoopzaro_v8_worker_runs WHERE season=%s
                    ORDER BY run_utc DESC LIMIT 1""", (season,))
                worker = cur.fetchone()
                cur.execute("""SELECT model_id, count(*) AS archived,
                    count(*) FILTER (WHERE actual_home IS NOT NULL
                      AND actual_away IS NOT NULL AND settled_at IS NOT NULL) AS settled
                    FROM hoopzaro_v8_shadow_forecasts WHERE season=%s
                    GROUP BY model_id ORDER BY model_id""", (season,))
                models = cur.fetchall()
        status = classify_worker(worker)
        if worker:
            worker = dict(worker)
            worker["run_utc"] = worker["run_utc"].isoformat()
        return {"status": status, "worker": worker, "models": models,
                "scope": "V8 archive telemetry; not a live API or accuracy check"}
    except Exception:
        # Never return connection strings, database exceptions or provider payloads.
        return {"status": "unavailable"}


def read_scorecard(url, season):
    """Reuse the prospective evaluator without recalculating or settling games."""
    if not url:
        return {"status": "setup_required"}
    try:
        from v8_shadow.evaluation import read_report
        report = read_report(url, season)
        # Only aggregate scorecard fields are needed by the admin screen.
        return {key: report[key] for key in (
            "status", "season", "model_metrics", "common_game_comparisons", "shared_cohort",
            "v8_archived_by_version", "v8_valid_settled_by_version",
            "sample_disclaimer") if key in report}
    except Exception as exc:
        # Only a sanitized category / SQLSTATE; never log the exception text.
        import re
        state = getattr(exc, "sqlstate", None)
        code = state if isinstance(state, str) and re.fullmatch(r"[A-Z0-9]{5}", state) else (
            "connection" if type(exc).__name__ == "OperationalError" else "processing")
        return {"status": "unavailable", "diagnostic": code}
