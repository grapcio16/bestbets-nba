"""Network-free regression checks for on-demand ESPN matchup history loading."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from types import ModuleType
from unittest.mock import Mock, patch
import sys

import pandas as pd

from espn_player_data import (matchup_espn_logs, prefetch_matchup_boxscores,
                              _BOX_PREFETCH_LOCK, _BOX_PREFETCH_PENDING)


class MatchupHistoryLatencyTests(unittest.TestCase):
    @staticmethod
    def cached_sources():
        """Stub disk-cache reads without importing network-facing dependencies."""
        module = ModuleType("sources")
        module.read_cache = Mock(return_value=(None, None))
        module.store_cache = Mock()
        return module

    @staticmethod
    def history(per_team):
        rows = []
        for team in ("IND", "PHI"):
            for index in range(per_team):
                rows.append({
                    "game_id": str(401000000 + index + (100 if team == "IND" else 200)),
                    "start_utc": pd.Timestamp("2026-11-01T00:00:00Z") + pd.Timedelta(days=index),
                    "status_code": 3,
                    "home": team,
                    "away": "BOS" if team == "IND" else "NYK",
                })
        return pd.DataFrame(rows)

    @staticmethod
    def selected_game():
        return {"game_id": "401999999", "start_utc": "2026-11-15T00:00:00Z",
                "home": "PHI", "away": "IND"}

    def test_all_fourteen_boxscores_share_one_bounded_request_wave(self):
        received = []

        def fake_fetch(game):
            received.append(game["game_id"])
            return [{"GAME_ID": game["game_id"], "TEAM_ABBREVIATION": game["home"],
                     "PLAYER_NAME": "Test " + game["home"], "PTS": 12}]

        with (patch.dict(sys.modules, {"sources": self.cached_sources()}),
              patch("espn_player_data.fetch_boxscore", side_effect=fake_fetch),
              patch("espn_player_data.ThreadPoolExecutor", wraps=ThreadPoolExecutor) as pool):
            data, meta = matchup_espn_logs(self.history(7), self.selected_game())

        pool.assert_called_once_with(max_workers=14)
        self.assertEqual(len(received), 14)
        self.assertEqual(data["GAME_ID"].nunique(), 14)
        self.assertEqual(set(data["TEAM_ABBREVIATION"]), {"IND", "PHI"})
        self.assertIn("IND: 7/7", meta["coverage"])
        self.assertIn("PHI: 7/7", meta["coverage"])
        self.assertFalse(meta["stale"])

    def test_small_history_does_not_spawn_unused_workers(self):
        with (patch.dict(sys.modules, {"sources": self.cached_sources()}),
              patch("espn_player_data.fetch_boxscore", return_value=[]),
              patch("espn_player_data.ThreadPoolExecutor", wraps=ThreadPoolExecutor) as pool):
            data, meta = matchup_espn_logs(self.history(1), self.selected_game())

        pool.assert_called_once_with(max_workers=2)
        self.assertTrue(data.empty)
        self.assertIn("0/2 boxscore", meta["coverage"])

    def test_background_warmup_and_foreground_share_actual_boxscores(self):
        release = Event()
        mutex = Lock()
        requested = []

        def slow_boxscore(game):
            with mutex:
                requested.append(game["game_id"])
            if not release.wait(timeout=4):
                raise TimeoutError("Test warm-up did not release pending requests")
            return [{"GAME_ID": game["game_id"], "TEAM_ABBREVIATION": game["home"],
                     "PLAYER_NAME": "Test " + game["home"], "PTS": 12}]

        with _BOX_PREFETCH_LOCK:
            _BOX_PREFETCH_PENDING.clear()
        try:
            with (patch.dict(sys.modules, {"sources": self.cached_sources()}),
                  patch("espn_player_data.fetch_boxscore", side_effect=slow_boxscore)):
                launched = prefetch_matchup_boxscores(self.history(7), self.selected_game())
                self.assertEqual(launched, 14)
                with ThreadPoolExecutor(max_workers=1) as pool:
                    foreground = pool.submit(matchup_espn_logs,
                                             self.history(7), self.selected_game())
                    release.set()
                    data, meta = foreground.result(timeout=5)
            self.assertEqual(len(requested), 14, "Do not fetch twice during prefetch")
            self.assertEqual(data["GAME_ID"].nunique(), 14)
            self.assertFalse(meta["stale"])
        finally:
            release.set()
            with _BOX_PREFETCH_LOCK:
                _BOX_PREFETCH_PENDING.clear()

    def test_background_warmup_skips_already_cached_final_boxscores(self):
        fake = self.cached_sources()
        fake.read_cache = Mock(side_effect=lambda key, ttl:
            ({"boxscore": {}}, {"stale": False}) if key.startswith("espn-final-summary-")
            else (None, None))
        with (patch.dict(sys.modules, {"sources": fake}),
              patch("espn_player_data.fetch_boxscore") as fetch):
            submitted = prefetch_matchup_boxscores(self.history(7), self.selected_game())
        self.assertEqual(submitted, 0)
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
