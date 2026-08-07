"""The BARE MiniMax backend — the pyproject `minimax` extra, implemented.

pyproject.toml has declared this slot all along:

    # The bare MiniMax / Anthropic-compatible backend needs the anthropic client.
    minimax = ["anthropic>=0.40"]

This is that backend: `.run(prompt) -> str` on the anthropic client pointed at
MiniMax's Anthropic-compatible endpoint. NO tools, NO heaven — chat only (the
heaven backend remains the one for real tooled coding agents, per the
examples/__init__ docstring). Use it anywhere heaven isn't installed (CI,
containers, GitHub Actions): the runtime slot is polymorphic, so the SAME
worlds/teams/deities run on either backend unchanged.

Per-instance message history ⇒ one continuing conversation (like
MiniMaxRuntime's history_id). A FRESH session is simply a fresh instance —
which is exactly what a fresh-model test gate wants.
"""
from __future__ import annotations

import os
from typing import List, Optional

DEFAULT_MODEL = "MiniMax-M2.7-highspeed"
DEFAULT_BASE = "https://api.minimax.io/anthropic"


class BareMiniMaxRuntime:
    """`set_runtime` backend: `.run(prompt) -> str` (async), chat-only."""

    def __init__(self, name: str = "agent", system_prompt: str = "",
                 model: Optional[str] = None, max_tokens: int = 4000,
                 temperature: float = 0.7, base_url: Optional[str] = None):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model or os.environ.get("CAVE_MINIMAX_MODEL") or DEFAULT_MODEL
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.base_url = base_url or os.environ.get("MINIMAX_BASE_URL") or DEFAULT_BASE
        self.messages: List[dict] = []
        self._client = None

    def _ensure(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.AsyncAnthropic(
                api_key=os.environ["MINIMAX_API_KEY"], base_url=self.base_url)
        return self._client

    async def run(self, prompt: str) -> str:
        client = self._ensure()
        self.messages.append({"role": "user", "content": prompt})
        resp = await client.messages.create(
            model=self.model, max_tokens=self.max_tokens,
            temperature=self.temperature, system=self.system_prompt,
            messages=self.messages)
        text = "".join(b.text for b in resp.content
                       if getattr(b, "type", "text") == "text").strip()
        self.messages.append({"role": "assistant", "content": text})
        return text


__all__ = ["BareMiniMaxRuntime"]
