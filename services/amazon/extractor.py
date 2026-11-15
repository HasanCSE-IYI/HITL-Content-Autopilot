import re
import logging
from typing import List, Optional, Dict, Any
from core.models import AmazonProduct
from core.config import settings
from services.amazon.parser import extract_asin, build_affiliate_url
from services.amazon.scraper import scrape_amazon_product
from services.amazon.paapi import AmazonPAAPIClient
from services.amazon.adapter import get_product_discovery_adapter
from services.amazon.csv_importer import parse_product_facts_csv

logger = logging.getLogger(__name__)

DEFAULT_BADGES = [
    "Our Top Pick",
    "Best Value / Budget Pick",
    "Premium Choice",
    "Best Performance",
    "Runner Up",
    "Editor's Choice",
    "Most Versatile",
    "Best for Beginners"
]

def parse_manual_product_block(block: str, affiliate_tag: str, country: str = "com", index: int = 1) -> AmazonProduct:
    """
    Parses a user-written product fact block into an AmazonProduct object.
    Supports key-value formats (e.g. Title: ..., Price: ..., Specs: ..., Pros: ..., Link: ...)
    or simple bullet lines.
    """
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    title = f"Product #{index}"
    price = "Check Price on Amazon"
    features = []
    pros = []
    cons = []
    asin = f"MANUAL{index:03d}"
    affiliate_url = ""

    for line in lines:
        lower = line.lower()
        if lower.startswith("product:") or lower.startswith("title:") or lower.startswith("name:"):
            title = line.split(":", 1)[1].strip()
        elif lower.startswith("price:"):
            price = line.split(":", 1)[1].strip()
        elif lower.startswith("specs:") or lower.startswith("features:"):
            raw_specs = line.split(":", 1)[1].strip()
            features.extend([s.strip() for s in re.split(r"[,;|]", raw_specs) if s.strip()])
        elif lower.startswith("pros:") or lower.startswith("advantages:"):
            raw_pros = line.split(":", 1)[1].strip()
            pros.extend([p.strip() for p in re.split(r"[,;|]", raw_pros) if p.strip()])
        elif lower.startswith("cons:") or lower.startswith("drawbacks:"):
            raw_cons = line.split(":", 1)[1].strip()
            cons.extend([c.strip() for c in re.split(r"[,;|]", raw_cons) if c.strip()])
        elif lower.startswith("link:") or lower.startswith("url:"):
            raw_url = line.split(":", 1)[1].strip()
            extracted = extract_asin(raw_url)
            if extracted:
                asin = extracted
                affiliate_url = build_affiliate_url(extracted, affiliate_tag, country)
            else:
                affiliate_url = raw_url
        elif lower.startswith("asin:"):
            raw_asin = line.split(":", 1)[1].strip().upper()
            if len(raw_asin) == 10:
                asin = raw_asin
                affiliate_url = build_affiliate_url(asin, affiliate_tag, country)
        elif not title or title.startswith("Product #"):
            # First non-empty line without key could be title
            title = line

    if not affiliate_url:
        affiliate_url = build_affiliate_url(asin, affiliate_tag, country)

    return AmazonProduct(
        asin=asin,
        title=title,
        price=price,
        features=features[:8] if features else [title],
        pros=pros if pros else features[:3],
        cons=cons if cons else ["Availability may vary"],
        affiliate_url=affiliate_url,
        badge=DEFAULT_BADGES[(index - 1) % len(DEFAULT_BADGES)],
        provenance=f"Manual Fact Entry ({datetime_stamp()})"
    )

def datetime_stamp() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")

def fetch_products_hybrid(
    inputs: List[str],
    affiliate_tag: Optional[str] = None,
    country: Optional[str] = None,
    manual_facts_text: Optional[str] = None
) -> List[AmazonProduct]:
    """
    Hybrid product fetcher:
    1. If manual_facts_text is provided, parses manual product blocks.
    2. Otherwise extracts ASINs from inputs.
    3. Tries Amazon PA-API 5.0 if credentials configured in Settings.
    4. Falls back to Smart Scraper for missing items.
    """
    tag = affiliate_tag or settings.AMAZON_ASSOCIATE_TAG
    loc = country or settings.AMAZON_COUNTRY

    # 1. Check for manual facts blocks (or CSV text)
    if manual_facts_text and manual_facts_text.strip():
        first_line = manual_facts_text.strip().splitlines()[0].lower()
        if "asin," in first_line or "title," in first_line or "product," in first_line:
            csv_products = parse_product_facts_csv(manual_facts_text, affiliate_tag=tag, country=loc)
            if csv_products:
                return csv_products

        # Blocks separated by double newline or '---'
        raw_blocks = re.split(r"\n\s*\n|---+", manual_facts_text.strip())
        manual_products = []
        for idx, block in enumerate(raw_blocks):
            if block.strip():
                prod = parse_manual_product_block(block.strip(), affiliate_tag=tag, country=loc, index=idx+1)
                manual_products.append(prod)
        if manual_products:
            return manual_products

    # 2. Extract valid ASINs from inputs
    asins = []
    for item in inputs:
        parsed = extract_asin(item)
        if parsed and parsed not in asins:
            asins.append(parsed)

    if not asins:
        logger.warning("No valid ASINs found in inputs")
        return []

    # 3. Retrieve products via Section 16 Product Discovery Adapter
    adapter = get_product_discovery_adapter()
    discovered_products = adapter.get_items(asins, marketplace=loc, tracking_id=tag)
    products_map = {p.asin: p for p in discovered_products}

    # 4. For any missing ASINs, scrape
    for asin in asins:
        if asin not in products_map:
            logger.info(f"Scraping product data for ASIN {asin}...")
            product = scrape_amazon_product(asin, affiliate_tag=tag, country=loc)
            product.provenance = f"Amazon Smart Scraper ({datetime_stamp()})"
            products_map[asin] = product

    # 5. Preserve original order and assign badges
    ordered_products = []
    for idx, asin in enumerate(asins):
        if asin in products_map:
            prod = products_map[asin]
            if not prod.badge:
                prod.badge = DEFAULT_BADGES[idx % len(DEFAULT_BADGES)]
            ordered_products.append(prod)

    return ordered_products
