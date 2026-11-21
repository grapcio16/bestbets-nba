"""Offline performance regressions for the HOOPZARO public dashboard."""
import json
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Lock
from unittest import mock

import pandas as pd

import sources
from bestbets_centre_data import build_centre_snapshot
from global_player_catalog import build_global_catalog
from roster_data import ESPN_TEAM_IDS


class DashboardPerformanceTest(unittest.TestCase):
    def test_compact_hoopzaro_team_logos_preserves_content(self):
        """Repeated fixture logos should cross the iframe boundary just once."""
        logo = "data:image/png;base64," + "A" * 8000
        provider = lambda team: logo if team in ("BOS", "NYK") else ""
        games = pd.DataFrame([
            {
                "game_id": str(i + 1000),
                "start_utc": "2026-11-21T21:00:00Z",
                "away": "BOS", "home": "NYK",
                "away_score": None, "home_score": None,
                "status_code": 1, "status": "Scheduled",
            }
            for i in range(12)
        ])
        now = pd.Timestamp("2026-11-21T19:00:00Z")
        standard = build_centre_snapshot(games, now=now, logo_provider=provider)
        compact = build_centre_snapshot(
            games, now=now, logo_provider=provider, compact_logos=True
        )

        self.assertEqual(compact["team_logos"], {"BOS": logo, "NYK": logo})
        self.assertEqual(compact["games"][0]["away_logo"], "team-logo:BOS")
        self.assertEqual(compact["games"][0]["home_logo"], "team-logo:NYK")
        self.assertEqual(
            [x["id"] for x in standard["calendar_games"]],
            [x["id"] for x in compact["calendar_games"]],
        )
        self.assertEqual(
            [(g["away"], g["home"], g["state"]) for g in standard["games"]],
            [(g["away"], g["home"], g["state"]) for g in compact["games"]],
        )
        self.assertLess(
            len(json.dumps(compact)), len(json.dumps(standard)) * 0.4
        )

    def test_simultaneous_cached_espn_requests_fetch_once(self):
        """Independent sessions must not download the same expired key 8 times."""
        calls = []
        calls_lock = Lock()

        def fake_http(*_args, **_kwargs):
            with calls_lock:
                calls.append(1)
            time.sleep(0.04)
            return {"events": [{"id": "123"}]}

        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(sources, "CACHE", Path(tmp)), \
             mock.patch.object(sources, "http_json", side_effect=fake_http):
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(
                    lambda _: sources.memoized_json(
                        "one-expired-scoreboard", "https://example.invalid/",
                        ttl_seconds=120, request_timeout=2
                    ),
                    range(8),
                ))
        self.assertEqual(len(calls), 1)
        self.assertTrue(all(row[0]["events"][0]["id"] == "123" for row in results))
        self.assertFalse(any(meta.get("stale") for _, meta in results))

    def test_missing_nba_rosters_retry_in_bounded_parallel(self):
        """Two missing teams should retry simultaneously; verified IDs stay intact."""
        counts = {}
        counts_lock = Lock()
        parallel_retry = Barrier(2)

        def roster_fetch(team):
            with counts_lock:
                counts[team] = counts.get(team, 0) + 1
                attempt = counts[team]
            if team in ("DEN", "GSW"):
                if attempt == 1:
                    raise TimeoutError("Fake first-attempt failure")
                parallel_retry.wait(timeout=3)
            return pd.DataFrame([
                {"PLAYER_ID": str(100000 + 100 * ESPN_TEAM_IDS[team] + i),
                 "PLAYER_NAME": f"{team} athlete {i}",
                 "TEAM_ABBREVIATION": team,
                 "POSITION": "G", "ROSTER_STATUS": "Active"}
                for i in range(8)
            ]), {"stale": False}

        catalog, coverage = build_global_catalog(roster_fetch, max_workers=5)
        self.assertEqual(coverage["teams_loaded"], 30)
        self.assertEqual(counts["DEN"], 2)
        self.assertEqual(counts["GSW"], 2)
        self.assertEqual(coverage["retried_teams"], ["DEN", "GSW"])
        self.assertEqual(len(catalog), 240)


if __name__ == "__main__":
    unittest.main()
