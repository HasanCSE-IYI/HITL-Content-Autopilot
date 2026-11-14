import pytest
from unittest.mock import patch, MagicMock
from services.generator.category_recommender import recommend_category_and_tags

def test_category_recommender_ai_match():
    categories = [
        {"id": 2, "name": "Keyboards"},
        {"id": 5, "name": "Headphones"},
        {"id": 8, "name": "Desk Accessories"}
    ]
    tags = [
        {"id": 101, "name": "Wireless"},
        {"id": 102, "name": "Mechanical"},
        {"id": 103, "name": "Noise Cancelling"}
    ]

    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    mock_client.generate_json.return_value = {
        "category_id": 2,
        "category_name": "Keyboards",
        "tag_ids": [101, 102],
        "confidence": 0.95,
        "reasoning": "Keyword directly matches Keyboards."
    }

    rec = recommend_category_and_tags(
        keyword="Best Wireless Mechanical Keyboards",
        title="7 Best Wireless Mechanical Keyboards in 2026",
        categories=categories,
        tags=tags,
        client=mock_client
    )

    assert rec["category_id"] == 2
    assert rec["category_name"] == "Keyboards"
    assert 101 in rec["tag_ids"]
    assert rec["confidence"] >= 0.9

def test_category_recommender_heuristic_fallback():
    categories = [
        {"id": 5, "name": "Gaming Audio"},
        {"id": 9, "name": "Mechanical Keyboards"}
    ]
    # Client unconfigured -> heuristic match
    mock_client = MagicMock()
    mock_client.is_configured.return_value = False

    rec = recommend_category_and_tags(
        keyword="mechanical keyboards 2026",
        title="Best Mechanical Keyboards",
        categories=categories,
        tags=[],
        client=mock_client
    )

    assert rec["category_id"] == 9
    assert rec["category_name"] == "Mechanical Keyboards"
