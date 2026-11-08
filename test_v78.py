"""Test transparent opponent adjustment without any future game outcomes."""
import unittest
import pandas as pd
from opponent_ratings import regularized_matchup_means
from model_validation import evaluate_models, score_model


class OpponentRatingTests(unittest.TestCase):
    def setUp(self):
        rows=[]
        # Synthetic 100-game history; completed opponents share information.
        teams=["SAS","POR","DEN","IND","NYK","CLE","BKN","ATL","OKC","WAS"]
        for i in range(120):
            home=teams[i%len(teams)]
            away=teams[(i*3+1)%len(teams)]
            if home==away:
                away=teams[(i+1)%len(teams)]
            t=pd.Timestamp("2026-09-10T00:00:00Z")+pd.Timedelta(hours=12*i)
            rows.append({
                "game_id":str(401000000+i),"start_utc":t,
                "home":home,"away":away,"home_score":104+i%20,
                "away_score":109+i%9,"status_code":3})
        self.games=pd.DataFrame(rows)
        self.cutoff="2026-11-07T23:00:00Z"

    def test_regression_returns_finite_means(self):
        result=regularized_matchup_means(
            "SAS","POR",self.games,self.cutoff)
        self.assertIsNotNone(result)
        self.assertTrue(65<result["home"]<165)
        self.assertTrue(65<result["away"]<165)
        self.assertIn("badawczy",result["source"])

    def test_future_scores_have_no_effect(self):
        base=regularized_matchup_means("SAS","POR",self.games,self.cutoff)
        extra=self.games.copy()
        new=pd.DataFrame([{"game_id":"999999999",
            "start_utc":pd.Timestamp("2026-11-08T03:00:00Z"),
            "home":"SAS","away":"POR","home_score":190,"away_score":75,
            "status_code":3}])
        more=pd.concat([extra,new],ignore_index=True)
        again=regularized_matchup_means("SAS","POR",more,self.cutoff)
        self.assertAlmostEqual(base["home"],again["home"],places=10)
        self.assertAlmostEqual(base["away"],again["away"],places=10)

    def test_pregame_minimum_samples(self):
        early=self.games.head(5)
        result=regularized_matchup_means("SAS","POR",early,self.cutoff)
        self.assertIsNone(result)

    def test_unfinished_games_ignored(self):
        before=regularized_matchup_means("SAS","POR",self.games,self.cutoff)
        extra=pd.concat([self.games,
            pd.DataFrame([{"game_id":"999999998",
                "start_utc":pd.Timestamp("2026-10-07T03:00:00Z"),
                "home":"SAS","away":"POR",
                "home_score":180,"away_score":70,"status_code":2}])],
            ignore_index=True)
        after=regularized_matchup_means("SAS","POR",extra,self.cutoff)
        self.assertAlmostEqual(before["home"],after["home"],places=10)

    def test_holdout_compares_same_events(self):
        frame,summary=evaluate_models(self.games)
        # Evaluator requires sufficiently long date span, otherwise no bluff.
        if summary:
            self.assertEqual(
                len(frame[frame.model=="legacy"]),
                len(frame[frame.model=="opponent_ridge"]))
            self.assertEqual(set(summary),{"legacy","recency","opponent_ridge"})

    def test_score_metrics_symmetric(self):
        model={"home":118,"away":112}
        m=score_model(model,120,109)
        self.assertEqual(m["total_error"],1.0)
        self.assertEqual(m["winner_hit"],1)
        self.assertTrue(0<=m["brier"]<=1)


if __name__=="__main__":
    unittest.main()
