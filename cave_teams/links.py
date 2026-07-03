"""
links.py — cave-teams LEAF Links: a single LLM agent as a chain-ontology Link.

AgentLink wraps one RUNTIME (any object with `.run(str) -> str` — cave's set_runtime protocol, e.g.
`cave_teams.examples.MiniMaxRuntime` / `ClaudePRuntime`) as a `Link`: execute(context) reads its
input from the context, runs ONE agent turn (off-thread if the runtime is sync, awaited if async),
and writes the reply back into the context under `output_key` + the conventional `output` +
`output:<name>` keys. So a single agent composes in Chain / ConcurrentChain / EvalChain exactly like
any other Link — and cave() specs with `{"op":"agent", ...}` leaves are RUNNABLE.

(The pre-rebuild AgentLink wrapped the superseded `Conversation`; this one wraps the runtime
protocol the rebuild standardized on. Same context convention as before.)

Context convention: a Link reads its input from `input_key` if given, else the previous link's
`output` (or `goal`/`input` at the start), and writes its reply to `output`. Dovetail overrides this
with typed extraction when a step needs named inputs.
"""

from __future__ import annotations

import asyncio
import json as _json
from typing import Any, Dict, Optional

from .chain_ontology import Link, LinkResult, LinkStatus


def input_from_context(ctx: Dict[str, Any], input_key: Optional[str]) -> str:
    val = ctx[input_key] if (input_key and input_key in ctx) else (
        ctx.get("output") or ctx.get("goal") or ctx.get("input") or "")
    return val if isinstance(val, str) else _json.dumps(val, default=str)


def _make_runtime(name: str, system_prompt: str, backend: str, model: Optional[str]):
    """Build an example-instance runtime for a backend name. minimax/claude-p are the demo
    backends (examples/); ANY object with .run(str)->str works via AgentLink(runtime=...)."""
    if backend in ("minimax", "heaven"):
        from .examples.minimax_runtime import MiniMaxRuntime
        return MiniMaxRuntime(name=name, system_prompt=system_prompt, model=model)
    if backend in ("claude-p", "claude", "claude_p", "opus"):
        from .examples.claude_p_runtime import ClaudePRuntime
        return ClaudePRuntime(name=name, system_prompt=system_prompt, model=model)
    raise ValueError(f"unknown backend '{backend}' — pass runtime=<object with .run(str)>, "
                     f"or use 'minimax' / 'claude-p'")


class AgentLink(Link):
    """A single LLM agent as a Link (over any `.run(str) -> str` runtime)."""

    def __init__(self, name: str, system_prompt: str = "", backend: str = "minimax",
                 model: Optional[str] = None, runtime: Any = None,
                 input_key: Optional[str] = None, output_key: str = "output"):
        self.name = name
        self.runtime = runtime or _make_runtime(name, system_prompt, backend, model)
        self.backend = backend if runtime is None else type(runtime).__name__
        self.input_key = input_key
        self.output_key = output_key

    async def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs):
        ctx = dict(context) if context else {}
        content = input_from_context(ctx, self.input_key)
        try:
            if asyncio.iscoroutinefunction(self.runtime.run):
                res = await self.runtime.run(content)
            else:
                res = await asyncio.to_thread(self.runtime.run, content)
            if asyncio.iscoroutine(res):
                res = await res
        except Exception as e:
            return LinkResult(status=LinkStatus.ERROR, context=ctx, error=str(e))
        text = res if isinstance(res, str) else ("" if res is None else str(res))
        ctx[self.output_key] = text
        ctx["output"] = text
        ctx[f"output:{self.name}"] = text
        return LinkResult(status=LinkStatus.SUCCESS, context=ctx)

    def describe(self, depth: int = 0) -> str:
        return "  " * depth + f'AgentLink "{self.name}" ({self.backend})'


__all__ = ["AgentLink", "input_from_context"]
