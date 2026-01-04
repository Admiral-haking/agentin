from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
PROMPTS_DIR = ROOT_DIR / "app" / "prompts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
    )

    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str

    DIRECTAM_BASE_URL: str = Field(
        validation_alias=AliasChoices("DIRECTAM_BASE_URL", "SERVICE_BASE_URL")
    )
    SERVICE_API_KEY: str
    DIRECTAM_SEND_PREFIX: str = ""
    DIRECTAM_CONTACTS_PATH: str | None = None
    DIRECTAM_CONTACTS_METHOD: str = "GET"
    DIRECTAM_CONTACTS_BODY: str | None = None
    DIRECTAM_CONTACTS_DATA_PATH: str | None = None
    DIRECTAM_CONTACTS_ID_FIELD: str | None = None
    DIRECTAM_CONTACTS_USERNAME_FIELD: str | None = None
    DIRECTAM_CONTACTS_FOLLOW_STATUS_FIELD: str | None = None
    DIRECTAM_CONTACTS_FOLLOWER_COUNT_FIELD: str | None = None

    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"

    DEEPSEEK_API_KEY: str | None = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    LLM_MODE: str = "hybrid"
    DEFAULT_LANGUAGE: str = "fa"
    MAX_HISTORY_MESSAGES: int = 20
    MAX_RESPONSE_CHARS: int = 800
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 700
    LLM_TIMEOUT_SEC: float = 15.0
    LLM_MAX_PROMPT_CHARS: int = 12000
    LLM_MESSAGE_MAX_CHARS: int = 1200
    LLM_MAX_USER_TURNS: int = 6
    WINDOW_HOURS: int = 24
    REQUEST_TIMEOUT_SEC: float = 20.0

    WEBHOOK_SECRET: str | None = None

    MAX_QUICK_REPLIES: int = 13
    MAX_BUTTONS: int = 3
    MAX_TEMPLATE_SLIDES: int = 10
    QUICK_REPLY_TITLE_MAX_CHARS: int = 20
    QUICK_REPLY_PAYLOAD_MAX_CHARS: int = 20

    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    ADMIN_UI_ORIGINS: str = ""
    LOGIN_RATE_LIMIT_WINDOW_SEC: int = 300
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = 5

    PRODUCTS_FEATURE_ENABLED: bool = False
    TOROB_PRODUCTS_URL: str = "https://ghlbedovom.com/api/torob/products"
    SITEMAP_URL: str = "https://ghlbedovom.com/sitemap.xml"
    PRODUCT_SYNC_CACHE_TTL_SEC: int = 300
    PRODUCT_SYNC_TIMEOUT_SEC: float = 15.0
    PRODUCT_SYNC_RETRIES: int = 2
    PRODUCT_SCRAPE_ENABLED: bool = True
    PRODUCT_SCRAPE_CONCURRENCY: int = 2
    PRODUCT_SCRAPE_DELAY_SEC: float = 0.3
    PRODUCT_SCRAPE_MAX: int = 50
    PRODUCT_MATCH_LIMIT: int = 5
    PRODUCT_MATCH_CANDIDATES: int = 50
    PRODUCT_MATCH_MIN_SCORE: int = 2
    PRODUCT_MATCH_SINGLE_TOKEN_MIN_LEN: int = 5
    PRODUCT_MATCH_QUERY_TERMS: int = 14
    PRODUCT_CATALOG_TTL_SEC: int = 0
    PRODUCT_CATALOG_RECENT_COUNT: int = 5
    PRODUCT_CATALOG_TOP_CATEGORIES: int = 5
    RESPONSE_LOG_CONTEXT_LIMIT: int = 3
    ORDER_FORM_ENABLED: bool = True
    ORDER_FORM_TTL_MIN: int = 30
    MEDIA_PROXY_BASE_URL: str = ""
    MEDIA_PROXY_ALLOWED_HOSTS: str = "ghlbedovom.com"
    MEDIA_PROXY_TIMEOUT_SEC: float = 12.0
    MEDIA_PROXY_MAX_BYTES: int = 10_000_000


settings = Settings()
