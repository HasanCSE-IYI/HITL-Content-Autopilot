import pytest
from services.media.image_policy import (
    validate_product_image_policy,
    get_editorial_image_prompt,
    audit_article_images
)
from core.models import AmazonProduct

def test_validate_authorized_amazon_media_cdn():
    valid_amazon_urls = [
        "https://m.media-amazon.com/images/I/71xyz987._AC_SL1500_.jpg",
        "https://images-na.ssl-images-amazon.com/images/I/51abc123.jpg",
        "https://ws-na.amazon-adsystem.com/widgets/q?_encoding=UTF8&ASIN=B08N5WRWNW"
    ]
    for url in valid_amazon_urls:
        res = validate_product_image_policy(url)
        assert res["is_compliant"] is True
        assert res["source_type"] == "amazon_authorized"
        assert res["is_synthetic_ai"] is False

def test_validate_flags_synthetic_ai_images():
    synthetic_urls = [
        "https://cdn.openai.com/dall-e-3/product_render_fake_keychron.png",
        "https://cdn.midjourney.com/v6/mechanical_keyboard_close_up.webp",
        "https://assets.example.com/ai_generated_product_preview.jpg"
    ]
    for url in synthetic_urls:
        res = validate_product_image_policy(url)
        assert res["is_compliant"] is False
        assert res["source_type"] == "disallowed_ai_synthetic"
        assert res["is_synthetic_ai"] is True
        assert "synthetic" in res["reason"].lower()

def test_validate_licensed_external_asset():
    licensed_url = "https://cdn.mycustomnicheblog.com/uploads/2026/11/office-desk-setup.jpg"
    res = validate_product_image_policy(licensed_url)
    assert res["is_compliant"] is True
    assert res["source_type"] == "licensed_asset"
    assert res["is_synthetic_ai"] is False

def test_get_editorial_image_prompt_prohibits_fake_branding():
    prompt = get_editorial_image_prompt("wireless mechanical keyboards", "The Value-First Guide")
    assert "wireless mechanical keyboards" in prompt
    assert "The Value-First Guide" in prompt
    assert "Conceptual artwork only" in prompt
    assert "do not render recognizable physical trademarks" in prompt

def test_audit_article_images_scans_content():
    sample_content = """
    # The Best Wireless Keyboards

    Here is our top pick:
    ![Keychron K2](https://m.media-amazon.com/images/I/71xyz.jpg)

    And here is an unverified synthetic mock:
    <img src="https://example.com/midjourney/mockup.png" alt="Fake Mockup" />
    """
    _, audit_log = audit_article_images(sample_content, products=[])
    assert len(audit_log) == 2
    assert audit_log[0]["is_compliant"] is True
    assert audit_log[0]["source_type"] == "amazon_authorized"
    assert audit_log[1]["is_compliant"] is False
    assert audit_log[1]["is_synthetic_ai"] is True
