"""AWS Bedrock provider implementation."""

import boto3
from reportagent.config import get_settings


class BedrockProvider:
    """Llama 3 via AWS Bedrock."""

    def __init__(self):
        settings = get_settings()
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_default_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        self.model_id = "meta.llama3-70b-instruct-v1:0"

    def invoke(self, messages: list[dict], max_tokens: int = 1000) -> str:
        """Synchronously invoke Llama 3 via Bedrock Converse API."""
        # Convert message format: if content is a string, wrap it as list
        formatted_messages = []
        for msg in messages:
            content = msg["content"]
            if isinstance(content, str):
                content = [{"text": content}]
            formatted_messages.append({
                "role": msg["role"],
                "content": content,
            })

        response = self.client.converse(
            modelId=self.model_id,
            messages=formatted_messages,
            inferenceConfig={
                "maxTokens": max_tokens,
                "temperature": 0.5,
                "topP": 0.9,
            },
        )
        return response["output"]["message"]["content"][0]["text"]

    async def ainvoke(self, messages: list[dict], max_tokens: int = 1000) -> str:
        """Asynchronously invoke Llama 3 via Bedrock."""
        return self.invoke(messages, max_tokens)
