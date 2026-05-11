from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    github_token: str | None = os.getenv("GITHUB_TOKEN")
    groq_api_key: str | None = os.getenv("GROQ_API_KEY")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    gmail_user: str | None = os.getenv("GMAIL_USER")
    gmail_app_password: str | None = os.getenv("GMAIL_APP_PASSWORD")
    recipient_email: str | None = os.getenv("RECIPIENT_EMAIL")
    sqlite_path: Path = Path(os.getenv("SQLITE_PATH", "data/goodfirstfindr.db"))
    digest_enabled: bool = _get_bool("DIGEST_ENABLED", True)
    digest_keyword: str = os.getenv("DIGEST_KEYWORD", "python machine learning")
    digest_time: str = os.getenv("DIGEST_TIME", "08:00")
    digest_timezone: str = os.getenv("DIGEST_TIMEZONE", "America/Phoenix")
    github_timeout_seconds: float = _get_float("GITHUB_TIMEOUT_SECONDS", 15.0)
    groq_timeout_seconds: float = _get_float("GROQ_TIMEOUT_SECONDS", 20.0)
    github_candidate_limit: int = _get_int("GITHUB_CANDIDATE_LIMIT", 40)


settings = Settings()
