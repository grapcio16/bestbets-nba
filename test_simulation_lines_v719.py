"""Regression: BestBets v7.19 game line scenario interpretation and no lookahead."""
import unittest

import numpy as np
import pandas as pd

from simulation_lines import (
    alternate_scenarios, score_line_probabilities,
    quoted_price_diagnostics, scenario_line_table,
)
from simulation_engine import completed_team_scores, legacy_matchup_means, simulate_game


class PregameLineTests(unittest.TestCase):
    def test_totals_and_home_spread_sign(self):
        h=np.r_[np.full(2000,110),np.full(3000,115)]
        a=np.r_[np.full(2000,100),np.full(3000,110)]
        p=score_line_probabilities(h,a,210,-6.5)
        self.assertEqual(p["n"],5000)
        self.assertAlmostEqual(p["total_over"],.6)
        self.assertAlmostEqual(p["total_push"],.4)
        self.assertAlmostEqual(p["total_under"],0)
        self.assertAlmostEqual(p["home_cover"],.4)
        self.assertAlmostEqual(p["away_cover"],.6)
        self.assertAlmostEqual(p["spread_push"],0)
        self.assertAlmostEqual(p["total_over"]+p["total_under"]+p["total_push"],1)
        self.assertAlmostEqual(p["home_cover"]+p["away_cover"]+p["spread_push"],1)

    def test_integer_spread_push_and_quarter_line(self):
        h=np.r_[np.full(2000,110),np.full(3000,115)]
        a=np.r_[np.full(2000,100),np.full(3000,110)]
        p=score_line_probabilities(h,a,210,-10)
        self.assertAlmostEqual(p["spread_push"],.4)
        self.assertAlmostEqual(p["away_cover"],.6)
        self.assertAlmostEqual(p["home_cover"],0)

    def test_price_with_push_and_unquoted_is_not_invented(self):
        self.assertIsNone(quoted_price_diagnostics(.4,.3,""))
        p=quoted_price_diagnostics(.4,.3,"1,85")
        self.assertEqual(p["odds"],1.85)
        self.assertAlmostEqual(p["conditional_break_even"],.7/1.85)
        self.assertAlmostEqual(p["model_ev_pct"],100*(.4*1.85+.3-1))
        for value in ("0.99","foo","Inf","101"):
            with self.assertRaises(ValueError):
                quoted_price_diagnostics(.4,0,value)

    def test_invalid_draws_or_lines_fail(self):
        with self.assertRaises(ValueError):
            score_line_probabilities([110],[100],210.5,-5.5)
        with self.assertRaises(ValueError):
            score_line_probabilities(np.ones(5000)*110,np.ones(5000)*100,500,-5.5)
        with self.assertRaises(ValueError):
            score_line_probabilities(np.ones(5000)*110,np.ones(5000)*100,210.5,float("nan"))

    def test_exact_counts_from_actual_simulation(self):
        game={"game_id":"fixed","home":"BOS","away":"NYK"}
        model={"home":112.,"away":109.,"source":"unit"}
        summary,_,home,away=simulate_game(game,model)
        p=score_line_probabilities(home,away,221.5,-4.5)
        self.assertAlmostEqual(
            p["total_mean"],np.mean(home+away),places=9)
        self.assertAlmostEqual(
            p["total_over"]+p["total_under"]+p["total_push"],1,places=8)
        self.assertAlmostEqual(p["margin_mean"],np.mean(home-away),places=8)


class ResearchCandidateTests(unittest.TestCase):
    def setUp(self):
        start=pd.Timestamp("2026-10-01T00:00:00Z")
        self.hist=pd.DataFrame([{
            "game_id":str(i),"start_utc":start+pd.Timedelta(days=i),
            "status_code":3,
            "home":"BOS" if i%2==0 else "NYK",
            "away":"NYK" if i%2==0 else "BOS",
            "home_score":110+i%8, "away_score":104+i%9,
        } for i in range(24)])
        self.game={"game_id":"future","start_utc":pd.Timestamp("2026-11-10T00:00:00Z"),
                   "home":"BOS","away":"NYK"}

    def test_candidate_not_copied_from_later_game(self):
        original=alternate_scenarios(self.hist,self.game,pd.DataFrame())
        self.assertTrue(original)
        future=pd.DataFrame([{
            "game_id":"future_completed",
            "start_utc":pd.Timestamp("2026-11-12T00:00:00Z"),
            "status_code":3,"home":"BOS","away":"NYK",
            "home_score":192,"away_score":70,
        }])
        new=alternate_scenarios(
            pd.concat([self.hist,future],ignore_index=True),
            self.game,pd.DataFrame())
        self.assertEqual(set(original),set(new))
        for k in original:
            self.assertEqual(original[k]["home"],new[k]["home"])
            self.assertEqual(original[k]["away"],new[k]["away"])

    def test_real_line_scenario_list_start_with_exact_card(self):
        models=alternate_scenarios(self.hist,self.game)
        self.assertIn("Podstawowy v7.2",models)
        summary,_,h,a=simulate_game(self.game,models["Podstawowy v7.2"])
        table,review=scenario_line_table(
            self.game,self.hist,pd.DataFrame(),221.5,-5.5,summary,h,a)
        self.assertGreaterEqual(len(table),2)
        self.assertEqual(table.iloc[0]["Wariant"],"Na karcie meczu")
        self.assertAlmostEqual(table.iloc[0]["Średnia suma"],summary["total_points"],places=1)
        self.assertEqual(table.iloc[0]["P(gospodarze wygrają) (%)"],summary["home_win_pct"])
        self.assertTrue(review["available"])
        self.assertTrue(all(c in table.columns for c in (
            "Wariant","Suma OVER (%)","Gospodarze pokryją (%)")))

    def test_missing_history_reports_no_consensus(self):
        game=self.game.copy()
        h=np.full(5000,112);a=np.full(5000,106)
        frame,review=scenario_line_table(
            game,pd.DataFrame(),pd.DataFrame(),218.5,-6.5,
            {"home_win_pct":100.},h,a)
        self.assertEqual(len(frame),1)
        self.assertFalse(review["available"])
        self.assertIn("Brak",review["warning"])


if __name__=="__main__":
    unittest.main()
