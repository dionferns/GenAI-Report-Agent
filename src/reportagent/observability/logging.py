"""Structured logging configuration using structlog."""

import structlog
from pathlib import Path
from reportagent.config import get_settings


def setup_logging() -> None:
    """Configure structlog for JSON logging to stdout and file."""
    settings = get_settings()

    # Create log directory
    Path(settings.log_file).parent.mkdir(parents=True, exist_ok=True)

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure file logging
    file_handler = open(settings.log_file, "a", encoding="utf-8")

    def file_logger_factory():
        return structlog.PrintLogger(file=file_handler)

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def get_logger():
    """Get a structlog logger instance."""
    return structlog.get_logger()
