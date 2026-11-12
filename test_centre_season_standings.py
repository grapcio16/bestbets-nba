"""Offline regression tests for 2026/27 regular season W-L standings."""
import unittest
from unittest import mock

from teams import TEAM_FULL
from bestbets_centre_standings import (
    SEASON_YEAR, SEASON_LABEL, STANDINGS_URL,
    parse_season_standings, fetch_season_standings, apply_season_form,
)


def fixture():
    east, west = [], []
    for index, (code, name) in enumerate(TEAM_FULL.items()):
        w, l = ((11, 3) if code == "BOS" else
                (8, 6) if code == "MIN" else (0, 0))
        record = {"team": {"abbreviation": code, "displayName": name},
                  "stats": [{"name": "wins", "value": float(w)},
                            {"name": "losses", "displayValue": str(l)}]}
        (east if index < 15 else west).append(record)
    return {"season": {"year": 2027},
            "children": [{"standings": {"entries": east}},
                         {"standings": {"entries": west}}]}


class SeasonStandingTests(unittest.TestCase):
    def test_all_30_teams_and_full_regular_season_sample(self):
        parsed = parse_season_standings(fixture())
        self.assertEqual(len(parsed), 30)
        self.assertEqual(parsed["BOS"]["wins"], 11)
        self.assertEqual(parsed["BOS"]["losses"], 3)
        self.assertEqual(parsed["BOS"]["sample"], 14)
        self.assertTrue(parsed["BOS"]["record_verified"])
        self.assertEqual(parsed["ATL"]["sample"], 0)
        self.assertTrue(parsed["ATL"]["record_verified"])

    def test_wrong_season_or_incomplete_table_rejected(self):
        old = fixture()
        old["season"]["year"] = 2026
        with self.assertRaises(ValueError):
            parse_season_standings(old)
        missing = fixture()
        missing["children"] = missing["children"][:1]
        with self.assertRaises(ValueError):
            parse_season_standings(missing)

    def test_invalid_stat_does_not_turn_into_zero(self):
        broken = fixture()
        broken["children"][0]["standings"]["entries"][0]["stats"][0]["value"] = "N/A"
        with self.assertRaises(ValueError):
            parse_season_standings(broken)

    def test_provider_request_is_season_specific_and_cached(self):
        with mock.patch("sources.memoized_json", return_value=(fixture(), {"stale": False})) as fetch:
            result, meta = fetch_season_standings()
        self.assertEqual(len(result), 30)
        self.assertFalse(meta["stale"])
        self.assertEqual(fetch.call_args.args[1], STANDINGS_URL)
        self.assertEqual(fetch.call_args.kwargs["params"]["season"], SEASON_YEAR)
        self.assertEqual(fetch.call_args.kwargs["params"]["seasontype"], 2)
        self.assertGreaterEqual(fetch.call_args.kwargs["ttl_seconds"], 600)

    def test_overrides_short_week_and_never_claims_fake_season(self):
        base = {
            "form": [{"team": "BOS", "wins": 2, "losses": 0, "sample": 2},
                     {"team": "MIN", "wins": 1, "losses": 1, "sample": 2}],
            "form_options": [{"team": code, "name": name, "logo": "",
                              "wins": 0, "losses": 0, "sample": 0}
                             for code, name in TEAM_FULL.items()],
        }
        verified = apply_season_form(dict(base), parse_season_standings(fixture()), {"stale": False})
        self.assertEqual(verified["form_period"], SEASON_LABEL)
        self.assertEqual([t["team"] for t in verified["form"]], ["BOS", "MIN"])
        self.assertEqual(verified["form"][0]["wins"], 11)
        self.assertEqual(verified["form"][0]["sample"], 14)
        self.assertTrue(verified["form_available"])
        unavailable = apply_season_form(dict(base), None)
        self.assertFalse(unavailable["form_available"])
        self.assertIsNone(unavailable["form"][0]["wins"])
        self.assertFalse(unavailable["form"][0]["record_verified"])

    def test_stale_cache_is_marked_not_presented_as_fresh(self):
        row = apply_season_form({"form": [], "form_options": []},
                                parse_season_standings(fixture()), {"stale": True})
        self.assertTrue(row["form_stale"])


if __name__ == "__main__":
    unittest.main()
