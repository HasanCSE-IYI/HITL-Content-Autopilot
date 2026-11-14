import re
import markdown
from typing import List, Optional
from core.models import AmazonProduct, ArticleDraft, ArticleType, ArticleStatus
from services.generator.gemini_client import GeminiClient
from services.generator.prompts import build_roundup_prompt
from services.generator.schema import (
    generate_item_list_schema,
    generate_faq_schema,
    combine_schemas_to_html
)
from services.compliance.rules import inject_compliance_markdown, enforce_nofollow_sponsored
from services.compliance.quality_checker import audit_article_quality

def generate_roundup_article(
    keyword: str,
    products: List[AmazonProduct],
    client: Optional[GeminiClient] = None,
    tone: str = "authoritative, engaging, and unbiased"
) -> ArticleDraft:
    """
    Generates a full 'Top X Best' roundup article draft with schema markup and compliance checks.
    """
    gemini = client or GeminiClient()
    prompt = build_roundup_prompt(keyword=keyword, products=products, tone=tone)

    data = gemini.generate_json(prompt)

    title = data.get("title", f"Best {keyword.title()} in 2026")
    meta_title = data.get("meta_title", title)
    meta_desc = data.get("meta_description", f"Discover the top tested {keyword} for 2026. Complete reviews, pros & cons, and buying guide.")
    slug = data.get("slug") or re.sub(r"[^\w\s-]", "", title.lower()).strip().replace(" ", "-")[:60]
    
    raw_markdown = data.get("markdown_content", "")
    compliant_markdown = inject_compliance_markdown(raw_markdown)

    # Convert to HTML
    html_body = markdown.markdown(
        compliant_markdown,
        extensions=["tables", "fenced_code", "nl2br"]
    )
    compliant_html = enforce_nofollow_sponsored(html_body)

    # Generate Schemas
    schemas = []
    schemas.append(generate_item_list_schema(products, title))
    faqs = data.get("faqs", [])
    if faqs:
        schemas.append(generate_faq_schema(faqs))
    schema_html = combine_schemas_to_html(schemas)

    draft = ArticleDraft(
        title=title,
        slug=slug,
        article_type=ArticleType.ROUNDUP,
        target_keyword=keyword,
        meta_title=meta_title,
        meta_description=meta_desc,
        products=products,
        content_markdown=compliant_markdown,
        content_html=compliant_html,
        schema_json_ld=schema_html,
        status=ArticleStatus.NEEDS_REVIEW
    )
    return draft
