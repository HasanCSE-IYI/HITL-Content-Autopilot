import sqlite3
import json
import os
import tempfile
import logging
from typing import List, Optional
from datetime import datetime
from pathlib import Path
from core.config import settings
from core.models import ArticleDraft, AmazonProduct

logger = logging.getLogger(__name__)

def resolve_db_path() -> str:
    """
    Resolves the SQLite database path.
    Tries settings.DATA_DIR first; if on a restricted filesystem (e.g. OneDrive sandbox),
    seamlessly falls back to a user local temp path so SQLite can always write.
    """
    preferred_path = settings.DATA_DIR / "autopilot.db"
    try:
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

def init_db():
    conn = get_connection()
    with conn:
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
    conn.close()

# Auto initialize
init_db()

def _row_to_draft(row: sqlite3.Row) -> ArticleDraft:
    products_raw = json.loads(row["products_json"] or "[]")
    products = [AmazonProduct(**p) for p in products_raw]
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
        published_url=row["published_url"]
    )

def save_draft(draft: ArticleDraft) -> ArticleDraft:
    conn = get_connection()
    products_json = json.dumps([p.model_dump() for p in draft.products])
    draft.updated_at = datetime.now().isoformat()
    with conn:
        conn.execute("""
            INSERT INTO drafts (
                id, title, slug, article_type, target_keyword,
                meta_title, meta_description, products_json,
                content_markdown, content_html, schema_json_ld,
                status, created_at, updated_at,
                wordpress_post_id, published_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                published_url=excluded.published_url
        """, (
            draft.id, draft.title, draft.slug, draft.article_type, draft.target_keyword,
            draft.meta_title, draft.meta_description, products_json,
            draft.content_markdown, draft.content_html, draft.schema_json_ld,
            draft.status, draft.created_at, draft.updated_at,
            draft.wordpress_post_id, draft.published_url
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

def list_drafts(status: Optional[str] = None) -> List[ArticleDraft]:
    conn = get_connection()
    cursor = conn.cursor()
    if status and status != "all":
        cursor.execute("SELECT * FROM drafts WHERE status = ? ORDER BY updated_at DESC", (status,))
    else:
        cursor.execute("SELECT * FROM drafts ORDER BY updated_at DESC")
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

def update_draft_status(draft_id: str, status: str, wordpress_post_id: Optional[int] = None, published_url: Optional[str] = None) -> bool:
    conn = get_connection()
    now = datetime.now().isoformat()
    with conn:
        cursor = conn.execute("""
            UPDATE drafts SET
                status = ?,
                updated_at = ?,
                wordpress_post_id = COALESCE(?, wordpress_post_id),
                published_url = COALESCE(?, published_url)
            WHERE id = ?
        """, (status, now, wordpress_post_id, published_url, draft_id))
        updated = cursor.rowcount > 0
    conn.close()
    return updated
