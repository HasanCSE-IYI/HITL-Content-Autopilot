import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from core.models import AmazonProduct

class ProductScore(BaseModel):
    total_score: int
    grade: str  # Excellent (85-100), Good (70-84), Fair (50-69), Needs Attention (<50)
    relevance_score: int
    verified_data_score: int
    rating_signals_score: int
    price_viability_score: int
    content_fit_score: int
    breakdown: Dict[str, int] = Field(default_factory=dict)
    missing_data: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    verdict: str = ""

def score_product(product: AmazonProduct, keyword: str = "") -> ProductScore:
    """
    Evaluates an AmazonProduct using a transparent 0-100 point scoring system:
    - Relevance (max 30 pts): Keyword alignment, title completeness, category fit
    - Verified Data Available (max 25 pts): ASIN validity, images, specs/features, brand
    - Review & Rating Signals (max 20 pts): Verified rating, customer feedback volume
    - Price Viability (max 15 pts): Verified price presence, commercial transparency
    - Content Fit (max 10 pts): Editorial badge, pros/cons readiness

    Itemizes exact missing data and produces an honest audit.
    """
    missing_data: List[str] = []
    strengths: List[str] = []

    # 1. RELEVANCE (max 30 pts)
    relevance_score = 0
    clean_title = (product.title or "").strip().lower()
    clean_kw = keyword.strip().lower()

    if clean_kw and clean_kw in clean_title:
        relevance_score += 30
        strengths.append(f"Title exactly matches target keyword '{keyword}'")
    elif clean_kw:
        kw_tokens = set(re.findall(r"\w+", clean_kw))
        # Filter out trivial stop words
        kw_tokens = {t for t in kw_tokens if len(t) > 2 and t not in {"the", "best", "and", "for", "with"}}
        title_tokens = set(re.findall(r"\w+", clean_title))
        features_text = " ".join(product.features).lower()
        
        matched_tokens = kw_tokens.intersection(title_tokens)
        if kw_tokens:
            ratio = len(matched_tokens) / len(kw_tokens)
            relevance_pts = int(ratio * 25)
            # Check features for remaining tokens
            if ratio < 1.0 and any(t in features_text for t in kw_tokens - title_tokens):
                relevance_pts = min(28, relevance_pts + 4)
            relevance_score = max(10, relevance_pts)
            if ratio >= 0.75:
                strengths.append("High contextual relevance to seed keyword")
        else:
            relevance_score = 22
    else:
        # No keyword provided; judge based on title quality and length
        if len(clean_title) >= 40:
            relevance_score = 25
            strengths.append("Detailed, descriptive product title")
        elif len(clean_title) >= 15:
            relevance_score = 20
        else:
            relevance_score = 10
            missing_data.append("Product title is unusually brief or generic")

    # 2. VERIFIED DATA AVAILABLE (max 25 pts)
    verified_score = 0
    # ASIN validation
    if product.asin and re.match(r"^[A-Z0-9]{10}$", product.asin.upper()):
        verified_score += 5
    else:
        missing_data.append("Invalid or missing 10-character Amazon ASIN")

    # Image validation
    if product.main_image and product.main_image.startswith("http"):
        verified_score += 5
        strengths.append("Verified high-resolution product imagery available")
    else:
        missing_data.append("Missing verified product image URL")

    # Features / Specifications
    feature_count = len(product.features)
    if feature_count >= 4:
        verified_score += 10
        strengths.append(f"Rich specifications ({feature_count} technical features)")
    elif feature_count >= 2:
        verified_score += 6
        missing_data.append(f"Limited technical bullet points ({feature_count} provided; 4+ recommended)")
    elif feature_count == 1:
        verified_score += 3
        missing_data.append("Only 1 feature bullet provided")
    else:
        missing_data.append("No technical feature bullet points found")

    # Brand
    if product.brand and product.brand.strip():
        verified_score += 5
    else:
        missing_data.append("Manufacturer brand attribute is unverified")

    # 3. REVIEW & RATING SIGNALS (max 20 pts)
    rating_score = 0
    if product.rating is not None and product.rating > 0:
        if product.rating >= 4.5:
            rating_score += 12
            strengths.append(f"Outstanding customer rating ({product.rating:.1f}/5.0)")
        elif product.rating >= 4.0:
            rating_score += 10
            strengths.append(f"Solid customer rating ({product.rating:.1f}/5.0)")
        elif product.rating >= 3.5:
            rating_score += 6
        else:
            rating_score += 2
            missing_data.append(f"Sub-optimal customer rating ({product.rating:.1f}/5.0)")
    else:
        missing_data.append("Customer star rating unverified / missing")

    if product.review_count is not None and product.review_count > 0:
        if product.review_count >= 1000:
            rating_score += 8
            strengths.append(f"High social proof ({product.review_count:,} reviews)")
        elif product.review_count >= 100:
            rating_score += 6
            strengths.append(f"Established feedback ({product.review_count:,} reviews)")
        else:
            rating_score += 3
            missing_data.append(f"Low review volume ({product.review_count} reviews)")
    else:
        missing_data.append("Customer review count unverified / missing")

    # 4. PRICE VIABILITY (max 15 pts)
    price_score = 0
    price_str = (product.price or "").strip()
    if price_str and "$" in price_str and "Check Price" not in price_str:
        price_score = 15
        strengths.append(f"Verified live price point ({price_str})")
    elif price_str and "Check Price" in price_str:
        price_score = 8
        missing_data.append("Live numerical price unverified (using 'Check Price on Amazon' safe fallback)")
    else:
        price_score = 5
        missing_data.append("Price information missing")

    # 5. CONTENT FIT & EDITORIAL VALUE (max 10 pts)
    content_fit_score = 0
    if product.badge and product.badge.strip():
        content_fit_score += 4
        strengths.append(f"Editorial badge assigned: '{product.badge}'")
    else:
        missing_data.append("No editorial badge assigned (e.g. Best Overall, Best Value)")

    if len(product.pros) >= 2:
        content_fit_score += 3
    elif len(product.pros) == 1:
        content_fit_score += 1

    if len(product.cons) >= 1:
        content_fit_score += 3
    else:
        missing_data.append("No critical product drawbacks/cons identified")

    # TOTAL CALCULATION
    total = relevance_score + verified_score + rating_score + price_score + content_fit_score
    total = max(0, min(100, total))

    if total >= 85:
        grade = "Excellent"
    elif total >= 70:
        grade = "Good"
    elif total >= 50:
        grade = "Fair"
    else:
        grade = "Needs Attention"

    breakdown = {
        "Relevance": relevance_score,
        "Verified Data": verified_score,
        "Ratings & Reviews": rating_score,
        "Price Viability": price_score,
        "Content Fit": content_fit_score
    }

    # Generate transparent verdict
    if grade in ("Excellent", "Good"):
        verdict = f"High-confidence candidate ({total}/100, {grade}). Strong content fit for affiliate publication."
        if missing_data:
            verdict += f" Minor gaps: {'; '.join(missing_data[:2])}."
    else:
        verdict = f"Cautious candidate ({total}/100, {grade}). Requires manual verification of key specs or reviews."

    return ProductScore(
        total_score=total,
        grade=grade,
        relevance_score=relevance_score,
        verified_data_score=verified_score,
        rating_signals_score=rating_score,
        price_viability_score=price_score,
        content_fit_score=content_fit_score,
        breakdown=breakdown,
        missing_data=missing_data,
        strengths=strengths,
        verdict=verdict
    )
