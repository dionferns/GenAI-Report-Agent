"""AWS Bedrock Titan Embeddings provider."""

import json
from reportagent.llm.aws_auth import get_aws_client


class BedrockEmbedder:
    """AWS Bedrock Titan Embeddings."""

    def __init__(self):
        self.client = get_aws_client("bedrock-runtime")
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
