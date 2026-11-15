import pytest
from services.amazon.extractor import parse_manual_product_block, fetch_products_hybrid

def test_parse_manual_product_block():
    block = """
    Product: Keychron K2 Wireless Keyboard
    Price: $79.99
    Specs: 75% Layout, Hot-Swappable, RGB
    Pros: Great typing feel, compact
    Cons: Slightly high profile
    Link: https://www.amazon.com/dp/B08N5WRWNW
    """
    prod = parse_manual_product_block(block, affiliate_tag="mytag-20", country="com", index=1)
    assert prod.asin == "B08N5WRWNW"
    assert "Keychron K2" in prod.title
    assert prod.price == "$79.99"
    assert len(prod.features) >= 2
    assert len(prod.pros) >= 1
    assert len(prod.cons) >= 1
    assert "mytag-20" in prod.affiliate_url
    assert "Manual" in prod.provenance

def test_fetch_products_hybrid_manual():
    manual_text = """
    Product: Item A
    Price: $20
    Specs: Feature 1, Feature 2
    
    Product: Item B
    Price: $40
    Specs: Feature 3, Feature 4
    """
    products = fetch_products_hybrid([], manual_facts_text=manual_text)
    assert len(products) == 2
    assert products[0].title == "Item A"
    assert products[1].title == "Item B"
    assert products[0].price == "$20"

def test_fetch_products_hybrid_delegates_to_adapter(monkeypatch):
    from unittest.mock import MagicMock
    from core.models import AmazonProduct

    mock_adapter = MagicMock()
    mock_adapter.get_items.return_value = [
        AmazonProduct(
            asin="B0CX23V2ZT",
            title="Adapter Sourced Keyboard",
            price="$99.00",
            affiliate_url="https://amazon.com/dp/B0CX23V2ZT?tag=tag-20"
        )
    ]
    monkeypatch.setattr("services.amazon.extractor.get_product_discovery_adapter", lambda: mock_adapter)

    products = fetch_products_hybrid(["B0CX23V2ZT"])
    assert len(products) == 1
    assert products[0].asin == "B0CX23V2ZT"
    assert products[0].title == "Adapter Sourced Keyboard"
    mock_adapter.get_items.assert_called_once()
