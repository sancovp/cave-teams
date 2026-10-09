"""
worlds_features2.py — the remaining INDIVIDUAL world-system features: npc + nested worlds.
Real TOOLED coding agents (MiniMaxRuntime tools=None via AgentLink default). Reads the resulting
state. (blackboard, season, evolve already passed on tooled agents in worlds_test.py.)
NOT the complex WoS/sim composition — that comes after, on Isaac's go.
"""
import os, sys, json, asyncio, time
sys.path.insert(0, os.path.expanduser("~/repo/cave-teams"))
from cave_teams import AgentLink, blackboard
from cave_teams.npc import npc_mutator
from cave_teams.gameworld import GameWorld, world_as_agent
from cave_teams.chain_ontology import Link, LinkResult, LinkStatus

SD = os.path.dirname(os.path.abspath(__file__))
T0 = time.time()
def log(m): print(f"[{time.time()-T0:6.1f}s] {m}", flush=True)


class AsAction(Link):
    """Run a real TOOLED AgentLink, expose its text under ctx['action'] (what a blackboard reads)."""
    def __init__(self, name, agent):
        self.name = name; self._a = agent
    async def execute(self, ctx=None, **kw):
        r = await self._a.execute(dict(ctx or {}))
        c = dict(r.context or ctx or {}); c["action"] = (r.context or {}).get("output", "")
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


class PlayerCallsNPC(Link):
    """A player whose move is to CALL an NPC (the in-world agent-factory interface)."""
    def __init__(self, name, npc_name, ask):
        self.name = name; self._npc = npc_name; self._ask = ask
    async def execute(self, ctx=None, **kw):
        c = dict(ctx or {})
        c["action"] = {"type": "call_npc", "npc": self._npc, "ask": self._ask}
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


def rec(state, name, action):   # base economy: record a text move
    s = dict(state); s.setdefault("moves", []); s["moves"] = s["moves"] + [{name: str(action)[:60]}]
    return s


# ── NPC ─────────────────────────────────────────────────────────────────────
async def test_npc():
    log("NPC: a player emits call_npc → the NPC (a real tooled agent) runs → artifact into inventory")
    # a REAL tooled coding agent as the NPC; reads its input from ctx['ask']
    oracle = AgentLink("oracle", system_prompt="You are the Oracle NPC. Answer the 'ask' in ONE word.",
                       backend="minimax", input_key="ask")
    agents = {"hero": PlayerCallsNPC("hero", "oracle", "What color is the sky on a clear day?")}
    mutator = npc_mutator(rec, {"oracle": oracle})          # wrap the base economy with NPC routing
    arena = blackboard(agents, mutator, rounds=1)
    res = await arena.execute({"board": {}})
    board = res.context["board"]
    inv = board.get("inventory", {}).get("hero", [])
    ran = len(inv) == 1 and inv[0].get("npc") == "oracle" and inv[0].get("artifact")
    print("  hero inventory after calling the NPC:", inv)
    print("  applied writes:", [f"{m['agent']}:{m['ok']}" for m in res.context["_blackboard_log"]])
    return ("npc", bool(ran), {"inventory": inv})


# ── NESTED WORLDS ─────────────────────────────────────────────────────────────
async def test_nested_worlds():
    log("NESTED WORLDS: a whole GameWorld plays as ONE agent inside an outer world (agent=team=world)")
    # inner world: a minimal GameWorld (season∘blackboard) with a real tooled agent
    scribe = AsAction("scribe", AgentLink("scribe", backend="minimax",
                      system_prompt="You are the inner-world scribe. Output ONE short invented rune name."))
    inner = GameWorld(agents={"scribe": scribe}, mutator=rec, rounds=1, seasons=1, name="inner_world")
    # nest it: the inner world's result becomes its MOVE in the outer world
    def derive(inner_board):
        moves = inner_board.get("moves", [])
        return f"subworld ran; inner produced {len(moves)} move(s): {moves}"
    subworld = world_as_agent(inner, derive, name="subworld")
    # outer world: an ordinary blackboard whose 'agent' is the whole inner world
    outer = blackboard({"subworld": subworld}, rec, rounds=1)
    res = await outer.execute({"board": {}})
    board = res.context["board"]
    outer_moves = board.get("moves", [])
    nested_ran = any("subworld ran" in str(m) for m in outer_moves)
    print("  OUTER board moves (the nested world's derived move):", outer_moves)
    return ("nested_worlds", bool(nested_ran), {"outer_moves": outer_moves})


async def main():
    results = []
    for coro in (test_npc(), test_nested_worlds()):
        try:
            results.append(await coro)
        except Exception as e:
            import traceback; traceback.print_exc()
            results.append(("feature", False, {"error": f"{type(e).__name__}: {e}"}))
    print("\n" + "=" * 60 + "\nINDIVIDUAL WORLD-FEATURE TALLY (this run)")
    for name, ok, info in results:
        print(f"  {'✓ PASS' if ok else '✗ FAIL'}  {name}")
    json.dump([[n, ok, i] for n, ok, i in results], open(os.path.join(SD, "worlds2_results.json"), "w"), indent=2, default=str)

asyncio.run(main())
sys.stdout.flush()
os._exit(0)
