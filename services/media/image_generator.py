import re
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import requests
from core.config import settings, DEFAULT_IMAGE_QUALITY
from services.media.image_policy import get_editorial_image_prompt
from services.generator.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

def create_article_hero_image(
    keyword: str,
    article_angle: str = "",
    quality: str = "medium",
    client: Optional[OpenAIClient] = None
) -> Dict[str, Any]:
    """
    Creates an original editorial / concept hero graphic for the article using Image 2.5 Flare.
    Enforces compliance policy (no fake branded product photos).
    Quality is strictly 'low' or 'medium'.
    """
    clean_q = quality.strip().lower()
    if clean_q not in ("low", "medium"):
        clean_q = DEFAULT_IMAGE_QUALITY

    prompt = get_editorial_image_prompt(keyword, article_angle)
    oai = client or OpenAIClient()

    if not oai.is_configured():
        return {
            "success": False,
            "message": "OpenAI API key is not configured for image creation."
        }

    res = oai.generate_image(prompt=prompt, quality=clean_q)
    if not res.get("success"):
        return res

    image_url = res.get("image_url", "")
    local_path = None

    # Save to local data/images directory if valid URL
    if image_url and image_url.startswith("http"):
        try:
            slug = re.sub(r"[^\w\s-]", "", keyword.lower()).strip().replace(" ", "-")[:40]
            filename = f"{slug}-hero.png"
            dest = settings.IMAGES_DIR / filename
            
            img_resp = requests.get(image_url, timeout=30)
            if img_resp.status_code == 200:
                dest.write_bytes(img_resp.content)
                local_path = str(dest)
                logger.info(f"Saved Image 2.5 Flare hero image to {dest}")
        except Exception as e:
            logger.warning(f"Could not save image locally: {e}. Preserving remote URL.")

    return {
        "success": True,
        "image_url": image_url,
        "local_path": local_path,
        "prompt": prompt,
        "model": "Image 2.5 Flare",
        "quality": clean_q,
        "message": f"Successfully created hero image using Image 2.5 Flare ({clean_q} quality)."
    }
