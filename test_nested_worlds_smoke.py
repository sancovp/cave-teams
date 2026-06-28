#!/usr/bin/env python3
"""nested worlds — "this deity is itself a player in a gameworld." A whole GameWorld plays as ONE agent
inside a bigger GameWorld. Proves worlds nest at any depth (agent = team = world). NO API."""
import asyncio

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams.gameworld import GameWorld, world_as_agent


def econ_mutator(state, agent, action):
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


def total_gold(board):
    return sum(a.get("gold", 0) for a in board.get("agents", {}).values())


async def main():
    # INNER world: two workers earn 10 + 20 over 2 seasons (gold carries) → total 60
    inner = GameWorld({"x": Worker("x", 10), "y": Worker("y", 20)}, econ_mutator, seasons=2, name="inner")

    # the inner world plays as ONE agent in the OUTER world: its total gold becomes its move
    inner_player = world_as_agent(inner, derive_action=lambda b: {"type": "earn", "amount": total_gold(b)},
                                  name="inner_world")

    # OUTER world: a normal worker + the whole inner world as a fellow player
    outer = GameWorld({"solo": Worker("solo", 5), "inner_world": inner_player}, econ_mutator, seasons=1, name="outer")
    r = await outer.execute({"board": {}})
    board = r.context["board"]

    assert board["agents"]["solo"]["gold"] == 5
    assert board["agents"]["inner_world"]["gold"] == 60     # the inner WORLD's outcome was its single move
    print("  nest    a whole GameWorld played as one agent in a bigger world ✓", board["agents"])

    # depth check — nest the outer inside a third world (3 levels deep)
    outer_player = world_as_agent(outer, derive_action=lambda b: {"type": "earn", "amount": total_gold(b)},
                                  name="outer_world")
    top = GameWorld({"top_inner": outer_player}, econ_mutator, seasons=1, name="top")
    rt = await top.execute({"board": {}})
    assert rt.context["board"]["agents"]["top_inner"]["gold"] == 65   # 60 (inner) + 5 (solo), surfaced up
    print("  depth   worlds nest 3 levels (agent = team = world, all the way up) ✓")

    print("NESTED WORLDS PASS — the deity of one world is a player in another")


if __name__ == "__main__":
    asyncio.run(main())
