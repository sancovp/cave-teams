"""
sdna_bridge.py — Phase 2: the SDNA / heaven agent zoo as leaf Links.

Because cave_teams.chain_ontology re-exports the REAL `sdna.chain_ontology` when present, SDNA's own
SDNAC / SDNAFlow / SDNAFlowchain are ALREADY cave-teams `Link`s and compose directly in a Chain /
ConcurrentChain / EvalChain — nothing to wrap. This module adds:

  - `as_link(obj, ...)` — adapt ANY runnable into a Link: a Link passes through; otherwise its
    .run / .handle_message / .send / __call__ is called and the reply written into the context. This
    covers heaven agents (BaseHeavenAgent.run), cave-teams TeamRuntime/Conversation, plain callables.
  - import-guarded re-exports of the SDNA agent constructors (SDNAC, SDNAFlow, SDNAFlowchain, sdnac)
    so a cave-teams user can build SDNA leaf Links without importing sdna directly.

Everything here is OPTIONAL and import-guarded — cave-teams stays standalone (claude-p leaf) if SDNA /
heaven aren't installed.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from .chain_ontology import Link, LinkResult, LinkStatus


class RunnableLink(Link):
    """Adapt any non-Link runnable (heaven agent, callable, .send/.run object) into a Link."""

    def __init__(self, name: str, obj: Any, input_key: Optional[str] = None, output_key: str = "output"):
        self.name = name
        self.obj = obj
        self.input_key = input_key
        self.output_key = output_key

    async def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs):
        from .links import input_from_context
        ctx = dict(context) if context else {}
        content = input_from_context(ctx, self.input_key)
        obj = self.obj
        try:
            if hasattr(obj, "run"):
                res = await obj.run(content) if _is_async(obj.run) else await asyncio.to_thread(obj.run, content)
            elif hasattr(obj, "handle_message"):
                fn = obj.handle_message
                res = await fn(content) if _is_async(fn) else await asyncio.to_thread(fn, content)
            elif hasattr(obj, "send"):
                fn = obj.send
                r = await fn(content) if _is_async(fn) else await asyncio.to_thread(fn, content)
                res = getattr(r, "text", r)
            elif callable(obj):
                res = obj(content)
                if asyncio.iscoroutine(res):
                    res = await res
            else:
                res = str(obj)
            if asyncio.iscoroutine(res):
                res = await res
        except Exception as e:  # pragma: no cover
            return LinkResult(status=LinkStatus.ERROR, context=ctx, error=str(e))
        text = res if isinstance(res, str) else getattr(res, "text", str(res))
        ctx[self.output_key] = text
        ctx["output"] = text
        ctx[f"output:{self.name}"] = text
        return LinkResult(status=LinkStatus.SUCCESS, context=ctx)

    def describe(self, depth: int = 0) -> str:
        return "  " * depth + f'RunnableLink "{self.name}" ({type(self.obj).__name__})'


def _is_async(fn) -> bool:
    return asyncio.iscoroutinefunction(fn)


def as_link(obj: Any, name: Optional[str] = None,
            input_key: Optional[str] = None, output_key: str = "output") -> Link:
    """Adapt ANY runnable into a chain-ontology Link.

    - already a Link (SDNAC, SDNAFlow, a cave-teams Chain/AgentLink/TeamRuntime) → returned as-is.
    - heaven agent / .run / .handle_message / .send object / plain callable → wrapped as a RunnableLink
      that reads its input from the context and writes the reply back.
    """
    if isinstance(obj, Link):
        return obj
    return RunnableLink(name or getattr(obj, "name", "agent"), obj, input_key, output_key)


# ---- optional SDNA constructors (LAZY import-guarded, PEP 562) ----
# Loaded on first attribute access, NOT at module import — so `import cave_teams` never drags
# sdna/heaven in as a side effect just because they happen to be installed (the standalone contract
# protects against sdna being present-but-unwanted, not only absent).
_SDNA_NAMES = ("SDNAC", "SDNAFlow", "SDNAFlowchain", "sdnac")


def __getattr__(name: str):  # pragma: no cover
    if name in _SDNA_NAMES:
        try:
            from sdna import sdna as _sdna_mod
            return getattr(_sdna_mod, name)
        except Exception:
            return None
    if name == "SDNA_AVAILABLE":
        try:
            import sdna.sdna  # noqa: F401
            return True
        except Exception:
            return False
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
