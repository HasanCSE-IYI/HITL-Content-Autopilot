import json
import logging
from typing import List, Dict, Any, Optional
from core.config import settings
from services.generator.factory import get_llm_client

logger = logging.getLogger(__name__)

def recommend_category_and_tags(
    keyword: str,
    title: str,
    categories: List[Dict[str, Any]],
    tags: Optional[List[Dict[str, Any]]] = None,
    client: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Recommends the best matching WordPress category and tags from synced taxonomies.
    Applies heuristic short-circuiting to save 100% tokens on obvious matches,
    and prunes candidate lists to minimize token consumption when AI is required.
    """
    if not categories:
        return {
            "category_id": None,
            "category_name": None,
            "tag_ids": [],
            "confidence": 0.0,
            "reasoning": "No categories available on target site."
        }

    clean_kw = (keyword or "").strip().lower()
    clean_title = (title or "").strip().lower()

    # 1. Heuristic Short-Circuit (100% Token Savings)
    for c in categories:
        cat_name = c["name"].strip().lower()
        if (
            cat_name == clean_kw 
            or (len(cat_name) > 3 and cat_name in clean_kw)
            or (len(clean_kw) > 3 and clean_kw in cat_name)
        ):
            matching_tag_ids = [
                t["id"] for t in (tags or []) 
                if t["name"].strip().lower() in clean_kw or t["name"].strip().lower() in clean_title
            ][:3]
            return {
                "category_id": c["id"],
                "category_name": c["name"],
                "tag_ids": matching_tag_ids,
                "confidence": 0.95,
                "reasoning": f"Direct heuristic match with '{c['name']}' (0 LLM tokens spent)."
            }

    llm = client or get_llm_client()
    if not llm.is_configured():
        return {
            "category_id": categories[0]["id"],
            "category_name": categories[0]["name"],
            "tag_ids": [],
            "confidence": 0.5,
            "reasoning": "Defaulted to first category (LLM unconfigured)."
        }

    # 2. Candidate Pruning (Minimizes prompt token footprint)
    # Score categories by keyword overlap
    kw_words = set(clean_kw.split() + clean_title.split())
    def score_taxonomy(item):
        name_words = set(item.get("name", "").lower().split())
        return len(kw_words.intersection(name_words))

    sorted_cats = sorted(categories, key=score_taxonomy, reverse=True)[:8]
    cats_summary = [{"id": c["id"], "name": c["name"]} for c in sorted_cats]
    
    sorted_tags = sorted(tags or [], key=score_taxonomy, reverse=True)[:10]
    tags_summary = [{"id": t["id"], "name": t["name"]} for t in sorted_tags]

    prompt = f"""You are an expert WordPress content organizer.
Recommend the single best category and up to 3 tags from the pruned candidate taxonomy list.

TOPIC:
- Keyword: "{keyword}"
- Title: "{title}"

CANDIDATE CATEGORIES:
{json.dumps(cats_summary)}

CANDIDATE TAGS:
{json.dumps(tags_summary)}

Return strictly valid JSON:
{{
  "category_id": <int>,
  "category_name": "<string>",
  "tag_ids": [<int>, ...],
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<brief explanation>"
}}
"""
    try:
        data = llm.generate_json(
            prompt,
            temperature=0.2,
            max_tokens=getattr(settings, "MAX_TOKENS_CATEGORY", 300),
            task_type="category_recommendation"
        )
        cat_id = data.get("category_id")
        matching_cat = next((c for c in categories if c["id"] == cat_id), None)
        if matching_cat:
            return {
                "category_id": matching_cat["id"],
                "category_name": matching_cat["name"],
                "tag_ids": [t for t in data.get("tag_ids", []) if any(et["id"] == t for et in (tags or []))],
                "confidence": float(data.get("confidence", 0.8)),
                "reasoning": data.get("reasoning", "AI semantic match on pruned taxonomy.")
            }
    except Exception as e:
        logger.warning(f"AI category recommendation failed: {e}. Falling back to default.")

    return {
        "category_id": categories[0]["id"],
        "category_name": categories[0]["name"],
        "tag_ids": [],
        "confidence": 0.5,
        "reasoning": "Fallback to first category after failed AI classification."
    }
