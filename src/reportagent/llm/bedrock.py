"""AWS Bedrock provider implementation."""

import json
import boto3
from reportagent.config import get_settings


class BedrockProvider:
    """Claude via AWS Bedrock."""

    def __init__(self):
        settings = get_settings()
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_default_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        # Use Claude 3 Haiku (cheapest option - 85% cost reduction)
        self.model_id = "anthropic.claude-3-haiku-20240307-v1:0"

    def invoke(self, messages: list[dict], max_tokens: int = 1000) -> str:
        """Synchronously invoke Claude via Bedrock."""
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": messages,
        })
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=body,
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]

    async def ainvoke(self, messages: list[dict], max_tokens: int = 1000) -> str:
        """Asynchronously invoke Claude via Bedrock."""
        # For async, we use the sync method in an executor
        # In production, use aioboto3
        return self.invoke(messages, max_tokens)
