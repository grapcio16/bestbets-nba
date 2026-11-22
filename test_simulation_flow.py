"""Flow reconstruction: synthetic end results only; absolutely no external NBA feed."""
import unittest
import numpy as np

from simulation_flow import conditional_flow, _allocate


class FlowTests(unittest.TestCase):
    def sample(self):
        rng = np.random.default_rng(74)
        return rng.integers(96, 129, 5000), rng.integers(99, 132, 5000)

    def test_same_5000_final_draws_without_fake_sequence_data(self):
        away, home = self.sample()
        before_a, before_h = away.copy(), home.copy()
        flow = conditional_flow(away, home, game_id="401999555",
                                model_id="research_form_v74")
        self.assertTrue(flow["available"])
        self.assertEqual(flow["n_sims"], 5000)
        self.assertEqual(flow["method"], "conditional_neutral_6min_v1")
        self.assertFalse(flow["rotation_available"])
        self.assertFalse(flow["scoring_runs_available"])
        self.assertIn("nie sa to dane play-by-play", flow["source"])
        self.assertEqual([r["minute"] for r in flow["timeline"]],
                         list(range(0, 49, 6)))
        self.assertEqual(flow["timeline"][0]["margin_mean"], 0.0)
        self.assertAlmostEqual(flow["timeline"][-1]["margin_mean"],
                               np.mean(home-away), delta=.011)
        self.assertAlmostEqual(sum(q["away_mean"] for q in flow["quarters"]),
                               away.mean(), delta=.06)
        self.assertAlmostEqual(sum(q["home_mean"] for q in flow["quarters"]),
                               home.mean(), delta=.06)
        for q in flow["quarters"]:
            self.assertAlmostEqual(q["away_outscores_pct"]+
                                   q["home_outscores_pct"]+
                                   q["tie_pct"], 100, delta=.16)
        np.testing.assert_array_equal(before_a, away)
        np.testing.assert_array_equal(before_h, home)
        self.assertEqual(flow, conditional_flow(
            away, home, game_id="401999555", model_id="research_form_v74"))

    def test_reconstructed_windows_exactly_conserve_each_score(self):
        rng = np.random.default_rng(5)
        points = rng.integers(70, 150, 5000)
        weights = rng.dirichlet(np.full(8, 20.0), size=5000)
        allocation = _allocate(points, weights, rng)
        np.testing.assert_array_equal(allocation.sum(axis=1), points)
        self.assertTrue((allocation >= 0).all())

    def test_incomplete_or_invalid_draws_fail_closed(self):
        a, h = self.sample()
        for broken in (a[:4999], np.full(5000, float("nan")),
                       np.full(5000, -10)):
            self.assertFalse(conditional_flow(
                broken, h, game_id="1", model_id="test")["available"])

    def test_pdf_is_generated_from_server_flow_only(self):
        a, h = self.sample()
        flow = conditional_flow(a, h, game_id="401999555",
                                model_id="research_form_v74")
        from flow_report import build_flow_pdf
        pdf = build_flow_pdf(
            day="2026-11-23", game_id="401999555", model_id="research_form_v74",
            away="NYK", home="BOS", variant="base",
            stats={"away_points": float(a.mean()), "home_points": float(h.mean())},
            flow=flow)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertLess(len(pdf), 200_000)
        with self.assertRaises(ValueError):
            build_flow_pdf(
                day="2026-11-23", game_id="401999555", model_id="research_form_v74",
                away="NYK", home="BOS", variant="base", stats={},
                flow={"available": False})


if __name__ == "__main__":
    unittest.main()
