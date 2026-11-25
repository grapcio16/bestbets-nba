"""V8 research telemetry entrypoint; existing V7 and V8 math untouched."""
import json
import os
import pandas as pd
from v8_shadow.readiness import audit_evidence
from v8_shadow.storage import read_boxes, record_worker_run
from v8_shadow.worker import run

def run_monitored():
    report = run()
    url = os.environ.get("TRACKER_DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("Durable V8 research storage required")
    evidence = read_boxes(url, report["season"])
    ready = audit_evidence(evidence, pd.Timestamp.now(tz="UTC"))
    ingest = report.get("boxscore_ingest") or {}
    record_worker_run(
        url, report["season"], ready,
        upcoming_checked=int(report.get("upcoming_games_checked") or 0),
        calculated=int(report.get("shadow_forecasts_calculated") or 0),
        saved=int(report.get("new_shadow_forecasts") or 0),
        boxes_added=int(report.get("new_boxscore_games") or 0),
        boxes_rejected=int(ingest.get("rejected") or 0))
    report["readiness"] = ready
    return report

if __name__ == "__main__":
    print(json.dumps(run_monitored(), ensure_ascii=False, default=str))
