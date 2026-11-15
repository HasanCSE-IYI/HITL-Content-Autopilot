import pytest
from services.amazon.adapter import (
    ManualDiscoveryAdapter,
    OfficialPAAPIDiscoveryAdapter,
    HybridDiscoveryAdapter,
    get_product_discovery_adapter
)

def test_manual_discovery_adapter():
    adapter = ManualDiscoveryAdapter()
    assert adapter.is_configured() is True
    assert "Manual" in adapter.get_adapter_name()

    items = adapter.get_items(["B0CX23V2ZT"], marketplace="com", tracking_id="testtag-20")
    assert len(items) == 1
    assert items[0].asin == "B0CX23V2ZT"
    assert "testtag-20" in items[0].affiliate_url
    assert "Manual" in items[0].provenance

def test_official_paapi_adapter_unconfigured():
    adapter = OfficialPAAPIDiscoveryAdapter(access_key="", secret_key="")
    assert adapter.is_configured() is False
    assert "PA-API" in adapter.get_adapter_name()

    # Falls back gracefully to manual mode when unconfigured
    items = adapter.get_items(["B09V3HN1KC"], marketplace="com", tracking_id="tag-20")
    assert len(items) == 1
    assert items[0].asin == "B09V3HN1KC"

def test_official_paapi_adapter_configured():
    adapter = OfficialPAAPIDiscoveryAdapter(access_key="AKIAEXAMPLE", secret_key="SecretExample")
    assert adapter.is_configured() is True

def test_get_product_discovery_adapter_factory():
    adapter = get_product_discovery_adapter()
    assert adapter is not None
    assert hasattr(adapter, "get_items")
    assert hasattr(adapter, "search_products")
    assert hasattr(adapter, "is_configured")
