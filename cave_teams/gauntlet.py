"""
gauntlet.py — the viral "Gauntlet Loop" (Shumer, 2026-07) as ONE GameWorld preset.

The wave's pattern was: a lead decomposes, parallel builder subagents each own a
subsystem, a fresh-context blind critic compares the build to a real reference, loop.
Its coordination lived in a prose ARCHITECTURE.md ("own your directory, never edit
outside it"); its lessons died with the session; its termination was a human watching
the meter. Here the same loop is a composition of existing primitives:

    gauntlet = season( blackboard(builders ↔ board ↔ blind critic), advance = carry/ratchet )

with each prose rule reified into the slot that enforces it:

  prompt version                          this preset
  ─────────────────────────────────────   ──────────────────────────────────────────
  "never edit outside your directory"     the MUTATOR — a cross-subsystem write raises
       (a request, in prose)                ValueError: rejected, logged, arena survives
  fresh-context critic, lessons lost      critique ledger CARRIES across the season
                                            boundary (the critic's history is board data)
  fixed bar, human is the brake           the RATCHET raises the bar each season; the
                                            season count is the termination, in-world
  one session, cannot be re-entered       the board is data in/out — persist it, resume
                                            it, nest the whole gauntlet as one agent
                                            (world_as_agent) inside a bigger world

The whole usage is a spec (the "~20 lines" receipt — builders/critic are any Links,
LLM-backed or deterministic):

    world = GauntletWorld(
        builders={"render": render_agent, "audio": audio_agent, "ai": ai_agent},
        critic=blind_critic,          # reads board, writes board["critique"], may _stop
        rounds=6, seasons=4,
    )
    r = await world.execute({"board": {"bar": 1, "reference": "CoD frame set"}})
    # r.context["board"]: subsystems built, critique ledger, bar ratcheted, _seasons audit

Receipts for why each slot matters are in garage-lab/GAUNTLET-LOOP-ANATOMY.md (the
original run's own README: parallel rounds +0.46 with defects UP vs sequential +1.00;
critics repeating a wrong diagnosis for three rounds because nothing carried).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .chain_ontology import Link
from .gameworld import GameWorld
from .season import carry_reset_ratchet


def ownership_mutator(state: Dict[str, Any], agent: str, action: Any) -> Dict[str, Any]:
    """The ARCHITECTURE.md contract as code: a builder's action is
    {"subsystem": <name>, "build": <payload>} and it may ONLY write its own subsystem
    (subsystem name == agent name). A cross-subsystem write is REJECTED (ValueError →
    logged by the arena, never crashes it) instead of requested in prose."""
    if not isinstance(action, dict):
        raise ValueError(f"{agent}: action must be a dict, got {type(action).__name__}")
    target = action.get("subsystem", agent)
    if target != agent:
        raise ValueError(f"ownership contract: {agent} may not write subsystem '{target}'")
    s = dict(state)
    subs = dict(s.get("subsystems", {}))
    subs[agent] = action.get("build")
    s["subsystems"] = subs
    return s


def raise_bar(board: Dict[str, Any], n: int) -> Dict[str, Any]:
    """The default ratchet: the quality bar climbs at every season boundary — termination
    is an in-world condition (the season count against a rising bar), not an operator's
    patience. Carries automatically: subsystems, critique ledger, defect history."""
    b = dict(board)
    b["bar"] = b.get("bar", 1) + 1
    return b


class GauntletWorld(GameWorld):
    """The Gauntlet Loop with the missing slots filled: builders propose concurrently and
    blind to peers (the blackboard round), the ownership contract is enforced by the
    mutator, the blind critic sits in the adjudicator slot (reads the board, appends to
    board["critique"], may set board["_stop"] on a won blind pick), and the season
    boundary does what the prompt version structurally cannot: CARRY the critique/defect
    ledger, RESET the round scratch, RATCHET the bar."""

    def __init__(self,
                 builders: Dict[str, Link],
                 critic: Optional[Link] = None,
                 rounds: int = 3,
                 seasons: int = 1,
                 reset_to: Optional[Dict[str, Any]] = None,
                 ratchet=raise_bar,
                 name: str = "gauntlet"):
        super().__init__(builders, ownership_mutator, deity=critic,
                         advance=carry_reset_ratchet(reset_to=reset_to or {"scratch": dict},
                                                     ratchet=ratchet),
                         rounds=rounds, seasons=seasons, name=name)


__all__ = ["GauntletWorld", "ownership_mutator", "raise_bar"]
