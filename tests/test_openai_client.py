import pytest
from unittest.mock import patch, MagicMock
from services.generator.openai_client import OpenAIClient

def test_openai_client_is_configured():
    client_unconfigured = OpenAIClient(api_key="")
    assert client_unconfigured.is_configured() is False

    client_configured = OpenAIClient(api_key="sk-proj-test123456789")
    assert client_configured.is_configured() is True
    assert client_configured.model == "gpt-6-luna"

def test_openai_client_test_api_key_success():
    client = OpenAIClient(api_key="sk-testkey")
    with patch("requests.Session.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "OK"}}]}
        mock_post.return_value = mock_resp

        res = client.test_api_key()
        assert res["success"] is True
        assert "GPT-6 Luna" in res["model"]

def test_openai_client_generate_text_gpt6_luna():
    client = OpenAIClient(api_key="sk-valid")
    with patch("requests.Session.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Expert affiliate review drafted by GPT-6 Luna."}}]
        }
        mock_post.return_value = mock_resp

        text = client.generate_text("Write a roundup section", use_cache=False)
        assert "GPT-6 Luna" in text
        # Verify model and max_completion_tokens sent in payload
        called_payload = mock_post.call_args[1]["json"]
        assert called_payload["model"] == "gpt-6-luna"
        assert "max_completion_tokens" in called_payload
        assert "max_tokens" not in called_payload

def test_openai_client_generate_json_gpt6_luna():
    client = OpenAIClient(api_key="sk-valid")
    with patch("requests.Session.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"title": "Best Ergonomic Mice 2026", "score": 98}'}}]
        }
        mock_post.return_value = mock_resp

        data = client.generate_json("Generate JSON format", use_cache=False)
        assert data["title"] == "Best Ergonomic Mice 2026"
        assert data["score"] == 98
        called_payload = mock_post.call_args[1]["json"]
        assert called_payload["model"] == "gpt-6-luna"
        assert "max_completion_tokens" in called_payload
        assert "max_tokens" not in called_payload

def test_openai_client_temperature_fallback_on_reasoning_model():
    client = OpenAIClient(api_key="sk-valid")
    with patch("requests.Session.post") as mock_post:
        # First call fails with 400 temperature error, second succeeds
        resp_fail = MagicMock()
        resp_fail.status_code = 400
        resp_fail.text = "Unsupported parameter: 'temperature' is not supported with this model."
        
        resp_success = MagicMock()
        resp_success.status_code = 200
        resp_success.json.return_value = {
            "choices": [{"message": {"content": "Content generated after temperature stripped."}}]
        }
        mock_post.side_effect = [resp_fail, resp_success]

        res = client.generate_text("Explain ergonomics", use_cache=False)
        assert "Content generated after temperature stripped." in res
        assert mock_post.call_count == 2
        # Verify second call had temperature removed
        second_payload = mock_post.call_args_list[1][1]["json"]
        assert "temperature" not in second_payload

def test_openai_client_generate_image_flare_medium():
    client = OpenAIClient(api_key="sk-valid")
    with patch("requests.Session.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{"url": "https://oaidalleapiprodscus.blob.core.windows.net/sample_flare.png"}]
        }
        mock_post.return_value = mock_resp

        res = client.generate_image("Cozy minimalist workspace setup", quality="medium")
        assert res["success"] is True
        assert "sample_flare.png" in res["image_url"]
        assert res["quality"] == "medium"
        assert "Image 2.5 Flare" in res["model"]

        called_payload = mock_post.call_args[1]["json"]
        assert called_payload["model"] == "gpt-image-2.5-flare"
        assert called_payload["quality"] == "medium"

def test_openai_client_generate_image_flare_low_quality():
    client = OpenAIClient(api_key="sk-valid")
    with patch("requests.Session.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{"url": "https://oaidalleapiprodscus.blob.core.windows.net/low_res_flare.png"}]
        }
        mock_post.return_value = mock_resp

        res = client.generate_image("Modern ergonomic keyboard banner", quality="low")
        assert res["success"] is True
        assert res["quality"] == "low"

        called_payload = mock_post.call_args[1]["json"]
        assert called_payload["model"] == "gpt-image-2.5-flare"
        assert called_payload["quality"] == "low"

def test_openai_client_generate_image_unsupported_quality_fallback():
    client = OpenAIClient(api_key="sk-valid")
    with patch("requests.Session.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{"url": "https://oaidalleapiprodscus.blob.core.windows.net/fallback.png"}]
        }
        mock_post.return_value = mock_resp

        # Asking for "ultra" quality should safely fall back to "medium"
        res = client.generate_image("Test concept", quality="ultra")
        assert res["success"] is True
        assert res["quality"] == "medium"
        called_payload = mock_post.call_args[1]["json"]
        assert called_payload["quality"] == "medium"
