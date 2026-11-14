import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

# Auto-create .env from .env.example if missing
if not ENV_PATH.exists():
    try:
        example_path = BASE_DIR / ".env.example"
        if example_path.exists():
            ENV_PATH.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            ENV_PATH.write_text("GEMINI_API_KEY=\nGEMINI_MODEL=gemini-3.8-flash\n", encoding="utf-8")
    except Exception:
        pass

class Settings:
    # App
    APP_NAME: str = "HITL Content Autopilot"
    APP_VERSION: str = "1.0.0"
    DATA_DIR: Path = BASE_DIR / "data"

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
        db_amazon_tag = get_setting("AMAZON_ASSOCIATE_TAG", "")
        db_amazon_country = get_setting("AMAZON_COUNTRY", "")
        db_amazon_access = get_setting("AMAZON_ACCESS_KEY", "")
        db_amazon_secret = get_setting("AMAZON_SECRET_KEY", "")
        db_wp_url = get_setting("WORDPRESS_URL", "")
        db_wp_user = get_setting("WORDPRESS_USERNAME", "")
        db_wp_pass = get_setting("WORDPRESS_APP_PASSWORD", "")
        db_wp_status = get_setting("WORDPRESS_DEFAULT_STATUS", "")
        db_timeout = get_setting("GEMINI_TIMEOUT_SECONDS", "60")

        self.GEMINI_API_KEY = db_gemini_key or os.getenv("GEMINI_API_KEY", "").strip()
        self.GEMINI_MODEL = db_gemini_model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
        self.AMAZON_ASSOCIATE_TAG = db_amazon_tag or os.getenv("AMAZON_ASSOCIATE_TAG", "myaffiliate-20").strip()
        self.AMAZON_COUNTRY = db_amazon_country or os.getenv("AMAZON_COUNTRY", "com").strip()
        self.AMAZON_ACCESS_KEY = db_amazon_access or os.getenv("AMAZON_ACCESS_KEY", "").strip()
        self.AMAZON_SECRET_KEY = db_amazon_secret or os.getenv("AMAZON_SECRET_KEY", "").strip()
        self.WORDPRESS_URL = db_wp_url or os.getenv("WORDPRESS_URL", "").strip().rstrip("/")
        self.WORDPRESS_USERNAME = db_wp_user or os.getenv("WORDPRESS_USERNAME", "").strip()
        self.WORDPRESS_APP_PASSWORD = db_wp_pass or os.getenv("WORDPRESS_APP_PASSWORD", "").strip()
        self.WORDPRESS_DEFAULT_STATUS = db_wp_status or os.getenv("WORDPRESS_DEFAULT_STATUS", "draft").strip()
        try:
            self.GEMINI_TIMEOUT = int(db_timeout)
        except ValueError:
            self.GEMINI_TIMEOUT = 60

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

    def save(
        self,
        gemini_api_key: str = None,
        gemini_model: str = None,
        amazon_associate_tag: str = None,
        amazon_country: str = None,
        amazon_access_key: str = None,
        amazon_secret_key: str = None,
        wordpress_url: str = None,
        wordpress_username: str = None,
        wordpress_app_password: str = None,
        wordpress_default_status: str = None,
        gemini_timeout: int = None
    ):
        from core.database import set_setting

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

        # Try to write to .env if permissions allow
        content = (
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
except Exception:
    pass
