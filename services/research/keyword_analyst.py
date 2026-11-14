import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from services.generator.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

class EditorialAngle(BaseModel):
    name: str
    target_audience: str
    editorial_focus: str

class UserQuestion(BaseModel):
    question: str
    focal_answer_point: str

class KeywordAnalysisResult(BaseModel):
    keyword: str
    search_intent: str  # Commercial Investigation, Informational, Transactional
    intent_explanation: str
    related_queries: List[str] = Field(default_factory=list)
    user_questions: List[UserQuestion] = Field(default_factory=list)
    editorial_angles: List[EditorialAngle] = Field(default_factory=list)
    recommended_article_type: str = "roundup"
    metrics_note: str = "Search volume and keyword difficulty are not fabricated without a verified SEO API provider."

def analyze_keyword(keyword: str, client: Optional[GeminiClient] = None) -> KeywordAnalysisResult:
    """
    Expands a seed keyword into search intent, related long-tail queries,
    People Also Ask questions, and 3 differentiated editorial angles.
    Never fabricates fake search volume or difficulty numbers.
    """
    clean_kw = keyword.strip()
    gemini = client or GeminiClient()

    if not gemini.is_configured():
        return KeywordAnalysisResult(
            keyword=clean_kw,
            search_intent="Commercial Investigation",
            intent_explanation="User is comparing products before making a purchase.",
            related_queries=[f"best {clean_kw}", f"{clean_kw} reviews", f"{clean_kw} budget", f"top rated {clean_kw}"],
            user_questions=[
                UserQuestion(question=f"What is the best {clean_kw}?", focal_answer_point="Depends on budget and primary use case."),
                UserQuestion(question=f"How to choose {clean_kw}?", focal_answer_point="Consider durability, build quality, and value.")
            ],
            editorial_angles=[
                EditorialAngle(name="The Value-First Guide", target_audience="Budget-conscious buyers", editorial_focus="Maximum performance per dollar"),
                EditorialAngle(name="The Premium Top-Tier", target_audience="Professionals and enthusiasts", editorial_focus="Uncompromising build and features"),
                EditorialAngle(name="The Everyday Practical Choice", target_audience="General consumers", editorial_focus="Ease of use and balanced features")
            ]
        )

    prompt = f"""You are a professional SEO content strategist and search intent analyst.
Analyze the following seed keyword for an affiliate marketing publication:
KEYWORD: "{clean_kw}"

REQUIREMENTS:
1. Determine Primary Search Intent: 'Commercial Investigation', 'Informational', or 'Transactional'.
2. Provide a 1-sentence explanation of why the user is searching for this.
3. List 6-8 relevant, realistic long-tail related search queries.
4. List 4-5 high-intent user questions (People Also Ask style) with the critical focal point to answer in the article.
5. Propose 3 differentiated editorial angles for the article (e.g. Budget/Value, Pro/Premium, Everyday/Versatile).
6. State recommended article format: 'roundup', 'single_review', or 'comparison'.

CRITICAL RULE:
- Do NOT fabricate fake numerical search volume or keyword difficulty scores.

Return output strictly as JSON matching this format:
{{
  "search_intent": "Commercial Investigation",
  "intent_explanation": "...",
  "related_queries": ["...", "..."],
  "user_questions": [
    {{"question": "...", "focal_answer_point": "..."}}
  ],
  "editorial_angles": [
    {{"name": "...", "target_audience": "...", "editorial_focus": "..."}}
  ],
  "recommended_article_type": "roundup"
}}
"""
    try:
        data = gemini.generate_json(prompt, temperature=0.3)
        questions = [UserQuestion(**q) for q in data.get("user_questions", [])]
        angles = [EditorialAngle(**a) for a in data.get("editorial_angles", [])]

        return KeywordAnalysisResult(
            keyword=clean_kw,
            search_intent=data.get("search_intent", "Commercial Investigation"),
            intent_explanation=data.get("intent_explanation", "Comparing options before buying."),
            related_queries=data.get("related_queries", []),
            user_questions=questions,
            editorial_angles=angles,
            recommended_article_type=data.get("recommended_article_type", "roundup")
        )
    except Exception as e:
        logger.error(f"Keyword analysis error: {e}")
        return KeywordAnalysisResult(
            keyword=clean_kw,
            search_intent="Commercial Investigation",
            intent_explanation=f"Intent analysis fallback: {e}",
            related_queries=[f"best {clean_kw}", f"{clean_kw} review", f"{clean_kw} 2026"],
            user_questions=[UserQuestion(question=f"Is {clean_kw} worth it?", focal_answer_point="Key value considerations.")],
            editorial_angles=[EditorialAngle(name="Comprehensive Guide", target_audience="All buyers", editorial_focus="Testing and review")]
        )
