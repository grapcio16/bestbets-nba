"""Synthetic end-to-end research tests; no live data or database writes."""
import unittest
from copy import deepcopy
import pandas as pd

from test_player_intelligence_pregame_snapshot import fixture, NOW, TIP, GID
from player_intelligence.empirical import MODEL, complete_history, absence_impact
from player_intelligence.rotation import VERSION
from player_intelligence.pipeline import run_research, forecast_envelopes
from player_intelligence.evaluation import evaluate_paired


def observed_game(gid, tip, absent=False):
    rows=[]
    for team,offset in (("BOS",100),("NYK",200)):
        for i in range(10):
            mins=24
            if team=="BOS" and absent:
                mins=0 if i==0 else 36 if i in (1,2) else 24
            rows.append({"game_id":gid,"team":team,"player_id":f"nba:{offset+i}",
                "start_utc":tip.isoformat(),"observed_at":(tip+pd.Timedelta(hours=5)).isoformat(),
                "final_verified":True,"regulation_only":True,"played":mins>0,
                "minutes":mins,"PTS":int(mins/2),"REB":int(mins/6),
                "AST":int(mins/8),"FG3M":int(mins/12)})
    return rows


def research_fixture():
    f=fixture()
    logs=[]
    for i in range(6):
        logs.extend(observed_game(f"nba:00226001{i:02d}",NOW-pd.Timedelta(days=7-i),
                                  absent=i>=3))
    f["logs"]=logs
    f["assumptions"]={
        "BOS":{"assume_active_ids":[f"nba:{i}" for i in range(101,110)]},
        "NYK":{"assume_active_ids":[f"nba:{i}" for i in range(200,210)]},
    }
    f["n"]=200
    return f


def forecast_pair(f=None):
    f=research_fixture() if f is None else f
    bundle=run_research(**f)
    records=forecast_envelopes(bundle,issued_at=NOW+pd.Timedelta(minutes=1))
    actuals=observed_game(GID,TIP,absent=True)
    return bundle,records,actuals


class ResearchTests(unittest.TestCase):
    def test_both_models_and_matched_absence(self):
        bundle,records,_=forecast_pair()
        self.assertEqual(len(records),4)
        team=bundle["teams"]["BOS"]
        p=team["empirical"]
        self.assertEqual(p["status"],"shadow_conditional")
        self.assertEqual(p["same_absence_games"],3)
        self.assertTrue(p["same_absence_used"])
        self.assertAlmostEqual(p["team_minutes"],240)
        out=p["players"][0]
        self.assertEqual(out["player_id"],"nba:100")
        self.assertEqual(out["minutes"]["mean"],0)
        self.assertEqual(out["PTS"]["p90"],0)
        for row in p["players"]:
            self.assertLessEqual(row["minutes"]["p90"],48)
            self.assertAlmostEqual(row["PRA"]["mean"],sum(row[k]["mean"] for k in ("PTS","REB","AST")))
            self.assertLessEqual(3*row["FG3M"]["mean"],row["PTS"]["mean"])
        self.assertEqual(team["absence_audit"][0]["status"],"descriptive_only")
        self.assertFalse(team["absence_audit"][0]["apply_to_v8"])

    def test_deterministic_and_future_evidence_not_used(self):
        f=research_fixture()
        a=run_research(**f)
        f["logs"].extend(observed_game("future",NOW+pd.Timedelta(days=1),absent=False))
        b=run_research(**f)
        self.assertEqual(a,b)

    def test_incomplete_history_not_imputed(self):
        f=research_fixture()
        f["logs"]=[r for r in f["logs"] if r["player_id"]!="nba:100"]
        result=run_research(**f)["teams"]["BOS"]["empirical"]
        self.assertEqual(result["status"],"insufficient_complete_rotation_history")
        self.assertEqual(result["comparable_games"],0)

    def test_dnp_not_missing_or_injury_causality(self):
        f=research_fixture()
        result=absence_impact(logs=f["logs"],team="BOS",player_id="nba:100",asof=NOW,exclude_game_id=GID)
        self.assertEqual((result["played_games"],result["dnp_games"]),(3,3))
        self.assertFalse(result["causal"])
        f["logs"]=[r for r in f["logs"] if not (r["player_id"]=="nba:100" and not r["played"])]
        result=absence_impact(logs=f["logs"],team="BOS",player_id="nba:100",asof=NOW,exclude_game_id=GID)
        self.assertEqual(result["dnp_games"],0)
        self.assertEqual(result["status"],"insufficient_evidence")

    def test_expired_issue_and_envelope_copy(self):
        bundle,records,_=forecast_pair()
        with self.assertRaisesRegex(ValueError,"pregame"):
            forecast_envelopes(bundle,issued_at=TIP-pd.Timedelta(minutes=15))
        original=records[0]["projection"]["players"][0]["minutes"]
        bundle["teams"]["BOS"]["baseline"]["players"][0]["minutes"]=999
        self.assertEqual(records[0]["projection"]["players"][0]["minutes"],original)

    def test_paired_settlement_includes_explicit_dnp(self):
        _,records,actuals=forecast_pair()
        result=evaluate_paired(forecasts=records,actuals=actuals,models=[VERSION,MODEL],asof=TIP+pd.Timedelta(hours=6))
        self.assertEqual(result["paired_players"],20)
        self.assertEqual(result["dnp"],1)
        self.assertEqual(result["paired_team_games"],2)
        self.assertEqual(result["missing_actual_players"],0)
        self.assertIsNone(result["models"][VERSION]["interval_80_coverage"]["PTS"])
        self.assertIsNotNone(result["models"][MODEL]["interval_80_coverage"]["PTS"])

    def test_missing_actual_not_zero_and_future_observation_excluded(self):
        _,records,actuals=forecast_pair()
        actuals=[r for r in actuals if r["player_id"]!="nba:100"]
        result=evaluate_paired(forecasts=records,actuals=actuals,models=[VERSION,MODEL],asof=TIP+pd.Timedelta(hours=6))
        self.assertEqual(result["paired_players"],19)
        self.assertEqual(result["missing_actual_players"],1)
        self.assertEqual(result["dnp"],0)
        result=evaluate_paired(forecasts=records,actuals=actuals,models=[VERSION,MODEL],asof=TIP+pd.Timedelta(hours=4))
        self.assertEqual(result["paired_players"],0)

    def test_late_forecast_and_multiple_scenarios_not_selected_postgame(self):
        _,records,actuals=forecast_pair()
        late=deepcopy(records)
        for r in late:
            r["issued_at"]=TIP.isoformat()
        args=dict(actuals=actuals,models=[VERSION,MODEL],asof=TIP+pd.Timedelta(hours=6))
        self.assertEqual(evaluate_paired(forecasts=late,**args)["paired_players"],0)
        alternative=deepcopy(records)
        for r in alternative:
            r["scenario_id"]="alternative"
        result=evaluate_paired(forecasts=records+alternative,**args)
        self.assertEqual(result["paired_players"],0)
        self.assertEqual(result["excluded_multiple_scenario_team_games"],2)

class ArchiveTests(unittest.TestCase):
    def test_immutable_first_forecast_and_integrity(self):
        from player_intelligence.research_archive import ResearchArchive
        _,records,_=forecast_pair()
        archive=ResearchArchive(clock=lambda:NOW+pd.Timedelta(minutes=1))
        try:
            self.assertEqual(archive.append_batch(records),4)
            self.assertEqual(archive.append_batch(records),0)
            self.assertEqual(len(archive.records()),4)
            tampered=deepcopy(records)
            tampered[0]["projection"]["players"][0]["minutes"]=999
            with self.assertRaisesRegex(ValueError,"integrity"):
                archive.append_batch(tampered)
            import sqlite3
            with self.assertRaises(sqlite3.IntegrityError):
                archive.db.execute("DELETE FROM player_research_forecast")
            archive.db.rollback()
            self.assertEqual(len(archive.records()),4)
        finally:
            archive.close()

    def test_expired_archive_and_remote_path_rejected(self):
        from player_intelligence.research_archive import ResearchArchive
        _,records,_=forecast_pair()
        archive=ResearchArchive(clock=lambda:TIP)
        try:
            with self.assertRaisesRegex(ValueError,"expired"):
                archive.append_batch(records)
            self.assertEqual(archive.records(),[])
        finally:
            archive.close()
        with self.assertRaisesRegex(ValueError,"local"):
            ResearchArchive("postgresql://example.invalid/research")


class EvidenceModeTests(unittest.TestCase):
    def test_replay_rejected_by_prospective_archive_and_evaluator(self):
        from player_intelligence.research_archive import ResearchArchive
        bundle,records,actuals=forecast_pair()
        replay_records=forecast_envelopes(bundle,issued_at=NOW+pd.Timedelta(minutes=1),mode="captured_replay")
        archive=ResearchArchive(clock=lambda:NOW+pd.Timedelta(minutes=1))
        try:
            with self.assertRaisesRegex(ValueError,"only prospective"):
                archive.append_batch(replay_records)
            self.assertEqual(archive.records(),[])
        finally:
            archive.close()
        args=dict(actuals=actuals,models=[VERSION,MODEL],asof=TIP+pd.Timedelta(hours=6))
        with self.assertRaisesRegex(ValueError,"mixed"):
            evaluate_paired(forecasts=records+replay_records,**args)
        result=evaluate_paired(forecasts=replay_records,mode="captured_replay",**args)
        self.assertEqual(result["paired_players"],20)
        self.assertEqual(result["evidence_mode"],"captured_replay")

if __name__=="__main__":
    unittest.main()
