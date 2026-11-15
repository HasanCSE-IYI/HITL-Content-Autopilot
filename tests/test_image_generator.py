import pytest
from unittest.mock import MagicMock, patch
from services.media.image_generator import create_article_hero_image

def test_create_article_hero_image_success():
    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    mock_client.generate_image.return_value = {
        "success": True,
        "image_url": "https://images.example.com/generated_flare_hero.png",
        "model": "Image 2.5 Flare",
        "quality": "medium"
    }

    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"fake-png-binary-data"
        mock_get.return_value = mock_resp

        res = create_article_hero_image(
            keyword="best mechanical keyboards",
            article_angle="The Value-First Guide",
            quality="medium",
            client=mock_client
        )
        assert res["success"] is True
        assert res["model"] == "Image 2.5 Flare"
        assert res["quality"] == "medium"
        assert "generated_flare_hero.png" in res["image_url"]

        # Verify prompt generated enforces compliance policy
        assert "best mechanical keyboards" in res["prompt"]
        assert "Conceptual artwork only" in res["prompt"]
        assert "do not render recognizable physical trademarks" in res["prompt"]

def test_create_article_hero_image_low_quality():
    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    mock_client.generate_image.return_value = {
        "success": True,
        "image_url": "https://images.example.com/low_quality_hero.png",
        "model": "Image 2.5 Flare",
        "quality": "low"
    }

    res = create_article_hero_image(
        keyword="wireless gaming mouse",
        quality="low",
        client=mock_client
    )
    assert res["success"] is True
    assert res["quality"] == "low"
    mock_client.generate_image.assert_called_once()
    called_quality = mock_client.generate_image.call_args[1]["quality"]
    assert called_quality == "low"
