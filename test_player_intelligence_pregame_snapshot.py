"""Offline normalized pregame evidence contract tests."""
import unittest
import pandas as pd
from player_intelligence.pregame_snapshot import build_snapshot
from player_intelligence.rotation import project_rotation

NOW = pd.Timestamp("2026-11-27T12:00:00Z")
TIP = NOW+pd.Timedelta(hours=3)
GID = "nba:0022600201"


def fixture():
    game={"provider":"nba","verified":True,"game_id":"0022600201",
          "home":"BOS","away":"NYK","start_utc":TIP}
    rosters={}
    for team,start in (("BOS",100),("NYK",200)):
        rosters[team]={"team":team,"complete_verified":True,
            "published_at":NOW-pd.Timedelta(hours=1),"captured_at":NOW,
            "evidence_ref":"fixture-roster-"+team,
            "players":[{"team":team,"nba_person_id":i,"identity_verified":True}
                       for i in range(start,start+10)]}
    report={"game_id":GID,"home":"BOS","away":"NYK","start_utc":TIP,
            "team":"BOS","verified":True,"submission":"submitted",
            "published_at":NOW-pd.Timedelta(hours=2),"captured_at":NOW,
            "evidence_ref":"fixture-report-1",
            "players":[{"team":"BOS","nba_person_id":100,"identity_verified":True,"status":"out"}]}
    return dict(fixture=game,asof=NOW,rosters=rosters,reports=[report])


class SnapshotTests(unittest.TestCase):
    def test_omissions_and_missing_team_stay_unknown(self):
        r=build_snapshot(**fixture())
        self.assertEqual(len(r["availability"]),1)
        self.assertEqual(r["availability"][0]["player_id"],"nba:100")
        self.assertEqual(r["diagnostics"]["BOS"]["unresolved_player_ids"],
                         [f"nba:{i}" for i in range(101,110)])
        self.assertEqual(r["diagnostics"]["NYK"]["report_state"],"missing_report")
        self.assertEqual(len(r["diagnostics"]["NYK"]["unresolved_player_ids"]),10)
        outcome=project_rotation(game=r["game"],team="BOS",asof=r["asof"],
            roster=r["rosters"]["BOS"],logs=[],availability=r["availability"])
        self.assertEqual(outcome["status"],"unresolved_availability")
        self.assertEqual(outcome["unresolved_player_ids"],r["diagnostics"]["BOS"]["unresolved_player_ids"])

    def test_new_whole_report_removes_previous_status(self):
        f=fixture()
        f["reports"].append(dict(f["reports"][0],players=[],
            evidence_ref="fixture-report-2",published_at=NOW-pd.Timedelta(minutes=30)))
        r=build_snapshot(**f)
        self.assertEqual(r["availability"],[])
        self.assertEqual(len(r["diagnostics"]["BOS"]["unresolved_player_ids"]),10)

    def test_not_submitted_supersedes_older_report(self):
        f=fixture()
        f["reports"].append(dict(f["reports"][0],players=[],submission="not_submitted",
            evidence_ref="fixture-report-2",published_at=NOW-pd.Timedelta(minutes=30)))
        r=build_snapshot(**f)
        self.assertEqual(r["availability"],[])
        self.assertEqual(r["diagnostics"]["BOS"]["report_state"],"not_submitted")

    def test_fresh_capture_cannot_refresh_stale_publication(self):
        f=fixture()
        f["reports"][0]["published_at"]=NOW-pd.Timedelta(hours=7)
        r=build_snapshot(**f)
        self.assertEqual(r["availability"],[])
        self.assertEqual(r["diagnostics"]["BOS"]["report_state"],"stale_report")
        f["rosters"]["BOS"]["published_at"]=NOW-pd.Timedelta(hours=25)
        with self.assertRaisesRegex(ValueError,"stale"):
            build_snapshot(**f)

    def test_future_capture_ignored_even_if_published_earlier(self):
        f=fixture()
        f["reports"].append(dict(f["reports"][0],players=[],
            published_at=NOW-pd.Timedelta(minutes=30),captured_at=NOW+pd.Timedelta(seconds=1)))
        self.assertEqual(len(build_snapshot(**f)["availability"]),1)

    def test_conflicting_same_publication(self):
        f=fixture()
        f["reports"].append(dict(f["reports"][0],players=[]))
        with self.assertRaisesRegex(ValueError,"conflicting"):
            build_snapshot(**f)

    def test_report_wrong_tip_and_unverified_identity(self):
        f=fixture()
        f["reports"][0]["start_utc"]=TIP+pd.Timedelta(hours=1)
        with self.assertRaisesRegex(ValueError,"fixture identity"):
            build_snapshot(**f)
        f=fixture()
        f["reports"][0]["players"][0]["identity_verified"]=False
        with self.assertRaisesRegex(ValueError,"unverified report"):
            build_snapshot(**f)

    def test_cross_team_and_absent_roster_identity(self):
        f=fixture()
        f["rosters"]["NYK"]["players"][0]["nba_person_id"]=100
        with self.assertRaisesRegex(ValueError,"both teams"):
            build_snapshot(**f)
        f=fixture()
        f["reports"][0]["players"][0]["nba_person_id"]=999
        with self.assertRaisesRegex(ValueError,"absent from roster"):
            build_snapshot(**f)

    def test_snapshot_fingerprint_stable_and_changes_with_evidence(self):
        f=fixture()
        a=build_snapshot(**f)["snapshot_sha256"]
        f["rosters"]["BOS"]["players"].reverse()
        self.assertEqual(a,build_snapshot(**f)["snapshot_sha256"])
        f["reports"][0]["players"][0]["status"]="available"
        self.assertNotEqual(a,build_snapshot(**f)["snapshot_sha256"])

if __name__=="__main__":
    unittest.main()
