"""Base protocol for LLM providers."""

from typing import Protocol


class LLMProvider(Protocol):
    """Protocol for LLM provider implementations."""

    def invoke(self, messages: list[dict], max_tokens: int = 1000) -> str:
        """Synchronously invoke the LLM with a list of messages."""
        ...

    async def ainvoke(self, messages: list[dict], max_tokens: int = 1000) -> str:
        """Asynchronously invoke the LLM with a list of messages."""
        ...
