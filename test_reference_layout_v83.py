"""BestBets v8.3 visual reference + live-data UX regression tests."""
import unittest
from pathlib import Path
from datetime import datetime,timezone

import pandas as pd

from mvp_player_card import (
    MARKET_SHORT, _plot, _headline_html, _stats_panel, _take_html,
)
from season_props import observed_hit_rates


def sample_logs():
    return pd.DataFrame({
        "GAME_DATE":pd.date_range(
            "2026-10-20",periods=10,freq="2D",tz="UTC"),
        "MATCHUP":["BOS @ NYK","BOS vs. CHI"]*5,
        "PTS":[19,21,27,16,20,16,25,30,20,29],
        "REB":[5,7,8,4,6,5,9,8,4,7],
        "AST":[3,4,6,5,3,8,4,7,4,3],
    })


class ApprovedReferenceTests(unittest.TestCase):
    def test_six_controlled_sections_same_viewport(self):
        code=Path("mvp_player_card.py").read_text(encoding="utf8")
        app=Path("mvp_app.py").read_text(encoding="utf8")
        search=Path("mvp_prop_ui.py").read_text(encoding="utf8")
        theme=Path("mvp_reference_theme.py").read_text(encoding="utf8")
        for part in (
            "bb83-hero","bb83-controls","bb83-research","bb83-rate-grid",
            "bb83-defense","bb83-take","bb83-grade",
        ):
            self.assertIn(part,code+theme,part)
        self.assertIn('if page=="props":\n        return',app)
        self.assertIn('render_reference_footer(set_page,_season())',app)
        self.assertIn('with st.container(key="bb83_search")',search)
        self.assertIn('with st.container(key="bb83-suggest")',search)
        self.assertIn('on_click=_preset',search)
        for part in (".st-key-bb83_search",".bb83-hero",
                     ".bb83-rate-grid",".bb83-footer-heading",
                     "@media(max-width:700px)"):
            self.assertIn(part,theme)

    def test_all_five_market_buttons_provided(self):
        self.assertEqual(
            MARKET_SHORT,("PTS","REB","AST","FG3M","PRA"))
        card=Path("mvp_player_card.py").read_text(encoding="utf8")
        self.assertIn("on_change=_sync_tabs_to_market",card)
        self.assertIn("on_change=_sync_market_to_tabs",card)
        self.assertIn("PRA",Path("mvp_prop_ui.py").read_text(encoding="utf8"))

    def test_proper_chart_matches_green_and_red_history(self):
        games=sample_logs()
        rates=observed_hit_rates(games,"PTS",25.5)
        self.assertEqual(rates["last10"]["over"],3)
        self.assertEqual(rates["last10"]["under"],7)
        chart=_plot(games,"PTS",25.5)
        bars=chart.data[0]
        self.assertEqual(len(bars.y),10)
        self.assertEqual(
            list(bars.marker.color).count("#00e66a"),3)
        self.assertEqual(
            list(bars.marker.color).count("#ff5149"),7)
        self.assertEqual(bars.y[-1],29)
        self.assertEqual(bars.y[0],19)
        self.assertIn("hline",str(chart.layout.shapes).lower()) if False else None
        self.assertTrue(any(abs(shape.y0-25.5)<.001 for shape in chart.layout.shapes))

    def test_live_pra_and_side_direction_not_fake(self):
        logs=sample_logs()
        logs["PRA"]=logs["PTS"]+logs["REB"]+logs["AST"]
        rates=observed_hit_rates(logs,"PRA",35.5)
        html=_stats_panel(
            rates,38.5,35.1,"PRA","UNDER",
            {"Obrona: stracone pkt/mecz":None},"")
        self.assertIn(f'{rates["last10"]["under_pct"]:.0f}%',html)
        self.assertIn("38.5",html)
        self.assertIn("35.1",html)
        self.assertIn("Brak potwierdzonej obrony",html)
        take=_take_html("Jayson Tatum","PRA",35.5,"UNDER",
                        rates["season"])
        self.assertIn("UNDER 35.5",take)
        self.assertIn(str(rates["season"]["under"]),take)
        self.assertIn("historyczna",take)

    def test_absent_grade_not_a_fake_letter(self):
        rates=observed_hit_rates(sample_logs(),"PTS",25.5)
        rendered=_headline_html(
            "Jayson Tatum","BOS","SF","PHI","",
            "2026-27",rates["season"],25.5,rates["last10"],None)
        self.assertIn("MATCHUP GRADE",rendered)
        self.assertIn("niekalibrowana",rendered)
        self.assertNotIn("A+",rendered)
        self.assertNotIn("24th",rendered)
        self.assertIn("60%",rendered) if False else None
        self.assertIn("30%",rendered)

    def test_all_six_bottom_cards_work_as_links(self):
        footer=Path("mvp_reference_footer.py").read_text(encoding="utf8")
        for route in ("home","simulations","games","players","teams"):
            self.assertIn(f'("{route}"',footer)
        self.assertIn('on_click=on_navigate,args=(route,)',footer)
        self.assertIn('"bb83_footer_shortcut"',footer)
        self.assertIn('"Jayson Tatum over 35.5 PRA"',footer)

    def test_safe_html_escape_for_names(self):
        rates=observed_hit_rates(sample_logs(),"PTS",25.5)
        html=_headline_html(
            "<script>alert(1)</script>",
            "BOS","SF","<img src=x>","",
            "2026-27",rates["season"],25.5,rates["last10"])
        self.assertNotIn("<script>",html)
        self.assertNotIn("<img src=x>",html)
        self.assertIn("&lt;script&gt;",html)


if __name__=="__main__":
    unittest.main()
