"""v7.6 regression: model disagreement and rigorous bookmaker fixture matching."""
import unittest
import pandas as pd
import numpy as np

from forecast_quality import quality_report
from simulation_engine import match_real_odds, simulate_game


class ModelQualityTests(unittest.TestCase):
    def setUp(self):
        dates=[pd.Timestamp("2026-11-01T03:00:00Z")+pd.Timedelta(days=i)
               for i in range(6)]
        self.history={
            "SAS":[(d,115,108,"POR") for d in dates],
            "POR":[(d,109,114,"SAS") for d in dates],
        }
        self.game={"game_id":"401234567","home":"SAS","away":"POR",
                   "start_utc":"2026-11-08T04:00:00Z"}

    def test_missing_history_is_accurately_reported(self):
        report=quality_report(
            self.game,{"home":116,"away":111},None,self.history)
        self.assertFalse(report["alternate_available"])
        self.assertTrue(any("tylko 6" in x for x in report["alerts"]))
        self.assertTrue(any("Brak danych do niezależnego" in x
                            for x in report["alerts"]))

    def test_significant_favorite_flip_is_flagged(self):
        report=quality_report(
            self.game,{"home":118,"away":110},
            {"home":108,"away":119},self.history)
        self.assertTrue(report["favorite_flip"])
        self.assertEqual(report["margin_disagreement"],19.0)
        self.assertTrue(any("innych faworytów" in x for x in report["alerts"]))

    def test_agreement_with_enough_recent_games(self):
        extra=[pd.Timestamp("2026-11-07T01:00:00Z"),
               pd.Timestamp("2026-11-07T07:00:00Z")]
        for code in ("SAS","POR"):
            self.history[code]+=[(d,110,107,"SAS" if code=="POR" else "POR")
                                 for d in extra]
        report=quality_report(
            self.game,{"home":116,"away":110},
            {"home":115.5,"away":110.5},self.history)
        self.assertFalse(report["favorite_flip"])
        self.assertEqual(report["alerts"],[])
        self.assertEqual(report["history_games"]["SAS"],8)

    def test_stale_results_warn(self):
        stale={"SAS":[(pd.Timestamp("2026-09-01T03:00:00Z"),
                       115,112,"POR")]*10,
               "POR":[(pd.Timestamp("2026-09-01T03:00:00Z"),
                       110,112,"SAS")]*10}
        r=quality_report(self.game,{"home":112,"away":110},
                         {"home":112,"away":110},stale)
        self.assertTrue(any("ostatni znany" in f for f in r["alerts"]))


class OddsFixtureMatchingTests(unittest.TestCase):
    def setUp(self):
        self.game={"game_id":"401234568","home":"SAS","away":"POR",
                   "start_utc":"2026-11-08T04:00:00Z"}
        self.sim={"home_win_pct":45.0,"away_win_pct":55.0}
        self.offer={"home_team":"San Antonio Spurs",
                    "away_team":"Portland Trail Blazers",
                    "name":"Portland Trail Blazers",
                    "market":"h2h","odds":1.9,
                    "bookmaker":"Test fixture", "line":None}

    def test_reject_other_game_even_if_team_names_identical(self):
        other=dict(self.offer,start_utc="2026-11-08T09:00:00Z")
        valid=dict(self.offer,start_utc="2026-11-08T04:20:00Z")
        rows=match_real_odds(pd.DataFrame([other,valid]),self.game,self.sim,
                             np.ones(5000,dtype=int)*110,
                             np.ones(5000,dtype=int)*111)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows.iloc[0]["Kurs"],1.9)

    def test_reject_reversed_home_away(self):
        wrong=dict(self.offer,start_utc=self.game["start_utc"],
                   home_team="Portland Trail Blazers",
                   away_team="San Antonio Spurs")
        rows=match_real_odds(pd.DataFrame([wrong]),self.game,self.sim,
                             np.ones(5000,dtype=int)*110,
                             np.ones(5000,dtype=int)*111)
        self.assertTrue(rows.empty)

    def test_fixed_seed_produces_same_scores(self):
        mean={"home":115,"away":114,"source":"unit test"}
        a,_,home_a,away_a=simulate_game(self.game,mean)
        b,_,home_b,away_b=simulate_game(self.game,mean)
        np.testing.assert_array_equal(home_a,home_b)
        np.testing.assert_array_equal(away_a,away_b)
        self.assertEqual(a["home_win_pct"]+a["away_win_pct"],100.0)
        self.assertFalse(np.any(home_a==away_a))


if __name__=="__main__":
    unittest.main()
