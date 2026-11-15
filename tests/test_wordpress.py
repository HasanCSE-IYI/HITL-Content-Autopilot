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

def test_wordpress_publish_article_none_html_markdown_fallback():
    publisher = WordPressPublisher(
        wp_url="https://mysite.com",
        username="admin",
        app_password="test-password"
    )
    # Draft with content_html = "" or None
    draft = ArticleDraft(
        title="Draft with Markdown Only",
        slug="draft-markdown-only",
        article_type=ArticleType.ROUNDUP,
        target_keyword="keyboards",
        meta_title="Keyboards",
        meta_description="Desc",
        content_markdown="# Auto Compiled Heading\n\nSome body text.",
        content_html="",
        schema_json_ld='<script type="application/ld+json">{}</script>',
        status=ArticleStatus.APPROVED
    )

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"id": 88, "link": "https://mysite.com/post-88/"}
        mock_post.return_value = mock_resp

        res = publisher.publish_article(draft, status="publish")
        assert res["success"] is True
        assert res["post_id"] == 88
        
        # Verify post payload received compiled markdown HTML
        called_payload = mock_post.call_args[1]["json"]
        assert "Auto Compiled Heading" in called_payload["content"]
        assert "<script" in called_payload["content"]

def test_wordpress_publish_article_featured_image_priority():
    publisher = WordPressPublisher(
        wp_url="https://mysite.com",
        username="admin",
        app_password="test-password"
    )
    draft = ArticleDraft(
        title="Featured Image Test",
        slug="featured-image-test",
        article_type=ArticleType.SINGLE_REVIEW,
        target_keyword="keyboards",
        meta_title="Keyboards",
        meta_description="Desc",
        featured_image="https://cdn.example.com/hero-lifestyle.png",
        products=[AmazonProduct(asin="B08N5WRWNW", title="Product", main_image="https://amazon.com/product.jpg")],
        content_markdown="Body",
        content_html="<p>Body</p>",
        status=ArticleStatus.APPROVED
    )

    with patch.object(publisher, "upload_featured_image", return_value=999) as mock_upload:
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 201
            mock_resp.json.return_value = {"id": 100, "link": "https://mysite.com/post-100/"}
            mock_post.return_value = mock_resp

            res = publisher.publish_article(draft, status="draft")
            assert res["success"] is True
            # Verify upload_featured_image was called with hero image first
            mock_upload.assert_called_once_with("https://cdn.example.com/hero-lifestyle.png", "Featured Image Test")
            called_payload = mock_post.call_args[1]["json"]
            assert called_payload["featured_media"] == 999
