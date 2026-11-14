import pytest
from core.models import AmazonProduct
from services.generator.schema import (
    generate_product_schema,
    generate_item_list_schema,
    generate_faq_schema,
    combine_schemas_to_html
)

def test_generate_product_schema():
    prod = AmazonProduct(
        asin="B08N5WRWNW",
        title="Sample Product",
        brand="Apple",
        rating=4.7,
        review_count=500,
        main_image="https://m.media-amazon.com/images/I/71TPda7cwUL.jpg",
        affiliate_url="https://amazon.com/dp/B08N5WRWNW?tag=test-20"
    )
    schema = generate_product_schema(prod)
    assert schema["@type"] == "Product"
    assert schema["name"] == "Sample Product"
    assert schema["brand"]["name"] == "Apple"
    assert schema["aggregateRating"]["ratingValue"] == "4.7"

def test_generate_item_list_schema():
    prods = [
        AmazonProduct(asin="B01", title="Item 1", affiliate_url="https://amazon.com/dp/B01"),
        AmazonProduct(asin="B02", title="Item 2", affiliate_url="https://amazon.com/dp/B02")
    ]
    schema = generate_item_list_schema(prods, "Best Items in 2026")
    assert schema["@type"] == "ItemList"
    assert len(schema["itemListElement"]) == 2
    assert schema["itemListElement"][0]["position"] == 1

def test_generate_faq_schema():
    faqs = [
        {"question": "How long does the battery last?", "answer": "Up to 18 hours."},
        {"question": "Is it waterproof?", "answer": "Yes, IPX8 rated."}
    ]
    schema = generate_faq_schema(faqs)
    assert schema["@type"] == "FAQPage"
    assert len(schema["mainEntity"]) == 2
    assert schema["mainEntity"][0]["name"] == "How long does the battery last?"

def test_combine_schemas_to_html():
    faqs = [{"question": "Q?", "answer": "A."}]
    schema = generate_faq_schema(faqs)
    html = combine_schemas_to_html([schema])
    assert '<script type="application/ld+json">' in html
    assert '"@type": "FAQPage"' in html
