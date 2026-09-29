import os
from pathlib import Path

from dotenv import load_dotenv


def parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "on"}


BACKEND_DIR = Path(__file__).parent
PROJECT_PATH = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = ENVIRONMENT != "production"
TESTING_MODE = parse_bool(os.getenv("TESTING_MODE", "false"))

SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY")
if not SESSION_SECRET_KEY:  # pragma: no cover
    raise ValueError("SESSION_SECRET_KEY must be set")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./smallfolk.db",
)
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5341")
API_PREFIX = os.getenv("API_PREFIX", "/api")
API_URL = os.getenv("API_URL", f"{BASE_URL}{API_PREFIX}")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", BASE_URL)
SITE_NAME = os.getenv("SITE_NAME", "SmallFolks")
SESSION_MAX_AGE_SECONDS = int(
    os.getenv("SESSION_MAX_AGE_SECONDS", str(60 * 60 * 24 * 30))
)
MAGIC_LOGIN_COOLDOWN_SECONDS = int(os.getenv("MAGIC_LOGIN_COOLDOWN_SECONDS", "120"))
MAGIC_LOGIN_MAX_AGE_SECONDS = int(
    os.getenv("MAGIC_LOGIN_MAX_AGE_SECONDS", str(60 * 15))
)
EMAIL_VERIFICATION_COOLDOWN_SECONDS = int(
    os.getenv("EMAIL_VERIFICATION_COOLDOWN_SECONDS", "120")
)
EMAIL_VERIFICATION_MAX_AGE_SECONDS = int(
    os.getenv("EMAIL_VERIFICATION_MAX_AGE_SECONDS", str(60 * 60 * 24))
)
PASSWORD_RESET_COOLDOWN_SECONDS = int(
    os.getenv("PASSWORD_RESET_COOLDOWN_SECONDS", "120")
)
PASSWORD_RESET_MAX_AGE_SECONDS = int(
    os.getenv("PASSWORD_RESET_MAX_AGE_SECONDS", str(60 * 30))
)
DIST_DIR = Path(os.getenv("DIST_DIR", PROJECT_PATH / "frontend" / "dist"))
ENABLE_HTML_SERVING = parse_bool(
    os.getenv("ENABLE_HTML_SERVING", "false" if TESTING_MODE else "true")
)
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_USE_TLS = parse_bool(os.getenv("SMTP_USE_TLS", "true"))
SMTP_USE_SSL = parse_bool(os.getenv("SMTP_USE_SSL", "false"))
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", SITE_NAME)
SMTP_TIMEOUT_SECONDS = float(os.getenv("SMTP_TIMEOUT_SECONDS", "20"))
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GA_MEASUREMENT_ID = os.getenv("GA_MEASUREMENT_ID", "")
EMAIL_DELIVERY_ENABLED = parse_bool(
    os.getenv(
        "EMAIL_DELIVERY_ENABLED",
        "true" if SMTP_HOST and SMTP_FROM_EMAIL else "false",
    )
)
