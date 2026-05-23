"""AWS authentication helper for role assumption."""

import boto3
from reportagent.config import get_settings


def get_aws_client(service_name: str = "bedrock-runtime"):
    """
    Get an AWS service client with proper credential handling.

    Priority:
    1. If AWS_SESSION_TOKEN is set (from assume-role), use it directly
    2. If AWS_ROLE_ARN is set, call STS AssumeRole to get temporary credentials
    3. Otherwise, use IAM user credentials directly (fallback for local dev)

    Usage:
        bedrock = get_aws_client("bedrock-runtime")
        s3 = get_aws_client("s3")
    """
    settings = get_settings()

    # If session token is already provided (from assume-role), use it directly
    if settings.aws_session_token:
        return boto3.client(
            service_name,
            region_name=settings.aws_default_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            aws_session_token=settings.aws_session_token,
        )

    # If role ARN is set, assume it to get temporary credentials
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

    # Fallback: use access keys directly (for local dev without role)
    return boto3.client(
        service_name,
        region_name=settings.aws_default_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )