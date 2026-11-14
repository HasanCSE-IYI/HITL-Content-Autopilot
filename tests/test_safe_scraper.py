import pytest
from unittest.mock import patch, MagicMock
from services.amazon.scraper import (
    get_anti_block_headers,
    is_verification_challenge,
    scrape_amazon_product
)
from core.database import cache_product, get_cached_product
from core.models import AmazonProduct

def test_anti_block_headers_structure():
    headers = get_anti_block_headers()
    assert "User-Agent" in headers
    assert "Accept" in headers
    assert "Accept-Language" in headers
    assert "Upgrade-Insecure-Requests" in headers
    assert "Sec-Fetch-Mode" in headers
    assert headers["DNT"] == "1"

def test_is_verification_challenge_detection():
    # Detects captcha text
    captcha_html = "<html><body><h4>Enter the characters you see below</h4><img src='captcha.jpg'></body></html>"
    assert is_verification_challenge(captcha_html, 200) is True

    # Detects robot check
    robot_html = "<html><title>Robot Check</title><body>Please verify you are a human.</body></html>"
    assert is_verification_challenge(robot_html, 200) is True

    # Detects 503 / 403 status codes
    assert is_verification_challenge("<html>Forbidden</html>", 403) is True
    assert is_verification_challenge("<html>Service Unavailable</html>", 503) is True

    # Normal product page
    clean_html = "<html><title>Keychron K2 Mechanical Keyboard</title><span id='productTitle'>Keychron K2</span></html>"
    assert is_verification_challenge(clean_html, 200) is False

def test_scraped_product_24h_caching():
    test_asin = "B0TESTCACHE"
    sample_prod = AmazonProduct(
        asin=test_asin,
        title="Cached Mechanical Gaming Keyboard",
        price="$79.99",
        rating=4.6,
        review_count=1250,
        features=["Hot-swappable switches", "RGB backlight"],
        affiliate_url=f"https://www.amazon.com/dp/{test_asin}?tag=test-20"
    )

    # Save to SQLite 24h cache
    cache_product(sample_prod, country="com")

    # Fetch from cache
    cached = get_cached_product(test_asin, country="com", max_age_hours=24)
    assert cached is not None
    assert cached.asin == test_asin
    assert cached.title == "Cached Mechanical Gaming Keyboard"
    assert cached.price == "$79.99"
    assert cached.rating == 4.6

def test_scrape_amazon_product_cache_hit_bypasses_network():
    test_asin = "B0CACHEHIT1"
    sample_prod = AmazonProduct(
        asin=test_asin,
        title="Immediate Cache Hit Item",
        price="$49.99",
        affiliate_url=f"https://www.amazon.com/dp/{test_asin}?tag=test-20"
    )
    cache_product(sample_prod, country="com")

    # Call scrape_amazon_product with use_cache=True; session.get should NOT be called
    with patch("requests.Session.get") as mock_get:
        prod = scrape_amazon_product(test_asin, affiliate_tag="test-20", country="com", use_cache=True, apply_delay=False)
        assert prod.title == "Immediate Cache Hit Item"
        mock_get.assert_not_called()

def test_scrape_amazon_product_graceful_challenge_fallback():
    test_asin = "B0CHALLENGE"
    challenge_html = "<html><title>Robot Check</title><body>Enter the characters you see below</body></html>"

    with patch("requests.Session.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = challenge_html
        mock_get.return_value = mock_resp

        # Should not crash; returns safe fallback product
        prod = scrape_amazon_product(test_asin, affiliate_tag="test-20", country="com", use_cache=False, apply_delay=False)
        assert prod.asin == test_asin
        assert "Amazon Product" in prod.title or "Check Price" in prod.price
        assert "Verification Notice" in prod.provenance
