"""BestBets v7.18 Prediction Engine 2.0: no-lookahead/model parity tests."""
import unittest

import numpy as np
import pandas as pd

from core import normalize_logs, calc_projection, prop_probability
from prediction_engine_v2 import forecast_v2
from player_model_battle import chronological_battle


def player_logs(n=27, team="BOS", name="Research Player", start="2026-10-09T00:00:00Z"):
    dates=pd.date_range(start,periods=n,freq="D")
    rows=[]
    for i,date in enumerate(dates):
        minutes=22+(i%7)+ (4 if i>=n-5 else 0)
        pts=12+(i%10)+(4 if i>=n-5 else 0)
        reb=4+i%4
        ast=2+i%5
        shots=3+i%5
        makes=min(shots,1+i%3)
        rows.append(dict(
            PLAYER_NAME=name,PLAYER_ID=f"{team}-123",
            TEAM_ABBREVIATION=team,GAME_DATE=date, GAME_ID=f"{team}-{i}",
            MIN=float(minutes),PTS=float(pts),REB=float(reb),AST=float(ast),
            FG3M=float(makes),FG3A=float(shots),MATCHUP=f"{team} vs NYK",
        ))
    return normalize_logs(pd.DataFrame(rows))


class V2DistributionTests(unittest.TestCase):
    def setUp(self):
        self.logs=player_logs()
        self.asof=pd.Timestamp("2026-11-15T00:00:00Z")

    def test_deterministic_stochastic_engine(self):
        a=forecast_v2(self.logs,"PTS",18.5,self.asof)
        b=forecast_v2(self.logs,"PTS",18.5,self.asof)
        self.assertEqual(a,b)
        self.assertGreater(a["sample"],15)
        self.assertTrue(0<=a["p_over"]<=1)
        self.assertAlmostEqual(a["p_over"]+a["p_under"],1.,places=8)
        self.assertGreater(a["p90"],a["p10"])
        self.assertTrue(3<a["minutes"]<43)
        self.assertIn("NIEKALIBROWANE"," ".join(a["warnings"]))

    def test_no_future_leakage_and_line_changes_only_threshold(self):
        original=forecast_v2(self.logs,"PTS",17.5,self.asof)
        future=self.logs.iloc[[-1]].copy()
        future["GAME_DATE"]=pd.Timestamp("2026-12-01T00:00:00Z")
        future["GAME_ID"]="future"
        future["PTS"]=150.
        updated=forecast_v2(pd.concat([self.logs,future],ignore_index=True),
                             "PTS",17.5,self.asof)
        self.assertEqual(original,updated)
        harder=forecast_v2(self.logs,"PTS",24.5,self.asof)
        self.assertEqual(original["mean"],harder["mean"])
        self.assertGreaterEqual(original["p_over"],harder["p_over"])

    def test_all_five_markets_and_three_point_attempts(self):
        for market,line in [("PTS",19.5),("REB",5.5),("AST",3.5),
                            ("FG3M",1.5),("PRA",28.5)]:
            value=forecast_v2(self.logs,market,line,self.asof,draws=512)
            self.assertTrue(np.isfinite(value["mean"]))
            self.assertGreaterEqual(value["p90"],value["p10"])
            self.assertTrue(0<=value["p_over"]<=1)
        self.assertIn("Beta-Binomial",
                      forecast_v2(self.logs,"FG3M",1.5,self.asof)["method"])
        self.assertIn("wspólny indeks",
                      forecast_v2(self.logs,"PRA",28.5,self.asof)["method"])

    def test_missing_minutes_or_unvalidated_market_fails(self):
        few=self.logs.head(7).copy()
        with self.assertRaises(ValueError):
            forecast_v2(few,"PTS",15.5,self.asof)
        with self.assertRaises(ValueError):
            forecast_v2(self.logs,"MISSING",15.5,self.asof)
        with self.assertRaises(ValueError):
            forecast_v2(self.logs,"PTS",-1,self.asof)

    def test_transfer_old_club_not_counted_as_new_team_sample(self):
        new=self.logs.tail(5).copy()
        new["TEAM_ABBREVIATION"]="NYK"
        new["PLAYER_ID"]="NYK-123"
        new["GAME_DATE"]=pd.date_range("2026-11-06",periods=5,tz="UTC")
        new["GAME_ID"]=[f"traded-{i}" for i in range(5)]
        with self.assertRaises(ValueError):
            forecast_v2(pd.concat([self.logs,new],ignore_index=True),
                        "PTS",20.5,"2026-11-18T00:00:00Z")


class ModelBattleTests(unittest.TestCase):
    def setUp(self):
        self.logs=pd.concat([
            player_logs(25,team="BOS",name="Player One",start="2025-10-11T00:00:00Z"),
            player_logs(25,team="NYK",name="Player Two",start="2025-10-11T00:00:00Z"),
            player_logs(25,team="BOS",name="Player One",start="2026-10-11T00:00:00Z"),
            player_logs(25,team="LAL",name="Player Three",start="2026-10-11T00:00:00Z"),
        ],ignore_index=True)

    def test_same_cases_and_genuine_multiseason_brier(self):
        frame,summary=chronological_battle(self.logs,"PTS",max_cases=100)
        self.assertGreater(len(frame),20)
        self.assertEqual(summary["n_seasons"],2)
        self.assertEqual(summary["n_players"],3)
        self.assertEqual(summary["all"]["n"],len(frame))
        self.assertIn("NIE kurs bukmachera",summary["line_source"])
        self.assertFalse(summary["training_or_tuning_performed"])
        for k in ("legacy","v2"):
            self.assertTrue(0<=summary["all"][k]["brier"]<=1)
            self.assertTrue(0<=summary["all"][k]["over_under_accuracy"]<=1)
            self.assertTrue(np.isfinite(summary["all"][k]["mae"]))
        self.assertTrue(all((frame["line"]%1)==.5))

    def test_future_game_cannot_change_earlier_predictions(self):
        start=self.logs.copy()
        x,_=chronological_battle(start,"PTS",max_cases=300)
        extra=start.iloc[[0]].copy()
        extra["GAME_DATE"]=pd.Timestamp("2027-10-01T00:00:00Z")
        extra["GAME_ID"]="future"
        extra["PTS"]=122.
        future=pd.concat([start,extra],ignore_index=True)
        y,_=chronological_battle(future,"PTS",max_cases=300)
        self.assertEqual(x["gameid"].tolist(),y["gameid"].tolist()) if "gameid" in x else None
        pd.testing.assert_frame_equal(x,y,check_dtype=False)

    def test_less_than_ten_games_is_not_evaluated(self):
        short=player_logs(8)
        frame,summary=chronological_battle(short,"PTS")
        self.assertTrue(frame.empty)
        self.assertFalse(summary)


if __name__=="__main__":
    unittest.main()
