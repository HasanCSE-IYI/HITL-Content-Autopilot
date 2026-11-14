import os
import requests
from typing import Dict, Any, List, Optional
import logging
from core.models import ArticleDraft
from core.config import settings

logger = logging.getLogger(__name__)

class WordPressPublisher:
    def __init__(
        self,
        wp_url: Optional[str] = None,
        username: Optional[str] = None,
        app_password: Optional[str] = None
    ):
        self.wp_url = (wp_url or settings.WORDPRESS_URL).rstrip("/")
        self.username = username or settings.WORDPRESS_USERNAME
        self.app_password = (app_password or settings.WORDPRESS_APP_PASSWORD).replace(" ", "")
        self.auth = (self.username, self.app_password) if self.username and self.app_password else None

    def is_configured(self) -> bool:
        return bool(self.wp_url and self.username and self.app_password)

    def test_connection(self) -> Dict[str, Any]:
        """
        Tests WordPress connection and authentication.
        """
        if not self.is_configured():
            return {"success": False, "message": "WordPress URL, username, or application password not configured."}
        
        endpoint = f"{self.wp_url}/wp-json/wp/v2/users/me"
        try:
            resp = requests.get(endpoint, auth=self.auth, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "user": data.get("name"),
                    "message": f"Successfully connected to WordPress as {data.get('name')}!"
                }
            else:
                return {
                    "success": False,
                    "status_code": resp.status_code,
                    "message": f"Authentication failed ({resp.status_code}): {resp.text}"
                }
        except Exception as e:
            return {"success": False, "message": f"Connection error: {str(e)}"}

    def get_categories(self) -> List[Dict[str, Any]]:
        """
        Fetches categories list from WordPress.
        """
        if not self.is_configured():
            return []
        endpoint = f"{self.wp_url}/wp-json/wp/v2/categories?per_page=100"
        try:
            resp = requests.get(endpoint, auth=self.auth, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"Error fetching WordPress categories: {e}")
        return []

    def upload_featured_image(self, image_url: str, title: str) -> Optional[int]:
        """
        Downloads an external image and uploads it to WordPress Media Library.
        Returns the media attachment ID.
        """
        if not self.is_configured() or not image_url:
            return None

        try:
            # 1. Download image
            img_resp = requests.get(image_url, timeout=15)
            if img_resp.status_code != 200:
                logger.warning(f"Could not download image from {image_url}")
                return None

            content_type = img_resp.headers.get("content-type", "image/jpeg")
            ext = "png" if "png" in content_type else "jpg"
            filename = f"featured-{abs(hash(image_url)) % 100000}.{ext}"

            # 2. Upload to WP
            endpoint = f"{self.wp_url}/wp-json/wp/v2/media"
            headers = {
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": content_type
            }

            upload_resp = requests.post(
                endpoint,
                headers=headers,
                data=img_resp.content,
                auth=self.auth,
                timeout=30
            )

            if upload_resp.status_code in [200, 201]:
                media_data = upload_resp.json()
                media_id = media_data.get("id")
                # Update alt text
                if media_id:
                    requests.post(
                        f"{endpoint}/{media_id}",
                        json={"alt_text": title, "title": title},
                        auth=self.auth,
                        timeout=10
                    )
                return media_id
            else:
                logger.warning(f"Failed to upload media: {upload_resp.status_code} {upload_resp.text}")
        except Exception as e:
            logger.error(f"Error in upload_featured_image: {e}")

        return None

    def publish_article(
        self,
        draft: ArticleDraft,
        status: str = "draft",
        category_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Publishes or drafts an article to WordPress.
        """
        if not self.is_configured():
            return {"success": False, "message": "WordPress configuration missing."}

        # 1. Upload featured image if available
        featured_media_id = None
        if draft.products and draft.products[0].main_image:
            featured_media_id = self.upload_featured_image(
                draft.products[0].main_image,
                draft.title
            )

        # 2. Prepare HTML content + Schema
        full_content = draft.content_html
        if draft.schema_json_ld:
            full_content += f"\n\n{draft.schema_json_ld}"

        payload = {
            "title": draft.title,
            "content": full_content,
            "status": status,
            "slug": draft.slug,
            "meta": {
                "_yoast_wpseo_title": draft.meta_title,
                "_yoast_wpseo_metadesc": draft.meta_description,
                "rank_math_title": draft.meta_title,
                "rank_math_description": draft.meta_description,
                "rank_math_focus_keyword": draft.target_keyword
            }
        }

        if category_ids:
            payload["categories"] = category_ids

        if featured_media_id:
            payload["featured_media"] = featured_media_id

        endpoint = f"{self.wp_url}/wp-json/wp/v2/posts"
        try:
            resp = requests.post(endpoint, json=payload, auth=self.auth, timeout=30)
            if resp.status_code in [200, 201]:
                data = resp.json()
                post_id = data.get("id")
                link = data.get("link")
                return {
                    "success": True,
                    "post_id": post_id,
                    "link": link,
                    "status": status,
                    "message": f"Successfully published to WordPress ({status})! Post ID: {post_id}"
                }
            else:
                return {
                    "success": False,
                    "status_code": resp.status_code,
                    "message": f"WordPress publish error ({resp.status_code}): {resp.text}"
                }
        except Exception as e:
            return {"success": False, "message": f"Network error during publish: {str(e)}"}
