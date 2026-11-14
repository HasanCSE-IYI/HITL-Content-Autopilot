import pytest
from datetime import datetime, timedelta, timezone
from ui.tab_monitor import _calculate_age_days
from core.models import ArticleDraft, BulkTask, BulkTaskStatus
from core.database import (
    save_draft,
    save_bulk_tasks,
    update_bulk_task_status,
    get_bulk_task
)
import uuid

def test_calculate_age_days_exact():
    now = datetime.now()
    ten_days_ago = (now - timedelta(days=10)).isoformat()
    assert _calculate_age_days(ten_days_ago) == 10

    sixty_days_ago = (now - timedelta(days=60)).isoformat()
    assert _calculate_age_days(sixty_days_ago) == 60

    # Handles timezone-aware
    tz_now = datetime.now(timezone.utc)
    twenty_days_ago_tz = (tz_now - timedelta(days=20)).isoformat()
    assert _calculate_age_days(twenty_days_ago_tz) == 20

    # Handles empty or invalid
    assert _calculate_age_days(None) == 0
    assert _calculate_age_days("") == 0
    assert _calculate_age_days("invalid-date") == 0

def test_freshness_thresholds_categorization():
    now = datetime.now()
    
    # 95 days old -> Critical
    d_critical = ArticleDraft(
        id=f"draft_{uuid.uuid4().hex[:8]}",
        title="Outdated 2025 Buying Guide",
        slug="outdated-guide",
        article_type="roundup",
        target_keyword="ergonomic mouse",
        meta_title="Outdated Buying Guide",
        meta_description="Review of mouse",
        status="published",
        updated_at=(now - timedelta(days=95)).isoformat()
    )
    save_draft(d_critical, update_timestamp=False)
    age = _calculate_age_days(d_critical.updated_at)
    assert age >= 90

    # 65 days old -> Warning High
    d_warning = ArticleDraft(
        id=f"draft_{uuid.uuid4().hex[:8]}",
        title="Late Spring Roundup",
        slug="spring-roundup",
        article_type="roundup",
        target_keyword="standing desk",
        meta_title="Spring Roundup",
        meta_description="Desk reviews",
        status="published",
        updated_at=(now - timedelta(days=65)).isoformat()
    )
    save_draft(d_warning, update_timestamp=False)
    age_warn = _calculate_age_days(d_warning.updated_at)
    assert 60 <= age_warn < 90

def test_failed_task_retry_flow():
    batch_id = f"batch_{uuid.uuid4().hex[:6]}"
    task = BulkTask(
        id=f"task_{uuid.uuid4().hex[:8]}",
        batch_id=batch_id,
        keyword="gaming headset under 50",
        article_type="roundup",
        status=BulkTaskStatus.FAILED,
        error_message="Connection timed out while fetching ASIN details"
    )
    save_bulk_tasks([task])

    # Check task is stored as FAILED
    stored = get_bulk_task(task.id)
    assert stored is not None
    assert stored.status == BulkTaskStatus.FAILED

    # Perform retry
    update_bulk_task_status(task.id, status=BulkTaskStatus.PENDING, progress=0, error_message="")
    refreshed = get_bulk_task(task.id)
    assert refreshed.status == BulkTaskStatus.PENDING
    assert refreshed.error_message == ""
