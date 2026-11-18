"""Allowlist for public subscription destinations (never Stripe private keys)."""
from urllib.parse import urlparse


def validated_checkout_url(url: str) -> str:
    url = str(url or "").strip()
    try:
        parsed = urlparse(url)
    except ValueError:
        return ""
    if (parsed.scheme != "https" or parsed.hostname not in
            {"buy.stripe.com", "checkout.stripe.com"} or
            parsed.username or parsed.password or not parsed.path.strip("/")):
        return ""
    return url


def is_test_checkout_url(url: str) -> bool:
    """Identify test sessions from the Stripe path, never from URL query text."""
    path = urlparse(url).path.strip("/")
    return path.startswith("test_") or path.startswith("c/pay/cs_test_")
