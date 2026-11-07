"""Offline unit checks for roster parsing (no ESPN requests, no Streamlit)."""
import unittest

from roster_data import parse_team_roster, ESPN_TEAM_IDS


class TestRosterCatalog(unittest.TestCase):
    def test_all_30_teams_mapped(self):
        self.assertEqual(len(ESPN_TEAM_IDS),30)
        self.assertEqual(len(set(ESPN_TEAM_IDS.values())),30)

    def test_flat_athletes_and_missing_stats(self):
        response={"athletes":[
            {"id":"3975","displayName":"Stephen Curry","position":{"abbreviation":"PG"}},
            {"id":"123","displayName":"Example Player","position":{"abbreviation":"SF"}},
        ]}
        rows=parse_team_roster(response,"GSW")
        self.assertEqual(len(rows),2)
        self.assertIn("Stephen Curry",rows["PLAYER_NAME"].tolist())
        self.assertEqual(rows.loc[rows["PLAYER_NAME"]=="Stephen Curry",
                                  "TEAM_ABBREVIATION"].iloc[0],"GSW")
        self.assertNotIn("PTS",rows.columns)

    def test_position_groups_and_duplicate_athletes(self):
        response={"athletes":[{"position":"G","items":[
            {"id":"3975","displayName":"Stephen Curry"},
            {"id":"3975","displayName":"Stephen Curry"},
        ]}]}
        rows=parse_team_roster(response,"GSW")
        self.assertEqual(rows["PLAYER_ID"].tolist(),["3975"])

    def test_blank_missing_id_is_not_fabricated(self):
        rows=parse_team_roster({"athletes":[{"displayName":"Unknown"}]},"BOS")
        self.assertTrue(rows.empty)


if __name__=="__main__":
    unittest.main()
