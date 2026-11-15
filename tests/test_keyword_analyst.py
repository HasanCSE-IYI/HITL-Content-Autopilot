import pytest
from unittest.mock import MagicMock
from services.research.keyword_analyst import (
    analyze_keyword,
    KeywordAnalysisResult,
    EditorialAngle,
    UserQuestion
)

def test_keyword_analyst_unconfigured_fallback():
    mock_client = MagicMock()
    mock_client.is_configured.return_value = False

    result = analyze_keyword("wireless mechanical keyboard", client=mock_client)
    assert isinstance(result, KeywordAnalysisResult)
    assert result.keyword == "wireless mechanical keyboard"
    assert result.search_intent == "Commercial Investigation"
    assert len(result.editorial_angles) == 3
    assert len(result.user_questions) >= 2
    assert "Search volume and keyword difficulty are not fabricated" in result.metrics_note

def test_keyword_analyst_gemini_json_parsing():
    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    mock_client.generate_json.return_value = {
        "search_intent": "Commercial Investigation",
        "intent_explanation": "Users want to upgrade their typing experience with a cordless model.",
        "related_queries": [
            "best wireless mechanical keyboard for mac",
            "quiet mechanical keyboard bluetooth",
            "budget wireless hot swap keyboard"
        ],
        "user_questions": [
            {
                "question": "Is a wireless mechanical keyboard good for gaming?",
                "focal_answer_point": "Yes, 2.4GHz dongles provide latency on par with wired connections."
            },
            {
                "question": "How long do wireless keyboard batteries last?",
                "focal_answer_point": "From 40 hours with RGB to several months without backlighting."
            }
        ],
        "editorial_angles": [
            {
                "name": "The Value-First Champion",
                "target_audience": "Students and budget enthusiasts",
                "editorial_focus": "Maximum switches and features under $100"
            },
            {
                "name": "The Executive Minimalist",
                "target_audience": "Remote professionals",
                "editorial_focus": "Sleek low-profile aluminum aesthetics with multi-device Bluetooth"
            },
            {
                "name": "The Custom Hobbyist Pick",
                "target_audience": "Keeb enthusiasts",
                "editorial_focus": "Hot-swappable PCB and QMK/VIA key remapping support"
            }
        ],
        "recommended_article_type": "roundup"
    }

    result = analyze_keyword("best wireless keyboard", client=mock_client)
    assert result.search_intent == "Commercial Investigation"
    assert len(result.related_queries) == 3
    assert len(result.user_questions) == 2
    assert len(result.editorial_angles) == 3
    assert result.editorial_angles[0].name == "The Value-First Champion"
    assert result.user_questions[0].focal_answer_point.startswith("Yes, 2.4GHz")
    assert result.recommended_article_type == "roundup"

def test_keyword_analyst_uses_factory_client_by_default(monkeypatch):
    mock_factory_client = MagicMock()
    mock_factory_client.is_configured.return_value = False
    monkeypatch.setattr("services.research.keyword_analyst.get_llm_client", lambda: mock_factory_client)

    result = analyze_keyword("standing desk converter")
    assert result.keyword == "standing desk converter"
    assert result.search_intent == "Commercial Investigation"
    mock_factory_client.is_configured.assert_called_once()

def test_keyword_analyst_resilient_key_parsing():
    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    # LLM returns varied key abbreviations
    mock_client.generate_json.return_value = {
        "search_intent": "Transactional",
        "intent_explanation": "Ready to buy.",
        "related_queries": ["buy wireless keyboard"],
        "user_questions": [
            {"q": "Is mechanical better for typing?", "a": "Yes, tactile feedback improves speed."},
            {"question": "How long do switches last?", "focal": "50 to 100 million keystrokes."}
        ],
        "editorial_angles": [
            {"angle": "The Budget Pick", "audience": "Students", "focus": "Under $50 mechanical boards"}
        ],
        "recommended_article_type": "roundup"
    }

    result = analyze_keyword("best mechanical keyboard", client=mock_client)
    assert result.search_intent == "Transactional"
    assert len(result.user_questions) == 2
    assert result.user_questions[0].question == "Is mechanical better for typing?"
    assert result.user_questions[0].focal_answer_point == "Yes, tactile feedback improves speed."
    assert result.user_questions[1].question == "How long do switches last?"
    assert len(result.editorial_angles) == 1
    assert result.editorial_angles[0].name == "The Budget Pick"
    assert result.editorial_angles[0].target_audience == "Students"
