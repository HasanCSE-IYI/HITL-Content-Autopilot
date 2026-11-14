import pytest
from core.models import AmazonProduct
from services.research.product_scorer import score_product, ProductScore

def test_product_scorer_high_quality_product():
    product = AmazonProduct(
        asin="B08N5WRWNW",
        title="Keychron K2 Pro Wireless Mechanical Keyboard for Mac & Windows",
        brand="Keychron",
        price="$89.99",
        rating=4.7,
        review_count=2300,
        features=[
            "75% Compact Layout with 84 keys",
            "QMK/VIA fully programmable key remapping",
            "Hot-swappable Keychron K Pro switches",
            "Wireless Bluetooth 5.1 and wired USB-C connectivity"
        ],
        main_image="https://m.media-amazon.com/images/I/71xyz123.jpg",
        affiliate_url="https://www.amazon.com/dp/B08N5WRWNW?tag=test-20",
        badge="Best Overall",
        pros=["Exceptional tactile feel", "Hot-swap PCB"],
        cons=["Slightly tall front edge"]
    )

    score: ProductScore = score_product(product, keyword="best wireless mechanical keyboard")
    assert isinstance(score, ProductScore)
    assert score.total_score >= 85
    assert score.grade == "Excellent"
    assert score.breakdown["Relevance"] >= 20
    assert score.breakdown["Verified Data"] == 25
    assert score.breakdown["Ratings & Reviews"] == 20
    assert score.breakdown["Price Viability"] == 15
    assert score.breakdown["Content Fit"] == 10
    assert "High social proof" in score.strengths[0] or any("social proof" in s.lower() for s in score.strengths)
    assert len(score.missing_data) == 0

def test_product_scorer_detects_missing_data():
    incomplete_product = AmazonProduct(
        asin="B0INCOMPLETE",
        title="Generic Mechanical Keyboard",
        price="Check Price on Amazon",
        rating=None, # Missing rating
        review_count=None, # Missing reviews
        features=[], # Missing features
        main_image=None, # Missing image
        brand=None # Missing brand
    )

    score: ProductScore = score_product(incomplete_product, keyword="ergonomic keyboard")
    assert score.total_score < 50
    assert score.grade == "Needs Attention"
    assert any("star rating" in m.lower() for m in score.missing_data)
    assert any("review count" in m.lower() for m in score.missing_data)
    assert any("image" in m.lower() for m in score.missing_data)
    assert any("bullet points" in m.lower() or "features" in m.lower() for m in score.missing_data)
    assert any("brand" in m.lower() for m in score.missing_data)

def test_product_scorer_keyword_relevance_penalty():
    unrelated_product = AmazonProduct(
        asin="B0COFFEE123",
        title="Stainless Steel Pour Over Coffee Maker with Glass Carafe",
        brand="BrewMaster",
        price="$29.99",
        rating=4.5,
        review_count=850,
        features=["Durable filter", "Heat resistant glass"],
        main_image="https://m.media-amazon.com/images/I/coffee.jpg"
    )

    # Scored against wireless keyboard keyword
    score = score_product(unrelated_product, keyword="wireless mechanical keyboard")
    assert score.relevance_score <= 15
