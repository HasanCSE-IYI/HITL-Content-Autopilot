import json
import logging
from typing import Optional, Union, Any, Dict
from core.config import settings, SUPPORTED_OPENAI_MODELS
from services.generator.gemini_client import GeminiClient, SUPPORTED_GEMINI_MODELS
from services.generator.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

class MockLLMClient:
    """
    🛡️ Zero-Cost Dry-Run Simulation Client:
    Generates realistic, fully compliant affiliate markdown articles,
    SEO metadata, and JSON-LD schemas with ZERO network calls, ZERO latency,
    and ZERO credit or token consumption.
    """
    def __init__(self, model: str = "gpt-6-luna (Dry-Run Simulation)"):
        self.model = model
        self.provider = "dry_run"

    def is_configured(self) -> bool:
        return True

    def test_api_key(self) -> Dict[str, Any]:
        return {
            "success": True,
            "message": "🛡️ Dry-Run Simulator Active: Connection simulated with $0.00 credit usage.",
            "model": self.model
        }

    def generate_image(self, prompt: str, quality: str = "medium", size: str = "1024x1024") -> Dict[str, Any]:
        return {
            "success": True,
            "image_url": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=1200&q=80",
            "message": "🛡️ Dry-Run Simulated Hero Image generated with $0.00 credit usage.",
            "model": "gpt-image-2.5-flare (Simulation)",
            "quality": quality
        }

    def generate_text(self, prompt: str, system_instruction: Optional[str] = None, use_cache: bool = True) -> str:
        # If it's a section regenerate prompt:
        if "REWRITE" in prompt.upper() or "REGENERATE" in prompt.upper() or "TONE" in prompt.upper():
            return "This section has been smoothly regenerated with high-converting buyer advice, crisp active phrasing, and clear ergonomic insights."

        # Return full, realistic, high-quality affiliate review / roundup article
        return """*Affiliate Disclosure: As an Amazon Associate, we earn from qualifying purchases at no additional cost to you.*

# Top 5 Best Ergonomic Keyboards in 2026: Tested & Reviewed

When spending 8 to 10 hours a day typing at your desk, standard flat keyboards force your forearms into an unnatural pronation, leading directly to wrist fatigue and repetitive strain. Finding the best ergonomic keyboard is not just about comfort—it is a long-term investment in your physical well-being and daily typing speed.

Over the past four weeks, our editorial team rigorously benchmarked the leading split, tented, and curved ergonomic keyboards on Amazon. Below is our definitive comparison and buyer's breakdown.

## Quick Comparison: Top Ergonomic Keyboards

| Product Name | Design Type | Connectivity | Key Advantage | Rating | Check Price |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **Keychron K2 Pro** | Compact 75% | Bluetooth / USB-C | Hot-Swappable Switches | 4.8 / 5 | [View on Amazon]({{AFF_LINK_1}}) |
| **Logitech Ergo K860** | Curved Split | Wireless / Unifying | Integrated Pillowed Wrist Rest | 4.7 / 5 | [View on Amazon]({{AFF_LINK_2}}) |
| **Kinesis Advantage2** | Contoured Bowl | USB Wired | Ortholinear Matrix Layout | 4.9 / 5 | [View on Amazon]({{AFF_LINK_3}}) |

---

## 1. Keychron K2 Pro Wireless Mechanical Keyboard — Best Overall Custom Feel

The **Keychron K2 Pro** delivers a rare balance of premium acoustic dampening, custom QMK/VIA key remapping, and ergonomic wrist incline. For developers, writers, and power typists who crave tactile responsiveness without the fatigue of stiff keybeds, this keyboard represents the pinnacle of compact workstation efficiency.

### Who It's Best For
- Typists who demand mechanical tactile feedback with custom keycaps.
- Multi-device users switching between macOS and Windows via dedicated hardware toggles.

### Key Specifications & Highlights
- **Layout:** Compact 75% tenkeyless design saving valuable mouse desk space.
- **Battery Life:** Up to 300 hours with backlighting disabled.
- **Switches:** Pre-lubed Keychron K Pro Mechanical Switches.

### Pros & Cons
**Pros:**
- Superb acoustic dampening foam eliminates hollow ping.
- Hot-swappable sockets permit effortless switch replacement without soldering.
- Native macOS and Windows keycap legends included out of the box.

**Cons:**
- Taller chassis profile requires an external wrist rest for optimal comfort.

👉 [Check Latest Price for Keychron K2 Pro on Amazon]({{AFF_LINK_1}})

---

## Comprehensive Buyer's Guide: How We Test

When evaluating ergonomic keyboards, our testing protocol focuses on three non-negotiable criteria:
1. **Neutral Wrist Alignment:** Whether the keybed supports zero-degree or negative tilt to keep wrists flat.
2. **Key Actuation Force:** Light, responsive actuation prevents bottoming out and finger tendon stress.
3. **Software Programmability:** On-board memory allows remapping repetitive shortcuts to thumbs.

---

## Frequently Asked Questions (FAQ)

### Are ergonomic keyboards really worth the learning curve?
Yes. Clinical studies indicate that split curved layouts reduce forearm muscle activity by up to 25%, significantly lowering the risk of carpal tunnel syndrome.

### Can I connect an ergonomic keyboard to both Mac and Windows?
Yes, modern options from Keychron and Logitech support multi-device Bluetooth pairing with immediate OS key swapping.

---

*Amazon Pricing Disclaimer: Product prices and availability are accurate as of the date/time indicated and are subject to change. Any price and availability information displayed on Amazon at the time of purchase will apply to the purchase of this product.*
"""

    def generate_json(self, prompt: str, system_instruction: Optional[str] = None, use_cache: bool = True) -> Dict[str, Any]:
        # Keyword research prompt response:
        if "INTENT" in prompt.upper() or "KEYWORD" in prompt.upper():
            return {
                "search_intent": "commercial",
                "difficulty": "medium",
                "intent_reasoning": "High-intent commercial query driven by buyers seeking tested ergonomics.",
                "paa_questions": [
                    "Is an ergonomic keyboard better for carpal tunnel?",
                    "How long does it take to get used to a split keyboard?",
                    "What is the best ergonomic mechanical keyboard in 2026?"
                ],
                "recommended_angle": "Ultimate Ergonomic Workstation Comfort",
                "audience_profile": "Knowledge workers, software engineers, and writers sitting 8+ hours."
            }

        # Category recommendation response:
        if "CATEGORY" in prompt.upper() or "TAG" in prompt.upper():
            return {
                "category_id": 1,
                "category_name": "Computer Accessories",
                "suggested_tags": ["keyboards", "ergonomics", "workstation"],
                "confidence": 0.95,
                "reasoning": "Matched based on ergonomic peripherals and workstation accessories taxonomy."
            }

        # Default SEO Metadata JSON:
        return {
            "seo_title": "Top 5 Best Ergonomic Keyboards in 2026: Tested & Reviewed",
            "meta_description": "Compare the best ergonomic keyboards for wrist pain, typing speed, and long hours at your desk. Tested by our workstation experts.",
            "primary_keyword": "best ergonomic keyboards",
            "score": 95
        }

def get_llm_client(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: Optional[int] = None
) -> Union[GeminiClient, OpenAIClient, MockLLMClient]:
    """
    Unified Factory returning an active LLM Client (GeminiClient, OpenAIClient, or MockLLMClient)
    based on explicit provider, model name signature, or system settings.
    """
    # 🛡️ Zero-Cost Dry-Run Mode check
    active_provider = (provider or "").strip().lower()
    if active_provider == "dry_run" or (not active_provider and getattr(settings, "DRY_RUN_MODE", False)):
        return MockLLMClient()

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
