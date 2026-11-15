import sqlite3
import json
import os
import re
import tempfile
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
from core.models import (
    ArticleDraft,
    AmazonProduct,
    WordPressSite,
    BulkTask,
    BulkTaskStatus,
    QualityScorecard
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

def resolve_db_path() -> str:
    preferred_path = DATA_DIR / "autopilot.db"
    try:
        if preferred_path.exists() and preferred_path.stat().st_size == 0:
            try:
                preferred_path.unlink()
            except Exception:
                pass
        conn = sqlite3.connect(preferred_path)
        conn.execute("CREATE TABLE IF NOT EXISTS _test_lock (id INT)")
        conn.execute("DROP TABLE _test_lock")
        conn.close()
        return str(preferred_path)
    except Exception as e:
        logger.info(f"Preferred DB path {preferred_path} not directly writable ({e}). Using local temp DB.")
        fallback_path = Path(tempfile.gettempdir()) / "hitl_autopilot.db"
        return str(fallback_path)

DB_PATH = resolve_db_path()

def set_database_path(new_path: str):
    """
    Sets the active SQLite database path (used by test suites to guarantee database isolation).
    """
    global DB_PATH
    DB_PATH = new_path
    init_db()

def get_connection():
    global DB_PATH
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        DB_PATH = str(Path(tempfile.gettempdir()) / "hitl_autopilot.db")
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def _ensure_column(conn, table_name: str, column_def: str):
    if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
        raise ValueError(f"Invalid table name identifier: {table_name}")
    col_parts = column_def.strip().split()
    if not col_parts:
        return
    col_name = col_parts[0]
    if not re.match(r"^[a-zA-Z0-9_]+$", col_name):
        raise ValueError(f"Invalid column name identifier: {col_name}")
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    cols = [row[1] for row in cursor.fetchall()]
    if col_name not in cols:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_def}")

def init_db():
    conn = get_connection()
    with conn:
        # 1. Drafts table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS drafts (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                slug TEXT NOT NULL,
                article_type TEXT NOT NULL,
                target_keyword TEXT NOT NULL,
                meta_title TEXT,
                meta_description TEXT,
                products_json TEXT,
                content_markdown TEXT,
                content_html TEXT,
                schema_json_ld TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                wordpress_post_id INTEGER,
                published_url TEXT
            )
        """)
        # Ensure migration columns for multi-site, taxonomies and quality score
        _ensure_column(conn, "drafts", "wp_site_id INTEGER")
        _ensure_column(conn, "drafts", "suggested_category_id INTEGER")
        _ensure_column(conn, "drafts", "suggested_category_name TEXT")
        _ensure_column(conn, "drafts", "selected_category_id INTEGER")
        _ensure_column(conn, "drafts", "selected_tags_json TEXT")
        _ensure_column(conn, "drafts", "scheduled_at TEXT")
        _ensure_column(conn, "drafts", "quality_scorecard_json TEXT")
        _ensure_column(conn, "drafts", "featured_image TEXT")

        # 2. Key-Value Settings table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 3. Saved ASIN & Keyword Presets table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS asin_presets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                keyword TEXT,
                asins TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # 4. Multi-Site WordPress table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wordpress_sites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                username TEXT NOT NULL,
                app_password TEXT NOT NULL,
                is_default INTEGER DEFAULT 0,
                categories_json TEXT DEFAULT '[]',
                tags_json TEXT DEFAULT '[]',
                last_synced_at TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # 5. Bulk Queue Tasks table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bulk_tasks (
                id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                keyword TEXT NOT NULL,
                article_type TEXT NOT NULL,
                asins_or_facts TEXT,
                target_wp_site_id INTEGER,
                target_category_id INTEGER,
                status TEXT NOT NULL,
                progress INTEGER DEFAULT 0,
                draft_id TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 6. Scraped Products 24-Hour Cache table (Anti-block & Rate reduction)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scraped_products_cache (
                asin TEXT PRIMARY KEY,
                country TEXT NOT NULL,
                product_json TEXT NOT NULL,
                cached_at TEXT NOT NULL
            )
        """)

        # 7. LLM Response Cache table (Token Optimization)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_cache (
                cache_key TEXT PRIMARY KEY,
                model TEXT NOT NULL,
                task_type TEXT NOT NULL,
                prompt_hash TEXT NOT NULL,
                response_json TEXT NOT NULL,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
        """)

        # 8. Token Usage Logs table (Observability & Cost Tracking)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS token_usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model TEXT NOT NULL,
                task_type TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                is_cached INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
    conn.close()

init_db()

# ==========================================
# Settings Operations
# ==========================================

def set_setting(key: str, value: str) -> None:
    conn = get_connection()
    now = datetime.now().isoformat()
    with conn:
        conn.execute("""
            INSERT INTO system_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
        """, (key, str(value), now))
    conn.close()

def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM system_settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row["value"]
    return default

def get_all_settings() -> Dict[str, str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM system_settings")
    rows = cursor.fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}

# ==========================================
# Scraped Products Cache Operations
# ==========================================

def get_cached_product(asin: str, country: str = "com", max_age_hours: int = 24) -> Optional[AmazonProduct]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT product_json, cached_at FROM scraped_products_cache
        WHERE asin = ? AND country = ?
    """, (asin.upper(), country.lower()))
    row = cursor.fetchone()
    conn.close()
    if row:
        try:
            cached_time = datetime.fromisoformat(row["cached_at"])
            age = (datetime.now() - cached_time).total_seconds() / 3600.0
            if age <= max_age_hours:
                data = json.loads(row["product_json"])
                return AmazonProduct(**data)
        except Exception as e:
            logger.warning(f"Error reading cached product {asin}: {e}")
    return None

def cache_product(product: AmazonProduct, country: str = "com") -> None:
    conn = get_connection()
    now = datetime.now().isoformat()
    product_json = json.dumps(product.model_dump())
    with conn:
        conn.execute("""
            INSERT INTO scraped_products_cache (asin, country, product_json, cached_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(asin) DO UPDATE SET
                country = excluded.country,
                product_json = excluded.product_json,
                cached_at = excluded.cached_at
        """, (product.asin.upper(), country.lower(), product_json, now))
    conn.close()

# ==========================================
# LLM Response Cache & Token Usage (Optimization)
# ==========================================

def get_cached_llm_response(cache_key: str) -> Optional[Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT response_json, expires_at FROM llm_cache
        WHERE cache_key = ?
    """, (cache_key,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    try:
        expires_at = datetime.fromisoformat(row["expires_at"])
        if datetime.now() > expires_at:
            conn = get_connection()
            with conn:
                conn.execute("DELETE FROM llm_cache WHERE cache_key = ?", (cache_key,))
            conn.close()
            return None
        return json.loads(row["response_json"])
    except Exception as e:
        logger.warning(f"Error reading cached LLM response for {cache_key}: {e}")
        return None

def save_cached_llm_response(
    cache_key: str,
    model: str,
    task_type: str,
    response_data: Any,
    prompt_hash: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    ttl_hours: int = 48
) -> None:
    from datetime import timedelta
    conn = get_connection()
    now = datetime.now()
    expires_at = (now + timedelta(hours=ttl_hours)).isoformat()
    now_str = now.isoformat()
    response_json = json.dumps(response_data) if not isinstance(response_data, str) else json.dumps({"raw_text": response_data})
    with conn:
        conn.execute("""
            INSERT INTO llm_cache (
                cache_key, model, task_type, prompt_hash, response_json,
                prompt_tokens, completion_tokens, created_at, expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                response_json = excluded.response_json,
                prompt_tokens = excluded.prompt_tokens,
                completion_tokens = excluded.completion_tokens,
                created_at = excluded.created_at,
                expires_at = excluded.expires_at
        """, (cache_key, model, task_type, prompt_hash, response_json, prompt_tokens, completion_tokens, now_str, expires_at))
    conn.close()

def clear_llm_cache() -> int:
    conn = get_connection()
    with conn:
        cursor = conn.execute("DELETE FROM llm_cache")
        deleted = cursor.rowcount
    conn.close()
    return deleted

def log_token_usage(
    model: str,
    task_type: str,
    prompt_tokens: int,
    completion_tokens: int,
    is_cached: bool = False
) -> None:
    conn = get_connection()
    now = datetime.now().isoformat()
    total = prompt_tokens + completion_tokens
    with conn:
        conn.execute("""
            INSERT INTO token_usage_logs (
                model, task_type, prompt_tokens, completion_tokens, total_tokens, is_cached, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (model, task_type, prompt_tokens, completion_tokens, total, 1 if is_cached else 0, now))
    conn.close()

def get_token_usage_summary() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            SUM(prompt_tokens) as total_prompt,
            SUM(completion_tokens) as total_completion,
            SUM(total_tokens) as total_tokens,
            COUNT(*) as total_requests,
            SUM(CASE WHEN is_cached = 1 THEN 1 ELSE 0 END) as cache_hits,
            SUM(CASE WHEN is_cached = 0 THEN 1 ELSE 0 END) as api_calls
        FROM token_usage_logs
    """)
    row = cursor.fetchone()
    
    today_prefix = datetime.now().date().isoformat()
    cursor.execute("""
        SELECT SUM(total_tokens) as today_tokens
        FROM token_usage_logs
        WHERE created_at LIKE ? AND is_cached = 0
    """, (f"{today_prefix}%",))
    today_row = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) as cached_entries FROM llm_cache")
    cache_row = cursor.fetchone()
    
    conn.close()

    total_prompt = (row["total_prompt"] if row and row["total_prompt"] else 0) or 0
    total_completion = (row["total_completion"] if row and row["total_completion"] else 0) or 0
    total_tokens = (row["total_tokens"] if row and row["total_tokens"] else 0) or 0
    cache_hits = (row["cache_hits"] if row and row["cache_hits"] else 0) or 0
    api_calls = (row["api_calls"] if row and row["api_calls"] else 0) or 0
    total_requests = (row["total_requests"] if row and row["total_requests"] else 0) or 0
    today_tokens = (today_row["today_tokens"] if today_row and today_row["today_tokens"] else 0) or 0
    cached_entries = (cache_row["cached_entries"] if cache_row and cache_row["cached_entries"] else 0) or 0

    estimated_tokens_saved = cache_hits * 2200
    estimated_cost_saved = round((estimated_tokens_saved / 1000.0) * 0.002, 3)

    return {
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_tokens": total_tokens,
        "today_tokens": today_tokens,
        "total_requests": total_requests,
        "api_calls": api_calls,
        "cache_hits": cache_hits,
        "cached_entries": cached_entries,
        "estimated_tokens_saved": estimated_tokens_saved,
        "estimated_cost_saved_usd": estimated_cost_saved
    }

# ==========================================
# ASIN Presets Operations
# ==========================================

def save_asin_preset(name: str, asins: str, keyword: str = "") -> None:
    conn = get_connection()
    now = datetime.now().isoformat()
    with conn:
        conn.execute("""
            INSERT INTO asin_presets (name, keyword, asins, created_at)
            VALUES (?, ?, ?, ?)
        """, (name, keyword, asins, now))
    conn.close()

def get_asin_presets() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, keyword, asins, created_at FROM asin_presets ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_asin_preset(preset_id: int) -> bool:
    conn = get_connection()
    with conn:
        cursor = conn.execute("DELETE FROM asin_presets WHERE id = ?", (preset_id,))
        deleted = cursor.rowcount > 0
    conn.close()
    return deleted

# ==========================================
# WordPress Sites Operations
# ==========================================

def _row_to_wp_site(row: sqlite3.Row) -> WordPressSite:
    return WordPressSite(
        id=row["id"],
        name=row["name"],
        url=row["url"],
        username=row["username"],
        app_password=row["app_password"],
        is_default=bool(row["is_default"]),
        categories=json.loads(row["categories_json"] or "[]"),
        tags=json.loads(row["tags_json"] or "[]"),
        last_synced_at=row["last_synced_at"],
        created_at=row["created_at"]
    )

def add_wordpress_site(site: WordPressSite) -> WordPressSite:
    conn = get_connection()
    now = datetime.now().isoformat()
    with conn:
        if site.is_default:
            conn.execute("UPDATE wordpress_sites SET is_default = 0")
        cursor = conn.execute("""
            INSERT INTO wordpress_sites (
                name, url, username, app_password, is_default,
                categories_json, tags_json, last_synced_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            site.name, site.url.rstrip("/"), site.username, site.app_password,
            1 if site.is_default else 0,
            json.dumps(site.categories), json.dumps(site.tags),
            site.last_synced_at, now
        ))
        site.id = cursor.lastrowid
    conn.close()
    return site

def update_wordpress_site(site: WordPressSite) -> bool:
    if not site.id:
        return False
    conn = get_connection()
    with conn:
        if site.is_default:
            conn.execute("UPDATE wordpress_sites SET is_default = 0 WHERE id != ?", (site.id,))
        cursor = conn.execute("""
            UPDATE wordpress_sites SET
                name = ?, url = ?, username = ?, app_password = ?,
                is_default = ?, categories_json = ?, tags_json = ?,
                last_synced_at = ?
            WHERE id = ?
        """, (
            site.name, site.url.rstrip("/"), site.username, site.app_password,
            1 if site.is_default else 0,
            json.dumps(site.categories), json.dumps(site.tags),
            site.last_synced_at, site.id
        ))
        updated = cursor.rowcount > 0
    conn.close()
    return updated



def delete_wordpress_site(site_id: int) -> bool:
    conn = get_connection()
    with conn:
        cursor = conn.execute("DELETE FROM wordpress_sites WHERE id = ?", (site_id,))
        deleted = cursor.rowcount > 0
    conn.close()
    return deleted

def get_wordpress_site(site_id: int) -> Optional[WordPressSite]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM wordpress_sites WHERE id = ?", (site_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return _row_to_wp_site(row)
    return None

def list_wordpress_sites() -> List[WordPressSite]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM wordpress_sites ORDER BY is_default DESC, id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_wp_site(r) for r in rows]

def get_default_wordpress_site() -> Optional[WordPressSite]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM wordpress_sites WHERE is_default = 1 LIMIT 1")
    row = cursor.fetchone()
    if not row:
        cursor.execute("SELECT * FROM wordpress_sites ORDER BY id ASC LIMIT 1")
        row = cursor.fetchone()
    conn.close()
    if row:
        return _row_to_wp_site(row)
    return None

def set_default_wordpress_site(site_id: int) -> bool:
    conn = get_connection()
    with conn:
        conn.execute("UPDATE wordpress_sites SET is_default = 0")
        cursor = conn.execute("UPDATE wordpress_sites SET is_default = 1 WHERE id = ?", (site_id,))
        updated = cursor.rowcount > 0
    conn.close()
    return updated



def update_site_taxonomies(site_id: int, categories: List[Dict[str, Any]], tags: List[Dict[str, Any]]) -> bool:
    conn = get_connection()
    now = datetime.now().isoformat()
    with conn:
        cursor = conn.execute("""
            UPDATE wordpress_sites SET
                categories_json = ?,
                tags_json = ?,
                last_synced_at = ?
            WHERE id = ?
        """, (json.dumps(categories), json.dumps(tags), now, site_id))
        updated = cursor.rowcount > 0
    conn.close()
    return updated



# ==========================================
# Bulk Queue Tasks Operations
# ==========================================

def _row_to_bulk_task(row: sqlite3.Row) -> BulkTask:
    return BulkTask(
        id=row["id"],
        batch_id=row["batch_id"],
        keyword=row["keyword"],
        article_type=row["article_type"],
        asins_or_facts=row["asins_or_facts"] or "",
        target_wp_site_id=row["target_wp_site_id"],
        target_category_id=row["target_category_id"],
        status=row["status"],
        progress=row["progress"],
        draft_id=row["draft_id"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )

def create_bulk_task(task: BulkTask) -> BulkTask:
    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO bulk_tasks (
                id, batch_id, keyword, article_type, asins_or_facts,
                target_wp_site_id, target_category_id, status, progress,
                draft_id, error_message, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task.id, task.batch_id, task.keyword, task.article_type,
            task.asins_or_facts, task.target_wp_site_id, task.target_category_id,
            task.status, task.progress, task.draft_id, task.error_message,
            task.created_at, task.updated_at
        ))
    conn.close()
    return task

def save_bulk_tasks(tasks: List[BulkTask]) -> List[BulkTask]:
    for t in tasks:
        create_bulk_task(t)
    return tasks

def update_bulk_task(
    task_id: str,
    status: Optional[str] = None,
    progress: Optional[int] = None,
    draft_id: Optional[str] = None,
    error_message: Optional[str] = None
) -> bool:
    conn = get_connection()
    now = datetime.now().isoformat()
    with conn:
        cursor = conn.execute("""
            UPDATE bulk_tasks SET
                status = COALESCE(?, status),
                progress = COALESCE(?, progress),
                draft_id = COALESCE(?, draft_id),
                error_message = COALESCE(?, error_message),
                updated_at = ?
            WHERE id = ?
        """, (status, progress, draft_id, error_message, now, task_id))
        updated = cursor.rowcount > 0
    conn.close()
    return updated



update_bulk_task_status = update_bulk_task

def get_bulk_task(task_id: str) -> Optional[BulkTask]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bulk_tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return _row_to_bulk_task(row)
    return None

def list_bulk_tasks(batch_id: Optional[str] = None) -> List[BulkTask]:
    conn = get_connection()
    cursor = conn.cursor()
    if batch_id:
        cursor.execute("SELECT * FROM bulk_tasks WHERE batch_id = ? ORDER BY created_at ASC", (batch_id,))
    else:
        cursor.execute("SELECT * FROM bulk_tasks ORDER BY created_at DESC LIMIT 200")
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_bulk_task(r) for r in rows]

def get_batch_summary(batch_id: str) -> Dict[str, Any]:
    tasks = list_bulk_tasks(batch_id=batch_id)
    total = len(tasks)
    completed = len([t for t in tasks if t.status == BulkTaskStatus.COMPLETED])
    failed = len([t for t in tasks if t.status == BulkTaskStatus.FAILED])
    processing = len([t for t in tasks if t.status == BulkTaskStatus.PROCESSING])
    pending = len([t for t in tasks if t.status == BulkTaskStatus.PENDING])
    return {
        "batch_id": batch_id,
        "total": total,
        "completed": completed,
        "failed": failed,
        "processing": processing,
        "pending": pending,
        "percent_complete": int((completed / total) * 100) if total > 0 else 0
    }

# ==========================================
# Drafts Operations
# ==========================================

def _row_to_draft(row: sqlite3.Row) -> ArticleDraft:
    products_raw = json.loads(row["products_json"] or "[]")
    products = [AmazonProduct(**p) for p in products_raw]

    # Handle quality scorecard
    scorecard_raw = row["quality_scorecard_json"] if "quality_scorecard_json" in row.keys() else None
    scorecard = QualityScorecard(**json.loads(scorecard_raw)) if scorecard_raw else None

    # Handle tags
    tags_raw = row["selected_tags_json"] if "selected_tags_json" in row.keys() else None
    selected_tags = json.loads(tags_raw) if tags_raw else []

    return ArticleDraft(
        id=row["id"],
        title=row["title"],
        slug=row["slug"],
        article_type=row["article_type"],
        target_keyword=row["target_keyword"],
        meta_title=row["meta_title"] or "",
        meta_description=row["meta_description"] or "",
        products=products,
        content_markdown=row["content_markdown"] or "",
        content_html=row["content_html"] or "",
        schema_json_ld=row["schema_json_ld"] or "",
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        wordpress_post_id=row["wordpress_post_id"],
        published_url=row["published_url"],
        wp_site_id=row["wp_site_id"] if "wp_site_id" in row.keys() else None,
        suggested_category_id=row["suggested_category_id"] if "suggested_category_id" in row.keys() else None,
        suggested_category_name=row["suggested_category_name"] if "suggested_category_name" in row.keys() else None,
        selected_category_id=row["selected_category_id"] if "selected_category_id" in row.keys() else None,
        selected_tags=selected_tags,
        scheduled_at=row["scheduled_at"] if "scheduled_at" in row.keys() else None,
        featured_image=row["featured_image"] if "featured_image" in row.keys() else None,
        quality_scorecard=scorecard
    )

def save_draft(draft: ArticleDraft, update_timestamp: bool = True) -> ArticleDraft:
    conn = get_connection()
    products_json = json.dumps([p.model_dump() for p in draft.products])
    scorecard_json = json.dumps(draft.quality_scorecard.model_dump()) if draft.quality_scorecard else None
    tags_json = json.dumps(draft.selected_tags)
    if update_timestamp:
        draft.updated_at = datetime.now().isoformat()
    with conn:
        conn.execute("""
            INSERT INTO drafts (
                id, title, slug, article_type, target_keyword,
                meta_title, meta_description, products_json,
                content_markdown, content_html, schema_json_ld,
                status, created_at, updated_at,
                wordpress_post_id, published_url,
                wp_site_id, suggested_category_id, suggested_category_name,
                selected_category_id, selected_tags_json, scheduled_at,
                quality_scorecard_json, featured_image
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                slug=excluded.slug,
                article_type=excluded.article_type,
                target_keyword=excluded.target_keyword,
                meta_title=excluded.meta_title,
                meta_description=excluded.meta_description,
                products_json=excluded.products_json,
                content_markdown=excluded.content_markdown,
                content_html=excluded.content_html,
                schema_json_ld=excluded.schema_json_ld,
                status=excluded.status,
                updated_at=excluded.updated_at,
                wordpress_post_id=excluded.wordpress_post_id,
                published_url=excluded.published_url,
                wp_site_id=excluded.wp_site_id,
                suggested_category_id=excluded.suggested_category_id,
                suggested_category_name=excluded.suggested_category_name,
                selected_category_id=excluded.selected_category_id,
                selected_tags_json=excluded.selected_tags_json,
                scheduled_at=excluded.scheduled_at,
                quality_scorecard_json=excluded.quality_scorecard_json,
                featured_image=excluded.featured_image
        """, (
            draft.id, draft.title, draft.slug, draft.article_type, draft.target_keyword,
            draft.meta_title, draft.meta_description, products_json,
            draft.content_markdown, draft.content_html, draft.schema_json_ld,
            draft.status, draft.created_at, draft.updated_at,
            draft.wordpress_post_id, draft.published_url,
            draft.wp_site_id, draft.suggested_category_id, draft.suggested_category_name,
            draft.selected_category_id, tags_json, draft.scheduled_at,
            scorecard_json, draft.featured_image
        ))
    conn.close()
    return draft

def get_draft(draft_id: str) -> Optional[ArticleDraft]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return _row_to_draft(row)
    return None

def list_drafts(status: Optional[str] = None, wp_site_id: Optional[int] = None) -> List[ArticleDraft]:
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM drafts WHERE 1=1"
    params = []
    if status and status != "all":
        query += " AND status = ?"
        params.append(status)
    if wp_site_id:
        query += " AND wp_site_id = ?"
        params.append(wp_site_id)
    query += " ORDER BY updated_at DESC"

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_draft(r) for r in rows]

def get_draft_status_counts() -> Dict[str, int]:
    """
    High-speed status count aggregation directly using SQL GROUP BY.
    Avoids loading/deserializing draft bodies, markdown, and JSON-LD into memory.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status, COUNT(*) as cnt FROM drafts GROUP BY status")
    rows = cursor.fetchall()
    conn.close()

    counts = {r["status"]: r["cnt"] for r in rows}
    total = sum(counts.values())
    return {
        "total": total,
        "needs_review": counts.get("needs_review", 0),
        "approved": counts.get("approved", 0),
        "scheduled": counts.get("scheduled", 0) + counts.get("future", 0),
        "published": counts.get("published", 0),
        "draft": counts.get("draft", 0)
    }

def delete_draft(draft_id: str) -> bool:
    conn = get_connection()
    with conn:
        cursor = conn.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
        deleted = cursor.rowcount > 0
    conn.close()
    return deleted

def update_draft_status(
    draft_id: str,
    status: str,
    wordpress_post_id: Optional[int] = None,
    published_url: Optional[str] = None,
    scheduled_at: Optional[str] = None
) -> bool:
    conn = get_connection()
    now = datetime.now().isoformat()
    with conn:
        cursor = conn.execute("""
            UPDATE drafts SET
                status = ?,
                updated_at = ?,
                wordpress_post_id = COALESCE(?, wordpress_post_id),
                published_url = COALESCE(?, published_url),
                scheduled_at = COALESCE(?, scheduled_at)
            WHERE id = ?
        """, (status, now, wordpress_post_id, published_url, scheduled_at, draft_id))
        updated = cursor.rowcount > 0
    conn.close()
    return updated

def purge_mock_test_drafts() -> int:
    """
    Purges known test / mock drafts accidentally generated by pytest runs.
    """
    conn = get_connection()
    mock_keywords = [
        "Best Headphones 2026",
        "Late Spring Roundup",
        "Outdated 2025 Buying Guide",
        "Best Laptops in 2026",
        "widgets",
        "Test MacBook Air M1"
    ]
    query = f"DELETE FROM drafts WHERE title IN ({','.join(['?']*len(mock_keywords))}) OR title LIKE '%Test%'"
    with conn:
        cursor = conn.execute(query, tuple(mock_keywords))
        count = cursor.rowcount
    conn.close()
    return count

def purge_all_drafts() -> int:
    """
    Purges all drafts from the local database to reset to a pristine clean slate.
    """
    conn = get_connection()
    with conn:
        cursor = conn.execute("DELETE FROM drafts")
        count = cursor.rowcount
    conn.close()
    return count



