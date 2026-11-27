"""Synthetic identity resolution tests; no real patient/medical details."""
import unittest
from test_player_intelligence_pregame_snapshot import fixture
from player_intelligence.report_identity import resolve_report
from player_intelligence.pregame_snapshot import build_snapshot


def raw_fixture():
    f=fixture()
    roster=f["rosters"]["BOS"]
    for i,p in enumerate(roster["players"]):
        p["name"]=f"Given{i} Family{i}"
    roster["players"][0]["name"]="Jean André"
    report=f["reports"][0]
    report["section_complete_verified"]=True
    report["players"]=[{"team":"BOS","player_name":"André, Jean","status":"Out"}]
    return f,roster,report


class IdentityTests(unittest.TestCase):
    def test_exact_reversed_unicode_name_joins_snapshot(self):
        f,roster,report=raw_fixture()
        report["players"][0]["player_name"]="Andre\u0301, JEAN"
        result=resolve_report(report=report,roster=roster)
        self.assertEqual(result["players"][0]["nba_person_id"],"100")
        f["reports"]=[result]
        snapshot=build_snapshot(**f)
        self.assertEqual(snapshot["availability"][0]["player_id"],"nba:100")

    def test_no_fuzzy_matching_or_unverified_alias(self):
        _,roster,report=raw_fixture()
        report["players"][0]["player_name"]="Andre, Jean"
        with self.assertRaisesRegex(ValueError,"unresolved"):
            resolve_report(report=report,roster=roster)
        roster["players"][0]["verified_aliases"]=[{"name":"Jean Andre","verified":False}]
        with self.assertRaisesRegex(ValueError,"unverified name alias"):
            resolve_report(report=report,roster=roster)
        roster["players"][0]["verified_aliases"]=[{"name":"Jean Andre","verified":True,"evidence_ref":"verified-alias"}]
        self.assertEqual(resolve_report(report=report,roster=roster)["players"][0]["nba_person_id"],"100")

    def test_ambiguous_or_wrong_team_identity_rejected(self):
        _,roster,report=raw_fixture()
        roster["players"][1]["name"]="Jean André"
        with self.assertRaisesRegex(ValueError,"ambiguous"):
            resolve_report(report=report,roster=roster)
        roster["players"][1]["name"]="Different Player"
        report["players"][0]["team"]="NYK"
        with self.assertRaisesRegex(ValueError,"team mismatch"):
            resolve_report(report=report,roster=roster)

    def test_partial_or_future_evidence_rejected(self):
        _,roster,report=raw_fixture()
        report["section_complete_verified"]=False
        with self.assertRaisesRegex(ValueError,"complete"):
            resolve_report(report=report,roster=roster)
        report["section_complete_verified"]=True
        import pandas as pd
        roster["captured_at"]+=pd.Timedelta(seconds=1)
        with self.assertRaisesRegex(ValueError,"point-in-time"):
            resolve_report(report=report,roster=roster)

    def test_not_submitted_and_duplicate_rows(self):
        _,roster,report=raw_fixture()
        report["players"].append(dict(report["players"][0]))
        with self.assertRaisesRegex(ValueError,"duplicate"):
            resolve_report(report=report,roster=roster)
        report["submission"]="not_submitted"
        with self.assertRaisesRegex(ValueError,"not-submitted"):
            resolve_report(report=report,roster=roster)
        report["players"]=[]
        self.assertEqual(resolve_report(report=report,roster=roster)["players"],[])

if __name__=="__main__":
    unittest.main()
