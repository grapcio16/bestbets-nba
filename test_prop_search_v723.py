"""BestBets v7.23: natural-language props, safe athlete resolution and styling."""
import unittest

import pandas as pd

from prop_search import (
    parse_prop_query, parse_prop_batch, resolve_catalog_player,
    plain,
)


class NaturalLanguageSearchTests(unittest.TestCase):
    def test_the_four_requested_jayson_tatum_queries(self):
        examples=[
            ("jason tatum uver 25,5 point","OVER",25.5,"PTS"),
            ("jason tatum under 3,5 asist","UNDER",3.5,"AST"),
            ("jason tatum over 2,5 three point","OVER",2.5,"FG3M"),
            ("jason tatum over 7,5 rebunds","OVER",7.5,"REB"),
        ]
        for query,side,line,market in examples:
            with self.subTest(query=query):
                result=parse_prop_query(query)
                self.assertEqual(result["name_input"],"jason tatum")
                self.assertEqual(result["side"],side)
                self.assertEqual(result["line"],line)
                self.assertEqual(result["market"],market)

    def test_full_name_and_polish_queries(self):
        a=parse_prop_query("Jayson Tatum powyżej 25,5 punktów")
        b=parse_prop_query("Jayson Tatum poniżej 7,5 zbiórek")
        c=parse_prop_query("Jayson Tatum over 37.5 PRA")
        self.assertEqual((a["side"],a["market"]),("OVER","PTS"))
        self.assertEqual((b["side"],b["market"]),("UNDER","REB"))
        self.assertEqual(c["market"],"PRA")

    def test_batch_semicolons_lines_and_warnings(self):
        batch=(
            "Jason Tatum over 25,5 point\n"
            "Jason Tatum under 3.5 assists;"
            "Jason Tatum uver 2,5 3PM\n"
            "bad input no odds"
        )
        rows,errors=parse_prop_batch(batch)
        self.assertEqual(len(rows),3)
        self.assertEqual(len(errors),1)
        self.assertIn("Wiersz 4",errors[0])
        self.assertEqual(rows[2]["market"],"FG3M")

    def test_input_rejects_missing_direction_market_line(self):
        for query in ("Jayson Tatum 25,5 points",
                      "Jayson Tatum over 22.5",
                      "Jayson Tatum over ??? points",
                      "over 15.5 points",
                      "Jayson Tatum over 200.5 points"):
            with self.subTest(query=query):
                with self.assertRaises(ValueError):
                    parse_prop_query(query)

    def test_batch_fails_closed_when_more_than_twelve(self):
        text="\n".join("Jayson Tatum over 25.5 points" for _ in range(13))
        with self.assertRaisesRegex(ValueError,"12"):
            parse_prop_batch(text)

    def test_exact_unique_and_typos_require_confirmation(self):
        catalog=pd.DataFrame([
            {"PLAYER_NAME":"Jayson Tatum","PLAYER_ID":"1628369",
             "TEAM_ABBREVIATION":"BOS"},
            {"PLAYER_NAME":"Stephen Curry","PLAYER_ID":"201939",
             "TEAM_ABBREVIATION":"GSW"},
            {"PLAYER_NAME":"Jaylen Brown","PLAYER_ID":"1627759",
             "TEAM_ABBREVIATION":"BOS"},
        ])
        exact=resolve_catalog_player("Jayson Tatum",catalog)
        self.assertEqual(exact["quality"],"exact")
        self.assertEqual(exact["id"],"1628369")
        typo=resolve_catalog_player("Jason Tatum",catalog)
        self.assertEqual(typo["name"],"Jayson Tatum")
        self.assertEqual(typo["quality"],"suggested")
        unknown=resolve_catalog_player("Imaginary Athlete",catalog)
        self.assertEqual(unknown["quality"],"unknown")
        self.assertIsNone(unknown["id"])

    def test_ambiguous_names_are_not_silently_assigned(self):
        catalog=pd.DataFrame([
            {"PLAYER_NAME":"Jordan Smith","PLAYER_ID":"11",
             "TEAM_ABBREVIATION":"AAA"},
            {"PLAYER_NAME":"Jordan Smith","PLAYER_ID":"22",
             "TEAM_ABBREVIATION":"BBB"},
        ])
        result=resolve_catalog_player("Jordan Smith",catalog)
        self.assertEqual(result["quality"],"ambiguous")
        self.assertIsNone(result["id"])


class PremiumStyleChecks(unittest.TestCase):
    def test_design_system_targets_entire_navigation(self):
        from premium_theme import PREMIUM_CSS
        for hook in (
            "[data-testid=\"stSidebar\"]","[data-testid=\"stMetric\"]",
            "[data-testid=\"stDataFrame\"]","[data-testid=\"stTabs\"]",
            "[data-testid=\"stPlotlyChart\"]",".bb-gamecard",
            ".bb-fixture-card",".bb-top10-grid-card",
            ".bb-search-hero",".bb-prop-hero",
            "@media(max-width:850px)",
        ):
            self.assertIn(hook,PREMIUM_CSS)

    def test_data_only_cards_change_on_user_line(self):
        from core import normalize_logs
        from season_props import clean_player_season, observed_hit_rates
        n=13
        raw=pd.DataFrame([
            {"PLAYER_NAME":"Sample Athlete","PLAYER_ID":"123",
             "TEAM_ABBREVIATION":"BOS",
             "GAME_ID":str(i),
             "GAME_DATE":pd.Timestamp("2026-10-10T00:00:00Z")+
                         pd.Timedelta(days=i),
             "MIN":30.,"PTS":12.+(i%5)*4,
             "REB":6.+(i%3),"AST":4.+(i%2),"FG3M":1.+(i%3),
             "MATCHUP":"BOS @ NYK" if i%2 else "BOS vs. NYK",
             "OPPONENT":"NYK",
             } for i in range(n)])
        season=clean_player_season(
            normalize_logs(raw),"Sample Athlete","2026-27",
            "2026-11-10T00:00:00Z","123")
        a=observed_hit_rates(season,"PTS",15.5)
        b=observed_hit_rates(season,"PTS",23.5)
        self.assertNotEqual(a["season"]["over"],b["season"]["over"])
        c=observed_hit_rates(season,"REB",7.5)
        self.assertEqual(c["season"]["n"],13)
        self.assertEqual(a["last5"]["n"],5)


if __name__=="__main__":
    unittest.main()
