"""Resilient live NBA availability retrieval, entirely offline synthetic QA."""
import unittest
from unittest.mock import patch

import pandas as pd

from simulation_injury_sources import _team_fetch, selected_matchup_availability


def rows(team, status="Out", name="Sample Player"):
    return pd.DataFrame([{"team": team, "player": name, "status": status,
                          "note": "", "athlete_id": "123456"}])


class InjurySourcesTest(unittest.TestCase):
    def test_recent_league_snapshot_supplies_matchup_without_team_requests(self):
        team_calls = []
        now = pd.Timestamp("2026-11-23T20:00:00Z")
        all_rows = pd.concat([rows("POR"), rows("PHI", "Questionable")])
        result, meta = selected_matchup_availability(
            "POR", "PHI", now=now,
            league_fetch=lambda: (all_rows, {"timestamp": "2026-11-23T19:58:00Z",
                                             "stale": False}),
            team_fetch=lambda team: team_calls.append(team))
        self.assertEqual(set(result["team"]), {"POR", "PHI"})
        self.assertEqual(meta["source"], "ESPN liga")
        self.assertTrue(meta["available"])
        self.assertEqual(team_calls, [])

    def test_broken_league_uses_both_verified_team_endpoints(self):
        def unavailable():
            raise RuntimeError("ESPN league unavailable")
        observed = []
        def teams(code):
            observed.append(code)
            return rows(code)
        got, meta = selected_matchup_availability(
            "POR", "PHI", league_fetch=unavailable,
            team_fetch=teams, now="2026-11-23T20:00:00Z")
        self.assertEqual(set(observed), {"POR", "PHI"})
        self.assertEqual(set(got["team"]), {"POR", "PHI"})
        self.assertEqual(meta["source"], "ESPN drużyny")
        self.assertEqual(set(meta["coverage_teams"]), {"POR", "PHI"})
        self.assertFalse(meta["partial"])

    def test_one_team_failure_preserves_its_explicit_out_only(self):
        def teams(code):
            if code == "PHI":
                raise RuntimeError("outage")
            return rows(code)
        got, meta = selected_matchup_availability(
            "POR", "PHI",
            league_fetch=lambda: (pd.DataFrame(), {"stale": True}),
            team_fetch=teams, now="2026-11-23T20:00:00Z")
        self.assertEqual(got["team"].tolist(), ["POR"])
        self.assertEqual(meta["coverage_teams"], ["POR"])
        self.assertTrue(meta["partial"])

    def test_no_feed_does_not_fake_a_healthy_roster(self):
        def bad(*_args):
            raise RuntimeError("offline")
        got, meta = selected_matchup_availability(
            "POR", "PHI", league_fetch=bad, team_fetch=bad)
        self.assertTrue(got.empty)
        self.assertFalse(meta["available"])
        self.assertTrue(meta["stale"])

    def test_espn_team_schema_preserves_team_and_player_id(self):
        example = {"injuries": [
            {"athlete": {"id": "555001", "displayName": "Example Out"},
             "status": "Out",
             "details": {"detail": "Knee"}},
            {"athlete": {"id": "555002", "displayName": "Example Probable"},
             "status": "Probable"}
        ]}
        with patch("simulation_injury_sources.http_json", return_value=example):
            df = _team_fetch("POR")
        self.assertEqual(len(df), 2)
        self.assertEqual(set(df["team"]), {"POR"})
        self.assertEqual(set(df["athlete_id"]), {"555001", "555002"})

    def test_report_with_no_matchup_entries_still_checks_both_teams(self):
        calls = []
        def team_fetch(team):
            calls.append(team)
            return pd.DataFrame(columns=["team", "player", "status", "athlete_id", "note"])
        got, meta = selected_matchup_availability(
            "POR", "PHI",
            league_fetch=lambda: (rows("NYK"), {
                "timestamp": "2026-11-23T20:00:00Z", "stale": False
            }),
            team_fetch=team_fetch, now="2026-11-23T20:00:00Z")
        self.assertTrue(got.empty)
        self.assertEqual(set(calls), {"POR","PHI"})
        self.assertTrue(meta["available"])
        self.assertEqual(meta["source"], "ESPN drużyny")


if __name__ == "__main__":
    unittest.main()
