#!/usr/bin/env python3
"""NPCs — agents in the world that players call via a skill and get stuff back. NO API.
A player calls a 'sage' NPC; the NPC crafts an artifact; it lands in the player's inventory.
And an NPC can be a whole GameWorld (GameMaster Heaven)."""
import asyncio

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams.blackboard import blackboard
from cave_teams.npc import npc_mutator
from cave_teams.gameworld import GameWorld


def base_econ(state, agent, action):
    """ordinary economy: agents earn gold (sync mutator — still works alongside async NPC routing)."""
    s = dict(state)
    ag = dict(s.get("agents", {}))
    me = dict(ag.get(agent, {"gold": 0}))
    if action.get("type") == "earn":
        me["gold"] = me.get("gold", 0) + action.get("amount", 0)
    ag[agent] = me
    s["agents"] = ag
    return s


class Sage(Link):
    """an NPC: crafts a skill in response to the player's ask."""
    name = "sage"

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        ask = ctx.get("ask", "")
        ctx["artifact"] = {"kind": "skill", "title": f"skill-for::{ask}", "by": "sage"}
        return LinkResult(LinkStatus.SUCCESS, ctx)


class Player(Link):
    def __init__(self, name, action):
        self.name = name
        self._action = action

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        ctx["action"] = self._action
        return LinkResult(LinkStatus.SUCCESS, ctx)


async def main():
    # a world: one player who CALLS the sage NPC, one who just earns
    npcs = {"sage": Sage()}
    mut = npc_mutator(base_econ, npcs)
    seeker = Player("seeker", {"type": "call_npc", "npc": "sage", "ask": "how to trade"})
    worker = Player("worker", {"type": "earn", "amount": 15})

    arena = blackboard({"seeker": seeker, "worker": worker}, mut, rounds=1)
    r = await arena.execute({})
    board = r.context["board"]

    # the player talked to the NPC and got an artifact in inventory
    inv = board["inventory"]["seeker"]
    assert len(inv) == 1 and inv[0]["npc"] == "sage"
    assert inv[0]["artifact"]["title"] == "skill-for::how to trade"
    assert board["agents"]["worker"]["gold"] == 15        # the base economy still runs alongside NPCs
    print("  npc     player called the sage and got a crafted skill ✓", inv[0]["artifact"]["title"])

    # unknown NPC → rejected, logged, arena survives
    bad = blackboard({"p": Player("p", {"type": "call_npc", "npc": "ghost", "ask": "x"})}, mut, rounds=1)
    rb = await bad.execute({})
    assert any(not e["ok"] and "no such NPC" in e.get("error", "") for e in rb.context["_blackboard_log"])
    print("  npc     unknown NPC rejected + logged, arena survives ✓")

    # an NPC can BE a whole GameWorld — "GameMaster Heaven": calling it runs a world
    class WorldNPC(Link):
        name = "heaven"

        def __init__(self):
            self.world = GameWorld({"w": Player("w", {"type": "earn", "amount": 99})}, base_econ, seasons=1)

        async def execute(self, context=None, **k):
            ctx = dict(context) if context else {}
            wr = await self.world.execute({"board": {}})
            ctx["artifact"] = {"kind": "world_result", "board": wr.context["board"]}
            return LinkResult(LinkStatus.SUCCESS, ctx)

    mut2 = npc_mutator(base_econ, {"heaven": WorldNPC()})
    deity = Player("deity", {"type": "call_npc", "npc": "heaven", "ask": "run a world"})
    gmh = blackboard({"deity": deity}, mut2, rounds=1)
    rg = await gmh.execute({})
    art = rg.context["board"]["inventory"]["deity"][0]["artifact"]
    assert art["board"]["agents"]["w"]["gold"] == 99      # the NPC ran a whole gameworld
    print("  npc     an NPC can be a whole GameWorld (GameMaster Heaven) ✓")

    print("NPC PASS — agents in the world, callable via a skill; an NPC can be a world")


if __name__ == "__main__":
    asyncio.run(main())
