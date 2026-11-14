import logging
from typing import List, Optional
from core.models import AmazonProduct
from core.config import settings
from services.amazon.parser import extract_asin, build_affiliate_url
from services.amazon.scraper import scrape_amazon_product
from services.amazon.paapi import AmazonPAAPIClient

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

def fetch_products_hybrid(
    inputs: List[str],
    affiliate_tag: Optional[str] = None,
    country: Optional[str] = None
) -> List[AmazonProduct]:
    """
    Hybrid product fetcher:
    1. Extracts ASINs from URLs or strings.
    2. Tries Amazon PA-API 5.0 if configured.
    3. Seamlessly falls back to Smart Scraper for missing or all items.
    4. Automatically assigns comparison badges.
    """
    tag = affiliate_tag or settings.AMAZON_ASSOCIATE_TAG
    loc = country or settings.AMAZON_COUNTRY

    # 1. Extract valid ASINs
    asins = []
    for item in inputs:
        parsed = extract_asin(item)
        if parsed and parsed not in asins:
            asins.append(parsed)

    if not asins:
        logger.warning("No valid ASINs found in inputs")
        return []

    products_map = {}

    # 2. Try PA-API if credentials available
    if settings.AMAZON_ACCESS_KEY and settings.AMAZON_SECRET_KEY:
        try:
            logger.info(f"Attempting PA-API 5.0 fetch for {len(asins)} items...")
            client = AmazonPAAPIClient(
                access_key=settings.AMAZON_ACCESS_KEY,
                secret_key=settings.AMAZON_SECRET_KEY,
                associate_tag=tag,
                country=loc
            )
            paapi_results = client.get_items(asins)
            for p in paapi_results:
                products_map[p.asin] = p
        except Exception as e:
            logger.warning(f"PA-API attempt failed: {e}. Falling back to scraper.")

    # 3. For any missing ASINs, scrape
    for asin in asins:
        if asin not in products_map:
            logger.info(f"Scraping product data for ASIN {asin}...")
            product = scrape_amazon_product(asin, affiliate_tag=tag, country=loc)
            products_map[asin] = product

    # 4. Preserve original order and assign badges
    ordered_products = []
    for idx, asin in enumerate(asins):
        if asin in products_map:
            prod = products_map[asin]
            if not prod.badge:
                prod.badge = DEFAULT_BADGES[idx % len(DEFAULT_BADGES)]
            ordered_products.append(prod)

    return ordered_products
