import pytest
from services.compliance.rules import (
    inject_compliance_markdown,
    enforce_nofollow_sponsored,
    FTC_DISCLOSURE_MARKDOWN
)

def test_inject_compliance_markdown():
    raw_md = "## 1. Top Pick\nHere is a review of product."
    compliant = inject_compliance_markdown(raw_md)
    assert "Affiliate Disclosure" in compliant
    assert "Product prices and availability are accurate" in compliant
    assert "As an Amazon Associate, we earn from qualifying purchases" in compliant

def test_enforce_nofollow_sponsored():
    html_input = '<p>Check it out: <a href="https://www.amazon.com/dp/B08N5WRWNW?tag=tag-20">Buy Now</a></p>'
    result = enforce_nofollow_sponsored(html_input)
    assert 'rel="nofollow sponsored"' in result
    assert 'target="_blank"' in result

def test_non_amazon_links_untouched():
    html_input = '<p>Visit <a href="https://mywebsite.com/about">About Us</a></p>'
    result = enforce_nofollow_sponsored(html_input)
    assert 'rel="nofollow sponsored"' not in result
