import pytest
from services.generator.factory import get_llm_client
from services.generator.gemini_client import GeminiClient
from services.generator.openai_client import OpenAIClient

def test_llm_factory_explicit_provider():
    gemini_client = get_llm_client(provider="gemini")
    assert isinstance(gemini_client, GeminiClient)

    openai_client = get_llm_client(provider="openai")
    assert isinstance(openai_client, OpenAIClient)

def test_llm_factory_deduce_by_model_name():
    # Model starting with gpt- should produce OpenAIClient
    client1 = get_llm_client(model="gpt-6-luna")
    assert isinstance(client1, OpenAIClient)
    assert client1.model == "gpt-6-luna"

    # Model starting with gemini- should produce GeminiClient
    client2 = get_llm_client(model="gemini-3.8-flash")
    assert isinstance(client2, GeminiClient)
    assert client2.model == "gemini-3.8-flash"
