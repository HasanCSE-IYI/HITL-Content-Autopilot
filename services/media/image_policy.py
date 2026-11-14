import re
from urllib.parse import urlparse
from typing import Dict, Any, List, Tuple
from core.models import AmazonProduct

# Whitelisted Amazon Product Image Media CDNs
AUTHORIZED_AMAZON_MEDIA_DOMAINS = {
    "m.media-amazon.com",
    "images-na.ssl-images-amazon.com",
    "ws-na.amazon-adsystem.com",
    "images-eu.ssl-images-amazon.com",
    "images-fe.ssl-images-amazon.com",
    "ecx.images-amazon.com",
    "z-na.amazon-adsystem.com",
    "ir-na.amazon-adsystem.com"
}

# Suspicious indicators of synthetic AI pretending to be real products
AI_SYNTHETIC_MARKERS = [
    "dall-e",
    "midjourney",
    "stability.ai",
    "stablediffusion",
    "generated_photos",
    "firefly.adobe",
    "synthetic_product",
    "ai_generated"
]

def validate_product_image_policy(image_url: str) -> Dict[str, Any]:
    """
    Enforces Amazon Associates & FTC Compliance on Product Imagery:
    - Product-specific factual imagery MUST use official Amazon media CDNs or verified licensed assets.
    - AI-generated synthetic images pretending to show the exact physical product are strictly forbidden.
    """
    if not image_url or not isinstance(image_url, str):
        return {
            "is_compliant": False,
            "source_type": "invalid_url",
            "is_synthetic_ai": False,
            "reason": "Image URL is empty or missing."
        }

    clean_url = image_url.strip()
    parsed = urlparse(clean_url)
    domain = (parsed.netloc or "").lower()

    # Check for disallowed AI synthetic signatures in URL path or parameters
    lower_url = clean_url.lower()
    for marker in AI_SYNTHETIC_MARKERS:
        if marker in lower_url:
            return {
                "is_compliant": False,
                "source_type": "disallowed_ai_synthetic",
                "is_synthetic_ai": True,
                "reason": f"Disallowed synthetic AI image detected ('{marker}'). Affiliate policies require authentic authorized product imagery."
            }

    # Check Amazon media CDN whitelist
    if any(domain == auth_domain or domain.endswith("." + auth_domain) for auth_domain in AUTHORIZED_AMAZON_MEDIA_DOMAINS):
        return {
            "is_compliant": True,
            "source_type": "amazon_authorized",
            "is_synthetic_ai": False,
            "reason": f"Authorized Amazon Media CDN asset ({domain})."
        }

    # Check if HTTPS standard web URL from an approved/custom publisher CDN
    if parsed.scheme in ("http", "https") and domain:
        return {
            "is_compliant": True,
            "source_type": "licensed_asset",
            "is_synthetic_ai": False,
            "reason": f"External licensed or publisher-hosted image ({domain}). Ensure commercial redistribution license is held."
        }

    return {
        "is_compliant": False,
        "source_type": "invalid_url",
        "is_synthetic_ai": False,
        "reason": f"Invalid or non-HTTP image URL structure: '{clean_url}'."
    }

def get_editorial_image_prompt(keyword: str, article_angle: str = "") -> str:
    """
    Generates a prompt for original editorial / conceptual illustrations.
    Explicitly instructs the image generator NOT to produce fake branded product mockups.
    """
    base_concept = f"Editorial concept illustration for an in-depth article about '{keyword}'"
    if article_angle:
        base_concept += f" with an angle focused on {article_angle}"

    return (
        f"{base_concept}. Modern vector lifestyle aesthetic, clean flat color palette, "
        f"subtle technical infographic accents, natural ambient lighting, workspace or lifestyle context. "
        f"STRICT COMPLIANCE REQUIREMENT: Conceptual artwork only; do not render recognizable physical trademarks, "
        f"fictional product boxes, or mock brand logos."
    )

def audit_article_images(content: str, products: List[AmazonProduct]) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Audits all images inside the markdown or HTML content.
    Returns:
      (sanitized_or_verified_content, audit_log)
    """
    audit_log: List[Dict[str, Any]] = []
    
    # 1. Regex find markdown images: ![alt](url)
    md_img_pattern = re.compile(r"!\[(.*?)\]\((.*?)\)")
    for match in md_img_pattern.finditer(content):
        alt, url = match.group(1), match.group(2)
        val = validate_product_image_policy(url)
        audit_log.append({
            "type": "markdown_image",
            "alt": alt,
            "url": url,
            "is_compliant": val["is_compliant"],
            "source_type": val["source_type"],
            "is_synthetic_ai": val["is_synthetic_ai"],
            "reason": val["reason"]
        })

    # 2. Regex find HTML <img> tags
    html_img_pattern = re.compile(r'<img\s+[^>]*src=[\'"]([^\'"]+)[\'"][^>]*>', re.IGNORECASE)
    for match in html_img_pattern.finditer(content):
        url = match.group(1)
        val = validate_product_image_policy(url)
        audit_log.append({
            "type": "html_image",
            "url": url,
            "is_compliant": val["is_compliant"],
            "source_type": val["source_type"],
            "is_synthetic_ai": val["is_synthetic_ai"],
            "reason": val["reason"]
        })

    return content, audit_log
