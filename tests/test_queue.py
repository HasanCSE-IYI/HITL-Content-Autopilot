import pytest
import uuid
from unittest.mock import patch, MagicMock
from core.models import BulkTask, BulkTaskStatus, ArticleDraft, AmazonProduct
from core.database import (
    create_bulk_task,
    get_bulk_task,
    update_bulk_task,
    list_bulk_tasks,
    get_batch_summary
)
from services.queue.bulk_manager import process_single_task

def test_bulk_queue_database_operations():
    batch_id = f"batch_{str(uuid.uuid4())[:8]}"
    task = BulkTask(
        batch_id=batch_id,
        keyword="Best Office Chairs",
        article_type="roundup",
        asins_or_facts="B08N5WRWNW"
    )
    saved = create_bulk_task(task)
    assert saved.id is not None
    assert saved.status == BulkTaskStatus.PENDING

    # Update status
    update_bulk_task(saved.id, status=BulkTaskStatus.PROCESSING, progress=50)
    retrieved = get_bulk_task(saved.id)
    assert retrieved.status == BulkTaskStatus.PROCESSING
    assert retrieved.progress == 50

    # Summary
    summary = get_batch_summary(batch_id)
    assert summary["total"] == 1
    assert summary["processing"] == 1

def test_process_single_task_success():
    batch_id = f"batch_{str(uuid.uuid4())[:8]}"
    task = BulkTask(
        batch_id=batch_id,
        keyword="Wireless Headphones",
        article_type="roundup",
        asins_or_facts="B08N5WRWNW"
    )
    create_bulk_task(task)

    mock_product = AmazonProduct(
        asin="B08N5WRWNW",
        title="Test Headphones",
        price="$99.00",
        affiliate_url="https://amazon.com/dp/B08N5WRWNW?tag=test-20"
    )

    mock_draft = ArticleDraft(
        title="Best Headphones 2026",
        slug="best-headphones-2026",
        target_keyword="Wireless Headphones",
        meta_title="Best Headphones",
        meta_description="Review",
        products=[mock_product],
        content_markdown="# Review\n> Affiliate Disclosure: ...",
        content_html="<h1>Review</h1>"
    )

    with patch("services.queue.bulk_manager.fetch_products_hybrid", return_value=[mock_product]):
        with patch("services.queue.bulk_manager.generate_roundup_article", return_value=mock_draft):
            success = process_single_task(task.id, delay_seconds=0.0)
            assert success is True

            updated = get_bulk_task(task.id)
            assert updated.status == BulkTaskStatus.COMPLETED
            assert updated.progress == 100
            assert updated.draft_id is not None
