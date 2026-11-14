import re
from datetime import datetime
from services.amazon.parser import build_affiliate_url

FTC_DISCLOSURE_MARKDOWN = (
    "> **Affiliate Disclosure:** *We independently research, test, and recommend the best products. "
    "If you buy something through our links, we may earn an affiliate commission at no extra cost to you. "
    "As an Amazon Associate, we earn from qualifying purchases.*\n\n---\n"
)

FTC_DISCLOSURE_HTML = (
    '<div class="affiliate-disclosure-box" style="background:#f8f9fa; border-left:4px solid #ff9900; padding:12px 16px; margin-bottom:24px; font-size:14px; color:#555;">'
    '<strong>Affiliate Disclosure:</strong> <em>We independently research, test, and recommend the best products. '
    'If you buy something through our links, we may earn an affiliate commission at no extra cost to you. '
    'As an Amazon Associate, we earn from qualifying purchases.</em>'
    '</div>'
)

def get_price_disclaimer() -> str:
    now_str = datetime.now().strftime("%B %d, %Y")
    return (
        f"\n\n---\n*Disclaimer: Product prices and availability are accurate as of {now_str} "
        f"and are subject to change. Any price and availability information displayed on Amazon at the "
        f"time of purchase will apply to the purchase of this product.*"
    )

def inject_compliance_markdown(content: str) -> str:
    """
    Ensures FTC disclosure is at the top and Amazon price disclaimer at the bottom.
    """
    clean_content = content
    if "Affiliate Disclosure" not in clean_content:
        clean_content = FTC_DISCLOSURE_MARKDOWN + clean_content

    if "Product prices and availability are accurate" not in clean_content:
        clean_content = clean_content + get_price_disclaimer()

    return clean_content

def enforce_nofollow_sponsored(html: str) -> str:
    """
    Ensures all amazon links have rel='nofollow sponsored' and target='_blank'.
    """
    def _replace_link(match):
        full_tag = match.group(0)
        href = match.group(1)
        if "amazon." in href:
            # Check rel
            if 'rel=' not in full_tag:
                full_tag = full_tag.replace('>', ' rel="nofollow sponsored">', 1)
            elif 'nofollow' not in full_tag:
                full_tag = re.sub(r'rel=["\'][^"\']*["\']', 'rel="nofollow sponsored"', full_tag)
            
            # Check target
            if 'target=' not in full_tag:
                full_tag = full_tag.replace('>', ' target="_blank">', 1)
        return full_tag

    # Match <a> tags
    pattern = re.compile(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
    return pattern.sub(_replace_link, html)
