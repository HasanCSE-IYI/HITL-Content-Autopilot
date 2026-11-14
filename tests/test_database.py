import pytest
from core.models import ArticleDraft, AmazonProduct, ArticleStatus, ArticleType
from core.database import save_draft, get_draft, list_drafts, delete_draft, update_draft_status

def test_database_crud():
    prod = AmazonProduct(
        asin="B08N5WRWNW",
        title="Test MacBook Air M1",
        price="$799.00",
        rating=4.8,
        review_count=12000,
        features=["M1 Chip", "8GB RAM", "256GB SSD"],
        affiliate_url="https://amazon.com/dp/B08N5WRWNW?tag=test-20"
    )

    draft = ArticleDraft(
        title="Best Laptops in 2026",
        slug="best-laptops-2026",
        article_type=ArticleType.ROUNDUP,
        target_keyword="best laptops",
        meta_title="Best Laptops in 2026 - Tested & Ranked",
        meta_description="Read our comprehensive review of the best laptops.",
        products=[prod],
        content_markdown="# Best Laptops\n\nContent here...",
        content_html="<h1>Best Laptops</h1><p>Content here...</p>",
        status=ArticleStatus.NEEDS_REVIEW
    )

    # 1. Save
    saved = save_draft(draft)
    assert saved.id == draft.id

    # 2. Get
    retrieved = get_draft(draft.id)
    assert retrieved is not None
    assert retrieved.title == "Best Laptops in 2026"
    assert len(retrieved.products) == 1
    assert retrieved.products[0].asin == "B08N5WRWNW"

    # 3. Update status
    update_draft_status(draft.id, ArticleStatus.APPROVED)
    updated = get_draft(draft.id)
    assert updated.status == ArticleStatus.APPROVED

    # 4. List
    all_drafts = list_drafts()
    assert any(d.id == draft.id for d in all_drafts)

    # 5. Delete
    deleted = delete_draft(draft.id)
    assert deleted is True
    assert get_draft(draft.id) is None
