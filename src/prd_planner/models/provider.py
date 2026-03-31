from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Protocol

import httpx


class ModelAdapter(Protocol):
    def complete(self, prompt: str) -> str:
        ...


@dataclass
class DeterministicAdapter:
    name: str = "deterministic"

    def complete(self, prompt: str) -> str:
        return f"[{self.name}] {prompt[:400]}"


@dataclass
class OllamaAdapter:
    model: str
    base_url: str = "http://localhost:11434"
    timeout_s: float = 1.5
    think: bool = False
    num_predict: int = 256

    def complete(self, prompt: str) -> str:
        url = f"{self.base_url.rstrip('/')}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "think": self.think,
            "options": {"num_predict": self.num_predict},
        }
        try:
            response = httpx.post(url, json=payload, timeout=self.timeout_s)
            response.raise_for_status()
            data = response.json()
            return str(data.get("response") or "").strip() or f"[ollama:{self.model}] {prompt[:200]}"
        except Exception:
            # Keep PoC resilient if Ollama is not running.
            return f"[ollama-fallback:{self.model}] {prompt[:200]}"


@dataclass
class OpenAIAdapter:
    model: str
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    timeout_s: float = 5.0

    def complete(self, prompt: str) -> str:
        if not self.api_key:
            return f"[openai-fallback:{self.model}] {prompt[:200]}"
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a planning assistant."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            response = httpx.post(url, content=json.dumps(body), headers=headers, timeout=self.timeout_s)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception:
            return f"[openai-fallback:{self.model}] {prompt[:200]}"


@dataclass
class LLMManager:
    provider: str = "ollama"
    ollama_model: str = "llama3.1:8b"
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout_s: float = 300.0
    ollama_think: bool = False
    ollama_num_predict: int = 256
    openai_model: str = "gpt-4o-mini"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    def adapter_for(self, role: str, override: str | None = None) -> ModelAdapter:
        provider = (override or self.provider).lower()
        if provider == "ollama":
            return OllamaAdapter(
                model=self.ollama_model,
                base_url=self.ollama_base_url,
                timeout_s=self.ollama_timeout_s,
                think=self.ollama_think,
                num_predict=self.ollama_num_predict,
            )
        if provider == "openai":
            return OpenAIAdapter(
                model=self.openai_model,
                api_key=self.openai_api_key,
                base_url=self.openai_base_url,
            )
        return DeterministicAdapter(name=f"deterministic:{role}")

    def complete(self, role: str, prompt: str, provider_override: str | None = None) -> str:
        return self.adapter_for(role=role, override=provider_override).complete(prompt)


class ModelRegistry:
    """Backwards-compatible wrapper used by orchestrator."""

    def __init__(
        self,
        profile: str = "default",
        manager: LLMManager | None = None,
    ) -> None:
        self.profile = profile
        self.manager = manager or LLMManager(
            provider=os.getenv("LLM_PROVIDER", "ollama"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_timeout_s=float(os.getenv("OLLAMA_TIMEOUT_S", "300")),
            ollama_think=os.getenv("OLLAMA_THINK", "false").lower() == "true",
            ollama_num_predict=int(os.getenv("OLLAMA_NUM_PREDICT", "256")),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )

    def get(self, role: str, override: str | None = None) -> ModelAdapter:
        return self.manager.adapter_for(role=role, override=override)
