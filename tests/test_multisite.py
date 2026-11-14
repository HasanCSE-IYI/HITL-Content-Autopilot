import pytest
from unittest.mock import patch, MagicMock
from core.models import WordPressSite
from core.database import (
    add_wordpress_site,
    get_wordpress_site,
    list_wordpress_sites,
    delete_wordpress_site,
    set_default_wordpress_site,
    update_site_taxonomies
)
from services.publisher.wordpress import WordPressPublisher

def test_multisite_crud_and_taxonomies():
    site = WordPressSite(
        name="Tech Test Site",
        url="https://techtest.com",
        username="editor",
        app_password="pass-1234-word",
        is_default=True
    )
    # Add
    saved = add_wordpress_site(site)
    assert saved.id is not None
    assert saved.is_default is True

    # Get
    retrieved = get_wordpress_site(saved.id)
    assert retrieved.name == "Tech Test Site"
    assert retrieved.url == "https://techtest.com"

    # Update Taxonomies
    categories = [{"id": 1, "name": "Keyboards", "slug": "keyboards", "count": 5}]
    tags = [{"id": 10, "name": "Wireless", "slug": "wireless", "count": 12}]
    update_site_taxonomies(saved.id, categories, tags)

    updated = get_wordpress_site(saved.id)
    assert len(updated.categories) == 1
    assert updated.categories[0]["name"] == "Keyboards"
    assert len(updated.tags) == 1

    # Publisher with site object
    publisher = WordPressPublisher(site=updated)
    assert publisher.site_id == saved.id
    assert publisher.wp_url == "https://techtest.com"

    # Delete
    deleted = delete_wordpress_site(saved.id)
    assert deleted is True
    assert get_wordpress_site(saved.id) is None
