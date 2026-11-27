import unittest
from decimal import Decimal
from unittest.mock import patch
from admin_revenue import project_revenue, checkout_diagnostics, revenue_snapshot

class RevenueTest(unittest.TestCase):
    def test_default_projection(self):
        p = project_revenue(100, fixed_cost=100)
        self.assertEqual(p["monthly_gross"], Decimal("999.00"))
        self.assertEqual(p["annualized_gross"], Decimal("11988.00"))
        self.assertEqual(p["monthly_operating_result"], Decimal("899.00"))
        self.assertEqual(p["break_even_subscribers"], 11)

    def test_fees_and_variable_cost(self):
        p = project_revenue(100, 10, 100, 5, 0.5, 2)
        self.assertEqual(p["monthly_payment_fees"], Decimal("100.00"))
        self.assertEqual(p["monthly_operating_result"], Decimal("600.00"))
        self.assertEqual(p["break_even_subscribers"], 15)

    def test_no_positive_contribution(self):
        self.assertIsNone(project_revenue(1, 10, 100, 100)["break_even_subscribers"])

    def test_invalid_inputs(self):
        for args in ((-1,), (1.5,), (1,"NaN"), (1,10,0,101)):
            with self.assertRaises(ValueError):
                project_revenue(*args)

    def test_checkout_diagnostics_does_not_claim_verification(self):
        r = checkout_diagnostics("https://buy.stripe.com/test_fake", "true")
        self.assertEqual(r["checkout_mode"],"test")
        self.assertTrue(r["fulfillment_declared_ready"])
        self.assertFalse(r["stripe_verified"])
        self.assertIsNone(r["actual_revenue"])
        self.assertNotIn("test_fake",str(r))
        self.assertEqual(checkout_diagnostics("https://example.com",False)["checkout_mode"],"invalid")

    def test_non_admin_denied(self):
        for role in ("guest","free","premium"):
            with patch("access_control.current_role",return_value=role):
                self.assertEqual(revenue_snapshot(),{"status":"denied"})

if __name__ == "__main__":
    unittest.main()
