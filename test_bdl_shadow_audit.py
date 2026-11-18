"""Offline contract tests: no provider keys or network calls required."""

import unittest
from unittest.mock import Mock

from bdl_shadow_audit import (
    BDLClient, align_games, bdl_player_rows, compare_game, normalized_name,
)


BDL_SAMPLE = {
    "min": "30", "pts": 23, "reb": 7, "ast": 1,
    "fg3m": 5, "fg3a": 9, "fga": 18,
    "oreb": 2, "dreb": 5, "turnover": 1,
    "player": {"id": 70, "first_name": "Jaylen", "last_name": "Brown"},
    "team": {"abbreviation": "BOS"},
}


class TestBDLShadowAudit(unittest.TestCase):
 def test_bdl_stats_match_espn_verified_opening_game(self):
    bdl = bdl_player_rows([BDL_SAMPLE])
    espn = [{"PLAYER_NAME": "Jaylen Brown", "TEAM_ABBREVIATION": "BOS",
             "MIN": 29.9, "PTS": 23, "REB": 7, "AST": 1,
             "FG3M": 5, "FG3A": 9, "FGA": 18,
             "OREB": 2, "DREB": 5, "TOV": 1}]
    audit = compare_game(espn, bdl, game_label="NYK @ BOS")
    assert audit["matched_players"] == 1
    assert audit["matching_fields"] == 9
    assert audit["comparable_fields"] == 9
    assert not audit["mismatches"]
    assert not audit["minute_differences_over_1m"]


 def test_missing_stats_not_fabricated_as_zero(self):
    bdl = bdl_player_rows([BDL_SAMPLE])
    audit = compare_game([{"PLAYER_NAME": "Jaylen Brown", "TEAM_ABBREVIATION": "BOS",
                           "PTS": 23, "REB": None, "AST": 1, "FG3M": None}],
                         bdl, game_label="NYK @ BOS")
    assert audit["comparable_fields"] == 2
    assert audit["matching_fields"] == 2


 def test_absent_players_are_flagged(self):
    audit = compare_game([{"PLAYER_NAME": "Steph Curry", "TEAM_ABBREVIATION": "GSW"}],
                         bdl_player_rows([BDL_SAMPLE]), game_label="GSW @ BOS")
    assert audit["only_espn"] == ["Steph Curry"]
    assert audit["only_bdl"] == ["Jaylen Brown"]


 def test_unknown_participation_not_invented(self):
    assert bdl_player_rows([{**BDL_SAMPLE, "min": "0"}]) == []
    assert bdl_player_rows([{**BDL_SAMPLE, "min": None}]) == []


 def test_game_ids_are_not_assumed_equal(self):
    espn = [{"game_id": "401000001", "home": "BOS", "away": "NYK",
             "home_score": "132", "away_score": "109"}]
    bdl = [{"id": 15907438, "status_state": "final",
            "home_team": {"abbreviation": "BOS"},
            "visitor_team": {"abbreviation": "NYK"},
            "home_team_score": 132, "visitor_team_score": 109}]
    matched, warnings = align_games(espn, bdl)
    assert len(matched) == 1
    assert matched[0][1]["id"] == 15907438
    assert warnings == []


 def test_nonfinal_games_do_not_enter_audit(self):
    bdl = [{"id": 1, "status_state": "in_progress",
            "home_team": {"abbreviation": "BOS"},
            "visitor_team": {"abbreviation": "NYK"}}]
    matched, warnings = align_games([{"game_id": "400", "home": "BOS", "away": "NYK"}], bdl)
    assert not matched
    assert len(warnings) == 1


 def test_api_pagination_and_header_never_written_to_result(self):
    response = Mock(status_code=200)
    response.json.return_value = {"data": [BDL_SAMPLE], "meta": {"per_page": 100}}
    response.raise_for_status.return_value = None
    session = Mock()
    session.get.return_value = response
    client = BDLClient("private-value", session=session)
    assert client.player_stats(123) == [BDL_SAMPLE]
    assert session.get.call_args.kwargs["headers"]["Authorization"] == "private-value"
    assert session.get.call_args.kwargs["params"]["game_ids[]"] == 123


 def test_names_with_accents_are_normalized(self):
    assert normalized_name("Luka Dončić") == normalized_name("Luka Doncic")


 def test_blank_key_is_rejected(self):
    with self.assertRaisesRegex(ValueError, "Brak klucza"):
        BDLClient("   ")
