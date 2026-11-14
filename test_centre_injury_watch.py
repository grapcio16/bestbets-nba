"""Offline tests for the publicly visible Injury Watch card's real-data contract."""
from pathlib import Path
from unittest import TestCase, mock

import pandas as pd

from bestbets_centre_injuries import (
    get_centre_injury_watch, status_badge, summarize_injuries,
)


class InjuryWatchTests(TestCase):
    def test_public_studio_photo_index_is_loaded_before_portraits(self):
        frontend = Path(__file__).resolve().parent / "bestbets_reference_frontend"
        index = (frontend / "index.html").read_text(encoding="utf-8")
        roster = (frontend / "nba_player_ids.js").read_text(encoding="utf-8")
        self.assertLess(index.index('src="nba_player_ids.js"'),
                        index.index('src="portraits.js"'))
        self.assertIn('"adem bona":"1641737"', roster)
        self.assertIn('"ajay mitchell":"1642349"', roster)

    def test_statuses_are_explicit_not_inferred(self):
        self.assertEqual(status_badge("Out")[:2], ("OUT", "out"))
        self.assertEqual(status_badge("Questionable")[:2], ("QST", "question"))
        self.assertEqual(status_badge("Day-To-Day")[:2], ("DTD", "question"))
        self.assertEqual(status_badge("Game-Time Decision")[:2], ("GTD", "question"))
        self.assertEqual(status_badge("Probable")[:2], ("PROB", "probable"))

    def test_real_rows_sorted_deduplicated_with_verified_ids(self):
        data = pd.DataFrame([
            {"player": "Player B", "team": "NYK", "status": "Questionable",
             "note": "Knee", "athlete_id": "789"},
            {"player": "Player A", "team": "BOS", "status": "Out",
             "note": "Ankle", "athlete_id": "123"},
            {"player": "Player B", "team": "NYK", "status": "Questionable",
             "note": "Knee", "athlete_id": "789"},
        ])
        result = summarize_injuries(data, {"timestamp": "2026-11-14T07:00:00Z"})
        self.assertTrue(result["available"])
        self.assertEqual([r["name"] for r in result["rows"]], ["Player A", "Player B"])
        self.assertEqual(result["rows"][0]["athlete_id"], "123")
        self.assertEqual(result["rows"][0]["badge"], "OUT")
        self.assertNotIn("_priority", result["rows"][0])

    def test_injury_portait_id_comes_from_offline_nba_catalog(self):
        result = summarize_injuries(
            pd.DataFrame([{"player": "Alperen Şengün", "team": "HOU", "status": "Out"}]),
            nba_ids={"alperen sengun": "1630578"},
        )
        self.assertEqual(result["rows"][0]["nba_id"], "1630578")

    def test_complete_report_keeps_more_than_two_players(self):
        report = pd.DataFrame([
            {"player": "Player " + str(index), "team": "BOS", "status": "Out"}
            for index in range(22)
        ])
        result = summarize_injuries(report, nba_ids={})
        self.assertEqual(len(result["rows"]), 22)

    def test_stale_two_hour_report_is_hidden(self):
        result = summarize_injuries(
            pd.DataFrame([{"player": "Player A", "team": "BOS", "status": "Out"}]),
            {"stale": True, "age_min": 200},
        )
        self.assertFalse(result["available"])
        self.assertEqual(result["rows"], [])

    def test_feed_error_has_no_fabricated_players(self):
        with mock.patch("sources.memoized_json", side_effect=TimeoutError("network")):
            result = get_centre_injury_watch()
        self.assertFalse(result["available"])
        self.assertEqual(result["rows"], [])

    def test_feed_parses_team_and_athlete_id(self):
        payload = {"teams": [{"team": {"abbreviation": "NY"}, "injuries": [
            {"athlete": {"id": "345", "displayName": "Player Z"},
             "status": "Out", "details": {"detail": "Hip"}},
        ]}]}
        with mock.patch("sources.memoized_json", return_value=(payload, {"stale": False})):
            result = get_centre_injury_watch()
        self.assertEqual(result["rows"][0]["name"], "Player Z")
        self.assertEqual(result["rows"][0]["team"], "NYK")
        self.assertEqual(result["rows"][0]["athlete_id"], "345")
        self.assertEqual(result["rows"][0]["note"], "Hip")
