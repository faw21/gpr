"""AI providers for PR generation."""

from .base import BaseProvider, ProviderError
from .claude import ClaudeProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider

__all__ = [
    "BaseProvider",
    "ProviderError",
    "ClaudeProvider",
    "OllamaProvider",
    "OpenAIProvider",
]

PROVIDER_MAP: dict[str, type[BaseProvider]] = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
}


def get_provider(name: str, **kwargs) -> BaseProvider:
    """Get a provider by name."""
    if name not in PROVIDER_MAP:
        valid = ", ".join(PROVIDER_MAP.keys())
        raise ProviderError(f"Unknown provider '{name}'. Valid providers: {valid}")
    return PROVIDER_MAP[name](**kwargs)
