"""minimax_runtime.py — a MiniMax `set_runtime` backend (the example instance).

A PLAIN runtime, NOT a Link: cave's `set_runtime` takes any object with `.run(str) -> str`.
Modeled on onionmorph's OMRuntime (the proven heaven path):

  provider = ANTHROPIC + model = "MiniMax-M2.7-highspeed"  → heaven auto-routes the MiniMax
  anthropic-compatible URL and reads MINIMAX_API_KEY (auto-sourced from ~/system_config.sh).
  MiniMax is NOT its own provider — the MODEL NAME selects it inside provider=ANTHROPIC.

This is the CORRECTED path. The old `HeavenMiniMaxLink` was wrong: it read model + anthropic_api_url
from conductor_agent_config.json (NOT heaven's config), never set provider, and claimed no API key
was needed. Don't revive it — this replaces it.

heaven is imported lazily (container-only), so importing cave_teams stays host-safe.
"""
from __future__ import annotations

import os
from typing import List, Optional

DEFAULT_MODEL = "MiniMax-M2.7-highspeed"


class MiniMaxRuntime:
    """A MiniMax agent backend for cave's `set_runtime`. `.run(prompt) -> str`.

    Holds a heaven `history_id` so repeated turns continue one conversation (per-agent memory).
    tools=None → a coding toolset (BashTool + NetworkEditTool); tools=[] → no tools (pure chat).
    """

    def __init__(self, name: str = "agent", system_prompt: str = "", model: Optional[str] = None,
                 tools: Optional[List] = None, max_tokens: int = 8000, max_tool_calls: int = 99,
                 temperature: float = 0.7):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model or os.environ.get("CAVE_MINIMAX_MODEL") or DEFAULT_MODEL
        self._tools = tools
        self.max_tokens = max_tokens
        self.max_tool_calls = max_tool_calls
        self.temperature = temperature
        self.history_id: Optional[str] = None
        self._config = None

    def _build_config(self):
        from heaven_base.baseheavenagent import HeavenAgentConfig
        from heaven_base.unified_chat import ProviderEnum
        if self._tools is None:
            from heaven_base.tools.bash_tool import BashTool
            from heaven_base.tools.network_edit_tool import NetworkEditTool
            tools = [BashTool, NetworkEditTool]
        else:
            tools = self._tools
        return HeavenAgentConfig(
            name=self.name,
            system_prompt=self.system_prompt,
            tools=tools,
            provider=ProviderEnum.ANTHROPIC,   # MiniMax runs through ANTHROPIC, selected by model name
            model=self.model,
            use_uni_api=False,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

    async def run(self, prompt: str) -> str:
        from heaven_base.baseheavenagent import BaseHeavenAgent
        from heaven_base.unified_chat import UnifiedChat
        from heaven_base.docs.examples.heaven_callbacks import (
            BackgroundEventCapture, CompositeCallback,
        )
        if self._config is None:
            self._config = self._build_config()
        kwargs = dict(config=self._config, unified_chat=UnifiedChat(), max_tool_calls=self.max_tool_calls)
        if self.history_id:
            kwargs["history_id"] = self.history_id
        agent = BaseHeavenAgent(**kwargs)

        capture = BackgroundEventCapture()
        result = await agent.run(prompt, heaven_main_callback=CompositeCallback([capture]))

        if isinstance(result, dict) and result.get("history_id"):
            self.history_id = result["history_id"]
        msgs = capture.get_events_by_type("AGENT_MESSAGE")
        return (msgs[-1].get("data", {}).get("content", "") or "") if msgs else ""

    def reset(self) -> None:
        """Drop history — start a fresh conversation."""
        self.history_id = None
