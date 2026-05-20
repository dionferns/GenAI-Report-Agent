"""Configuration management using Pydantic settings."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # LLM Configuration
    llm_provider: str = "anthropic"  # "bedrock" or "anthropic"
    anthropic_api_key: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_default_region: str = "eu-west-2"

    # LangSmith Configuration
    langchain_api_key: str = ""
    langchain_tracing_v2: bool = True
    langchain_project: str = "data-reply-genai-agent"

    # Storage Configuration
    chroma_persist_dir: str = "./data/chroma"
    sqlite_db_path: str = "./data/archive.db"
    log_file: str = "./logs/agent.log"

    # Agent Configuration
    default_topic: str = "uk_ai_regulation"
    ingest_interval_minutes: int = 60
    max_urls_per_run: int = 15
    max_critic_iterations: int = 2

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Source map for topic-based URLs
SOURCE_MAP = {
    "uk_ai_regulation": [
        "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "https://www.gov.uk/search/news-and-communications.atom?keywords=artificial+intelligence",
        "https://www.gov.uk/search/news-and-communications.atom?keywords=ai+regulation",
    ]
}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
