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
