import re
from typing import Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

ASIN_REGEX = re.compile(r"(?:/dp/|/gp/product/|/exec/obidos/ASIN/|/o/ASIN/|/gp/aw/d/)([A-Z0-9]{10})", re.IGNORECASE)
BARE_ASIN_REGEX = re.compile(r"^[A-Z0-9]{10}$", re.IGNORECASE)

def extract_asin(input_str: str) -> Optional[str]:
    """
    Extracts 10-character Amazon ASIN from a URL or raw ASIN string.
    """
    if not input_str:
        return None
    cleaned = input_str.strip()
    # Check if raw ASIN
    if BARE_ASIN_REGEX.match(cleaned):
        return cleaned.upper()
    # Match in URL
    match = ASIN_REGEX.search(cleaned)
    if match:
        return match.group(1).upper()
    return None

def build_affiliate_url(asin: str, tag: str, country: str = "com") -> str:
    """
    Builds a compliant, clean affiliate link for an ASIN with the specified tracking tag.
    """
    clean_asin = asin.strip().upper()
    clean_tag = tag.strip()
    return f"https://www.amazon.{country}/dp/{clean_asin}?tag={clean_tag}"
