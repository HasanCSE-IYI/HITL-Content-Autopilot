from pathlib import Path
from typing import Optional
import streamlit as st
import logging

logger = logging.getLogger(__name__)

def render_safe_image(
    image_source: Optional[str],
    caption: Optional[str] = None,
    width: Optional[int] = None,
    use_container_width: bool = True
) -> bool:
    """
    Safely renders an image in Streamlit, protecting against MediaFileStorageError
    caused by protocol-relative URLs, missing local files, or broken image paths.
    Returns True if rendered successfully, False otherwise.
    """
    if not image_source or not isinstance(image_source, str):
        return False

    clean_src = image_source.strip()
    if not clean_src:
        return False

    # Fix protocol-relative URLs (//m.media-amazon.com/... -> https://m.media-amazon.com/...)
    if clean_src.startswith("//"):
        clean_src = f"https:{clean_src}"
    elif not clean_src.startswith(("http://", "https://", "data:image")):
        # Treat as local file path: verify file exists on disk
        try:
            p = Path(clean_src)
            if not p.is_file():
                st.caption(f"🖼️ [Image asset not found: {p.name}]")
                return False
        except Exception:
            return False

    try:
        if width:
            st.image(clean_src, caption=caption, width=width)
        else:
            st.image(clean_src, caption=caption, use_container_width=use_container_width)
        return True
    except Exception as e:
        logger.warning(f"Error rendering image in Streamlit ({clean_src[:60]}): {e}")
        st.caption("🖼️ [Image preview unavailable]")
        return False
