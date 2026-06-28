#!/usr/bin/env python3
"""season — the bounded epoch: transient RESETS, earned CARRIES, the standard RATCHETS. NO API.
Also proves season ∘ blackboard composes (both are Links)."""
import asyncio

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams.season import season, carry_reset_ratchet
from cave_teams.blackboard import blackboard


class Play(Link):
    """one season of activity: earn gold (transient) + xp (earned)."""
    name = "play"

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        b = dict(ctx.get("board", {}))
        b["gold"] = b.get("gold", 0) + 10
        b["xp"] = b.get("xp", 0) + 5
        ctx["board"] = b
        return LinkResult(LinkStatus.SUCCESS, ctx)


def tighten(board, n):
    b = dict(board)
    b["bar"] = b.get("bar", 1) + 1        # rarity_consensus ratchets — the standard climbs
    return b


async def main():
    advance = carry_reset_ratchet(reset_to={"gold": 0}, ratchet=tighten)
    r = await season(Play(), advance, seasons=3).execute({"board": {"bar": 1}})
    b = r.context["board"]
    assert b["gold"] == 10, b             # RESET each boundary → only the last season's earnings
    assert b["xp"] == 15, b               # CARRIED → 5 × 3 seasons
    assert b["bar"] == 3, b               # RATCHETED twice (between 3 seasons): 1 → 3
    assert len(r.context["_seasons"]) == 3
    print("  season  transient RESETS (gold=10) · earned CARRIES (xp=15) · standard RATCHETS (bar=3) ✓")

    # season ∘ blackboard (both Links)
    def mut(state, agent, action):
        s = dict(state)
        s["gold"] = s.get("gold", 0) + action.get("amount", 0)
        return s

    class Earner(Link):
        name = "earner"

        async def execute(self, context=None, **k):
            c = dict(context) if context else {}
            c["action"] = {"type": "earn", "amount": 7}
            return LinkResult(LinkStatus.SUCCESS, c)

    arena = blackboard({"earner": Earner()}, mut, rounds=1)
    r2 = await season(arena, carry_reset_ratchet(reset_to={"gold": 0}), seasons=2).execute({"board": {}})
    assert r2.context["board"]["gold"] == 7, r2.context["board"]   # +7 each season, reset between → 7
    print("  compose season ∘ blackboard (arena reset between epochs) ✓")

    print("SEASON PASS — bounded epoch: carry / reset / ratchet (the climb)")


if __name__ == "__main__":
    asyncio.run(main())
