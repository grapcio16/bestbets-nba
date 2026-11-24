"""Strict synthetic ESPN boxscore ingestion tests for V8 Shadow."""
import unittest
import pandas as pd

from v8_shadow.data import parse_espn_summary, collect_team_boxes, _team_box_stats

BASE = {"game_id":"401910038","season":"2026-27",
        "start_utc":"2026-11-23T23:30:00Z",
        "home":"IND","away":"OKC","home_score":125,
        "away_score":120,"status_code":3}


def source():
    def stats(fgm, fga, ftm, fta, oreb, to):
        return [
            {"name":"fieldGoalsMade-fieldGoalsAttempted",
             "displayValue":f"{fgm}-{fga}"},
            {"name":"freeThrowsMade-freeThrowsAttempted",
             "displayValue":f"{ftm}-{fta}"},
            {"name":"offensiveRebounds","displayValue":str(oreb)},
            {"name":"turnovers","displayValue":str(to)}
        ]
    return {
        "header":{"id":BASE["game_id"],"competitions":[{
            "id":BASE["game_id"],"status":{"type":{"completed":True}},
            "competitors":[
                {"homeAway":"home","team":{"abbreviation":"IND"},
                 "score":"125","linescores":[1,2,3,4]},
                {"homeAway":"away","team":{"abbreviation":"OKC"},
                 "score":"120","linescores":[1,2,3,4]},
            ]}]},
        "boxscore":{"teams":[
            {"team":{"abbreviation":"OKC"},
             "statistics":stats(44,90,19,25,12,11)},
            {"team":{"abbreviation":"IND"},
             "statistics":stats(46,91,18,23,10,12)},
        ]}
    }


class DataTest(unittest.TestCase):
    def test_complete_team_evidence_and_physical_possessions(self):
        parsed = parse_espn_summary(source(),BASE)
        self.assertEqual(parsed["home_score"],125)
        self.assertEqual(parsed["away_score"],120)
        self.assertEqual(parsed["home_fga"],91)
        self.assertEqual(parsed["away_tov"],11)
        self.assertAlmostEqual(parsed["home_poss"],103.12,2)
        self.assertAlmostEqual(parsed["away_poss"],100.0,2)

    def test_score_and_team_identity_never_inferred(self):
        sample = source()
        sample["header"]["competitions"][0]["competitors"][0]["score"] = "116"
        with self.assertRaisesRegex(ValueError,"score mismatch"):
            parse_espn_summary(sample,BASE)
        sample = source()
        sample["boxscore"]["teams"][0]["team"]["abbreviation"] = "BOS"
        with self.assertRaisesRegex(ValueError,"both team"):
            parse_espn_summary(sample,BASE)

    def test_reject_overtime_and_missing_possessions_inputs(self):
        sample=source()
        sample["header"]["competitions"][0]["competitors"][0]["linescores"].append(5)
        with self.assertRaisesRegex(ValueError,"overtime"):
            parse_espn_summary(sample,BASE)
        sample=source()
        sample["boxscore"]["teams"][0]["statistics"] = []
        with self.assertRaisesRegex(ValueError,"required"):
            parse_espn_summary(sample,BASE)

    def test_team_fga_fta_outliers_block_training(self):
        sample=source()
        sample["boxscore"]["teams"][0]["statistics"][0]["displayValue"]="22-999"
        with self.assertRaises(ValueError):
            parse_espn_summary(sample,BASE)

    def test_collector_omits_previously_persisted_and_failed(self):
        df=pd.DataFrame([BASE, {**BASE,"game_id":"401910039"}])
        finished, report=collect_team_boxes(
            df, existing_ids=["401910038"], limit=2,
            fetch=lambda g: {**BASE,"game_id":g["game_id"]})
        self.assertEqual(report["checked"],1)
        self.assertEqual(report["accepted"],1)
        self.assertEqual(finished[0]["game_id"],"401910039")

    def test_collector_no_fabricated_defaults(self):
        df=pd.DataFrame([{**BASE,"status_code":1}])
        result, report=collect_team_boxes(
            df, limit=2,fetch=lambda g:parse_espn_summary(source(),g))
        self.assertEqual(result,[])
        self.assertEqual(report["checked"],0)


if __name__=="__main__":
    unittest.main()
