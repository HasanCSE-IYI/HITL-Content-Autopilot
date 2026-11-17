import pytest
from core.config import (
    settings,
    SUPPORTED_OPENAI_MODELS,
    DEFAULT_OPENAI_MODEL,
    IMAGE_MODEL,
    SUPPORTED_IMAGE_QUALITIES,
    DEFAULT_IMAGE_QUALITY
)

def test_exclusive_text_model_is_gpt6_luna():
    assert SUPPORTED_OPENAI_MODELS == ["gpt-6-luna"]
    assert DEFAULT_OPENAI_MODEL == "gpt-6-luna"
    assert settings.OPENAI_MODEL == "gpt-6-luna"

def test_exclusive_image_model_is_image_2_5_flare():
    assert IMAGE_MODEL == "gpt-image-2.5-flare"
    assert settings.IMAGE_MODEL == "gpt-image-2.5-flare"

def test_exclusive_image_quality_options():
    assert set(SUPPORTED_IMAGE_QUALITIES) == {"low", "medium"}
    assert DEFAULT_IMAGE_QUALITY == "medium"

def test_settings_persists_image_quality():
    # Test setting low quality
    settings.save(image_quality="low")
    assert settings.IMAGE_QUALITY == "low"

    # Test setting medium quality
    settings.save(image_quality="medium")
    assert settings.IMAGE_QUALITY == "medium"

    # Unsupported quality falls back or is ignored
    settings.save(image_quality="ultra_high_invalid")
    assert settings.IMAGE_QUALITY in ["low", "medium"]

def test_dry_run_mode_persistence_and_factory():
    from services.generator.factory import get_llm_client, MockLLMClient
    
    # Enable dry-run
    settings.save(dry_run_mode=True)
    assert settings.DRY_RUN_MODE is True

    client = get_llm_client()
    assert isinstance(client, MockLLMClient)
    assert client.is_configured() is True
    
    # Test generation
    text = client.generate_text("Write article for testing")
    assert "Affiliate Disclosure" in text
    assert len(text) > 500

    json_data = client.generate_json("Search intent analysis")
    assert json_data.get("search_intent") == "commercial"

    img_data = client.generate_image("Modern keyboard")
    assert img_data.get("success") is True
    assert "image_url" in img_data

    # Restore dry-run to False
    settings.save(dry_run_mode=False)
    assert settings.DRY_RUN_MODE is False
