"""Real LLM integration tests — calls actual APIs, not mocks.

Run with: pytest tests/test_integration_llm.py -v -s
Uses small/cheap models to save cost.
"""

from __future__ import annotations

import os
import pytest
from dotenv import load_dotenv

load_dotenv("/Users/aaronwu/Local/my-projects/give-it-all/.env")

from gpr.providers.claude import ClaudeProvider
from gpr.providers.openai import OpenAIProvider
from gpr.providers.ollama import OllamaProvider


SYSTEM = "You are a helpful assistant. Keep responses very short."
USER = "Say exactly: 'LLM test OK'"

has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
has_openai = bool(os.environ.get("OPENAI_API_KEY"))


# ── Claude ───────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not has_anthropic, reason="ANTHROPIC_API_KEY not set")
def test_claude_real_generate():
    """Real call to Anthropic claude-haiku-4-5."""
    provider = ClaudeProvider(model="claude-haiku-4-5-20251001")
    result = provider.generate(SYSTEM, USER)
    assert isinstance(result, str)
    assert len(result) > 0
    print(f"\n[Claude] response: {result!r}")


# ── OpenAI ───────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not has_openai, reason="OPENAI_API_KEY not set")
def test_openai_real_generate():
    """Real call to OpenAI gpt-5-nano."""
    provider = OpenAIProvider(model="gpt-5-nano")
    result = provider.generate(SYSTEM, USER)
    assert isinstance(result, str)
    assert len(result) > 0
    print(f"\n[OpenAI] response: {result!r}")


# ── Ollama ───────────────────────────────────────────────────────────────────

def test_ollama_real_generate():
    """Real call to local Ollama qwen2.5:1.5b."""
    provider = OllamaProvider(model="qwen2.5:1.5b")
    result = provider.generate(SYSTEM, USER)
    assert isinstance(result, str)
    assert len(result) > 0
    print(f"\n[Ollama] response: {result!r}")
