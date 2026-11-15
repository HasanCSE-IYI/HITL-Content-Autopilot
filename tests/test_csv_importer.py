import pytest
from services.amazon.csv_importer import (
    generate_product_facts_csv_template,
    generate_bulk_keywords_csv_template,
    parse_product_facts_csv,
    parse_bulk_keywords_csv
)

def test_generate_product_facts_csv_template():
    tpl = generate_product_facts_csv_template()
    assert "asin,title,price,specs,pros,cons,url" in tpl
    assert "Keychron K2 Pro" in tpl
    assert "B0CX23V2ZT" in tpl

def test_generate_bulk_keywords_csv_template():
    tpl = generate_bulk_keywords_csv_template()
    assert "keyword,asins,article_type" in tpl
    assert "Best Wireless Mechanical Keyboards" in tpl
    assert "roundup" in tpl

def test_parse_product_facts_csv():
    csv_data = """asin,title,price,specs,pros,cons,url
B0TEST0001,Test Mechanical Keyboard,$99.99,"RGB; Hot-Swap; Wireless","Great build; Low latency","High profile",https://www.amazon.com/dp/B0TEST0001
B0TEST0002,Ergonomic Vertical Mouse,$49.99,"Bluetooth 5.0, 4000 DPI","Ergonomic grip, USB-C","Right-handed only",https://www.amazon.com/dp/B0TEST0002
"""
    products = parse_product_facts_csv(csv_data, affiliate_tag="affil-20", country="com")
    assert len(products) == 2

    p1 = products[0]
    assert p1.asin == "B0TEST0001"
    assert p1.title == "Test Mechanical Keyboard"
    assert p1.price == "$99.99"
    assert "Hot-Swap" in p1.features or "RGB" in p1.features
    assert "Great build" in p1.pros
    assert "High profile" in p1.cons
    assert "affil-20" in p1.affiliate_url

    p2 = products[1]
    assert p2.asin == "B0TEST0002"
    assert p2.title == "Ergonomic Vertical Mouse"
    assert p2.price == "$49.99"

def test_parse_product_facts_csv_empty():
    assert parse_product_facts_csv("") == []
    assert parse_product_facts_csv("   ") == []

def test_parse_bulk_keywords_csv():
    csv_data = """keyword,asins,article_type
Best Gaming Mice 2026,B01; B02,roundup
Top Standing Desks,B03,roundup
Best Gaming Mice 2026,B04,comparison
Logitech MX Master Review,B05,single_review
"""
    tasks, duplicates = parse_bulk_keywords_csv(csv_data)
    assert len(tasks) == 3
    assert len(duplicates) == 1
    assert "Best Gaming Mice 2026" in duplicates

    assert tasks[0]["keyword"] == "Best Gaming Mice 2026"
    assert tasks[0]["asins"] == "B01; B02"
    assert tasks[0]["article_type"] == "roundup"

    assert tasks[1]["keyword"] == "Top Standing Desks"
    assert tasks[2]["keyword"] == "Logitech MX Master Review"
    assert tasks[2]["article_type"] == "single_review"

def test_parse_csv_with_utf8_bom():
    # Simulate Windows Excel export with leading \ufeff Byte Order Mark
    bom_product_csv = "\ufeffasin,title,price,specs,pros,cons,url\nB0BOMTEST1,BOM Keyboard,$79.99,Specs,Pros,Cons,https://amazon.com/dp/B0BOMTEST1"
    products = parse_product_facts_csv(bom_product_csv)
    assert len(products) == 1
    assert products[0].asin == "B0BOMTEST1"
    assert products[0].title == "BOM Keyboard"

    bom_kw_csv = "\ufeffkeyword,asins,article_type\nBest Mechanical Keyboards,B0BOMTEST1,roundup"
    tasks, duplicates = parse_bulk_keywords_csv(bom_kw_csv)
    assert len(tasks) == 1
    assert tasks[0]["keyword"] == "Best Mechanical Keyboards"
