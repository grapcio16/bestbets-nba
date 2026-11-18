"""Pregame guardrails for research minutes and non-official ESPN OUT context."""
import unittest

import pandas as pd

from simulation_availability_v75 import availability_evidence
from simulation_context_v75 import simulation_inputs_v75
from test_simulation_context_v75 import fixtures


class AvailabilityV75Tests(unittest.TestCase):
    def setUp(self):
        self.game = {"game_id": "900000", "home": "BOS", "away": "NYK",
                     "start_utc": pd.Timestamp("2026-11-19T01:00:00Z")}
        self.now = pd.Timestamp("2026-11-18T15:00:00Z")
        self.meta = {"timestamp": "2026-11-18T14:50:00Z", "available": True,
                     "stale": False}
        self.players = pd.DataFrame([
            {"Drużyna": "BOS", "Zawodnik": "Sample Star", "Minuty": 30,
             "Próba występów": 7, "PTS": 25},
            {"Drużyna": "NYK", "Zawodnik": "Sample Guard", "Minuty": 28,
             "Próba występów": 7, "PTS": 20},
        ])
        games = [pd.Timestamp(f"2026-11-{d:02d}T01:00:00Z") for d in (11, 13, 15, 17)]
        self.logs = pd.DataFrame([{
            "GAME_ID": f"G{i}", "TEAM_ABBREVIATION": code,
            "PLAYER_NAME": name, "GAME_DATE": day, "MIN": minutes,
        } for i, day in enumerate(games)
            for code, name, minutes in (("BOS", "Sample Star", 30),
                                        ("NYK", "Sample Guard", 28))])

    def evidence(self, status="Out", *, meta=None, logs=None, historical=False,
                 report_team="BOS"):
        report = pd.DataFrame([{
            "Drużyna": report_team, "Zawodnik": "Sample Star", "Status ESPN": status,
        }])
        return availability_evidence(
            self.players, report, self.meta if meta is None else meta, self.game,
            logs=self.logs if logs is None else logs,
            now=self.now, historical=historical)

    def test_recent_out_changes_only_team_with_proven_participation(self):
        result = self.evidence()
        self.assertTrue(result["report_fresh"])
        self.assertEqual(result["score_delta"], {"home": -2.5, "away": 0.0})
        self.assertEqual(result["out_count"], {"home": 1, "away": 0})
        self.assertEqual(result["players"][("BOS", "samplestar")]["minutes"], 0.0)
        self.assertEqual(result["players"][("BOS", "samplestar")]["normal_minutes"], 30.0)
        self.assertEqual(result["players"][("NYK", "sampleguard")]["minutes"], 28.0)

    def test_uncertain_injury_is_only_an_risk_marker(self):
        for status in ("Questionable", "Doubtful", "Day-to-day", "Probable"):
            with self.subTest(status=status):
                result = self.evidence(status)
                self.assertEqual(result["score_delta"]["home"], 0)
                self.assertEqual(result["players"][("BOS", "samplestar")]["minutes"], 30.0)
                self.assertEqual(result["uncertain_count"]["home"],
                                 0 if status == "Probable" else 1)

    def test_stale_or_retrospective_report_never_alters_points(self):
        conditions = (
            {**self.meta, "stale": True},
            {**self.meta, "timestamp": "2026-11-18T09:00:00Z"},
            {**self.meta, "timestamp": "2026-11-18T16:00:00Z"},
            {**self.meta, "available": False},
        )
        for meta in conditions:
            with self.subTest(meta=meta):
                self.assertEqual(self.evidence(meta=meta)["score_delta"]["home"], 0)
        self.assertEqual(self.evidence(historical=True)["score_delta"]["home"], 0)

    def test_wrong_team_or_future_boxscores_do_not_create_absence(self):
        self.assertEqual(self.evidence(report_team="NYK")["score_delta"]["home"], 0)
        future = self.logs.copy()
        future["GAME_DATE"] = pd.Timestamp("2026-11-20T01:00:00Z")
        self.assertEqual(self.evidence(logs=future)["score_delta"]["home"], 0)

    def test_scarce_history_does_not_create_effect(self):
        one_game = self.logs[self.logs["GAME_ID"] == "G0"].copy()
        self.assertEqual(self.evidence(logs=one_game)["score_delta"]["home"], 0)
        small_sample = self.players.copy()
        small_sample.loc[0, "Próba występów"] = 2
        report = pd.DataFrame([{"Drużyna": "BOS", "Zawodnik": "Sample Star",
                                "Status ESPN": "Out"}])
        value = availability_evidence(small_sample, report, self.meta, self.game,
                                      logs=self.logs, now=self.now)
        self.assertEqual(value["score_delta"]["home"], 0)

    def test_injury_adjustment_only_changes_optional_v75_context(self):
        historical = fixtures(28)
        with_evidence = simulation_inputs_v75(historical, self.game,
                                               availability=self.evidence())
        unchanged = simulation_inputs_v75(historical, self.game)
        self.assertAlmostEqual(with_evidence["means"]["home"],
                               unchanged["means"]["home"] - 2.5)
        self.assertEqual(with_evidence["means"]["away"], unchanged["means"]["away"])
        self.assertEqual(with_evidence["context"]["v75_factors"]["injury_home_pts"], -2.5)
        self.assertFalse(unchanged["context"]["v75_factors"]["injuries_espn_fresh"])
        self.assertFalse(with_evidence["context"]["v75_factors"]["injuries_confirmed"])


if __name__ == "__main__":
    unittest.main()
