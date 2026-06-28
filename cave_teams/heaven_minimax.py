"""heaven_minimax.py — a MiniMax agent as a cave-teams Link, via the heaven framework.

Mirrors onionmorph's OMRuntime / OMAgent (the proven in-environment MiniMax path, the same one
the Conductor uses): define a HeavenAgentConfig with `use_uni_api=False` +
`extra_model_kwargs={"anthropic_api_url": <minimax url>}` + `model=<minimax model>` read from
/tmp/heaven_data/conductor_agent_config.json, then run via
`BaseHeavenAgent(config, UnifiedChat(), history_id).run(msg, heaven_main_callback=BackgroundEventCapture)`
and take the last AGENT_MESSAGE. This is NOT the bare-anthropic MINIMAX_API_KEY path
(cave_teams.primitives.run_minimax) — in this environment heaven self-authenticates MiniMax, so no
MINIMAX_API_KEY in the env is needed.

heaven_base + cave are provided by the monorepo environment, so EVERY heaven import here is lazy
(inside methods): `import cave_teams` still works on the host with zero heaven dependency; a
HeavenMiniMaxLink only needs heaven at execute() time (i.e. where the heaven framework is available).

A HeavenMiniMaxLink IS a Link — it reads its input from the context and writes `output` /
`output:<name>` exactly like AgentLink, so it composes in the FULL algebra (>>, |, tournament,
gate) and nests like any other Link. Each link keeps its own heaven `history_id` → persistent
per-agent conversation (the cave-teams "agents remember everything" contract, heaven-side).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .chain_ontology import Link, LinkResult, LinkStatus
from .links import input_from_context

HEAVEN_DATA = Path(os.environ.get("HEAVEN_DATA_DIR", "/tmp/heaven_data"))


def minimax_coords(config_name: str = "conductor_agent_config.json") -> dict:
    """Read MiniMax coordinates the way onionmorph/conductor.py do (the shared config file)."""
    p = HEAVEN_DATA / config_name
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def default_tools() -> List:
    """The tools a cave-teams MiniMax agent gets BY DEFAULT — a real coding agent needs to run
    bash and edit files (mirrors onionmorph's OM agent). Lazy import (heaven is container-only)."""
    from heaven_base.tools.bash_tool import BashTool
    from heaven_base.tools.network_edit_tool import NetworkEditTool
    return [BashTool, NetworkEditTool]


def build_minimax_config(name: str, system_prompt: str, tools: Optional[List] = None,
                         max_tokens: Optional[int] = None):
    """Define a MiniMax heaven agent config — the onionmorph way (use_uni_api=False + anthropic_api_url).

    tools=None → the default coding toolset (BashTool + NetworkEditTool); tools=[] → no tools."""
    from heaven_base.baseheavenagent import HeavenAgentConfig

    cfg = minimax_coords()
    model = os.environ.get("CAVE_MINIMAX_MODEL") or cfg.get("model", "")
    url = cfg.get("extra_model_kwargs", {}).get("anthropic_api_url", "")
    mt = max_tokens or cfg.get("max_tokens", 8000)
    resolved_tools = default_tools() if tools is None else tools

    return HeavenAgentConfig(
        name=name,
        system_prompt=system_prompt,
        tools=resolved_tools,
        model=model,
        use_uni_api=False,
        max_tokens=mt,
        extra_model_kwargs={"anthropic_api_url": url},
    )


class HeavenMiniMaxLink(Link):
    """A MiniMax agent (run through the heaven framework) as a cave-teams leaf Link.

    Parallels AgentLink, but on the heaven runtime instead of the bare-anthropic backend.
    Holds its own `history_id` so repeated turns continue one conversation.
    """

    def __init__(self, name: str, system_prompt: str = "", tools: Optional[List] = None,
                 input_key: Optional[str] = None, output_key: str = "output",
                 max_tokens: Optional[int] = None, max_tool_calls: int = 25):
        self.name = name
        self.system_prompt = system_prompt
        # None → default coding toolset (BashTool + NetworkEditTool); [] → explicitly no tools.
        self._tools = tools
        self.input_key = input_key
        self.output_key = output_key
        self.max_tokens = max_tokens
        self.max_tool_calls = max_tool_calls
        self.history_id: Optional[str] = None
        self._config = None

    def _ensure_config(self):
        if self._config is None:
            self._config = build_minimax_config(self.name, self.system_prompt, self._tools, self.max_tokens)
        return self._config

    async def _run(self, message: str) -> str:
        """The OMRuntime.run core: heaven agent + BackgroundEventCapture → last AGENT_MESSAGE."""
        from heaven_base.baseheavenagent import BaseHeavenAgent
        from heaven_base.unified_chat import UnifiedChat
        from heaven_base.docs.examples.heaven_callbacks import (
            BackgroundEventCapture,
            CompositeCallback,
        )

        kwargs = dict(config=self._ensure_config(), unified_chat=UnifiedChat(),
                      max_tool_calls=self.max_tool_calls)
        if self.history_id:
            kwargs["history_id"] = self.history_id
        agent = BaseHeavenAgent(**kwargs)

        capture = BackgroundEventCapture()
        result = await agent.run(message, heaven_main_callback=CompositeCallback([capture]))

        new_hid = result.get("history_id") if isinstance(result, dict) else None
        if new_hid:
            self.history_id = new_hid

        msgs = capture.get_events_by_type("AGENT_MESSAGE")
        return (msgs[-1].get("data", {}).get("content", "") or "") if msgs else ""

    async def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs):
        ctx = dict(context) if context else {}
        content = input_from_context(ctx, self.input_key)
        try:
            text = await self._run(content)
        except Exception as e:
            return LinkResult(status=LinkStatus.ERROR, context=ctx, error=str(e))
        ctx[self.output_key] = text
        ctx["output"] = text
        ctx[f"output:{self.name}"] = text
        return LinkResult(status=LinkStatus.SUCCESS, context=ctx)

    def reset(self) -> None:
        """Drop history — start a fresh conversation."""
        self.history_id = None

    def describe(self, depth: int = 0) -> str:
        return "  " * depth + f'HeavenMiniMaxLink "{self.name}" (minimax/heaven)'
