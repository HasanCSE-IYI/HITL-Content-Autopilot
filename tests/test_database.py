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

def test_settings_and_presets_persistence():
    from core.database import (
        set_setting,
        get_setting,
        save_asin_preset,
        get_asin_presets,
        delete_asin_preset
    )
    # Setting test
    set_setting("TEST_KEY", "TEST_VAL_123")
    assert get_setting("TEST_KEY") == "TEST_VAL_123"
    assert get_setting("NON_EXISTENT", "default") == "default"

    # Presets test
    save_asin_preset("Headphones", "B01\nB02", "best headphones")
    presets = get_asin_presets()
    assert len(presets) >= 1
    target = next((p for p in presets if p["name"] == "Headphones"), None)
    assert target is not None
    assert "B01" in target["asins"]
    assert target["keyword"] == "best headphones"
    
    # Delete preset
    delete_asin_preset(target["id"])

def test_get_draft_status_counts():
    from core.database import get_draft_status_counts, save_draft, delete_draft
    
    # Initial counts
    counts_before = get_draft_status_counts()
    assert isinstance(counts_before, dict)
    assert "total" in counts_before
    assert "needs_review" in counts_before

    # Insert test draft
    draft = ArticleDraft(
        title="Status Count Test",
        slug="status-count-test",
        article_type=ArticleType.ROUNDUP,
        target_keyword="status test",
        meta_title="Status Count Test Meta",
        meta_description="Status Count Test Description",
        products=[],
        status=ArticleStatus.NEEDS_REVIEW
    )
    save_draft(draft)

    counts_after = get_draft_status_counts()
    assert counts_after["total"] == counts_before["total"] + 1
    assert counts_after["needs_review"] == counts_before["needs_review"] + 1

    # Cleanup
    delete_draft(draft.id)
    counts_cleaned = get_draft_status_counts()
    assert counts_cleaned["total"] == counts_before["total"]

def test_ensure_column_validation():
    from core.database import _ensure_column, get_connection
    conn = get_connection()
    with pytest.raises(ValueError, match="Invalid table name identifier"):
        _ensure_column(conn, "drafts; DROP TABLE drafts;--", "col TEXT")
    with pytest.raises(ValueError, match="Invalid column name identifier"):
        _ensure_column(conn, "drafts", "bad-col-name;-- TEXT")

