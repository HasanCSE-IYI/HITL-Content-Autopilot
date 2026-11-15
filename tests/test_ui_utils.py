import pytest
from unittest.mock import patch, MagicMock
from ui.ui_utils import render_safe_image

def test_render_safe_image_empty_and_none():
    assert render_safe_image("") is False
    assert render_safe_image(None) is False
    assert render_safe_image("   ") is False

def test_render_safe_image_protocol_relative_url():
    with patch("streamlit.image") as mock_st_img:
        res = render_safe_image("//m.media-amazon.com/images/I/71example.jpg", caption="Test")
        assert res is True
        mock_st_img.assert_called_once()
        called_url = mock_st_img.call_args[0][0]
        assert called_url == "https://m.media-amazon.com/images/I/71example.jpg"

def test_render_safe_image_missing_local_file():
    with patch("streamlit.image") as mock_st_img:
        # Pass a nonexistent local file path
        res = render_safe_image("non_existent_folder/missing_image_123.png")
        assert res is False
        mock_st_img.assert_not_called()

def test_render_safe_image_catches_streamlit_media_storage_error():
    from streamlit.runtime.media_file_storage import MediaFileStorageError
    with patch("streamlit.image", side_effect=MediaFileStorageError("Error opening media file")):
        res = render_safe_image("https://example.com/broken_image.jpg")
        # Should gracefully catch the error and not crash
        assert res is False
