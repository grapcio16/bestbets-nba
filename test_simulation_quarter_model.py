"""No invented Q1-Q4: ESPN final line-score parser + pre-tipoff matchup profiles."""
import unittest
import pandas as pd
import numpy as np

from simulation_sources import parse_espn_quarter_linescores
from simulation_quarter_model import pregame_quarter_evidence
from simulation_flow import conditional_flow


def espn_event(eid, home=(31, 24, 34, 25), away=(20, 29, 36, 30),
               overtime=False, incorrect_total=False, complete=True):
    def competitor(side, quarter):
        values = [{"period": i + 1, "value": n}
                  for i, n in enumerate(quarter)]
        if overtime:
            values.append({"period": 5, "value": 12})
        return {"homeAway": side, "score": str(sum(quarter)
                    + (12 if overtime else 0) + (1 if incorrect_total else 0)),
                "linescores": values, "team": {"abbreviation": side.upper()}}
    return {"id": str(eid), "status": {"type": {"completed": complete}},
            "competitions": [{
                "competitors": [competitor("home", home),
                                competitor("away", away)],
                "status": {"type": {"completed": complete}}
            }]}


def observed_history():
    records = []
    for i in range(9):
        # DET often scores much more during Q3 than Q1.
        a = [20 + (i % 3), 29 - (i % 2), 39 + (i % 2), 22]
        ah = [27, 26, 28, 28]
        row = {"game_id": str(401800000 + i),
               "start_utc": pd.Timestamp("2026-11-01", tz="UTC")
                            + pd.Timedelta(days=int(i)),
               "away": "DET", "home": "ORL",
               "away_score": sum(a), "home_score": sum(ah),
               "status_code": 3}
        for q in range(1, 5):
            row[f"away_q{q}"] = a[q-1]
            row[f"home_q{q}"] = ah[q-1]
        records.append(row)
    for i in range(9):
        # ATL often scores more during Q1 than Q3.
        h = [36 + i % 2, 29, 23 + i % 2, 25]
        a = [24, 25, 26, 27]
        row = {"game_id": str(401900000 + i),
               "start_utc": pd.Timestamp("2026-11-01", tz="UTC")
                            + pd.Timedelta(days=int(i)),
               "away": "BKN", "home": "ATL",
               "away_score": sum(a), "home_score": sum(h),
               "status_code": 3}
        for q in range(1, 5):
            row[f"away_q{q}"] = a[q-1]
            row[f"home_q{q}"] = h[q-1]
        records.append(row)
    return pd.DataFrame(records)


GAME = {"away": "DET", "home": "ATL",
        "start_utc": pd.Timestamp("2026-11-22 00:00:00", tz="UTC")}


class ESPNQuarterEvidenceTest(unittest.TestCase):
    def test_exact_four_quarters_only(self):
        valid = espn_event(401234567)
        raw = {"events": [
            valid,
            espn_event(401234568, overtime=True),
            espn_event(401234569, incorrect_total=True),
            espn_event(401234570, complete=False),
            espn_event(401234571, home=(0, 0, 0, 0)),
        ]}
        result = parse_espn_quarter_linescores(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["game_id"], "401234567")
        self.assertEqual(result[0]["home_q1"], 31)
        self.assertEqual(result[0]["away_q3"], 36)
        self.assertEqual(len(parse_espn_quarter_linescores({})), 0)
        self.assertEqual(len(parse_espn_quarter_linescores(None)), 0)

    def test_no_regulation_data_or_short_sample_means_no_forecast(self):
        history = observed_history()
        absent = pregame_quarter_evidence(history.drop(columns=["home_q4"]), GAME)
        self.assertFalse(absent["available"])
        too_few = history[history["away"].ne("DET") |
                          history["start_utc"].lt(pd.Timestamp("2026-11-06", tz="UTC"))]
        sample = pregame_quarter_evidence(too_few, GAME)
        self.assertFalse(sample["available"])
        self.assertIn("Za mało", sample["reason"])
        self.assertLess(sample["away_sample"], 6)

    def test_no_future_leak_and_real_nonuniform_quarter_shapes(self):
        history = observed_history()
        evidence = pregame_quarter_evidence(history, GAME)
        self.assertTrue(evidence["available"], evidence)
        self.assertEqual(evidence["away_sample"], 9)
        self.assertEqual(evidence["home_sample"], 9)
        self.assertEqual(evidence["league_games"], 18)
        self.assertAlmostEqual(sum(evidence["away"]), 1, places=5)
        self.assertAlmostEqual(sum(evidence["home"]), 1, places=5)
        self.assertGreater(evidence["away"][2], evidence["away"][0] + .03)
        self.assertGreater(evidence["home"][0], evidence["home"][2] + .03)
        # The next day's final score cannot enter a prediction for Nov 22.
        later = history.iloc[-1].copy()
        later["game_id"] = "401999999"
        later["start_utc"] = pd.Timestamp("2026-11-23", tz="UTC")
        later["home_q1"] = 70
        later["home_q2"] = 10
        later["home_q3"] = 10
        later["home_q4"] = 10
        later["home_score"] = 100
        added = pd.concat([history, pd.DataFrame([later])], ignore_index=True)
        self.assertEqual(evidence, pregame_quarter_evidence(added, GAME))

    def test_five_thousand_outcomes_are_unchanged_and_quarters_not_flat(self):
        evidence = pregame_quarter_evidence(observed_history(), GAME)
        rng = np.random.default_rng(17)
        away = rng.integers(99, 129, size=5000)
        home = rng.integers(102, 132, size=5000)
        copy_away, copy_home = away.copy(), home.copy()
        flow = conditional_flow(away, home, game_id="401999555",
                                model_id="research_form_v74",
                                quarter_evidence=evidence)
        self.assertTrue(flow["quarter_model"]["available"])
        self.assertEqual(flow["quarter_model"]["away_sample"], 9)
        self.assertEqual(flow["method"], "conditional_espn_quarters_v1")
        actual = flow["quarters"]
        self.assertGreater(actual[2]["away_mean"], actual[0]["away_mean"] + 3)
        self.assertGreater(actual[0]["home_mean"], actual[2]["home_mean"] + .8)
        self.assertAlmostEqual(sum(q["away_mean"] for q in actual),
                               away.mean(), delta=.05)
        self.assertAlmostEqual(sum(q["home_mean"] for q in actual),
                               home.mean(), delta=.05)
        self.assertAlmostEqual(flow["timeline"][-1]["margin_mean"],
                               (home-away).mean(), delta=.02)
        np.testing.assert_array_equal(copy_away, away)
        np.testing.assert_array_equal(copy_home, home)
        self.assertEqual(flow, conditional_flow(away, home,
                         game_id="401999555", model_id="research_form_v74",
                         quarter_evidence=evidence))

    def test_missing_evidence_suppresses_all_quarter_probabilities_and_points(self):
        a = np.full(5000, 112)
        h = np.full(5000, 115)
        empty = conditional_flow(a, h, game_id="401", model_id="legacy_v72")
        self.assertTrue(empty["available"])
        self.assertFalse(empty["quarter_model"]["available"])
        for q in empty["quarters"]:
            self.assertIsNone(q["away_mean"])
            self.assertIsNone(q["home_mean"])
            self.assertIsNone(q["away_outscores_pct"])
            self.assertIsNone(q["home_outscores_pct"])
            self.assertIsNone(q["tie_pct"])
        self.assertAlmostEqual(empty["timeline"][-1]["margin_mean"], 3.0)


if __name__ == "__main__":
    unittest.main()
