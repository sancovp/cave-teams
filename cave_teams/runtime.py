"""
runtime.py — a TEAM as a first-class AGENT (the homoiconic close: agent = team = agent).

A TeamRuntime wraps a whole cave-team (agents + a topology) behind ONE uniform interface:

    .send(content, ...) -> AgentResult   # the cave-teams HARNESS interface, so a team can be a
                                         #   MEMBER of another team → runtime STACKING / hierarchies
    .run(message) -> str                 # the CAVE / HEAVEN runtime interface, so you can OVERRIDE a
                                         #   heaven/CAVE agent's run with a team (CAVE DI's run/
                                         #   handle_message/__call__ — a TeamRuntime satisfies all three)
    __call__(message) -> str             # APPLY NOTATION: team(message)

Because a team's member can itself be a TeamRuntime, runtimes nest arbitrarily. You program any
agent runtime by APPLYING topology combinators to agents and sub-teams (extensional OOP, apply
notation) — not by writing class hierarchies. agent = team = agent, closed under composition.

    inner = as_agent("inner", inner_spec, lambda h: chain(h, ["x", "y"]))   # a team, behind one agent
    inner("hello")                                                          # apply notation
    outer.register("draft", inner)                                          # ...as a MEMBER of another team
    heaven_agent.run = as_agent("squad", spec, wire).run                    # ...as a heaven agent's runtime
"""

from __future__ import annotations

import asyncio
import json as _json
from typing import Any, Callable, Dict, Optional, Tuple

from .primitives import AgentResult
from .chain_ontology import Link, LinkResult, LinkStatus


class TeamRuntime(Link):
    """A whole team presented as a single agent. Substitutable as:
      - a chain-ontology Link (.execute(context) — composes in Chain/ConcurrentChain/EvalChain),
      - a cave-teams member (.send),
      - a CAVE/HEAVEN runtime (.run / .handle_message),
      - a plain callable (__call__ — apply notation)."""

    def __init__(self, name: str, run_fn: Callable[[str, Optional[Callable]], str],
                 backend: str = "team", model: str = "team"):
        self.name = name
        self.backend = backend
        self.model = model
        self.messages: list = []          # history_length() compat for the harness
        self._run_fn = run_fn

    # ---- cave-teams HARNESS interface (a team is a team-member → stacking) ----
    def send(self, content: str, from_agent: str = "harness",
             on_chunk: Optional[Callable[[str], None]] = None) -> AgentResult:
        self.messages.append({"role": "user", "content": content})
        try:
            text = self._run_fn(content, on_chunk) or ""
            self.messages.append({"role": "assistant", "content": text})
            return AgentResult(text=text, duration_ms=0)
        except Exception as e:
            return AgentResult(error=str(e), success=False)

    def history_length(self) -> int:
        return len(self.messages)

    # ---- CAVE / HEAVEN runtime interface (override an agent's run with a team) ----
    def run(self, message: Any = None) -> str:
        return self.send("" if message is None else str(message)).text

    def handle_message(self, message: Any) -> str:
        return self.run(message)

    # ---- apply notation: team(message) ----
    def __call__(self, message: Any = None) -> str:
        return self.run(message)

    # ---- chain-ontology Link interface (a team composes as a Link) ----
    async def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs):
        ctx = dict(context) if context else {}
        val = ctx.get("output") or ctx.get("goal") or ctx.get("input") or ""
        content = val if isinstance(val, str) else _json.dumps(val, default=str)
        res = await asyncio.to_thread(self.send, content)   # off-thread → ConcurrentChain stays parallel
        if not res.success:
            return LinkResult(status=LinkStatus.ERROR, context=ctx, error=res.error)
        ctx["output"] = res.text
        ctx[f"output:{self.name}"] = res.text
        return LinkResult(status=LinkStatus.SUCCESS, context=ctx)

    def describe(self, depth: int = 0) -> str:
        return "  " * depth + f'TeamRuntime "{self.name}" (team-as-Link)'


def as_agent(name: str, spec: dict, wire: Callable[[Any], Tuple[str, str]]) -> TeamRuntime:
    """Wrap a team (a build_team `spec` + a `wire(harness) -> (entry, exit)` topology) as ONE agent.

    `wire(h)` sets up the sub-team's edges/conditions and returns its (entry, exit) agents — the
    topology combinators already return (head, tail), so `wire=lambda h: chain(h, ["x","y"])` works.
    On each call: the content is sent to `entry`, the sub-team runs to idle, and `exit`'s last output
    is returned. Register it like any agent (`harness.register(name, as_agent(...))`) and you have
    runtime stacking; a member of THAT sub-team can itself be an as_agent(...) → nests forever.

    The sub-team is built FRESH per call (stateless turn). The sub-team's token stream forwards to the
    caller's on_chunk, so a stacked team still streams live in the gallery.
    """
    from .adaptor import build_team

    def run_fn(content: str, on_chunk=None) -> str:
        def fwd(ev):
            if on_chunk and getattr(ev, "kind", None) == "stream":
                on_chunk(ev.data.get("delta", ""))
        sub = build_team({**spec, "concurrent": spec.get("concurrent", True)}, on_event=fwd)
        entry, exit = wire(sub)
        sub.send_message("leader", entry, content)
        sub.wait_idle(timeout=spec.get("timeout", 600))
        return sub.get_flag(f"output:{exit}") or ""

    return TeamRuntime(name, run_fn, backend="team")
