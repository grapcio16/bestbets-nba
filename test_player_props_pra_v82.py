"""PRA = points + rebounds + assists in the SAME completed NBA appearance.

Product tests require visible shorthand and honest full-season Over/Under counts.
No network, synthetic forecasts, or odds calculations are used here.
"""
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from core import normalize_logs,STAT_NAMES
from prop_search import parse_prop_query,parse_prop_batch
from season_props import clean_player_season,observed_hit_rates
from mvp_player_card import MARKET_TEXT


class PlayerPropsPraTests(unittest.TestCase):
    def test_english_and_polish_pra_shortcuts(self):
        cases=[
            ("Jayson Tatum over 35.5 PRA","OVER",35.5),
            ("Jayson Tatum under 35,5 PRA","UNDER",35.5),
            ("Jayson Tatum powyżej 35,5 punkty+zbiórki+asysty","OVER",35.5),
            ("Jayson Tatum poniżej 35,5 punktów+zbiórek+asyst","UNDER",35.5),
            ("Jayson Tatum over 35.5 p+r+a","OVER",35.5),
            ("Jayson Tatum over 35.5 PTS+REB+AST","OVER",35.5),
            ("Jayson Tatum over 35.5 points+rebounds+assists","OVER",35.5),
            ("Jayson Tatum powyżej 35,5 punkty, zbiórki i asysty","OVER",35.5),
        ]
        for query,side,line in cases:
            with self.subTest(query=query):
                match=parse_prop_query(query)
                self.assertEqual((match["market"],match["side"],match["line"]),
                                 ("PRA",side,line))

    def test_same_game_pra_sum_over_and_under_counts(self):
        raw=pd.DataFrame([
            {"PLAYER_NAME":"Jayson Tatum","PLAYER_ID":"1628369",
             "TEAM_ABBREVIATION":"BOS","GAME_ID":str(i),
             "GAME_DATE":pd.Timestamp("2026-10-22T00:00:00Z")+
                        pd.Timedelta(days=i),
             "MIN":"34:00","PTS":p,"REB":r,"AST":a,"FG3M":2.,
             "PRA":999.,  # stale provider statistic must be ignored
             "MATCHUP":"BOS vs. NYK"}
            for i,(p,r,a) in enumerate(
                ((20,7,4),(28,10,6),(31,5,7),(14,9,2),(22,8,5)))
        ])
        history=clean_player_season(
            normalize_logs(raw),"Jayson Tatum","2026-27",
            "2026-11-11T00:00:00Z","1628369")
        self.assertEqual(history["PRA"].tolist(),[31,44,43,25,35])
        rate=observed_hit_rates(history,"PRA",35.5)
        self.assertEqual(rate["season"]["n"],5)
        self.assertEqual(rate["season"]["over"],2)
        self.assertEqual(rate["season"]["under"],3)
        self.assertEqual(rate["season"]["over_pct"],40.)
        self.assertEqual(rate["season"]["under_pct"],60.)
        self.assertEqual(rate["season"]["mean"],35.6)
        self.assertAlmostEqual(
            history[["PTS","REB","AST"]].mean().sum(),35.6)

    def test_missing_component_does_not_fake_pra_value(self):
        rows=pd.DataFrame([
            {"PLAYER_NAME":"Jayson Tatum","PLAYER_ID":"1628369",
             "TEAM_ABBREVIATION":"BOS","GAME_ID":"100",
             "GAME_DATE":"2026-10-21","MIN":32,
             "PTS":27,"REB":9,"AST":np.nan,"FG3M":2,
             "PRA":1234},
            {"PLAYER_NAME":"Jayson Tatum","PLAYER_ID":"1628369",
             "TEAM_ABBREVIATION":"BOS","GAME_ID":"101",
             "GAME_DATE":"2026-10-22","MIN":31,
             "PTS":22,"REB":7,"AST":5,"FG3M":3,
             "PRA":1234},
        ])
        # Specifically bypass normalization: production source can include
        # a stale precomputed PRA field, which must be recomputed regardless.
        season=clean_player_season(
            rows,"Jayson Tatum","2026-27",
            "2026-11-11T00:00:00Z","1628369")
        self.assertTrue(pd.isna(season["PRA"].iloc[0]))
        self.assertEqual(season["PRA"].iloc[1],34)
        rates=observed_hit_rates(season,"PRA",33.5)
        self.assertEqual(rates["season"]["n"],1)
        self.assertEqual(rates["season"]["over"],1)
        self.assertEqual(rates["season"]["under"],0)

    def test_batch_mixed_stats_separates_pra(self):
        queries,errors=parse_prop_batch(
            "Jayson Tatum over 35,5 PRA\n"
            "Jayson Tatum under 25.5 points\n"
            "Jayson Tatum over 3,5 assists")
        self.assertEqual(errors,[])
        self.assertEqual([x["market"] for x in queries],
                         ["PRA","PTS","AST"])

    def test_pra_visible_on_player_props_and_dropdown(self):
        text=Path("mvp_prop_ui.py").read_text(encoding="utf8")
        card=Path("mvp_player_card.py").read_text(encoding="utf8")
        theme=Path("mvp_theme.py").read_text(encoding="utf8")
        self.assertIn('("PRA · 35.5", "Jayson Tatum over 35.5 PRA")',text)
        self.assertIn("Jak wpisać PRA:",text)
        self.assertIn("bbm-pra-chip",text)
        self.assertIn("bbm-pra-breakdown",card)
        self.assertIn("bbm-pra-breakdown",theme)
        self.assertIn("PRA",MARKET_TEXT)
        self.assertIn("PRA",STAT_NAMES)


if __name__=="__main__":
    unittest.main()
