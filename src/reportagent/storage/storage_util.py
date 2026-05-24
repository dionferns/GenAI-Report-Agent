"""Conditional storage utilities for Lambda (S3) vs local dev (filesystem)."""

import os
import boto3
from pathlib import Path
from reportagent.config import get_settings
import structlog

log = structlog.get_logger()


def is_lambda() -> bool:
    """Check if running on AWS Lambda."""
    return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


def save_text_file(filename: str, content: str, subdir: str = "data") -> None:
    """
    Save text content to file or S3 depending on environment.

    Args:
        filename: Just the filename (e.g., "extracted_articles_123.md")
        content: File content as string
        subdir: Local subdirectory (e.g., "data", "logs"). Ignored on Lambda.
    """
    settings = get_settings()

    if is_lambda():
        # Save to S3
        s3_client = boto3.client("s3")
        key = f"{subdir}/{filename}"
        try:
            s3_client.put_object(
                Bucket=settings.s3_bucket_name,
                Key=key,
                Body=content.encode("utf-8"),
                ContentType="text/plain",
            )
            log.info("file_saved_to_s3", bucket=settings.s3_bucket_name, key=key, filename=filename)
        except Exception as e:
            log.error("failed_to_save_to_s3", filename=filename, error=str(e))
            raise
    else:
        # Save locally
        Path(subdir).mkdir(parents=True, exist_ok=True)
        filepath = Path(subdir) / filename
        filepath.write_text(content)
        log.info("file_saved_locally", path=str(filepath), filename=filename)
