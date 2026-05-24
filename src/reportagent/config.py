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
    aws_role_arn: str = ""  # For assuming role, if using IAM user
    aws_session_token: str = ""  # Auto-injected on Lambda/App Runner, leave blank for local dev

    # LangSmith Configuration
    langchain_api_key: str = ""
    langchain_tracing_v2: bool = True
    langchain_project: str = "data-reply-genai-agent"

    # Storage Configuration
    chroma_persist_dir: str = "./data/chroma"
    sqlite_db_path: str = "./data/archive.db"
    log_file: str = "./logs/agent.log"

    # Agent Configuration
    default_topic: str = "uk_economy"
    ingest_interval_minutes: int = 60
    max_urls_per_run: int = 10
    max_articles_per_run: int = 10
    max_critic_iterations: int = 2
    max_empty_batches: int = 3

    # S3 Storage Configuration
    s3_bucket_name: str = "genai-report-agent"
    use_s3_archive: bool = False  # False locally, True on Lambda/AppRunner

    # OpenSearch Serverless
    opensearch_endpoint: str = ""
    vector_store_provider: str = "chroma"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Source map for topic-based URLs
SOURCE_MAP = {
    "uk_economy": [
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://feeds.bbci.co.uk/news/business/companies/rss.xml",
        "https://feeds.bbci.co.uk/news/uk/rss.xml",
    ]
    # "uk_ai_regulation": [
    #     "https://feeds.bbci.co.uk/news/technology/rss.xml",
    #     "https://feeds.bbci.co.uk/news/business/rss.xml",
    #     "https://www.gov.uk/search/news-and-communications.atom?keywords=artificial+intelligence",
    #     "https://www.gov.uk/search/news-and-communications.atom?keywords=ai+regulation",
    # ]
    # "sports": [
    #     "https://feeds.bbci.co.uk/news/sport/rss.xml",
    #     "https://feeds.bbci.co.uk/sport/football/rss.xml",
    #     "https://feeds.bbci.co.uk/sport/cricket/rss.xml",
    # ]
}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
