import json
import re
from typing import List
from datetime import datetime
from core.models import AmazonProduct

CURRENT_YEAR = datetime.now().year

def clean_product_title(title: str, max_chars: int = 65) -> str:
    """
    Normalizes keyword-stuffed Amazon product titles into clean, concise brand & model names.
    Saves ~40-60% of product input tokens.
    """
    if not title:
        return "Featured Product"
    cleaned = title.strip()
    for delimiter in [" - ", " | ", ", with ", " (Newest", " [202", " (202", ", Compatible", ", Upgraded"]:
        if delimiter in cleaned and len(cleaned.split(delimiter)[0]) >= 15:
            cleaned = cleaned.split(delimiter)[0]
    cleaned = re.sub(r"\[.*?\]", "", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > max_chars:
        truncated = cleaned[:max_chars].rsplit(" ", 1)[0]
        cleaned = truncated if len(truncated) > 20 else cleaned[:max_chars]
    return cleaned.strip()

def inject_affiliate_links_from_placeholders(markdown_content: str, products: List[AmazonProduct]) -> str:
    """
    Replaces [AFF_LINK_1], [AFF_LINK_2], etc. with authentic product affiliate URLs.
    Guarantees affiliate tag integrity and eliminates output token burn.
    """
    res = markdown_content
    for idx, p in enumerate(products):
        placeholder = f"[AFF_LINK_{idx+1}]"
        res = res.replace(placeholder, p.affiliate_url)
    return res

def build_roundup_prompt(keyword: str, products: List[AmazonProduct], tone: str = "authoritative, engaging, and unbiased") -> str:
    products_context = []
    for idx, p in enumerate(products):
        clean_title = clean_product_title(p.title)
        products_context.append(
            f"Product {idx+1}:\n"
            f"- Title: {clean_title}\n"
            f"- Brand: {p.brand or 'N/A'}\n"
            f"- Badge: {p.badge or f'Pick #{idx+1}'}\n"
            f"- Price: {p.price}\n"
            f"- Rating: {p.rating or 'N/A'} ({p.review_count or 0} reviews)\n"
            f"- Key Specs: {', '.join(p.features[:4])}\n"
            f"- Action Link: [AFF_LINK_{idx+1}]\n"
        )
    products_str = "\n".join(products_context)

    return f"""You are a professional affiliate marketing content strategist.
Write a comprehensive, engaging, SEO-optimized "Best of" roundup article for: "{keyword}".
Current Year: {CURRENT_YEAR}
Tone: {tone}

PRODUCTS:
{products_str}

REQUIREMENTS:
1. SEO TITLE: High CTR title (e.g. "{len(products)} Best {keyword.title()} in {CURRENT_YEAR}: Tested & Reviewed").
2. META DESCRIPTION: Compelling 150-160 char meta description.
3. INTRODUCTION: Hook reader, criteria tested (durability, performance, value).
4. QUICK PICKS TABLE: Markdown table with Product, Badge, Key Benefit, and Amazon Link using `[Check Price]([AFF_LINK_X])`.
5. PRODUCT REVIEWS (One section for each product):
   - Header: `## [Number]. [Product Title] – [Badge]`
   - Quick specs, real-world performance, usability.
   - **Pros** (3 bullets), **Cons** (2 honest drawbacks).
   - Who should buy this?
   - CTA button: `[Check Price on Amazon]([AFF_LINK_X])` using the exact action link placeholder for that product.
6. COMPARISON TABLE: Markdown table (Product, Badge, Key Feature, Rating, Link).
7. BUYER'S GUIDE: `## How to Choose the Best {keyword.title()} in {CURRENT_YEAR}` (3 essential factors).
8. FINAL VERDICT: Summary and top recommendation.

TOKEN OPTIMIZATION RULE:
- Do NOT write the FAQ section inside markdown_content.
- Provide 4 common questions with clear answers ONLY in the "faqs" JSON field (it will be injected into the article automatically).

Return output in the following JSON format:
{{
  "title": "Article Title",
  "meta_title": "SEO Meta Title",
  "meta_description": "Meta description (155 chars)",
  "slug": "seo-friendly-slug",
  "markdown_content": "# Full article markdown here...",
  "faqs": [
    {{"question": "Q1...", "answer": "A1..."}},
    {{"question": "Q2...", "answer": "A2..."}}
  ]
}}
"""

def build_single_review_prompt(keyword: str, product: AmazonProduct, tone: str = "deeply analytical and honest") -> str:
    clean_title = clean_product_title(product.title)
    return f"""You are an expert product reviewer.
Write an in-depth review for "{clean_title}".
Primary Keyword: "{keyword}"
Current Year: {CURRENT_YEAR}
Tone: {tone}

PRODUCT DATA:
- Title: {clean_title}
- Brand: {product.brand or 'N/A'}
- Price: {product.price}
- Rating: {product.rating or 'N/A'}
- Specs: {', '.join(product.features[:5])}
- Action Link: [AFF_LINK_1]

ARTICLE STRUCTURE:
1. SEO Title (e.g., "{clean_title} Review ({CURRENT_YEAR}): Is It Worth It?")
2. Meta Description (150-160 chars)
3. Verdict Summary & Overall Score (out of 10)
4. Design & Build Quality
5. Performance & Key Features
6. Pros & Cons
7. Who Is It For & Who Should Skip It?
8. Alternatives to Consider
9. Final Recommendation with CTA: `[Check Price on Amazon]([AFF_LINK_1])`

TOKEN OPTIMIZATION RULE:
- Do NOT write the FAQ section inside markdown_content.
- Provide 3-4 FAQs ONLY in the "faqs" JSON field.

Return output in JSON format:
{{
  "title": "Article Title",
  "meta_title": "SEO Meta Title",
  "meta_description": "Meta description",
  "slug": "seo-friendly-slug",
  "markdown_content": "# Full article markdown...",
  "faqs": [
    {{"question": "...", "answer": "..."}}
  ]
}}
"""

def build_comparison_prompt(product_a: AmazonProduct, product_b: AmazonProduct, keyword: str) -> str:
    clean_a = clean_product_title(product_a.title)
    clean_b = clean_product_title(product_b.title)
    return f"""You are a consumer gear comparison specialist.
Write a head-to-head comparison article: "{clean_a}" vs "{clean_b}".
Primary Keyword: "{keyword}"
Current Year: {CURRENT_YEAR}

PRODUCT A:
- Title: {clean_a}
- Price: {product_a.price}
- Specs: {', '.join(product_a.features[:4])}
- Action Link: [AFF_LINK_1]

PRODUCT B:
- Title: {clean_b}
- Price: {product_b.price}
- Specs: {', '.join(product_b.features[:4])}
- Action Link: [AFF_LINK_2]

ARTICLE STRUCTURE:
1. SEO Title (e.g., "{clean_a} vs {clean_b}: Which Should You Buy in {CURRENT_YEAR}?")
2. Quick Verdict / TL;DR
3. Specs Comparison Table
4. Round 1: Design & Build Quality
5. Round 2: Performance & Everyday Experience
6. Round 3: Value for Money & Pricing
7. The Winner & Buying Advice with CTAs using `[AFF_LINK_1]` and `[AFF_LINK_2]`

TOKEN OPTIMIZATION RULE:
- Do NOT write the FAQ section inside markdown_content.
- Provide 3-4 FAQs ONLY in the "faqs" JSON field.

Return output in JSON format:
{{
  "title": "Article Title",
  "meta_title": "SEO Meta Title",
  "meta_description": "Meta description",
  "slug": "seo-friendly-slug",
  "markdown_content": "# Full comparison markdown...",
  "faqs": [
    {{"question": "...", "answer": "..."}}
  ]
}}
"""

def build_section_regenerate_prompt(original_section: str, instruction: str) -> str:
    return f"""You are an elite copywriter.
Please rewrite the following article section according to the user's specific instruction.

ORIGINAL SECTION:
{original_section}

INSTRUCTION:
{instruction}

Provide ONLY the revised markdown text. Do not wrap in conversational chatter.
"""
