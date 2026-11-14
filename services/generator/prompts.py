import json
from typing import List
from datetime import datetime
from core.models import AmazonProduct

CURRENT_YEAR = datetime.now().year

def build_roundup_prompt(keyword: str, products: List[AmazonProduct], tone: str = "authoritative, engaging, and unbiased") -> str:
    products_context = []
    for idx, p in enumerate(products):
        products_context.append(
            f"Product {idx+1}:\n"
            f"- Title: {p.title}\n"
            f"- Brand: {p.brand or 'N/A'}\n"
            f"- Badge: {p.badge or f'Pick #{idx+1}'}\n"
            f"- Price: {p.price}\n"
            f"- Rating: {p.rating or 'N/A'} ({p.review_count or 0} reviews)\n"
            f"- Key Specs / Features: {', '.join(p.features[:5])}\n"
            f"- Affiliate URL: {p.affiliate_url}\n"
        )
    products_str = "\n".join(products_context)

    return f"""You are a professional affiliate marketing content strategist and expert product tester.
Write a comprehensive, engaging, SEO-optimized "Best of" roundup article targeting the primary keyword: "{keyword}".
Current Year: {CURRENT_YEAR}
Tone: {tone}

PRODUCTS TO REVIEW:
{products_str}

ARTICLE REQUIREMENTS & STRUCTURE:
1. SEO TITLE:
   - Provide a high CTR title (e.g., "{len(products)} Best {keyword.title()} in {CURRENT_YEAR}: Tested & Reviewed").
2. META DESCRIPTION:
   - Provide a compelling 150-160 character meta description.
3. INTRODUCTION:
   - Hook the reader immediately.
   - Discuss why finding the right {keyword} is challenging and what criteria we tested (durability, performance, value).
4. QUICK PICKS (AT A GLANCE):
   - A markdown table highlighting each product's Badge, Name, Key Benefit, and Amazon Link.
5. IN-DEPTH PRODUCT REVIEWS (One section for each product):
   - Header: `## [Number]. [Product Title] – [Badge]`
   - Image placeholder or mention if available.
   - Quick Specifications box.
   - Detailed analysis: Real-world performance, build quality, usability, unique selling point.
   - **Pros** (3-4 bullet points).
   - **Cons** (2 honest drawbacks).
   - Who should buy this?
   - Call To Action markdown button: `[Check Price on Amazon]({{affiliate_url}})` using the exact affiliate URL provided.
6. COMPREHENSIVE COMPARISON TABLE:
   - Markdown comparison table with columns: Product, Badge, Key Feature, Rating, Link.
7. BUYER'S GUIDE:
   - `## How to Choose the Best {keyword.title()} in {CURRENT_YEAR}`
   - 3-4 essential factors to consider before buying.
8. FREQUENTLY ASKED QUESTIONS (FAQ):
   - `## Frequently Asked Questions`
   - 4 common questions with clear, direct answers.
9. FINAL VERDICT:
   - Clear conclusion summarizing our top recommendation.

FORMATTING RULES:
- Output clean GitHub Flavored Markdown.
- Use the exact Affiliate URLs provided for each product.
- Do NOT fabricate fake live prices. Use "Check Price on Amazon" or the provided price string.
- Return output in the following JSON format:
{{
  "title": "Article Title",
  "meta_title": "SEO Meta Title",
  "meta_description": "Compelling Meta Description (155 chars)",
  "slug": "seo-friendly-slug",
  "markdown_content": "# Full article markdown here...",
  "faqs": [
    {{"question": "Q1...", "answer": "A1..."}},
    {{"question": "Q2...", "answer": "A2..."}}
  ]
}}
"""

def build_single_review_prompt(keyword: str, product: AmazonProduct, tone: str = "deeply analytical and honest") -> str:
    return f"""You are an expert product reviewer.
Write an in-depth, hands-on review article for "{product.title}".
Primary Target Keyword: "{keyword}"
Current Year: {CURRENT_YEAR}
Tone: {tone}

PRODUCT DATA:
- Title: {product.title}
- Brand: {product.brand or 'N/A'}
- Price: {product.price}
- Rating: {product.rating or 'N/A'}
- Specs: {', '.join(product.features)}
- Affiliate URL: {product.affiliate_url}

ARTICLE STRUCTURE:
1. SEO Title (e.g., "{product.title} Review ({CURRENT_YEAR}): Is It Worth It?")
2. Meta Description (150-160 characters)
3. Verdict Summary & Overall Score (out of 10)
4. Design & Build Quality
5. Performance & Key Features
6. Pros & Cons
7. Who Is It For & Who Should Skip It?
8. Alternatives to Consider
9. Final Recommendation with CTA: `[Check Price on Amazon]({product.affiliate_url})`

Return output in the following JSON format:
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
    return f"""You are a tech and consumer gear comparison specialist.
Write a head-to-head showdown article comparing "{product_a.title}" vs "{product_b.title}".
Primary Keyword: "{keyword}"
Current Year: {CURRENT_YEAR}

PRODUCT A:
- Title: {product_a.title}
- Price: {product_a.price}
- Specs: {', '.join(product_a.features[:5])}
- Affiliate URL: {product_a.affiliate_url}

PRODUCT B:
- Title: {product_b.title}
- Price: {product_b.price}
- Specs: {', '.join(product_b.features[:5])}
- Affiliate URL: {product_b.affiliate_url}

ARTICLE STRUCTURE:
1. SEO Title (e.g., "{product_a.title} vs {product_b.title}: Which Should You Buy in {CURRENT_YEAR}?")
2. Quick Verdict / TL;DR
3. Specs Comparison Table
4. Round 1: Design & Build Quality
5. Round 2: Performance & Everyday Experience
6. Round 3: Value for Money & Pricing
7. The Winner & Buying Advice

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
