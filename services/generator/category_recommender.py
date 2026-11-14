import json
import logging
from typing import List, Dict, Any, Optional
from services.generator.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

def recommend_category_and_tags(
    keyword: str,
    title: str,
    categories: List[Dict[str, Any]],
    tags: Optional[List[Dict[str, Any]]] = None,
    client: Optional[GeminiClient] = None
) -> Dict[str, Any]:
    """
    Uses Gemini to recommend the best matching WordPress category and tags
    from the target website's synced taxonomy list.
    """
    if not categories:
        return {
            "category_id": None,
            "category_name": None,
            "tag_ids": [],
            "confidence": 0.0,
            "reasoning": "No categories available on target site."
        }

    gemini = client or GeminiClient()
    if not gemini.is_configured():
        # Fallback to simple keyword search
        for c in categories:
            if c["name"].lower() in keyword.lower() or keyword.lower() in c["name"].lower():
                return {
                    "category_id": c["id"],
                    "category_name": c["name"],
                    "tag_ids": [],
                    "confidence": 0.7,
                    "reasoning": "Matched by keyword name."
                }
        return {
            "category_id": categories[0]["id"],
            "category_name": categories[0]["name"],
            "tag_ids": [],
            "confidence": 0.5,
            "reasoning": "Defaulted to first category."
        }

    cats_summary = [{"id": c["id"], "name": c["name"]} for c in categories]
    tags_summary = [{"id": t["id"], "name": t["name"]} for t in (tags or [])[:50]]

    prompt = f"""You are an expert WordPress content organizer and SEO strategist.
Given an affiliate article topic, recommend the single best WordPress category and relevant tags from the website's available taxonomy.

ARTICLE TOPIC:
- Keyword: "{keyword}"
- Title: "{title}"

AVAILABLE CATEGORIES:
{json.dumps(cats_summary)}

AVAILABLE TAGS:
{json.dumps(tags_summary)}

Select the most specific and relevant category ID and up to 3 relevant tag IDs.
Return your answer in strictly valid JSON:
{{
  "category_id": <int>,
  "category_name": "<string>",
  "tag_ids": [<int>, ...],
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<brief explanation>"
}}
"""
    try:
        data = gemini.generate_json(prompt, temperature=0.2)
        cat_id = data.get("category_id")
        # Validate that cat_id actually exists in categories
        matching_cat = next((c for c in categories if c["id"] == cat_id), None)
        if matching_cat:
            return {
                "category_id": matching_cat["id"],
                "category_name": matching_cat["name"],
                "tag_ids": [t for t in data.get("tag_ids", []) if any(et["id"] == t for et in (tags or []))],
                "confidence": float(data.get("confidence", 0.8)),
                "reasoning": data.get("reasoning", "AI semantic match.")
            }
    except Exception as e:
        logger.warning(f"AI category recommendation failed: {e}. Falling back to fuzzy matching.")

    # Fallback to keyword matching
    for c in categories:
        if c["name"].lower() in keyword.lower() or keyword.lower() in c["name"].lower():
            return {
                "category_id": c["id"],
                "category_name": c["name"],
                "tag_ids": [],
                "confidence": 0.6,
                "reasoning": "Keyword name heuristic match."
            }

    return {
        "category_id": categories[0]["id"],
        "category_name": categories[0]["name"],
        "tag_ids": [],
        "confidence": 0.4,
        "reasoning": "Selected default site category."
    }
