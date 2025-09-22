# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    ENV: str = "dev"
    CORS_ALLOW_ORIGINS: List[str] = ["*"]  # demo-friendly
    # Demo keys place-holders (wire later)
    TAVILY_API_KEY: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
