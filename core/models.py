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
    badge: Optional[str] = None  # e.g., "Best Overall", "Best Budget", "Editor's Choice"

class ArticleType:
    ROUNDUP = "roundup"              # "Top X Best [Keyword] in 2026"
    SINGLE_REVIEW = "single_review"  # Deep dive single product review
    COMPARISON = "comparison"        # "Product A vs Product B"

class ArticleStatus:
    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    PUBLISHED = "published"

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
    wordpress_post_id: Optional[int] = None
    published_url: Optional[str] = None
