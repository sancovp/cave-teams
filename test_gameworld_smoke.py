#!/usr/bin/env python3
"""GameWorld — a whole gameworld is now (1) a PROGRAM (one composition) and (2) a CLASS
(instantiable, data-driven from_spec, subclassable). NO API."""
import asyncio

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams.gameworld import GameWorld
from cave_teams.season import carry_reset_ratchet
from cave_teams import algebra as Alg


def econ_mutator(state, agent, action):
    """the world's execute.sh, in one function: agents earn gold."""
    s = dict(state)
    ag = dict(s.get("agents", {}))
    me = dict(ag.get(agent, {"gold": 0}))
    if action.get("type") == "earn":
        me["gold"] = me.get("gold", 0) + action.get("amount", 0)
    ag[agent] = me
    s["agents"] = ag
    return s


class Worker(Link):
    def __init__(self, name, amt):
        self.name = name
        self.amt = amt

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        ctx["action"] = {"type": "earn", "amount": self.amt}
        return LinkResult(LinkStatus.SUCCESS, ctx)


def ratchet(board, n):
    b = dict(board)
    b["bar"] = b.get("bar", 1) + 1        # the rarity standard climbs each season
    return b


# A WoS-style world AS A SUBCLASS — fixes the economy + makes gold reset per season
class SkillcraftWorld(GameWorld):
    def __init__(self, agents, seasons=2):
        super().__init__(agents, econ_mutator, deity=None,
                         advance=carry_reset_ratchet(reset_to={"agents": dict}, ratchet=ratchet),
                         rounds=1, seasons=seasons, name="skillcraft")


async def main():
    workers = {"a": Worker("a", 10), "b": Worker("b", 20)}

    # (1) a whole world is a PROGRAM — compiled from a spec, runs in one call
    world = GameWorld.from_spec(
        {"rounds": 1, "seasons": 3, "reset_to": {}, "ratchet": ratchet, "name": "w1"},
        workers, econ_mutator)
    r = await world.execute({"board": {"bar": 1}})
    board = r.context["board"]
    assert board["agents"]["b"]["gold"] == 60          # 20×3, gold carries (reset_to empty)
    assert board["bar"] == 3                            # ratcheted across 3 seasons
    assert len(r.context["_seasons"]) == 3
    print("  program  a whole gameworld ran as ONE composition (3 seasons) ✓", board["agents"])

    # (2) it's a CLASS — subclass specializes the economy (gold resets each season)
    sworld = SkillcraftWorld(workers, seasons=2)
    r2 = await sworld.execute({"board": {"bar": 1}})
    assert r2.context["board"]["agents"]["b"]["gold"] == 20   # reset each season → last season only
    print("  class    SkillcraftWorld(GameWorld) subclass specializes the world ✓")

    # (3) a GameWorld IS a Link — a whole world nests/composes
    after = await Alg.seq(world, _Tap()).execute({"board": {"bar": 1}})
    assert after.context["tapped"] == "world-ran"
    print("  compose  GameWorld nests as a Link (world ∘ next) ✓")

    print("GAMEWORLD PASS — a whole gameworld is a program, and a class")


class _Tap(Link):
    name = "tap"

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        ctx["tapped"] = "world-ran" if ctx.get("board", {}).get("bar") == 3 else "no"
        return LinkResult(LinkStatus.SUCCESS, ctx)


if __name__ == "__main__":
    asyncio.run(main())
