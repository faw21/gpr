"""Anthropic Claude provider."""

from __future__ import annotations

import os

import httpx

from .base import BaseProvider, ProviderError

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class ClaudeProvider(BaseProvider):
    """Provider using Anthropic Claude API."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None):
        self._model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise ProviderError(
                "ANTHROPIC_API_KEY environment variable not set. "
                "Get your key at https://console.anthropic.com/"
            )

    @property
    def name(self) -> str:
        return f"claude ({self._model})"

    def generate(self, system: str, user: str) -> str:
        try:
            response = httpx.post(
                API_URL,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": 1024,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]
        except httpx.HTTPStatusError as e:
            body = e.response.text
            raise ProviderError(f"Claude API error {e.response.status_code}: {body}") from e
        except httpx.RequestError as e:
            raise ProviderError(f"Network error calling Claude API: {e}") from e
        except (KeyError, IndexError) as e:
            raise ProviderError(f"Unexpected Claude API response format: {e}") from e
