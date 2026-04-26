from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "PlacamIA API")
    DATABASE_URL: str = os.getenv("DATABASE_URL")


settings = Settings()
