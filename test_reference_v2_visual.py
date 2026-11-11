"""Offline visual-contract checks for the user-approved premium BestBets V2 reference."""
import unittest


class ReferenceLook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from bestbets_v2_preview import HTML, CSS, JS
        cls.html,cls.css,cls.js=HTML,CSS,JS

    def test_reference_brand_and_controls(self):
        self.assertIn("NBA ANALYTICS",self.html)
        self.assertIn('id="clear-query"',self.html)
        self.assertIn('aria-label="Wyczyść wyszukiwanie"',self.html)
        self.assertIn('id="query"',self.html)
        self.assertIn('id="chart-svg"',self.html)
        self.assertIn('id="hero"',self.html)
        self.assertIn('id="home-selected-name"',self.html)
        self.assertIn('id="home-player-avatar"',self.html)
        self.assertGreaterEqual(self.html.count('<svg'),12)

    def test_no_fake_premium_ratings_or_forecast_numbers(self):
        self.assertIn('id="hero-grade">—',self.html)
        self.assertIn('id="rate-season">—',self.html)
        self.assertIn('id="home-selected-name"',self.html)
        self.assertNotIn('71.3%',self.html)
        self.assertNotIn('226.6',self.html)
        self.assertNotIn('50% A-',self.html)

    def test_reference_look_but_true_responsiveness(self):
        self.assertIn('radial-gradient',self.css)
        self.assertIn('--bb-orange:#ff8b1f',self.css)
        self.assertIn('--sidebar-width:clamp(',self.css)
        self.assertIn('grid-template-columns:minmax(0,1fr) clamp(440px,32vw,610px)',self.css)
        self.assertIn('@media (max-width:640px)',self.css)
        self.assertNotIn('bb-v2-viewport',self.html)
        self.assertNotIn('<foreignObject',self.html)
        self.assertNotIn('streamlit:setFrameHeight',self.js)

    def test_under_chart_correctly_marks_losses_red(self):
        self.assertIn('state.side==="UNDER"',self.js)
        self.assertIn('under?"#00ec79":over?"#ff514b"',self.js)
        self.assertIn('setImage("home-player-avatar"',self.js)
        self.assertIn('id="query"',self.html)
        self.assertIn('clearButton.addEventListener("click"',self.js)

    def test_team_cards_use_local_data_urls_or_fallback(self):
        self.assertIn('class="mini-ball team-mark team-BOS"',self.html)
        self.assertIn('class="mini-ball team-mark team-NYK"',self.html)
        self.assertIn('class="mini-ball team-mark team-PHI"',self.html)
        self.assertIn('alt="" loading="lazy"',self.html)

if __name__ == "__main__":
    unittest.main()
