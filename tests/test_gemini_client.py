import pytest
from unittest.mock import patch, MagicMock
from services.generator.gemini_client import GeminiClient

def test_gemini_client_fallback_on_503():
    client = GeminiClient(api_key="test-api-key", model="gemini-3.8-flash")
    
    # Mock responses: 1st call (gemini-3.8-flash) gives 503, 2nd call (gemini-3.8-pro) gives 200
    resp_503 = MagicMock()
    resp_503.status_code = 503
    resp_503.text = "Model is overloaded."

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Generated successfully with fallback to 3.8-pro!"}]
                }
            }
        ]
    }

    with patch.object(client.session, "post", side_effect=[resp_503, resp_503, resp_200]):
        text = client.generate_text("Test prompt")
        assert text == "Generated successfully with fallback to 3.8-pro!"

def test_gemini_client_uses_secure_header():
    client = GeminiClient(api_key="secret-key-12345", model="gemini-3.8-flash")
    headers = client._get_headers("secret-key-12345")
    assert headers["x-goog-api-key"] == "secret-key-12345"
    assert headers["Content-Type"] == "application/json"
