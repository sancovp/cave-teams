"""
gameworld.py — a WHOLE gameworld as ONE composable object: a program, and a class.

Everything the agent_mmorpg sprawl did with bash `execute.sh` + a 73KB `game.json` + `deity-season.sh`
now collapses into a composition of cave_teams primitives:

    GameWorld  =  season( blackboard(agents ↔ shared state ↔ deity), advance = carry/reset/ratchet )

A GameWorld IS a Link, so a whole world nests, runtime-stacks, and composes like any single agent. And
because it's a CLASS, a world is:
  - instantiable     — many worlds from one definition
  - data-driven      — GameWorld.from_spec(spec, ...) (the mode → economy compiler)
  - subclassable     — WoS = a GameWorld subclass that fixes its economy + ratchet
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .chain_ontology import Link, LinkResult, LinkStatus
from .blackboard import blackboard
from .season import season, carry_reset_ratchet


class GameWorld(Link):
    """A whole gameworld, composed: blackboard arena (agents ↔ shared state ↔ deity) wrapped in a
    season epoch (carry/reset/ratchet). Instantiate it, run it, nest it, subclass it."""

    def __init__(self,
                 agents: Dict[str, Link],
                 mutator: Callable[[Dict[str, Any], str, Any], Dict[str, Any]],
                 deity: Optional[Link] = None,
                 advance: Optional[Callable[[Dict[str, Any], int], Dict[str, Any]]] = None,
                 rounds: int = 1,
                 seasons: int = 1,
                 state_key: str = "board",
                 name: str = "gameworld"):
        self.name = name
        self.state_key = state_key
        self.arena = blackboard(agents, mutator, adjudicator=deity, rounds=rounds,
                                state_key=state_key, name=f"{name}:arena")
        self.epoch = season(self.arena, advance=advance, seasons=seasons,
                            state_key=state_key, name=name)

    async def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs):
        return await self.epoch.execute(context)

    def describe(self, depth: int = 0) -> str:
        return "  " * depth + f'GameWorld "{self.name}":\n' + self.epoch.describe(depth + 1)

    @classmethod
    def from_spec(cls, spec: Dict[str, Any], agents: Dict[str, Link],
                  mutator: Callable[[Dict[str, Any], str, Any], Dict[str, Any]],
                  deity: Optional[Link] = None) -> "GameWorld":
        """Compile a world from a spec (the mode → economy compiler):
        {rounds, seasons, reset_to, ratchet, name}."""
        return cls(agents, mutator, deity=deity,
                   advance=carry_reset_ratchet(reset_to=spec.get("reset_to"), ratchet=spec.get("ratchet")),
                   rounds=spec.get("rounds", 1), seasons=spec.get("seasons", 1),
                   state_key=spec.get("state_key", "board"), name=spec.get("name", "gameworld"))


def world_as_agent(world: GameWorld,
                   derive_action: Callable[[Dict[str, Any]], Any],
                   name: str = "world_agent",
                   inner_key: str = "inner_board") -> Link:
    """Make a whole GameWorld play as ONE agent inside a bigger world — "this deity is itself a player
    in a gameworld." Each turn it runs the inner world, then `derive_action(inner_board)` becomes its
    move in the outer world. Because a GameWorld is a Link and the agent/deity slots accept any Link,
    worlds nest at any depth: agent = team = world, all the way up."""
    class _WorldAgent(Link):
        def __init__(self):
            self.name = name
            self.world = world

        async def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs):
            ctx = dict(context) if context else {}
            r = await self.world.execute({"board": dict(ctx.get(inner_key, {}))})
            inner_board = (r.context or {}).get("board", {})
            ctx["action"] = derive_action(inner_board)
            ctx["_inner"] = inner_board
            return LinkResult(status=LinkStatus.SUCCESS, context=ctx)

    return _WorldAgent()


__all__ = ["GameWorld", "world_as_agent"]
