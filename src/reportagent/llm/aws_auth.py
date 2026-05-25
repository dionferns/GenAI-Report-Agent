"""AWS authentication helper for role assumption."""

import os
import boto3
from reportagent.config import get_settings


def get_aws_client(service_name: str = "bedrock-runtime"):
    """
    Get an AWS service client with proper credential handling.

    On ECS/Lambda: Credentials automatically come from the task/execution role via
    the metadata service. boto3 auto-discovers them; we just create a client.

    On local dev: Uses role assumption (if AWS_ROLE_ARN set) or direct keys.

    Usage:
        bedrock = get_aws_client("bedrock-runtime")
        s3 = get_aws_client("s3")
    """
    settings = get_settings()

    # On ECS Fargate or Lambda, credentials auto-discovered from task/execution role metadata
    is_aws = os.getenv("AWS_EXECUTION_ENV") or os.getenv("AWS_LAMBDA_FUNCTION_NAME") or os.getenv("ECS_CONTAINER_METADATA_URI")

    if is_aws:
        # Let boto3 auto-detect credentials from the task role
        return boto3.client(service_name, region_name=settings.aws_default_region)

    # Local dev: use role assumption or direct keys
    if settings.aws_role_arn:
        sts = boto3.client(
            "sts",
            region_name=settings.aws_default_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        assumed_role = sts.assume_role(
            RoleArn=settings.aws_role_arn,
            RoleSessionName="genai-report-agent-session",
        )
        credentials = assumed_role["Credentials"]

        return boto3.client(
            service_name,
            region_name=settings.aws_default_region,
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
        )

    # Fallback: direct keys (local dev without role assumption)
    return boto3.client(
        service_name,
        region_name=settings.aws_default_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )