"""Synthetic offline fixtures: not evidence of actual NBA accuracy."""
import unittest
import pandas as pd
from player_intelligence.rotation import project_rotation, _allocate_minutes

NOW = pd.Timestamp("2026-11-27T12:00:00Z")
IDS = [f"p{i}" for i in range(10)]


def fixture():
    roster = {"team":"BOS", "complete_verified":True, "observed_at":NOW, 
              "players":[{"player_id":p} for p in IDS]}
    game = {"game_id":"future", "home":"BOS", "away":"NYK",
            "start_utc":NOW+pd.Timedelta(hours=5)}
    statuses = [{"player_id":p, "team":"BOS", "status":"available",
                 "observed_at":NOW, "verified":True} for p in IDS]
    logs = []
    for j in range(5):
        start = NOW-pd.Timedelta(days=j+1)
        for i,p in enumerate(IDS):
            logs.append({"player_id":p, "game_id":f"g{j}", "team":"BOS",
                "start_utc":start,"observed_at":start+pd.Timedelta(hours=4),
                "final_verified":True,"regulation_only":True,
                "minutes":35-i*2,"PTS":16,"REB":5,"AST":4,"FG3M":2})
    return dict(game=game,team="BOS",asof=NOW,roster=roster,logs=logs,availability=statuses)


class RotationTests(unittest.TestCase):
    def test_conserves_regulation_minutes_and_pra(self):
        r=project_rotation(**fixture())
        self.assertEqual(r["status"],"shadow_conditional")
        self.assertAlmostEqual(r["team_minutes"],240)
        self.assertFalse(r["assumptions_used"])
        for p in r["players"]:
            self.assertTrue(0 <= p["minutes"] <= 48)
            self.assertAlmostEqual(p["PRA"],p["PTS"]+p["REB"]+p["AST"])

    def test_out_gets_zero_and_minutes_redistribute(self):
        f=fixture()
        baseline=project_rotation(**f)
        f["availability"][0]["status"]="out"
        r=project_rotation(**f)
        self.assertEqual(r["players"][0]["minutes"],0)
        self.assertEqual(r["players"][0]["PRA"],0)
        self.assertAlmostEqual(r["team_minutes"],240)
        self.assertGreater(r["players"][1]["minutes"],baseline["players"][1]["minutes"])
        with self.assertRaisesRegex(ValueError,"verified OUT"):
            project_rotation(**f,assume_active_ids=["p0"])

    def test_unknown_and_stale_not_healthy(self):
        f=fixture()
        f["availability"][0]["observed_at"]=NOW-pd.Timedelta(hours=7)
        self.assertEqual(project_rotation(**f)["unresolved_player_ids"],["p0"])
        r=project_rotation(**f,assume_active_ids=["p0"])
        self.assertTrue(r["assumptions_used"])
        self.assertEqual(r["players"][0]["availability"],"assumed_active")

    def test_questionable_branches_explicit(self):
        f=fixture()
        f["availability"][0]["status"]="questionable"
        self.assertEqual(project_rotation(**f)["status"],"unresolved_availability")
        a=project_rotation(**f,assume_active_ids=["p0"])
        b=project_rotation(**f,assume_out_ids=["p0"])
        self.assertGreater(a["players"][0]["PTS"],b["players"][0]["PTS"])
        self.assertAlmostEqual(b["team_minutes"],240)

    def test_other_team_and_future_data_do_not_leak(self):
        f=fixture()
        baseline=project_rotation(**f)
        f["logs"].extend([dict(f["logs"][0],game_id="trade",team="NYK",PTS=90),
                         dict(f["logs"][0],game_id="future-log",observed_at=NOW+pd.Timedelta(seconds=1),PTS=90),
                         dict(f["logs"][0],game_id="future",PTS=90)])
        f["availability"].append(dict(f["availability"][0],observed_at=NOW+pd.Timedelta(seconds=1),status="out"))
        self.assertEqual(project_rotation(**f),baseline)

    def test_duplicate_logs_and_roster_rejected(self):
        f=fixture()
        f["logs"].append(dict(f["logs"][0]))
        with self.assertRaisesRegex(ValueError,"duplicate player-game"):
            project_rotation(**f)
        f=fixture()
        f["roster"]["players"].append({"player_id":"p0"})
        with self.assertRaisesRegex(ValueError,"duplicate"):
            project_rotation(**f)

    def test_no_fabricated_rookie_stats_or_roster(self):
        f=fixture()
        f["logs"]=[x for x in f["logs"] if x["player_id"]!="p0"]
        self.assertEqual(project_rotation(**f)["missing_player_ids"],["p0"])
        f["roster"]["complete_verified"]=False
        self.assertEqual(project_rotation(**f)["status"],"insufficient_verified_roster")

    def test_capacity_and_exact_boundary(self):
        f=fixture()
        for a in f["availability"][:6]:
            a["status"]="out"
        self.assertEqual(project_rotation(**f)["status"],"insufficient_rotation_capacity")
        self.assertEqual(list(_allocate_minutes([1,2,3,4,5,0])),[48,48,48,48,48,0])

    def test_zero_minute_dnp_not_counted_as_active_evidence(self):
        f=fixture()
        f["logs"].append(dict(f["logs"][0],game_id="dnp",minutes=0,PTS=0,REB=0,AST=0,FG3M=0))
        r=project_rotation(**f)
        self.assertEqual(r["players"][0]["sample_games"],5)

    def test_future_roster_and_late_cutoff(self):
        f=fixture()
        f["roster"]["observed_at"]=NOW+pd.Timedelta(seconds=1)
        self.assertEqual(project_rotation(**f)["status"],"stale_or_future_roster")
        f=fixture()
        f["asof"]=f["game"]["start_utc"]-pd.Timedelta(minutes=15)
        with self.assertRaisesRegex(ValueError,"cutoff"):
            project_rotation(**f)

if __name__=="__main__":
    unittest.main()
