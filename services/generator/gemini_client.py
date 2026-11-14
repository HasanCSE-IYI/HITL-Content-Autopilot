import os
import json
import re
import logging
from typing import Dict, Any, Optional
import requests
from core.config import settings

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL or "gemini-2.5-flash"
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def generate_text(self, prompt: str, temperature: float = 0.7) -> str:
        """
        Calls Gemini API directly via HTTP REST for maximum reliability.
        """
        if not self.is_configured():
            raise ValueError("GEMINI_API_KEY is not set. Please configure it in Settings or your .env file.")

        url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 8192
            }
        }

        headers = {"Content-Type": "application/json"}
        response = requests.post(url, headers=headers, json=payload, timeout=90)

        if response.status_code != 200:
            error_msg = f"Gemini API error ({response.status_code}): {response.text}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        data = response.json()
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("No generation candidate returned by Gemini.")
            text = candidates[0]["content"]["parts"][0]["text"]
            return text
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected response structure from Gemini: {data}") from e

    def generate_json(self, prompt: str, temperature: float = 0.7) -> Dict[str, Any]:
        """
        Generates text and parses it into a JSON dictionary, stripping markdown code blocks if necessary.
        """
        raw_text = self.generate_text(prompt, temperature=temperature)
        
        # Try direct json load
        try:
            return json.loads(raw_text.strip())
        except json.JSONDecodeError:
            pass

        # Try extracting ```json ... ``` block
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Fallback: find first { and last }
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(raw_text[start:end+1])
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Failed to parse JSON from model output:\n{raw_text[:500]}...")
