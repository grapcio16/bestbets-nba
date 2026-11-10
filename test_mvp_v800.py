"""BestBets MVP v8.0: navigation, final-only team analytics and user-input math."""
import unittest

import pandas as pd

from mvp_data import confirmed_finals,team_games,team_summary,league_table
from mvp_app import MAIN_PAGES,EXTRA_PAGES,ALL_PAGES,PAGE_HEADINGS


def fixture():
    start=pd.Timestamp("2026-10-25T01:00:00Z")
    teams=["BOS","NYK","GSW","SAS"]
    rows=[]
    for i in range(15):
        h=teams[i%4]
        a=teams[(i+1)%4]
        rows.append({
            "game_id":str(400+i),
            "start_utc":start+pd.Timedelta(days=i),
            "home":h,"away":a,"status_code":3,
            "home_score":120+i%7,"away_score":104+i%4,
        })
    return pd.DataFrame(rows)


class MvpDataTests(unittest.TestCase):
    def setUp(self):
        self.results=fixture()
        self.cutoff=pd.Timestamp("2026-11-10T23:00:00Z")

    def test_team_games_only_completed_before_cutoff(self):
        sample=self.results
        future=sample.iloc[[0]].copy()
        future["game_id"]="99999"
        future["start_utc"]=pd.Timestamp("2026-11-12T01:00:00Z")
        future["home_score"]=199
        live=sample.iloc[[0]].copy()
        live["game_id"]="99998"
        live["status_code"]=2
        mixed=pd.concat([sample,future,live,sample.iloc[[0]]],
                        ignore_index=True)
        finals=confirmed_finals(mixed,self.cutoff)
        self.assertEqual(len(finals),len(sample))
        self.assertNotIn("99999",finals["game_id"].tolist())
        self.assertNotIn("99998",finals["game_id"].tolist())

    def test_wins_losses_and_scorer_stats(self):
        finals=confirmed_finals(self.results,self.cutoff)
        games=team_games(finals,"BOS")
        self.assertGreater(len(games),0)
        self.assertTrue(set(games.columns)>={"margin","scored","allowed","win"})
        summary=team_summary(finals,"BOS")
        self.assertEqual(summary["wins"]+summary["losses"],summary["gp"])
        self.assertAlmostEqual(summary["win_pct"],100*summary["wins"]/summary["gp"])
        self.assertAlmostEqual(summary["margin"],summary["scored"]-summary["allowed"])
        self.assertLessEqual(summary["last5"],100)

    def test_empty_history_is_labeled_not_invented(self):
        missing=team_summary(pd.DataFrame(),"BOS")
        self.assertEqual(missing["gp"],0)
        self.assertIsNone(missing["margin"])
        self.assertIsNone(missing["scored"])
        self.assertIsNone(missing["win_pct"])

    def test_trend_rankings_observe_minimum_sample(self):
        finals=confirmed_finals(self.results,self.cutoff)
        leaders=league_table(finals,minimum_games=4)
        self.assertTrue((leaders["gp"]>=4).all())
        self.assertLessEqual(len(leaders),4)
        self.assertEqual(len(league_table(finals,minimum_games=100)),0)

    def test_no_status_or_scores_makes_no_fake_matches(self):
        bad=self.results.copy()
        bad["home_score"]=1
        self.assertTrue(confirmed_finals(bad,self.cutoff).empty)


class MvpNavigationTests(unittest.TestCase):
    def test_six_core_views_preserve_app_requirements(self):
        core=[v for v,_ in MAIN_PAGES]
        self.assertEqual(
            core,["home","props","games","simulations","players","teams"])
        self.assertEqual(len(set(core)),6)

    def test_reference_inspired_workspace_navigation_without_legacy_clutter(self):
        self.assertEqual(
            [v for v,_ in EXTRA_PAGES],
            ["favorites","trends","tools","settings"])
        self.assertEqual(set(PAGE_HEADINGS),set(ALL_PAGES))
        all_labels=" ".join(ALL_PAGES.values())
        for blocked in ("screenshot","kursy","performance tracker",
                        "backtesting","data lab"):
            self.assertNotIn(blocked,all_labels.lower())


if __name__=="__main__":
    unittest.main()
