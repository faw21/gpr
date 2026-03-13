"""Base provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ProviderError(Exception):
    """Raised when a provider encounters an error."""


class BaseProvider(ABC):
    """Abstract base for AI providers."""

    @abstractmethod
    def generate(self, system: str, user: str) -> str:
        """Generate text from system + user prompt.

        Args:
            system: System prompt
            user: User message

        Returns:
            Generated text

        Raises:
            ProviderError: If generation fails
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider display name."""
