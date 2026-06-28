"""
conditions — fire-gate HOOKS for the Harness (the "fire when xyz" predicates).

A condition is `Callable[[Harness, agent_name], bool]`. An agent fires only when it has a
pending message AND ALL its conditions pass. Register with `harness.add_condition(agent, cond)`;
flip runtime state with `harness.set_flag(name)`. Composing these gives any topology declaratively:

    h.add_condition("reviewer", after("writer"))        # join/barrier: wait for writer
    h.add_condition("publisher", when_flag("approved"))  # gated branch
    h.add_condition("worker", when(lambda h,a: h.get_flag("budget") > 0))   # arbitrary check

These mirror CAVE's Automation system (EventAutomation / `depends_on`) but stay STANDALONE.
`wrap_cave_automation` lets a condition BE a CAVE automation when you want the full machinery
(uses cave the LIBRARY — no running CAVE server required).
"""

from __future__ import annotations

from typing import Any, Callable

# Condition = Callable[[Harness, str], bool]  (Harness imported lazily to avoid a cycle)


def when_flag(name: str, value: Any = True):
    """Fire only when flag `name` == `value`."""
    return lambda h, a: h.get_flag(name) == value


def when_not_flag(name: str):
    """Fire only when flag `name` is unset/falsey."""
    return lambda h, a: not h.get_flag(name)


def after(*agents: str):
    """Join / barrier: fire only after EACH named agent has completed at least one turn.
    (Each delivery auto-sets the flag `done:<agent>` as a completion counter.)"""
    return lambda h, a: all(int(h.get_flag(f"done:{x}") or 0) >= 1 for x in agents)


def when(predicate: Callable[[Any, str], bool]):
    """Arbitrary hook — 'condition is to check xyz'. predicate(harness, agent) -> bool."""
    return lambda h, a: bool(predicate(h, a))


def all_of(*conds):
    """Fire only when ALL of the given conditions pass."""
    return lambda h, a: all(c(h, a) for c in conds)


def any_of(*conds):
    """Fire when ANY of the given conditions passes."""
    return lambda h, a: any(c(h, a) for c in conds)


def wrap_cave_automation(automation):
    """Use a CAVE `InputAutomation` (CronAutomation / EventAutomation / ...) as a fire condition.

    Uses cave the LIBRARY, not a running server: a Cron/Manual automation gates on `is_due()`;
    anything else passes (its own trigger semantics apply elsewhere). Lets cave-teams ride CAVE's
    full Automation/condition machinery when present, without a hard dependency.
    """
    def cond(h, a) -> bool:
        try:
            is_due = getattr(automation, "is_due", None)
            return bool(is_due()) if callable(is_due) else True
        except Exception:
            return False
    return cond
