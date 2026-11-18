"""Public checkout URL can never leak arbitrary destinations or secret keys."""
import unittest

from checkout_links import validated_checkout_url, is_test_checkout_url


class CheckoutURLTests(unittest.TestCase):
    def test_verified_stripe_payment_link(self):
        self.assertEqual(validated_checkout_url("https://buy.stripe.com/test_abc123"),
                         "https://buy.stripe.com/test_abc123")

    def test_rejects_external_or_insecure_links(self):
        for url in (
            "http://buy.stripe.com/test_abc123",
            "https://buy.stripe.com.attacker.example/abc123",
            "https://attacker.example/premium",
            "https://buy.stripe.com/",
        ):
            with self.subTest(url=url):
                self.assertEqual(validated_checkout_url(url), "")

    def test_query_string_cannot_fake_test_checkout(self):
        self.assertTrue(is_test_checkout_url("https://buy.stripe.com/test_abc123"))
        self.assertTrue(is_test_checkout_url("https://checkout.stripe.com/c/pay/cs_test_abc"))
        self.assertFalse(is_test_checkout_url(
            "https://buy.stripe.com/live123?reference=test_abc123"))


if __name__ == "__main__":
    unittest.main()
