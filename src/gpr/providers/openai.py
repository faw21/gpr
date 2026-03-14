"""OpenAI provider."""

from __future__ import annotations

import os

import httpx

from .base import BaseProvider, ProviderError

DEFAULT_MODEL = "gpt-4o-mini"
API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(BaseProvider):
    """Provider using OpenAI API."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None):
        self._model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise ProviderError(
                "OPENAI_API_KEY environment variable not set. "
                "Get your key at https://platform.openai.com/api-keys"
            )

    @property
    def name(self) -> str:
        return f"openai ({self._model})"

    def generate(self, system: str, user: str) -> str:
        try:
            response = httpx.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_completion_tokens": 1024,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            body = e.response.text
            raise ProviderError(f"OpenAI API error {e.response.status_code}: {body}") from e
        except httpx.RequestError as e:
            raise ProviderError(f"Network error calling OpenAI API: {e}") from e
        except (KeyError, IndexError) as e:
            raise ProviderError(f"Unexpected OpenAI API response format: {e}") from e
