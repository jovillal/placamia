import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


def parse_bool(value: str | None, default: bool = False) -> bool:
    """Parse an environment-style boolean value.

    Args:
        value: Raw environment variable value to parse.
        default: Value returned when the environment variable is not set.

    Returns:
        True for common truthy strings, false for common falsy strings, or the
        provided default when the value is missing.

    Side effects:
        None.
    """
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    """Runtime settings loaded from environment variables.

    Settings are intentionally explicit so security-sensitive options, such as
    SQL logging, have safe defaults and are easy to audit.
    """

    def __init__(self) -> None:
        """Load application settings from the process environment.

        Args:
            None.

        Returns:
            None.

        Side effects:
            Reads environment variables already loaded from `apps/api/.env`.
        """
        self.APP_NAME: str = os.getenv("APP_NAME", "PlacamIA API")
        self.DATABASE_URL: str | None = os.getenv("DATABASE_URL")
        self.SQLALCHEMY_ECHO: bool = parse_bool(os.getenv("SQLALCHEMY_ECHO"))


settings = Settings()
