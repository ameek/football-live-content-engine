from enum import Enum
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderType(str, Enum):
    LIVE = "live"
    SPORTSDB = "sportsdb"
    MOCK = "mock"


class TargetPlatform(str, Enum):
    FACEBOOK = "facebook"
    TWITTER = "twitter"
    TELEGRAM = "telegram"


class Settings(BaseSettings):
    # Ingestion & Polling
    provider_type: ProviderType = ProviderType.LIVE
    poll_interval_seconds: int = 15
    request_timeout_seconds: float = 10.0

    # API Server
    host: str = "0.0.0.0"
    port: int = 8000

    # AI Content Generator
    default_platform: TargetPlatform = TargetPlatform.FACEBOOK
    openai_api_key: str = ""
    gemini_api_key: str = ""
    ai_model_name: str = "gpt-4o-mini"
    enable_auto_publish: bool = False

    # Security & Access Control
    desk_security_pin: str = "2026"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FOOTBALL_",
        extra="ignore"
    )


settings = Settings()
