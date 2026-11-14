from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

class AmazonProduct(BaseModel):
    asin: str
    title: str
    brand: Optional[str] = None
    price: Optional[str] = "Check Price on Amazon"
    rating: Optional[float] = None
    review_count: Optional[int] = None
    features: List[str] = Field(default_factory=list)
    main_image: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    affiliate_url: str = ""
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)
    badge: Optional[str] = None
    provenance: Optional[str] = "Extracted from Amazon"

class QualityScorecard(BaseModel):
    total_score: int = 100
    word_count: int = 0
    has_ftc_disclosure: bool = True
    has_price_disclaimer: bool = True
    has_schema_markup: bool = True
    has_comparison_table: bool = True
    has_pros_cons: bool = True
    compliant_link_ratio: float = 1.0
    issues: List[str] = Field(default_factory=list)

class WordPressSite(BaseModel):
    id: Optional[int] = None
    name: str
    url: str
    username: str
    app_password: str
    is_default: bool = False
    categories: List[Dict[str, Any]] = Field(default_factory=list)
    tags: List[Dict[str, Any]] = Field(default_factory=list)
    last_synced_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class BulkTaskStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class BulkTask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    batch_id: str
    keyword: str
    article_type: str = "roundup"
    asins_or_facts: str = ""
    target_wp_site_id: Optional[int] = None
    target_category_id: Optional[int] = None
    status: str = BulkTaskStatus.PENDING
    progress: int = 0
    draft_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class ArticleType:
    ROUNDUP = "roundup"              # "Top X Best [Keyword] in 2026"
    SINGLE_REVIEW = "single_review"  # Deep dive single product review
    COMPARISON = "comparison"        # "Product A vs Product B"

class ArticleStatus:
    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    SCHEDULED = "scheduled"

class ArticleDraft(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    slug: str
    article_type: str = ArticleType.ROUNDUP
    target_keyword: str
    meta_title: str
    meta_description: str
    products: List[AmazonProduct] = Field(default_factory=list)
    content_markdown: str = ""
    content_html: str = ""
    schema_json_ld: str = ""
    status: str = ArticleStatus.NEEDS_REVIEW
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # Multi-Site & Publishing Metadata
    wp_site_id: Optional[int] = None
    suggested_category_id: Optional[int] = None
    suggested_category_name: Optional[str] = None
    selected_category_id: Optional[int] = None
    selected_tags: List[int] = Field(default_factory=list)
    scheduled_at: Optional[str] = None
    wordpress_post_id: Optional[int] = None
    published_url: Optional[str] = None
    quality_scorecard: Optional[QualityScorecard] = None
