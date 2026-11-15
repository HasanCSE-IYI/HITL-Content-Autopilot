import re
import markdown
from typing import Optional, Any
from core.models import AmazonProduct, ArticleDraft, ArticleType, ArticleStatus
from core.config import settings
from services.generator.factory import get_llm_client
from services.generator.prompts import build_single_review_prompt, inject_affiliate_links_from_placeholders
from services.generator.schema import (
    generate_product_schema,
    generate_faq_schema,
    combine_schemas_to_html
)
from services.compliance.rules import inject_compliance_markdown, enforce_nofollow_sponsored
from services.compliance.quality_checker import audit_article_quality

def generate_single_review_article(
    keyword: str,
    product: AmazonProduct,
    client: Optional[Any] = None,
    tone: str = "deeply analytical and honest"
) -> ArticleDraft:
    """
    Generates an in-depth single product review article with token optimization.
    """
    llm = client or get_llm_client()
    prompt = build_single_review_prompt(keyword=keyword, product=product, tone=tone)

    data = llm.generate_json(
        prompt,
        max_tokens=getattr(settings, "MAX_TOKENS_REVIEW", 2500),
        task_type="review"
    )

    title = data.get("title", f"{product.title} Review: Tested in 2026")
    meta_title = data.get("meta_title", title)
    meta_desc = data.get("meta_description", f"Our comprehensive hands-on review of {product.title}. Discover performance, specs, pros & cons.")
    slug = data.get("slug") or re.sub(r"[^\w\s-]", "", title.lower()).strip().replace(" ", "-")[:60]

    raw_markdown = data.get("markdown_content", "")
    raw_markdown = inject_affiliate_links_from_placeholders(raw_markdown, [product])

    # Single-source FAQ injection
    faqs = data.get("faqs", [])
    if faqs and "## Frequently Asked Questions" not in raw_markdown and "## FAQ" not in raw_markdown:
        faq_lines = ["\n\n## Frequently Asked Questions\n"]
        for f in faqs:
            q = f.get("question") or f.get("q")
            a = f.get("answer") or f.get("a")
            if q and a:
                faq_lines.append(f"### {q}\n{a}\n")
        raw_markdown += "\n".join(faq_lines)

    compliant_markdown = inject_compliance_markdown(raw_markdown)

    html_body = markdown.markdown(
        compliant_markdown,
        extensions=["tables", "fenced_code", "nl2br"]
    )
    compliant_html = enforce_nofollow_sponsored(html_body)

    schemas = [generate_product_schema(product)]
    if faqs:
        schemas.append(generate_faq_schema(faqs))
    schema_html = combine_schemas_to_html(schemas)

    draft = ArticleDraft(
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
    draft.quality_scorecard = audit_article_quality(draft)
    return draft
