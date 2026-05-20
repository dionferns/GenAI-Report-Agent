"""LLM provider implementations."""

from reportagent.config import get_settings


def get_llm_provider():
    """Factory function to get the configured LLM provider."""
    settings = get_settings()
    if settings.llm_provider == "bedrock":
        from reportagent.llm.bedrock import BedrockProvider
        return BedrockProvider()
    else:
        from reportagent.llm.anthropic_direct import AnthropicDirectProvider
        return AnthropicDirectProvider()
