import pytest
from core.models import ArticleDraft, QualityScorecard
from services.compliance.quality_checker import audit_article_quality

def test_audit_article_quality_full_score():
    draft = ArticleDraft(
        title="Best Keyboards 2026",
        slug="best-keyboards-2026",
        target_keyword="keyboards",
        meta_title="Best Keyboards",
        meta_description="Review of top keyboards",
        content_markdown=(
            "> **Affiliate Disclosure:** *We earn from Amazon Associates.* \n\n"
            + ("word " * 1550) + "\n\n"
            + "| Product | Price | Link |\n|---|---|---|\n| Item 1 | $50 | [Check](url) |\n\n"
            + "### Pros and Cons\n**Pros:** Good battery.\n**Cons:** Heavy.\n\n"
            + "## Frequently Asked Questions\nQ: Is it good? A: Yes.\n\n"
            + "*Disclaimer: Prices are accurate as of today and subject to change.*"
        ),
        content_html='<p><a href="https://amazon.com/dp/B08" rel="nofollow sponsored" target="_blank">Buy</a></p>',
        schema_json_ld='<script type="application/ld+json">{"@context": "https://schema.org"}</script>'
    )

    scorecard = audit_article_quality(draft)
    assert scorecard.has_ftc_disclosure is True
    assert scorecard.has_price_disclaimer is True
    assert scorecard.has_comparison_table is True
    assert scorecard.has_pros_cons is True
    assert scorecard.has_faq is True
    assert scorecard.has_schema_markup is True
    assert scorecard.compliant_link_ratio == 1.0
    assert scorecard.total_score >= 90
    assert len(scorecard.issues) == 0

def test_audit_article_quality_detects_missing_elements():
    # Draft missing FTC disclosure, price disclaimer, and table
    draft = ArticleDraft(
        title="Incomplete Article",
        slug="incomplete",
        target_keyword="shoes",
        meta_title="Shoes",
        meta_description="Shoes",
        content_markdown="Just a very short article with no tables or disclaimers.",
        content_html='<a href="https://amazon.com/dp/B09">Check price</a>',
        schema_json_ld=""
    )

    scorecard = audit_article_quality(draft)
    assert scorecard.has_ftc_disclosure is False
    assert scorecard.has_price_disclaimer is False
    assert scorecard.has_comparison_table is False
    assert scorecard.compliant_link_ratio < 1.0
    assert scorecard.total_score < 50
    assert len(scorecard.issues) >= 3

def test_audit_article_quality_spaced_table_detection():
    # Verify standard spaced markdown tables (| --- | --- |) are properly detected
    draft = ArticleDraft(
        title="Spaced Table Article",
        slug="spaced-table",
        target_keyword="table test",
        meta_title="Table Test",
        meta_description="Table Test",
        content_markdown=(
            "> **Affiliate Disclosure:** *We earn from Amazon Associates.*\n\n"
            "| Feature | Product A | Product B |\n"
            "| :--- | :--- | :--- |\n"
            "| Price | $100 | $150 |\n\n"
            "### Pros and Cons\n**Pros:** Good.\n**Cons:** Bad.\n\n"
            "## Frequently Asked Questions\nQ: FAQ?\n\n"
            "*Disclaimer: Prices are accurate as of today and subject to change.*"
        ),
        content_html='<p><a href="https://amazon.com/dp/B08" rel="nofollow sponsored" target="_blank">Buy</a></p>',
        schema_json_ld=""
    )
    scorecard = audit_article_quality(draft)
    assert scorecard.has_comparison_table is True
    assert "Missing quick comparison table." not in scorecard.issues
