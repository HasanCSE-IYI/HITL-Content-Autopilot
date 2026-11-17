import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
IMAGES_DIR = BASE_DIR / "data" / "images"

# Auto-create .env from .env.example if missing
if not ENV_PATH.exists():
    try:
        example_path = BASE_DIR / ".env.example"
        if example_path.exists():
            ENV_PATH.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            ENV_PATH.write_text("OPENAI_API_KEY=\nOPENAI_MODEL=gpt-6-luna\nAI_PROVIDER=openai\nIMAGE_MODEL=gpt-image-2.5-flare\nIMAGE_QUALITY=medium\n", encoding="utf-8")
    except Exception:
        pass

# Exclusive Next-Gen Model Standards
SUPPORTED_OPENAI_MODELS = [
    "gpt-6-luna"
]
DEFAULT_OPENAI_MODEL = "gpt-6-luna"

# Image Creation: Exclusively Image 2.5 Flare with Low/Medium Quality
IMAGE_MODEL = "gpt-image-2.5-flare"
SUPPORTED_IMAGE_QUALITIES = ["low", "medium"]
DEFAULT_IMAGE_QUALITY = "medium"

SUPPORTED_AI_PROVIDERS = ["openai", "gemini"]

# Token Optimization Standards
ENABLE_LLM_CACHE = True
LLM_CACHE_TTL_HOURS = 48
MAX_TOKENS_KEYWORD = 900
MAX_TOKENS_ROUNDUP = 3500
MAX_TOKENS_REVIEW = 2500
MAX_TOKENS_COMPARISON = 3000
MAX_TOKENS_CATEGORY = 300
MAX_TOKENS_SECTION = 800

class Settings:
    # App
    APP_NAME: str = "HITL Content Autopilot"
    APP_VERSION: str = "2.0.0"
    DATA_DIR: Path = BASE_DIR / "data"
    IMAGES_DIR: Path = IMAGES_DIR

    def __init__(self):
        self.reload()

    def reload(self):
        try:
            load_dotenv(ENV_PATH, override=True)
        except Exception:
            pass

        # Load from DB fallback
        from core.database import get_setting

        db_gemini_key = get_setting("GEMINI_API_KEY", "")
        db_gemini_model = get_setting("GEMINI_MODEL", "")
        db_openai_key = get_setting("OPENAI_API_KEY", "")
        db_openai_model = get_setting("OPENAI_MODEL", "")
        db_image_quality = get_setting("IMAGE_QUALITY", "")
        db_ai_provider = get_setting("AI_PROVIDER", "")
        db_amazon_tag = get_setting("AMAZON_ASSOCIATE_TAG", "")
        db_amazon_country = get_setting("AMAZON_COUNTRY", "")
        db_amazon_access = get_setting("AMAZON_ACCESS_KEY", "")
        db_amazon_secret = get_setting("AMAZON_SECRET_KEY", "")
        db_scraper_proxy = get_setting("AMAZON_SCRAPER_PROXY", "")
        db_wp_url = get_setting("WORDPRESS_URL", "")
        db_wp_user = get_setting("WORDPRESS_USERNAME", "")
        db_wp_pass = get_setting("WORDPRESS_APP_PASSWORD", "")
        db_wp_status = get_setting("WORDPRESS_DEFAULT_STATUS", "")
        db_timeout = get_setting("GEMINI_TIMEOUT_SECONDS", "60")
        db_openai_timeout = get_setting("OPENAI_TIMEOUT_SECONDS", "60")

        self.OPENAI_API_KEY = db_openai_key or os.getenv("OPENAI_API_KEY", "").strip()
        self.OPENAI_MODEL = DEFAULT_OPENAI_MODEL

        self.IMAGE_MODEL = IMAGE_MODEL
        img_qual = (db_image_quality or os.getenv("IMAGE_QUALITY", DEFAULT_IMAGE_QUALITY)).strip().lower()
        self.IMAGE_QUALITY = img_qual if img_qual in SUPPORTED_IMAGE_QUALITIES else DEFAULT_IMAGE_QUALITY

        self.GEMINI_API_KEY = db_gemini_key or os.getenv("GEMINI_API_KEY", "").strip()
        self.GEMINI_MODEL = db_gemini_model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
        if self.GEMINI_MODEL not in ["gemini-3.8-flash", "gemini-3.8-pro", "gemini-3.8-flash-lite"]:
            self.GEMINI_MODEL = "gemini-3.8-flash"

        self.AI_PROVIDER = db_ai_provider or os.getenv("AI_PROVIDER", "gemini").strip().lower()
        if self.AI_PROVIDER not in SUPPORTED_AI_PROVIDERS:
            self.AI_PROVIDER = "gemini"

        self.AMAZON_ASSOCIATE_TAG = db_amazon_tag or os.getenv("AMAZON_ASSOCIATE_TAG", "myaffiliate-20").strip()
        self.AMAZON_COUNTRY = db_amazon_country or os.getenv("AMAZON_COUNTRY", "com").strip()
        self.AMAZON_ACCESS_KEY = db_amazon_access or os.getenv("AMAZON_ACCESS_KEY", "").strip()
        self.AMAZON_SECRET_KEY = db_amazon_secret or os.getenv("AMAZON_SECRET_KEY", "").strip()
        self.AMAZON_SCRAPER_PROXY = db_scraper_proxy or os.getenv("AMAZON_SCRAPER_PROXY", "").strip()
        self.WORDPRESS_URL = db_wp_url or os.getenv("WORDPRESS_URL", "").strip().rstrip("/")
        self.WORDPRESS_USERNAME = db_wp_user or os.getenv("WORDPRESS_USERNAME", "").strip()
        self.WORDPRESS_APP_PASSWORD = db_wp_pass or os.getenv("WORDPRESS_APP_PASSWORD", "").strip()
        self.WORDPRESS_DEFAULT_STATUS = db_wp_status or os.getenv("WORDPRESS_DEFAULT_STATUS", "draft").strip()
        
        try:
            self.GEMINI_TIMEOUT = int(db_timeout)
        except ValueError:
            self.GEMINI_TIMEOUT = 60

        try:
            self.OPENAI_TIMEOUT = int(db_openai_timeout)
        except ValueError:
            self.OPENAI_TIMEOUT = 60

        # Token Optimization & Response Cache
        db_enable_llm_cache = get_setting("ENABLE_LLM_CACHE", "true")
        self.ENABLE_LLM_CACHE = db_enable_llm_cache.strip().lower() in ("true", "1", "yes")
        db_cache_ttl = get_setting("LLM_CACHE_TTL_HOURS", "48")
        try:
            self.LLM_CACHE_TTL_HOURS = int(db_cache_ttl)
        except ValueError:
            self.LLM_CACHE_TTL_HOURS = 48

        # Dry-Run / Safe Simulation Mode (Zero Credit Waste)
        db_dry_run = get_setting("DRY_RUN_MODE", "false")
        self.DRY_RUN_MODE = db_dry_run.strip().lower() in ("true", "1", "yes") or os.getenv("DRY_RUN_MODE", "false").strip().lower() in ("true", "1", "yes")

        self.MAX_TOKENS_KEYWORD = MAX_TOKENS_KEYWORD
        self.MAX_TOKENS_ROUNDUP = MAX_TOKENS_ROUNDUP
        self.MAX_TOKENS_REVIEW = MAX_TOKENS_REVIEW
        self.MAX_TOKENS_COMPARISON = MAX_TOKENS_COMPARISON
        self.MAX_TOKENS_CATEGORY = MAX_TOKENS_CATEGORY
        self.MAX_TOKENS_SECTION = MAX_TOKENS_SECTION

    def get_openai_api_key(self) -> str:
        if self.OPENAI_API_KEY:
            return self.OPENAI_API_KEY
        from core.database import get_setting
        db_key = get_setting("OPENAI_API_KEY", "").strip()
        if db_key:
            self.OPENAI_API_KEY = db_key
            return db_key
        env_val = os.getenv("OPENAI_API_KEY", "").strip()
        if env_val:
            self.OPENAI_API_KEY = env_val
            return env_val
        return ""

    def get_gemini_api_key(self) -> str:
        if self.GEMINI_API_KEY:
            return self.GEMINI_API_KEY
        from core.database import get_setting
        db_key = get_setting("GEMINI_API_KEY", "").strip()
        if db_key:
            self.GEMINI_API_KEY = db_key
            return db_key
        env_val = os.getenv("GEMINI_API_KEY", "").strip()
        if env_val:
            self.GEMINI_API_KEY = env_val
            return env_val
        return ""

    def get_active_provider(self) -> str:
        if self.AI_PROVIDER in ("gemini", "openai"):
            return self.AI_PROVIDER
        if self.get_gemini_api_key():
            return "gemini"
        if self.get_openai_api_key():
            return "openai"
        return "gemini"

    def save(
        self,
        openai_api_key: str = None,
        openai_model: str = None,
        image_quality: str = None,
        ai_provider: str = None,
        gemini_api_key: str = None,
        gemini_model: str = None,
        amazon_associate_tag: str = None,
        amazon_country: str = None,
        amazon_access_key: str = None,
        amazon_secret_key: str = None,
        amazon_scraper_proxy: str = None,
        wordpress_url: str = None,
        wordpress_username: str = None,
        wordpress_app_password: str = None,
        wordpress_default_status: str = None,
        gemini_timeout: int = None,
        openai_timeout: int = None,
        enable_llm_cache: bool = None,
        llm_cache_ttl_hours: int = None,
        dry_run_mode: bool = None
    ):
        from core.database import set_setting

        if dry_run_mode is not None:
            self.DRY_RUN_MODE = bool(dry_run_mode)
            os.environ["DRY_RUN_MODE"] = "true" if self.DRY_RUN_MODE else "false"
            set_setting("DRY_RUN_MODE", "true" if self.DRY_RUN_MODE else "false")

        if enable_llm_cache is not None:
            self.ENABLE_LLM_CACHE = bool(enable_llm_cache)
            set_setting("ENABLE_LLM_CACHE", "true" if self.ENABLE_LLM_CACHE else "false")

        if llm_cache_ttl_hours is not None:
            self.LLM_CACHE_TTL_HOURS = int(llm_cache_ttl_hours)
            set_setting("LLM_CACHE_TTL_HOURS", str(self.LLM_CACHE_TTL_HOURS))

        if openai_api_key is not None:
            self.OPENAI_API_KEY = openai_api_key.strip()
            os.environ["OPENAI_API_KEY"] = self.OPENAI_API_KEY
            set_setting("OPENAI_API_KEY", self.OPENAI_API_KEY)

        if openai_model is not None:
            self.OPENAI_MODEL = DEFAULT_OPENAI_MODEL
            os.environ["OPENAI_MODEL"] = self.OPENAI_MODEL
            set_setting("OPENAI_MODEL", self.OPENAI_MODEL)

        if image_quality is not None:
            clean_q = image_quality.strip().lower()
            if clean_q in SUPPORTED_IMAGE_QUALITIES:
                self.IMAGE_QUALITY = clean_q
                os.environ["IMAGE_QUALITY"] = self.IMAGE_QUALITY
                set_setting("IMAGE_QUALITY", self.IMAGE_QUALITY)

        if ai_provider is not None:
            clean_provider = ai_provider.strip().lower()
            if clean_provider in SUPPORTED_AI_PROVIDERS:
                self.AI_PROVIDER = clean_provider
                os.environ["AI_PROVIDER"] = self.AI_PROVIDER
                set_setting("AI_PROVIDER", self.AI_PROVIDER)

        if gemini_api_key is not None:
            self.GEMINI_API_KEY = gemini_api_key.strip()
            os.environ["GEMINI_API_KEY"] = self.GEMINI_API_KEY
            set_setting("GEMINI_API_KEY", self.GEMINI_API_KEY)

        if gemini_model is not None:
            self.GEMINI_MODEL = gemini_model.strip()
            os.environ["GEMINI_MODEL"] = self.GEMINI_MODEL
            set_setting("GEMINI_MODEL", self.GEMINI_MODEL)

        if amazon_associate_tag is not None:
            self.AMAZON_ASSOCIATE_TAG = amazon_associate_tag.strip()
            os.environ["AMAZON_ASSOCIATE_TAG"] = self.AMAZON_ASSOCIATE_TAG
            set_setting("AMAZON_ASSOCIATE_TAG", self.AMAZON_ASSOCIATE_TAG)

        if amazon_country is not None:
            self.AMAZON_COUNTRY = amazon_country.strip()
            os.environ["AMAZON_COUNTRY"] = self.AMAZON_COUNTRY
            set_setting("AMAZON_COUNTRY", self.AMAZON_COUNTRY)

        if amazon_access_key is not None:
            self.AMAZON_ACCESS_KEY = amazon_access_key.strip()
            os.environ["AMAZON_ACCESS_KEY"] = self.AMAZON_ACCESS_KEY
            set_setting("AMAZON_ACCESS_KEY", self.AMAZON_ACCESS_KEY)

        if amazon_secret_key is not None:
            self.AMAZON_SECRET_KEY = amazon_secret_key.strip()
            os.environ["AMAZON_SECRET_KEY"] = self.AMAZON_SECRET_KEY
            set_setting("AMAZON_SECRET_KEY", self.AMAZON_SECRET_KEY)

        if amazon_scraper_proxy is not None:
            self.AMAZON_SCRAPER_PROXY = amazon_scraper_proxy.strip()
            os.environ["AMAZON_SCRAPER_PROXY"] = self.AMAZON_SCRAPER_PROXY
            set_setting("AMAZON_SCRAPER_PROXY", self.AMAZON_SCRAPER_PROXY)

        if wordpress_url is not None:
            self.WORDPRESS_URL = wordpress_url.strip().rstrip("/")
            os.environ["WORDPRESS_URL"] = self.WORDPRESS_URL
            set_setting("WORDPRESS_URL", self.WORDPRESS_URL)

        if wordpress_username is not None:
            self.WORDPRESS_USERNAME = wordpress_username.strip()
            os.environ["WORDPRESS_USERNAME"] = self.WORDPRESS_USERNAME
            set_setting("WORDPRESS_USERNAME", self.WORDPRESS_USERNAME)

        if wordpress_app_password is not None:
            self.WORDPRESS_APP_PASSWORD = wordpress_app_password.strip()
            os.environ["WORDPRESS_APP_PASSWORD"] = self.WORDPRESS_APP_PASSWORD
            set_setting("WORDPRESS_APP_PASSWORD", self.WORDPRESS_APP_PASSWORD)

        if wordpress_default_status is not None:
            self.WORDPRESS_DEFAULT_STATUS = wordpress_default_status.strip()
            os.environ["WORDPRESS_DEFAULT_STATUS"] = self.WORDPRESS_DEFAULT_STATUS
            set_setting("WORDPRESS_DEFAULT_STATUS", self.WORDPRESS_DEFAULT_STATUS)

        if gemini_timeout is not None:
            self.GEMINI_TIMEOUT = gemini_timeout
            set_setting("GEMINI_TIMEOUT_SECONDS", str(gemini_timeout))

        if openai_timeout is not None:
            self.OPENAI_TIMEOUT = openai_timeout
            set_setting("OPENAI_TIMEOUT_SECONDS", str(openai_timeout))

        # Try to write to .env if permissions allow
        content = (
            f"DRY_RUN_MODE={'true' if self.DRY_RUN_MODE else 'false'}\n"
            f"OPENAI_API_KEY={self.OPENAI_API_KEY}\n"
            f"OPENAI_MODEL={self.OPENAI_MODEL}\n"
            f"IMAGE_MODEL={self.IMAGE_MODEL}\n"
            f"IMAGE_QUALITY={self.IMAGE_QUALITY}\n"
            f"AI_PROVIDER={self.AI_PROVIDER}\n"
            f"GEMINI_API_KEY={self.GEMINI_API_KEY}\n"
            f"GEMINI_MODEL={self.GEMINI_MODEL}\n"
            f"AMAZON_ASSOCIATE_TAG={self.AMAZON_ASSOCIATE_TAG}\n"
            f"AMAZON_COUNTRY={self.AMAZON_COUNTRY}\n"
            f"AMAZON_ACCESS_KEY={self.AMAZON_ACCESS_KEY}\n"
            f"AMAZON_SECRET_KEY={self.AMAZON_SECRET_KEY}\n"
            f"WORDPRESS_URL={self.WORDPRESS_URL}\n"
            f"WORDPRESS_USERNAME={self.WORDPRESS_USERNAME}\n"
            f"WORDPRESS_APP_PASSWORD={self.WORDPRESS_APP_PASSWORD}\n"
            f"WORDPRESS_DEFAULT_STATUS={self.WORDPRESS_DEFAULT_STATUS}\n"
        )
        try:
            ENV_PATH.write_text(content, encoding="utf-8")
        except Exception:
            pass

settings = Settings()

try:
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    os.makedirs(settings.IMAGES_DIR, exist_ok=True)
except Exception:
    pass
