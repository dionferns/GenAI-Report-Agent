"""AWS Bedrock provider implementation."""

from reportagent.llm.aws_auth import get_aws_client


class BedrockProvider:
    """Llama 3 via AWS Bedrock."""

    def __init__(self):
        self.client = get_aws_client("bedrock-runtime")
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
