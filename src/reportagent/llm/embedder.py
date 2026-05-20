"""AWS Bedrock Titan Embeddings provider."""

import json
import boto3
from reportagent.config import get_settings


class BedrockEmbedder:
    """AWS Bedrock Titan Embeddings."""

    def __init__(self):
        settings = get_settings()
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_default_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        self.model_id = "amazon.titan-embed-text-v2:0"

    def encode(self, text: str) -> list[float]:
        """Encode text using Bedrock Titan."""
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps({"inputText": text}),
        )
        result = json.loads(response["body"].read())
        return result["embedding"]


def get_embedder() -> BedrockEmbedder:
    """Get Bedrock embedder instance."""
    return BedrockEmbedder()
