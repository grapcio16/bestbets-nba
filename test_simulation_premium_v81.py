"""BestBets v8.1 compact simulation presentation checks.

These tests never call the network or imply statistical calibration.
"""
import unittest
from pathlib import Path
import pandas as pd

from simulation_premium import (
    game_tile_html, matchup_hero_html, matchup_metrics_html,
    compact_team_context_html, injury_preview_html,
    player_previews_html, injury_status_cards_html,
)
from mvp_theme import MVP_CSS

SIM={
    "home":"NYK","away":"MIL","home_win_pct":71.3,"away_win_pct":28.7,
    "home_points":117.6,"away_points":109.0,"total_points":226.6,
    "total_p10":201,"total_p90":252,
}
NAMES={"MIL":"Milwaukee Bucks","NYK":"New York Knicks"}
GAME={"game_id":"401",
      "start_utc":pd.Timestamp("2026-11-11T00:30:00Z")}
LOGOS={"MIL":"<img src='data:image/png;base64,abc' alt='MIL'>",
       "NYK":"<img src='data:image/png;base64,def' alt='NYK'>"}


class PremiumSimulationTests(unittest.TestCase):
    def test_card_html_compact_and_grounded(self):
        card=game_tile_html(SIM,GAME,NAMES,LOGOS["MIL"],
                            LOGOS["NYK"],"11.11.2026 · 01:30")
        self.assertIn("Milwaukee Bucks",card)
        self.assertIn("New York Knicks",card)
        self.assertIn("109.0",card)
        self.assertIn("117.6",card)
        self.assertIn("226.6",card)
        self.assertIn("28.7%",card)
        self.assertIn("71.3%",card)
        self.assertIn("5,000 RUNS",card)
        self.assertIn("MODEL LEADER",card)
        self.assertNotIn("guaranteed",card.lower())
        self.assertNotIn("Live result",card)

    def test_matchup_details_top_summary_and_real_simulated_interval(self):
        hero=matchup_hero_html(SIM,GAME,NAMES,LOGOS["MIL"],
                               LOGOS["NYK"],"11.11.2026 · 01:30")
        tiles=matchup_metrics_html(SIM)
        self.assertIn("PROJECTED SCORE",hero)
        self.assertIn("SIMULATION AVERAGES",hero)
        self.assertIn("80% RANGE",tiles)
        self.assertIn("201–252",tiles)
        self.assertIn("5,000",tiles)
        self.assertNotIn("A+",hero)

    def test_side_by_side_team_snapshot_no_fake_pace(self):
        forms={
            "away":{"games_last5":5,"wins_last5":0,
                    "scored_last5":103.4,"allowed_last5":119.0},
            "home":{"games_last5":5,"wins_last5":4,
                    "scored_last5":114.6,"allowed_last5":103.4},
        }
        ctx={
            "away":{"available":True,"rest_days":1,"back_to_back":False},
            "home":{"available":True,"rest_days":2,"back_to_back":False},
        }
        html=compact_team_context_html(
            "MIL","NYK",NAMES,forms,ctx,{},LOGOS)
        for expected in ("0/5","4/5","103.4","114.6","—",
                         "BACK-TO-BACK","REST DAYS"):
            self.assertIn(expected,html)

    def test_unavailable_injury_data_not_equated_to_full_roster(self):
        empty=injury_preview_html(pd.DataFrame(),{"stale":True})
        self.assertIn("has NOT been verified",empty)
        report=pd.DataFrame([
            {"Zawodnik":"One","Drużyna":"NYK","Status ESPN":"Day-to-day"},
            {"Zawodnik":"Two","Drużyna":"MIL","Status ESPN":"Questionable"},
        ])
        found=injury_preview_html(report,{"stale":True})
        self.assertIn("2 entries",found)
        self.assertIn("stale",found)

    def test_injury_statuses_are_separated_for_both_teams(self):
        items=pd.DataFrame([
            {"Drużyna":"NYK","Zawodnik":"Player A",
             "Status ESPN":"Questionable","Informacja":"Ankle"},
            {"Drużyna":"MIL","Zawodnik":"Player B",
             "Status ESPN":"Out","Informacja":"Knee"},
        ])
        html=injury_status_cards_html(items,"MIL","NYK",NAMES)
        self.assertIn("Player A",html)
        self.assertIn("Player B",html)
        self.assertIn("bb81-injury-badge out",html)
        self.assertIn("bb81-injury-badge question",html)
        self.assertIn("New York Knicks",html)
        self.assertIn("Milwaukee Bucks",html)
        self.assertIn("not confirmed",injury_status_cards_html(
            pd.DataFrame(),"MIL","NYK",NAMES))

    def test_player_projection_cards_are_not_sampled_or_invented(self):
        table=pd.DataFrame([
            {"Zawodnik":"Starter A","PTS":21.5,"REB":6.2,"AST":7.1,
             "3PM":2.3,"Minuty":31.4,"Status ESPN":None},
            {"Zawodnik":"Starter B","PTS":9.5,"REB":2.0,"AST":2.2,
             "3PM":1.0,"Minuty":22.7,"Status ESPN":"Day-to-day"},
            {"Zawodnik":"Unverified","PTS":None,"REB":None,
             "AST":None,"3PM":None,"Minuty":None},
        ])
        html=player_previews_html("NYK","New York Knicks",table)
        self.assertIn("Starter A",html)
        self.assertIn("Starter B",html)
        self.assertIn("Day-to-day",html)
        self.assertNotIn("Unverified",html)
        self.assertIn("21.5",html)
        self.assertIn("not confirmed starters",html)
        self.assertIn("No verified player projection available.",
                      player_previews_html("NYK","Knicks",pd.DataFrame()))

    def test_badge_escapes_untrusted_data(self):
        malicious={"MIL":"<script>alert(1)</script>",
                   "NYK":"New York Knicks"}
        card=game_tile_html(SIM,GAME,malicious,"","","> bad <")
        self.assertNotIn("<script>",card)
        self.assertIn("&lt;script&gt;",card)

    def test_details_default_view_loads_without_roster_fetch(self):
        from pathlib import Path
        source=Path("simulation_view.py").read_text(encoding="utf8")
        start=source.index("def show_game_details(")
        section=source[start:source.index("def render_simulations(",start)]
        self.assertIn('["🏟️ Przegląd","👥 Zawodnicy"',section)
        overview=section.index('if view=="🏟️ Przegląd":')
        fetch=section.index('matchup_players_cached(',overview)
        self.assertLess(overview,fetch)
        self.assertIn('if view in ("👥 Zawodnicy","🩺 Rotacja i absencje")',section)
        self.assertIn("season=None, nonce=0",section)

    def test_technical_panels_appear_after_projected_cards(self):
        source=Path("simulation_view.py").read_text(encoding="utf8")
        body=source[source.index("def render_simulations("):]
        first=body.index("done={str(s[\"game_id\"]):s for s in summary}")
        second=body.index("with st.expander('Źródła danych i kompletność'")
        self.assertLess(first,second)
        self.assertIn("season=season,nonce=nonce",body)
        handler=body[body.index("📊 MATCHUP INTELLIGENCE · VIEW DETAILS"):]
        self.assertNotIn("players,player_meta=matchup_players_cached(",handler)

    def test_compact_responsive_global_visuals(self):
        for selector in (
            "bb81-game-tile","bb81-game-match","bb81-matchup-hero",
            "bb81-matchup-head","bb81-matchup-kpis",
            "bb81-context-pair","bb81-player-row",
            "@media(max-width:620px)"):
            self.assertIn(selector,MVP_CSS,selector)


if __name__=="__main__":
    unittest.main()
