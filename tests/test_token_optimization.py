import pytest
from unittest.mock import MagicMock, patch
from core.models import AmazonProduct
from core.config import settings
from core.database import (
    get_cached_llm_response,
    save_cached_llm_response,
    clear_llm_cache,
    log_token_usage,
    get_token_usage_summary
)
from services.generator.prompts import (
    clean_product_title,
    inject_affiliate_links_from_placeholders,
    build_roundup_prompt
)
from services.generator.category_recommender import recommend_category_and_tags
from services.generator.openai_client import OpenAIClient
from services.generator.roundup import generate_roundup_article

def test_clean_product_title_strips_bloat():
    bloated_title = "Logitech MX Master 3S Wireless Performance Mouse, with Quiet Clicks, 8K DPI Tracking - Black (2026 Edition) [Upgraded]"
    cleaned = clean_product_title(bloated_title, max_chars=60)
    assert len(cleaned) <= 60
    assert "Logitech MX Master 3S" in cleaned
    assert "[Upgraded]" not in cleaned

def test_clean_product_title_handles_short_and_empty():
    assert clean_product_title("", max_chars=50) == "Featured Product"
    assert clean_product_title("Sony WH-1000XM5", max_chars=50) == "Sony WH-1000XM5"

def test_inject_affiliate_links_from_placeholders():
    products = [
        AmazonProduct(asin="B001", title="Mouse A", affiliate_url="https://amazon.com/dp/B001?tag=aff-20"),
        AmazonProduct(asin="B002", title="Keyboard B", affiliate_url="https://amazon.com/dp/B002?tag=aff-20")
    ]
    markdown_text = "Check out [Product 1]([AFF_LINK_1]) and also [Product 2]([AFF_LINK_2])."
    injected = inject_affiliate_links_from_placeholders(markdown_text, products)

    assert "[AFF_LINK_1]" not in injected
    assert "[AFF_LINK_2]" not in injected
    assert "https://amazon.com/dp/B001?tag=aff-20" in injected
    assert "https://amazon.com/dp/B002?tag=aff-20" in injected

def test_build_roundup_prompt_uses_placeholders():
    products = [
        AmazonProduct(asin="B001", title="Mouse A, with Very Long Bloat", price="$49.99", affiliate_url="https://amazon.com/dp/B001?tag=aff-20")
    ]
    prompt = build_roundup_prompt("best mouse", products)
    assert "[AFF_LINK_1]" in prompt
    assert "https://amazon.com/dp/B001" not in prompt  # URL omitted from prompt to save tokens

def test_llm_cache_crud():
    clear_llm_cache()
    cache_key = "test:model:task:abc123"
    payload = {"title": "Cached Title", "score": 95}
    
    # Save to cache
    save_cached_llm_response(
        cache_key=cache_key,
        model="gpt-6-luna",
        task_type="test",
        response_data=payload,
        prompt_hash="abc123",
        prompt_tokens=100,
        completion_tokens=50,
        ttl_hours=24
    )
    
    # Retrieve from cache
    cached = get_cached_llm_response(cache_key)
    assert cached is not None
    assert cached["title"] == "Cached Title"
    assert cached["score"] == 95

    # Clear cache
    deleted = clear_llm_cache()
    assert deleted >= 1
    assert get_cached_llm_response(cache_key) is None

def test_token_usage_logging_and_summary():
    # Log simulated token usage
    log_token_usage(model="gpt-6-luna", task_type="article", prompt_tokens=500, completion_tokens=300, is_cached=False)
    log_token_usage(model="gpt-6-luna", task_type="article", prompt_tokens=0, completion_tokens=0, is_cached=True)

    summary = get_token_usage_summary()
    assert summary["total_tokens"] >= 800
    assert summary["api_calls"] >= 1
    assert summary["cache_hits"] >= 1

def test_category_heuristic_short_circuit_skips_llm():
    categories = [
        {"id": 10, "name": "Gaming Mice"},
        {"id": 20, "name": "Mechanical Keyboards"}
    ]
    tags = [{"id": 101, "name": "Wireless"}, {"id": 102, "name": "RGB"}]

    mock_client = MagicMock()
    # Call with keyword that directly matches a category
    result = recommend_category_and_tags(
        keyword="gaming mice",
        title="10 Best Gaming Mice in 2026",
        categories=categories,
        tags=tags,
        client=mock_client
    )

    # LLM should NEVER be called on heuristic match!
    mock_client.generate_json.assert_not_called()
    assert result["category_id"] == 10
    assert result["category_name"] == "Gaming Mice"
    assert result["confidence"] >= 0.9

def test_openai_client_caching_and_token_tracking():
    clear_llm_cache()
    client = OpenAIClient(api_key="sk-test-valid-key-for-testing")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '{"summary": "Token optimization success"}'}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 40, "total_tokens": 160}
    }

    test_prompt = "Analyze this keyword for token optimization."

    with patch.object(client.session, "post", return_value=mock_resp) as mock_post:
        # First call: hits network
        res1 = client.generate_json(test_prompt, temperature=0.2, task_type="test_task", use_cache=True)
        assert res1["summary"] == "Token optimization success"
        assert mock_post.call_count == 1

        # Second call with identical prompt: MUST hit local cache with 0 network calls!
        res2 = client.generate_json(test_prompt, temperature=0.2, task_type="test_task", use_cache=True)
        assert res2["summary"] == "Token optimization success"
        assert mock_post.call_count == 1  # Network call count still 1!

def test_roundup_single_source_faq():
    products = [
        AmazonProduct(asin="B001", title="Product 1", price="$29.99", affiliate_url="https://amazon.com/dp/B001?tag=aff-20")
    ]
    mock_client = MagicMock()
    mock_client.generate_json.return_value = {
        "title": "Best Widgets 2026",
        "markdown_content": "# Best Widgets\n\nIntro content.\n[Check Price]([AFF_LINK_1])",
        "faqs": [
            {"question": "How long does it last?", "answer": "Over 5 years."}
        ]
    }

    draft = generate_roundup_article("widgets", products, client=mock_client)
    # Verify affiliate link replaced
    assert "https://amazon.com/dp/B001?tag=aff-20" in draft.content_markdown
    # Verify FAQs injected into markdown from single JSON source
    assert "## Frequently Asked Questions" in draft.content_markdown
    assert "How long does it last?" in draft.content_markdown
    assert "Over 5 years." in draft.content_markdown
