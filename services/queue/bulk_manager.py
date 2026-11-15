import time
import logging
import threading
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from core.models import BulkTask, BulkTaskStatus, ArticleType, ArticleStatus
from core.database import (
    get_bulk_task,
    update_bulk_task,
    list_bulk_tasks,
    save_draft,
    get_wordpress_site
)
from services.amazon.extractor import fetch_products_hybrid
from services.amazon.adapter import get_product_discovery_adapter
from services.generator.roundup import generate_roundup_article
from services.generator.review import generate_single_review_article
from services.generator.comparison import generate_comparison_article
from services.generator.category_recommender import recommend_category_and_tags
from services.generator.factory import get_llm_client

logger = logging.getLogger(__name__)

# Active background runners registry to track running threads
_ACTIVE_BATCHES = {}

def process_single_task(task_id: str, delay_seconds: float = 3.0) -> bool:
    """
    Executes a single bulk task: Sourcing -> Generation -> AI Category Matching -> Draft Save.
    """
    task = get_bulk_task(task_id)
    if not task:
        return False

    update_bulk_task(task_id, status=BulkTaskStatus.PROCESSING, progress=15)

    try:
        # 1. Product Sourcing
        raw_inputs = [i.strip() for i in task.asins_or_facts.replace(",", "\n").splitlines() if i.strip()]
        
        update_bulk_task(task_id, progress=35)
        # Check if manual facts or ASINs
        is_manual = any(line.lower().startswith(("product:", "title:", "specs:")) for line in raw_inputs)
        if is_manual:
            products = fetch_products_hybrid([], manual_facts_text=task.asins_or_facts)
        else:
            products = fetch_products_hybrid(raw_inputs)

        if not products and task.keyword:
            # Fallback to product discovery adapter for seed keyword
            adapter = get_product_discovery_adapter()
            products = adapter.search_products(task.keyword, limit=3)

        if not products:
            update_bulk_task(task_id, status=BulkTaskStatus.FAILED, error_message="No products found or extracted. Please provide ASINs or manual product facts.")
            return False

        update_bulk_task(task_id, progress=60)

        # 2. Content Generation
        client = get_llm_client()
        if task.article_type == ArticleType.SINGLE_REVIEW:
            draft = generate_single_review_article(keyword=task.keyword, product=products[0], client=client)
        elif task.article_type == ArticleType.COMPARISON and len(products) >= 2:
            draft = generate_comparison_article(keyword=task.keyword, product_a=products[0], product_b=products[1], client=client)
        else:
            draft = generate_roundup_article(keyword=task.keyword, products=products, client=client)

        update_bulk_task(task_id, progress=85)

        # 3. AI Category Recommendation & Multi-site binding
        if task.target_wp_site_id:
            draft.wp_site_id = task.target_wp_site_id
            site = get_wordpress_site(task.target_wp_site_id)
            if site and site.categories:
                rec = recommend_category_and_tags(
                    keyword=task.keyword,
                    title=draft.title,
                    categories=site.categories,
                    tags=site.tags,
                    client=client
                )
                draft.suggested_category_id = rec.get("category_id")
                draft.suggested_category_name = rec.get("category_name")
                draft.selected_category_id = task.target_category_id or rec.get("category_id")
                draft.selected_tags = rec.get("tag_ids", [])
        elif task.target_category_id:
            draft.selected_category_id = task.target_category_id

        # 4. Save to Database
        saved = save_draft(draft)
        update_bulk_task(task_id, status=BulkTaskStatus.COMPLETED, progress=100, draft_id=saved.id)

        # Polite rate limiting delay
        time.sleep(delay_seconds)
        return True

    except Exception as e:
        logger.error(f"Error processing task {task_id}: {e}")
        update_bulk_task(task_id, status=BulkTaskStatus.FAILED, error_message=str(e)[:400])
        return False

def _run_batch_worker(batch_id: str, concurrency: int = 2, delay_seconds: float = 3.0):
    try:
        tasks = list_bulk_tasks(batch_id=batch_id)
        pending_tasks = [t for t in tasks if t.status == BulkTaskStatus.PENDING]
        
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
            futures = [executor.submit(process_single_task, t.id, delay_seconds) for t in pending_tasks]
            for f in futures:
                try:
                    f.result()
                except Exception as e:
                    logger.error(f"Worker exception: {e}")
    finally:
        _ACTIVE_BATCHES.pop(batch_id, None)

def start_batch_execution(batch_id: str, concurrency: int = 2, delay_seconds: float = 3.0) -> bool:
    """
    Starts execution of a bulk batch in a background thread.
    """
    if batch_id in _ACTIVE_BATCHES:
        return False  # Already running

    thread = threading.Thread(
        target=_run_batch_worker,
        args=(batch_id, concurrency, delay_seconds),
        daemon=True
    )
    _ACTIVE_BATCHES[batch_id] = thread
    thread.start()
    return True

def is_batch_running(batch_id: str) -> bool:
    return batch_id in _ACTIVE_BATCHES
