"""Admin-only point-in-time source probes. No public cache or database writes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from time import monotonic

URLS = {
    "ESPN scoreboard": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
    "NBA scoreboard": "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json",
    "ESPN injuries": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries",
}

def assess_payload(name, payload):
    if not isinstance(payload, dict):
        return "invalid_schema", None
    if name == "ESPN scoreboard":
        rows = payload.get("events")
        valid = isinstance(rows, list) and all(
            isinstance(row, dict) and row.get("id") and isinstance(row.get("competitions"), list)
            and bool(row["competitions"]) for row in rows)
    elif name == "NBA scoreboard":
        board = payload.get("scoreboard")
        rows = board.get("games") if isinstance(board, dict) else None
        valid = isinstance(rows, list) and all(
            isinstance(row, dict) and row.get("gameId") and
            isinstance(row.get("homeTeam"), dict) and isinstance(row.get("awayTeam"), dict)
            for row in rows)
    elif name == "ESPN injuries":
        rows = payload.get("injuries")
        valid = isinstance(rows, list) and all(
            isinstance(row, dict) and isinstance(row.get("injuries"), list)
            for row in rows)
        if valid:
            # Team groups are not proof of complete coverage or fresh publication.
            rows = [item for group in rows for item in group["injuries"]]
            valid = all(isinstance(item, dict) and isinstance(item.get("athlete"), dict)
                        and bool(item.get("status")) for item in rows)
    else:
        return "invalid_schema", None
    if not valid:
        return "invalid_schema", None
    return ("empty_response" if not rows else "schema_ok"), len(rows)

def probe(name, get=None):
    started = monotonic()
    status, count, code = "unavailable", None, None
    try:
        if get is None:
            import requests
            get = requests.get
        # Fixed endpoints only; no user-controlled URLs or request credentials.
        response = get(URLS[name], timeout=(3, 5), allow_redirects=False)
        code = response.status_code
        if code == 200:
            status, count = assess_payload(name, response.json())
        else:
            status = "http_error"
    except Exception:
        pass
    return {"source": name, "status": status, "http_status": code,
            "elapsed_ms": round((monotonic() - started)*1000),
            "rows": count, "checked_utc": datetime.now(timezone.utc).isoformat()}

def source_snapshot():
    with ThreadPoolExecutor(max_workers=3) as pool:
        return list(pool.map(probe, URLS))
