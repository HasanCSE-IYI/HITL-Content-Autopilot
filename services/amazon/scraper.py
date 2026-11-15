import re
import json
import random
import time
import logging
from typing import Optional, List, Dict, Any
import requests
from bs4 import BeautifulSoup
from core.models import AmazonProduct
from services.amazon.parser import build_affiliate_url
from core.database import get_cached_product, cache_product, get_setting

logger = logging.getLogger(__name__)

# Complete desktop browser fingerprints
BROWSER_PROFILES = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
        "Sec-Ch-Ua": "",
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
        "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Microsoft Edge";v="126"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
    }
]

def get_anti_block_headers() -> Dict[str, str]:
    profile = random.choice(BROWSER_PROFILES)
    headers = {
        "User-Agent": profile["User-Agent"],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1"
    }
    if profile["Sec-Ch-Ua"]:
        headers["Sec-Ch-Ua"] = profile["Sec-Ch-Ua"]
        headers["Sec-Ch-Ua-Mobile"] = profile["Sec-Ch-Ua-Mobile"]
        headers["Sec-Ch-Ua-Platform"] = profile["Sec-Ch-Ua-Platform"]
    return headers

def parse_proxy_pool(raw_config: Optional[str] = None) -> List[str]:
    """
    Parses a single or multi-line proxy string into a normalized list of proxy URLs.
    Supports:
      - ip:port
      - http://ip:port
      - http://username:password@ip:port
      - socks5://...
    """
    raw = (raw_config if raw_config is not None else get_setting("AMAZON_SCRAPER_PROXY", "")).strip()
    if not raw:
        return []
    lines = [p.strip() for p in re.split(r"[\n,;]", raw) if p.strip()]
    normalized = []
    for line in lines:
        if not re.match(r"^[a-zA-Z0-9]+://", line):
            line = f"http://{line}"
        normalized.append(line)
    return normalized

def get_active_proxy(raw_config: Optional[str] = None) -> Optional[Dict[str, str]]:
    """
    Randomly selects an active proxy from the configured rotating pool.
    """
    pool = parse_proxy_pool(raw_config)
    if not pool:
        return None
    selected = random.choice(pool)
    return {"http": selected, "https": selected}

def check_proxy_connection(proxy_url: str, timeout: int = 10) -> Dict[str, Any]:
    """
    Pings an IP check service through the target proxy to verify connectivity,
    external IP, and response latency.
    """
    clean_proxy = proxy_url.strip()
    if not clean_proxy:
        return {"success": False, "message": "Proxy URL is empty."}
    if not re.match(r"^[a-zA-Z0-9]+://", clean_proxy):
        clean_proxy = f"http://{clean_proxy}"

    proxies = {"http": clean_proxy, "https": clean_proxy}
    test_endpoints = [
        "https://api.ipify.org?format=json",
        "https://httpbin.org/ip"
    ]
    
    start_time = time.time()
    for endpoint in test_endpoints:
        try:
            resp = requests.get(endpoint, proxies=proxies, timeout=timeout)
            elapsed_ms = int((time.time() - start_time) * 1000)
            if resp.status_code == 200:
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                detected_ip = data.get("ip") or data.get("origin") or "Verified"
                return {
                    "success": True,
                    "ip": detected_ip,
                    "latency_ms": elapsed_ms,
                    "proxy": clean_proxy,
                    "message": f"Proxy connected successfully! Detected external IP: {detected_ip} (Latency: {elapsed_ms}ms)"
                }
        except requests.exceptions.Timeout:
            return {"success": False, "message": f"Connection timed out after {timeout} seconds via {clean_proxy}."}
        except Exception as e:
            return {"success": False, "message": f"Proxy connection error: {str(e)}"}
            
    return {"success": False, "message": "Failed to connect through proxy endpoints."}

def is_verification_challenge(html_text: str, status_code: int) -> bool:
    """
    Detects if Amazon served an anti-bot verification or captcha challenge.
    """
    if status_code in [503, 403]:
        return True
    lower = html_text.lower()
    challenge_indicators = [
        "enter the characters you see below",
        "to discuss automated access to amazon data",
        "api-services-support@amazon.com",
        "robot check",
        "automated access"
    ]
    return any(ind in lower for ind in challenge_indicators)

def scrape_amazon_product(
    asin: str,
    affiliate_tag: str,
    country: str = "com",
    use_cache: bool = True,
    apply_delay: bool = True
) -> AmazonProduct:
    """
    Safely fetches product details for an ASIN from Amazon with:
    1. 24-hour local SQLite cache check (eliminates redundant hits)
    2. Polite randomized jitter delay (2.5s-4.0s)
    3. Complete modern browser header profile
    4. Optional proxy support
    5. Anti-bot challenge detection and graceful fallback
    """
    clean_asin = asin.strip().upper()
    affiliate_url = build_affiliate_url(clean_asin, affiliate_tag, country)

    # 1. Check local 24-hour cache
    if use_cache:
        cached = get_cached_product(clean_asin, country=country, max_age_hours=24)
        if cached:
            # Refresh affiliate URL in case tracking tag changed
            cached.affiliate_url = affiliate_url
            cached.provenance = f"Local SQLite Cache (ASIN {clean_asin})"
            logger.info(f"Loaded ASIN {clean_asin} from local 24-hour cache.")
            return cached

    # 2. Polite randomized delay to avoid rate limiting
    if apply_delay:
        delay = random.uniform(2.5, 4.0)
        time.sleep(delay)

    product = AmazonProduct(
        asin=clean_asin,
        title=f"Amazon Product ({clean_asin})",
        affiliate_url=affiliate_url,
        price="Check Price on Amazon",
        provenance=f"Amazon Safe Scraper ({time.strftime('%Y-%m-%d')})"
    )

    url = f"https://www.amazon.{country}/dp/{clean_asin}"
    headers = get_anti_block_headers()

    # Rotating proxy from configured pool
    proxies = get_active_proxy()

    try:
        session = requests.Session()
        resp = session.get(url, headers=headers, proxies=proxies, timeout=14)

        # 3. Check for verification challenge
        if is_verification_challenge(resp.text, resp.status_code):
            logger.warning(f"Amazon requested verification for ASIN {clean_asin} (Status {resp.status_code}). Falling back gracefully.")
            product.provenance = "Amazon Verification Notice (Link Preserved, Ready for Facts)"
            return product

        if resp.status_code != 200:
            logger.warning(f"Amazon returned status {resp.status_code} for ASIN {clean_asin}")
            return product

        soup = BeautifulSoup(resp.content, "html.parser")

        # 4. Extract Title
        title_el = soup.find(id="productTitle") or soup.find("span", {"id": "title"}) or soup.find("h1", {"id": "title"})
        if title_el:
            product.title = title_el.get_text(strip=True)

        # 5. Extract Price
        price_el = (
            soup.select_one(".a-price .a-offscreen")
            or soup.find(id="priceblock_ourprice")
            or soup.find(id="priceblock_dealprice")
            or soup.select_one(".apexPriceToPay .a-offscreen")
        )
        if price_el:
            price_text = price_el.get_text(strip=True)
            if price_text:
                product.price = price_text

        # 6. Extract Rating
        rating_el = soup.select_one("#acrPopover span.a-icon-alt") or soup.select_one("span[data-hook='rating-out-of-text']")
        if rating_el:
            rating_match = re.search(r"(\d+(?:\.\d+)?)", rating_el.get_text(strip=True))
            if rating_match:
                try:
                    product.rating = float(rating_match.group(1))
                except ValueError:
                    pass

        # 7. Extract Review Count
        rev_count_el = soup.find(id="acrCustomerReviewText")
        if rev_count_el:
            count_match = re.search(r"([\d,]+)", rev_count_el.get_text(strip=True))
            if count_match:
                try:
                    product.review_count = int(count_match.group(1).replace(",", ""))
                except ValueError:
                    pass

        # 8. Extract Bullet Points / Specs
        bullets = []
        feature_div = soup.find(id="feature-bullets")
        if feature_div:
            for item in feature_div.select("ul li span.a-list-item"):
                text = item.get_text(strip=True)
                if text and not text.lower().startswith("make sure this fits"):
                    bullets.append(text)
        product.features = bullets[:8]

        # 9. Extract High-Res Image (Authorized Amazon Asset URL)
        img_el = soup.find(id="landingImage") or soup.find(id="imgBlkFront")
        if img_el:
            dynamic_data = img_el.get("data-a-dynamic-image")
            if dynamic_data:
                try:
                    img_dict = json.loads(dynamic_data)
                    sorted_images = sorted(img_dict.items(), key=lambda x: x[1][0] * x[1][1], reverse=True)
                    if sorted_images:
                        product.main_image = sorted_images[0][0]
                except Exception:
                    pass
            if not product.main_image:
                product.main_image = img_el.get("data-old-hires") or img_el.get("src")

        if product.main_image:
            product.main_image = product.main_image.strip()
            if product.main_image.startswith("//"):
                product.main_image = f"https:{product.main_image}"

        if bullets:
            product.pros = bullets[:3]

        # 10. Cache valid product data locally for 24 hours
        if product.title and not product.title.startswith("Amazon Product ("):
            cache_product(product, country=country)

    except Exception as e:
        logger.error(f"Error scraping ASIN {clean_asin}: {e}")

    return product
