import os
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from core.models import ArticleDraft, WordPressSite
from core.config import settings
from core.database import (
    get_wordpress_site,
    get_default_wordpress_site,
    update_site_taxonomies
)

logger = logging.getLogger(__name__)

class WordPressPublisher:
    def __init__(
        self,
        wp_url: Optional[str] = None,
        username: Optional[str] = None,
        app_password: Optional[str] = None,
        site_id: Optional[int] = None,
        site: Optional[WordPressSite] = None
    ):
        self.site_id = site_id
        
        # 1. Resolve site from object or ID
        target_site = site
        if not target_site and site_id:
            target_site = get_wordpress_site(site_id)
        if not target_site and not wp_url:
            target_site = get_default_wordpress_site()

        if target_site:
            self.site_id = target_site.id
            self.wp_url = target_site.url.rstrip("/")
            self.username = target_site.username
            self.app_password = target_site.app_password.replace(" ", "")
        else:
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
            resp = requests.get(endpoint, auth=self.auth, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "user": data.get("name"),
                    "site_url": self.wp_url,
                    "message": f"Successfully connected to WordPress ({self.wp_url}) as '{data.get('name')}'!"
                }
            else:
                return {
                    "success": False,
                    "status_code": resp.status_code,
                    "message": f"Authentication failed ({resp.status_code}): {resp.text[:300]}"
                }
        except Exception as e:
            return {"success": False, "message": f"Connection error: {str(e)}"}

    def get_categories(self) -> List[Dict[str, Any]]:
        """
        Fetches categories list from WordPress REST API.
        """
        if not self.is_configured():
            return []
        endpoint = f"{self.wp_url}/wp-json/wp/v2/categories?per_page=100"
        try:
            resp = requests.get(endpoint, auth=self.auth, timeout=12)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"Error fetching WordPress categories: {e}")
        return []

    def get_tags(self) -> List[Dict[str, Any]]:
        """
        Fetches tags list from WordPress REST API.
        """
        if not self.is_configured():
            return []
        endpoint = f"{self.wp_url}/wp-json/wp/v2/tags?per_page=100"
        try:
            resp = requests.get(endpoint, auth=self.auth, timeout=12)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"Error fetching WordPress tags: {e}")
        return []

    def sync_taxonomies(self, site_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Synchronizes categories and tags from WordPress and saves to local SQLite database.
        """
        target_id = site_id or self.site_id
        if not self.is_configured():
            return {"success": False, "message": "Site not configured."}

        try:
            categories = self.get_categories()
            tags = self.get_tags()

            formatted_cats = [
                {"id": c["id"], "name": c["name"], "slug": c.get("slug", ""), "count": c.get("count", 0)}
                for c in categories
            ]
            formatted_tags = [
                {"id": t["id"], "name": t["name"], "slug": t.get("slug", ""), "count": t.get("count", 0)}
                for t in tags
            ]

            if target_id:
                update_site_taxonomies(target_id, formatted_cats, formatted_tags)

            return {
                "success": True,
                "categories_count": len(formatted_cats),
                "tags_count": len(formatted_tags),
                "categories": formatted_cats,
                "tags": formatted_tags,
                "message": f"Successfully synced {len(formatted_cats)} categories and {len(formatted_tags)} tags!"
            }
        except Exception as e:
            return {"success": False, "message": f"Taxonomy sync failed: {str(e)}"}

    def upload_featured_image(self, image_url: str, title: str) -> Optional[int]:
        """
        Downloads an external image and uploads it to WordPress Media Library.
        Returns the media attachment ID.
        """
        if not self.is_configured() or not image_url:
            return None

        try:
            if os.path.exists(image_url):
                with open(image_url, "rb") as f:
                    img_bytes = f.read()
                content_type = "image/png" if image_url.lower().endswith(".png") else "image/jpeg"
            elif image_url.startswith(("http://", "https://")):
                img_resp = requests.get(image_url, timeout=15)
                if img_resp.status_code != 200:
                    logger.warning(f"Could not download image from {image_url}")
                    return None
                img_bytes = img_resp.content
                content_type = img_resp.headers.get("content-type", "image/jpeg")
            else:
                logger.warning(f"Invalid image source (neither local file nor valid URL): {image_url}")
                return None

            ext = "png" if "png" in content_type else "jpg"
            filename = f"featured-{abs(hash(image_url)) % 100000}.{ext}"

            endpoint = f"{self.wp_url}/wp-json/wp/v2/media"
            headers = {
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": content_type
            }

            upload_resp = requests.post(
                endpoint,
                headers=headers,
                data=img_bytes,
                auth=self.auth,
                timeout=30
            )

            if upload_resp.status_code in [200, 201]:
                media_data = upload_resp.json()
                media_id = media_data.get("id")
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
        category_ids: Optional[List[int]] = None,
        tag_ids: Optional[List[int]] = None,
        scheduled_datetime: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Publishes, drafts, or schedules an article to WordPress.
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

        # 3. Determine publish status & scheduled date
        final_status = status
        post_date_gmt = None

        if status == "scheduled" or scheduled_datetime or status == "future":
            final_status = "future"
            if scheduled_datetime:
                # Format ISO 8601 string for WordPress
                try:
                    dt = datetime.fromisoformat(scheduled_datetime.replace("Z", ""))
                    post_date_gmt = dt.strftime("%Y-%m-%dT%H:%M:%S")
                except Exception:
                    post_date_gmt = scheduled_datetime

        payload = {
            "title": draft.title,
            "content": full_content,
            "status": final_status,
            "slug": draft.slug,
            "meta": {
                "_yoast_wpseo_title": draft.meta_title,
                "_yoast_wpseo_metadesc": draft.meta_description,
                "rank_math_title": draft.meta_title,
                "rank_math_description": draft.meta_description,
                "rank_math_focus_keyword": draft.target_keyword
            }
        }

        if post_date_gmt:
            payload["date_gmt"] = post_date_gmt

        # Categories & Tags
        cats = category_ids or ([draft.selected_category_id] if draft.selected_category_id else None)
        if cats:
            payload["categories"] = [c for c in cats if c]

        tags = tag_ids or (draft.selected_tags if draft.selected_tags else None)
        if tags:
            payload["tags"] = [t for t in tags if t]

        if featured_media_id:
            payload["featured_media"] = featured_media_id

        endpoint = f"{self.wp_url}/wp-json/wp/v2/posts"
        try:
            resp = requests.post(endpoint, json=payload, auth=self.auth, timeout=30)
            if resp.status_code in [200, 201]:
                data = resp.json()
                post_id = data.get("id")
                link = data.get("link")
                msg_status = "scheduled" if final_status == "future" else final_status
                return {
                    "success": True,
                    "post_id": post_id,
                    "link": link,
                    "status": msg_status,
                    "scheduled_at": post_date_gmt,
                    "message": f"Successfully posted to WordPress ({msg_status})! Post ID: {post_id}"
                }
            else:
                return {
                    "success": False,
                    "status_code": resp.status_code,
                    "message": f"WordPress publish error ({resp.status_code}): {resp.text[:400]}"
                }
        except Exception as e:
            return {"success": False, "message": f"Network error during publish: {str(e)}"}
