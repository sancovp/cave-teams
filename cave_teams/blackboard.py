"""
blackboard.py — the arena / stigmergy topology (the gameworld core).

Not a dataflow shape (seq/par/dag thread context THROUGH a composition); this is N autonomous agents ↔ 1
persistent shared state ↔ 1 adjudicator, coordinating INDIRECTLY through the environment. Each round:

  1. every agent reads the CURRENT board snapshot and PROPOSES an action (concurrently, blind to peers)
  2. the MUTATOR applies each proposal serially — the single atomic write path, with kill-criteria
     (a rejected action raises ValueError → logged, never crashes the arena)   [= execute.sh's `exit 1`]
  3. the ADJUDICATOR (deity) observes the board, may rewrite it (bulletins) and set board["_stop"]   [= the gate]
  4. repeat until `rounds` or board["_stop"]                                     [= the season loop]

The mutator is where ALL world-logic lives (agents only propose); the adjudicator is the valuation gate
(peer/market ⇒ sound, self ⇒ self-granting — see LAWS P2). A Blackboard IS a Link, so arenas nest.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable, Dict, List, Optional

from .chain_ontology import Link, LinkResult, LinkStatus


class Blackboard(Link):
    """agents: {name: Link} (each reads board, outputs ctx['action']);
    mutator: (state, agent_name, action) -> new_state, raising ValueError to REJECT;
    adjudicator: optional Link run each round on the board (may write it / set _stop)."""

    def __init__(self,
                 agents: Dict[str, Link],
                 mutator: Callable[[Dict[str, Any], str, Any], Dict[str, Any]],
                 adjudicator: Optional[Link] = None,
                 rounds: int = 1,
                 state_key: str = "board",
                 name: str = "blackboard"):
        self.agents = dict(agents)
        self.mutator = mutator
        self.adjudicator = adjudicator
        self.rounds = rounds
        self.state_key = state_key
        self.name = name

    async def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs):
        ctx0 = dict(context) if context else {}
        state: Dict[str, Any] = dict(ctx0.get(self.state_key, {}))   # the persistent blackboard
        log: List[Dict[str, Any]] = []
        rounds_run = 0

        for rnd in range(self.rounds):
            rounds_run += 1

            async def propose(name: str, link: Link):
                inp = dict(ctx0)
                inp[self.state_key] = dict(state)        # every agent sees the SAME snapshot
                inp["agent_id"] = name
                inp["round"] = rnd
                return name, await link.execute(inp)

            proposals = await asyncio.gather(*[propose(n, l) for n, l in self.agents.items()])

            for name, r in proposals:                     # serial apply = the single atomic write path
                action = (r.context or {}).get("action")
                if action is None:
                    continue
                try:
                    mutated = self.mutator(state, name, action)         # mutator may be sync OR async
                    state = await mutated if inspect.isawaitable(mutated) else mutated
                    log.append({"round": rnd, "agent": name, "action": action, "ok": True})
                except Exception as e:                    # kill-criterion: rejected, logged, arena survives
                    # ValueError is the INTENDED rejection; any other exception (a buggy mutator's
                    # KeyError/TypeError, an NPC blowing up) must ALSO not crash the arena.
                    log.append({"round": rnd, "agent": name, "action": action, "ok": False,
                                "error": str(e), "error_type": type(e).__name__})

            if self.adjudicator is not None:
                inp = dict(ctx0)
                inp[self.state_key] = dict(state)
                inp["round"] = rnd
                ar = await self.adjudicator.execute(inp)
                state = (ar.context or {}).get(self.state_key, state)   # deity may rewrite the board (bulletins)
                if state.get("_stop"):
                    break

        final = dict(ctx0)
        final[self.state_key] = state
        final["_blackboard_log"] = log
        final["_rounds_run"] = rounds_run
        final["output"] = state
        return LinkResult(status=LinkStatus.SUCCESS, context=final)

    def describe(self, depth: int = 0) -> str:
        pad = "  " * depth
        adj = self.adjudicator.name if self.adjudicator is not None else "none"
        return (f'{pad}blackboard "{self.name}": {len(self.agents)} agents '
                f'[{", ".join(self.agents)}] ↔ mutator ↔ adjudicator={adj}, rounds≤{self.rounds}')


def blackboard(agents: Dict[str, Link],
               mutator: Callable[[Dict[str, Any], str, Any], Dict[str, Any]],
               adjudicator: Optional[Link] = None,
               rounds: int = 1,
               state_key: str = "board",
               name: str = "blackboard") -> Blackboard:
    """The arena topology: N agents ↔ shared state ↔ adjudicator, over rounds (the gameworld turn loop)."""
    return Blackboard(agents, mutator, adjudicator, rounds=rounds, state_key=state_key, name=name)


__all__ = ["blackboard", "Blackboard"]
