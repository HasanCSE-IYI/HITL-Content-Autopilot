import re
from typing import List, Dict, Any, Tuple
from core.models import ArticleDraft, QualityScorecard

def audit_article_quality(draft: ArticleDraft) -> QualityScorecard:
    """
    Audits an article draft for FTC compliance, Amazon Associates policies,
    SEO readability, and structured content elements.
    Returns a QualityScorecard with total score (0-100) and actionable issues.
    """
    content = draft.content_markdown or ""
    html = draft.content_html or ""
    issues: List[str] = []
    score = 0

    # 1. Word Count Check (Max 15 pts)
    words = len(content.split())
    if words >= 1500:
        score += 15
    elif words >= 1000:
        score += 10
        issues.append(f"Word count is {words} words (recommended: 1,500+ for affiliate roundups).")
    elif words >= 500:
        score += 5
        issues.append(f"Word count is low ({words} words). Consider adding more product details.")
    else:
        issues.append(f"Article is too short ({words} words).")

    # 2. FTC Affiliate Disclosure Check (20 pts)
    has_ftc = "affiliate disclosure" in content.lower() or "amazon associate" in content.lower()
    if has_ftc:
        score += 20
    else:
        issues.append("Missing mandatory FTC Affiliate Disclosure at the top.")

    # 3. Amazon Price Policy & Disclaimer (15 pts)
    has_price_disclaimer = "accurate as of" in content.lower() or "subject to change" in content.lower()
    if has_price_disclaimer:
        score += 15
    else:
        issues.append("Missing dynamic Amazon price accuracy disclaimer.")

    # 4. Content Structure Elements:
    # A. Comparison Table (15 pts)
    has_table = "|" in content and "-|-" in content
    if has_table:
        score += 15
    else:
        issues.append("Missing quick comparison table.")

    # B. Pros & Cons (10 pts)
    has_pros_cons = "**pros" in content.lower() or "**cons" in content.lower() or "### pros" in content.lower()
    if has_pros_cons:
        score += 10
    else:
        issues.append("Missing structured Pros & Cons sections.")

    # C. FAQ Section (10 pts)
    has_faq = "frequently asked questions" in content.lower() or "## faq" in content.lower()
    if has_faq:
        score += 10
    else:
        issues.append("Missing FAQ section for Google rich snippets.")

    # 5. Schema Markup Check (5 pts)
    has_schema = bool(draft.schema_json_ld and "application/ld+json" in draft.schema_json_ld)
    if has_schema:
        score += 5
    else:
        issues.append("Missing JSON-LD structured schema markup.")

    # 6. Affiliate Link Audit (10 pts)
    # Check all amazon links in HTML for nofollow sponsored
    amazon_links = re.findall(r'<a\s+[^>]*href=["\']([^"\']*amazon\.[^"\']*)["\'][^>]*>', html, re.IGNORECASE)
    compliant_links = 0
    total_amz_links = len(amazon_links)

    if total_amz_links > 0:
        for link_match in re.finditer(r'<a\s+([^>]*href=["\'][^"\']*amazon\.[^"\']*["\'][^>]*)>', html, re.IGNORECASE):
            attrs = link_match.group(1).lower()
            is_compliant = ("rel=" in attrs and "nofollow" in attrs and "sponsored" in attrs) or ("rel=" in attrs and "sponsored" in attrs)
            if is_compliant:
                compliant_links += 1

        link_ratio = compliant_links / total_amz_links
        score += int(link_ratio * 10)
        if link_ratio < 1.0:
            issues.append(f"{total_amz_links - compliant_links} Amazon link(s) missing 'rel=nofollow sponsored'.")
    else:
        link_ratio = 1.0
        score += 10

    total_score = min(max(score, 0), 100)

    return QualityScorecard(
        total_score=total_score,
        word_count=words,
        has_ftc_disclosure=has_ftc,
        has_price_disclaimer=has_price_disclaimer,
        has_schema_markup=has_schema,
        has_comparison_table=has_table,
        has_pros_cons=has_pros_cons,
        has_faq=has_faq,
        compliant_link_ratio=round(link_ratio, 2),
        issues=issues
    )
