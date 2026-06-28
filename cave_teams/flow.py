"""
flow.py — CHECK always / LIFT on condition (the gate, rule 01).

A condition is a predicate over the team's message log: Callable[[List[TeamMessage]], bool].
cave-teams CHECKs the dir continuously and LIFTs (dispatches a "read {path}" pointer) only
when ALL of an edge's conditions pass. Runtime-agnostic: the caller supplies a dispatch_fn —
in-process just calls the agent and writes its response; a detached runtime's paia hook writes
it. No hooks here; conditions only ever read files.

The conditions registry is cave-teams' OWN (agents are cave's; cave-teams owns conditions + teams).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from .messages import TeamMessage, RESPONSE, FLAG

Condition = Callable[[List[TeamMessage]], bool]


# ── condition predicates over the message log ───────────────────────────────
def responded(agent: str) -> Condition:
    """True once `agent` has written a RESPONSE message."""
    return lambda log: any(m.frm == agent and m.kind == RESPONSE for m in log)


def after(*agents: str) -> Condition:
    """Join / barrier: True once EVERY named agent has responded."""
    return lambda log: all(any(m.frm == a and m.kind == RESPONSE for m in log) for a in agents)


def when_flag(name: str, value: Any = True) -> Condition:
    """True when the latest FLAG message for `name` equals `value`."""
    def cond(log: List[TeamMessage]) -> bool:
        flags = [m for m in log if m.kind == FLAG and m.data.get("name") == name]
        return bool(flags) and flags[-1].data.get("value") == value
    return cond


def when_message(predicate: Callable[[TeamMessage], bool]) -> Condition:
    """Arbitrary check — True if ANY message matches the predicate."""
    return lambda log: any(predicate(m) for m in log)


def all_of(*conds: Condition) -> Condition:
    return lambda log: all(c(log) for c in conds)


def any_of(*conds: Condition) -> Condition:
    return lambda log: any(c(log) for c in conds)


def always() -> Condition:
    return lambda log: True


# ── the conditions registry (cave-teams owns this; team configs reference by name) ──
_CONDITIONS: Dict[str, Condition] = {}


def register_condition(name: str, cond: Condition) -> None:
    _CONDITIONS[name] = cond


def get_condition(name: str) -> Condition:
    if name not in _CONDITIONS:
        raise KeyError(
            f"unknown condition '{name}' — register_condition() it first; "
            f"known: {list(_CONDITIONS)}")
    return _CONDITIONS[name]


def registered_conditions() -> List[str]:
    return list(_CONDITIONS)


# ── the edge: an addressed dispatch gated by conditions ─────────────────────
@dataclass
class Edge:
    """When ALL `conditions` hold over the log, LIFT: dispatch a 'read {pointer}' to `to`."""
    to: str
    conditions: List[Condition] = field(default_factory=list)
    pointer: str = ""
    frm: str = "runtime"
    once: bool = True
    fired: bool = False


# NOTE: the mechanical CHECK/LIFT `TeamFlow` dispatcher was REMOVED — teams run LEADER-DRIVEN
# (a leader proposes messages, the guardrail checks them, the LLM self-fixes). See runner.py.
# These conditions/edges are now the GUARDRAILS the leader's messages are checked against.
