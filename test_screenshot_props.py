"""Validate the screenshot-market import and selected-player calculations."""
import unittest
import pandas as pd
from screenshot_props import (screenshot_props,market_ledger,player_snapshot,
                              player_market_report,SNAPSHOT_ASOF_UTC)


class ScreenshotPropsTests(unittest.TestCase):
    def test_exact_volume_and_market_counts(self):
        offers=screenshot_props()
        self.assertEqual(len(offers),53)
        self.assertEqual(offers.groupby("market").size().to_dict(),
                         {"PTS":13,"FG3M":10,"AST":9,"REB":12,"PRA":9})
        self.assertEqual(len(market_ledger(offers)),106)
        self.assertEqual(offers[["player","market"]].duplicated().sum(),0)

    def test_aaron_gordon_lines_and_prices(self):
        g=player_snapshot("Aaron Gordon")
        self.assertEqual(len(g),5)
        actual={r["market"]:(r["line"],r["over"],r["under"])
                for r in g.to_dict("records")}
        self.assertEqual(actual,{
            "PTS":(13.5,1.93,1.72),
            "FG3M":(1.5,1.98,1.68),
            "AST":(2.5,1.82,1.82),
            "REB":(5.5,1.81,1.83),
            "PRA":(21.5,1.81,1.79),
        })

    def test_name_normalization_oubre_jr(self):
        self.assertEqual(len(player_snapshot("Kelly Oubre Jr.")),3)

    def test_missing_logs_shows_market_prices_without_fabricating_predictions(self):
        summary=player_market_report(pd.DataFrame(),player_snapshot("Aaron Gordon"))
        self.assertEqual(len(summary),5)
        self.assertTrue(summary["Prognoza"].isna().all())
        self.assertTrue(summary["OVER model %"].isna().all())
        self.assertEqual(summary["OVER kurs"].iloc[0],1.93)

    def test_future_game_not_used_for_archive(self):
        samples=pd.DataFrame([
            {"GAME_DATE":pd.Timestamp("2026-11-06T03:00:00Z"),"MIN":32,"PTS":15,"REB":6,
             "AST":3,"FG3M":2,"PRA":24},
            {"GAME_DATE":SNAPSHOT_ASOF_UTC+pd.Timedelta(hours=5),"MIN":32,"PTS":50,
             "REB":20,"AST":10,"FG3M":7,"PRA":80},
        ])
        summary=player_market_report(samples,player_snapshot("Aaron Gordon"))
        self.assertTrue((summary["Występy"]==1).all())
        self.assertTrue(summary["Prognoza"].isna().all())

if __name__=="__main__":
    unittest.main()
