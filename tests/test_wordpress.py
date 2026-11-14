import pytest
from unittest.mock import patch, MagicMock
from core.models import ArticleDraft, AmazonProduct, ArticleType, ArticleStatus
from services.publisher.wordpress import WordPressPublisher

def test_wordpress_unconfigured():
    publisher = WordPressPublisher(wp_url="", username="", app_password="")
    assert publisher.is_configured() is False
    res = publisher.test_connection()
    assert res["success"] is False

def test_wordpress_connection_success():
    publisher = WordPressPublisher(
        wp_url="https://mysite.com",
        username="admin",
        app_password="test-password"
    )
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": 1, "name": "Admin User"}
        mock_get.return_value = mock_resp

        res = publisher.test_connection()
        assert res["success"] is True
        assert res["user"] == "Admin User"

def test_wordpress_publish_article():
    publisher = WordPressPublisher(
        wp_url="https://mysite.com",
        username="admin",
        app_password="test-password"
    )
    draft = ArticleDraft(
        title="Best Keyboards 2026",
        slug="best-keyboards-2026",
        article_type=ArticleType.ROUNDUP,
        target_keyword="keyboards",
        meta_title="Best Keyboards 2026 SEO",
        meta_description="Read our review.",
        products=[AmazonProduct(asin="B08N5WRWNW", title="Test Keyboard", affiliate_url="https://amzn.to/test")],
        content_markdown="# Review",
        content_html="<h1>Review</h1>",
        status=ArticleStatus.APPROVED
    )

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"id": 42, "link": "https://mysite.com/best-keyboards-2026/"}
        mock_post.return_value = mock_resp

        res = publisher.publish_article(draft, status="draft", category_ids=[5])
        assert res["success"] is True
        assert res["post_id"] == 42
        assert res["link"] == "https://mysite.com/best-keyboards-2026/"
