import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if present
load_dotenv(BASE_DIR / ".env")

class Settings:
    # App
    APP_NAME: str = "HITL Content Autopilot"
    APP_VERSION: str = "1.0.0"
    DATA_DIR: Path = BASE_DIR / "data"

    # Gemini AI
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Amazon Associates
    AMAZON_ASSOCIATE_TAG: str = os.getenv("AMAZON_ASSOCIATE_TAG", "myaffiliate-20")
    AMAZON_COUNTRY: str = os.getenv("AMAZON_COUNTRY", "com")
    
    # Optional PA-API 5.0
    AMAZON_ACCESS_KEY: str = os.getenv("AMAZON_ACCESS_KEY", "")
    AMAZON_SECRET_KEY: str = os.getenv("AMAZON_SECRET_KEY", "")

    # WordPress
    WORDPRESS_URL: str = os.getenv("WORDPRESS_URL", "").rstrip("/")
    WORDPRESS_USERNAME: str = os.getenv("WORDPRESS_USERNAME", "")
    WORDPRESS_APP_PASSWORD: str = os.getenv("WORDPRESS_APP_PASSWORD", "")
    WORDPRESS_DEFAULT_STATUS: str = os.getenv("WORDPRESS_DEFAULT_STATUS", "draft")

settings = Settings()
try:
    os.makedirs(settings.DATA_DIR, exist_ok=True)
except Exception:
    pass

