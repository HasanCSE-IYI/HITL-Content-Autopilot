import pytest
from unittest.mock import patch, MagicMock
from services.amazon.scraper import (
    parse_proxy_pool,
    get_active_proxy,
    check_proxy_connection,
    scrape_amazon_product
)

def test_parse_proxy_pool_empty():
    assert parse_proxy_pool("") == []
    assert parse_proxy_pool(None) == []

def test_parse_proxy_pool_normalization():
    raw = """
    192.168.1.100:8080
    http://user:pass@10.0.0.1:3128
    socks5://proxy.example.com:1080
    """
    pool = parse_proxy_pool(raw)
    assert len(pool) == 3
    assert pool[0] == "http://192.168.1.100:8080"
    assert pool[1] == "http://user:pass@10.0.0.1:3128"
    assert pool[2] == "socks5://proxy.example.com:1080"

def test_get_active_proxy():
    assert get_active_proxy("") is None
    pool_str = "http://proxy1:8080\nhttp://proxy2:8080"
    active = get_active_proxy(pool_str)
    assert active is not None
    assert "http" in active
    assert "https" in active
    assert active["http"] in ["http://proxy1:8080", "http://proxy2:8080"]

def test_check_proxy_connection_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {"ip": "198.51.100.42"}

    with patch("requests.get", return_value=mock_resp):
        res = check_proxy_connection("http://198.51.100.42:8080")
        assert res["success"] is True
        assert res["ip"] == "198.51.100.42"
        assert "Verified" in res["message"] or "198.51.100.42" in res["message"]

def test_check_proxy_connection_timeout():
    import requests
    with patch("requests.get", side_effect=requests.exceptions.Timeout("Timed out")):
        res = check_proxy_connection("http://198.51.100.42:8080", timeout=2)
        assert res["success"] is False
        assert "timed out" in res["message"].lower()

def test_scrape_amazon_product_with_rotating_proxy():
    sample_html = """
    <html>
        <body>
            <span id="productTitle">Ergonomic Wireless Mouse</span>
            <span class="a-price"><span class="a-offscreen">$39.99</span></span>
        </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = sample_html
    mock_resp.content = sample_html.encode("utf-8")

    with patch("services.amazon.scraper.get_active_proxy", return_value={"http": "http://proxy:8080", "https": "http://proxy:8080"}), \
         patch("requests.Session.get", return_value=mock_resp) as mock_get:
        
        product = scrape_amazon_product("B09TESTPROX", affiliate_tag="aff-20", use_cache=False, apply_delay=False)
        assert product.title == "Ergonomic Wireless Mouse"
        assert product.price == "$39.99"
        # Confirm proxies parameter was passed to session.get
        mock_get.assert_called_once()
        _, kwargs = mock_get.call_args
        assert kwargs.get("proxies") == {"http": "http://proxy:8080", "https": "http://proxy:8080"}
