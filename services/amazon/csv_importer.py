import csv
import io
import logging
from typing import List, Dict, Any, Tuple, Optional
from core.models import AmazonProduct
from services.amazon.parser import extract_asin, build_affiliate_url

logger = logging.getLogger(__name__)

PRODUCT_CSV_HEADERS = ["asin", "title", "price", "specs", "pros", "cons", "url"]
KEYWORD_CSV_HEADERS = ["keyword", "asins", "article_type"]

SAMPLE_PRODUCT_CSV = """asin,title,price,specs,pros,cons,url
B0CX23V2ZT,Keychron K2 Pro Wireless Mechanical Keyboard,$89.99,"75% Layout, Hot-Swappable, Bluetooth 5.1 & Wired, RGB","Tactile feel, Solid build, Multi-device","Requires wrist rest for comfort",https://www.amazon.com/dp/B0CX23V2ZT
B09V3HN1KC,Logitech MX Mechanical Mini,$149.99,"Low-Profile Switches, Smart Illumination, USB-C","Ultra-sleek, Long battery life, Quiet switches","Premium price tag",https://www.amazon.com/dp/B09V3HN1KC
B0BSHF7WHW,NuPhy Air75 V2 Ultra-Slim Keyboard,$119.95,"Ultra-slim 75%, 2.4GHz + BT 5.0, PBT Keycaps","Super portable, Mac and Windows keys included","Gateron low profile switches only",https://www.amazon.com/dp/B0BSHF7WHW
"""

SAMPLE_KEYWORD_CSV = """keyword,asins,article_type
Best Wireless Mechanical Keyboards,B0CX23V2ZT; B09V3HN1KC; B0BSHF7WHW,roundup
Logitech MX Mechanical Mini In-Depth Review,B09V3HN1KC,single_review
Keychron K2 Pro vs Logitech MX Mechanical Mini,B0CX23V2ZT; B09V3HN1KC,comparison
Quiet Air Purifiers for Bedroom 2026,,roundup
Ergonomic Office Chair Under 300,,roundup
"""

def generate_product_facts_csv_template() -> str:
    """
    Generates a standardized CSV template string for manual product facts import.
    """
    return SAMPLE_PRODUCT_CSV.strip()

def generate_bulk_keywords_csv_template() -> str:
    """
    Generates a standardized CSV template string for bulk keywords import.
    """
    return SAMPLE_KEYWORD_CSV.strip()

def parse_product_facts_csv(
    csv_text: str,
    affiliate_tag: str = "tag-20",
    country: str = "com"
) -> List[AmazonProduct]:
    """
    Parses a CSV string of product records into AmazonProduct instances.
    Supports columns: asin, title, price, specs, pros, cons, url.
    """
    if not csv_text or not csv_text.strip():
        return []

    # Strip UTF-8 BOM if present (common when exported from Windows Excel)
    clean_csv = csv_text.lstrip("\ufeff").strip()
    f = io.StringIO(clean_csv)
    reader = csv.DictReader(f)
    
    # Normalize headers to lowercase
    if reader.fieldnames:
        reader.fieldnames = [fn.strip().lower() for fn in reader.fieldnames]

    products: List[AmazonProduct] = []

    for idx, row in enumerate(reader, 1):
        # Extract title
        title = (row.get("title") or row.get("product") or row.get("name") or f"Imported Product #{idx}").strip()
        price = (row.get("price") or "Check Price on Amazon").strip()
        raw_url = (row.get("url") or row.get("link") or "").strip()
        raw_asin = (row.get("asin") or "").strip().upper()

        # Resolve ASIN
        resolved_asin = raw_asin if len(raw_asin) == 10 else (extract_asin(raw_url) or f"CSV{idx:03d}")

        # Resolve affiliate link
        if resolved_asin and len(resolved_asin) == 10:
            affiliate_url = build_affiliate_url(resolved_asin, affiliate_tag, country)
        elif raw_url:
            affiliate_url = raw_url
        else:
            affiliate_url = build_affiliate_url(resolved_asin, affiliate_tag, country)

        # Parse comma or semicolon separated lists
        def split_list(val: Optional[str]) -> List[str]:
            if not val:
                return []
            parts = [p.strip() for p in val.replace(";", ",").replace("|", ",").split(",") if p.strip()]
            return parts

        specs = split_list(row.get("specs") or row.get("features"))
        pros = split_list(row.get("pros") or row.get("advantages"))
        cons = split_list(row.get("cons") or row.get("drawbacks"))

        if not specs:
            specs = [f"Verified product: {title}"]
        if not pros:
            pros = specs[:3] if len(specs) >= 1 else ["Quality engineering"]
        if not cons:
            cons = ["Check current stock availability"]

        product = AmazonProduct(
            asin=resolved_asin,
            title=title,
            price=price,
            features=specs[:8],
            pros=pros[:5],
            cons=cons[:5],
            affiliate_url=affiliate_url,
            badge=f"Top Pick #{idx}" if idx == 1 else "Recommended",
            provenance=f"CSV Import (Product #{idx})"
        )
        products.append(product)

    return products

def parse_bulk_keywords_csv(csv_text: str) -> Tuple[List[Dict[str, str]], List[str]]:
    """
    Parses a CSV string of bulk keywords.
    Returns:
    - valid_tasks: List of dicts with keys 'keyword', 'asins', 'article_type'
    - duplicates: List of duplicate keyword strings flagged during parse
    """
    if not csv_text or not csv_text.strip():
        return [], []

    # Strip UTF-8 BOM if present (common when exported from Windows Excel)
    clean_csv = csv_text.lstrip("\ufeff").strip()
    f = io.StringIO(clean_csv)
    reader = csv.DictReader(f)

    if reader.fieldnames:
        reader.fieldnames = [fn.strip().lower() for fn in reader.fieldnames]

    tasks: List[Dict[str, str]] = []
    seen_keywords = set()
    duplicates: List[str] = []

    for row in reader:
        kw = (row.get("keyword") or row.get("key") or row.get("query") or "").strip()
        if not kw:
            continue

        kw_normalized = kw.lower()
        if kw_normalized in seen_keywords:
            duplicates.append(kw)
            continue

        seen_keywords.add(kw_normalized)
        asins = (row.get("asins") or row.get("asin") or row.get("products") or "").strip()
        art_type = (row.get("article_type") or row.get("type") or "roundup").strip().lower()

        if art_type not in ["roundup", "single_review", "comparison"]:
            art_type = "roundup"

        tasks.append({
            "keyword": kw,
            "asins": asins,
            "article_type": art_type
        })

    return tasks, duplicates
