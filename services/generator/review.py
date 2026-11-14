import re
import markdown
from typing import Optional
from core.models import AmazonProduct, ArticleDraft, ArticleType, ArticleStatus
from services.generator.gemini_client import GeminiClient
from services.generator.prompts import build_single_review_prompt
from services.generator.schema import (
    generate_product_schema,
    generate_faq_schema,
    combine_schemas_to_html
)
from services.compliance.rules import inject_compliance_markdown, enforce_nofollow_sponsored

def generate_single_review_article(
    keyword: str,
    product: AmazonProduct,
    client: Optional[GeminiClient] = None,
    tone: str = "deeply analytical and honest"
) -> ArticleDraft:
    """
    Generates an in-depth single product review article.
    """
    gemini = client or GeminiClient()
    prompt = build_single_review_prompt(keyword=keyword, product=product, tone=tone)

    data = gemini.generate_json(prompt)

    title = data.get("title", f"{product.title} Review: Tested in 2026")
    meta_title = data.get("meta_title", title)
    meta_desc = data.get("meta_description", f"Our comprehensive hands-on review of {product.title}. Discover performance, specs, pros & cons.")
    slug = data.get("slug") or re.sub(r"[^\w\s-]", "", title.lower()).strip().replace(" ", "-")[:60]

    raw_markdown = data.get("markdown_content", "")
    compliant_markdown = inject_compliance_markdown(raw_markdown)

    html_body = markdown.markdown(
        compliant_markdown,
        extensions=["tables", "fenced_code", "nl2br"]
    )
    compliant_html = enforce_nofollow_sponsored(html_body)

    schemas = [generate_product_schema(product)]
    faqs = data.get("faqs", [])
    if faqs:
        schemas.append(generate_faq_schema(faqs))
    schema_html = combine_schemas_to_html(schemas)

    return ArticleDraft(
        title=title,
        slug=slug,
        article_type=ArticleType.SINGLE_REVIEW,
        target_keyword=keyword,
        meta_title=meta_title,
        meta_description=meta_desc,
        products=[product],
        content_markdown=compliant_markdown,
        content_html=compliant_html,
        schema_json_ld=schema_html,
        status=ArticleStatus.NEEDS_REVIEW
    )
