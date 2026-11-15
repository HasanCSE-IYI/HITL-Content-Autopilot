import re
import markdown
from typing import Optional, Any
from core.models import AmazonProduct, ArticleDraft, ArticleType, ArticleStatus
from core.config import settings
from services.generator.factory import get_llm_client
from services.generator.prompts import build_comparison_prompt, inject_affiliate_links_from_placeholders
from services.generator.schema import (
    generate_product_schema,
    generate_faq_schema,
    combine_schemas_to_html
)
from services.compliance.rules import inject_compliance_markdown, enforce_nofollow_sponsored
from services.compliance.quality_checker import audit_article_quality

def generate_comparison_article(
    keyword: str,
    product_a: AmazonProduct,
    product_b: AmazonProduct,
    client: Optional[Any] = None
) -> ArticleDraft:
    """
    Generates a head-to-head comparison article (Product A vs Product B) with token optimization.
    """
    llm = client or get_llm_client()
    prompt = build_comparison_prompt(product_a, product_b, keyword)

    data = llm.generate_json(
        prompt,
        max_tokens=getattr(settings, "MAX_TOKENS_COMPARISON", 3000),
        task_type="comparison"
    )

    title = data.get("title", f"{product_a.title} vs {product_b.title}: Complete Comparison")
    meta_title = data.get("meta_title", title)
    meta_desc = data.get("meta_description", f"Comparing {product_a.title} vs {product_b.title}. Which one is worth your money in 2026?")
    slug = data.get("slug") or re.sub(r"[^\w\s-]", "", title.lower()).strip().replace(" ", "-")[:60]

    raw_markdown = data.get("markdown_content", "")
    raw_markdown = inject_affiliate_links_from_placeholders(raw_markdown, [product_a, product_b])

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

    schemas = [generate_product_schema(product_a), generate_product_schema(product_b)]
    if faqs:
        schemas.append(generate_faq_schema(faqs))
    schema_html = combine_schemas_to_html(schemas)

    draft = ArticleDraft(
        title=title,
        slug=slug,
        article_type=ArticleType.COMPARISON,
        target_keyword=keyword,
        meta_title=meta_title,
        meta_description=meta_desc,
        products=[product_a, product_b],
        content_markdown=compliant_markdown,
        content_html=compliant_html,
        schema_json_ld=schema_html,
        status=ArticleStatus.NEEDS_REVIEW
    )
    draft.quality_scorecard = audit_article_quality(draft)
    return draft
