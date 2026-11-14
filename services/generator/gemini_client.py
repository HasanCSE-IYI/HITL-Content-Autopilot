import os
import json
import re
import time
import logging
from typing import Dict, Any, Optional, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from core.config import settings

logger = logging.getLogger(__name__)

# Supported Gemini Models (Gemini 3.8 and newer only)
SUPPORTED_GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.8-pro",
    "gemini-3.8-flash-lite"
]

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"

def get_network_session(retries: int = 2) -> requests.Session:
    """
    Session with connection/timeout retry only.
    HTTP status codes (503, 429) are handled in Python logic for smart model cascading.
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=0,  # Do not raise MaxRetryError on HTTP status codes
        backoff_factor=1.0,
        allowed_methods=["POST", "GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

class GeminiClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, timeout: Optional[int] = None):
        self.api_key = (api_key or settings.get_gemini_api_key()).strip()
        self.model = model or settings.GEMINI_MODEL or DEFAULT_GEMINI_MODEL
        self.timeout = timeout or getattr(settings, "GEMINI_TIMEOUT", 60)
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.session = get_network_session(retries=2)

    def is_configured(self) -> bool:
        key = self.api_key or settings.get_gemini_api_key()
        return bool(key and len(key.strip()) > 5)

    def _get_headers(self, key: str) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": key
        }

    def _get_candidate_models(self) -> List[str]:
        """
        Builds an ordered list of models starting with user's selected model,
        followed by fallback alternatives in case of 503 (model overloaded) or 429 (rate limit).
        """
        candidates = [self.model]
        for m in SUPPORTED_GEMINI_MODELS:
            if m not in candidates:
                candidates.append(m)
        return candidates

    def test_api_key(self) -> Dict[str, Any]:
        """
        Tests the API key and model against the Gemini endpoint with auto-fallback if 503 occurs.
        """
        key = self.api_key or settings.get_gemini_api_key()
        if not key:
            return {"success": False, "message": "API key is empty. Please enter your Gemini API key."}

        models_to_try = self._get_candidate_models()
        last_error = ""

        payload = {
            "contents": [{"parts": [{"text": "Say 'OK' in one word."}]}]
        }

        for model_name in models_to_try[:3]:
            url = f"{self.base_url}/{model_name}:generateContent"
            headers = self._get_headers(key)
            try:
                resp = self.session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=max(self.timeout, 45)
                )
                if resp.status_code == 200:
                    if model_name != self.model:
                        # Auto-update to the working model
                        self.model = model_name
                        settings.save(gemini_model=model_name)
                        return {
                            "success": True,
                            "model": model_name,
                            "message": f"Verified! Note: Primary model was busy, so connected successfully using fallback '{model_name}'."
                        }
                    return {
                        "success": True,
                        "model": model_name,
                        "message": f"Connection verified! Model '{model_name}' is ready."
                    }
                elif resp.status_code == 503:
                    last_error = f"Model '{model_name}' is currently overloaded (503)."
                    logger.warning(f"{last_error} Trying fallback model...")
                    time.sleep(1.5)
                    continue
                else:
                    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    err_msg = data.get("error", {}).get("message") or resp.text
                    last_error = f"Gemini API Error ({resp.status_code}): {err_msg}"
                    # If invalid key or permission, stop immediately
                    if resp.status_code in [400, 401, 403]:
                        return {"success": False, "status_code": resp.status_code, "message": last_error}
            except requests.exceptions.Timeout:
                last_error = f"Request timed out for '{model_name}'."
                time.sleep(1.5)
            except Exception as e:
                last_error = f"Network error: {str(e)}"
                time.sleep(1.5)

        return {
            "success": False,
            "message": f"{last_error} (All attempted models were unavailable or timed out)."
        }

    def generate_text(self, prompt: str, temperature: float = 0.7) -> str:
        """
        Calls Gemini API with automatic model cascading on 503 (overloaded) and 429 (rate-limited).
        """
        key = self.api_key or settings.get_gemini_api_key()
        if not key:
            raise ValueError("GEMINI_API_KEY is not set. Please enter your API key in Settings or the sidebar.")

        headers = self._get_headers(key)
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

        models_to_try = self._get_candidate_models()
        req_timeout = max(self.timeout * 2, 120)
        errors = []

        for model_name in models_to_try:
            url = f"{self.base_url}/{model_name}:generateContent"
            for attempt in range(1, 3):
                try:
                    response = self.session.post(url, headers=headers, json=payload, timeout=req_timeout)

                    if response.status_code == 200:
                        data = response.json()
                        candidates = data.get("candidates", [])
                        if not candidates:
                            raise RuntimeError(f"No generation candidate returned by {model_name}.")
                        text = candidates[0]["content"]["parts"][0]["text"]
                        return text

                    # Handle 503 (Overloaded) or 429 (Rate Limit) -> switch to next model
                    if response.status_code in [503, 429]:
                        err_msg = f"Model {model_name} is overloaded (HTTP {response.status_code})."
                        logger.warning(f"{err_msg} Attempt {attempt}/2. Backing off...")
                        time.sleep(2)
                        continue

                    # Other HTTP error (e.g. 404 model not found)
                    error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    msg = error_data.get("error", {}).get("message") or response.text
                    errors.append(f"{model_name}: {msg}")
                    break

                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    logger.warning(f"Timeout/Network issue with {model_name} on attempt {attempt}: {e}")
                    time.sleep(2)
                    continue

        all_errs = "; ".join(errors) if errors else "Google servers are currently overloaded across all tested models."
        raise RuntimeError(f"Generation failed: {all_errs}. Please try again in a few moments.")

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
