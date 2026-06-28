"""
context_engineering.py — context surgery (inject / weave / dovetail), the context-assembly plane.

How an agent's prompt gets BUILT from blocks (inject) and how one context borrows a slice of another
(weave). This is the layer NPC / player / deity prompts are composed from, and how a deity is handed the
context of the worlds running under it.

cave_teams always ships native, pure-Python helpers (compose_context / weave_text) so this works
standalone; AND it re-exports SDNA's full context_engineering (the real inject/weave/dovetail surgery +
tmux↔SDK transport) when importable — same shim pattern as chain_ontology.
"""

from __future__ import annotations

from typing import Any, Dict, List, Union


# ── native helpers (always available, pure, NO transport) ───────────────────
def compose_context(blocks: Union[List[Any], Dict[str, Any]], method: str = "prepend") -> str:
    """Assemble an agent's context from blocks. dict → '## key\\n value' sections; list → joined.
    `method` mirrors SDNA's InjectMethod (prepend/file/rules/env) — native version returns the text;
    the caller decides where it goes."""
    if isinstance(blocks, dict):
        parts = [f"## {k}\n{v}" for k, v in blocks.items()]
    else:
        parts = [str(b) for b in blocks]
    return "\n\n".join(parts)


def weave_text(text: str, start: int, end: int) -> str:
    """Splice a line-range [start:end] out of a source text — the native shadow of weave_context
    (which does it across live sessions/transcripts)."""
    return "\n".join(text.splitlines()[start:end])


# ── re-export SDNA's full context_engineering when present ──────────────────
try:
    from sdna.context_engineering import (  # noqa: F401
        weave_context, inject_context, ContextEngineeringLib, get_lib,
        WeaveContext, InjectContext, RunSequence, ActivateLoop, InjectMethod, TransportType,
    )
    CONTEXT_ENGINEERING_SOURCE = "sdna"
except Exception:
    CONTEXT_ENGINEERING_SOURCE = "native-only"

    def inject_context(context: Dict[str, Any], method: str = "prepend") -> str:
        """Fallback inject — composes the blocks (no live transport)."""
        return compose_context(context, method=method)

    def weave_context(source_id: str, start: int, end: int):  # type: ignore
        """Fallback weave — requires a real session/transport; native-only build returns None."""
        return None


__all__ = [
    "compose_context", "weave_text", "inject_context", "weave_context",
    "CONTEXT_ENGINEERING_SOURCE",
]
