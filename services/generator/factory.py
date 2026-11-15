from typing import Optional, Union, Any
from core.config import settings, SUPPORTED_OPENAI_MODELS
from services.generator.gemini_client import GeminiClient, SUPPORTED_GEMINI_MODELS
from services.generator.openai_client import OpenAIClient

def get_llm_client(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: Optional[int] = None
) -> Union[GeminiClient, OpenAIClient]:
    """
    Unified Factory returning an active LLM Client (GeminiClient or OpenAIClient)
    based on explicit provider, model name signature, or system settings.
    """
    active_provider = (provider or "").strip().lower()

    if not active_provider:
        if model and any(model.startswith(prefix) for prefix in ("gpt-", "o1-", "o3-")):
            active_provider = "openai"
        elif model and model.startswith("gemini-"):
            active_provider = "gemini"
        else:
            active_provider = settings.get_active_provider()

    if active_provider == "openai":
        return OpenAIClient(api_key=api_key, model=model, timeout=timeout)
    else:
        return GeminiClient(api_key=api_key, model=model, timeout=timeout)
