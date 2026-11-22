"""Regression: selected-match ESPN statuses are real, team-scoped and fail closed.

All fixtures and ESPN responses here are synthetic; no external HTTP traffic.
"""
import unittest
from unittest.mock import patch

import pandas as pd

from sources import injury_rows, selected_espn_injuries


FRESH = {"timestamp": "2026-11-22T12:50:00+00:00", "stale": False}


class SelectedEspnInjuriesTests(unittest.TestCase):
    def test_league_response_matches_numeric_espn_team_ids(self):
        payload = {"injuries": [
            {"team": {"id": "8"}, "athlete": {"id": "1234", "displayName": "Detroit Sample"},
             "status": "Out", "shortComment": "Ankle"},
            {"team": {"id": 1}, "athlete": {"id": "5678", "displayName": "Atlanta Sample"},
             "status": "Questionable"},
        ]}
        result = injury_rows(payload)
        self.assertEqual(set(result["team"]), {"DET", "ATL"})
        self.assertEqual(result.loc[result["team"] == "DET", "athlete_id"].iloc[0], "1234")
        self.assertEqual(result.loc[result["team"] == "DET", "note"].iloc[0], "Ankle")

    @patch("sources.memoized_json")
    @patch("sources.injuries")
    def test_missing_team_in_league_feed_uses_only_that_team_endpoint(self, league, fetch):
        league.return_value = (
            pd.DataFrame([{"player": "Hawk", "team": "ATL", "status": "Out",
                           "note": "", "athlete_id": "1"}]), FRESH)
        fetch.return_value = ({"injuries": []}, FRESH)
        rows, meta = selected_espn_injuries("DET", "ATL")
        self.assertTrue(meta["available"])
        self.assertFalse(meta["stale"])
        self.assertEqual(meta["checked_teams"], ["ATL", "DET"])
        self.assertEqual(rows["player"].tolist(), ["Hawk"])
        self.assertEqual(fetch.call_count, 1)
        self.assertIn("/teams/8/injuries", fetch.call_args.args[1])

    @patch("sources.memoized_json")
    @patch("sources.injuries")
    def test_team_response_without_team_identity_is_scoped_to_requested_team(self, league, fetch):
        league.return_value = (pd.DataFrame(), FRESH)
        def response(key, url, **kwargs):
            if "/teams/8/" in url:
                return ({"injuries": [{"athlete": {"displayName": "Sample Piston"},
                                       "status": "Day-to-day"}]}, FRESH)
            return ({"injuries": []}, FRESH)
        fetch.side_effect = response
        rows, meta = selected_espn_injuries("DET", "ATL")
        self.assertTrue(meta["available"])
        self.assertEqual(rows[["player", "team"]].values.tolist(),
                         [["Sample Piston", "DET"]])
        self.assertEqual(fetch.call_count, 2)

    @patch("sources.memoized_json")
    @patch("sources.injuries")
    def test_empty_both_team_reports_mean_zero_entries_not_healthy_roster(self, league, fetch):
        league.return_value = (pd.DataFrame(), FRESH)
        fetch.return_value = ({"injuries": []}, FRESH)
        rows, meta = selected_espn_injuries("DET", "ATL")
        self.assertTrue(meta["available"])
        self.assertTrue(rows.empty)
        self.assertEqual(meta["checked_teams"], ["ATL", "DET"])

    @patch("sources.memoized_json")
    @patch("sources.injuries")
    def test_incomplete_source_cannot_claim_available(self, league, fetch):
        league.side_effect = TimeoutError("league down")
        fetch.side_effect = [({"injuries": []}, FRESH), TimeoutError("team down")]
        rows, meta = selected_espn_injuries("DET", "ATL")
        self.assertFalse(meta["available"])
        self.assertTrue(meta["stale"])
        self.assertTrue(rows.empty)
        self.assertEqual(len(meta["checked_teams"]), 1)

    @patch("sources.memoized_json")
    @patch("sources.injuries")
    def test_unparseable_nonempty_report_is_not_an_empty_verified_report(self, league, fetch):
        league.return_value = (pd.DataFrame(), FRESH)
        fetch.return_value = ({"injuries": [{"unexpected": "not a status"}]}, FRESH)
        rows, meta = selected_espn_injuries("DET", "ATL")
        self.assertFalse(meta["available"])
        self.assertTrue(rows.empty)
        self.assertTrue(meta["stale"])

    @patch("sources.memoized_json")
    @patch("sources.injuries")
    def test_stale_team_feed_does_not_become_fresh(self, league, fetch):
        league.return_value = (pd.DataFrame(), FRESH)
        fetch.return_value = ({"injuries": []}, {**FRESH, "stale": True})
        rows, meta = selected_espn_injuries("DET", "ATL")
        self.assertFalse(meta["available"])
        self.assertTrue(meta["stale"])
        self.assertTrue(rows.empty)


if __name__ == "__main__":
    unittest.main()
