"""LangSmith tracing setup."""

import os
from reportagent.config import get_settings


def setup_tracing() -> None:
    """Configure LangSmith tracing if API key is available."""
    settings = get_settings()

    if settings.langchain_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = str(settings.langchain_tracing_v2).lower()
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
