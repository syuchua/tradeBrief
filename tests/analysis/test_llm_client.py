import os
from unittest.mock import patch, MagicMock

import pytest

from trade_digest.analysis.llm_client import OpenAICompatibleClient, AnthropicClient, get_llm_client


def test_openai_compatible_client_parses_json_content():
    fake_response = MagicMock()
    fake_response.json.return_value = {"choices": [{"message": {"content": '{"market_summary": "ok"}'}}]}
    fake_response.raise_for_status.return_value = None
    client = OpenAICompatibleClient(base_url="https://api.example.com/v1", api_key="key", model="gpt-test")

    with patch("trade_digest.analysis.llm_client.requests.post", return_value=fake_response) as mock_post:
        result = client.generate("system prompt", {"foo": "bar"})

    assert result == {"market_summary": "ok"}
    called_url = mock_post.call_args.args[0]
    assert called_url == "https://api.example.com/v1/chat/completions"


def test_anthropic_client_parses_json_content():
    fake_response = MagicMock()
    fake_response.json.return_value = {"content": [{"text": '{"market_summary": "ok"}'}]}
    fake_response.raise_for_status.return_value = None
    client = AnthropicClient(api_key="key", model="claude-test")

    with patch("trade_digest.analysis.llm_client.requests.post", return_value=fake_response) as mock_post:
        result = client.generate("system prompt", {"foo": "bar"})

    assert result == {"market_summary": "ok"}
    called_url = mock_post.call_args.args[0]
    assert called_url == "https://api.anthropic.com/v1/messages"


def test_get_llm_client_returns_anthropic_when_configured():
    env = {"LLM_PROVIDER": "anthropic", "LLM_API_KEY": "key", "LLM_MODEL": "claude-test"}
    with patch.dict(os.environ, env, clear=True):
        client = get_llm_client()
    assert isinstance(client, AnthropicClient)


def test_get_llm_client_defaults_to_openai_compatible():
    env = {"LLM_API_KEY": "key"}
    with patch.dict(os.environ, env, clear=True):
        client = get_llm_client()
    assert isinstance(client, OpenAICompatibleClient)
