"""
links.py — cave-teams LEAF Links: a single LLM agent as a chain-ontology Link.

AgentLink wraps one Conversation (claude-p or MiniMax agent) as a `Link`: execute(context) reads its
input from the context, runs ONE agent turn OFF-THREAD (so a ConcurrentChain of AgentLinks is truly
parallel even though Conversation.send is blocking), and writes the reply back into the context under
`output_key` + the conventional `output` + `output:<name>` keys. So a single agent composes in
Chain / ConcurrentChain / EvalChain exactly like any other Link — the SDNA chain ontology runs over
cave-teams agents.

Context convention: a Link reads its input from `input_key` if given, else the previous link's
`output` (or `goal`/`input` at the start), and writes its reply to `output`. Dovetail overrides this
with typed extraction when a step needs named inputs.
"""

from __future__ import annotations

import asyncio
import json as _json
from typing import Any, Dict, Optional

from .chain_ontology import Link, LinkResult, LinkStatus
from .conversation import Conversation


def input_from_context(ctx: Dict[str, Any], input_key: Optional[str]) -> str:
    val = ctx[input_key] if (input_key and input_key in ctx) else (
        ctx.get("output") or ctx.get("goal") or ctx.get("input") or "")
    return val if isinstance(val, str) else _json.dumps(val, default=str)


class AgentLink(Link):
    """A single LLM agent as a Link."""

    def __init__(self, name: str, system_prompt: str = "", backend: str = "minimax",
                 model: Optional[str] = None, cwd: str = "/tmp",
                 conversation: Optional[Conversation] = None,
                 input_key: Optional[str] = None, output_key: str = "output"):
        self.name = name
        self.conversation = conversation or Conversation(
            name=name, system_prompt=system_prompt, backend=backend, model=model, cwd=cwd)
        self.input_key = input_key
        self.output_key = output_key

    async def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs):
        ctx = dict(context) if context else {}
        content = input_from_context(ctx, self.input_key)
        result = await asyncio.to_thread(self.conversation.send, content)
        if not result.success:
            return LinkResult(status=LinkStatus.ERROR, context=ctx, error=result.error)
        ctx[self.output_key] = result.text
        ctx["output"] = result.text
        ctx[f"output:{self.name}"] = result.text
        return LinkResult(status=LinkStatus.SUCCESS, context=ctx)

    def describe(self, depth: int = 0) -> str:
        return "  " * depth + f'AgentLink "{self.name}" ({self.conversation.backend})'
