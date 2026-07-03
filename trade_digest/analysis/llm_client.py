import json
import os
from typing import Protocol

import requests

_JSON_INSTRUCTION = "\n\nRespond with a single valid JSON object only, no other text, no markdown code fences."


class LLMClient(Protocol):
    def generate(self, system_prompt: str, payload: dict) -> dict: ...


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def generate(self, system_prompt: str, payload: dict) -> dict:
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt + _JSON_INSTRUCTION},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
            },
            timeout=60,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)


class AnthropicClient:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def generate(self, system_prompt: str, payload: dict) -> dict:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 2048,
                "system": system_prompt + _JSON_INSTRUCTION,
                "messages": [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            },
            timeout=60,
        )
        response.raise_for_status()
        content = response.json()["content"][0]["text"]
        return json.loads(content)


def get_llm_client() -> LLMClient:
    provider = os.environ.get("LLM_PROVIDER", "openai")
    api_key = os.environ["LLM_API_KEY"]
    model = os.environ.get("LLM_MODEL") or ("claude-sonnet-5" if provider == "anthropic" else "gpt-4o-mini")
    if provider == "anthropic":
        return AnthropicClient(api_key=api_key, model=model)
    base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
    return OpenAICompatibleClient(base_url=base_url, api_key=api_key, model=model)
