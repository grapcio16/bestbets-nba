"""Regression tests: future NBA player forecasts cannot imply an injured
athlete is available. All data here are synthetic test-only examples.
"""
import unittest
import pandas as pd

from availability_context import matchup_injuries
from simulation_player_availability_guard import (
    injury_status, report_is_current, should_suppress_forecast,
    suppress_player_forecasts,
)

NOW = pd.Timestamp("2026-11-23T20:00:00Z")


def watch(*rows, future=True):
    return {
        "fresh": future,
        "checked_at": "2026-11-23T19:30:00Z",
        "valid_until": "2026-11-23T21:00:00Z",
        "rows": list(rows),
    }


class AvailabilityGuardTest(unittest.TestCase):
    def test_current_espn_out_is_never_projected(self):
        report = watch({"name": "Test Guard Alpha", "team": "PHI",
                        "status": "Out", "espn_id": "12345"})
        self.assertTrue(report_is_current(report, now=NOW))
        self.assertEqual(injury_status("Test Guard Alpha", "PHI", "12345", report), "Out")
        active, excluded = suppress_player_forecasts(
            [{"name": "Test Guard Alpha", "team": "PHI",
              "pts": 25.0, "availability": "Out"},
             {"name": "Test Guard Beta", "team": "MIL",
              "pts": 18.0, "availability": "Niezweryfikowany"}],
            report, future=True)
        self.assertEqual([p["name"] for p in active], ["Test Guard Beta"])
        self.assertEqual(excluded[0]["status"], "Out")

    def test_same_espn_id_overrides_spelling_mismatch(self):
        report = watch({"name": "Synthetic J. Sample Jr.", "team": "BOS",
                        "status": "Out", "espn_id": "987654"})
        self.assertEqual(injury_status("Jonathan Sample", "BOS", "987654", report),
                         "Out")
        self.assertEqual(injury_status("Jonathan Sample", "MIA", "987654", report),
                         "Niezweryfikowany")

    def test_one_player_cannot_invalidate_same_name_on_opponent(self):
        report = watch({"name": "Same Name", "team": "NYK", "status": "Out"})
        self.assertEqual(injury_status("Same Name", "NYK", "", report), "Out")
        self.assertEqual(injury_status("Same Name", "BOS", "", report),
                         "Niezweryfikowany")

    def test_explicit_roster_inactive_blocks_without_name_in_injury_feed(self):
        self.assertEqual(injury_status("Different Name", "MIA", "", watch(),
                                       roster_status="Inactive"), "Out")

    def test_conflicting_and_uncertain_statuses_are_not_recommended(self):
        report = watch({"name": "Risk Sample", "team": "MIA",
                        "status": "Questionable"},
                       {"name": "Risk Sample", "team": "MIA",
                        "status": "Probable"})
        self.assertEqual(injury_status("Risk Sample", "MIA", "", report),
                         "Sprzeczne")
        for status in ("Out", "Doubtful", "Questionable", "Day-to-day",
                       "Sprzeczne", "Inny / niepotwierdzony"):
            self.assertTrue(should_suppress_forecast(status), status)
        self.assertFalse(should_suppress_forecast("Probable"))
        self.assertFalse(should_suppress_forecast("Niezweryfikowany"))

    def test_espn_status_out_wins_over_probable_when_conflicting(self):
        report = watch({"name": "Risk Sample", "team": "MIA",
                        "status": "Probable"},
                       {"name": "Risk Sample", "team": "MIA",
                        "status": "Out"})
        self.assertEqual(injury_status("Risk Sample", "MIA", "", report), "Out")

    def test_expired_report_blocks_all_future_player_forecasts(self):
        old = watch({"name": "Test Guard Alpha", "team": "PHI",
                     "status": "Probable"})
        self.assertFalse(report_is_current(old, now=pd.Timestamp("2026-11-23T21:05:00Z")))
        old["fresh"] = False
        players = [{"name": "Test Guard Alpha", "team": "PHI",
                    "pts": 23, "availability": "Probable"}]
        safe, excluded = suppress_player_forecasts(players, old, future=True)
        self.assertEqual(safe, [])
        self.assertEqual(len(excluded), 1)

    def test_missing_timestamp_or_missing_report_fails_closed(self):
        report = watch()
        report.pop("checked_at")
        self.assertFalse(report_is_current(report, now=NOW))
        self.assertFalse(report_is_current({}, now=NOW))
        self.assertFalse(report_is_current(None, now=NOW))

    def test_status_report_never_applied_to_historical_final(self):
        report = watch({"name": "Test Guard Alpha", "team": "PHI",
                        "status": "Out"})
        history = [{"name": "Test Guard Alpha", "team": "PHI",
                    "pts": 25, "availability": "Out"}]
        safe, excluded = suppress_player_forecasts(history, report, future=False)
        self.assertEqual(safe, history)
        self.assertEqual(excluded, [])

    def test_espn_identifier_preserved_from_raw_provider(self):
        raw = pd.DataFrame([{"team": "PHI", "player": "Test Guard Alpha",
                             "status": "Out", "athlete_id": "15376", "note": "out"},
                            {"team": "BOS", "player": "Test Guard Beta",
                             "status": "Out", "athlete_id": "15377", "note": "out"}])
        matched, meta = matchup_injuries(raw, "PHI", "MIL")
        self.assertEqual(meta["records"], 1)
        self.assertEqual(matched.iloc[0]["ESPN_ID"], "15376")

    def test_out_of_window_report_cannot_be_verified(self):
        invalid = watch()
        invalid["checked_at"] = "2026-11-23T15:00:00Z"
        self.assertFalse(report_is_current(invalid, now=NOW))


if __name__ == "__main__":
    unittest.main()
