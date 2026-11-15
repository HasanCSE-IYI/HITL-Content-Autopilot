import os
import json
import re
import time
import hashlib
import logging
from typing import Dict, Any, Optional, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from core.config import (
    settings,
    SUPPORTED_OPENAI_MODELS,
    DEFAULT_OPENAI_MODEL,
    IMAGE_MODEL,
    SUPPORTED_IMAGE_QUALITIES,
    DEFAULT_IMAGE_QUALITY
)
from core.database import (
    get_cached_llm_response,
    save_cached_llm_response,
    log_token_usage
)

logger = logging.getLogger(__name__)

def get_openai_network_session(retries: int = 2) -> requests.Session:
    """
    HTTP Session with connection/timeout retry for OpenAI endpoints.
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=0,
        backoff_factor=1.0,
        allowed_methods=["POST", "GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def _fetch_openai_key(explicit_key: Optional[str] = None) -> str:
    if explicit_key is not None:
        return explicit_key.strip()
    if hasattr(settings, "get_openai_api_key"):
        return settings.get_openai_api_key().strip()
    return getattr(settings, "OPENAI_API_KEY", "").strip()

class OpenAIClient:
    """
    Client for OpenAI next-gen models:
    - Text Generation: GPT-6 Luna (gpt-6-luna)
    - Image Generation: Image 2.5 Flare (gpt-image-2.5-flare) with Quality: low / medium
    """
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, timeout: Optional[int] = None):
        self.api_key = _fetch_openai_key(api_key)
        self.model = DEFAULT_OPENAI_MODEL
        self.timeout = timeout or getattr(settings, "OPENAI_TIMEOUT", 60)
        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.image_url = "https://api.openai.com/v1/images/generations"
        self.session = get_openai_network_session(retries=2)

    def is_configured(self) -> bool:
        key = self.api_key if self.api_key is not None else _fetch_openai_key()
        return bool(key and len(key.strip()) > 5)

    def _get_headers(self, key: str) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}"
        }

    def test_api_key(self) -> Dict[str, Any]:
        """
        Tests the API key against OpenAI with GPT-6 Luna.
        """
        key = self.api_key or _fetch_openai_key()
        if not key:
            return {"success": False, "message": "API key is empty. Please enter your OpenAI API key."}

        headers = self._get_headers(key)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": "Say 'OK' in one word."}
            ],
            "max_completion_tokens": 10
        }

        try:
            resp = self.session.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=max(self.timeout, 30)
            )
            if resp.status_code == 200:
                return {
                    "success": True,
                    "model": "GPT-6 Luna (gpt-6-luna)",
                    "message": "Connection verified! GPT-6 Luna is ready for text generation."
                }
            elif resp.status_code == 401:
                return {
                    "success": False,
                    "status_code": 401,
                    "message": "Authentication failed: Invalid OpenAI API key. Please check your credentials."
                }
            elif resp.status_code == 429:
                return {
                    "success": False,
                    "status_code": 429,
                    "message": "OpenAI Rate limit / Quota exceeded (429). Please check your account usage balance."
                }
            else:
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                err_msg = data.get("error", {}).get("message") or resp.text
                return {
                    "success": False,
                    "status_code": resp.status_code,
                    "message": f"OpenAI API Error ({resp.status_code}): {err_msg}"
                }
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "message": f"Connection timed out while verifying model '{self.model}'."
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Network error connecting to OpenAI: {str(e)}"
            }

    def _compute_cache_key(self, task_type: str, prompt: str, temperature: float) -> tuple[str, str]:
        prompt_hash = hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()
        cache_key = f"{self.model}:{task_type}:{prompt_hash[:16]}:{temperature}"
        return cache_key, prompt_hash

    def generate_text(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        task_type: str = "general",
        use_cache: bool = True
    ) -> str:
        """
        Generates text using GPT-6 Luna with token caching and max_tokens protection.
        """
        key = self.api_key or _fetch_openai_key()
        if not key:
            raise ValueError("OPENAI_API_KEY is not configured! Please set it in Settings.")

        cache_key, prompt_hash = self._compute_cache_key(task_type, prompt, temperature)
        if use_cache and getattr(settings, "ENABLE_LLM_CACHE", True):
            cached = get_cached_llm_response(cache_key)
            if cached is not None:
                log_token_usage(self.model, task_type, 0, 0, is_cached=True)
                if isinstance(cached, dict):
                    return cached.get("raw_text", "")
                return str(cached)

        headers = self._get_headers(key)
        limit_tokens = max_tokens or getattr(settings, "MAX_TOKENS_SECTION", 800)
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_completion_tokens": limit_tokens
        }

        try:
            resp = self.session.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            # Defensive retry if temperature is unsupported on reasoning model
            if resp.status_code == 400 and "temperature" in resp.text.lower():
                payload.pop("temperature", None)
                resp = self.session.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
            if resp.status_code == 200:
                data = resp.json()
                usage = data.get("usage", {})
                prompt_toks = usage.get("prompt_tokens", 0)
                comp_toks = usage.get("completion_tokens", 0)
                log_token_usage(self.model, task_type, prompt_toks, comp_toks, is_cached=False)

                choices = data.get("choices", [])
                text_content = choices[0].get("message", {}).get("content", "").strip() if choices else ""
                
                if use_cache and getattr(settings, "ENABLE_LLM_CACHE", True) and text_content:
                    ttl = getattr(settings, "LLM_CACHE_TTL_HOURS", 48)
                    save_cached_llm_response(
                        cache_key=cache_key,
                        model=self.model,
                        task_type=task_type,
                        response_data={"raw_text": text_content},
                        prompt_hash=prompt_hash,
                        prompt_tokens=prompt_toks,
                        completion_tokens=comp_toks,
                        ttl_hours=ttl
                    )
                return text_content
            else:
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                err_msg = data.get("error", {}).get("message") or resp.text
                raise RuntimeError(f"OpenAI GPT-6 Luna Error ({resp.status_code}): {err_msg}")
        except requests.exceptions.Timeout:
            raise RuntimeError(f"Timeout while generating text with GPT-6 Luna.")

    def generate_json(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        task_type: str = "general",
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Generates structured JSON using GPT-6 Luna with JSON object mode, token caching, and ceiling limits.
        """
        key = self.api_key or _fetch_openai_key()
        if not key:
            raise ValueError("OPENAI_API_KEY is not configured! Please set it in Settings.")

        cache_key, prompt_hash = self._compute_cache_key(task_type, prompt, temperature)
        if use_cache and getattr(settings, "ENABLE_LLM_CACHE", True):
            cached = get_cached_llm_response(cache_key)
            if cached is not None and isinstance(cached, dict):
                log_token_usage(self.model, task_type, 0, 0, is_cached=True)
                return cached

        headers = self._get_headers(key)
        limit_tokens = max_tokens or getattr(settings, "MAX_TOKENS_ROUNDUP", 3500)
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a professional affiliate content strategist. Always output valid JSON strictly matching the requested format."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "max_completion_tokens": limit_tokens
        }

        try:
            resp = self.session.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            # Defensive retry if temperature is unsupported on reasoning model
            if resp.status_code == 400 and "temperature" in resp.text.lower():
                payload.pop("temperature", None)
                resp = self.session.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
            if resp.status_code == 200:
                data = resp.json()
                usage = data.get("usage", {})
                prompt_toks = usage.get("prompt_tokens", 0)
                comp_toks = usage.get("completion_tokens", 0)
                log_token_usage(self.model, task_type, prompt_toks, comp_toks, is_cached=False)

                choices = data.get("choices", [])
                if not choices:
                    return {}
                raw_text = choices[0].get("message", {}).get("content", "").strip()
                
                parsed_json = {}
                try:
                    parsed_json = json.loads(raw_text)
                except json.JSONDecodeError:
                    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
                    if match:
                        try:
                            parsed_json = json.loads(match.group(0))
                        except json.JSONDecodeError:
                            parsed_json = {"raw_content": raw_text}
                    else:
                        logger.error(f"Failed to parse JSON from GPT-6 Luna response: {raw_text[:200]}")
                        parsed_json = {"raw_content": raw_text}

                if use_cache and getattr(settings, "ENABLE_LLM_CACHE", True) and parsed_json:
                    ttl = getattr(settings, "LLM_CACHE_TTL_HOURS", 48)
                    save_cached_llm_response(
                        cache_key=cache_key,
                        model=self.model,
                        task_type=task_type,
                        response_data=parsed_json,
                        prompt_hash=prompt_hash,
                        prompt_tokens=prompt_toks,
                        completion_tokens=comp_toks,
                        ttl_hours=ttl
                    )

                return parsed_json
            else:
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                err_msg = data.get("error", {}).get("message") or resp.text
                raise RuntimeError(f"OpenAI GPT-6 Luna Error ({resp.status_code}): {err_msg}")
        except requests.exceptions.Timeout:
            raise RuntimeError(f"Timeout while generating JSON with GPT-6 Luna.")

    def generate_image(
        self,
        prompt: str,
        quality: str = "medium",
        size: str = "1024x1024"
    ) -> Dict[str, Any]:
        """
        Generates an original editorial / concept illustration using Image 2.5 Flare.
        Quality options strictly restricted to: 'low' or 'medium'.
        """
        key = self.api_key or _fetch_openai_key()
        if not key:
            return {"success": False, "message": "OPENAI_API_KEY is not configured! Please set it in Settings."}

        clean_q = quality.strip().lower()
        if clean_q not in ("low", "medium"):
            clean_q = "medium"

        headers = self._get_headers(key)
        payload = {
            "model": IMAGE_MODEL,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "quality": clean_q
        }

        try:
            resp = self.session.post(
                self.image_url,
                headers=headers,
                json=payload,
                timeout=max(self.timeout, 60)
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", [])
                if items:
                    image_url = items[0].get("url") or items[0].get("b64_json")
                    return {
                        "success": True,
                        "image_url": image_url,
                        "model": "Image 2.5 Flare (gpt-image-2.5-flare)",
                        "quality": clean_q,
                        "message": f"Successfully created image using Image 2.5 Flare ({clean_q} quality)."
                    }
                return {"success": False, "message": "No image data returned by Image 2.5 Flare."}
            else:
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                err_msg = data.get("error", {}).get("message") or resp.text
                return {
                    "success": False,
                    "status_code": resp.status_code,
                    "message": f"Image 2.5 Flare Error ({resp.status_code}): {err_msg}"
                }
        except requests.exceptions.Timeout:
            return {"success": False, "message": "Image 2.5 Flare request timed out."}
        except Exception as e:
            return {"success": False, "message": f"Network error during image generation: {str(e)}"}
