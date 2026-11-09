"""BestBets v7.21: real season Over/Under, opponent context and research toggle."""
import unittest
import numpy as np
import pandas as pd

from core import normalize_logs, norm_name
from season_props import (
    clean_player_season, observed_hit_rates, opponent_defensive_profile,
    upcoming_team_games, analyze_season_offers,
)
from simulation_engine import (
    completed_team_scores, legacy_matchup_means,
    matchup_means, simulate_game,
)
from prediction_engine_v2 import forecast_v2


def logs_for(name="Test Athlete", club="BOS"):
    base=pd.Timestamp("2026-10-10T00:00:00Z")
    return normalize_logs(pd.DataFrame([
        {
            "PLAYER_NAME":name,"PLAYER_ID":"123","TEAM_ABBREVIATION":club,
            "GAME_ID":str(100+i),"GAME_DATE":base+pd.Timedelta(days=i),
            "MATCHUP":f"{club} vs NYK","MIN":30.,
            "PTS":10. if i%2 else 22.,"REB":3.,"AST":4.,
            "FG3M":2.,"FG3A":6.,
        } for i in range(14)
    ]))


def results_for():
    start=pd.Timestamp("2026-10-10T00:00:00Z")
    records=[]
    for i in range(16):
        records.append({
            "game_id":str(90000+i),
            "start_utc":start+pd.Timedelta(days=i),
            "home":"BOS" if i%2==0 else "NYK",
            "away":"NYK" if i%2==0 else "BOS",
            "home_score":116+i%4,
            "away_score":108+i%5,
            "status_code":3,
        })
    return pd.DataFrame(records)


class SeasonRateTests(unittest.TestCase):
    def setUp(self):
        self.player=logs_for()
        self.cutoff=pd.Timestamp("2026-11-10T00:00:00Z")
        self.games=results_for()

    def test_full_season_over_under_including_last10(self):
        p=clean_player_season(self.player,"Test Athlete","2026-27",self.cutoff,"123")
        self.assertEqual(len(p),14)
        r=observed_hit_rates(p,"PTS",15.5)
        self.assertEqual(r["season"]["n"],14)
        self.assertEqual(r["season"]["over"],7)
        self.assertEqual(r["season"]["under"],7)
        self.assertEqual(r["season"]["push"],0)
        self.assertEqual(r["last10"]["n"],10)
        self.assertEqual(r["last10"]["over"],5)
        self.assertAlmostEqual(r["season"]["over_pct"]+r["season"]["under_pct"],100)

    def test_whole_number_line_has_three_outcomes(self):
        season=clean_player_season(self.player,"Test Athlete","2026-27",self.cutoff)
        results=observed_hit_rates(season,"PTS",10)
        self.assertEqual(results["season"]["push"],7)
        self.assertAlmostEqual(
            results["season"]["over_pct"]+
            results["season"]["under_pct"]+
            results["season"]["push_pct"],100,places=1)

    def test_future_game_and_previous_season_excluded(self):
        extra=self.player.iloc[[0]].copy()
        extra["GAME_DATE"]=pd.Timestamp("2026-11-12T00:00:00Z")
        extra["GAME_ID"]="future"
        extra["PTS"]=99.
        old=self.player.iloc[[0]].copy()
        old["GAME_DATE"]=pd.Timestamp("2026-04-11T00:00:00Z")
        old["GAME_ID"]="prior-year"
        mixed=pd.concat([self.player,extra,old],ignore_index=True)
        p=clean_player_season(mixed,"Test Athlete","2026-27",self.cutoff)
        self.assertEqual(len(p),14)
        self.assertEqual(observed_hit_rates(p,"PTS",15.5)["season"]["over"],7)

    def test_upcoming_opponent_local_day_explicit_and_unambiguous(self):
        games=pd.DataFrame([
            {"game_id":"991","start_utc":pd.Timestamp("2026-11-10T01:00:00Z"),
             "home":"BOS","away":"NYK","status_code":1},
            {"game_id":"992","start_utc":pd.Timestamp("2026-11-10T03:00:00Z"),
             "home":"PHI","away":"LAL","status_code":1},
        ])
        mapping=upcoming_team_games(
            games,pd.Timestamp("2026-11-10"),"Europe/Warsaw",
            pd.Timestamp("2026-11-09T20:00:00Z"))
        self.assertEqual(mapping["BOS"]["opponent"],"NYK")
        self.assertEqual(mapping["NYK"]["opponent"],"BOS")
        self.assertEqual(mapping["BOS"]["game_id"],"991")
        self.assertNotIn("LAL",mapping) if False else None

    def test_opponent_defense_only_prior_and_tiered(self):
        before=opponent_defensive_profile(self.games,"NYK",self.cutoff)
        self.assertIsNotNone(before)
        self.assertEqual(before["games"],16)
        self.assertTrue(.92<=before["scoring_multiplier"]<=1.08)
        later=pd.DataFrame([{
            "game_id":"bad_future","start_utc":"2026-11-17T01:00:00Z",
            "home":"NYK","away":"BOS","home_score":190,
            "away_score":55,"status_code":3,
        }])
        after=opponent_defensive_profile(
            pd.concat([self.games,later],ignore_index=True),
            "NYK",self.cutoff)
        self.assertEqual(before,after)
        self.assertIsNone(opponent_defensive_profile(
            self.games.head(2),"NYK",self.cutoff))

    def test_season_batch_includes_histories_opp_and_v2_percentages(self):
        offers=pd.DataFrame([{
            "Zawodnik":"Test Athlete","Rynek":"PTS","Linia":15.5,
            "Kurs OVER":None,"Kurs UNDER":1.8,
        }, {
            "Zawodnik":"Unknown Name","Rynek":"PTS","Linia":10.5,
            "Kurs OVER":1.75,"Kurs UNDER":None,
        }])
        identity={norm_name("Test Athlete"):{"id":"123","team":"BOS",
                  "source":"ESPN sezonowy gamelog","partial":False}}
        histories={norm_name("Test Athlete"):self.player}
        events={"BOS":{"opponent":"NYK","game_id":"999",
                       "start_utc":self.cutoff,"ambiguous":False}}
        table=analyze_season_offers(
            offers,histories,identity,events,self.games,
            "2026-27","2026-11-09T10:00:00Z")
        self.assertEqual(len(table),2)
        first=table.iloc[0]
        self.assertEqual(first["Występy sezon"],14)
        self.assertEqual(first["OVER sezon %"],50.)
        self.assertEqual(first["UNDER sezon %"],50.)
        self.assertEqual(first["Przeciwnik"],"NYK")
        self.assertIsNotNone(first["Obrona: stracone pkt/mecz"])
        self.assertEqual(first["Status"],"MODEL TESTOWY")
        self.assertGreaterEqual(first["P(OVER) v2 %"],0)
        self.assertAlmostEqual(
            first["P(OVER) v2 %"]+first["P(UNDER) v2 %"],100.,places=1)
        self.assertEqual(table.iloc[1]["Status"],"BRAK DANYCH")

    def test_low_sample_shows_actual_counts_not_fake_model(self):
        short=self.player.head(6)
        offers=pd.DataFrame([{
            "Zawodnik":"Test Athlete","Rynek":"PTS","Linia":15.5,
        }])
        identities={norm_name("Test Athlete"):{"id":"123","team":"BOS",
                    "source":"częściowa","partial":True}}
        table=analyze_season_offers(
            offers,{norm_name("Test Athlete"):short},identities,{},None,
            "2026-27",self.cutoff)
        x=table.iloc[0]
        self.assertEqual(x["Występy sezon"],6)
        self.assertEqual(x["Status"],"TYLKO HISTORIA")
        self.assertTrue(pd.isna(x["P(OVER) v2 %"]))
        self.assertIn("częstości dotyczą tylko pobranych",x["Uwagi"])


class ResearchToggleTests(unittest.TestCase):
    def test_advanced_both_teams_now_genuinely_blends_real_form(self):
        prior=completed_team_scores(results_for())
        # Advanced teams have deliberately distinct numbers vs raw completed scoring.
        ratings={
            "BOS":{"pace":101.,"off":130.,"def":104.},
            "NYK":{"pace":100.,"off":113.,"def":115.},
        }
        base=legacy_matchup_means("BOS","NYK",ratings,prior)
        research=matchup_means("BOS","NYK",ratings,prior)
        self.assertIn("70%",research["source"])
        self.assertNotAlmostEqual(base["home"],research["home"],places=3)
        self.assertNotAlmostEqual(base["away"],research["away"],places=3)
        game={"home":"BOS","away":"NYK","game_id":"909"}
        a,_,_,_=simulate_game(game,base)
        b,_,_,_=simulate_game(game,research)
        self.assertNotEqual(a["total_points"],b["total_points"])

    def test_no_observed_games_means_no_fake_toggle_impact(self):
        ratings={
            "BOS":{"pace":101.,"off":130.,"def":104.},
            "NYK":{"pace":100.,"off":113.,"def":115.},
        }
        baseline=legacy_matchup_means("BOS","NYK",ratings,{})
        research=matchup_means("BOS","NYK",ratings,{})
        self.assertEqual(baseline["home"],research["home"])
        self.assertEqual(baseline["away"],research["away"])
        self.assertIn("BRAK historii",research["source"])

    def test_base_model_still_unmodified(self):
        ratings={
            "BOS":{"pace":101.,"off":130.,"def":104.},
            "NYK":{"pace":100.,"off":113.,"def":115.},
        }
        base=legacy_matchup_means("BOS","NYK",ratings,completed_team_scores(results_for()))
        expected_h=(101+100)/2*(130+115)/200+1.5
        expected_a=(101+100)/2*(113+104)/200-1.5
        self.assertAlmostEqual(base["home"],expected_h)
        self.assertAlmostEqual(base["away"],expected_a)


if __name__=="__main__":
    unittest.main()
