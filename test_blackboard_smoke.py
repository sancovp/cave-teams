#!/usr/bin/env python3
"""blackboard — the arena/gameworld topology, as a mini WoS economy. NO API.
Proves: agents propose ‖, mutator applies serially + REJECTS with kill-criteria, deity stops early,
agents read the board, and a Blackboard composes as a Link."""
import asyncio

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams import algebra as Alg
from cave_teams.blackboard import blackboard


# --- the gameworld's execute.sh, in Python: the single typed write path with kill-criteria ---
def gold_mutator(state, agent, action):
    s = dict(state)
    agents = dict(s.get("agents", {}))
    me = dict(agents.get(agent, {"gold": 0}))
    t = action.get("type")
    if t == "earn":
        me["gold"] = me.get("gold", 0) + int(action.get("amount", 0))
    elif t == "spend":
        amt = int(action.get("amount", 0))
        if me.get("gold", 0) < amt:                       # kill-criterion (like "Not enough gold")
            raise ValueError(f"{agent}: not enough gold")
        me["gold"] -= amt
    else:
        raise ValueError(f"unknown action {t!r}")
    agents[agent] = me
    s["agents"] = agents
    return s


class Proposer(Link):
    """a scripted agent — proposes actions[round]."""
    def __init__(self, name, actions):
        self.name = name
        self.actions = actions

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        rnd = ctx.get("round", 0)
        ctx["action"] = self.actions[rnd] if rnd < len(self.actions) else None
        return LinkResult(LinkStatus.SUCCESS, ctx)


class Deity(Link):
    """adjudicator — reads the board, stops the season when anyone reaches 100 gold."""
    name = "deity"

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        board = dict(ctx.get("board", {}))
        agents = board.get("agents", {})
        if any(a.get("gold", 0) >= 100 for a in agents.values()):
            board["_stop"] = True
            ctx["board"] = board
        return LinkResult(LinkStatus.SUCCESS, ctx)


async def main():
    alice = Proposer("alice", [{"type": "earn", "amount": 60}, {"type": "earn", "amount": 60}])
    bob = Proposer("bob", [{"type": "spend", "amount": 50},   # REJECTED — bob has 0 gold
                           {"type": "earn", "amount": 10}])

    arena = blackboard({"alice": alice, "bob": bob}, gold_mutator, adjudicator=Deity(), rounds=5)
    r = await arena.execute({})
    board = r.context["board"]
    log = r.context["_blackboard_log"]

    # deity stopped early: alice hit 120 (>=100) after round 1 → only 2 rounds ran (not 5)
    assert r.context["_rounds_run"] == 2, r.context["_rounds_run"]
    assert board["agents"]["alice"]["gold"] == 120
    assert board["agents"]["bob"]["gold"] == 10              # r0 spend rejected, r1 earn applied
    print("  arena   propose ‖ → mutate → adjudicate → rounds; deity stopped at 100 ✓", board["agents"])

    # the rejected action was logged, not crashed (kill-criterion survived)
    rejected = [e for e in log if not e["ok"]]
    assert len(rejected) == 1 and rejected[0]["agent"] == "bob" and "not enough gold" in rejected[0]["error"]
    print("  gate    invalid action REJECTED + logged, arena survives ✓", rejected[0]["error"])

    # a Blackboard IS a Link — it composes
    after = await Alg.seq(arena, _Tap()).execute({})
    assert after.context["tapped"] == "board-seen"
    print("  compose blackboard ∘ next  (arena is a Link) ✓")

    print("BLACKBOARD PASS — stigmergy arena: N agents ↔ shared state ↔ deity, over rounds")


class _Tap(Link):
    name = "tap"

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        ctx["tapped"] = "board-seen" if "board" in ctx else "no-board"
        return LinkResult(LinkStatus.SUCCESS, ctx)


if __name__ == "__main__":
    asyncio.run(main())
