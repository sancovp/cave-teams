"""
npc.py — NPCs: agents that exist inside the world, callable by the players via a skill.

A player (or a deity) acts with {"type": "call_npc", "npc": <name>, "ask": ...}; the NPC (an agent in the
world's registry) runs and its crafted reply — a prompt, a skill, a whole agent, anything PromptWorld can
make (including cave_teams itself) — is deposited into the caller's inventory on the board. NPCs are the
in-world interface to the agent-factory: players talk to them and get stuff.

`npc_mutator(base, npcs)` wraps any world mutator so `call_npc` actions are routed to the NPC registry and
everything else delegates to the base economy. Because the blackboard awaits its mutator, NPCs (async
agents) just work. NPCs are Links, so an NPC can itself be a whole GameWorld ("GameMaster Heaven").
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, Dict

from .chain_ontology import Link


def npc_mutator(base_mutator: Callable[[Dict[str, Any], str, Any], Dict[str, Any]],
                npcs: Dict[str, Link],
                inventory_key: str = "inventory") -> Callable:
    """Return an async mutator: a `call_npc` action runs the named NPC and deposits its artifact into the
    caller's inventory; all other actions delegate to `base_mutator` (sync or async). Unknown NPC or an
    NPC error is recorded as a rejected call — the arena survives."""

    async def mut(state: Dict[str, Any], agent: str, action: Any) -> Dict[str, Any]:
        if isinstance(action, dict) and action.get("type") == "call_npc":
            name = action.get("npc")
            npc = npcs.get(name)
            s = dict(state)
            inv = dict(s.get(inventory_key, {}))
            mine = list(inv.get(agent, []))
            if npc is None:
                raise ValueError(f"no such NPC: {name!r}")        # kill-criterion → logged, arena survives
            r = await npc.execute({"ask": action.get("ask"), "caller": agent})
            ctx = r.context or {}
            artifact = ctx.get("artifact", ctx.get("output"))
            mine.append({"npc": name, "ask": action.get("ask"), "artifact": artifact})
            inv[agent] = mine
            s[inventory_key] = inv
            return s
        result = base_mutator(state, agent, action)
        return await result if inspect.isawaitable(result) else result

    return mut


__all__ = ["npc_mutator"]
