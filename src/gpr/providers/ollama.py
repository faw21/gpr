"""Ollama local LLM provider."""

from __future__ import annotations

import httpx

from .base import BaseProvider, ProviderError

DEFAULT_MODEL = "llama3.2"
DEFAULT_HOST = "http://localhost:11434"


class OllamaProvider(BaseProvider):
    """Provider using local Ollama server (no API key required)."""

    def __init__(self, model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST):
        self._model = model
        self._host = host.rstrip("/")

    @property
    def name(self) -> str:
        return f"ollama ({self._model})"

    def generate(self, system: str, user: str) -> str:
        url = f"{self._host}/api/chat"
        try:
            response = httpx.post(
                url,
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.3},
                },
                timeout=120.0,  # Local models can be slow
            )
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]
        except httpx.ConnectError as e:
            raise ProviderError(
                f"Cannot connect to Ollama at {self._host}. "
                "Make sure Ollama is running: https://ollama.ai"
            ) from e
        except httpx.HTTPStatusError as e:
            body = e.response.text
            raise ProviderError(f"Ollama error {e.response.status_code}: {body}") from e
        except httpx.RequestError as e:
            raise ProviderError(f"Network error calling Ollama: {e}") from e
        except (KeyError, IndexError) as e:
            raise ProviderError(f"Unexpected Ollama response format: {e}") from e
