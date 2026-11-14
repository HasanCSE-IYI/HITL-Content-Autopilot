import pytest
from services.amazon.parser import extract_asin, build_affiliate_url

def test_extract_asin_standard_url():
    url = "https://www.amazon.com/dp/B08N5WRWNW"
    assert extract_asin(url) == "B08N5WRWNW"

def test_extract_asin_long_seo_url():
    url = "https://www.amazon.com/Apple-MacBook-13-inch-256GB-Storage/dp/B08N5WRWNW/ref=sr_1_1"
    assert extract_asin(url) == "B08N5WRWNW"

def test_extract_asin_gp_url():
    url = "https://www.amazon.com/gp/product/B09V3HN1KC"
    assert extract_asin(url) == "B09V3HN1KC"

def test_extract_asin_bare_string():
    assert extract_asin("b0cx23v2zt") == "B0CX23V2ZT"
    assert extract_asin(" B08N5WRWNW ") == "B08N5WRWNW"

def test_extract_asin_invalid():
    assert extract_asin("https://google.com") is None
    assert extract_asin("invalid_asin_string_too_long") is None
    assert extract_asin("") is None

def test_build_affiliate_url():
    link = build_affiliate_url("B08N5WRWNW", "testaffiliate-20", country="com")
    assert link == "https://www.amazon.com/dp/B08N5WRWNW?tag=testaffiliate-20"
