"""Tests for AI providers."""

import pytest
from unittest.mock import MagicMock, patch

from gpr.providers.base import ProviderError
from gpr.providers.claude import ClaudeProvider
from gpr.providers.openai import OpenAIProvider
from gpr.providers.ollama import OllamaProvider
from gpr.providers import get_provider, PROVIDER_MAP


class TestClaudeProvider:
    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY"):
            ClaudeProvider()

    def test_init_with_explicit_key(self):
        provider = ClaudeProvider(api_key="test-key")
        assert provider.name.startswith("claude")

    def test_name_contains_model(self):
        provider = ClaudeProvider(api_key="test", model="claude-haiku-4-5-20251001")
        assert "claude-haiku-4-5-20251001" in provider.name

    @patch("httpx.post")
    def test_generate_success(self, mock_post):
        response = MagicMock()
        response.json.return_value = {
            "content": [{"text": "Generated PR description"}]
        }
        response.raise_for_status = MagicMock()
        mock_post.return_value = response

        provider = ClaudeProvider(api_key="test-key")
        result = provider.generate("system prompt", "user message")
        assert result == "Generated PR description"

    @patch("httpx.post")
    def test_generate_http_error(self, mock_post):
        import httpx
        response = MagicMock()
        response.status_code = 401
        response.text = "Unauthorized"
        mock_post.return_value = response
        mock_post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=response
        )

        provider = ClaudeProvider(api_key="bad-key")
        with pytest.raises(ProviderError, match="Claude API error"):
            provider.generate("system", "user")

    @patch("httpx.post")
    def test_generate_network_error(self, mock_post):
        import httpx
        mock_post.side_effect = httpx.RequestError("Connection refused")

        provider = ClaudeProvider(api_key="test-key")
        with pytest.raises(ProviderError, match="Network error"):
            provider.generate("system", "user")


class TestOpenAIProvider:
    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
            OpenAIProvider()

    def test_name_contains_model(self):
        provider = OpenAIProvider(api_key="test", model="gpt-4o")
        assert "gpt-4o" in provider.name

    @patch("httpx.post")
    def test_generate_success(self, mock_post):
        response = MagicMock()
        response.json.return_value = {
            "choices": [{"message": {"content": "OpenAI PR description"}}]
        }
        response.raise_for_status = MagicMock()
        mock_post.return_value = response

        provider = OpenAIProvider(api_key="test-key")
        result = provider.generate("system", "user")
        assert result == "OpenAI PR description"

    @patch("httpx.post")
    def test_generate_http_error(self, mock_post):
        import httpx
        response = MagicMock()
        response.status_code = 429
        response.text = "Rate limit exceeded"
        mock_post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429", request=MagicMock(), response=response
        )

        provider = OpenAIProvider(api_key="test-key")
        with pytest.raises(ProviderError):
            provider.generate("system", "user")


class TestOllamaProvider:
    def test_default_model(self):
        provider = OllamaProvider()
        assert "llama3.2" in provider.name

    def test_custom_model(self):
        provider = OllamaProvider(model="mistral")
        assert "mistral" in provider.name

    def test_name_format(self):
        provider = OllamaProvider(model="codellama")
        assert provider.name == "ollama (codellama)"

    @patch("httpx.post")
    def test_generate_success(self, mock_post):
        response = MagicMock()
        response.json.return_value = {
            "message": {"content": "Ollama PR description"}
        }
        response.raise_for_status = MagicMock()
        mock_post.return_value = response

        provider = OllamaProvider()
        result = provider.generate("system", "user")
        assert result == "Ollama PR description"

    @patch("httpx.post")
    def test_connect_error(self, mock_post):
        import httpx
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        provider = OllamaProvider()
        with pytest.raises(ProviderError, match="Cannot connect to Ollama"):
            provider.generate("system", "user")

    @patch("httpx.post")
    def test_uses_correct_url(self, mock_post):
        response = MagicMock()
        response.json.return_value = {"message": {"content": "ok"}}
        response.raise_for_status = MagicMock()
        mock_post.return_value = response

        provider = OllamaProvider(host="http://custom-host:11434")
        provider.generate("system", "user")
        call_url = mock_post.call_args[0][0]
        assert "custom-host:11434" in call_url


class TestGetProvider:
    def test_returns_claude_provider(self):
        provider = get_provider("claude", api_key="test-key")
        assert isinstance(provider, ClaudeProvider)

    def test_returns_openai_provider(self):
        provider = get_provider("openai", api_key="test-key")
        assert isinstance(provider, OpenAIProvider)

    def test_returns_ollama_provider(self):
        provider = get_provider("ollama")
        assert isinstance(provider, OllamaProvider)

    def test_raises_for_unknown_provider(self):
        with pytest.raises(ProviderError, match="Unknown provider"):
            get_provider("unknown-ai")

    def test_all_providers_in_map(self):
        assert "claude" in PROVIDER_MAP
        assert "openai" in PROVIDER_MAP
        assert "ollama" in PROVIDER_MAP
