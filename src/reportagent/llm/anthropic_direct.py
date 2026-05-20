"""Anthropic direct API provider implementation."""

import anthropic
from reportagent.config import get_settings


class AnthropicDirectProvider:
    """Claude via direct Anthropic API."""

    def __init__(self):
        settings = get_settings()
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-3-5-sonnet-20241022"

    def invoke(self, messages: list[dict], max_tokens: int = 1000) -> str:
        """Synchronously invoke Claude."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages,
        )
        return response.content[0].text

    async def ainvoke(self, messages: list[dict], max_tokens: int = 1000) -> str:
        """Asynchronously invoke Claude."""
        async with anthropic.AsyncAnthropic(
            api_key=get_settings().anthropic_api_key
        ) as client:
            response = await client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=messages,
            )
            return response.content[0].text
