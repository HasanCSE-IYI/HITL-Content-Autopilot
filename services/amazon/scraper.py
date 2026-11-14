import re
import json
import random
import logging
from typing import Optional, List, Dict, Any
import requests
from bs4 import BeautifulSoup
from core.models import AmazonProduct
from services.amazon.parser import build_affiliate_url

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0"
]

def get_headers() -> Dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1"
    }

def scrape_amazon_product(asin: str, affiliate_tag: str, country: str = "com") -> AmazonProduct:
    """
    Scrapes product details for a given ASIN from Amazon.
    Returns an AmazonProduct object.
    """
    url = f"https://www.amazon.{country}/dp/{asin}"
    affiliate_url = build_affiliate_url(asin, affiliate_tag, country)

    product = AmazonProduct(
        asin=asin,
        title=f"Amazon Product ({asin})",
        affiliate_url=affiliate_url,
        price="Check Price on Amazon"
    )

    try:
        session = requests.Session()
        resp = session.get(url, headers=get_headers(), timeout=12)
        if resp.status_code != 200:
            logger.warning(f"Amazon returned status {resp.status_code} for ASIN {asin}")
            return product

        soup = BeautifulSoup(resp.content, "html.parser")

        # 1. Title
        title_el = soup.find(id="productTitle") or soup.find("span", {"id": "title"})
        if title_el:
            product.title = title_el.get_text(strip=True)

        # 2. Price
        # Look for offscreen price or main price block
        price_el = soup.select_one(".a-price .a-offscreen") or soup.find(id="priceblock_ourprice") or soup.find(id="priceblock_dealprice")
        if price_el:
            price_text = price_el.get_text(strip=True)
            if price_text:
                product.price = price_text

        # 3. Rating
        rating_el = soup.select_one("#acrPopover span.a-icon-alt") or soup.select_one("span[data-hook='rating-out-of-text']")
        if rating_el:
            rating_match = re.search(r"(\d+(?:\.\d+)?)", rating_el.get_text(strip=True))
            if rating_match:
                try:
                    product.rating = float(rating_match.group(1))
                except ValueError:
                    pass

        # 4. Review count
        rev_count_el = soup.find(id="acrCustomerReviewText")
        if rev_count_el:
            count_match = re.search(r"([\d,]+)", rev_count_el.get_text(strip=True))
            if count_match:
                try:
                    product.review_count = int(count_match.group(1).replace(",", ""))
                except ValueError:
                    pass

        # 5. Bullet point features
        bullets = []
        feature_div = soup.find(id="feature-bullets")
        if feature_div:
            for item in feature_div.select("ul li span.a-list-item"):
                text = item.get_text(strip=True)
                if text and not text.lower().startswith("make sure this fits"):
                    bullets.append(text)
        product.features = bullets[:8]

        # 6. Main Image
        img_el = soup.find(id="landingImage") or soup.find(id="imgBlkFront")
        if img_el:
            # Check dynamic images json
            dynamic_data = img_el.get("data-a-dynamic-image")
            if dynamic_data:
                try:
                    img_dict = json.loads(dynamic_data)
                    # Pick highest resolution URL
                    sorted_images = sorted(img_dict.items(), key=lambda x: x[1][0] * x[1][1], reverse=True)
                    if sorted_images:
                        product.main_image = sorted_images[0][0]
                except Exception:
                    pass
            if not product.main_image:
                product.main_image = img_el.get("data-old-hires") or img_el.get("src")

        # 7. Customer Reviews / Highlights (for pros/cons synthesis)
        review_snippets = []
        for rev_body in soup.select("span[data-hook='review-body'] span")[:5]:
            snippet = rev_body.get_text(strip=True)
            if snippet:
                review_snippets.append(snippet)
        
        # Populate basic pros based on bullets if available
        if bullets:
            product.pros = bullets[:3]

    except Exception as e:
        logger.error(f"Error scraping ASIN {asin}: {e}")

    return product
