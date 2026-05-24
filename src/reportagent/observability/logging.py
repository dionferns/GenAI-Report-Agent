"""Structured logging configuration using structlog."""

import os
import structlog
from pathlib import Path
from reportagent.config import get_settings


def setup_logging() -> None:
    """Configure structlog for JSON logging to stdout and file."""
    settings = get_settings()

    # On Lambda, skip file logging (filesystem is read-only except /tmp)
    # Lambda automatically captures stdout to CloudWatch Logs
    if not os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        # Create log directory (only on local/App Runner)
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


def get_logger():
    """Get a structlog logger instance."""
    return structlog.get_logger()
