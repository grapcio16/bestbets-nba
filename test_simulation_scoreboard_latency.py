"""Regression tests for concurrent, cached ESPN season scoreboard acquisition."""
from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch
import sys
import unittest

import pandas as pd


class SeasonScoreboardLatencyTests(unittest.TestCase):
    @staticmethod
    def isolated_adapter(fetch):
        sources = ModuleType("sources")
        sources.ESPN_SCOREBOARD = "https://example.invalid/scoreboard"
        sources.memoized_json = Mock(side_effect=fetch)
        sources.parse_espn_schedule = lambda raw: pd.DataFrame([raw])
        path = Path(__file__).with_name("simulation_sources.py")
        spec = spec_from_file_location("test_isolated_simulation_sources", path)
        adapter = module_from_spec(spec)
        with patch.dict(sys.modules, {"sources": sources}):
            spec.loader.exec_module(adapter)
        return adapter, sources

    def test_independent_months_are_requested_in_one_concurrent_batch(self):
        def fetch(key, url, **kwargs):
            return {"key": key}, {"stale": False}

        adapter, sources = self.isolated_adapter(fetch)
        periods = [pd.Period("2026-10"), pd.Period("2026-11"),
                   pd.Period("2026-12")]
        with patch.object(adapter, "ThreadPoolExecutor", wraps=ThreadPoolExecutor) as pool:
            chunks, errors = adapter._season_scoreboard_months(periods)

        pool.assert_called_once_with(max_workers=3)
        self.assertEqual(errors, [])
        self.assertEqual([chunk.iloc[0]["key"] for chunk in chunks], [
            "sim-finished-scoreboard-202610",
            "sim-finished-scoreboard-202611",
            "sim-finished-scoreboard-202612",
        ])
        self.assertEqual(sources.memoized_json.call_count, 3)
        for call in sources.memoized_json.call_args_list:
            self.assertEqual(call.kwargs["ttl_seconds"], 45 * 60)

    def test_one_failed_month_does_not_hide_other_verified_months(self):
        def fetch(key, url, **kwargs):
            if key.endswith("202611"):
                raise RuntimeError("ESPN timeout")
            return {"key": key}, {"stale": False}

        adapter, _ = self.isolated_adapter(fetch)
        chunks, errors = adapter._season_scoreboard_months([
            pd.Period("2026-10"), pd.Period("2026-11")])
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].iloc[0]["key"], "sim-finished-scoreboard-202610")
        self.assertEqual(len(errors), 1)
        self.assertIn("202611", errors[0])


if __name__ == "__main__":
    unittest.main()
