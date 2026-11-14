import sqlite3
import json
import os
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
    col_name = column_def.split()[0]
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
        quality_scorecard=scorecard
    )

def save_draft(draft: ArticleDraft) -> ArticleDraft:
    conn = get_connection()
    products_json = json.dumps([p.model_dump() for p in draft.products])
    scorecard_json = json.dumps(draft.quality_scorecard.model_dump()) if draft.quality_scorecard else None
    tags_json = json.dumps(draft.selected_tags)
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
                quality_scorecard_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                quality_scorecard_json=excluded.quality_scorecard_json
        """, (
            draft.id, draft.title, draft.slug, draft.article_type, draft.target_keyword,
            draft.meta_title, draft.meta_description, products_json,
            draft.content_markdown, draft.content_html, draft.schema_json_ld,
            draft.status, draft.created_at, draft.updated_at,
            draft.wordpress_post_id, draft.published_url,
            draft.wp_site_id, draft.suggested_category_id, draft.suggested_category_name,
            draft.selected_category_id, tags_json, draft.scheduled_at,
            scorecard_json
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
